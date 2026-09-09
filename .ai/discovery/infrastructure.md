# Discovery — Infrastructure

How this system is actually run on a developer machine: every container, every port, every
environment variable that matters, how each part is started and verified, and the traps that have
already caught someone.

**Scope.** Four projects under `/Users/nabeel.amd93/Desktop/Old-School`: `process` (the Spring Boot
backend and its stack), `scheduler1` (the deployed Angular 8 frontend and the Angular 22 rewrite in
`scheduler1/next`), `job-search` (Python Kafka workers — **out of scope for the current phase**,
inventoried briefly in §7), and the supporting stacks those projects publish. All paths below are
relative to that workspace root. Two further directories exist there — `my-user-redux-frontend/`
and `service-3/` — and were **not** inventoried. Neither has a running container, and a grep for
their names across `process/`, `scheduler1/src`, `scheduler1/next/src` and `job-search/etl` returns
nothing.

**Method.** Every claim comes from a file in the workspace or from a read-only probe of the running
machine (`docker ps`, `docker inspect`, `curl` against health endpoints, `git ls-files`). Live
observations were taken on **2026-09-01** and are labelled as such — a container list is a fact
about this moment, not about the repository. No application code was changed.

> **Two files were rewritten by someone else while this was being written.** `process/README.md`
> (mtime 00:57) and `scheduler1/DEPLOYMENT.md` (mtime 00:56) both changed mid-session; both were
> re-read afterwards and the citations below are against the *current* content. Line numbers in
> those two files are the least durable in this document.

**No secret value appears in this document.** Where a credential exists, the variable name is given
and the place it comes from is named. Two places where credentials are committed to git are
recorded in §8 as findings; the values themselves are not reproduced here.

---

## 1. The whole local stack

### 1.1 Compose projects

There are four separate Docker Compose projects on this machine. They are genuinely separate —
different networks, different lifecycles — and most of the operational pain in §8 comes from that.

| Compose project | File | What it is |
|---|---|---|
| `process` | `process/docker-compose.yml` | The backend and everything it owns: Postgres, Zookeeper, Kafka, Redis, two browser UIs, the Spring Boot app |
| `kafka-it` | `process/kafka-it/docker-compose.kafka-it.yml` | A throwaway Kafka broker with seven security listeners, for the security matrix test |
| `scheduler1` | `scheduler1/docker-compose.yml` | The old Angular 8 frontend, built and served by nginx |
| `job-search` | `job-search/docker-compose.yml` and `job-search/docker-compose.integrated.yml` | Python workers, plus the MinIO/OpenSearch/Ollama/Cassandra support stack |

Project names were confirmed live with
`docker inspect <name> --format '{{index .Config.Labels "com.docker.compose.project"}}'`.
Notably, **`minio` and `opensearch` are owned by `job-search/docker-compose.integrated.yml`**, not
by `process` — `process` only reaches them across the host gateway.

### 1.2 The `process` stack, service by service

Source: `process/docker-compose.yml`.

| Service | Container | Image | Host ports | Purpose |
|---|---|---|---|---|
| `postgres` | `postgres_db` | `postgres:15` | `5433 -> 5432` | Application database `etl_job` (L15–36) |
| `zookeeper` | `zookeeper` | `confluentinc/cp-zookeeper:7.5.0` | `2181` | Kafka's coordination service (L39–47) |
| `kafka` | `kafka` | `confluentinc/cp-kafka:7.5.0` | `9092`, `9093` | Dev broker, two listeners (L50–71) |
| `redis` | `redis` | `redis:7-alpine` | `6379` | WebSocket presence registry + cache, `--appendonly yes` (L76–89) |
| `kafka_ui` | `kafka_ui` | `provectuslabs/kafka-ui:latest` | `8085 -> 8080` | Read-only broker browser (L97–109) |
| `redisinsight` | `redisinsight` | `redis/redisinsight:latest` | `5540` | Redis browser, named volume keeps the saved connection (L114–123) |
| `process_app` | `process_app` | built from `process/Dockerfile` | `9098` | The Spring Boot API (L126–216) |

**Volumes** (L7–11): `postgres_data`, `kafka_data` (declared but not mounted by any service —
see §8), `redis_data`, `redisinsight_data`. `process_app` additionally bind-mounts `./logs` to
`/app/logs` and the host's `/tmp/efs` to `/tmp/efs` (L208–210).

### 1.3 How the pieces reach each other

Three distinct addressing schemes are in play, and mixing them up is the single most common failure
mode in this workspace.

| From | To | Address used | Where it is set |
|---|---|---|---|
| `process_app` | Postgres | `postgres:5432` (compose DNS) | `docker-compose.yml:138` |
| `process_app` | Kafka | `kafka:9092` (INTERNAL listener) | `docker-compose.yml:141` |
| `process_app` | Redis | `redis:6379` | `docker-compose.yml:142–143` |
| `kafka_ui` | Kafka | `kafka:9092` | `docker-compose.yml:107` |
| `process_app` | MinIO / OpenSearch / Ollama / audio-extract / **LocalStack SES** | `host.docker.internal:<published port>` | `extra_hosts` at `docker-compose.yml:134–135`; `OPENSEARCH_URL` default at L183; `AWS_SES_ENDPOINT` default at L150 (§2.5); Java defaults in `AiAgentServiceImpl.java:82`, `FileChatExtractionServiceImpl.java:63`, `AudioTranscriptServiceImpl.java:43` |
| Host tools (psql, GUI clients) | Postgres | `localhost:5433` | `docker-compose.yml:23–29` |
| Host tools (kafka CLI) | Kafka | `localhost:9093` (EXTERNAL listener) | `docker-compose.yml:63` |
| Browser | API | `<page protocol>//<page hostname>:9098/api/v1` | `scheduler1/webpack.config.js:61`; `scheduler1/next/src/app/core/api/api.config.ts:6` |
| `job-search` workers | Kafka | `kafka:9092`, by joining the external `process_default` network | `job-search/docker-compose.yml:53–55, 67` |
| `job-search` workers | the API | `http://host.docker.internal:9098/api/v1` | `job-search/docker-compose.yml:23, 57, 109` |

The Kafka listener split is the thing worth internalising. `docker-compose.yml:61–65` publishes
`INTERNAL://0.0.0.0:9092` and `EXTERNAL://0.0.0.0:9093`, advertised as `kafka:9092` and
`localhost:9093` respectively. A Kafka client always **follows the advertised address after
bootstrapping**, so:

- a container on `process_default` must use `kafka:9092` — `localhost:9093` would send it back to
  itself;
- a process on the host must use `localhost:9093` — `kafka:9092` does not resolve.

The `job-search` compose file carries this reasoning verbatim at
`job-search/docker-compose.yml:48–52`, which is why those workers join `process_default` rather
than reconfiguring the broker.

### 1.4 The frontends

| App | Path | Build | Served |
|---|---|---|---|
| Angular 8 (deployed) | `scheduler1/` | Webpack 4 on Node 14 (`scheduler1/Dockerfile:5–31`) | nginx 1.27-alpine on host port 80, under `/scheduler/` (`scheduler1/Dockerfile:36–49`, `scheduler1/nginx.conf:40–52`) |
| Angular 22 (rewrite) | `scheduler1/next/` | Angular CLI 22 / `@angular/build:application` (`scheduler1/next/angular.json:16–20`) | `ng serve` for dev (default **4200**), or nginx 1.27-alpine on host port **4400** for a container (`scheduler1/next/Dockerfile`, `docker-compose.yml`, added 2026-09-03) |

The old app's bundle sets `output.publicPath = '/scheduler/'`
(`scheduler1/webpack.config.js:12`), which is why nginx serves it from a `/scheduler/` subpath
rather than the root, and why the app is reached at **`http://localhost/scheduler/`**, not
`http://localhost/`. The Dockerfile clears `/usr/share/nginx/html/` and copies the build into
`/usr/share/nginx/html/scheduler` (`scheduler1/Dockerfile:38, 40`), so the `location /` fallback at
`nginx.conf:54–56` has no `index.html` to serve. `scheduler1/DEPLOYMENT.md:32, 35` now states this
explicitly, including the `location = /scheduler` redirect at `nginx.conf:40–42` that makes the
no-trailing-slash form work. (An earlier version of that file, read at the start of this session,
gave `http://localhost/` instead.)

`scheduler1/next/.claude/launch.json` **does not exist** (checked with `find next/.claude -type f`,
which returned nothing). The only `launch.json` in the neighbourhood belongs to a different
repository, `/Users/nabeel.amd93/Desktop/io-frontend/.claude/launch.json`, which runs
`npx ng serve --port 4300`. That repo's git remote is `github.com/NABEEL-AHMED-JAMIL/io-frontend`,
so it is not part of this workspace.

### 1.5 Observed live state (2026-09-01)

`docker ps`, trimmed to name / status / published ports:

| Container | Status | Published |
|---|---|---|
| `process_app` | Up ~1h (healthy) | 9098 |
| `postgres_db` | Up 5h (healthy) | 5433→5432 |
| `kafka` | Up 5h | 9092, 9093 |
| `zookeeper` | Up 5h | 2181 |
| `redis` | Up 5h (healthy) | 6379 |
| `kafka_ui` | Up 5h | 8085→8080 |
| `redisinsight` | Up 5h | 5540 |
| `kafka_it` | Up ~1h | 19092–19098 |
| `kafka_it_zookeeper` | Up 5h | (internal only) |
| `scheduler1-app` | Up 5h (healthy) | 80 |
| `minio` | Up 5h (healthy) | 9000, 9001 |
| `opensearch` | Up 5h (healthy) | 9200 |
| `audio_extract_service` | Up 5h (healthy) | 8100 |
| `tpd_scrapping_listener` | Up 5h | — |
| `tpd_test_listener` | Up 5h | — |

Networks present: `process_default`, `kafka-it_default`, `scheduler1_default`,
`job-search_default`, `job-search_integrated_net`.

Two containers have joined since, and neither existed when the table above was taken. Both were
confirmed with `docker ps` on **2026-09-08**:

| Container | Image | Published | Owner |
|---|---|---|---|
| `next-app` | built from `scheduler1/next/Dockerfile` | 4400→80 | `scheduler1/next/docker-compose.yml` (§2.4) |
| `localstack-aws` | `localstack/localstack-pro:latest` | 127.0.0.1:443, 4510–4559, **4566** | **no compose file in this workspace** — started by hand, on the default `bridge` network (§2.5) |

Health probes run at the same time, all returning:

```
curl -s http://localhost:9098/api/v1/actuator/health   # {"status":"UP"}
curl -s http://localhost/health                        # OK
curl -s http://localhost:8100/health                   # {"status":"ok"}
curl -s http://localhost:9200                          # OpenSearch 2.10.0 banner
```

---

## 2. Bringing each part up, and verifying it

### 2.1 The `process` stack

The Dockerfile does **not** build inside the image. It `COPY`s a jar that must already exist:

```
ARG JAR_FILE=target/process-1.0-0.jar          # process/Dockerfile:39
COPY ${JAR_FILE} app.jar                       # process/Dockerfile:42
```

So the order is always: build the jar, then build the image.

```bash
cd /Users/nabeel.amd93/Desktop/Old-School/process
mvn package                       # writes target/process-1.0-0.jar
./run_process_docker.sh           # the safe path — see below
```

`run_process_docker.sh` is the recommended entry point because it refuses to deploy a stale jar
(L20–30): it fails if `target/process-1.0-0.jar` is missing, and fails again if anything under
`src/main` is newer than the jar. It then runs `docker-compose build process_app`,
`docker-compose up -d process_app`, and polls
`http://localhost:9098/api/v1/actuator/health` every 5s for up to 300s (L32–52).

Alternatives, both of which skip the staleness guard:

```bash
./docker-compose.sh start         # builds the jar with -DskipTests if absent, then compose up -d
docker-compose up -d              # raw; whatever jar is in target/ is what ships
```

`docker-compose.sh` (L51–101) builds with `mvn clean package -DskipTests` only when the jar is
absent — an existing but stale jar is used as-is.

**Verification**

| Piece | Command | Expected |
|---|---|---|
| API | `curl -s http://localhost:9098/api/v1/actuator/health` | `{"status":"UP"}` |
| API (container's own check) | `docker inspect --format '{{.State.Health.Status}}' process_app` | `healthy` — the check is `curl -f .../actuator/health`, `docker-compose.yml:211–216` |
| Postgres | `docker inspect --format '{{.State.Health.Status}}' postgres_db` | `healthy` — `pg_isready`, `docker-compose.yml:32–36` |
| Redis | `docker inspect --format '{{.State.Health.Status}}' redis` | `healthy` — `redis-cli ping`, `docker-compose.yml:85–89` |
| Kafka | `docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092` | broker listing; **there is no healthcheck on this service** |
| Zookeeper | `docker logs zookeeper` | no healthcheck defined |
| Kafka UI | open `http://localhost:8085` | topic list for cluster `etl-local` |
| RedisInsight | open `http://localhost:5540` | no healthcheck defined |
| Swagger | `http://localhost:9098/api/v1/swagger-ui.html` | per `docker-compose.sh:88` |
| Prometheus scrape | `http://localhost:9098/api/v1/actuator/prometheus` | exposed at `application.properties:15` |

Note the health endpoint answers `{"status":"UP"}` and nothing more:
`management.endpoint.health.show-details=when-authorized` (`application.properties:17`), and
`/actuator/health` is `permitAll` while every other actuator path requires `PLATFORM_ADMIN`
(`process/src/main/java/process/config/SecurityConfig.java:51–52`). The mail indicator is
deliberately excluded from the aggregate (`application.properties:18–25`) so a flaky sandbox SMTP
account cannot mark the container unhealthy. That exclusion now also means health says nothing at
all about outbound mail: the indicator it disables probes SMTP, which is no longer the transport
(§2.5), so `UP` is not evidence that mail works and never was.

Logs land in `process/logs/process.log`, rolled daily/10MB into `process/logs/archived/`
(`src/main/resources/logback.xml:3, 9–19`). The path is relative to the container's `WORKDIR /app`
(`Dockerfile:8`), and `./logs:/app/logs` (`docker-compose.yml:209`) surfaces it on the host.

Stop with `docker-compose down`, or `./docker-compose.sh stop`. `./docker-compose.sh stop-clean`
removes the volumes and prompts first (`docker-compose.sh:112–123`).

### 2.2 The `kafka-it` security stack

```bash
cd /Users/nabeel.amd93/Desktop/Old-School/process/kafka-it
./start.sh          # generates certs on first run, brings the broker up, waits, creates the SCRAM account
./stop.sh           # docker compose down -v; secrets/ and .env are left in place
```

`start.sh` regenerates certificate material if either `.env` or `secrets/` is missing (L8–11),
sources `.env` (L12), brings the compose file up, then polls
`kafka-broker-api-versions --bootstrap-server localhost:19092` inside the container up to 60 times
at 2s intervals (L16–23). Once the broker answers it creates the SCRAM account in Zookeeper
(L25–30) — SCRAM credentials cannot live in a JAAS entry the way PLAIN's does, so this step can
only happen after the cluster is running. It is idempotent.

`generate-certs.sh` builds a throwaway CA, a broker identity, a client identity, and client stores
in **both** PKCS12 and JKS (L26–74), then writes `.env` with `STORE_PASSWORD`, `SASL_USER=etl` and
a freshly generated `SASL_PASSWORD` (L83–92). Both passwords are `openssl rand -hex 16` (L20, L83)
— nothing here is a value anybody typed or could reuse. The broker certificate's SAN covers
`localhost`, `kafka-it`, `host.docker.internal` and `127.0.0.1` (L41); omitting
`host.docker.internal` failed every TLS profile with a handshake error, which the script's comment
records was the hostname check working, not a broken certificate.

**Verification**

```bash
docker ps --format '{{.Names}}' | grep -x kafka_it
docker exec kafka_it kafka-broker-api-versions --bootstrap-server localhost:19092
for p in 19092 19093 19094 19095 19096 19097 19098; do nc -z localhost $p && echo "$p open"; done
```

`start.sh:33–36` prints the listener map on success.

### 2.3 The `scheduler1` frontend

```bash
cd /Users/nabeel.amd93/Desktop/Old-School/scheduler1
docker-compose build --no-cache
docker-compose up -d
curl -s http://localhost/health          # -> OK
open http://localhost/scheduler/
```

`DEPLOYMENT.md:17–23` is the source for those commands, and `DEPLOYMENT.md:39–44` for the two
health URLs — both are answered by nginx (`nginx.conf:33–37, 48–52`) without touching the app, so a
healthy container means nginx started and says nothing about whether the Angular bundle is good.
The image is two-stage: Node 14 Bullseye builds (`Dockerfile:5–31`), nginx 1.27-alpine serves
(`Dockerfile:36–49`). The build stage does
`rm -rf dist` before building (`Dockerfile:21`) so a stale host `dist/` cannot be shipped —
belt-and-braces, since `.dockerignore:1` already excludes `dist`. Two patch steps run around the
build (`patch.js`, `patch_dist.js`, `Dockerfile:24, 31`) to fix out-of-order Unicode ranges in
emitted regexes; both are `|| true`, so a failure there is silent.

The container healthcheck uses `127.0.0.1` rather than `localhost`
(`scheduler1/docker-compose.yml:14–17`), because nginx binds IPv4 only (`nginx.conf:2`) and
`localhost` inside the container can resolve to `::1` first.

Dev server for the old app:

```bash
cd /Users/nabeel.amd93/Desktop/Old-School/scheduler1
npm start     # cross-env NODE_OPTIONS=--openssl-legacy-provider webpack-dev-server --mode development --open --open-page scheduler/
```

(`scheduler1/package.json:10`.) No port is given on that command line and
`webpack.config.js:78–83` sets only `publicPath` and `historyApiFallback`, so this takes
webpack-dev-server's default port — **not verified** against a running instance, and see §8 for the
`8084` discrepancy.

### 2.4 The Angular 22 rewrite

```bash
cd /Users/nabeel.amd93/Desktop/Old-School/scheduler1/next
npm install
npm start          # ng serve, default http://localhost:4200/
npm run build      # ng build, defaultConfiguration "production"
npm test           # ng test, @angular/build:unit-test -> vitest
```

Sources: `scheduler1/next/package.json:5–9`, `angular.json:53, 65, 67–69`,
`scheduler1/next/README.md:9–13`.

Also runs in Docker: `scheduler1/next/Dockerfile` (two-stage, `node:22-alpine` build ->
`nginx:1.27-alpine` runtime), `nginx.conf`, `docker-compose.yml` (`4400:80`). Verified end to end
on 2026-09-03 -- image builds clean, container reports healthy, `/` and a path-based deep link
(`/admin/users`) both return 200, and a login submitted through the browser reaches the real
backend at `http://localhost:9098/api/v1/auth.json/login` with a correct CORS preflight and a
correctly rendered error for bad credentials. `API_BASE` (`api.config.ts`) is derived from
`window.location.hostname` at runtime, so the container needs no build arg or environment variable
to find the backend -- only that it is reachable at the same hostname on `:9098`. Port 4400 was
chosen because `process/docker-compose.yml`'s `WEBSOCKET_ALLOWED_ORIGINS` default and the
backend's `app.console.url` default already assume the console lives there.

This is dev-parity infrastructure, not a production decision: nothing in this workspace routes
production traffic to it yet, and there is no CI building or publishing the image.

### 2.5 Outbound mail — SES against LocalStack

Mail no longer goes over SMTP. `process/src/main/java/process/emailer/MailTransport.java` is the
interface, `SesMailSender` is the default implementation
(`@ConditionalOnProperty(name = "app.mail.transport", havingValue = "ses", matchIfMissing = true)`,
`SesMailSender.java:39`) and it calls the AWS SDK's `SendRawEmail` with the MIME message
`EmailMessagesFactory` already builds, so attachments, CC and the HTML body are unchanged by the
move (`SesMailSender.java:74–83`). The dependency is `software.amazon.awssdk:ses` 2.25.60,
the same SDK and version as the S3 client (`pom.xml:265–271`).

**The SMTP path still exists and is deprecated.** `SmtpMailSender` is annotated `@Deprecated` and
only becomes a bean at `app.mail.transport=smtp` (`SmtpMailSender.java:21–23`); its constructor
logs a warning saying so (L31–34). `spring.mail.*` in all three profiles is now dead configuration
unless that property is set — each profile marks it (`application-dev.properties:92`,
`application-stage.properties:95`, `application-prod.properties:97`).

**Locally, SES is LocalStack.** Observed on 2026-09-08: container `localstack-aws`, image
`localstack/localstack-pro:latest`, publishing `127.0.0.1:4566` (plus 443 and 4510–4559).

It is **declared by no compose file in this workspace** — `grep -rni localstack` across `process`,
`scheduler1` and `job-search` matches only comments (`pom.xml:266`, `docker-compose.yml:145`,
`SesMailSender.java:29, 51`), never a service — so it is started by hand, like Ollama. And
`docker inspect` puts it on the default `bridge` network while `process_app` is on
`process_default`, so the app cannot reach it by container name at all. `AWS_SES_ENDPOINT`
therefore defaults to
`http://host.docker.internal:4566` (`docker-compose.yml:150`) — the same host-gateway route the
app already uses for MinIO, OpenSearch, Ollama and the audio service, and the reason `extra_hosts`
exists at `docker-compose.yml:134–135`. It is one more instance of the §1.3 addressing rule, not an
exception to it.

```bash
# Which transport actually loaded — the constructor logs it on every boot (SesMailSender.java:71)
docker logs process_app 2>&1 | grep 'Outbound mail transport'   # -> SES us-east-1 at http://host.docker.internal:4566

# The From address must be a verified SES identity or the send is refused
docker exec localstack-aws awslocal ses list-identities         # -> no-reply@etl-console.local
```

Both were run on 2026-09-08 with the results shown. The identity matches the `app.mail.from`
default (`application-dev.properties:126`).

Two things make a broken transport quiet, and they are unchanged by this move: the send is inside a
`catch (Exception)` that logs and returns rather than raising
(`EmailMessagesFactory.java:234, 241`), and the mail health indicator is deliberately off
(`management.health.mail.enabled=false`, `application.properties:25`), so `/actuator/health` stays
`UP` whatever mail is doing. The startup log line above is the only cheap way to tell which
transport is live.

`application-e2e.properties:40–50` was **not** updated for the switch: it still configures
`spring.mail.*` at `localhost:1025` and sets no `app.mail.transport`, so the e2e context builds a
`SesMailSender` pointing at the real AWS endpoint under the default credential chain. Nothing in
the suite sends mail, so this has no observed effect — but the SMTP settings there now describe a
path that profile does not take.

### 2.6 Analytics Studio — DuckDB runs inside the backend JVM

Added **2026-09-08**. There is nothing here to bring up, and that is the whole operational story.

**DuckDB is embedded. It runs in the `process_app` JVM, as the backend, sharing that process's
memory with the ETL dispatcher.** It is not a container, not a service, not a port, and it appears
in no compose file — which is exactly why it is easy to miss when reading a `docker ps` and
concluding you have seen the stack. `process/pom.xml:273–281` adds the single dependency:

```xml
<groupId>org.duckdb</groupId>
<artifactId>duckdb_jdbc</artifactId>
<version>1.1.3</version>
```

The comment above it (`pom.xml:273–276`) states the trade the choice was made for: embedded means
no server to operate, and the extension reads object storage directly, so a 1 GB scan never streams
through Spring.

**The jar ships native libraries, and it is large.** 72,932,587 bytes (~70 MB) in
`~/.m2/repository/org/duckdb/duckdb_jdbc/1.1.3/`, because it carries four prebuilt engines rather
than a platform-specific classifier:

| Entry in the jar | Uncompressed |
|---|---|
| `libduckdb_java.so_linux_amd64` | 54.6 MB |
| `libduckdb_java.so_linux_arm64` | 50.9 MB |
| `libduckdb_java.so_osx_universal` | 98.1 MB |
| `libduckdb_java.so_windows_amd64` | 28.3 MB |

Spring Boot's repackaging stores a dependency jar inside the fat jar without recompressing it, so
all ~70 MB lands whole in the deployable artefact: `BOOT-INF/lib/duckdb_jdbc-1.1.3.jar`,
72,932,587 bytes, inside a `target/process-1.0-0.jar` of 205,593,272 bytes. **DuckDB is about a
third of the jar that every image build `COPY`s** (§2.1). All of the above verified with `ls -la`
and `unzip -l` on 2026-09-08.

The runtime combination in use is **Java 17 Temurin on linux/aarch64 (Ubuntu 26.04)**, which is
served by the `linux_arm64` entry above. The container's base image is `eclipse-temurin:17-jdk`
(`process/Dockerfile:2`), matching the JDK the build is pinned to (§6.3).

DuckDB unpacks its native library on first use, so `DuckDbSessionFactory` loads the driver in a
`static` block rather than leaving it to JDBC auto-discovery
(`process/src/main/java/process/analytics/DuckDbSessionFactory.java:53–60`). The effect at run time
is that a broken or unloadable native library **names itself at startup** instead of surfacing as a
`ClassNotFoundException` inside the first analytics request after a restart.

**Why the memory point matters operationally.** `analytics.duckdb.memory-limit` is DuckDB's ceiling
**per connection** and a session is opened per query, so the worst case is
`max-concurrent × memory-limit` — **4 × 512 MB = 2 GB** on the defaults — held by the engine at the
same time as the JVM heap, in the same container as the crons in `discovery/backend.md` §5. The
`AnalyticsLimits` javadoc says as much directly (`AnalyticsLimits.java:46–52`: each concurrent query
"can hold DuckDB's memory limit at the same time"). Two things make that worth writing down here
rather than only in the code:

- **`process_app` has no memory limit.** There is no `mem_limit` and no `deploy.resources` on the
  service (`docker-compose.yml:126–216`), and no `JAVA_OPTS`/`-Xmx` is set anywhere in the compose
  file or the Dockerfile. Nothing bounds the container's total footprint; the six `analytics.*`
  properties are the only bound on the analytics half of it.
- **Nothing in the stack fails visibly first.** `/actuator/health` reports `{"status":"UP"}` and
  nothing more (§2.1), so memory pressure from an analytics scan shows up as the container's OOM
  killer taking the backend — dispatcher included — rather than as a degraded health check.

**Verification.** There is no endpoint to poll and no process to check; the module is exercised
through the API:

```bash
# Both require a TENANT_USER bearer token. Reads a dataset in place; writes nothing.
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:9098/api/v1/analytics.json/schema?connection=<alias>&path=sales.csv"
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:9098/api/v1/analytics.json/preview?connection=<alias>&path=sales.csv&page=0"
```

Verified live against **MinIO** on 2026-09-08 through both the API and the UI: a 7-row / 4-column
`sales.csv`, whose schema came back as `region`/`rep`/`product` `VARCHAR` and `amount` `DOUBLE`; a
glob over three partition files read as **one** dataset (7 rows, 5 columns — the extra column is the
filename DuckDB adds for a multi-file scan, each row carrying its own
`s3://etl-bucket/etl-demo/F768945/out/<file>.csv`); and a Parquet read. Those partition files are
the output of the `csv_partition` pipeline in §7, which is the only cross-reference between the two
pieces of work done that day — the reader is otherwise unrelated to the ETL side. The five
refusal paths each returned a friendly `ERROR`, never a stack trace. Both layers of the path
confinement were observed separately on an absolute path (`/etc/passwd.csv`): it is confined
**inside the connection's bucket** by `DatasetResolver`, and there is separately **no local
filesystem left for it to reach** inside the session. Azure was **not** exercised — see §8.

---

## 3. Environment variables

### 3.1 Where they come from

`process/docker-compose.yml` supplies `process_app`'s environment explicitly (L136–184). Docker
Compose auto-loads `process/.env` from the compose file's own directory to resolve the `${VAR}`
references in it. `process/.env.example` lists the ten keys that file is expected to carry:
`EFS_FILE_DIRE`, `SPRING_DATASOURCE_URL`, `SPRING_DATASOURCE_USERNAME`,
`SPRING_DATASOURCE_PASSWORD`, `SPRING_KAFKA_BOOTSTRAP_SERVERS`, `MAIL_HOST`, `MAIL_PORT`,
`MAIL_USERNAME`, `MAIL_PASSWORD`, `WORKER_CALLBACK_TOKEN`.

Two of those are read from `.env` but then **overridden** in the compose file and therefore never
reach the app: `SPRING_DATASOURCE_URL` (hardcoded to `jdbc:postgresql://postgres:5432/etl_job` at
L138) and `SPRING_KAFKA_BOOTSTRAP_SERVERS` (hardcoded to `kafka:9092` at L141). Two others are
consumed by the *postgres* container rather than the app: `SPRING_DATASOURCE_USERNAME` and
`SPRING_DATASOURCE_PASSWORD` become `POSTGRES_USER`/`POSTGRES_PASSWORD` at L20–21.

`.env.example` is now behind the code on one point: its four mail keys are `MAIL_HOST`,
`MAIL_PORT`, `MAIL_USERNAME` and `MAIL_PASSWORD` — the **deprecated SMTP** set (§2.5). The keys
the default transport reads (`MAIL_FROM`, `MAIL_TRANSPORT`, `AWS_SES_*`) are not listed there at
all; they exist only as compose defaults at `docker-compose.yml:148–153`.

`process/src/test/java/process/config/ApplicationPropertiesDeclarationTest.java` is the guard rail
here. It asserts that every profile declares the properties its code reads (L33–41, L68–76) and
that every credential-bearing property is declared as `${VAR:}` with an empty default and never a
literal value (L43–53, L102–117). That test only reads `application-*.properties` — it does not see
`docker-compose.yml`, which is where the exceptions in §8 live.

### 3.2 The application's variables

Secrets are marked **S**. No value for any of them appears in this document.

| Variable | Property | What it does | Source of the value | S |
|---|---|---|---|---|
| `SPRING_PROFILES_ACTIVE` | — | `dev` in compose (`docker-compose.yml:137`); base default also `dev` (`application.properties:7`) | compose literal | |
| `SPRING_DATASOURCE_URL` | `spring.datasource.url` | JDBC URL (`application-dev.properties:65`) | compose literal L138 | |
| `SPRING_DATASOURCE_USERNAME` | `spring.datasource.username` | DB user; also `POSTGRES_USER` | `process/.env` | |
| `SPRING_DATASOURCE_PASSWORD` | `spring.datasource.password` | DB password; also `POSTGRES_PASSWORD` | `process/.env` | **S** |
| `POSTGRES_DB` | — | Database name, default `etl_job` (L22) | compose default | |
| `SPRING_KAFKA_BOOTSTRAP_SERVERS` | `spring.kafka.bootstrap-servers` | Bound into Spring's `KafkaProperties`, consumed by `KafkaProducerConfig.java:24–33` | compose literal L141 | |
| `SPRING_REDIS_HOST` / `SPRING_REDIS_PORT` | `spring.redis.*` | Redis connection for `RedisConfig.java` and the presence registry | compose literals L142–143 | |
| `EFS_FILE_DIRE` | `storage.efsFileDire` (`application-dev.properties:4`) | Local file staging directory; also the `/tmp/efs` bind mount (L194) | `process/.env`, compose default `/tmp/efs` | |
| `MAIL_TRANSPORT` | `app.mail.transport` (`application-dev.properties:127`) | Picks the outbound mail bean: `ses` (default, `SesMailSender`) or `smtp` (deprecated, `SmtpMailSender`). Nothing else selects a transport — see §2.5 | compose default `ses` at L149 | |
| `MAIL_FROM` | `app.mail.from` (`application-dev.properties:126`) | The From address on every outgoing message. Was `${spring.mail.username}`, which is an SMTP **login** rather than an address; SES rejects that, so it became its own setting (`EmailMessagesFactory.java:32–40`). Must be a verified SES identity | compose default `no-reply@etl-console.local` at L148 | |
| `AWS_SES_ENDPOINT` | `app.mail.ses.endpoint` (`application-dev.properties:129`) | Blank on a real deployment (the SDK's own regional endpoint applies). Locally it points at LocalStack over the host gateway | compose default `http://host.docker.internal:4566` at L150 | |
| `AWS_SES_REGION` | `app.mail.ses.region` (`application-dev.properties:128`) | SES region, default `us-east-1` | compose default L151 | |
| `AWS_SES_ACCESS_KEY`, `AWS_SES_SECRET_KEY` | `app.mail.ses.access-key` / `.secret-key` (`application-dev.properties:130–131`) | Only supplied for LocalStack. Left blank, `SesMailSender.java:62–67` skips the static provider entirely and the default chain picks up the instance's IAM role — which is what moving off SMTP removes a stored credential pair *for* | compose defaults are LocalStack's placeholder pair at L152–153 — see §8 | **S** (nominally) |
| `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME` | `spring.mail.*` (`application-dev.properties:92–95`) | **Deprecated.** SMTP host/port/login, read only when `MAIL_TRANSPORT=smtp` | compose defaults (Mailtrap sandbox) at L154–156 / `.env` | |
| `MAIL_PASSWORD` | `spring.mail.password` | **Deprecated.** SMTP password, read only when `MAIL_TRANSPORT=smtp` | compose has a **literal default** at L157 — see §8 | **S** |
| `LOOKUP_ENCRYPTION_KEY` | `lookup.encryption.key` (`application-dev.properties:10`) | Base64 256-bit AES key for encrypted lookup values and stored connection credentials. Rotating it makes existing ciphertext undecryptable (`docker-compose.yml:158–162`). `EncryptionUtil.java:60–61` throws when it is blank | compose has a **literal default** at L162 — see §8 | **S** |
| `JWT_SECRET_KEY` | `jwt.secret.key` (`application-dev.properties:15`) | Base64 256-bit HMAC key. `JwtUtil.java:83` throws `IllegalStateException` if unset. Rotating logs everyone out | compose has a **literal default** at L166 — see §8 | **S** |
| `JWT_ACCESS_TOKEN_EXPIRY_MINUTES` | `jwt.access-token.expiry-minutes` | Default 30 (`application-dev.properties:16`) | unset | |
| `JWT_REFRESH_TOKEN_EXPIRY_DAYS` | `jwt.refresh-token.expiry-days` | Default 7 (`application-dev.properties:17`) | unset | |
| `WORKER_CALLBACK_TOKEN` | `worker.callback.token` (`application-dev.properties:108`) | Shared secret the ETL workers send as `X-Worker-Token` on `/changeState`, `/addLogs`, `/addLogsBatch`. **The app refuses to start without it** — `NotifyResetApi.java:56–64`, `@PostConstruct`. Those three paths are `permitAll` in the filter chain (`SecurityConfig.java:42`), so this token is the only thing authenticating them. Must match the workers' value (`job-search/docker-compose.yml:26, 60, 110`) | `process/.env`; compose passes it through with **no** default (L176) | **S** |
| `PLATFORM_ADMIN_BOOTSTRAP_PASSWORD` | `platform.admin.bootstrap-password` (`application-dev.properties:114`) | Password the seeded `admin@platform.local` account is created with, read only on first boot against an empty DB. Unset means **no platform admin is seeded at all** — `TenantSeedService.java:108–110` logs an error and continues | **not set anywhere in this workspace** — not in compose, not in `.env.example` | **S** |
| `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | `minio.*` (`application-dev.properties:22–25`) | Legacy passthrough only. Credentials now live encrypted in the `storage_connection` table; `StorageConnectionBootstrap.java:55–61` copied these in on first startup and nothing reads them once a bucket has a connection row (`docker-compose.yml:167–172`) | compose passes through, no default (L177–179) | **S** (keys) |
| `AWS_S3_ACCESS_KEY`, `AWS_S3_SECRET_KEY`, `AWS_S3_REGION` | `aws.s3.*` (`application-dev.properties:26–28`) | S3 bucket browser; region defaults `us-east-1`. Separate from the `AWS_SES_*` pair above — object storage and mail are configured independently | compose passthrough (L191–193) | **S** (keys) |
| `AZURE_STORAGE_CONNECTION_STRING` | `azure.storage.connection-string` | Azure Blob bucket browser | compose passthrough (L194) | **S** |
| `STORAGE_ALLOW_INSTANCE_ROLE` | `storage.allow-instance-role` | Whether a keyless S3 connection may fall through to the host IAM role. Default `false` — fail closed (`application-dev.properties:34`, `StorageClientFactory.java:52`) | unset | |
| `OPENSEARCH_URL` | `opensearch.url` (`application-dev.properties:23`) | Job audit log sink, read by `OpenSearchAuditLogClient.java:36`. Default `http://host.docker.internal:9200`, i.e. the `job-search` integrated stack's published port | compose default L183 | |
| `AI_ALLOWED_ENDPOINT_HOSTS` | `ai.allowed-endpoint-hosts` | Allowlist of hosts an AI agent may be pointed at over a private address or plain http; default `host.docker.internal` (`application-dev.properties:43`, `AiAgentServiceImpl.java:82`) | unset | |
| `KAFKA_SECRET_CACHE_DIR` | `kafka.secret-cache.dir` | Where truststores/keystores downloaded for a connection profile are cached. Unset lands in the shared JVM temp dir (`application-dev.properties:47–50`, `KafkaTemplateProvider.java:73`) | unset | |
| `KAFKA_SSL_LOCAL_STORE_DIR` | `kafka.ssl.local-store-dir` | The one directory a profile may name a store in without going through a storage bucket. Unset = no bucket-less path accepted at all (`application-dev.properties:51–56`) | unset | |
| `KAFKA_TOPIC_DEFAULT_REPLICATION_FACTOR` | `kafka.topic.default-replication-factor` | `1` in dev/stage, `-1` (ask the broker) in prod — `application-dev.properties:59`, `application-prod.properties:66`, `application-stage.properties:63` | unset | |
| `WEBSOCKET_ALLOWED_ORIGINS` | `websocket.allowed-origins` | STOMP/SockJS origin allowlist, read at `WebSocketConfig.java:25–26`. **Only prod and stage declare this property** (`application-prod.properties:21`, `application-stage.properties:21`); the `dev` profile has no line for it, which is why compose supplies it directly with a long default including the LAN IP (`docker-compose.yml:195–200`) | compose default L200 | |
| `AVATAR_BUCKET` | `app.avatar.bucket` | Single shared bucket for profile pictures, default `etl-avatar` (`application-dev.properties:118`) | unset | |
| `DOCUMENT_CONVERTER_MAX_FILE_SIZE_MB` | `document.converter.max-file-size-mb` | Default 50; the response base64s the output, so each conversion costs ~4x the file size in heap (`application.properties:75–77`) | unset | |
| `AUDIO_EXTRACT_MAX_FILE_SIZE_MB` | `audio.extract.max-file-size-mb` | Default 250 (`application.properties:78–80`) | unset | |
| `SCHEDULER_POOL_SIZE` | `spring.task.scheduling.pool.size` | Default 5 — one thread per cron. `application.properties:82–90` records that a single shared thread let a slow query sweep stop the minute-cycle ETL crons outright | unset | |

**Analytics Studio's six**, added 2026-09-08. All six are declared in **all three** profiles
(`application-dev.properties:133–142`, `application-stage.properties:136–145`,
`application-prod.properties:136–145`) with identical values, and all six are read by the single
`AnalyticsLimits` bean (`process/src/main/java/process/analytics/AnalyticsLimits.java`). None of
them appears in `docker-compose.yml` or `.env.example` — confirmed by grep on 2026-09-08 — so on
every stack in this workspace the property default in the table below is what is actually in force,
and changing one means editing a properties file or adding a compose entry. Each is a limit on what
a single analytics request may take **from the ETL dispatcher sharing the JVM** (§2.6), which is
what the comment above them in each profile says.

| Variable | Property | Default | What it protects against | Source of the value | S |
|---|---|---|---|---|---|
| `ANALYTICS_QUERY_TIMEOUT_SECONDS` | `analytics.query.timeout-seconds` | `30` | A request thread held indefinitely by a scan that will never finish. Applies to the whole statement, and bounds how long one caller may hold a concurrency slot | unset | |
| `ANALYTICS_QUERY_MAX_ROWS` | `analytics.query.max-rows` | `10000` | A result set with no cap — serialised into a JSON response and then held by the browser. The bound is applied as a SQL `LIMIT`, so the rows are never read rather than being read and then truncated. In phase one its only caller is `pageSize()` (`AnalyticsQueryService.java:137–140`), which clamps a requested page size to it; the wider ceiling the javadoc describes matters once a later phase runs arbitrary queries | unset | |
| `ANALYTICS_QUERY_MAX_CONCURRENT` | `analytics.query.max-concurrent` | `4` | Unbounded parallel scans, each entitled to the memory limit below. This is the multiplier in the 4 × 512 MB worst case (§2.6). Requests past it are **refused after a 2-second wait**, not queued | unset | |
| `ANALYTICS_PREVIEW_PAGE_SIZE` | `analytics.preview.page-size` | `100` | Nothing on its own — it is the default page a browser gets when the caller names no `pageSize`. Clamped by `max-rows` above | unset | |
| `ANALYTICS_DUCKDB_MEMORY_LIMIT` | `analytics.duckdb.memory-limit` | `512MB` | **The container's OOM killer taking the whole backend.** With no limit set, a large scan competes with the ETL dispatcher for the same memory; with one, DuckDB spills or fails instead. Regex-restricted to `[0-9]+[A-Za-z]{0,3}` before being interpolated into SQL — a mistyped value would otherwise be able to unlock the engine (`DuckDbSessionFactory.java:214–227`) | unset | |
| `ANALYTICS_DUCKDB_THREADS` | `analytics.duckdb.threads` | `2` | Analytics starving the dispatcher of CPU. Worker threads **per DuckDB connection**, so the real ceiling is this times `max-concurrent` | unset | |

**These six are enforced by `ApplicationPropertiesDeclarationTest`.** All of them are on its
`REQUIRED_IN_EVERY_PROFILE` list (`process/src/test/java/process/config/ApplicationPropertiesDeclarationTest.java:46–51`),
so a profile that omits one fails the build rather than silently taking the `@Value` default. The
comment on that block (`:43–45`) gives the reason in one line: **an absent limit is an unlimited
one**, and DuckDB runs in this JVM, so a missing memory ceiling is the OOM killer taking the ETL
dispatcher down along with the query. That is the same guard rail §3.1 describes, applied to a case
where the failure is operational rather than a leaked credential. None of the six is a secret, so
none is on the `SECRETS` list.

Properties read **only** as a Java `@Value` default, declared in no properties file — exactly the
pattern `ApplicationPropertiesDeclarationTest` (L15–26) exists to stamp out, and still present for
these:

| Property | Default | Read at |
|---|---|---|
| `app.console.url` | `http://localhost:4400` | `AppUserServiceImpl.java:71`, `TenantRequestServiceImpl.java:68` |
| `ollama.base.url` | `http://host.docker.internal:11434` | `OllamaServiceImpl.java:28`, `FileChatExtractionServiceImpl.java:63` |
| `ollama.vision.model` | `llava` | `FileChatExtractionServiceImpl.java:66` |
| `audio.extract.service.base.url` | `http://host.docker.internal:8100` | `AudioTranscriptServiceImpl.java:43` |
| `query-engine.max-rows` | `1000000` | `QueryExecutionRunner.java:109` |
| `query-engine.query-timeout-seconds` | `300` | `QueryExecutionRunner.java:112` |
| `report.submit.allow-internal` | `false` | `ReportExportServiceImpl.java:67` |
| `audit.log.sync.initial-lookback-days` | `30` | `AuditLogSyncCron.java:31` |
| `kafka.secret.max-file-size-kb` | `512` | `KafkaSecretServiceImpl.java:53` |

### 3.3 The `kafka-it` stack's variables

`process/kafka-it/.env` is generated by `generate-certs.sh:87–92` and gitignored
(`kafka-it/.gitignore:3–4`). It holds exactly three keys:

| Variable | What it does | Where it comes from | S |
|---|---|---|---|
| `STORE_PASSWORD` | Password for the broker keystore, key, and truststore — passed as `KAFKA_SSL_KEYSTORE_PASSWORD`, `KAFKA_SSL_KEY_PASSWORD`, `KAFKA_SSL_TRUSTSTORE_PASSWORD` (`docker-compose.kafka-it.yml:83–87`). Also written to `secrets/store-password`, which the matrix test reads (`KafkaSecurityMatrixIT.java:98`) | `openssl rand -hex 16`, `generate-certs.sh:20` | **S** (throwaway) |
| `SASL_USER` | The SASL account name, literally `etl` (`generate-certs.sh:89`) | generated file | |
| `SASL_PASSWORD` | Password for the PLAIN JAAS entries (`docker-compose.kafka-it.yml:106–113`) and the SCRAM account created by `start.sh:28–30` | `openssl rand -hex 16`, `generate-certs.sh:83` | **S** (throwaway) |

The compose file is explicit that these end up visible to `docker inspect`, and explicit about why
that is acceptable *here only*: the stack is generated per run, holds nothing but throwaway
certificates, and is destroyed by `stop.sh` (`docker-compose.kafka-it.yml:78–80`).

### 3.4 The `job-search` workers' variables (out of scope, listed for the shared secret)

The one that couples to `process` is `WORKER_CALLBACK_TOKEN`
(`job-search/docker-compose.yml:24–26, 58–60, 110`). Set it to the same value on both sides or the
backend rejects every `/changeState` and `/addLogs` callback and job status silently stops
updating. Credentials in that stack are declared `${VAR:?}` with no default so the stack refuses to
start rather than coming up on a committed value (`job-search/docker-compose.yml:8–10`);
`job-search/.env.example` lists the names.

---

## 4. The test stacks

Three suites, three different requirements. `process/README.md:94–98` gives the counts:

| Suite | Command | Needs | Count (per README) |
|---|---|---|---|
| Unit | `mvn -o test` | nothing running | 516 |
| End-to-end over real HTTP | `./run-e2e.sh` | `process_app` + `postgres_db` up | 86 |
| Kafka security matrix | `./run-kafka-matrix.sh` | `kafka_it` up, **and a container to run in** | 17 |

The counts are the README's claim, not something re-measured here — and the unit figure is now
stale twice over. `mvn test` reported **587 passing** on 2026-09-08, and **607** later the same day
once Analytics Studio's twenty landed (`process/src/test/java/process/analytics/`, 13 + 7 — see
`discovery/backend.md` §8.4); `process/README.md:96` still says 516. The other two rows were not
re-run, and neither gained a case. The analytics tests need **no container**: `DatasetResolverTest`
is a plain unit test, and `DuckDbLockdownTest` runs a real but embedded and in-memory DuckDB against
a MinIO connection deliberately given no endpoint, "so no network call is attempted by these tests"
(`DuckDbLockdownTest.java:67`). They do exercise the real native library, though — so a machine
where that fails to unpack (§2.6) fails these seven rather than only failing at run time.

### 4.1 The end-to-end suite

Entry point: `process/run-e2e.sh`.

```bash
cd /Users/nabeel.amd93/Desktop/Old-School/process
./run-e2e.sh
```

It runs `mvn -o test -Dtest='*E2EIT,HarnessSmokeIT'` (L31) — offline, so `~/.m2` must already be
warm.

**How it gets its credentials.** Nothing secret is stored for this suite. `run-e2e.sh` reads three
values out of the *running* `process_app` container with `docker exec … printenv` (L20–28):

| Exported | Read from the container's | Why |
|---|---|---|
| `E2E_DATASOURCE_USERNAME` | `SPRING_DATASOURCE_USERNAME` | the suite talks to the same dev database |
| `E2E_DATASOURCE_PASSWORD` | `SPRING_DATASOURCE_PASSWORD` | ditto |
| `E2E_LOOKUP_ENCRYPTION_KEY` | `LOOKUP_ENCRYPTION_KEY` | without the *application's own* key, every stored credential — including the `etl-avatar` connection's secret key — fails to decrypt, and a request the guard admits is refused a step later by the storage layer instead. That is a refusal the tests cannot tell apart from the ones they are asserting about (L23–27) |

If `process_app` is not running the script exits with a message telling you to start the stack or
supply the variables yourself (L13–18). Each is overridable — `${E2E_DATASOURCE_USERNAME:-…}` —
so a different stack can be targeted.

`process/src/test/resources/application-e2e.properties` fills in everything else:

- datasource URL defaults to `jdbc:postgresql://localhost:5433/etl_job`, i.e. the **host-published**
  Postgres port (L12) — the suite runs on the host, not in a container;
- username and password default to empty (L13–14), so the suite simply cannot run without the
  environment;
- Liquibase off and `ddl-auto=none` (L17–18) — the database has already been migrated;
- a JWT signing key is committed here **on purpose** and is not a credential: it signs tokens for
  users the suite creates inside a transaction that is rolled back, and the base64 decodes to a
  sentence saying so (L29–32);
- `worker.callback.token=e2e-placeholder-not-a-secret` (L37) exists only to satisfy the
  `@PostConstruct` startup check in `NotifyResetApi.java:56–64`;
- mail points at a nonexistent `localhost:1025` and JODConverter is disabled (L40–53), because a
  developer's machine has no LibreOffice. The mail half of that is now describing a path this
  profile does not take: those are `spring.mail.*` settings, the profile sets no
  `app.mail.transport`, and the default is `ses` — see §2.5.

Isolation comes from `E2ESupport` (`src/test/java/process/e2e/E2ESupport.java:55–59`):
`@SpringBootTest` + `@AutoConfigureMockMvc` + `@ActiveProfiles("e2e")` + `@Transactional`, so each
test rolls back. `OfficeManager` and `DocumentFormatRegistry` are the only mocks (L61–62) — nothing
security-relevant is stubbed, and tokens are minted with the application's own `JwtUtil`.

Suites in scope of the default run: `HarnessSmokeIT`, `BucketAccessE2EIT`, `KafkaSecretE2EIT`,
`TenantLifecycleE2EIT`, `UserManagementE2EIT`. `ContextProbeIT` is **not** matched by
`-Dtest='*E2EIT,HarnessSmokeIT'` and only runs if named explicitly.

### 4.2 The Kafka security matrix

Entry point: `process/run-kafka-matrix.sh`, after `kafka-it/start.sh`.

```bash
cd /Users/nabeel.amd93/Desktop/Old-School/process
./kafka-it/start.sh
./run-kafka-matrix.sh
./kafka-it/stop.sh
```

**It must run in a container, and this is not a preference.** Every listener in
`docker-compose.kafka-it.yml:68` advertises `host.docker.internal`, so that the application
container (which has `host.docker.internal:host-gateway`, `docker-compose.yml:134–135`) can reach
the broker. The host cannot resolve that name. A run from the host connects to `localhost:1909x`
perfectly well, is handed back `host.docker.internal:1909x` as the node to actually talk to, and
then sits there until the call times out. `run-kafka-matrix.sh:4–13` records exactly what that
looks like: **thirteen `TimeoutException`s saying "Timed out waiting for a node assignment", no
handshake error, no authentication error, and the four cases that never open a connection still
passing** — a failure mode that reads like a code regression and is not one.

So the script (L32–45):

1. checks `kafka_it` is running, and points at `kafka-it/start.sh` if not (L22–26);
2. discovers the broker's network from `docker inspect` (L28–29) — in practice `kafka-it_default`;
3. runs `maven:3.9-eclipse-temurin-17` on that network with
   `--add-host host.docker.internal:host-gateway`, mounting the repo at `/w` and `~/.m2`;
4. writes a throwaway `toolchains.xml` pointing at the image's own `$JAVA_HOME`, because the
   repository's `~/.m2/toolchains.xml` names a macOS path that does not exist in the container
   (L38–42);
5. runs `mvn -o -t /tmp/toolchains.xml test -Dtest=KafkaSecurityMatrixIT -Dkafka.it.host=host.docker.internal`.

`kafka.it.host` is a JVM system property read at `KafkaSecurityMatrixIT.java:73` (with the reasoning
in the comment at L61–72), defaulting to `localhost` — the value that works from a developer's own
machine for the parts that do not need the advertised address.

**JDK 17 is also not a preference.** `kafka-clients` 2.5 authenticates through
`Subject.getSubject(AccessController.getContext())`, removed with the SecurityManager in JDK 24, so
a build that forks a newer JVM fails every SASL case on something that cannot happen in production.
The test itself guards this with an assumption (`KafkaSecurityMatrixIT.java:92–95`), the build pins
it with `maven-toolchains-plugin` (`pom.xml:284–317`), and `~/.m2/toolchains.xml` on this machine
points at `/Library/Java/JavaVirtualMachines/jdk-17.jdk/Contents/Home`. Live check: `mvn -v`
reports Maven 3.9.9 and `java -version` reports 17.0.12 — but the toolchain file's own comment says
`mvn` here has run on a Homebrew JDK 25, so the pin is doing real work.

**What the seven listeners are** (`docker-compose.kafka-it.yml:8–16`, echoed by `start.sh:34–36`):

| Port | Security | Listener name |
|---|---|---|
| 19092 | PLAINTEXT | `PLAINTXT` |
| 19093 | SSL, server auth only | `SSLONLY` |
| 19094 | SSL + client auth required (mTLS) | `SSLMTLS` |
| 19095 | SASL_PLAINTEXT / PLAIN | `SASLPLAIN` |
| 19096 | SASL_SSL / PLAIN | `SASLSSLPLAIN` |
| 19097 | SASL_PLAINTEXT / SCRAM-SHA-256 | `SASLSCRAM256` |
| 19098 | SASL_SSL / SCRAM-SHA-512 | `SASLSSLSCRAM512` |

Plus `INTERNAL://kafka-it:29092` for inter-broker traffic, deliberately separate so a broken TLS
setting cannot stop the broker talking to itself (`docker-compose.kafka-it.yml:65–66`).

Two naming traps are baked into that file and worth reading before editing it:

- **Listener names carry no underscores.** The Confluent image turns an underscore in an env var
  into a dot, so a listener called `SASL_PLAIN` produced `listener.name.sasl.plain.*` and the
  broker refused to start, unable to find its own JAAS entry. The escapes are positional: `__` →
  underscore, `___` → hyphen, which is why SCRAM-SHA-256 is spelled `SCRAM___SHA___256`
  (L51–56, L114).
- **Real Kafka property names, not the image's `_FILENAME`/`_CREDENTIALS` convention.** That
  convention was passed through verbatim into `kafka.properties`, giving the broker
  `ssl.keystore.filename` (not a Kafka property) and no `ssl.keystore.location` at all. It then
  could not present a certificate, and every TLS listener answered `handshake_failure` while
  looking correctly configured (L72–76).

The test covers 10 parameterized connection cases plus 6 negative/edge cases
(`KafkaSecurityMatrixIT.java:199–212, 215–322`): missing truststore, mTLS with no client
certificate, wrong SASL password, a password full of quotes, an attempt to downgrade the protocol
via additional properties, and store-type declaration — 17 test cases in total, which matches the
count in `process/README.md:98`. It is named `*IT` so plain `mvn test` skips it, and every case
`assumeTrue`s itself away if `kafka-it` is not up (L85–87, L220 and the per-listener probes
at L240–323). The store password is read from `secrets/store-password` at L97.

### 4.3 The provisioning driver

`process/run-kafka-provisioning.sh` creates one Kafka connection profile of **every** security
configuration for the "Ajwa LLC" tenant and tests each against the local broker. It writes rows
that are meant to survive, so it is gated behind `-DprovisionKafka=true` and
`@EnabledIfSystemProperty` (`AjwaKafkaProvisioningDriver.java:63`) — a plain `mvn test` never
creates anything.

It runs in a container on **`process_default`** (not `kafka-it_default`), because it needs both the
application database at `postgres:5432` and the storage connection at `host.docker.internal:9000`
(`run-kafka-provisioning.sh:23–35`). Credentials come from the running `process_app` container the
same way `run-e2e.sh` gets them (L17–21), including `LOOKUP_ENCRYPTION_KEY` — anything it writes has
to be decryptable by the running app. Prerequisites: both `kafka_it` (L12–15) and `process_app`
must be up.

Its store files land in the platform bucket **for real** and are not rolled back, because a profile
pointing at a truststore that no longer exists would be worse than useless
(`AjwaKafkaProvisioningDriver.java:53–55`; the docker prerequisite is stated at L57). Everything it
writes is printed at the end so it can be undone by hand.

---

## 5. Ports

Every mapping below is a plain `hostPort:containerPort`, so each is reachable from the Mac at
`localhost:<port>` while the container runs. "Live" reflects `docker ps` on 2026-09-01.

| Host port | Service | Container | Compose file | Live |
|---|---|---|---|---|
| 80 | Angular 8 frontend (nginx) | `scheduler1-app` | `scheduler1/docker-compose.yml:11` | yes |
| 2181 | Zookeeper (dev) | `zookeeper` | `process/docker-compose.yml:47` | yes |
| 4400 | Angular 22 frontend (nginx) → 80 | `next-app` | `scheduler1/next/docker-compose.yml` | yes (since 2026-09-03) |
| 4566 | LocalStack — SES for outbound mail | `localstack-aws` | **none in this workspace** | yes (2026-09-08) |
| 5433 | PostgreSQL → 5432 | `postgres_db` | `process/docker-compose.yml:29` | yes |
| 5540 | RedisInsight | `redisinsight` | `process/docker-compose.yml:121` | yes |
| 5601 | OpenSearch Dashboards | `opensearch-dashboards` | `job-search/docker-compose.integrated.yml:99` | no |
| 6379 | Redis | `redis` | `process/docker-compose.yml:82` | yes (owned by `process`) |
| 8085 | Kafka UI → 8080 | `kafka_ui` | `process/docker-compose.yml:104` | yes |
| 8100 | Audio Extract Service (FastAPI) | `audio_extract_service` | `job-search/docker-compose.yml:19` | yes |
| 9000 / 9001 | MinIO API / console | `minio` | `job-search/docker-compose.integrated.yml:196–197` | yes |
| 9092 | Kafka INTERNAL | `kafka` | `process/docker-compose.yml:70` | yes |
| 9093 | Kafka EXTERNAL | `kafka` | `process/docker-compose.yml:71` | yes |
| 9098 | Spring Boot API | `process_app` | `process/docker-compose.yml:133` | yes |
| 9200 | OpenSearch | `opensearch` | `job-search/docker-compose.integrated.yml:77` | yes |
| 11434 | Ollama | `ollama` | `job-search/docker-compose.integrated.yml:28` | no |
| 19092–19098 | Kafka security matrix, 7 listeners | `kafka_it` | `process/kafka-it/docker-compose.kafka-it.yml:33–39` | yes |

Dev servers (not containers):

| Port | What | Source |
|---|---|---|
| 4200 | `ng serve` for `scheduler1/next` | `scheduler1/next/README.md:13`, `angular.json:65` |
| webpack default | `npm start` for `scheduler1` | `scheduler1/package.json:10` — no port given, **not verified** |
| 4400 | The console URL the backend assumes | `app.console.url` default in `AppUserServiceImpl.java:71`; `WEBSOCKET_ALLOWED_ORIGINS` default in `docker-compose.yml:200`. Since 2026-09-03 the `next-app` container **does** serve it (§2.4) — this row previously read "nothing in this workspace serves on 4400", which was true when written |

### Collisions to know about

`job-search`'s support stacks claim several ports and container names that `process` also uses.
These cannot run at the same time:

| Port / name | `process` | `job-search` |
|---|---|---|
| `8085` | Kafka UI (`docker-compose.yml:104`) | Cassandra Web (`docker-compose.integrated.yml:176`) |
| `6379` + container name `redis` | Redis (`docker-compose.yml:82`) | Redis (`docker-compose.integrated.yml:122`, and `docker-files/docker-compose.monitoring.yml:123`) |
| `2181` + container name `zookeeper` | Zookeeper (`docker-compose.yml:47`) | Zookeeper (`docker-files/docker-compose.kafka.yml:13`, `.full.yml:74`) |
| `9093` + container name `kafka` | Kafka EXTERNAL (`docker-compose.yml:71`) | Kafka (`docker-files/docker-compose.kafka.yml:29`, `.full.yml:89`) |

`job-search/docker-files/PORTS.md:39–49` documents the collisions *within* `job-search`, but not
these cross-project ones. Its "currently running" table (L12, L21–23) is also stale: it attributes
`redis` and `kafka` to `job-search` compose files when `docker inspect` shows both are currently
owned by the `process` project, and it lists Postgres on 5432 when `process/docker-compose.yml:29`
publishes 5433.

---

## 6. Known operational traps

These are recorded because each one has already cost somebody time. Most are documented in the
scripts themselves; the citations point at where.

### 6.1 A stale jar can ship, deploy cleanly, and pass its health check

The Dockerfile `COPY`s `target/process-1.0-0.jar` rather than building inside the image
(`Dockerfile:39–42`), so `docker-compose build` happily wraps a new image around an old jar.
`mvn test` does **not** write that jar — only `mvn package` does. `run_process_docker.sh:15–19`
records the consequence verbatim: a deploy reported success, restarted cleanly, passed its health
check, and was still running code from days ago; the only clue was a file timestamp nobody looks
at.

The guard (`run_process_docker.sh:20–30`) refuses to start if the jar is missing, and refuses again
if `find src/main -newer` finds anything. **`docker-compose up -d` and `./docker-compose.sh start`
both bypass that guard** — `docker-compose.sh:69–72` only builds when the jar is *absent*, not when
it is stale. Prefer `run_process_docker.sh`.

`process/README.md` documents the unguarded path (`README.md:60–69`) but now warns about the
failure mode directly above and below it (`README.md:61, 71`), suggesting a checksum comparison
between the jar in the image and `target/`. It does not mention `run_process_docker.sh`, which is
the only start path that actually enforces the check.

### 6.2 The build/package race between `mvn test` and `mvn package`

Same root cause, different symptom: `mvn test` produces classes but no jar, so a test-then-deploy
loop leaves the image at whatever `mvn package` last produced. Always `mvn package` before building
the image.

### 6.3 JDK version mismatch breaks every SASL test in a way that cannot happen in production

`kafka-clients` 2.5 authenticates through `Subject.getSubject`, removed with the SecurityManager in
JDK 24. A `mvn` running on JDK 24+ forks Surefire on the same JVM and every SASL case fails on
something the deployed JDK-17 image never encounters. Three separate defences exist and all three
matter:

- `pom.xml:284–317` pins the build to a toolchain JDK 17 and fails with a clear message if
  `~/.m2/toolchains.xml` has no 17 entry;
- `KafkaSecurityMatrixIT.java:88–93` skips itself with an explanatory message on JDK 24+;
- the two container scripts restate the toolchain against the image's `$JAVA_HOME`, because the
  repository's toolchain file names a macOS path that does not exist inside a container
  (`run-kafka-matrix.sh:38–42`, `run-kafka-provisioning.sh:38–42`).

### 6.4 The security matrix cannot run from the host

Covered in §4.2. The failure is thirteen metadata timeouts with no handshake or auth error, and the
four cases that never open a connection still pass — it looks like a regression and is not
(`run-kafka-matrix.sh:4–13`, `KafkaSecurityMatrixIT.java:60–71`, `kafka-it/start.sh:38–41`).

### 6.5 Underscores in Kafka listener names, and the image's credentials convention

Both covered in §4.2 and both recorded in `docker-compose.kafka-it.yml:51–56` and `:72–76`. Either
one produces a broker that looks correctly configured and is not.

### 6.6 Postgres is on 5433, not 5432

`docker-compose.yml:23–29` publishes 5433 precisely because the host may already run its own
Postgres on 5432 — and it does: `job-search/docker-compose.yml:82–88` points the F768920 pipeline
at a Homebrew `postgresql@18` on `host.docker.internal:5432`. The app itself never uses the host
mapping (it connects over the Docker network), so this only affects host tools. Two places still
say 5432: `docker-compose.sh:93` prints it in the "Services are running" banner, and
`job-search/docker-files/PORTS.md:23` lists it. `application-e2e.properties:12` has it right.

### 6.7 `docker-compose` (v1 syntax) and `docker compose` (v2) are both used

`run_process_docker.sh:33–34` and `docker-compose.sh` use hyphenated `docker-compose`;
`kafka-it/start.sh:14` and `stop.sh:8` use `docker compose`. Both exist on this machine
(v5.1.3 and v5.1.4 respectively), so nothing breaks here — but a machine with only one of them will
fail on half the scripts.

### 6.8 `process_app` only waits for Kafka to have *started*

`docker-compose.yml:201–207` waits on `service_healthy` for Postgres and Redis, but only
`service_started` for Kafka — and the `kafka` service defines no healthcheck at all. The app can
therefore come up before the broker is accepting connections.

### 6.9 A fresh clone will not start, and a fresh database has no admin

- `WORKER_CALLBACK_TOKEN` is passed through with **no** default (`docker-compose.yml:176`) and
  `NotifyResetApi.java:56–64` throws at startup when it is blank. Without `process/.env` (which is
  gitignored) the container will not boot. This is deliberate — the alternative was three
  unauthenticated write endpoints — but it is not written down anywhere a newcomer would look.
- `PLATFORM_ADMIN_BOOTSTRAP_PASSWORD` is set nowhere in this workspace, so
  `TenantSeedService.java:108–110` logs an error and seeds no platform admin. A first run against a
  genuinely empty database comes up with no account to sign in as.

### 6.10 `secrets/*creds` files are generated and never used

`generate-certs.sh:76–79` writes `keystore-creds`, `key-creds` and `truststore-creds`, with the
comment "The broker reads its passwords from files rather than the environment, so they stay out of
`docker inspect`". The compose file does the opposite — it passes `${STORE_PASSWORD}` as
`KAFKA_SSL_*_PASSWORD` env vars (`docker-compose.kafka-it.yml:83–87`) and says so explicitly at
L78–80. The three `*creds` files are dead, and the comment above them is wrong. Harmless (the
material is throwaway), but the two comments contradict each other.

### 6.11 The e2e profile's scheduler kill-switch does nothing

`application-e2e.properties:22` sets `process.scheduling.enabled=false` with the comment "The crons
would otherwise dispatch real jobs while the tests are asserting on rows." **That property is read
nowhere** — `grep -rn 'process.scheduling' src` finds only that one line, and
`ProcessConfig.java:20` carries an unconditional `@EnableScheduling`. The pool size is capped at 1
on the line above (L21), which slows the crons but does not stop them. The suite runs against the
real dev database.

### 6.12 Documentation that points at things that do not exist

- `application-e2e.properties:5` says "see `StackE2ETest` for the command"; **no class of that name
  exists** — `grep -rn StackE2ETest` across the repository matches only that comment. The command
  is in `run-e2e.sh`.
- `process/README.md:47–54` gives `mvn clean package -DskipTests` then `java -jar target/*.jar` as
  the local option, with no mention of `process/.env` or the `WORKER_CALLBACK_TOKEN` startup
  requirement (§6.9). A newcomer following it gets an `IllegalStateException` at boot with no
  pointer to the file that fixes it.
- `job-search/docker-files/PORTS.md` is stale about which project owns which container (§5).
- Two earlier entries in this list — a dead `DOCKER_SETUP.md` link in `process/README.md` and a
  wrong URL in `scheduler1/DEPLOYMENT.md` — were **fixed by a concurrent rewrite of both files
  during this session** and no longer apply. `process/README.md:122–124` now flags five further
  unverified markdown files; they exist — `process/ext-detail/md/` holds
  `DATABASE_CONNECTION_GUIDE.md`, `REFACTORING_SUMMARY.md`, `SQL_UPDATE_GUIDE.md` and
  `QUICK_REFERENCE.md`, and `process/docs/design/` holds `kafka-dynamic-configuration.md`. None
  were read for this document; treat them as unknown.

### 6.13 A query engine now lives in the backend, and `docker ps` does not show it

Added 2026-09-08 with §2.6, and recorded here because everything else this document teaches you to
look at is something you can point at: a container, a published port, a compose file, a script.
DuckDB is none of those. It has no container, no port and no compose entry, so taking stock of this
stack the usual way does not see it at all — while the ceiling on what `process_app` may allocate
went up the day it landed. Three consequences follow that are easy to meet the hard way:

- **The six `analytics.*` limits cannot be changed from `docker-compose.yml` as it stands.** The
  `ANALYTICS_*` variables exist only as `${VAR:default}` references inside the three properties
  files; nothing in `docker-compose.yml` or `.env.example` passes them through (§3.2). Setting one
  in `process/.env` does nothing on its own — Compose only forwards a variable the service's
  `environment:` block names.
- **`process_app` still has no memory limit**, so the 4 × 512 MB analytics ceiling sits on top of an
  unbounded JVM in an unbounded container (§2.6). Nothing degrades gracefully; the OOM killer takes
  the dispatcher along with the query.
- **The jar grew by ~70 MB.** Every image build and every `COPY` of `target/process-1.0-0.jar` now
  carries four platform builds of the native engine (§2.6), which is worth knowing before blaming a
  slow build on something else.

---

## 7. `job-search` — brief inventory (OUT OF SCOPE for the current phase)

> **These are explicitly out of scope for the current phase.** Recorded here only because they run
> on the same machine, share the `process_default` network, share a secret with the backend, and
> own the MinIO/OpenSearch containers `process` depends on.

Python 3.12 workers, one image (`job-search/Dockerfile:5`, `image: job-search-app`) run with three
different commands (`job-search/docker-compose.yml`). The image installs ffmpeg, tesseract-ocr,
libsndfile1 and build-essential (L16–22).

| Service | Container | Command | Topic consumed | Group |
|---|---|---|---|---|
| `audio-extract-service` | `audio_extract_service` | `uvicorn etl.service.audio_extract_service:app --port 8100 --workers 1` (L33) | — (HTTP, not Kafka) | — |
| `tpd-scrapping-listener` | `tpd_scrapping_listener` | `python -m etl.tpd.tpd_scrapping_listener` (L92) | `scrapping-topic` (L68) | `scrapping-group` (L69) |
| `tpd-test-listener` | `tpd_test_listener` | `python -m etl.tpd.tpd_test_listener` (L125) | `test-topic` (L112) | `test-group` (L113) |

The test listener's pipeline is simulated work — a counted loop with a short sleep and one
audit-log callback per iteration — running 3 processes × 10 threads, so one container is 30 parallel
workers (L94–97).

**What the scrapping listener can actually run** is a registry, not a switch. `PIPELINE_TASKS`
(`job-search/etl/tpd/tpd_scrapping_listener.py:59–81`) maps a pipeline id to a
`(module, function)` pair, imported with `importlib` at dispatch time (L182–187) so that one
container does not pay for every pipeline's dependencies — the comment above the dict names the
two that made this necessary, `F768927` (torch + whisper) and `F768920` (the Firebase SDK). An id
with no entry raises `Unknown pipeline <id>` (L183–184). A second map,
`pipeline_xml_parser` in `job-search/etl/util/xml_parser.py:239–261`, turns the task's XML payload
into that function's arguments; the two maps must carry the same keys, and a pipeline missing from
either one is dead.

**20 pipelines are registered**, in two groups: four one-off workers (`F768926` hurricanes,
`F768927` MP3 noise/transcription, `F768920` Firebase export, `F76800` email batch) and the
16-strong object-storage CSV family, `F768930`–`F768945`. Every member of that family takes a flat
list of XML tags, declared rather than hand-written through one `_flat_parser` factory
(`xml_parser.py:149–173`), and every one accepts an optional `<bucket>` where absent means the
platform bucket. Two comments in that file still say "fifteen" and "F768930 - F768944"
(`xml_parser.py:128, 131, 176`) — they were not updated when the sixteenth was added, so trust the
dict, not the prose above it.

The newest is **`F768945` — `csv_partition`** (`job-search/etl/tasks/csv_partition_f768945.py`,
registered at `tpd_scrapping_listener.py:80` and `xml_parser.py:213–215`, added 2026-09-08). It
splits one CSV into a separate object per distinct value of a column — where `F768938` splits by
row count, this splits by the data — taking `input_object`, `partition_column`, `output_folder`
and optional `prefix` / `max_partitions` / `bucket`. Two of its behaviours matter operationally:
a partition value ends up in an object **key**, so every value is sanitised to `[A-Za-z0-9._-]`
with leading dots stripped (`safe_name`, L34–50) — a value of `../etc` cannot write outside the
output folder — and the mapping from value to file name is written to the audit log; and a column
with more distinct values than `max_partitions` (default 200) fails **before** anything is
written (L113–120), because the failure it exists to prevent is partitioning on an id column and
finding out once the bucket holds a file per row. Values that sanitise to the same name share a
file, which is logged rather than hidden (L122–127), and rows with no value go to `_blank.csv`
rather than being dropped (L135–140). Verified end to end on 2026-09-08: `job_queue` row 5397
(job 2417) reads `Completed`.

Both listeners join the external `process_default` network (L53–55, L105–107, L127–129) to reach
`kafka:9092`, and reach the backend at `http://host.docker.internal:9098/api/v1`. Both send
`WORKER_CALLBACK_TOKEN` as `X-Worker-Token`; a mismatch means job status silently stops updating
(L24–26).

`--workers 1` on the audio service is required, not tuning: more workers would each load a separate
Whisper model instead of sharing the one lazy-loaded singleton
(`job-search/run_audio_extract_service.sh:33–34`).

The `job-search/docker-files/` and `docker-compose.integrated.yml` stacks are a grab bag of support
services (MongoDB, Kafka, Schema Registry, Prometheus, Grafana, OpenSearch, Cassandra, MinIO,
Ollama, Open WebUI, Flower). Only `docker-compose.integrated.yml`'s `minio` and `opensearch` are
load-bearing for `process`, via `MINIO_ENDPOINT` / `OPENSEARCH_URL`.

---

## 8. Risks

Ordered by how much damage each can do.

1. **`process/.env.bak.1787579140` is committed to git and holds live credentials.**
   `git cat-file -e HEAD:.env.bak.1787579140` succeeds, and `git ls-files` lists it. It carries all
   ten keys from `.env.example`, including `SPRING_DATASOURCE_PASSWORD`, `MAIL_PASSWORD` and
   `WORKER_CALLBACK_TOKEN`. `process/.gitignore:35` ignores `.env` and `.env.local` but has no
   pattern covering `.env.bak.*`, so the backup slipped straight through — precisely the mistake
   the comment at `.gitignore:37–38` says was already made once with `.env` itself. (By contrast
   `job-search/.gitignore:26–27` uses `.env` **and** `.env.*`, which does cover its backup.)
   Values not reproduced here. Needs `git rm --cached`, a `.gitignore` pattern, and rotation of
   every value in it.

2. **`job-search/env` (no dot) is committed and holds the Mongo credentials.** Confirmed with
   `git cat-file -e HEAD:env`. `job-search/.gitignore:29–33` documents this and stops the next one
   being added, but explicitly notes it does not untrack the file already indexed — that still
   needs `git rm --cached` and rotation.

3. **`process/docker-compose.yml` carries literal fallback values for three secrets.**
   `LOOKUP_ENCRYPTION_KEY` (L162), `JWT_SECRET_KEY` (L166) and `MAIL_PASSWORD`/`MAIL_USERNAME`
   (L156–157) all have real values as `${VAR:-<literal>}` defaults in a tracked file. The comments
   above them acknowledge this and tell you to override with a real env var, and
   `ApplicationPropertiesDeclarationTest.everyCredentialIsDeclaredWithAnEmptyDefault` enforces the
   no-literal rule — but only across `application-*.properties`, which is not where these live. A
   stack started without `.env` therefore runs on a signing key and an encryption key that are
   public. Values not reproduced here.

   Two notes as of 2026-09-08. The `MAIL_*` pair is now the **deprecated** SMTP path (§2.5) and is
   read only at `MAIL_TRANSPORT=smtp`, so on a default stack it is an unused committed credential
   rather than a live one — still worth removing, no longer worth rotating first. And
   `AWS_SES_ACCESS_KEY`/`AWS_SES_SECRET_KEY` also carry literal defaults (L152–153), but those are
   LocalStack's universal `test`/`test` placeholders and authenticate against nothing real; they
   belong in this entry only so that a later reader does not mistake them for the same class of
   problem.

4. **No platform admin is seeded on a fresh database.** §6.9. Nothing in the workspace sets
   `PLATFORM_ADMIN_BOOTSTRAP_PASSWORD`, and `TenantSeedService.java:108–110` only logs.

5. **The e2e suite's scheduler kill-switch is dead code.** §6.11. Crons run during e2e runs against
   the shared dev database.

6. **The stale-jar failure mode is one command away.** §6.1. The guard exists in exactly one of
   three start paths, and `process/README.md:60–69` documents one of the unguarded ones — with a
   warning attached (L71), but without naming `run_process_docker.sh`, the script that enforces it.

7. **Cross-project port and container-name collisions are undocumented.** §5. `PORTS.md` covers
   collisions inside `job-search` and is itself stale about which project owns `redis` and `kafka`.

8. ~~**Nothing serves on port 4400**~~ — **closed 2026-09-08.** 4400 is the default for
   `app.console.url` (`AppUserServiceImpl.java:71`, `TenantRequestServiceImpl.java:68` — used to
   build the links in outgoing email) and appears in the `WEBSOCKET_ALLOWED_ORIGINS` default
   (`docker-compose.yml:200`), and when this was written nothing answered there, so every emailed
   link pointed at a dead port. The `scheduler1/next` container added on 2026-09-03 (§2.4) serves
   exactly that port, and `docker ps` on 2026-09-08 shows `next-app` published on `4400→80`. The
   original open question — whether somebody started the console on 4400 by hand — is moot: a
   compose service does it. What remains true is the narrower point in §2.4: the container exists,
   but no deployment decision has been made, so nothing guarantees it is running when mail is sent.

9. **`WEBSOCKET_ALLOWED_ORIGINS` hardcodes a LAN IP.** The default at `docker-compose.yml:200`
   includes `http://10.0.0.248` and `http://10.0.0.248:8084`; the comment above it says to update
   this when the host's LAN IP changes. It will go stale silently — the symptom is a WebSocket that
   refuses to connect from a phone on the same network. The `:8084` entry is described as "webpack
   dev server", but `scheduler1/package.json:10` sets no port and `webpack.config.js:78–83` does
   not either, while `8084` **is** the Redis Commander port in
   `job-search/docker-compose.integrated.yml:141`. Which of those the origin was meant for is
   **not verified**.

10. **The `dev` profile does not declare `websocket.allowed-origins` at all.** Only prod and stage
    do (`application-prod.properties:21`, `application-stage.properties:21`). Compose papers over
    it for the container, so a developer running `mvn spring-boot:run` on the host falls back to
    the `@Value` default in `WebSocketConfig.java:25` — `http://localhost,http://localhost:8080` —
    which does not include 4200 or 4400.

11. **`kafka_data` volume is declared but never mounted.** `docker-compose.yml:9` declares it; the
    `kafka` service (L50–71) has no `volumes:` block. The broker's log directory lives in the
    container's writable layer, so topic data does not survive `docker-compose down`. Whether that
    matters depends on whether anything but transient job messages lives there — **not verified**.

12. **`docker-compose.sh:93–96` prints database credentials to the terminal** as part of its
    "Services are running" banner, and the host/port it prints (5432) is wrong (§6.6).

13. **The Liquibase master changelog uses `exclude:` entries**
    (`src/main/resources/db/changelog/db.changelog-master.yaml:15–22`, four of them, for V4.0–V7.0).
    `include` and `includeAll` are the documented directives; whether `exclude` is honoured,
    ignored, or merely tolerated by this Liquibase version is **not verified** — the running app
    starts cleanly with `spring.liquibase.enabled=true` and `contexts=init`
    (`application-dev.properties:101–103`), and `process/README.md:79` states migration is
    automatic and needs no manual bootstrap SQL, so it is at least not fatal. Belongs to the data
    discovery; flagged here because it affects first-boot behaviour.

14. **`patch.js` and `patch_dist.js` run with `|| true`** in the frontend build
    (`scheduler1/Dockerfile:24, 31`). If either stops working, the build still succeeds and the
    regex bug they exist to fix returns at runtime.

The two below were added on **2026-09-08** with Analytics Studio (§2.6). They are appended rather
than ranked into the order above, so that the existing numbers keep pointing at what they always
did — but on the list's own measure, entry 15 belongs near the top: it is the only item here that
can take the ETL dispatcher down.

15. **An analytics query and the ETL dispatcher share one unbounded process.** DuckDB is embedded in
    `process_app`, its ceiling is `max-concurrent × memory-limit` (4 × 512 MB by default), and the
    container itself has neither a `mem_limit` nor a `-Xmx` (`docker-compose.yml:126–216`). The six
    limits in §3.2 are therefore the *only* thing standing between a large scan and the OOM killer
    taking the crons down with it, and `/actuator/health` will say `UP` right up until it does. The
    limits are at least enforced as *present* in every profile by
    `ApplicationPropertiesDeclarationTest` (§3.2); whether 512 MB is the right number for this host
    is **not verified** — nothing has been measured against a dataset large enough to reach it.
    Note also that the ceiling is per JVM, not per tenant: one workspace can hold all four slots
    (`discovery/backend.md` §9, entry 15).

16. **The Azure branch of the analytics reader has never been run.** S3 and MinIO share the S3
    protocol and were verified live against MinIO (§2.6). Azure Blob is a separate branch that
    executes `INSTALL azure` / `LOAD azure` and builds a different secret from
    `azureConnectionStringEnc` (`process/src/main/java/process/analytics/DuckDbSessionFactory.java:130–134,
    171–179`); no test reaches it and it has never been exercised against a real container. Do not
    describe Azure as working. What happens on a host that cannot reach DuckDB's extension
    repository at that point is **not verified** — see the closing section.

---

## What could not be determined

- **The webpack dev server's actual port** for `scheduler1`. `package.json:10` passes no `--port`
  and `webpack.config.js:78–83` sets none; the `8084` in the WebSocket origin allowlist matches
  Redis Commander's published port rather than anything in the webpack config. Looked at
  `package.json`, `webpack.config.js`, and grepped the whole workspace for `8084`.
- ~~**Whether anything serves port 4400.**~~ **Determined 2026-09-08:** the `next-app` container
  does (§2.4, §5, and risk 8 above). When this line was written, grep found 4400 only in
  `app.console.url` and `WEBSOCKET_ALLOWED_ORIGINS`; `scheduler1/next/docker-compose.yml` has
  since claimed it.
- **Whether `KAFKA_*` topic names are ever set on the `process` side.** The workers' topics are
  fixed in `job-search/docker-compose.yml` (`scrapping-topic`, `test-topic`), but on the backend the
  topic appears to come from per-task database rows rather than configuration — `KafkaTopicProvisioner`
  and `KafkaConnectionResolver` were skimmed, not read in full. That is the ETL discovery's
  territory.
- **Whether `process/.env` and `process/.env.bak.1787579140` currently hold the same values.**
  `diff -q` reports them different; the contents were not inspected beyond key names.
- **Where DuckDB's extensions come from at run time, and what happens when they cannot be
  fetched.** `DuckDbSessionFactory.open()` runs `INSTALL httpfs` / `LOAD httpfs` (or the `azure`
  pair) on **every** session, i.e. on every analytics request
  (`process/src/main/java/process/analytics/DuckDbSessionFactory.java:123–134`). The S3 path
  demonstrably works on this machine — §2.6's live reads went through it — but nothing was checked
  about whether the extension is bundled in the jar, cached under the home directory, or downloaded,
  and therefore nothing is known about the behaviour of an air-gapped or egress-filtered host. It is
  the one run-time dependency of this module that is neither a container nor a property. Looked at:
  `DuckDbSessionFactory.java`, `pom.xml`, the jar's entry list.
- **Whether 512 MB and four concurrent queries are the right numbers.** Nothing has been run against
  a dataset large enough to reach either ceiling. Risk 15.
- **Prod and stage deployment.** `application-prod.properties` and `application-stage.properties`
  exist and differ from dev in three meaningful ways (`ddl-auto=validate` at prod L92 / stage L89,
  replication factor `-1` at prod L66, `websocket.allowed-origins` declared at L21 in both), but
  there is no compose file, Dockerfile arg, CI pipeline or deployment script for either profile
  anywhere in the workspace. How they are deployed is **not verified**.
