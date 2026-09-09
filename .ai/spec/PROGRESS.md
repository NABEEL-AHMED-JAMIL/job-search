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
| Architecture — remove duplicated services | PARTIAL, improved 2026-09-09 | StorageService reused rather than copied; a second charting/dashboard stack refused (synthesis 3.11). **The `AnalyticsEngine` seam is now real rather than paper**: the DuckDB bean was an unconditional `@Service`, so a deployment supplying its own engine got a `NoUniqueBeanDefinitionException` and no context at all — it is now `@ConditionalOnProperty(analytics.engine=duckdb, matchIfMissing=true)`. And `AnalyticsQueryService.shutdown()` reached for the engine with `instanceof DuckDbAnalyticsEngine`, so the seam covered every method except the one stopping the background thread; `shutdown()` is now on the interface. "Simplify abstractions" still not attempted. |
| Architecture — verify dependency boundaries | PARTIAL | `process.analytics` now reaches `process.model.service.StorageBrowserService` (AnalyticsBenchmarkService) — a new direction, flagged by its author, never reviewed. |
| Architecture — inspect query plans | MISSING | No EXPLAIN/plan inspection anywhere. |
| Security — penetration-style authorization tests | PARTIAL | Real: the `schema_name` cross-bucket exploit, the cross-tenant resolver bug, the StatementGate evasion corpus. Not systematic. |
| Security — secret scanning | **DONE 2026-09-09** | gitleaks over the git HISTORY of both repositories (a working-tree scan calls two of the three `process` findings clean, because the files no longer exist in HEAD). Nine raw findings triaged to three real; five false positives allowlisted with the reason beside each. `.ai/tools/secret-scan.sh` fails when the count goes up, and is proved to by mutation. Full triage in `SECRET-SCAN.md`. **Two exposures were previously unknown: an RSA private key (2024) and a Google OAuth client secret (2022), both in pushed history.** All three need rotation, which is not something a commit can do. |
| Security — tenant-isolation review | DONE | DatasetResolver `isOwnedByCaller` + `Status.Active`; per-entity `@Filter`; the findById trap handled via scopedFind. |
| Security — audit completeness | **DONE 2026-09-09** | Schema, preview and profile now write a history row too, successes AND refusals — before this, "who read this file" was answerable for the SQL console and not for the nine other tabs, which is how the file is actually read. The descriptor is a SQL comment (`-- preview page=3 sorted searched`) so it can never be read back as a statement, and it names the FACT of a search without the search term: filter values are the reader's own data. Verified against the live stack — 38 rows written by one E2E run, with row counts and durations. Five tests. **This makes the missing TTL cleanup below more pressing, not less: a reader paging a 1,500-page dataset now leaves 1,500 rows and nothing removes them.** |
| UX — visual consistency | PARTIAL | Tokens throughout, no raw hex. No systematic pass. |
| UX — accessibility | MISSING | No audit, no automated check. |
| UX — keyboard navigation | MISSING | Only CodeMirror's Ctrl/Cmd+Enter. |
| UX — responsive behaviour | PARTIAL | Mobile checked once by hand; container queries for the rails. |
| UX — loading/error/empty states | DONE | Four dataset-pane states, four chart empty states, distinct quality empties. |
| UX — dense data-table ergonomics | **DONE — the audit was stale, not the feature missing** | Re-checked against document 06 line by line: all EIGHT Data-view capabilities are built — pagination, column resize, sorting, filtering, search, column visibility, copy cell, horizontal scroll. The "2 of 8" figure predates the sort/search/filter work and was carried forward without re-reading. Now pinned by five E2E tests so the number cannot go stale again in the other direction. One real fix found while writing them: the screen-reader caption said "1 rows of 1 columns". |
| Performance — benchmark regression suite | **DONE 2026-09-09** | The harness measured; `BenchmarkRegression` now NOTICES. Every run compares against the best median on record for the same label/measure/format/path, and the endpoint says so in its own message rather than only in a log on a server. **Baseline is the BEST on record, not the previous run** — against the previous run, two runs each 15% slower are each inside a 25% tolerance and the pair is 32% slower than where it started. A FILE_OPEN is never compared with a QUERY (three sessions against one) and CSV is never compared with Parquet (that comparison is the point of the harness). Ten tests, including the trap that a run reading history back after writing finds itself as its own baseline. Reports rather than throws: these are timings from a real network on whatever machine ran them. |
| Performance — profile expensive queries | MISSING | One agent profiled chart parsing. Nothing else. |
| Performance — optimize high-cardinality analytics | MISSING | No Top-N/high-cardinality path exists to optimise. |
| Performance — verify cancellation | **DONE — row was stale** | Cancellation exists and is real: `RunningQueries.Handle`, a single watchdog thread, `Statement.cancel()` (measured working on 1.1.3 where `setQueryTimeout` is a no-op), QUEUED→RUNNING transitions that honour a cancel arriving while queued, and cancel-before-close ordering. Re-verified 2026-09-09. |
| Performance — optimize storage reads | PARTIAL | `knownTotal` removed the repeat COUNT on every page turn. |
| Reliability — retry policy for transient storage errors | **DONE 2026-09-09** | One retry, and only for the BUILT-IN reads (schema, preview, profile) — user SQL is not retried, because that caller holds a run id and may be watching a stop button. A fresh session per attempt, since the broken thing IS the connection to the object store. Classified narrowly: connection resets and 5xx/429/`SlowDown` retry; 401/403, 404, parser errors, malformed CSV, memory pressure and timeouts do not. **The classifier test found a real bug: S3's throttling code is `SlowDown`, one word, and the spaced check matched nothing.** Eleven tests, proved load-bearing by mutation. |
| Reliability — idempotent export/write | **DONE 2026-09-08** | Two mechanisms, because the cost of being wrong is somebody's data: the stamp went to milliseconds, and `refuseToOverwrite` asks the platform's own storage service whether the key is taken before writing. `overwrite=true` is honoured — replacing yesterday's export on purpose is a real thing to want; doing it by accident is not. Fails CLOSED: an unreadable answer refuses the write rather than assuming the key is free, which would restore the clobber precisely when the store is unhealthy and it is hardest to notice. Four tests, proved load-bearing by removing the guard and watching the two refusals fail while the two controls stayed green. |
| Reliability — cleanup of temporary resources | **DONE 2026-09-09, and smaller than the row implies** | Audited first: DuckDB deliberately writes no temp files (`preserve_insertion_order=false`, no temp directory — DuckDbSessionFactory:103), and `RunningQueries.inFlight` cannot leak because `close()` is the only removal and sits in an outer `finally` covering completion, failure, timeout, cancellation and a caller who never got a permit. The one thing that grows is `analytics_query_run`. A retention cron now exists (`AnalyticsHistoryCleanupCron`, ShedLock, hourly) — **defaulted OFF**, because V32 argued deliberately for leaving that table unpruned and named the condition that would change its mind (a machine issuing queries on a schedule), which read-auditing is not. Mechanism shipped, policy left to whoever owns the audit question. Five tests; the default-off test was rewritten after mutation showed the first version did not guard the default at all. |

## Document 16 — implementation checklist (audited inline 2026-09-08)

Final gate, verbatim from the document, with the truth beside it:

| Gate | Status |
|---|---|
| backend build passes | DONE — `mvn -o package`, 1,098 tests, 0 failures |
| frontend build passes | DONE — `ng build` clean, 1,065 tests |
| migrations pass | **CORRECTED** — V31/V32/V33 were applied; V34 was NOT, and this line claimed otherwise. The claim was true of a throwaway scratch database, not of `etl_job`. Now applied; seven analytics tables live, and a Postgres integration test guards the drift. |
| all critical tests pass | DONE. Backend 1,098 / frontend 1,065, both clean. **E2E now exists** — 8 Playwright specs over the real 150,000-row fixture, all passing, one proven load-bearing by mutation. **The 20 analytics integration tests do run in `mvn package`** — they are named `*IntegrationTest`, which matches surefire's default includes, and re-running them under `-Danalytics.it.required=true` (which turns "infrastructure absent" from a skip into a failure) passes with real HTTP reads logged against MinIO :9000 and LocalStack :4566. Separately, eight pre-existing non-analytics `*IT.java` classes never run: surefire's defaults do not match `*IT` and there is no Failsafe plugin. |
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
