# Implementation Checklist

## Discovery
- [ ] Existing repository inspected
- [ ] Existing storage abstraction identified
- [ ] S3/MinIO/Azure capabilities mapped
- [ ] Existing UI components mapped
- [ ] Existing auth/RBAC mapped
- [ ] Existing event architecture mapped

## Storage
- [ ] Generic read interface
- [ ] Generic write interface
- [ ] S3 verified
- [ ] MinIO verified
- [ ] Azure verified
- [ ] Path/prefix browsing
- [ ] Pagination
- [ ] Authorization

## Analytics
- [ ] DuckDB integration
- [ ] CSV
- [ ] Parquet
- [ ] JSON
- [ ] schema
- [ ] preview
- [ ] profiling
- [ ] quality
- [ ] SQL
- [ ] query cancellation
- [ ] joins

## Advanced analytics
- [ ] 1 dimension
- [ ] 2 dimensions
- [ ] 3 dimensions
- [ ] count
- [ ] distinct count
- [ ] sum
- [ ] average
- [ ] min/max
- [ ] filters
- [ ] AND/OR groups
- [ ] drill-down
- [ ] drill-up
- [ ] cross-filtering
- [ ] Top-N
- [ ] pivot

## Visualization
- [ ] table
- [ ] KPI
- [ ] bar
- [ ] line
- [ ] area
- [ ] histogram
- [ ] scatter
- [ ] dashboard

## Output
- [ ] CSV export
- [ ] XLSX where supported
- [ ] S3 write-back
- [ ] MinIO write-back
- [ ] Azure write-back

## Quality
- [ ] unit tests
- [ ] integration tests
- [ ] E2E
- [ ] security tests
- [ ] tenant isolation tests
- [ ] benchmark harness
- [ ] documentation

## Final gate
- [ ] backend build passes
- [ ] frontend build passes
- [ ] migrations pass
- [ ] all critical tests pass
- [ ] actual benchmark evidence captured
- [ ] no fake/mock completion claims
