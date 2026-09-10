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

### F3 — No date-granularity grouping (open, and the most limiting)
`AnalysisRequest` has dimensions, measure, filters, topN, sort, drillPath — and **no grain**. There
is no `date_trunc` anywhere in `AnalysisQueryBuilder`. Grouping a date column therefore yields one
bucket per day and no way to fold them, so **"revenue by month" is not expressible** over a user's
own dated file.

Worked around *for the sample data only* by denormalising `order_month`, `order_year`,
`order_quarter`, `order_weekday`, `order_hour` into the file — which is what a warehouse does
anyway. **The engine gap is untouched**: a reader pointing the Canvas at their own dated CSV still
cannot ask the question.

### F4 — CSV money is read as DOUBLE; Parquet keeps DECIMAL (open, found by validation)
DuckDB's CSV sniffer types a column of `1999.20` as `DOUBLE`. Over the 250,000-row sample:

| Format | `SUM(amount)` |
|---|---|
| Parquet | `103909527.58` |
| CSV | `103909527.57999855` |

Under two thousandths of a penny here, and it **grows with the row count**. Nothing in the product
tells a reader that a financial total over CSV is inexact in its last places. Pinned by
`ReportNumbersValidationIT#csvSumsMoneyAsAdoubleWhileParquetKeepsItExact`, which asserts the
*difference* rather than a tolerance — so the day the CSV path starts reading DECIMAL, that test
fails and says so.

### F5 — No dashboard-level filter, and no cross-widget synchronisation (open)
Each widget carries the filters frozen into its saved analysis. There is no filter bar over a
dashboard and no way for one widget to narrow the others. (Cross-filtering exists *inside* the
Canvas — Canvas → Data tab — and was built earlier this session; dashboards have nothing.)

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

1. **F3 date granularity** — the most limiting, and the one users hit on their own files
2. **F5 dashboard filters** — a filter bar, and cross-widget narrowing
3. **F4 CSV decimals** — a correctness note at minimum, a typed read at best
4. **Summary widgets** — dimension / trend / distribution summaries, and a filter widget
5. **F6 per-tile loading skeleton**
6. **F7 `/reports` migration** — only with a decision that it is worth a rewrite

UI/UX work (grid layout, spacing, typography, dark mode) has **not** been started.
