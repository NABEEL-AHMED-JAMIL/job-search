# Ollama Integration Guide - Pacific Hurricane Extractor

This guide explains how to use Ollama with the Pacific hurricane data extractor to automatically extract death counts and affected areas from hurricane descriptions using LLM.

## Architecture

```
┌─────────────────────────────────────────┐
│   Pacific Hurricane Extractor           │
│   (etl/tasks/pacific_hurricanes_1975_extractor.py)
└──────────────────┬──────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  Ollama API          │
        │  (localhost:11434)   │
        └──────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │  Mistral Model       │
        │  (pre-downloaded)    │
        └──────────────────────┘
```

## Quick Start

### 1. Start Ollama and Initialize Model

```bash
# Start the integrated stack (Ollama + OpenSearch + Redis)
docker-compose -f docker-compose.integrated.yml up -d

# Wait for services to be healthy (30-60 seconds)
docker ps --filter "name=ollama" --format "table {{.Names}}\t{{.Status}}"
```

The `ollama-setup` service will automatically:
- Wait for Ollama to be healthy
- Pull the `mistral` model (~4GB, takes a few minutes)
- Verify everything is ready

### 2. Run the Hurricane Extractor with Ollama

```bash
# Test mode (processes only 2023-2024)
export OLLAMA_ENABLED=true
export TEST_MODE=true
python3 etl/tasks/pacific_hurricanes_1975_extractor.py
```

Or set environment variables in `.env`:
```
OLLAMA_ENABLED=true
TEST_MODE=true
OLLAMA_HOST=http://localhost:11434
```

### 3. Production Mode (All Years 1950-2026)

```bash
export OLLAMA_ENABLED=true
export TEST_MODE=false
python3 etl/tasks/pacific_hurricanes_1975_extractor.py
```

**Warning:** This processes 77 years of data. With Ollama extraction, it will take several hours.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_ENABLED` | `true` | Enable/disable Ollama-based text extraction |
| `TEST_MODE` | `true` | Only process 2023-2024 (vs. all years 1950-2026) |
| `JOBSEARCH_USER_AGENT` | `JobSearchBot/1.0 (+https://example.org; contact: ops@example.org)` | User-Agent for Wikipedia requests |
| `PACIFIC_HURRICANES_BASE_URL` | `https://en.wikipedia.org/wiki/{year}_Pacific_hurricane_season` | Wikipedia page template |

### Ollama API Configuration

The extractor uses the following Ollama endpoint:
```
POST http://localhost:11434/api/generate
```

**Request Body:**
```json
{
  "model": "mistral",
  "prompt": "<extraction_prompt>",
  "stream": false,
  "temperature": 0.3
}
```

To change the model or temperature, edit the `extract_info_from_text()` function in `pacific_hurricanes_1975_extractor.py`.

## Available Models

By default, the setup pulls `mistral`. Other options:

```bash
# SSH into Ollama container
docker exec -it ollama /bin/sh

# Pull alternative models
ollama pull llama2        # General-purpose, ~4GB
ollama pull neural-chat   # Optimized for chat, ~4GB
ollama pull orca-mini     # Smaller, ~2GB
ollama pull phi           # Very small, ~1.5GB

# List available models
ollama list

# Exit
exit
```

## Output Format

The extractor outputs hurricane data with the following structure:

```python
{
  "name": "Hurricane Agatha",
  "content": "Detailed description from Wikipedia...",
  "start_date": "2022-05-28",
  "end_date": "2022-05-31",
  "deaths": 9,                          # Extracted by Ollama
  "affected_areas": [                   # Extracted by Ollama
    "Oaxaca",
    "Sierra Madre del Sur",
    "Mexico"
  ]
}
```

## Troubleshooting

### Ollama service not starting

```bash
# Check container logs
docker logs ollama

# If port 11434 is in use, stop conflicting process
lsof -i :11434
kill <PID>

# Restart
docker-compose -f docker-compose.integrated.yml restart ollama
```

### Model not downloading

```bash
# Check if model exists
docker exec ollama ollama list

# Manually pull model
docker exec ollama ollama pull mistral

# Monitor download progress
docker logs -f ollama
```

### Extraction returning empty results

```bash
# Check if Ollama is responding
curl http://localhost:11434/api/tags

# Test extraction with debug logging
export LOGLEVEL=DEBUG
python3 etl/tasks/pacific_hurricanes_1975_extractor.py
```

### Memory issues

If Ollama crashes on large models:

```bash
# Increase Docker memory limit
# Edit docker-compose.integrated.yml:
# - Change shm_size: 4gb to shm_size: 8gb
# - Or increase Docker Desktop memory allocation

docker-compose -f docker-compose.integrated.yml down
# Edit docker-compose.integrated.yml
docker-compose -f docker-compose.integrated.yml up -d
```

## Performance Optimization

### Use Lighter Models

For faster extraction with lower memory usage:

```bash
# Edit pacific_hurricanes_1975_extractor.py
# In extract_info_from_text(), change:
#   "model": "mistral",
# To:
#   "model": "orca-mini",  # Or "phi" for fastest
```

### Batch Processing

Process only specific years:

```python
from exmple import fetch_and_extract_all_seasons

# Process 2000-2010 only
data = fetch_and_extract_all_seasons(
    start_year=2000,
    end_year=2010,
    use_ollama=True
)
```

### Disable Ollama for Speed

If you just need raw data without LLM extraction:

```bash
export OLLAMA_ENABLED=false
python3 etl/tasks/pacific_hurricanes_1975_extractor.py
```

This runs ~10x faster since there's no Ollama overhead.

## Integration with Other Components

### OpenSearch
Store extracted hurricane data:
```python
from opensearchpy import OpenSearch

client = OpenSearch([{"host": "localhost", "port": 9200}])
for year, hurricanes in all_data.items():
    doc_id = f"hurricanes-{year}"
    client.index(index="hurricanes", id=doc_id, body={
        "year": year,
        "data": hurricanes
    })
```

### Redis
Cache results:
```python
import redis

cache = redis.StrictRedis(host='localhost', port=6379, password='redis123')
cache.set(f"hurricanes:2023", json.dumps(hurricanes), ex=86400)  # 24 hours
```

## Next Steps

- [ ] Configure a production Ollama instance with GPU support (see Ollama docs)
- [ ] Store results in MongoDB or OpenSearch
- [ ] Set up scheduled daily extraction via APScheduler/Flower
- [ ] Create API endpoints to query hurricane data
- [ ] Build Grafana dashboards for visualizations

## Resources

- [Ollama Documentation](https://ollama.ai)
- [Ollama Model Library](https://ollama.ai/library)
- [Mistral Model Card](https://huggingface.co/mistralai/Mistral-7B)


