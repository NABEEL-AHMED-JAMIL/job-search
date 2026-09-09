# Deployment & Operations

## Configuration
Follow existing environment/configuration conventions.

Conceptual settings:
```yaml
analytics:
  enabled: true
  query-timeout-ms: 120000
  max-result-rows: 100000
  max-concurrent-queries: 4
  profile-sample-rows: 1000000
  benchmark-enabled: true
  parquet-conversion-enabled: true
```

## Health
Expose analytics health through the existing application health mechanism.

Validate:
- DuckDB availability
- metadata database
- storage provider connectivity only through safe checks
- queue/event dependencies if used

## Observability
Use correlation IDs and structured logs.

Track:
- query duration
- storage latency
- profile duration
- export duration
- failures
- cancellation
- resource saturation

## Rollout
Use feature flags if available:
1. internal users
2. test tenant
3. controlled production rollout
4. broader availability

## Cleanup
Temporary files, sessions and abandoned jobs must have TTL/cleanup behavior.
