# Completing the specification — working tracker

Started 2026-09-08 from the audit in `AUDIT.md` (370 requirements: 120 done, 71 partial, 19 deviated,
160 missing) plus documents 15 and 16, which that audit omitted and which are recorded below.

Rule for this tracker, inherited from 16's final gate: a line moves to done only with evidence. No
line is ticked because a class exists with a promising name.

## Document 15 — V2 hardening (audited inline 2026-09-08)

V2's stated precondition is "after the first implementation is working". It is not, so this is a
status record, not a failure to have finished.

| Item | Status | Evidence / note |
|---|---|---|
| Architecture — remove duplicated services / **simplify abstractions** | **DONE 2026-09-10** | StorageService reused rather than copied; a second charting/dashboard stack refused (synthesis 3.11). The `AnalyticsEngine` seam is real rather than paper: `@ConditionalOnProperty(analytics.engine=duckdb, matchIfMissing=true)`, and `shutdown()` moved onto the interface after an `instanceof` was found covering every method except the one that stops the background thread. **"Simplify abstractions" was then done by measuring rather than by taste.** Only one interface in the module has one implementation and it is the seam above, so there was no interface bloat to cut; what the measurement DID find was four abstractions that cost something and returned nothing, three of them the same defect — a configuration knob an operator can set that changes nothing. See the row below. |
| Architecture — the inert-configuration sweep (part of "simplify abstractions") | **DONE 2026-09-10** | Every `public` method in `process.analytics` was checked for a caller. Four had none. **`analytics.benchmark.enabled`** and **`analytics.parquet.conversion-enabled`** were each declared, given a refusal sentence written for an operator, reported by `/actuator/health` among the limits *in force* — and read by no production code, so setting either to false switched off nothing while the health endpoint agreed it was off. Both are now enforced at the point the caller's word is first believed, with tests that fail when the guard is removed; the benchmark's switch deliberately still allows PAST results to be read. **`analytics.history.cleanup-interval-hours`** described a six-hour cadence, the cron ran hourly, and the cron's own comment claimed the property took effect — deleted, because retention-days is the control here and the cadence is not. **`analytics.profile.sample-rows`** was declined on a measurement rather than removed on taste: on 2M rows × 6 cols of CSV, `USING SAMPLE 200000 ROWS` (what the property means) costs 374 ms against 396 ms for the whole SUMMARIZE — a reservoir sample reads every row, so it saves 5% and buys a number that is no longer true. The numbers and the form that WOULD work (a percentage sample, labelled as one in the UI) are in `AnalyticsLimits`. The fourth, `AnalyticsQueryService.runningCount()`, was a facade hop over `RunningQueries.size()` that nothing called — the hop is gone and the count is now reported by `/actuator/health` beside max-concurrent, which is the pair that answers "why is my query waiting". `RunningQueries.size()` also finally has the leak assertion its javadoc said it existed for: every terminal path a run can take, then the same run ids reused to prove the registry really emptied. |
| Architecture — verify dependency boundaries | **DONE 2026-09-09** | Reviewed, and the review is now executable. There IS a package cycle and it is deliberate: `analytics` reaches `model.repository` (no store of its own), `model.service.StorageBrowserService` (two calls, both about OBJECTS not rows) and `config` (the query-completed announcement borrows the one configured Kafka producer); `AnalyticsDatasetServiceImpl` reaches back for `DatasetResolver`, because reachability is analytics's own rule and a duplicate is how the two would disagree about who may read what. `AnalyticsBoundaryTest` states exactly those five crossings and fails on a sixth — it caught two I had not listed (the Kafka pair) on its first run, and a probe import in `model.service` fails it in the other direction. What it stops is a narrow argued cycle widening into an unexamined one. |
| Architecture — inspect query plans | **DONE 2026-09-09** | `AnalysisQueryPlanTest` EXPLAINs the builder's own SQL across the matrix that changes the plan and pins four properties: no nested-loop join, no `DELIM_JOIN`, one pass for a plain grouping, exactly two for a Top-N. Production EXPLAIN logging was considered and **declined** — `inSession()` does not hold the SQL text, the only run worth capturing is a slow or failed one whose connection has since been interrupted, and it would spend a second statement while holding one of four permits. |
| Security — penetration-style authorization tests | **DONE 2026-09-09** | Now systematic: `AnalyticsAuthorizationE2EIT` DISCOVERS every `@RequestMapping` on the four analytics controllers by reflection rather than listing them, so an endpoint cannot be added without being covered — a hand-written list is one somebody forgets to add to, and the forgetting looks like passing. Twenty endpoints, none answering an unauthenticated caller; cross-tenant reads refused as a business ERROR rather than a 500. |
| Security — secret scanning | **DONE 2026-09-09** | gitleaks over the git HISTORY of both repositories (a working-tree scan calls two of the three `process` findings clean, because the files no longer exist in HEAD). Nine raw findings triaged to three real; five false positives allowlisted with the reason beside each. `.ai/tools/secret-scan.sh` fails when the count goes up, and is proved to by mutation. Full triage in `SECRET-SCAN.md`. **Two exposures were previously unknown: an RSA private key (2024) and a Google OAuth client secret (2022), both in pushed history.** All three need rotation, which is not something a commit can do. |
| Security — tenant-isolation review | DONE | DatasetResolver `isOwnedByCaller` + `Status.Active`; per-entity `@Filter`; the findById trap handled via scopedFind. |
| Security — audit completeness | **DONE 2026-09-09** | Schema, preview and profile now write a history row too, successes AND refusals — before this, "who read this file" was answerable for the SQL console and not for the nine other tabs, which is how the file is actually read. The descriptor is a SQL comment (`-- preview page=3 sorted searched`) so it can never be read back as a statement, and it names the FACT of a search without the search term: filter values are the reader's own data. Verified against the live stack — 38 rows written by one E2E run, with row counts and durations. Five tests. **This makes the missing TTL cleanup below more pressing, not less: a reader paging a 1,500-page dataset now leaves 1,500 rows and nothing removes them.** |
| UX — visual consistency | **DONE 2026-09-09** | axe at WCAG A/AA now runs in DARK mode as well as light, across five tabs and a dashboard — a palette that passes light and fails dark is the usual way this breaks. Plus a check for the exact failure a token defined only in the light block produces: text the same colour as its own background. |
| UX — accessibility | **DONE 2026-09-09** | axe-core over all ten tabs, the browse screen and the library, at WCAG 2.1 A/AA, on every suite run. Found two criticals on the first run, both real: every focusable column-resize separator was missing `aria-valuenow` (Angular drops an attribute bound to `undefined`, and a column is auto-sized until someone resizes it), and the saved-analysis refresh button had no accessible name. The spec states what axe CANNOT see — it will pass a screen that is unusable by keyboard — and `keyboard.spec.ts` covers that half. |
| UX — keyboard navigation | **DONE 2026-09-09** | The ten view tabs were ten Tab stops; now a roving tabindex — one stop, with Left/Right/Home/End moving between them and wrapping. **Manual activation, not the more common automatic variant**, because four of those tabs trigger a full scan behind a four-permit governor: automatic would spend three permits getting from Details to Canvas. `role="toolbar"` rather than `role="tablist"`, since the tabs sit in three `role="group"` boxes that carry what each costs. Five E2E tests, one asserting arrowing does not open a tab. |
| UX — responsive behaviour | **DONE 2026-09-09** | Checked every run at 390×844 rather than once by hand. A table may be wider than a phone; the PAGE may not, and the check allows wide content that carries its own scroller instead of forbidding it. |
| UX — loading/error/empty states | DONE | Four dataset-pane states, four chart empty states, distinct quality empties. |
| UX — dense data-table ergonomics | **DONE — the audit was stale, not the feature missing** | Re-checked against document 06 line by line: all EIGHT Data-view capabilities are built — pagination, column resize, sorting, filtering, search, column visibility, copy cell, horizontal scroll. The "2 of 8" figure predates the sort/search/filter work and was carried forward without re-reading. Now pinned by five E2E tests so the number cannot go stale again in the other direction. One real fix found while writing them: the screen-reader caption said "1 rows of 1 columns". |
| Performance — benchmark regression suite | **DONE 2026-09-09** | The harness measured; `BenchmarkRegression` now NOTICES. Every run compares against the best median on record for the same label/measure/format/path, and the endpoint says so in its own message rather than only in a log on a server. **Baseline is the BEST on record, not the previous run** — against the previous run, two runs each 15% slower are each inside a 25% tolerance and the pair is 32% slower than where it started. A FILE_OPEN is never compared with a QUERY (three sessions against one) and CSV is never compared with Parquet (that comparison is the point of the harness). Ten tests, including the trap that a run reading history back after writing finds itself as its own baseline. Reports rather than throws: these are timings from a real network on whatever machine ran them. |
| Performance — profile expensive queries | **DONE 2026-09-09** | The Top-N path profiled with EXPLAIN on DuckDB 1.1.3 and two measured inefficiencies fixed: a correlated EXISTS that degraded to a `DELIM_JOIN` whenever a filter was present (75ms→30ms on 4M rows), and a `count(DISTINCT)` duplicating a list already being built (491ms→392ms on 8M). Both result-identical; the plan test above stops either being lost. |
| Performance — optimize high-cardinality analytics | **DONE 2026-09-09** | The row was stale — a Top-N path with an Other bucket does exist. Profiled and improved (above). The two passes it makes are inherent and correct: the ranking must be known before the roll-up can be aggregated from raw rows, which is what makes Other a real total rather than a subtraction. Verified live over 250,000 rows: top 10 customers plus Other sum to the filtered total, to the penny. |
| Performance — verify cancellation | **DONE — row was stale** | Cancellation exists and is real: `RunningQueries.Handle`, a single watchdog thread, `Statement.cancel()` (measured working on 1.1.3 where `setQueryTimeout` is a no-op), QUEUED→RUNNING transitions that honour a cancel arriving while queued, and cancel-before-close ordering. Re-verified 2026-09-09. |
| Performance — optimize storage reads | **DONE 2026-09-09** | `knownTotal` removed the repeat COUNT per page turn; a **cell budget** now bounds a response by rows×columns rather than rows alone (100,000 rows of ten columns was 12.9 MB of JSON and 61 MB of heap; it is 1.25 MB and 6 MB now, and says it was cut); and the preview's page size no longer bypasses the ceiling — `?pageSize=100000` returned a hundred-thousand-row payload through an endpoint meant to return one page. |
| Reliability — retry policy for transient storage errors | **DONE 2026-09-09** | One retry, and only for the BUILT-IN reads (schema, preview, profile) — user SQL is not retried, because that caller holds a run id and may be watching a stop button. A fresh session per attempt, since the broken thing IS the connection to the object store. Classified narrowly: connection resets and 5xx/429/`SlowDown` retry; 401/403, 404, parser errors, malformed CSV, memory pressure and timeouts do not. **The classifier test found a real bug: S3's throttling code is `SlowDown`, one word, and the spaced check matched nothing.** Eleven tests, proved load-bearing by mutation. |
| Reliability — idempotent export/write | **DONE 2026-09-08** | Two mechanisms, because the cost of being wrong is somebody's data: the stamp went to milliseconds, and `refuseToOverwrite` asks the platform's own storage service whether the key is taken before writing. `overwrite=true` is honoured — replacing yesterday's export on purpose is a real thing to want; doing it by accident is not. Fails CLOSED: an unreadable answer refuses the write rather than assuming the key is free, which would restore the clobber precisely when the store is unhealthy and it is hardest to notice. Four tests, proved load-bearing by removing the guard and watching the two refusals fail while the two controls stayed green. |
| Reliability — cleanup of temporary resources | **DONE 2026-09-09, and smaller than the row implies** | Audited first: DuckDB deliberately writes no temp files (`preserve_insertion_order=false`, no temp directory — DuckDbSessionFactory:103), and `RunningQueries.inFlight` cannot leak because `close()` is the only removal and sits in an outer `finally` covering completion, failure, timeout, cancellation and a caller who never got a permit. The one thing that grows is `analytics_query_run`. A retention cron now exists (`AnalyticsHistoryCleanupCron`, ShedLock, hourly) — **defaulted OFF**, because V32 argued deliberately for leaving that table unpruned and named the condition that would change its mind (a machine issuing queries on a schedule), which read-auditing is not. Mechanism shipped, policy left to whoever owns the audit question. Five tests; the default-off test was rewritten after mutation showed the first version did not guard the default at all. |

## Document 16 — implementation checklist (audited inline 2026-09-08)

Final gate, verbatim from the document, with the truth beside it:

| Gate | Status |
|---|---|
| backend build passes | DONE — `mvn -o package`, **1,233** tests, 0 failures (2026-09-14) |
| frontend build passes | DONE — `ng build` clean, **1,228** tests (2026-09-14) |
| migrations pass | **CORRECTED** — V31/V32/V33 were applied; V34 was NOT, and this line claimed otherwise. The claim was true of a throwaway scratch database, not of `etl_job`. Now applied; seven analytics tables live, and a Postgres integration test guards the drift. |
| all critical tests pass | DONE. **2026-09-10: backend 1,154 unit / frontend 1,143 unit / 45 Playwright / 102 backend E2E, every one green against a stack rebuilt from this source.** That last clause is the point: :4400 and :9098 are containers, and a run against a stale bundle failed two specs that the same code passes — one of them looking like an accessibility regression. Rebuild both before believing a browser run. **E2E now exists** — Playwright specs over the real 150,000-row fixture, all passing, one proven load-bearing by mutation. **The 20 analytics integration tests do run in `mvn package`** — they are named `*IntegrationTest`, which matches surefire's default includes, and re-running them under `-Danalytics.it.required=true` (which turns "infrastructure absent" from a skip into a failure) passes with real HTTP reads logged against MinIO :9000 and LocalStack :4566. **CORRECTED 2026-09-09** — I recorded here, more than once, that eight `*IT.java` classes had never run. That was wrong. `run-e2e.sh` runs the five `*E2EIT` classes plus `HarnessSmokeIT` (86 tests, recorded in this repo's own README), and `run-kafka-matrix.sh` covers `KafkaSecurityMatrixIT`. Only **`ContextProbeIT` and `OpenSearchRagClientIT`** matched no runner's glob and had genuinely never executed. The real defect was that none of them sat in a lifecycle phase, so `mvn verify` reached none and nothing could gate a build on them. **Fixed**: a `maven-failsafe-plugin` under an `it` profile — `mvn -o verify -Pit`. Behind a profile because every one needs Docker services, and a `verify` that goes red on a laptop with no Docker running is a `verify` nobody runs. `ContextProbeIT` now runs and passes. |
| **actual benchmark evidence captured** | **PASSES 2026-09-09 — six rows recorded through the harness, on the real request path.** See below. |
| **no fake/mock completion claims** | **Held, and enforced: the Azure refusal's "S3 and MinIO have been verified" was removed on 2026-09-08 once it emerged every S3 connection points at LocalStack, so the AWS path is unexercised too.** |

Checklist body items are tracked by the same evidence in `AUDIT.md`.

## Build order

Chosen from the audit's dependency structure, not the document order.

1. **Engine and lifecycle** — `AnalyticsEngine` abstraction, the six lifecycle states, and real
   cancellation. Everything below runs through it, and it is the one refactor that gets harder the
   more callers exist.
2. **Persistence** — `analytics_analysis`, `analytics_dashboard`, `analytics_dashboard_widget`, and
   wiring `analytics_dataset`, which is live schema nothing writes.
3. **Operations** — config aligned to 14's values, health indicator, feature flag, correlation IDs,
   TTL cleanup.
4. **The analysis model** — filter compiler and analysis query builder compiled to safe SQL through
   the existing gate and governor. This is 07, and it is the single largest gap (2 of 48).
5. **Workspace** — the ten tabs, the real data grid, the Canvas UI, charts and dashboards.
6. **Evidence** — generate real CSV/Parquet at size, run the harness, capture measured numbers;
   integration tests against the MinIO and LocalStack already running here; the eight E2E scenarios.
   **All three DONE: benchmark 2026-09-08, integration tests and E2E 2026-09-09.**
7. **V2 hardening** — the table above, once there is a whole implementation to harden.

## Benchmark evidence — captured 2026-09-08

Document 16's final gate demands "actual benchmark evidence captured" and 12 says "Never fabricate
numbers." Until now `analytics_benchmark_result` held zero rows and the module was shipping advice
(`explain()`: "Try a narrower dataset, or Parquet instead of CSV") that nobody had checked.

**Data generated and uploaded**, so there is something real to measure — `etl-bucket/analytics-benchmark/`:

| Tier | Rows | CSV | Parquet |
|---|---:|---:|---:|
| 10 MB | 150,000 | 9.3 MB | 2.3 MB |
| 100 MB | 1,500,000 | 94 MB | 23 MB |

Row shape is deliberately not flattering to Parquet: a low-cardinality dimension, a high-cardinality
one, a decimal, a date and free text. A file of one repeated integer would compress to nothing and
manufacture the result.

**First measurement**, 100 MB tier, `GROUP BY region` with `count` and `sum` over 1,500,000 rows,
through the full request path a user actually takes (HTTP → Spring → governor → DuckDB → MinIO):

| Format | Runs (ms) | Median |
|---|---|---:|
| CSV | 1027, 987, 977, 989 | **988** |
| Parquet | 127, 127, 134, 107 | **127** |

**Parquet ~7.8x faster**, with a spread tight enough that this is not noise. The advice the product
gives users is therefore true on this deployment. Two honest limits: this is the request path, not the
harness, so it is not yet a persisted `analytics_benchmark_result` row; and it is one of the ten
operations 12 lists.

## Two display defects found while measuring

Both from the same root: values are stringified server-side with `getString()` and no type travels
with them, which is also why 09's "typed column metadata" is unmet.

- `SELECT sum(amount)` over the 10 MB file returns **`7.466125E7`** — 74,661,250 in scientific
  notation. A currency total is the single most likely thing a person aggregates.
- `SELECT min(booked_on)` on a DATE column returns **`2024-01-01 00:00:00.0`** — a midnight that does
  not exist in the data. The column has no time.

Fix belongs with `QueryResultDto` carrying column types and `rowsOf()` rendering faithfully. Deferred
only because `AnalyticsQueryService` is being refactored by the engine agent in wave 1.

## Wave 1 — done 2026-09-08

Backend 845 → **943** tests. Frontend 765 → **768**. Both builds clean. V31–V34 apply to a real
Postgres in order.

**Closed:** the `AnalyticsEngine` seam; all six spec lifecycle states plus REFUSED; real
user-initiated cancellation, reachable from the UI; `analytics_analysis`, `analytics_dashboard`,
`analytics_dashboard_widget` (V34) with services and endpoints; `analytics_dataset` stops being dead
schema; config raised to 14's values (timeout 30→120, max-rows 10,000→100,000) with the three missing
keys added; an analytics health indicator; `analytics.enabled` as a real switch.

**Five defects the adversarial pass found and this session fixed**, each with a regression test:

1. **Cross-tenant oracle in the query registry.** `RunningQueries` keyed one global map on the
   client-supplied id, so "A query with that id is already running." answered *is this id live in
   another workspace?* — the exact oracle `cancel()` twelve lines below spends a paragraph closing.
   Worse, a stranger holding an id blocked its rightful owner, who could not clear it because
   `cancel()` correctly refuses a handle that is not theirs: a denial of service on a namespace,
   delivered by the one method being scrupulous. Now keyed on (tenant, user, id). The reviewer's two
   probes asserted the defect; they are inverted into regressions.
2. **`analytics.enabled` switched nothing.** Property, three guard methods, zero callers — so
   `false` left all endpoints serving while the health check reported the feature off. An operator
   killing analytics mid-incident got a green confirmation of a state that was not true. Wired at all
   six controllers (two of which landed in the same wave and no handoff could have listed), pinned by
   a test that asserts nothing reaches the engine, with a control proving it still serves when on.
3. **A cancelled query was reported to the user as "failed".** The template's `@default` swept
   CANCELLED and TIMED_OUT into the one word the comment six lines above forbids for REFUSED. Every
   state now has its own word, and there is no default.
4. **Cancellation was unreachable.** Built, tested, and no user could get to it — the client never
   named the run, so there was nothing to stop. The client now mints the id (forced by the endpoint
   being synchronous), and there is a Stop control.
5. **Deleting a saved query silently deleted dashboard tiles.** V34's `ON DELETE CASCADE` changed an
   endpoint whose owner could not see the change. Handled explicitly now — and it has to be, because
   the cascade is keyed on (id, tenant_id) and Postgres does not enforce a composite foreign key
   with a null column, so it never fired for a platform admin.

**Still open from that review, deliberately:**

- **max-rows at 100,000 on an un-streamed path.** Measured: 12.9 MB of JSON and 61 MB of heap for
  one response at ten columns, against four concurrent queries in the JVM that also runs ETL. The
  spec's value shipped; the streaming that would make it safe did not.
- **The engine seam over-claims swappability.** `DuckDbAnalyticsEngine` is `@Service` with no
  conditional, so a second implementation fails the context; `AnalyticsQueryService` still takes a
  `DuckDbSessionFactory` and has an `instanceof DuckDbAnalyticsEngine`. The javadoc is honest about
  the data crossing the seam; the wiring is not yet honest about bean selection.
- **Scientific notation and phantom midnights.** `sum(amount)` returns `7.466125E7`; a DATE returns
  `2024-01-01 00:00:00.0`. Same root as 09's unmet "typed column metadata".
- **The master changelog cannot build a database from scratch** — it fails at V12 because early
  changesets assume Hibernate `ddl-auto` ran first. Pre-existing and unrelated to analytics, but it
  means no CI job can verify a migration from empty.

## Wave 2 — the Analytics Canvas — done 2026-09-09

Backend 943 → **1064**. Frontend 768 → **895**. Document 07 goes from 2 of 48 to substantially built:
1/2/3 dimensions, all eight aggregations, all fourteen filter operators with nested AND/OR, Top-N with
a real roll-up, drill-down and drill-up with server-composed crumbs, pivot, cross-filtering, saved
analyses. Plus 20 integration tests that read real objects from the MinIO and LocalStack running here,
and the typed-column metadata 09 asked for.

**Seven defects found by the adversarial pass, all reproduced, all fixed:**

1. **A dataset value spelled "Other" collided with the roll-up, and the pivot silently dropped one.**
   Measured: 500 vanished from a 740 total with nothing on the response saying a row had gone. The
   cause was a comment that read as a safeguard and was the defect — "the marker column is what tells
   them apart, and it never leaves" — because it never left, nothing downstream could tell them apart,
   including the pivot builder in the same class. Roll-up rows are now tracked by index.
2. **Top-N's "Other" reported only the LAST roll-up row** with two or three dimensions, so members
   were undercounted and some were named nowhere. Merged across every roll-up row.
3. **`other.valueCount` was short by one** whenever the no-value group was rolled up: `list(DISTINCT)`
   includes null and `count(DISTINCT)` does not, so the response shipped a four-element list beside a
   count of three and flagged nothing. The existing test asserted the wrong number and was corrected.
4. **Every value-bearing filter on a TIME column failed**, and `explain()` told the user their file
   was malformed — the application blaming customer data for a binding bug. `java.time.LocalTime` is
   refused by duckdb_jdbc 1.1.3. Measured while fixing it: `java.sql.Time`, the obvious repair, binds
   without complaint and **matches nothing**, which is worse. Bound as validated text with an explicit
   `CAST(? AS TIME)`, since text compares implicitly for `=` and not for `>`.
5. **TIME rendered without its seconds** — 14:30:00 came back as "14:30" — the same defect class as
   the phantom midnight, from the method rewritten to stop doing exactly that.
6. **Deep filter nesting was a StackOverflowError inside Jackson** before the depth guard ran. An
   Error passes every catch. Jackson 2.11 predates StreamReadConstraints, so a byte ceiling at the
   filter is the honest guard — it does not pretend to be a depth check, and the depth rule still runs.
7. Top-N plus `max-rows` can still cut the Other row; recorded, not fixed.

**What the pass could NOT break**, stated because it is the point of doing it: 25 injection payloads
through the real compiler into a real DuckDB all produced byte-identical parameterised SQL; field
names are an allow-list derived from the data itself, so a request cannot contribute even the case of
an identifier; the governed path, the tenancy checks and StatementGate all hold behind the new
composer.

**Two environment findings worth more than they look:**

- **The eight existing `*IT.java` classes have never run in the build.** Surefire's default includes
  do not match `*IT.java`, the pom configures neither includes nor Failsafe, and `mvn -o package`
  stops before `verify`. Confirmed by the absence of any surefire report for them.
- **V34 had never been applied to the local database**, which contradicts this file's earlier claim.
  That claim was true of a throwaway scratch database and not of `etl_job`; under `ddl-auto=validate`
  the application would not have started. The new Postgres integration test found it on its first run
  and now catches that class of drift automatically.

**Also closed this wave, from V2's reliability row:** write-back no longer silently overwrites — a
millisecond stamp plus an existence check that fails closed, with `overwrite=true` honoured.


## Benchmark evidence — recorded through the harness, 2026-09-09

Document 16's last failing gate. Previously the table held zero rows and the only measurement
existed in a chat log, which is not evidence a system holds.

Run through `POST /analyticsBenchmark.json/runBenchmark`, against the fixtures in
`etl-bucket/analytics-benchmark/`, on the deployed stack:

| Label | Measure | Format | min | median | max | runs | warmups | sessions/run | bytes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| csv-vs-parquet-10mb | QUERY | CSV | 236 | **242** | 260 | 5 | 2 | 1 | 9,707,067 |
| csv-vs-parquet-10mb | QUERY | PARQUET | 43 | **50** | 68 | 5 | 2 | 1 | 2,390,395 |
| csv-vs-parquet-100mb | QUERY | CSV | 991 | **1001** | 1175 | 5 | 2 | 1 | 98,571,749 |
| csv-vs-parquet-100mb | QUERY | PARQUET | 112 | **117** | 163 | 5 | 2 | 1 | 23,792,311 |
| file-open-100mb | FILE_OPEN | CSV | 1261 | **1290** | 1421 | 3 | 1 | 3 | 98,571,749 |
| file-open-100mb | FILE_OPEN | PARQUET | 117 | **132** | 134 | 3 | 1 | 3 | 23,792,311 |

**Parquet is 4.8x faster at 10 MB and 8.6x at 100 MB on a GROUP BY**, and 9.8x on a whole file
open. So the advice the product already gives users — *"Try a narrower dataset, or Parquet instead
of CSV"* — is true on this deployment, at both sizes, for both kinds of work.

Three things the rows record that a bare duration would not, and each was a stated design goal:

- `sessions_per_run` is **3** for FILE_OPEN and **1** for QUERY. That is the confound document 12
  warns about, carried on the row rather than left for a reader to trip over: a file open spends
  the per-session cost three times, so the two measures are not comparable and `measured_what`
  says so in words.
- `limits_at_run` captures `maxRows=100000, timeoutSeconds=120, maxConcurrent=4,
  duckdbMemoryLimit=512MB, duckdbThreads=2`. Numbers taken under different ceilings are not
  comparable, and these were taken after the ceilings moved.
- `dataset_bytes` is populated, which also confirms the alias-versus-bucket-name fix: that lookup
  used to be handed a bucket name where the storage service wanted a connection alias, and the
  column silently came back null — whose documented meaning is "this was a glob".

**Still not measured**, and the matrix says so honestly: only MinIO (no second provider), only two
of document 12's ten operations (full scan/aggregation), no 1 GB tier, and no JSON/NDJSON.

## The changelog cannot build a database from scratch (diagnosed 2026-09-09)

Previously recorded as "fails at V12". That understates it: **fifteen core tables are created by no
changeset at all** — they exist only because `ddl-auto=update` made them once. Under stage and
prod's `validate`, a fresh database has never been possible. Full diagnosis, all five blockers in
order, and a reproduction recipe in `LIQUIBASE-FROM-SCRATCH.md`. **Not fixed**: the real fix is a
squash, and it encodes decisions about what a fresh environment should reproduce that belong to
whoever owns the schema. A tested, idempotent baseline is kept at `liquibase-baseline/` for
whoever does it.

## Five reports, built and run (2026-09-09)

The module used rather than unit-tested. Five dashboards, twenty-seven widgets, over the real
150,000-row dataset, written to the live database and owned by `admin@platform.local`
(ids 1034-1038). **Every one of the 27 widget configurations was posted to `/analyze` against real
MinIO and had to return rows** — 27 real DuckDB scans — before being saved. The assertion caught a
design flaw in my own first draft: a tile for "orders with no note" would have drawn an empty chart
forever, because every row in this dataset carries one.

Full inventory, verification table and removal SQL in `REPORTS.md`.

## Reports / Analytics end-to-end review (2026-09-09)

Seven findings, four of them previously unknown — including that **CSV money is read as DOUBLE
while Parquet keeps DECIMAL**, found by independently validating the engine's arithmetic against a
hand parse of the source file. Full review, evidence and priority order in `REPORTS-REVIEW.md`.

Delivered: a 250,000-row × 21-column sample dataset in the bucket, ten independent-validation
assertions against it, and twenty reports of 106 widgets — every widget proved to run against the
real object. Not started: the UI/UX work, and the widget types that need wiring (line, area,
stacked, histogram, KPI card).

## Live updates, chart palette and the widget tile (2026-09-14)

Five areas investigated in parallel, 32 findings verified, all acted on except the five listed as
deliberately open. **The socket transport was never at fault** — it was verified healthy end to end
at runtime — and almost nothing was ever published to it.

Delivered: status now announced from `BulkAction.changeJobStatus`, the one method all nine writers
pass through; the run-logs screen subscribed to `job.log` and its poll fixed (it had re-armed
exactly once); `publishChanged` wired to create/update/toggle/delete **after commit**; timestamps
read in the zone the application pins for itself rather than in the reader's own -- correcting an
investigation finding that was WRONG and a first fix shipped on it, which made the jobs list report
healthy runs as stalled; the scheduler stopped from running real jobs out of every test run; an eight-colour categorical palette that is no
longer the status ramp; the widget tile's hidden rows made reachable without a second query; height
and caption on `widget_config` with no migration; `rankedShare` and `cumulative` added; a legend for
stacked bars.

Verified: backend 1242 unit + 102 E2E, frontend 1248 unit, Playwright 45 — all green, every fix
mutation-proven. Full account in `REALTIME-AND-UI-SWEEP.md`.

## Job assistant QA (2026-09-14)

Fifty-plus cases over `/jobs/:jobId/assistant`. Eleven defects, all fixed, each mutation-proven.

The pattern table was the problem, and the consequence of a miss was the part nobody had costed:
an unrecognised question is handed to a configured AI agent, so a gap in the table did not degrade
to "I don't know" — it degraded to a model answering about a job whose real figures were one match
away. Worst of them: the scope guard required a three-digit job id, so **"tell me about job 99" was
answered with a summary of the job in view**, and "what about job 12" went to the model with that
job's facts attached.

Delivered: the scope guard split so the word "job" admits any id length while a bare `#` keeps its
floor; plural "jobs" read as fleet-wide; `\bstat` bounded so it stops matching "state" and "status";
history read before target so "the log file" is runs, not a bucket; failures read before stats;
new `capability` and `action` intents so a greeting and "run it now" are answered here rather than
by a model that cannot act; sixteen plain phrasings routed to answers that already existed;
`priority` shown, having been collected and rendered nowhere. Component: the reload effect no longer
depends on the agent list — it was **fetching the job twice per load and wiping the transcript**;
Enter now respects the in-flight guard the Ask button already had; an empty success body shows an
error rather than a blank page.

Verified: frontend 1445 unit (1378 before), all green; `next-app` rebuilt and checked on the running
app — one job fetch per load, nine previously-broken phrasings answered locally. Two non-defects
recorded so they are not chased again. Full account in `JOB-ASSISTANT-QA.md`.

## RAG, Redis and the file chat (2026-09-14)

Reported as "we are not creating the vector data", with the PDF chat named. The vectors were being
created correctly -- 225 chunks, all with a real 768-float L2-normalised embedding. **The text in
them had been silently destroyed since the feature shipped.**

The `_bulk` body went out as `application/x-ndjson` with no charset, and Spring's
StringHttpMessageConverter special-cases UTF-8 only for types compatible with `application/json`,
so it fell back to ISO-8859-1. Characters above U+00FF became `?`; characters in U+0080..U+00FF
became a byte that is not valid UTF-8, so OpenSearch rejected that document and the chunk vanished
mid-file. The tell: across 225 chunks of CVs, PDFs, CSVs and Markdown, not one character above
U+007F, and 108 question marks.

Delivered: the charset; a bulk reporter that counts what was actually stored and names the lost
chunk indexes, replacing a single WARN that named nothing and returned void; completeness derived
from chunkIndex contiguity rather than from a document count that agrees perfectly with an index
that has a hole in it; a real filtered k-NN query in place of dragging every chunk's 768 floats
over HTTP (229 KB per question); `isAvailable()` no longer running three real inferences per
message; bounded embedding batches so a 588-chunk file is no longer unindexable forever; a Redis
outage degrading to a cache miss instead of a 500, including the FTP listing cache that bypasses
the handler; cache eviction on upload/delete/rename; `json_mode` actually reaching the provider;
the agent's vision model and instructions reaching the model that looks at an image; a failed
vision call no longer cached as the file's text and embedded into the index; and emailing a chat
export through the existing FileShareService rather than a second copy of its rules.

Verified: backend **1392**, frontend **1457**, both green; 50 new tests; the charset and contiguity
fixes both mutation-proven. Both containers rebuilt and healthy.

Proven end to end on the deployed stack: one file's chunks were deleted, a question re-indexed it,
and the same 20 chunks came back carrying **84 characters above U+007F and zero question marks**,
against 0 and 84 before -- every destroyed character restored, exactly.

**Open:** 205 chunks in the live index are still Latin-1 damaged. The fix stops new damage but does
not repair what is stored, because a chunk set is only rewritten when a file's etag changes or its
chunks are removed. Repairing them means a deliberate reindex. Full account in
`RAG-CHAT-REVIEW.md`.

---

## 2026-09-15 — Run retry with backoff

**Why this and not something else.** Asked what else the ETL platform could gain, the honest answer
was a ranked list with job *dependencies* at the top. Reading the dispatcher first changed the
order: retry is the smaller change, is strictly additive, and is the safe way to touch the most
load-bearing code in the platform once before doing the larger thing to it. Dependencies remain
first by value and are now second by sequence.

**What landed.** A failed run is re-queued with a doubling backoff, capped at an hour, before
anything announces a failure. Policy is per job — `max_attempts` (default **1** = no retry, the
behaviour every existing job had) and `retry_backoff_seconds` (default 60), both bounded by CHECK
constraints and by `SourceJobServiceImpl.retryPolicyError` so an out-of-range value is a sentence
rather than an internal error. Schema `V38.0-job-retry`. Form controls on the job editor.

**A prediction in the plan was wrong, and the record should say so.** The plan named the danger as
"a pending retry eats the next scheduled run" and proposed excluding retries from the busy count.
That was backwards twice over. The skip is *correct* — the busy count is what stops two workers
writing the same output folder, and a retry is the same slot's work, so it must keep occupying the
slot. The real defect was elsewhere: `findAllJobForTodayWithLimit` takes any Queue row with
`job_send = false`, so a retry would have dispatched on the very next tick with its backoff
ignored entirely. That is the query that changed, and its cutoff is passed from Java rather than
read as SQL `now()`, because the database is UTC while the application pins America/Chicago.

**A real bug that only a live run caught.** Retry was first wired to
`MessageQServiceImpl.changeJobStatus`, found by grepping `JobStatus.Failed` and reading the first
plausible match. All 1422 tests passed and the feature did not work: the live worker reports through
**`NotifyServiceImpl.changeState`**, a file that appeared in the very first grep and was never
opened. A real run of an always-failing job went straight to Failed at attempt 1 and mailed about
it. Four sites mark a run Failed and three have nearly identical shape; they are now enumerated in
`discovery/module-workflows.md` §4.6, and `NotifyServiceRetryTest` exists so the gap cannot reopen
silently.

**Verified.** Backend **1428** green (17 new), frontend **1545** green. Five mutations caught,
including the one that proves the failure email is suppressed while a retry is pending. Migration
applied live and its CHECK constraint proved by a rejected insert in a rolled-back transaction. The
backoff filter proved against real Postgres: a retry due in five minutes excluded, one due a minute
ago taken, an ordinary run unaffected.

**Proven end to end on the deployed stack.** Job 2410, built to fail, at three attempts and a
five-second base: attempt 1 failed at 12:40:15, attempt 2 at 12:41:15 (backoff doubled 5s → 10s),
attempt 3 at 12:42:15, then Failed with an end time — and **exactly one email for the three
attempts**, against one per attempt before. Control job 2411 at the default single attempt failed
immediately with `attempt = 1` and `next_attempt_at` null, confirming unchanged behaviour for every
job nobody has opted in.

**Open.** Job dependencies (`dependsOn` plus a gate in dispatch stage 2) is the next step and the
dispatcher is now read closely enough to do it. Left as test data: job 2410 at 3 attempts / 5s, job
2420 at 3 attempts, and runs 5705–5707.

## 2026-09-15 — Read a transcript aloud

The transcript tool can now read its output back, marking the spoken word in yellow and tinting its
passage, so the text keeps the reader's place while they check it against the audio.
`shared/ui/read-aloud.service.ts` is the counterpart of `dictation.service.ts` and is kept beside
it; `read-along-text.ts` renders the mark and is shared by all three transcript views.

Two decisions worth keeping: **one passage per utterance**, because boundary events report a
character offset and an offset into one passage is directly usable while an offset into a
concatenation of forty must be mapped back (and because Chrome truncates long utterances); and the
mark is positioned **by offset rather than by matching the word**, because the same word appears
several times in most passages and matching by content marks the wrong one.

**Verified against the real engine, not only the fake** — the fake proves logic, it cannot tell you
the browser agrees. 180 voices; nine word-boundary events for a nine-word sentence at exact offsets;
the mark tracking the voice across line wraps on a real 6-minute transcript; pause holding the place;
stop-while-paused leaving the engine able to speak again (the resume-before-cancel guard, which some
engines need); and navigating away silencing it. Contrast measured rather than eyeballed: the marked
word is **13.3:1** in light and **11.4:1** in dark. The dark-mode timestamp *looked* too dim and
measured 4.88:1 — it passes, and would have been "fixed" on a hunch without the measurement.

**34 new tests, 1545 green.** Four mutations caught, including trusting a reported word length of
zero (which collapses the highlight to one letter on Safari) and dropping the stale-generation guard.
