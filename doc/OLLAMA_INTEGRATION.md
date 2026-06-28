# Ollama Integration Guide

## Overview

[Ollama](https://ollama.ai) is an easy tool for running large language models locally. This guide shows how to integrate Ollama with your job-search ETL project for AI-powered job analysis, summarization, and categorization.

---

## Quick Start

### 1. Start Ollama
```bash
cd /Users/nabeel.amd93/Desktop/Old-School/job-search
docker-compose -f docker-compose.ollama.yml up -d
```

### 2. Access the Web UI
Open http://localhost:3001 in your browser

### 3. Pull a Model
```bash
# Chat model (fast, good for conversations)
curl http://localhost:11434/api/pull -d '{"name":"mistral"}'

# Or reasoning model (slower, better analysis)
curl http://localhost:11434/api/pull -d '{"name":"neural-chat"}'
```

### 4. Test It
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Summarize this job description: Software Engineer needed for Python/Go backend work"
}'
```

---

## Services

### Ollama API Server
- **Port:** 11434
- **URL:** http://localhost:11434
- **Container name:** ollama
- **Purpose:** Runs LLM inference
- **Models location:** Persisted in `ollama_models` volume

### Open WebUI
- **Port:** 3001
- **URL:** http://localhost:3001
- **Container name:** open-webui
- **Purpose:** Web interface for chatting with models
- **Data location:** Persisted in `webui_data` volume

---

## Available Models

### Recommended for Job Analysis

**Mistral (7B)** - RECOMMENDED
- Size: ~4.1 GB
- Speed: Fast
- Best for: Job summarization, categorization
- Download: `curl http://localhost:11434/api/pull -d '{"name":"mistral"}'`

**Neural Chat (7B)**
- Size: ~4.7 GB
- Speed: Fast
- Best for: Detailed analysis, Q&A
- Download: `curl http://localhost:11434/api/pull -d '{"name":"neural-chat"}'`

**Llama2 (7B)**
- Size: ~3.8 GB
- Speed: Fast
- Best for: General purpose
- Download: `curl http://localhost:11434/api/pull -d '{"name":"llama2"}'`

**Starling LM (7B)**
- Size: ~4.3 GB
- Speed: Fast
- Best for: High quality responses
- Download: `curl http://localhost:11434/api/pull -d '{"name":"starling-lm"}'`

### Lightweight Models (Fast, Lower Memory)

**Orca Mini (3B)**
- Size: ~1.9 GB
- Speed: Very fast
- Download: `curl http://localhost:11434/api/pull -d '{"name":"orca-mini"}'`

**Phi (2.7B)**
- Size: ~1.6 GB
- Speed: Very fast
- Download: `curl http://localhost:11434/api/pull -d '{"name":"phi"}'`

---

## Integration with Job-Search Project

### Python Client for Ollama

```python
import requests
import json

OLLAMA_BASE_URL = "http://localhost:11434"

def analyze_job_description(job_description: str, model: str = "mistral") -> str:
    """Use Ollama to analyze a job description."""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    
    prompt = f"""Analyze this job description and provide:
1. Key skills required
2. Experience level needed
3. Technologies/languages
4. Seniority level (Junior/Mid/Senior)
5. Job type (Remote/Hybrid/On-site)

Job Description:
{job_description}

Provide a structured summary."""
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.7
    }
    
    response = requests.post(url, json=payload)
    result = response.json()
    return result.get("response", "")

def categorize_job(job_data: dict, model: str = "mistral") -> dict:
    """Categorize a job using LLM."""
    url = f"{OLLAMA_BASE_URL}/api/generate"
    
    prompt = f"""Categorize this job and return JSON:
Title: {job_data.get('title', 'N/A')}
Company: {job_data.get('company', 'N/A')}
Description: {job_data.get('description', 'N/A')}

Response format:
{{
  "category": "Backend/Frontend/Full-Stack/DevOps/Data/Other",
  "seniority": "Junior/Mid/Senior",
  "is_remote": true/false,
  "primary_language": "Python/Go/JS/Java/etc",
  "score": 1-10
}}

Return only valid JSON, no other text."""
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.3
    }
    
    response = requests.post(url, json=payload)
    result = response.json()
    
    try:
        return json.loads(result.get("response", "{}"))
    except json.JSONDecodeError:
        return {"error": "Failed to parse response"}

# Usage
if __name__ == "__main__":
    job = {
        "title": "Senior Python Developer",
        "company": "TechCorp",
        "description": "Looking for experienced Python developer with Django..."
    }
    
    print("Analyzing job...")
    analysis = analyze_job_description(job["description"])
    print(analysis)
    
    print("\nCategorizing job...")
    category = categorize_job(job)
    print(json.dumps(category, indent=2))
```

### Integration with Listeners

Add to `etl/util/job_state_client.py` or create `etl/util/ollama_client.py`:

```python
import requests
import os
from typing import Optional

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral")

class OllamaClient:
    @staticmethod
    def generate(prompt: str, model: Optional[str] = None) -> str:
        """Generate text using Ollama."""
        model = model or OLLAMA_MODEL
        url = f"{OLLAMA_BASE_URL}/api/generate"
        
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }
        
        try:
            response = requests.post(url, json=payload, timeout=60)
            result = response.json()
            return result.get("response", "")
        except Exception as e:
            print(f"Ollama error: {e}")
            return ""
    
    @staticmethod
    def list_models() -> list:
        """List available models."""
        url = f"{OLLAMA_BASE_URL}/api/tags"
        try:
            response = requests.get(url, timeout=10)
            result = response.json()
            return [m["name"] for m in result.get("models", [])]
        except Exception as e:
            print(f"Failed to list models: {e}")
            return []
```

---

## Use Cases for Job-Search Project

### 1. Job Categorization
```python
# Automatically categorize scraped jobs
category = OllamaClient.generate(f"""
Categorize this job in one word:
Title: {job['title']}
Description: {job['description']}

Response: Just the category word, nothing else.
""")
job['category'] = category.strip()
```

### 2. Salary Analysis
```python
# Estimate salary range
salary_analysis = OllamaClient.generate(f"""
Based on this job description, estimate the salary range:
{job['description']}

Respond with: "$X - $Y (Currency)"
""")
job['estimated_salary'] = salary_analysis.strip()
```

### 3. Skill Extraction
```python
# Extract required skills
skills = OllamaClient.generate(f"""
Extract required skills from this job description (comma-separated):
{job['description']}

Return only the skills, comma-separated.
""")
job['required_skills'] = [s.strip() for s in skills.split(",")]
```

### 4. Job Quality Scoring
```python
# Score job quality (1-10)
score = OllamaClient.generate(f"""
Rate this job posting quality (1-10):
Title: {job['title']}
Description length: {len(job['description'])} chars
Has apply URL: {bool(job['apply_url'])}

Reply with only the number.
""")
try:
    job['quality_score'] = int(score.strip())
except:
    job['quality_score'] = 5
```

---

## Docker Compose with Ollama

### Development (Full Stack + Ollama)
```bash
docker-compose -f docker-compose.full.yml \
  -f docker-compose.ollama.yml up -d
```

### Production (Full Stack + Monitoring + Ollama)
```bash
docker-compose -f docker-compose.full.yml \
  -f docker-compose.monitoring.yml \
  -f docker-compose.ollama.yml up -d
```

---

## Environment Variables

Add to `.env` file:
```env
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral
OLLAMA_TIMEOUT=60
```

---

## Performance Tuning

### Memory Optimization
For systems with limited RAM, use lighter models:
```bash
# Pull a small model
curl http://localhost:11434/api/pull -d '{"name":"orca-mini"}'
```

### GPU Support (Optional)
If you have an NVIDIA GPU:
```yaml
# In docker-compose.ollama.yml, uncomment:
# environment:
#   CUDA_VISIBLE_DEVICES: "0"
# devices:
#   - /dev/nvidia0:/dev/nvidia0
```

### Increase Shared Memory
For larger models, edit docker-compose.ollama.yml:
```yaml
ollama:
  shm_size: 8gb  # Increase if needed
```

---

## Common Commands

### Check if Ollama is Running
```bash
curl http://localhost:11434/api/tags
```

### List Downloaded Models
```bash
curl http://localhost:11434/api/tags
```

### Pull a New Model
```bash
curl http://localhost:11434/api/pull -d '{"name":"mistral"}'
```

### Delete a Model
```bash
curl -X DELETE http://localhost:11434/api/delete -d '{"name":"mistral"}'
```

### Generate Text (Sync)
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Your prompt here"
}'
```

### Generate Text (Streaming)
```bash
curl http://localhost:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Your prompt here",
  "stream": true
}'
```

---

## Troubleshooting

### Ollama container won't start
```bash
docker logs ollama
docker-compose -f docker-compose.ollama.yml up -d
```

### Out of memory
- Use a smaller model (orca-mini, phi)
- Reduce batch size
- Increase Docker memory allocation

### Model takes too long to download
- Be patient (models are 1-4 GB)
- Check internet connection
- Try `docker logs ollama` to see progress

### WebUI won't connect to Ollama
```bash
# Verify Ollama is running
docker ps | grep ollama

# Check connectivity
curl http://localhost:11434/api/tags

# Restart WebUI
docker-compose -f docker-compose.ollama.yml restart open-webui
```

---

## Stopping Ollama

```bash
# Stop Ollama and WebUI
docker-compose -f docker-compose.ollama.yml down

# Stop and remove all data
docker-compose -f docker-compose.ollama.yml down -v
```

---

## Integration Checklist

- [ ] Start Ollama: `docker-compose -f docker-compose.ollama.yml up -d`
- [ ] Verify it's running: `curl http://localhost:11434/api/tags`
- [ ] Access WebUI: http://localhost:3001
- [ ] Pull a model: `curl http://localhost:11434/api/pull -d '{"name":"mistral"}'`
- [ ] Test generation: See commands above
- [ ] Create Python client code (examples provided)
- [ ] Add to listeners (examples provided)
- [ ] Test with real job data
- [ ] Monitor performance
- [ ] Adjust model if needed

---

## Next Steps

1. **Start Ollama:**
   ```bash
   docker-compose -f docker-compose.ollama.yml up -d
   ```

2. **Pull a model:**
   ```bash
   curl http://localhost:11434/api/pull -d '{"name":"mistral"}'
   ```

3. **Test the API:**
   ```bash
   curl http://localhost:11434/api/generate -d '{"model":"mistral","prompt":"What is a software engineer?"}'
   ```

4. **Integrate with your code:**
   - Copy the Python client example above
   - Add to your listeners
   - Start analyzing jobs!

5. **Monitor performance:**
   - Check response times
   - Adjust model/prompts as needed
   - Scale up if processing many jobs

---

## Resources

- [Ollama Documentation](https://github.com/ollama/ollama)
- [Open WebUI](https://openwebui.com)
- [Available Models](https://ollama.ai/library)
- [API Reference](https://github.com/ollama/ollama/blob/main/docs/api.md)

---

**Status:** ✅ Ready to use with job-search project

