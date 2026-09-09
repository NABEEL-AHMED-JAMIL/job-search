# Discovery — Risk register

Everything the five Discovery inventories flagged, consolidated and ranked. **64 findings**, numbered 1–64. Each was recorded with a file path by the agent that found it; the ones marked ✔ **verified** below were additionally re-checked by hand.

This is a register, not a work plan. Discovery does not change code — an entry appears here because it was found, not because anyone is acting on it. Items become work when a feature's [synthesis](../synthesis/) document picks them up, except the P0 block, which should not wait for a feature. Where a later phase has since closed one, the entry stays in place, keeps its number, and says what closed it and when. The history is the point: a register that held only what is still broken could not be used to check whether a symptom has been seen before.

> **Re-verified 2026-09-08 against the working tree.** All fifteen P0 and P1 items were read
> against current source again, one at a time. **None is resolved.** `.env.bak.1787579140` is still
> on disk and still tracked (#1); the compose literals have only moved line, to
> `docker-compose.yml:156-157` (`MAIL_USERNAME`/`MAIL_PASSWORD`), `:162` (`LOOKUP_ENCRYPTION_KEY`)
> and `:166` (`JWT_SECRET_KEY`) (#2); `ddl-auto=validate` still stands on stage and prod (#3);
> `PLATFORM_ADMIN_BOOTSTRAP_PASSWORD` is referenced by all three property files and set in none of
> them, nor in `.env` or `.env.example` (#4); `process.scheduling.enabled` still appears only in
> `src/test/resources/application-e2e.properties:22` and `ProcessConfig:20` still carries an
> unconditional `@EnableScheduling` (#5); every controller still carries `@CrossOrigin(origins = "*")`
> and there is still no `CorsConfigurationSource` anywhere in `src/main` (#6); Swagger is still
> `permitAll` at `SecurityConfig:52-53` with a Docket that still selects
> `RequestHandlerSelectors.any()` (#7); `JwtAuthenticationFilter` still builds the authentication from
> the claims alone, with no per-request user read and no denylist (#8); `MessageQRestApi` still has no
> method-level `@PreAuthorize` and `SourceJobRestApi` is still class-level `TENANT_USER` (#9);
> `AudioTranscriptRestApi:40,50` still return `ex.getMessage()` (#10); the `StorageConnection`
> `@Filter` still declares the shared-catalogue predicate (#11); `enable_lazy_load_no_trans=true` on
> all three profiles (#12); `KafkaConnectionProfileServiceImpl`, `SettingServiceImpl` and
> `TaskFormServiceImpl` still never call `TenantFilterHelper` — all three gained tenant-isolation
> tests this session, which pins the hand-written predicates but does not activate the filter (#13);
> `AppUser` still declares no `@Filter` (#14). #15 still matches the code.
>
> **Two counts inside the findings have drifted, in both cases because features were deleted rather
> than because anything was secured.** #6 says 27 controllers; there are now 24 `@RestController`
> classes and all 24 carry the wildcard — three of them (`SourceTaskRestApi`, `SourceJobRestApi`,
> `StorageBrowserRestApi`) spell it with an added `exposedHeaders`, which is why a plain grep for the
> bare annotation finds only 21. #7 says 181 endpoints; the RestApi controllers now declare 155 mapped
> methods. The Query Engine, Search Engine, dynamic forms and PDF highlighter removals (V26–V29)
> account for the difference.
>
> **Twelve findings were added on this date, numbered 48–59**, from a session of fixes across
> Reports, Queue, notifications, mail, the audit-log cron and the frontend bootstrap. Eleven were
> closed in that same session and #52 was closed only in part; all twelve are recorded rather than
> omitted, per the rule above. The header also said "46 findings" while the list already ran to 47 —
> #47 was appended on 2026-09-07 without the count being changed. It said 59 at the end of that
> batch, and says 64 after the one below.
>
> **Five more were added later the same date, numbered 60–64**, from Analytics Studio phase one —
> a new module that reads a file where it lies in object storage using an embedded DuckDB, shipped
> on 2026-09-08 — which is what takes the header from 59 to **64**. **None of them is closed, and
> that work closed none of the existing entries either**; the entries below are the residue of a
> build that went in deliberately, not a list of mistakes. Two are P1, one P2 and two P5. #61 is unlike anything else in this register in that it
> describes a risk that does not exist yet: phase one runs no user-written SQL, and the entry is
> here so the lock-down that phase three will depend on is on the record before that phase, rather
> than being reconstructed after it.
>
> **One count in the note above has drifted again, upward this time.** #6 says 27 controllers and
> this note said 24; there are now **25** `@RestController` classes, and all 25 still carry
> `@CrossOrigin(origins = "*")` — `AnalyticsRestApi:21` is the twenty-fifth, and it took the
> wildcard because every controller beside it has one. (`GlobalExceptionHandler` matches a grep for
> the string but is `@RestControllerAdvice`, so it is not one of the 25.) The endpoint count in #7
> likewise grows by the two `/analytics.json` methods. Neither is a new finding; both are #6 and #7
> getting slightly larger.
>
> **What phase one deliberately did not build is scope, not findings, and has no entry here:** no
> user-written SQL, no profiling, no charts, no dashboards, no saved queries, no benchmarks, no
> caching, no database table — a dataset selection lives in the component and is not persisted —
> and no frontend unit test for the Studio component, which is why the frontend suite is unchanged
> at 580. The backend suite went from 587 to 607. Those gaps are recorded in the feature's own
> documents; they are listed here only so a reader does not go looking for the numbers that would
> cover them.
>
> The previous pass is kept below.
>
> **Re-verified 2026-09-02 against the working tree.** All fifteen P0 and P1 items were re-read
> against current source, one at a time. **None is resolved** — every one still reproduces as
> written, and the register is accurate as of that date. Specifically: `.env.bak.1787579140` is
> still tracked (#1); the compose literals are still at `docker-compose.yml:147-157` (#2);
> `ddl-auto=validate` still stands on stage and prod (#3); `PLATFORM_ADMIN_BOOTSTRAP_PASSWORD`
> appears in neither `.env` nor `.env.example` (#4); `process.scheduling.enabled` is still read
> nowhere and `ProcessConfig:20` still carries an unconditional `@EnableScheduling`, with no
> `@ConditionalOnProperty` anywhere in `src/main` (#5); 27 controllers still carry
> `@CrossOrigin(origins = "*")` with no `CorsConfigurationSource` (#6); Swagger is still
> `permitAll` (#7); `JwtAuthenticationFilter` still reads role and tenant from claims only (#8);
> `MessageQRestApi` still has no method-level `@PreAuthorize`, so all four methods remain at the
> class-level `TENANT_USER` (#9); `AudioTranscriptRestApi` still returns `ex.getMessage()` (#10);
> the `StorageConnection` `@Filter` still declares the shared-catalogue predicate (#11);
> `enable_lazy_load_no_trans=true` on all three profiles (#12); none of the three services calls
> `TenantFilterHelper` (#13); `AppUser` still declares no `@Filter` (#14). #15 was never a defect
> and its description still matches the code.
>
> Unrelated fixes *have* landed in the working tree since this register was written — most
> notably `StorageConnectionServiceImpl.isOwnedByCaller`, which used
> `Objects.equals(tenantId, callerTenantId)` and therefore made a tenant-less caller the owner of
> every platform-owned connection; it now delegates to `TenantOwnership`. That defect was never
> numbered here, so nothing above is retired by it.

---

## P0 — Act on these regardless of the feature plan

### 1. Live credentials are committed and pushed ✔ verified

`process/.env.bak.1787579140` is **tracked in git and present on `origin/new-screen-2026`** at `github.com/NABEEL-AHMED-JAMIL/process.git`. It contains the real values of ten keys, including:

- `SPRING_DATASOURCE_PASSWORD`
- `MAIL_PASSWORD`
- `WORKER_CALLBACK_TOKEN`

`process/.gitignore:35-38` covers `.env` and `.env.local`, and its own comment records that *"the datasource and mail passwords were committed here before this line existed."* The same mistake then happened again through a filename the pattern does not match — `.env.bak.*`.

`job-search/env` (no leading dot) is likewise tracked and holds MongoDB credentials. `job-search/.gitignore:29-33` documents this and prevents the next one, while explicitly noting it does not untrack the file already indexed.

**This has not been touched.** Untracking is easy; the exposure is not undone by it, because the values remain in the pushed history. The full remedy is a decision for the repository owner:

1. **Rotate every value in both files.** Assume they are compromised — this is the only step that actually closes it.
2. `git rm --cached process/.env.bak.1787579140` and `git rm --cached env` in `job-search`, then commit.
3. Add `.env.bak.*` and `.env.*.bak` to `process/.gitignore`.
4. Optionally purge the history (`git filter-repo`) — a rewrite that requires a force-push and coordination with anyone else holding a clone.

### 2. Secrets have literal fallbacks in a tracked compose file

`process/docker-compose.yml` carries literal defaults for `LOOKUP_ENCRYPTION_KEY` (L153), `JWT_SECRET_KEY` (L157) and `MAIL_USERNAME`/`MAIL_PASSWORD` (L147-148). A stack started without a `.env` therefore runs on **a publicly known signing key and encryption key** — anyone with the repo can mint a valid token.

`ApplicationPropertiesDeclarationTest` enforces a no-literal-credentials rule, but only across `application-*.properties`. It never sees the compose file.

### 3. A fresh stage or prod database cannot be built

`ddl-auto=validate` on stage and prod (`application-stage.properties:90`, `application-prod.properties:92`) means Hibernate creates nothing. Liquibase creates only **6** tables. The other 22 — `tenant`, `app_user`, `source_job`, `source_task`, `scheduler`, `job_queue`, `job_audit_logs` and the rest — have **no creation path** on those environments, and there is no baseline dump or `docker-entrypoint-initdb.d` seed anywhere in the repository.

Development works only because `dev` uses `ddl-auto=update`. The schema is effectively defined by the JPA entities, with Liquibase patching around them.

Compounding it: most changesets are unguarded. V8 and V11 wrap statements in a `to_regclass` guard precisely because Liquibase runs before Hibernate; V12–V18, V20, V22 and V24 issue plain `ALTER TABLE` / `CREATE INDEX` against Hibernate-owned tables without one. **V15** is the sharpest — `ALTER TABLE scheduler RENAME COLUMN recurrence TO interval_value` is not idempotent, and the current entity already creates `interval_value`.

### 4. First run has no account to sign in as

`PLATFORM_ADMIN_BOOTSTRAP_PASSWORD` is set **nowhere** in the workspace — not in compose, not in `.env.example`. `TenantSeedService.java:108-110` logs an error and seeds no platform admin, so a first run against an empty database comes up with nothing to log in with.

### 5. The E2E kill-switch does nothing

`application-e2e.properties:22` sets `process.scheduling.enabled=false`, with a comment saying the crons would otherwise dispatch real jobs while tests assert on rows. **That property is read nowhere in the codebase**, and `ProcessConfig.java:20` carries an unconditional `@EnableScheduling`. The E2E suite runs against the real development database with the crons live.

---

## P1 — Security

| # | Finding | Where |
|---|---|---|
| 6 | **CORS is open to every origin.** All 27 controllers carry `@CrossOrigin(origins = "*")`, `AuthRestApi` included. `SecurityConfig` enables `.cors()` but registers no `CorsConfigurationSource`, and `WebConfig` is an empty `WebMvcConfigurer` — so the annotation is the entire policy | all controllers |
| 7 | **Swagger is `permitAll` in every profile**, and the Docket selects every handler, publishing the full **181-endpoint** surface unauthenticated | `SecurityConfig.java:53-54`, `SwaggerConfig.java:28-30` |
| 8 | **A JWT outlives a status change.** Role and tenant come from the token claims with no per-request user read. Deactivating a user, suspending a tenant or changing a role takes effect only when the token expires (~30 min). There is no revocation or denylist anywhere | `JwtAuthenticationFilter.java:40-47` |
| 9 | **Any signed-in user can rewrite run state.** `failJobLogs`, `interruptJobLogs` and `changeJobStatus` sit under the class-level `TENANT_USER`. `SourceJobRestApi` is the same shape — create, update, delete, run and skip are all `TENANT_USER` | `MessageQRestApi.java:21,43,54,65` |
| 10 | **Raw exception messages returned to callers** with HTTP 400 — the opposite of the policy `KafkaSecretRestApi:50-51` states for itself | `AudioTranscriptRestApi:40,50` |
| 11 | **A filter and its guard contradict each other.** `StorageConnection` declares the shared-catalogue predicate `(tenant_id = :tenantId or tenant_id is null)`, publishing platform connections to every tenant, while `StorageBrowserServiceImpl.collectBuckets` deliberately refuses them. The service is narrower so the outcome is safe today — but only one statement of the rule is tested | `StorageConnection.java:44` vs `StorageBrowserServiceImpl:100-104` |
| 12 | **`enable_lazy_load_no_trans=true`.** Lazy loads outside a transaction open their own session; since `tenantFilter` is enabled per `EntityManager` by explicit call, a lazy load on a fresh session may not carry it. *Not verified* whether any current path escapes this way — worth a deliberate test | `application-dev.properties:80` |
| 13 | **The tenant filter is inert on three services.** `KafkaConnectionProfileServiceImpl`, `SettingServiceImpl` and `TaskFormServiceImpl` never call `TenantFilterHelper.enableIfNeeded`, so the `@Filter` on their entities does nothing on those read paths — each hand-writes the predicate instead, and one already diverges | — |
| 14 | **`findById` is not filtered**, mitigated only by **87 hand-placed** ownership checks. `AppUser` is the sharpest case: it carries `tenant_id` but declares no `@Filter` at all, so the check is the only control | `TenantOwnership.java:10-23` |
| 15 | **`dynamicQueryResponse` runs supplied SQL as given.** Correctly `PLATFORM_ADMIN` at both annotation and service body, but it is the highest-value endpoint in the API to anyone who obtains such a token | `QueryService.java:58` |
| 48 | **Every tenant's job notifications went to one personal mailbox.** `EMAIL_RECEIVER` was a single `lookup_data` row with `tenant_id` NULL, seeded by `V2__insert_lookup_setting.sql:21` with a personal address, and `sendSourceJobEmail` addressed every Skip/Completed/Failed mail to it — so one person received every workspace's job names and failure messages, on a platform whose own tenants page promises that jobs, buckets, tasks and users never cross between them. The job's own assignee was told nothing, which is the entire purpose of a job notification. **Fixed 2026-09-08** — the recipient is resolved once, from `source_job.assigned_user_id` → `app_user.username`, so the dispatcher, the queue consumer and the worker callback all get the same answer; a job with no assignee sends nothing and logs a warning rather than falling back to an address nobody asked for. The row was removed by a new changeset with a rollback, `V30.0-drop-email-receiver`, rather than by editing the already-applied V2 seed | `EmailMessagesFactory.java:65-99`, `V30__drop_email_receiver.sql` |
| 49 | **A platform admin editing a task was served another tenant's pipeline form, and saving overwrote the task's payload with it.** The editor asks `formForPipeline` for the form belonging to a pipeline; a platform admin sees every tenant's rows, so with no tenant to narrow by it received whichever tenant's form for that pipeline had the lower id, and the save wrote that form's fields into this task's tags and payload. The guard existed on both sides already — the one line that feeds it did not, so it could never fire. **Fixed 2026-09-08** — `fetchSourceTaskWithSourceTaskId` sets `tenantId` on the DTO and the editor passes it back as a request parameter | `SourceTaskServiceImpl.java:471-476` vs `task-edit.ts:169,236` |
| 60 | **A dataset read leaves no durable record, and a refused one leaves nothing at all.** Nothing in `process/analytics` or `AnalyticsRestApi` writes an audit row, publishes a Kafka event or raises a notification — the spec asked for the first two and neither is built. The only trace a successful read leaves is one `logger.debug` line naming the dataset and the tenant; it does reach the log (`logback.xml:24` puts the `process` logger at `debug` on every profile, there being no `<springProfile>` blocks) but it lands in a rolling file kept 60 days, is not queryable, and is written only after the read has already succeeded. `DatasetResolver` declares no logger at all, so a cross-tenant refusal, a `..` and a rejected path are invisible — the events on this path most worth a record produce none. Set against what the platform does elsewhere: a pipeline run gets a durable, queryable line in `job_audit_logs`, synced from OpenSearch by `AuditLogSyncCron`, while a request that returns a customer's own rows out of their bucket to a browser gets a debug string. The gap widens rather than closes in phase three, when the thing worth recording stops being "which file" and becomes "which query" | `AnalyticsQueryService.java:170`, `DatasetResolver.java` (no logger), `logback.xml:9-27` |
| 61 | **The DuckDB lock-down is not load-bearing yet, and phase three is when it becomes so.** Phase one accepts no SQL from anyone: every statement is assembled in `AnalyticsQueryService` from a scan expression a `DatasetRef` produced, and no endpoint takes a query string. The session lock-down and the governor were nevertheless built and tested first — `DuckDbSessionFactory.open()` sets the limits, attaches credentials as a `SECRET`, disables `LocalFileSystem` and sets `lock_configuration=true` **last**, and `DuckDbLockdownTest` asserts against a real engine (7 tests, including a positive control) that a session cannot read a local file, write one, raise its own memory ceiling or put the filesystem back. That is the right order and it is why this entry is a *note* rather than a defect. But that ordering and those settings today defend a surface no caller can reach; the moment SQL Studio lands they are the whole of what stands between a signed-in `TENANT_USER` and an engine that can read local files, open sockets and install extensions as the backend process. Written down now so the review at that point begins from "these are the control" instead of discovering it. Three things to re-check then, all of them properties this build has and a later one could quietly lose: that `lock_configuration=true` is still the last statement `open()` executes, that no second code path anywhere opens a DuckDB connection outside this factory, and that the semaphore and `setQueryTimeout` bound a statement a *user* wrote and not only ones the application built | `DuckDbSessionFactory.java:76-98,190-193`, `AnalyticsQueryService.java:21-37,150-179` |

---

## P2 — Correctness

| # | Finding | Where |
|---|---|---|
| 16 | **A live code path re-creates the corruption a migration was written to repair.** `update source_job set job_status = UPPER(?2)` turns `Active`/`Delete` into `ACTIVE`/`DELETE` — exactly what `V16__fix_source_job_status_casing.sql` documents as causing silent exclusion from typed JPQL and `IllegalArgumentException: No enum constant`. Two live callers. The sibling method uses `?2` with no `UPPER`, so the two paths disagree about the same column | `SourceJobRepository.java:57-60`; `SettingServiceImpl.java:329,354` |
| 17 | **Two tenants can never hold a lookup of the same type.** `lookup_data.lookup_type` is globally `UNIQUE` on a table that carries `tenant_id`, has a per-tenant ownership check, a per-tenant count and a per-tenant backfill. The second tenant gets a unique violation. Compare `uq_tenant_task_type`, which correctly includes `tenant_id` | `V1__…:16`, `LookupData.java:53-55` |
| 18 | **The public form-fill page cannot submit.** `fetchFormByUuid` is `permitAll` while `submitForm` still requires `TENANT_USER`, so an anonymous visitor can read a shared form and not answer it. The page warns up front, but the feature is half-delivered until the server changes | `features/forms/form-fill.ts:9-19` |
| 19 | **The websocket event union and its only handler disagree.** `job.log` is declared and never consumed; `job.updated` is consumed and never declared. A trailing `| string` stops the compiler flagging either | `core/socket/job-events.service.ts:9` vs `features/jobs/jobs.ts:285-307` |
| 20 | **Two endpoints return their payload in `message` rather than `data`,** and each caller must know: `xmlCreateChecker` is read as `(response as any).message ?? response.data`, and a new job's id is recovered by regexing `/jobId (\d+)/` out of `created.message`. Both break on any change to the server's wording | `task-edit.ts`, `jobs.ts` |
| 21 | **FK coverage gaps** left after the V12–V14 sweep, largest block being every `created_by`/`updated_by` added by V22 across 10 tables — an `app_user` reference with no referential integrity, which is precisely the condition V12's own rationale describes | — |
| 22 | **Two partial unique indexes cannot be expressed in JPA** (`ux_task_form_pipeline_tenant`, `ux_tenant_request_open_email`). They exist only because a changeset created them, so a database built from the entity mappings alone silently lacks both guarantees | — |
| 23 | **The same byte count is formatted two ways on one screen.** `objects.ts:151` binds the shared helper while `objects.ts:478` declares a divergent `formatBytes` used by the header total and the Size column — exactly the drift `shared/ui/format-size.ts` was extracted to end | `features/objects/` |
| 50 | **A cron's watermark could never advance past a purged run, so its scan window grew without bound.** OpenSearch keeps audit lines long after the run they describe has left `job_queue`, and `AuditLogSyncCron` handed every hit to an insert guarded by `fk_job_audit_logs_job_queue`: **262 of 477 hits** in a measured run were refused, a stack trace each, while the run still logged itself a success. Worse, any failure set `hadParseFailure`, which pinned the bookmark at its previous value — so the next scan re-read the same dead rows, failed on them again and pinned it again, and a window whose head was nothing but purged runs would never move at all. **Fixed 2026-09-08** — the batch's `job_queue` ids are checked once up front (one query however many hits came back), orphans are skipped rather than inserted, a skipped hit still carries the watermark forward because its run is not coming back, and the whole batch produces one `warn` line naming a sample of the missing ids. Verified after deploy: `scanned=485 upserted=8 skipped=262`, zero FK violations. The per-hit `catch` is deliberately kept — the live check is a snapshot, not a lock | `AuditLogSyncCron.java:70,83,99,114,142` |
| 51 | **A screen that asked for every row was given ten.** `PagingUtil.ApplyPagingAndSorting` defaults an absent `limit` to `10`, and several screens post to `listSourceTask` with no paging at all, meaning "all of them". The Tasks screen therefore listed 10 of 21 tasks, and the job editor's task dropdown offered 10 — so a job could not be attached to the eleventh task at all, with nothing on screen to say why. **Fixed 2026-09-08** — both call sites pass `LIST_LIMIT`, a shared ceiling of 1000, and the Tasks screen warns when a response comes back at exactly that size instead of quietly showing a partial list. Verified: the screen reads "21 of 21". The server-side default is unchanged and still catches the next caller that forgets | `PagingUtil.java:19`; `core/api/list-limit.ts`, `tasks.ts:251`, `job-edit.ts:95` |
| 52 | **The run duration every screen reports is queue wait, not execution.** `job_queue.start_time` is stamped at ENQUEUE, not at pickup, so `end_time - start_time` is dispatcher wait plus execution with no way to separate them — and on this deployment the wait is **99.4%** of it: 41.25s of a 41.48s average, for tasks that run in 0.23s, because the dispatcher polls once a minute. Every reader of that number is being invited to optimise a transform that was never slow. **Partly closed 2026-09-08** — `runReportRows` left-joins the `Job started` audit marker to emit `exec_seconds` (`-1` where the marker is absent, so a run without one is excluded rather than counted as instant), and Reports gained three Execution measures beside the existing ones. The stamping itself is unchanged, so Queue, Job History and Dashboard still show the combined figure and still call it duration | `QueryService.java:265-296` |
| 53 | **A screen's charts described one population and its table another.** On Queue the outcome donut, the failure rate and the counts were computed from the unfiltered fetch — the donut from a server statistic that obeyed no filter at all — while the table obeyed the search and status filters, so narrowing the list left every visualisation beside it describing the whole set. **Fixed 2026-09-08** — every tile, chart and counter reads the one `data()` computed the table reads, and the server statistic is reported separately and labelled as such. Verified: searching narrows the donut from 53 messages to 1. Reports was built the same way in the same session: the Task, Job, Outcome, Owner and Workspace filters added there all narrow a single `data()` that every tile, chart, table and the pivot reads | `features/queue/queue.ts:80-88` |
| 54 | **A by-id read returned soft-deleted rows the list hid.** `fetchSourceTaskWithSourceTaskId` applied the tenant check but not the status check, while `listSourceTask` filters `Delete` out — so a task the list said was gone could still be opened, edited and saved by anyone holding its id. **Fixed 2026-09-08** — a deleted task reads as absent, with the same wording as one belonging to another tenant, so the by-id read and the list now agree | `SourceTaskServiceImpl.java:459-467` |
| 55 | **Two write endpoints answered SUCCESS for work they had not done.** `markRead`'s update is scoped by recipient *and* by `read = false`, so "no rows touched" covered both an already-read row and another user's id, and both came back looking like a real mark-as-read. `DocumentConverter.deleteTask` fell through to SUCCESS for an id that did not exist, so the user got a success toast and found the row still there on the next refresh. **Fixed 2026-09-08** — `markRead` reads the row back and separates already-read (idempotent SUCCESS) from not-found (ERROR, deliberately not a distinct "not yours", which would confirm the id exists to a caller not allowed to see it); `deleteTask` returns ERROR for a missing id. `deleteTask` still does **not** remove the converted objects from the bucket, and that is a decision rather than an oversight: the confirmation the user accepts says in as many words that the converted file stays in the bucket, and both keys sit in a bucket and folder the user chose in `convert()`, next to their own files — so deleting them would be a data-loss bug worse than the leak. The retention is now stated in the response instead of being left implicit | `NotificationCenterServiceImpl.java:138-154`, `DocumentConverterServiceImpl.java:282-288,314` |
| 56 | **A Kafka connection profile became permanently undeletable.** The delete guard counted every task type referencing the profile, soft-deleted ones included — and a deleted task type keeps its `kafka_connection_profile_id` — so deleting the last task type that used a profile locked that profile in place for good, refused in the name of a task type the UI no longer shows. **Fixed 2026-09-08** — the guard reads as "a task type that still exists uses this" (`existsByKafkaConnectionProfileIdAndStatusNot`). Tenant routes are hard-deleted, so their half of the check needs no such qualification | `KafkaConnectionProfileServiceImpl.java:163-170` |
| 62 | **The Azure branch of Analytics Studio has never been run against a real container.** Nothing gates it: `StorageProvider.isObjectStore()` returns true for `AZURE`, so `DatasetResolver` admits an Azure connection like any other, and `DuckDbSessionFactory` then does `INSTALL azure` / `LOAD azure` and builds a `SECRET` from `getAzureConnectionStringEnc()`. S3 and MinIO share one protocol and one secret shape, and that shared path was verified live against MinIO on 2026-09-08 — note that this is evidence for the branch, not for Amazon's own endpoint, which differs in that it derives from the region rather than being set; Azure needs DuckDB's separate extension, a different secret and a different credential field, and **no test exercises any of it** — the only occurrence of the word in `DuckDbLockdownTest` is line 163, asserting the wording of the message that refuses FTP. So the first person to run that code is a user with an Azure connection. The feature must not be described as supporting Azure: the branch is written, wired and unverified, which is a different claim. The likely failure is contained rather than dangerous — the branch throws `SQLException`, which `explain()` maps or, failing that, logs in full and reports as "The dataset could not be read." — so the cost is a broken screen for that user, not an unsafe one. It is listed here as correctness rather than operational because the code claims a capability the evidence does not support | `DuckDbSessionFactory.java:130-134,171-179`, `StorageProvider.java`, `DatasetResolver.java:84` |

---

## P3 — Tests that would not catch a regression

Both instances are the pattern this project has hit repeatedly: **the test asserts against a copy of the logic, not the logic.**

| # | Finding |
|---|---|
| 24 | `features/tools/transcript/transcript.spec.ts` re-implements the component's parser rather than importing it — lines 3-11 say so outright. Seven tests pass against a copy while the real `Transcript.segments` can drift silently. The parser is not exported |
| 25 | The `StorageConnection` filter/guard contradiction (#11) is enforced by only one of its two statements in `TenantFilterDeclarationTest` |

---

## P4 — Dead, inert and misleading

| # | Finding |
|---|---|
| 26 | `@EnableAsync` is declared with **no** `@Async` method, `TaskExecutor` or `ExecutorService` bean anywhere — dead configuration that misleads anyone assuming work is offloaded (`ProcessConfig.java:19`) |
| 27 | Four declared frontend dependencies are never imported: `echarts`, `ngx-echarts`, `marked`, `file-saver`. Every chart is hand-built SVG/CSS; the markdown parser is hand-written |
| 28 | `spring.liquibase.contexts=init` is set in all three profiles, but **no changeset declares a context**, so it currently selects nothing. The first changeset that adds one becomes the only one that has to opt in |
| 29 | `spring.jpa.hibernate.naming-strategy` is the Hibernate 4 property name, not read by Spring Boot 2.x. Inert, and masked because the default strategy produces the same result |
| 30 | `notification.tenant_id` is written and indexed, and **never read** — an index supporting no query, on a column with no FK |
| 31 | `document_converter_task.target_folder` is write-only |
| 32 | The docs screenshot feature is fully wired and entirely unused — no step sets `shot`, and `public/docs` is empty. Adding one yields a broken image |
| 33 | Duplicate Liquibase version number: `V18.0-foreign-key-indexes.yaml` and `V18.0-user-avatar.yaml` are unrelated changes sharing a version |
| 34 | `task_form` and `task_form_field` share one sequence — a future `setval` for one silently moves the other |
| 35 | `SettingServiceImpl:360-375` re-implements both ownership predicates inline instead of delegating to `TenantOwnership` — a second copy of the rule whose own header says it was centralised because *"the copies had begun to disagree"* |

---

## P5 — Operational

| # | Finding |
|---|---|
| 36 | **Cross-project port and container-name collisions**, undocumented: `8085`, `6379` + name `redis`, `2181` + name `zookeeper`, `9093` + name `kafka`. `job-search/docker-files/PORTS.md` covers only collisions inside `job-search`, and is itself stale |
| 37 | ~~**Nothing serves port 4400**, yet it is the default for `app.console.url` — used to build links in outgoing email — and appears in `WEBSOCKET_ALLOWED_ORIGINS`. The Angular dev server defaults to 4200.~~ **Resolved 2026-09-03** — `scheduler1/next/docker-compose.yml` now publishes `4400:80`, matching what the backend already assumed. Verified end to end: build, health check, deep-link routing, and a live login against `process` on `:9098` with CORS intact. Still true for a bare `ng serve`, which stays on 4200 by design — this closes the gap only for the containerized path |
| 38 | **`API_BASE` hard-codes port 9098** with no build-time or runtime override. No `environments/` directory, no `fileReplacements` — any deployment where the API is elsewhere needs a source change and a rebuild |
| 39 | **The stale-jar failure mode is one command away.** Only `run_process_docker.sh` enforces the freshness check; the README documents an unguarded path |
| 40 | **No lint config, no e2e framework, no coverage gate** on the frontend |
| 41 | `143` uses of `any` in non-spec frontend code, concentrated where payloads are richest — `task-edit.ts` (11), `tenants.ts` (7), `file-chat.ts` (6). With `strictTemplates` on elsewhere, these are where a server-side rename fails at runtime instead of at build |
| 42 | The websocket has **one** consumer. `JobEventsService` is a session-long singleton, but only `features/jobs/jobs.ts` subscribes; Queue, Job History and Dashboard poll or need a manual refresh |
| 43 | Primary nav is not keyboard-accessible as a menu — no `role="menu"`, no roving focus, no arrow keys. Row action menus use the CDK and are fine |
| 44 | `mustChangePassword` is read from the localStorage blob rather than the token — a client-trusted flag guarding a client-side redirect |
| 45 | `kafka_connection_profile.sasl_password` holds ciphertext but lacks the `_enc` suffix its three siblings on the same table carry, breaking the convention `StorageConnection.java:19-20` states |
| 46 | ~~`query_definition.query_text` encrypts the **SQL itself**...~~ **Moot 2026-09-05** — the Query Engine and Search Engine features, including `query_definition` and its three sibling tables, were removed whole (`V27__drop_query_engine.sql`, commit `889ae2e`); the table this finding was about no longer exists |
| 47 | **Spring Boot 2.3.2's default embedded Tomcat (9.0.37) crashes the whole backend from an ordinary WebSocket disconnect** — an uncaught `NullPointerException` in `NioEndpoint$Poller.events()` (a channel closed concurrently with the poller processing a queued event for it) kills the poller thread; the JVM stays up (the Docker healthcheck still sees the process running) but the HTTP connector stops answering for every tenant, permanently, until restarted. Reproduced live during a QA pass on `source-jobs`: navigating between its list and edit pages (which cycles the STOMP connection) triggered it and halted that pass outright — see `.ai/qa/source-jobs.md` QA-32. **Fixed 2026-09-07** — `process/pom.xml` now overrides `tomcat.version` to `9.0.83`, the same 9.0.x line Spring Boot already manages, past where this exact race was fixed upstream. Verified live by deliberately repeating the crashing navigation pattern post-fix; stayed healthy |
| 57 | **A deploy left every open tab dead, with nothing on screen to say why.** Every route is lazy and every chunk is content-hashed, so a deploy replaces the filenames a tab loaded before it. The next nav-bar click asked for a chunk that no longer exists, the dynamic import rejected, and the router simply stopped — the nav bar went dead and the user's only recourse was to guess that a hard refresh would fix it. Not an edge case: it happens to every open tab on every deploy, and the frontend had no recovery of any kind. **Fixed 2026-09-08** — `core/stale-bundle.ts` recognises a chunk-load failure across the engines this app runs in, reloads once per URL (`NavigationError` carries the URL, so the user lands where they meant to go), and re-arms on the next `NavigationEnd`. A second failure for the same URL is left alone to surface as an ordinary error rather than spinning in a reload loop, and a `sessionStorage` that throws is treated as "reload once too often" rather than never. Wired in `app.config.ts:15` |
| 58 | **Redis unread-notification counters were created and never removed.** `notif:unread:<id>` is written by every notification, has no expiry, and nothing deleted it — this instance held **23 keys against 6 `app_user` rows**, one of those already `Status.Delete`. The keyspace only ever grew. **Fixed 2026-09-08** — `clearUnreadCount` is on `NotificationCenterService` and `AppUserServiceImpl.changeUserStatus:349-351` calls it whenever an account stops being Active. A TTL was rejected deliberately, and the reasoning is recorded in the code: `create()` bumps the badge with `INCR`, and `INCR` on a missing key answers 1 rather than forcing a recount, so expiring a live user's key would republish "1 unread" over a mailbox holding 49 and then serve that 1 back out of cache. `incrementUnread` now seeds from the database on a miss, so neither removal path can corrupt the badge |
| 59 | **Outgoing mail was sent From an SMTP login rather than an address.** The From header was `${spring.mail.username}`, which on this deployment resolves to `ce545af2135fd6`. SMTP relays tolerated it; SES will not, and neither will a recipient's mail client. **Fixed 2026-09-08** — the From address is its own setting, `app.mail.from`, defaulting to a real address (`EmailMessagesFactory.java:32-40`). In the same change the transport moved behind a `MailTransport` interface, with `SesMailSender` (AWS SDK `SendRawEmail`, so the existing `MimeMessageHelper` building is untouched) as the default and `SmtpMailSender` `@Deprecated` behind `app.mail.transport=smtp`. Tested end to end against LocalStack SES. This does **not** retire #2: `docker-compose.yml:156-157` still carries literal `MAIL_USERNAME`/`MAIL_PASSWORD` fallbacks, now for a path nothing uses by default |
| 63 | **A query engine now runs inside the backend JVM, and its ceiling is per JVM rather than per tenant.** DuckDB is embedded, not a service: an analytics scan competes for memory and CPU with the ETL dispatcher, the crons and every request thread in the same container. The bounds are real and were designed in rather than added afterwards — `analytics.duckdb.memory-limit=512MB` and `analytics.duckdb.threads=2` per session, `analytics.query.max-concurrent=4` behind a **fair** semaphore, `analytics.query.timeout-seconds=30`, one session per query closed with it — and all six properties are declared on dev, stage and prod and named in `ApplicationPropertiesDeclarationTest.java:46-51`, because an absent limit here is an unlimited one. What remains after all that is two things worth writing down. First, four permits at 512MB is up to **2 GB** of engine memory, DuckDB is a native library so what it allocates sits outside the Java heap, and neither the Dockerfile's `ENTRYPOINT` nor `docker-compose.yml` sets a heap size or a container memory limit for `process` — so the 512MB figure is the only number bounding any of it. Second, **the permits are global**: nothing partitions them by tenant, so one workspace running four scans makes every other workspace wait 2 seconds and then read "Too many analytics queries are running right now." The 30-second timeout bounds how long that can last, so it degrades rather than fails — but it is the one place in this feature where one tenant's behaviour is visible to another, on a platform that otherwise holds itself to the opposite. The policy is `AnalyticsLimits.java` in full; the governor is `AnalyticsQueryService.java:52,62,158-161`; the properties are `application-dev.properties:137-142`, and `:140-145` on stage and prod |
| 64 | **A 70 MB dependency carrying native libraries, and a deployment now tied to an architecture.** `org.duckdb:duckdb_jdbc:1.1.3` is 70 MB in the local repository, most of it prebuilt native libraries, and it is on the runtime classpath of every `process` container whether or not anyone opens Analytics Studio. In proportion it is not the worst thing about this image — the base is `eclipse-temurin:17-jdk` and already installs ffmpeg and a headless LibreOffice, which the Dockerfile's own comment calls the real cost of that feature — so this is an increment on an already-large layer rather than a new problem. The consequence that does deserve an entry is architecture: DuckDB runs only where it ships a native, there is no software fallback, and on an unsupported platform the feature does not degrade, it fails to load. Phase one was verified on exactly one combination — Java 17 Temurin, linux/aarch64, Ubuntu 26.04 — so any other is untested here. `DuckDbSessionFactory`'s static block forces the driver to load at startup precisely for this: the failure names itself when the application comes up rather than inside the first request thread that asks for a dataset. One related unknown, recorded as unknown: `INSTALL httpfs` runs per session (`DuckDbSessionFactory.java:126`), before the local filesystem is disabled, and nothing in the phase-one verification record covers a deployment with no outbound network access. The dependency is `process/pom.xml:276-281`; the static block is `DuckDbSessionFactory.java:53-60` |

---

## How to use this

- **P0** should be scheduled now; none of it belongs to a single feature, and #1 needs a decision only the repository owner can make.
- **P1–P2** should be picked up by the [synthesis](../synthesis/) document of whichever feature owns the code. Where a finding spans features (#8, #14), it wants its own piece of work.
- **P3** items are cheap and should be fixed the next time anyone is in the file.
- **P4–P5** are the backlog. Fix them opportunistically; do not open a project for them.

Fifteen entries now carry a resolution note — #37, #46 and #47 from earlier sessions, and #48–#59 dated 2026-09-08, of which #52 is closed only in part. **The other forty-nine stand, including all five P0 items and all twelve unresolved P1 items**: forty-four of them were re-read against current source on 2026-09-08, and the five added later that day (#60–#64, from Analytics Studio phase one) were written from the source they name rather than from a build report. Each item names its file so the claim can be checked before anyone acts on it, and a resolved entry names the change that closed it so the same check can be run on the fix.

One entry, **#61**, is a standing note rather than a defect: it describes what becomes true when phase three of Analytics Studio accepts user-written SQL. It is deliberately here before that lands. Treat it as a precondition on that work, not as something to fix now — and do not close it on the grounds that nothing is currently wrong, because nothing currently being wrong is the state it exists to record.
