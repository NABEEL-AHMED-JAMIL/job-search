# Integrated Stack Reference (`docker-compose.integrated.yml`)

Single-file local dev stack: **Ollama + OpenSearch + Redis + Cassandra +
MinIO**, each with a web UI for browsing data. Use this doc as the reference
for starting, checking health, and troubleshooting the stack.

File: [`../docker-compose.integrated.yml`](../docker-compose.integrated.yml)

## Services & URLs

| Service | Purpose | Container | Host Port | URL / Address |
|---|---|---|---|---|
| Ollama | LLM runtime & API | `ollama` | 11434 | http://localhost:11434 |
| Ollama Setup | one-shot job that pulls the `mistral` model | `ollama-setup` | — | exits after pulling the model |
| OpenSearch | log/data store & search engine | `opensearch` | 9200 | http://localhost:9200 |
| OpenSearch Dashboards | OpenSearch data viewer | `opensearch-dashboards` | 5601 | http://localhost:5601 |
| Redis | cache / session store | `redis` | 6379 | `localhost:6379` (password `redis123`) |
| Redis Commander | Redis data viewer | `redis-commander` | 8084 | http://localhost:8084 |
| Cassandra | NoSQL wide-column database | `cassandra` | 9042 | `localhost:9042` (CQL) |
| Cassandra Web | Cassandra data viewer | `cassandra-web` | 8085 | http://localhost:8085 |
| MinIO | S3-compatible local file/object storage | `minio` | 9000 (API), 9001 (console) | API: http://localhost:9000 · Console: http://localhost:9001 |

All services share the `integrated_net` bridge network and persist data in
named volumes (`ollama_models`, `opensearch_data`, `redis_data`,
`cassandra_data`) so data survives `docker-compose down` (but not `-v`).

### Note: Postgres is not part of this stack

`postgres_db` runs in a **separate** compose project
(`/Users/nabeel.amd93/Desktop/Old-School/process/docker-compose.yml`) but
publishes port 5432 on the host, so any tool you add here can reach it via
`host.docker.internal:5432` (user `nabeel.amd93`, password `admin`, db
`etl_job`) without needing to touch that stack. An Adminer viewer was tried
for this and later removed in favor of Cassandra Web — see History below.

## Starting the stack

```bash
cd "/Users/nabeel.amd93/Desktop/Old-School/job-search"
docker-compose -f docker-compose.integrated.yml up -d
```

Start/recreate a single service (e.g. after editing its config):

```bash
docker-compose -f docker-compose.integrated.yml up -d <service-name>
```

Stop everything (keeps volumes/data):

```bash
docker-compose -f docker-compose.integrated.yml stop
```

Tear down containers + network (keeps volumes/data):

```bash
docker-compose -f docker-compose.integrated.yml down
```

Tear down **and delete all data**:

```bash
docker-compose -f docker-compose.integrated.yml down -v
```

## Checking health

Quick status of every container (state + published ports):

```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | \
  grep -E "ollama|opensearch|redis|cassandra"
```

Expect `(healthy)` for: `ollama`, `opensearch`, `opensearch-dashboards`,
`redis`, `cassandra`. `ollama-setup` has no healthcheck — it's expected to
show `Exited (0)` once the model pull finishes (check with
`docker logs ollama-setup`). `redis-commander` and `cassandra-web` have no
healthcheck defined; use their HTTP endpoints instead (below).

Per-service checks:

```bash
# Ollama
curl -s http://localhost:11434/api/tags

# OpenSearch
curl -s http://localhost:9200/_cluster/health?pretty

# OpenSearch Dashboards
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5601/api/status

# Redis
docker exec redis redis-cli -a redis123 ping

# Redis Commander UI
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8084

# Cassandra
docker exec cassandra cqlsh -e "describe cluster"

# Cassandra Web UI
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8085

# MinIO API
curl -s http://localhost:9000/minio/health/live -w "\n%{http_code}\n"

# MinIO Console
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:9001
```

### Uploading/fetching files from MinIO

Easiest via the console UI: open http://localhost:9001, log in (see
credentials table below), create a bucket, then drag-and-drop files to
upload/download.

From the CLI, using the `mc` client (no local install needed — runs via
Docker on the same network):

```bash
# create a bucket
docker run --rm --network job-search_integrated_net minio/mc \
  sh -c "mc alias set local http://minio:9000 minioadmin minioadmin123 && mc mb local/my-bucket"

# upload a file
docker run --rm --network job-search_integrated_net \
  -v /absolute/path/to/file.txt:/tmp/file.txt minio/mc \
  sh -c "mc alias set local http://minio:9000 minioadmin minioadmin123 && mc cp /tmp/file.txt local/my-bucket/file.txt"

# fetch/download a file
docker run --rm --network job-search_integrated_net \
  -v /absolute/path/to/downloads:/tmp/out minio/mc \
  sh -c "mc alias set local http://minio:9000 minioadmin minioadmin123 && mc cp local/my-bucket/file.txt /tmp/out/file.txt"
```

From application code, use any S3 SDK (boto3, aws-sdk, etc.) pointed at
`http://localhost:9000` (or `http://minio:9000` from another container on
`integrated_net`) with the access/secret key from the credentials table.

View logs for a service:

```bash
docker logs <container-name> --tail 50 -f
```

## Known issues & fixes already applied

1. **`redis-commander` port conflict on 8083.** A local `java` process was
   already bound to host port 8083. Fixed by mapping `redis-commander` to
   `8084:8081` instead of `8083:8081`.

2. **`opensearch-dashboards` stuck `unhealthy` (401 on `/api/status`).** The
   dashboards image's security plugin was still active even though
   `plugins.security.disabled: "true"` was set on the `opensearch` cluster
   itself, so dashboards' health/status calls got rejected. Fixed by adding
   `DISABLE_SECURITY_DASHBOARDS_PLUGIN: "true"` to the
   `opensearch-dashboards` environment.

3. **Cassandra takes ~60–90s to become healthy.** Its healthcheck has
   `start_period: 60s` and 10 retries — if `cassandra-web` won't connect
   right after `up -d`, just wait; it has `depends_on: condition:
   service_healthy` so it won't start until Cassandra is actually ready.

4. **`cassandra-web` crash-looped / `IPAddr::InvalidAddressError`.** The
   `markusgulden/cassandra-web` image ignores `CASSANDRA_HOST`/
   `CASSANDRA_PORT` env vars (needs CLI flags), and its `--hosts` flag
   requires a literal IP, not a hostname — passing `--hosts cassandra`
   fails to parse. Fixed by overriding the entrypoint to resolve the
   `cassandra` service name to an IP with `getent` at container start:
   `cassandra-web --hosts "$(getent hosts cassandra | awk '{print $1}')" --port 9042`.
   Also note: the image is `linux/amd64` only, so on Apple Silicon Docker
   emits a harmless platform-mismatch warning (runs under emulation).

## History of changes to this stack

- Initial file already defined Ollama, OpenSearch (+Dashboards), and Redis
  (+Commander).
- Ran the stack for the first time — hit and fixed the two port/health
  issues above.
- Added **Adminer** as a Postgres viewer (pointed at the existing
  `postgres_db` container from the separate `process` stack via
  `host.docker.internal:5432`), exposed on host port 8085.
- Later removed **Adminer** and added **Cassandra** + **Cassandra Web**
  instead, reusing host port 8085 for the Cassandra Web UI.
- Added **MinIO** for local S3-compatible file/object storage, with its
  web console on port 9001 for uploading/browsing files, and API on 9000
  for application/SDK use. Verified with a real upload+download round trip
  using the `mc` client.

## Credentials quick-reference

| Service | Username | Password | Notes |
|---|---|---|---|
| Redis | — | `redis123` | set via `--requirepass` |
| Cassandra | — | — | default install, no auth configured |
| MinIO | `minioadmin` | `minioadmin123` | access key / secret key for S3 API + console login |
| Postgres (external `process` stack) | `nabeel.amd93` | `admin` | db `etl_job`, host `host.docker.internal`, port `5432` |
