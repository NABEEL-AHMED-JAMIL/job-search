# Docker Compose Configurations Reference

## Summary

I've created **5 additional docker-compose files** for your project:

| File | Services | Purpose | When to Use |
|------|----------|---------|-------------|
| `docker-compose.yml` | MongoDB, Mongo Express | Original setup | Local development with DB only |
| `docker-compose.kafka.yml` | Zookeeper, Kafka, Kafka UI, Schema Registry | Message streaming | Add Kafka to existing MongoDB setup |
| `docker-compose.full.yml` | MongoDB + All Kafka services | Complete stack | Start everything from scratch |
| `docker-compose.monitoring.yml` | Prometheus, Grafana, Elasticsearch, Kibana, Redis, Flower | Observability & metrics | Production monitoring & logging |
| `docker-compose.ollama.yml` | Ollama API Server, Open WebUI | Local LLM inference | AI-powered job analysis |

---

## Quick Start Commands

### Start MongoDB only (original)
```bash
docker-compose up -d
```
Access: http://localhost:8081 (Mongo Express)

### Add Kafka to existing MongoDB
```bash
docker-compose -f docker-compose.kafka.yml up -d
```
Access: http://localhost:8080 (Kafka UI)

### Start everything (MongoDB + Kafka)
```bash
docker-compose -f docker-compose.full.yml up -d
```
Access:
- MongoDB: localhost:27017
- Kafka UI: http://localhost:8080
- Mongo Express: http://localhost:8081

### Add monitoring/observability
```bash
docker-compose -f docker-compose.monitoring.yml up -d
```
Access:
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin123)
- Kibana: http://localhost:5601
- Redis Commander: http://localhost:8083
- Flower (job monitoring): http://localhost:5555

### Add AI/LLM capabilities (Ollama)
```bash
docker-compose -f docker-compose.ollama.yml up -d
```
Access:
- API: http://localhost:11434
- WebUI: http://localhost:3001

### Start EVERYTHING (recommended for development)
```bash
docker-compose -f docker-compose.full.yml \
  -f docker-compose.monitoring.yml \
  -f docker-compose.ollama.yml up -d
```

---

## Service Details

### File: `docker-compose.kafka.yml`
**Kafka-specific services:**
- **Zookeeper**: Coordination for Kafka brokers
- **Kafka**: Message broker (localhost:9093 for Python, kafka:29093 for containers)
- **Kafka UI**: Web UI to create topics, monitor messages, manage consumers
- **Schema Registry**: Optional schema management for structured data

**Use case:** Python listeners in `etl/tpd/` connect to localhost:9093

---

### File: `docker-compose.full.yml`
**All-in-one stack:**
- MongoDB + Mongo Express (database layer)
- Zookeeper + Kafka + Kafka UI + Schema Registry (messaging layer)
- Single unified network (`app_net`)

**Use case:** Complete production-like environment in one command

---

### File: `docker-compose.monitoring.yml`
**Observability services:**
- **Prometheus**: Scrapes metrics from your applications
- **Grafana**: Visualize metrics on dashboards
- **Elasticsearch**: Centralized log storage
- **Kibana**: Search and visualize logs
- **Redis**: In-memory cache and session store
- **Flower**: Monitor async Celery jobs

**Use case:** Production monitoring, performance tracking, debugging complex issues

---

### File: `docker-compose.ollama.yml`
**Local LLM services:**
- **Ollama**: Local language model inference API (port 11434)
- **Open WebUI**: Web interface for chatting with models (port 3001)
- Supports multiple models: Mistral, Llama2, Neural Chat, Orca Mini, Phi, etc.

**Use case:** AI-powered job analysis, categorization, salary estimation, skill extraction
**Integration:** Python API for analyzing job descriptions with LLMs
**Models:** 1-4 GB each, run locally with no API keys needed

---

## Configuration Files Needed

For some services to work optimally, you may need:

### For Prometheus (`docker-compose.monitoring.yml`)
Create `prometheus.yml`:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'python-app'
    static_configs:
      - targets: ['localhost:8000']
```

### For Grafana dashboards
Create `grafana/provisioning/datasources/datasource.yml`:
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://prometheus:9090
    access: proxy
    isDefault: true
```

---

## Running Your Listeners

Once services are running:

```bash
# Install Python dependencies
pip install -r requirements.txt
pip install playwright  # If you plan to use Indeed scraper

# Run all listeners
python -m etl.main.run_all_listeners

# Or run in background
nohup python -m etl.main.run_all_listeners > listener.log 2>&1 &

# Monitor logs
tail -f listener.log
```

---

## Environment Variables

The project uses these env vars (see `env` file):

```env
# MongoDB
MONGO_ROOT_USER=admin
MONGO_ROOT_PASSWORD=admin123
MONGO_DATABASE=mydb

# Kafka (optional, auto-created)
KAFKA_SERVERS=localhost:9093
KAFKA_TEST_TOPIC=test-topic
KAFKA_SCRAPPING_TOPIC=scrapping-topic

# Playwright scraper (optional)
TWO_CAPTCHA_API_KEY=your_api_key_here
GOOGLE_SIGNIN_EMAIL=your_email@gmail.com

# Monitoring (optional)
PROMETHEUS_PORT=9090
GRAFANA_ADMIN=admin
GRAFANA_PASSWORD=admin123
```

Export them before running:
```bash
source env
export $(cat env | grep -v '^#' | xargs)

# Then run
python -m etl.main.run_all_listeners
```

---

## Stopping Services

```bash
# Stop specific compose file
docker-compose -f docker-compose.kafka.yml down

# Stop ALL services gracefully (keeps data)
docker-compose down
docker-compose -f docker-compose.kafka.yml down
docker-compose -f docker-compose.monitoring.yml down

# Clear all data (removes volumes)
docker-compose down -v
docker-compose -f docker-compose.full.yml down -v
```

---

## Troubleshooting

### Check service status
```bash
docker-compose ps
docker-compose -f docker-compose.full.yml ps
```

### View logs
```bash
# Specific service
docker-compose logs kafka
docker-compose logs mongodb

# All services
docker-compose logs -f

# Last 50 lines
docker-compose logs --tail=50
```

### Restart a service
```bash
docker-compose restart kafka
docker-compose stop mongodb && docker-compose start mongodb
```

### Check port availability
```bash
lsof -i :9093          # Kafka
lsof -i :27017         # MongoDB
lsof -i :8080          # Kafka UI
lsof -i :3000          # Grafana
lsof -i :6379          # Redis
```

### Force cleanup (if ports still in use)
```bash
# Remove all stopped containers
docker container prune

# Stop all containers
docker stop $(docker ps -aq)

# Remove all containers
docker rm $(docker ps -aq)
```

---

## About "ollma" / "olmma" (Ollama)

✅ **SOLVED!** This is **Ollama** - a local LLM runtime!

I've created a complete docker-compose configuration for Ollama:
- `docker-compose.ollama.yml` ✅ Created
- `OLLAMA_INTEGRATION.md` ✅ Complete integration guide

**What you can do with Ollama + job-search:**
- Analyze job descriptions with local LLMs
- Categorize jobs automatically
- Extract skills and requirements
- Estimate salary ranges
- Score job quality
- No API keys, runs locally, private data

**Quick start:**
```bash
docker-compose -f docker-compose.ollama.yml up -d
curl http://localhost:11434/api/pull -d '{"name":"mistral"}'
# Open http://localhost:3001 to chat
```

See `OLLAMA_INTEGRATION.md` for detailed setup and Python integration examples.

---

## Next Steps

1. **Choose your setup:**
   ```bash
   # Option A: Just MongoDB + Python listeners
   docker-compose up -d
   python -m etl.main.run_all_listeners
   
   # Option B: MongoDB + Kafka (recommended)
   docker-compose -f docker-compose.full.yml up -d
   python -m etl.main.run_all_listeners
   
   # Option C: Full production stack
   docker-compose -f docker-compose.full.yml \
     -f docker-compose.monitoring.yml up -d
   python -m etl.main.run_all_listeners
   ```

2. **Verify services are running:**
   ```bash
   python test_kafka_connection.py
   ```

3. **Access web interfaces:**
   - Kafka UI: http://localhost:8080
   - Mongo Express: http://localhost:8081
   - Grafana (if monitoring): http://localhost:3000
   - Kibana (if monitoring): http://localhost:5601

4. **Send test data and verify it's processed**

---

**For detailed setup instructions, see `DOCKER_SETUP.md`**

