# 🚀 Ollama + Pacific Hurricane Extractor - Setup Guide

## What Was Built

A complete data extraction pipeline that:
1. **Fetches** Wikipedia hurricane data for years 1950-2026
2. **Parses** HTML and extracts structured information
3. **Uses Ollama LLM** (Mistral model) to intelligently extract:
   - Number of deaths
   - Affected areas/locations
4. **Stores** in Docker containers (Ollama + OpenSearch + Redis)

---

## ⚡ Quick Start (3 Commands)

### Option A: Automatic Setup (Recommended)
```bash
cd /Users/nabeel.amd93/Desktop/Old-School/job-search
chmod +x ollama-quickstart.sh
./ollama-quickstart.sh
```

This will:
- ✅ Start Docker containers
- ✅ Download Mistral model (~4GB)
- ✅ Extract 2023-2024 data
- ✅ Show service URLs

**Estimated time:** 10-15 minutes (first run due to model download)

---

### Option B: Manual Step-by-Step

#### Step 1: Start Docker Services
```bash
cd /Users/nabeel.amd93/Desktop/Old-School/job-search
docker-compose -f docker-compose.integrated.yml up -d
```

Check status:
```bash
docker ps
```

#### Step 2: Wait for Ollama to Download Mistral Model
```bash
# Monitor progress
docker logs -f ollama-setup
```

Wait until you see: `Model ready!` (takes 5-15 minutes depending on internet)

#### Step 3: Run the Extractor
```bash
# Test mode (fast - only 2023-2024)
export OLLAMA_ENABLED=true
export TEST_MODE=true
python3 etl/tasks/pacific_hurricanes_1975_extractor.py
```

---

## 📊 Expected Output

```
INFO:etl.tasks.pacific_hurricanes_1975_extractor:Fetching data for 2023...
INFO:etl.tasks.pacific_hurricanes_1975_extractor:Successfully fetched and parsed the content of https://en.wikipedia.org/wiki/2023_Pacific_hurricane_season
INFO:etl.tasks.pacific_hurricanes_1975_extractor:Extracted 24 hurricanes from 2023
INFO:etl.tasks.pacific_hurricanes_1975_extractor:Fetching data for 2024...
INFO:etl.tasks.pacific_hurricanes_1975_extractor:Successfully fetched and parsed the content of https://en.wikipedia.org/wiki/2024_Pacific_hurricane_season
INFO:etl.tasks.pacific_hurricanes_1975_extractor:Extracted 16 hurricanes from 2024

✓ Year 2023: 24 hurricanes
  Sample: {
    'name': 'Hurricane Otis',
    'start_date': '2023-10-05',
    'end_date': '2023-10-26',
    'deaths': 64,
    'affected_areas': ['Mexico', 'California']
  }
```

---

## 🎛️ Configuration Options

### Mode 1: Test Mode (Fast - Recommended First)
```bash
export OLLAMA_ENABLED=true
export TEST_MODE=true
python3 etl/tasks/pacific_hurricanes_1975_extractor.py
```
- **Time:** ~2-3 minutes
- **Data:** 2023-2024 only
- **Use case:** Development & testing

### Mode 2: Production Mode (All Years)
```bash
export OLLAMA_ENABLED=true
export TEST_MODE=false
python3 etl/tasks/pacific_hurricanes_1975_extractor.py
```
- **Time:** ~40-60 minutes
- **Data:** 1950-2026 (77 years)
- **Use case:** Full data extraction

### Mode 3: Fast Mode (No LLM)
```bash
export OLLAMA_ENABLED=false
export TEST_MODE=true
python3 etl/tasks/pacific_hurricanes_1975_extractor.py
```
- **Time:** ~1-2 minutes
- **Data:** Basic hurricane info (no Ollama extraction)
- **Use case:** Quick data fetch

---

## 🔍 Verify Setup

### Check Docker Services
```bash
docker ps
```

You should see:
- ✅ `ollama` (running)
- ✅ `ollama-setup` (exited - this is normal)
- ✅ `opensearch` (running)
- ✅ `opensearch-dashboards` (running)
- ✅ `redis` (running)
- ✅ `redis-commander` (running)

### Test Ollama API
```bash
curl http://localhost:11434/api/tags
```

Should return:
```json
{
  "models": [
    {
      "name": "mistral:latest",
      "modified_at": "2024-06-17T...",
      "size": 4000000000
    }
  ]
}
```

---

## 🌐 Service URLs

After setup, access these services:

| Service | URL | Credentials |
|---------|-----|-------------|
| **Ollama API** | `http://localhost:11434` | N/A |
| **Ollama Models** | `http://localhost:11434/api/tags` | View available models |
| **OpenSearch** | `http://localhost:9200` | N/A (dev mode, security disabled) |
| **OpenSearch Dashboards** | `http://localhost:5601` | N/A |
| **Redis** | `localhost:6379` | Password: `redis123` |
| **Redis Commander** | `http://localhost:8083` | Web UI for Redis |

---

## 📚 Documentation Files

Inside `/Users/nabeel.amd93/Desktop/Old-School/job-search/`:

1. **`OLLAMA_INTEGRATION_GUIDE.md`** - Complete documentation
   - Architecture overview
   - Detailed configuration
   - Troubleshooting guide
   - Performance optimization

2. **`OLLAMA_IMPLEMENTATION_SUMMARY.md`** - What was built
   - Features implemented
   - Data flow
   - Test results
   - Next steps

3. **`ollama-quickstart.sh`** - Automated setup script

---

## 🐛 Troubleshooting

### "Ollama not responding"
```bash
# Check if container is running
docker ps | grep ollama

# Restart Ollama
docker-compose -f docker-compose.integrated.yml restart ollama

# Check logs
docker logs ollama
```

### "Mistral model not found"
```bash
# Manually pull model
docker exec ollama ollama pull mistral

# Or restart the setup service
docker-compose -f docker-compose.integrated.yml up --reset-container-name ollama-setup
```

### "Port 11434 already in use"
```bash
# Find what's using it
lsof -i :11434

# Kill the process
kill <PID>

# Or change port in docker-compose.integrated.yml
```

### "Out of memory"
```bash
# Stop containers
docker-compose -f docker-compose.integrated.yml down

# Increase Docker memory:
# - Mac: Docker Desktop > Settings > Resources > Memory
# - Then restart: docker-compose up -d
```

---

## 🎯 Next Steps

After confirming the setup works:

### 1. Process Full Data
```bash
export OLLAMA_ENABLED=true
export TEST_MODE=false
python3 etl/tasks/pacific_hurricanes_1975_extractor.py
```

### 2. Store Results

```python
import json
from exmple import fetch_and_extract_all_seasons

# Get data
data = fetch_and_extract_all_seasons(start_year=2020, end_year=2024, use_ollama=True)

# Save to JSON
with open('hurricanes_2020_2024.json', 'w') as f:
    json.dump(data, f, indent=2)
```

### 3. Store in OpenSearch
```python
from opensearchpy import OpenSearch

client = OpenSearch([{"host": "localhost", "port": 9200}])
for year, hurricanes in data.items():
    client.index(index="hurricanes", id=f"year_{year}", body={
        "year": year,
        "hurricanes": hurricanes
    })
```

### 4. Cache in Redis
```python
import redis

cache = redis.StrictRedis(host='localhost', port=6379, password='redis123')
for year, hurricanes in data.items():
    cache.set(f"hurricanes:{year}", json.dumps(hurricanes), ex=86400)
```

---

## ⚙️ Advanced: Different Ollama Models

The setup uses **Mistral** by default. To use a different model:

```bash
# Available models
docker exec ollama ollama list

# Pull another model
docker exec ollama ollama pull llama2        # ~4GB
docker exec ollama ollama pull neural-chat  # ~4GB
docker exec ollama ollama pull orca-mini    # ~2GB (faster)
docker exec ollama ollama pull phi          # ~1.5GB (very fast)
```

Then edit `etl/tasks/pacific_hurricanes_1975_extractor.py`:
```python
# Line ~245, change:
"model": "mistral",
# To:
"model": "orca-mini",  # or another model
```

---

## 📋 Quick Reference

```bash
# Start everything
docker-compose -f docker-compose.integrated.yml up -d

# View logs
docker logs ollama
docker logs ollama-setup

# Run extractor
python3 etl/tasks/pacific_hurricanes_1975_extractor.py

# Stop everything
docker-compose -f docker-compose.integrated.yml down

# Clean up (remove volumes)
docker-compose -f docker-compose.integrated.yml down -v
```

---

## 🎓 How It Works

1. **Fetch**: Requests Wikipedia hurricane season page
2. **Parse**: BeautifulSoup extracts storm names & descriptions
3. **Enhance**: Sends description to Ollama (Mistral LLM)
4. **Extract**: LLM parses text and returns JSON with:
   - `number_of_deaths`: Extracted count
   - `areas_affected`: List of locations
5. **Return**: Complete hurricane object with all data

---

## ✅ Verification Checklist

- [ ] Docker services are running (`docker ps`)
- [ ] Ollama healthcheck passes
- [ ] Mistral model downloaded (check `docker logs ollama-setup`)
- [ ] Extract runs without errors
- [ ] Output shows hurricanes with death/area data
- [ ] Can reach OpenSearch/Redis dashboards

---

## 📞 Support

For issues:
1. Check **OLLAMA_INTEGRATION_GUIDE.md** (Troubleshooting section)
2. Review **logs**: `docker logs <service_name>`
3. Test manually: `curl http://localhost:11434/api/tags`

---

## 🎉 You're Ready!

Your Hurricane Data Extraction pipeline with Ollama LLM is now ready.

**Start here:**
```bash
cd /Users/nabeel.amd93/Desktop/Old-School/job-search
./ollama-quickstart.sh
```

Enjoy! 🌪️📊


