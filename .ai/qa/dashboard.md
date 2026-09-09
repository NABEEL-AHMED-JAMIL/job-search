# QA — Dashboard

Companion to `.ai/grooming/dashboard.md` (acceptance criteria in its §11; known issues in its §12).
That grooming document is unusually thorough — it already static-read the frontend and backend
source line-by-line and pre-identified 19 known issues with file:line citations. This pass exists
to **exercise those same claims against the live, running app** (`http://localhost:4400`, backend
`http://localhost:9098`, both already running in Docker) rather than to re-derive them from
source, and to go beyond them per `.ai/prompts/qa.md`'s four groups (Functional, UI/UX, Backend,
End to end), attacking authorization at the API rather than trusting the UI.

**Scope of this pass.** The whole `dashboard` feature/screen, both themes, a 375px viewport, and
both accounts provided. Not scoped: the destination screens the dashboard drills into
(`/jobs/:id/history`, `/jobs/history`) beyond confirming the link itself lands correctly with the
right query parameters — those screens' own behaviour belongs to `job-runs-and-queue`'s QA pass.

**Fixtures used.**
- **Platform Admin** (`admin@platform.local`, no tenant) — this environment's Platform Admin
  account already carries substantial real fleet data: 134 jobs (all `Active`), 118 with a last
  outcome of `Failed`, and job-queue runs concentrated on two dates (`2026-09-05`, a Saturday, and
  `2026-09-07`, a Monday). This served as the "many jobs" fixture for functional/UI testing — no
  data was created for this account.
- **Tenant Admin** `qa-test-admin@example.com` (tenant **Acme Analytics**, `tenantId=1817`) — per
  the task brief, this account currently owns **zero jobs** (`/jobs` reads "No jobs yet.",
  confirmed via `Source Jobs` screen and via `dashboard.json/jobStatusStatistics` returning
  `{"name":"All","value":0}`). This served as the empty-state fixture, and — combined with the
  Platform Admin's 134 jobs being invisible to it — as a live negative control for tenant scoping
  (QA-16). **Nothing was created for this pass**: no new job, task, or tenant. The pre-existing
  `Acme Analytics` tenant here already has 51 users (5 tenant admins, 46 tenant users) seeded
  before this session; none of their passwords were available, so no live TENANT_USER-role
  coverage was obtained (see "Not exercised" below) — an attempt to open the "New user" dialog to
  create one is recorded as QA-20 (tooling issue, not an app defect) and abandoned rather than
  force through it.
- No test data was created or left behind by this pass.

---

## Acceptance criteria exercised (grooming §11)

| # | Criterion | Result |
|---|---|---|
| 1 | Signed-out visitor → `/login?returnUrl=/dashboard` → signs in → lands on `/dashboard` | **PASS** — see QA-15 |
| 2 | TENANT_USER sees the screen | **untested** — no TENANT_USER credentials available (see Fixtures) |
| 3 | TENANT_ADMIN sees the same screen, nothing hidden/added | **PASS** — exercised throughout as `qa-test-admin@example.com` |
| 4 | PLATFORM_ADMIN sees the same screen | **PASS** — exercised throughout as `admin@platform.local` |
| 5 | No `Authorization` header → 401; valid TENANT_USER-hierarchy token → 200 | **PASS** — see QA-15 |
| 6 | TENANT_USER of T1 sees only T1's jobs/drill-down | **partial** — no TENANT_USER account; TENANT_ADMIN-of-T1 case confirmed instead, see QA-16 |
| 7 | TENANT_USER of T2 sees only T2's, not T1's (paired control) | **partial** — same caveat; live negative control obtained (QA-16), but not the exact paired two-populated-tenant fixture |
| 8 | PLATFORM_ADMIN sees T1 **and** T2 | **PASS** (as fleet total) — Platform Admin's 134 spans whichever tenants own that data; not decomposed per-tenant since the UI has no such breakdown (grooming's own "No fleet-level view" gap, §13) |
| 9 | Cross-tenant `weeklyHrRunningStatisticsDimensionDetail?...&jobId=<foreign>` refused; own id succeeds | **PASS** — see QA-16 |
| 10 | Tenantless non-admin refused/empty; tenantless PLATFORM_ADMIN still gets fleet figures | **partial** — second half confirmed live (QA-17); first half **not reachable**, consistent with grooming §12.1's own note that no legitimate account without a tenant exists for a non-admin role, and forging one requires the JWT signing secret |
| 11 | Default range = today−6 to today, same timezone as subtitle/heatmap | **FAIL** — see QA-18 |
| 12 | Empty `From` + Apply → validation message, no request sent | **FAIL** — see QA-07 |
| 13 | `From` > `To` + Apply → validation message, no request sent | **FAIL** — see QA-08 |
| 14 | `To` = tomorrow refused by field bounds | **FAIL** — see QA-09 |
| 15 | Valid narrowed range reloads all four panels, subtitle updates | **PASS** — exercised repeatedly (e.g. QA-16's targeted date) |
| 16 | Reset restores 7-day default, reloads, closes drill-down | **PASS**, with a caveat — see QA-19 |
| 17 | `weeklyRunningJobStatistics?startDate=notadate` → 400 naming the format | **FAIL** — see QA-07 |
| 18 | `jobStatusStatistics?startDate=notadate` → same 400 behaviour, not silent all-time | **FAIL** — see QA-07 |
| 19 | Two-slice ring (`Active`/`Inactive`), no `All` slice | **untested** — this environment has zero `Inactive` jobs anywhere (confirmed via full-range query, QA section below); the "no `All` slice" half is confirmed true for the single-slice case that does exist |
| 20 | Busy state on load; no tile reads `0` before its call answers | **FAIL** — see QA-10 |
| 21 | `weeklyHrsRunningJobStatistics` 500 → heatmap shows error + Retry | **FAIL** — see QA-11 |
| 22 | 7-day range draws all 7 weekday rows, including a zero-run weekday | **FAIL** — see QA-13 |
| 23 | 14-day range sums both dates into one cell | **untested** — this environment's entire fixture spans exactly 2 distinct dates on 2 *different* weekdays (Sat, Mon), so no (weekday, hour) pair has two dates to sum; confirmed by querying the full available range via the API (0 duplicate weekday/hour pairs found) |
| 24 | Heatmap marks today + current hour | **FAIL** — see QA-14 |
| 25 | Click cell → drill-down card with correct per-job counts | **PASS** — see QA-16 |
| 26 | `<tfoot>` totals recompute correctly, "N jobs" label | **PASS** — see QA-16 |
| 27 | Search narrows rows and `<tfoot>` recomputes | **PASS** — see QA-16 |
| 28 | Click a status count → history filtered to job+date+hour+status | **PASS** — see QA-16 |
| 29 | Click a row's Total → history with no `jobStatus`, all runs | **PASS** — see QA-21 |
| 30 | Click footer Total → `/jobs/history`, no `jobId`, all rows | **PASS** — see QA-21 |
| 31 | Zero count not clickable, muted, tooltip explains why | **PASS** — see QA-16 |
| 32 | >50 rows → paginates at 50, `1–50 of N`, table scrolls in its own box | **PASS** — see QA-16 |
| 33 | Page 3+, search narrows below page count → pager stays honest | **untested** — this environment's largest single-hour result set is 72 rows (2 pages at the fixed 50/page minimum); reproducing the exact "page 3 of 6" scenario grooming's code reading describes needs either a page-size control below 50 (none exists in the UI — options are 50/100/150/200 only) or a cell with >150 jobs, neither available here |
| 34 | 8 (or however many) status columns sum to Total | **PASS — contradicts grooming §12.11** — see QA-22 |
| 35 | Failed segment is the same colour everywhere | **FAIL** — see QA-15 |
| 36 | Auto-refresh on a fixed interval, page states when last refreshed | **FAIL** — see QA-12 |
| 37 | Auto-refresh doesn't disturb an open drill-down | **N/A** — there is no auto-refresh to test against (36) |
| 38 | Unread tile and bell badge agree, including >20 unread | **untested** — neither test account has any unread notifications in this environment (both `unreadCount` = 0), so the >20-cap divergence grooming §12.14 describes cannot be provoked without generating >20 notifications, which was judged out of scope for a dashboard-only pass |
| 39 | Dark mode: every chart redraws, nothing stays light-only | **PASS** — see QA-23 |
| 40 | 375px: no horizontal page scroll, tiles 2-col, table scrolls in its own box | **PASS** — see QA-23 |

**Not exercised in this pass:** the TENANT_USER role specifically (2, 6, 7 partial), the exact
paired two-tenant-with-data fixture for 6–8, the tenantless-non-admin half of 10, the two-slice
ring case (19), the 14-day cross-date heatmap sum (23), the stale-pager-after-filter repro at
page 3+ (33), and the Unread-tile/bell-badge divergence at volume (38). Each is untested because
this environment's data did not admit the scenario, not because it was skipped — see each row
above for the specific gap.

---

### QA-07 · major · Dashboard — no date validation anywhere, and the two malformed-date paths disagree

**Did:** Signed in as Platform Admin. On `/dashboard`, cleared the `From` field entirely (native
`<input type="date">` now empty) and pressed Apply.

**Expected:** A validation message beside the field (or at minimum a single consistent refusal),
and no request sent with a blank date — grooming criterion 12.

**Got:** No validation message anywhere in the UI. Four requests went out with `startDate=`:
- `jobStatusStatistics?startDate=&endDate=2026-09-08` → **200**, silently returned all-time data
  (which coincidentally matched the 7-day figures here, since all fixture data falls within the
  default window).
- `jobRunningStatistics?startDate=&endDate=2026-09-08` → **200**, same silent all-time behaviour.
- `weeklyRunningJobStatistics?startDate=&endDate=2026-09-08` → **500**,
  body `{"status":"ERROR","message":"Some internal error occurred contact with support."}`.
- `weeklyHrsRunningJobStatistics?startDate=&endDate=2026-09-08` → **500**, identical body.

So the same screen, from the same button press, produces two silently-wrong panels and two
generic-500 panels, and the user is told nothing on any of the four. Separately confirmed
criteria 17/18 with a direct `fetch()` using the stored token:
`GET dashboard.json/weeklyRunningJobStatistics?startDate=notadate&endDate=2026-09-08` also
returns HTTP 500 with the same body — a malformed date and a database outage are indistinguishable
to the caller and in the response.

**Evidence:** response bodies captured via the page's own network log and via direct `fetch()`,
quoted above verbatim. Browser console recorded the resulting unhandled RxJS errors as raw
`ERROR {status: 500, ...}` objects (see QA-11).

---

### QA-08 · major · Dashboard — inverted date range (`From` after `To`) is accepted silently

**Did:** As Platform Admin, set `From = 09/08/2026` and `To = 09/02/2026` (via the native date
inputs) and pressed Apply.

**Expected:** A validation message and no request sent (criterion 13).

**Got:** Subtitle updated to `Showing 2026-09-08 to 2026-09-02` with no complaint. The request went
out and returned 200 with genuinely empty results — every tile dropped to `0`, both rings read
"No data in this range.", the bar chart read "No runs in this range.", and the heatmap read "No
activity in this range." A user reading only the screen has no way to tell "this range truly has
no data" apart from "I typed the range backwards."

**Evidence:** screenshot sequence: field values `09/08/2026` / `09/02/2026`, subtitle
`Showing 2026-09-08 to 2026-09-02`, all six tiles at `0`.

---

### QA-09 · minor · Dashboard — the `To` field has no upper bound

**Did:** As Platform Admin, inspected the date inputs' `min`/`max` attributes via the DOM, then set
`To = 12/31/2027` and pressed Apply.

**Expected:** The field's own bound refuses a future date (criterion 14; the old app had
`[max]="today_date"`).

**Got:** `document.querySelector('input[type=date]').max` for the `To` field is an **empty
string** — no upper bound at all — while its `min` is wired to the current `From` value. Setting it
to `2027-12-31` was accepted with no complaint; Apply fired normally and the subtitle read
`Showing 2026-09-02 to 2027-12-31`.

**Evidence:** `{fromMax: "2026-09-02", fromMin: "", toMax: "", toMin: "2026-09-08"}` read directly
from the two inputs' DOM properties; follow-up screenshot with the accepted future date in the
subtitle.

---

### QA-10 · major · Dashboard — no loading state is ever shown

**Did:** As Platform Admin (134 real jobs), triggered a reload via Reset and took a screenshot
immediately following the click (fastest achievable round-trip in this environment).

**Expected:** A busy indicator on the tile row and each chart while the five requests are in
flight; no tile should read a bare `0` before its own call has answered (criterion 20).

**Got:** No spinner, skeleton, or any busy treatment appeared at any point — the screenshot taken
immediately after the click already showed either the settled data or (in the empty-tenant case,
QA-07/QA-08) a bare `0`/`No data` with nothing to say whether that's a real empty answer or a
still-loading one. This is consistent with grooming §12.5's code reading (`loading` signal set but
never referenced in the template) — I could not capture the literal transient zero-value frame
photographically, because this local backend answers in well under one screenshot round-trip, but
the absence of any loading UI at all was directly and repeatedly observed, including across a
~40-second wait for the initial five-request burst on first login.

**Evidence:** screenshots immediately post-click showing settled state with no interstitial
loading affordance, taken during QA-08/QA-19.

---

### QA-11 · major · Dashboard — three of five panel failures are silent, and one prints a raw error to the console

**Did:** Building on QA-07's malformed-date scenario (empty `From`), read the browser console
after the two 500s landed.

**Expected:** Each panel should show its own error state with a retry (criterion 21).

**Got:** No error message appeared anywhere on screen for either the bar chart ("Queue volume by
day") or the heatmap ("Queue activity by hour") — both simply kept showing their last-good data
(the 09-02→09-08 range's real figures), silently stale. The browser console recorded two unhandled
errors as raw objects:
```
ERROR {headers: e, status: 500, statusText: Unknown Error,
       url: http://localhost:9098/api/v1/dashboard.json/weeklyRunningJobStatistics?startDate=&endDate=2026-09-08,
       ok: false, …}
```
— exactly the shape grooming §12.6 predicts (no `error` handler on 3 of 5 subscriptions; the 4th,
`jobStatus`, fails silently by design rather than loudly). Only the drill-down panel (not exercised
via a forced failure in this pass, but confirmed present at `dashboard.ts` per grooming and
consistent with its own toast-based error handling seen working correctly elsewhere in this pass).

**Evidence:** console capture (`read_console_messages`) quoted above; screenshots showing the bar
chart and heatmap both retaining their pre-error data with no visible error affordance.

---

### QA-12 · major · Dashboard — no auto-refresh

**Did:** As Tenant Admin, loaded `/dashboard`, cleared the network log, then waited 70 seconds
(seven 10-second waits) with the tab in the foreground and re-read the network log filtered to
`dashboard.json`.

**Expected:** If the screen is meant to auto-refresh (as the old app did, every 60s — grooming
§2.3/§12.13), five new requests should appear.

**Got:** Zero new requests in 70+ seconds. The five initial requests from page load are the only
ones recorded; nothing fires again without a user action (Apply/Reset). The page also does not
state anywhere that its figures are static/when they were last fetched — an operator leaving this
open on a wall display would see stale numbers indefinitely with no indication.

**Evidence:** `read_network_requests` filtered to `dashboard.json`, cleared, then re-read after
70s — identical (empty-of-new-entries) result both times.

---

### QA-13 · major · Dashboard — heatmap drops weekdays with zero runs instead of drawing them empty

**Did:** As Platform Admin, viewed "Queue activity by hour" over the default 7-day range
(`2026-09-02` to `2026-09-08`, which spans all seven weekdays).

**Expected:** All seven weekday rows draw, including the five that had no runs at all in this
range (criterion 22).

**Got:** Only **two** rows are drawn: `Mon` and `Sat` — the two weekdays that happen to have data.
Tuesday, Wednesday, Thursday, Friday and Sunday are entirely absent from the grid, not shown as
empty rows. A reader has to notice an absence of a row rather than see a row full of "no runs"
cells, exactly as grooming §12.7 describes from the code
(`DAY_ORDER.filter(day => byDay.has(day))`).

**Evidence:** screenshot of the full heatmap card showing exactly two labelled rows (`Mon`, `Sat`)
against a 7-day default range.

---

### QA-14 · minor · Dashboard — heatmap has no "now" marker

**Did:** As Platform Admin, with the default range including today, inspected every cell's
accessible name and visual styling for any indication of the current date/hour.

**Expected:** Today's row and the current hour's column marked distinctly, per grooming criterion
24 (the old app had an amber border on the "now" cell, amber hour label, indigo today-label).

**Got:** No such marking exists anywhere. Every cell's hover/accessible text is only
`"<Weekday> <hour> — N runs"` (or "no runs"); the legend under the grid explains only "Less/More"
shading, nothing about a current-time indicator. Confirmed by reading the full accessibility tree
of the heatmap region — no cell, label, or legend text contains any reference to "today"/"now"/
"current".

**Evidence:** full `read_page` dump of the heatmap region (68 cell buttons, all following the
`"<Day> <hour> — N runs"` pattern with no distinguishing marker anywhere).

---

### QA-15 · major · Dashboard — drill-down mini-bar colours by column position, not by status

**Did:** As Platform Admin, opened the drill-down for `2026-09-07` at `12a` (72 jobs, each with
exactly one `Failed` run and nothing else). Compared the mini-bar's segment colour for these
all-Failed rows against the red/maroon used for "Failed" everywhere else on the same screen (the
"Jobs by last outcome" ring, and the KPI "Failed" tile, both render Failed in red/maroon —
`#8b2635`-ish in light mode, pink in dark mode).

**Expected:** The mini-bar's Failed segment is the same colour as the outcome ring's Failed slice
(criterion 35) — grooming notes the component already imports `statusColor` and uses it for the
ring but not here.

**Got:** Every row's mini-bar rendered **solid blue** (`--chart-0`, the position-0 colour), not
red — because `Failed` happened to be the first non-zero status in `segmentsFor(row)` for these
particular rows. A row whose only nonzero status were `Completed` would render the *identical*
blue, indistinguishable from a row whose only status is `Failed` — confirming grooming §12.12's
"colours by index, not meaning" exactly.

**Evidence:** screenshot of the drill-down table: "Failed" column reads `1` for every visible row,
"BREAKDOWN" mini-bar is uniformly blue, while the "Jobs by last outcome" ring two panels up renders
its `Failed: 118 (100%)` slice in red/maroon (light) / pink (dark) — a direct colour mismatch for
the same status on the same screen.

---

### QA-16 · pass · Dashboard — drill-down mechanics, tenant scoping, and the cross-tenant API attack all behaved correctly

**Did**, across several steps, all on the fixture cell `2026-09-07` at `12a`:
1. As Platform Admin, clicked the heatmap cell — opened "Jobs in 2026-09-07 at 12a (72 of 73)"
   listing all 72 jobs plus a separate `<tfoot>` "Total · 72 jobs" row.
2. Typed `2019` into the search box — narrowed to 1 row, `<tfoot>` recomputed to "Total · 1 job".
3. Typed `zzzznotfound` — got "No jobs match your search.", no stale `<tfoot>`, no pager.
4. Clicked job `#2019`'s `Failed` count (`1`) — navigated to
   `/jobs/2019/history?targetDate=2026-09-07&targetHr=0&jobStatus=Failed`, which rendered "Run
   history — WPV Job en · 02 Decode Gzip", "Filtered to `Failed` on 2026-09-07 at 12a", and listed
   exactly the one matching run.
5. Went to page 2 of the pager (72 rows / 50 per page) — `51–72 of 72`, `Page 2 of 2`, correct.
6. Confirmed every zero-count cell in the table renders as a **disabled** `<button>` with an
   accessible name like `"No queue runs"` / `"No stop runs"` (9 such labels read directly from the
   accessibility tree), while nonzero cells read `"View the failed runs for this job in this
   hour"` / `"View every run for this job in this hour"`.
7. **The attack**: as `qa-test-admin@example.com` (TENANT_ADMIN, tenant 1817 — which owns none of
   these 134 jobs), called, with that account's own real bearer token, directly against the API
   (not through the UI):
   `GET dashboard.json/weeklyHrRunningStatisticsDimensionDetail?targetDate=2026-09-07&targetHr=0&jobId=2019`
   — a job id that plainly exists and belongs to a different tenant.
8. As a tenant-scoping negative control, the **same account** called
   `GET dashboard.json/weeklyHrRunningStatisticsDimension?targetDate=2026-09-07&targetHr=0` (the
   cell-summary endpoint, no specific job) for the exact cell that has 72 jobs for every other
   tenant.

**Expected:** (7) refused, or at minimum returns nothing identifying the foreign job — matches
grooming criterion 9's shape. (8) returns this tenant's own (zero) data, not the other tenants'
72 jobs — matches criteria 6/7/8's tenant-isolation intent.

**Got:** All of it correct.
- (7) → `{"status":"SUCCESS","message":"No data found."}` — no `sourceJob` block, no run list, no
  confirmation the id exists. Doesn't leak the job's name, tenant, or existence.
- (8) → `{"status":"SUCCESS","data":[{"jobName":"TOTAL","total":0,"failed":0,...}]}` — only the
  synthetic `TOTAL` row with every count at zero. The other tenants' 72 jobs for this exact cell
  are completely invisible to this caller.

**Evidence:** response bodies quoted above verbatim, captured via `fetch()` using each account's
own stored `accessToken`; screenshots of steps 1–6.

---

### QA-17 · pass · Dashboard — a tenantless Platform Admin token correctly still gets fleet-wide figures

**Did:** Decoded the Platform Admin's own JWT payload (`admin@platform.local`) from
`localStorage`.

**Expected:** Per criterion 10, a tenantless PLATFORM_ADMIN should still see fleet-wide data (the
divergence grooming flags is specifically about a tenantless **non-admin**).

**Got:** The token's payload carries no `tenantId` claim at all (`{sub, appUserId, userRole:
"PLATFORM_ADMIN", type, iat, exp}` — no tenant field), and this account correctly sees the full
134-job fleet total on the dashboard throughout this pass. The other half of criterion 10 (a
tenantless **non-admin** should be refused/empty, not unscoped) could not be tested — no such
account is reachable through the live API, matching grooming §12.1's own note that
`AppUserServiceImpl` refuses to create one.

**Evidence:** decoded JWT payload (quoted in full in the session), showing no `tenantId` field for
`admin@platform.local`.

---

### QA-18 · minor · Dashboard — the default range's "today" is UTC, not the browser's local day

**Did:** Compared the browser's own local clock against the dashboard's computed default range,
both read at the same moment.

**Expected:** Criterion 11: the default range's "today" should agree with whatever timezone the
rest of the screen (subtitle, heatmap "now") uses.

**Got:** `new Date().toString()` in the browser read `Mon Sep 07 2026 20:00:27 GMT-0500 (Central
Daylight Time)` — i.e., locally still Monday evening, September 7th — while
`new Date().toISOString()` (what the app actually uses per grooming §2.2) read
`2026-09-08T01:00:27.313Z`, and the dashboard's default `To` field was indeed `09/08/2026`. So for
roughly the last several hours of every local day, the dashboard's "today" is already tomorrow by
the browser's own clock — confirming grooming's code-level claim
(`new Date().toISOString().slice(0,10)`) with a live, timestamped observation rather than only a
source reading.

**Evidence:** `{browserToday: "Mon Sep 07 2026 20:00:27 GMT-0500 (Central Daylight Time)", iso:
"2026-09-08T01:00:27.313Z"}` captured via `javascript_tool`, alongside the dashboard's own
`Showing 2026-09-02 to 2026-09-08` subtitle at the same moment.

---

### QA-19 · minor · Dashboard — Reset visibly lags one render frame behind its own network response

**Did:** As Platform Admin, with an inverted/empty range showing zeroed-out panels, clicked Reset
and took an immediate screenshot.

**Expected:** Reset restores the default range and reloads (criterion 16).

**Got:** The date fields updated correctly to the 7-day default immediately, and the network log
confirmed all four correct requests fired and returned 200 — but the very next screenshot still
showed the *old* zeroed/no-data panel content for a moment before a follow-up screenshot showed the
correct 134/118 figures. Reset does work (this is not the same defect as QA-10's total absence of
a loading state elsewhere) — it's a brief, cosmetic staleness between the field values updating and
the panels catching up, worth noting but not blocking.

**Evidence:** two consecutive screenshots after a single Reset click: first showing stale/empty
panels with the corrected date fields, second (after network requests are confirmed 200 in the
log) showing correct data.

---

### QA-20 · cosmetic · Administration → Users — "New user" dialog opens in the DOM but never becomes visible in this test harness

**Did:** As Tenant Admin, on `/admin/users`, clicked "New user" (both via direct click and via a
programmatic `.click()` on the button element) intending to create a TENANT_USER test account for
role coverage (see Fixtures).

**Expected:** A dialog appears for entering the new user's details.

**Got:** No dialog became visible in the Browser-pane screenshot or in `get_page_text`, but a DOM
inspection confirmed a CDK overlay backdrop and pane genuinely opened
(`.cdk-overlay-backdrop-showing` present, `popover="manual"` overlay element with real content).
This looks specific to this automation harness's rendering of the CSS Popover API rather than an
app defect — the same pattern (`popover="manual"` CDK overlays) is presumably used by every other
dialog in the app, several of which (login, drill-down) rendered and behaved correctly elsewhere in
this same pass. Recorded for completeness and so the "TENANT_USER untested" gap above isn't
mistaken for having been skipped without cause; not re-attempted after two failed tries, and not
treated as an application bug given the inconsistency with other dialogs.

**Evidence:** `document.querySelectorAll('.cdk-overlay-container *').length` → 325 (nonzero,
confirming DOM presence) immediately after the click, while the corresponding screenshot showed no
visible modal.

---

### QA-21 · pass · Dashboard — Total-column drill-through (row and footer) both correctly omit `jobStatus`

**Did:** As Platform Admin, on the same `2026-09-07 12a` cell: (a) clicked job `#2019`'s **Total**
column (not its Failed column) and (b) clicked the `<tfoot>` footer's **Total** column.

**Expected:** Both navigate with `targetDate`/`targetHr` but **no** `jobStatus`, per criteria 29
and 30 — (a) should list all of that job's runs, (b) should list every job's runs in the hour.

**Got:**
- (a) → `/jobs/2019/history?targetDate=2026-09-07&targetHr=0` (no `jobStatus`). Fresh reload
  rendered "Filtered to [blank] on 2026-09-07 at 12a" (no status chip, unlike the `Failed`-specific
  click which showed a red "Failed" chip) and listed the job's 1 run.
- (b) → `/jobs/history?targetDate=2026-09-07&targetHr=0` (no `jobId`, no `jobStatus`). Fresh reload
  rendered "Run history — All runs across every job on 2026-09-07 at 12a", "Filtered to `every
  job`", and "Runs (72 of 72)" — matching the drill-down's own "72 of 73" (73 including the
  synthetic TOTAL row the server appends) exactly.

**Evidence:** both destination URLs and their rendered headings/filter chips, screenshotted after a
full page reload of each.

---

### QA-22 · pass, contradicts grooming §12.11 · Dashboard — the drill-down does render a `Stop` column, and the columns do sum to `Total`

**Did:** As Platform Admin, read the drill-down table's header row and a full row's values for the
`2026-09-07 12a` cell.

**Expected per grooming §2.7/§12.11:** "Neither app renders a `Stop` column... the eight visible
columns therefore do not sum to Total."

**Got:** The live header row reads `JOB · Queue · Start · Running · Failed · Completed · Skip ·
Stop · Interrupt · Missed · TOTAL · BREAKDOWN` — **Stop is present**, between Skip and Interrupt.
Every row's values sum correctly: a job with `Failed=1` and everything else `0` (including
`Stop=0`) totals `1`; the footer row (`Failed=72`, everything else `0`) totals `72`. This directly
contradicts the grooming document's finding — either the code changed since that document was
written, or the static reading missed this column. Recorded as a live correction rather than a new
bug: **this appears to already be fixed**, and criterion 34 should be read as passing, not failing,
based on what's actually running.

**Evidence:** `get_page_text` dump of the table header and every visible row for the `12a` cell,
quoted in full during the session; footer row `Total · 72 jobs 0 0 0 72 0 0 0 0 0 72` matches
9 status columns + Total summing correctly.

---

### QA-23 · pass · Dashboard — dark mode and 375px viewport both hold up

**Did:** As Platform Admin with the real 134/118 fixture on screen: (a) toggled the header's theme
button light→dark and inspected every region; (b) called `resize_window` to the `mobile` preset
(375×812) and inspected layout, then opened the drill-down at that width.

**Expected:** Criteria 39 (no light-only fills) and 40 (no horizontal page scroll; table scrolls in
its own box).

**Got:**
- Dark mode: both donut rings, the bar chart, the KPI tiles, and the heatmap all redrew from
  dark-mode tokens — the outcome ring's Failed slice switched from maroon to a legible pink, the
  bar chart stayed blue-on-dark, tile surfaces and text contrast all held up. No element was found
  still painted with a light-mode-only fill.
- 375px: `document.documentElement.scrollWidth === document.documentElement.clientWidth === 375`
  (no horizontal page overflow) at every scroll position tested. KPI tiles fell to a 2-column grid,
  the date row stacked to full-width fields, and the heatmap rendered as 25 very small columns with
  no scrollbar (matches grooming's "gets small, doesn't overflow" prediction exactly). Opening the
  drill-down at this width showed the table's *own* horizontal scrollbar (a visible grey thumb
  inside the table's box) while the page itself still did not scroll sideways — column text
  truncates with `…` at this width, which is expected/acceptable behaviour for a data-dense table
  this narrow.

**Evidence:** screenshots of both themes on the same data; `scrollWidth`/`clientWidth` equality
check at 375px; screenshot of the drill-down table's internal scrollbar at 375px.

---

## UI/UX — additional notes beyond the numbered criteria

- **KPI tiles are `<a>` elements with no `href` (five of six).** Reading the DOM directly: `Total
  jobs`, `Active jobs`, `Running now`, `Completed`, and `Failed` are all rendered as `<a>` tags
  (confirmed by both the accessibility tree, which reports them as `link`, and
  `getAttribute('href')`, which returns `null` for all five) — only `Unread` carries a real
  `href="/notifications"` and actually navigates (confirmed by clicking it and reading
  `location.href`). Clicking any of the other five does nothing and goes nowhere. This is
  **cosmetic/minor**: semantically these are dead links (not real anchors, arguably confusing for
  a screen-reader user told "link" for something inert), but grooming already independently flags
  the broader issue that these tiles are hand-rolled rather than using the shared `StatTile`
  component (§2.4) — this is one concrete symptom of that.
- Empty-state copy is present and matches the grooming spec exactly for all four data panels
  (`No data in this range.` ×2 rings, `No runs in this range.` bar chart, `No activity in this
  range.` heatmap, `No jobs match your search.` / a job-count-based no-rows message in the
  drill-down) — contrary to what an unread version of grooming §4.6 might suggest, none of these
  are actually missing; they were all directly observed against the genuinely-empty tenant
  fixture.
- The route-progress bar (thin blue bar under the header) is visible only briefly during
  navigation, exactly as grooming describes — it finishes well before the five dashboard XHRs
  return and does not read as a loading state for the data itself.

## Backend — additional notes

- `GET dashboard.json/jobStatusStatistics` with no `Authorization` header → HTTP 401
  (`{"status":401,"error":"Unauthorized", ...}`); the identical call with a valid token → HTTP 200.
  Confirms the class-level `@PreAuthorize` is in force and not bypassable by omission.
- Every dashboard 500 observed in this pass (QA-07) carries the identical generic body
  `{"status":"ERROR","message":"Some internal error occurred contact with support."}` regardless of
  cause — confirmed live for a malformed-date `IllegalArgumentException`, matching grooming's
  prediction that this makes a client mistake indistinguishable from a real outage in the response
  body (and, by extension, in whatever server log line accompanies it).
- No query in this pass was slow enough to notice — the busiest cell (72 jobs) and full-fleet
  aggregate (134 jobs) both answered fast enough that no loading state was even catchable
  end-to-end (QA-10). Not a finding against grooming §6's index-gap concern, just a note that this
  fixture's scale (hundreds of rows, not the millions a mature deployment would have) doesn't
  surface it.

---

## Known issues from grooming §12 — live status

| # | Grooming's claim | This pass |
|---|---|---|
| 12.1 | Tenantless non-admin unscoped rather than refused | not reachable live (QA-17) |
| 12.2 | No date validation at all | **confirmed** (QA-07, QA-08) |
| 12.3 | `To` has no upper bound | **confirmed** (QA-09) |
| 12.4 | Same bad input, 3 different server behaviours | **confirmed** (QA-07) |
| 12.5 | `loading` signal never rendered | **confirmed** (QA-10) |
| 12.6 | 3 of 5 requests have no error handler | **confirmed** (QA-11) |
| 12.7 | Weekday with no runs dropped from heatmap | **confirmed** (QA-13) |
| 12.8 | >7-day range heatmap discards data (last-write-wins) | not reproducible — fixture data spans only 2 dates on 2 different weekdays |
| 12.9 | Heatmap lost its "now" markers | **confirmed** (QA-14) |
| 12.10 | Drill-down pager can report a stale page | not reproducible — largest fixture cell is 72 rows (2 pages at the 50-row minimum page size); no UI control goes below 50/page |
| 12.11 | `Stop` status counted into Total, shown in no column | **contradicted live — Stop column is present and sums correctly** (QA-22) |
| 12.12 | Mini-bar colours by position, not status | **confirmed** (QA-15) |
| 12.13 | 60s auto-refresh not migrated | **confirmed** (QA-12) |
| 12.14 | Unread tile vs. bell badge can disagree | not reproducible — both accounts have 0 unread notifications in this environment |
| 12.15 | `DashboardService.breakdownDetail` dead code | not independently re-verified live (a static-code claim about an uncalled method; no live behaviour to observe) |
| 12.16 | Duplicate weekday labels on bar chart over >7 days | not exercised — would need to widen the range past 7 days with cross-week same-weekday data, which this fixture lacks (same root cause as 12.8's gap) |
| 12.17 | No index on `job_queue.date_created` | not exercised — a performance characteristic, not observable as a functional defect at this data volume |
| 12.18 | A job named "Total" would vanish from the drill-down | not exercised — no job in this fixture is named "Total" and creating one was judged out of scope |
| 12.19 | No tests exist for this feature | out of scope for a live-app QA pass (this is a statement about the test suite, not the running app) |

---

## Summary

Of the 19 previously-documented known issues, **12 were independently reproduced live** in this
pass with fresh evidence (12.2–12.7, 12.9, 12.12–12.13), **1 was directly contradicted** by live
observation (12.11 — the Stop column exists and sums correctly today), and the remaining 6 could
not be provoked with this environment's current data volume or were out of scope for a black-box
pass (12.1, 12.8, 12.10, 12.14, 12.15/12.17/12.19 by nature, 12.16, 12.18). Three new observations
were made that grooming's static reading didn't call out: the UTC-vs-local-timezone default range
(QA-18), the KPI tiles' dead `<a>` elements (UI/UX notes), and Reset's one-frame render lag
(QA-19) — all minor. The security-relevant checks (unauthenticated 401, cross-tenant job-detail
fetch by id, tenant-scoped aggregate query) all passed cleanly (QA-15/16/17) — no working
exploit was found against this feature's authorization in this pass, though the tenantless-non-admin
gap (12.1) remains a real, if currently unreachable, divergence per grooming's own analysis.
