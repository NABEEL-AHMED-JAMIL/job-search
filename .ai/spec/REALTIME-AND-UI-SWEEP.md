# Live updates, the chart palette, and the widget tile — 2026-09-14

Five areas investigated in parallel and every factual claim verified against the running stack
before it was acted on. **32 findings survived verification**, 6 of them critical. This records
what was actually broken, what was fixed, and what was deliberately left.

The short version: **the socket was never the problem.** The transport was verified healthy end to
end — `/ws/info` answers 200 with the right CORS origin, `process_app` logs
`WebSocket CONNECT authenticated as admin@platform.local`, and there is not one `Refused SUBSCRIBE`
in the log. Destinations, the tenant suffix, the STOMP auth interceptor and the allowed origins are
all correct. Almost nothing was ever *published*, and the one screen that says "Live" had never been
wired to the socket at all.

| area | verified findings | what it actually was |
|---|---|---|
| websockets | 8 | the platform's own status changes announced nothing; live logs polled once and stopped |
| chart colour | 9 | the "chart palette" was the status ramp, four of six values byte-identical |
| widget table | 3 | rows 9..N were fetched, parsed, and thrown away with no route to them |
| widget sizing | 6 | height was the literal `180` written four times, reaching 4 of 16 kinds |
| more widgets | 6 | two-dimension results had four outcomes; share stopped at six categories |

---

## 1. Status changes that told nobody

`publishStatus` had exactly one caller: `NotifyServiceImpl.changeState`, reachable only from the
worker callback `POST /changeState/...`. So a status moved on screen **only when an external Python
worker reported in.** Every transition the platform makes to itself was silent:

| site | transition |
|---|---|
| `ProducerBulkEngine:59` | → `Queue` ("Run now") |
| `ProducerBulkEngine:170` | → `Queue` (scheduler picks a job up) |
| `ProducerBulkEngine:348` | → `Start` (dispatch succeeded) |
| `ProducerBulkEngine:365` | → `Failed` (every dispatch failure) |
| `ProducerBulkEngine:135` | → `Interrupt` (stalled-run reconcile) |
| `BulkAction:215` | → `Missed` |
| `MessageQServiceImpl:153/178/212` | Failed / Interrupt / any |

**Fixed at the choke point, not at the callers.** All nine writers go through
`BulkAction.changeJobStatus`, so the publish lives there — a tenth caller cannot forget it.

The publish is **unconditional, including a repeat of the status already held**, and that is
load-bearing. `Start → Start` and `Running → Running` are legal transitions
(`NotifyServiceImpl.isValidStatusTransition`) because that is how a worker says it is still alive,
and the jobs table advances its stall clock on each one. A "only publish when the value changed"
guard — which was written and then removed before shipping — would have switched the heartbeat off
and made every healthy long run report as stalled. `BulkActionJobEventTest` fails if it comes back.

`NotifyServiceImpl`'s own explicit publish was removed: `changeJobStatus` now announces the same
transition, and no consumer reads the extra `jobQueueId`/`message` the richer call carried.

## 2. "Live" logs that polled exactly once

Two independent defects on one screen.

**The poll never re-armed.** The effect read `autoRefreshing()` — `live() && stillRunning()` — which
stays `true` for the whole of a running job. Every load replaced `run()` with a fresh object,
`stillRunning()` recomputed to the same `true`, the computed therefore notified nobody, and the
effect never ran again. The screen polled once, five seconds after opening, and then sat still
under a green "Live" badge. The re-arm now happens from the completion of each load, which is what
the comment above it always claimed.

**`job.log` was published and consumed nowhere.** The server had always announced each line as it
was written; nothing on the client subscribed. It does now, and appends as lines arrive. The next
poll replaces the list wholesale, so a line that arrives twice cannot persist as a duplicate — the
socket is an early view of the same rows, not a second source of truth.

## 3. `publishChanged` had no callers anywhere

Declared, typed on both sides, branched on by the jobs table — and never called, so an edit, toggle
or delete made in one tab stayed invisible in another. Now announced from create, update, toggle
and delete in `SourceJobServiceImpl`, **after commit** via `publishChangedAfterCommit`. That detail
matters: the client answers these events by re-reading the row, and a read started inside the
writing transaction is served the old values — the exact staleness the push exists to remove,
arriving faster and looking authoritative.

## 4. Timestamps, and a wrong diagnosis I shipped before catching it

**The investigation's finding here was wrong, and so was my first fix.** Recorded in full because
the mistake is more instructive than the fix.

The claim was that the container runs UTC (`TZ` unset, `docker exec process_app date` reports UTC)
while the browser runs CDT, so every naive `LocalDateTime` on the wire was a UTC instant being read
as a local one — five hours in the future. The supporting evidence was
`source_job.last_job_run = 2026-09-13 13:23:37 while the host clock reads 15:38 CDT`, which
compares a timestamp from the **previous day** to "now" and calls the difference skew. It proves
nothing. I acted on it without checking the direction.

What is actually true: `ModelApplication.main` pins the application's own zone —

```java
TimeZone.setDefault(TimeZone.getTimeZone("America/Chicago"));
```

— so the JVM starts UTC from the OS and the application immediately overrides it. Every
`LocalDateTime` it writes is a **Chicago wall clock**. That is why `date` inside the container and
the application's own log lines disagree by five hours, and why a `jshell` started in the same
container reports `Etc/UTC` while the running app does not. Verified directly: rows the container
wrote during a Playwright run read `17:20:45`, and that run happened at 17:20 CDT.

So reading naive timestamps as UTC made every one of them five hours older than it was. The
visible consequence was a **false stalled-run warning**: a job stamped `17:02` CDT, read as `17:02`
UTC, looks five hours idle, and the jobs list reported a run as stalled seconds after it started.

`core/instant.ts` now reads an offset-less timestamp in the zone the server pins — not as UTC, and
not as "wherever the reader happens to be", which is right only for a viewer who shares the
server's zone. A timestamp that states an offset is taken at its word, so the real instants
`JobEventPublisher` now sends over the socket are unaffected, and the same moment arriving by REST
and by socket resolves to one instant.

Two implementation notes worth keeping: the zone offset is measured against the instant **floored
to the second**, because `formatToParts` resolves no finer and the milliseconds a `LocalDateTime`
carries otherwise fold into the "offset" (`.271` came back as `.813`); and the offset is resolved
once more against the resulting instant, so a reading near a daylight-saving boundary settles on
the offset actually in force.

**Why the tests did not catch the original defect, or my wrong fix:** every existing timestamp test
built its input with `toISOString()`, which appends a `Z`. The REST API never sends one. The suite
was exercising a format the code never meets in production, so both the naive path and its meaning
were entirely untested.

**Still open:** the REST API serialises `LocalDateTime` with no offset, so the client has to be
told out-of-band what zone that is. `SERVER_ZONE` is that out-of-band knowledge, and it is a
constant that must be changed by hand if `ModelApplication` ever changes. Emitting offsets on the
wire is the real fix and is a Jackson change across many DTOs.

## 5. The chart palette was the status ramp

Four of the six light values were **byte-identical** to semantic tokens — `--chart-2` *was*
`--color-ok-500`, `--chart-3` *was* `--color-warn-500`, `--chart-4` *was* `--color-crit-500`. On the
Queue screen a duration bucket labelled "30s–2m" was painted the exact green of the `Completed`
pill in the table below it, and "2–10m" the `Missed` amber. A reader cannot be expected to know
which greens mean something.

It also failed as a palette on its own terms. Simulating deuteranopia and protanopia and computing
CIEDE2000: dark `--chart-1` and `--chart-5` were **ΔE00 0.4** apart for a deuteranope — the same
colour. `--chart-0` was a near-black at 14.67:1 while its neighbours sat at 5–6, so the first series
in every chart read as ink rather than as data.

Replaced with **eight** hues on the two arcs the status families leave free (176–268 and 298–348),
every one at least 12 ΔE00 from the nearest semantic token, spaced 20–24° of hue **and** laddered on
L\* — lightness being the one channel both deuteranopia and protanopia preserve.

Eight rather than six because three call sites indexed the ramp with no upper bound, so a seventh
category silently repeated the first. The count now lives in one exported constant, `CHART_SLOTS`,
because it had been written as a bare `% 6` in six places and the two new colours would otherwise
never have been drawn.

Two related colour defects fixed with it:

- **The main dashboard's outcome bar coloured statuses by array POSITION**, so a row whose first
  status happened to be `Failed` painted it with slot 0 while the `Failed` pill beside it stayed
  red. This is the same bug the analytics board had already fixed and documented.
- **`--accent-text` was the dimmest word in the navigation.** After the monochrome rebrand it
  resolved to `--color-brand-300` (`#99a1af`), byte-identical to `--text-muted`, measuring 6.82:1 on
  the header — while every *inactive* label beside it used `--text-secondary` at 12.05:1. With no
  hue to carry it, an accent has only contrast; it is now the strongest step there is.

## 6. The widget tile

**Rows 9..N were already in the browser.** The server bounds a response at 100,000 cells; everything
under that arrives in one response and is fully parsed. `analysisView` then sliced to 8 and the rest
was garbage-collected on the same tick — and the caption under the tile told the reader, correctly,
that sixteen rows existed which they could not see. It was a dead end: no export, no dialog, no
route, and the Canvas cannot be deep-linked. Reading row 9 meant leaving the board, re-opening the
dataset by hand, and spending a second permit off a JVM-wide semaphore of four on the identical
query.

The cut now belongs to the tile rather than to the result, and "Show all rows" opens what is already
in hand. It issues no query, takes no permit, and writes nothing back — the board's rule that a
widget stores a reference and never a result is untouched. The partial-result banner and every note
are repeated inside the dialog, because an expanded table is the one place a truncated result would
otherwise read as the whole thing.

**Height and caption** are stored in the existing `widget_config` TEXT column — already on the
schema, the POJO and both sides of the wire, round-tripped on every edit, and never written to by
anything. No migration. Height is clamped 120–600 **on read**, because the stored value is
unvalidated JSON that a widget carries around. `LineChart` and `ScatterPlot` were given real height
inputs; without them the control would have done nothing on 12 of the 16 kinds.

**The cross-tab was the one kind with no limit at all**, so a single tile could be hundreds of rows
tall and push every other tile off the board. It is capped like every other table, and counted in
its own units: a grid of four regions over six months says nothing about the 150,000 rows behind it,
and counting marks printed "0 of 24 rows shown" under a grid showing all twenty-four.

## 7. More widget kinds

Two added, and one bug found while adding them.

- **`rankedShare`** — share of the total for more than eight categories. The ring was the only share
  chart and it refuses past the colours the palette can tell apart, so "what share does each of
  these forty customers carry" had no chart at all. Bars label themselves, so the colour limit does
  not apply; the conditions that must hold are the ones the ring already tests, minus the slice
  count.
- **`cumulative`** — a running total along the dimension, on the existing `LineChart`, from the
  marks already drawn. Refused over a rank order, which would draw the shape of the sort rather than
  of the data.
- **`line`, `area` and `trendSummary` were offered over two-dimension results.** `stacked` and
  `shareStacked` read `dimensionCount` two lines below them and these did not, so a 2-D result
  reached them as interleaved categories — jan/north, jan/south, feb/north, feb/south — and drew a
  sawtooth between two unrelated series. The trend summary was worse: it stated a *number*, the
  "change" between two points of that interleaving.

## 8. Motion the reader asked not to see

Three named animations honoured `prefers-reduced-motion` — `.spin`, `.pulse` and `.typing` — and
nothing else did. Those three are a rounding error next to the actual motion in this application:
every colour fade, width tween and height transition still played in full for someone with
vestibular sensitivity who had asked the operating system for less. Now handled globally, with
durations collapsed to 0.01ms rather than 0s so a `transitionend` listener still fires.

This surfaced through an **intermittent** contrast failure, which is worth recording because the
first two explanations were both wrong. axe runs the instant a tab is clicked, so it can measure an
element part-way through a `transition-colors` — it reported 1.41:1 for `#7d828a` on `#989da4` on a
`.pill-solid-brand` whose settled values are `--color-ink-300` on `--color-ink-950`, about 16:1, and
neither measured colour exists in either theme. It reproduced roughly one run in two, and only when
the whole file ran; in isolation it passed every time. The two contrast specs now ask for reduced
motion, so they measure the colours a reader actually sees instead of a frame of the animation.

**Stacked bars had no legend.** Six colours keyed on category, with the mapping stated only inside
each bar's `title` attribute — mouse-only, absent on touch, not read out in order. The chart encoded
its second dimension in colour alone, which is what WCAG 1.4.1 is about.

---

## 9. The test suite was running real jobs

Found by chasing a stalled-run warning that turned out to be the false positive from section 4 —
but the job underneath it was genuinely executed, and should not have been.

`src/test/resources/application-e2e.properties` has set `process.scheduling.enabled=false` since the
E2E profile was written. **Nothing in the codebase reads that property.** So every end-to-end run
booted the whole application on a developer's machine with `@EnableScheduling` live, and five
seconds later `ProcessCron.addJobInQueue` enqueued and started every DUE JOB in the shared
database. There is no worker listening to a test context, so each one failed.

One run dispatched and failed **22 of a tenant's jobs** — `CSV to Postgres demo job`,
`Postgres to CSV demo job`, the `report-history` set, the `F768945` partition jobs. Clusters of
exactly 22 simultaneous runs appear in `job_queue` on 2026-09-11 (three times), 09-09 (twice) and
09-08: this has happened on every E2E run for at least a week.

All three crons now carry
`@ConditionalOnProperty(name = "process.scheduling.enabled", havingValue = "true", matchIfMissing = true)`
— absent means enabled, so production is unchanged, and the container's scheduler was confirmed
still firing after the change. `SchedulingDisabledTest` asserts the bean is absent when the flag is
off, present when on, and present when the flag is missing; removing the guard fails the first.
A verified E2E run afterwards created **0** job runs where it previously created 22.

A property that is set and read by nobody is indistinguishable from one that works. This codebase
already had one of those — `AnalyticsHistoryCleanupCron` carries a comment about the same class of
bug — which is the argument for asserting the behaviour rather than trusting the file.

## Verification

- Backend **1242** unit tests, **102** E2E — 0 failures.
- Frontend **1248** unit tests — 0 failures.
- Playwright **45 passed, 0 failed** against rebuilt containers.
- Every fix mutation-proven: the fix was reverted and the test confirmed to fail. The heartbeat
  guard, the timezone read, the two-dimension refusal, the legend's keying and the row count each
  have a test that fails without them.

## Two process faults worth recording

**A test-data dependency that reads as a regression.** `dashboards.spec.ts` and `appearance.spec.ts`
assert against **real database rows** seeded by two opt-in Java tests behind
`-Danalytics.seed.reports=true` (`AnalyticsReportsE2EIT#seedTheFiveReports` and
`OrdersReportsE2EIT#seedTheTwentyReports`). Those rows had been wiped, and 19 specs failed in a way
that looks exactly like a UI defect. They were re-seeded as ids 1221–1245. Check the table before
diagnosing such a failure.

**A spec that restated a number the code owns.** `dashboards.spec.ts` asserted `toHaveLength(14)`
with the comment "the original four, seven chart kinds, and three summaries". It was already wrong
by two — `shareStacked` and `pivot` had been added and the sentence had not — so it failed on
whatever change ran next and read as that change's regression. The kind list moved to
`widget-kinds.ts`, with no Angular import so the Playwright suite can import it; the picker and the
test can no longer disagree.

## Left open, deliberately

- **Full WCAG 1.4.11 on card edges.** A card's boundary measured at most 1.24:1; it is now 1.47:1
  (light) and 1.60:1 (dark) by pointing `.card` at `--border-strong`. The 3:1 the guideline asks of a
  *meaningful* boundary would be a hard outline around every tile — a different design rather than a
  fix to this one, and the grouping is also carried by spacing and by each card's own heading.
- **A null-tenant job publishes nothing.** `publishStatus` and `publishLog` both return early on a
  null `tenantId`, so such a job reaches not even the cross-tenant admin feed that exists for that
  case. Not live today: every `source_job` row carries `tenant_id = 2364`.
- **A silently dead socket.** On an auto-reconnect the client replays a token that may have expired;
  the CONNECT is accepted *unauthenticated*, the SUBSCRIBE is dropped with no ERROR frame, and
  `connected` stays `true` — so the toolbar keeps showing a green "Live" dot forever.
- **Naive timestamps elsewhere.** `core/instant.ts` fixes the reading side for every path, but the
  API still serialises `LocalDateTime` on its REST responses. Emitting offsets there is a Jackson
  change across many DTOs.
- **`heatGrid`, `slope` and `pareto`** were specified and not built. The first two are the strongest
  remaining answers for two-dimension results; `pareto` needs an overlay axis and should be last.
