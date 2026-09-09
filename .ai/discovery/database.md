# Discovery -- Database

PostgreSQL, reached by one Spring Boot service (`process`, Spring Boot 2.3.2.RELEASE per
`process/pom.xml:9-10`). The schema is described in two places at once: Liquibase changelogs under
`process/src/main/resources/db/changelog/`, and the JPA entity mappings under
`process/src/main/java/process/model/pojo/`. Which of the two actually creates a given table is the
single most important thing to understand about this schema, and section 1 covers it first.

All paths below are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. How the schema is managed, and what happens on startup

### The two mechanisms

| Mechanism | Configured at | Value |
|---|---|---|
| Liquibase | `process/src/main/resources/application-dev.properties:101-103` | `enabled=true`, `contexts=init`, `change-log=classpath:db/changelog/db.changelog-master.yaml` |
| Liquibase | `application-stage.properties:104-106`, `application-prod.properties:106-108` | identical to dev |
| Hibernate DDL | `application-dev.properties:87` | `spring.jpa.hibernate.ddl-auto=update` |
| Hibernate DDL | `application-stage.properties:90`, `application-prod.properties:92` | `spring.jpa.hibernate.ddl-auto=validate` |

`spring.profiles.active=dev` is the default (`application.properties:7`).

### Order of operations on startup

Spring Boot initialises Liquibase before the JPA `EntityManagerFactory`, so **Liquibase runs first
and Hibernate's `ddl-auto` runs second**. The codebase relies on this and says so explicitly:

> "on a brand-new database this migration runs before Hibernate (ddl-auto=update) has ever created
> lookup_data, so without the guard this whole changeset fails outright"
> --- `process/src/main/resources/db/changelog/changelog-sets/V8.0-lookup-encryption/V8__add_lookup_encrypted_column.sql:5-8`

The same reasoning is restated at
`changelog-sets/V11.0-kafka-dynamic-config/V11__drop_schema_fields.sql:22-24`.

### What Liquibase actually creates

Only **six** tables and **four** sequences are created by a changeset. Grepping every changeset for
`CREATE TABLE` returns exactly:

| Table | Created in |
|---|---|
| `shedlock` | `changelog-sets/V1.0-init/V1__creating_shedlock_schema.sql:1` |
| `lookup_data` | `changelog-sets/V1.0-init/V1__creating_shedlock_schema.sql:13` |
| `source_task_type` | `changelog-sets/V1.0-init/V1__creating_shedlock_schema.sql:27` |
| `task_form` | `changelog-sets/V19.0-task-form-builder/V19__task_form_builder.sql:12` |
| `task_form_field` | `changelog-sets/V19.0-task-form-builder/V19__task_form_builder.sql:27` |
| `tenant_request` | `changelog-sets/V21.0-tenant-request/V21__tenant_request.sql:9` |

Sequences created by changesets: `lookup_id_Seq` and `source_task_type_source_Seq`
(`V1__creating_shedlock_schema.sql:10,24`), `task_form_source_seq`
(`V19__task_form_builder.sql:10`), `tenant_request_seq` (`V21__tenant_request.sql:7`).

**Every other table and sequence in this database exists only because Hibernate's
`ddl-auto=update` created it from an `@Entity` mapping.** That is 22 of the 28 application tables,
including `tenant`, `app_user`, `source_job`, `source_task`, `scheduler`, `job_queue` and
`job_audit_logs`. `V11__drop_schema_fields.sql:14-20` states this design intent directly: additive
columns are left to `ddl-auto=update`, and changesets only carry "the destructive/rename steps
ddl-auto=update can't do on its own".

The consequence is in section 8: `ddl-auto=validate` on stage and prod means Hibernate will not
create those 22 tables there, and no changeset will either.

### The master changelog

`process/src/main/resources/db/changelog/db.changelog-master.yaml` lists 22 `include` entries and
four `exclude` entries. V4.0--V7.0 are deliberately not applied; the file's header comment
(lines 2-8) explains they are "historical column/default fixups against schema states already
superseded by the current JPA entity mappings".

Two notes on the master file:

- `exclude` is not a Liquibase `databaseChangeLog` element (Liquibase supports `include`,
  `includeAll`, `changeSet`, `property`, `preConditions`). The effect intended --- V4--V7 never
  running --- is achieved simply by their absence from the `include` list; the `exclude` blocks read
  as documentation. Whether the Liquibase parser silently tolerates them or would reject them is
  **not verified** --- no Liquibase output appears in `process/logs/process.log`, and the version is
  whatever Spring Boot 2.3.2 manages (3.8.9 is present in the local `~/.m2`).
- `spring.liquibase.contexts=init` is set, but **no changeset declares a `context`**. In Liquibase, a
  changeset with no context runs under every context, so this setting currently selects nothing.

### Concurrency and locking

`shedlock` (`V1__creating_shedlock_schema.sql:1-7`) is a scheduler mutex, not application data ---
`V17__table_descriptions.sql:81-82` describes it as stopping "two application instances from firing
the same scheduled run". `databasechangelog` / `databasechangeloglock` are Liquibase's own
bookkeeping tables (`V17__table_descriptions.sql:84-88`).

### Rollbacks

Most changesets carry an explicit `rollback` block. Three are deliberate no-ops with a stated
reason: V16 ("the original casing was itself the bug"), V17 ("Comments are documentation, not
structure"). V10 and V11 declare no rollback at all.

---

## 2. Migration history

Each row is one changelog file under `process/src/main/resources/db/changelog/yaml/`, with its
changeset SQL under `changelog-sets/`.

| Changelog | What it changed | Why it matters |
|---|---|---|
| `V1.0-init.yaml` | Creates `shedlock`, `lookup_data` (+ `lookup_id_Seq`) and `source_task_type` (+ `source_task_type_source_Seq`), all `IF NOT EXISTS` | The only structural baseline in the whole chain. Everything else assumes Hibernate has built the rest. |
| `V2.0-init.yaml` | Seeds 7 `lookup_data` rows with hardcoded ids 1001--1019: `SCHEDULER_LAST_RUN_TIME`, `QUEUE_FETCH_LIMIT`, `PIPELINE_IDS`, `PIPELINE_HOME_PAGES`, `EMAIL_RECEIVER` | These are runtime configuration read by the ETL engine, not sample data. Ids are hardcoded, which is why V9/V10 have to `setval` the sequence afterwards. |
| `V3.0-init.yaml` | Seeds 11 `source_task_type` rows (ids 1000--1010) | The original consumer catalogue. V10 later established that 10 of the 11 described consumers that do not exist. |
| `V4.0-update-task-type-status.yaml` | **Excluded.** Would normalise status enums to PascalCase and set column defaults | Superseded by the entity mappings; running it against a fresh DB would `ALTER` tables Hibernate has not yet created. |
| `V5.0-update-lob-columns.yaml` | **Excluded.** `job_queue.job_status_message` and `job_audit_logs.log_detail` to `CLOB` | Historical; the entities now declare `columnDefinition = "TEXT"` directly. |
| `V6.0-fix-lob-to-text.yaml` | **Excluded.** Same two columns, `CLOB` -> `TEXT` | Undoes V5 --- `CLOB` was wrong for PostgreSQL. Kept in the tree as a record of the mistake. |
| `V7.0-add-status.yaml` | **Excluded.** Adds `status VARCHAR(50) NOT NULL DEFAULT 'Active'` to `job_queue` and `job_audit_logs` | Both columns exist today via the entity mappings (`JobQueue.java:90-93`, `JobAuditLogs.java:56-59`). |
| `V8.0-lookup-encryption.yaml` | Adds `lookup_data.is_encrypted BOOLEAN NOT NULL DEFAULT FALSE` | **Feature: encrypted lookup values.** Marks whether `lookup_value` holds AES-256-GCM ciphertext. First changeset to need a `to_regclass` guard and `splitStatements: false` (a `DO $$` block), because it runs before Hibernate has created `lookup_data` on a fresh database. |
| `V9.0-ai-provider-bucket-list.yaml` | Seeds `AI_PROVIDER` (OpenAI/Anthropic/Ollama, ids 1020--1023) and `BUCKET_LIST` (etl-bucket/test-bucket/from-craft, ids 1024--1027); then `setval('lookup_id_seq', max(lookup_id))` | **Feature: AI Agents + Object Browser.** The `setval` at line 38 is load-bearing: V2/V3 inserted hardcoded ids without touching the sequence, so JPA-generated lookups would otherwise collide. |
| `V10.0-fix-task-types-pipelines.yaml` | Deletes `source_task_type` 1001--1010, activates 1000, inserts 1011 (`ETL Scrapping Pipeline`); replaces `PIPELINE_IDS` child 1016 with 1028--1031 (F768924--F768927) | Reconciles the catalogue against the real Kafka listeners in the `job-search` project. The file records that 1007--1010 never matched `ProducerBulkEngine`'s `topic=X&partitions=[Y]` format and "could never have sent a single real message". |
| `V11.0-kafka-dynamic-config.yaml` | Drops `source_task_type.is_schema_register` and `.schema_payload`; renames `kafka_connection_profile.connection_active` -> `is_default` | **Feature: per-tenant Kafka routing.** Every additive column of that feature is left to `ddl-auto=update`; this changeset carries only the drop and the rename. Guarded with `to_regclass`, same as V8. |
| `V12.0-tenant-user-fk-constraints.yaml` | 23 `FOREIGN KEY` constraints on `tenant_id`, `assigned_user_id`, `created_by`, `updated_by` across 15 tables | Turns application-enforced tenancy into database-enforced tenancy. No `ON DELETE` clause, deliberately: the app soft-deletes via `Status.Delete` and never issues a real `DELETE FROM tenant`. |
| `V13.0-job-fk-constraints.yaml` | 3 FKs: `job_queue.job_id`, `scheduler.job_id` -> `source_job`; `job_audit_logs.job_queue_id` -> `job_queue` | Closes the job graph. |
| `V14.0-remaining-fk-constraints.yaml` | 11 FKs across `dynamic_form_submission`, `pdf_highlighter_field`, the whole Query Engine, and the Kafka route table | Completes the FK sweep started in V12/V13. See section 8 for what it still missed. |
| `V15.0-scheduler-recurrence-rules.yaml` | Renames `scheduler.recurrence` -> `interval_value`; adds `days_of_week`, `day_of_month`, `next_run_at`, `expired`, `date_updated`; drops `recurrence_time`; indexes `next_run_at` | **Feature: scheduler redesign.** `expired` replaces the old behaviour of "silently leaving recurrence_time frozen in the past with no signal anywhere". Mirrors `query_schedule.next_run_at`, which proved the pattern first. |
| `V16.0-fix-source-job-status-casing.yaml` | `UPDATE source_job SET job_status` from `ACTIVE`/`INACTIVE`/`DELETE` to `Active`/`Inactive`/`Delete` | **Data repair.** 44 of 45 rows were all-caps against a case-sensitive `@Enumerated(EnumType.STRING)` mapping --- two bugs at once: rows silently missing from typed JPQL, and `IllegalArgumentException: No enum constant` on any full-entity fetch. See section 8: a live code path still writes the bad casing. |
| `V17.0-table-descriptions.yaml` | 28 `COMMENT ON TABLE` statements: the 25 application tables that existed at the time, plus `shedlock` and the two Liquibase tables | Documentation in the database itself. Records which tables carry `tenant_id` and which inherit it, and calls out `source_task_payload.payload_id` as a foreign key despite its name. `task_form`, `task_form_field` and `tenant_request` did not exist yet and get their own comments in V19 and V21. |
| `V18.0-foreign-key-indexes.yaml` | 8 indexes on referencing-side FK columns and hot query paths | "Postgres indexes a primary key but never the referencing side." Explicitly not a response to a measured regression --- "for the shape of the query". |
| `V18.0-user-avatar.yaml` | Adds `app_user.avatar_bucket VARCHAR(255)` and `avatar_key VARCHAR(512)` + column comments | **Feature: user avatar.** Both halves stored because "a bucket is only reachable through the storage connection that owns it". Note the duplicated V18 number --- distinct changeset ids keep them from colliding, but the numbering is a wart. |
| `V19.0-task-form-builder.yaml` | Creates `task_form` + `task_form_field` + `task_form_source_seq`, a partial unique index and two plain indexes | **Feature: task form builder.** Deliberately stores no payload --- `source_task_payload` remains the source of truth, so "a task configured through a form and one configured by hand are the same task". |
| `V20.0-user-position.yaml` | Adds `app_user.position VARCHAR(120)` | **Feature: user job title.** Explicitly distinct from `user_role`: "a Lead and a Software Engineer can both be TENANT_USER". |
| `V21.0-tenant-request.yaml` | Creates `tenant_request` + `tenant_request_seq` + two indexes; adds `app_user.must_change_password BOOLEAN NOT NULL DEFAULT FALSE` | **Feature: self-service workspace requests.** Stored rather than acted on because the form is unauthenticated. `must_change_password` is what makes the emailed password one-time. |
| `V22.0-audit-columns.yaml` | Adds `created_by`/`updated_by` to 10 tables, `updated_by` alone to `task_form` | **Feature: authorship on every screen.** Five tables already had them; the rest showed work with no author. Purely operational tables (`job_queue`, `job_audit_logs`, `notification`) are deliberately left out. |
| `V23.0-avatar-key-layout.yaml` | Rewrites the `app_user.avatar_key` comment: `<appUserId>/profile/avatar.<ext>` instead of a flat `avatars/` prefix | **Comment-only, and that is the point.** V18's comment was corrected in a new changeset rather than by editing V18, "because that one has already run everywhere and changing it would fail Liquibase's checksum on the next start". |
| `V24.0-user-phone.yaml` | Adds `app_user.phone_number VARCHAR(20)` + comment | **Feature: user phone.** E.164 in one column, because "storing the country separately would let the two drift apart". |
| `V25.0-drop-avatar-backup.yaml` | `DROP TABLE IF EXISTS avatar_backup_20260824` | Removes a hand-made pre-migration snapshot. Done through Liquibase so "every environment loses it at the same point in the chain". |

---

## 3. Every table

28 application tables (one per `@Entity` in `process/src/main/java/process/model/pojo/` --- the
directory holds 30 files, of which `AuditListener.java` and `Audited.java` are not entities), plus
three infrastructure tables.

| Table | Entity class | Purpose | Owning feature |
|---|---|---|---|
| `tenant` | `Tenant.java` | An isolated workspace; every tenant-scoped row keys back here | Multi-tenancy |
| `app_user` | `AppUser.java` | Sign-in identity: role, tenant, avatar, phone, position, `must_change_password`. Soft-deleted | Auth / user management |
| `tenant_request` | `TenantRequest.java` | An unauthenticated request for a workspace, pending a platform admin's decision | Self-service onboarding (V21) |
| `source_task` | `SourceTask.java` | One unit of ETL work: bucket, input/output folder, pipeline, task type | ETL core |
| `source_task_type` | `SourceTaskType.java` | Consumer class: service name and `topic=name&partitions=[n]` | ETL core / Kafka |
| `source_task_payload` | `SourceTaskPayload.java` | The tag tree of a task's XML payload, one row per tag. FK column `payload_id` -> `source_task.task_detail_id` | ETL core |
| `source_job` | `SourceJob.java` | A task bound to a timetable: priority, execution mode, three notification flags | ETL core |
| `scheduler` | `Scheduler.java` | The timetable for one Auto job; `next_run_at` is what the dispatcher polls | Scheduling (redesigned V15) |
| `job_queue` | `JobQueue.java` | One execution of a job: queued/started/ended, final status and message | ETL runtime |
| `job_audit_logs` | `JobAuditLogs.java` | Worker log lines for one run, keyed by `job_queue_id`. **Not the primary store** — OpenSearch is; this table takes only the lines OpenSearch rejected, plus what the 4-hourly `AuditLogSyncCron` reads back into it. Normally near-empty | ETL runtime / observability |
| `lookup_data` | `LookupData.java` | Shared key/value reference data, self-referencing parent/child | Settings |
| `notification` | `Notification.java` | In-app message for one recipient: type, severity, read state, link | Notification centre |
| `storage_connection` | `StorageConnection.java` | Credentials for one storage backend (S3/MinIO/Azure/FTP/FTPS), addressed by `alias` | Object Browser / storage |
| `kafka_connection_profile` | `KafkaConnectionProfile.java` | How to reach a Kafka cluster: brokers, SASL, TLS store locations | Kafka dynamic config (V11) |
| `tenant_task_type_kafka_route` | `TenantTaskTypeKafkaRoute.java` | Routes one tenant's task type to a specific Kafka profile | Kafka dynamic config (V11) |
| `ai_agent` | `AiAgent.java` | A configured AI assistant: provider, model, endpoint, encrypted key, instructions, `tool_uuid` | AI Agents (V9) |
| `database_connection_profile` | `DatabaseConnectionProfile.java` | An external database the query engine reads from | Query Engine |
| `query_definition` | `QueryDefinition.java` | A saved, `@Version`-ed SQL query (the SQL itself is stored encrypted) | Query Engine |
| `query_schedule` | `QuerySchedule.java` | A recurring run of a saved query and where its output is written | Query Engine |
| `query_execution` | `QueryExecution.java` | One run: row count, output bucket/key, or the error | Query Engine |
| `document_converter_task` | `DocumentConverterTask.java` | A completed file conversion, input/output formats, sizes and storage keys | Document Converter |
| ~~`dynamic_form`~~ | ~~`DynamicForm.java`~~ | **Dropped 2026-09-03** (`V26.0-drop-dynamic-forms`) with the rest of this row's feature -- see [`../discovery/features.md`](features.md) §2 (row 13) | ~~Form builder~~ |
| ~~`dynamic_form_field`~~ | ~~`DynamicFormField.java`~~ | Dropped with `dynamic_form` | ~~Form builder~~ |
| ~~`dynamic_form_submission`~~ | ~~`DynamicFormSubmission.java`~~ | Dropped with `dynamic_form` | ~~Form builder~~ |
| `pdf_highlighter_task` | `PdfHighlighterTask.java` | An uploaded PDF and its processing state | PDF Highlighter |
| `pdf_highlighter_field` | `PdfHighlighterField.java` | One marked region: page, x/y/w/h, text and XPath selectors, `use_xpath_first` | PDF Highlighter |
| `task_form` | `TaskForm.java` | Describes the payload one pipeline expects, so a task can be filled in rather than hand-written | Task form builder (V19) |
| `task_form_field` | `TaskFormField.java` | One field of a task form: the XML tag it fills and how it is presented | Task form builder (V19) |
| `shedlock` | *(none)* | Scheduler mutex across application instances | ShedLock library |
| `databasechangelog` | *(none)* | Liquibase migration history | Liquibase |
| `databasechangeloglock` | *(none)* | Liquibase migration mutex | Liquibase |

### Identifier generation

Almost every entity uses a per-table `SequenceStyleGenerator` with `initial_value = 1000` and
`increment_size = 1` (e.g. `SourceJob.java:47-58`). Two exceptions:

- `Notification.java:30-33` uses `GenerationType.IDENTITY` --- the only identity column in the
  schema.
- `TaskForm.java:42-53` and `TaskFormField.java:21-32` **share one sequence**,
  `task_form_source_seq`. Not incorrect, but it means form ids and field ids interleave and neither
  table's ids are contiguous.

---

## 4. Relationships and foreign keys

### Foreign keys added by changesets

**V12** (`changelog-sets/V12.0-tenant-user-fk-constraints/V12__add_tenant_user_fk_constraints.sql:13-35`)
--- tenancy and authorship, 23 constraints:

- `tenant_id -> tenant(tenant_id)` on: `ai_agent`, `database_connection_profile`,
  `document_converter_task`, ~~`dynamic_form`~~ (table dropped 2026-09-03, see §3),
  `kafka_connection_profile`, `lookup_data`,
  `pdf_highlighter_task`, `query_definition`, `query_execution`, `query_schedule`, `source_job`,
  `source_task`, `source_task_type`, `tenant_task_type_kafka_route`, `app_user`
- `created_by` / `updated_by -> app_user(app_user_id)` on: `database_connection_profile`,
  `query_definition`, `query_schedule`; `created_by` only on `query_execution`
- `source_job.assigned_user_id -> app_user(app_user_id)`

**V13** (`V13__add_job_fk_constraints.sql:8-10`) --- the job graph:
`job_queue.job_id` and `scheduler.job_id` -> `source_job(job_id)`;
`job_audit_logs.job_queue_id -> job_queue(job_queue_id)`.

**V14** (`V14__add_remaining_fk_constraints.sql:11-21`) --- everything else found in the pojo layer:
`dynamic_form_submission.dynamic_form_id`, `pdf_highlighter_field.pdf_highlighter_task_id`, the
Query Engine cross-references (`query_definition`/`query_execution`/`query_schedule` <->
`database_connection_profile`, `query_execution`/`query_schedule` -> `query_definition`,
`query_execution.schedule_id -> query_schedule`), and
`source_task_type.kafka_connection_profile_id` plus both of
`tenant_task_type_kafka_route`'s references.

**Not from a changeset:** `lookup_data.parent_lookup_id -> lookup_data(lookup_id)` is inline in
`V1__creating_shedlock_schema.sql:20`, and `task_form_field.task_form_id -> task_form` with
`ON DELETE CASCADE` is inline in `V19__task_form_builder.sql:29` --- the **only** `ON DELETE`
clause anywhere in the schema. V12 explains the omission elsewhere: the app soft-deletes, so
Postgres's default `NO ACTION` "costs nothing today and is the safer default if that ever changes"
(`V12__add_tenant_user_fk_constraints.sql:8-11`).

### Tenancy: which tables carry `tenant_id`

Eighteen tables have a `tenant_id` column. They split three ways.

**Strictly tenant-scoped --- `tenant_id` is `NOT NULL` in the mapping:**

| Table | Mapping |
|---|---|
| `database_connection_profile` | `DatabaseConnectionProfile.java:43` |
| `query_definition` | `QueryDefinition.java:42` |
| `query_schedule` | `QuerySchedule.java:43` |
| `query_execution` | `QueryExecution.java:43` |
| `tenant_task_type_kafka_route` | `TenantTaskTypeKafkaRoute.java:48` |

**Tenant-scoped but nullable** --- a null here is a leftover or a platform row depending on the
table: `app_user`, `source_task`, `source_job`, `lookup_data`, `ai_agent`,
~~`dynamic_form`~~ (dropped 2026-09-03),
`document_converter_task`, `pdf_highlighter_task`, `notification`.

Several repositories carry an explicit backfill for exactly this, e.g.
`SourceJobRepository.java:23-26` (`update SourceJob s set s.tenantId = ?1 where s.tenantId is null`)
and the same pattern in `SourceTaskRepository`, `DynamicFormRepository`, `AiAgentRepository`,
`PdfHighlighterTaskRepository`, and `LookupDataRepository.backfillBucketTenantId`.

**Platform-owned when `tenant_id IS NULL`** --- these are the shared catalogues, published to every
tenant:

| Table | Written null by |
|---|---|
| `source_task_type` | Seeded rows 1000 and 1011 from `V3__insert_source_task_type.sql` / `V10__fix_source_task_type_and_pipeline_ids.sql:28-31` (no `tenant_id` in the insert) |
| `kafka_connection_profile` | `V11__drop_schema_fields.sql:9-12` --- the pre-existing profile becomes the platform default |
| `storage_connection` | `process/src/main/java/process/config/StorageConnectionBootstrap.java:158` |
| `task_form` | `V19__task_form_builder.sql:20-21`: "Null means the definition is available to every tenant" |

`app_user` also gets one null-tenant row: the seeded platform admin
(`process/src/main/java/process/model/service/impl/TenantSeedService.java:115`,
username `admin@platform.local`).

**No `tenant_id` at all** --- these inherit their tenant through a parent row:
`scheduler` (via `source_job`), `job_queue` (via `source_job`), `job_audit_logs` (via `job_queue`),
`source_task_payload` (via `source_task`), `dynamic_form_field` and `dynamic_form_submission` (via
`dynamic_form`), `pdf_highlighter_field` (via `pdf_highlighter_task`), `task_form_field` (via
`task_form`), plus `tenant` and `tenant_request` themselves, which are platform-owned by nature.

`V17__table_descriptions.sql:2-4` states the rule this creates: "a query that reaches them by id
must join the parent to stay inside the caller's tenant."

### `@ManyToOne` shadowing

A recurring pattern: the raw `Long` column is the writable mapping and the association is
read-only, e.g. `SourceJob.java:61-66`:

```java
@Column(name = "tenant_id")
private Long tenantId;

@ManyToOne(fetch = FetchType.LAZY)
@JoinColumn(name = "tenant_id", insertable = false, updatable = false)
private Tenant tenant;
```

Two associations are *not* read-only and own their column instead:
`SourceTask.sourceTaskType` (`SourceTask.java:93-95`) and `SourceJob.sourceTask`
(`SourceJob.java:79-81`), both eagerly fetched by default --- which is why
`SourceJobRepository.java:43-45` needs explicit `LEFT JOIN FETCH` to avoid "a couple of thousand
round trips on a tenant with a few hundred tasks".

### Naming quirks to know

- `source_task_payload.payload_id` is a **foreign key to `source_task.task_detail_id`**, not this
  table's own id (its PK is `task_payload_id`). The column exists only because of the unidirectional
  `@OneToMany` at `SourceTask.java:97-99`; `SourceTaskPayload.java` maps no such field.
  `V17__table_descriptions.sql:18-19` flags this explicitly.
- `LookupData.java:76` writes `@JoinColumn(name = "parentLookupId")` in camelCase. Spring Boot's
  default physical naming strategy folds this to `parent_lookup_id`, which is what
  `V1__creating_shedlock_schema.sql:19` and `V18__foreign_key_indexes.sql:20` use. It works, but
  the mapping is the odd one out.
- `application-dev.properties:76` sets `spring.jpa.hibernate.naming-strategy`, which is the
  Hibernate 4 property name and is **not** the one Spring Boot 2.x reads
  (`spring.jpa.hibernate.naming.physical-strategy`). The default `SpringPhysicalNamingStrategy`
  applies regardless, which happens to produce the same snake_case result.

---

## 5. Multi-tenancy at the data layer

### The filter

All fifteen filtered entities declare the same `@FilterDef`:

```java
@FilterDef(name = "tenantFilter", parameters = @ParamDef(name = "tenantId", type = "long"))
```

They then split into two predicates:

| Predicate | Entities |
|---|---|
| `tenant_id = :tenantId` | `AiAgent.java:23`, `DatabaseConnectionProfile.java:24`, `DocumentConverterTask.java:23`, `DynamicForm.java:25`, `PdfHighlighterTask.java:24`, `QueryDefinition.java:23`, `QueryExecution.java:24`, `QuerySchedule.java:24`, `SourceJob.java:29`, `SourceTask.java:24`, `TenantTaskTypeKafkaRoute.java:29` |
| `(tenant_id = :tenantId or tenant_id is null)` | `KafkaConnectionProfile.java:26`, `SourceTaskType.java:26`, `StorageConnection.java:44`, `TaskForm.java:30` |

The second group is the shared-catalogue rule: a platform-owned row is published to every tenant
rather than hidden. Each of the four carries a comment saying so; `TenantTaskTypeKafkaRoute.java:27-28`
carries the converse ("the column is not nullable and there is no shared row to admit").

### Entities that declare **no** filter

Thirteen entities have no `@FilterDef`/`@Filter` at all:

| Entity | Has `tenant_id`? | How it is scoped instead |
|---|---|---|
| `Tenant` | n/a | Platform-owned; `TenantRepository` has no tenant predicate |
| `AppUser` | **yes** (`AppUser.java:56`) | `AppUserRepository.findByTenantIdAndStatusNotOrderByAppUserIdDesc` --- by hand |
| `LookupData` | **yes** (`LookupData.java:68`) | `SettingServiceImpl.isLookupOwnedByCaller` (line 595) --- by hand |
| `Notification` | **yes** (`Notification.java:35`) | By `recipient_user_id` only --- see section 8 |
| `TenantRequest` | no | Platform-admin surface |
| `Scheduler` | no | Inherits via `source_job` |
| `JobQueue` | no | Inherits via `source_job` |
| `JobAuditLogs` | no | Inherits via `job_queue` |
| `SourceTaskPayload` | no | Inherits via `source_task` |
| ~~`DynamicFormField`~~ | -- | Entity and table both dropped 2026-09-03 with the rest of the feature |
| ~~`DynamicFormSubmission`~~ | -- | Entity and table both dropped 2026-09-03 with the rest of the feature |
| `PdfHighlighterField` | no | Inherits via `pdf_highlighter_task` |
| `TaskFormField` | no | Inherits via `task_form` |

`AppUser`, `LookupData` and `Notification` are the notable ones: they carry a `tenant_id` column
that the filter mechanism does not act on.

### How the filter is turned on

`process/src/main/java/process/security/TenantFilterHelper.java:19-39`:

```java
if (tenantId == null || TenantContext.isPlatformAdmin()) {
    if (session.getEnabledFilter(FILTER_NAME) != null) {
        session.disableFilter(FILTER_NAME);
    }
    return;
}
session.enableFilter(FILTER_NAME).setParameter("tenantId", tenantId);
```

`TenantContext` (`process/src/main/java/process/security/TenantContext.java`) is a set of
`ThreadLocal`s populated per request; `isPlatformAdmin()` is a literal `"PLATFORM_ADMIN"` string
comparison on the role (line 38-40).

`enableIfNeeded` is called **72 times across 12 service classes**:
`AiAgentServiceImpl`, `ConnectionProfileServiceImpl`, `DocumentConverterServiceImpl`,
`DynamicFormServiceImpl`, `JobAssistantServiceImpl`, `PdfHighlighterTaskServiceImpl`,
`QueryDefinitionServiceImpl`, `QueryExecutionServiceImpl`, `QueryScheduleServiceImpl`,
`SourceJobServiceImpl`, `SourceTaskServiceImpl`, `StorageConnectionServiceImpl`.

**Three services that own filtered entities never call it**: `KafkaConnectionProfileServiceImpl`
(`KafkaConnectionProfile`), `SettingServiceImpl` (`SourceTaskType`, `LookupData`) and
`TaskFormServiceImpl` (`TaskForm`). Those instead write the predicate into the query by hand ---
e.g. `KafkaConnectionProfileRepository.java:35-38` (`and p.tenantId = :tenantId`),
`SourceTaskTypeRepository.java:42-46` (`where source_task_type.tenant_id = :tenantId or ... is null`),
`TaskFormRepository.java:27-30`. The declared `@Filter` on those three entities is therefore
inert on their own read paths; it only takes effect if some *other* service enabled the filter
earlier in the same Hibernate session.

### The filter does not apply to `findById`

This is the single most important caveat, and the codebase is explicit about it.
`process/src/main/java/process/security/TenantOwnership.java:10-23` states the rule:

> "The reading settled here is the one each entity already declares in its Hibernate tenant filter,
> so a row unreachable in a list query stays unreachable by id"

Hibernate's `@Filter` applies to queries and to collection loads, **not** to `Session.get()` /
`EntityManager.find()`, which is what Spring Data's `findById` compiles to. So every `findById`
that reaches a tenant-scoped entity must be followed by an explicit ownership check. The
compensating control is `TenantOwnership`:

```java
public static boolean isOwnedByCaller(Long ownerTenantId) {
    if (TenantContext.isPlatformAdmin()) { return true; }
    Long callerTenantId = TenantContext.getTenantId();
    return callerTenantId != null && Objects.equals(ownerTenantId, callerTenantId);
}

public static boolean isVisibleToCaller(Long ownerTenantId) {
    return ownerTenantId == null || isOwnedByCaller(ownerTenantId);
}
```

`isOwnedByCaller` deliberately answers **no** for a platform-owned (`null`) row and **no** for a
caller with no tenant --- both fail closed. `isVisibleToCaller` is the read-path variant for the
four shared catalogues: platform rows are published for reading, but write paths keep asking
`isOwnedByCaller`.

There are **87 references** to these two methods across the service layer, usually reached through a
thin per-service wrapper such as `SourceJobServiceImpl.java:104-107`:

```java
private boolean isOwnedByCaller(SourceJob sourceJob) {
    return sourceJob != null && TenantOwnership.isOwnedByCaller(sourceJob.getTenantId());
}
```

A worked example of the pattern is `SettingServiceImpl.java:318-320`: `findById` first, then
`isSourceTaskTypeOwnedByCaller` before anything is written.

Two frictions worth recording:

- `SettingServiceImpl.java:360-375` re-implements both predicates inline rather than delegating to
  `TenantOwnership`. The logic is currently identical, but it is a second copy of exactly the rule
  `TenantOwnership`'s header says was centralised because "the copies had begun to disagree".
- `TenantOwnership.java:19` lists the shared catalogues as "SourceTaskType, TaskForm and
  KafkaConnectionProfile" --- `StorageConnection` also uses the `or tenant_id is null` predicate
  (`StorageConnection.java:44`) and is missing from that list. Its own comment (lines 38-43)
  explains the case, so this is documentation drift, not a behaviour gap.

---

## 6. Encrypted columns

`process/src/main/java/process/util/EncryptionUtil.java` is the only cipher in the codebase:
AES/GCM/NoPadding, 128-bit tag, 12-byte random IV prepended to the ciphertext, the whole thing
Base64-encoded (lines 20-41). The key is a Base64 256-bit value from `lookup.encryption.key`
(`application-dev.properties:10`), and `secretKey()` throws outright when it is unset (lines 59-65).

### Columns that hold ciphertext

| Column | Encrypted at | Decrypted at |
|---|---|---|
| `lookup_data.lookup_value` **(only when `is_encrypted = true`)** | `SettingServiceImpl.java:460,503` | `LookupDataCacheService.java:85` |
| `ai_agent.api_key` | `AiAgentServiceImpl.java:559` | `AiAgentServiceImpl.java:246` |
| `database_connection_profile.password_encrypted` | `ConnectionProfileServiceImpl.java:195,268` | `StorageClientFactory`/query engine paths |
| `query_definition.query_text` | `QueryDefinitionServiceImpl.java:110,148` | `QueryDefinitionServiceImpl.java:302,361`; `QueryExecutionRunner.java:72` |
| `kafka_connection_profile.sasl_password` | `KafkaConnectionProfileServiceImpl.java:636` | `KafkaTemplateProvider.java:146` |
| `kafka_connection_profile.ssl_truststore_password_enc` | via `KafkaSecretServiceImpl.java:128` | `KafkaTemplateProvider.java:162` |
| `kafka_connection_profile.ssl_keystore_password_enc` | via `KafkaSecretServiceImpl.java:175` | `KafkaTemplateProvider.java:172` |
| `kafka_connection_profile.ssl_key_password_enc` | same store-generation path | `KafkaTemplateProvider.java:175` |
| `storage_connection.secret_key_enc` | `StorageConnectionServiceImpl.java:515,576`; `StorageConnectionBootstrap.java:170,276` | `StorageClientFactory.java:170` |
| `storage_connection.azure_connection_string_enc` | `StorageConnectionServiceImpl.java:518,580`; `StorageConnectionBootstrap.java:282` | `StorageClientFactory.java:170` |
| `storage_connection.password_enc` (FTP/FTPS) | `StorageConnectionServiceImpl.java:583` | `StorageClientFactory.java:170` |

Two observations:

- **`query_definition.query_text` is encrypted.** The saved SQL itself, not just a credential. That
  makes the column opaque to any `LIKE`/full-text search, and means a lost
  `LOOKUP_ENCRYPTION_KEY` costs every saved query, not just every stored password.
- **`kafka_connection_profile.sasl_password` holds ciphertext but has no `_enc` suffix**, unlike
  every other secret column including its three siblings on the same table
  (`KafkaConnectionProfile.java:83-84` vs `92-105`). The convention documented at
  `StorageConnection.java:19-20` --- "`*_enc` columns hold `EncryptionUtil` ciphertext, never
  plaintext" --- is broken by exactly this one column.

### Columns that hold plaintext, and are meant to

`app_user.password` is a **BCrypt hash**, not `EncryptionUtil` ciphertext --- it goes through
`PasswordEncoder` (`TenantSeedService.java:6`), and is `@JsonIgnore`d at `AppUser.java:66-68`.

Deliberately plaintext, sitting right next to their encrypted counterparts:
`database_connection_profile.username`/`host`/`port`/`database_name`,
`storage_connection.access_key`/`endpoint`/`username`/`bucket_name`,
`kafka_connection_profile.sasl_username`/`bootstrap_servers`/`ssl_*_location`,
`ai_agent.api_endpoint`/`model`/`instructions`.

Everything not listed in the ciphertext table above is plaintext --- including every
`source_task_payload.tag_value`, `source_task.task_payload`, `dynamic_form_submission.payload`,
`job_queue.job_status_message` and `job_audit_logs.log_detail`.

`lookup_data` is the one table where the same column is sometimes ciphertext and sometimes not:
`is_encrypted` (V8) is the discriminator, and `SettingServiceImpl.fillLookupDateDto` (around line
605) replaces an encrypted value with `MASKED_LOOKUP_VALUE` on the way out rather than decrypting it
for display.

---

## 7. Indexes and unique constraints that matter

### Unique constraints

| Constraint | Where | Note |
|---|---|---|
| `lookup_data.lookup_type` UNIQUE | `V1__creating_shedlock_schema.sql:16`, `LookupData.java:53-55` | **Global**, on a tenant-scoped table --- see section 8 |
| `storage_connection.alias` (`uq_storage_connection_alias`) | `StorageConnection.java:31-33` | **Global** --- the alias is how the rest of the app addresses a bucket (`findByAlias`) |
| `tenant_task_type_kafka_route (tenant_id, source_task_type_id)` (`uq_tenant_task_type`) | `TenantTaskTypeKafkaRoute.java:16-17` | One route per tenant per task type. Correctly tenant-qualified |
| `ux_task_form_pipeline_tenant` on `(pipeline_id, COALESCE(tenant_id, -1)) WHERE form_status <> 'Delete'` | `V19__task_form_builder.sql:45-47` | Partial + expression index. The `COALESCE` makes the platform row participate; the `WHERE` lets a soft-deleted form free its slot |
| `ux_tenant_request_open_email` on `lower(contact_email) WHERE status = 'Pending'` | `V21__tenant_request.sql:27-29` | Stops a double-click queueing the same ask twice, while still allowing a second request after a decision |
| `tenant.tenant_code`, `tenant.uuid` | `Tenant.java:48,54` | |
| `app_user.username`, `app_user.uuid` | `AppUser.java:53,63` | Username is global --- it is the login identity |
| `ai_agent.tool_uuid` | `AiAgent.java:96` | The unguessable handle exposing the agent as a callable tool |
| `dynamic_form.uuid`, `dynamic_form_submission.uuid` | `DynamicForm.java:77`, `DynamicFormSubmission.java:41` | Share handles |
| `job_audit_logs.external_id` | `JobAuditLogs.java:46` | Load-bearing: `JobAuditLogRepository.java:25-27` relies on it for `on conflict (external_id) do nothing` when syncing from OpenSearch |

The two partial/expression indexes (`ux_task_form_pipeline_tenant`, `ux_tenant_request_open_email`)
cannot be expressed as a JPA `@UniqueConstraint` --- they exist **only** because a changeset created
them, and would be silently absent on any database built from the entity mappings alone.

### Indexes

From `V18__foreign_key_indexes.sql` (referencing-side FK columns Postgres does not index for you):
`idx_scheduler_job_id`, `idx_source_job_task_detail_id`, `idx_source_task_type_id` (on
`source_task`), `idx_source_task_payload_task` (on `payload_id`), `idx_lookup_data_parent`,
`idx_lookup_data_tenant_id`, `idx_notification_tenant_id`, and
`idx_notification_recipient (recipient_user_id, date_created DESC)`.

From `V15__scheduler_recurrence_rules.sql:23`: `idx_scheduler_next_run_at` --- the dispatcher's poll
predicate (`SchedulerRepository.java:17-22`).

From entity `@Table(indexes = ...)`: a `tenant_id` index on every filtered entity
(`idx_source_job_tenant_id`, `idx_source_task_tenant_id`, `idx_stt_tenant_id`, `idx_kcp_tenant_id`,
`idx_ai_agent_tenant_id`, ~~`idx_dynamic_form_tenant_id`~~ (dropped with its table, 2026-09-03), `idx_query_*_tenant_id`,
`idx_pdf_highlighter_task_tenant_id`, `idx_document_converter_task_tenant_id`,
`idx_storage_connection_tenant_id`, `idx_db_connection_profile_tenant_id`,
`idx_app_user_tenant_id`), plus `idx_job_queue_job_id`, `idx_job_audit_logs_job_queue_id`,
`idx_source_job_assigned_user_id`, `idx_query_schedule_next_run_at`, `idx_query_execution_query_id`,
`idx_notification_recipient_read (recipient_user_id, is_read)` and the three `idx_ttkr_*`.

`ix_task_form_field_form` and `ix_task_form_tenant` come from `V19__task_form_builder.sql:49-50`;
`ix_tenant_request_status` from `V21__tenant_request.sql:31`.

Redundant `unique = true` on a primary key column appears on
`SourceTaskType.java:54`, `DocumentConverterTask.java:38`, `PdfHighlighterTask.java:39` and
`PdfHighlighterField.java:29` --- harmless, but it makes Hibernate create a second unique index
alongside the PK on a fresh build.

---

## 8. Risks

Ordered roughly by consequence.

### 1. A genuinely fresh stage or prod database cannot be built by this pipeline

`ddl-auto=validate` on stage and prod (`application-stage.properties:90`,
`application-prod.properties:92`) means Hibernate will not create tables there. Liquibase creates
only six (section 1). There is no baseline dump: `process/docker-compose.yml` mounts nothing into
`/docker-entrypoint-initdb.d` and no `.sql` seed file exists in the repo. So the 22 tables Hibernate
owns --- `tenant`, `app_user`, `source_job`, `source_task`, `scheduler`, `job_queue`,
`job_audit_logs`, and the rest --- have no creation path on stage or prod at all. Those
environments only work because their databases already exist and were originally grown by a
`ddl-auto=update` process.

### 2. Most changesets are unguarded against the table not existing yet

V8 and V11 wrap their statements in `DO $$ ... to_regclass(...) IS NOT NULL ...` precisely because
Liquibase runs before Hibernate creates the table. **V12, V13, V14, V15, V16, V17, V18 (both),
V20, V22 and V24 carry no such guard** and issue plain `ALTER TABLE` / `UPDATE` / `CREATE INDEX` /
`COMMENT ON` against Hibernate-owned tables. Against an empty database V12's first statement ---
`ALTER TABLE ai_agent ADD CONSTRAINT fk_ai_agent_tenant ...` --- has no `ai_agent` to alter. V15 is
worse than the others: `ALTER TABLE scheduler RENAME COLUMN recurrence TO interval_value` is not
idempotent even against a Hibernate-built `scheduler`, which the current entity creates with
`interval_value` already (`Scheduler.java:55-56`). The master changelog's own header (lines 4-8)
identifies exactly this failure mode as the reason V4--V7 are excluded; V12 onward reintroduced it.

### 3. A live code path rewrites the casing V16 had to repair

`SourceJobRepository.java:57-60`:

```java
@Query(value = "update source_job set job_status = UPPER(?2)\n" +
    "where task_detail_id in (select task_detail_id from source_task where source_task_type_id = ?1)",
    nativeQuery = true)
public int statusChangeSourceJobLinkWithSourceTaskTypeId(Long sourceTaskTypeId, String status);
```

`UPPER(?2)` turns `Active`/`Delete` into `ACTIVE`/`DELETE` --- exactly the corruption
`V16__fix_source_job_status_casing.sql` was written to undo, and which that file documents as
causing both silent exclusion from typed JPQL and `IllegalArgumentException: No enum constant` on a
full-entity fetch. It has two live callers: `SettingServiceImpl.java:329` (saving a task type with a
status) and `SettingServiceImpl.java:354` (deleting a task type). The sibling method
`statusChangeSourceJobWithSourceTaskId` (line 64) uses `?2` with no `UPPER`, so the two paths
disagree about the same column. Editing a task type's status today re-creates the V16 data bug for
every job linked to it.

### 4. `lookup_data.lookup_type` is globally unique on a tenant-scoped table

`V1__creating_shedlock_schema.sql:16` declares `lookup_type VARCHAR(255) UNIQUE`, and
`LookupData.java:53-55` repeats it. But `lookup_data` carries `tenant_id`
(`LookupData.java:68`), has a per-tenant ownership check
(`SettingServiceImpl.isLookupOwnedByCaller`, line 595), a per-tenant count
(`LookupDataRepository.countByTenantIdAndParent_LookupType`) and a per-tenant backfill
(`backfillBucketTenantId`). The constraint is not tenant-qualified, so **two tenants can never hold
a lookup of the same type** --- the second one to try gets a unique-violation. Compare
`uq_tenant_task_type`, which correctly includes `tenant_id`. `storage_connection.alias`
(`StorageConnection.java:32`) has the same shape, though there the global namespace looks
intentional since `findByAlias` resolves without a tenant.

### 5. `notification.tenant_id` is written, indexed, and never read

`NotificationCenterServiceImpl.java:68` sets it. Nothing reads it back:
`Notification.getTenantId()` has no caller outside the pojo, and every `NotificationRepository`
query filters on `recipient_user_id` alone. `V18__foreign_key_indexes.sql:24` created
`idx_notification_tenant_id` for it, so there is an index supporting no query, on a column that also
has no FK to `tenant`. Notification tenancy rests entirely on the recipient id.

### 6. FK coverage gaps left after the V12--V14 sweep

Columns that reference another table and still have no constraint:

| Column | Should reference | Why it was missed |
|---|---|---|
| `storage_connection.tenant_id` | `tenant` | Not in V12's list |
| `notification.tenant_id` | `tenant` | Not in V12's list |
| `notification.recipient_user_id` | `app_user` | Not in V12's list |
| `task_form.tenant_id`, `task_form.created_by`, `task_form.updated_by` | `tenant`, `app_user` | Table created in V19, after the sweep |
| `tenant_request.decided_by`, `.created_tenant_id`, `.created_user_id` | `app_user`, `tenant`, `app_user` | Table created in V21, after the sweep |
| `source_task_payload.payload_id` | `source_task.task_detail_id` | Not in V14's list, despite V18 indexing it |
| ~~`dynamic_form_field.dynamic_form_id`~~ | ~~`dynamic_form`~~ | Moot -- both the column and the table were dropped 2026-09-03 (`V26.0-drop-dynamic-forms`) |
| every `created_by`/`updated_by` added by V22 (10 tables) | `app_user` | V22 adds columns only; no FK changeset followed |

V22's audit columns are the largest block: ten tables gained an `app_user` reference with no
referential integrity, in a schema whose V12 rationale was that such columns "were plain Longs with
no FK, so a bad write (or a bug) could silently leave a dangling reference".

### 7. The declared tenant filter is inert on three services

`KafkaConnectionProfileServiceImpl`, `SettingServiceImpl` and `TaskFormServiceImpl` never call
`TenantFilterHelper.enableIfNeeded`, so the `@Filter` on `KafkaConnectionProfile`, `SourceTaskType`,
`LookupData` (which has none anyway) and `TaskForm` does nothing on their own read paths. Those
services hand-write the predicate instead, which currently agrees with the filter --- with one
documented divergence: `KafkaConnectionProfileRepository.findVisibleToTenant` (lines 35-38)
deliberately does **not** admit platform rows, while the entity filter
(`KafkaConnectionProfile.java:26`) does. The repository's comment explains the choice, but the two
declarations now say different things about the same table, and a future service that *does* enable
the filter would get the entity's answer rather than the repository's.

### 8. `document_converter_task.target_folder` is write-only

Set at `DocumentConverterServiceImpl.java:216`. `DocumentConverterTask.getTargetFolder()`
(`DocumentConverterTask.java:206-208`) has no caller anywhere in `src/main/java`. The value is
stored and never retrieved.

### 9. Smaller things

- **Duplicate V18 number.** `V18.0-foreign-key-indexes.yaml` and `V18.0-user-avatar.yaml` are
  unrelated changes sharing a version. Distinct changeset ids keep Liquibase happy; the numbering
  still misleads.
- **`spring.liquibase.contexts=init` selects nothing**, since no changeset declares a context. If a
  future changeset adds one, it will be the only one that has to opt in --- an easy trap.
- **`task_form` and `task_form_field` share `task_form_source_seq`** (`TaskForm.java:46`,
  `TaskFormField.java:25`). Functional, but it makes both tables' ids sparse and interleaved, and a
  future `setval` intended for one silently moves the other.
- **`spring.jpa.hibernate.naming-strategy` (`application-dev.properties:76`) is the Hibernate 4
  property name** and is not read by Spring Boot 2.x. It is inert; the default
  `SpringPhysicalNamingStrategy` happens to produce the same result. Worth removing rather than
  leaving as a false statement of intent.
- **`SettingServiceImpl.java:360-375` duplicates `TenantOwnership`.** Currently identical logic, in
  the one place the centralised class exists to prevent.
- **Redundant unique indexes on primary keys** (`SourceTaskType.java:54`,
  `DocumentConverterTask.java:38`, `PdfHighlighterTask.java:39`, `PdfHighlighterField.java:29`).
- **`AppUser` has a `tenant_id` and no `@Filter`**, so a `findById` on a user relies entirely on the
  caller remembering to check --- `AppUserServiceImpl` does call
  `TenantOwnership.isOwnedByCaller(user.getTenantId())`, but there is no structural backstop the way
  there is for `SourceJob` or `SourceTask`.

---

## 9. Unused tables (audited 2026-09-07)

Method: `docker ps` confirmed the running Postgres container is `postgres_db` (`postgres:15`,
`0.0.0.0:5433->5432/tcp`). `docker exec postgres_db psql -U nabeel.amd93 -d etl_job -c "\dt"`
worked with the credentials already used elsewhere in this project (no need to fall back to
`process/docker-compose.yml`'s `POSTGRES_USER`/`POSTGRES_PASSWORD` defaults). That query returned
**24 tables** --- exactly the 21 `@Entity`-backed application tables plus `shedlock`,
`databasechangelog` and `databasechangeloglock`. Every file in
`process/src/main/java/process/model/pojo/` except `AuditListener.java` and `Audited.java` (not
entities) maps to one of the 21, and no table exists without a matching entity --- so, unlike the
state audited before V25-V27, **there is no orphaned schema-only table left to find**: the four
prior migrations (`V25__drop_avatar_backup.sql`, `V26__drop_dynamic_forms.sql`,
`V27__drop_query_engine.sql`, `V28__drop_pipeline_ids_lookup.sql`, all under
`process/src/main/resources/db/changelog/changelog-sets/`) already removed everything that fit that
bar. `V28` did not drop a table --- it deleted the `PIPELINE_IDS` `lookup_data` rows
(`parent_lookup_id = 1015` and the row itself), which is why `lookup_data` still exists below.

Row counts, all queried in one statement:

```
docker exec postgres_db psql -U nabeel.amd93 -d etl_job -c "
select 'tenant' t, count(*) from tenant
union all select 'app_user', count(*) from app_user
union all select 'tenant_request', count(*) from tenant_request
union all select 'source_task', count(*) from source_task
union all select 'source_task_type', count(*) from source_task_type
union all select 'source_task_payload', count(*) from source_task_payload
union all select 'source_job', count(*) from source_job
union all select 'scheduler', count(*) from scheduler
union all select 'job_queue', count(*) from job_queue
union all select 'job_audit_logs', count(*) from job_audit_logs
union all select 'lookup_data', count(*) from lookup_data
union all select 'notification', count(*) from notification
union all select 'storage_connection', count(*) from storage_connection
union all select 'kafka_connection_profile', count(*) from kafka_connection_profile
union all select 'tenant_task_type_kafka_route', count(*) from tenant_task_type_kafka_route
union all select 'ai_agent', count(*) from ai_agent
union all select 'document_converter_task', count(*) from document_converter_task
union all select 'pdf_highlighter_task', count(*) from pdf_highlighter_task
union all select 'pdf_highlighter_field', count(*) from pdf_highlighter_field
union all select 'task_form', count(*) from task_form
union all select 'task_form_field', count(*) from task_form_field
union all select 'shedlock', count(*) from shedlock
union all select 'databasechangelog', count(*) from databasechangelog
union all select 'databasechangeloglock', count(*) from databasechangeloglock
order by 1;"
```
gave: `ai_agent=3, app_user=269, databasechangelog=25, databasechangeloglock=1,
document_converter_task=0, job_audit_logs=548, job_queue=138, kafka_connection_profile=21,
lookup_data=145, notification=138, pdf_highlighter_field=0, pdf_highlighter_task=0, scheduler=122,
shedlock=5, source_job=136, source_task=134, source_task_payload=486, source_task_type=7,
storage_connection=7, task_form=6, task_form_field=28, tenant=13, tenant_request=2,
tenant_task_type_kafka_route=0`.

### 9.1 Already removed --- not re-examined here

`avatar_backup_20260824` (V25), `dynamic_form`/`dynamic_form_field`/`dynamic_form_submission`
(V26), `database_connection_profile`/`query_definition`/`query_schedule`/`query_execution` (V27).
The `PIPELINE_IDS` lookup family (`lookup_data` rows, parent 1015 + children) was deleted by V28,
not dropped as a table --- `lookup_data` itself stays, see below.

### 9.2 Infrastructure tables --- not candidates, by design

| Table | Why it is excluded from consideration |
|---|---|
| `shedlock` | Scheduler mutex, not application data (`V17__table_descriptions.sql:81-82`, and section 1 above). 5 live rows are exactly the expected lock rows. |
| `databasechangelog` | Liquibase's own migration history (`V17__table_descriptions.sql:84-88`). 25 rows = 25 applied changesets. |
| `databasechangeloglock` | Liquibase's own migration mutex (same citation). 1 row is its steady state. |

### 9.3 Application tables examined --- all confirmed still used

Every one of the 21 tables below has a live `@Entity`, a repository or direct cascade path that is
actually called from a service, a controller endpoint reachable from that service, and at least one
frontend call site in `scheduler1/next/src` (or, for PDF Highlighter, in `scheduler1/src`, which
`.ai/README.md` treats as in-scope reference, not something already retired). None met the bar this
document's own precedent (§2, V25-V28) sets for "unused": empty *and* no code path *and* no
frontend reach. None is recommended for removal.

| Table | Entity | Repository / write path | Controller (endpoint owner) | Frontend call site (evidence) | Live rows | Verdict |
|---|---|---|---|---|---|---|
| `tenant` | `Tenant.java` | `TenantRepository.java` | `process/api/TenantRestApi.java:21` | `scheduler1/next/src/app/app.routes.ts` (tenant admin route) | 13 | Used --- core multi-tenancy |
| `app_user` | `AppUser.java` | `AppUserRepository.java` | `process/api/AppUserRestApi.java` | `scheduler1/next/src/app/core/auth/auth.service.ts` | 269 | Used --- auth/identity |
| `tenant_request` | `TenantRequest.java` | `TenantRequestRepository.java` | `process/api/TenantRequestRestApi.java` | `scheduler1/next/src/app/features/tenant-request/{request-workspace.ts,tenant-requests.ts,tenant-requests.html}`, `.../features/shell/shell.ts` | 2 | Used --- self-service onboarding (V21) |
| `source_task` | `SourceTask.java` | `SourceTaskRepository.java` | `process/api/SourceTaskRestApi.java` | `scheduler1/next/src` task screens (per §3 of this file) | 134 | Used --- ETL core |
| `source_task_type` | `SourceTaskType.java` | `SourceTaskTypeRepository.java` | `process/api/SettingRestApi.java:47-62` (`addSourceTaskType`/`updateSourceTaskType`) | `scheduler1/next/src/app/features/settings/task-types/{task-types.ts,task-type-dialog.ts}` | 7 | Used --- task-type catalogue |
| `source_task_payload` | `SourceTaskPayload.java` | No dedicated repository --- written/read only via `SourceTask`'s cascaded `@OneToMany`, in `process/model/service/impl/SourceTaskServiceImpl.java:175-181,226-232,456-461,620-623` | Same as `source_task` (payload travels with the task) | Same as `source_task` | 486 | Used --- task's XML tag tree |
| `source_job` | `SourceJob.java` | `SourceJobRepository.java` | `process/api/SourceJobRestApi.java` | `scheduler1/next/src/app/features/jobs/*` | 136 | Used --- ETL core |
| `scheduler` | `Scheduler.java` | `SchedulerRepository.java`, called from `DashboardServiceImpl`, `SourceJobServiceImpl`, `TransactionServiceImpl`, `SourceJobBulkServiceImpl`, `JobAssistantServiceImpl` (all in `process/model/service/impl/`) | reached through `SourceJobRestApi` → `SourceJobService`/`SourceJobBulkService` | `scheduler1/next/src/app/features/jobs/*` (recurrence UI) | 122 | Used --- job timetable |
| `job_queue` | `JobQueue.java` | `JobQueueRepository.java`, called from `DashboardServiceImpl`, `SourceJobServiceImpl`, `TransactionServiceImpl`, `JobAssistantServiceImpl`, `MessageQServiceImpl` | `SourceJobRestApi` / dispatcher path | `scheduler1/next/src/app/features/jobs/*` | 138 | Used --- one row per execution |
| `job_audit_logs` | `JobAuditLogs.java` | `JobAuditLogRepository.java` | job-log read path off `SourceJobRestApi` | job log viewer under `scheduler1/next/src/app/features/jobs/*` | 548 | Used --- non-empty is expected; this file's §3 already documents it as normally-near-empty by design (OpenSearch is primary, this is the overflow/backfill store), and 548 rows shows the backfill path is active, not dead |
| `lookup_data` | `LookupData.java` | `LookupDataRepository.java` | `SettingRestApi` (settings) | `scheduler1/next/src/app/features/settings/*` | 145 | Used --- shared key/value config; `PIPELINE_IDS` rows are gone (V28) but every other lookup type is live |
| `notification` | `Notification.java` | `NotificationRepository.java` | `process/api/NotificationRestApi.java` | `scheduler1/next/src/app/features/shell/{notification-bell.ts,shell.ts}`, `.../dashboard/dashboard.ts`, `.../profile/profile.ts`, `.../jobs/jobs.ts` | 138 | Used --- in-app notification centre |
| `storage_connection` | `StorageConnection.java` | `StorageConnectionRepository.java` | `process/api/StorageConnectionRestApi.java` | `scheduler1/next/src/app/features/admin/storage/{storage-connections.html,connection-dialog.ts}` | 7 | Used --- Object Browser / storage backends |
| `kafka_connection_profile` | `KafkaConnectionProfile.java` | `KafkaConnectionProfileRepository.java` | `process/api/KafkaConnectionProfileRestApi.java` | `scheduler1/next/src/app/features/settings/kafka/{kafka-connections.html,kafka-dialog.ts,kafka-tls-section.ts}` | 21 | Used --- Kafka dynamic config (V11) |
| `tenant_task_type_kafka_route` | `TenantTaskTypeKafkaRoute.java` | `TenantTaskTypeKafkaRouteRepository.java`, called from `process/config/KafkaConnectionResolver.java:22-26` and `process/model/service/impl/SettingServiceImpl.java:381-417` (`fetchKafkaRoute`/`setKafkaRoute`/`deleteKafkaRoute`) | `SettingRestApi.java:80-101` (`/fetchKafkaRoute` GET, `/setKafkaRoute` PUT, `/deleteKafkaRoute` DELETE) | `scheduler1/next/src/app/features/settings/task-types/{task-types.ts,task-type-dialog.ts}` (calls all three endpoints), plus legacy `scheduler1/src/app/_services/kafka-connection-profile.service.ts` | **0** | Used, but currently no tenant has set an override --- a per-tenant *optional* row, not a dead table. Do not drop: the write path is live and reachable, 0 rows just means the default routing has sufficed so far |
| `ai_agent` | `AiAgent.java` | `AiAgentRepository.java` | `process/api/AiAgentRestApi.java` | `scheduler1/next/src/app/features/ai/agents/{agents.ts,agent-dialog.ts}`, `.../objects/chat/file-chat.ts` | 3 | Used --- AI Agents feature (V9) |
| `document_converter_task` | `DocumentConverterTask.java` | `DocumentConverterTaskRepository.java` | `process/api/DocumentConverterRestApi.java` | `scheduler1/next/src/app/features/tools/converter/{converter.ts,converter.html}` (also legacy `scheduler1/src/app/_component/document-converter/*`) | **0** | Used, but currently empty --- this file's §8 already notes `target_folder` is write-only on this entity, and the whole feature simply has no conversions recorded in this environment yet. Both frontends can reach it; not a removal candidate |
| ~~`pdf_highlighter_task`~~ | ~~`PdfHighlighterTask.java`~~ | ~~`PdfHighlighterTaskRepository.java`~~ | ~~`process/api/PdfHighlighterTaskRestApi.java` (9 endpoints, per `.ai/discovery/features.md` §2.1)~~ | ~~**Only** `scheduler1/src/app/_component/pdf-highlighter/*`~~ | 0 | **Removed 2026-09-07** (product owner's explicit call, made knowing this row's own "do not drop" verdict) -- table, entity, repository, controller, and the legacy screen all deleted; `process/.../db/changelog/yaml/V29.0-drop-pdf-highlighter.yaml` is the down-migration. See `.ai/synthesis/pdf-highlighter.md`'s decision banner for the full reasoning. |
| ~~`pdf_highlighter_field`~~ | ~~`PdfHighlighterField.java`~~ | ~~`PdfHighlighterFieldRepository.java`~~ | ~~same `PdfHighlighterTaskRestApi`~~ | ~~same as `pdf_highlighter_task`~~ | 0 | **Removed 2026-09-07**, same change as `pdf_highlighter_task` above. |
| `task_form` | `TaskForm.java` | `TaskFormRepository.java` | `process/api/TaskFormRestApi.java` | `scheduler1/next/src/app/features/settings/forms/{task-forms.ts,task-form-dialog.ts}`, `.../tasks/edit/task-edit.ts` | 6 | Used --- Task Form builder (renamed user-facingly to "Pipeline Forms" 2026-09-07), and per `V28`'s own description now the sole source of truth for pipeline definitions |
| `task_form_field` | `TaskFormField.java` | `TaskFormRepository.java` (child of `task_form`, `ON DELETE CASCADE` per `V19__task_form_builder.sql:29`) | same as `task_form` | same as `task_form` | 28 | Used --- one row per form field |

### 9.4 Conclusion

**Update, 2026-09-07: `pdf_highlighter_task`/`pdf_highlighter_field` have since been removed** --
see the strikethrough rows above and `.ai/synthesis/pdf-highlighter.md`'s decision banner. At the
time this section was written, the finding below was accurate; it's kept as the record of that
analysis, not a live statement of the schema.
>
> No table in the live schema is safe to remove today. All 21 application tables have a live
> entity, a called repository/service path, a controller endpoint, and a reachable frontend screen
> (19 of them in `scheduler1/next`; `pdf_highlighter_task`/`pdf_highlighter_field` only in the legacy
> `scheduler1/src`, which is still in-scope per `.ai/README.md`). Four tables are currently empty
> (`document_converter_task`, `pdf_highlighter_task`, `pdf_highlighter_field`,
> `tenant_task_type_kafka_route`) but each has a live, callable write path --- they read as
> lightly-used, not unused. The one table worth watching, not dropping, is the
> `pdf_highlighter_*` pair: it is reachable only through the legacy app, so it becomes a genuine
> removal candidate the day `scheduler1/src` is retired without that feature having been carried
> into `scheduler1/next` first (tracked already at `.ai/discovery/features.md` §2.1).

Of the 21, **19 remain** after the removal above.
