# DuckDB Integration

## Responsibilities
DuckDB performs:
- scans
- filters
- projections
- aggregation
- joins
- profiling
- analytical SQL
- result generation

## Session model
Use controlled backend-managed sessions or per-request connections according to concurrency requirements. Do not create unbounded connections.

## File access
Resolve a generic dataset reference into a safe DuckDB relation/view. Credentials must remain server-side.

## Query lifecycle
QUEUED → RUNNING → COMPLETED | FAILED | CANCELLED | TIMED_OUT.

Persist query metadata, not necessarily the full result.

## Safety
Enforce:
- timeout
- maximum result rows
- maximum concurrent queries
- cancellation
- memory/resource settings where supported
- statement validation/policy where required

## Profiling
Use efficient aggregate queries and sampling for large data. Avoid issuing one expensive query per metric when a combined scan can calculate multiple metrics.

## Future-proofing
Hide DuckDB behind AnalyticsEngine so another execution engine can be introduced later.
