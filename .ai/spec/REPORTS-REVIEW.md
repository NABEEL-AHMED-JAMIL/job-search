# Reports / Analytics — end-to-end review

Review carried out 2026-09-09 against the running stack. Findings first, then what was done about
them. Nothing here is inferred from reading alone: every claim was checked by running something.

## Scope: there are two modules, not one

| | `/reports` | `/analytics` (Analytics Studio) |
|---|---|---|
| Reads | pipeline job runs from Postgres | datasets in object storage |
| Age / size | older, ~3,000 lines, own pivot + chart stack | current, widget + saved-analysis architecture |
| Widget architecture | **no** — bespoke charts per view | yes — dashboards of widgets referencing saved analyses |

The bucket-driven half of this review is Analytics Studio. `/reports` is reviewed below but was not
migrated; that is a deliberate stop, explained at the end.

## Findings

### F1 — Dashboards expose four widget types; the chart library has more (**CLOSED 2026-09-09**)
`WidgetVisualization` is `'table' | 'ranked' | 'bar' | 'donut'` (`analytics.service.ts:626`), and
the dashboard picker offers exactly those four (`dashboard.ts:427`). Meanwhile
`shared/charts/` already contains `day-series` (time series / line), `split-bar` (stacked),
`histogram` and `heatmap`, and the Canvas itself supports `histogram` and `pivot`.

**So the gap is wiring, not drawing.** Line, area, stacked-bar and histogram widgets are mostly a
matter of admitting them to the vocabulary and dispatching on them.

### F2 — There is no KPI / metric card (**CLOSED 2026-09-09**)
A single-figure analysis ("Total revenue") renders as a one-row, one-column table. Every executive
summary in the new catalogue has this shape, and each is a table where a number belongs.

### F3 — No date-granularity grouping (**CLOSED 2026-09-09**)
`AnalysisRequest` has dimensions, measure, filters, topN, sort, drillPath — and **no grain**. There
is no `date_trunc` anywhere in `AnalysisQueryBuilder`. Grouping a date column therefore yields one
bucket per day and no way to fold them, so **"revenue by month" is not expressible** over a user's
own dated file.

**Now closed properly.** A closed `Grain` enum (DAY, WEEK, MONTH, QUARTER, YEAR) and a list
index-aligned with the dimensions, compiled to `date_trunc`. Index-aligned because a drill replaces
a dimension *by index* — the grain has to travel with the slot. The Canvas offers a bucket picker
beside any date column and none beside a text one, and the heading names the grain, because a month
renders as the first of that month and "by order_date" over `2024-07-01` reads as one day.

Verified over the 250,000-row dataset: 730 days, 105 weeks, 24 months, 8 quarters, 2 years — every
one summing to `103,909,527.58`, the same as the ungrained total.

The denormalised `order_month`/`order_year`/`order_quarter`/`order_weekday`/`order_hour` columns
stay in the sample data: they are what a warehouse does anyway, and they exercise a different path
(a plain grouping over a text column) than the grain does.

### F4 — CSV money is read as DOUBLE; Parquet keeps DECIMAL (**CLOSED 2026-09-09 for the analysis path**)
DuckDB's CSV sniffer types a column of `1999.20` as `DOUBLE`. Over the 250,000-row sample:

| Format | `SUM(amount)` |
|---|---|
| Parquet | `103909527.58` |
| CSV | `103909527.57999855` |

Under two thousandths of a penny here, and it **grows with the row count**.

**Fixed for the structured analysis path.** `SUM` over a binary-float column is routed through
`CAST(CAST(x AS VARCHAR) AS DECIMAL(38,15))`. DuckDB renders a DOUBLE to text as the shortest
decimal that round-trips, and text→DECIMAL never touches binary floating point — so this recovers
the number the writer wrote. Verified live: both formats now return `103909527.58`.

**The read was deliberately NOT changed**, and that was measured rather than assumed. Steering the
sniffer with `auto_type_candidates` types a column of `3.14159265358979` as `DECIMAL(18,3)` and
reads it as `3.142` — a 0.013% error manufactured to fix a 1e-9 one — and turns a file that reads
today into a hard failure when a large value appears past the sniff sample.

**Still open, narrowly:** `AVERAGE` cannot be fixed this way — `avg()` over a DECIMAL still returns
DOUBLE in 1.1.3 — and raw SQL through the SQL console is the reader's own statement and is not
rewritten. `MIN`/`MAX` never accumulated error.

### F5 — No dashboard-level filter (**CLOSED 2026-09-09**); cross-widget click (**CLOSED 2026-09-10**)
Each widget carried the filters frozen into its saved analysis, with no filter bar over the board.

**A board filter now exists.** Session-only rather than persisted — the smaller honest change, and
a persisted one would narrow the board silently for the next person who opens it, when a dashboard
is described in its own schema as the thing made to be shown to somebody who did not build it.

Scoped to **one dataset**, because a condition naming a column another file lacks is a hard refusal
from the server — an unscoped bar would turn half a board into error tiles. Every tile on the
chosen dataset is narrowed; **every other tile says on its face that it was not, and why** — a
board that looks uniformly narrowed and is not is the failure the scoping exists to prevent.

The saved and board filters are ANDed and **nested, never flattened**: spreading a saved
`region = north OR region = south` alongside a board condition turns it into
`north OR (south AND …)`, a different question wearing the same words, drawn as a perfectly
ordinary chart. Tested as a pure function because that failure has no visible symptom.

**Editing the bar runs nothing.** An explicit Apply reuses the existing serial queue — ten widgets
is ten governed queries against a server that runs four at a time.

**Cross-widget click now works, and most of the work was in refusing it.** `Mark` carries
`operands` — the RAW value behind each dimension, with its column — because the drawn name is not
a filter operand: dates are shortened, decimals are trimmed, and several dimensions are joined
with ` · ` into a string no column holds. Clicking a bar fills the board filter bar with those
operands and applies once, which is the same cost as pressing Apply, and opens the bar so the
reader ends up looking at a filter they can read, edit and clear rather than at numbers that moved
for a reason with no trace on screen.

A mark is only an operand when it names **exactly one group**, and three ordinary cases mean it
does not. Each would draw a completely correct-looking chart answering a different question:

| case | what would go wrong |
|---|---|
| a **grained** date | the bar says `2024-03-01` and MEANS March; `booked_on = '2024-03-01'` returns a thirtieth of it. `AnalysisResult.grains` already travelled for exactly this reason |
| two rows **merged** into one label | `1E2` and `100` are one bar; filtering on either returns half of what is drawn |
| a **null** dimension | `field = null` is never true, so the whole board would narrow to nothing while looking like an ordinary filter |

Each unnarrowable bar is inert INDIVIDUALLY — not a button, not a tab stop — while the rest of
the chart works. Requiring every mark was the first shape of this and it was wrong: nearly every
Top-N report has a roll-up row, so "all or nothing" would have taken the feature away from most of
the boards that have it. The Canvas already treats that row exactly this way, one row at a time.

**One gap in it sent a field back to the server.** The roll-up was identified by its LABEL, which
is all the response carried — and a dataset is entitled to contain a value genuinely spelled
"Other". `AnalysisService` had the exact answer all along (its pivot builder keys on the row
indices, after a label collision there once lost a measured 500 out of a 740 total) and simply
never sent it. `AnalysisResultDto.rollupRows` now does, omitted entirely when nothing rolled up;
both the dashboard and the Canvas use it and keep the label as the fallback.

Fourteen unit tests, three guards proved load-bearing by mutation, and one Playwright spec that
clicks a real bar on report 05 against the live stack: the roll-up bar is disabled, the real bar
fills `sub_category = Laptops` into the board filter, and the board comes back narrowed to one.

### F6 — Widget states exist, but only per board (**partly wrong — corrected**)
`dashboard.ts` has `loading` and `error` signals at the board level and per-widget error text.
**My original claim that a slow board "shows a static page" was wrong** — seen live, the board
renders `Running 4 of 5 — Completed revenue by month.`, and each pending tile says
`Waiting its turn. Widgets run one at a time.` That is better than I credited. What is genuinely
missing is a per-tile skeleton in place of the text.

### F7 — `/reports` does not use the widget architecture (open, deliberate)
It predates it, reads a different data source, and is ~3,000 lines with its own pivot engine and
tests. Migrating it is a rewrite of a working module against a different domain, and nothing found
in this review says it is broken.

## What was done

| # | Action | Evidence |
|---|---|---|
| 1 | **Realistic sample dataset generated and uploaded** | 250,000 rows × 21 columns, 31 MB CSV + 8.9 MB Parquet at `etl-bucket/analytics-samples/orders.{csv,parquet}`, written through the platform's own storage service |
| 2 | **The engine's arithmetic independently validated** | `ReportNumbersValidationIT` — 10 tests, all passing |
| 3 | **20 reports built, 106 widgets** | `OrdersReportsE2EIT` — every widget runs against the real object |
| 4 | **5 earlier reports over the 150k fixture** | `AnalyticsReportsE2EIT` — 27 widgets |
| 5 | **Report-building machinery shared** | `ReportBuildingSupport`, extracted when the second catalogue arrived |

### The validation, specifically

The CSV is pulled back out of MinIO and parsed **by hand in plain Java** — `BufferedReader`, split
on comma, `BigDecimal` — with no DuckDB, no SQL and no shared code with the engine. Ten assertions
compare that second opinion against the engine: row count, `SUM`, `MIN`, `MAX`, `AVG`, revenue by
category *for every group*, count by region and by status *for every group*, and that nulls are
counted as nulls rather than as zero.

`BigDecimal` and not `double`, deliberately: 250,000 money values summed as doubles accumulate
error in the last places, and the disagreement would look exactly like an engine bug. That
discipline is what surfaced F4.

### The 20 reports, and why these twenty

Each is a different *shape* of question, not a different subject: no dimension / one / two;
count / sum / average / min / max / median / distinct; unfiltered / single filter / ANDed group;
Top-N and Bottom-N; ordered by measure and ordered by dimension. Four assertions target the
combinations a single-shape smoke test never reaches — two-dimension groupings reaching the
response, Bottom-N actually returning the smallest, and an ANDed filter narrowing more than either
half.

## What F1/F2 became

Eleven kinds, not four: single figure, table, ranked bars, bars in order, stacked bars, line,
filled area, share of the total, histogram, scatter, comparison. Four new components; `histogram`
wired in from the existing library; stacking done through `bar-chart`'s existing segment support.

Every kind carries the reason it cannot draw a given result, which is the half worth having. It
also exposed two bugs that four kinds had hidden: `drawn()` NAMED its four, so every new kind was
offered, stored, shown as selected and silently drawn as a table; and the row count always counted
the table's eight rows, so a 24-bar chart read "8 of 24 rows shown".

## Still open

**One item, and it is a decision rather than a task.**

1. **F7 `/reports` migration** — not taken, deliberately. It predates the widget architecture,
   reads a different data source, and is ~3,000 lines with its own pivot engine and tests.
   Nothing in this review says it is broken, and rewriting a working module against a different
   domain is not a fix. Revisit it when something it actually does is wrong.

**This section used to list six things, and five of them had been closed without it being
updated** — which is the failure mode a review document has: it is read as current and is only as
current as its last edit. Closed since, each with its own section above and its evidence there:
F3 date granularity (the `Grain` enum and `date_trunc`), F4 CSV decimals (the exact-decimal CAST
in `AnalysisQueryBuilder`), F5 board filters AND cross-widget click, the summary widgets
(`dimensionSummary` / `trendSummary` / `distributionSummary` — 14 widget kinds now, from four),
and F6's per-tile skeleton, which is in `dashboard.ts` beside the "Waiting its turn" text and is
`.pulse` rather than `animate-pulse` so it honours `prefers-reduced-motion`.

The line that used to sit here saying UI/UX work "has **not** been started" was stale in the same
way. See `PROGRESS.md`: visual consistency, accessibility, keyboard navigation and responsive
behaviour are each closed with evidence — axe at WCAG 2.1 A/AA over ten tabs in BOTH themes, a
roving tabindex that turned ten tab stops into one, and every E2E run checked at 390x844 rather
than once by hand.
