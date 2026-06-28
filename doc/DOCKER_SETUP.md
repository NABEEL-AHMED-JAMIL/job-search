# Docker Compose Setup Guide

## Overview

This project now includes multiple docker-compose configurations to support the job-search ETL pipeline with MongoDB and Kafka.

## Available Docker Compose Files

### 1. `docker-compose.yml` (Original)
**Services:**
- MongoDB 7.0
- Mongo Express UI (admin panel for MongoDB)

**Use when:**
- You only need MongoDB database
- You're using an external/existing Kafka setup
- You want minimal resource usage

**Run:**
```bash
docker-compose up -d
```

Access:
- Mongo Express UI: http://localhost:8081 (admin/admin123)
- MongoDB: localhost:27017

---

### 2. `docker-compose.kafka.yml` (Kafka Stack Only)
**Services:**
- Zookeeper (Kafka coordination)
- Kafka Broker (message broker at localhost:9093)
- Kafka UI (web interface for monitoring)
- Schema Registry (optional schema management)

**Use when:**
- You have MongoDB running elsewhere
- You want to add Kafka to an existing MongoDB setup
- You want to run them separately

**Run alongside MongoDB:**
```bash
# Start MongoDB
docker-compose up -d

# In another terminal, or add to existing setup
docker-compose -f docker-compose.kafka.yml up -d
```

Access:
- Kafka UI: http://localhost:8080
- Kafka Broker: localhost:9093
- Zookeeper: localhost:2181
- Schema Registry: http://localhost:8082

---

### 3. `docker-compose.full.yml` (Complete Stack)
**Services:**
- MongoDB + Mongo Express
- Zookeeper
- Kafka Broker
- Kafka UI
- Schema Registry

**Use when:**
- You want a complete, self-contained environment
- You're starting fresh
- You want everything in one command

**Run:**
```bash
docker-compose -f docker-compose.full.yml up -d
```

Access all services listed above.

---

## Quick Start Guide

### Option A: Minimal Setup (MongoDB only)
```bash
cd /Users/nabeel.amd93/Desktop/Old-School/job-search
docker-compose up -d
```

### Option B: Recommended Setup (MongoDB + Kafka)
```bash
cd /Users/nabeel.amd93/Desktop/Old-School/job-search

# Start everything
docker-compose -f docker-compose.kafka.yml up -d
docker-compose up -d

# Or use the full stack in one command
docker-compose -f docker-compose.full.yml up -d
```

### Option C: Start Only What You Need
```bash
# Just Kafka (no MongoDB)
docker-compose -f docker-compose.kafka.yml up -d

# Just MongoDB (no Kafka)
docker-compose up -d
```

---

## Environment Variables

See the `env` file in the project root for configuration:

```env
# MongoDB Credentials
MONGO_ROOT_USER=admin
MONGO_ROOT_PASSWORD=admin123
MONGO_DATABASE=mydb

# App User
MONGO_APP_USER=appuser
MONGO_APP_PASSWORD=apppassword

# Mongo Express UI
ME_BASICAUTH_USER=admin
ME_BASICAUTH_PASSWORD=admin123
```

---

## Health Checks

All services have built-in health checks. View status:

```bash
docker-compose ps
# or
docker-compose -f docker-compose.full.yml ps
```

Wait for all services to show `healthy` or `Up`:

```bash
while true; do docker-compose ps | grep -q "healthy\|Up" && echo "All services ready!" && break; sleep 2; done
```

---

## Verifying Services Are Running

### MongoDB
```bash
# Test connection
mongosh --host localhost --port 27017 -u admin -p admin123

# Inside mongosh shell
> use mydb
> db.adminCommand('ping')
{ ok: 1 }
```

### Kafka
```bash
# Test Kafka connection
python test_kafka_connection.py

# Expected output: Lists all topics
```

---

## Running the Job Search Listeners

Once services are running:

```bash
# Install dependencies
pip install -r requirements.txt

# Run all listeners
python -m etl.main.run_all_listeners

# Or in background with nohup
nohup python -m etl.main.run_all_listeners > listener.log 2>&1 &
```

---

## Stopping Services

```bash
# Stop all services (keeps data)
docker-compose down

# Stop and remove volumes (clears data)
docker-compose down -v

# For full stack
docker-compose -f docker-compose.full.yml down
```

---

## Troubleshooting

### Services won't start
```bash
# Check logs
docker-compose logs kafka
docker-compose logs zookeeper
docker-compose logs mongodb

# Restart services
docker-compose restart kafka
```

### Can't connect to Kafka
```bash
# Verify Kafka is running
docker ps | grep kafka

# Test connection
docker-compose exec kafka kafka-broker-api-versions --bootstrap-server localhost:9093
```

### MongoDB connection refused
```bash
# Check MongoDB logs
docker-compose logs mongodb

# Ensure port 27017 is available
lsof -i :27017
```

---

## Network Architecture

Services communicate over the `app_net` bridge network:

- **MongoDB Container:** Accessible at `mongodb:27017` to other containers
- **Kafka Container:** Accessible at `kafka:29093` to other containers
- **External Access:** 
  - MongoDB: `localhost:27017`
  - Kafka: `localhost:9093`
  - Kafka UI: `http://localhost:8080`
  - Mongo Express: `http://localhost:8081`

---

## Resource Requirements

Typical resource usage for `docker-compose.full.yml`:

| Service | CPU | Memory |
|---------|-----|--------|
| MongoDB | 0.5 | 512MB |
| Zookeeper | 0.2 | 256MB |
| Kafka | 0.5 | 512MB |
| Kafka UI | 0.1 | 128MB |
| Mongo Express | 0.1 | 64MB |
| Schema Registry | 0.2 | 256MB |
| **Total** | **~1.6 CPUs** | **~1.7 GB** |

Adjust resource limits in docker-compose based on your system.

---

## Production Considerations

For production deployments:

1. **Use environment variables** for sensitive credentials
2. **Enable network segmentation** (restricted network access)
3. **Set resource limits** (memory, CPU) for containers
4. **Use persistent volumes** with backup strategy
5. **Enable authentication** for Kafka and MongoDB
6. **Monitor container health** with proper alerting
7. **Use Docker secrets** or HashiCorp Vault for sensitive data

See individual docker-compose files for configuration options.

---

## Next Steps

1. Start services:
   ```bash
   docker-compose -f docker-compose.full.yml up -d
   ```

2. Verify everything is running:
   ```bash
   python test_kafka_connection.py
   ```

3. Test MongoDB:
   ```bash
   mongosh --host localhost -u admin -p admin123
   ```

4. Run the listeners:
   ```bash
   python -m etl.main.run_all_listeners
   ```

5. Send test messages and verify they're processed!

---

## Support

For issues:
1. Check `docker-compose logs <service_name>`
2. Verify ports are available: `lsof -i | grep LISTEN`
3. Ensure Docker daemon is running: `docker ps`
4. Review configuration in docker-compose files

