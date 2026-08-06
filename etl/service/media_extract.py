"""
    Media Extract
    @author: Nabeel Ahmed Jamil

    Pre-processing helpers that turn a video file or a YouTube link into a plain
    audio file, so audio_extract_service.py can hand that off to the existing
    F768927 pipeline (mp3_noise_processing_extract_txt_f768927.process_one_audio_file)
    completely unchanged -- this module never imports from or modifies that script,
    it just produces the same kind of local .mp3 file an uploaded audio file would be.

    Why a separate extraction step instead of feeding a video straight into the
    pipeline: process_one_audio_file's validate_audio() calls MutagenFile() first,
    which only understands audio-container tags (ID3/MP4-audio/FLAC/WAVE/etc) --
    it does not reliably parse general video containers (.mkv/.avi/.webm, and even
    .mov/video-.mp4 aren't guaranteed), so most video uploads would fail validation
    immediately even though ffmpeg itself can decode the audio track fine.
"""
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from etl.util.logging_config import get_logger

logger = get_logger(__name__)

# Video extensions this module accepts as input.
VIDEO_EXTENSIONS = (".mp4", ".mov", ".mkv", ".webm", ".avi")

# Keeps a single ad-hoc request bounded -- on top of the download itself, noise
# reduction + VAD + Whisper still have to run synchronously afterward.
MAX_YOUTUBE_DURATION_SEC = 2 * 60 * 60

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "music.youtube.com"}

FFMPEG_VIDEO_EXTRACT_TIMEOUT_SEC = 15 * 60


def _with_scheme(url: str) -> str:
    """urlparse (and yt-dlp) need a scheme to populate the hostname -- a user pasting
    "youtube.com/watch?v=..." or "www.youtube.com/..." without http(s):// would otherwise
    parse with an empty host and get wrongly rejected, even though the frontend's looser
    substring check already let it through. Bug: this is exactly what was happening before."""
    url = (url or "").strip()
    if url and not re.match(r"^https?://", url, re.IGNORECASE):
        return "https://" + url
    return url


def is_youtube_url(url: str) -> bool:
    """Basic host allowlist check -- not a full sandbox, just a fast-fail guard
    before handing an arbitrary URL to yt-dlp."""
    try:
        host = (urlparse(_with_scheme(url)).hostname or "").lower()
    except Exception:
        return False
    return host in YOUTUBE_HOSTS


def extract_audio_from_video(video_path: str, output_mp3_path: str) -> None:
    """Shells out to ffmpeg to pull just the audio track out of a video file --
    same ProcessBuilder-style approach as AudioTranscodeUtil.java on the process
    side, just from Python. Raises RuntimeError with ffmpeg's stderr on failure."""
    logger.info("Extracting audio track from video: %s", video_path)
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", video_path, "-vn", "-acodec", "libmp3lame", "-q:a", "2", output_mp3_path],
        capture_output=True, text=True, timeout=FFMPEG_VIDEO_EXTRACT_TIMEOUT_SEC,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed to extract audio from video: {result.stderr[-2000:]}")
    logger.info("Audio track extracted to: %s", output_mp3_path)


def download_youtube_audio(url: str, output_dir: str) -> str:
    """Downloads the best available audio for a YouTube URL and converts it to
    mp3 via yt-dlp's ffmpeg postprocessor. Returns the local mp3 path. Raises
    ValueError if the video exceeds MAX_YOUTUBE_DURATION_SEC (checked via a
    metadata-only lookup before the real download starts)."""
    url = _with_scheme(url)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Fetching YouTube metadata: %s", url)
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    duration = info.get("duration") or 0
    if duration > MAX_YOUTUBE_DURATION_SEC:
        raise ValueError(
            f"Video is {duration / 60:.0f} min, exceeds the "
            f"{MAX_YOUTUBE_DURATION_SEC // 60}-minute limit for on-demand extraction."
        )

    logger.info("Downloading YouTube audio (%s, %.0fs)", info.get("title", url), duration)
    download_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(output_dir / "audio.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(download_opts) as ydl:
        ydl.extract_info(url, download=True)

    output_path = output_dir / "audio.mp3"
    if not output_path.exists():
        raise RuntimeError("yt-dlp did not produce the expected audio file.")
    logger.info("YouTube audio downloaded to: %s", output_path)
    return str(output_path)
