#!/bin/bash
# Runs the ad-hoc Audio Extract Service (etl/service/audio_extract_service.py)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "════════════════════════════════════════════════════════════"
echo "  Audio Extract Service"
echo "════════════════════════════════════════════════════════════"

if [ ! -f ".env" ]; then
    echo "❌ .env not found in $SCRIPT_DIR — copy/create one before running."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "❌ .venv not found in $SCRIPT_DIR — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

echo ""
echo "🐍 Activating virtualenv..."
source .venv/bin/activate

echo ""
echo "📦 Verifying dependencies (requirements.txt)..."
pip install --quiet -r requirements.txt

echo ""
echo "▶️  Starting service on :${AUDIO_EXTRACT_SERVICE_PORT:-8100} (uvicorn, --workers 1)..."
echo "    --workers 1 is required -- more workers would each load a separate"
echo "    Whisper model instead of sharing the one lazy-loaded singleton."
echo "    Ctrl+C to stop."
echo ""
exec uvicorn etl.service.audio_extract_service:app \
    --host "${AUDIO_EXTRACT_SERVICE_HOST:-0.0.0.0}" \
    --port "${AUDIO_EXTRACT_SERVICE_PORT:-8100}" \
    --workers 1
