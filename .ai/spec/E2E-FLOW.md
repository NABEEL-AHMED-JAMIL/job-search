# End-to-end flow — http://localhost:4400/analytics

Walked by hand against the deployed stack on 2026-09-09, backend and frontend both rebuilt from
`platform-fixes-and-cleanup`, over the real 150,000-row fixture at
`etl-bucket/analytics-benchmark/sales-10mb.csv`. Every result below was observed, not inferred.

This doubles as the script for the automated E2E suite document 13 asks for: each numbered step is
one scenario, and the "what proves it" column is its assertion. The suite now exists, at
`scheduler1/next/e2e/analytics-workspace.spec.ts` — 8 specs, all passing (2026-09-09). Run it with
`E2E_PASSWORD=… npx playwright test` from `scheduler1/next`; it skips, rather than fails, when the
stack is not running.

Step 8's scenario is proven load-bearing by mutation: reverting the drill-up fix and redeploying
makes it fail at the "All rows" crumb assertion specifically.

## The flow

| # | Step | What proves it worked |
|---|---|---|
| 1 | Open `/analytics`, pick the **ETL Bucket · MINIO** connection | Folder list appears; the connection picker offers only connections the reader can actually read |
| 2 | Walk to `analytics-benchmark/`, click `sales-10mb.csv` | Header reads `150K rows · 6 columns · 9.3 MB on disk`; ten tabs render in three groups |
| 3 | **Data** → click the `amount` header twice | First row is `999.99` — the **dataset's** maximum, not the page's. `aria-sort="descending"` on that column alone |
| 4 | Type `cust-26813` into *Search all rows* | Count becomes **"3 of 150,000 rows"**; pager disappears; 3 body rows |
| 5 | Clear the search | Count returns to **150,000 rows / Page 1 of 1,500** — the dataset does not stay shrunk |
| 6 | **Canvas** → dimension `region`, measure `Sum` of `amount`, Run | 5 groups, `583 ms in the engine`, typed headers `region VARCHAR` / `amount_sum DOUBLE` |
| 7 | Set *then by* `customer`, click **Drill** on `east` | Crumbs read `All rows / region: east`; heading becomes "Sum of amount by customer"; 10,000 groups |
| 8 | Click the **All rows** crumb | Filter is removed — **but see finding 2** |
| 9 | **Compact** | One line per column: column, type, sample, null %, distinct %, key metric, quality. `≈` on estimated distincts, `(est.)` on an estimated median |
| 10 | **Quality** | "Nothing needs attention", followed by the five checks it actually ran and an explicit note that duplicate rows were not among them |
| 11 | `/analytics/dashboards` | "A page of saved analyses and saved queries, **re-run every time it is opened**" — the reference-not-cache decision, stated to the reader |

## Two defects this walkthrough found

**1. A note that had gone stale, and told the reader the product was less capable than it is.**
The Canvas filter panel said filters "do not narrow the Data tab's preview — that endpoint takes a
page and a size and *has no filter to give it*". True when the Canvas was built; false from the
moment the Data tab gained server-side filtering. The two narrowings are still separate, but the
reason is now that nothing carries a chip from one to the other, not that there is nowhere to carry
it to. **Fixed.**

**2. Drill-up does not return you to where you started.** Clicking the `All rows` crumb removes the
filter and leaves the dimension at the drilled one, so a reader who drilled `region → east → by
customer` and clicked the first crumb lands on "Sum of amount by customer" across all 50,000
customers rather than the five-region analysis they began with. The crumb promises a return and
delivers a different analysis.

The server is not at fault. `AnalysisQueryBuilder` derives the effective dimensions from the ROOT
dimensions plus the drill path (`:359-388`), so it restores correctly when handed a root. The client
loses the root: `analytics.ts:3186` sets `dimensions` from `response.data.dimensions`, which is the
EFFECTIVE post-drill grouping, so after one drill the client's root is already `customer` and
drill-up asks the server to restore something that is no longer there.

**FIXED 2026-09-09.** The root-versus-effective split now exists: `dimensions()` is the root the
request carries, `groupedBy()` is what the server reports as grouped, `effectiveDimensions()` is
what the screen and the drill controls read, and the reported grouping is dropped when the root is
re-picked. Confirmed in the running product — by region → drill to by customer → click the crumb →
back to five regions. Step 8 above now passes.

## What this flow does not cover yet

SQL console, Charts, Activity, export and write-back, save/reopen of an analysis, cancellation, and
the whole of the 100 MB tier. Document 13's eight scenarios also want a second provider and a
tenant-isolation pass, neither of which is in this walkthrough.
