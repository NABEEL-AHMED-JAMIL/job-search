# Synthesis -- Reports

Feature `reports`, row 10 of [../discovery/features.md](../discovery/features.md). Status **new**.
Grooming: [../grooming/reports.md](../grooming/reports.md).

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

Reports is new in the rewrite, so there is no parity work here and nothing to migrate. What exists is
a genuinely good screen -- a four-dimension, twelve-measure pivot over run history with cell
drill-down and three export destinations, and the one piece of it most likely to be wrong (the
arithmetic) is the one piece that has tests. The work is not to build it. The work is to finish it,
and to take one capability away from the role that should never have had it.

Three things have to happen and the rest is polish. **First, the submit destination has to become an
administrator's action with a proper guard.** As shipped, any `TENANT_USER` can make the application
server POST a file to an address they typed and read the reply back -- an outbound request primitive
that the two comparable surfaces in this same codebase both reserve for `TENANT_ADMIN`, behind a
stricter address check than the one Reports uses. **Second, the date range has to be required.**
Clearing a date input does not produce an error, it produces an unbounded scan of `job_queue` on a
predicate no index can serve, capped at fifty thousand rows only after the whole result set has been
materialised. **Third, four of the ten chart kinds have to stop drawing arithmetic they cannot
support** -- stacked, 100%-stacked, pie and donut all treat the pivot as additive, and it is additive
for exactly two of the twelve measures.

After that: replace three `window.prompt` calls with the shared dialog (which also fixes a default
bucket that is guaranteed to be refused for every non-platform role), enable a cell that has runs
behind it but measures zero, put transparency on the overlay charts, add the index, declare the
security property, put timeouts on the HTTP client, and write the three test files that do not exist.
None of that is large. All of it is the difference between a screen that demos well and one that can
be operated.

> **Brought current 2026-09-08 against the working tree.** Every one of the twenty gaps was re-read
> against current source. **Four are closed** -- 7, 10, 15, 17. **One is half done** -- 8 (area yes,
> radar no). **Four are partial** -- 5, 9, 11, 16, each with what remains stated in section 3. The
> other eleven still reproduce exactly as written, including the whole security block (1, 2, 3, 4)
> and the index (6), so the ordering in section 4 still starts where it started.
>
> **Two things about the citations below.** First, the pivot builder has moved: what was
> `reports.ts` / `reports.html` is now `report-pivot.ts` / `report-pivot.html`, and `reports.ts` is
> a dashboard host that owns the one fetch, the date range and a filter bar the builder reads
> through. Line numbers in the **Current** column are left as they were written -- they record where
> a finding was made, not where the code lives today -- and the **Status** column gives the current
> file where it differs. Second, several gaps were closed by something other than the solution the
> table proposed; the Status column says *done*, and section 3 says what actually shipped.
>
> A separate matter, and the most consequential thing this pass found: the durations this screen
> reports are not what a reader takes them for. See section 2.1.

---

## 2. The gap table

| # | Status | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|---|
| 1 | Open | Any `TENANT_USER` can POST the grid to any URL they type and read back the reply (`ReportExportServiceImpl.java:221-253`, `ReportRestApi.java:27`) | Dialling a caller-named address is `TENANT_ADMIN`, as it is for AI agents and database profiles | Outbound request primitive at the lowest role | Destination check in `export`; `auth.canSubmitReports()` gating the button; service test with a positive control | S | **High** -- security |
| 2 | Open | The submit guard checks only the five `InetAddress` predicates and permits plain http anywhere (`ReportExportServiceImpl.java:271`, `:280-288`) | The guard covers what `AiAgentServiceImpl.isInternalAddress:381-394` covers, and https unless the host is allow-listed | CGNAT, IPv6 ULA and `0.0.0.0/8` reachable; http to any public host | Extract the sibling's checks into a shared util; add `report.submit.allowed-hosts` | S | **High** -- security |
| 3 | Open | `report.submit.allow-internal` exists only as an `@Value` default (`ReportExportServiceImpl.java:67-68`) | Declared in all three profiles, asserted by `ApplicationPropertiesDeclarationTest` | An operator cannot discover the property exists | Three property lines and one list entry in the existing test | XS | Low |
| 4 | Open | `new RestTemplate()` with no timeouts (`ReportExportServiceImpl.java:58`) | 3s connect / 5s read, as `OpenSearchAuditLogClient.java:39-50` | A hostile or dead endpoint pins a request thread forever | Copy the factory builder | XS | Low |
| 5 | **Partial 2026-09-08** | Both date parameters optional; an empty one drops the filter entirely (`ReportRestApi.java:41-42`, `QueryService.java:166-171`) | Both required, `yyyy-MM-dd`, start not after end, bounded span | Unbounded scan of the largest table, reachable by clearing an input | Validator in `runRows`; guard in the template; a `MAX_SPAN_DAYS` constant | S | Medium |
| 6 | Open | `job_queue` has one index, on `job_id` (`JobQueue.java:19-21`); the predicate is `date(start_time) between …` | The range predicate is index-served | Every load is a sequential scan | New changelog set with an expression index | S | Medium |
| 7 | **Done 2026-09-08** | Stacked, 100% stacked, pie and donut divide by re-aggregated totals as though they were sums (`report-chart.ts:120`, `:161`, `:233`) | Additive-only kinds offered only for `count` and `sum` | Segments that do not sum to their bar; a donut whose centre is a sum of averages | `additiveMeasure` computed; disable the four buttons with a reason; auto-fall-back to Grouped | S | Medium |
| 8 | **Half 2026-09-08** | Area and radar paint opaque polygons per series (`report-chart.ts:46-48`, `:280-306`) | Every series is visible | A contained series is entirely hidden | `fill-opacity` on the segment path; drop the duplicated radar stroke | XS | Low |
| 9 | **Partial 2026-09-08** | A cell is disabled when its measured value is falsy (`reports.html:222`) | A cell with runs behind it is always clickable | Under a duration measure, runs that never finished are unreachable | Bind `disabled` to `cellRows[ri][ci].length === 0` | XS | Low |
| 10 | **Done 2026-09-08** | `humanSeconds(0)` returns an em dash (`pivot.ts:154`) | Em dash means no data; `0s` means zero | Two different facts render identically | Aggregate returns `null` for "no data"; formatter distinguishes | S | Medium -- touches tested code |
| 11 | **Partial 2026-09-08** | Bucket, folder and URL come from three `window.prompt` calls, defaulting to `etl-bucket` (`reports.ts:246-256`) | One `app-form-dialog` with a bucket **list**, folder, format and validated URL | Unthemed, inaccessible, unvalidatable, and the default bucket is refused for every non-platform role | New `export-dialog.ts` on the shared shell, buckets from `storage.json/buckets` | M | Low |
| 12 | Open | Save and Submit hardcode `'csv'` (`reports.html:114`, `:119`) | Any format to any destination | Implemented server capability unreachable | Falls out of gap 11 | XS | Low |
| 13 | Open | Drill drawer is a bespoke fixed panel with no Escape, no backdrop, no dialog role (`reports.html:257-297`) | Escape closes it; a backdrop tap closes it | Keyboard users are stuck in it | `@HostListener` on Escape plus a backdrop element | XS | Low |
| 14 | Open | Only the row label column and the totals row scroll away (`styles.css:329-339` sticks the header only) | Row labels stick horizontally; the All row sticks to the bottom | On a narrow screen the reader loses both anchors | Two `position: sticky` rules | XS | Low |
| 15 | **Done 2026-09-08** | A platform admin sees every tenant merged with no tenant column (`QueryService.java:213`) | A platform admin can tell the tenants apart | The one role that can see everything cannot separate it | Fifth dimension `tenant`, from a column already on `source_job` | S | Low |
| 16 | **Partial 2026-09-08** | `runRows`, `ReportRestApi`, `Reports` and `ReportChart` have no tests (`ReportExportServiceImplTest:28`, `backend.md:1061`) | Tenant isolation asserted; the screen's four states asserted | 684 untested frontend lines and the whole isolation surface | Three new test files | M | Low |
| 17 | **Done 2026-09-08** | The line/area axis flip is decided by a hyphen in the first column label (`report-chart.ts:263`) | The flip is decided by which dimension is Day | Silent axis inversion for a task called `etl-daily` | Pass the two `Dimension` objects into the chart | XS | Low |
| 18 | Open | `[shown]` and `[total]` are the same expression (`reports.html:154-155`) | The count means something or is absent | "(N of N)" on every load | Drop `[shown]`/`[total]` | XS | None |
| 19 | Open | `Integer.valueOf(String.valueOf(r[4]))` on a value whose SQL type varies by PostgreSQL major version (`ReportExportServiceImpl.java:110`) | Parse defensively | A 500 on PostgreSQL 13 or earlier | `((Number) r[4]).intValue()` | XS | Low |
| 20 | Open | No record of a successful bucket write or submit (`ReportExportServiceImpl.java:211`, `:250` log failures only) | "Who sent our run data where" is answerable | No audit trail on the two exfiltrating destinations | Deferred -- see section 5 and question Q3 | -- | -- |

---

## 2.1 What the gap table did not anticipate

Five defects found on 2026-09-08 that no row above describes. Four are drawing and fetching
mistakes; the fifth is not a defect in the ordinary sense at all, and it is the one that matters.

**The bar chart thinned its labels by bar count, with no width term.** The rule was "more than
sixteen bars, label every `ceil(n/8)`th", which is a rule about the data and not about the picture.
The same 31 bars are 14px apart in a third-of-a-row card and 45px apart at full width, so one
constant could not serve both -- at 1024px, 114 of the 350 possible bar counts produced collisions,
and the default 31-day range drew "09-06" and "09-08" 28px apart under a label that measures 30px.
That is the smeared axis a reader sees first on this screen. `shared/charts/bar-chart.ts` now
measures its own host (a `ResizeObserver`, plus a window listener for environments without one) and
derives both the label stride and whether value labels are drawn from the measured pitch in pixels
(`:128-135`, `:173-186`, `:203-226`). A second bug lived inside the old rule: it pinned the last
index unconditionally on top of its modulo grid, so index 28 and index 30 were both labelled
whatever the stride said. The stride is now anchored against the end (`:251-254`).

**`daysCovered()` measured the axis, not the days that carried runs.** It returned
`runsByDay().length`, and `runsByDay` is gap-filled to the selected range -- so it returned the
*range length* by construction. The "these runs all happened on one day" branch could therefore
never fire: 49 runs all on 2026-09-08 inside a 30-day range read as 31 days, and the caption told
the reader about gaps in a trend that did not exist. Now `activeDays()`, counting bars with a value
(`reports.ts:437-447`, used at `reports.html:217-220`).

**The 366-day cap kept the wrong end of the range.** The series walked forward from the range start
and stopped at the cap, which keeps the *oldest* days and silently drops the newest. A two-year
range therefore drew 366 empty days and reported nothing, while the tile beside it counted fifty
runs from last week. The cap is now anchored to the recent end, and says so:
`shared/charts/day-series.ts:24-41`, surfaced as `daysCapped()`.

**The runs payload was fetched twice on every visit.** The pivot builder issued its own
`GET /report.json/runs` with the same parameters the dashboard above it had just fetched. The
builder now takes the rows as an input (`report-pivot.ts:31-32`, `:49`), so a visit costs three
requests in total: the runs, the failure detail (only when there are failures to explain), and the
prior period for the comparison footnotes.

**Every duration this screen reports is 99.4% dispatcher wait.** This is the finding that reframes
what the page is for. `job_queue.start_time` is stamped at **enqueue**, not at pickup -- measured
across every run on this instance, `start_time` and `date_created` are within 10ms of each other --
so `end_time - start_time`, which is what every measure outside the new Execution group
reads, is queue wait plus execution with no way to tell them apart. On this deployment the
dispatcher polls once a minute, and the split is 41.25s of a 41.48s average, for tasks that do
0.23s of work. A screen captioned "median
duration" was therefore reporting the scheduler's poll interval and inviting every reader to
optimise a transform that was never slow.

The pickup instant *is* recorded, just not in `job_queue`: the worker writes a `Job started` audit
line, and it covers every run in this database. `QueryService.runReportRows` now left-joins that
marker and emits `exec_seconds` alongside `seconds` (`QueryService.java:265-296`), carried at row
index 8 (`pivot.ts:52-57`). Three measures read it -- Mean, Median and Longest execution, kept as
their own group rather than doubling every measure above them, because mixing the two families
in one list is how a reader ends up comparing them (`pivot.ts:137-154`). A run without the marker
reports -1 and is excluded rather than counted as instant. Both clocks are now named on screen:
on the builder (`report-pivot.ts:59-67`) and on the duration tile (`reports.ts:345-365`).

Two consequences worth stating. **The execution measures round to two decimals** where the others
round to whole seconds: the real answer down here is 0.23, and rounding it prints "0s", which reads
as no data and throws away the contrast the column exists for (`pivot.ts:193-198`,
`humanSeconds:284-286`). And **this is not, in the end, a reporting defect** -- see Q6.

**Not anticipated, and not defects.** The same pass added a Job dimension built in the browser from
a name every row already carried (`pivot.ts:94-106`), five filters that all narrow one `data()`
computed which every tile, chart, table *and* the pivot reads (`reports.ts:123-144`), runs-by-day
stacked by outcome with a click that narrows the range to that day (`reports.ts:743-757`), and the
run-log drill-through the code had previously refused on the grounds that `job_audit_logs` had no
rows -- a comment that was factually stale.

---

## 3. Solution detail

### 3.1 Gap 1 -- make `submit` a tenant-admin action

**What changes.** `ReportExportServiceImpl.export` gains a check before the destination switch at
`:177`: if the resolved destination is `submit` and
`!"TENANT_ADMIN".equals(role) && !TenantContext.isPlatformAdmin()`, return
`ResponseDto(ERROR, "Only a tenant admin can submit a report to an endpoint.")`. On the frontend,
`core/auth/auth.service.ts` gains `canSubmitReports = computed(() => this.hasAtLeast('TENANT_ADMIN'))`
alongside the eight `canManage*` computeds already there (`:87-98`), and `reports.html:118-122` wraps
the Submit button in `@if (auth.canSubmitReports())`.

**Why in the service and not the controller.** The obvious approach is a method-level
`@PreAuthorize("hasRole('TENANT_ADMIN')")` on `export`. **Rejected**, because the destination is in
the request body and `@PreAuthorize` would have to raise the bar for *all three* destinations --
download and bucket included. Downloading your own grid as a CSV is the primary use of this screen
and belongs to every role, and writing to your own tenant's bucket is already `TENANT_USER` in the
object browser (`StorageBrowserRestApi.java:36`), so raising the whole endpoint would break parity
with the object browser for no gain. Splitting `export` into two endpoints was also considered and
rejected: it duplicates validation, the CSV build and the format handling, for a distinction the
caller expresses in one field.

**Why the frontend gate is not the fix.** Stated so nobody later deletes the service check as
redundant: the button is a courtesy so a tenant user does not fill in a dialog to be refused. The
enforcement is the service, and acceptance criterion 39 in the grooming document exists to prove it
by calling the endpoint directly.

### 3.2 Gap 2 -- one address guard, shared

**What changes.** `AiAgentServiceImpl.isInternalAddress` (`:381-394`) moves to
`process/util/OutboundTargetGuard.java` unchanged, and both callers use it. `rejectUnsafeTarget`
(`ReportExportServiceImpl.java:263-293`) is rewritten in the shape of
`AiAgentServiceImpl.validateEndpoint` (`:327-359`): allow-listed host passes; otherwise https is
required; otherwise every resolved address is tested against the shared guard.
`report.submit.allow-internal` stays as the escape hatch and gains a sibling
`report.submit.allowed-hosts`, both declared per profile.

**Why extract rather than copy.** Copying the four extra range checks into `ReportExportServiceImpl`
is two lines and would work today. **Rejected** because there are now two places to keep in step, and
the codebase has already been bitten by exactly that pattern -- `reports.ts:61-68` carries a comment
explaining that this screen drew Interrupt in the wrong colour precisely because the status mapping
had been written out a second time. An address classifier is more consequential than a colour.

**What is deliberately not changed.** The TOCTOU between resolving the host in the guard and
resolving it again in `RestTemplate` is not closed. Closing it means a custom `ClientHttpRequestFactory`
that pins the resolved address, which is a real piece of work and belongs to a security pass across
every outbound caller, not to this feature. It is recorded in the grooming document (K2) and left
alone. The redirect question is different -- it is cheap to answer and cheap to fix
(`SimpleClientHttpRequestFactory.setInstanceFollowRedirects(false)`), so it goes in the same commit as
the timeouts.

### 3.3 Gaps 5 and 6 -- bound the range, then index it

> **Gap 5, partial 2026-09-08. Gap 6, untouched.** Nothing changed on the server: `ReportRestApi`
> still takes both dates as optional, `runRows` still has no validator, there is no `MAX_SPAN_DAYS`,
> and no index changeset exists. What landed is the client half, and only part of that.
> `Reports.rangeValid()` (`reports.ts:212-223`) refuses to issue the request unless both dates match
> `yyyy-mm-dd` and start is not after end; `load()` (`:600-609`) sets an error instead of fetching.
> The error card then distinguishes the two failures rather than offering one control for both: a
> request that actually failed gets "Try again", a bad range gets **"Reset to the last 30 days"**
> (`reports.html:126-141`, `reports.ts:611-616`) -- the offer to retry sent the reader round a loop
> that could never succeed. So the unbounded scan is no longer reachable *from this screen*, and is
> exactly as reachable from the endpoint as it was. **What remains:** the server-side validator, the
> span cap, and the expression index -- which is to say the whole of the reason this pair was
> ordered second.

**What changes.** `ReportRestApi.java:41-42` becomes `required = true`. `runRows` validates both
against `\d{4}-\d{2}-\d{2}`, that start is not after end, and that the span is at most
`MAX_SPAN_DAYS = 365`, returning a `ResponseDto(ERROR, …)` naming the offence in each case.
`reports.html:23-31` gains `required` and a submit guard so the client says the same thing first. A
new changelog set adds `create index idx_job_queue_start_date on job_queue ((start_time::date))`.

**Why a validator in `runRows` rather than fixing `dateRangeFilter`.** The natural instinct is to make
`QueryService.dateRangeFilter` (`:166-171`) throw instead of returning an empty string, the way
`requireValidDate` (`:177-182`) already does. **Rejected for this pass:** nine other queries call
`dateRangeFilter`, and several of them -- `jobStatusStatistics`, `jobRunningStatistics`,
`userStatistics` -- are called by the dashboard with both dates deliberately null to mean "all time".
Changing the shared helper turns a documented behaviour into an exception on five other screens. The
report is the only caller for which "all time" is unacceptable, so the report is where the rule
belongs.

**Why an expression index rather than rewriting the predicate.** The half-open rewrite
(`start_time >= :start and start_time < :endPlusOne`) is the better SQL and would let a plain btree
index serve it. **Rejected for this pass** for the same reason: it means changing `dateRangeFilter`,
which nine queries share. The expression index matches the predicate exactly, costs one changelog
set, and does not touch a line of Java. If `dateRangeFilter` is ever refactored across the board, the
expression index is dropped in the same change.

**Why 365 days.** Arbitrary but defensible: it is the longest range a person actually reads on one
screen, it is well inside the 50,000-row cap for any realistic tenant, and it makes the existing
"narrow the range" message advice rather than an epitaph. It is a constant, not a property, until
somebody asks for it to be configurable -- see Q2.

### 3.4 Gap 7 -- gate the charts on additivity

> **Done 2026-09-08, as proposed -- plus a fifth kind this table missed.** `pivot.ts:135` declares
> `ADDITIVE = {count, sum}` beside `COUNTING`, with the reasoning above written into the comment.
> The gate lives in `report-pivot.ts:96-122`: `SUMMING` names five kinds, not the four listed here
> -- **radar** belongs with them, because it sums its spokes exactly as a stacked bar sums its
> segments, and it was missed when this row was written. `kindAllowed` / `kindRefusal` disable the
> button and put the reason on it in words ("Donut adds cells together, and mean duration cannot be
> added"), `report-pivot.html:89-105` repeats it as a line in the chart header, and an `effect`
> falls back to Grouped rather than leaving a now-disabled chart on screen. `pivot.spec.ts:194-199`
> asserts the execution measures are not additive.

**What changes.** `pivot.ts` gains `export const ADDITIVE: ReadonlySet<Measure> = new Set(['count',
'sum'])` beside the existing `COUNTING` (`:47`). `Reports` gains
`additive = computed(() => ADDITIVE.has(this.measure()))`. The four additive-only buttons in
`reports.html:132-137` get `[disabled]="!additive() && isAdditiveOnly(option)"` and a `title`
explaining why -- "a stacked bar only makes sense when the parts add up to the whole". Selecting a
non-additive measure while one of those kinds is active falls back to `grouped`.

**Why gate rather than fix the maths.** The alternative is to make the stacked kinds compute their
denominator as the sum of the cells rather than the row total. **Rejected**, and this is the rejection
worth keeping: for a median, the sum of the cell medians is not a quantity. A 100%-stacked bar of
medians would then be internally consistent and still meaningless -- it would say "this task's
Completed median is 40% of the sum of its per-outcome medians", which is a sentence nobody can act
on. `pivot.ts:142` re-aggregates row totals for exactly this reason and `pivot.spec.ts:125-130`
asserts it. Making the chart agree with a number that should not exist would be undoing a correct
decision to accommodate an incorrect one.

Ranked, heat, grouped, line, area and radar are all fine for every measure -- they compare cells
against each other and never sum them -- so six of the ten kinds stay available throughout.

> **Corrected 2026-09-08: radar does not belong in that list.** It fills the polygon its spokes
> enclose, so it asserts an area, which is a sum by another name. It was moved into `SUMMING` with
> the other four, and **five of the ten kinds stay available throughout**, not six.

### 3.5 Gap 10 -- separate zero from nothing

> **Done 2026-09-08 -- but not by any of this.** Zero and nothing are now distinguishable, and the
> signature was never changed. `aggregate` still returns `number` and still returns 0 for an empty
> set, because the charts scale against a maximum and can take neither a `null` nor a negative. What
> shipped instead is three things:
>
> 1. **`humanSeconds` reads the sentinel it already had.** Negative means no data and renders an em
>    dash; **0 renders `0s`**, because a run that finished inside a second is a real run
>    (`pivot.ts:273-290`). The old `if (!value) return '—'` conflated them, so an instant run was
>    reported as "no duration recorded" and a gridline at the origin was labelled with a dash.
> 2. **Values under ten seconds keep two decimals** (`pivot.ts:284-286`, `:193-198`). This was not
>    contemplated when the row was written and the execution measures make it necessary: the honest
>    answer down there is 0.23, and rounding it to "0s" is indistinguishable from no data -- the
>    exact confusion this gap is about, reintroduced one layer down.
> 3. **The grid tells "no runs" from "runs that took no time" using something the charts do not
>    have.** `ReportPivot.cellText` (`report-pivot.ts:183-198`) consults `cellRows[ri][ci]` -- the
>    actual runs behind the cell -- and prints an em dash when there are none. The charts keep 0.
>
> The rejection recorded below still holds and is precisely why the fix sits where it does: -1 means
> "this run did not finish" at the ROW level, so it could not be reused at the aggregate level. The
> answer was to stop overloading the aggregate at all and let the one caller that knows better --
> the grid -- answer from the rows.
>
> **The predicted test risk did not materialise.** Because `aggregate` was not re-typed, the eight
> assertions expecting 0 stand as written. One assertion changed: `humanSeconds(0)`, from `'—'` to
> `'0s'`, with the reason recorded in the spec itself (`pivot.spec.ts:142-148`).

**What changes.** `aggregate` returns `number | null`, with `null` where it currently returns 0 for
"no runs carried a duration" (`pivot.ts:76`). `formatMeasure` renders `null` as an em dash and 0 as
`0s`. `humanSeconds` loses its `if (!value) return '—'` guard (`:154`) and formats 0 as `0s`. The
chart treats `null` as "no bar" rather than "a bar of height zero".

**Why change the signature rather than use a sentinel.** A sentinel (-1, matching the wire format)
would avoid touching the type. **Rejected**: -1 already means "this run did not finish" at the row
level (`pivot.ts:15`), and reusing it at the aggregate level to mean "no runs finished" is two
meanings for one value in one file. `null` is unambiguous and TypeScript will find every site that
has to handle it, which is the point.

**Why this is the riskiest small change here.** `pivot.spec.ts` has eight assertions that currently
expect 0 (`:62-67`, `:69-73`, `:140`). Every one of them has to be re-read and re-decided rather than
mechanically updated -- `aggregate([], 'count')` should stay 0, because zero runs *is* a count of
zero, while `aggregate(onlyUnfinished, 'avg')` should become `null`. That distinction is the whole
change and it lives in the test file.

### 3.6 Gap 11 -- one dialog for three prompts

> **Partial 2026-09-08 -- the prompts are gone; the bucket list is not.**
> `features/reports/report-destination-dialog.ts` replaces the three sequential `window.prompt`
> calls with one themed CDK dialog on the app's own dialog stack, in two shapes -- bucket + folder,
> or endpoint URL -- with the confirm button disabled until the input is valid and the URL checked
> against `^https?://\S+` (`:69-73`). That closes the unthemed, tab-blocking and unvalidated thirds
> of this gap, and `report-destination-dialog.spec.ts` covers it.
>
> **What remains is the half the reasoning below was actually about.** The bucket is still a
> free-text input (`:34-36`) still defaulting to **`etl-bucket`** (`:65`) -- the platform secret
> bucket, refused for every non-platform caller and, for the one caller it does not refuse, a way to
> write a report next to every tenant's Kafka key material. Nothing yet calls `storage.json/buckets`.
> Format is also absent from the dialog, so **gap 12 did not fall out of this after all**: Save and
> Submit still hardcode `'csv'` at `report-pivot.html:62` and `:68`.

**What changes.** A new `features/reports/export-dialog.ts` on `shared/ui/form-dialog.ts`, with
destination (Download / Bucket / Endpoint), format (CSV / Excel), a bucket `select` fed by
`GET storage.json/buckets`, a folder input defaulting to `reports`, and a URL input shown only for
Endpoint. `reports.ts:245-258` collapses into one `openExport()` and one `send()`.

**Why a bucket list rather than a validated text field.** `reports.ts:246` currently suggests
`etl-bucket`, which `KafkaSecretService.java:27` defines as the platform secret bucket and
`StorageBrowserServiceImpl.resolveServiceForCaller:431-437` refuses for every non-platform caller. So
the suggested default fails for the two roles most likely to use it, and succeeds for the one role
whose success writes a report next to every tenant's Kafka key material. A text field with better
placeholder text does not fix that; a list of the buckets the caller can actually reach does, and the
endpoint to populate it (`storage.json/buckets`, `TENANT_USER`) already exists and is already
tenant-narrowed by `collectBuckets(false)` (`StorageBrowserServiceImpl.java:91-113`).

**Why not reuse the object browser's bucket picker component.** Looked for; the object browser builds
its picker inline rather than as a shared component, so there is nothing to import. Extracting it is
a bigger change than writing a `select` and belongs to whoever next touches that screen.

### 3.7 Gap 15 -- a tenant dimension

> **Done 2026-09-08 -- as a name, not an id, and unconditionally.** `runReportRows` selects
> `coalesce(t.tenant_name, '(no workspace)')` through a new `left join tenant t on t.tenant_id =
> sj.tenant_id` (`QueryService.java:264`, `:292`). The alternative this section offered --
> `sj.tenant_id`, a column already on the row -- was not taken: an id is not something a reader can
> tell workspaces apart by, and the join costs one line. `ReportExportServiceImpl` interns it as a
> fifth dictionary at **row index 7** (`:117`, `:127`), and `DIMENSIONS` carries
> `{ key: 'tenant', label: 'Workspace', idx: TENANT_IDX }` (`pivot.ts:79`). It is labelled
> *Workspace* rather than *Tenant*, which is the word the rest of the console uses.
>
> **"Conditional rather than always present" was not followed in the dimension list**, and was
> honoured one level up instead. The pivot always offers Workspace, so a tenant user can pick a
> dimension with one value in it. What is conditional is the dashboard above: the Workspace
> *filter* appears only when the payload carries more than one (`reports.ts:144`), and the Overview
> caption reads "**These totals combine N workspaces** -- pick one above to separate them" only then
> (`reports.html:158-160`). That answers the same question earlier and without the reader having to
> build anything. The argument below for hiding the single-valued dimension still stands if anyone
> wants it; it is a small blemish, not a defect.

**What changes.** `runReportRows` selects `sj.tenant_id` (or a joined tenant name) as an eighth
column; `runRows` interns it into a fifth dictionary; `DIMENSIONS` gains a fifth entry, present only
when the payload carries more than one distinct tenant.

**Why conditional rather than always present.** A tenant user's report would otherwise carry a
dimension with exactly one value in it -- a column of "Acme" against everything. Showing it only when
it discriminates keeps the four-dimension screen four-dimensional for the people who are not platform
admins, which is almost everybody.

**Why a dimension rather than a filter.** A filter answers "show me tenant B"; a dimension answers
"how do the tenants compare", which is the question a platform admin actually opens this screen with.
The filter can be had for free afterwards by pivoting on tenant and reading one row.

### 3.8 Gap 16 -- the three test files

> **Partial 2026-09-08 -- a great many tests were added, and none of them is one of these three.**
> The suites now stand at **587 passing on the backend** (`mvn test`) and **580 on the frontend**
> (`npx ng test --watch=false`), with 44 test classes in
> `process/src/test/java/process/model/service/impl/` alone. None of them is `RunReportQueryTest`:
> the only Reports-adjacent classes there are still `ReportExportServiceImplTest` and the
> `UserStatisticsQueryTest` this section says to model it on. On the frontend, `features/reports/`
> holds `pivot.spec.ts` and `report-destination-dialog.spec.ts` and nothing else.
>
> So **the tenant-isolation surface remains entirely unasserted**, which was the whole point of the
> first of the three and the reason gap 15 was ordered last. Gap 15 has now landed ahead of it,
> which is the opposite of the order this document argued for.
>
> What did land nearby: `pivot.spec.ts` grew `ADDITIVE` and `humanSeconds` cases (`:142-148`,
> `:194-199`), and `shared/charts/day-series.spec.ts` and `shared/charts/bar-chart.spec.ts` now
> cover the two section-2.1 defects that live in shared code. `report-chart.spec.ts` is still
> missing, and it was supposed to be written *before* gap 8 so there was something to prove the fix
> by -- gap 8 shipped without it.

- `process/src/test/java/process/model/service/impl/RunReportQueryTest.java`, modelled line for line
  on `UserStatisticsQueryTest` (`:18-50`): assert the SQL contains `sj.tenant_id = 1004` for a tenant
  user, contains no `tenant_id =` for a platform admin, and -- the case that file does *not* cover --
  that a tenantless non-admin caller is refused rather than unscoped. The SQL is asserted as a string
  and not executed, for the reason that file gives at `:14-17`: the isolation is a property of the
  text, and a test that ran it would pass just as happily against a database with one tenant in it.
- `scheduler1/next/src/app/features/reports/reports.spec.ts`: the four states, the truncated toast,
  and the body each export button sends.
- `scheduler1/next/src/app/features/reports/report-chart.spec.ts`: geometry for the ten kinds at a
  fixed measured width, asserting that every series produces at least one visible path.

### 3.9 Gaps 8, 9 and 17 -- what landed, for the three with no section of their own

**Gap 17 -- done 2026-09-08, as proposed.** The chart is told which axis holds Day rather than
guessing. `ReportPivot.dayAxis` (`report-pivot.ts:101-103`) resolves to `'col'`, `'row'` or
`'none'` from the two `Dimension` objects and is bound as an input (`report-pivot.html:109`);
`seriesLayout` reads it (`report-chart.ts:341-353`). The hyphen test is gone, and the comment left
in its place names the case that broke it: every task in the seeded catalogue is named like
`report-history`, so putting tasks in the columns silently transposed the line chart and drew each
task as a point on a time axis. A narrowed fallback survives for `'none'` -- more columns than rows
*and* the first column label matching an ISO date -- which is a guess about data rather than about
naming, and cannot be fooled by a hyphen.

**Gap 8 -- half done 2026-09-08. Area yes, radar no.** `areaFills` now emits `opacity: 0.35`, bound
through to `fill-opacity` on the path (`report-chart.ts:397-410`, `:72`), with the failure recorded
in the comment: at full opacity each series painted over the one before it, so an area chart of N
series showed exactly one -- the last -- under a legend listing N.

**Radar was not touched.** `radarFills` (`report-chart.ts:413-424`) still paints opaque polygons,
so a contained series is still entirely hidden, and it carries a second defect this gap never
mentioned: `p.rowLabels.slice(0, 4)` caps it at **four series with no notice to the reader**. The
legend agrees with the cap (`report-pivot.ts:148` slices to 4 as well), so nothing on screen is
inconsistent -- but a five-task radar silently describes four tasks. The remedy is the same one
line of `opacity` plus the caption the ranked chart already has for exactly this
(`report-pivot.html:110-115` prints "Showing the top 8 of N rows"). Radar is also now in `SUMMING`
(see 3.4), so it is offered for Runs and Total time alone, which narrows the exposure without
closing it.

**Gap 9 -- partial 2026-09-08. The text was fixed; the binding was not.** `cellText` distinguishes
"no runs" from "no time" (see 3.5), so the *reading* of the cell is now correct. But
`report-pivot.html:196` still binds `[disabled]="!pivot().matrix[ri][ci]"` -- the falsy test this
row is about. So the two cases now render differently and behave identically: a cell with runs
behind it that measures zero prints an honest `0s` and is **still unclickable**, which is the worse
of the two states, because the reader can now see the runs are there and still cannot open them.
Under the execution measures, which are genuinely sub-second, that is a real population. The
one-line change this row proposed -- `[disabled]="!pivot().cellRows[ri][ci].length"` -- is still the
fix, and it is now plainly available: the same button reads exactly that value three lines below, at
`:199`.

---

## 4. Ordering

**First, and independently of everything else: gaps 1, 2, 3, 4.** They are one commit's worth of work,
they are the only findings with a security consequence, and none of them touches the frontend beyond
hiding one button. Doing them first means the rest of this list can be scheduled rather than rushed.
Gap 3 (declare the property) must land in the same change as gap 2, or the new allow-list property
repeats the mistake the old one made.

**Second: gaps 5 and 6, together.** The validator without the index leaves every load a sequential
scan; the index without the validator leaves the scan reachable by clearing an input. They are one
change with two artefacts. This unblocks any honest performance measurement of the screen -- until
the range is bounded there is no such thing as a representative load.

**Third: gap 11, the export dialog.** It subsumes gap 12 and fixes the `etl-bucket` default, and it
is the visible half of gap 1 -- the Submit control has to live somewhere once it is role-gated, and
that somewhere is this dialog. Doing gap 1 first and gap 11 third means Submit is briefly a hidden
button rather than a dialog option, which is fine.

**Fourth: gaps 7, 8, 9, 10, 17 -- the correctness batch.** All inside `pivot.ts`,
`report-chart.ts` and `reports.html`, all small, and gap 10 has to come last within this batch because
gaps 7 and 9 both read values that gap 10 changes the type of. Gap 16's `report-chart.spec.ts` should
be written *before* gap 8, so there is something to prove the fix by.

**Fifth: gaps 13, 14, 18 -- the polish.** Independent of everything, safe at any time, and each one
is under ten lines.

**Last: gap 15, the tenant dimension.** It is the only gap that changes the wire format, so it wants
the test files from gap 16 already in place. It is also the only one a reasonable person might decline
-- see Q1.

> **Where this stands, 2026-09-08.** The order was not followed, and the record should say so plainly
> rather than be quietly re-drawn to match what happened. **The fourth batch went first**: gaps 7,
> 8 (half), 9 (partial), 10 and 17 are the ones that landed, along with everything in section 2.1.
> **Gap 15, which was ordered last and explicitly wanted gap 16 in place first, also landed** -- and
> gap 16 did not, so the wire format changed with the isolation surface still unasserted. **The
> first batch has not started**: gaps 1, 2, 3 and 4 are exactly as written, so an outbound request
> primitive is still available to `TENANT_USER`, and that remains the first thing to do. Gaps 5 and
> 6 were meant to move together and did not: gap 5 got its client-side half, gap 6 nothing, so the
> screen is bounded and the endpoint is not.
>
> **The order that remains is the order above, unchanged.** First 1, 2, 3, 4. Then 5 (server) and 6
> together. Then the rest of 11, with 12 folded in. Then the remainders of 8 (radar), 9 (one
> binding) and 16 (three files, `RunReportQueryTest` first). Then 13, 14, 18, 19. Gap 20 stays
> deferred at Q3.

---

## 5. Out of scope

**Saved and scheduled reports.** No way to name a shape, come back to it, share it, or have it
delivered on a schedule. Deliberately not done: the query engine already has saved definitions,
schedules and execution history (`query-and-search-engines`), so building a second, weaker version of
that inside Reports would create the duplication this rewrite is trying to remove. If saved reports
are wanted, the honest answer is that a report becomes a kind of saved query, and that is a feature
decision, not a defect fix.

> **The reason above no longer exists, 2026-09-08.** The Query and Search Engines feature was
> removed whole -- `V27.0-drop-query-engine`, and there is no `QueryDefinition` entity or
> `tools/query` route left in the tree (see `../discovery/risks.md` #46). So there is nothing to
> duplicate any more, and "a report becomes a kind of saved query" now points at nothing. **This
> stays out of scope, but on a weaker footing than it had**: the argument is now simply that saved
> reports are a feature request nobody has made, not that the capability already lives elsewhere.
> Anyone picking it up should re-decide it rather than inherit a justification that has expired.

**Deep-linking the report shape into the URL.** Cheap and genuinely useful -- it would let somebody
paste "median duration by task and day, last fortnight" into a chat. Left out because it is additive
and none of the twenty gaps depends on it; it is the first thing to add once this list is done.

> **Still out of scope, and worth more than it was, 2026-09-08.** There is now more state to carry:
> five filters, the builder's open/closed state, and a range that a click on a day bar rewrites
> (`reports.ts:743-757`). None of it survives a reload or a paste, so "the runs that failed for this
> task last Tuesday" -- a view the screen can now produce in three clicks -- still cannot be sent to
> anybody.

**Merging `report-chart.ts` into `shared/charts`.** `.ai/discovery/frontend.md:804-806` records the
duplication: two chart implementations, and any change to how a chart reads has to be made in both.
That is real, and it is a cross-cutting refactor affecting the dashboard, jobs, queue, history,
profile and assistant as well as Reports. Doing it under a feature ticket would put a six-screen
regression risk inside a change whose acceptance criteria are all about pivots. It wants its own pass
with its own test plan.

> **Still out of scope, and the boundary has moved, 2026-09-08.** The dashboard half of this screen
> was built on `shared/charts` -- `BarChart`, `Donut`, `Histogram`, `daySeries` and `statusColor`
> (`reports.ts:7-11`) -- so the two implementations now sit inside one feature folder rather than in
> two features. That is an argument for the merge, not against it: the label-thinning defect in
> section 2.1 was fixed once in `shared/charts/bar-chart.ts` and reaches all five screens that draw
> one -- dashboard, jobs, job history, queue and this one -- while `report-chart.ts` still lays out
> its own axis and was not fixed by it. The refactor is unchanged in size and still wants its own
> pass.

**Closing the DNS TOCTOU on outbound calls.** See 3.2. Belongs to a security pass across every
outbound caller, not to this feature.

**Refactoring `QueryService.dateRangeFilter`.** See 3.3. Nine callers, several of which depend on the
current "null means all time" behaviour.

**Escape/focus handling for dialogs generally.** The drill drawer gets an Escape handler (gap 13)
because it is this feature's overlay. The observation that `shared/ui/form-dialog.ts` has no Escape
handling either, and therefore neither do the sixteen dialogs built on it, is recorded in the grooming
document (K16) and left for a shared-component pass.

**An audit trail for export (gap 20).** Recorded, not solved here. See Q3.

---

## 6. Open questions

**Q1 -- should a platform admin see a merged, unlabelled report at all? -- SETTLED 2026-09-08**

Today `tenantClause` (`QueryService.java:213`) returns an empty string for a platform admin, so the
report merges every tenant's runs with nothing distinguishing them. Three options: (a) leave it,
consistent with the dashboard; (b) add `tenant` as a conditional fifth dimension (gap 15); (c) require
a platform admin to pick a tenant before the screen loads anything.

**Recommendation: (b).** (a) leaves the one role that can see everything unable to tell what it is
looking at, which is worse than not showing it. (c) is safest but makes the platform admin's Reports
strictly less capable than a tenant admin's, and cross-tenant comparison is a legitimate thing for
that role to want. (b) costs one `select` item, one dictionary and one conditional `DIMENSIONS` entry,
and it turns the merge from a confusion into the feature.

> **Settled as (b), 2026-09-08.** Shipped as gap 15 -- see 3.7 for what actually landed and where it
> deviates (a joined tenant *name* rather than the id, and an unconditional entry in `DIMENSIONS`
> with the conditionality moved up to the filter and the caption). The merged view is no longer
> silent about being merged: a platform admin is told "These totals combine N workspaces" above the
> figures. Nothing about (c) was adopted and it is not being kept open.

**Q2 -- what is the maximum range, and is it configurable?**

Section 3.3 proposes a hard-coded 365 days. The alternatives are no maximum (relying on the 50,000-row
cap alone) or a property.

**Recommendation: hard-code 365, revisit only when somebody asks.** The 50,000-row cap is not a
substitute -- it truncates *after* the database has produced the whole result set, so it bounds the
payload and not the query. A property invites a deployment to set it to 3,650 and reintroduce the
problem, and `ApplicationPropertiesDeclarationTest` would then have to carry it. A constant is honest
about the fact that this is a screen, not a data warehouse, and the existing "narrow the range"
message already tells the user what to do.

> **Still open, 2026-09-08, and one thing must not be mistaken for the answer.** The client-side
> guard that landed with gap 5 checks *format* and *order*, not span, so a hundred-year range is
> still a valid request. And `MAX_DAYS = 366` in `shared/charts/day-series.ts` is **not** this
> maximum: it caps the number of bars drawn, in the browser, after the whole result set has arrived.
> It bounds the picture, exactly as the 50,000-row cap bounds the payload, and neither bounds the
> query. `MAX_SPAN_DAYS` is still unwritten. Note the two numbers differ by one -- 365 proposed here
> against 366 shipped there -- and should be reconciled to one constant if the server-side cap is
> ever added, or a range that is legal will draw an axis that is capped.

**Q3 -- does exporting need an audit trail, and whose is it?**

A successful bucket write and a successful submit currently leave no record at all; only failures are
logged (`ReportExportServiceImpl.java:211`, `:250`). Once gap 1 lands, submit is at least a
tenant-admin action, which narrows the population. Options: (a) nothing; (b) an info-level log line on
success in this service; (c) a real record -- a notification, or a row in a new action log.

**Recommendation: (b) now, and raise (c) as a cross-cutting question.** A log line is two lines of
code and makes "who sent our run data where" answerable by somebody with log access, which is the
realistic need. (c) is the right long-term answer and Reports is the wrong place to invent it: the
same question applies to the object browser's file share, the query engine's bucket writes and the
document converter, and a scheme invented for one of them will not fit the others. Raise it as a
platform item with Reports named as one of four consumers.

> **Still open, and one of the four is gone, 2026-09-08.** The query engine was removed
> (`V27.0-drop-query-engine`), so the cross-cutting question now has three consumers, not four:
> the object browser's file share, the document converter, and Reports. The recommendation is
> unchanged and (b) has not been done -- `ReportExportServiceImpl` still logs failures only.

**Q4 -- should `report.submit.allowed-hosts` default to empty, or to the same
`host.docker.internal` that `ai.allowed-endpoint-hosts` defaults to (`AiAgentServiceImpl.java:82`)?**

**Recommendation: empty.** The AI default exists so a developer's local Ollama works out of the box,
which is a real convenience for a feature whose whole point is calling a model. Reports has no
equivalent -- there is no endpoint a fresh install is expected to submit to -- so an empty default
means the feature ships closed and an operator opts in deliberately. That is also what
`ApplicationPropertiesDeclarationTest:15-25` is arguing for in general.

**Q5 -- with `submit` restricted to `TENANT_ADMIN`, is the destination worth keeping at all?**

It is the least-used destination, it carries the most risk, and no screen or document in the repo
names a system that consumes it. The alternative is to delete it and keep download and bucket.

**Recommendation: keep it, gated.** The class javadoc at `ReportExportServiceImpl.java:17-20` gives a
coherent reason for the whole service to be server-side -- two of three destinations are only
reachable from the server -- and removing one of those two makes the remaining architecture look
arbitrary. It is also the only way to get a report out of the deployment to a system that is not a
bucket, which is a normal integration need. But this is worth putting to whoever asked for it: if
nobody can name the endpoint it was built for, deleting it removes gaps 1, 2, 3 and 4 in one stroke,
and that is a genuinely attractive trade.

**Q6 -- whose problem is the 41 seconds: the report's, or the dispatcher's? (new 2026-09-08)**

Section 2.1 records the measurement: on this deployment a run averages 41.48s end to end, of which
41.25s -- **99.4%** -- is waiting for a dispatcher that polls once a minute, for tasks that do 0.23s
of work. Reports has answered this the only way a reporting screen honestly can: by separating the
two clocks, naming both on screen, and adding three Execution measures that read the `Job started`
audit marker (see 2.1).

But that fix makes the screen truthful, not the system fast, and it leaves a question this document
cannot settle on its own. Three things could be meant by "fix it": (a) nothing further -- the report
now says what it measures, and a once-a-minute dispatcher is a deliberate design nobody has
complained about; (b) `job_queue` stamps `start_time` at enqueue and never resets it at pickup, so
every duration in this system -- not only this screen's -- conflates wait with work; a pickup
timestamp on the row would remove the left join and fix the dashboard, the queue screen and the job
history at the same time; (c) the poll interval itself is the finding, and the report is merely the
first place it became visible.

**No recommendation, deliberately.** (b) is a schema change with callers well outside this feature,
and (c) is a capacity decision, not a defect. What Reports can assert is the evidence: the `Job
started` marker exists for every run in this database, the 99.4% figure is measured rather than
estimated, and **Reports is not the only screen affected** -- `queue.ts:194` and
`job-history.ts:191` each compute `endTime - startTime` from the same rows, in the browser, with no
equivalent of the Execution measures and no caption saying what they are measuring. Whatever is
decided, it is not a Reports decision. It belongs in front of whoever owns the engine, with Reports
named only as the place it became visible.
