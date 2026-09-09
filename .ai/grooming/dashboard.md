# Grooming -- Dashboard

Feature `dashboard`, migration status **migrated**. All paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Purpose

The dashboard is the screen an operator opens first, to answer three questions before anything
else: *is the fleet healthy right now*, *when did work actually run*, and *which job was
responsible*.

It answers them in that order. Six counters across the top say how many jobs exist, how many are
switched on, and how the last run of each went. Two rings and a bar chart break those counters
down. Below them an hour-by-weekday grid shows *when* runs happened, because a scheduler's real
failure mode is not "a job failed" but "everything piled into 02:00 and half of it missed its
window". Clicking one square in that grid opens the fourth thing: a table of every job that ran in
that one hour, with its outcome counts, and every count is a link into the run history filtered to
exactly that job, that hour and that outcome.

Everything is scoped to a date range, defaulting to the last seven days, and everything is scoped
to the caller's tenant.

---

## 2. Existing behaviour

Both applications have this screen. The old one is `HomeComponent`, the new one is `Dashboard`.

### 2.1 Route and access

| | Old | New |
|---|---|---|
| Route | `home` (`scheduler1/src/app/app.routing.ts:53-55`) | `dashboard` (`scheduler1/next/src/app/app.routes.ts:63-65`), plus shell `''` → `dashboard` (`:58-61`) |
| Guard | `AuthGuard` on the route | `authGuard` on the shell parent (`app.routes.ts:46-53`); the dashboard child declares no `minRole` and no `roleGuard` |
| Navigation entry | `app.component.html` nav | `features/shell/shell.ts:49` -- `{ label: 'Dashboard', path: '/dashboard', icon: 'chart' }`, not `adminOnly` |
| Wildcard | `**` → `home` | `**` → `''`; the shell's empty path redirects to `dashboard` |

The old app has no dark mode at all; the new app is theme-aware
(`scheduler1/next/src/app/core/theme.service.ts`, class-based `html.dark`).

### 2.2 Date range

The old app derives both defaults through Angular's `DatePipe` pinned to `America/Chicago`
(`_component/home/home.component.ts:32, 99-101`): `endDate` is today in Chicago, `startDate` is six
days earlier. `applyFilter()` (`:120-130`) refuses an empty date and refuses `start > end`, each
with a toast; `resetFilter()` (`:132-136`) returns to the seven-day default. The `To` input is
clamped with `[max]="today_date"` and the `From` input with `[max]="filterEndDate"`
(`home.component.html:8-15`). A `Reset` button appears only when the range differs from the default
(`isCustomRange`, `:116-118`, template `:22-27`).

The new app derives both defaults from `new Date().toISOString().slice(0, 10)`
(`features/dashboard/dashboard.ts:277-281`), which is **UTC**, not Chicago and not the browser's own
zone. `applyRange()` (`:255`) performs **no validation at all**. The `From` input carries
`[max]="endDate()"` and the `To` input carries only `[min]="startDate()"` -- there is no upper bound
(`dashboard.html:14-21`). `Reset` is always shown (`:23`).

### 2.3 What loads, and when

The old app fires four requests on init and then **re-fires all four every 60 seconds**
(`home.component.ts:34, 105-107, 147-152`), passing `silent = true` so the auto-refresh does not
flash the global spinner and does not raise a toast on failure. `ngOnDestroy` clears the timer
(`:109-114`). The drill-down table deliberately survives an auto-refresh, because
`autoRefreshDashboard()` calls the four fetchers directly rather than `loadDashboard()`, and only
`loadDashboard()` clears it (`:138-145`).

The new app fires **five** requests in `load()` (`dashboard.ts:136-158`) -- the same four plus
`notification.json/unreadCount` -- **once, on `ngOnInit`**, and never again unless the user presses
Apply or Reset. There is no timer anywhere in `features/dashboard`.

| Call | Old | New |
|---|---|---|
| `dashboard.json/jobStatusStatistics` | `hom.service.ts:13-16` | `dashboard.service.ts:22-25` |
| `dashboard.json/jobRunningStatistics` | `hom.service.ts:18-21` | `dashboard.service.ts:27-30` |
| `dashboard.json/weeklyRunningJobStatistics` | `hom.service.ts:23-25` | `dashboard.service.ts:32-35` |
| `dashboard.json/weeklyHrsRunningJobStatistics` | `hom.service.ts:27-29` | `dashboard.service.ts:37-40` |
| `dashboard.json/weeklyHrRunningStatisticsDimension` | `hom.service.ts:31-33`, on a heatmap click | `dashboard.service.ts:42-45`, on a heatmap click |
| `notification.json/unreadCount` | via the shared `NotificationService` BehaviorSubject (`_services/notification.service.ts:37-38, 58-62`) | direct `HttpClient` call in the component (`dashboard.ts:154-157`) |

`DashboardService.breakdownDetail` (`dashboard.service.ts:47-51`) is **dead code** -- nothing calls
it. The only consumer of `weeklyHrRunningStatisticsDimensionDetail` in the new app is
`features/jobs/history/job-history.ts:284`, which builds the request itself.

### 2.4 The six KPI tiles

Both apps show the same six: Total jobs, Active jobs, Running now, Completed, Failed, Unread
notifications, with the last linking to `/notifications`.

Old: `home.component.html:32-75`, values from getters at `home.component.ts:154-177`. Each tile has a
glyphicon.

New: `dashboard.html:28-48`, an inline array literal in the template, values from computed signals at
`dashboard.ts:66-77`. **No icons.** The tiles are hand-rolled `<a class="card p-4 block">` even
though `shared/ui/stat-tile.ts` is the shared KPI tile used by five other screens and supports an
icon and a tone.

Total is read from the `All` bucket the endpoint appends rather than summed, in both apps
(`home.component.ts:154-156`; `dashboard.ts:66-69`, with a fallback to the sum). The new app also
strips `All` out of the ring's slices (`statusCategories`, `dashboard.ts:73-74`); the old app does
the same inside the chart builder (`home.component.ts:282`).

### 2.5 The three charts

**Job status ring.** Old: an echarts donut with a hard-coded `Active`/`Inactive`/`Delete` colour map
(`home.component.ts:234-244`). New: `shared/charts/donut.ts` with no `colorFor`, so slices take
`--chart-0..5` by position (`dashboard.html:54`).

**Last-outcome ring.** Old: an echarts pie with a `START/RUNNING/FAILED/COMPLETED` colour map
(`home.component.ts:324-329`), titled "Running jobs". New: the same donut with
`[colorFor]="outcomeColor"` wired to the shared `statusColor` (`dashboard.html:62`,
`dashboard.ts:84`), retitled "Jobs by last outcome" with a template comment explaining that the
endpoint counts *jobs by the state of their latest run*, not runs.

**Queue volume by day.** Old: a fixed seven-bar echarts bar chart, Mon→Sun, filled by
`dayOrder.map(day => data.find(el => el.name === day)?.value || 0)` (`home.component.ts:389-392`).
`find` takes the *first* match, so on a range longer than seven days every later occurrence of a
weekday is discarded. New: `shared/charts/bar-chart.ts` rendering **one bar per returned row in
server order** (`dashboard.ts:80-81`), so a 14-day range draws 14 bars whose labels read
`Mon Tue … Mon Tue …` with no date to tell them apart; the component suppresses repeated labels
(`bar-chart.ts:65, 83`).

### 2.6 The hour x weekday heatmap

Old (`home.component.ts:476-577`, template `:109-124`): an echarts heatmap, x = 24 hour labels
(`12AM`…`11PM`), y = **Monday→Sunday**, all seven rows always drawn. It marks the current moment --
an amber 3px border on the "now" cell, the current hour's axis label in amber, today's weekday label
in indigo, and Sunday's in amber as a week boundary -- with a legend in the card header explaining
each marker (`home.component.html:114-116`).

New (`shared/charts/heatmap.ts`, used at `dashboard.html:79`): a CSS grid, x = 24 hours with every
second label shown, y = **Sunday→Saturday**, and `DAY_ORDER.filter(day => byDay.has(day))`
(`heatmap.ts:97`) so **a weekday with no runs at all is dropped from the grid entirely** rather than
drawn empty. Cells are real `<button>`s with `sr-only` text (`:30-47`), disabled at zero, with a
hover readout that includes the date and a Less/More legend plus "Busiest hour: N runs"
(`:53-73`). There is **no "now" marker, no today emphasis and no week boundary** -- searching
`heatmap.ts` for `today` or `now` returns nothing.

Both collapse duplicates the same way. The server groups by `daycode, hr, date`
(`QueryService.java:319-329`), so a range longer than seven days returns several rows per
(weekday, hour). The new heatmap keys a `Map` on `day` then `hour` (`heatmap.ts:92-96`), so the last
row wins; the old one hands overlapping points to echarts, which paints the last one on top.

### 2.7 The drill-down table

Clicking a cell calls `weeklyHrRunningStatisticsDimension(targetDate, targetHr)`. The endpoint
returns one row per job plus a `UNION ALL` summary row with `job_id = NULL` and
`job_name = 'TOTAL'`, ordered `job_id ASC NULLS LAST` (`QueryService.java:330-382`).

| | Old (`home.component.html:126-221`) | New (`dashboard.html:83-237`) |
|---|---|---|
| Columns | Job ID, Job name, Queue, Start, Running, Failed, Completed, Skip, Interrupt, Missed, Total, Breakdown | Job (name + `#id`), the same eight statuses, Total, Breakdown (`dashboard.ts:18-20`) |
| TOTAL row | rendered as an ordinary row | separated into a `<tfoot>` (`isSummaryRow`, `dashboard.ts:106-107`) and **recomputed from the rows on screen** (`breakdownTotal`, `:115-124`) |
| Search | the generic `searchFilter` pipe -- token search over *every* field, with `field:value` syntax and `-negation` (`_helpers/search-filter.ts:40-102`) | substring on `jobId` and `jobName` only (`dashboard.ts:126-132`) |
| Paging | none -- every row rendered | `createPager<JobBreakdown>(50)` plus `app-pagination` (`dashboard.ts:31-39`, `dashboard.html:231-234`) |
| Zero cells | clickable; click raises a toast "No X records available to view." (`home.component.ts:625-629`) | `[disabled]` with an explanatory `title`, and `openCount` still guards with a toast (`dashboard.html:140-144`, `dashboard.ts:198-203`) |
| Mini bar colours | fixed per status from `BREAKDOWN_COLOR` (`home.component.ts:14-23`, used at `:619`) | `var(--chart-$index % 6)` -- **by position, not by status** (`dashboard.html:165, 219`) |
| Close | none; the panel stays until the next Apply | explicit `Close` button (`dashboard.html:100`) |
| Empty / loading | `No jobs match "<term>"` only (`home.component.html:210-215`) | separate loading, no-match and no-rows messages (`dashboard.html:103-108`) |

**Neither app renders a `Stop` column**, although the endpoint returns one
(`WeeklyHrJobDimensionStatisticsDto.java:21`, `QueryService.java:344`) and `total` counts it. The new
service interface even declares `stop?: number` and then omits it from `BREAKDOWN_COLUMNS`
(`dashboard.service.ts:14`, `dashboard.ts:18-20`).

### 2.8 Where a count click goes

Old (`home.component.ts:625-639`): `router.navigate(['jobList/jobHistory'], { queryParams: { jobId,
jobStatus: type, targetDate, targetHr } })`. `jobStatus` is sent even for `Total`; the service strips
it there (`hom.service.ts:43-45`). On the TOTAL row `jobId` is null, which Angular omits, so the
history screen widens to every job.

New (`dashboard.ts:198-239`): two methods. `openCount` navigates to `/jobs/:jobId/history`;
`openTotal` navigates to `/jobs/history`. Both omit `jobStatus` when the column is `Total`, with a
comment recording that passing `"Total"` through had filtered every run away. `features/jobs/history/
job-history.ts:251-302` reads `targetDate` + `targetHr` as the drill-down signal and treats a missing
`jobId` as "every job in this hour".

### 2.9 Backend

One controller, `process/src/main/java/process/api/DashboardRestApi.java`. Class-level
`@PreAuthorize("hasRole('TENANT_USER')")` (`:19`); **no method carries its own `@PreAuthorize`**, so
the class rule is the rule for all seven methods. Every method wraps its call in
`try { ... } catch (Exception ex)` and returns HTTP 500 with the fixed string
`"Some internal error occurred contact with support."` (`ProcessUtil.java:10`).

`DashboardServiceImpl` (`model/service/impl/DashboardServiceImpl.java`) does no authorisation of its
own except at `:246-247`. Every aggregation is a native SQL string built by
`QueryService` and run through `EntityManager.createNativeQuery` (`QueryService.java:42-46`).

Tenant scoping is one method, `QueryService.tenantClause` (`:212-217`):

```java
private String tenantClause(String tableAlias) {
    if (TenantContext.isPlatformAdmin() || ProcessUtil.isNull(TenantContext.getTenantId())) {
        return "";
    }
    return String.format(" and %s.tenant_id = %d ", tableAlias, TenantContext.getTenantId());
}
```

It is always applied to `source_job`, never to `job_queue` -- correctly, because `job_queue` carries
no tenant column (`model/pojo/JobQueue.java` declares `jobQueueId, startTime, endTime, skipTime,
jobStatus, jobId, jobStatusMessage, bucket, outputFolder, skipManual, runManual, dateCreated,
jobSend, status` and nothing else), so every query joins through `source_job` to reach it.

Input handling differs by endpoint, and that difference is load-bearing:

| Builder | Dates | On a malformed date |
|---|---|---|
| `jobStatusStatistics` (`:219-227`) | `dateRangeFilter` (`:166-172`) | filter silently omitted -- returns all-time |
| `jobRunningStatistics` (`:294-302`) | `dateRangeFilter` | filter silently omitted -- returns all-time |
| `weeklyRunningJobStatistics` (`:304-317`) | `requireValidDate` (`:177-182`) | throws `IllegalArgumentException` → HTTP 500 |
| `weeklyHrsRunningJobStatistics` (`:319-328`) | `requireValidDate` | throws → HTTP 500 |
| `weeklyHrRunningStatisticsDimension` (`:330-382`) | `requireValidDate` | throws → HTTP 500 |

`targetHr` and `jobId` are typed `Long` at the controller, and `jobStatus` passes a whitelist
(`sanitizeJobStatus`, `:205-210`), so nothing on these five paths is interpolated unchecked.

### 2.10 Tests

There are none for this feature, on either side.

- New frontend: `features/dashboard` has **no `.spec.ts`** -- confirmed by
  `.ai/discovery/frontend.md` §7.2 and by listing the directory (three files, none a spec).
- Old frontend: the whole of `scheduler1/src` contains **zero** `.spec.ts` files.
- Backend: `process/src/test/java/process/model/service/impl/UserStatisticsQueryTest.java` covers
  `QueryService.userStatistics` and `QueryService.runReportRows`. **None of the five dashboard SQL
  builders is covered by any test**, and `DashboardServiceImpl` has no test class.
- The only place the word "dashboard" appears in a new-app spec is
  `core/auth/auth.interceptor.spec.ts:47, 69`, where dashboard URLs are used as a fixture for the
  parallel-401 refresh test.

---

## 3. Expected behaviour

Where this differs from section 2, the difference is called out.

1. **The screen refreshes itself.** An operator leaves this page open on a wall display. The old app
   refreshed every 60 s; the new app does not refresh at all, so a dashboard opened at 09:00 still
   reads 09:00 at noon with nothing on screen saying so. *Differs from the new app today.*
2. **A range is validated before it is sent.** Both dates present, start on or before end, end not in
   the future. *Differs from the new app today -- there is no client validation and no `max` on the
   `To` field.*
3. **A range means the same thing to every panel.** A malformed or empty date should produce one
   clear refusal, not three panels silently showing all-time data beside two panels showing nothing.
   *Differs from the server today.*
4. **A failed panel says so.** Each of the five calls should leave its own panel in a stated error
   state. *Differs from the new app today: three of the five subscriptions have no `error` handler at
   all, and the fourth swallows the error silently.*
5. **The screen shows that it is loading.** *Differs from the new app today: the `loading` signal
   exists and is never rendered.*
6. **A status keeps its colour.** The breakdown mini-bar should colour a segment by what it means, as
   the old app did and as `shared/charts/status-color.ts` already provides. *Differs from the new app
   today, which colours by position.*
7. **The heatmap tells the truth over a long range.** Either every (weekday, hour) cell aggregates
   every date that falls in it, or the range is capped at what one grid can honestly show. *Differs
   from both apps today.*
8. **The heatmap orients the reader in time.** Today and the current hour should be marked. *Differs
   from the new app today; the old app had it.*
9. **Every status the endpoint counts has a column, or `total` stops counting it.** *Differs from
   both apps today -- `Stop` is counted into `total` and shown nowhere.*
10. **A tenant sees exactly its own tenant's numbers; a platform admin sees the fleet.** Met today
    for any caller that carries a tenant. A caller carrying **no** tenant should be refused, not
    unscoped. *Differs from `QueryService.tenantClause` today.*

---

## 4. Frontend requirements

### 4.1 Routes

| Route | Component | Guard | Notes |
|---|---|---|---|
| `dashboard` | `features/dashboard/dashboard.ts` `Dashboard` | `authGuard` (shell), `passwordChangeGuard` (shell) | no role restriction -- every signed-in role may open it |
| `''` (inside shell) | -- | as above | redirect to `dashboard` |

### 4.2 Components

| Component | File | Role here |
|---|---|---|
| `Dashboard` | `features/dashboard/dashboard.ts` + `.html` | the screen |
| `DashboardService` | `features/dashboard/dashboard.service.ts` | the five calls, plus the unused `breakdownDetail` |
| `Donut` | `shared/charts/donut.ts` | both rings |
| `BarChart` | `shared/charts/bar-chart.ts` | queue volume by day |
| `Heatmap` | `shared/charts/heatmap.ts` | hour x weekday grid |
| `Pagination` + `createPager` | `shared/ui/pagination.ts`, `shared/ui/pager.ts` | drill-down paging |
| `Icon` | `shared/ui/icon.ts` | `filter`, `refresh`, `search`, `close` -- all four present |
| `statusColor` | `shared/charts/status-color.ts` | outcome ring today; should also drive the mini-bar |
| `StatTile` | `shared/ui/stat-tile.ts` | **available and unused here** -- the KPI tiles are hand-rolled |

### 4.3 Forms

One form, and it is not a `FormGroup`: two native `<input type="date">` bound through `(change)` to
signals, plus Apply and Reset (`dashboard.html:11-24`). It does not use `shared/ui/field.ts`, so it
has nowhere to render a validation message today.

### 4.4 Tables

One: the drill-down. Header row, one row per job, a `<tfoot>` total. Columns are generated from
`BREAKDOWN_COLUMNS` (`dashboard.ts:18-20`), so adding `stop` is a one-line change on the front end.
Every count cell is a full-bleed `<button>` (`!p-0` on the `<td>`, padding on the button) so the whole
cell is the hit target and is keyboard-reachable.

### 4.5 Dialogs

None. The drill-down is an in-page card, not a modal -- correct, because it has to stay visible
beside the heatmap that opened it.

### 4.6 Loading, empty and error states

| Region | Loading | Empty | Error |
|---|---|---|---|
| KPI tiles | **none** | shows `0` | **none** -- indistinguishable from a real zero |
| Job status ring | none | `No data in this range.` (`donut.ts:59`) | none |
| Outcome ring | none | as above | none |
| Queue volume | none | `No runs in this range.` (`dashboard.html:67`) | none |
| Heatmap | none | `No activity in this range.` (`heatmap.ts:76`) | none |
| Drill-down | `Loading…` (`dashboard.html:104`) | `No jobs ran in this hour.` / `No jobs match your search.` (`:107`) | `toast.error` (`dashboard.ts:174, 178`) |

The route progress bar (`shared/ui/route-progress.ts`) covers *navigation* only -- the lazy chunk
load -- and is finished before any of the five XHRs return, so it is not a loading state for this
data.

Required: a busy state on each of the four data panels and on the tile row, and a per-panel error
state carrying a retry.

### 4.7 Dark and light mode

Implemented and token-based. `--chart-0..5` and `--series-*` each have a light and a dark definition
(`styles.css:1070-1075, 1089-1093` light; `:1097-1108` dark). The heatmap tints with
`color-mix(in srgb, var(--color-brand-500) …)` over `var(--surface-sunken)` (`heatmap.ts:104-109`), so
it follows the theme. The date picker indicator is inverted in dark (`styles.css:938`). The old app
has no dark mode.

### 4.8 Responsive behaviour

- Tiles: `grid-cols-2 md:grid-cols-3 xl:grid-cols-6` (`dashboard.html:28`).
- Charts: `grid lg:grid-cols-3` (`:51`).
- Date row: `flex flex-wrap items-end` with `min-w-[9.5rem] sm:flex-none` on each field, with a
  comment recording that two date fields plus the buttons need 454 px and overflowed on a phone
  (`:9-21`).
- Drill-down table: `overflow-x-auto scroll-table` (`:113`), so the wide table scrolls inside its own
  box rather than the page.
- Heatmap: 25-column CSS grid at `minmax(0, 1fr)` (`heatmap.ts:16-17`). At 375 px that is roughly
  13 px per cell -- it does not overflow, but it does not scroll either, so the squares simply get
  very small. Not verified against a device; verified only by reading the grid definition.

---

## 5. Backend requirements

### 5.1 Endpoints

All on `DashboardRestApi`, all GET, all governed by the single class-level
`@PreAuthorize("hasRole('TENANT_USER')")` at `DashboardRestApi.java:19`. With the hierarchy in
`config/MethodSecurityConfig.java:29` (`PLATFORM_ADMIN > TENANT_ADMIN > TENANT_USER`) that admits all
three roles.

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/dashboard.json/jobStatusStatistics` | TENANT_USER+ | Counts `source_job` rows by `job_status` in (`Active`,`Inactive`), plus an `All` union row. `startDate`/`endDate` optional and silently dropped if malformed. `DashboardRestApi:30-39`, SQL `QueryService:219-227` |
| GET | `/dashboard.json/jobRunningStatistics` | TENANT_USER+ | Counts `source_job` rows by `UPPER(job_running_status)` in (`START`,`RUNNING`,`FAILED`,`COMPLETED`) -- **jobs by the state of their latest run, not runs**. `:54-64`, SQL `:294-302` |
| GET | `/dashboard.json/weeklyRunningJobStatistics` | TENANT_USER+ | Run counts per calendar date, labelled with the 3-letter weekday, grouped and ordered by the date itself. Both dates **required and validated**. `:66-76`, SQL `:304-317` |
| GET | `/dashboard.json/weeklyHrsRunningJobStatistics` | TENANT_USER+ | Run counts per (weekday, hour, date) for the heatmap. Both dates required and validated. `:78-88`, SQL `:319-328` |
| GET | `/dashboard.json/weeklyHrRunningStatisticsDimension` | TENANT_USER+ | Per-job outcome counts for one exact `targetDate` + `targetHr`, plus a `UNION ALL` `TOTAL` row with a null `job_id`. `targetDate` validated, `targetHr` typed `Long`. `:90-100`, SQL `:330-382` |
| GET | `/dashboard.json/weeklyHrRunningStatisticsDimensionDetail` | TENANT_USER+ | Individual runs for a cell, optionally narrowed by `jobStatus` and `jobId`; adds the job, its task, its schedule and its lifetime stats when `jobId` is given. Owned by `job-runs-and-queue`, not by this screen. `:102-114` |
| GET | `/dashboard.json/userStatistics` | TENANT_USER+ | Per-user totals. Owned by `tenants-and-users`. `:42-52` |

### 5.2 Services

| Class | File | Responsibility |
|---|---|---|
| `DashboardService` | `model/service/DashboardService.java` | interface, seven methods |
| `DashboardServiceImpl` | `model/service/impl/DashboardServiceImpl.java` (340 lines) | maps each `Object[]` result row into its DTO; the only authorisation it performs is the ownership filter at `:246-247` |
| `QueryService` | `model/service/impl/QueryService.java` | builds every SQL string and executes it through the `EntityManager` (`:36-58`); owns `tenantClause` (`:212-217`), `dateRangeFilter` (`:166-172`), `requireValidDate` (`:177-182`), `sanitizeJobStatus` (`:205-210`) |

DTOs: `JobStatusStatisticDto` (`{name, value}`), `WeeklyJobStatisticsDto`
(`{dayCode, hr, date, count}`), `WeeklyHrJobDimensionStatisticsDto` (12 fields including `stop`),
`SourceJobQueueDto`. All are `@JsonInclude(NON_NULL)`, so a null field is absent from the JSON rather
than null.

No backend change is *required* to keep the screen working. The changes worth making are in
section 12 and section 13, and none of them alters a response shape the front end already reads.

---

## 6. Database requirements

### 6.1 Tables read

| Table | Entity | Columns this feature reads | Tenant column |
|---|---|---|---|
| `source_job` | `model/pojo/SourceJob.java` | `job_id`, `job_name`, `job_status`, `job_running_status`, `date_created`, `tenant_id`, `task_detail_id`, `assigned_user_id` | `tenant_id` (`:61-62`), indexed (`:21`) |
| `job_queue` | `model/pojo/JobQueue.java` | `job_queue_id`, `job_id`, `job_status`, `date_created`, and on the detail path `start_time`, `end_time`, `skip_time`, `job_status_message`, `run_manual`, `skip_manual`, `job_send` | **none** -- reached only by joining `source_job` |
| `scheduler` | `model/pojo/Scheduler.java` | detail path only, via `findSchedulerByJobId` | **none**, and no `@Filter` declared |

### 6.2 Indexes

`job_queue` declares exactly one index, on `job_id` (`JobQueue.java:19-21`). There is **no index on
`job_queue.date_created`** anywhere -- searching
`process/src/main/resources/db/changelog/` for an index on `date_created` returns one hit, and it is
on `notification` (`changelog-sets/V18.0-foreign-key-indexes/V18__foreign_key_indexes.sql:25`).

Every dashboard query filters with `date(jq.date_created) between …` or
`DATE(job_queue.date_created) = …` -- a function applied to the column, which cannot use a plain
b-tree index on `date_created` even if one existed. `weeklyHrRunningStatisticsDimension` additionally
filters on `EXTRACT(HOUR FROM job_queue.date_created)`.

### 6.3 Migration needed

None to make the screen work. One is worth considering and is scoped in the synthesis: a functional
index, `CREATE INDEX CONCURRENTLY … ON job_queue ((date(date_created)), job_id)`, added as a
Liquibase changeset under `db/changelog/yaml/` following the existing `Vn.0-*` convention. Schema
management is Liquibase with `ddl-auto=validate` in stage and prod
(`application-prod.properties:92, 106-108`), so a hand-run `CREATE INDEX` is not an option.

---

## 7. Validation

| Rule | Client | Server | Verdict |
|---|---|---|---|
| Both dates present | old: yes (`home.component.ts:121-124`); **new: no** | `weeklyRunningJobStatistics` / `weeklyHrsRunningJobStatistics` throw → 500; `jobStatusStatistics` / `jobRunningStatistics` silently ignore | server-enforced but as a 500, not a 400, and inconsistently across the five calls |
| `start <= end` | old: yes (`:125-128`); **new: no**, only `[max]`/`[min]` attribute hints, which browsers do not enforce on a typed value | **not enforced** -- `between '<end>' and '<start>'` simply returns nothing | **client-only in the old app, nowhere in the new one** |
| End date not in the future | old: `[max]="today_date"` (`home.component.html:14`); **new: absent** | not enforced | **client-only, and the new client dropped it** |
| Date format `yyyy-MM-dd` | native `<input type="date">` | `isValidDate` regex `\d{4}-\d{2}-\d{2}` (`QueryService.java:172-175`) | both |
| `targetHr` is an integer | comes from the heatmap, never typed | `@RequestParam … Long targetHr` (`DashboardRestApi:93`) | both |
| `jobStatus` is a known status | comes from the column key | `sanitizeJobStatus` whitelist (`QueryService:205-210`) | both |
| A zero count is not a link | old: clickable, refused with a toast (`home.component.ts:626-629`); new: `[disabled]` plus the same toast guard (`dashboard.html:140`, `dashboard.ts:199-203`) | n/a | client-only, correctly -- it is a usability rule, not a security one |

**The finding here is the second and third rows.** `start <= end` and "end is not in the future" have
never had a server-side counterpart, and the new client dropped both. The consequence is not a
security hole -- an inverted range returns an empty result -- but it is a silent one: the user sees
empty charts and is told nothing.

---

## 8. Security

Four layers, each stated separately, because they do not agree.

### Layer 1 -- frontend guard

Old: `AuthGuard` on `home` (`app.routing.ts:53-55`), which only checks `isLoggedIn()`
(`_helpers/auth.guard.ts:16-22`). No role check.

New: `authGuard` on the shell (`app.routes.ts:49`) plus `passwordChangeGuard` as
`canActivateChild` (`:52`). The `dashboard` child declares **no `minRole` and no `roleGuard`**
(`:62-65`), and the nav entry is not `adminOnly` (`shell.ts:49`).

Verdict: correct and deliberate. The dashboard is a TENANT_USER screen; there is nothing on it a
tenant user may not see. The guard's own doc comment records that `roleGuard` must sit on the route
carrying `minRole`, never on the parent, and that mounting it on the shell had previously made the
check pass for everyone (`auth.guard.ts:19-32`) -- so the absence here is an absence of a rule, not
a misplaced one.

### Layer 2 -- controller `@PreAuthorize`

`DashboardRestApi.java:19` carries `@PreAuthorize("hasRole('TENANT_USER')")` at class level. **No
method in the class carries its own `@PreAuthorize`** -- verified by reading all seven methods. Since
a method-level annotation would *replace* the class-level one rather than add to it, the absence of
method annotations is what keeps the class rule in force everywhere.

`config/MethodSecurityConfig.java:26-31` installs
`ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN > ROLE_TENANT_USER` into the method-security expression
handler, so:

| Role | Reaches the endpoints? |
|---|---|
| PLATFORM_ADMIN | yes, via the hierarchy |
| TENANT_ADMIN | yes, via the hierarchy |
| TENANT_USER | yes, directly |
| unauthenticated | no -- `.anyRequest().authenticated()` (`config/SecurityConfig.java:55`); `/dashboard.json/**` is on none of the `permitAll` lists |

`JwtAuthenticationFilter` grants exactly one authority, `ROLE_<userRole>` from the token
(`security/JwtAuthenticationFilter.java:45-46`), and clears `TenantContext` in a `finally`
(`:57`), so a thread cannot inherit a previous request's tenant.

### Layer 3 -- service rule

There is no role check in `DashboardServiceImpl`. Data scoping is entirely
`QueryService.tenantClause` (`:212-217`), applied to the `source_job` alias in all five dashboard
builders and in the detail builder.

| Caller | `tenantClause` emits | Effect |
|---|---|---|
| PLATFORM_ADMIN (tenant or none) | `""` | sees every tenant -- intended, and what the role is for |
| TENANT_ADMIN with tenant `T` | `and source_job.tenant_id = T` | sees only `T` |
| TENANT_USER with tenant `T` | `and source_job.tenant_id = T` | sees only `T` -- note the dashboard is tenant-wide, **not** narrowed to the user's own assigned jobs, in both apps |
| **any non-admin with no tenant** | `""` | **sees every tenant** |

That last row is the divergence. The codebase already has a canonical answer to it:
`security/TenantOwnership.java:35-41` refuses a caller with no tenant outright, and its class comment
(`:13-18`) states the rule -- "A context with no tenant owns nothing, so it is refused outright
rather than being compared equal to the tenant-less rows." `tenantClause` does the opposite, and
`UserStatisticsQueryTest.noTenantInContext` (`:45-50`) currently asserts the opposite behaviour as
correct.

The same divergence appears once more, in miniature, at `DashboardServiceImpl.java:246-247`:

```java
Optional<SourceJob> sourceJob = this.sourceJobRepository.findById(jobId)
    .filter(job -> TenantContext.isPlatformAdmin() || Objects.equals(job.getTenantId(), TenantContext.getTenantId()));
```

`Objects.equals(null, null)` is `true`, so a tenantless caller is the owner of any platform-owned
`source_job` row. `TenantOwnership.isOwnedByCaller(job.getTenantId())` is the same expression without
that hole, and six other services already call it (`QueryScheduleServiceImpl`,
`SourceJobServiceImpl`, `DocumentConverterServiceImpl`, `StorageConnectionServiceImpl`,
`DynamicFormServiceImpl`, `AppUserServiceImpl`).

**Reachability, honestly.** Neither precondition is reachable through the current API.
`AppUserServiceImpl.addUser:165-176` refuses to create a non-PLATFORM_ADMIN without a tenant, and
`updateUser:301-303` refuses to remove one; `SourceJobServiceImpl.addSourceJob:135-137` refuses to
create a `source_job` with no tenant. The exposure needs a legacy row, a direct database write, or a
forged token. It is still a divergence from the rule the codebase states about itself, and the fix is
a one-line substitution in each place.

### Layer 4 -- Hibernate filter

`SourceJob` declares `@FilterDef(name = "tenantFilter", …)` and
`@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")` (`SourceJob.java:28-29`).
`JobQueue` and `Scheduler` declare neither.

For this feature the filter is **irrelevant on every path**:

- Six of the seven endpoints never touch Hibernate's entity layer. They run native SQL through
  `EntityManager.createNativeQuery` (`QueryService.java:42-46`), which no `@Filter` inspects.
- The seventh, `weeklyHrRunningStatisticsDimensionDetail`, reaches `sourceJobRepository.findById`
  (`DashboardServiceImpl:246`) -- and a `@Filter` does not apply to `findById`. The explicit
  `.filter(...)` on the next line is what stands in for it, which is the right shape; only its
  null-versus-null reading is wrong.
- Had the queries been JPQL, `JobQueue` would still have been unprotected, because it declares no
  filter at all and a filter silently no-ops on an entity that never declared one.

So the tenant boundary on this feature rests entirely on layer 3, and specifically on one `String`
concatenation. That is worth knowing, and it is the reason a test at the SQL-string level -- the
shape `UserStatisticsQueryTest` already uses for `userStatistics` -- is the right test to add.

### Data disclosed

Job names, job ids, per-status run counts, and run timestamps for the caller's tenant. No
credentials, no payloads, no file contents. A TENANT_USER sees their whole tenant's jobs including
ones assigned to colleagues -- true in both apps, and consistent with the jobs list.

---

## 9. Error handling

### What the user sees today

| Failure | Old app | New app |
|---|---|---|
| Any of the four panel calls returns HTTP 500 | red toast carrying the raw `HttpErrorResponse` (`home.component.ts:226, 316, 402, 471`), and the global spinner is hidden | **nothing.** `jobRunning`, `weekly` and `hourly` have no `error` handler at all (`dashboard.ts:145-153`); the error becomes an unhandled RxJS error in the console and the panel keeps its previous, now-stale content |
| `jobStatusStatistics` fails | toast | `error: () => this.loading.set(false)` (`dashboard.ts:143`) -- silent; the tiles show `0` |
| `unreadCount` fails | the shared `NotificationService` keeps its last value | swallowed on purpose, tile shows `0` (`dashboard.ts:156`) |
| A blank date is submitted | blocked client-side with "Please select both a start and end date." | request goes out; the two `requireValidDate` endpoints 500, the other two silently return **all-time** data, and the user is told none of it |
| `start > end` is submitted | blocked client-side | request goes out; every panel returns empty and reads as "nothing happened this week" |
| Drill-down call fails | toast (`home.component.ts:588, 592`) | `toast.error(err?.error?.message \|\| 'Could not load that hour.')` (`dashboard.ts:174-179`) -- the one call in the new screen that handles its own failure |
| Session expired | interceptor refreshes once for the whole burst; on refusal, logout (`core/auth/auth.interceptor.ts:105-133`) | same |
| Empty result | `SUCCESS` with `data: []` and message `"No data found."` (`DashboardServiceImpl:54, 112, 127, 142`) -- never an error | same envelope; each chart renders its own empty message |

### What it should be

Every panel owns its own state: `idle | loading | ready | error`. On error the panel shows a short
sentence and a Retry that re-runs just that call. The tile row shows `—` rather than `0` until its
call has answered, so "no data yet" and "genuinely zero" are distinguishable. A rejected range is
refused before it is sent, with the message under the date field rather than in a toast.

The server's `IllegalArgumentException` on a bad date should surface as an HTTP 400 with the
validator's own message, not as a 500 with `"Some internal error occurred contact with support."`
-- the current handling makes a client mistake indistinguishable from a database outage in the
logs as well as on screen.

---

## 10. Dependencies

- **`authentication-and-access`** -- the route sits inside the shell behind `authGuard` and
  `passwordChangeGuard`; every call carries the bearer token the interceptor attaches; the tenant
  claim in that token is the entire basis of the scoping in section 8.
- **`source-jobs`** -- reads `source_job`. Only jobs whose `job_status` is `Active` or `Inactive` are
  counted; a deleted job disappears from every number on this screen.
- **`job-runs-and-queue`** -- every count on the drill-down links into run history, and shares the
  `weeklyHrRunningStatisticsDimensionDetail` endpoint. A change to the history screen's query
  parameters (`targetDate`, `targetHr`, `jobStatus`, `jobId`) breaks the dashboard's links.
- **`own-account-and-notifications`** -- the Unread tile calls `notification.json/unreadCount` and
  links to `/notifications`.
- **Shared chart and UI components** -- `Donut`, `BarChart`, `Heatmap`, `Pagination`, `Icon`,
  `statusColor`. Four other screens (Jobs, Queue, History, Reports) share `statusColor`, so a change
  there is not local to this feature.

---

## 11. Acceptance criteria

Each is checkable by someone who did not write the code. Fixtures are named where one is needed.

**Fixture A** -- tenant `T1` with three jobs (`J1` Active, `J2` Active, `J3` Inactive) and runs in
`job_queue` on a known date `D` at hour `14`: `J1` 3 Completed + 1 Failed, `J2` 2 Completed. Tenant
`T2` with one job `J9` and 5 Completed runs on the same date and hour.

### Access

1. A signed-out visitor who opens `/dashboard` is redirected to `/login` with
   `returnUrl=/dashboard`, and after signing in lands on `/dashboard`.
2. A signed-in TENANT_USER who opens `/dashboard` sees the screen -- no redirect to `/unauthorized`.
   (Positive control for 3 and 4.)
3. A signed-in TENANT_ADMIN sees the same screen with the same panels; nothing on it is hidden or
   added by role.
4. A signed-in PLATFORM_ADMIN sees the same screen.
5. A request to `GET /dashboard.json/jobStatusStatistics` with no `Authorization` header is refused
   with 401; the same request with a valid TENANT_USER token returns 200 and a `SUCCESS` envelope.

### Tenant scoping

6. Signed in as a TENANT_USER of `T1` on fixture A, the Total jobs tile reads `3` and the drill-down
   for `D` 14:00 lists `J1` and `J2` and **not** `J9`.
7. Signed in as a TENANT_USER of `T2` on the same fixture, the drill-down for `D` 14:00 lists `J9`
   and **not** `J1` or `J2`. (The paired positive control for 6 -- both directions, same fixture.)
8. Signed in as a PLATFORM_ADMIN on the same fixture, the drill-down for `D` 14:00 lists `J1`, `J2`
   **and** `J9`.
9. A TENANT_USER of `T1` who calls
   `GET /dashboard.json/weeklyHrRunningStatisticsDimensionDetail?targetDate=D&targetHr=14&jobId=<J9>`
   by hand receives a `SUCCESS` envelope containing **no** `sourceJob` object and an empty
   `sourceJobQueues` list; the same call with `jobId=<J1>` returns `J1`'s runs and its `sourceJob`
   block. (Refusal and positive control on one fixture.)
10. A principal whose token carries a `TENANT_USER` role and **no** `tenantId` claim receives an
    error or an empty result from `GET /dashboard.json/jobStatusStatistics` -- **not** the union of
    every tenant's jobs. A PLATFORM_ADMIN token with no `tenantId` still receives the fleet-wide
    figures. *(Fails today -- see Known issue 12.1.)*

### Date range

11. On first load the `From` field holds today minus six days and the `To` field holds today, both
    computed in the same timezone the subtitle and the heatmap use.
12. Clearing the `From` field and pressing Apply shows a validation message beside the field, and
    **no** HTTP request is sent. *(Fails today -- see 12.2.)*
13. Setting `From` later than `To` and pressing Apply shows a validation message and sends no
    request. *(Fails today -- see 12.2.)*
14. Setting `To` to tomorrow is refused by the field's own bounds. *(Fails today -- see 12.3.)*
15. A valid narrowed range -- `From` and `To` both set to `D` -- reloads all four panels, and the
    subtitle reads `Showing D to D`. (Positive control for 12--14.)
16. Pressing Reset restores the seven-day default, reloads, and closes any open drill-down.
17. `GET /dashboard.json/weeklyRunningJobStatistics?startDate=notadate&endDate=D` returns HTTP 400
    with a message naming the expected format -- not HTTP 500 and not an all-time result.
    *(Fails today -- see 12.4.)*
18. `GET /dashboard.json/jobStatusStatistics?startDate=notadate&endDate=D` behaves the same way as
    17, rather than silently returning all-time counts. *(Fails today -- see 12.4.)*

### Panels

19. On fixture A with the range covering `D`, the Total jobs tile reads `3`, Active jobs reads `2`,
    and the Job status ring shows two slices (`Active` 2, `Inactive` 1) with no `All` slice.
20. While the five calls are in flight the tile row and each chart show a busy state, and no tile
    reads `0` before its call has answered. *(Fails today -- see 12.5.)*
21. If `weeklyHrsRunningJobStatistics` returns HTTP 500, the heatmap card shows an error message and
    a Retry control; pressing Retry re-issues only that call. *(Fails today -- see 12.6.)*
22. With a range of exactly seven days ending today, the heatmap draws all seven weekday rows,
    including a weekday on which nothing ran. *(Fails today -- see 12.7.)*
23. With a range of fourteen days, the count shown in the (weekday, hour) cell equals the **sum** of
    both dates that fall in it, and the hover readout says so; it does not equal only the later
    date's count. *(Fails today -- see 12.8.)*
24. The heatmap marks today's row and the current hour's column distinctly from the others, and the
    card explains the marking. *(Fails today -- see 12.9.)*

### Drill-down

25. Clicking the `D` 14:00 cell opens a card headed `Jobs in D at 2p` listing `J1` and `J2`, with
    `J1` showing Completed 3 and Failed 1.
26. The `<tfoot>` on that card reads Completed 5, Failed 1, Total 6, and its label says `2 jobs`.
27. Typing `J1` into the drill-down search leaves one row, and the `<tfoot>` recomputes to Completed
    3, Failed 1, Total 4, `1 job`.
28. Clicking `J1`'s Failed count `1` opens `/jobs/<J1>/history` with query parameters
    `targetDate=D`, `targetHr=14`, `jobStatus=Failed`, and the page lists exactly that one run.
29. Clicking `J1`'s Total count `4` opens `/jobs/<J1>/history` with `targetDate` and `targetHr` but
    **no** `jobStatus`, and lists all four runs. (The refusal case is that no run is ever in a state
    called `Total`; the positive control is 28 on the same fixture.)
30. Clicking the footer's Total opens `/jobs/history` with `targetDate` and `targetHr` and no
    `jobId`, and lists all six runs across both jobs.
31. A count of `0` is not clickable, is visually muted, and its tooltip says why.
32. On an hour with more than 50 jobs, the drill-down pages at 50 per page and the pager reports
    `1–50 of N`; the table body scrolls inside its own box while the heatmap stays on screen.
33. On page 3 of a paged drill-down, typing a search term that reduces the result to fewer than
    three pages leaves the pager reporting a page number that exists, and the row range it reports
    matches the rows displayed. *(Fails today -- see 12.10.)*
34. A run recorded with a status the table has no column for is either given a column or excluded
    from `Total`, so the eight status columns always sum to the `Total` column.
    *(Fails today -- see 12.11.)*
35. In the drill-down mini bar, a `Failed` segment is the same colour as the `Failed` segment in
    every other row and the same colour the outcome ring uses for `Failed`, regardless of which
    other statuses that row contains. *(Fails today -- see 12.12.)*

### Refresh and consistency

36. A dashboard left open re-fetches its four panels on a fixed interval, and the page states when
    the figures were last refreshed. *(Fails today -- see 12.13.)*
37. An auto-refresh that lands while a drill-down is open leaves the drill-down open and its rows
    unchanged.
38. The Unread tile and the header bell badge report the same number for the same account at the
    same moment, including when there are more than 20 unread notifications.
    *(Fails today -- see 12.14.)*

### Theme and layout

39. Switching to dark mode leaves every chart legible: both rings, the bar chart and the heatmap all
    redraw from the dark `--chart-*` / `--series-*` tokens, and no element keeps a light-mode fill.
40. At a 375 px viewport the page does not scroll horizontally; the date row wraps, the tiles fall to
    two columns, and the drill-down table scrolls inside its own container.

---

## 12. Known issues

Each is a defect that exists today, with the evidence for it. None has been fixed here.

**12.1 A tenantless non-admin caller is unscoped rather than refused.**
`QueryService.tenantClause:212-217` returns an empty string when `TenantContext.getTenantId()` is
null, whatever the role, so every dashboard aggregation runs unfiltered for such a caller. The same
reading appears at `DashboardServiceImpl:246-247`, where `Objects.equals(null, null)` makes a
tenantless caller the owner of a platform-owned `source_job`. Both contradict
`security/TenantOwnership.java:13-18, 35-41`, which is the codebase's own stated rule and is already
used by six other services. `UserStatisticsQueryTest:45-50` asserts the current behaviour as
intended, so fixing it means changing that test too. Not reachable through the API today --
`AppUserServiceImpl:165-176` and `:301-303` both refuse a tenantless non-admin, and
`SourceJobServiceImpl:135-137` refuses a tenantless job -- so this is a latent divergence, not an
open door.

**12.2 The new dashboard has no date validation at all.**
`applyRange()` (`dashboard.ts:255`) is `{ this.load(); this.clearCell(); }`. The old app refused an
empty date and an inverted range with a toast (`home.component.ts:120-130`). Clearing the `From`
field and pressing Apply sends `startDate=` to all four endpoints: `weeklyRunningJobStatistics` and
`weeklyHrsRunningJobStatistics` hit `requireValidDate` (`QueryService:177-182`), throw, and return
HTTP 500; `jobStatusStatistics` and `jobRunningStatistics` hit `dateRangeFilter` (`:166-172`), drop
the filter, and return **all-time** counts. The user sees two panels go blank and four tiles jump to
lifetime totals, with no message anywhere -- see also 12.6.

**12.3 The `To` field lost its upper bound.**
Old: `[max]="today_date"` (`home.component.html:14`). New: `[min]="startDate()"` only
(`dashboard.html:19`). A future end date is accepted and simply returns nothing extra.

**12.4 The same bad input produces three different server behaviours.**
`dateRangeFilter` silently drops a malformed date; `requireValidDate` throws. Both live in
`QueryService`, both are reached from the same screen with the same two parameters. And the throw
surfaces as HTTP 500 with `"Some internal error occurred contact with support."`
(`DashboardRestApi:73-74`, `ProcessUtil:10`), which is the message for a database outage, so a
client mistake and an infrastructure failure are indistinguishable in the response and in the log
line above it.

**12.5 The `loading` signal is declared and never rendered.**
`dashboard.ts:56` declares it, `:137, 142, 143` set it, and `grep -n loading dashboard.html` returns
**no match**. The screen therefore has no loading state: for the duration of five parallel requests
the tiles read `0`, the rings say `No data in this range.` and the heatmap says
`No activity in this range.` The old app blocked the page with a global spinner
(`home.component.ts:206, 297, 379, 449`). `shared/ui/route-progress.ts` does not cover this -- it is
driven by router navigation events only, and finishes before the XHRs return.

**12.6 Three of the five requests have no error handler.**
`dashboard.ts:145-153`: the `jobRunning`, `weekly` and `hourly` subscriptions declare only `next`. A
non-2xx response becomes an unhandled RxJS error; the interceptor rethrows anything that is not a 401
(`auth.interceptor.ts:67-70`) and nothing catches it. The panel keeps whatever it last held. The
fourth, `jobStatus`, has `error: () => this.loading.set(false)` (`:143`) -- silent by construction.
Only the drill-down raises a toast (`:174-179`).

**12.7 A weekday with no runs is dropped from the heatmap.**
`heatmap.ts:97`: `DAY_ORDER.filter(day => byDay.has(day))`. A week in which nothing ran on Wednesday
renders six rows, so the reader has to notice an absence rather than see an empty row. The old
echarts axis was fixed at seven (`home.component.ts:517`).

**12.8 Over a range longer than seven days the heatmap silently discards data.**
The server returns one row per (weekday, hour, **date**) -- the SQL groups on all three
(`QueryService:319-328`) and the DTO carries `date` (`WeeklyJobStatisticsDto:16`). `heatmap.ts:92-96`
keys a nested `Map` on `day` then `hour`, so for a 14-day range the second occurrence overwrites the
first: the cell shows one date's count while the reader reads it as the fortnight's. The old app has
the same flaw by a different route -- overlapping echarts heatmap points, last painted wins. The
"Busiest hour: N runs" figure (`heatmap.ts:72`) is wrong for the same reason.

**12.9 The heatmap lost its "now" markers.**
`home.component.ts:483-530` marked the current cell with a 3px amber border, the current hour's axis
label in amber, today's weekday in indigo, and Sunday in amber as the week boundary, with a legend in
the card header (`home.component.html:114-116`). `heatmap.ts` contains no reference to the current
date or hour. On a grid of 168 identical squares this was the reader's only anchor.

**12.10 The drill-down pager can report a page that no longer exists.**
`createPager.slice` clamps the page it *renders* (`pager.ts:21-24`) but never writes the clamped
value back to the `page` signal, and neither `filteredBreakdown` changing nor `selectCell`
(`dashboard.ts:165-181`) calls `breakdownPager.reset()`. On page 5 of 6 (300 rows), typing a search
that leaves 120 rows renders page 3's rows while `app-pagination` reports `Page 5 of 3` and
`201–120 of 120` (`pagination.ts:18, 26, 54-55`), with `Next` still enabled.

**12.11 The `Stop` status is counted into `Total` and shown in no column.**
`QueryService:344` counts `job_status = 'STOP'` into the `stop` column, `:373` includes it in
`COUNT(*)` as `total`, and `WeeklyHrJobDimensionStatisticsDto:21` carries it. Neither frontend renders
it -- `home.component.html:141-152` and `dashboard.ts:18-20`. The eight visible columns therefore do
not sum to `Total`. In practice the discrepancy is zero, because `model/enums/JobStatus.java` declares
only `Queue, Start, Running, Failed, Completed, Skip, Interrupt, Missed` -- there is no `Stop` -- and
grepping the backend for `JobStatus.Stop` returns nothing. But `sanitizeJobStatus`
(`QueryService:201-202`) accepts `"STOP"` as a valid filter value, and `DashboardServiceImpl:218` calls
`JobStatus.valueOf(...)` on whatever the row holds, which would throw and produce a 500 if a legacy
`Stop` row existed. The three sources disagree about whether `Stop` is a status.

**12.12 The drill-down mini bar colours by position, not by status.**
`dashboard.html:165` and `:219`: `[style.background]="'var(--chart-' + $index % 6 + ')'"`, where
`$index` is the index within `segmentsFor(row)` -- a list already filtered to non-zero statuses. A row
whose only outcome is `Completed` and a row whose only outcome is `Failed` both get `--chart-0`. The
old app used a fixed per-status map (`home.component.ts:14-23`, applied at `:619`). The new app
already imports the correct helper -- `statusColor` (`dashboard.ts:13, 84`) -- and uses it for the
outcome ring but not for the bars.

**12.13 The 60-second auto-refresh was not migrated.**
`home.component.ts:34, 105-107, 147-152` refreshed all four panels every 60 s with `silent = true`,
and cleaned the timer up in `ngOnDestroy` (`:109-114`). Searching `features/dashboard` for
`setInterval` or `interval(` returns nothing. The new dashboard loads once in `ngOnInit`
(`dashboard.ts:134`) and shows nothing about how old its figures are. This is the largest single
behavioural loss in the migration of this screen. `.ai/discovery/frontend.md` §7.5 records the same
observation from the websocket side: the Queue, History and Dashboard screens all show run state and
none of them subscribes to `JobEventsService`.

**12.14 The Unread tile and the bell badge can disagree.**
The tile calls `notification.json/unreadCount` once on load (`dashboard.ts:154-157`). The bell derives
its badge from `notification.json/list?page=1&limit=20` and counts unread within that page
(`features/shell/notification-bell.ts:102, 122-124`), refreshing every 60 s (`:110`). With more than
20 unread the bell caps at 20 while the tile shows the true figure, and marking one read in the bell
(`:138-141`) does not change the tile. The old app had one `BehaviorSubject` behind both
(`_services/notification.service.ts:15, 37-38, 109-118`).

**12.15 `DashboardService.breakdownDetail` is dead code.**
`dashboard.service.ts:47-51` declares it with `ApiResponse<any[]>`; nothing calls it. The one consumer
of that endpoint, `features/jobs/history/job-history.ts:284`, builds the request itself. Its `any[]`
return is also one of the eight `any` returns `.ai/discovery/frontend.md` §7.5 flags.

**12.16 `weeklyRunningJobStatistics` returns duplicate weekday labels the client cannot tell apart.**
The SQL correctly groups and orders by the date (`QueryService:304-317`, with a comment explaining
that grouping on the name alone had merged weekdays across weeks), but the DTO returned is
`JobStatusStatisticDto{name, value}` -- **the date is dropped on the way out**
(`DashboardServiceImpl:130-134`). Over a 14-day range the client receives two rows named `Mon`. The
old app's `find` (`home.component.ts:391`) silently kept the first and discarded the rest; the new app
draws both, producing an axis reading `Mon Tue Wed … Mon Tue Wed` with no way to tell which week a bar
belongs to (`dashboard.ts:80-81`, `bar-chart.ts:65`).

**12.17 No index supports the dashboard's date filters.**
`job_queue` declares one index, on `job_id` (`JobQueue.java:19-21`), and no changeset under
`process/src/main/resources/db/changelog/` adds one on `date_created`. Every dashboard query filters
on `date(jq.date_created)` -- a function on the column, which a plain b-tree index would not serve
anyway. Four of the five panel queries scan `job_queue` on every load, and the old app did that every
60 seconds per open tab.

**12.18 A job genuinely named "Total" would vanish from the drill-down.**
`isSummaryRow` (`dashboard.ts:106-107`) returns true for `!row.jobId` **or**
`jobName.trim().toUpperCase() === 'TOTAL'`. The first clause alone is sufficient -- the summary row's
`job_id` is `NULL` by construction (`QueryService:357`) and the result is ordered `NULLS LAST`
(`:378`). The second clause is what creates the collision.

**12.19 No test covers any of this.**
`features/dashboard` has no `.spec.ts`; the old app has none anywhere; and no backend test exercises
`jobStatusStatistics`, `jobRunningStatistics`, `weeklyRunningJobStatistics`,
`weeklyHrsRunningJobStatistics`, `weeklyHrRunningStatisticsDimension` or `DashboardServiceImpl`. The
one adjacent test, `UserStatisticsQueryTest`, covers `userStatistics` and `runReportRows` and
demonstrates exactly the SQL-string assertion style these five builders need.

---

## 13. Missing functionality

Absent from both applications, in rough order of how much an operator would notice.

**No export.** There is no way to take the drill-down table or the KPI figures out of the screen. The
new `reports` feature has a server-side export (`report.json/export`), so the pattern exists; this
screen simply does not offer it. Cost: a button plus a client-side CSV of `filteredBreakdown()`, since
the rows are already in the browser -- roughly a small addition, with the caveat that CSV formula
injection has already been dealt with elsewhere in this codebase
(`features/objects/chat/csv-injection.spec.ts`, `features/jobs/assistant/csv-injection.spec.ts`) and
that handling should be reused rather than rewritten.

**No shareable state.** The date range and the selected heatmap cell live only in component signals.
An operator cannot send a colleague a link to "the 02:00 spike on the 14th"; they have to describe it.
Cost: read and write four query parameters on the route -- small, and it would also make the screen's
state survive a refresh.

**No comparison.** There is no previous-period figure beside any tile, so "14 failures" carries no
information about whether that is normal. Cost: a second call per tile-bearing endpoint over the
shifted range, or one endpoint change to return both -- medium, and it needs a product decision about
which period to compare against.

**No fleet-level view for a platform admin.** A PLATFORM_ADMIN gets the same screen with every
tenant's numbers summed together and no way to see which tenant contributed what -- `tenant_id` is
dropped from every dashboard `select` list. `userStatistics` already demonstrates the shape for a
per-principal breakdown. Cost: medium; a new SQL builder plus a grouping control that appears only for
that role.

**No drill from the two rings or the bar chart.** `BarChart` supports `[clickable]` and emits
`barClicked` (`bar-chart.ts:16, 18, 47-48`); the dashboard passes neither
(`dashboard.html:67`). Clicking a day in "Queue volume by day" ought to filter the range to that day.
Cost: small -- the component already has the input.

**No live updates.** `core/socket/job-events.service.ts` is a root singleton with exactly one
subscriber, `features/jobs/jobs.ts`. The dashboard is the screen most obviously about "what is
happening now" and it is not connected. Cost: medium; the panels would need to recompute
incrementally rather than refetch, or the socket becomes a trigger for a refetch, at which point
12.13's interval is the cheaper answer.

**No "Stop" column, and no decision about whether `Stop` exists.** See 12.11. The cheapest honest fix
is to delete `stop` from the SQL, the DTO and `sanitizeJobStatus`, so that all three agree with
`JobStatus`. That is a small change that removes a class of silent arithmetic error, but it needs
someone to confirm no historical `job_queue` row carries `'Stop'`.
