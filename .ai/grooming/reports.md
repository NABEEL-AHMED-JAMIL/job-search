# Grooming -- Reports

Feature `reports`, row 10 of [../discovery/features.md](../discovery/features.md). Status **new** --
the old application never had this screen, so nothing below is a parity question. The question is
whether what was built is complete, correct and correctly authorized.

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Purpose

Every other screen in the console answers a question somebody already decided to ask. The jobs list
answers "what is configured", run history answers "what happened to *this* job", the dashboard
answers "how are we doing this week" in a shape somebody chose months ago and nobody can change.

Reports exists for the question that has not been decided yet:

> "Group my runs by whatever I want, measure them however I want, show me the shape of it, and let
> me click on a number to see the actual runs behind it -- then let me take the answer away."

Six things a reader can group by (the task a run belonged to, the job that drove it, the outcome it
ended in, who owns the job, the workspace it belongs to, and the day it started), sixteen ways to
measure a group (how many, how long, how long *usually*, how long at the bad end, and how long the
worker actually spent once the wait is taken out), ten ways to draw the result, and a click on any
number to see the runs that produced it. When they have the answer they can download it, write it
into a bucket, or post it to an endpoint that is waiting for it.

*Amended 2026-09-08.* A builder answers nothing until the reader has built the answer, and the
answers people were building by hand were the same handful every time. So the page now opens on
those -- how many ran, how many failed, how long they took, which tasks are struggling, and what
each failure actually said -- and the builder is one click below, unchanged in what it does. The
question above is still the one the builder exists for; it is no longer the only question the screen
answers.

The unit is the **run** -- one `job_queue` row -- exactly as in `job-runs-and-queue`. Reports creates
nothing, changes nothing and deletes nothing. It is a read plus a file.

---

## 2. Existing behaviour

### 2.1 The old app

There is none. Searching the whole of `scheduler1/src` for `report.json` returns zero matches, and
`scheduler1/src/app/app.routing.ts` declares no reports route. Three old files match the word
"report" case-insensitively (`_component/source-task/task/task.component.html`,
`_component/document-converter/document-converter.component.html`,
`_component/setting/query-engine/query-engine.component.html`) and none of them is a report -- the
word appears in labels and placeholder text. This matches `.ai/discovery/features.md:225`.

Nothing was migrated, and nothing was lost. Sections 2.2 and 2.3 describe the whole of the feature.

### 2.2 The new app -- frontend

*Brought current 2026-09-08. The screen described below is materially larger than the one this
section described when it was written: the pivot builder that used to be the whole of `/reports`
is now a child component behind a toggle, and above it sits a dashboard that answers the common
questions without the reader having to build them. Section 2.2.1 records what changed and what
each change closed.*

Nine files under `scheduler1/next/src/app/features/reports/`: `reports.ts` (780 lines),
`reports.html` (402), `report-pivot.ts` (347), `report-pivot.html` (268), `pivot.ts` (294),
`report-chart.ts` (550), `report-destination-dialog.ts` (84), and two specs -- `pivot.spec.ts`
(200) and `report-destination-dialog.spec.ts` (72).

**Route.** `app.routes.ts:215-219` -- `reports`, lazy, a child of the shell. It carries **no**
`data.minRole` and **no** `canActivate`, so the only gates are the shell's own
`canActivate: [authGuard]` and `canActivateChild: [passwordChangeGuard]`. Unlike the other
deliberately-open routes in the same file it still carries no comment saying the openness was
decided.

**Navigation.** `features/shell/shell.ts:83-84`, inside the *Pipelines* group, after Queue, with
the hint "Group and measure your runs" and a comment above it (`:81-82`) explaining why it sits
beside the runs it summarises rather than under Tools. No `adminOnly` or `platformOnly` flag, so
every signed-in role sees it.

**Load.** `reports.ts:566-609`. `GET {API_BASE}/report.json/runs` with `startDate` and `endDate`
from two signals defaulting to today minus 30 days and today (`:193-194`, `:775-780`). The request
goes through a `Subject` and a `switchMap` (`:566`, `:570`) so two quick date edits cannot land out
of order, and the `catchError` sits **inside** the `switchMap` (`:578-582`) so a failed request does
not terminate the subject and leave every later Refresh pushing into a dead stream. The envelope is
checked for `status === 'SUCCESS'` (`:587`); `truncated` raises a toast and a pill (`:592-593`).

A visit issues **three** requests, not one: the runs feed, the same query over the equally-long
window immediately before it (`loadPriorPeriod`, `:676-715`) so the tiles can state a change, and
`POST /message.json/fetchLogs` narrowed to `Failed`/`Interrupt` for the error text
(`loadFailures`, `:635-669`), which fires only when the range contains a failure (`:636`). The
builder issues none: it takes the rows as an input (`report-pivot.ts:49`), where it used to repeat
the same GET for itself.

**The shape of the payload.** Columnar. Five dictionaries (`task`, `status`, `owner`, `day`,
`tenant`) and a list of rows, each row being
`[taskIdx, statusIdx, ownerIdx, dayIdx, seconds, jobName, runId, tenantIdx, execSeconds]`
(`pivot.ts:10-45`). `withJobDimension` (`pivot.ts:94-106`) then interns the job name that was
already on every row into a sixth dictionary in the browser and appends its index at position 9, so
the reader can group by Job -- the grouping most often wanted after Task -- over data that was
already on the page. `seconds` is **queued to finished**; `execSeconds` is the part the worker
actually spent. Both carry `-1` when unknown, and `-1` is the no-data sentinel everywhere.

**The pivot** (`pivot.ts`). Six dimensions (`:74-81`): Task, Job, Outcome, Owner, Workspace, Day.
Sixteen measures in five labelled groups (`:113-150`): `count` and `distinct` are tallies
(`COUNTING`, `:123`), ten are queued-to-finished durations, and the *Execution* group -- `execAvg`,
`execMedian`, `execMax` (`EXECUTION`, `:153-154`) -- reads `EXEC_SECONDS` instead of `SECONDS`
(`aggregate`, `:185`). `aggregate` (`:181-224`) filters out every `-1` before computing any duration
measure (`:186`), so a dispatched-but-unfinished run is excluded rather than averaged in as a zero,
and the three execution measures keep two decimals (`:196-198`) because the real answer on this
deployment is 0.23s and rounding prints "0s". `buildPivot` (`:245-270`) drops a row-dimension value
with no runs at all (`:257`) but keeps every column, and `rowTotals[ri]` is **re-aggregated over the
whole row** rather than summed from the cells (`:262`) -- the right answer for a median, and
`pivot.spec.ts:127-131` asserts exactly that.

`ADDITIVE` (`pivot.ts:135`) is the new set that governs the charts: `count` and `sum`, and nothing
else. Its comment records the case that produced it -- a mean-duration donut drew 56%/44% for data
whose real split was 92%/8%, because it summed 34s and 27s and called 61s the whole.

**The page** (`reports.ts` + `reports.html`). One page, top to bottom:

| Region | Lines (`reports.html`) | What it holds |
|---|---|---|
| Page head | `:2-19` | Title, a "Build your own view" toggle, Refresh disabled while loading |
| Range card | `:23-102` | Two `<input type="date">` firing `load()` on change; a run-count pill; **five filter selects**; a "capped" pill and a sentence when truncated |
| Filter strip | `:104-120` | One removable pill per active filter, a Clear all, and "N of M runs" |
| Loading | `:122-126` | Spinner card, "Reading your runs…" |
| Error | `:127-142` | Alert icon, the message, and either Try again or **Reset to the last 30 days** |
| Empty | `:143-150` | Chart icon, "No runs started in this range." |
| Overview | `:154-180` | Four `app-stat-tile`s: Runs started, Failed, Success rate, Median duration |
| Outcomes and timing | `:183-234` | Outcome donut, duration histogram, runs-by-day bar chart |
| Task health | `:236-307` | One row per task that ran, worst first |
| What failed, and why | `:309-384` | The error text per failed run, with drill-through |
| The builder | `:391-400` | `<app-report-pivot>`, hidden rather than destroyed |

The loading, error and empty states at `:122-150` are handled by the page itself. The error card
distinguishes a request that failed from a range that cannot succeed: only when `rangeValid()` is
true is a "Try again" offered (`:135-136`); an invalid range gets "Reset to the last 30 days"
(`:137-141`), because retrying a start-after-end range sends the reader round the same loop for ever.

**Filters.** Five signals -- task, job, outcome, owner, workspace (`reports.ts:123-127`) -- narrow
one `data()` computed (`:176-190`), and `data()` is what the tiles, all three charts, the task
table, the failure table *and* the pivot builder read. The predicate lives in exactly one place, so
a filter cannot reach some of the page and miss the rest. The option lists are built from the **raw**
payload (`:130-134`) so choosing one never empties the other pickers, and only `rows` is narrowed --
the dictionaries are carried through untouched, because every row holds indexes into them. The
Workspace select renders only when more than one workspace is present (`showTenantFilter`, `:144`),
which for a tenant admin is never and for a platform admin is exactly when it is needed; when it is
shown and unset, the Overview subtitle says in bold that the totals combine N workspaces
(`reports.html:158-161`).

**The overview tiles** (`reports.ts:252-364`). Success rate divides by **settled** runs -- completed
plus failed -- not by every run (`:272-276`), with the in-flight count reported separately in the
tile's own foot (`:337-342`); dividing by the whole population made a mid-batch refresh read 69% and
turn red for a problem that did not exist. The deltas against the prior window are stated in *points*
for a rate and per cent for a count (`:297-323`), and when the prior window has no runs the tile says
so rather than printing +100%. A prior window that came back `truncated` is discarded rather than
compared against (`:702`). The Median duration tile's foot names what it is measuring
(`durationFoot`, `:355-364`): when the execution median is known it reads "0.23s running, rest is
queue wait", and otherwise "queued to finished, wait included".

**Runs by day** (`reports.ts:394-454`, `reports.html:214-232`). Gap-filled across the **selected
range** through the shared `daySeries` helper (`shared/charts/day-series.ts:29-53`), stacked by
outcome (`:398-411`, `:424-433`), and clickable: `focusDay` (`:745-751`) narrows both dates to that
day and refetches. `activeDays()` (`:447`) counts the days that carry a run rather than the slots on
the axis, and `daysCapped()` (`:437`) says when the 366-day cap has shortened the axis -- which
`daySeries` anchors to the **recent** end (`day-series.ts:41`).

**Task health** (`reports.ts:466-537`, `reports.html:236-307`). One row per task that ran: runs,
distinct jobs, failures, success rate on the same settled denominator the tile uses, median, slowest,
last run, and a state with the reason travelling beside it rather than in a legend. Clicking the task
name filters the whole page to it (`focusTask`, `:754-756`). The comment at `:458-465` is explicit
that this is not a health *score*: there is no SLA, no expected duration and no baseline in this
system to score against.

**What failed, and why** (`reports.ts:635-669`, `reports.html:309-384`). `fetchLogs` supplies the
error text and the job id, which the columnar runs feed deliberately does not carry; the job and task
*names* are joined in from the runs payload by run id (`runIndex`, `:240-250`) rather than asking the
server for a name it would have to be taught to send. Two drill-throughs: the job name opens
`/jobs/:id/history` (`:728-730`) and a Logs button opens `/jobs/:id/runs/:q/logs` (`:732-736`). The
comment above them (`:719-727`) records that the old refusal to offer a run-log link -- on the
grounds that `job_audit_logs` had no rows -- was factually stale rather than wrong in principle.

**The builder** (`report-pivot.ts`, `report-pivot.html`). Everything the old `/reports` did:
two dimension selects with a swap, the grouped measure select, ten chart kinds, the pivot grid with
its per-column header summaries, click-any-number drill-down and the four export paths. It is
`[hidden]`, not `@if` (`reports.html:391`) -- destroying it threw away the reader's dimensions,
measure, chart kind and open drawer every time the section was collapsed. Column headers still carry
their own summary (`report-pivot.html:150-172`): a stacked distribution strip from `columnMix()`
(`report-pivot.ts:201-209`) for a counting measure, a twelve-bin histogram from `columnHistogram()`
(`:212-224`) for a duration one.

**Chart kinds are gated by the measure.** `SUMMING` (`report-pivot.ts:96-97`) names the five kinds
that add cells together -- stacked, 100% stacked, donut, pie, radar -- and `kindAllowed`
(`:106-107`) offers them only when `ADDITIVE` holds the measure. A disallowed button is `[disabled]`
with `kindRefusal` (`:109-112`) in its `title` naming the measure and the alternatives
(`report-pivot.html:96-99`), a sentence beside the row says totalling charts are off
(`:101-105`), and an `effect` (`report-pivot.ts:120-122`) falls back to Grouped rather than leaving a
lie on screen when the measure changes underneath an open chart.

**Cells are buttons.** `report-pivot.html:191-200`. Clicking one calls `drill(ri, ci)` and fills the
drawer with `pivot.cellRows[ri][ci]`. Row totals (`:204-207`) and column totals (`:216-219`) drill to
the whole row and the whole column. The grand total (`:222-223`) is not clickable. A cell whose value
is falsy is still `[disabled]` (`:196`) -- see K11 -- but its *text* now distinguishes the two cases
`aggregate` cannot: `cellText` (`report-pivot.ts:193-198`) prints an em dash for a cell with **no
runs** and the formatted value for a cell whose runs measured zero.

**The chart** (`report-chart.ts`). One component, 550 lines, ten kinds, still no shared code with
`shared/charts` -- `.ai/discovery/frontend.md:394-396` and `:804-806` record this as a duplicated
implementation, and the page now renders both implementations at once (the dashboard's donut,
histogram and bar chart are the shared ones). It measures its own host with a `ResizeObserver`
*and* a window listener (`:161-177`), which the comment at `:138-158` explains: the builder starts
collapsed, so the chart first renders at zero width inside a `[hidden]` section and opening it fires
no window resize at all. `maxOf` (`:28-32`) replaces `Math.max(...cells)`, which threw a `RangeError`
on a pivot of 146,400 cells and killed the whole chart. Which axis carries Day is **told** to it
through a `dayAxis` input (`:113`, `:350-358`) rather than guessed from the label text. Area fills
carry `fill-opacity` 0.35 (`:408`) so overlapping series stay visible. Line and area charts draw a
marker per point (`:379-395`), because a polyline through one point paints nothing and a single-day
range is exactly the current data. Axis labels thin by measured slot width rather than by a fixed
count (`:488`, `:511-512`). The ranked chart's top-8 cut is now reported rather than silent
(`rankedHidden`, `:258-261`, surfaced at `report-pivot.html:110-114`).

**Export** (`report-pivot.ts:274-345`). `grid()` (`:274-292`) turns the current pivot into a header
row plus one array per row plus an "All" row -- the *rendered* grid, not the underlying runs -- and
puts the date range into the exported title (`:278-281`), because a spreadsheet outlives the screen
it came from. Then:

| Button | Handler | Destination | Format |
|---|---|---|---|
| CSV | `export('csv')` `:297` | `download` | csv |
| Excel | `export('xlsx')` `:297` | `download` | xlsx |
| Save | `saveToBucket('csv')` `:310` | `bucket` | **csv only** (`report-pivot.html:62`) |
| Submit | `submit('csv')` `:321` | `submit` | **csv only** (`report-pivot.html:68`) |

`saveToBucket` and `submit` now open `ReportDestinationDialog` (`report-destination-dialog.ts`), a
CDK dialog with real fields, a `valid()` guard and Cancel/Confirm, in place of the three sequential
`window.prompt` calls. It is *not* built on the shared `app-form-dialog` shell, and the bucket field
is still free text pre-filled with `etl-bucket` (`:65`) -- see K13. A download decodes the base64 the
server returns and clicks a synthetic `<a download>` (`report-pivot.ts:300-306`).

**Tests.** `pivot.spec.ts` -- 26 `it` blocks (one an `it.each` of five rows) covering the measures,
percentile interpolation, the grid's row-dropping and column-keeping rules, the re-aggregated row
total, cell drill-down contents, the formatters including the deliberate `0 -> '0s'` change, and a
five-case group on the execution measures asserting they read `EXEC_SECONDS` and are not additive.
`report-destination-dialog.spec.ts` -- 7 cases on the dialog's defaults, validity and trimming.
There is still **no test for `Reports`, none for `ReportPivot` and none for `ReportChart`**.

#### 2.2.1 What changed on 2026-09-08

| Change | Where | Closes |
|---|---|---|
| Summing chart kinds gated on `ADDITIVE` | `pivot.ts:135`, `report-pivot.ts:96-122` | K7, K8 |
| Area fills translucent | `report-chart.ts:408` | K9, area half |
| `humanSeconds(0)` is `0s`; em dash means no data; `cellText` tells an empty cell from a zero one | `pivot.ts:281-290`, `report-pivot.ts:193-198` | K12 |
| Workspace dimension and filter | `QueryService.java:264`, `:292`; `ReportExportServiceImpl.java:117`, `:127`; `pivot.ts:79`; `reports.ts:127` | §8.2, §13 |
| Axis flip decided by a `dayAxis` input | `report-chart.ts:113`, `:350-358`; `report-pivot.ts:102-103` | K10 |
| A destination dialog replaces three `window.prompt`s | `report-destination-dialog.ts` | K14 |
| Execution measures, separated from queue wait | `QueryService.java:283-288`, `pivot.ts:153-154` | new |
| Filters over one `data()` computed | `reports.ts:176-190` | new |
| Pixel-measured axis and value labels | `report-chart.ts:488`, `:511-512`; `shared/charts/bar-chart.ts:199-225` | new |
| Day cap anchored to the recent end | `shared/charts/day-series.ts:41` | new |
| `activeDays()` counts days with runs, not axis slots | `reports.ts:447` | new |
| Run-log drill-through | `reports.ts:732-736` | new |
| Builder reads the parent's rows instead of refetching | `report-pivot.ts:49` | new |

Still open in the §12 register, and untouched by this pass: K1, K2, K3, K4, K5, K11, K13, K15, K16,
K18, K19. Addressed only in part: K6 (client only), K9 (area only, radar unchanged) and K17 (the
three files it names still do not exist). Four findings were opened on 2026-09-08: K20 to K23.

### 2.3 The new app -- backend

**Controller.** `process/src/main/java/process/api/ReportRestApi.java`. Class-level
`@PreAuthorize("hasRole('TENANT_USER')")` at `:27`. **Neither method carries a method-level
`@PreAuthorize`**, so the class-level value governs both -- worth stating explicitly because
`@PreAuthorize` is not repeatable and a method-level annotation elsewhere in this codebase replaces
rather than adds to the class-level one (`QueryEngineRestApi` uses that pattern twelve times). Both
methods wrap everything in `try/catch (Exception)` and answer a 500 carrying
`ProcessUtil.INTERNAL_ERROR_500` on anything unexpected (`:45-50`, `:57-62`).

**`runRows`** (`ReportExportServiceImpl.java:85-134`). Builds SQL through
`QueryService.runReportRows` and runs it through `QueryService.executeQuery`. On any exception it
returns `ResponseDto(ERROR, "Could not read the runs for that range.")` at HTTP 200 rather than
throwing (`:86-93`). Results over `MAX_ROWS = 50_000` (`:45`) are cut to the first 50,000 and flagged
`truncated` (`:95-97`); the ordering is `job_queue_id desc`, so that is the *most recent* 50,000. The
**five** dimension values are interned into dictionaries (`:99-120`) so the payload carries indexes
rather than repeated strings, and the response names them at `:122-130`.

**The SQL** (`QueryService.java:250-303`), as of 2026-09-08:

```
select coalesce(st.task_name,'(no task)'), q.job_status,
       coalesce(u.full_name, u.username, 'Unassigned'),
       to_char(q.start_time,'YYYY-MM-DD'),
       case when q.end_time is null then -1
            else round(extract(epoch from (q.end_time - q.start_time))) end,
       sj.job_name, q.job_queue_id,
       coalesce(t.tenant_name,'(no workspace)'),
       case when x.exec_start is null or q.end_time is null then -1
            else round(cast(extract(epoch from (q.end_time - x.exec_start)) as numeric), 2) end
from job_queue q
join source_job sj on sj.job_id = q.job_id
left join source_task st on st.task_detail_id = sj.task_detail_id
left join tenant t on t.tenant_id = sj.tenant_id
left join app_user u on u.app_user_id = sj.assigned_user_id
left join (select job_queue_id, min(date_created) as exec_start
           from job_audit_logs where log_detail = 'Job started'
           group by job_queue_id) x on x.job_queue_id = q.job_queue_id
where q.start_time is not null and upper(sj.job_status) <> 'DELETE'
  <date filter> <tenant clause>
order by q.job_queue_id desc
```

Two columns were added on 2026-09-08 and both are load-bearing.

`tenant_name` exists because a platform admin has the tenant filter switched off, so their report
already merged every workspace's runs into one set of totals with nothing on screen to say so. The
join is a `left join`, so a job with no tenant reads `(no workspace)` rather than dropping out.

`exec_seconds` exists because `job_queue.start_time` is stamped at **enqueue**, not at pickup, so
`end_time - start_time` is queue wait plus execution with no way to tell them apart -- and on this
deployment the wait is 99.4% of it (41.25s of a 41.48s average, for tasks that run in 0.23s),
because the dispatcher polls once a minute. The worker writes a `Job started` audit line the moment
it picks a run up, so the pickup instant *is* recorded, just not in `job_queue`; the derived join
recovers it. It is a `left join`, so a run with no marker reports `-1` and is excluded from the
execution statistics rather than counted as instant. It is rounded to two decimals rather than to
whole seconds, because whole seconds print the real answer as "0s". The cast is written
`cast(... as numeric)` and not `::numeric`, because this string goes to
`entityManager.createNativeQuery`, which reads `:` as the start of a named parameter.

Tenant narrowing is `QueryService.tenantClause("sj")` (`:211-217`), which appends
`and sj.tenant_id = <id>` -- **unless** the caller is a platform admin or `TenantContext.getTenantId()`
is null, in which case it appends nothing. **Unchanged**; see K5. The date filter is
`dateRangeFilter` (`:157-162`), which appends nothing at all unless *both* dates match
`\d{4}-\d{2}-\d{2}` (`:164-166`). **Unchanged**; see K6.

**`export`** (`ReportExportServiceImpl.java:140-185`). Validates, builds CSV once, converts to xlsx
if asked, then dispatches on destination:

- **download** (`:189-195`) -- base64 in the response body alongside a filename and content type.
- **bucket** (`:197-219`) -- requires a bucket name; assembles the key itself from a sanitised folder
  plus the generated filename (`:202-206`) and calls `StorageBrowserService.uploadObject`, which is
  the *caller-scoped* overload (`StorageBrowserServiceImpl.java:296-299` then
  `resolveServiceForCaller` at `:431-437`), not the trusted workflow one.
- **submit** (`:221-253`) -- multipart POSTs the file to a caller-supplied URL and hands back the
  HTTP status and the first 500 characters of the response body (`:244-248`).

The CSV writer (`:298-330`) quotes commas, quotes and newlines, truncates a cell at 32,000
characters, and prefixes an apostrophe onto any non-numeric cell opening with `= + - @ tab CR`
(`:53`, `:316-330`) so a spreadsheet reads it as text rather than a formula.

The xlsx path goes through `FileChatExtractionServiceImpl.convertContent` (`:159-160`), which routes
csv to xlsx through JODConverter/LibreOffice; `DocumentConverterFormatRegistry.java:55-58` confirms
csv is a SPREADSHEET input and xlsx a SPREADSHEET output, so the pair is registered.

**The submit guard** (`:263-293`). Rejects anything that is not `http`/`https`, anything with no
host, and -- unless `report.submit.allow-internal` is true -- any host that resolves to a loopback,
link-local, site-local, wildcard or multicast address. Every address the name resolves to is checked,
not just the first.

**Tests.** `process/src/test/java/process/model/service/impl/ReportExportServiceImplTest.java` -- 16
JUnit cases: seven on the CSV writer (including formula defusing and leaving negative numbers
alone), five on validation and the download path, and four on the submit guard, including a positive
control at `:198-211` that flips the flag by reflection and asserts the refusal changes shape. The
service is constructed with three nulls (`:28`), so **`runRows` is never exercised**, and
`.ai/discovery/backend.md:1061` lists `ReportRestApi` among the twenty controllers with no test at
any level.

---

## 3. Expected behaviour

Most of what is described in section 2 is what the feature should do. This section states the
deltas -- where a finished Reports differs from today. Items delivered on 2026-09-08 are marked and
kept, because the reasoning is what makes the next one arguable.

**The range must be a range.** A report over "everything ever" is not a report, it is a table scan.
Clearing either date input silently widens the query to the whole of history
(`QueryService.java:157-162` returns an empty filter when either date fails the pattern), and nothing
on the server checks that the start is before the end. Expected: both dates required, the start not
after the end, enforced on the client for the message and on the server for the truth, with a refusal
rather than a silent widening when either is absent or malformed, and a maximum span.
**PARTLY DONE 2026-09-08** -- `rangeValid()` (`reports.ts:220-223`) refuses on the client and `load()`
(`:600-609`) never issues the request, and an invalid range is offered "Reset to the last 30 days"
rather than a "Try again" that cannot succeed (`reports.html:135-141`). The server is unchanged:
no `required = true`, no validator, no `MAX_SPAN_DAYS`. See K6.

**A cell with runs behind it must be reachable.** A cell is disabled when its measured value is
falsy (`report-pivot.html:196`). For a duration measure, a cell containing only runs that never
finished measures 0 and is therefore unclickable -- which hides precisely the runs a reader opened
the report to find. Expected: the button is enabled when the cell has runs, whatever the measure
says. **NOT DONE.** The `[disabled]` binding is unchanged; only the cell's *text* now distinguishes
the two cases (`report-pivot.ts:193-198`), which makes the defect more visible rather than less --
such a cell now reads `0s` and refuses the click. See K11.

**Zero must be distinguishable from nothing.** `humanSeconds(0)` returned an em dash, so "these runs
took no measurable time" and "none of these runs has a duration" rendered identically.
**DONE 2026-09-08** -- `humanSeconds` (`pivot.ts:281-290`) treats **negative** as the no-data
sentinel and returns `0s` for a real zero, keeping two decimals below ten seconds so the execution
measures read as something; `cellText` (`report-pivot.ts:193-198`) uses `cellRows` to print an em
dash for a cell with no runs at all. This changed an assertion in `pivot.spec.ts:147`, which now
records why. See K12.

**A chart must not claim something the arithmetic does not support.** Stacked, 100%-stacked, pie and
donut all treated the pivot as additive. It is additive for `count` and `sum` and for nothing else.
**DONE 2026-09-08** -- `ADDITIVE` (`pivot.ts:135`), `SUMMING` (`report-pivot.ts:96-97`) and
`kindAllowed` (`:106-107`) disable the five summing kinds for a non-additive measure, state the
reason in the button's title (`:109-112`) and beside the row (`report-pivot.html:101-105`), and fall
back to Grouped rather than leaving a wrong chart on screen (`report-pivot.ts:120-122`). See K7, K8.

**Every series in an overlay chart must be visible.** Area and radar drew one filled polygon per
series with no transparency, so the last series painted hid the ones under it.
**PARTLY DONE 2026-09-08** -- area fills carry `fill-opacity` 0.35 (`report-chart.ts:408`) and the
stroke on top keeps each edge legible. **Radar is unchanged**: `radarFills` (`:413-426`) still
returns opaque polygons, still draws each of them twice (`segments()` `:306` and `strokes()` `:431`
both call it), and still silently caps at four series (`:418`). See K9.

**Choosing where a file goes is a form, not three prompts.** `window.prompt` is unstyleable,
unthemed, unvalidatable, hostile on a touch keyboard, and blocked outright by some browser
configurations. **PARTLY DONE 2026-09-08** -- `ReportDestinationDialog`
(`report-destination-dialog.ts`) is a CDK dialog with labelled fields, a `valid()` guard, trimming
and 7 tests. It is not built on the shared `app-form-dialog` shell, the bucket is still free text
rather than a picker populated from `storage.json/buckets`, and it still offers no format choice.
See K13, K14, K15.

**Every destination should offer every format.** The server handles format and destination
independently (`ReportExportServiceImpl.java`); only the template limits Save and Submit to csv
(`report-pivot.html:62`, `:68`). Expected: csv or xlsx to any of the three destinations.
**NOT DONE.** See K15.

**Posting the console's data to an address somebody typed is an administrator's decision.** See
section 8. **NOT DONE.** See K1.

**The report must be able to answer a question without being built first.** *Added 2026-09-08, and
delivered in the same pass.* A pivot builder is the only surface that can answer a question nobody
anticipated, and it is the wrong thing to open on: it answers nothing until the reader has built the
answer themselves, and the answers people built by hand every time were the same four or five. The
page now opens on those -- four tiles, an outcome donut, a duration histogram, a runs-by-day chart, a
task-health table and the error text of every failed run -- with the builder one click away and
unchanged in what it does (`reports.html:391-400`). The whole page is computed in the browser from
the same single fetch the builder reads, so the addition cost one extra request, not one per section.

**A filter must narrow everything or nothing.** *Added 2026-09-08, and delivered in the same pass.*
A screen that filters its table while its charts describe a larger population states two answers
about the same data, fifty pixels apart -- the defect this pass fixed on `/queue`. Here the five
filters narrow one `data()` computed (`reports.ts:176-190`) that every tile, chart, table and the
pivot builder read. The one exception is the failure table, which is fed by a different endpoint;
see K22.

---

## 4. Frontend requirements

### 4.1 Route and shell

| Route | Component | Guards | Nav |
|---|---|---|---|
| `reports` | `features/reports/reports.ts` `Reports` | `authGuard` + `passwordChangeGuard`, inherited from the shell | Pipelines then Reports, `shell.ts:65-66` |

No role gate on the route -- reading runs is `TENANT_USER` on the server and the page is a read.
That decision should be written down in the route entry the way `tasks` and `ai/agents` write theirs
down, so the next reader does not have to infer that the absence is deliberate. The Submit control
inside the page is a separate question (section 8).

### 4.2 Components

*Updated 2026-09-08: the builder was split out of `Reports` into its own component so the page above
it could grow without the file becoming unreadable, and so the two could not fetch the same rows
twice.*

| Component | File | Responsibility |
|---|---|---|
| `Reports` | `features/reports/reports.ts` | Load the runs, hold the range and the five filters, derive the tiles, the three charts, task health and the failure table; own the drill-through routes |
| `ReportPivot` | `features/reports/report-pivot.ts` | The builder: shape, measure, chart kind, the grid, the drill drawer and the four export paths. Takes rows as an `input`, fetches nothing |
| `ReportChart` | `features/reports/report-chart.ts` | Draw the current pivot as one of ten SVG kinds |
| `ReportDestinationDialog` | `features/reports/report-destination-dialog.ts` | Bucket + folder, or endpoint URL, for Save and Submit |
| `pivot.ts` | `features/reports/pivot.ts` | Dimensions, measures, `ADDITIVE`, `aggregate`, `buildPivot`, formatters -- no Angular |
| `StatTile` | `shared/ui/stat-tile.ts` | The four Overview tiles |
| `Donut`, `Histogram`, `BarChart` | `shared/charts/` | The dashboard's three charts, shared with Queue and the dashboard |
| `daySeries` | `shared/charts/day-series.ts` | Gap-filled day axis and the 366-day cap, shared with Queue |
| `TableShell` | `shared/ui/data-table.ts` | Card chrome, horizontal scroll, sticky header |
| `StatusPill` | `shared/ui/status-pill.ts` | Outcome in the failure table and the drill drawer |
| `Icon` | `shared/ui/icon.ts` | `refresh`, `alert`, `chart`, `download`, `table`, `cloud`, `send`, `close`, `play`, `check`, `clock`, `history`, `info`, `chevronDown`, `chevronRight` |

The pivot arithmetic stays outside the component. That separation is why the sixteen measures are
testable at all, and it is what made the chart-kind gate a one-line set in `pivot.ts` rather than a
rule restated in the chart.

Requirement, unmet: `ReportChart` is still a second bar-chart implementation living beside the
shared one, and the page now renders both at the same time. See K21.

### 4.3 Controls

| Control | Kind | Rule |
|---|---|---|
| From / To | `input[type=date]` | Both required; From <= To; reload on change. Enforced on the client at `reports.ts:220-223`, **not** on the server (K6) |
| Task / Job / Outcome / Owner / Workspace | five `select`s | Narrow `data()`, which everything on the page reads. Options come from the raw payload so one never empties another. Workspace renders only when more than one is present (`reports.ts:144`) |
| Filter strip | removable pills | One per active filter, plus Clear all and "N of M runs" (`reports.html:104-120`) |
| Runs-by-day bar | clickable bar | Narrows both dates to that day and refetches (`reports.ts:745-751`) |
| Task name | button in the health table | Toggles the page's Task filter (`reports.ts:754-756`) |
| Build your own view | toggle button | Shows the builder. `[hidden]`, not `@if`, so the builder's state survives collapsing |
| Rows | `select` | One of Task / Job / Outcome / Owner / Workspace / Day. Choosing the current Columns value swaps the two rather than producing a diagonal (`report-pivot.ts:163-168`) |
| Columns | `select` | Same, mirrored (`:169-173`) |
| Swap | button | Exchange rows and columns |
| Measure | grouped `select` | Sixteen options in five `optgroup`s: How many / Middle / Edges / Spread / Execution |
| Chart kind | ten toggle buttons | Selected kind is `btn-default`, the rest `btn-ghost`. The five summing kinds are `[disabled]` with a stated reason unless the measure is additive |
| CSV / Excel | buttons | Download. All four disabled while any export is in flight |
| Save | button | Opens `ReportDestinationDialog` in bucket mode. Format is hard-coded csv (K15) |
| Submit | button | Opens `ReportDestinationDialog` in endpoint mode. Format is hard-coded csv (K15). Should be hidden for a role that may not use it (section 8) -- not done |
| Refresh | button | Re-runs the current range |

Defaults worth stating: Rows and Columns are looked up **by key** and not by position
(`report-pivot.ts:74-75`, `dimensionFor` at `pivot.ts:68-72`). Inserting Job into `DIMENSIONS` at
index 1 had silently moved the default column from Outcome to Job, and since each task belongs to
one job the opening view became a 19x19 matrix that was empty everywhere off the diagonal.

### 4.4 Dialog

One dialog replacing the three prompts. **Built 2026-09-08** as
`features/reports/report-destination-dialog.ts` -- a CDK `Dialog` component, two modes sharing one
file, `cdkFocusInitial` on the first field, a `valid()` guard on the confirm button, trimming and a
`reports` fallback for a blank folder, with 7 tests. Against the requirement as written, three parts
are still outstanding:

- **Destination** -- Download / Bucket / Endpoint. *Not built as a choice.* The dialog is opened in
  one of two modes by the button that opened it (`report-pivot.ts:311`, `:323`).
- **Format** -- CSV / Excel, available for all three destinations. *Not built.* Both callers pass
  the literal `'csv'` (`report-pivot.html:62`, `:68`). See K15.
- **Bucket** -- a `select` populated from `storage.json/buckets`, not free text. *Not built.* The
  field is still an `<input>` defaulting to `etl-bucket` (`report-destination-dialog.ts:35`, `:65`),
  which is a platform bucket that `resolveServiceForCaller` refuses for every non-platform role
  (`StorageBrowserServiceImpl.java:431-437`, `:466-468`; `KafkaSecretService.java:27` defines
  `SECRET_BUCKET = "etl-bucket"`), so the suggested default still cannot work for the people most
  likely to press the button. See K13.
- **Folder** -- free text, defaulting to `reports`. **Done** (`:38-40`, `:66`). The leading-slash and
  `..` stripping the server applies is still not shown as a hint.
- **Endpoint** -- a URL field, scheme validated on the client for the message, with the server's
  guard as the enforcement. **Done in part** (`:47-49`, `:72`): the client accepts `http` as well as
  `https`, matching the server's own guard, which is itself weaker than the sibling guard in this
  codebase. See K2.

The requirement said `shared/ui/form-dialog.ts`. It was built as its own card markup instead
(`report-destination-dialog.ts:25-58`), while thirteen other files in the app reference the shared
shell. That is a defensible choice -- the shape is two labelled inputs and a pair of buttons
-- but it is a divergence, and it should be an argued one rather than an accidental one.

### 4.5 States

| State | Today | Requirement |
|---|---|---|
| Loading | `reports.html:122-126`, spinner card | Keep. Also disable the range inputs, not just Refresh -- still not done |
| Error, request failed | `:127-136`, message + Try again | Keep |
| Error, range invalid | `:137-141`, message + **Reset to the last 30 days** | **Done 2026-09-08.** Retrying a start-after-end range can never succeed, so the retry is replaced by the one control that resolves it |
| Empty | `:143-150`, "No runs started in this range." | Keep. The wording now says *started*, which is what `where q.start_time is not null` means |
| Truncated | `:92-100`, pill + a sentence + toast (`reports.ts:593`) | **Done 2026-09-08.** The pill now sits beside a visible sentence saying every figure describes a sample, so the meaning no longer lives only in a tooltip |
| Filtered | `:104-120`, one removable pill per filter plus "N of M runs" | **Added 2026-09-08.** Every figure describes the narrowed set, which is only honest while the narrowing is visible |
| Exporting | `report-pivot.html:51-73`, spinner on Excel, Save and Submit | Partly done: CSV alone still shows no progress of its own, though all four are disabled while any export is in flight |
| Failures loading / error | `reports.html:322-326`, through `TableShell` with its own retry | **Added 2026-09-08.** A second endpoint feeds this table, so it has its own three states |
| Drawer empty | none | A cell with runs always drills; a cell with none is disabled, so this state should be unreachable by construction. **Still not true under a duration measure** -- see K11 |

### 4.6 Dark and light mode

Everything the screen draws already resolves through per-theme tokens: surfaces and text via the
semantic utilities registered at `styles.css:61-78`, chart series via `--series-*` and `--chart-N`,
which are redefined under `html.dark` at `styles.css:1096-1109`. The chart's SVG uses
`var(--border-subtle)`, `var(--text-muted)`, `var(--text-secondary)` and `var(--text-primary)`
directly (`report-chart.ts:38`, `:40`, `:55`, `:60`, `:66`, `:68`), and the heat map builds its fill
with `color-mix(in oklab, var(--series-brand) …%, transparent)` (`:212`) so it follows the theme too.
No hard-coded colour appears anywhere in the three files. Requirement: keep it that way -- in
particular, do not introduce a fixed hex when gating chart kinds.

### 4.7 Responsive

- The chart measures its host through a `ResizeObserver` **and** a window listener, with a 320px
  floor (`report-chart.ts:161-177`), so it narrows rather than squashing type. The observer was
  added on 2026-09-08 because the builder starts collapsed: the chart first renders at zero width
  inside a `[hidden]` section, and opening it fires no window resize at all, so a 1331px card was
  drawing a 960px viewBox for ever. The `:host { display: block }` at `:56` is part of the same fix
  -- a `ResizeObserver` never fires for an inline element, which has no content box to observe.
- Axis labels and the numbers above bars are now thinned by **measured pixels**, not by a count
  (`report-chart.ts:488`, `:511-512`, `:529-542`; and in the shared bar chart at
  `shared/charts/bar-chart.ts:199-225`). The count-based rule had no width term at all, so the
  31-day default range drew `09-06` and `09-08` 28px apart under a 30px label -- 114 of the 350
  possible bar counts collided at 1024px.
- The dashboard's three chart cards each carry `min-w-0` (`reports.html:194`, `:203`, `:214`), and
  the comment at `:190-192` is the reason: a grid item's automatic minimum is its min-content width,
  so at phone width the donut's legend row pushed the auto track to 411px inside a 343px grid and
  the whole **page** scrolled sideways.
- The pivot table scrolls horizontally inside `TableShell`'s `overflow-x-auto` and vertically inside
  `.scroll-table` with a sticky header. The **first column is not sticky horizontally** and the "All"
  total row is not sticky vertically, so on a narrow screen with many columns the reader loses both
  the row label and the totals. Both should stick. **Unchanged.**
- Every toolbar row is `flex-wrap` (`reports.html:24`, `:40`; `report-pivot.html:10`, `:86`), so the
  controls stack rather than overflow. The task-health and failure tables drop columns by breakpoint
  instead (`reports.html:258`, `:263`, `:264`, `:332`, `:333`).
- The drill drawer is still a fixed bottom sheet capped at 56vh (`report-pivot.html:229-230`) with
  its own scroller. On a phone that is workable; it still needs an Escape handler and a close on
  backdrop tap, neither of which exists. See K16.

---

## 5. Backend requirements

### 5.1 Endpoints

| Method | Path | Role today | Role required | What it does |
|---|---|---|---|---|
| GET | `/report.json/runs?startDate&endDate` | `TENANT_USER` (class, `ReportRestApi.java:27`) | `TENANT_USER` | Returns the run rows for the range, tenant-narrowed, columnar, capped at 50,000 with a `truncated` flag. Since 2026-09-08 each row also carries a workspace index and an execution duration, and the response carries a fifth `tenant` dictionary |
| POST | `/report.json/export` | `TENANT_USER` (class) | `TENANT_USER` for `download` and `bucket`; **`TENANT_ADMIN` for `submit`** | Builds a csv or xlsx from the grid in the body and returns it, writes it to a bucket, or POSTs it to a URL |

Both endpoints answer HTTP 200 with `ResponseDto{status,message,data}` for both success and business
failure; only an unhandled exception produces a 500 (`ReportRestApi.java:45-50`, `:57-62`).

`/report.json/runs` request parameters:

| Name | Required today | Required | Format |
|---|---|---|---|
| `startDate` | no (`:41`) | yes | `yyyy-MM-dd` |
| `endDate` | no (`:42`) | yes | `yyyy-MM-dd` |

`/report.json/export` body (`ReportExportRequestDto.java:14-27`):

| Field | Type | Meaning |
|---|---|---|
| `title` | string | Sheet title and filename stem; slugged to `[a-z0-9-]`, capped at 60 chars, plus a `yyyyMMdd-HHmmss` stamp (`ReportExportServiceImpl.java:338-345`) |
| `columns` | string[] | Header row. Required and non-empty |
| `rows` | Object[][] | Body. Capped at 50,000 |
| `format` | string | `csv` or `xlsx` |
| `destination` | string | `download`, `bucket` or `submit` |
| `bucket` | string | Required when destination is `bucket` |
| `folder` | string | Defaults to `reports` |
| `submitUrl` | string | Required when destination is `submit` |

### 5.2 Services

| Service | File | Responsibility |
|---|---|---|
| `ReportExportServiceImpl` | `model/service/impl/ReportExportServiceImpl.java` | `runRows` (read + columnar packing) and `export` (build + deliver). 355 lines, no repository of its own |
| `QueryService` | `model/service/impl/QueryService.java` | `runReportRows` (`:251-271`) assembles the native SQL, `tenantClause` (`:212-217`) applies the narrowing, `executeQuery` (`:42-46`) runs it |
| `StorageBrowserService` | `model/service/StorageBrowserService.java` | The bucket destination writes through the **caller-scoped** `uploadObject`, correctly, not `uploadForWorkflow` |
| `FileChatExtractionServiceImpl` | `model/service/impl/FileChatExtractionServiceImpl.java` | csv to xlsx via JODConverter, shared with the document converter and the job assistant |

Two changes are required of these services and neither is cosmetic:

1. `ReportExportServiceImpl:58` builds `new RestTemplate()` with no timeouts. `submit` therefore
   holds a request thread for as long as the remote host is willing to keep the socket open. The
   house pattern is `OpenSearchAuditLogClient.java:39-50` -- 3s connect, 5s read.
2. `report.submit.allow-internal` (`ReportExportServiceImpl:67-68`) is a security decision expressed
   only as a Java `@Value` default. `ApplicationPropertiesDeclarationTest:15-25` states the rule this
   breaks in as many words, and lists seven such properties at `:35-42`; this one is not among them
   and appears in none of `application.properties`, `application-dev.properties`,
   `application-stage.properties` or `application-prod.properties`.

---

## 6. Database requirements

**No new table. No new column. No data migration.** *Still true after 2026-09-08: the Workspace
dimension and the Execution measures were both built from columns that already existed.* The report
is now a read over six existing tables:

| Table | Columns read | Role in the query |
|---|---|---|
| `job_queue` | `job_queue_id`, `job_id`, `job_status`, `start_time`, `end_time` | The run itself. `job_status` is a `JobStatus` enum stored as a string -- Queue, Start, Running, Failed, Completed, Skip, Interrupt, Missed (`model/enums/JobStatus.java:6-7`, `JobQueue.java:55-58`) |
| `source_job` | `job_id`, `job_name`, `task_detail_id`, `assigned_user_id`, `job_status`, `tenant_id` | The join that carries the tenant. `job_queue` has no `tenant_id` of its own (`database.md:338`), so `sj` is the only thing narrowing can attach to |
| `source_task` | `task_detail_id`, `task_name` | Left-joined; a job with no task reads as `(no task)` |
| `app_user` | `app_user_id`, `full_name`, `username` | Left-joined; a job with no assignee reads as `Unassigned` |
| `tenant` | `tenant_id`, `tenant_name` | *Added 2026-09-08.* Left-joined on `sj.tenant_id`; a job with no tenant reads as `(no workspace)` |
| `job_audit_logs` | `job_queue_id`, `date_created`, `log_detail` | *Added 2026-09-08.* A derived table -- `min(date_created)` where `log_detail = 'Job started'`, grouped by run -- left-joined to recover the instant the worker picked each run up, which `job_queue` does not record. Indexed on `job_queue_id` (`JobAuditLogs.java:14-15`, `idx_job_audit_logs_job_queue_id`); `log_detail` is not indexed, so the derived table scans it |

**One index is worth adding.** `job_queue` declares exactly one index, `idx_job_queue_job_id`
(`JobQueue.java:19-21`), confirmed against `database.md:529`. The report's predicate is
`q.start_time is not null and date(q.start_time) between …`, and `date(...)` wraps the column, so
even an index on `start_time` would not be used. Two options, in order of preference:

1. An expression index -- `create index idx_job_queue_start_date on job_queue ((start_time::date))`
   -- matching the predicate exactly.
2. Rewrite the filter as a half-open range on the bare column (`start_time >= :start and start_time <
   :endPlusOne`) and add a plain btree index. This changes `dateRangeFilter`, which nine other
   queries share, so it is the larger blast radius.

Either is a new changelog set under
`process/src/main/resources/db/changelog/changelog-sets/`, following the existing numbering (the
latest as of 2026-09-08 is `V30.0-drop-email-receiver`).

**The soft-delete column is not consulted.** `job_queue.status` exists (`JobQueue.java:90-93`) and the
report does not filter on it; it filters on `source_job.job_status <> 'DELETE'` instead
(`QueryService.java:268`). Whether a `job_queue` row is ever set to `Delete` is **not verified** --
no writer of that column was traced in this pass. If it is, deleted runs are counted.

---

## 7. Validation

| # | Rule | Client | Server | Verdict |
|---|---|---|---|---|
| V1 | `startDate` and `endDate` present | **yes, since 2026-09-08** -- `rangeValid()` (`reports.ts:220-223`) and `load()` (`:600-609`) refuse to issue the request and say why | no -- `required = false` (`ReportRestApi.java:41-42`) | **Client only.** The screen can no longer produce the all-history scan; a hand-made request still can |
| V2 | Dates match `yyyy-MM-dd` | yes -- both the native `input[type=date]` and `rangeValid()`'s own regex | yes -- `isValidDate` (`QueryService.java:164-166`) | Both, but a server-side failure still *drops the filter* instead of refusing |
| V3 | `startDate` <= `endDate` | **yes, since 2026-09-08** -- `rangeValid()` (`reports.ts:223`) | no | **Client only.** The message is right and the enforcement is in the wrong place |
| V4 | Rows and columns are different dimensions | yes -- `setRowDim`/`setColDim` swap (`report-pivot.ts:163-173`) | n/a | Client-only, and correctly so: the server does not pivot |
| V5 | `columns` non-empty | no | yes (`ReportExportServiceImpl.java:141-143`) | Server-side; the client cannot produce an empty grid, so this guards a hand-made request |
| V6 | Rows <= 50,000 | no | yes (`:145-149`) | Server-side |
| V7 | `format` is csv or xlsx | yes, by construction -- only two literals are passed | yes (`:150-153`) | Both |
| V8 | `destination` is download, bucket or submit | yes, by construction | yes (`:177-184`) -- refused, not defaulted | Both |
| V9 | `bucket` present when destination is `bucket` | yes -- the dialog's Save button is disabled while the field is blank (`report-destination-dialog.ts:69-73`) | yes (`:199-201`) | Both |
| V10 | Bucket key contains no traversal | n/a | yes -- the key is assembled server-side and `..` is stripped (`:202-206`); `StorageBrowserServiceImpl.requireSafeKey` (`:296-297`) checks it again | Server, twice |
| V11 | Caller may write to that bucket | no | yes -- `resolveServiceForCaller` (`StorageBrowserServiceImpl.java:431-437`) | Server-side |
| V12 | `submitUrl` present | yes -- the dialog's Submit button is disabled until the field matches `^https?://\S+` (`report-destination-dialog.ts:69-73`) | yes (`:223-225`) | Both |
| V13 | `submitUrl` is http/https with a host | yes, shape only (`report-destination-dialog.ts:72`) | yes (`:270-276`) | Both; the server is the enforcement |
| V14 | `submitUrl` is not an internal address | no | partial (`:280-288`) -- see K2 | Server-side, incomplete |
| V15 | Cell content cannot become a spreadsheet formula | no | yes (`:53`, `:316-330`), tested at `ReportExportServiceImplTest:79-89` | Server-side, which is the right layer: the server builds the file |
| V16 | Cell content capped at 32,000 chars | no | yes (`:319`) | Server-side, silent |

Rows V1 and V3 are the two client-only gaps. As of 2026-09-08 they are *enforced*, but only in the
browser: the screen can no longer produce the all-history scan, and a reader who inverts the range
is told so and offered a way out. Nothing changed on the server, so the consequential half stands --
V1 is not a usability defect, it is an unbounded scan of the largest table in the schema on an
unindexed predicate, and `curl` still reaches it. The client guard is worth having (it removes the
common path and it produces the message), but it must not be mistaken for the fix. See K6.

---

## 8. Security

### 8.1 The four layers, for each endpoint

**`GET /report.json/runs`**

| Layer | What it does |
|---|---|
| Frontend guard | `authGuard` + `passwordChangeGuard` on the shell (`app.routes.ts:46-53`). No role guard on the route. Correct for a `TENANT_USER` read, but undocumented |
| Controller `@PreAuthorize` | `hasRole('TENANT_USER')` at class level (`ReportRestApi.java:27`), no method-level override. With the hierarchy at `MethodSecurityConfig.java:26-31` (`PLATFORM_ADMIN > TENANT_ADMIN > TENANT_USER`) all three roles pass |
| Service rule | `QueryService.tenantClause("sj")` (`:212-217`) -- appends `sj.tenant_id = <id>` for a tenant-bearing non-admin caller, appends **nothing** for a platform admin **and nothing for a caller whose tenant is null** |
| Hibernate `@Filter` | **Inert.** `SourceJob` declares `tenantFilter` (`SourceJob.java:28-29`) but the report never loads an entity -- it goes through `EntityManager.createNativeQuery` (`QueryService.java:42-46`), which Hibernate filters do not touch. `JobQueue` never declared the filter at all (`database.md:338`) |

The whole of the isolation therefore rests on layer 3, on a string. That is the same arrangement as
the dashboard and the user statistics, and it is defensible -- but it means the *only* thing standing
between one tenant and another's run history is thirty characters of concatenated SQL that no test
covers for this query.

**`POST /report.json/export`**

| Layer | `download` | `bucket` | `submit` |
|---|---|---|---|
| Frontend guard | none beyond the shell | none | none |
| Controller | `TENANT_USER` | `TENANT_USER` | `TENANT_USER` |
| Service rule | none -- the grid is the caller's | `resolveServiceForCaller` refuses a platform bucket to a non-platform-admin and another tenant's connection to anyone (`StorageBrowserServiceImpl.java:431-437`, `:523-548`) | `rejectUnsafeTarget` refuses non-http(s) and, by default, private addresses (`ReportExportServiceImpl.java:263-293`) |
| Hibernate `@Filter` | n/a | n/a | n/a |

### 8.2 By role

**`TENANT_USER`.** May open the screen, read their own tenant's runs, pivot, chart and drill. May
download the grid as csv or xlsx. May write it into a bucket their tenant owns -- and that is
consistent with the object browser, whose own `storage.json/uploadObject` is also `TENANT_USER`
(`StorageBrowserRestApi.java:36`, with no method-level override at `:113-114`), so the report is not
a privilege-escalation path to a bucket write. **May also cause the server to POST a file to any
public address on the internet and read back the first 500 characters of the reply.** That last
capability is the one that does not belong to this role -- see 8.3.

**`TENANT_ADMIN`.** Everything a tenant user can do, within the same tenant. No additional capability
on this screen today, and none is needed apart from Submit.

**`PLATFORM_ADMIN`.** `tenantClause` returns an empty string (`QueryService.java:212-214`), so the
report still covers **every tenant's runs merged into one set of totals**. That is consistent with
how the dashboard treats a platform admin and it is probably the intent; what used to make it a
defect was that nothing on screen said it had happened.

**Closed 2026-09-08.** The query carries `coalesce(t.tenant_name, '(no workspace)')` through a left
join on `tenant` (`QueryService.java:264`, `:292`), the service interns it as a fifth dictionary at
row index 7 (`ReportExportServiceImpl.java:117`, `:127`), `DIMENSIONS` gained `Workspace`
(`pivot.ts:79`) so the builder can group and pivot on it, and the page gained a Workspace filter
that appears only when more than one workspace is actually present (`reports.ts:127`, `:144`).
When it is present and unset the Overview subtitle says in bold that the totals combine N workspaces
(`reports.html:158-161`), so a platform admin is told rather than left to infer it. A tenant admin
sees no such control, because for them it would be a select with one option.

Unchanged: a platform admin *can* pass `resolveServiceForCaller` for `etl-bucket`, so accepting the
Save dialog's default writes a report into the bucket that holds every tenant's Kafka key material.
See K13.

**A caller with no tenant who is not a platform admin.** `tenantClause` appends nothing
(`QueryService.java:213`), so this principal sees every tenant's runs. `AppUserServiceImpl:166-176`
refuses to create a `TENANT_USER` or `TENANT_ADMIN` without a tenant when the actor is a platform
admin, and takes the tenant from context otherwise, so the API does not mint one; `app_user.tenant_id`
is nonetheless nullable (`AppUser.java:56-57`, FK added by
`V12__add_tenant_user_fk_constraints.sql:35` with no NOT NULL), so a legacy or hand-edited row would
produce exactly this principal. The codebase treats this shape as a live threat elsewhere --
`StorageConnectionTenantlessCallerTest` exists for nothing else. It is untested here.

### 8.3 The submit destination

`export(destination = "submit")` makes the application server issue an outbound HTTP POST to an
address the caller typed into a `window.prompt`, and returns the response status and body prefix to
the caller (`ReportExportServiceImpl.java:241-248`). Three things follow:

1. **It is not "a configured endpoint".** The class javadoc (`:32-33`) and the button's tooltip
   (`report-pivot.html:69`) both still say the report is posted to a configured endpoint. Nothing is
   configured. The URL is free text supplied per request -- since 2026-09-08 typed into a dialog
   rather than a `window.prompt`, which changes the ergonomics and nothing else.
2. **It is an outbound request primitive available to the lowest role.** The two comparable surfaces
   in this codebase are both administrator-only. `aiAgent.json/addAgent` and `/updateAgent`, which
   name an endpoint the server will later call, are `TENANT_ADMIN` (`AiAgentRestApi.java:21`, no
   method-level override at `:32`, `:42`). `ConnectionProfileServiceImpl:200-203` refuses outright to
   dial an unsaved target for anyone below tenant admin, with the reason written above it at
   `:185-190`.
3. **Its guard is weaker than the sibling guard in the same codebase.** See K2.

Requirement: `submit` requires `TENANT_ADMIN`, enforced in the service on the destination (the
controller cannot express it, because the destination is in the body), with the button hidden from
lower roles through an `auth.canSubmitReports()` computed in the mould of `canManageAgents`
(`core/auth/auth.service.ts:92`). Hiding the button is not the enforcement and must not be mistaken
for it.

---

## 9. Error handling

| What fails | Where it is caught | What the user sees |
|---|---|---|
| Range is blank or inverted | `reports.ts:601-605` -- no request is issued | Error card: "Pick a start and end date, with the start on or before the end." with **Reset to the last 30 days** rather than a Try again that cannot succeed (`reports.html:137-141`) |
| `runs` query throws | `ReportExportServiceImpl:86-93` | Error card: "Could not read the runs for that range." with a Try again button (`reports.html:135-136`) |
| `runs` throws outside that try | `ReportRestApi:45-50` then HTTP 500 | Error card carrying `ProcessUtil.INTERNAL_ERROR_500` -- "Some internal error occurred contact with support." |
| Range returns nothing | not an error | Empty card: "No runs started in this range." / "Widen the dates, or run a job from the Jobs screen to see it here." (`reports.html:143-150`) |
| More than 50,000 runs | `ReportExportServiceImpl:95-97`, `:130-132` | A `capped` pill, a visible sentence saying every figure describes that sample, and an info toast: "Showing the most recent 50,000 runs; narrow the range to see the rest." (`reports.html:92-100`, `reports.ts:592-593`) |
| The prior-period comparison fails or is capped | `reports.ts:702`, `:713` | Nothing. The tiles simply carry no delta -- a missing comparison is not worth interrupting the page for, and comparing against a capped window would compare against a number the server chose |
| The failure detail fails | `reports.ts:645-647`, `:664-667` | The failure table alone shows an error with its own Try again (`reports.html:322-326`); the rest of the page is unaffected |
| Session expired mid-load | `auth.interceptor.ts` refresh, then retry or sign-out | Either a transparent retry or a redirect to sign in |
| Empty or non-JSON 200 | `auth.interceptor.ts:28-39` | The error shape the caller already handles: "The server returned an empty response." |
| Export with no columns | `ReportExportServiceImpl:141-143` | Error toast: "The report has no columns to export." |
| Export over 50,000 rows | `:145-149` | Error toast naming both numbers |
| Bad format | `:150-153` | "Export format must be csv or xlsx." |
| Bad destination | `:177-184` | "Destination must be download, bucket or submit." |
| xlsx conversion fails | `:161-164` | "The spreadsheet could not be built: …" carrying the underlying exception message |
| xlsx comes back empty | `:165-167` | "The spreadsheet came back empty." |
| No bucket chosen | `:199-201` | "Choose a bucket to save into." |
| Bucket refused or unreachable | `:210-213` | "Could not save to that bucket: Unknown bucket: etl-bucket." -- which is what the *suggested default* produces for every non-platform role |
| No submit URL | `:223-225` | "There is no endpoint configured to submit to." -- misleading, since nothing is configured either way |
| Submit target refused | `:227-230` via `:263-293` | One of four messages: not a valid URL / only http and https / that URL has no host / that address is inside this deployment's own network |
| Submit target unresolvable | `:289-291` | "That host could not be resolved." |
| Remote endpoint rejects it | `:249-252` | "The endpoint did not accept it: …" |
| Remote endpoint never answers | **nothing** | The request hangs. No timeout is configured (`:58`) |
| Any export throws | `ReportRestApi:57-62` then 500 | Error toast: "Some internal error occurred contact with support." |

Two messages are wrong rather than merely terse: "There is no endpoint configured to submit to" when
no endpoint is ever configured, and "Could not save to that bucket: Unknown bucket: etl-bucket" when
the bucket exists and the caller is simply not allowed near it. The second leaks nothing -- it is
`resolveServiceForCaller`'s deliberate "unknown" rather than "forbidden" -- but it reads as a
configuration fault rather than a permission one, which will cost somebody an afternoon.

---

## 10. Dependencies

| Depends on | Why |
|---|---|
| `job-runs-and-queue` | Every row of this report is a `job_queue` row. The report's status vocabulary is `JobStatus`, and its "did not finish" case is the same `end_time is null` that run history renders as a dash. **Since 2026-09-08 this is a runtime dependency, not only a conceptual one:** the failure table calls that feature's `POST /message.json/fetchLogs` directly (`reports.ts:639-641`), and both drill-throughs navigate into its routes (`:729`, `:734`). A change to `fetchLogs`'s payload or to those route shapes breaks this screen |
| `job_audit_logs` (via `job-runs-and-queue`) | The Execution measures are derived from the worker's `Job started` audit line (`QueryService.java:294-296`). If that log text ever changes, every execution figure silently becomes `-1` and the measures report nothing rather than reporting wrongly -- which is the right failure mode, but it is a coupling to a string |
| `source-jobs` | The tenant lives on `source_job`, and the report excludes `job_status = 'DELETE'` so that its totals agree with the dashboard's on the same data (`QueryService.java:265-268`) |
| `source-tasks` | The Task dimension is `source_task.task_name`, left-joined |
| `tenants-and-users` | The Owner dimension is `source_job.assigned_user_id` to `app_user`, left-joined |
| `storage-connections` | The bucket destination resolves through a storage connection; `.ai/discovery/features.md:444-450` names report export as one of the seven consumers |
| `content-and-ai-tools` | csv to xlsx runs through the shared JODConverter/LibreOffice route, so Excel export fails wherever the document converter fails |
| `authentication-and-access` | Role, tenant and the shell guards |
| Infrastructure | PostgreSQL (`process/docker-compose.yml:16` pins `postgres:15`); a LibreOffice-capable converter for xlsx; outbound network egress for the submit destination |

Nothing depends on `reports`. It is a leaf, which is why it is a safe place to fix things.

---

## 11. Acceptance criteria

Fixtures assumed throughout: tenant **A** and tenant **B**, each with jobs, tasks, owners and runs in
the last 30 days; user `ua` (`TENANT_USER`, tenant A), `aa` (`TENANT_ADMIN`, tenant A), `ub`
(`TENANT_USER`, tenant B), `pa` (`PLATFORM_ADMIN`). At least one run in tenant A has
`end_time is null`.

**Reading**

1. `ua` opens `/reports` and, without touching anything, sees a grid whose From is 30 days ago and
   whose To is today.
2. `ua` opens `/reports` while the network is slow and sees the spinner card with "Reading your
   runs…", not an empty grid.
3. `ua` sets a range in which tenant A has no runs and sees "No runs started in this range." -- not
   an empty table, not an error. *Wording updated 2026-09-08 to say what the query means: the
   predicate is `q.start_time is not null`, so a run that never started is absent by construction.*
4. With `report.json/runs` forced to fail, `ua` sees "Could not read the runs for that range." and a
   Try again button; pressing it re-issues the request.
5. `ua` sees only tenant A's task names, job names and owner names. **Positive control:** `ub`
   running the same steps on the same day sees only tenant B's, and the two sets do not intersect.
6. A `TENANT_USER` whose token carries no `tenantId` claim is refused, or is scoped to nothing --
   **not** shown every tenant's runs. **Positive control:** the same request with tenant A's claim
   present returns tenant A's runs.
7. `pa` sees runs from both tenants in one grid.
8. An unauthenticated `GET /report.json/runs` returns 401. **Positive control:** the same request
   with `ua`'s bearer token returns 200 and a `SUCCESS` envelope.

**Range**

9. `ua` clears the From date and the request is **refused** with a message naming the missing date;
   the grid does not silently become all-history. **Positive control:** restoring a valid From date
   reloads and the run count changes. **MET ON THE CLIENT 2026-09-08** -- `rangeValid()`
   (`reports.ts:220-223`) blocks the request and `load()` (`:601-605`) sets the message. **NOT MET ON
   THE SERVER:** the same request issued by hand still returns all history. The criterion is not
   satisfied until both halves pass; see K6.
10. `ua` sets From later than To and sees a message saying so, not an empty grid. **MET 2026-09-08**
    -- and the card offers "Reset to the last 30 days" rather than a Try again that cannot succeed
    (`reports.html:137-141`).
11. With a range containing more than 50,000 runs, `ua` sees the `capped` pill, a toast naming the
    50,000 figure, and rows that are the *most recent* ones -- the newest run in the range is present
    in the grid. A visible sentence, not only a tooltip, says every figure on the page describes that
    sample (`reports.html:96-99`).

**Pivot**

12. `ua` sets Rows = Task and Columns = Outcome; every cell in the Completed column equals the number
    of that task's runs that ended Completed, counted independently against the database.
13. `ua` sets Rows = Task, then sets Columns = Task; the two selects end up on different dimensions
    (the previous Rows value moves to Columns) rather than both reading Task.
14. `ua` presses the swap button and the grid transposes: the previous row labels are now the column
    headers.
15. `ua` switches the measure from Runs to Median duration; the row total for a task is the median of
    that task's runs, **not** the sum of its cell medians.
16. A task with no runs in the range does not appear as a row. **Positive control:** an outcome with
    no runs in the range still appears as a column, so the shape stays comparable across ranges.
17. With the measure set to Mean duration, a group containing only runs that never finished shows an
    em dash rather than `0s`, and a group whose runs genuinely took zero measurable seconds shows
    `0s`. **MET IN PART 2026-09-08.** `humanSeconds` (`pivot.ts:281-290`) now returns `0s` for zero
    and an em dash only for the negative sentinel, and `cellText` (`report-pivot.ts:193-198`) prints
    an em dash for a cell with **no runs**. The remaining case is a cell that *has* runs, none of
    which finished: `aggregate` returns 0 for it and it therefore reads `0s`, which is the wrong
    answer. Distinguishing it needs `aggregate` to report "nothing measurable" separately from zero.

**Drilling**

18. `ua` clicks a cell showing 7 and the drawer opens listing exactly 7 runs, headed with the row and
    column labels.
19. `ua` clicks a cell whose runs all lack an end time, under a duration measure; the drawer opens and
    lists them. **Positive control:** a cell with no runs behind it at all is not clickable.
    **STILL FAILS.** `[disabled]="!pivot().matrix[ri][ci]"` (`report-pivot.html:196`) is unchanged,
    so such a cell reads `0s` and refuses the click while the row total beside it drills to the same
    runs. See K11.
20. `ua` clicks a row total and the drawer lists every run in that row; clicking a column total lists
    every run in that column.
21. With more than 300 runs behind a cell, the drawer lists 300 and a final line reading "… and N
    more".
22. `ua` presses Escape and the drawer closes. **STILL FAILS.** See K16.

**Chart**

23. `ua` selects each of the ten chart kinds in turn; each draws without a console error and the
    legend matches what is drawn. *With the measure set to Runs, so all ten are offered -- see 25.*
24. `ua` selects Area with three series; all three are distinguishable -- no series is completely
    hidden behind another. **MET 2026-09-08** (`report-chart.ts:408`). **Radar still fails the same
    test**; see 25a.
25. With the measure set to Median duration, the additive-only kinds (Stacked, 100% stacked, Pie,
    Donut) are unavailable and say why. **Positive control:** with the measure set to Runs, all ten
    are available. **MET 2026-09-08** -- and Radar is disabled with them, because a radar sums its
    spokes too (`report-pivot.ts:96-97`). Switching the measure while a summing chart is open falls
    back to Grouped rather than leaving a disabled button under a wrong chart (`:120-122`).
    **25a.** *Added 2026-09-08.* With the measure set to Runs and four or more rows, `ua` selects
    Radar; every series is distinguishable, and if rows beyond the fourth are not drawn the screen
    says so. **STILL FAILS** on both halves -- `radarFills` (`report-chart.ts:413-426`) returns
    opaque polygons and silently slices at four. See K9.
26. `ua` switches the console to dark mode; every series, axis label, grid line and heat-map cell
    remains legible, and no colour is hard-coded.
27. `ua` narrows the browser to 375px; the chart re-measures rather than overflowing, and the pivot
    table scrolls horizontally inside its card while the page body does not. **The page-body half
    was failing and was fixed 2026-09-08**: the dashboard's chart cards needed `min-w-0`
    (`reports.html:190-194`) or the donut's legend widened the grid track past the viewport.

**Export**

28. `ua` presses CSV; a file downloads whose name starts with a slug of the report title and ends
    `.csv`, and whose first line is the column headers currently on screen.
29. `ua` presses Excel; a `.xlsx` downloads that opens in a spreadsheet with the same numbers.
30. With a task named `=cmd|' /C calc'!A0`, the exported csv shows that cell prefixed with an
    apostrophe and no spreadsheet evaluates it. **Positive control:** a cell holding `-5` exports as
    `-5` and totals correctly.
31. `ua` chooses Bucket, picks a bucket their tenant owns from a **list** (not free text), chooses
    Excel, and the file appears at `<folder>/<name>.xlsx` in that bucket. **STILL FAILS on both
    halves:** the bucket field is free text (`report-destination-dialog.ts:35`) and the format is
    hard-coded csv (`report-pivot.html:62`). See K13, K15.
32. `ua` chooses Bucket and names `etl-bucket`; the write is refused. **Positive control:** `pa`
    naming the same bucket succeeds, and `ua` naming their own tenant's bucket succeeds.
33. `ua` chooses Bucket and a bucket belonging to tenant B; the write is refused. **Positive
    control:** `ub` writing to that same bucket succeeds.
34. A folder of `../../etc` writes to a key with no `..` in it, inside the bucket.
35. `ua` does not see a Submit control at all. **Positive control:** `aa` does. **STILL FAILS.**
    See K1.
36. `aa` submits to `http://169.254.169.254/latest/meta-data/` and is refused with the "own network"
    message. **Positive control:** with `report.submit.allow-internal=true`, the same request reaches
    the connection attempt and fails for a different reason.
37. `aa` submits to `http://100.64.0.1/` and to `http://[fc00::1]/` and both are refused.
38. `aa` submits to a public host that never responds; the request fails within the configured read
    timeout rather than hanging.
39. `ua` calls `POST /report.json/export` directly with `destination: "submit"`; it is refused by the
    server, not merely absent from the UI. **Positive control:** the same call with
    `destination: "download"` succeeds for `ua`.
40. An export with `format: "exe"` is refused; one with `destination: "email"` is refused rather than
    treated as a download.

**Configuration and tests**

41. `report.submit.allow-internal` appears in `application-dev.properties`,
    `application-stage.properties` and `application-prod.properties`, and
    `ApplicationPropertiesDeclarationTest` fails if any profile loses it. **STILL FAILS** -- grepped
    again on 2026-09-08, zero `report.*` keys in all four files. See K3.
42. `QueryService.runReportRows` has a test asserting the SQL contains `sj.tenant_id = <id>` for a
    tenant user, contains no `tenant_id =` for a platform admin, and is refused rather than unscoped
    for a tenantless non-admin caller -- in the shape of `UserStatisticsQueryTest:27-50`.
    **STILL FAILS.** See K5, K17.
43. `Reports` and `ReportChart` have component tests covering the loading, error, empty and truncated
    states and at least the grouped, stacked and donut chart kinds. **STILL FAILS** -- neither has a
    spec. `pivot.spec.ts` grew from 20 cases to 26 and gained the execution measures and the
    additivity assertions, and `report-destination-dialog.spec.ts` (7 cases) is new, but the three
    files this criterion names do not exist. See K17.

**The dashboard, added 2026-09-08.** These describe the page as it now behaves and are what a
reviewer should check next.

44. `ua` opens `/reports` and, before touching anything, sees four tiles, an outcome donut, a
    duration histogram, a runs-by-day chart, a task-health table and — if anything failed — a table
    of the errors, with the builder collapsed. **Positive control:** pressing "Build your own view"
    reveals the builder with Task x Outcome and the measure Runs.
45. `ua` picks a task in the Task filter. The Runs-started tile, the Failed tile, the success rate,
    the median duration, all three charts, the task-health table **and** the pivot grid inside the
    builder all narrow to that task together, and a removable pill above them names the filter with
    "N of M runs" beside it. **Positive control:** removing the pill restores every one of them to
    the same numbers as before.
46. Clicking a task's name in the task-health table applies the same Task filter; clicking it again
    removes it.
47. `ua` collapses the builder, changes nothing, and reopens it: the dimensions, measure, chart kind
    and any open drill drawer are exactly as they were left, and no request was issued.
48. The Workspace filter is absent for `aa` (one workspace) and present for `pa` (more than one).
    **Positive control:** with it present and unset, the Overview subtitle states in bold how many
    workspaces the totals combine; selecting one removes that sentence and the totals change.
49. `ua` sets Rows = Owner and Columns = Task where a task name contains a hyphen, then selects Line.
    The axes are **not** transposed. **Positive control:** setting Columns = Day does put days on the
    x axis. *This is what `dayAxis` (`report-pivot.ts:102-103`) replaced: the old rule tested the
    first column label for a hyphen, and every seeded task name contains one.*
50. With the default 31-day range at 1024px, no two labels on the runs-by-day chart overlap, and the
    value above a bar is either legible or absent -- never drawn on top of its neighbour.
51. `ua` clicks a bar on the runs-by-day chart. Both dates become that day and the page refetches;
    the bar's stacked segments match the outcome donut that follows. **Positive control:** clicking a
    day with no runs changes nothing -- `focusDay` returns early on a zero bar (`reports.ts:747`) --
    rather than loading an empty range.
52. With all runs on one day inside a 30-day range, the runs-by-day caption reads "All of these runs
    happened on one day", not a claim about a trend. *`activeDays()` (`reports.ts:447`) counts days
    carrying runs; `runsByDay().length` is the axis, which is the range.*
53. With a range longer than 366 days, the chart keeps the **most recent** 366 days and says it has
    (`daysCapped()`), and the newest day in the range is drawn. **Positive control:** a 30-day range
    draws 30 bars and reports no cap.
54. With the measure set to Median execution, the pivot's figures are smaller than the same
    Median duration figures on the same rows, and the note above the grid says the wait has been
    taken out (`report-pivot.ts:60-67`). **Positive control:** a run whose `Job started` audit line
    is missing is excluded rather than counted as instant.
55. The Median duration tile's foot names both parts -- "0.23s running, rest is queue wait" -- when
    an execution median is available, and says "queued to finished, wait included" when it is not.
56. `ua` opens a range containing failures and the browser makes exactly **three** requests:
    `report.json/runs` for the range, `report.json/runs` for the prior window, and
    `message.json/fetchLogs` for the failure detail. **Positive control:** a range with no failures
    makes two -- `loadFailures` does not fire (`reports.ts:636`) -- and opening the builder makes
    none.
57. In the failure table, the job name opens that job's run history and the Logs button opens that
    run's log with entries in it. **Positive control:** a row with no `jobId` or no `jobQueueId`
    renders no Logs button at all rather than one that opens nothing.
58. With a Workspace or Owner filter applied, the "What failed, and why" table narrows with the rest
    of the page. **STILL FAILS** -- `visibleFailures` (`reports.ts:546-557`) honours Task, Job and
    Outcome only. See K22.

---

## 12. Known issues

Each was a defect present in the code when it was recorded. Entries fixed on 2026-09-08 are marked
**FIXED** with what closed them and are kept rather than deleted; the history is the point of this
register. K20 to K23 were found on 2026-09-08 and are not fixed.

**K1 -- `submit` is an outbound HTTP primitive available to `TENANT_USER`. OPEN.**
`ReportExportServiceImpl.java:221-253` POSTs a file to a URL supplied in the request body and returns
`response.getStatusCodeValue()` and the first 500 characters of the body to the caller (`:244-248`).
`ReportRestApi.java:27` gates the whole controller at `TENANT_USER`. The URL is free text typed by
the caller -- since 2026-09-08 into `ReportDestinationDialog` rather than a `window.prompt`, which
changes nothing about this finding -- so nothing is "configured" despite the class javadoc at
`:32-33` and the button tooltip at `report-pivot.html:69` saying so. The two comparable surfaces in
the same codebase are administrator-only: `AiAgentRestApi.java:21` (`TENANT_ADMIN` for the endpoints
that name a URL the server will call) and `ConnectionProfileServiceImpl.java:200-203` ("Only a tenant
admin can test a connection that is not saved yet"). Severity: this is still the highest-consequence
finding in the feature, and 2026-09-08 did not touch it.

**K2 -- the submit guard misses ranges the sibling guard in this codebase covers. OPEN.**
`rejectUnsafeTarget` (`ReportExportServiceImpl.java:280-288`) tests only the five `InetAddress`
predicates. `AiAgentServiceImpl.isInternalAddress` (`:381-394`) additionally covers carrier-grade NAT
`100.64.0.0/10`, the IPv6 unique-local range `fc00::/7` and `0.0.0.0/8`, with a comment at `:377-379`
explaining that `InetAddress` does not classify them. The report guard also permits plain **http** to
any public address, where `AiAgentServiceImpl.validateEndpoint:343-345` requires https unless the host
is on an operator-named allow-list. Whether `RestTemplate`'s default request factory follows a
redirect from an allowed host to an internal one is **not verified** -- no redirect policy is set at
`ReportExportServiceImpl:58`, and it should be checked before the guard is called complete.

**K3 -- `report.submit.allow-internal` is declared in no properties file. OPEN**, re-grepped
2026-09-08: zero `report.*` keys across all four profiles.
`ReportExportServiceImpl.java:66-67` reads it with a fail-closed default and it appears in none of
`application.properties`, `application-dev.properties`, `application-stage.properties`,
`application-prod.properties` (grepped: zero `report.*` keys in all four).
`ApplicationPropertiesDeclarationTest:15-25` states the rule this breaks: "the only way to find out a
property existed was to read the class that reads it -- which is how a deployment ends up on the
fail-closed default by accident rather than on purpose."

**K4 -- the submit `RestTemplate` has no timeouts. OPEN.** `ReportExportServiceImpl.java:58` --
`private final RestTemplate restTemplate = new RestTemplate();`. It is the only bare `new
RestTemplate()` in the backend; `OpenSearchAuditLogClient.java:45-50` is the house pattern, with 3s
connect and 5s read. A slow or hostile endpoint holds a Tomcat request thread indefinitely.

**K5 -- the report's tenant narrowing is inert for a tenantless non-admin caller, and untested.
OPEN.** `QueryService.tenantClause:212-214` returns an empty string when
`TenantContext.getTenantId()` is null, whatever the role -- re-read on 2026-09-08 and unchanged.
Layer 4 cannot help: the query is native SQL, which Hibernate's `tenantFilter` does not touch, and
`JobQueue` never declared the filter anyway (`database.md:338`). `ReportExportServiceImplTest:28`
constructs the service with a null `QueryService`, so `runRows` is exercised by no test at any level,
and `ReportRestApi` is on `backend.md:1061`'s list of twenty untested controllers. Reachability
through the API is closed (`AppUserServiceImpl:166-176`), but `app_user.tenant_id` is nullable, so a
legacy row would produce this principal. The Workspace dimension added on 2026-09-08 makes the
consequence *visible* -- such a caller now sees a Workspace picker listing every workspace -- but
does nothing to prevent it.

**K6 -- clearing a date silently widens the report to all history. PARTLY FIXED 2026-09-08 on the
client; the server is unchanged.**
`dateRangeFilter` (`QueryService.java:157-162`) still returns an empty string unless *both* dates
match `\d{4}-\d{2}-\d{2}`, and `ReportRestApi.java:41-42` still marks both parameters optional. The
result is still an unindexed scan of `job_queue` -- the largest table in the schema, with only
`idx_job_queue_job_id` (`JobQueue.java:19-21`) -- capped at 50,000 rows only after the whole result
set has been materialised (`ReportExportServiceImpl.java:95-97`).

What changed is that the screen no longer produces it: `rangeValid()` (`reports.ts:220-223`) tests
both dates against the same pattern *and* asserts start <= end, `load()` (`:601-605`) refuses to
issue the request and sets a message naming the rule, and the error card offers "Reset to the last
30 days" instead of a "Try again" that could never succeed (`reports.html:137-141`). There is still
no server-side validator and no `MAX_SPAN_DAYS`, so `curl` reaches the scan exactly as before.
**Do not close this entry on the strength of the client guard.**

**K7 -- the stacked and 100%-stacked charts are arithmetically wrong for ten of the twelve measures.
FIXED 2026-09-08.** Closed by `ADDITIVE = {count, sum}` (`pivot.ts:135`) and the
`SUMMING`/`kindAllowed`/`kindRefusal` trio in the builder (`report-pivot.ts:96-112`): Stacked and
100% stacked are `[disabled]` with a stated reason unless the measure is additive
(`report-pivot.html:96-99`), and an `effect` (`report-pivot.ts:120-122`) falls back to Grouped if the
measure changes underneath an open chart. The underlying arithmetic is untouched and still correct
for what it now draws -- `report-chart.ts:188` still scales `stacked` by `max(rowTotals)` and `:240`
still divides by the row total for `pct`, which is right once only additive measures reach them.
`pivot.spec.ts:194-199` asserts the additivity set directly.

**K8 -- pie and donut present a share of a meaningless total. FIXED 2026-09-08**, by the same gate:
`SUMMING` includes `donut` and `pie` (`report-pivot.ts:97`). `radialSegments`
(`report-chart.ts:310-340`) still sums `colTotals` and `centre()` (`:544-549`) still labels that sum
"total", which is now only ever reached for `count` and `sum`, where it is true. The comment on
`ADDITIVE` (`pivot.ts:125-134`) records the case that produced this finding: a mean-duration donut
drew 56%/44% for data whose real split was 92%/8%.

**K9 -- area and radar series occlude each other. AREA FIXED 2026-09-08; RADAR OPEN.**
`areaFills` (`report-chart.ts:397-411`) now returns `opacity: 0.35` per series (`:408`) and the
template binds it (`:72`), with the stroke drawn on top keeping each edge legible. **Radar is
untouched**: `radarFills` (`:413-426`) returns fully opaque polygons with no opacity, is still called
twice per render -- once from `segments()` (`:306`) and once from `strokes()` (`:431`) -- and still
slices at four series (`:418`) with nothing on screen saying so. The additivity gate now keeps radar
off a non-additive measure, which narrows when this is reachable without fixing it.

**K10 -- the line/area axis flip is decided by looking for a hyphen. FIXED 2026-09-08.** Replaced by
a `dayAxis` input (`report-chart.ts:113`) that the builder computes from the dimension keys
themselves (`report-pivot.ts:102-103`) and passes down (`report-pivot.html:109`). `seriesLayout`
(`report-chart.ts:350-358`) flips on that; the label-shape heuristic survives only as a fallback for
`dayAxis === 'none'`, and even then it now tests a real ISO-day pattern (`ISO_DAY`, `:18`) rather
than the presence of a hyphen. The comment at `:342-349` records the failure that forced it: every
task in the seeded catalogue is named like `report-history setting left blank`, so putting tasks in
the columns silently transposed the chart.

**K11 -- a cell with runs behind it can be unclickable. OPEN.** `report-pivot.html:196` still
disables the cell button on `!pivot().matrix[ri][ci]`. Under any duration measure, `aggregate`
returns 0 for a group whose runs all carry `seconds = -1` (`pivot.ts:186-187`), so a cell containing
genuine unfinished runs is disabled and its drill-down is unreachable. Row totals have no such guard
(`report-pivot.html:204-207`), so the same runs *are* reachable one level up.

2026-09-08 made this **more** visible rather than less. `cellText` (`report-pivot.ts:193-198`) now
prints an em dash only when `cellRows` is empty, so a cell with unfinished runs reads `0s` and
refuses the click, next to an empty cell that reads `—` and also refuses it. The fix is to bind
`[disabled]` to `cellRows[ri][ci].length === 0`, which is the information the grid already has.

**K12 -- zero and no-data render identically. FIXED 2026-09-08.** `humanSeconds`
(`pivot.ts:281-290`) now treats **negative** as the no-data sentinel and returns `0s` for a real
zero, keeping two decimals below ten seconds so the execution measures -- which are genuinely
sub-second here -- read as something rather than as nothing. `cellText` (`report-pivot.ts:193-198`)
uses `cellRows` to distinguish a cell with no runs from a cell whose runs measured zero. The
assertion in `pivot.spec.ts:147` changed with it, and the comment at `:142-146` records why. One case
remains and is filed as K11: a cell that has runs, none of which finished.

**K13 -- the bucket the Save dialog suggests cannot work for the people most likely to press it.
OPEN.** The prompt became a dialog on 2026-09-08 and the default did not change:
`report-destination-dialog.ts:65` initialises the bucket to `'etl-bucket'` and `:35` renders it as a
free-text `<input>` with the same string as its placeholder. `KafkaSecretService.java:27` defines that
exact string as `SECRET_BUCKET`; `StorageBrowserServiceImpl.isPlatformBucketName:466-468` names it as
a platform bucket, and `resolveServiceForCaller:431-437` throws `Unknown bucket: etl-bucket.` for
every caller who is not a platform admin. So a tenant user or tenant admin who accepts the default
gets "Could not save to that bucket: Unknown bucket: etl-bucket." (`:210-213`), and a platform admin
who accepts it writes a report into the bucket holding every tenant's Kafka key material. The fix is
the same as it was: a `select` populated from `storage.json/buckets`.

**K14 -- three browser prompts stand in for a dialog. FIXED 2026-09-08.** Closed by
`features/reports/report-destination-dialog.ts` -- a CDK `Dialog` component with two modes,
`cdkFocusInitial`, labelled fields, a `valid()` guard on the confirm button, trimming and a `reports`
fallback for a blank folder, opened from `report-pivot.ts:310-330`, with 7 tests in
`report-destination-dialog.spec.ts`. It is themed, keyboard-reachable and not blockable by a browser
setting. Two things the requirement in §4.4 asked for did not arrive with it and are filed
separately: the bucket picker (K13) and the format choice (K15). It also does not reuse
`shared/ui/form-dialog.ts`, which is a divergence worth an argued decision.

**K15 -- Save and Submit can only produce csv. OPEN.** `report-pivot.html:62` and `:68` pass the
literal `'csv'`, exactly as the old template did. The server handles format and destination
independently, so xlsx-to-a-bucket is implemented and unreachable. Now that the dialog exists, this
is one radio group and one parameter.

**K16 -- the drill drawer is a bespoke overlay with no dismissal affordances. OPEN.**
`report-pivot.html:228-267`: `position: fixed`, `z-40`, no `role="dialog"`, no `aria-modal`, no focus
management, no Escape handler, no backdrop. Closing requires finding and clicking the Close button.
The drawer moved from `reports.html` into `report-pivot.html` on 2026-09-08 unchanged.

**K17 -- no test covers the screen, the chart, the controller or the query. PARTLY ADDRESSED
2026-09-08; the three files this entry names still do not exist.**

Added: `pivot.spec.ts` grew from 20 to 26 `it` blocks, with a five-case group on the execution
measures asserting they read `EXEC_SECONDS` rather than `SECONDS`, exclude a run whose pickup was
never recorded, and are not additive (`:165-200`); the formatting group now pins the deliberate
`0 -> '0s'` change (`:141-149`). `report-destination-dialog.spec.ts` is new (7 cases). Around the
feature, `shared/charts/day-series.spec.ts` (7) and `bar-chart.spec.ts` (11) cover the gap filling,
the recent-end cap and the pixel-measured label thinning that the runs-by-day chart depends on.

Still absent, and still the point of this entry: `Reports` (`reports.ts`, 780 lines), `ReportPivot`
(`report-pivot.ts`, 347 lines) and `ReportChart` (`report-chart.ts`, 550 lines) have no spec, and
neither `ReportRestApi` nor `QueryService.runReportRows` has a test at any level. That is 1,677 lines
of untested frontend -- more than before, because the screen grew -- and the entire tenant-isolation
surface.

**K18 -- `TableShell` is fed a meaningless count. OPEN.** `report-pivot.html:128-129` passes the same
expression to `[shown]` and `[total]`, so the pivot card's heading always reads "(N of N)". The task
health table does the same (`reports.html:251-252`). The failure table deliberately does
(`reports.html:322-324`), with the reason written above it at `:319-321`: `[total]` used to be
`counts().failed`, which comes from the runs feed while the rows come from `fetchLogs`, and the two
filter on different date columns -- so the header could read "(5 of 4)". Cosmetic in all three.

**K19 -- run duration relies on a PostgreSQL type coercion. OPEN, and widened 2026-09-08.**
`ReportExportServiceImpl.java:112` does `Integer.valueOf(String.valueOf(r[4]))` on the result of
`case when q.end_time is null then -1 else round(extract(epoch from …)) end`
(`QueryService.java:257-258`). On PostgreSQL 14 and later, `extract` returns `numeric`, so the driver
hands back a `BigDecimal` whose `toString` is `"123"` and the parse succeeds; the deployment pins
`postgres:15` (`process/docker-compose.yml:16`). On PostgreSQL 13 and earlier, `extract` returns
`double precision` and the same expression would yield `"123.0"`, which `Integer.valueOf` rejects
with a `NumberFormatException` that the `try/catch` at `:86-93` does not cover -- it would surface as
a 500.

The new `exec_seconds` column is parsed the same way at `:119` --
`Double.valueOf(String.valueOf(r[8]))` -- which is safer, because `Double.valueOf` accepts both
forms. But it is a second implicit coercion over the same JDBC boundary, and it is guarded only by
`r.length > 8 && r[8] != null`. **Not verified against a live PostgreSQL 13**; recorded because the
coercion is implicit and one version away from breaking.

**K20 -- the prior-period comparison doubles the heaviest query on every visit. NEW 2026-09-08.**
`loadPriorPeriod` (`reports.ts:676-715`) issues a second full `GET /report.json/runs` over the
equally-long window before the selected one, purely to compute two numbers for the tile feet -- the
run count and the success rate. It runs the same unindexed `job_queue` scan as the main query
(§6), against a range of the same size, on every load and every date change. It is written carefully
in every other respect: it discards a stale answer (`:696`), refuses to compare against a `truncated`
window (`:702`), and swallows its own failure rather than interrupting the page (`:713`). But the
server has no endpoint that returns a count without returning the rows, so the browser downloads a
whole second population to reduce it to two integers. Either a `count`-shaped endpoint or a cached
figure would remove it. Severity: cost, not correctness -- but it doubles the cost of the thing K6
says is already unbounded.

**K21 -- the page now renders two bar-chart implementations at once. NEW 2026-09-08.**
`report-chart.ts` (550 lines) has always duplicated `shared/charts`
(`.ai/discovery/frontend.md:394-396`, `:804-806`). Until this pass the duplication was on a screen
that used only the private one. The dashboard added above the builder uses the **shared** `Donut`,
`Histogram` and `BarChart` (`reports.ts:103`), so a reader who opens the builder sees two independent
bar-chart engines on one page, each with its own label-thinning rule, colour lookup and resize
strategy. The cost is already visible: the *same* label-overlap defect had to be fixed twice on
2026-09-08, once in `report-chart.ts` (`:488`, `:511-512`) and once in `shared/charts/bar-chart.ts`
(`:199-225`), with two different constants. Merging them is not a small change and is not urgent;
recording it is, because the next fix will otherwise be applied to one of the two.

**K22 -- the filters narrow everything except the failure table's owner and workspace. NEW
2026-09-08.** `visibleFailures` (`reports.ts:546-557`) narrows the failure rows by Task, Job and
Outcome. Owner is explicitly not applied and the code says so (`:550-552`): a failure row comes from
`fetchLogs`, which returns `job_queue` columns only and carries no owner. Workspace is not considered
at all. So a platform admin who filters the page to one workspace gets tiles, charts, task health and
a pivot describing that workspace, above a table listing **every** workspace's failures, with nothing
saying the last table is different. The `runIndex` map (`:240-250`) already joins job and task names
onto a failure row by run id; owner and workspace could be joined the same way, from the same
payload, and the workspace one matters most because it is the isolation-shaped filter.

**K23 -- the failure table is drawn from a different date column than the rest of the page. NEW
2026-09-08.** The runs feed filters on `date(q.start_time)` (`QueryService.java:252`, `:300`);
`fetchLogs`, which feeds "What failed, and why", filters on `cast(jq.date_created as date)`
(`QueryService.java:469`). A run queued just before midnight and started just after falls into the
range for one and out of it for the other. The header count was already corrected for this
(`reports.html:319-324` sets `[total]` from the rows actually rendered, with the reason written down),
so the symptom of "(5 of 4)" is gone -- but the two populations still differ, and nothing on screen
says the failure list is bounded differently from the Failed tile above it. The honest fixes are to
select the error text from the same query, or to state the difference in the section subtitle.

---

## 13. Missing functionality

*Reviewed 2026-09-08. Four items below were delivered and are kept, marked, with what remains of
each; the rest are unchanged.*

**Required date range with a bound.** Section 7 V1/V3. Both dates required at the controller, start
not after end, and a maximum span (365 days is a defensible starting point) so that "narrow the
range" is advice the product gives rather than a message the user gets after a table scan. Cost: a
validator method on `ReportExportServiceImpl.runRows`, two `required = true` changes, one guard in
the template. **The template guard was built 2026-09-08** (`reports.ts:220-223`, `:601-605`) and it
carries the message. The controller change, the validator and the maximum span are all still
outstanding, and they are the half that actually bounds the query.

**A supporting index.** Section 6. One changelog set. Without it the report is a sequential scan of
`job_queue` on every load, and every load happens on every date change.

**Role separation for the submit destination.** Section 8.3. A destination check inside
`ReportExportServiceImpl.export` plus an `auth.canSubmitReports()` computed and a template gate. Cost:
about twenty lines and one test file.

**An allow-list for submit targets.** Replace the boolean with `report.submit.allowed-hosts`,
mirroring `ai.allowed-endpoint-hosts` (`AiAgentServiceImpl.java:82-83`, `:361-372`), and adopt
`isInternalAddress`'s fuller range checks (`:381-394`). The boolean stays as the escape hatch for a
deployment that genuinely posts to something inside its own network, and gets declared in all three
profiles.

**Timeouts on the submit client.** Section 5.2. Four lines, copied from `OpenSearchAuditLogClient`.

**A real export dialog.** Section 4.4. Bucket list from `storage.json/buckets`, folder, format for
every destination, validated URL. **PARTLY BUILT 2026-09-08** as `report-destination-dialog.ts`,
which closed K14: the prompts are gone, the fields are labelled and themed, the confirm button is
guarded, and there are 7 tests. It did **not** remove K13 or K15 -- the bucket is still free text
defaulting to a platform bucket, and both callers still hard-code csv. What remains is a `select`
fed by `storage.json/buckets` and a format radio, plus threading `format` through the two call sites
(`report-pivot.html:62`, `:68`). Small, and now much smaller than it was.

**Chart-kind gating by measure additivity.** Section 3. **BUILT 2026-09-08** -- `ADDITIVE`
(`pivot.ts:135`), `SUMMING` (`report-pivot.ts:96-97`), `kindAllowed`/`kindRefusal` (`:106-112`), a
`[disabled]` and a `title` on the buttons (`report-pivot.html:96-99`), a sentence beside the row
(`:101-105`) and a fallback effect (`report-pivot.ts:120-122`). Closes K7 and K8. Radar was included
in the summing set, which was not in the original plan and is right: a radar sums its spokes.

**Fill transparency on overlay charts.** K9. **HALF BUILT 2026-09-08** -- area carries
`fill-opacity` 0.35 (`report-chart.ts:408`). Radar was left alone, so the decision the original entry
asked for -- whether radar should be filled at all -- is still open, along with its silent four-series
cap and its double render.

**A tenant dimension for the platform admin.** Section 8.2. **BUILT 2026-09-08**, and both halves
rather than either: `tenant` is a dimension the builder can pivot on (`pivot.ts:79`) *and* a filter
on the range card that appears only when more than one workspace is present (`reports.ts:127`,
`:144`), with the Overview subtitle saying so in bold when it is unset (`reports.html:158-161`). The
column came from `tenant.tenant_name` through a left join rather than from `source_job.tenant_id`, so
the report shows a name rather than an id (`QueryService.java:264`, `:292`).

**A supporting index -- now more necessary, not less.** *Added to this section 2026-09-08.* Section 6
proposed one changelog set for `job_queue (start_time::date)`. Since then the page issues **two** of
that scan per visit rather than one, because the prior-period comparison runs the same query over the
preceding window (K20). Nothing about the index proposal changes; its value roughly doubled.

**A count-shaped endpoint for the period comparison.** *Added 2026-09-08.* K20. The tiles need two
integers from the prior window and download the whole window to get them. A
`GET /report.json/summary?startDate&endDate` returning `{runs, completed, failed}` -- one `group by`
over the same predicate -- would remove the second scan and the second payload. Alternatively drop
the comparison; it is the least-load-bearing thing on the page.

**Workspace and owner on the failure table.** *Added 2026-09-08.* K22. `runIndex`
(`reports.ts:240-250`) already joins the job and task names onto a failure row from the runs payload
by run id; owner and workspace are on the same rows and could ride along, after which
`visibleFailures` can honour all five filters instead of three. Until then the failure table is the
one place on the page where a filter does not reach, and a workspace filter that does not reach is
the one that matters.

**Tests.** K17. Still three files: a `QueryService.runReportRows` isolation test in the shape of
`UserStatisticsQueryTest`; a `reports.spec.ts` covering load/empty/error/truncated/range-refusal, the
single-`data()` filter contract (criterion 45) and the three-request shape (criterion 56); and a
`report-chart.spec.ts` covering geometry for the ten kinds at a fixed width plus the `dayAxis` flip.
A fourth is now worth having: a `report-pivot.spec.ts` for `kindAllowed`, `kindRefusal`, the
fallback effect and `cellText`, all of which are pure functions of signals and cheap to test.
`pivot.spec.ts` was extended on 2026-09-08 and needs no further change for these.

**Saved reports.** Not present, not required, and worth naming so nobody assumes it exists: there is
no way to save a shape and come back to it, no URL that encodes the current dimensions and measure,
and no scheduled delivery. The query engine has all three (`query-and-search-engines`), so if this is
wanted the pattern already exists. Deep-linking the shape into the query string is the cheap 80% and
is not in scope for this pass.

**An audit trail for export.** Writing a file into a bucket and posting the console's data to an
external address both leave no record beyond the application log lines at
`ReportExportServiceImpl.java:211` and `:250`, and those only fire on failure. Nothing records a
successful bucket write or a successful submit, so there is no way to answer "who sent our run data
where". Whether this belongs to Reports or to a cross-cutting action log is a question for section 6
of the synthesis document.
