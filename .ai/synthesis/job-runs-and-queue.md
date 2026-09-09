# Synthesis -- Job Runs and Queue

Feature `job-runs-and-queue`, status **partial**. Reads on
[../grooming/job-runs-and-queue.md](../grooming/job-runs-and-queue.md); every section number in
`§n` form below refers to that document.

Paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

The rewrite carried this feature further than the table's `partial` label suggests: all three old
screens have successors, the run-logs screen is genuinely better than the one it replaced, and the
run history gained a drill-down, expandable failure messages and real loading/error/empty states.
What did not cross is narrower than a whole screen and mostly concentrated on the queue: the
server-side job-id and run-id filters, six of thirteen table columns, the Gantt view of overlapping
runs, and the pipeline strip on the logs screen. Those are the migration gaps, and only one of them
is large.

The work that actually has to happen, though, is not mostly migration. It is four correctness
problems that the rewrite either inherited or introduced. Two are tenancy: `QueryService.tenantClause`
returns an empty string for a caller with no tenant, so such a caller reads every tenant's queue;
and `MessageQServiceImpl` carries a private copy of the ownership rule that says yes when both
tenant ids are null, where the rest of the codebase uses `TenantOwnership` and refuses. One is a
missing server-side guard: `interruptJobLogs` will overwrite a run that finished weeks ago, and the
only thing preventing it is a hidden button. One is a broken link: the all-jobs run history builds
its Logs URL from the route's job id, which on that route is empty, so the one screen that lists
runs across jobs cannot open any of them. Alongside those sit two things the UI states as fact and
gets wrong — the queue's outcome donut counts the tenant's entire history while claiming to be
capped, and `Mark as failed` is offered on rows the server will refuse. A sixth is a fragility
rather than a confirmed defect and is recorded as unverified: the dashboard drill-down reads
`select job_queue.*` by ordinal on a table `ddl-auto=update` extends by appending, and nothing in
the code makes those ordinals line up.

The proposal is: fix the four correctness items and the two lies first; then close the queue's
filter and column gaps and add the logs link, which together make `/queue` at least as capable as
Q-Message was; then decide on the Gantt and on the dead `changeJobStatus` endpoint. Live updates,
which this feature is unusually well placed to adopt because the publisher already emits run-level
events nobody consumes, are a follow-on rather than part of the crossing.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | `QueryService.tenantClause` returns `""` when `TenantContext.getTenantId()` is null (`:212-217`), so a tenant-less non-admin reads every tenant's rows through `fetchLogs` and the dashboard drill-down | A caller with no tenant owns nothing and sees nothing | Cross-tenant read on `/queue` and `/jobs/history` | Fail closed: return a clause that matches nothing for a tenant-less non-admin. Add a test per endpoint | S | **High** — touches every raw-SQL read in the app, not just this feature |
| 2 | `MessageQServiceImpl.isJobOwnedByCaller` (`:130-137`) uses a bare `Objects.equals`, so a tenant-less caller owns platform-owned jobs; `DashboardServiceImpl:246-247` has the same shape | Both call `TenantOwnership.isOwnedByCaller` | Cross-tenant write, conditional on a null-tenant `source_job` row existing | Delete both private copies; call the shared helper | S | Low |
| 3 | `interruptJobLogs` (`:167-185`) has no status precondition; both clients hide the button instead | The server refuses a run that has already reached a terminal state | Client-only validation on a destructive, unrecoverable write | Add the precondition beside the one `failJobLogs` already has (`:149-151`) | S | Low |
| 4 | The all-jobs history's Logs link uses the route's `jobId`, empty on `/jobs/history` (`job-history.html:352-355`) | The link uses the row's `run.jobId` | Logs unreachable from the one cross-job list | One-line template change | S | Low |
| 5 | `Mark as failed` is offered on `Start` and `Running` rows (`queue.ts:259-262`) which the server refuses | Offered only where it will be accepted, as the old screen did | Danger dialog that ends in an error | Split `inFlight` into per-action predicates | S | Low |
| 6 | The queue donut is fed by a statistic that ignores date, status and id filters (`QueryService.java:455-459`), and the UI blames a row cap that does not exist (`queue.ts:160-165`) | Chart and table answer the same question, or the difference is stated correctly | A chart of several thousand over a table of forty, with a false explanation | Apply the same filters to the statistic query | S | Medium — the statistic is shared with the old app's Q-Message chart |
| 7 | `/queue` has no server-side `jobId` / `jobQId` filter; only a client search over the loaded page (`queue.ts:63-70`) | Both filters, as `queue-message.component.html:33-38` had | Migration gap; the operator's "show me this job's queue" is gone | Two toolbar inputs; the server side already works | S | Low |
| 8 | The queue table has 7 columns against the old screen's 13 (`queue-message.component.html:86-142`) | Start, End, Skip Time and the three flags are visible | Migration gap | Add columns; the fields are already on the wire | S | Low |
| 9 | The queue table has no way into a run's logs | A Logs link per row | Neither app had it; the queue is where the question is asked | One cell | S | Low |
| 10 | The logs screen has no pipeline strip (`job-logs.component.ts:285-308` had one) | The run's progress through Queue → Start → Running → terminal | Migration gap | A presentational component over `run.jobStatus` | S | Low |
| 11 | No Gantt of start→end across runs (`queue-message.component.ts:234-292`) | Overlap between runs is visible | Migration gap, and the only lost *answer* rather than lost chrome | A timeline chart in `shared/charts/`; `shared/charts/` has none | L | Medium |
| 12 | Run history renders every run with no pager (`job-history.html`) | Bounded, like the other two screens | Never present in either app | Reuse `createPager` as `/queue` does | S | Low |
| 13 | `job_queue.bucket` / `output_folder` are written at dispatch and never returned (§12.9) | A run reports where its own output went | Never present; both apps show the task's *current* bucket | Two DTO fields, two `select` columns, one cell | S | Low |
| 14 | `job-history.ts:242-249` fetches the whole job list to read one name already present in two other responses | Read the name from the payload in hand | Wasted round trip, ~30KB | Delete the call | S | Low |
| 15 | Manual fail/interrupt publish no STOMP event (§12.7); no screen here subscribes although `job.log` and `job.status` carry `jobQueueId` | Queue, history and logs update live; manual actions emit | Never present | Publisher into `MessageQServiceImpl`; subscribe in three screens | M | Medium — `JobLogs`' 5 s poll is the safety net and must stay as fallback |
| 16 | `message.json/changeJobStatus` is a `TENANT_USER` write called by no client (§12.11) | An explicit decision | Undecided surface, and the only part of this feature with tests | Decide: restrict, move behind `X-Worker-Token`, or delete | S | Low once decided |
| 17 | A malformed date becomes an opaque 500 (§12.6) although `requireValidDate` wrote the reason | The user is told the date was wrong | Contradicts the project's own observability rule | Catch `IllegalArgumentException` separately in the three controllers | S | Low |
| 18 | No test covers any screen or any live endpoint of this feature (§12.13) | Tests that fail when the behaviour is removed | The rules above are unprotected once fixed | Backend tests per fixed rule; frontend specs for the three screens | M | Low |
| 19 | Queue status chips collapse to one after selection (§12.12) | The multi-select the code already supports is reachable | Minor UX regression against a capability the component has | Render the fixed `STATUSES` list, not `counts()` | S | Low |
| 20 | The dashboard drill-down selects `job_queue.*` and reads it by ordinal (§12.10) on a table `ddl-auto=update` extends by appending | The query names the columns it parses | Whether the ordinals line up is a per-environment property; a mismatch on a nullable column is skipped silently | Name the eleven columns in the `select` | S | Medium — shared with the old app's history screen and the dashboard |

---

## 3. Solution detail

### 3.1 The tenant clause (row 1)

`QueryService.tenantClause` is one method and its two branches conflate two different callers:

```java
if (TenantContext.isPlatformAdmin() || ProcessUtil.isNull(TenantContext.getTenantId())) {
    return "";
}
```

A platform admin should see everything, so `""` is right for them. A tenant-less non-admin should
see nothing, and `""` gives them everything. Split the two: keep `""` for the platform admin, and
for a tenant-less non-admin emit a predicate that cannot match — `and 1 = 0`, or the equivalent
`and <alias>.tenant_id is not null and false`.

*Why not throw instead?* Throwing an `IllegalStateException` would be more honest about the caller
being malformed, but it would surface as a 500 through the controllers' blanket catch (row 17 is
unfixed at that point) and would turn a data-scoping decision into an outage for a class of token
whose reachability we have not established. A clause that matches nothing produces the same
observable result as a tenant with no runs, which is the correct answer, and it does so on every one
of `QueryService`'s ~15 call sites at once rather than only the two this feature owns.

*Why not fix it only in `fetchJobQLog` and `weeklyHrRunningStatisticsDimensionDetail`?* Because
`tenantClause` is the single statement of the rule for every raw-SQL read in the application, and a
local fix would leave the same hole in the dashboard, the reports and the user statistics while
making it look addressed. That does widen the blast radius beyond this feature, which is why row 1
is the only High risk in the table and why §4 puts it first and alone.

### 3.2 The private ownership copies (row 2)

Delete `MessageQServiceImpl.isJobOwnedByCaller` (`:130-137`) and the inline predicate at
`DashboardServiceImpl:246-247`; call `TenantOwnership.isOwnedByCaller(job.getTenantId())` in both.
`SourceJobServiceImpl:104-106` is already the model. The helper's javadoc
(`TenantOwnership.java:6-8`) names this exact drift as the reason it exists, so this is not a design
choice being made here — it is a call site that was missed.

`MessageQServiceImplTenantIsolationTest.anEmptyContextIsTreatedAsUntrusted` (`:190-201`) must gain a
sibling whose fixture job carries `tenantId = null`, because the existing test passes against tenant
B's job for a reason unrelated to the rule (`Objects.equals(2002L, null)` is false either way). Pair
it with a platform-admin positive control on the same fixture, as
`StorageConnectionTenantlessCallerTest` does.

### 3.3 The interrupt precondition (row 3)

`failJobLogs` already carries the shape:

```java
if (!jobQueue.get().getJobStatus().equals(JobStatus.Queue)) {
    return new ResponseDto(ERROR, "Only 'In Queue' Job can be fail.", jobQId);
}
```

Add the mirror in `interruptJobLogs`, refusing anything not in `{Queue, Start, Running}`. Note the
set: the new client's `inFlight` already admits `Queue`, and the old client did not
(`queue-message.component.html:180` allowed only `Running`/`Start`). Interrupting a queued run that
has not started is a coherent operation and the server has always permitted it, so the wider set is
the one to enforce; narrowing to the old client's pair would break a path the new UI already offers.

*Why not make the client the only guard, as today?* Because the write is not recoverable. It
overwrites `job_status`, `job_status_message` and `end_time` on a historical row and appends a log
line asserting an interrupt that never happened. There is no audit of the previous values.

While here, fix the message on the fail branch: `"Only 'In Queue' Job can be fail."` is what the user
sees in a toast when row 5 misfires, and it will still be reachable through the API afterwards.

### 3.4 The Logs link and the fail/interrupt predicates (rows 4, 5)

Row 4 is `job-history.html:352-355` changing `jobId()` to `run.jobId`. The row's id is already bound
three lines above in the Job column (`:307-312`), which is the column the all-jobs view adds — the
data was there and the wrong variable was reached for.

*Why not hide the Logs button in the all-jobs view instead?* Because the button is the point of that
view. The dashboard's TOTAL cell exists so an operator can ask "what ran in this hour" and then
"what did that one do"; removing the second step leaves a list you can only look at.

Row 5 replaces the single `inFlight` predicate with two:

```ts
canFail(row)      { return row.jobStatus === 'Queue' && !row.endTime; }
canInterrupt(row) { return ['Queue','Start','Running'].includes(row.jobStatus) && !row.endTime; }
```

and renders each menu item on its own predicate, hiding the menu when neither applies. `inFlight`
stays for the "in flight" duration label, which is a different question. This has to land together
with row 3 or the two definitions of "interruptible" will disagree across the wire.

### 3.5 The queue statistic (row 6)

`fetchJobQLog(search, isState = true)` skips the whole `if (!isState)` block that builds the
predicates (`:436-454`) and then adds its own bare `where` (`:457`). Restructure so the predicates
are built once and both branches use them, differing only in the `select` list and the trailing
`group by` / `order by`. The two branches also disagree today on which jobs count — the row query
excludes `Delete` (`:439`), the statistic includes only `ACTIVE`/`INACTIVE` (`:457`); make them the
same predicate.

Then delete the `notListed` computed and its tooltip (`queue.ts:160-165`, `queue.html:45-52`). Once
the statistic matches the filters it should equal `rows().length`, and a residual difference would
be a bug rather than something to narrate.

*Why not simply drop the server statistic and count client-side, as `counts()` already does?*
Tempting — it is one line — and rejected. The statistic is the one number in this feature that does
not depend on how many rows the client happened to load, which is exactly what makes it the right
input the day server-side paging arrives (row 12's larger sibling). Deleting it now would mean
reintroducing it then. It is also still consumed by the old app's Q-Message chart
(`queue-message.component.ts:342-397`), which is running against the same backend, so changing the
query's semantics is a shared change and dropping the field would break that screen outright.

### 3.6 Queue parity: filters, columns, logs link (rows 7, 8, 9)

These three are what make `/queue` a replacement for Q-Message rather than a summary of it.

**Filters.** `MessageQSearchDto` already carries `Set<Long> jobId` and `Set<Long> jobQId`
(`:18-19`) and `QueryService` already consumes them (`:441-448`). The work is entirely in
`queue.html` and `queue.ts`: two inputs accepting a comma-separated list, parsed to numbers, dropped
from the body when empty. The old app's parse is `value.split(',').map(Number)`
(`queue-message.component.ts:151`, `:155`) — filter out `NaN` rather than sending it, because a
`NaN` in a `Set<Long>` is a Jackson deserialisation failure and therefore a 500.

**Columns.** Start, End and Skip Time and the three booleans are all on `SourceJobQueueDto` and all
already parsed by `fetchLogs` (`MessageQServiceImpl.java:67-113`). Adding six columns to a table
that already scrolls horizontally inside `TableShell` costs nothing structurally. Prefer the history
screen's treatment of the flags — a small icon or a muted dash rather than the old app's
red/green pill per boolean, which coloured a `false` as if it were an error.

**Logs link.** One cell, `['/jobs', row.jobId, 'runs', row.jobQueueId, 'logs']`. Once it exists the
old app's `from=qMessage` back-target (`job-logs.component.ts:18-27`) becomes relevant again: the
new `JobLogs` always goes back to the job's history (`job-logs.html:3-5`), which is not where the
user came from. Deferring that is acceptable — the browser's own Back works — but it should be a
noted follow-on rather than an omission.

### 3.7 The pipeline strip (row 10)

`job-logs.component.ts:285-308` is 24 lines and the logic is worth reading before reimplementing:
the happy path is `Queue → Start → Running → Completed`; a terminal alternate replaces the fourth
stage rather than being appended; and `Skip` marks `Start` and `Running` as *bypassed*, not done,
because a skipped run never entered them. Rebuild as a presentational component in
`features/jobs/logs/` taking `run.jobStatus`, using the theme tokens rather than the old glyphicons.

*Why rebuild rather than declare it lost?* It answers a question the new screen cannot: "how far did
this get". The detail card shows the final status, and the entries show what the worker said, but
neither tells you at a glance that a run reached `Running` and then stopped versus never having
started. It is small, self-contained and has no backend dependency.

### 3.8 The Gantt (row 11) — and why it is a separate decision

`shared/charts/` has `Donut`, `RankedBar`, `BarChart` and `SplitBar` and nothing time-axed. The old
chart is an echarts `custom` series with a `renderItem` clipping rectangles into the coordinate
system (`queue-message.component.ts:274-291`), a time x-axis, a categorical y-axis of job ids,
`dataZoom` on both inside and slider, and click-through to logs. That is a genuine component, not a
configuration of an existing one, and it is the only thing in either app that shows **overlap** —
two runs of different jobs contending for the same window.

Two options were considered and one deferred rather than rejected outright:

- **Rebuild it as `shared/charts/timeline.ts`.** Correct, and reusable: `reports` and the dashboard
  would both have uses for a time-axed series. Large, and it lands on a screen that has four charts
  already.
- **Approximate it with the existing `BarChart` — duration per run, ordered by start time.** Cheap,
  and it does not answer the question. Duration ordered by start is what the history screen's
  duration trend already shows; it cannot show two runs occupying the same minute. Rejected: it
  would let the row be marked done without the capability being back.

Recommendation in §6.

### 3.9 Live updates (row 15)

The infrastructure is finished and unused. `JobEventPublisher.publishLog` and `publishStatus` both
carry `jobQueueId` (`:40-67`); `NotifyServiceImpl` calls them from the worker callback path
(`:74`, `:118`, `:142`); `JobEventsService` already names `job.log` in its type union
(`core/socket/job-events.service.ts:8-16`) and no consumer handles it. `JobLogs` polls every five
seconds for entries that are being pushed to a socket the app already holds open.

Three pieces: inject `JobEventPublisher` into `MessageQServiceImpl` so a manual fail or interrupt
emits `job.status` like the worker path does; subscribe in `Queue` and `JobHistory` to patch a row's
status in place; subscribe in `JobLogs` to append a `job.log` whose `jobQueueId` matches.

**Keep the 5-second poll as a fallback, unconditionally.** The socket drops, reconnects and can miss
messages while disconnected; the poll is what makes a missed push invisible rather than fatal.
Replacing the poll with the socket is the version of this change that looks cleanest and is wrong.

### 3.10 The drill-down's ordinal parse (row 20)

`QueryService.weeklyHrRunningStatisticsDimensionDetail` selects `job_queue.*`
(`QueryService.java:405`) and `DashboardServiceImpl:194-241` reads eleven fixed indices out of the
result. The entity has fourteen columns. `job_queue` has no `CREATE TABLE` in Liquibase — it is
created and extended by `ddl-auto=update` (`.ai/discovery/database.md:21`, `:57-61`), which appends
new columns at the end — so which ordinal holds which column is a property of each environment's
migration history rather than of `JobQueue.java`.

Replace `job_queue.*` with the same eleven-column list `fetchJobQLog` already spells out
(`QueryService.java:432`), in the order the parser expects.

*Why not verify the ordinals first and leave the query alone if they happen to line up?* Because
"happen to" is the problem. Even if they line up on every environment today, the next column added
to `JobQueue` — and `ddl-auto=update` will add it silently — can move them, and the failure mode is
not an exception: every field is guarded by `if (!isNull(obj[index]))`, so a mismatch on a nullable
column is skipped and the screen renders plausible wrong data. Naming the columns is smaller than
the investigation it would replace, and it makes the question unanswerable rather than answered.

This is marked Medium risk rather than Low because it is the read path behind the old app's entire
run-history screen as well as the new app's drill-down: if the ordinals are currently *wrong* in
some environment, fixing the query changes what that screen displays there, and that change should
be expected rather than treated as a new bug.

### 3.11 Tests (row 18)

Every rule fixed above needs a test that fails when it is removed, and every refusal needs its
positive control on the same fixture — the acceptance criteria in §11 are written in pairs for
exactly this reason.

Backend, extending `MessageQServiceImplTenantIsolationTest` and adding a
`SourceJobRunHistoryTenantTest`:

- tenant-less caller against a null-tenant job — refused; platform admin on the same fixture —
  admitted (rows 1, 2)
- `interruptJobLogs` on a `Completed` run — refused; on a `Running` run of the same job — admitted
  (row 3)
- `fetchLogs` with a `jobId` filter naming another tenant's job — no rows; with the caller's own —
  rows (rows 1, 7)
- `fetchSourceJobQueueListWithJobId` and `findSourceJobAuditLog` for another tenant's job — refused;
  own job — admitted. Neither has any test today.

Frontend, three new spec files. The two highest-value are pure functions worth extracting first, as
`stalled.ts` and `notify-summary.ts` already were for `source-jobs`: the fail/interrupt predicates
from row 5, and the gap/stall computation in `job-logs.ts:112-193`, which is 80 lines of arithmetic
with no test. Extracting them makes them testable without mounting a component and is the pattern
this codebase already follows.

---

## 4. Ordering

**First, alone: row 1 (the tenant clause).** It is the only change that reaches outside this feature
— `tenantClause` serves the dashboard, reports and user statistics too — so it wants its own commit
and its own run of the backend suite. Everything else can follow in parallel.

**Then the correctness batch: rows 2, 3, 5, 4.** Rows 3 and 5 are one change split across the wire
and must land together or the client and server will disagree about what "interruptible" means. Row
2 is independent. Row 4 is independent and one line — take it early because it unblocks manual
verification of the whole all-jobs path, which is currently a dead end.

**Then row 6 (the statistic), before rows 7 and 8.** Fixing the query first means the new filters
added in row 7 are reflected in the chart from the moment they exist, rather than making an already
wrong number wronger and then correcting it.

**Then queue parity: rows 7, 8, 9, 19.** These are what let the old Q-Message screen be retired
without argument. Row 9 (the logs link) should land last of the four, because it is the one that
makes the missing back-target noticeable.

**Row 20 goes with row 13, and before it.** Both change what `job_queue` columns reach the client;
naming the drill-down's columns first means row 13 is adding two named fields to a query that names
its columns, rather than adding two more ordinals to one that does not.

**Then rows 10, 12, 14, 17.** Independent of each other and of everything above. Row 13 touches
`getSourceJobQueueDto`, which three screens consume (`Queue`, `JobHistory`, and the jobs list's run
strip via `fetchSourceJobQueueListWithJobId`), so it wants a check that none of them break on the
two added fields — they will not, but the shared DTO is worth naming.

**Row 18 (tests) is not a phase.** Each test lands with the change it protects. The two extractions
in §3.10 are the exception and can be done at any point.

**Last, and only after the above are green: row 15 (live updates), and rows 11 and 16 once §6 is
answered.** Live updates change how three screens get their data and are the change most likely to
produce an intermittent failure; putting them on top of a feature whose correctness is already
settled means a regression there is unambiguous.

---

## 5. Out of scope

- **Anything that creates a run.** Dispatch, "Run now" and skip-next belong to `source-jobs`; the
  scheduler belongs to the engine. This feature reads runs and forces two of them terminal.
- **The dashboard's heat-map and its other four endpoints.** `weeklyHrRunningStatisticsDimensionDetail`
  is shared and is touched here only through row 1; the four statistics endpoints beside it are
  `dashboard`'s.
- **`reports` and `job-assistant`**, both of which read `job_queue`. Row 13 adds two fields to a
  shared DTO and nothing else here changes a payload shape they depend on.
- **The `NotifyResetApi` worker callbacks.** They write the rows this feature reads, they are
  machine-to-machine behind `X-Worker-Token`, and `.ai/discovery/features.md` already records them as
  correctly having no UI. Row 16 may end with `changeJobStatus` joining them; that is a move, not a
  change to the callbacks themselves.
- **Replacing the raw SQL in `QueryService` with JPA.** `fetchJobQLog` and its neighbours are string
  concatenation with hand-rolled sanitisation, which is a legitimate thing to dislike. It is also
  fifteen call sites of shared machinery and rewriting it under cover of a queue-screen fix is how a
  two-day change becomes a two-week one. Rows 1 and 6 change what those strings say, not how they
  are built.
- **Retention or archiving of `job_queue` / `job_audit_logs`.** Row 12 bounds what is *rendered*.
  How long runs are kept is an operational policy nobody has stated, and inventing one here would be
  a data-deletion decision made by the wrong document.
- **Per-user narrowing of run visibility.** A `TENANT_USER` can see and force any run in its tenant
  (§8.1). That matches the old app and matches `source-jobs`, and changing it is a product decision
  affecting several features at once — raised in §6, not acted on here.
- **The old app.** It stays on the same backend and is reference-only. Row 6 changes a query it
  consumes, which is why §3.5 checks that its chart still works; nothing else here touches it.

---

## 6. Open questions

**Q1. The Gantt: rebuild, drop, or defer?**
Options: (a) build `shared/charts/timeline.ts` and restore it on `/queue`; (b) declare it dropped
and record the decision; (c) defer until someone asks for it.
**Recommendation: (a), but not in this pass — schedule it as its own piece of work after §4 is
green.** It is the only capability in this feature whose *question* has no other answer in the new
app — the four charts on `/queue` say what happened and how much, and none of them says *when, and
at the same time as what*. That is the question an operator asks when the pipeline is behind, which
is precisely the audience for this screen. Dropping it is defensible only if nobody has used it, and
we have no usage data. Deferring indefinitely is how (b) happens without being decided. Building it
as a shared component rather than a queue-screen one pays for itself the moment `reports` wants a
time axis.

**Q2. `message.json/changeJobStatus` — restrict, move, or delete?**
It is a `TENANT_USER` write that can set any run in the caller's tenant to any status, rewrite its
message and end time, and append audit lines. No client calls it. It is also the only endpoint in
this feature with tests.
Options: (a) delete it and its tests; (b) restrict to `TENANT_ADMIN` and leave it; (c) move it
behind `X-Worker-Token` beside the `NotifyResetApi` callbacks.
**Recommendation: (c).** Its shape is a worker callback — `AUDIT_LOG` appends a line, `QUEUE_DETAIL`
reports a terminal status with an end time — and `NotifyResetApi` already hosts three endpoints that
do exactly that. Moving it puts it where its authentication model matches its purpose and keeps the
eight tests, which are good tests, meaningful. (a) discards working, tested code on the strength of
a grep. (b) leaves a general-purpose run-rewriting endpoint on the tenant surface for no consumer.
If (c) is rejected on effort, (b) is an acceptable stopgap; (a) is not, until somebody has checked
that no external integration calls it.

**Q3. Should forcing a run terminal require `TENANT_ADMIN`?**
Today `failJobLogs` and `interruptJobLogs` are `TENANT_USER`, matching the old app and matching
`runSourceJob` / `deleteSourceJob` in `source-jobs`.
**Recommendation: leave it at `TENANT_USER`, and raise it as a product question rather than deciding
it here.** The consistency argument is strong: a `TENANT_USER` who may delete a job outright is not
meaningfully restrained by being unable to mark one of its runs failed. Tightening this endpoint
alone would produce a surface where the small destructive action is harder than the large one.
If the answer comes back that write operations should be `TENANT_ADMIN`, that is a decision for
`source-jobs` and this feature together, and it changes route guards as well as annotations.

**Q4. Should a null-tenant `source_job` row be possible at all?**
Row 2's severity depends on it. `addSourceJob` refuses one (`SourceJobServiceImpl.java:135-137`),
the bulk path inherits the task's tenant (`SourceJobBulkServiceImpl.java:228`), but
`source_job.tenant_id` is a nullable FK (`V12__add_tenant_user_fk_constraints.sql:30`) and whether
such rows exist today is not verified — I did not query the database.
**Recommendation: fix row 2 regardless, and separately run
`select count(*) from source_job where tenant_id is null` on each environment before deciding
whether to add `NOT NULL`.** The fix is three lines and closes the hole whatever the answer; the
constraint is a migration that will fail on any environment that has such a row, so it needs the
count first. If the count is zero everywhere, adding `NOT NULL` turns row 2's whole class of bug
into something the schema prevents — worth doing, in `source-jobs`' scope rather than this one.

**Q5. Client-side or server-side paging for run history (row 12)?**
`fetchSourceJobQueueListWithJobId` returns every run ever recorded and three screens consume it.
Options: (a) client-side pager, as `/queue` uses; (b) add `page`/`size` to the endpoint.
**Recommendation: (a) now, (b) only on evidence.** The response is already being fetched in full by
the jobs list's run strip and by the assistant, both of which want the whole set; adding server-side
paging would mean either a second endpoint or three callers passing "give me everything". A client
pager fixes the render cost, which is the observed problem, and costs one import. Revisit if a job
appears with runs in the tens of thousands — the largest seen in the code's own comments is 210
(`SourceJobServiceImpl.java:617`).
