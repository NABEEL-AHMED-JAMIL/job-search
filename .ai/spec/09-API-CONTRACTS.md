# API Contracts

Adapt endpoint names to existing project conventions.

## Dataset
```text
GET  /api/analytics/datasets
GET  /api/analytics/datasets/{id}
GET  /api/analytics/datasets/{id}/preview
GET  /api/analytics/datasets/{id}/schema
GET  /api/analytics/datasets/{id}/profile
GET  /api/analytics/datasets/{id}/quality
```

## Analysis
```text
POST /api/analytics/analyze
POST /api/analytics/analyze/drill
POST /api/analytics/analyze/drill-up
```

Example request:
```json
{
  "datasetId": "ds_123",
  "dimensions": ["department", "status"],
  "measure": "user_id",
  "aggregation": "DISTINCT_COUNT",
  "filters": [
    {"field":"country","operator":"EQ","value":"US"}
  ],
  "limit": 50
}
```

## SQL
```text
POST /api/analytics/query
POST /api/analytics/query/{id}/cancel
GET  /api/analytics/query/history
POST /api/analytics/query/save
GET  /api/analytics/query/saved
```

## Export
```text
POST /api/analytics/export
GET  /api/analytics/export/{id}
```

## Benchmark
```text
POST /api/analytics/benchmark
GET  /api/analytics/benchmark/{id}
```

## Response principles
Return stable IDs, status, timing, warnings and typed column metadata. Use existing API error envelopes and correlation IDs.
