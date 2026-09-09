# Testing & QA

## Unit
Test:
- storage adapters
- dataset resolver
- schema detector
- profile calculator
- quality rules
- analysis query builder
- filter compiler
- query lifecycle
- export service
- authorization

## Integration
Test:
- S3
- MinIO
- Azure Blob
- DuckDB
- PostgreSQL
- Redis if used
- Kafka integration where applicable

## Frontend
Test:
- dataset browser
- tabs
- data grid
- column metrics
- filter builder
- dimension selector
- drill-down/up
- chart interactions
- SQL editor
- query cancellation
- export
- dashboard

## Security tests
- cross-tenant dataset access
- unauthorized storage connection
- unauthorized export
- guessed dataset IDs
- query referencing unauthorized datasets

## E2E scenarios
1. S3 CSV → preview → profile → analysis → export.
2. MinIO CSV → columns → filters → drill-down.
3. Azure Parquet → SQL → chart → dashboard.
4. Multiple files → logical dataset → join.
5. CSV → benchmark → Parquet → benchmark comparison.
6. Large query → timeout/cancel.
7. Tenant A cannot access Tenant B.
8. Write-back to all three providers.

## Regression
Every bug discovered in implementation becomes an automated regression test where practical.
