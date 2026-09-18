# Regression checklist

What has to keep working. Run the relevant sections after **every** significant change — the whole thing before a release.

The feature names match [../discovery/features.md](../discovery/features.md).

## First: the automated suites

These are the cheap part and they catch most of it. All four green before any manual pass.

| Suite | Command | Expected |
|---|---|---|
| Backend unit | `mvn -o test` (from `process/`) | 607 passing |
| Backend E2E | `./run-e2e.sh` | 86 passing |
| Frontend | `npx ng test --watch=false` (from `scheduler1/next/`) | 580 passing |
| Kafka security matrix | `./run-kafka-matrix.sh` | 17 passing, real broker |

A count that has gone **down** without a deletion you intended is a regression in itself.

> The backend and frontend numbers were re-confirmed on 2026-09-08 (587 and 580, both green) —
> they had been 516 and 445, and the work of that session added tests rather than removing any.
> The E2E and Kafka-matrix suites were **not** re-run that day; their expected counts are carried
> forward unverified.

> **Re-confirmed 2026-09-17: backend 1517 (`mvn -o test`, 0 failures after the
> `AvatarBucketPropertyTest` fix), frontend 1583 (74 files).** The four `AvatarBucketPropertyTest`
> errors that had been carried since 2026-09-16 were a private `@Configuration` CGLIB could not
> proxy -- one word, fixed in `889a09c`. Access profiles, per-run callback tokens and the report
> outcome columns added the rest. E2E and Kafka-matrix counts still carried forward unverified;
> Playwright's 42 known failures (missing `etl-bucket`/`analytics-samples/orders.csv` fixture and
> unseeded dashboards) are pre-existing and unrelated.

> Later the same day, Analytics Studio phase one took the backend from 587 to **607**: twenty new
> tests, `DatasetResolverTest` (13) and `DuckDbLockdownTest` (7). The frontend figure is unchanged
> at 580 and that is **not** a neutral fact — **no frontend unit test was written for the Studio
> component at all**. `features/analytics/analytics.ts` and `analytics.service.ts` have no `.spec.ts`
> beside them, so everything the new screen does is covered by the manual line below and by nothing
> else. Treat the unchanged 580 as an outstanding gap, not as a suite that had nothing to add.

> Run the project's own commands. `npx vitest` instead of `ng test` produces dozens of failures that are not real; the Kafka matrix cannot pass from the host at all. A wrong runner has cost more debugging time here than any actual bug.

## What to re-test when you change X

Taken from the dependency graph in [../discovery/features.md](../discovery/features.md) §5. Changing something on the left means re-testing everything on the right.

| If you change… | Re-test |
|---|---|
| `authentication-and-access` | **Everything.** It is the only source of the token and the role |
| Anything tenant-scoped (a service, an entity, a filter) | Every feature that reads that entity, **as two different tenants** |
| `platform-configuration` (task types, Kafka routes, lookups) | `source-tasks`, `source-jobs`, and any dispatch |
| `storage-connections` | `object-browser`, Kafka certificate upload, avatars, and — since 2026-09-08 — `analytics-studio`: a dataset is named as a connection **alias** plus a path, and the bucket comes from the connection record (`getBucketName()`, falling back to the alias), so the record is the only thing deciding which bucket a query reads |
| `features/objects/storage.service.ts` | `object-browser` **and `analytics-studio`**. The Studio's left rail calls this service's `buckets()` and `listObjects()` rather than carrying a second copy, and `analytics.ts` imports `BucketSummary` and `ObjectSummary` by name — so a change to the service or to either shape is a change to two screens, and only one of them has unit tests |
| `source-tasks` | `source-jobs`, `bulk-transfer` |
| `source-jobs` | `job-runs-and-queue`, `job-assistant`, `reports`, `dashboard`, `bulk-transfer` |
| Shared UI in `shared/ui` or `shared/charts` | Every screen using it — grep before assuming |
| `shared/charts/day-series.ts` | `reports` **and** `job-runs-and-queue`. Both draw a runs-per-day axis from it, so the empty-day gap fill and the `MAX_DAYS` cap are shared behaviour, not one screen's |
| `shared/charts/bar-chart.ts` | Every bar chart, at a **narrow** container and at a container that starts hidden. Label thinning is decided from the measured pixel width, not the bar count |
| `core/api/list-limit.ts` | The Tasks list and the job editor's task dropdown. Both send `LIST_LIMIT` because `PagingUtil` defaults an absent limit to ten; a change here silently shortens both lists |
| The auth interceptor or guard | Every route, plus the token-refresh path under parallel 401s |
| `PageKey`, `PageAccessInterceptor`, `PageAccessServiceImpl.resolve`, or `app.routes.ts` `data.pageKey` | **`page-access-profiles` as a tenant user with a restrictive profile**: the menu, a direct link to a withheld page, and the API behind it (must be 403). Adding a route without a `pageKey` makes it open to everyone; adding one with a key that is not in `PageKey` makes it closed to everyone |
| `RunCallbackTokens`, `NotifyResetApi`, `ProducerBulkEngine.getSourceJobDetail`, `job_queue` columns | **A real dispatch and a real callback** -- `curl` the three endpoints with the token from the Kafka message, then with it again after `Completed` (must be 401), then a UI cancel followed by that run's token (must be 401). The unit tests mock the repository; only a live run proves the row round-trips |
| `QueryService.runReportRows` | `reports` with a skipped run in range (make one with *Skip next run* on an Auto job): it must count in Runs, appear in the Skipped column and the donut |

## Feature checklist

Each line is a smoke test: the feature's main path still works, as the role that normally uses it.

### Foundation

- [ ] **authentication-and-access** — sign in; a bad password is refused; the token refreshes rather than logging you out; `mustChangePassword` pins the session to `/profile`; an unauthorised route lands on `/unauthorized`
- [ ] **tenants-and-users** — the tenant code chip copies and ticks; the Admin column names the first tenant admin (Default shows —); email and phone copy from the **table** as well as the cards; a phone saves from the dialog, the tenant-admin API and `/profile`, always in E.164; list, create, edit, deactivate a user; reset a password; a tenant admin sees only its own tenant's users; a platform admin sees all; on `/admin/tenants` the pipeline count appears under Tasks only when it differs from the task count
- [ ] **workspace-requests** — submit a request from the public page; approve one; reject one
- [ ] **page-access-profiles** — as a tenant admin: create a profile, make it default, assign it, tick a per-person exception in the grid and reset it; as that tenant user: the withheld page is gone from the menu, its URL lands on Unauthorized, "Request access" notifies the admin, and its API group answers 403; as a platform admin: pick a workspace first, and the Tenants row menu's "Access profiles" lands on that workspace's grid with the picker showing its name
- [ ] **worker-callback-tokens** — run a job; the `job_queue` row gets a hash and expiry at dispatch (not at Run); the token in the Kafka message opens `addLogs` / `Running` / `Completed`; afterwards the hash is null and the same token is 401; a run cancelled from the screen refuses its own token
- [ ] **own-account-and-notifications** — view and edit your profile; change your password; upload an avatar and see it appear; the activity list loads; the bell shows unread and marking read clears it; marking an **already-read** notification still reports success while an unknown id is refused; deactivating an account clears its unread count rather than leaving a Redis key that never expires

### Configuration

- [ ] **platform-configuration** — task types; Kafka connection profiles list, save, **test connection**; certificate upload and truststore/keystore generation; lookups and sub-lookups; XML checker; a profile whose last referencing task type has been **deleted** can itself be deleted (a soft-deleted task type must not hold it hostage); `/settings/kafka` shows the Workspace column
- [ ] **storage-connections** — list, add, edit, clone, **test connection**, discover buckets, delete; a tenant sees only its own connections and **neither platform bucket**

### Core workflow

- [ ] **source-tasks** — list, create, edit, delete; the task form loads for the selected pipeline; linked jobs are shown; the list shows **every** task, not the first ten — the count reads *n* of *n*; a deleted task cannot be opened or edited **by id** — the fetch has to agree with the list about what is gone; as a platform admin, opening another tenant's task serves **that tenant's** pipeline form, and saving does not overwrite the payload with a form from the wrong tenant
- [ ] **source-jobs** — list, create, edit, delete; enable/disable; run now; skip next; live status arrives over the websocket; the task dropdown offers **every** task, so a job can be attached to the eleventh one; a job's notification email reaches the job's own assigned user rather than a single platform-wide mailbox
- [ ] **job-runs-and-queue** — run history for one job and across jobs; run logs; the queue screen; fail/interrupt a job; on the queue screen the donut, the failure rate and the counts move with the **table's** filters — narrow the search and every one of them narrows with it
- [ ] **bulk-transfer** — download a template, upload a filled one, download the current list, for both jobs and tasks
- [ ] **dashboard** — every tile and chart loads, including the empty case for a brand-new tenant

### Tools and content

- [ ] **object-browser** — browse, upload, download, preview, create folder, rename, delete, multi-delete; file share; file chat
- [ ] **analytics-studio** — **phase one only.** Pick a connection, walk folders, open a CSV, TSV, JSON or Parquet file, and read both tabs — Overview and Data, the latter showing the rows and a columns rail side by side; filter the folder listing by name and confirm the count narrows and clears on navigation; page the Data tab forward and back; "Read the folder as one dataset" turns a folder of like files into **one** dataset with a filename column, and the Overview figures then cover every file the pattern matched. Then the refusals, which are the half worth more of the two: a path containing `..`, a path with a character outside the allow-list, a file type it does not read, a path that is not there, and an alias belonging to **another workspace** — each must come back as a designed sentence in the ERROR body (the house convention: HTTP 200, `ResponseDto` status ERROR), never a stack trace and never a DuckDB error verbatim. The other-workspace refusal must read **identically** to the does-not-exist one; if the two ever diverge, the alias has become an enumeration oracle and that is a security regression, not a wording one. **Azure is untested** — S3 and MinIO share the S3 protocol and were verified live, the `azure` branch has never been run against a real container, so do not record it as passing. There is no user-written SQL, no profiling, no charts, no dashboards and no saved queries in phase one; if you find yourself testing one of those, the checklist is wrong, not the build. **Two tenancy checks added 2026-09-08, and they are the ones worth doing first:** sign in as a tenant user and confirm the connection picker is **empty** — every connection in this environment is platform-owned, so Analytics Studio must show a tenant user exactly what the Object Browser shows them, which is nothing; then confirm a platform admin still reads all seven. If a tenant user can read a bucket here that the Object Browser refuses them, that is the A1 regression and it is a cross-tenant read, not a wording problem. Also confirm a connection switched to **Inactive** disappears from both screens together.

  **Phases two to five, added 2026-09-08.** The Studio now has five tabs and three more endpoints, so the
  checklist grows with it. **Profile and Quality:** open a CSV, visit Profile, and confirm the scan is
  issued ONCE and shared by both tabs (it is lazy — not on file open, because a file open already costs
  three of the governor's four permits). Every inexact figure must still read as inexact: the distinct
  count as an estimate, any absolute null count as "about", a text column's extremes as "first/last (A-Z)"
  rather than min/max, the quartiles as estimated. On a **header-only file** — columns, no rows — Quality
  must say there was nothing to check and must NOT recite the five checks it did not run; that exact
  false clean bill was a real defect. **SQL console:** run a query, confirm the row count, and confirm a
  result that hit the ceiling says so ON the count and again above the table, never only below it. Then
  the refusals, which matter more: `SELECT * FROM 's3://other/x.csv'`, `SELECT * FROM "s3://other/"."x.csv"`
  (the quoted-schema form — this one smuggled a URL past the gate and produced a SIGNED cross-bucket S3
  GET and arbitrary outbound HTTP; if it is ever admitted again that is a critical regression, not a
  wording one), `SELECT * FROM "http://169.254.169.254/"."latest.json"`, `COPY (SELECT 1) TO '/tmp/x.csv'`,
  and a multi-statement `SELECT 1; DROP TABLE t`. Each must come back HTTP 200 + status ERROR with a
  sentence, and `SELECT count(*) FROM dataset` must still succeed — without that control, a gate that
  refused everything would pass every line above. Confirm each attempt, refusals included, lands a row in
  `analytics_query_run`. **Saved queries and history:** save, load, rename, delete; confirm another
  workspace's saved query is unreachable and that the refusal reads identically to not-found.
  **Export:** download CSV/TSV/JSON, and confirm a truncated export is marked in the filename, inside the
  file, and on the screen. **Write-back:** confirm it lands in the connection's OWN bucket, that a folder
  containing `..`, `.`, `//`, a leading slash or a scheme is refused, and that no endpoint anywhere accepts
  a URL to post to — that destination was deliberately never built, and reports gaps 1-4 are why.
  **Benchmark:** PLATFORM_ADMIN only, one at a time, and the stored row must say what was measured
  (`measure_kind`, `sessions_per_run`) and the spread, not just a mean
- [ ] **query-and-search-engines** — connections, saved queries, execute one, schedules
- [ ] **content-and-ai-tools** — document converter; audio transcript; text cleaner; AI agents CRUD; Ollama model list; deleting a converter task removes the row and **leaves the converted object in the bucket**, which is what the confirm dialog promises; deleting an id that is not there is refused rather than reported as a success
- [ ] **job-assistant** — ask a question about a job and get an answer; export the conversation
- [ ] **reports** — Task health shows Completed / Failed / Interrupted / Skipped / Missed, the Runs tile foot counts "skipped or missed", and a skipped run dated in range appears; the runs report loads and exports; the Task / Job / Outcome / Owner / Workspace filters move **every** tile, chart, table and the pivot together, not just the table; a chart kind that sums cells (stacked, 100% stacked, donut, pie, radar) is disabled with a stated reason when the measure is not additive, and the choice falls back to Grouped; clicking a day on runs-by-day narrows the range to that day; a run opens its log; the Execution measures are distinct from the queue-wait ones

> `dynamic-forms` was removed whole on 2026-09-03 — feature, route, screens, controller, service,
> entities. `/settings/dynamic-forms` now redirects to the app root via the wildcard route, which
> is the one thing worth re-checking after any change to `app.routes.ts`. See
> [`../old-scope/dynamic-forms-grooming.md`](../old-scope/dynamic-forms-grooming.md).

### Cheap to check, and each one was a real defect

Two minutes each, and both are invisible from the screens above — the first happens on a timer
with nobody watching, the second looks like a rendering nicety until you try to read the axis.

- [ ] **The audit-log sync cron.** Let `AuditLogSyncCron` tick once (30 minutes) and read the log. It must end with one line of the shape `scanned=… upserted=… skipped=…` and contain **no** foreign-key violations. A run whose `job_queue` row has since been purged is skipped and the watermark moves **past** it — if the watermark is pinned instead, the scan window grows without bound and re-explodes on the same purged runs for ever. The reference healthy line after the 2026-09-08 deploy was `scanned=485 upserted=8 skipped=262`
- [ ] **Bar-chart axis labels at the default range.** Open Reports on its default range — the last 30 days, so 31 bars — and read the x axis: the day labels must not overlap. `app-bar-chart` thins them from its own **measured pixel width**, so the cases worth trying are a narrow viewport and a chart inside a section that starts hidden and is then opened — a container that begins at zero width is what a bar-count-only rule got wrong

### Not migrated

- [x] ~~**pdf-highlighter** — **only in the old app**, at `http://localhost/scheduler/pdfHighlighter`. Its backend (9 endpoints) is live and must keep working while the decision on it is open. If you touch `PdfHighlighterTaskRestApi`, `PdfHighlighterTaskServiceImpl`, or the storage guard, test it there~~ **Removed 2026-09-07** (decision made: drop, not migrate) — the route, backend, and tables are gone; this checklist item no longer applies. See `.ai/synthesis/pdf-highlighter.md`'s decision banner.

## Cross-cutting, every release

- [ ] **Tenant isolation.** As tenant A, try to reach tenant B's records **by id**, not only through a list. A Hibernate filter does not apply to `findById`
- [ ] **Role floors.** Each protected endpoint called as the role one step below the one it requires
- [ ] **The tenant-less caller.** A token with no tenant claim must own nothing — in particular not the platform-owned rows (`etl-avatar`, `etl-bucket`)
- [ ] **Storage keys.** As user 1248, try `1249/profile/…` and `12480/profile/…`
- [ ] **No secrets in responses.** No password, private key or store location returned to a caller that does not own the profile
- [ ] **The analytics engine's lock-down.** `DuckDbLockdownTest` is the standing proof and it runs against a **real** DuckDB rather than a mock, because the claim is about what a specific engine refuses to do: the session cannot read a local file, cannot write one, cannot raise its own memory ceiling, cannot re-enable the local filesystem, refuses an FTP connection by name, rejects a malformed memory-limit property rather than interpolating it — and **still reads a dataset**, which is the control that stops the other six passing vacuously. If you touch `DuckDbSessionFactory`, check by eye as well as by suite that `SET lock_configuration=true` is still the **last** thing `open()` does, and that a session which fails part-way through configuration is closed rather than returned: a half-configured session is an unlocked one
- [ ] **Dark and light mode** on every screen you touched
- [ ] **Narrow viewport** on every screen you touched
- [ ] **Empty states** — a brand-new tenant with no jobs, no tasks, no connections should see a designed empty state everywhere, not a blank panel or a spinner that never stops
- [ ] **A deploy under an open tab.** Leave a tab sitting on a screen, redeploy, then click the nav bar. Every route is lazy, so the old bundle asks for a chunk filename that is gone; the tab must reload **once** and land on the destination rather than the router stopping dead. `core/stale-bundle.ts` re-arms after a successful navigation, so a second deploy has to recover too
- [ ] **Outbound mail.** Send one real notification. It leaves through the SES SDK (`app.mail.transport=ses`, the default) and the From address is `app.mail.from` — not an SMTP login, which is what `${spring.mail.username}` used to put there

## Recording a run

Add a row. Keep failures in the table rather than deleting them once fixed — the history is what shows which areas are fragile.

| Date | Change | Sections run | Result |
|---|---|---|---|
| 2026-09-08 | Reports rework (filters, additive-measure gating, execution vs queue wait, Workspace dimension) plus the session's fixes across notifications, queue, tasks, jobs, Kafka profiles, the converter, the audit cron and mail | Automated: backend unit, frontend. Manual: spot checks only, not the full checklist — the queue donut under a search, the Tasks count, the reports filters and axis, the audit cron after deploy | Backend 587 passing, frontend 580 passing. E2E and the Kafka matrix **not run**. `pivot.spec.ts` had one existing assertion changed by the `humanSeconds` no-data sentinel — an intended change, not a failure |
| 2026-09-08 | Analytics Studio **phase one** — a new `process.analytics` module reading a file where it lives in object storage through an embedded DuckDB, six `analytics.*` properties, the `org.duckdb:duckdb_jdbc:1.1.3` dependency, and the `/analytics` screen, route and nav entry | Automated: backend unit, frontend. Manual: the new `analytics-studio` line only, live against MinIO — `sales.csv` (7 rows, 4 columns), a glob over three partition files read as one dataset (7 rows, 5 columns, the filename column present), a Parquet read, the refusal paths, and an absolute `/etc/passwd.csv` confined inside the connection bucket; dark mode and a narrow width on the new screen. **No other section of this checklist was re-run** | Backend **607** passing (`DatasetResolverTest` 13 + `DuckDbLockdownTest` 7 are the whole of the +20). Frontend 580 passing — **unchanged because nothing was added**, see the note under the suite table. E2E and the Kafka matrix **not run**; the backend was rebuilt and redeployed and came up (Java 17 Temurin, linux/aarch64, Ubuntu 26.04), so the DuckDB driver's static-block load was exercised at startup, but that is the only thing about those two suites this run can say. **Azure was not exercised at all** |
