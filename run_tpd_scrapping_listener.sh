#!/bin/bash
# Runs the TPD Kafka scrapping-topic listener (etl/tpd/tpd_scrapping_listener.py)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "════════════════════════════════════════════════════════════"
echo "  TPD Scrapping Listener"
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
echo "▶️  Starting listener (python -m etl.tpd.tpd_scrapping_listener)..."
echo "    Ctrl+C to stop."
echo ""
exec python -m etl.tpd.tpd_scrapping_listener
