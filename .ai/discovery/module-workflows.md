# Discovery — Module Workflows

**How each module actually runs**, end to end: what starts it, which code it passes through, where
its state ends up, and how it fails.

This is the companion to the two documents either side of it, and it is worth being clear about the
difference, because all three describe the same system:

| Document | Answers |
|---|---|
| [application-inventory.md](application-inventory.md) | **What is there** — the runtimes, the deployables, the dependencies |
| [features.md](features.md) | **What it does, and whether it crossed** — routes, endpoints, entities, migration status |
| **this document** | **How it works at runtime** — the path a request or a run takes, and where it can stop |

If you need to know which endpoint a screen calls, read `features.md`. If you need to know what
*happens* after it calls it, read this.

Paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`. Every claim about behaviour cites a
file; anything specific cites a line. Where something is genuinely unknown it says so.

---

## 1. The shape of the platform

Three runtimes and the infrastructure between them. Nothing else talks to the database.

```
  Browser
     │  HTTPS :4400  (nginx, static Angular bundle)
     │  REST  :9098/api/v1        ─┐
     │  STOMP :9098/ws (SockJS)   ─┤
     ▼                             │
  scheduler1/next      ANGULAR 22, Tailwind 4, signals, zoneless
                                   │
                                   ▼
  process              SPRING BOOT 2.3 · Java 17 runtime · SOURCE LEVEL JAVA 8
     │                 The only writer to PostgreSQL. Owns auth, tenancy,
     │                 scheduling, analytics, RAG, storage brokering, email.
     │
     ├── PostgreSQL :5433   metadata: users, tenants, jobs, runs, datasets, agents
     ├── Kafka              job dispatch; the topic comes from the task type
     ├── MinIO / S3 :9000   objects: inputs, outputs, exports, avatars
     ├── OpenSearch :9200   audit log lines, and the RAG vector index
     ├── Redis              caches and session state
     ├── Ollama             embeddings (nomic-embed-text, 768-dim) and chat
     └── LibreOffice        in-container, drives document conversion
                                   │
                                   ▼ Kafka
  job-search           PYTHON WORKERS. One consumer process per topic; the
                       pipeline id inside the payload picks the work.
                       Does the actual ETL. Reports back over REST.
```

**Two directions of travel, and they are not symmetric.** A browser request goes
`Angular → process → infrastructure` and returns. A job run goes
`process → Kafka → Python → back to process over REST`. The Python side never touches PostgreSQL;
it asks `process` to write for it. That is why [§4](#4-the-job-run-lifecycle) is the longest
section here — it is the only path that crosses a process boundary and comes back.

**Source level is Java 8** even though the runtime is 17. No `var`, no `List.of`, no text blocks,
`javax.*` not `jakarta.*`. This catches people out constantly.

---

## 2. Every request: authentication and tenancy

Before any module does anything, two things have already happened to the request.

**1. The JWT is unpacked.** `security/JwtAuthenticationFilter.java:36` looks for
`Authorization: Bearer <token>`, and on success calls `TenantContext.set(...)` at line 44 with the
tenant id, role, user id and username.

**2. The tenant is pinned to the thread.** `security/TenantContext.java` is four `ThreadLocal`s.
Every service below reads the tenant from there rather than from the request body — which is the
point, since a tenant id in a body is caller-supplied and a tenant id on the thread is not.

`TenantContext.clear()` runs in a `finally` at line 57. On a pooled thread, skipping that would
leak one caller's tenant into the next request on the same thread.

**`isPlatformAdmin()` is the escape hatch.** A platform admin bypasses the tenant filter. Ownership
checks in the services read as *"platform admin, or the row's tenant equals mine"* — for example
`MessageQServiceImpl.isJobOwnedByCaller`.

> **Where this bites.** Anything running off the request thread — a Kafka send callback, an
> `@Async` method, a scheduled cron — has **no TenantContext**. Code moved into one of those
> silently loses its tenant. The dispatcher works around this by reading the tenant off the job row
> instead (`ProducerBulkEngine.pushMessageToQueue` passes `sourceJob.getTenantId()` to the Kafka
> resolver).

---

## 3. Every response: the envelope

`ResponseDto` wraps everything, and **a business failure is HTTP 200 with `status: "ERROR"`**, not a
4xx. So:

```json
{ "status": "SUCCESS" | "ERROR", "message": "...", "data": { ... } }
```

The frontend checks `response.status === API_SUCCESS`, never the HTTP code
(`core/api/api.config.ts`). A 4xx or 5xx means something unhandled — the request never reached the
service, or the service threw. Reading the HTTP code alone will tell you a failed operation
succeeded.

---

## 4. The job run lifecycle

The core of the platform, and the only flow that leaves the JVM and comes back. Nine steps.

```
 [1] scheduler row becomes due
      │  ProcessCron.addJobInQueue        every 60s, ShedLock "addJobInQueue"
      ▼
 [2] job_queue row created, status Queue
      │
      │  ProcessCron.startJobInCurrentTimeSlot   every 60s, separate lock
      ▼
 [3] pick up eligible Queue rows  ──► [3a] configuration wrong? → Failed, no retry
      │
      ▼
 [4] resolve the tenant's Kafka connection, send to the task type's topic
      │                                 └─► [4a] send fails → RETRYABLE
      ▼
 [5] job_queue status Start, job_send = true
      │  ~~~~~~~~~~~~~~ process boundary ~~~~~~~~~~~~~~
      ▼
 [6] Python consumer receives it, reports Running
      │
      ▼
 [7] the pipeline function runs the actual ETL
      │                                 └─► [7a] task throws → RETRYABLE
      ▼
 [8] logs flushed, then Completed reported
      ▼
 [9] status written, socket published, email sent if subscribed
```

### 4.1 Becoming due — `engine/cron/ProcessCron.java`

Three scheduled methods, each under its own ShedLock so two instances cannot both run it:

| method | every | does |
|---|---|---|
| `addJobInQueue` | 60s | finds due schedulers, creates `job_queue` rows |
| `startJobInCurrentTimeSlot` | 60s | dispatches queued rows to Kafka |
| `reconcileStalledRuns` | 15 min | closes runs stuck in flight for 6 hours |

The whole class is behind `@ConditionalOnProperty("process.scheduling.enabled")`, defaulting to
**on**. That guard exists because the E2E profile set the property and *nothing read it*, so every
end-to-end run on a developer machine dispatched real jobs out of the shared database — twelve of
one tenant's jobs were marked Failed by a single test run.

### 4.2 The busy check, and why a job skips itself

`ProducerBulkEngine.addJobInQueue` (line 178) asks
`getCountForInQueueJobByJobId(jobId) > 0` — counting rows in **Queue, Start or Running** — and if
anything is in flight it writes a `Skip` row instead of a second run.

**This is deliberate and load-bearing.** Two runs of one job at once means two workers writing the
same output folder. Every design decision downstream respects it, including retry.

### 4.3 Dispatch — `ProducerBulkEngine.startJobInCurrentTimeSlot`

Reads Queue rows that have `job_send = false` **and are past their `next_attempt_at`**, ordered by
id, capped by `QUEUE_FETCH_LIMIT`. The loop stops at a 7-minute budget (`DISPATCH_BUDGET_MS`)
because the ShedLock lasts ten and a batch that outruns the lock can be dispatched twice by
another instance.

**Two things pick where a job goes, and they are easy to conflate.** The *topic* comes from the task
type's `queue_topic_partition`, so a task type can have its own topic. The *work* is chosen by the
`pipelineId` **inside the payload**, not by the topic — which is why the deployed task types nearly
all share one topic (`scrapping-topic`, which the live listener reads with group `scrapping-group`,
a single consumer process) and still run twenty-one different pipelines. Changing a task's pipeline
changes what runs; changing its task type changes which broker and topic carry it.

The *broker* comes from
`config/KafkaConnectionResolver.java:49`, which resolves per tenant — a route row for
`(tenantId, sourceTaskTypeId)` first, then the task type's own default. That is how one platform
dispatches to different tenants' Kafka clusters.

### 4.4 The payload

`getSourceJobDetail` builds a `JobPayloadDTO`: `jobQueueId`, `jobId`, `homePageId`, **`pipelineId`**,
`taskPayload` (the task's XML) and `priority`. The `pipelineId` is what routes it on the Python side.

### 4.5 The Python side — `job-search/etl/tpd/tpd_scrapping_listener.py`

1. Reports `RUNNING` back over REST (line 175).
2. `extract_task_payload` parses the task XML with the parser registered for that pipeline in
   `pipeline_xml_parser`. A parser that cannot read the XML returns `None` and the caller raises a
   message naming the task, rather than letting `'NoneType' object does not support item assignment`
   reach the operator.
3. `PIPELINE_TASKS` (line 59) maps the pipeline id to `(module, function)` — **21 pipelines today**.
   The import is *inside* the dispatch, not at module scope, and that is load-bearing: `F768927`
   pulls in torch and whisper, `F768920` the Firebase SDK. Importing all of them to run one would
   make every worker pay for every pipeline's dependencies.
4. The task function runs.
5. **Logs are flushed before the terminal status** — on success *and* on failure. A reader opening
   a completed run's logs must not find the last lines still in a buffer, and on failure the
   buffered lines are usually what explains it.

### 4.6 Reporting back — and the trap

The worker reports status to **`NotifyServiceImpl.changeState`**, reached via
`api/NotifyResetApi.java` at `/changeState/jobId/{}/jobQueueId/{}/jobStatus/{}`.

> **Four places mark a run Failed, and three look nearly identical.** This is the single most
> confusing thing in the codebase and it has cost real time:
>
> | site | who calls it |
> |---|---|
> | `NotifyServiceImpl.changeState` | **the live Python worker** |
> | `MessageQServiceImpl.changeJobStatus` (`QUEUE_DETAIL`) | authenticated API route, not the worker |
> | `MessageQServiceImpl.failJobLogs` | the console's "Mark as failed" button |
> | `ProducerBulkEngine.changeStatusForLastJob` | dispatch-side failures |
>
> Confirm which one you are in by triggering a real run and reading `docker logs process_app`.
> Do not infer it from the file name.

`changeState` also enforces a transition table (`isValidStatusTransition`): `Queue → Start`,
`Start → Start|Running`, `Running → Running|Failed|Completed`, and terminal states only to
themselves. An out-of-order report is refused rather than applied.

### 4.7 Retry — added 2026-09-15

A failed run is offered another attempt before anything announces a failure.

`BulkAction.scheduleRetry(jobQueueId, jobId, reason)` decides, and **its return value is the
contract**: `true` means the run is going round again and nothing has failed as far as the rest of
the platform is concerned. Callers that ignore it send one failure email per attempt.

- **Policy per job**: `source_job.max_attempts` (default **1** = no retry, i.e. the behaviour every
  job had before this existed) and `retry_backoff_seconds` (default 60). CHECK constraints bound
  them to 1–10 and 1–3600; `SourceJobServiceImpl.retryPolicyError` rejects out-of-range values with
  a sentence rather than letting the constraint produce an internal error.
- **Backoff doubles** per attempt, capped at one hour.
- **The queue row is re-used**, not replaced — so the retry keeps occupying the single in-flight
  slot its job is allowed (§4.2). Per-attempt history goes to the audit log.
- **`job_send` is reset to false and `end_time` cleared**, or the retry is written down and never
  dispatched.
- **`next_attempt_at` is compared against a timestamp passed from Java**, never SQL `now()`: the
  database is UTC while the application pins `America/Chicago` in `ModelApplication.main`. Compared
  against the wrong clock a backoff is either instantly elapsed or five hours long.

**What retries and what does not:**

| failure | retried |
|---|---|
| worker reports the task failed | **yes** — the case this exists for |
| producer threw while building or connecting | **yes** |
| job deleted/inactive, no task, no task type, bad topic, task type off | no — configuration |
| stalled six hours (`Interrupt`) | no — the worker may have done the work |
| a person clicking "Mark as failed" | no — that was a decision |

**Consequence worth knowing:** a job whose backoff outlasts its own interval will skip its next
slot. That is the intended ordering — finish the slot you are on before starting the next.

Migration: `V38.0-job-retry`. Verified live on job 2410 (a job built to fail): three attempts at
5s then 10s backoff, then Failed — **one email, not three**.

### 4.8 Where run state lives

| what | where |
|---|---|
| the run | `job_queue` — status, attempt, next_attempt_at, start/end, message |
| the job's current status | `source_job.job_running_status` — a denormalised copy the console reads |
| the narrative | **OpenSearch index `job-audit-logs`**, falling back to the `job_audit_logs` table only if the index write fails (`TransactionServiceImpl.saveJobAuditLogs:57`) |

> That fallback surprises people: a run's audit lines are usually **not** in PostgreSQL. If the
> table looks empty, query OpenSearch before concluding nothing was written.

---

## 5. Cross-cutting machinery

### 5.1 Real-time — `socket/`

STOMP over SockJS at `/ws`, broker prefixes `/queue`, `/user`, `/topic`
(`config/WebSocketConfig.java:43`).

- **`JobEventPublisher`** → `/topic/jobs.{tenantId}` — job status transitions, tenant-scoped by
  topic name.
- **`NotificationService`** → `convertAndSendToUser(..., "/queue/reply", ...)` — per-user.
- `StompAuthChannelInterceptor` authenticates the socket; `WebSocketPresenceService` tracks who is
  connected.

**All nine status transitions publish from one place** — `BulkAction.changeJobStatus`. They used to
publish at the call sites, where eight of nine were silent and a job sat at its old status until
someone pressed Refresh on a screen that claims to be live. Publishing is `publishStatusAfterCommit`,
because a status announced before the write is durable is a lie if the transaction rolls back.

### 5.2 Notifications — `NotificationCenterServiceImpl`

Durable, per-user, separate from the socket. Types:
`JOB_COMPLETED, JOB_FAILED, JOB_SKIPPED, TASK_ASSIGNED, BATCH_DONE, KAFKA_TEST_FAILED, USER_ADDED,
FILE_SHARE_SENT, FILE_SHARE_FAILED, FILE_SHARED_WITH_YOU`.

Every one is a *thing that happened*. **There is no alert for nothing happening** — a job that
quietly stops produces no notification, which is the failure mode that actually hurts. `JobStatus`
already has a `Missed` state, so half the vocabulary exists.

### 5.3 Email — `emailer/`

`MailTransport` has two implementations, `SesMailSender` and `SmtpMailSender`, chosen by
configuration. Templates are Velocity (`VelocityManager`, `TemplateType`).

`deliversToRealInboxes()` distinguishes a real send from an emulated one — SES returns
`!emulated`, and an overridden endpoint means LocalStack.

> **Current state:** `AWS_SES_ENDPOINT` points at LocalStack, so mail is captured, not delivered.
> Real delivery needs a real endpoint, credentials and a verified `MAIL_FROM`.

### 5.4 Storage — one interface, five adapters

`S3`, `MinIO`, `AzureBlob`, `FTP`, plus `BucketRewritingStorageService` which wraps another adapter
and rewrites bucket names. `StorageConnectionServiceImpl` holds the credentials;
`StorageBrowserServiceImpl` is what the Objects screen talks to.

Every module that touches a file goes through this, so adding a provider is one adapter rather than
a change per feature.

---

## 6. The modules

### 6.1 `dashboard`

Five aggregate endpoints on `DashboardRestApi` over `job_queue`/`source_job`. Read-only.

`ModelApplication.main` pins `America/Chicago`, so the database stores Chicago wall-clock while
Postgres `now()` is UTC. **A naive "minutes since last run" reads five hours high.** Any time
arithmetic here has to pick a clock and stay on it.

### 6.2 `source-jobs` and `source-tasks`

A **task** is *what to run*: a pipeline id, a task type (which decides the Kafka topic), and a
payload of XML built by a Task Form. A **job** is *when to run it*: a task plus a scheduler plus an
execution mode plus, now, a retry policy.

- `execution = Manual` — the dispatcher skips it; only "Run now" starts it.
- `execution = Auto` — the scheduler row drives it.
- Switching to Manual **holds the timetable** (`expired` stays false), so switching back resumes
  exactly as before.
- `V37.0` enforces **one scheduler row per job** in the database. The code had always assumed it —
  `findSchedulerByJobId` returns a single row — so a second row turned every by-id read of that job
  into a 500.

**Task Forms** (`TaskFormServiceImpl`) are how a pipeline gets a typed form instead of hand-written
XML: `TaskForm` + `TaskFormField`, keyed by pipeline id, rendered by the task editor and serialised
into `taskPayload`.

### 6.3 `job-runs-and-queue`

Reads `job_queue` and the audit log. `failJobLogs` and `interruptJobLogs` are the manual overrides,
both restricted to runs still in flight (`IN_FLIGHT_STATUSES` = Queue, Start, Running) — re-failing
a Completed run would rewrite history.

### 6.4 `analytics-studio` — the deepest module

```
storage connection → bucket → path → dataset registration → schema detection
   → preview → profile → quality → dimensions/measures → analysis → chart
   → save → dashboard → export
```

- **`DatasetResolver.resolve(connectionAlias, path)`** turns an alias plus a path into a
  `DatasetRef`, reading credentials from `StorageConnectionRepository`.
- **`DuckDbAnalyticsEngine`** runs the query. `DuckDbSessionFactory` hardens each session:
  `INSTALL/LOAD httpfs` only, `SET disabled_filesystems='LocalFileSystem'`, then
  **`SET lock_configuration=true`** so nothing downstream can undo it. Memory limit and thread
  count come from `AnalyticsLimits`.
- **`StatementGate`** and `AnalyticsBodyLimitFilter` bound what can be asked.
- **`RunningQueries`** plus a JVM-wide permit governor (`analytics.query.max-concurrent`, default
  **4**) bound how much runs at once — it is JVM-wide, not per tenant, so a heavy tenant can
  starve others.

**DuckDB 1.1.3 specifics that bite:** no `width_bucket`, no two-argument `histogram`. `mode()` and
`approx_count_distinct` work. Binning is arithmetic: `least(floor((col-min)/width), bins-1)`.

Storage reads retry twice with a 250ms backoff (`storageRetryAttempts`) — the pattern job retry was
later modelled on.

### 6.5 `file-chat` / RAG

```
file in a bucket → extract text → chunk → embed (Ollama) → index (OpenSearch)
   → question → embed question → k-NN retrieve → agent prompt → answer
```

- `FileChatExtractionServiceImpl` extracts; `memoizedExtraction(bucket, key, etag, agentConfig)`
  caches on the object's **etag**, so re-opening an unchanged file does not re-extract. Vision-capable
  types route to the agent-aware overload via `VISION_CAPABLE_EXTENSIONS`.
- `EmbeddingServiceImpl` — `nomic-embed-text`, **768 dimensions**, batched 64 at a time, with a
  read timeout that scales with chunk count because a cold Ollama needs time to load the model.
- `OpenSearchRagClient` indexes and retrieves. The index must declare a `method` or the graph is
  built for the default `l2` space while the ranking is cosine.
- The agent (`AiAgent`) supplies the system prompt, model and JSON mode.
- Answers can be **exported** (`convertForExport`, `EXPORT_CONTENT_TYPES`) or **emailed**
  (`emailExport`, via `FileShareService`).

> **The `_bulk` bug, fixed and worth remembering.** `StringHttpMessageConverter.getContentTypeCharset`
> returns UTF-8 only if the content type `isCompatibleWith(application/json)`, otherwise
> `ISO_8859_1`. `application/x-ndjson` is not compatible, so every bulk body went out as Latin-1:
> each indexed chunk was mangled, and any chunk carrying U+0080–U+00FF was **rejected outright and
> lost from the middle of its file**. Fixed by setting the charset explicitly. **205 chunks in the
> live index are still damaged** — the fix prevents new damage, it does not repair stored data. A
> deliberate reindex is still outstanding.

### 6.6 `object-browser`

Browse, preview, upload, rename, delete across any connection; share a file by email
(`FileShareService`); or start a file chat on it. Listing is paged with a continuation token —
a folder holding more than 200 entries silently truncated before that was threaded through.

### 6.7 `tools`

**Transcript** — `AudioTranscriptRestApi` → `AudioTranscriptServiceImpl`, which posts over HTTP to
the **separate `audio_extract_service` container** (default `:8100`), the same Whisper pipeline as
batch job `F768927`. Chunked, with filler-word cleaning. Optional `[HH:MM:SS.mmm]` markers split the
result into segments.

*Read along (added 2026-09-15):* `shared/ui/read-aloud.service.ts` speaks the transcript back
through the browser's `speechSynthesis`, one segment per utterance, marking the spoken word in
yellow via `shared/ui/read-along-text.ts`. One passage per utterance because boundary events report
an offset — into one passage that is directly usable, into a concatenation it must be mapped back —
and because Chrome truncates long utterances. The counterpart of `dictation.service.ts`, which goes
the other way.

**Converter** — `DocumentConverterServiceImpl` drives **LibreOffice inside the `process` container**
through JODConverter. The Dockerfile installs targeted components plus metric-compatible fonts
(Liberation, Carlito, Caladea): without them LibreOffice substitutes a fallback for every document
referencing Arial, Times New Roman, Calibri or Cambria, and converted output reflows.

### 6.8 `bulk-transfer`

Download a template, fill it, upload it. Jobs and tasks each have their own template, list export
and upload endpoint. `SourceJobBulkServiceImpl` validates per row so one bad row does not reject the
file.

### 6.9 `admin`, `tenants`, `settings`

`TenantServiceImpl` and `TenantRequestServiceImpl` handle workspace requests and approval;
`TenantSeedService` provisions a new tenant and **backfills** tenant ids onto pre-tenant rows.
`SettingServiceImpl` and `LookupData` provide the lookup tables the task editor reads.

### 6.10 `job-assistant` and `ai/agents`

`JobAssistantServiceImpl` answers questions about a job from its own rows — status, schedule, recent
runs, audit lines — rather than from a model's memory. `AiAgentServiceImpl` manages the agents that
supply prompts and models to both this and file chat.

---

## 7. Failure modes worth knowing before you debug

| Symptom | Likely cause |
|---|---|
| A job collects "skip, already in queue" forever | a stranded in-flight row; `reconcileStalledRuns` only sweeps Start and Running |
| Times are five hours out | the app pins Chicago, the database is UTC |
| An audit log looks empty in PostgreSQL | it is in OpenSearch; the table is only the fallback |
| A failed operation looks successful | the envelope — business failures are HTTP 200 with `status: "ERROR"` |
| Your change is not running | `:4400`/`:9098` are **containers**. `process/Dockerfile` **copies** `target/*.jar`, so `mvn test` is not enough — run `mvn package` first |
| Tenant is null in new code | it runs off the request thread; `TenantContext` is a ThreadLocal |
| A `-Dtest=A+B` run passes suspiciously fast | wrong separator; use commas, or `failIfNoTests=false` reports a false green |
| RAG answers miss text from mid-file | the Latin-1 damage; 205 chunks still need reindexing |

---

## 8. What this platform does not have

Named because their absence is a design fact, not an oversight to be discovered again:

- **No job dependencies.** `SourceJob` has `priority` but no `dependsOn`. Everything is
  time-triggered, so "extract, then transform" is three jobs on three timers spaced by guesswork.
  The natural place for a gate is stage 2 of the dispatcher (§4.3).
- **No incremental loads.** `postgres_to_csv_f768941` runs a whole free-text `SELECT` every run.
- **No data lineage.** Nothing answers "which job produced this file".
- **No freshness alerting.** See §5.2.
- **No backfill.** No "re-run for 1–14 September".
- **No Parquet or Excel connector**, though `pandas` is already a dependency.

---

*Last updated 2026-09-15. Sources: the 31 controllers in `process/src/main/java/process/api/`,
`engine/`, `analytics/`, `security/`, `socket/`, `emailer/`; `job-search/etl/`; and
`scheduler1/next/src/app/`.*
