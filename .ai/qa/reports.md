# QA — Reports

Companion to `.ai/grooming/reports.md` (acceptance criteria in its §11, known issues in its §12) and
`.ai/synthesis/reports.md` (the twenty-row gap table this pass repeatedly lands on). All paths are
relative to `/Users/nabeel.amd93/Desktop/Old-School`.

**This pass broke the QA phase's own rule, and says so rather than hiding it.**
`.ai/qa/README.md` is explicit: *"Record, do not fix. A finding fixed in the same pass is a finding
that quietly disappears when the fix turns out to be hard."* Every finding below was fixed in the
same session it was found, on 2026-09-08. That is a departure from the method, made deliberately --
the findings arrived as live user QA on a screen already under active execution, not as a scheduled
QA sweep after Execution had closed -- and it costs something real: none of these defects sat
un-fixed long enough for anyone to weigh them against each other, and the record below is therefore
a fix log wearing a QA register's clothes. It is written in the register's format anyway, with the
observation kept separate from the fix, because the observation is the part worth keeping. Where a
fix is partial, the remainder is stated in the same entry rather than in a follow-up nobody reads.

**Numbering.** This file restarts at `QA-01` rather than continuing from `QA-35`
(`qa/source-jobs.md`), on instruction. That contradicts `qa/README.md`'s continuous-numbering rule,
whose whole point is that a finding can be named in a commit message without ambiguity -- so cite
these as **`reports/QA-nn`**, not bare `QA-nn`, which now collides with `source-tasks/QA-01`-`06`.

**Scope of this pass.** The `/reports` screen only, as a reader -- the summary tiles, the runs-by-day
chart, the outcome mix, task health, the pivot and its chart, and the drill-through. Live, against
the running stack, one workspace's real run data. Not in scope, and not touched: the export
destinations (download, bucket, submit) and everything the synthesis document files under security.

**Fixtures.** No data was created for this pass. The population in front of the reader was this
deployment's own accumulated `job_queue` history, which turned out to be the most useful fixture
available precisely because of its shape: **49 runs, all of them stamped on a single day
(2026-09-08), inside the screen's default 30-day range**, and durations dominated by dispatcher
latency rather than work (a 41.48s mean end-to-end against 0.23s of actual execution). Three of the
five most serious findings below are visible only on data shaped like that, and would have been
invisible against an evenly-spread synthetic fixture. Nothing was left behind.

**What this pass is not.** It is a single-role, single-workspace, single-viewport reading pass. There
was no second tenant, no negative control, no platform-admin session, no dark-mode sweep and no
375px sweep. See "Not exercised" below, which is longer than the findings list and should be read
first by anyone deciding whether `reports` is done.

---

## Acceptance criteria exercised (grooming §11)

Only the criteria this pass genuinely touched are listed. Everything omitted is **untested, not
passed** -- see the section after the findings.

| # | Criterion | Result |
|---|---|---|
| 1 | `/reports` opens on From = 30 days ago, To = today, untouched | **PASS** -- and this default range is exactly where QA-01 was found; the criterion passes while the chart it produces was unreadable |
| 9 | Clearing From is refused with a message naming the missing date, not silently all-history | **partial PASS, client only** -- `reports.ts:600-604` refuses a range that is not two `yyyy-mm-dd` dates. `ReportRestApi` still declares both parameters optional and `QueryService.dateRangeFilter` still drops the filter entirely on a blank one, so a direct call with no dates still scans all history. Synthesis gap 5 is half closed; there is no `MAX_SPAN_DAYS` |
| 10 | From later than To gives a message, not an empty grid | **PASS** (client) -- see QA-11 for the part of this that was wrong |
| 15 | A row total under a median measure is the median of the row, not the sum of the cell medians | **not re-exercised live** -- `pivot.spec.ts` asserts it and still does; this pass changed nothing about `rowTotals` and offers no fresh evidence either way |
| 17 | A group of never-finished runs shows an em dash; a group that genuinely took zero shows `0s` | **PASS after the fix** -- see QA-07. Both halves now render distinctly, and the grid tells "no runs" from "no time" using `cellRows` |
| 24 | Area with three series: none completely hidden | **PASS after the fix** -- see QA-08. **Radar is a different answer**: still opaque, and still silently capped at four series |
| 25 | Under a non-additive measure the summing chart kinds are unavailable and say why | **PASS after the fix** -- see QA-03, and the implementation went one kind further than the criterion: **radar** joins Stacked, 100% stacked, Pie and Donut in the disabled set, because a radar sums its spokes too |
| 27 | At 375px the chart re-measures rather than overflowing | **partial** -- the re-measure mechanism was built and verified at desktop widths (QA-01); the browser was never actually narrowed to 375px on this screen. The pivot table's own horizontal scroll was not checked at all |

---

### QA-01 · major, fixed 2026-09-08 · Runs by day — the axis labels collided at the screen's own default range

**Did:** Opened `/reports` and touched nothing. The default range is today minus 30 days to today
(`reports.ts:193-194`), so the "Runs by day" chart drew 31 bars. Read the axis at a 1024px viewport.

**Expected:** A legible date axis. Whatever thinning rule the chart uses, two labels that are drawn
should not overlap each other.

**Got:** The last two labels ran together as a single unreadable string -- rendered as `09-0609-08`.
Not a rounding-error overlap: a 5-character `MM-DD` label measures **29.6px** in this font
(`shared/charts/bar-chart.ts:26-30`), and the two labels were **28px** apart.

**Cause, read from source:** two independent mistakes in the same rule.
- The chart thinned labels **by bar count alone** -- "more than sixteen bars, show every
  `ceil(n/8)`th" -- a rule with no width term in it. The same 31 bars are ~14px apart in a
  third-of-a-row card and ~45px apart at full width, so no single constant could ever be right for
  both (`bar-chart.ts:128-133` now records this).
- On top of that modulo grid it **pinned the last index unconditionally**, which the grid knew
  nothing about. With 31 bars the labelled gaps came out `4,4,4,4,4,4,4,2` -- the trailing 2 being
  index 28 against the forced index 30, two bars and 28px apart under a 30px label.

**How far it reached:** enumerated during this pass across bar counts 1-350 at a 1024px width,
**114 of the 350 possible counts collided**. The default range is one of them, which is why this
was visible without going looking.

**Severity:** major. The primary chart on the screen, at the range the screen chooses for itself,
was unreadable -- and unreadable in a way that reads as a rendering glitch rather than as a chart
saying something.

**Evidence:** the rendered axis string `09-0609-08`; the labelled-index gap sequence
`4,4,4,4,4,4,4,2` for 31 bars; the 1024px enumeration above.

**Fixed:** `shared/charts/bar-chart.ts` now measures its own width (`ResizeObserver` plus a
`window` resize listener, with the component host blockified so `getBoundingClientRect` reports the
width the bars actually occupy) and derives both label thinning and value-label display **in
pixels**, from the measured pitch against `LABEL_PX = 34`. The labelled grid is anchored against
the **last** index instead of pinning it on top of a modulo run, so no labelled pair is ever closer
than the chosen stride. `bar-chart.spec.ts:77` -- "spaces every labelled pair evenly, so no two
labels can collide" -- asserts the invariant the old rule broke, across 17/20/24/25/30/31/45/60/91/
180/366 bars, and a second case asserts the first and last bars always carry a label so the axis
stays bounded.

**Left open:** the `ResizeObserver` path is unit-tested and was verified at desktop widths. It was
not verified at 375px (criterion 27).

---

### QA-02 · minor, fixed 2026-09-08 · Runs by day — the caption described gaps in a trend that did not exist

**Did:** Same screen, same load. All 49 runs in the population fell on **one day**, 2026-09-08,
inside a 31-day range. Read the caption under the chart.

**Expected:** The card's own one-day branch -- "All of these runs happened on one day — there is no
trend to read yet." -- which exists in the template precisely for this case
(`reports.html:217-218`).

**Got:** "Runs on **31 of 31** days. Days with no runs are drawn empty." The caption told the reader
about a month of daily activity, beside a chart showing a single bar.

**Cause, read from source:** the branch was fed by `daysCovered()`, which returned
`runsByDay().length`. The day series is **gap-filled** -- it emits a bar for every day in the range,
zero-valued or not -- so that length is the *selected range's* length and nothing else. It could
never be 1 unless the reader picked a one-day range by hand, which means the one-day branch was
unreachable by the data it was written for.

**Severity:** minor as a defect, but it is the second-order kind worth writing down: the caption was
not merely wrong, it was *confidently* wrong about the shape of the data, on a screen whose entire
purpose is telling a reader the shape of their data.

**Evidence:** the caption "Runs on 31 of 31 days" rendered against a single populated bar; the
population's day dictionary carrying exactly one value.

**Fixed:** `activeDays()` counts bars that actually carry a run
(`reports.ts:447` -- `runsByDay().filter(bar => bar.value > 0).length`), and `reports.html:217`
branches on `activeDays() <= 1`. The multi-day caption now reads "Runs on N of M days", where N and
M are different numbers. Two neighbouring captions were kept honest in the same edit: `daysCapped()`
(see QA-06) and `undatedRuns()`, which reports runs the chart could not place because their row
carries no day.

---

### QA-03 · major, fixed 2026-09-08 · The donut reported 56% / 44% where the real split was 92% / 8%

**Did:** Set Rows = Task, Columns = Outcome, measure = **Mean duration**, chart kind = **Donut**.
Read the segments. Then counted the same split directly from the underlying runs.

**Expected:** Either honest proportions, or no donut.

**Got:** The donut drew **56% / 44%**. The real split of the time those runs actually consumed was
**92% / 8%**. Nothing on screen distinguished the drawn figure from a fact.

**Cause, read from source:** every summing chart kind turns a set of cells into a whole -- a donut
divides each cell by the sum of the cells, a stacked bar piles them, a radar sums its spokes. The
pivot is additive for exactly **two** of its twelve measures. For a mean or a percentile, the
denominator those charts compute is the sum of the means, which is not a quantity: it is not the
total time, not the mean of the totals, and not anything a reader can act on. This is synthesis
gap 7, and the donut is its most photogenic instance because it prints the meaningless denominator
as a percentage to the reader's face.

**Severity:** major. Every other defect in this file makes the screen harder to read. This one made
it *wrong*, silently, in a shape designed to be believed.

**Evidence:** the 56%/44% donut; the 92%/8% split counted independently from the runs behind the
same two cells. The figures are kept in the code at `report-pivot.ts:88-95`, where the disabled
control now explains itself.

**Fixed:** `pivot.ts:135` gains `ADDITIVE = new Set(['count', 'sum'])` beside the existing
`COUNTING`. `report-pivot.ts:97-112` names the five summing kinds
(`stacked`, `pct`, `donut`, `pie`, `radar`), computes `measureIsAdditive()`, and exposes
`kindAllowed()` / `kindRefusal()`. `report-pivot.html:96` disables the button and states the reason
in full -- "*Donut adds cells together, and mean duration cannot be added. Pick Runs or Total time,
or use a bar, line or ranked chart.*" -- rather than hiding the control, so the refusal teaches
instead of looking like a bug. An `effect` falls back to Grouped if the measure changes underneath
an open summing chart, so the reader is moved to the honest equivalent rather than left with a
disabled button behind a lie.

**Deliberately not fixed the other way.** Making the summing charts compute their denominator from
the cells was rejected in `synthesis/reports.md` §3.4 and that rejection still holds: a
100%-stacked bar of medians would then be internally consistent *and* still meaningless. The chart
was made to agree with the arithmetic, not the arithmetic with the chart.

---

### QA-04 · major, fixed 2026-09-08 · The duration tile was 99.4% dispatcher wait, captioned as though it were task performance

**Did:** Read the "Median duration" tile against the whole population, then compared it against what
the tasks behind those runs actually do.

**Expected:** A figure a reader can act on -- "how long does this task take".

**Got:** A mean of **41.48s**, of which **41.25s (99.4%)** was queue wait. The tasks themselves ran
in **0.23s**. A reader optimising against this tile would have spent their week on a transform that
was never slow.

**Cause, read from source:** `job_queue` stamps `start_time` at **enqueue**, not at pickup --
measured across every run on this instance, `start_time` and `date_created` are within 10ms of each
other. There is no execution-start column on the table, so `end_time - start_time` is wait plus
execution with nothing to separate them, and on this deployment the dispatcher polls once a minute,
so the wait dominates. The tile was not computing the wrong thing; it was computing the only thing
available and presenting it under a name that means something else.

**Severity:** major. A number that is arithmetically correct and directionally misleading is worse
than a missing number, because nobody double-checks it.

**Evidence:** the 41.48s / 41.25s / 0.23s split, measured over the population and now recorded in
`QueryService.java:266-278` where the fix lives; the observed spread of 32s-61s end-to-end for
pipelines doing about a second of work (`reports.ts:344-353`).

**Fixed, in three places:**
- **The data.** `QueryService.runReportRows` left-joins the `job_audit_logs` "Job started" marker --
  the worker writes it the moment it picks a run up, and it covers every run in this database, so
  the pickup instant *is* recorded, just not in `job_queue` -- and emits `exec_seconds`
  (`QueryService.java:283-295`). `LEFT JOIN`, so a run with no marker reports `-1` and is excluded
  from execution statistics rather than counted as instant. Rounded to **two decimals**, unlike
  `seconds`: whole seconds print "0s" for a 0.23s run, which reads as *no data* and throws away the
  contrast the column exists to show.
- **The measures.** `pivot.ts` gains `execAvg` / `execMedian` / `execMax` in their own "Execution"
  group (`:149`), so a reader can pivot on real execution time rather than on the dispatcher.
- **The caption.** The tile's foot now states the split out loud -- "*<x> running, rest is queue
  wait*" (`reports.ts:355-364`) -- instead of the earlier hint that the wait was "included".

**Note on the SQL:** the epoch cast is written `cast(… as numeric)` and not `::numeric`, because
this string is handed to `entityManager.createNativeQuery`, which parses `:` as the start of a named
parameter -- `::numeric` was a syntax error at the database. Recorded because it is exactly the kind
of thing a later editor reverts on style grounds.

---

### QA-05 · major, fixed 2026-09-08 · The screen had no way to narrow anything except the two date boxes

**Did:** Tried to answer the ordinary follow-up question this screen invites -- "fine, but how did
*this one task* do?" -- and looked for a control.

**Expected:** Some way to narrow the population. The screen's own purpose statement in
`grooming/reports.md` §1 is "group my runs by whatever I want".

**Got:** Two date inputs. Nothing else. Every other question had to be answered either by
re-pivoting (which changes the shape of the whole screen to answer a question about one row) or by
reading the 49-row table by eye. The tiles, the runs-by-day chart, the outcome mix, task health and
the pivot all described the same undifferentiated population, and there was no way to make any of
them describe a subset.

**Severity:** major. Not a broken control -- a missing one, on the screen whose reason for existing
is asking questions that were not decided in advance.

**Evidence:** the toolbar as shipped, carrying From and To and no third control.

**Fixed:** Task, Job, Outcome, Owner and **Workspace** selects (`reports.html:46-90`), each backed
by a signal and a computed option list drawn from the payload's own dictionaries
(`reports.ts:123-152`), with per-filter clear chips and a clear-all.

**The part worth insisting on:** all five narrow **one** `data()` computed
(`reports.ts:176-190`), and every tile, chart, table *and* the pivot builder reads that one
computed. This is deliberate and it is written into the code's own comment, because the same
session fixed the opposite arrangement on the Queue screen -- where the donut, the failure rate and
the counts described the unfiltered population while the table obeyed the filters, so searching
narrowed the table from 53 messages to 1 and left the donut describing 53. A filter that reaches
some visualisations and misses others is a worse defect than no filter at all.

**Also added in the same pass, same "let the reader narrow it" story:** runs-by-day is now stacked
by outcome, and clicking a bar narrows the range to that day. The Workspace select renders only when
more than one workspace is actually present (`reports.ts:144`) -- a tenant admin would otherwise get
a select with one option that can never change anything.

---

### QA-06 · major, fixed 2026-09-08 · A range longer than the cap kept the oldest days and dropped the newest

**Did:** Read the runs-by-day axis against a range longer than the 366-day cap.

**Expected:** If an axis has to be shortened, it keeps the end the reader is looking at -- the recent
one.

**Got:** The chart drew **366 empty days and reported nothing**, while the summary tile beside it
counted fifty runs. The axis walked forward from the *start* of the range and stopped at the cap, so
a two-year range kept the oldest days and threw away everything the reader had actually come to see.

**Cause, read from source:** `shared/charts/day-series.ts` stepped from `from` and stopped at a
count. `MAX_DAYS = 366` is a reasonable cap; the direction it was applied in was not.

**Severity:** major. The failure is silent and self-consistent: an empty chart beside a non-zero
count reads as "the chart is broken", and the reader's most likely next move -- widen the range --
makes it worse.

**Evidence:** 366 empty bars against a tile reading fifty runs, on the same load; now recorded in
`day-series.ts:24-27`.

**Fixed:** `day-series.ts` anchors the axis to the **recent** end
(`start = capped ? end - (maxDays - 1) days : begin`). `daysCapped()` (`reports.ts:437`) drives a
caption saying "Showing the most recent N days", so the truncation is stated rather than inferred.
Days are still stepped in UTC and keys compared as text, so a local daylight-saving boundary cannot
duplicate or drop a bar.

---

### QA-07 · minor, fixed 2026-09-08 · Zero and "no data" rendered identically

**Did:** Under a duration measure, compared a cell whose runs finished too fast to measure against a
cell with no runs behind it at all.

**Expected:** Criterion 17 -- an em dash for absent data, `0s` for a real, instant run.

**Got:** Both printed an em dash. `humanSeconds` opened with `if (!value) return '—'`, so a run that
finished inside a second -- which rounds to 0 in the query -- was reported as "no duration recorded",
and a gridline at the origin was labelled with a dash. Once the Execution measures landed (QA-04),
which are *genuinely* sub-second, this stopped being an edge case and became the common one.

**Severity:** minor in isolation; it matters because it is the one change `synthesis/reports.md`
§3.5 calls "the riskiest small change here", and it changed a pre-existing test.

**Evidence:** two cells rendering the same em dash for two different facts, one of them with runs
behind it.

**Fixed:** `pivot.ts:281-289` -- **negative is the no-data sentinel** and renders the em dash, `0`
renders `0s`, and values under 10s keep two decimals so `0.23s` survives instead of rounding to
`0s`. Every caller already guarded the sentinel with `>= 0`, so returning a real answer for a real
zero is what they were expecting. The grid goes one step further: `cellText()`
(`report-pivot.ts:193-198`) consults `cellRows` -- the actual runs behind the cell, which the charts
do not have -- and prints an em dash for a cell with **no runs**, as against a cell whose runs took
no time.

**This changed an existing assertion.** `pivot.spec.ts:142-147` previously expected
`humanSeconds(0) === '—'` and now expects `'0s'`, with the reasoning written above the case rather
than left to a diff. Flagged loudly: an assertion that changes is the one place a "fix" can quietly
become a regression.

**Left open:** synthesis gap 9 is only half closed. The cell *text* now distinguishes the two cases;
the clickability does not. `report-pivot.html:196` still reads
`[disabled]="!pivot().matrix[ri][ci]"` -- bound to the falsy measured value, not to
`cellRows[ri][ci].length === 0` -- so under a duration measure a cell whose runs never finished is
still unreachable by drill-through. Criterion 19's positive control would still fail.

---

### QA-08 · minor, area fixed 2026-09-08 / radar open · An overlapping series was completely invisible

**Did:** Drew an Area chart with three series where one series' values were contained within
another's.

**Expected:** Criterion 24 -- all three distinguishable; no series completely hidden.

**Got:** The contained series was entirely invisible. Each series painted an opaque polygon in
series order, so a smaller one drawn earlier simply disappeared under a larger one drawn later.

**Severity:** minor -- the data is present and the legend is honest; the reader just cannot see it.

**Evidence:** a three-series area chart rendering two visible bands.

**Fixed for Area:** the segment fill is now translucent (`fill-opacity` 0.35), so overlapping series
are all visible. Criterion 24 passes.

**Not fixed for Radar, and stated rather than left implicit:** radar still paints opaque polygons,
and it still carries a **silent four-series cap** -- a fifth series is dropped with nothing on screen
saying so. Half of synthesis gap 8 is open. Radar has since been added to the
disabled-for-non-additive set (QA-03), which narrows when a reader can reach it but does not fix
either problem.

---

### QA-09 · minor, fixed 2026-09-08 · The line and area axes flipped on a hyphen in a task name

**Did:** Read the line/area branch's axis orientation against a pivot whose first column label
contained a hyphen but was not a date.

**Expected:** The chart puts Day on the axis that holds the Day dimension.

**Got:** The flip was decided by **testing the first column label for a hyphen** -- a proxy for "this
looks like `YYYY-MM-DD`". A task named `etl-daily`, or any other hyphenated label in the first
column, silently inverted the axes with no error and nothing to notice.

**Severity:** minor -- it needs a hyphenated label in the first column to trigger, and this codebase
is full of them.

**Evidence:** the label-text heuristic in the chart's line/area branch, since replaced.

**Fixed:** `report-pivot.ts:101-103` computes a `dayAxis` of `'row' | 'col' | 'none'` from which
`Dimension` actually carries the key `day`, and passes it into the chart as an input. The chart no
longer inspects label text to work out what it is drawing. Closes synthesis gap 17.

---

### QA-10 · major, fixed 2026-09-08 · A platform admin's report merged every workspace with nothing on screen to say so

**Did:** Read what a platform admin's report actually contains.

**Expected:** Criterion 7 says a platform admin sees runs from both tenants in one grid -- and it
should be possible to tell which is which.

**Got:** One merged grid. `tenantClause` returns an empty string for a platform admin, so the query
is deliberately unscoped, and the payload carried no tenant column, the pivot offered no tenant
dimension, and there was no filter. Two workspaces' tasks with the same name merged into one row and
totalled together. The one role that can see everything was the only role that could not tell what
it was looking at.

**Severity:** major. This is not a leak -- the merge is the intended behaviour for that role -- it is
an unlabelled merge, which turns a legitimate capability into a source of wrong answers.

**Evidence:** the runs payload's four dictionaries (`task`, `status`, `owner`, `day`) with no fifth;
`DIMENSIONS` with four entries.

**Fixed:** `QueryService.runReportRows` selects
`coalesce(t.tenant_name, '(no workspace)') as tenant` via a left join on `tenant`
(`QueryService.java:264`); `ReportExportServiceImpl` interns it as a `tenant` dictionary at **row
index 7**; `pivot.ts` gains `TENANT_IDX = 7` and a fifth `DIMENSIONS` entry. A **Workspace** filter
(QA-05) and a Workspace column on `/settings/kafka` came in the same pass. Closes synthesis gap 15,
which is the recommendation `synthesis/reports.md` Q1 argued for -- option (b), a conditional fifth
dimension -- over both leaving it merged and forcing a platform admin to pick one tenant first.

---

### QA-11 · minor, fixed 2026-09-08 · An impossible date range offered "Try again", which could never succeed

**Did:** Set From later than To.

**Expected:** A message saying so (criterion 10) and a way out of it.

**Got:** The message, and beside it a **"Try again"** button that re-issued the identical impossible
request. The reader could press it as many times as they liked; nothing about the range changed, so
nothing about the answer could. The one control offered was the one control that could not work.

**Severity:** minor -- the refusal itself was correct, and the reader eventually notices the dates.
Recorded because "offer a retry on anything that failed" is a habit, and this is the case where the
habit is wrong.

**Evidence:** the error card with its Try again button, and the unchanged response after pressing
it.

**Fixed:** `reports.html:131-141` branches on `rangeValid()`: a request that genuinely failed keeps
its retry; a range that can never load gets **"Reset to the last 30 days"**, which is the control
that resolves it (`reports.ts:610-614`). The comment above the branch says why, so the retry does
not get restored on tidy-up.

**Left open, and this is the important half:** the validation is entirely client-side. Synthesis gap
5 asked for a validator in `runRows`, `required = true` on both `ReportRestApi` parameters, and a
`MAX_SPAN_DAYS` constant. None of those exist. A direct call to `report.json/runs` with no dates
still returns the caller's entire history -- the unbounded scan of the largest table that gap 5 is
about -- capped only by `MAX_ROWS = 50_000` *after* the database has materialised the whole result
set. Criterion 9 passes at the UI and fails at the API.

---

### QA-12 · minor, fixed 2026-09-08 · The screen fetched the same runs payload twice on every visit

**Did:** Watched the network on a single visit to `/reports`.

**Expected:** One request for the runs.

**Got:** The runs payload was requested **twice** per visit -- the same range, the same response,
paid for twice on the largest query the screen makes.

**Severity:** minor -- nothing was wrong on screen, and on this deployment's data volume nobody would
feel it. It is the kind of finding that only stays minor while the data stays small.

**Evidence:** two identical `GET report.json/runs` entries on one page load.

**Fixed:** one load path through a single `switchMap`ped subject (`reports.ts:565-597`), giving
**three** requests per visit and each for something different: the runs, the failure detail
(`loadFailures`), and the immediately-preceding window used for the period-on-period deltas
(`loadPriorPeriod`). `switchMap` rather than a bare subscribe is deliberate and load-bearing:
editing both date boxes fires two overlapping requests, and without cancellation a slow first
response lands after the fast second one and the page shows a range the inputs no longer say. The
`catchError` sits **inside** the `switchMap` for the same class of reason -- on the outer subscribe
it would terminate the subject on the first failure, leaving every later Refresh and date edit
pushing into a dead stream with the spinner on and no request in flight.

---

### QA-13 · minor, fixed 2026-09-08 · The run-log drill-through was refused by a comment that was no longer true

**Did:** Looked for the run log behind a failed run, and found the code declining to offer it, with
a comment explaining that `job_audit_logs` has no rows.

**Expected:** Either a drill-through, or a refusal that is true.

**Got:** The claim was **factually stale on this deployment**. `job_audit_logs` carries a "Job
started" marker for every run in this database -- the same rows QA-04's `exec_seconds` column now
left-joins to compute real execution time. The table the comment said was empty is the table the
screen now depends on.

**Severity:** minor as a defect; worth its own entry as a category. A comment asserting a fact about
the data is a claim with a shelf life, and this one silently withheld a capability the data had been
supporting for some time.

**Evidence:** the `job_audit_logs` "Job started" rows joined at `QueryService.java:295`, against the
comment declaring the table empty.

**Fixed:** run-log drill-through added, and the stale comment removed rather than edited. The
drill-through joins the runs feed's own `job_queue_id` to name the job and task, because `fetchLogs`
projects `job_queue` columns only and carries neither name (`reports.ts:233-250`) -- the join is done
on the client rather than teaching the server to send something it already sent once.

---

## Not exercised — read this before calling `reports` done

This pass is a single-role, single-workspace reading pass. What it did **not** cover is larger than
what it did, and none of the following should be read as passing.

**The entire security half of the feature.** Synthesis gaps 1, 2, 3 and 4 -- the ones the synthesis
document orders **first, and independently of everything else** -- were not touched by this session
at all, and no criterion covering them was exercised:
- **Criterion 35 / 39** -- `submit` is still available to `TENANT_USER`. Any signed-in user can
  still make the application server POST the grid to an address they type and read the reply back.
  No destination check in `export`, no `auth.canSubmitReports()` gate.
- **Criteria 36, 37** -- the submit address guard still checks only the five `InetAddress`
  predicates, so CGNAT (`100.64.0.0/10`), IPv6 ULA (`fc00::/7`) and `0.0.0.0/8` remain reachable,
  and plain `http` to any public host is permitted.
- **Criterion 41** -- `report.submit.allow-internal` is still only an `@Value` default, undeclared
  in any profile and unasserted by `ApplicationPropertiesDeclarationTest`.
- **Criterion 38** -- the `RestTemplate` still has no connect or read timeout.

**Cross-tenant and role coverage: none.** Criteria 5, 6, 7, 8, 32, 33 are all untested. There was
one workspace's data in front of the reader and no second account, so there is **no negative
control** anywhere in this pass -- not for the runs query, not for the export destinations. QA-10
added a Workspace dimension and filter, which is a *display* change; it proves nothing about
`tenantClause` scoping, and specifically does not test criterion 6 (a tenantless `TENANT_USER`
token).

**Export: nothing.** Criteria 28-34 untested. Not exercised, but read from source and worth flagging
for whoever does: `report-destination-dialog.ts:36` still collects the bucket as a **free-text
input** with an `etl-bucket` placeholder, not the list of reachable buckets synthesis gap 11 asked
for -- and `etl-bucket` is the platform secret bucket, refused for every non-platform caller and
disastrous for the one caller it succeeds for. The `window.prompt` half of gap 11 was closed earlier
(2026-09-06, `scheduler1` commit "Fix report chart x-axis label overlap; replace window.prompt()
dialogs"); the bucket-list half was not.

**Themes and viewport.** Criterion 26 (dark mode) was not exercised at all. Criterion 27 is partial:
the chart's re-measure was built and verified at desktop widths, and the browser was never narrowed
to 375px on this screen. The pivot table's horizontal scroll inside its card was not checked.

**Pivot and drill mechanics.** Criteria 12, 13, 14, 16, 18, 19, 20, 21, 22 untested. Criterion 19's
positive control is *expected to fail* on the evidence in QA-07 (the `[disabled]` binding), and
criterion 22 (Escape closes the drawer) corresponds to synthesis gap 13, which is open.

**Range limits.** Criterion 11 (the 50,000-row cap, the `capped` pill, and that the retained rows
are the most recent ones) was not exercised -- this population is three orders of magnitude short of
provoking it.

**Chart kinds.** Criterion 23 -- each of the ten kinds drawing without a console error, legend
matching -- was not walked systematically. QA-01, QA-03, QA-08 and QA-09 each touched a specific
kind for a specific reason.

**Backend and component tests.** Criteria 42 and 43 untested, and this is the uncomfortable one:
many tests were added across the session (backend 587 passing, frontend 580 passing), but **none of
the three files synthesis gap 16 names** -- `RunReportQueryTest.java`, `reports.spec.ts`,
`report-chart.spec.ts`. The tenant-isolation assertion on `runReportRows`, which is the whole point
of gap 16, still does not exist -- next to QA-10 having just changed that query's `select` list.

**Still open from the synthesis gap table after this pass:** 1, 2, 3, 4, 6, 11, 12, 13, 14, 18, 19,
20; plus the radar half of 8, the `[disabled]` half of 9, the server half of 5, and the three test
files of 16.

---

## Summary

Thirteen defects were found and, contrary to the phase's own rule, fixed the same day. Six are
**major**: the default range's chart was unreadable (QA-01), the donut printed 56%/44% against a
real 92%/8% (QA-03), the headline duration figure was 99.4% dispatcher wait (QA-04), the screen had
no filter of any kind (QA-05), a long range kept the wrong end of the axis (QA-06), and a platform
admin's report merged every workspace unlabelled (QA-10). Seven are **minor**: a caption asserting a
month of activity on one day's data (QA-02), zero and no-data rendering identically (QA-07), an
invisible area series (QA-08), an axis that flipped on a hyphen (QA-09), a retry that could never
succeed (QA-11), a duplicated request (QA-12), and a capability withheld by a stale comment (QA-13).

The pattern across the six majors is worth naming, because it is not "the code was buggy". Five of
the six were **honest arithmetic presented under a name that meant something else** -- a mean of
means called a proportion, a queue wait called a duration, an axis length called a count of days, a
merged population called a report. Only QA-01 is a rendering defect in the ordinary sense. A screen
whose purpose is to let a reader ask their own questions fails in this particular way, and a QA pass
on the rest of this feature should be looking for more of it rather than for crashes.

Against the checklist's 43 criteria, **8 were exercised, several only partially**, and 35 are
untested. The untested set includes every security criterion, every cross-tenant criterion, every
export criterion, both presentation criteria and both test criteria. `reports` is materially better
than it was this morning and it is **not done**: the first item on `synthesis/reports.md`'s own
ordering -- make `submit` an administrator's action, behind a real address guard -- has not been
started.
