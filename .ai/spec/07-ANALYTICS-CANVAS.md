# Analytics Canvas — Dimensions, Measures, Filters and Drill-Down

## Purpose
This is the advanced analytics layer requested for the Dataset Workspace.

## Concepts
### Dimension
A grouping/category field, such as:
- department
- country
- status
- product
- date

### Measure
A value or derived metric, such as:
- row count
- distinct users
- revenue sum
- average amount

## Dimension limits
Support:
- one dimension
- two dimensions
- three dimensions

Examples:
```text
1D: Department → COUNT(user_id)
2D: Department × Status → COUNT(user_id)
3D: Department × Status × Location → COUNT(user_id)
```

## Measure menu
- Count rows
- Count non-null
- Distinct count
- Sum
- Average
- Minimum
- Maximum
- Median/percentiles where supported

## Advanced filter builder
Filters support:
- equals / not equals
- contains / starts with
- greater/less than
- between
- in / not in
- is null / not null
- date range
- relative date
- numeric range

Support nested AND/OR groups.

## Cross-filtering
Clicking a result applies a filter to:
- data table
- other compatible charts
- KPI cards
- subsequent dimension analyses

Show active filters as removable chips.

## Drill-down
Example:
Department → Engineering → Location → Chicago → Status → Active.

Each drill action narrows the current analytical context.

## Drill-up
Provide breadcrumb navigation:
All Users / Department: Engineering / Location: Chicago

Clicking a previous breadcrumb removes later filters.

## Pivot-style analysis
For two dimensions, support row dimension × column dimension with aggregation in cells.

## Top-N
For high-cardinality dimensions:
- Top 10
- Top 25
- Top 50
- custom N
- Other bucket

## Query generation
Generate safe backend analytical requests from a structured analysis model. Do not construct raw SQL by string concatenation with untrusted values.

## Result interactions
Every result row should carry enough context to reproduce its filter state.

## Saved analysis
Save:
- dataset reference
- dimensions
- measures
- aggregation
- filters
- sort
- top-N
- visualization type
- timestamp
- owner/tenant

This enables a saved analysis to be reopened without storing raw data.
