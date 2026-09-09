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
| Architecture — remove duplicated services | PARTIAL | StorageService reused rather than copied; a second charting/dashboard stack refused (synthesis 3.11). "Simplify abstractions" not attempted. |
| Architecture — verify dependency boundaries | PARTIAL | `process.analytics` now reaches `process.model.service.StorageBrowserService` (AnalyticsBenchmarkService) — a new direction, flagged by its author, never reviewed. |
| Architecture — inspect query plans | MISSING | No EXPLAIN/plan inspection anywhere. |
| Security — penetration-style authorization tests | PARTIAL | Real: the `schema_name` cross-bucket exploit, the cross-tenant resolver bug, the StatementGate evasion corpus. Not systematic. |
| Security — secret scanning | MISSING | Never run. |
| Security — tenant-isolation review | DONE | DatasetResolver `isOwnedByCaller` + `Status.Active`; per-entity `@Filter`; the findById trap handled via scopedFind. |
| Security — audit completeness | PARTIAL | Query attempts incl. refusals recorded. "Dataset opened" and "profile requested" write only a log line. |
| UX — visual consistency | PARTIAL | Tokens throughout, no raw hex. No systematic pass. |
| UX — accessibility | MISSING | No audit, no automated check. |
| UX — keyboard navigation | MISSING | Only CodeMirror's Ctrl/Cmd+Enter. |
| UX — responsive behaviour | PARTIAL | Mobile checked once by hand; container queries for the rails. |
| UX — loading/error/empty states | DONE | Four dataset-pane states, four chart empty states, distinct quality empties. |
| UX — dense data-table ergonomics | MISSING | The Data view is a page-turner: 2 of 06's 8 grid capabilities. |
| Performance — benchmark regression suite | MISSING | Harness exists; no suite, and it has never been run. |
| Performance — profile expensive queries | MISSING | One agent profiled chart parsing. Nothing else. |
| Performance — optimize high-cardinality analytics | MISSING | No Top-N/high-cardinality path exists to optimise. |
| Performance — verify cancellation | BLOCKED | Cancellation does not exist. |
| Performance — optimize storage reads | PARTIAL | `knownTotal` removed the repeat COUNT on every page turn. |
| Reliability — retry policy for transient storage errors | MISSING | No retry anywhere in the analytics path. |
| Reliability — idempotent export/write | MISSING | Known defect: a one-second filename stamp, so two write-backs in the same second silently overwrite. Found and not fixed. |
| Reliability — cleanup of temporary resources | MISSING | No TTL, no cleanup job. |

## Document 16 — implementation checklist (audited inline 2026-09-08)

Final gate, verbatim from the document, with the truth beside it:

| Gate | Status |
|---|---|
| backend build passes | DONE — `mvn -o package`, 845 tests |
| frontend build passes | DONE — `ng build` clean, 765 tests |
| migrations pass | DONE — V31/V32/V33 applied to real Postgres; four tables live |
| all critical tests pass | DONE for what exists; no integration or E2E tests exist to pass |
| **actual benchmark evidence captured** | **FAILS — `analytics_benchmark_result` holds 0 rows** |
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
