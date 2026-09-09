# Synthesis -- Dashboard

Companion to `.ai/grooming/dashboard.md`. Paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

The dashboard migrated, and the rewrite is genuinely better in the places it thought about: the
drill-down gained paging, a working search, a `<tfoot>` computed from the rows actually on screen,
disabled zero-cells, keyboard-reachable count buttons, a `Close` control, real empty states, and dark
mode. What it lost is everything that was not a control: the sixty-second auto-refresh, the date
validation, the "you are here" markers on the heatmap, per-status colouring on the breakdown bars,
and any loading or error state on four of its five requests. The pattern is consistent -- interactive
affordances survived the port, ambient ones did not -- and it means the new screen is quieter than
the old one in exactly the situations where it should be loudest: a stale figure, a bad date, a failed
request. Underneath, the backend is sound but uneven: the SQL is parameter-safe and correctly scoped
for any caller that carries a tenant, yet the same malformed date produces a silent all-time result
on two endpoints and an HTTP 500 on three, and the tenant clause reads a missing tenant as "no
filter" where the codebase's own `TenantOwnership` rule says it should mean "nothing". The work is
therefore mostly restoration plus one small server-side correctness pass, not a rebuild -- with two
genuine bugs, the heatmap's silent aggregation loss over long ranges and the pager's stale page
number, that neither app ever got right.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | New dashboard loads once in `ngOnInit` and never again (`dashboard.ts:134`); old refreshed all four panels every 60 s (`home.component.ts:34, 105-107`) | The screen keeps itself current and says how current it is | Auto-refresh dropped in the rewrite | Restore a 60 s interval that re-runs the four panel calls without touching an open drill-down; add a "last updated" line; clear the timer on destroy | S | Low |
| 2 | `applyRange()` is `load(); clearCell();` -- no validation (`dashboard.ts:255`); old refused blank and inverted ranges (`home.component.ts:120-130`) | A bad range is refused before it is sent, with the message beside the field | Client validation dropped; server never had `start <= end` | Validate in the component, render through `shared/ui/field.ts`, restore `[max]` on the `To` input | S | Low |
| 3 | Malformed date: two endpoints silently return all-time, three throw → HTTP 500 with the generic support message (`QueryService:166-172` vs `:177-182`) | One consistent refusal, as HTTP 400, naming the expected format | Two validators with opposite failure modes, and no 400 path in the controller | Make all five builders use `requireValidDate`; add an `@ExceptionHandler(IllegalArgumentException)` on `DashboardRestApi` returning 400 | M | Medium |
| 4 | `loading` is declared, set, and referenced nowhere in the template (`dashboard.ts:56`; no match in `dashboard.html`) | Each panel and the tile row show a busy state; a tile reads `—` not `0` until answered | No loading state at all on this screen | Split `loading` into four per-panel states; render skeletons | M | Low |
| 5 | Three of five subscriptions declare only `next` (`dashboard.ts:145-153`); the fourth swallows silently (`:143`) | Each panel states its own failure and offers Retry | No error handling on the panels | Give each call a `{ next, error }` pair writing a per-panel error signal; render an inline message plus Retry | M | Low |
| 6 | Heatmap keys a `Map` on `(day, hour)`; later dates overwrite earlier ones (`heatmap.ts:92-96`) | A cell's number is the sum of every date that falls in it | Silent data loss on any range over 7 days -- in **both** apps | Sum on collision in `Dashboard.heatCells`, and carry the contributing dates for the hover readout and the click | M | Medium |
| 7 | Heatmap drops weekdays with no data (`heatmap.ts:97`); has no today/now marker; starts the week on Sunday | Seven fixed rows, today and the current hour marked, as the old app did (`home.component.ts:483-530`) | Ambient orientation lost | Render `DAY_ORDER` unfiltered; add `today`/`currentHour` inputs and a legend row | S | Low |
| 8 | Mini-bar segments coloured `var(--chart-$index % 6)` (`dashboard.html:165, 219`) | A status keeps one colour everywhere | Position-based colouring; `statusColor` already imported and used for the ring only | Swap the two bindings to `statusColor(segment.key)`; extend `status-color.ts` if `stop` survives gap 11 | S | Low |
| 9 | `createPager` clamps the rendered slice but never writes back; nothing calls `reset()` (`pager.ts:21-24`, `dashboard.ts:126-181`) | The pager reports a page that exists and a row range that matches the rows shown | Stale page number after a filter or a new cell | Call `breakdownPager.reset()` when the search term changes and in `selectCell` | S | Low |
| 10 | `weeklyRunningJobStatistics` groups by date server-side but returns only `{name, value}` (`DashboardServiceImpl:130-134`) | A bar identifies its own date | The date is dropped in the DTO mapping; the old app hid it by keeping only the first match | Return `WeeklyJobStatisticsDto` with `date`; label bars by date and group-label by weekday | M | Medium |
| 11 | `Stop` is counted into `total` (`QueryService:344, 373`), carried in the DTO, rendered by neither app; `JobStatus` has no `Stop` | The visible columns sum to `Total` | Three sources disagree about whether `Stop` exists | Confirm no `job_queue` row holds `'Stop'`, then delete it from the SQL, the DTO and `sanitizeJobStatus` | S | Medium |
| 12 | `tenantClause` returns `""` for a tenantless non-admin (`QueryService:212-217`); `DashboardServiceImpl:246-247` compares null to null | A caller with no tenant owns nothing | Diverges from `security/TenantOwnership.java:13-18, 35-41`, used by six other services | Fail closed in `tenantClause`; replace the ad-hoc comparison with `TenantOwnership.isOwnedByCaller`; update `UserStatisticsQueryTest:45-50` | S | Medium |
| 13 | Defaults from `toISOString()` = UTC (`dashboard.ts:277-281`); old used `America/Chicago` (`home.component.ts:32`); the server compares in the database session's zone | One zone, stated once, used by the client and the server alike | Three different answers to "what is today" | Derive defaults in the browser's own zone; state the zone in the subtitle | S | Medium |
| 14 | Tile calls `unreadCount` once; bell counts unread within `list?limit=20` (`dashboard.ts:154`, `notification-bell.ts:102, 122-124`) | One number, one source | Two independent sources; old app shared a `BehaviorSubject` | Give the bell an `unreadCount` call and a shared signal both read | S | Low |
| 15 | KPI tiles hand-rolled with no icons (`dashboard.html:28-48`) while `shared/ui/stat-tile.ts` exists and is used by five screens | Tiles match the rest of the console and carry their icons back | Shared component not adopted here | Replace the inline array with `app-stat-tile` | S | Low |
| 16 | `DashboardService.breakdownDetail` uncalled (`dashboard.service.ts:47-51`) | No dead code | Left behind when history built its own request | Delete it, or move `job-history.ts:284`'s request onto it | S | Low |
| 17 | `isSummaryRow` also matches any job named "Total" (`dashboard.ts:106-107`) | Only the endpoint's summary row is treated as a summary | Redundant second clause | Drop the name check; `!row.jobId` is sufficient and guaranteed | S | Low |
| 18 | No index serves `date(job_queue.date_created)`; `job_queue` indexes `job_id` only (`JobQueue.java:19-21`) | The four panel queries do not scan `job_queue` per load | Missing functional index -- and gap 1 multiplies the load by the number of open tabs | Liquibase changeset adding `((date(date_created)), job_id)` | S | Medium |
| 19 | No test anywhere: no `features/dashboard` spec, no test over the five SQL builders | The tenant boundary and the aggregation shape are asserted | Untested feature whose only tenant boundary is one string concatenation | Add a `DashboardQueryTest` in the style of `UserStatisticsQueryTest`, plus a component spec | M | Low |
| 20 | Range and selected cell live only in signals | State is linkable and survives a refresh | Never built, in either app | Bind `from`, `to`, `date`, `hr` to query parameters | S | Low |

---

## 3. Solution detail

Only the rows where the *approach* was a real choice are argued here. The rest are one-line
substitutions whose alternative is "don't".

### Gaps 1 and 18 -- auto-refresh, and paying for it

**Change.** `features/dashboard/dashboard.ts`: a `setInterval` started in `ngOnInit` and cleared in
`ngOnDestroy`, calling a new `refresh()` that re-runs the four panel calls without touching
`selectedCell`, `breakdown` or `breakdownSearch`. A `lastUpdated` signal rendered beside the
subtitle. `process/src/main/resources/db/changelog/`: a new `Vn.0-*` changeset adding
`CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_job_queue_date_created ON job_queue ((date(date_created)), job_id)`.

**Why this approach.** The old app's split between `loadDashboard()` and `autoRefreshDashboard()`
(`home.component.ts:138-152`) already solved the hard part: an auto-refresh that closes the drill-down
the user is reading is worse than no auto-refresh. Copying that split is cheaper than inventing a new
one. The index belongs in the same change because the interval is what makes the missing index
expensive -- four `job_queue` scans per minute per open tab -- and shipping the refresh without it
would turn a latent performance problem into a live one.

**Rejected: drive the dashboard from the websocket instead.** `core/socket/job-events.service.ts` is
already a root singleton and already knows when a run changes state. Rejected because the dashboard's
figures are aggregates over a date range, not a list of rows: a `job.status` event tells you one run
moved, and recomputing five aggregates from it correctly means reimplementing the SQL in TypeScript.
Every place that would be wrong -- a run outside the selected range, a job in another tenant, a
status transition that changes two buckets at once -- is a place the interval is simply right. The
socket is the better answer for the *jobs list*, which is why that is the one screen subscribed to
it. Worth revisiting only if the interval's cost shows up in practice.

**Rejected: refresh only when the tab is visible.** Attractive, and `document.visibilityState` is two
lines. Not rejected on merit -- deferred, because it is an optimisation on top of a behaviour that
does not exist yet, and folding it in makes the restoration harder to verify against the old screen.

### Gaps 3 and 2 -- one meaning for a bad date

**Change.** `QueryService`: `jobStatusStatistics` and `jobRunningStatistics` switch from
`dateRangeFilter` to `requireValidDate`, keeping the "both absent means no filter" case explicit.
`DashboardRestApi`: an `@ExceptionHandler(IllegalArgumentException.class)` returning
`ResponseEntity.badRequest()` with the validator's own message. `dashboard.ts` /
`dashboard.html`: validate both dates and their order before `load()`, render the message through
`shared/ui/field.ts`, restore `[max]` on the `To` input.

**Why this approach.** Server-side first, client-side second, deliberately in that order. The client
validation is what the user actually experiences, but it is also what was silently dropped in the
migration once already -- so the server needs to hold the line whether or not the next rewrite
remembers. `requireValidDate` already exists and already throws the right thing; the only reason a
bad date is a 500 today is that `DashboardRestApi` catches `Exception` and maps everything to
`INTERNAL_ERROR_500` (`:36-38` and five siblings). A single `@ExceptionHandler` on the class fixes all
seven methods without touching any of them.

**Rejected: a `@ControllerAdvice` covering every controller.** Correct in the long run and out of
scope here: 27 controllers share the same catch-everything shape, and changing what a malformed
parameter returns across all of them is a decision about the whole API, not about this screen.
Recorded in "Out of scope".

**Rejected: enforce `start <= end` on the server too.** The client refusal is enough. An inverted
range is not an attack and not a data leak -- `between '<end>' and '<start>'` returns an empty set,
which is a truthful answer to a nonsensical question. Adding a server rule buys nothing and creates a
second place for the two to disagree.

### Gaps 4 and 5 -- four panels, four states

**Change.** Replace the single `loading` signal with a small per-panel record --
`{ status: 'loading' | 'ready' | 'error', message?: string }` for each of `jobStatus`, `jobRunning`,
`weekly`, `hourly` -- set in each subscription's `next` and `error`. Render a skeleton in the panel
while loading and an inline message with a Retry button on error. Tiles read `—` until their source
answers.

**Why per-panel rather than one page-level state.** The five calls are independent and fail
independently; the old app's global blocking spinner could not express "the heatmap failed but the
tiles are fine", and neither can a single boolean. Per-panel state is also what makes Retry
meaningful -- there is exactly one call to retry.

**Rejected: reuse `TableShell`.** `TableShell` gives 19 screens identical loading/error/empty chrome
and is the obvious candidate. Rejected because it is built around a *list*: it wraps a table, and the
four panels that need this are charts. Wrapping a donut in table chrome would mean bending the shared
component for one consumer. The drill-down table alone could use it, and that is worth doing
separately.

**Rejected: a global HTTP error toast in the interceptor.** It would fix this screen and eleven
others in one change. Rejected here because the interceptor deliberately does not do this -- several
screens swallow errors on purpose with a comment saying why (the bell:
*"A failing bell must not put an error in front of whatever the user is doing"*), and a blanket toast
would override every one of those decisions. It is an application-wide call, not a dashboard call.

### Gaps 6, 7 and 10 -- the heatmap and the bar chart tell the truth about time

**Change.** `dashboard.ts`: `heatCells` folds duplicates by summing `value` and collecting the
contributing dates instead of letting the last one win. `heatmap.ts`: render `DAY_ORDER` unfiltered so
all seven rows always appear; accept optional `today` and `currentHour` inputs and mark them; extend
the hover readout to list the dates behind a summed cell. `Dashboard.selectCell` takes a list of dates
rather than one. `DashboardServiceImpl.weeklyRunningJobStatistics` returns `WeeklyJobStatisticsDto`
carrying `date`; `bar-chart` labels by date with the weekday as the group label.

**Why summing rather than capping the range.** The alternative -- refuse a range longer than seven
days, since that is what a 7x24 grid can honestly show -- is simpler and defensible. It is rejected
because the range control is the screen's main affordance and "you may not ask that" is a poor answer
to a reasonable question; and because the server already returns exactly what is needed to sum
correctly. The cost is that a click on a summed cell now means "these three dates at 14:00", which
`weeklyHrRunningStatisticsDimension` cannot answer in one call -- it takes a single `targetDate`
(`DashboardRestApi:91`). The chosen resolution is to keep the endpoint as it is and, when a cell
covers more than one date, offer the dates rather than guessing: the drill-down opens on the one the
user picks. That keeps the server untouched and makes the ambiguity visible instead of silent, which
is the whole point of the fix.

**Rejected: change `weeklyHrRunningStatisticsDimension` to accept a date list.** Cleaner from the
client's side. Rejected because the endpoint is shared -- `features/jobs/history/job-history.ts:284`
depends on its sibling's single-date contract -- and widening a parameter to serve one caller's new
behaviour is how the `stop`-style disagreements in gap 11 started.

**Why the bar chart needs the date.** `.ai/discovery` records this as migrated and it is, but the old
app's `find` (`home.component.ts:391`) hid the problem by keeping only the first `Mon` and dropping the
rest. The new app draws every row honestly and is therefore the first version where the missing date
is visible. Adding `date` to the DTO is additive -- `@JsonInclude(NON_NULL)` means an existing consumer
that does not read it is unaffected -- and the `WeeklyJobStatisticsDto` four-argument constructor
already carrying `date` is the one `weeklyHrsRunningJobStatistics` uses (`DashboardServiceImpl:148-150`),
so the shape is already proven.

### Gap 12 -- the tenantless caller

**Change.** `QueryService.tenantClause`: return a clause that matches nothing (`and 1 = 0`) when the
caller is not a platform admin and carries no tenant, rather than an empty string.
`DashboardServiceImpl:246-247`: replace the inline comparison with
`TenantOwnership.isOwnedByCaller(job.getTenantId())`. Update `UserStatisticsQueryTest:45-50`, which
currently asserts the present behaviour.

**Why `and 1 = 0` rather than throwing.** A throw would surface as the same generic HTTP 500 as
everything else in this controller and would tell an attacker that the condition was detected. An
impossible predicate returns the same `SUCCESS` / `"No data found."` envelope a genuinely empty tenant
gets, which is both fail-closed and uninformative. It also needs no change to any calling code, and
`tenantClause` is used by more than the dashboard.

**Rejected: reject at the filter, by requiring a tenant claim for any non-PLATFORM_ADMIN token.**
Structurally the better fix -- one check in `JwtAuthenticationFilter` instead of one per query
builder. Rejected for this feature because it changes authentication for all 27 controllers, and the
one that would break first is not knowable from here. It belongs to `authentication-and-access`, and
is raised as an open question below rather than decided.

**On urgency.** This is not reachable through the current API: `AppUserServiceImpl:165-176, 301-303`
refuse to create or leave a tenantless non-admin, and `SourceJobServiceImpl:135-137` refuses a
tenantless job. It is ranked as small-and-worth-doing rather than urgent, because the cost is two
lines and a test edit, and because leaving one query builder disagreeing with `TenantOwnership` is how
the copies diverged in the first place -- which is what `TenantOwnership`'s own class comment says it
was written to stop.

### Gap 11 -- deciding whether `Stop` exists

**Change.** After confirming with a count query that no `job_queue` row holds `'Stop'`: remove the
`stop` column from `QueryService:344, 367, 393`, remove the field from
`WeeklyHrJobDimensionStatisticsDto`, remove `"STOP"` from `JOB_QUEUE_STATUSES` (`QueryService:201-202`),
and remove `stop?: number` from `dashboard.service.ts:14`.

**Why removal rather than adding the column.** Adding a ninth column to the drill-down makes the
arithmetic consistent and is a smaller diff. It is rejected because it would render a column that is
always zero, on the widest table in the console, to represent a state
`model/enums/JobStatus.java` does not define and no code path writes -- grepping the backend for
`JobStatus.Stop` returns nothing. The honest reading of the schema is that `Stop` was removed from the
enum and left behind in the SQL. Deleting it makes three sources agree; adding a column makes four
sources agree on a fiction.

**The precondition is real and must not be skipped.** If a legacy row does hold `'Stop'`, removing the
column changes historical totals, and `DashboardServiceImpl:218`'s `JobStatus.valueOf(...)` would
already be throwing on the detail path for that row. The count query settles both questions at once.

### Gap 19 -- what to test, given there is nothing

**Change.** `process/src/test/java/process/model/service/impl/DashboardQueryTest.java`, asserting the
SQL text the five builders produce: tenant clause present and naming the caller's tenant for a
TENANT_USER; absent for a PLATFORM_ADMIN; impossible for a tenantless non-admin; a malformed date not
interpolated; `job_status in ('Active','Inactive')` present so deleted jobs stay out.
`features/dashboard/dashboard.spec.ts`, covering the computed signals rather than the rendering:
`totalJobs` reads `All` and does not double-count, `isSummaryRow`, `breakdownTotal` following the
search box, `heatCells` summing duplicates, `openCount`/`openTotal` parameter shapes.

**Why SQL-string assertions rather than an integration test.** Verbatim the reasoning
`UserStatisticsQueryTest:14-16` already gives for the sibling builder: the isolation is a property of
the text, and a test that executes it would pass just as happily against a database holding one
tenant. That test is the template; following it means the two files read alike and a reviewer who
knows one knows the other.

**Why the component spec targets computed signals.** They are pure, they hold every rule that was got
wrong at least once in this document, and they need no `TestBed` rendering. `bar-chart.spec.ts` and
`status-color.spec.ts` are the precedent.

---

## 4. Ordering

**First, and independent of everything else.** Gap 12 (tenantless caller) and gap 11 (`Stop`), because
both are server-side, both are small, and both are decisions rather than construction -- gap 11 needs
the count query answered before anything else can be planned around it. Gap 18 (the index) goes here
too: it is a Liquibase changeset that blocks nothing and must be in place before gap 1 multiplies the
query load.

**Second, the server-side date contract.** Gap 3. Making all five builders validate identically and
adding the 400 handler unblocks gap 2 -- the client validation is worth much less if a request that
slips past it still returns three different things.

**Third, the client's state model.** Gaps 4 and 5 together, as one change: per-panel status, error and
retry. This is the largest single edit and it touches every subscription in `load()`, so gaps 1, 6 and
10 -- which also touch `load()` and `heatCells` -- should follow it rather than collide with it.

**Fourth, the restorations.** Gaps 1 (auto-refresh), 2 (client validation), 7 (heatmap markers and
fixed rows), 8 (status colours), 13 (timezone), 15 (`StatTile`). Each is small and independent of the
others; they can go in any order or in parallel.

**Fifth, the two real bugs neither app got right.** Gaps 6 (heatmap summing) and 10 (bar chart dates).
They come after the restorations because gap 6 changes what `selectCell` receives and gap 10 changes a
DTO, and doing either while the panels' loading and error handling is still in flight makes both
harder to review.

**Last, the tidying.** Gaps 9 (pager reset), 14 (unread count), 16 (dead `breakdownDetail`), 17
(`isSummaryRow`), 20 (query-parameter state). None blocks anything.

**Tests (gap 19) are not a phase.** The `DashboardQueryTest` cases for the tenant clause go in with
gap 12, in the same change; the signal specs go in with gaps 4/5 and 6. A test written after the fact
for code the same person just changed asserts what they remember doing.

---

## 5. Out of scope

- **Rewriting the dashboard's charts on a charting library.** The old app used echarts; the new one
  uses four hand-written components totalling under 400 lines. The hand-written ones are lighter, they
  are theme-aware through the same tokens as the rest of the console, and every gap in this document
  is a few lines inside them. Swapping libraries would rewrite the working parts to fix the broken
  ones.
- **A global `@ControllerAdvice` for `IllegalArgumentException`.** The right end state and a decision
  about all 27 controllers. This feature adds the handler on `DashboardRestApi` only.
- **Requiring a tenant claim in `JwtAuthenticationFilter`.** See gap 12's rejected option; it belongs
  to `authentication-and-access`.
- **Comparison-to-previous-period, per-tenant breakdown for a platform admin, and export.** All three
  are genuinely absent (grooming §13) and all three are new capability rather than migration. They
  need a product decision about what to compare against, how to group, and what format -- none of which
  this document can settle.
- **Connecting the dashboard to `JobEventsService`.** Argued and rejected under gap 1.
- **`userStatistics` and `weeklyHrRunningStatisticsDimensionDetail`.** They live on
  `DashboardRestApi` but belong to `tenants-and-users` and `job-runs-and-queue` respectively. Touched
  here only where gap 3 changes the shared exception handling and gap 12 changes the shared
  `tenantClause`, both of which are noted so those features' owners see them.
- **The old app.** Nothing in `scheduler1/src` is changed. It is read here as the specification for
  what the new screen is supposed to do, and it is being retired.

---

## 6. Open questions

**Q1. Does any `job_queue` row hold `'Stop'`?**
Options: (a) run `select count(*) from job_queue where upper(job_status) = 'STOP'` against production
before touching gap 11; (b) assume none, on the strength of `JobStatus` not declaring it; (c) keep the
column and add a ninth table column. **Recommendation: (a).** It is one query, it answers a question
three files currently disagree about, and it decides between deleting the field and preserving it. If
the count is non-zero, gap 11 becomes "add `Stop` to the enum and to both tables" instead, and
`DashboardServiceImpl:218` is already throwing on those rows today.

**Q2. Which timezone is "today"?**
Options: (a) the browser's own zone, so the dashboard agrees with every other date the user sees;
(b) a configured application zone, sent from the server, so every user of one deployment sees the same
figures; (c) leave it UTC. **Recommendation: (a) now, with the zone named in the subtitle.** It is the
smallest change, it is what a user expects from a date field, and it fixes the concrete defect -- a
Chicago user after 19:00 currently gets a default `To` of tomorrow. (b) is the correct answer for a
team spread across zones comparing figures with each other, but it needs a server-side setting that
does not exist and a decision about whose zone wins, and it should not hold up (a). What must not
survive is the present state, where the client says UTC, the old client said Chicago, and the database
compares in whatever zone its session holds.

**Q3. What should a heatmap cell covering several dates do when clicked?**
Options: (a) offer the contributing dates and drill into the chosen one; (b) drill into the most
recent; (c) cap the range at what the grid can show and never let the case arise.
**Recommendation: (a).** It is the only one that does not silently pick for the user, and it needs no
change to `weeklyHrRunningStatisticsDimension`. (b) is what happens today by accident -- the last row
wins -- and is exactly the behaviour that makes the bug invisible. (c) is defensible and cheaper, but
it removes a capability the range control advertises.

**Q4. Should the tenantless-caller fix land here or wait for a filter-level fix?**
Options: (a) fix `tenantClause` and `DashboardServiceImpl:246-247` now, and update
`UserStatisticsQueryTest:45-50`; (b) leave both and raise a filter-level change against
`authentication-and-access`; (c) both, in that order. **Recommendation: (c), starting with (a).** The
local fix is two lines and removes a divergence from a rule the codebase states about itself in
`TenantOwnership`'s class comment; the filter-level fix is the durable one but cannot be scoped from
inside this feature. Note explicitly that (a) requires editing a test that currently asserts the
opposite -- that is not incidental, it is the decision being made, and it should be reviewed as such.

**Q5. Is a sixty-second interval the right number?**
Options: (a) 60 s, matching the old app and the notification bell; (b) longer, say 5 minutes, given
gap 18's missing index and four `job_queue` scans per tick; (c) user-selectable, with a pause control.
**Recommendation: (a), with the index from gap 18 shipped first.** Matching the old screen makes the
restoration verifiable against something, and 60 s is already the cadence the bell runs at
(`notification-bell.ts:110`), so it is the number this application has already chosen. Revisit only
if the index does not make the scans cheap.
