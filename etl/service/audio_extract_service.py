"""
    Audio Extract Service
    @author: Nabeel Ahmed Jamil

    Ad-hoc HTTP wrapper around the F768927 noise-reduction + Whisper pipeline
    (etl.tasks.mp3_noise_processing_extract_txt_f768927), for extracting a
    transcript from a single audio file on demand -- outside the Kafka job
    queue. Reuses that module's already-instantiated MinioClient and its
    lazy Whisper model singleton, so the model loads once (on first request)
    and stays resident for the life of this process.

    Run with: ./run_audio_extract_service.sh (must stay --workers 1 -- more
    workers would each lazy-load their own separate Whisper model).
"""
import shutil
import tempfile
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from etl.service.image_extract import IMAGE_EXTENSIONS, extract_text_from_image
from etl.tasks.mp3_noise_processing_extract_txt_f768927 import (
    AUDIO_EXTENSIONS,
    ValidationConfig,
    minio_client,
    process_one_audio_file,
)
from etl.util.logging_config import get_logger

logger = get_logger(__name__)

app = FastAPI(title="Audio Extract Service")


class BucketExtractRequest(BaseModel):
    bucket: str
    key: str
    timestamps: bool = False


def _sentinel_task_payload() -> dict:
    # job_id/job_queue_id must be numeric -- the Java backend's audit-log
    # endpoint binds them as Long path variables. A non-existent job still
    # gets a clean "not found" response (verified: NotifyServiceImpl.addLogs
    # never throws), and JobStateClient swallows any failure -- so these are
    # safe throwaway values for a one-off extraction with no real job.
    return {"job_id": 0, "job_queue_id": int(time.time() * 1000)}


def _validate_extension(file_name: str, extensions: tuple = AUDIO_EXTENSIONS) -> None:
    if not (file_name or "").lower().endswith(extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type -- expected one of {extensions}",
        )


def _format_timestamp(ms: int) -> str:
    """ms -> HH:MM:SS.mmm, e.g. 3120 -> '00:00:03.120'."""
    total_seconds, millis = divmod(int(ms), 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _run_pipeline(file_name: str, input_path: Path, timestamps: bool = False) -> str:
    if input_path.stat().st_size > ValidationConfig.MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File too large")
    output_dir = input_path.parent / "output" / input_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_output = process_one_audio_file(
        _sentinel_task_payload(), file_name, str(input_path), output_dir
    )
    if transcript_output is None:
        raise HTTPException(status_code=422, detail="Audio failed validation (silent, too short, or unreadable)")
    if not timestamps:
        return transcript_output.cleaned_text
    return "\n".join(
        f"[{_format_timestamp(seg.start_ms)}] {seg.text}" for seg in transcript_output.segments
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/extract/upload")
async def extract_upload(file: UploadFile = File(...), timestamps: bool = Form(False)):
    _validate_extension(file.filename)
    tmp_dir = Path(tempfile.mkdtemp(prefix="adhoc_upload_"))
    try:
        input_path = tmp_dir / file.filename
        input_path.write_bytes(await file.read())
        return {"transcript": _run_pipeline(file.filename, input_path, timestamps)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Upload extraction failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/extract/bucket")
def extract_bucket(payload: BucketExtractRequest):
    file_name = payload.key.rsplit("/", 1)[-1]
    _validate_extension(file_name)
    tmp_dir = Path(tempfile.mkdtemp(prefix="adhoc_bucket_"))
    try:
        input_path = tmp_dir / file_name
        if not minio_client.download_file(payload.bucket, payload.key, str(input_path)):
            raise HTTPException(status_code=404, detail=f"Object not found: {payload.bucket}/{payload.key}")
        return {"transcript": _run_pipeline(file_name, input_path, payload.timestamps)}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Bucket extraction failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/extract/image")
async def extract_image(
    file: UploadFile = File(...),
    x: int = Form(None),
    y: int = Form(None),
    width: int = Form(None),
    height: int = Form(None),
):
    _validate_extension(file.filename, IMAGE_EXTENSIONS)
    tmp_dir = Path(tempfile.mkdtemp(prefix="adhoc_image_"))
    try:
        input_path = tmp_dir / file.filename
        input_path.write_bytes(await file.read())
        text = extract_text_from_image(str(input_path), x, y, width, height)
        if not text:
            raise HTTPException(status_code=422, detail="No text found in the image (or the selected region).")
        return {"transcript": text}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Image extraction failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
