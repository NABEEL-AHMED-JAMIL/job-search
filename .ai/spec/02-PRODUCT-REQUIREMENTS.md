# Product Requirements

## Dataset workspace
A user can select any authorized S3, MinIO or Azure connection, browse a bucket/container and arbitrary folder/path, select one or many files, and open a dataset workspace.

## Supported formats
MVP: CSV, Parquet, JSON/NDJSON. Add XLSX/Arrow only when compatible with the existing stack and dependency policy.

## Workspace tabs
- Details
- Compact
- Data
- Columns
- Profile
- Quality
- Analytics
- SQL
- Charts
- Activity

## Core capabilities
- server-side preview
- schema inference
- statistical profiling
- dimension/measure analysis
- advanced filters
- drill-down/drill-up
- cross-filtering
- SQL
- joins
- charts
- dashboards
- exports
- write-back
- benchmarks

## Functional limits
All large operations must be bounded by server-side limits, timeout and cancellation. Sampling must be explicitly labeled.
