# Runs both job-search Python processes (see docker-compose.yml for which command each
# service uses): the ad-hoc Audio/Video/YouTube/Image extraction FastAPI service
# (etl.service.audio_extract_service) and the Kafka scrapping-topic listener
# (etl.tpd.tpd_scrapping_listener) that drives the batch pipelines (F768924-F768927).
FROM python:3.12-slim

LABEL maintainer="nabeel.amd93@gmail.com"

WORKDIR /app

# ffmpeg: audio/video decode+transcode (pydub, video-to-audio extraction, yt-dlp postprocessing)
# tesseract-ocr: image OCR (pytesseract)
# libsndfile1: required by the soundfile package
# curl: health checks
# build-essential: webrtcvad has no prebuilt wheel for every platform, needs a C compiler
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        tesseract-ocr \
        libsndfile1 \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Overridden per-service in docker-compose.yml (audio-extract-service vs
# tpd-scrapping-listener) -- this default just makes `docker run` on the bare image useful too.
CMD ["uvicorn", "etl.service.audio_extract_service:app", "--host", "0.0.0.0", "--port", "8100", "--workers", "1"]
