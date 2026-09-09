# Dataset Workspace UX — Kaggle-Inspired, Enterprise-Oriented

The goal is to provide the useful dataset-preview experience users recognize from modern data platforms while adding enterprise analytics capabilities. Do not copy proprietary UI pixel-for-pixel.

## Header
Show:
- dataset name
- provider
- bucket/container
- path
- format
- file count
- size
- rows
- columns
- last modified
- refresh/profile action

## Details view
Top summary:
- row count
- column count
- missing values
- duplicate rows
- quality score
- data size

Include small distribution/summary visuals where useful.

## Compact view
A dense table-oriented mode:
- column name
- type
- sample
- null %
- distinct %
- key metric
- quality indicator

## Data view
Spreadsheet-like server-side table:
- pagination
- column resize
- sorting
- filtering
- search
- column visibility
- copy cell/value
- horizontal scroll

## Columns view
For every column show:
- name
- semantic/data type
- count
- null count
- null %
- distinct count
- distinct %
- min/max
- mean
- median
- standard deviation
- percentile values where applicable
- top values and frequency
- small distribution visualization
- quality warnings

Do not show incompatible metrics as zeros. Show “N/A” when a statistic does not apply.

## Profile view
Show aggregate distributions and data-type summaries.

## Quality view
Show actionable warnings and drill into affected records through a filtered data view.

## Interaction principle
Any summary value should be clickable where meaningful. Clicking a department in a count analysis should create a dataset filter and update the visible table/charts.

## Responsive behavior
Desktop-first for analytics, but usable on smaller screens. Avoid excessive nested cards.
