# Five reports, twenty-seven widgets

Built 2026-09-09 against the real 150,000-row dataset at
`etl-bucket/analytics-benchmark/sales-10mb.csv` (columns: `id`, `region`, `customer`, `amount`,
`booked_on`, `note`). These are not fixtures — they are rows in `analytics_dashboard`,
`analytics_dashboard_widget` and `analytics_analysis` on the live development database, owned by
`admin@platform.local`.

The point of them is not coverage. It is the module **used** rather than unit-tested: five
dashboards a sales team might plausibly keep, where every widget has to survive being opened.

## The reports

| id | Report | Widgets | What it is for |
|---|---|---|---|
| 1034 | **Sales by region** | 6 | Where the money comes from, six ways over the same five regions |
| 1035 | **Customer performance** | 5 | Who buys, how often, how much — capped at the top ten so it stays readable |
| 1036 | **Booking activity** | 5 | What the order book looks like over time |
| 1037 | **Revenue quality** | 5 | The tails: the very large, the very small, the incomplete |
| 1038 | **Executive summary** | 6 | Six numbers for somebody who has ninety seconds |

### 1034 — Sales by region
`SUM(amount)` bar · `COUNT_ROWS` donut · `AVERAGE(amount)` ranked · `MEDIAN(amount)` bar ·
`MAXIMUM(amount)` table · `MINIMUM(amount)` table — all grouped by `region`.

### 1035 — Customer performance
Top 10 by revenue (ranked) · top 10 by order count (ranked) · top 10 by average order (bar) ·
`DISTINCT_COUNT(customer)` over the whole file (table) · distinct customers per region (bar).

### 1036 — Booking activity
Revenue, order count, average order value, busiest dates and active customers — all by
`booked_on`, each capped at Top-N 20.

### 1037 — Revenue quality
High-value revenue by region (`amount > 900`) · high-value order count (donut) · low-value order
count (`amount < 100`) · top customers among high-value orders · orders carrying a note by region.

### 1038 — Executive summary
Total revenue · total orders · average order value · distinct customers · revenue by region
(donut) · top 5 customers (ranked).

## Every dimension is capped where it needs to be

`customer` and `booked_on` are high-cardinality — roughly 50,000 customers and 365 dates. Every
widget grouping by one carries a Top-N. A chart of fifty thousand bars is unreadable, and the
response is one nobody should have to receive.

## How they are verified

**`AnalyticsReportsE2EIT`** (`process/src/test/java/process/e2e/`) boots the whole application and
drives the real controllers. Four assertions, all passing:

| Test | What it proves |
|---|---|
| `everyWidgetOnEveryReportCanActuallyRun` | All 27 configurations posted to `/analytics.json/analyze` against real MinIO, and each returns rows. **This is 27 real DuckDB scans of a real object.** |
| `aReportComesBackWithItsWidgetsInOrder` | A dashboard that hands its widgets back unordered renders a different page every time |
| `everySavedAnalysisKeepsAConfigurationThatStillParses` | The round trip a dashboard makes on every open, since nothing is cached |
| `anotherWorkspaceCannotSeeTheseReports` | A tenant admin does not gain platform dashboards via the shared catalogue |

**`e2e/dashboards.spec.ts`** (Playwright) covers the half the Java suite structurally cannot: that
opening the page *draws* them. A tile that stored a good configuration and renders "could not be
read" looks identical in the database. One spec asserts opening a report puts `/analyze` requests
on the wire — the reference-not-cache decision checked rather than taken on trust.

## One design flaw the tests caught

The first draft of 1037 had a tile for **orders with no note**. Every row in this dataset carries
one, so it would have drawn an empty chart every time anybody opened the report. The
`produced no rows -- a widget that draws nothing` assertion caught it before it was saved. It is
now "orders carrying a note", which states completeness as a number people can see.

## Seeding more, or removing these

Seeding is behind two locks, and both are load-bearing — `@Rollback(false)` alone would make every
build write 27 rows into whatever database it was pointed at:

```bash
cd process
E2E_DATASOURCE_USERNAME=… E2E_DATASOURCE_PASSWORD=… E2E_LOOKUP_ENCRYPTION_KEY=… \
  mvn -o surefire:test -Dtest=AnalyticsReportsE2EIT#seedTheFiveReports \
  -Danalytics.seed.reports=true -DfailIfNoSpecifiedTests=false
```

They are left in place deliberately. To remove them:

```sql
DELETE FROM analytics_dashboard_widget WHERE analytics_dashboard_id BETWEEN 1034 AND 1038;
DELETE FROM analytics_dashboard        WHERE analytics_dashboard_id BETWEEN 1034 AND 1038;
-- the 27 analyses are named after their widget titles
```

## A note on connections, and why the tests use a second one

Every `storage_connection` row in this database has endpoint `http://host.docker.internal:9000`.
That resolves inside a container and **not on the host**, so a test JVM running here cannot read a
single one of them. The run tests therefore create their own row pointing at `localhost:9000`,
inside the transaction that rolls back — same bucket, same object, same resolver, engine and
governor; only the hostname differs. The seeded reports keep the real `etl-bucket` alias, because
they are opened by the deployed application, for which `host.docker.internal` is correct.
