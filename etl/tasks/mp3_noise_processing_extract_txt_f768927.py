"""
    1). Audio Validation
    ==========================================================================
    First stage of the audio processing pipeline. Cheaply rejects bad input
    before it reaches expensive downstream steps (noise reduction, VAD,
    segmentation, Whisper transcription, LLM processing).

    Checks performed:
      1. File integrity      - exists, non-empty, decodable
      2. Format / codec       - confirms it's actually MP3 (not a renamed file)
      3. Duration bounds      - rejects 0-length or absurdly long files
      4. Sample rate / channels - flags audio below Whisper's useful range
      5. Loudness / silence    - rejects files that are silent or near-silent
      6. Clipping             - flags heavily distorted audio

    Requires: pydub, mutagen, ffmpeg (system binary)
        pip install pydub mutagen --break-system-packages

    2). Noise Reduction
    ==========================================================================
    Second stage of the audio processing pipeline. Takes audio that contains
    both background noise and speech, and outputs audio where the noise is
    suppressed while the voice is preserved.

    Approach: spectral gating noise reduction (via the `noisereduce` library).
    It estimates what the "noise" sounds like (either from a quiet section of
    the file, or statistically across the whole clip) and subtracts that
    noise profile from the signal, frequency-band by frequency-band — leaving
    speech, which has a different spectral pattern, largely intact.

    Two modes:
      - stationary=True  : assumes noise is constant throughout (fans, hiss,
                            hum). Faster, works well for steady background noise.
      - stationary=False : adapts to noise that changes over time (traffic,
                            crowd chatter). Slower, more robust for real-world
                            recordings.

    Requires: noisereduce, soundfile, numpy, pydub, ffmpeg
        pip install noisereduce soundfile numpy pydub --break-system-packages


    3). Voice Activity Detection (VAD)
    ==========================================================================
    Third stage of the audio processing pipeline. Takes (ideally already
    noise-reduced) audio and identifies which portions actually contain
    speech, discarding everything else:
      - Remove silence
      - Remove empty segments
      - Keep speech only

    Approach: WebRTC VAD (`webrtcvad`) — a lightweight, frame-based speech /
    non-speech classifier. It scores short fixed-length frames (10/20/30ms)
    as speech or non-speech. Raw frame-level decisions are noisy on their own
    (a single frame can flicker speech/non-speech mid-word), so this module
    adds three layers on top of the raw classifier:

      1. Merge nearby speech frames into segments, bridging small gaps
         (e.g. a brief pause between words shouldn't split one utterance
         into two segments).
      2. Pad each segment's start/end slightly, since VAD often clips the
         very start/end of words if applied too tightly.
      3. Drop segments that are too short to be real speech (likely VAD
         false positives from noise clicks, breath sounds, etc.)

    Requires: webrtcvad, pydub, numpy, ffmpeg
        pip install webrtcvad pydub numpy --break-system-packages


    4). Audio Segmentation
    ==================================================================
    Fourth stage of the audio processing pipeline. Takes the ORIGINAL
    (noise-reduced) audio plus the speech segment boundaries already found
    by VAD, and groups them into Whisper-sized chunks.

    IMPORTANT: this stage must operate on VAD's *segment boundaries*
    (start_ms/end_ms in the original timeline), not on VAD's concatenated
    speech-only output file. Once VAD strips silence and concatenates
    segments together, the natural pause points — the only safe place to
    cut without slicing through a word — are gone. Segmentation re-derives
    safe cut points from the original segment list instead.

    Two situations handled:
      1. Normal case: greedily group consecutive speech segments into a
         chunk until adding the next one would exceed MAX_SEGMENT_DURATION_MS.
         The chunk boundary always falls in a silence gap between segments.
      2. Oversized segment: if a single VAD segment is itself longer than
         MAX_SEGMENT_DURATION_MS (e.g. one long continuous utterance with no
         detected pause), there's no silence to cut at. This module falls
         back to finding the quietest point within that segment and splitting
         there — still imperfect, but better than an arbitrary cut.

    Requires: pydub, numpy, ffmpeg
        pip install pydub numpy --break-system-packages

"""

from __future__ import annotations
import threading
import time

import json
import shutil
import tempfile
from pathlib import Path

import os
from dotenv import load_dotenv  # To load environment variables, such as API keys
from dataclasses import dataclass, field
from enum import Enum
# audio processing
from pydub import AudioSegment
from mutagen import File as MutagenFile, MutagenError
import numpy as np
import noisereduce as nr
import soundfile as sf
import webrtcvad
import torch
import whisper
import re
# job status
from etl.util.job_state_client import JobStateClient
from etl.util.minio_client import MinioClient
from etl.util.logging_config import get_logger

# ------------------------------------------------------------------------------
# Logging Configuration
# ------------------------------------------------------------------------------
logger = get_logger(__name__)
# ------------------------------------------------------------------------------
# Load environment variables
# ------------------------------------------------------------------------------
load_dotenv()
# ------------------------------------------------------------------------------
# ENV DATA LOAD
# ------------------------------------------------------------------------------
etl_event_url = os.getenv("ETL_EVENT_URL")
minio_bucket = os.getenv("MINIO_BUCKET_NAME", "etl-bucket")
# ------------------------------------------------------------------------------
# Dependencies
# ------------------------------------------------------------------------------
job_state_client = JobStateClient(etl_event_url)
minio_client = MinioClient()
# Audio extensions this pipeline accepts as input.
AUDIO_EXTENSIONS = (".mp3", ".m4a")
# ---------------------------------------------------------------------------
# Config — tune these for your use case
# ---------------------------------------------------------------------------
@dataclass
class ValidationConfig:
    MIN_DURATION_SEC = 0.5
    MAX_DURATION_SEC = 4 * 60 * 60          # 4 hours
    MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB

    MIN_SAMPLE_RATE_HZ = 16_000              # Whisper's native rate
    MAX_CHANNELS = 2

    SILENCE_DBFS_THRESHOLD = -50.0           # below this = "silent"
    SILENCE_MAX_RATIO = 0.98                 # reject if >98% of file is silent

    CLIPPING_SAMPLE_THRESHOLD = 0.999        # near full-scale amplitude
    CLIPPING_WARN_RATIO = 0.01               # warn if >1% of samples clip
    CLIPPING_FAIL_RATIO = 0.50               # fail if >50% of samples clip (whole file distorted)

@dataclass
class NoiseReductionConfig:
    # stationary=True works best for constant background noise (hiss, hum, fan/AC
    # noise). Set to False if your noise changes character over time (traffic,
    # crowd chatter, intermittent clatter) — adaptive mode handles that better,
    # but is less aggressive on steady noise. Test both against your real data.
    STATIONARY: bool = True
    PROP_DECREASE: float = 1.0        # how aggressively to reduce noise (0-1)
    TARGET_SAMPLE_RATE: int = 16_000  # Whisper's native rate; also speeds up processing

@dataclass
class VADConfig:
    AGGRESSIVENESS: int = 2  # 0-3; higher = more aggressive at filtering non-speech
    FRAME_DURATION_MS: int = 30  # webrtcvad only supports 10, 20, or 30
    SAMPLE_RATE: int = 16_000 # webrtcvad only supports 8000, 16000, 32000, 48000

    PADDING_MS: int = 200 # pad before/after each speech segment (avoids clipping words)
    MIN_SILENCE_GAP_MS: int = 300 # merge speech segments separated by less than this
    MIN_SPEECH_DURATION_MS: int = 250  # discard segments shorter than this (likely false positives)

@dataclass
class SegmentationConfig:
    MAX_CHUNK_DURATION_MS: int = 30_000     # Whisper performs best on chunks up to ~30s
    TARGET_CHUNK_DURATION_MS: int = 25_000  # close a chunk a bit before the hard max
    MIN_CHUNK_DURATION_MS: int = 1_500      # avoid emitting near-empty trailing fragments

@dataclass
class WhisperConfig:
    # NOTE: openai-whisper downloads model weights on first use from
    # openaipublic.azureedge.net. If your environment has restricted
    # egress, pre-download the model weights or whitelist that domain.
    MODEL_SIZE: str = "small"     # tiny/base/small/medium/large — bigger = more accurate, slower
    LANGUAGE: str = "en"          # set None to let Whisper auto-detect (slightly slower, less reliable)
    # Whisper's own fallback ladder (its library default). A single fixed value here
    # (e.g. 0.0) disables Whisper's built-in retry: normally, when a decode looks like
    # a repetition/hallucination loop (compression_ratio > compression_ratio_threshold,
    # or avg_logprob < logprob_threshold), Whisper automatically re-decodes at the next
    # temperature in this tuple instead of returning the looping text as-is. Pinning it
    # to a single float silently disabled that safety net, which is what caused chunks
    # to come back with a phrase repeated dozens of times ("the same amount of..." etc).
    TEMPERATURE: tuple = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
    CONDITION_ON_PREVIOUS_TEXT: bool = False  # False avoids error compounding across independent chunks

@dataclass
class TextCleanupConfig:
    # Deliberately excludes ambiguous words like "like", "actually", "basically" —
    # these can carry real clinical meaning ("symptoms like dizziness") and
    # stripping them risks silently deleting meaning from patient information.
    FILLER_WORDS: tuple = (
        "um", "uh", "uhh", "umm", "erm", "er",
        "you know", "i mean", "kind of", "sort of",
    )


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
class ValidationStatus(str, Enum):
    PASS = "pass"
    WARN = "warn"     # passable, but downstream steps should know
    FAIL = "fail"

@dataclass
class ValidationIssue:
    code: str
    message: str
    severity: ValidationStatus

@dataclass
class AudioMetadata:
    duration_sec: float | None = None
    sample_rate_hz: int | None = None
    channels: int | None = None
    bitrate_kbps: int | None = None
    file_size_bytes: int | None = None
    mean_dbfs: float | None = None
    silence_ratio: float | None = None
    clipping_ratio: float | None = None

@dataclass
class ValidationResult:
    status: ValidationStatus
    metadata: AudioMetadata = field(default_factory=AudioMetadata)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status != ValidationStatus.FAIL

    def add(self, code: str, message: str, severity: ValidationStatus) -> None:
        self.issues.append(ValidationIssue(code, message, severity))
        # Escalate overall status — FAIL > WARN > PASS
        if severity == ValidationStatus.FAIL:
            self.status = ValidationStatus.FAIL
        elif severity == ValidationStatus.WARN and self.status == ValidationStatus.PASS:
            self.status = ValidationStatus.WARN

@dataclass
class NoiseReductionResult:
    output_path: str
    input_rms_db: float  # loudness of the ORIGINAL audio, before noise reduction
    output_rms_db: float  # loudness of the CLEANED audio, after noise reduction
    noise_reduced_db: float  # the difference: input_rms_db - output_rms_db
    note: str = (
        "Loudness drop alone doesn't prove noise was removed selectively — "
        "verify with a before/after listen, or compare energy during speech "
        "vs. silent gaps if you have VAD timestamps available."
    )

@dataclass
class SpeechSegment:
    start_ms: int
    end_ms: int

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

@dataclass
class VADResult:
    segments: list[SpeechSegment]
    output_path: str
    total_duration_ms: float
    speech_duration_ms: float
    silence_removed_ms: float
    speech_ratio: float  # fraction of original audio kept as speech

@dataclass
class AudioChunk:
    start_ms: int
    end_ms: int
    forced_split: bool = False  # True if this chunk's boundary cut through live speech
                                 # (happens only when a single VAD segment alone exceeds
                                 # MAX_CHUNK_DURATION_MS, leaving no silence gap to cut at)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms

@dataclass
class SegmentationResult:
    chunks: list[AudioChunk]
    output_paths: list[str]
    total_duration_ms: float
    forced_split_count: int  # how many chunks had to cut mid-speech (quality warning signal)

@dataclass
class TranscriptSegment:
    chunk_index: int
    start_ms: int
    end_ms: int
    raw_text: str
    avg_logprob: float | None = None  # Whisper's confidence signal; lower (more negative) = less confident
    no_speech_prob: float | None = None  # probability the chunk had no real speech at all

@dataclass
class TranscriptionResult:
    segments: list[TranscriptSegment]
    full_raw_text: str  # naive concatenation, BEFORE cleanup — kept for audit/debugging
    low_confidence_count: int  # segments worth a human review pass

@dataclass
class CleanupResult:
    cleaned_text: str
    cleaned_segments: list[str]  # per-chunk cleaned text, same order as input
    fillers_removed_count: int

@dataclass
class TimestampedSegment:
    start_ms: int
    end_ms: int
    text: str

@dataclass
class AudioTranscriptOutput:
    cleaned_text: str  # the whole transcript merged into one block, as before
    segments: list[TimestampedSegment]  # per-chunk cleaned text with timing, empty-text chunks omitted

# ---------------------------------------------------------------------------
# Validation function
# ---------------------------------------------------------------------------
def validate_audio(
    task_payload,
    filepath: str,
    config: ValidationConfig = ValidationConfig(),
) -> ValidationResult:
    """
    Run all validation checks on an MP3 file.
    Returns a ValidationResult with overall status, parsed metadata,
    and a list of any issues found.
    """

    logger.info("Validating audio file: %s", filepath)
    job_audit_log(task_payload, f"Validating audio file: {filepath}")

    result = ValidationResult(status=ValidationStatus.PASS)

    def add_issue(
        code: str,
        message: str,
        severity: ValidationStatus,
        return_result: bool = False,
    ):
        log_fn = logger.error if severity == ValidationStatus.FAIL else logger.warning

        log_fn(message)
        job_audit_log(task_payload, message)
        result.add(code, message, severity)

        return result if return_result else None

    # ----------------------------------------------------------------------
    # 1. File Integrity
    # ----------------------------------------------------------------------
    if not os.path.isfile(filepath):
        return add_issue(
            "FILE_NOT_FOUND",
            f"No file at path: {filepath}",
            ValidationStatus.FAIL,
            return_result=True,
        )

    file_size = os.path.getsize(filepath)
    result.metadata.file_size_bytes = file_size

    logger.info("File size: %.2f MB", file_size / 1e6)
    job_audit_log(task_payload, f"File size: {file_size / 1e6:.2f} MB")

    if file_size == 0:
        return add_issue(
            "EMPTY_FILE",
            f"File is empty (0 bytes): {filepath}",
            ValidationStatus.FAIL,
            return_result=True,
        )

    if file_size > config.MAX_FILE_SIZE_BYTES:
        return add_issue(
            "FILE_TOO_LARGE",
            (
                f"File is {file_size / 1e6:.1f} MB, exceeds limit of "
                f"{config.MAX_FILE_SIZE_BYTES / 1e6:.0f} MB"
            ),
            ValidationStatus.FAIL,
            return_result=True,
        )

    # ----------------------------------------------------------------------
    # 2. Audio Tag Validation (MP3 or M4A)
    # ----------------------------------------------------------------------
    try:
        audio_info = MutagenFile(filepath)
    except MutagenError:
        audio_info = None

    if audio_info is None or audio_info.info is None:
        return add_issue(
            "INVALID_AUDIO_FILE",
            f"File is not a valid MP3/M4A or is corrupted: {filepath}",
            ValidationStatus.FAIL,
            return_result=True,
        )

    bitrate = getattr(audio_info.info, "bitrate", None)
    result.metadata.bitrate_kbps = round(bitrate / 1000) if bitrate else None
    result.metadata.sample_rate_hz = audio_info.info.sample_rate
    result.metadata.channels = audio_info.info.channels

    logger.info(
        "Audio info: bitrate=%s kbps, sample_rate=%s Hz, channels=%s",
        result.metadata.bitrate_kbps,
        result.metadata.sample_rate_hz,
        result.metadata.channels,
    )
    job_audit_log(
        task_payload,
        f"Audio info: bitrate={result.metadata.bitrate_kbps} kbps, "
        f"sample_rate={result.metadata.sample_rate_hz} Hz, "
        f"channels={result.metadata.channels}",
    )

    # ----------------------------------------------------------------------
    # 3. Decode Validation
    # ----------------------------------------------------------------------
    try:
        audio = AudioSegment.from_file(filepath)
    except Exception as e:
        return add_issue(
            "DECODE_FAILED",
            f"File {filepath} ffmpeg/pydub could not decode file: {e}",
            ValidationStatus.FAIL,
            return_result=True,
        )

    duration_sec = len(audio) / 1000.0
    result.metadata.duration_sec = duration_sec

    # ----------------------------------------------------------------------
    # 4. Duration Validation
    # ----------------------------------------------------------------------
    if duration_sec < config.MIN_DURATION_SEC:
        return add_issue(
            "DURATION_TOO_SHORT",
            f"Duration {duration_sec:.2f}s is below minimum {config.MIN_DURATION_SEC}s",
            ValidationStatus.FAIL,
            return_result=True,
        )

    if duration_sec > config.MAX_DURATION_SEC:
        return add_issue(
            "DURATION_TOO_LONG",
            (
                f"Duration {duration_sec / 3600:.2f}h exceeds maximum "
                f"{config.MAX_DURATION_SEC / 3600:.0f}h"
            ),
            ValidationStatus.FAIL,
            return_result=True,
        )

    # ----------------------------------------------------------------------
    # 5. Sample Rate / Channels
    # ----------------------------------------------------------------------
    if result.metadata.sample_rate_hz < config.MIN_SAMPLE_RATE_HZ:
        add_issue(
            "LOW_SAMPLE_RATE",
            (
                f"Sample rate {result.metadata.sample_rate_hz} Hz is below "
                f"recommended {config.MIN_SAMPLE_RATE_HZ} Hz "
                f"for transcription quality"
            ),
            ValidationStatus.WARN,
        )

    if result.metadata.channels > config.MAX_CHANNELS:
        add_issue(
            "UNEXPECTED_CHANNEL_COUNT",
            f"Found {result.metadata.channels} channels, expected mono/stereo",
            ValidationStatus.WARN,
        )

    # ----------------------------------------------------------------------
    # 6. Silence Detection
    # ----------------------------------------------------------------------
    mean_dbfs = audio.dBFS
    result.metadata.mean_dbfs = (
        mean_dbfs if mean_dbfs != float("-inf") else None
    )

    silence_ratio = estimate_silence_ratio(
        task_payload,
        audio,
        config.SILENCE_DBFS_THRESHOLD,
    )
    result.metadata.silence_ratio = silence_ratio

    if silence_ratio >= config.SILENCE_MAX_RATIO:
        return add_issue(
            "MOSTLY_SILENT",
            (
                f"{silence_ratio * 100:.1f}% of the file is below "
                f"{config.SILENCE_DBFS_THRESHOLD} dBFS — "
                "likely silent or empty"
            ),
            ValidationStatus.FAIL,
            return_result=True,
        )

    # ----------------------------------------------------------------------
    # 7. Clipping Detection
    # ----------------------------------------------------------------------
    clipping_ratio = estimate_clipping_ratio(
        task_payload,
        audio,
        config.CLIPPING_SAMPLE_THRESHOLD,
    )
    result.metadata.clipping_ratio = clipping_ratio

    if clipping_ratio > config.CLIPPING_FAIL_RATIO:
        return add_issue(
            "CLIPPING_DETECTED",
            (
                f"{clipping_ratio * 100:.2f}% of samples are clipped — "
                "audio is heavily distorted throughout"
            ),
            ValidationStatus.FAIL,
            return_result=True,
        )

    if clipping_ratio > config.CLIPPING_WARN_RATIO:
        add_issue(
            "CLIPPING_DETECTED",
            (
                f"{clipping_ratio * 100:.2f}% of samples are clipped — "
                "audio may be distorted"
            ),
            ValidationStatus.WARN,
        )

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def estimate_silence_ratio(
    task_payload,
    audio: AudioSegment,
    dbfs_threshold: float,
    window_ms: int = 100) -> float:
    """
        Fraction of fixed-size windows whose loudness falls below threshold
    """
    logger.info("Estimating silence ratio with threshold %.1f dBFS and window size %d ms", dbfs_threshold, window_ms)
    job_audit_log(task_payload, f"Estimating silence ratio with threshold {dbfs_threshold:.1f} dBFS and window size {window_ms} ms")
    total_windows = max(1, len(audio) // window_ms)
    silent_windows = 0

    for i in range(total_windows):
        chunk = audio[i * window_ms: (i + 1) * window_ms]
        if chunk.dBFS == float("-inf") or chunk.dBFS < dbfs_threshold:
            silent_windows += 1

    return silent_windows / total_windows

def estimate_clipping_ratio(
    task_payload,
    audio: AudioSegment,
    sample_threshold: float) -> float:
    """
        Fraction of samples sitting at or near full-scale amplitude (clipped).
    """
    logger.info("Estimating clipping ratio with sample threshold %.3f", sample_threshold)
    job_audit_log(task_payload, f"Estimating clipping ratio with sample threshold {sample_threshold:.3f}")
    samples = audio.get_array_of_samples()
    if not samples:
        return 0.0

    max_possible = 2 ** (8 * audio.sample_width - 1) - 1
    cutoff = sample_threshold * max_possible

    clipped = sum(1 for s in samples if abs(s) >= cutoff)
    return clipped / len(samples)

# ---------------------------------------------------------------------------
# Audio helpers
# ---------------------------------------------------------------------------
def ensure_parent_dir(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

def load_audio_segment(input_path, sample_rate=None, channels=None, sample_width=None):
    audio = AudioSegment.from_file(input_path)
    if channels is not None:
        audio = audio.set_channels(channels)
    if sample_rate is not None:
        audio = audio.set_frame_rate(sample_rate)
    if sample_width is not None:
        audio = audio.set_sample_width(sample_width)
    return audio

def audio_segment_to_float32(audio: AudioSegment) -> np.ndarray:
    samples = np.array(audio.get_array_of_samples()).astype(np.float32)
    samples /= np.iinfo(audio.array_type).max
    return samples

def extract_speech_segments(raw_pcm, config, total_duration_ms):
    frame_flags = classify_frames(raw_pcm, config)
    raw_segments_ms = frames_to_segments_ms(frame_flags, config.FRAME_DURATION_MS)
    merged = merge_close_segments(raw_segments_ms, config.MIN_SILENCE_GAP_MS)
    padded = pad_and_filter(merged, config, total_duration_ms)
    return merge_overlapping(padded)

# ---------------------------------------------------------------------------
# Noise reduction
# ---------------------------------------------------------------------------
def reduce_noise(
    task_payload,
    input_file_path: str,
    output_file_path: str,
    config: NoiseReductionConfig = NoiseReductionConfig()) -> NoiseReductionResult:
    """
    Load a noisy audio file, suppress background noise, keep the voice,
    and write the cleaned result to output_path.
    """
    logger.info("Reducing noise for file: %s", input_file_path)
    job_audit_log(task_payload, f"Reducing noise for file: {input_file_path}")

    # --- Load and normalize format -----------------------------------------
    audio = load_audio_segment(
        input_file_path,
        sample_rate=config.TARGET_SAMPLE_RATE,
        channels=1,
    )
    samples = audio_segment_to_float32(audio)
    input_rms_db = rms_dbfs(samples)
    logger.info(f"Input RMS DB: {input_rms_db}")
    job_audit_log(task_payload, f"Input RMS loudness: {input_rms_db:.2f} dBFS")

    # --- Run spectral gating noise reduction --------------------------------
    cleaned = nr.reduce_noise(
        y=samples,
        sr=config.TARGET_SAMPLE_RATE,
        stationary=config.STATIONARY,
        prop_decrease=config.PROP_DECREASE,
    )
    output_rms_db = rms_dbfs(cleaned)
    logger.info(f"Output RMS DB: {output_rms_db}")
    job_audit_log(task_payload, f"Output RMS loudness: {output_rms_db:.2f} dBFS")

    # --- Write result --------------------------------------------------------
    output_file_path = ensure_parent_dir(output_file_path)
    logger.info(f"Output file: {output_file_path}")
    job_audit_log(task_payload, f"Writing cleaned audio to: {output_file_path}")
    sf.write(output_file_path, cleaned, config.TARGET_SAMPLE_RATE)
    return NoiseReductionResult(
        output_path=str(output_file_path),
        input_rms_db=input_rms_db,
        output_rms_db=output_rms_db,
        noise_reduced_db=input_rms_db - output_rms_db,
    )

def rms_dbfs(samples: np.ndarray) -> float:
    """
        Root-mean-square loudness in dBFS, for before/after comparison.
    """
    rms = np.sqrt(np.mean(samples.astype(np.float64) ** 2))
    if rms <= 0:
        return float("-inf")
    return 20 * np.log10(rms)

# ---------------------------------------------------------------------------
# Voice Activity Detection (VAD)
# output_path from the noise will be input_path for detect voice activity
# ---------------------------------------------------------------------------
def detect_voice_activity(
    task_payload,
    input_path,
    output_path,
    config=VADConfig()) -> VADResult:
    """
        Detect speech segments in an audio file using WebRTC VAD, and export only the speech portions to a new file.
        Returns a VADResult with the detected speech segments and statistics.
    """
    logger.info(f"Detecting voice activity for file: {input_path}")
    job_audit_log(task_payload, f"Detecting voice activity for file: {input_path}")

    audio = load_audio_segment(
        input_path,
        sample_rate=config.SAMPLE_RATE,
        channels=1,
        sample_width=2,
    )
    raw_pcm = audio.raw_data
    total_duration_ms = len(audio)
    logger.info(f"Total duration: {total_duration_ms}")
    job_audit_log(task_payload, f"Total duration: {total_duration_ms}")

    final_segments = extract_speech_segments(raw_pcm, config, total_duration_ms)
    logger.info(f"Final segments: {final_segments}")
    job_audit_log(task_payload, f"Final segments: {final_segments}")

    output_path = ensure_parent_dir(output_path)
    export_speech_only(audio, final_segments, output_path)

    speech_duration_ms = sum(s.duration_ms for s in final_segments)

    return VADResult(
        segments=final_segments, output_path=output_path,
        total_duration_ms=total_duration_ms, speech_duration_ms=speech_duration_ms,
        silence_removed_ms=total_duration_ms - speech_duration_ms,
        speech_ratio=(speech_duration_ms / total_duration_ms) if total_duration_ms > 0 else 0.0,
    )

def classify_frames(raw_pcm, config):
    """
        Classify each frame of raw PCM audio as speech or non-speech using WebRTC VAD.
    """
    vad = webrtcvad.Vad(config.AGGRESSIVENESS)
    frame_bytes = int(config.SAMPLE_RATE * (config.FRAME_DURATION_MS / 1000) * 2)
    flags = []
    for i in range(0, len(raw_pcm) - frame_bytes + 1, frame_bytes):
        flags.append(vad.is_speech(raw_pcm[i:i + frame_bytes], config.SAMPLE_RATE))
    return flags

def frames_to_segments_ms(flags, frame_duration_ms):
    """
        Convert a list of boolean speech flags into a list of (start_ms, end_ms)
    """
    segments, in_speech, start_frame = [], False, 0
    for i, is_speech in enumerate(flags):
        if is_speech and not in_speech:
            start_frame, in_speech = i, True
        elif not is_speech and in_speech:
            segments.append((start_frame * frame_duration_ms, i * frame_duration_ms))
            in_speech = False
    if in_speech:
        segments.append((start_frame * frame_duration_ms, len(flags) * frame_duration_ms))
    return segments

def merge_close_segments(segments, min_gap_ms):
    """
        Merge speech segments that are separated by less than min_gap_ms.
    """
    merged = []
    for start, end in segments:
        if merged and start - merged[-1][1] <= min_gap_ms:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return merged

def pad_and_filter(segments, config, total_duration_ms):
    """
        Pad each speech segment by a fixed amount and filter out segments that are too short.
    """
    result = []
    for start, end in segments:
        if (end - start) < config.MIN_SPEECH_DURATION_MS:
            continue
        padded_start = max(0, start - config.PADDING_MS)
        padded_end = min(int(total_duration_ms), end + config.PADDING_MS)
        result.append(SpeechSegment(padded_start, padded_end))
    return result

def merge_overlapping(segments):
    """
        Merge overlapping or adjacent speech segments into single segments.
    """
    if not segments:
        return []
    segments = sorted(segments, key=lambda s: s.start_ms)
    merged = [segments[0]]
    for seg in segments[1:]:
        if seg.start_ms <= merged[-1].end_ms:
            merged[-1].end_ms = max(merged[-1].end_ms, seg.end_ms)
        else:
            merged.append(seg)
    return merged

def export_speech_only(audio, segments, output_path):
    """
        Export speech from audio and save to output_path, discarding non-speech segments.
    """
    speech_audio = AudioSegment.empty()
    for seg in segments:
        speech_audio += audio[seg.start_ms:seg.end_ms]
    speech_audio.export(output_path, format="wav")

# ---------------------------------------------------------------------------
# Audio Segmentation
# input_path here should be the NOISE-REDUCED audio (result.output_path from
# reduce_noise), and speech_segments should be result.segments from
# detect_voice_activity — i.e. the ORIGINAL-timeline segment boundaries, NOT
# VAD's concatenated speech-only output file. Concatenation destroys the
# silence gaps that segmentation relies on as safe (non-word-cutting) split
# points, so segmentation must re-derive chunks from the original boundaries.
# ---------------------------------------------------------------------------
def segment_audio(
    task_payload,
    input_path,
    speech_segments,
    output_dir,
    config=SegmentationConfig()) -> SegmentationResult:
    """
        Group VAD speech segments into Whisper-sized chunks and export each
        chunk as its own audio file, sliced from the original (noise-reduced)
        audio so that splits land in real silence gaps wherever possible.
    """
    logger.info(f"Segmenting audio for file: {input_path}")
    job_audit_log(task_payload, f"Segmenting audio for file: {input_path}")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    audio = load_audio_segment(input_path)
    total_duration_ms = len(audio)
    logger.info(f"Total duration: {total_duration_ms}")
    job_audit_log(task_payload, f"Total duration: {total_duration_ms}")

    segs = sorted([(s.start_ms, s.end_ms) for s in speech_segments], key=lambda s: s[0])
    chunks = group_segments_into_chunks(segs, config)
    logger.info(f"Chunks created: {len(chunks)}")
    job_audit_log(task_payload, f"Chunks created: {len(chunks)}")

    output_paths = []
    for i, chunk in enumerate(chunks):
        out_path = output_dir / f"chunk_{i:03d}.wav"
        audio[chunk.start_ms:chunk.end_ms].export(out_path, format="wav")
        output_paths.append(str(out_path))

    forced_count = sum(1 for c in chunks if c.forced_split)
    if forced_count:
        logger.warning(
            f"{forced_count} chunk(s) had to be force-split mid-speech "
            f"(a single VAD segment exceeded MAX_CHUNK_DURATION_MS with no "
            f"silence gap available) — transcription quality may suffer at "
            f"those boundaries"
        )
        job_audit_log(task_payload, f"{forced_count} chunk(s) force-split mid-speech")

    return SegmentationResult(
        chunks=chunks,
        output_paths=output_paths,
        total_duration_ms=total_duration_ms,
        forced_split_count=forced_count,
    )

def group_segments_into_chunks(segs, config):
    """
        Greedily pack speech segments into chunks. A chunk's boundary is
        always the gap between two segments (a safe, silent cut point)
        UNLESS a single segment itself exceeds MAX_CHUNK_DURATION_MS, in
        which case that one segment gets force-split internally.
    """
    chunks = []
    current_start = None
    current_end = None

    def flush():
        nonlocal current_start, current_end
        if current_start is not None and (current_end - current_start) >= config.MIN_CHUNK_DURATION_MS:
            chunks.append(AudioChunk(current_start, current_end))
        current_start, current_end = None, None

    for seg_start, seg_end in segs:
        seg_duration = seg_end - seg_start

        if seg_duration > config.MAX_CHUNK_DURATION_MS:
            # This single segment alone is too long — flush whatever chunk
            # we were building, then force-split this oversized segment on
            # its own since there's no silence gap available to cut at.
            flush()
            chunks.extend(force_split_segment(seg_start, seg_end, config))
            continue

        if current_start is None:
            current_start, current_end = seg_start, seg_end
            continue

        # Would adding this segment overshoot the max?
        if (seg_end - current_start) > config.MAX_CHUNK_DURATION_MS:
            flush()
            current_start, current_end = seg_start, seg_end
        else:
            current_end = seg_end
            # Once we've reached the target duration, prefer to close the
            # chunk here at this safe (silence) boundary rather than
            # packing in more and risking overshoot later.
            if (current_end - current_start) >= config.TARGET_CHUNK_DURATION_MS:
                flush()

    flush()
    return chunks

def force_split_segment(start_ms, end_ms, config):
    """
        Split a single oversized speech segment (no internal silence gap
        available) into pieces no longer than MAX_CHUNK_DURATION_MS. Marks
        each resulting chunk as forced_split=True so downstream consumers
        know transcription quality may suffer at that boundary.

        If the final remainder piece would be smaller than
        MIN_CHUNK_DURATION_MS, it's merged into the previous piece instead
        of emitted as its own tiny, low-value chunk.
    """
    pieces = []
    cursor = start_ms
    while end_ms - cursor > config.MAX_CHUNK_DURATION_MS:
        piece_end = cursor + config.MAX_CHUNK_DURATION_MS
        pieces.append(AudioChunk(cursor, piece_end, forced_split=True))
        cursor = piece_end

    remainder = end_ms - cursor
    if pieces and remainder < config.MIN_CHUNK_DURATION_MS:
        pieces[-1].end_ms = end_ms
    else:
        pieces.append(AudioChunk(cursor, end_ms, forced_split=(cursor != start_ms)))

    return pieces

# ---------------------------------------------------------------------------
# Speech-to-Text (Whisper)
# chunk_paths/chunks here should be SegmentationResult.output_paths and
# SegmentationResult.chunks — one Whisper call per chunk, run independently
# (CONDITION_ON_PREVIOUS_TEXT=False) so a bad transcription in one chunk
# can't compound errors into the next.
# ---------------------------------------------------------------------------

# Loaded once per process — model weights are sizeable; avoid reloading per file.
_whisper_model = None
_whisper_device = None
# openai-whisper's decode loop keeps its KV-cache as per-call mutable state on the model's
# own attention modules (via forward hooks keyed by module identity, not by request) -- it was
# never made safe for two .transcribe() calls to run concurrently against the same model
# instance. audio_extract_service.py handles requests on a thread pool, so without this lock,
# two audio files transcribing at the same time corrupt each other's KV-cache and crash with
# something like "KeyError: Linear(...)" or "cannot reshape tensor of 0 elements" -- neither
# of which has anything to do with the actual audio content of either request.
_whisper_transcribe_lock = threading.Lock()

def get_whisper_model(config: WhisperConfig = WhisperConfig()):
    global _whisper_model, _whisper_device
    if _whisper_model is None:
        # mps = Apple Silicon GPU (PyTorch's Metal backend). Only ever available when this
        # process runs natively on macOS -- a Docker container on Mac runs inside a Linux VM
        # with no path to Metal, so torch.backends.mps.is_available() is always False there
        # even on Apple Silicon hardware. fp16 stays off for mps (see the fp16= call below),
        # same as cpu -- openai-whisper's fp16 path is CUDA-specific and unstable on MPS.
        if torch.cuda.is_available():
            _whisper_device = "cuda"
        elif torch.backends.mps.is_available():
            _whisper_device = "mps"
        else:
            _whisper_device = "cpu"
        logger.info(f"Loading Whisper model: {config.MODEL_SIZE} (device={_whisper_device})")
        _whisper_model = whisper.load_model(config.MODEL_SIZE, device=_whisper_device)
    return _whisper_model

def transcribe_chunks(
    task_payload,
    chunk_paths,
    chunks,
    config=WhisperConfig()) -> TranscriptionResult:
    """
        Transcribe each segmented audio chunk independently using Whisper.
        chunk_paths and chunks must be the same length and in the same
        order (i.e. SegmentationResult.output_paths and .chunks).
    """
    logger.info(f"Transcribing {len(chunk_paths)} chunk(s)")
    job_audit_log(task_payload, f"Transcribing {len(chunk_paths)} chunk(s)")

    model = get_whisper_model(config)
    segments = []
    low_confidence_count = 0

    for i, (chunk_path, chunk) in enumerate(zip(chunk_paths, chunks)):
        logger.info(f"Transcribing chunk {i}: {chunk_path}")
        with _whisper_transcribe_lock:
            whisper_result = model.transcribe(
                str(chunk_path),
                language=config.LANGUAGE,
                temperature=config.TEMPERATURE,
                condition_on_previous_text=config.CONDITION_ON_PREVIOUS_TEXT,
                # Whisper defaults to fp16=True and silently falls back to fp32 on
                # CPU, emitting a UserWarning every call. Deciding this explicitly
                # from the model's actual device avoids the warning without
                # silencing it globally (which could hide unrelated warnings).
                fp16=(_whisper_device == "cuda"),
            )

        raw_text = whisper_result["text"].strip()

        # Whisper's per-segment confidence signals, averaged across the chunk.
        # avg_logprob closer to 0 = more confident; no_speech_prob closer to
        # 1 = Whisper thinks this chunk had no real speech (worth flagging,
        # since a force-split chunk from segmentation could land here).
        sub_segments = whisper_result.get("segments", [])
        avg_logprob = (
            sum(s.get("avg_logprob", 0.0) for s in sub_segments) / len(sub_segments)
            if sub_segments else None
        )
        no_speech_prob = (
            sum(s.get("no_speech_prob", 0.0) for s in sub_segments) / len(sub_segments)
            if sub_segments else None
        )

        is_low_confidence = (avg_logprob is not None and avg_logprob < -1.0) or \
                             (no_speech_prob is not None and no_speech_prob > 0.5)
        if is_low_confidence:
            low_confidence_count += 1
            logger.warning(
                f"Chunk {i} has low transcription confidence "
                f"(avg_logprob={avg_logprob}, no_speech_prob={no_speech_prob})"
            )
            job_audit_log(task_payload, f"Chunk {i} low confidence transcription")

        segments.append(TranscriptSegment(
            chunk_index=i,
            start_ms=chunk.start_ms,
            end_ms=chunk.end_ms,
            raw_text=raw_text,
            avg_logprob=avg_logprob,
            no_speech_prob=no_speech_prob,
        ))

    full_raw_text = " ".join(s.raw_text for s in segments if s.raw_text)

    if low_confidence_count:
        logger.warning(f"{low_confidence_count} chunk(s) flagged as low confidence — consider human review")
        job_audit_log(task_payload, f"{low_confidence_count} chunk(s) flagged as low confidence")

    return TranscriptionResult(
        segments=segments,
        full_raw_text=full_raw_text,
        low_confidence_count=low_confidence_count,
    )

# ---------------------------------------------------------------------------
# Text Cleanup
# transcript_segments here should be TranscriptionResult.segments — cleanup
# runs per-segment (so chunk boundaries are still known) then merges into
# one continuous document.
# ---------------------------------------------------------------------------
def clean_transcript(
    task_payload,
    transcript_segments,
    config=TextCleanupConfig()) -> CleanupResult:
    """
        Remove filler words, normalize punctuation/capitalization per chunk,
        then merge all chunks into one continuous cleaned document.
    """
    logger.info(f"Cleaning {len(transcript_segments)} transcript segment(s)")
    job_audit_log(task_payload, f"Cleaning {len(transcript_segments)} transcript segment(s)")

    cleaned_segments = []
    fillers_removed_count = 0

    for seg in transcript_segments:
        no_filler, removed = remove_filler_words(seg.raw_text, config)
        fillers_removed_count += removed
        fixed = fix_punctuation(no_filler)
        cleaned_segments.append(fixed)

    merged_text = merge_cleaned_segments(cleaned_segments)

    logger.info(f"Removed {fillers_removed_count} filler word occurrence(s)")
    job_audit_log(task_payload, f"Removed {fillers_removed_count} filler word occurrence(s)")

    return CleanupResult(
        cleaned_text=merged_text,
        cleaned_segments=cleaned_segments,
        fillers_removed_count=fillers_removed_count,
    )

def remove_filler_words(text, config):
    """
        Strip filler/disfluency words from text. Returns (cleaned_text, count_removed).
        Deliberately conservative — see TextCleanupConfig.FILLER_WORDS for why
        ambiguous words like "like" or "actually" are excluded by default.
    """
    cleaned = text
    total_removed = 0
    for filler in sorted(config.FILLER_WORDS, key=len, reverse=True):
        # Optional surrounding comma/whitespace consumed too, so "X, uh, Y"
        # becomes "X Y" rather than leaving a dangling comma behind.
        pattern = r'\s*,?\s*(?<!\w)' + re.escape(filler) + r'(?!\w)\s*,?\s*'
        cleaned, n = re.subn(pattern, ' ', cleaned, flags=re.IGNORECASE)
        total_removed += n
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned, total_removed

def fix_punctuation(text):
    """
        Normalize spacing around punctuation, fix capitalization after
        sentence-ending punctuation, and ensure the text ends with one.
    """
    text = re.sub(r'\s+([,.!?;:])', r'\1', text)         # no space before punctuation
    text = re.sub(r'([,.!?;:])(?!\s|$)', r'\1 ', text)   # space after punctuation
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(
        r'([.!?])\s*([a-z])',
        lambda m: f"{m.group(1)} {m.group(2).upper()}",
        text,
    )
    if text:
        text = text[0].upper() + text[1:]
    if text and text[-1] not in '.!?':
        text += '.'
    return text

def merge_cleaned_segments(cleaned_segments):
    """
        Join per-chunk cleaned text into one continuous document, ensuring
        each chunk ends with sentence-ending punctuation before the next
        chunk's text is appended.
    """
    merged = ""
    for chunk in cleaned_segments:
        if not chunk:
            continue
        if merged and merged[-1] not in '.!?':
            merged += '.'
        merged = f"{merged} {chunk}".strip() if merged else chunk
    return merged

def job_audit_log(task_payload, message: str):
    """
        Log a message to the job audit log via the JobStateClient.
    """
    time.sleep(0.1)
    job_state_client.job_audit_log(task_payload["job_id"], task_payload["job_queue_id"], message)

def process_one_audio_file(task_payload, file_name, input_file_path, file_output_folder):
    """
        Runs the full pipeline (validate -> noise reduction -> VAD -> segmentation
        -> transcription -> cleanup) for one local audio file (mp3 or m4a), writing
        all intermediate artifacts under file_output_folder. Returns the cleaned
        transcript text, or None if validation failed.
    """
    # 1). Audio Validation
    result = validate_audio(task_payload, input_file_path)
    logger.info(f"Validation result for {file_name}: {result.status.value}")
    logger.debug(f"Metadata for {file_name}: {json.dumps(result.metadata.__dict__, indent=2)}")
    job_audit_log(task_payload, f"Validation result for {file_name}: {result.status.value}")
    if result.issues:
        for issue in result.issues:
            logger.info(f"[{issue.severity.value.upper()}] {issue.code}: {issue.message}")
            job_audit_log(task_payload, f"[{issue.severity.value.upper()}] {issue.code}: {issue.message}")

    if result.status == ValidationStatus.FAIL:
        logger.error(f"Validation failed for {file_name} -- skipping the rest of the pipeline")
        job_audit_log(task_payload, f"Validation failed for {file_name} -- skipping the rest of the pipeline")
        return None

    wav_name = f"{Path(file_name).stem}.wav"
    output_file_path = file_output_folder / wav_name

    # 2). Noise Reduction
    result = reduce_noise(task_payload, input_file_path, output_file_path)
    logger.info(
        f"{file_name}: noise reduction done -- input {result.input_rms_db:.1f} dBFS, "
        f"output {result.output_rms_db:.1f} dBFS ({result.noise_reduced_db:.1f} dB reduced)"
    )
    job_audit_log(
        task_payload,
        f"{file_name}: noise reduction done -- input {result.input_rms_db:.1f} dBFS, "
        f"output {result.output_rms_db:.1f} dBFS ({result.noise_reduced_db:.1f} dB reduced)",
    )

    # 3). Voice Activity Detection (VAD)
    vad_output_path = file_output_folder / "speech" / f"{Path(file_name).stem}_speech.wav"
    result = detect_voice_activity(task_payload, result.output_path, vad_output_path)
    logger.info(f"{file_name}: speech ratio {result.speech_ratio * 100:.1f}%, {len(result.segments)} segment(s)")
    job_audit_log(task_payload, f"{file_name}: speech ratio {result.speech_ratio * 100:.1f}%, {len(result.segments)} segment(s)")

    # Per-segment detail is debug-only -- a long recording can produce hundreds of
    # segments, which would otherwise flood the logs (and the job's audit trail).
    for i, seg in enumerate(result.segments):
        logger.debug(f"  [{i}] {seg.start_ms / 1000:.2f}s - {seg.end_ms / 1000:.2f}s")

    if not result.segments:
        logger.warning(f"{file_name}: no speech detected -- transcript will be empty")
        job_audit_log(task_payload, f"{file_name}: no speech detected -- transcript will be empty")

    # 4). Audio Segmentation
    # NOTE: pass the NOISE-REDUCED audio path (the input VAD itself
    # received) together with the segment boundaries VAD found —
    # NOT vad_output_path, which is the concatenated speech-only
    # file and no longer has silence gaps to safely split on.
    noise_reduced_path = output_file_path
    chunks_output_dir = file_output_folder / "chunks"
    result = segment_audio(task_payload, noise_reduced_path, result.segments, chunks_output_dir)
    logger.info(f"{file_name}: created {len(result.chunks)} chunk(s), {result.forced_split_count} forced split(s)")
    job_audit_log(
        task_payload,
        f"{file_name}: created {len(result.chunks)} chunk(s), {result.forced_split_count} forced split(s)",
    )
    if result.forced_split_count:
        logger.warning(
            f"{file_name}: {result.forced_split_count} chunk(s) were force-split mid-speech "
            f"-- transcription quality may suffer at those boundaries"
        )
        job_audit_log(
            task_payload,
            f"{file_name}: {result.forced_split_count} chunk(s) force-split mid-speech",
        )

    for i, chunk in enumerate(result.chunks):
        flag = " [FORCED SPLIT]" if chunk.forced_split else ""
        logger.debug(
            f"  [{i}] {chunk.start_ms / 1000:.2f}s - {chunk.end_ms / 1000:.2f}s "
            f"({chunk.duration_ms / 1000:.2f}s){flag}"
        )

    # 5). Speech-to-Text (Whisper)
    segmentation_result = result
    transcription_result = transcribe_chunks(task_payload, segmentation_result.output_paths, segmentation_result.chunks)
    logger.info(f"{file_name}: transcribed {len(transcription_result.segments)} chunk(s), {transcription_result.low_confidence_count} low-confidence")
    job_audit_log(
        task_payload,
        f"{file_name}: transcribed {len(transcription_result.segments)} chunk(s), {transcription_result.low_confidence_count} low-confidence",
    )

    # 6). Text Cleanup
    cleanup_result = clean_transcript(task_payload, transcription_result.segments)
    logger.info(f"{file_name}: cleaned transcript ready ({cleanup_result.fillers_removed_count} filler word(s) removed, {len(cleanup_result.cleaned_text)} char(s))")
    logger.debug(cleanup_result.cleaned_text)
    job_audit_log(
        task_payload,
        f"{file_name}: cleaned transcript ready ({cleanup_result.fillers_removed_count} filler word(s) removed, "
        f"{len(cleanup_result.cleaned_text)} char(s))",
    )

    # Pair each chunk's cleaned text back up with its original timing so callers that want a
    # timestamped transcript (e.g. the ad-hoc Audio Extract Service) don't need to re-derive it.
    timestamped_segments = [
        TimestampedSegment(start_ms=seg.start_ms, end_ms=seg.end_ms, text=cleaned)
        for seg, cleaned in zip(transcription_result.segments, cleanup_result.cleaned_segments)
        if cleaned
    ]
    return AudioTranscriptOutput(cleaned_text=cleanup_result.cleaned_text, segments=timestamped_segments)


def mp3_noise_processing_extract_txt(task_payload):
    """
        Reads mp3/m4a files from MinIO under task_payload["input_folder"], runs the
        full audio processing pipeline (validation -> noise reduction -> VAD ->
        segmentation -> Whisper transcription -> cleanup) using a local temp
        directory for intermediate artifacts (required since ffmpeg/Whisper operate
        on real file paths), then uploads only the final cleaned transcript to
        MinIO under task_payload["output_folder"]/job_{job_id}_queue_{job_queue_id}/
        {file_stem}/transcript.txt -- matching the pdf_highlighter/hurricane
        pipelines' bucket-based input/output convention. The temp directory (and
        everything in it -- noise-reduced audio, speech-only audio, chunks) is
        removed after each file, whether it succeeds or fails.

        One file's failure (decode error, Whisper crash, MinIO hiccup, etc.) is
        logged and audited but does not abort the rest of the batch -- every other
        file in input_folder still gets a chance to process.
    """
    input_folder = task_payload["input_folder"]
    output_folder = task_payload["output_folder"]

    object_names = [
        name for name in sorted(minio_client.list_objects(minio_bucket, prefix=input_folder))
        if name.rsplit("/", 1)[-1].lower().endswith(AUDIO_EXTENSIONS)
    ]
    logger.info(f"Found {len(object_names)} audio file(s) under {minio_bucket}/{input_folder}")
    job_audit_log(task_payload, f"Found {len(object_names)} audio file(s) under {minio_bucket}/{input_folder}")

    succeeded = 0
    skipped = 0
    failed = 0

    for object_name in object_names:
        file_name = object_name.rsplit("/", 1)[-1]
        logger.info(f"Processing {file_name}")
        job_audit_log(task_payload, f"Processing {file_name}")

        audio_bytes = minio_client.get_object_bytes(minio_bucket, object_name)
        if audio_bytes is None:
            logger.error(f"Could not read {object_name} from MinIO bucket {minio_bucket}.")
            job_audit_log(task_payload, f"Could not read {object_name} from MinIO bucket {minio_bucket}.")
            failed += 1
            continue

        tmp_dir = Path(tempfile.mkdtemp(prefix="mp3proc_"))
        try:
            input_file_path = tmp_dir / file_name
            with open(input_file_path, "wb") as f:
                f.write(audio_bytes)

            # One self-contained temp folder per input file -- everything this
            # file produces (noise-reduced audio, speech-only audio, chunks,
            # transcript) lives together here until the final transcript is
            # uploaded, then the whole temp folder is discarded.
            file_output_folder = tmp_dir / "output" / Path(file_name).stem
            file_output_folder.mkdir(parents=True, exist_ok=True)

            transcript_output = process_one_audio_file(task_payload, file_name, str(input_file_path), file_output_folder)
            if transcript_output is None:
                skipped += 1
                continue

            object_prefix = "/".join([
                output_folder,
                f"job_{task_payload['job_id']}_queue_{task_payload['job_queue_id']}",
                Path(file_name).stem,
            ])
            transcript_object_name = f"{object_prefix}/{Path(file_name).stem}.txt"
            if not minio_client.upload_bytes(
                    minio_bucket, transcript_object_name, transcript_output.cleaned_text.encode("utf-8"), content_type="text/plain"):
                logger.error(f"Could not upload {transcript_object_name} to MinIO bucket {minio_bucket}.")
                job_audit_log(task_payload, f"Could not upload {transcript_object_name} to MinIO bucket {minio_bucket}.")
                failed += 1
                continue

            logger.info(f"Saved cleaned transcript to: {minio_bucket}/{transcript_object_name}")
            job_audit_log(task_payload, f"Saved cleaned transcript to: {minio_bucket}/{transcript_object_name}")
            succeeded += 1
        except Exception as e:
            # Catch-all so one bad file (corrupt decode mid-stream, Whisper OOM,
            # a transient MinIO error, etc.) doesn't abort the rest of the batch --
            # logged with the full traceback for debugging, audited with just the
            # message so the job's audit trail stays readable.
            logger.exception(f"Unexpected error processing {file_name}: {e}")
            job_audit_log(task_payload, f"Unexpected error processing {file_name}: {e}")
            failed += 1
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    logger.info(
        f"Batch complete: {len(object_names)} file(s) found, "
        f"{succeeded} succeeded, {skipped} skipped (failed validation), {failed} failed"
    )
    job_audit_log(
        task_payload,
        f"Batch complete: {len(object_names)} file(s) found, "
        f"{succeeded} succeeded, {skipped} skipped (failed validation), {failed} failed",
    )