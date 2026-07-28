# Local Port Reference

All services below are published with a plain `hostPort:containerPort` mapping in their
compose files, which Docker binds to `0.0.0.0` by default. That means every port here is
reachable from the Mac (host) at `localhost:<port>` — no extra config needed — as long as
the container is running. Verified live on 2026-07-27 (see ✅/⛔ status column).

## Currently running (`docker ps`)

| Service | Port(s) | URL / connection | Compose file | Status |
|---|---|---|---|---|
| Redis | 6379 | `redis://:redis123@localhost:6379/0` | `docker-compose.integrated.yml` | ✅ running |
| Redis Commander (UI) | 8084 | http://localhost:8084 | `docker-compose.integrated.yml` | ✅ running |
| Cassandra | 9042 | `localhost:9042` (cqlsh / driver) | `docker-compose.integrated.yml` | ✅ running |
| Cassandra Web (UI) | 8085 | http://localhost:8085 | `docker-compose.integrated.yml` | ✅ running |
| OpenSearch | 9200 | http://localhost:9200 | `docker-compose.integrated.yml` | ✅ running |
| OpenSearch Dashboards | 5601 | http://localhost:5601 | `docker-compose.integrated.yml` | ✅ running |
| MinIO API | 9000 | http://localhost:9000 | `docker-compose.integrated.yml` | ✅ running |
| MinIO Console | 9001 | http://localhost:9001 | `docker-compose.integrated.yml` | ✅ running |
| Ollama | 11434 | http://localhost:11434 | `docker-compose.integrated.yml` | ✅ running |
| Kafka | 9093 (external), 29093 (internal) | `localhost:9093` | `docker-compose.full.yml` / `.kafka.yml` | ✅ running |
| Zookeeper | 2181 | `localhost:2181` | `docker-compose.full.yml` / `.kafka.yml` | ✅ running |
| Postgres (`postgres_db`) | 5432 | `postgresql://localhost:5432` | *(external to job-search, another project's compose)* | ✅ running |

## Defined but not currently started

| Service | Port(s) | Compose file |
|---|---|---|
| MongoDB | 27017 | `docker-compose.yml` / `docker-compose.full.yml` |
| Mongo Express (UI) | 8081 | `docker-compose.yml` / `docker-compose.full.yml` |
| Kafka UI | 8080 | `docker-compose.full.yml` / `.kafka.yml` |
| Schema Registry | 8081 (`.kafka.yml`) / 8082 (`.full.yml`) | `docker-compose.full.yml` / `.kafka.yml` |
| Open WebUI (Ollama) | 3001 | `docker-compose.ollama.yml` |
| Prometheus | 9090 | `docker-compose.monitoring.yml` |
| Grafana | 3000 | `docker-compose.monitoring.yml` |
| Redis Commander (monitoring stack) | 8083 | `docker-compose.monitoring.yml` |
| Flower (Celery UI) | 5555 | `docker-compose.monitoring.yml` |

## Known port conflicts if multiple compose files are run together

- **8081** — Mongo Express (`docker-compose.yml`/`.full.yml`) and Schema Registry
  (`docker-compose.kafka.yml`) both claim host port 8081. `docker-compose.full.yml` avoids
  this by remapping Schema Registry to `8082:8081`.
- **Redis Commander** — `.integrated.yml` uses host port 8084, `.monitoring.yml` uses 8083,
  so those two can coexist, but both start a container literally named `redis-commander`,
  which will collide if run at the same time.
- **redis**, **opensearch**, **opensearch-dashboards**, **kafka**, **zookeeper** — defined
  in more than one compose file with the same container name; only run one variant at a
  time (or rename containers) to avoid `container name already in use` errors.

## Credentials

| Service | User / Key | Password / Secret |
|---|---|---|
| Redis | — | `redis123` |
| MongoDB | `admin` | `admin123` |
| Mongo Express (basic auth) | `admin` | `admin123` |
| MinIO | `minioadmin` | `minioadmin123` |
| Grafana | `admin` | `admin123` |

Corresponding `.env` entries for the Python project live in
[`../.env`](../.env) (`REDIS_*`, `CASSANDRA_*`, `OPENSEARCH_*`, `KAFKA_SERVERS`,
`OLLAMA_URL`, `MINIO_*`).
