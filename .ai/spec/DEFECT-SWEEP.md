# Platform defect sweep — 2026-09-14

Seven areas investigated in parallel, every finding then adversarially verified by a second pass
whose job was to REFUTE it. **66 candidates, 58 survived, 8 refuted and discarded.** The refuted
ones are not listed here on purpose: a document that records disproven claims alongside real ones
is a document whose reader has to re-do the triage.

Severity after verification: 11 critical, 30 major, 15 minor, 2 gaps.

| area | found | what it was |
|---|---|---|
| SQL multi-dataset | 7 | a saved JOIN lost half its inputs, at four independent points |
| source jobs | 13 | statuses discarded, schedules saved nowhere, dispatch killable by a typo |
| reports | 12 | numbers that were not true, in both report surfaces |
| widgets | 11 | charts that drew the wrong question, and kinds that existed unoffered |
| pipeline form | 6 | a dropdown could not have a key distinct from its label |
| RAG | 4 | real embeddings, real `knn_vector` mapping, and nothing ever queried it |
| general sweep | 5 | mostly in the newest, least-reviewed uncommitted code |

---

## 1. A saved SQL query that joins two files

**The second dataset was dropped FOUR times between the Studio and a dashboard tile, and any one
of them alone was fatal.** The Studio's save never read it; `analytics_query` had no column to put
it in; the dashboard tile posted a one-dataset body; and the engine, given no second dataset,
never created the `dataset2` view. The tile then sat permanently red showing DuckDB's own words:

> Catalog Error: Table with name dataset2 does not exist!

— a sentence naming a view the reader never created, on a query that ran perfectly the day it was
saved.

Two further losses the investigation turned up:

- **Reopening a saved join restored no second dataset**, so it silently read whatever second file
  happened to be selected. That is the one path that returned a WRONG ANSWER rather than an error,
  and it is why `loadSaved` now restores the second dataset while deliberately still not moving
  the first: the first is a file the reader can see in the picker, the second is named only inside
  the statement.
- **The audit row recorded one location for a query that read two.** `analytics_query_run` exists
  to answer "who read what", and for every join it was giving a wrong answer rather than an
  incomplete one.

Fixed across `V35`, `AnalyticsQuery`, `AnalyticsQueryLibraryServiceImpl`, `analytics.service.ts`,
`analytics.ts`, `dashboard.ts`, `AnalyticsRestApi` and `DuckDbAnalyticsEngine`. The second dataset
is validated as a PAIR at every layer — both or neither — because a path with no connection cannot
be resolved and a connection with no path names no file; the table enforces it as a CHECK too.
The engine now refuses a statement naming `dataset2` with none given, in words, before DuckDB gets
the chance to answer in its own.

## 2. Why the RAG has no vector search — the actual answer

The question was "why are we doing RAG without a vector database". The answer is more specific
than the question assumed, and all three parts matter:

1. **Embeddings are real.** Ollama `nomic-embed-text`, 768 dimensions, a genuine neural model —
   not a hash, not a stand-in.
2. **The index really does declare `knn_vector`, with `index.knn: true`.**
3. **Nothing ever queries it.** Retrieval issues a plain `term` filter, pulls back every chunk of
   the file *including all 768 floats each*, and ranks them with a hand-written cosine loop in
   Java. OpenSearch is a blob store; the HNSW graph is decoration. Dropping `index.knn` from the
   mapping today would not change a single answer.

**Making it real k-NN needs a REINDEX, which is why it was not done as part of a bug fix.** A
`knn_vector` field's `dimension` and `space_type` are fixed when the mapping is created, and
`index.knn` cannot be added afterwards. The full plan — the `method` block pinning
`space_type: cosinesimil`, the filtered `knn` query (supported natively on the deployed 2.10), and
the reindex — is written into `OpenSearchRagClient`'s class javadoc.

**A latent trap found on the way:** the mapping omits `method` entirely, so the graph that does get
built silently uses the default `l2` — Euclidean, not the cosine every comment in the class talks
about. Invisible while nothing queries the graph; wrong the moment something does.

Also corrected there: a claim in the old comment that the index was "ready for a cross-file search
built later without a reindex". It was not. Removed rather than softened.

## 3. Source jobs

The area with no reported symptom, and the one with the most defects. Three classes:

**The console asked for something the backend discarded.** `addSourceJob` and `addSourceTask` hard
-coded `Status.Active` and threw away the status the console sent — so both "Copied — it starts
inactive" flows and the create-as-Inactive form produced live, immediately-scheduling rows.

**Jobs that stopped existing as far as the scheduler was concerned.** `updateSourceJob` only ever
UPDATED a Scheduler row, never created one, so switching a Manual job to Auto saved the timetable
nowhere and answered "Job updated." And a queued run whose task had no source task type fell off
the end of the dispatcher with no status change and no audit line — stranded for ever, while the
"already in queue" count blocked every future run of that job.

**A platform-wide kill switch reachable by a typo.** `QUEUE_FETCH_LIMIT` was parsed with an
unguarded `Long.valueOf` inside a catch-all. Typing `5,000` in the settings screen stopped job
dispatch for the whole platform, silently, every cycle.

**The weekday bug is a data-shape decision worth knowing about.** The rewritten console wrote day
codes `'1'..'7'`; the engine only ever parsed `MON..SUN`; the legacy console wrote `MON..SUN`. So
`scheduler.days_of_week` holds BOTH vocabularies today, written by two shipped clients, and every
"Weekly on Mon, Wed" from the new console silently degraded to one run a week. Fixed by teaching
the engine to read both and the console to write the canonical form — **not** by a backfill, since
a partial or failed backfill leaves jobs mis-scheduled again, which is the exact failure being
repaired.

> **Deploy note:** a job stored as `"1,3"` was running once a week. After this it runs on Monday
> AND Wednesday. That is the repair, and it is a live schedule change.

## 4. Reports — the empty cell and the zero cell

Every one of these showed a reader a number that was not true, which is the worst defect class in
a reporting tool: invisible, and acted upon. The organising principle for all of them is that **an
empty cell and a zero cell must be distinguishable.**

- The CSV export wrote `0` into every cell the on-screen grid showed as `—`, so the file
  disagreed with the screen.
- A duration total printed `0s` for a group whose runs had no recorded duration — which reads as
  "instant" rather than "unknown".
- The pivot's drill button tested "is the number zero" when the question is "is there anything
  behind it". Those part company **in both directions**: a cell whose runs all finished inside a
  second measured a real 0 and could not be opened.
- The donut's centre summed the `-1` no-duration sentinel, so an unmeasurable column would have
  *subtracted* a second from the total.
- The "Failed runs" table ignored the workspace filter, so its count contradicted the tile above it.

In the analytics stack the same class of defect appeared as **two screens of one analysis
disagreeing about a number**: the Canvas printed the server's text verbatim while a dashboard tile
of the same saved analysis ran it through `readableCell`, so one read `20781905.520000000000000`
and the other `20,781,905.52`. Now both format measures and neither formats dimensions — because
grouping a DIMENSION rewrites it, and a year column was reading `2,024`.

## 5. Widgets

**Charts that drew the wrong question:**

- A dimension sorted **Z–A** — one click, and the natural choice for "newest first" — drew time
  running backwards and printed `Change −40.0% … down` over a year that rose 67%. The gate saw the
  sort AXIS but not its DIRECTION.
- A **Top-N with `includeOther` off** presented shares of a retained subset as shares of the total:
  a ring whose legend read "north 34%" where north was 11% of the data. Worse, the setting that
  makes the percentages wrong is also the setting that makes the ring available — with the bucket
  ON, the extra row trips the six-slice refusal.
- **Grains were dropped at save**, so "revenue by month" reopened and re-ran ungrained — one row
  per distinct instant, usually with no truncation banner because a year of orders is fewer than
  50,000 rows. The tile showed eight timestamps under a title that said "Monthly".
- The **Canvas cross-filter sent the drawn label as an `EQ` operand**, so clicking a Top-N "Other"
  bar asked the data for a value it does not contain and emptied the analysis. This is the same
  defect fixed in the dashboard the session before; it was still live one screen over.

**Kinds added** (both honest from the shape an analysis result already has):

| kind | what it needs | what it refuses |
|---|---|---|
| Share within each group | two dimensions, an additive measure | a group summing to zero — there is no share to show, and the plain stack draws that honestly |
| Cross-tab grid | the grid the SERVER already composes | a column dimension too wide to read, which the server refuses to build |

The cross-tab is the cheapest of the two: the server has been composing a pivot for every
two-dimension analysis all along, keyed on roll-up row indices so a real "Other" category cannot
collide with the Top-N bucket — and the dashboard read it zero times.

## 6. Pipeline form — key/value for a select

Choices live in one `TEXT` column, and there was exactly ONE parse site and ONE render site in the
whole platform, binding `[value]` and the label to the same string. That identity WAS the gap.

**Format chosen: one choice per line; the first `=` on a line separates value from label.** The
label is the unsplit remainder, so it may contain `=`, `:` or `,` with nothing escaped — which is
the case that breaks most alternatives. A line with no `=` is both halves, so every form written
before this reads exactly as it did, and an untouched form round-trips byte-identical rather than
being silently rewritten by an unrelated edit.

That legacy rule is load-bearing, not a courtesy: the task screen deletes a tag when its control
comes back blank, so a legacy line that stopped resolving to itself would have emptied every
existing task on the pipeline and dropped its answer on the next save.

**The one thing the format cannot express is `=` inside a VALUE**, so the dialog refuses it by
name rather than letting it truncate silently.

## 7. General sweep

- **A result cut by the cell budget reported itself COMPLETE** whenever the column count did not
  divide the budget. The loop stops when one more row would EXCEED the budget; the flag asked
  whether the cells collected had REACHED it. At the shipped 100,000 over three columns that is
  33,333 rows and 99,999 cells — so 33,333 rows of a 40,000-row answer came back with nothing
  saying it was partial.
- **`analytics.enabled=false` answered HTTP 500 on 24 of 32 endpoints** instead of the designed
  refusal, because `AnalyticsException` is checked and fell into each endpoint's generic catch.
  Switching analytics off looked to a user like a crash and to the operator like a stack trace at
  ERROR for a state they had just chosen. All 24 now catch it; a `@RestControllerAdvice` was added
  as well, so the twenty-fifth endpoint — the one written next year by somebody who copies a
  method — degrades to the right answer.

---

## What the guards caught, which is the point of having them

Two existing tests failed during this work and were **right to**:

- `AnalyticsQueryLibraryTest.everyMappedColumnIsCreatedByTheChangeset` read V32 alone, so it was a
  guard that worked exactly until the second changeset touched those tables. It now reads every
  changeset, which also keeps it right for V38 without anybody remembering to come back.
- `AnalyticsBoundaryTest` refused the new `GlobalExceptionHandler → AnalyticsException` import
  until it was argued in the diff. It is allowed now, narrowly, with the reason recorded.

## Still open, deliberately

- **`findSchedulerByJobId` callers in `DashboardServiceImpl` and `JobAssistantServiceImpl`** were
  not touched. The duplicate-scheduler trap is now closed at both write paths and by a unique
  constraint (V37, which applied cleanly — there were no duplicates), so it cannot be created;
  a database that already has duplicates will see V37 refuse to apply, which is the right failure.
- **`ProcessTimeUtil.stepFunction` discards `intervalValue`** for any weekly schedule naming days,
  so "every 2 weeks on Mon, Wed" runs every Mon and Wed. A genuine separate defect, left alone
  because fixing it silently changes the cadence of every correctly-coded weekly schedule.
- **Real k-NN retrieval**, per section 2 — a migration, not a code edit.
- **A non-admin with `app_user.tenant_id = NULL`** now sees nothing where it previously saw
  everything. That is the intended fix for a fail-open tenancy hole, but such an account goes from
  over-privileged to empty-screen; the root fix belongs at login.
