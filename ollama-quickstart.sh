#!/bin/bash
# Quick start script for Pacific Hurricane Extractor with Ollama

set -e

echo "════════════════════════════════════════════════════════════"
echo "  Pacific Hurricane Extractor - Quick Start with Ollama"
echo "════════════════════════════════════════════════════════════"

# Step 1: Start Docker services
echo ""
echo "📦 Step 1: Resetting and starting Docker services (Ollama + OpenSearch + Redis)..."
docker compose -f docker-compose.integrated.yml down --remove-orphans >/dev/null 2>&1 || true
docker compose -f docker-compose.integrated.yml up -d

# Step 2: Wait for Ollama to be healthy
echo ""
echo "⏳ Step 2: Waiting for Ollama to be healthy..."
max_retries=30
retry_count=0
until docker exec ollama ollama list > /dev/null 2>&1 || [ $retry_count -ge $max_retries ]; do
    echo "  Attempting to reach Ollama (attempt $((retry_count + 1))/$max_retries)..."
    retry_count=$((retry_count + 1))
    sleep 2
done

if [ $retry_count -ge $max_retries ]; then
    echo "❌ Ollama failed to start after $max_retries attempts"
    exit 1
fi
echo "✓ Ollama is healthy"

# Step 3: Run the one-shot model setup job
echo ""
echo "🔽 Step 3: Running Ollama model setup (this may take 5-10 minutes)..."
echo "           Model size: ~4GB. Progress will be shown below."
docker compose -f docker-compose.integrated.yml up --abort-on-container-exit --exit-code-from ollama-setup ollama-setup
echo ""

