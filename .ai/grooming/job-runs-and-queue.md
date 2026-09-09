# Grooming -- Job Runs and Queue

Feature `job-runs-and-queue`, row 4 of [../discovery/features.md](../discovery/features.md). Status
**partial**.

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Purpose

A job is a schedule. This feature is about what actually happened when that schedule fired.

Three questions, and each of them belongs to a different person on a different day:

- **"Did my job run last night, and how did it go?"** — the run history of one job: every attempt,
  when it was queued, when it started, when it ended, what state it ended in and what it said.
- **"This one run failed. Why?"** — the log stream a worker wrote while that run was executing, in
  order, with the pauses visible so you can see where it sat waiting rather than working.
- **"Something is stuck in the queue and the whole pipeline is behind."** — the operator's view
  across every job over a date range, with the ability to force a run that will never report back
  into a terminal state so it stops occupying the queue.

The unit under discussion is the **run**, not the job. One `source_job` row produces many
`job_queue` rows, and each `job_queue` row collects many `job_audit_logs` lines. Nothing here
creates a run; runs are created by the dispatcher and by the manual "Run now" action, both of which
belong to `source-jobs`. This feature only reads them, and forces two of them to a terminal state.

---

## 2. Existing behaviour

### 2.1 What the old app does

Three routes, all `AuthGuard` only — no role gate on any of them
(`scheduler1/src/app/app.routing.ts:95-104`, `:143-148`).

| Route | Component | Reached from |
|---|---|---|
| `jobList/jobHistory` | `JobHistoryActionComponent` | Job list row action; dashboard heat-map drill-down |
| `jobList/jobLogs` | `JobLogComponent` | A history row; a bar on the history chart; a bar on the Q-Message Gantt |
| `setting/queueMessage` | `QueueMessageComponent` | Navbar, "Q-Message" (`scheduler1/src/app/app.component.html:79`) |

**Run history** (`scheduler1/src/app/_component/job-history-action/job-history-action.component.ts`).
Driven entirely by query params — the constructor subscribes to `queryParamMap` and re-fetches on
every change (`:84-88`). It calls **one** endpoint for every case:
`dashboard.json/weeklyHrRunningStatisticsDimensionDetail` with `targetDate`, `targetHr`,
`jobStatus`, `jobId`, any of which may be null (`:98-120`). With only `jobId` set that returns the
job's entire history; with a date and hour it returns that hour; with no params at all it returns
every run of every job the caller can see.

The response carries three things and the screen uses all three: `sourceJobQueues` (the rows),
`sourceJob` (the job, its schedule and its linked task, rendered as a context banner) and
`sourceJobStatistics` — a server-computed count per status for the whole job, rendered as a
nine-cell KPI strip (`job-history-action.component.html:88-122`).

The table is 13 columns (`:174-221`) and each of six headers carries a miniature stacked bar
showing that column's distribution — start/end/skip time filled-vs-empty, `runManual` and
`skipManual` true-vs-false, and the status mix (`:177-219`, backed by `dateFillColumnStats`,
`booleanColumnStats` and `jobStatusColumnStats` at `job-history-action.component.ts:200-225`).
Below that, three echarts: a per-run duration bar coloured by outcome whose bars link into that
run's logs (`:142-198`), a status pie, and a boolean-fields chart. Search and status filter are
client-side over the loaded rows, and re-running either recomputes all four charts through the
setters at `:30-55`.

Per row, one action: a Logs button that navigates to `jobList/jobLogs` with **that row's**
`jobId` and `jobQueueId` (`:259-267`).

**Run logs** (`scheduler1/src/app/_component/job-logs/job-logs.component.ts`). Reads `jobId`,
`jobQueueId` and an optional `from` from the query string (`:87-102`) and calls
`sourceJob.json/findSourceJobAuditLog`. Notable behaviour:

- Three view modes — timeline, table, console — with a "stick to bottom" toggle
  (`:70`, `:186-203`, `job-logs.component.html:121-193`).
- A **pipeline strip**: `Queue → Start → Running → Completed`, or the first three plus the terminal
  alternate the run actually reached (`Failed`/`Interrupt`/`Skip`/`Missed`), with `Skip` marking
  Start and Running as bypassed rather than done (`:11-14`, `:285-308`,
  `job-logs.component.html:103-118`).
- A **log-gap bar chart**: one bar per interval between consecutive entries, anchored on the run's
  own `startTime`, coloured amber where a gap is both more than twice the average and over five
  seconds, with echarts `dataZoom` when there are more than 80 bars and the zoom position preserved
  across refreshes (`:213-271`, `:205-211`).
- **5-second auto-refresh** while the run is not terminal, re-armed after each load and stopped on
  a terminal status, with a manual Live toggle (`:16`, `:147-173`).
- `plainLogText` strips `<br>` and tags from a log line for the console view (`:278-283`).
- A `from` parameter drives the Back button — `jobHistory`, `jobList` or `qMessage` each get their
  own label and target, and anything else falls back to `Location.back()` (`:18-27`, `:310-333`).

**Q-Message** (`scheduler1/src/app/_component/setting/queue-message/queue-message.component.ts`).
A reactive filter form with five controls — `fromDate`, `toDate`, a single-select `jobStatuses`,
and comma-separated `jobId` and `jobQId` textareas (`:134-140`,
`queue-message.component.html:13-45`). It opens on the last seven days filtered to `Queue`
(`:127-132`) and POSTs to `message.json/fetchLogs`. The response's `jobStatusStatistic` is drawn as
a horizontal bar beside the form (`:342-397`).

The result table is 13 columns — QId, Job Id, Date Created, Start Time, End Time, Duration, Skip
Time, Run Manual, Skip Manual, Q Send, Job Status, Message, Action — with the same header
mini-charts as the history screen (`queue-message.component.html:86-142`). Four echarts below the
toolbar, of which the fourth is the one that matters: an echarts **custom series** laying every run
out as a bar from its start time to its end time on a time x-axis, grouped by job, with `dataZoom`,
and clicking a bar opens that run's logs (`:234-292`, `:294-304`).

Two row actions (`queue-message.component.html:173-185`):

- **Delete** — calls `failJobLogs`, and the button is `[disabled]` unless the row's status is
  exactly `Queue`.
- **Interrupt** — calls `interruptJobLogs`, `[disabled]` unless the status is `Running` or `Start`.

Neither asks for confirmation. Both re-run the current filter on success
(`queue-message.component.ts:306-340`).

### 2.2 What the new app does

Four routes, all inside the shell, all `authGuard` + `passwordChangeGuard`, **none carrying
`minRole`** (`scheduler1/next/src/app/app.routes.ts:77-96`, re-read 2026-09-08).

| Route | Component | File |
|---|---|---|
| `jobs/:jobId/history` | `JobHistory` | `features/jobs/history/job-history.ts` (334 lines) |
| `jobs/history` | `JobHistory` | same component, no `jobId` |
| `jobs/:jobId/runs/:jobQueueId/logs` | `JobLogs` | `features/jobs/logs/job-logs.ts` (285 lines) |
| `queue` | `Queue` | `features/queue/queue.ts` (349 lines, grown from 263 on 2026-09-08) |

**Run history** (`features/jobs/history/job-history.ts`). Route params arrive as signal inputs
(`:73-81`) and an `effect` re-loads on any change (`:229-239`). Unlike the old screen it uses **two**
endpoints and chooses between them (`:263-304`):

- Drill-down (`targetDate` set and `targetHr` non-empty) → `weeklyHrRunningStatisticsDimensionDetail`,
  sending `jobStatus` and `jobId` only when set (`:275-285`).
- Otherwise, with a `jobId` → `fetchSourceJobQueueListWithJobId`.
- Neither → an inline error, `"Open a job, or pick an hour on the dashboard, to see runs."`
  (`:266-271`).

The two payloads name the list differently and the component reads both
(`this.runs.set(data.sourceJobQueues ?? data.jobQueues ?? [])`, `:296`). The job's name comes from a
separate `listSourceJob` call in the constructor (`:242-249`), and the context panel from
`fetchSourceJobDetailWithSourceJobId` (`:170-180`), whose failure is swallowed on purpose so the run
list still renders.

Above the table: status count chips that toggle a client-side filter
(`job-history.html:187-199`); a collapsible Job & task detail card carrying the schedule, the
email-notification chips and the task payload with a copy button (`:39-185`); and behind a Charts
toggle an outcome donut, a duration trend over the last 24 runs with fastest/median/slowest, and a
split bar for the three per-run flags — where a flag no row in view carries is omitted entirely
rather than charted as an empty bar (`job-history.ts:101-117`).

The table is 8 columns (9 in the all-jobs case): Run, [Job], Queued, Started, Ended, Duration,
Message, Status, Logs. A message longer than 60 characters becomes a button that opens the full text
in a copyable `<pre>` beneath the row (`job-history.html:331-376`), which is a real improvement on
the old truncating cell. There is no paging.

**Run logs** (`features/jobs/logs/job-logs.ts`). Both ids are validated as digits before any request
is made, and a bad link gets a sentence saying what to do instead rather than a Java type-conversion
error (`:29-33`, `:241-246`). One call to `findSourceJobAuditLog`, whose single payload supplies the
entries, the job and the run (`:250-275`) — the old screen made the same call but the new one stops
there where the history screen still fetches the job separately.

Same three view modes and stick-to-bottom (`:55-60`, `job-logs.html:165-217`). Same 5-second
auto-refresh gated on a non-terminal status, expressed as an `effect` that re-arms itself and a
`quiet` load that does not blank the list (`:66-96`, `:236-248`). The gap analysis is **reshaped**:
instead of a bar per interval it ranks the eight longest gaps, states what share of the elapsed
span they account for, counts the ones that qualify as stalls, and separately calls out entries
stamped after the run finished because those inflate every following gap (`:112-193`). The reasoning
is in the file's own comment at `:135-141`.

**Queue** (`features/queue/queue.ts`, 349 lines; `queue.html`, 178; `queue.spec.ts`, 185).
*Substantially reworked 2026-09-08 — see 2.2.1.* Opens on the last seven days because `fetchLogs`
refuses a missing date (`:64-73`). POSTs `fromDate`, `toDate` and, when any are selected,
`jobStatuses` (`:265-292`), and reads the payload's `sourceJobQueues` — it used to read `jobQueues`,
which never matched, so the screen showed an empty table over hundreds of rows (`:282-285`).

**Every visualisation reads one collection.** `data()` (`:88-95`) applies the search term to the
fetched rows, and the outcome donut (`statusMix`, `:169-170`), the failure rate (`:248-254`), busiest
jobs (`:204-211`), volume by day (`:221-234`), the duration buckets (`:183-202`), the flag split
(`:173-181`), the table (`paged()`, `:101`) and the Charts toggle's own gate (`hasInsights`, `:259`)
all derive from it. The date range and the status chips are applied by the **server**, so `rows()`
already obeys those two; only the search box is applied in the browser. The comment at `:75-87`
records what this replaced: the table rendered the filtered list while four charts read the raw rows
and the donut read a server statistic that obeyed no filter at all, so typing a job number narrowed
the table to three rows and left every chart above it describing all fifty-two.

**The status chips are counted differently on purpose.** `counts()` (`:124`) tallies the **fetched**
rows, not `data()` (`:114-123`): a chip counted after the search box had been applied would vanish
the instant the search excluded its last row, taking with it the only control that could switch that
status back off. Describing the narrowed population is the charts' job.

**The narrowing is stated, not implied.** `activeFilters()` (`:133-141`) names the search term and
each selected status as a removable pill above the charts (`queue.html:31-52`), because the search
box lives in the table toolbar *below* them where a reader looking at the ring cannot see it.
`clearFilter` (`:143-152`) removes a search term in the browser and toggles a status off through a
refetch, since the two are enforced in different places. The "N of M messages" count renders only
when the two numbers differ (`queue.html:43-50`) — a status chip is server-applied, so it would
otherwise read "4 of 4" and invite the reader to think the search did nothing.

**The server's `jobStatusStatistic` is kept as a footnote and feeds no chart.** `statusStats`
(`:166`) is still read from the payload and `allTimeTotal()` (`:244-245`) sums it, but it is rendered
once, beside the donut, labelled "N on record all time" and only when it exceeds the fetched row
count (`queue.html:65-71`). Its tooltip says what it actually is: a server-side total with no date
range and no filters, counting every message this workspace has ever recorded, deleted runs included.
See §12.5 for why that is what it is, and what the caption used to claim instead.

Rows are paged client-side (`:100-104`, `queue.html:175-176`).

Row actions live in a CDK menu shown only when `inFlight(row)` — no end time and status in
`Queue`/`Start`/`Running` (`:346-348`, `queue.html:154-168`). Both go through a confirm dialog
(`:309-316`), then `failJobLogs` or `interruptJobLogs` with the parameter named **`jobQId`**
(`:325`), and reload on success. The comment at `:322-324` records that this parameter was previously
sent as `jobQueueId`, so Spring rejected both calls with a 400 before the handler ran and neither
action had ever once worked.

**Tests.** `queue.spec.ts` — 10 vitest cases, all regression tests for the two-populations defect:
the ring counts what the table lists, the failure rate moves with the filter, the server statistic is
excluded from the ring and reported separately, the busiest-jobs / duration / flag charts narrow with
the same filter, volume-by-day stays gap-filled over the filtered rows, the charts panel hides when a
filter empties the table, a selected chip survives a search that excludes it, and the filter strip
names and clears each filter. This is the **first** frontend test this feature has ever had.

#### 2.2.1 What changed on 2026-09-08

| Change | Where | Closes |
|---|---|---|
| Every chart reads the same filtered `data()` as the table | `queue.ts:88-95`, `:169-234` | §12.5, UI half; §3 item 3 |
| The all-time statistic is labelled as all-time and drives nothing | `queue.ts:155-166`, `:244-245`; `queue.html:65-71` | §12.5, UI half |
| The false "the server caps how many rows it returns" explanation removed | `queue.html:65-71` | §12.5 |
| A visible strip naming each active filter, each removable | `queue.ts:133-152`; `queue.html:31-52` | new |
| Volume by day gap-filled through the shared `daySeries` | `queue.ts:221-234`; `shared/charts/day-series.ts` | new |
| Ten frontend tests | `queue.spec.ts` | §12.13, in part |

Not changed, and still open: the Logs link (§13), the server-side `jobId`/`jobQId` filters (§13), the
interrupt precondition (§12.2), "Mark as failed" offered where the server refuses it (§12.3), the
chip set collapsing to one (§12.12), and the statistic query itself (§12.5, server half).

### 2.3 The backend both apps share

| Endpoint | Handler | Service |
|---|---|---|
| `POST /message.json/fetchLogs` | `MessageQRestApi.java:32-41` | `MessageQServiceImpl.java:56-128` |
| `DELETE /message.json/failJobLogs` | `:43-52` | `:139-165` |
| `DELETE /message.json/interruptJobLogs` | `:54-63` | `:167-185` |
| `PUT /message.json/changeJobStatus` | `:65-74` | `:187-232` |
| `GET /sourceJob.json/fetchSourceJobQueueListWithJobId` | `SourceJobRestApi.java:131-140` | `SourceJobServiceImpl.java:455-478` |
| `GET /sourceJob.json/findSourceJobAuditLog` | `:179-189` | `:390-418` |
| `GET /dashboard.json/weeklyHrRunningStatisticsDimensionDetail` | `DashboardRestApi.java:103-115` | `DashboardServiceImpl.java:187-271` |

`fetchLogs` and the dashboard drill-down are **hand-built SQL** in
`QueryService` (`:457-496` and `:436-455` — line numbers re-read 2026-09-08) executed through
`executeQuery`, with dates validated against `\d{4}-\d{2}-\d{2}` (`:164-173`), status names checked
against a fixed set (`:200-209`), and tenancy applied as a string clause (`:211-217`). The id filters
interpolate a `Set<Long>` and so cannot carry SQL (`MessageQSearchDto.java:18-19`).

One thing changed in `fetchJobQLog`'s row query since this section was written: it now excludes
deleted queue rows as well as deleted jobs — `and UPPER(sj.job_status) <> 'DELETE' and
UPPER(jq.status) <> 'DELETE'` (`:471`). The **statistic** half of the same method still filters on
neither, which is part of §12.5.

The other two go through JPA. `fetchSourceJobQueueListWithJobId` enables the Hibernate filter, reads
the job by id, refuses it unless `TenantOwnership.isOwnedByCaller` says yes, refuses a `Delete` job
outright with a comment explaining why (`:464-469`), then returns every `job_queue` row for that job
newest-first. `findSourceJobAuditLog` does the same ownership check, additionally requires the queue
row to belong to the job named in the request (`:403-404`), and returns the merged DB and OpenSearch
log lines de-duplicated on `external_id` (`:410-412`, `:420-439`).

`changeJobStatus` is reachable and implemented but **called by neither frontend** — verified by
searching both `scheduler1/src` and `scheduler1/next/src` for the string, which returns nothing.

---

## 3. Expected behaviour

Everything in §2.2 stays. On top of it:

1. **A run's logs are reachable from every list that shows the run.** Today the all-jobs history
   view builds its Logs link from the route's job id, which is empty on that route, and the queue
   table offers no way into logs at all. Both lists already hold `jobId` per row.
2. **The queue can be filtered by job id and by run id on the server**, as the old screen could.
   Client-side search over an unpaged, unbounded result set is not the same capability: it can only
   narrow what was already downloaded.
3. **The queue's status donut agrees with the queue's table, or says why it does not.**
   **DONE 2026-09-08**, and by the first of the two routes rather than the second: the donut no
   longer plots the server statistic at all. It is drawn from `statusMix()` (`queue.ts:169-170`),
   which tallies the same `data()` the table pages, so the two agree by construction and there is
   nothing left to explain. The server statistic survives as an explicitly labelled all-time
   footnote (`queue.html:65-71`) whose tooltip states what it counts. The sentence about row caps —
   which described a cap `fetchJobQLog` does not have — is gone. The query itself is unchanged; see
   §12.5.
4. **A destructive queue action is offered only where the server will accept it.** `Mark as failed`
   is offered on `Start` and `Running` rows where the server refuses; `Mark as interrupted` is
   offered on `Queue` rows where the server accepts it although the old app did not.
5. **`interruptJobLogs` refuses a run that has already finished**, on the server. Today the only
   thing stopping an operator from overwriting a two-week-old `Completed` run with `Interrupt` and a
   fresh end time is that the button is hidden.
6. **Forcing a run to a terminal state updates every open screen.** The STOMP publisher exists,
   carries `jobQueueId`, and is called from the worker callback path — but not from the two manual
   ones, so the jobs list keeps showing the old state until it is reloaded.
7. **A caller carrying no tenant sees nothing**, at the data layer as well as above it. Two code
   paths in this feature currently treat a tenant-less caller as unrestricted or as the owner of
   platform-owned rows. See §8.
8. **The run knows where its output went.** `job_queue.bucket` and `job_queue.output_folder` are
   written at dispatch and never returned by any DTO, so both apps can only show the task's
   *current* destination, which may have been edited since the run.
9. **A long run history is paged or bounded.** `fetchSourceJobQueueListWithJobId` returns every run
   ever recorded for a job and the history screen renders all of them.

---

## 4. Frontend requirements

### 4.1 Routes

| Path | Component | Guard | Params |
|---|---|---|---|
| `jobs/:jobId/history` | `JobHistory` | `authGuard`, `passwordChangeGuard` | route `jobId`; query `jobStatus`, `targetDate`, `targetHr` |
| `jobs/history` | `JobHistory` | same | query `jobStatus`, `targetDate`, `targetHr` |
| `jobs/:jobId/runs/:jobQueueId/logs` | `JobLogs` | same | route `jobId`, `jobQueueId` |
| `queue` | `Queue` | same | none |

No `minRole`. Every endpoint behind these screens is `TENANT_USER`, which the role hierarchy
(`MethodSecurityConfig.java:27-30`) grants to all three roles, so a role gate on the route would
hide a page the API serves. This matches the old app, where all three routes carried `AuthGuard`
only.

`queue` is in the Pipelines nav group (`features/shell/shell.ts:61-62`). The two history routes and
the logs route are not in the nav and are reached from the jobs list
(`features/jobs/jobs.html:238`, `:390`), the dashboard drill-down
(`features/dashboard/dashboard.ts:213`, `:238`), the run-duration bars on an expanded job row
(`features/jobs/jobs.ts:424-426`) and — required, not yet built — the queue table.

### 4.2 Components and their tables

**`JobHistory`.** Chips row (status counts, click to filter), collapsible detail card, optional
charts block, `TableShell`-wrapped table.

| Column | Source | Notes |
|---|---|---|
| Run | `jobQueueId` | plus a send icon when `jobSend` |
| Job | `jobId` | **all-jobs view only**; links to that job's own history |
| Queued | `dateCreated` | |
| Started | `startTime`, else `skipTime` | a skipped run says "skipped" in amber |
| Ended | `endTime` | |
| Duration | computed | null while running |
| Message | `jobStatusMessage` | > 60 chars expands into a copyable block |
| Status | `jobStatus` | `StatusPill` |
| — | | Logs link, built from **`run.jobId`**, not the route's |

**`JobLogs`.** Detail card, optional timing block, `TableShell` with a three-way view switcher, a
search box, a Live/Paused toggle shown only while the run is non-terminal, and a Refresh button.
Timeline / table / console render the same filtered list.

**`Queue`.** Chips row, an active-filter strip, an optional charts block, `TableShell` with two date
inputs, a search box and a Clear button, then the table and a pager.

| Column | Source |
|---|---|
| Run | `jobQueueId` |
| Job | `jobId` |
| Created | `dateCreated` |
| Duration | computed; "in flight" when `inFlight(row)` |
| Message | `jobStatusMessage` |
| Status | `jobStatus` |
| — | actions menu, and a Logs link (required, not present) |

Standing rule for this screen, added 2026-09-08 and worth stating as a requirement rather than as an
implementation note: **anything that describes the messages must derive from `data()`.** Charts
describe the narrowed population; the filter *controls* (the status chips) are counted over the
fetched rows, so selecting one cannot delete the control that switches it off. The distinction is
deliberate and is the reason `counts()` and `statusMix()` read different collections.

Required additions to the Queue toolbar: a **Job id** and a **Run id** input, each accepting a
comma-separated list, both sent to the server as `jobId` / `jobQId` arrays. Still not built.

### 4.3 Dialogs

One: the shared `confirmWith` confirmation before `Mark as failed` / `Mark as interrupted`
(`queue.ts:224-229`). It is `danger: true`, names the run and the job, and explains when the action
is appropriate. Keep it — the old app fired both actions with no confirmation at all. No other
dialog in this feature.

### 4.4 Loading, empty and error states

All three screens use `TableShell` (`shared/ui/data-table.ts:42-67`), which renders exactly one of:
a centred spinner with "Loading…"; an alert icon, the error text and a **Try again** button wired to
the screen's own reload; or an empty icon with a caller-supplied message. This is the single largest
improvement over the old app, where a failed load raised a 1.5-second toast and then looked
identical to an empty result.

Empty messages must distinguish "no data" from "no matches":

- `JobHistory`: `'No runs with that status.'` when filtered, `'This job has never run.'` otherwise
  (`job-history.html:267`).
- `JobLogs`: `'No entries match your search.'` / `'This run reported no log entries.'`
  (`job-logs.html:130`).
- `Queue`: `'Nothing in the queue for these filters.'` with a clock icon (`queue.html:105-106`).
  Since 2026-09-08 the charts block hides itself in that state as well (`hasInsights`,
  `queue.ts:256-259`): empty rings under a live "Charts" button read as a broken screen rather than
  as an empty filter.

`JobLogs` additionally has a pre-request refusal state for a URL whose ids are not numeric
(`job-logs.ts:241-246`), and `JobHistory` one for a URL that identifies neither a job nor an hour
(`job-history.ts:266-271`). Both are rendered through the same error slot.

The auto-refresh path must stay quiet: `JobLogs.load(true)` does not set `loading`, so the entries
on screen are never replaced by a spinner every five seconds.

### 4.5 Dark and light mode

No screen may hard-code a colour. Text and surfaces use the `--text-*`, `bg-raised`, `bg-sunken`,
`bg-code` and `border-subtle` tokens; status colours come from `statusColor`
(`shared/charts/status-color.ts:13-39`), which returns `--series-*` tokens with a different step per
theme precisely so a chart stays legible on a dark card. `JobLogs.toneOf` (`:277-284`) returns
`--color-crit-500` / `--color-warn-500` / `--color-ok-500` / `--border-strong`, all themed. The stall
colouring in `coloured` (`:120-131`) does the same.

### 4.6 Responsive behaviour

- Chart blocks are `grid gap-3 lg:grid-cols-3`, collapsing to one column below `lg`
  (`job-history.html:214`, `queue.html:55`). The history duration card spans 2 and the flag split
  spans 3 so the grid always tiles — the comment at `job-history.html:212-213` is the reason.
- The detail grid is `md:grid-cols-2 xl:grid-cols-4` (`job-history.html:70`) and
  `sm:grid-cols-2 lg:grid-cols-3` (`job-logs.html:29`).
- Tables scroll inside `overflow-x-auto` within `TableShell`, and long lists scroll inside
  `scroll-table` so the toolbar and pager stay put (`data-table.ts:63-70`).
- Toolbars are `flex flex-wrap`, so the date inputs, search and Clear wrap rather than overflow.

---

## 5. Backend requirements

### 5.1 Endpoints

Role is the effective minimum after the hierarchy in `MethodSecurityConfig.java:27-30`
(`PLATFORM_ADMIN > TENANT_ADMIN > TENANT_USER`), so `TENANT_USER` means "any signed-in user".

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/message.json/fetchLogs` | `TENANT_USER` | Queue messages in a date range, optionally narrowed by job ids, run ids and statuses. Returns `{ sourceJobQueues, jobStatusStatistic }`. `fromDate` and `toDate` are mandatory. |
| DELETE | `/message.json/failJobLogs?jobQId=` | `TENANT_USER` | Forces one run to `Failed`. Refuses unless its current status is exactly `Queue`. Writes an audit line, sets `end_time`, flips the parent job's `job_running_status`, and mails if the job has `skipJob` set. |
| DELETE | `/message.json/interruptJobLogs?jobQId=` | `TENANT_USER` | Forces one run to `Interrupt`. **No status precondition today** — see §7 and §12.2. |
| PUT | `/message.json/changeJobStatus` | `TENANT_USER` | Appends an audit line (`messageType: AUDIT_LOG`) or rewrites a run's status, message and end time (`QUEUE_DETAIL`). Called by no client. |
| GET | `/sourceJob.json/fetchSourceJobQueueListWithJobId?jobId=` | `TENANT_USER` | Every run of one job, newest first, as `{ jobQueues: [...] }`. Refuses an unowned or deleted job. |
| GET | `/sourceJob.json/findSourceJobAuditLog?jobId=&jobQueueId=` | `TENANT_USER` | One run's merged DB + OpenSearch log lines plus the job and the run: `{ auditLogs, sourceJob, sourceJobQueue }`. |
| GET | `/dashboard.json/weeklyHrRunningStatisticsDimensionDetail` | `TENANT_USER` | Runs matching any combination of `targetDate`, `targetHr`, `jobStatus`, `jobId` — all optional. Returns `{ sourceJobQueues }`, plus `{ sourceJob, sourceJobStatistics }` when `jobId` is given. |

Every one of these answers HTTP 200 with `{ status: 'SUCCESS' | 'ERROR', message, data }`. HTTP 500
with a fixed `INTERNAL_ERROR_500` body is the only other outcome, raised by the controller's blanket
catch. `status`, not the HTTP code, is the success signal
(`scheduler1/next/src/app/core/api/api.config.ts:8-15`).

### 5.2 Services

- **`MessageQServiceImpl`** (`process/src/main/java/process/model/service/impl/MessageQServiceImpl.java`).
  Owns all four `message.json` operations. Delegates every write to `BulkAction`
  (`changeJobStatus`, `changeJobQueueStatus`, `saveJobAuditLogs`, `changeJobQueueEndDate` —
  `BulkAction.java:44-87`, `:173-175`), which no-ops with a warning when the row is missing rather
  than throwing. Carries its **own private copy** of the ownership rule at `:130-137`, which is the
  subject of §12.1.
- **`SourceJobServiceImpl`** (`:390-418`, `:455-478`, `:606-623`). The read paths. `getSourceJobQueueDto`
  is the only mapping from `JobQueue` to the wire, and it copies ten of the entity's fourteen
  columns — `bucket`, `outputFolder` and `status` are never sent.
- **`DashboardServiceImpl`** (`:187-271`). The drill-down. Parses the raw `Object[]` rows positionally
  and enriches with the job and its all-time statistics when a `jobId` was supplied.
- **`QueryService`** (`:404-423`, `:425-464`). The SQL. Also the single place tenancy is applied for
  the two raw-SQL endpoints, via `tenantClause` (`:212-217`).
- **`OpenSearchAuditLogClient`** (`:186-195`). `searchByJobQueueId`, capped at `MAX_HITS = 5000`
  (`:34`), returning an empty list when OpenSearch is not configured so the DB rows still render.
- **`JobEventPublisher`** (`process/src/main/java/process/socket/JobEventPublisher.java:40-67`).
  Publishes `job.status` and `job.log`, both carrying `jobQueueId`, to `/topic/jobs.{tenantId}` and
  `/topic/jobs.all`. Called only from `NotifyServiceImpl` (`:74`, `:118`, `:142`) — the worker
  callback path — and from nowhere in `MessageQServiceImpl`.

---

## 6. Database requirements

### 6.1 Tables

**`job_queue`** — one execution of a job (`process/src/main/java/process/model/pojo/JobQueue.java`).

| Column | Field | Notes |
|---|---|---|
| `job_queue_id` | `jobQueueId` | PK, sequence `job_queue_source_Seq` from 1000 |
| `job_id` | `jobId` | FK → `source_job(job_id)`, `V13.0-job-fk-constraints.yaml`; indexed `idx_job_queue_job_id` |
| `start_time`, `end_time`, `skip_time` | | `TIMESTAMP`, all nullable |
| `job_status` | `jobStatus` | enum string, not null |
| `job_status_message` | | `TEXT` |
| `bucket`, `output_folder` | | written at dispatch (`BulkAction.java:162-163`), **never read back** |
| `skip_manual`, `run_manual` | | `Boolean` — nullable, and null is meaningful |
| `job_send` | `jobSend` | primitive `boolean` |
| `date_created` | | not null, set by `@PrePersist` |
| `status` | | `Status` enum; `Delete` rows are excluded by `fetchLogs` but not by the JPA read path |

**`job_audit_logs`** — worker log lines for one run
(`process/src/main/java/process/model/pojo/JobAuditLogs.java`).

| Column | Field | Notes |
|---|---|---|
| `job_audit_log_id` | | PK |
| `job_queue_id` | | FK → `job_queue`; indexed `idx_job_audit_logs_job_queue_id` |
| `external_id` | | `unique`; load-bearing for the OpenSearch upsert's `on conflict do nothing` (`JobAuditLogRepository.java:25-27`) |
| `log_detail` | | `TEXT`, not null |
| `date_created`, `status` | | |

**`source_job`** — read-only here, for ownership and for the context panel.

### 6.2 Tenancy

Neither `job_queue` nor `job_audit_logs` carries a `tenant_id`, and neither declares a Hibernate
`@Filter` — verified by reading both entity files in full. `TenantFilterHelper.enableIfNeeded` is
therefore a no-op for them, and `TenantFilterDeclarationTest` does not cover them because its scan
only looks at entities that have a `tenant_id` column
(`process/src/test/java/process/model/pojo/TenantFilterDeclarationTest.java:75-90`). Both inherit
their scope from `source_job` through the join, which means **every** isolation guarantee in this
feature is a service-layer check. That is a design decision, not a defect, but it is the reason §8
has to be read carefully.

### 6.3 Migrations

None required for the behaviour described in §3. Everything needed already exists as a column.
Two candidates if §13 items are taken:

- Nothing for exposing `bucket` / `output_folder` — the columns are there; only the DTO needs the
  two fields.
- A `job_queue (date_created)` index if server-side paging is added to `fetchLogs`, since the range
  predicate is `cast(jq.date_created as date) between …` (`QueryService.java:469-470`) and the cast
  makes the current indexes useless for it. Not needed at today's volumes; note it, do not add it
  speculatively.

---

## 7. Validation

| Rule | Where enforced | Verdict |
|---|---|---|
| `fetchLogs` requires `fromDate` | Server (`MessageQServiceImpl.java:58-59`) and client (`queue.ts:52-61, 185-186` never sends an empty one) | **Both** |
| `fetchLogs` requires `toDate` | Server (`:60-62`) and client (`:186`) | **Both** |
| Dates must be `yyyy-MM-dd` | Server (`QueryService.java:173-182`, throws `IllegalArgumentException` → 500) | **Server** |
| `jobStatus` must be one of nine names | Server (`QueryService.java:201-210`) | **Server**; the client only ever sends values it read back from the server |
| `failJobLogs` requires `jobQId` | Server (`:141-143`) plus Spring's required `@RequestParam` | **Server** |
| A run may be failed only from `Queue` | Server (`MessageQServiceImpl.java:149-151`) **and** old client (`queue-message.component.html:175` disables the button otherwise) | Server-enforced; **the new client no longer agrees** — see §12.3 |
| A run may be interrupted only from `Running`/`Start` | Old client only (`queue-message.component.html:180`); new client allows `Queue` too via `inFlight` (`queue.ts:259-262`) | **Client-only — a finding.** §12.2 |
| `changeJobStatus` requires `messageType` and `jobQueueId` | Server (`:189-195`) | **Server** |
| A supplied `jobId` must match the queue row's | Server (`:204-207`) | **Server**, and tested (`MessageQServiceImplTenantIsolationTest.java:126-139`) |
| `findSourceJobAuditLog` requires `jobQueueId` | Server (`SourceJobServiceImpl.java:393-395`) | **Server** |
| The queue row must belong to the job named | Server (`:403-404`) | **Server** |
| A deleted job has no readable history | Server (`:399-402`, `:467-469`) | **Server** |
| Both route ids must be numeric | Client (`job-logs.ts:29-33`) | **Client**, deliberately — it converts a Java type-conversion 500 into a sentence. The server is still authoritative on the ids themselves. |
| `jobId`/`jobQId` are numeric | Server, by type — `Set<Long>` on the DTO (`MessageQSearchDto.java:18-19`) | **Server** |

**The one client-only rule is the interrupt precondition**, and it matters: hiding the menu is the
only thing preventing an operator, or anyone with a signed-in session and `curl`, from rewriting a
run that completed weeks ago.

---

## 8. Security

### 8.1 Who may do what

| Actor | Read run history / logs | Read the queue | Fail / interrupt a run |
|---|---|---|---|
| `PLATFORM_ADMIN` | Every tenant's, and platform-owned jobs | Every tenant's | Any run |
| `TENANT_ADMIN` | Its own tenant's only | Its own tenant's only | Any run in its own tenant |
| `TENANT_USER` | Its own tenant's only | Its own tenant's only | **Any run in its own tenant** — identical to `TENANT_ADMIN` |
| Signed out | Nothing | Nothing | Nothing |

There is no per-user narrowing anywhere in this feature: a `TENANT_USER` sees and can force runs of
jobs it neither created nor is assigned to. That matches the old app and matches `source-jobs`,
where run/delete/skip are also `TENANT_USER`. It is recorded here as a deliberate reading of the
current design, not as a defect — but it is a question worth putting to a human (see the synthesis
document's open questions).

### 8.2 The four layers, endpoint by endpoint

**Layer 1 — frontend guard.** `authGuard` + `passwordChangeGuard` on all four routes; no `minRole`
(`app.routes.ts:77-96`). Correct: every endpoint behind them is `TENANT_USER`. Not enforcement.

**Layer 2 — controller `@PreAuthorize`.** `MessageQRestApi.java:21` and `SourceJobRestApi.java:29`
and `DashboardRestApi.java:19` all declare `hasRole('TENANT_USER')` at class level, and **no method
in any of the three overrides it** — verified by reading all three files. So the non-repeatability
trap does not bite here. What this layer does *not* do is separate reads from writes:
`failJobLogs`, `interruptJobLogs` and `changeJobStatus` sit under exactly the same annotation as
`fetchLogs`.

**Layer 3 — service rule.** This is the layer that actually enforces tenancy for this feature, and
the two families disagree with each other:

- `SourceJobServiceImpl` uses the shared helper: `isOwnedByCaller` → `TenantOwnership.isOwnedByCaller`
  (`:104-106`), which refuses a caller with no tenant and refuses a platform-owned row to a tenant
  (`TenantOwnership.java:35-41`). `findSourceJobAuditLog` and `fetchSourceJobQueueListWithJobId` both
  call it before touching `job_queue` or `job_audit_logs`, and `findSourceJobAuditLog` additionally
  requires the run to belong to the named job.
- `MessageQServiceImpl` does **not**. It has a private `isJobOwnedByCaller` at `:130-137` that
  compares with a bare `Objects.equals`. See §12.1.
- `DashboardServiceImpl:246-247` has a third copy, also a bare `Objects.equals`, guarding only the
  `sourceJob` enrichment.
- The two raw-SQL endpoints apply tenancy as a string clause in `QueryService.tenantClause`
  (`:212-217`), which returns the **empty string** when the caller has no tenant. See §12.1.

**Layer 4 — Hibernate filter.** Absent by design: neither `JobQueue` nor `JobAuditLogs` declares
`tenantFilter`, so `enableIfNeeded` does nothing for them. It is enabled for `SourceJob`, which is
what makes the ownership lookups in layer 3 the whole of the defence — and `findById`, which every
one of those lookups uses, is not filtered anyway. The design is coherent; it just leaves no
backstop, so a service-layer mistake is a tenancy breach with nothing behind it.

### 8.3 Secrets

Nothing in this feature returns credentials, keys or store locations. `getSourceJobQueueDto`
(`SourceJobServiceImpl.java:606-623`) is an explicit field-by-field copy rather than serialising the
entity, which is the right shape. `job_status_message` and `log_detail` are worker-authored free
text and are rendered as text, never as HTML, in the new app (`job-logs.html:176`, `:199`, `:212`) —
the old app's console view had to strip tags (`job-logs.component.ts:278-283`), which suggests the
data has historically contained markup.

---

## 9. Error handling

| Failure | What the user sees |
|---|---|
| Queue loaded with no date range | Cannot happen from the UI; the screen seeds seven days. A hand-made request gets `{status:'ERROR', message:'FromDate missing.'}` rendered in the `TableShell` error slot with a Try again button. |
| Malformed date reaches `requireValidDate` | `IllegalArgumentException` escapes to the controller's catch → HTTP 500 with the generic body. The screen shows `'Could not load the queue.'` (`queue.ts:203`). The reason is known to the code and is not told to the user — a §12 item. |
| Run history opened with neither a job nor an hour | `'Open a job, or pick an hour on the dashboard, to see runs.'` (`job-history.ts:269`) — no request is made. |
| A job the caller does not own, or a deleted job | `'SourceJob not found with <id>.'` from the server, shown in the error slot. Deliberately indistinguishable from "does not exist". |
| Logs opened with a non-numeric id | `'That link is missing the run it refers to. Open the run from the job's history instead.'` (`job-logs.ts:243-245`) — no request is made. |
| A run id that is not that job's | `'JobQueue not found with <q> for job <j>.'` (`SourceJobServiceImpl.java:406`). |
| Fail on a run that is not `Queue` | Toast: `"Only 'In Queue' Job can be fail."` (`MessageQServiceImpl.java:150`, surfaced by `queue.ts:244`). Awkward wording, and today reachable from the UI. |
| Fail/interrupt a run in another tenant | Toast `'JobQueue not found'` — the same text as a run that does not exist, which is the correct disclosure. |
| Network failure on any load | `err?.error?.message` if present, else a screen-specific fallback: `'Could not load the run history.'`, `'Could not load the logs.'`, `'Could not load the queue.'`. Each with a Try again button. |
| The context panel fails but the runs load | Nothing. The run list renders and the detail card is omitted (`job-history.ts:177-178`). |
| OpenSearch unavailable | Nothing visible; `searchByJobQueueId` returns empty and the DB rows render alone (`OpenSearchAuditLogClient.java:187-189`). |
| Copy to clipboard fails | `'Could not copy the message.'` toast (`job-history.ts:59`). |

In the old app every one of these was a 1.5-second toast over an empty table, and there was no retry
control anywhere (`.ai/discovery/frontend-old.md:961-963`).

---

## 10. Dependencies

- **`source-jobs` (3)** — hard. A run only exists because a job dispatched it; every read path here
  starts by resolving the `source_job` row and asking whether the caller owns it, and
  `fetchSourceJobQueueListWithJobId` is shared with the jobs list's expandable run-duration strip
  (`features/jobs/jobs.ts:391-422`) and with the assistant (`assistant/job-assistant.ts:175`).
  Changing that endpoint's payload changes three screens.
- **`source-tasks` (6)** and **`platform-configuration` (15)** — transitively. A run cannot be
  produced end to end without a task and a task type with a real Kafka topic behind it, which is the
  critical path recorded in `.ai/discovery/features.md:5.3`.
- **`authentication-and-access` (1)** — the token, the role and the tenant claim that
  `TenantContext` is filled from (`JwtAuthenticationFilter.java:40-44`).
- **`dashboard` (2)** — consumer and producer. It owns `weeklyHrRunningStatisticsDimensionDetail`,
  which this feature's history screen calls, and its heat-map cells are the only way to reach
  `jobs/history` (`features/dashboard/dashboard.ts:213`, `:238`).
- **`job-assistant` (5)** and **`reports` (10)** — downstream consumers of `job_queue`. Neither is
  changed by this work, but both break if the run payload changes shape.
- **Infrastructure** — PostgreSQL for both tables; OpenSearch, optional, for the log merge; Kafka
  and the workers, which are what write the rows in the first place; STOMP over SockJS for the
  push events this feature does not yet consume.

**Tests.** *Re-checked 2026-09-08.* Backend: `MessageQServiceImplTenantIsolationTest` (8 tests, all
on `changeJobStatus` — the one endpoint no client calls). Nothing covers `fetchLogs`, `failJobLogs`,
`interruptJobLogs`, `findSourceJobAuditLog` or `fetchSourceJobQueueListWithJobId`; no E2E test
touches this feature. **Unchanged.**

Frontend: `features/queue/queue.spec.ts` was added on 2026-09-08 — 10 cases, all regression tests
for the single-population rule (§2.2). `features/jobs/history/` and `features/jobs/logs/` still
contain no `.spec.ts` at all; the six job-related specs that exist
(`job-actions`, `notify-summary`, `stalled`, and three under `assistant/`) belong to `source-jobs`
and `job-assistant`. The workspace now holds 46 spec files.

---

## 11. Acceptance criteria

Fixtures assumed throughout: tenant **A** with jobs `A1` (has runs in several states) and `A2`;
tenant **B** with job `B1` and a run `QB` in state `Queue`; a `TENANT_USER` and a `TENANT_ADMIN` in
A, a `TENANT_USER` in B, and a `PLATFORM_ADMIN`.

**Run history**

1. A `TENANT_USER` in A opening `/jobs/A1/history` sees one table row per `job_queue` row of `A1`,
   newest first, and the count in the `TableShell` heading equals the number of rows returned.
2. The same user opening `/jobs/B1/history` sees the error slot with a message containing
   "not found" and a Try again button — no rows. **Positive control:** the same user, same session,
   opening `/jobs/A1/history` sees rows (criterion 1).
3. A `PLATFORM_ADMIN` opening `/jobs/B1/history` sees `B1`'s runs.
4. Clicking a status chip filters the table to that status and leaves the heading's total unchanged;
   clicking it again clears the filter.
5. Opening `/jobs/A1/history?targetDate=<d>&targetHr=<h>` shows only runs created in that hour, and
   a "Filtered to" bar with a control that returns to `/jobs/A1/history`.
6. Opening `/jobs/history?targetDate=<d>&targetHr=<h>` shows runs of **every** job in A for that
   hour, the table gains a Job column, and the control in the "Filtered to" bar reads "Back to
   dashboard".
7. In that all-jobs view, the Logs button on a row whose `jobId` is `A2` navigates to
   `/jobs/A2/runs/<jobQueueId>/logs` and that page loads the run's entries. **This fails today** —
   §12.4.
8. Opening `/jobs/history` with no query params shows the error slot reading "Open a job, or pick an
   hour on the dashboard, to see runs.", and no HTTP request is made.
9. A run whose `jobStatusMessage` is longer than 60 characters shows a clickable truncated cell;
   clicking it opens a `<pre>` beneath the row containing the whole message and a Copy button.
10. Deleting job `A2` (status `Delete`) then opening `/jobs/A2/history` shows the error slot, not an
    empty table. **Positive control:** `/jobs/A1/history` still lists rows.

**Run logs**

11. Opening `/jobs/A1/runs/<q>/logs` for a run of `A1` lists that run's audit entries oldest-first
    in all three views, and the Job & queue detail card shows the run's status, start, end and
    duration.
12. Opening `/jobs/A1/runs/<q>/logs` where `<q>` belongs to `A2` shows the error slot with a message
    naming both ids and no entries. **Positive control:** the correct pairing (criterion 11) lists
    entries.
13. A user in B opening `/jobs/A1/runs/<q>/logs` sees "SourceJob not found with A1." and no entries.
    **Positive control:** the same user opening a run of `B1` sees entries.
14. Opening `/jobs/abc/runs/xyz/logs` shows "That link is missing the run it refers to…" and the
    network panel records **no** request to `findSourceJobAuditLog`.
15. On a run whose status is `Running`, a Live/Paused control is present and, while Live, a request
    to `findSourceJobAuditLog` is made every 5 seconds without the entry list blanking; on a run
    whose status is `Completed` the control is absent and no repeat request is made.
16. Switching Timeline → Table → Console keeps the same filtered entry set and the same order in all
    three.
17. With more than one gap present, the Timing block names the eight longest gaps and states what
    share of the span between the first and last entry they account for.

**Queue**

18. Opening `/queue` issues one `fetchLogs` POST whose body carries a `fromDate` seven days back and
    a `toDate` of today, and lists the returned rows paged.
19. Changing either date input re-issues `fetchLogs` with the new range.
20. Clicking a status chip re-issues `fetchLogs` with that status in `jobStatuses`; clicking it again
    removes it. The chip set is a *server-side* filter, not a client one — the request is observable.
21. Entering a job id in the Job id field re-issues `fetchLogs` with that id in `jobId`, and the
    table shows only that job's runs. **Not built today** — §13.
22. A `TENANT_USER` in A sees no row whose `jobId` belongs to B, whatever the date range.
    **Positive control:** the same request as a `PLATFORM_ADMIN` returns rows from both tenants.
23. The actions menu appears on a row in `Queue`, `Start` or `Running` with no end time, and on no
    other row.
24. `Mark as failed` on a `Queue` row opens a confirmation naming the run and the job; confirming it
    sends `DELETE …/failJobLogs?jobQId=<id>`, shows a success toast, reloads, and the row's status
    is `Failed` with an end time set.
25. `Mark as failed` is not offered on a `Running` row. **Today it is offered and the server refuses
    it** — §12.3. **Positive control:** it is offered, and succeeds, on a `Queue` row (criterion 24).
26. `Mark as interrupted` on a `Running` row sends `DELETE …/interruptJobLogs?jobQId=<id>` and the
    row becomes `Interrupt` with an end time.
27. `DELETE …/interruptJobLogs?jobQId=<id>` sent directly against a run already in `Completed` is
    refused by the server with an ERROR response, and the run's status and end time are unchanged.
    **This fails today** — §12.2. **Positive control:** the same call against a `Running` run of the
    same job succeeds.
28. A user in B sending `failJobLogs` or `interruptJobLogs` for a run of `A1` gets
    `{status:'ERROR', message:'JobQueue not found'}` and nothing in `job_queue` or `job_audit_logs`
    changes. **Positive control:** the same user on a run of `B1` in `Queue` succeeds.
29. Forcing a run to `Failed` from `/queue` updates an open `/jobs` list in another browser tab
    without a manual reload. **Not true today** — §13.
30. Every row visible in the table is counted in the Outcomes donut for the same filters, and the
    donut's total equals the table's total, or the screen states accurately why they differ.
    **MET 2026-09-08.** The donut is `statusMix()` over `data()` (`queue.ts:169-170`), the same
    collection `paged()` slices, so the totals agree by construction. `queue.spec.ts:55-65` asserts
    it directly: with a search that narrows four rows to two, the ring sums to two.

    **30a.** *Added 2026-09-08.* Applying **any** narrowing — the search box, a status chip, or a date change
    — moves the Outcomes donut, the failure-rate sentence, Busiest jobs, Volume by day, How long runs
    took and How runs were started, all together and to the same population the table pages.
    **Positive control:** clearing it restores all six and the table to the same numbers.
    (`queue.spec.ts:67-75` and `:93-127` cover the search half of this; the chip and date halves go
    through the server and are observable as a refetch.)

    **30b.** *Added 2026-09-08.* The all-time figure beside the donut is labelled as all-time, appears only
    when it exceeds the fetched row count, and no chart is drawn from it. **Positive control:** with
    the Failed chip selected and one Failed row returned, the ring shows one segment of one while the
    footnote reads the server's whole-history total; the screen does not claim the two describe the
    same thing. (`queue.spec.ts:77-91`.)

    **30c.** *Added 2026-09-08.* Every narrowing in force is named in a removable pill above the charts, and
    removing one restores that dimension only. A search pill clears in the browser; a status pill
    refetches. **Positive control:** the "N of M messages" count appears only when the two numbers
    differ, so a server-applied status filter alone does not render "4 of 4".
    (`queue.spec.ts:156-184`.)

    **30d.** *Added 2026-09-08.* A status chip that is selected stays visible even when the search box
    excludes its last row, so it can be switched off. **Positive control:** the chip *counts* are
    those of the fetched rows, not of the filtered ones — with four rows fetched and a search
    matching none, the chips still read Completed 3 / Failed 1. (`queue.spec.ts:144-154`.)

    **30e.** *Added 2026-09-08.* A filter that empties the table also hides the charts panel, rather than
    leaving a live "Charts" button over empty rings. (`queue.spec.ts:129-136`.)

**Payload consistency**

31. For one known run of `A1`, the row returned by
    `weeklyHrRunningStatisticsDimensionDetail?jobId=A1&targetDate=<its date>&targetHr=<its hour>`
    and the row for the same `jobQueueId` returned by `fetchSourceJobQueueListWithJobId?jobId=A1`
    carry identical `jobStatus`, `startTime`, `endTime`, `skipTime`, `dateCreated`, `jobSend`,
    `runManual`, `skipManual` and `jobStatusMessage`. The two read the same row through two
    different code paths — one JPA, one a positional parse of `select job_queue.*` — and a
    divergence is §12.10.

**Tenancy and roles, across all three screens**

32. A token whose role is `TENANT_USER` and whose `tenantId` claim is absent receives **no rows**
    from `fetchLogs`, `weeklyHrRunningStatisticsDimensionDetail` or
    `fetchSourceJobQueueListWithJobId`. **Today the first two return every tenant's rows** — §12.1.
    **Positive control:** the same request with a `PLATFORM_ADMIN` token returns rows, and with a
    normal tenant-A token returns A's rows only.
33. The same tenant-less `TENANT_USER` token cannot fail or interrupt a run of a job whose
    `tenant_id` is null. **Positive control:** a `PLATFORM_ADMIN` can.
34. Every one of the four routes is reachable by a `TENANT_USER` — none redirects to
    `/unauthorized`.
35. Signed out, all four routes redirect to `/login` carrying the requested path as `returnUrl`.

**Presentation**

36. In light and in dark, every status pill and every chart series in all three screens takes its
    colour from a `--series-*` or `--color-*` token; no rendered element carries a literal hex value.
37. At 375px wide, all three screens scroll vertically only; each table scrolls horizontally inside
    its own container and the chart grids stack to one column.
38. Each screen shows a spinner while loading, a message plus a Try again button on error, and a
    distinct message for "no data" versus "no matches" — verifiable by forcing each of the three
    states.

---

## 12. Known issues

*Reviewed 2026-09-08. An entry fixed since it was written is marked **FIXED** with the date and what
closed it, and is kept rather than deleted; 12.14 and 12.15 were found on 2026-09-08 and are not
fixed. Every other entry was re-read against the code on that date and stands unchanged.*

### 12.1 `MessageQServiceImpl` and `QueryService` let a tenant-less caller through — OPEN

Two separate places, one cause.

**`QueryService.tenantClause` (`:211-217`):**

```java
if (TenantContext.isPlatformAdmin() || ProcessUtil.isNull(TenantContext.getTenantId())) {
    return "";
}
```

An empty clause is no restriction. Any principal that is not a platform admin and reaches the server
without a `tenantId` claim therefore reads **every tenant's** queue rows through `fetchLogs`
(`:440`, `:457`) and through `weeklyHrRunningStatisticsDimensionDetail` (`:407`) — which is
`/queue` and `/jobs/history` respectively. The intended reading is stated in
`process/src/main/java/process/security/TenantOwnership.java:14-16`: *"A context with no tenant owns
nothing, so it is refused outright."* This clause does the opposite.

**`MessageQServiceImpl.isJobOwnedByCaller` (`:130-137`), re-read 2026-09-08:**

```java
private boolean isJobOwnedByCaller(Long jobId) {
    if (TenantContext.isPlatformAdmin()) {
        return true;
    }
    return this.sourceJobRepository.findById(jobId)
        .map(job -> Objects.equals(job.getTenantId(), TenantContext.getTenantId()))
        .orElse(false);
}
```

The platform-admin short-circuit at the top is present and correct. The finding is the line below
it, and it is unchanged: a bare `Objects.equals` answers **true** when both sides are null — so a
tenant-less non-admin caller owns every platform-owned job and may fail or interrupt its runs. This
is precisely the defect class
`TenantOwnership`'s javadoc says the shared helper exists to prevent (`:6-8`: *"Every service had
grown its own private copy of it, and the copies had begun to disagree about the rows that carry no
tenant at all"*), and precisely the one
`process/src/test/java/process/model/service/impl/StorageConnectionTenantlessCallerTest.java:32-46`
was written for on another feature. `SourceJobServiceImpl` already uses the helper (`:104-106`);
`MessageQServiceImpl` and `DashboardServiceImpl:246-247` do not.

`MessageQServiceImplTenantIsolationTest.anEmptyContextIsTreatedAsUntrusted` (`:190-201`) looks like
it covers this and does not: its fixture job belongs to tenant B, so `Objects.equals(2002L, null)`
is false and the test passes for the wrong reason. No test uses a null-tenant job.

**Reachability, honestly.** `addSourceJob` refuses a task with no owning tenant
(`SourceJobServiceImpl.java:135-137`) and the bulk path copies the task's tenant (`SourceJobBulkServiceImpl.java:228`),
so no *new* null-tenant job can be created through the API. `source_job.tenant_id` is nevertheless a
nullable FK (`V12__add_tenant_user_fk_constraints.sql:30` adds the constraint, not `NOT NULL`), so
such rows are schema-permitted and may exist as seed or legacy data. Whether any exists today is
**not verified** — I did not query the database. The `tenantClause` half needs no such row at all:
a tenant-less caller reads everything regardless.

Severity: the `tenantClause` half is a cross-tenant read; the `isJobOwnedByCaller` half is a
cross-tenant write conditional on a row shape that may not exist.

### 12.2 `interruptJobLogs` has no status precondition on the server — OPEN

`MessageQServiceImpl.java:166-185` checks that the run exists and that the caller owns it, and then
unconditionally sets the job's running status to `Interrupt`, the run's status to `Interrupt`, writes
an audit line and stamps `end_time` with `LocalDateTime.now()`. Its sibling `failJobLogs` does have
the check (`:148-151`). Re-read 2026-09-08: unchanged.

Both frontends restrict the button — the old one to `Running`/`Start`
(`queue-message.component.html:180`), the new one to `inFlight` (`queue.ts:346-348`) — so the only
enforcement of this rule anywhere is in the browser. A `DELETE
/message.json/interruptJobLogs?jobQId=<any run of your own tenant>` overwrites the recorded outcome
of a run that completed successfully weeks ago, along with its end time, and appends a log line
saying it was interrupted. The run's real history is not recoverable from the row.

### 12.3 The new Queue offers "Mark as failed" where the server refuses it — OPEN

`inFlight` (`queue.ts:346-348`) admits `Queue`, `Start` and `Running`, and the template shows both
menu items for all three (`queue.html:154-168`). The server accepts a fail only from `Queue`
(`MessageQServiceImpl.java:148-151`). So on a `Start` or `Running` row the operator confirms a
danger dialog and is answered with `"Only 'In Queue' Job can be fail."` — a message that is both
ungrammatical and, at that point, too late. Re-read 2026-09-08: unchanged.

One thing about this path *was* fixed since the entry was written and is worth recording, because it
means the defect had never been observable: `forceStatus` sent the parameter as `jobQueueId` where
the endpoint declares `jobQId`, so Spring rejected both actions with a 400 before the handler ran and
neither had ever once worked (`queue.ts:322-325` carries the comment). With the name corrected, the
server's refusal message is now what an operator on a `Running` row actually sees.

The old app got this right by disabling the button per status
(`queue-message.component.html:175`, `:180`). The regression came in with the shared actions menu.

### 12.4 The all-jobs history builds its Logs link from the route, not the row — OPEN

Re-read 2026-09-08: `job-history.html:350` still builds the link from `jobId()`. Unchanged.

```html
<a class="btn btn-ghost btn-sm"
   [routerLink]="['/jobs', jobId(), 'runs', run.jobQueueId, 'logs']">
```

On `/jobs/history` — the route the dashboard's TOTAL row navigates to
(`features/dashboard/dashboard.ts:238`) — `jobId()` is `''`. Every row in that view therefore builds
a link with an empty job segment, and the run's logs cannot be opened from the only screen that
lists runs across jobs. The row's own id is available and is already used two cells to the left, in
the Job column added for exactly this case — `[routerLink]="['/jobs', run.jobId, 'history']"` at
`job-history.html:305`.

The old app used the row's id (`job-history-action.component.ts:259-267`), so this is a regression
introduced by the rewrite. Whether the resulting URL 404s to the wildcard or reaches `JobLogs` and
trips its own id validation (`job-logs.ts:29-33`) is **not verified** — either way the logs do not
open.

### 12.5 The queue's status statistics ignore every filter — SERVER HALF OPEN; UI HALF FIXED 2026-09-08

**The server half stands.** `QueryService.fetchJobQLog(messageQSearch, isState = true)` (`:487-491`)
builds:

```sql
select UPPER(jq.job_status), count(*) from job_queue jq
inner join source_job sj on sj.job_id = jq.job_id
where UPPER(sj.job_status) in ('ACTIVE','INACTIVE') <tenant clause>
group by UPPER(jq.job_status)
```

No date predicate, no status predicate, no id predicate — the whole `if (!isState)` block that adds
them (`:468-486`) is skipped. The statistic is the tenant's **all-time** run count per status. The
row query in the same method uses different predicates again — `UPPER(sj.job_status) <> 'DELETE' and
UPPER(jq.status) <> 'DELETE'` (`:471`) — so the two halves of one response still do not agree on
which rows count, and the statistic half additionally counts deleted queue rows that the row half
excludes.

**The UI half is fixed.** As of 2026-09-08 the Outcomes donut is `statusMix()` (`queue.ts:169-170`),
a tally of the same `data()` the table pages, so the ring and the table agree by construction. The
statistic is still read from the payload (`statusStats`, `:166`) but drives no chart; it is rendered
once as `allTimeTotal()` (`:244-245`) beside the donut, only when it exceeds the fetched row count,
labelled "N on record all time" with a tooltip stating exactly what it counts
(`queue.html:65-71`). The false explanation is gone: the screen used to attribute the gap to
*"The server caps how many rows it returns"*, and `fetchJobQLog`'s row query has no `LIMIT` at all,
so nothing was ever capped — the gap was the date range and the filters, which is what the label now
says. `statusStats`' own comment (`:155-165`) records the failure this replaced: with the Failed chip
selected the table showed 4 rows while the ring above drew 48 Completed and the caption called the
screen 8% failed. `queue.spec.ts:77-91` is the regression test.

What remains is the query. Until the statistic carries the same predicates as the rows beside it,
any future consumer of `jobStatusStatistic` will make the same mistake this screen made; the honest
options are to give the `isState` branch the same `where` block, or to stop returning it.

### 12.6 A malformed date returns 500 with a generic body although the reason is known — OPEN

`requireValidDate` throws `IllegalArgumentException("Invalid date -- expected yyyy-MM-dd.")`
(`QueryService.java:167-173`). Every controller in this feature catches `Exception` and answers
`ProcessUtil.INTERNAL_ERROR_500` (`MessageQRestApi.java:37-40`, `DashboardRestApi.java:111-114`), so
the sentence the code already wrote is discarded and the user is told "Could not load the queue."
The project's own non-functional requirement calls this a defect: *"An opaque 500 where the code
already knows the reason is a defect, not a rough edge"* (`.ai/project.md`).

### 12.7 Neither manual queue action publishes a job event — OPEN

Re-checked 2026-09-08: `JobEventPublisher` appears nowhere in `MessageQServiceImpl` (grepped, zero
matches). `MessageQServiceImpl`'s constructor takes five collaborators (`:43-53`) and it is
not among them. The worker callback path publishes both `job.status` and `job.log`
(`NotifyServiceImpl.java:74`, `:118`, `:142`), and the jobs list patches rows from those pushes. So a
run forced to `Failed` from `/queue` changes in the database and the open `/jobs` list keeps showing
it as running until someone reloads.

### 12.8 The history screen fetches the whole job list to learn one name — OPEN

`job-history.ts:242-249` calls `listSourceJob` in the constructor and searches the result for the
job's name. `fetchSourceJobDetailWithSourceJobId` is called two lines earlier
(`:170-180`) and its payload already carries `jobName`, as does the drill-down response
(`:297`). `listSourceJob` returns every job the caller can see with its scheduler and task attached
— roughly 30KB for 41 jobs by the endpoint's own comment (`SourceJobServiceImpl.java:501-507`) — to
read one string that has already arrived twice.

### 12.9 `job_queue.bucket` and `job_queue.output_folder` are written and never read — OPEN

`BulkAction.java:162-163` snapshots the task's bucket and output folder onto the queue row at
dispatch. `getSourceJobQueueDto` (`SourceJobServiceImpl.java:606-623`) does not copy either;
`fetchLogs`'s `select` list names eleven columns and neither of these is among them
(`QueryService.java:464`); and the drill-down selects `job_queue.*` (`QueryService.java:437`) but
its positional parser reads only eleven indices and stops (`DashboardServiceImpl.java:194-241`).
`SourceJobQueueDto` has no field for either. Both frontends therefore show
`job.taskDetail.bucket` instead, which is the task's *current* destination — so after a task is
edited, every historical run misreports where its output went.

### 12.10 The drill-down parses `select job_queue.*` by ordinal — OPEN, still unverified

`QueryService.weeklyHrRunningStatisticsDimensionDetail` selects `job_queue.*`
(`QueryService.java:437`) and `DashboardServiceImpl` reads the result positionally, assuming
index 0 is `job_queue_id`, 1 `date_created`, 2 `end_time`, 3 `job_id`, 4 `job_send`, 5 `job_status`,
6 `job_status_message`, 7 `run_manual`, 8 `skip_manual`, 9 `skip_time`, 10 `start_time`
(`:194-241`). The entity declares fourteen columns, so three — `bucket`, `output_folder` and
`status` — are in the result set and in none of those slots.

`job_queue` has no `CREATE TABLE` in Liquibase; it is created and extended by
`spring.jpa.hibernate.ddl-auto=update` (`.ai/discovery/database.md:21`, `:57-61`), which appends a
new column at the end of the table rather than in declaration order. The physical ordinal positions
of the columns are therefore a property of each environment's migration history, not of the entity
file.

**Not verified.** I did not query a database and cannot say whether the ordinals line up today.
What is verifiable from the code is that nothing makes them line up: the `select` names no columns,
the parser names no columns, and the guard on each field is `if (!isNull(obj[index]))`, so a
mismatch on a nullable column is skipped in silence rather than throwing. This is the read path
behind the old app's entire run-history screen and behind the new app's dashboard drill-down.
Confirming or refuting it needs one query — `select * from job_queue limit 1` — against each
environment. Naming the eleven columns in the `select` removes the question permanently and is a
smaller change than establishing the answer.

### 12.11 `message.json/changeJobStatus` is client-dead but fully exposed — OPEN

No call site in `scheduler1/src` or `scheduler1/next/src`. It is nonetheless a `TENANT_USER` write
that can set any run of the caller's tenant to any `JobStatus`, rewrite its message and end time, and
append audit lines — and it is the **only** endpoint in this feature with test coverage
(`MessageQServiceImplTenantIsolationTest`, 8 tests). Its worker-facing equivalents live on
`NotifyResetApi` behind `X-Worker-Token`, which is where machine callbacks belong.

### 12.12 The queue's status chips collapse once a status is selected — OPEN, and now half-navigable

`counts()` (`queue.ts:124`) derives the chip set from the rows currently loaded, and selecting a chip
narrows the **server** query. After selecting `Failed`, the only rows loaded are `Failed`, so
`Failed` is the only chip rendered — the multi-select the code supports (`selectedStatuses` is an
array, `:294-298`) still cannot be reached through the UI.

Two things changed on 2026-09-08 and neither closes it. Clear is no longer the only way back: the
active-filter strip renders one removable pill per selected status and `clearFilter` toggles that
status off through a refetch (`:133-152`, `queue.html:31-52`), so a reader can undo one selection
without resetting the dates and the search as well. And `counts()` was deliberately left reading
`rows()` rather than `data()` (`:114-123`), so a *selected* chip can no longer be deleted by a search
term that excludes its last row — which would have taken away the only control that switched it off.
Neither makes a second status selectable. The fix is still the same one: derive the chip set from a
statuses call that does not itself obey the status filter, or move the status filter into the
browser.

### 12.13 No test covers this feature's own screens or its live endpoints — BACKEND OPEN; FRONTEND PARTLY CLOSED 2026-09-08

Backend: **unchanged.** The only tests are the eight in `MessageQServiceImplTenantIsolationTest`, all
on `changeJobStatus` — the endpoint no client calls. `fetchLogs`, `failJobLogs`, `interruptJobLogs`,
`findSourceJobAuditLog` and `fetchSourceJobQueueListWithJobId` have none, and no E2E test in
`process/src/test/java/process/e2e/` touches `job_queue`. Given 12.1, 12.2 and 12.5 all live behind
those five endpoints, this is the half that matters.

Frontend: `features/queue/queue.spec.ts` was added on 2026-09-08 — 10 cases covering the
single-population rule, the chip-counting rule, the all-time footnote and the filter strip.
`features/jobs/history/` and `features/jobs/logs/` still contain **no** `.spec.ts`, so
`JobHistory` (333 lines) and `JobLogs` (285 lines) remain untested, including the gap-ranking
analysis at `job-logs.ts:112-193` and the two-endpoint choice at `job-history.ts:263-304` — both of
which are exactly the kind of derived logic a spec would pin cheaply.

### 12.14 The queue's charts are honest about the rows and silent about the range — NEW 2026-09-08

Since the charts began reading `data()`, everything on the screen describes the messages returned for
the current date range and status selection. Nothing on the screen states the **range** itself
outside the two date inputs in the table toolbar, which sit *below* the charts. The active-filter
strip names the search term and each status (`queue.ts:133-141`) and deliberately does not name the
dates.

That is a smaller version of the defect 12.5 records: a reader who scrolls to the Outcomes ring sees
a failure rate with no statement of what period it covers, and the default is a seven-day window
nobody chose. The strip is the natural place for it — one more entry reading
`Range: 2026-09-02 to 2026-09-08`, not removable but stated. Severity: presentational, and cheap.

### 12.15 `byDay` and the row query disagree about which timestamp a run belongs to — NEW 2026-09-08

`byDay` (`queue.ts:221-234`) buckets a row by `dateCreated`, and `fetchJobQLog`'s row predicate is
`cast(jq.date_created as date) between …` (`QueryService.java:469`), so those two agree. But
`durations()` (`:183-202`) and the table's Duration cell (`:336-343`) are computed from
`startTime`/`endTime`, and the Reports screen — which describes the same `job_queue` rows — bounds
its range on `start_time` instead (`QueryService.java:252`). A run queued just before midnight and
started just after therefore falls on one day here and the next day there, and appears in one
screen's seven-day window and not the other's.

Neither screen is wrong on its own terms; the two simply answer "when did this run happen" with
different columns and neither says which. Worth recording now because the Reports screen gained a
failure table fed by *this* feature's `fetchLogs` on 2026-09-08, so the two conventions now meet
inside one page. See `reports.md` K23 for the other half of this.

---

## 13. Missing functionality

*Reviewed 2026-09-08. Nothing in this section was built; one item is now cheaper than it was and the
reason is recorded against it.*

**Lost in the crossing** (present in the old app, absent in the new one):

| Capability | Where it was | What it would take |
|---|---|---|
| Server-side `jobId` / `jobQId` filters on the queue | `queue-message.component.html:33-38`, sent as arrays and consumed at `QueryService.java:473-480` | Two toolbar inputs on `queue.html` and two fields on the request body. The server side already works, and since 2026-09-08 the client has an `activeFilters` strip (`queue.ts:133-152`) the two new filters can register in for free. **S.** |
| The Gantt start→end comparison, with `dataZoom` and click-through to logs | `queue-message.component.ts:234-292`, `:294-304` | A new timeline chart component; `shared/charts/` has no equivalent. This is the only way either app ever showed *overlap* between runs. **L.** |
| The pipeline stage strip on the logs screen | `job-logs.component.ts:11-14`, `:285-308`; `job-logs.component.html:103-118` | A presentational component over `run.jobStatus`; the terminal-alternate and Skip-bypass rules are the whole of the logic. **S.** |
| The server-computed all-time KPI strip on run history | `sourceJobStatistics` from `QueryService.java:386-401`, rendered at `job-history-action.component.html:88-122` | The new screen's `runStats` (`job-history.ts:146-152`) counts only the runs in view, which is a different question in a drill-down. Read the field that already arrives. **S.** |
| Start / End / Skip time and the three flag columns on the queue table | `queue-message.component.html:90-139` — 13 columns against the new screen's 7 | Add columns; the fields are already on the wire. **S.** |
| Per-entry log-gap chart with `dataZoom` | `job-logs.component.ts:213-271` | Deliberately replaced by the top-8 ranked view, with the reasoning written down at `job-logs.ts:135-141`. Recorded as a change, not a regression. |
| Column header mini-charts | `job-history-action.component.html:177-219` | Replaced by the split-bar chart behind the Charts toggle. Recorded as a change. |
| The `from` back-target on the logs screen | `job-logs.component.ts:18-27`, `:310-333` | Moot while the queue has no logs link; becomes relevant the moment it gains one. |

**Never present in either app:**

| Capability | Why it is worth having | What it would take |
|---|---|---|
| A Logs link on the queue table | The queue is where an operator finds a stuck run; the next question is always "what was it doing". Both apps made you go via the job. | One cell. **S.** |
| Live updates on the queue and history screens | `JobEventPublisher` already emits `job.status` and `job.log` with `jobQueueId` (`:40-67`), and `JobEventsService` already declares `job.log` in its union (`core/socket/job-events.service.ts:8-16`). Nothing subscribes but `features/jobs/jobs.ts`. `JobLogs` polls every 5s for data that is being pushed. | Subscribe in three screens; add the publisher to `MessageQServiceImpl` so manual actions emit too. **M.** |
| Stall detection on the queue | `features/jobs/stalled.ts:14-46` already distinguishes "slow" from "stopped reporting" at a 30-minute threshold, and the jobs list uses it. The queue — the screen whose whole purpose is stuck runs — does not import it. | Import and render. **S.** |
| The run's own output location | §12.9. | Two DTO fields, two `select` columns, one cell. **S.** |
| Paging or a bound on run history | `fetchSourceJobQueueListWithJobId` returns every run ever recorded, and `job-history.html` renders all of them with no pager — the only one of the three screens without one. | Client-side pager first (the `createPager` helper the queue uses); server-side paging only if volumes demand it. **S/M.** |
| Export of a run's logs | The logs screen can search and copy one line at a time. Attaching a run's log to a ticket means selecting a scrolling `<pre>`. | A client-side text/CSV download. **S.** |
| Named columns in the drill-down's `select` | §12.10 — `select job_queue.*` read by ordinal, on a table `ddl-auto=update` extends. Naming the eleven columns costs less than establishing whether the ordinals are right. | **S.** |
| A decision on `changeJobStatus` | §12.11. Keep it behind `X-Worker-Token`, restrict it to `TENANT_ADMIN`, or delete it. | Decision first; see the synthesis document. |
| The selected date range stated above the charts | §12.14. Every figure on the queue now describes the filtered rows, and the only statement of *which days* those rows cover is two inputs below the charts. | One more entry in `activeFilters()`, not removable. **S.** |
| Backend tests for the five live endpoints | §12.13. The frontend half was addressed on 2026-09-08; the backend half is where 12.1, 12.2 and 12.5 live, and it has nothing. | A `fetchLogs` tenant-isolation test in the shape of the eight that exist for `changeJobStatus`, plus one status-precondition test each for `failJobLogs` and `interruptJobLogs` — the second of which fails today, which is the point. **M.** |
