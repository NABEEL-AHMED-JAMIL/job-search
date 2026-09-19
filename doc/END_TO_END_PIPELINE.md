# End-to-end pipeline flow

How a pipeline actually runs, from an empty database to a Python task function executing — and
what has to exist at each step for the next one to be possible.

Everything here was verified against the source on 2026-09-07. File references are
`path:line` relative to the repository root that contains `process/`, `scheduler1/` and
`job-search/`.

---

## 1. The four moving parts

| Part | Where | Role |
|---|---|---|
| Angular console | `scheduler1/next` | Where a human configures everything below |
| `process` backend | `process/` (Spring Boot, port 9098, context path `/api/v1`) | Owns the database, the REST API, and the only Kafka **producer** |
| Kafka | broker on 9092 | Carries one JSON message per job run |
| Python worker | `job-search/etl` | The Kafka **consumer**; parses the payload and runs the task |

The backend never runs a pipeline. It publishes a message and waits to be told what happened.
The worker never reads the database. It gets everything it needs from the message and reports
back over HTTP. Neither proves anything without the other, which is what
`scripts/seed_etl_demo.py` exists for — it builds the whole chain below through the real API
and then runs it (§7).

---

## 2. The dependency chain

Each step is impossible until the one above it exists. This ordering is not a style preference —
it is enforced by foreign keys and by validation in the service layer.

```
PLATFORM_ADMIN  (seeded; TenantSeedService.java:59-75)
      │
      ├─► Tenant                       POST /api/v1/tenant.json/addTenant        [PLATFORM_ADMIN]
      │       │
      │       ├─► AppUser (TENANT_ADMIN)   POST /api/v1/appUser.json/addUser
      │       │         │
      │       │         └─► everything below is created by this tenant admin
      │       │
      │       ├─► KafkaConnectionProfile   POST /api/v1/kafkaConnectionProfile.json/addProfile
      │       │       └─► setAsDefault     POST .../setAsDefault?kafkaConnectionProfileId=
      │       │
      │       ├─► SourceTaskType           POST /api/v1/setting.json/addSourceTaskType
      │       │       • REQUIRED: serviceName, description, queueTopicPartition
      │       │       • queueTopicPartition must match exactly:
      │       │             topic=<name>&partitions=[<n>|*]
      │       │         (KafkaTopicPartitionUtil.java:22-23)
      │       │       • optionally bound to a KafkaConnectionProfile
      │       │
      │       ├─► TaskForm ("Pipeline Form")  POST /api/v1/taskForm.json/saveForm
      │       │       • pipelineId + the fields a task on it must fill in
      │       │       • THIS IS NOW THE ONLY PIPELINE CATALOGUE — the old PIPELINE_IDS
      │       │         lookup family was removed (changeset V28)
      │       │
      │       ├─► SourceTask              POST /api/v1/sourceTask.json/addSourceTask
      │       │       • carries xmlTagsInfo[] → stored as source_task_payload rows
      │       │       • and task_payload: the generated XML string
      │       │
      │       └─► SourceJob               POST /api/v1/sourceJob.json/addSourceJob
      │               • priority is NOT NULL
      │               • execution Auto creates a Scheduler row; Manual does not
      │
      └─► JobQueue row  ← ProcessCron.addJobInQueue() every 60s, or runSourceJob (manual)
                │
                └─► Kafka send ← ProcessCron.startJobInCurrentTimeSlot() every 60s
                        (ProducerBulkEngine is the ONLY producer in the system)
```

### Two things that are easy to get wrong

- **`addProfile` never creates a default.** It always writes `isDefault=false`
  (`KafkaConnectionProfileServiceImpl.java:106`). A profile is only the tenant default after an
  explicit `setAsDefault` call. A dispatch that "mysteriously" uses the platform broker is
  usually this.
- **The `QUEUE_FETCH_LIMIT` lookup row must exist.** `ProducerBulkEngine.java:187-188`
  dereferences it with no null check, so a missing row throws on every dispatch pass, once a
  minute, for every tenant.

---

## 3. The Kafka message — the contract between the two languages

Produced by `ProducerBulkEngine`, serialised from `JobPayloadDTO` with
`new GsonBuilder().disableHtmlEscaping().create()` (`JobPayloadDTO.java:73-74`). Gson omits null
fields, so a key whose value is null is **absent**, not `null`.

```json
{
  "jobQueueId": 91422,
  "jobId": 1196,
  "pipelineId": "F768926",
  "taskPayload": "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"no\"?>\n<pipeline>\n  <start_year>1975</start_year>\n</pipeline>\n",
  "homePageId": "Object Browser Home 018",
  "priority": 1
}
```

| Key | Type | Notes |
|---|---|---|
| `jobQueueId` | Long | One per run |
| `jobId` | Long | The `SourceJob` |
| `pipelineId` | String | The **raw** string from `source_task.pipeline_id`, trimmed. Deliberately no longer a lookup id. This is what the worker routes on. |
| `taskPayload` | String | The task's XML, verbatim. `disableHtmlEscaping()` exists precisely so `<` and `>` survive as themselves. |
| `homePageId` | String | **Resolved through the lookup table** — the emitted value is `lookup_data.lookup_value`, not the stored numeric id. Absent when it does not resolve. |
| `priority` | Integer | Carried, never read back by either side. |

There is **no** `tenantId`, `jobName`, `bucket`, `outputFolder` or `topic` in the body. The record
key is a fresh `UUID.randomUUID()` per send, so it gives no ordering or idempotency guarantee.

**Topic and partition** come from `source_task_type.queue_topic_partition`. `partitions=[*]` sends
without a partition; a numeric value pins one.

---

## 4. The XML payload format

Generated by `XmlOutTagInfoUtil.makeXml` from the task's tag rows, and parsed on the Python side by
`etl/util/xml_parser.py`. The generator's exact output (verified on the JDK the image ships,
`eclipse-temurin:17-jdk`):

- Declaration is always `<?xml version="1.0" encoding="UTF-8" standalone="no"?>` — `standalone="no"`
  **is** emitted.
- Indent is exactly two spaces per level; lines end `\n`; the string ends with a single trailing `\n`.
- No namespaces, ever.
- In text nodes, `&` `<` `>` are escaped. Double quote and apostrophe are **not**.
- A `tagParent` naming a tag that no row created gets an auto-created wrapper with no text of its own.
- If the root row carries a non-blank value, the result is *mixed content* — the root's own text sits
  on its own indented line. Python's `ElementTree` handles this, but `root.text` is then
  `"\n  value\n  "`, so any code reading it must `.strip()`.

```xml
<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<pipeline>
  <start_year>1975</start_year>
  <end_year>2026</end_year>
  <hurricanes_url>https://example/{year}</hurricanes_url>
  <folder>hurricane/output</folder>
</pipeline>
```

---

## 5. The pipelines

Routed in `etl/tpd/tpd_scrapping_listener.py` (`execute_task`), parsed by
`pipeline_xml_parser` in `etl/util/xml_parser.py`.

| Pipeline | Task function | Required XML tags | Needs, beyond MinIO |
|---|---|---|---|
| `F768926` | `fetch_and_extract_all_seasons` | `start_year`, `end_year`, `hurricanes_url`, `folder` (optional `bucket`) | Outbound internet |
| `F768927` | `mp3_noise_processing_extract_txt` | `input_folder`, `output_folder` | `ffmpeg`, torch/whisper; downloads model weights on first run |
| `F768920` | `zanium_firebase_data_export` | `bucket`, `credential`, `extracted_data`, `target_type`, `target_table_config` | Firebase service account + a reachable `v4_backend` Postgres |
| `F76800` | `send_email_batch` | `email_config_uuid` (optional `recipients_bucket`, `recipients_object`) | A reachable SMTP server |

### The object-storage family (F768930–F768944)

Fifteen pipelines that read and write MinIO — and, for two of them, Postgres — and nothing else.
No internet, no model weights, no external service, so they run anywhere the stack runs. Every
one takes a flat tag list, accepts an optional `<bucket>`, and fails with a sentence naming the
setting rather than a stack trace when something is missing.

| Pipeline | Task function | Required tags | Optional |
|---|---|---|---|
| `F768930` | `csv_to_json` | `input_folder`, `output_folder` | `format` (records\|lines) |
| `F768931` | `csv_schema_validate` | `input_folder`, `output_folder`, `required_columns` | `numeric_columns`, `summary_name` |
| `F768932` | `csv_deduplicate` | `input_folder`, `output_folder` | `key_columns`, `keep` (first\|last) |
| `F768933` | `filter_csv_rows` | `input_folder`, `output_folder`, `column`, `operator` | `value` (required unless the operator is `is_empty`/`is_not_empty`) |
| `F768934` | `merge_csv_files` | `input_folder`, `output_folder`, `output_name` | `add_source_column` |
| `F768935` | `csv_group_by_aggregate` | `input_folder`, `output_folder`, `group_by`, `aggregation` | `aggregate_column` (not needed for `count`) |
| `F768936` | `csv_select_rename` | `input_folder`, `output_folder`, `column_mapping` | — |
| `F768937` | `csv_quality_report` | `input_folder`, `output_folder` | — |
| `F768938` | `split_csv_into_chunks` | `input_key`, `output_folder`, `rows_per_chunk` | — |
| `F768939` | `compress_objects_for_archival` | `input_folder`, `output_folder` | `suffix`, `delete_source` |
| `F768940` | `csv_to_postgres` | `input_folder`, `target_table`, `db_host`, `db_name`, `db_user`, `db_password` | `db_port`, `db_schema`, `truncate_before_load` |
| `F768941` | `export_postgres_query_to_csv` | `query`, `output_folder`, `output_name`, `db_host`, `db_name`, `db_user`, `db_password` | `db_port` |
| `F768942` | `join_csv_objects` | `left_object`, `right_object`, `join_key`, `output_folder`, `output_name` | `join_type`, `right_suffix` |
| `F768943` | `csv_snapshot_diff` | `previous_object`, `current_object`, `output_folder` | `key_columns`, `prefix` |
| `F768944` | `sweep_objects_for_retention` | `input_folder`, `archive_folder`, `older_than_days` | `dry_run` |

Two things worth knowing before configuring these:

- **`F768939`'s `<suffix>` filters the input, it does not name the output.** The output is always
  `<object>.gz`. Setting it to `.gz` makes the pipeline look for already-compressed input and
  correctly report finding nothing.
- **`F768940` and `F768941` carry their database credentials in the task payload**, which is a
  row in the same database. Point them at a role scoped to the one table they touch — never the
  application's own role. `F768940` deliberately checks whether the schema and table exist before
  issuing any `CREATE`: Postgres tests the privilege before the existence, so a bare
  `CREATE SCHEMA IF NOT EXISTS public` demands database-level `CREATE` even though `public` is
  already there, and that alone would force the ETL role to be over-privileged.

`PIPELINE_TASKS` in `tpd_scrapping_listener.py` and `pipeline_xml_parser` in `xml_parser.py`
are now exactly in step — nineteen entries each, no orphan on either side. The table form
exists so the two lists can be read against each other; a router branch with no parser, or a
parser no branch can reach, is visible as a one-line difference.


---

## 6. The worker's callbacks

The worker reports progress to `NotifyResetApi` at `ETL_EVENT_URL` (`…/api/v1`), authenticated by a
token in `X-Worker-Token`, **not** a JWT. Since 2026-09-18 every dispatch carries `callbackToken`,
good for that run alone (`RunCallbackTokens` on the server, a hash on the queue row); the listener
remembers it per run (`JobStateClient.remember_run_token`) and echoes it on every callback for
that run, so a callback can only touch the run it was handed. The shared
`WORKER_CALLBACK_TOKEN` is honoured only for a run dispatched before tokens existed and is the
fallback, not the rule.

| Call | Purpose |
|---|---|
| `POST /changeState/jobId/{jobId}/jobQueueId/{jobQueueId}/jobStatus/{status}` | Running / Completed / Failed |
| `POST /addLogsBatch/jobId/{jobId}/jobQueueId/{jobQueueId}` body `{"messages":[…]}` | Batched log lines — what the worker actually uses |
| `POST /addLogs/jobId/{jobId}/jobQueueId/{jobQueueId}` | A single line |

Not every transition is legal — `Queue → Running` is rejected — and, in keeping with the rest of
this API, a rejection arrives as **HTTP 200 with an error body**, not a 4xx.

### AI steps handed to the worker

A pipeline can carry an AI step (Configuration › Pipelines, a field of type "AI prompt"). One
that runs *before dispatch* is invisible here: the console runs the prompt and the document
arrives with the answer as an ordinary tag. One that runs *in the worker* arrives as

```xml
<ai_step prompt="<uuid>" version="3" output="summary" on_error="fail">
  <var name="claim_id" from="claim_id" as="text"/>
  <var name="document_text" from="document" as="file"/>
</ai_step>
```

`etl/util/ai_steps.resolve_ai_steps` runs before the pipeline's parser in both listeners: it reads
each variable (`as="text"`: the tag's text; `as="file"`: the contents of the object the tag names,
from the task's `<bucket>` or the platform bucket), calls
`POST /aiPrompt.json/run` with `{jobId, jobQueueId, promptUuid, version, stepTag, variables}` and
the run's token, writes the answer to `<summary>`, and drops the element. The console holds the
model key, makes the call, records the run with its tokens and time, and hands back the text; a
refusal (`on_error="fail"`) fails the run, or (`continue`) leaves the tag empty. No task module
knows a model was involved -- the parser sees a tag. The test listener needs the MinIO variables
for this, which `docker-compose.yml` now passes it.

A step whose variable reads `from="object"` runs **once per object under the task's
`<input_folder>`** in its `<bucket>` (its contents with `as="text"`, its key with `as="name"`), and
each answer is written to `<output_folder>/<object basename>.<output tag>.json|txt` -- the same
folders the object-storage family reads and writes, so an AI summary lands next to the pipeline's
own outputs. The tag then holds a manifest (`{"objects", "written", "failed"}`); each object is its
own run on the console (`tag#key`), so a retried run skips the objects already answered. At most
200 objects per step.

---

## 7. Seeding and running the whole chain

```bash
cd job-search
.venv/bin/python scripts/seed_etl_demo.py            # build the configuration
.venv/bin/python scripts/seed_etl_demo.py --run      # build it, then run all fifteen
.venv/bin/python scripts/seed_etl_demo.py --cleanup  # remove everything it made
```

`scripts/seed_etl_demo.py` walks §2 from the top: a tenant, a tenant admin, a Kafka connection
profile (and the `setAsDefault` call that a new profile still needs), a Source Task Type on
`scrapping-topic`, then a Pipeline Form, Source Task and Source Job for each of the fifteen —
and it stages each pipeline's demo input in MinIO so every job has something real to read.
`--run` dispatches them and follows each to a terminal state.

Nothing is mocked. It logs in over HTTP like any other client, and every row it writes is one
the console can open, edit and run.

`scripts/etl_demo_catalogue.py` holds the fifteen as data: the form fields, the tag values, and
the demo input. `assert_catalogue_is_consistent()` runs before anything is written and fails if
a task sends a tag its form does not have, or a form marks a field required that the task never
sets — both are invisible until a run fails.

Three things worth knowing before running it:

- **Sign in as the tenant, not the platform admin.** `saveForm` deliberately files a platform
  admin's new form under the seeded *default* tenant (`TaskFormServiceImpl:136-144`), so seeding
  as one puts fifteen forms on an unrelated tenant. The script creates the tenant admin and
  switches to it before creating anything tenant-scoped, which is also what a real operator does.
- **`setAsDefault` scopes by the profile's own `tenantId`.** A profile created by a platform
  admin has none, so making it default clears the *platform* default and every tenant without
  its own profile loses its broker. Creating it as the tenant admin keeps the blast radius to
  that tenant. `--cleanup` warns if no platform default is left.
- **`F768941` is held back until `F768940` finishes.** It exports the table `F768940` loads;
  dispatched together they race, and the loser reports a successful export of zero rows.

Credentials are never stored in the repository. The script reads the database credentials out of
the running `process_app` container, the same way `process/run-e2e.sh` does for the Java suite,
and MinIO's from `.env`. Each run inserts its own throwaway `PLATFORM_ADMIN` with a freshly
generated password, prints it once, and `--cleanup` deletes the row.

It also creates `public.etl_demo_products` and a Postgres role `etl_demo` granted on that table
alone — the landing table for `F768940` and the source for `F768941`. `--cleanup` leaves both in
place and prints the two statements to drop them, because dropping a role and a table is not
something a cleanup flag should do on its own.

---

## 8. A note on scope

`.ai/README.md` records `job-search` as out of scope for the console rewrite phase. The seeder is
deliberately an exception: it is the only place the *cross-language* contract is exercised end to
end, and that contract is exactly what breaks silently when either side changes alone.

## 9. Metering — what a run reports it used

Every run reports what it used to the **metering service** (`etl_meter`, `etl/meter`, port 8200),
and the console's Cost & usage page shows the month priced from it. A pipeline does not have to
do anything: the listener opens one `Meter` per run (`etl/util/meter.py`) and hands it to the task
in `task_payload["meter"]`; the `Pipeline` helper's `read_bytes`, `write_bytes`, `list_keys` and
`delete` go through it, so every get, put and delete — and the bytes each moved, a delete's size
read *before* it goes — is counted. Worker minutes are added at close. Anything else a task wants
counted is one call: `p.meter.event("ai.tokens.in", 1240, unit="token", subject=("prompt", uuid))`.

**How it reports.** One batch at the end of the run (on failure too), `POST /v1/events`, with the
run's own callback token and its ids (`X-Worker-Token`, `X-Job-Id`, `X-Job-Queue-Id`). The meter
asks the console (`/meter.json/verifyRun`) whose run that is and stamps the workspace itself — a
run cannot report as another tenant. Every event's `dedupeKey` is `{jobQueueId}#{meter}#{seq}`, so a
replayed batch is all duplicates and the totals do not move.

**When the meter is down.** Three tries, then the batch is spooled to `METER_SPOOL_DIR`
(`/tmp/etl-meter-spool`) and sent ahead of the next run's batch, under its own run's token. The
console keeps a finished run's token good for reports for 24 hours (`RunCallbackTokens.retire`),
so a spooled batch is still provably that run's; a callback on a finished run is refused as before.
The job completes either way — metering is never a reason for a run to fail.

**Units.** Byte meters carry bytes (`unit="byte"`) and are priced per GB on the rate card; the
ledger stores `numeric(18,6)`, which would have rounded a 40-byte archive stored as GB to nothing.

**Testing it.** `tests/test_meter_service.py` (the contract, on an in-memory store) and
`tests/test_meter_client.py` (counting, the batch, the spool, the refusal). The end-to-end run the
design describes — N files of size S through a compress-and-delete task, `bytes.deleted = N × S`
and `ops.delete = N` exactly; a replayed batch all duplicates; the meter stopped mid-run and the
spool arriving with the next run; a delete from the console named on the page — is the
`meter-e2e-full.py` script recorded in `.ai/execution/README.md`.
