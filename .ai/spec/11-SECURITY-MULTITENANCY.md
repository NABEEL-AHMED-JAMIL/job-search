# Security & Multi-Tenancy

## Authorization
Check authorization at:
1. route/API boundary
2. service layer
3. dataset/storage resolution
4. query execution
5. export/write-back

## Tenant isolation
Tenant ID must come from trusted authenticated context, not a client-supplied arbitrary tenant ID.

Every dataset, saved analysis, query history item and dashboard must be tenant-scoped.

## Storage
Do not return credentials or signed URLs unless the existing platform explicitly uses short-lived, scoped URLs and its security policy permits them.

## Audit
Record:
- dataset opened
- profile requested
- query executed
- export requested
- output written
- dashboard changed
- permission failures

## Data leakage prevention
Validate every dataset reference in SQL/analysis requests. Never allow a user to reference another tenant's dataset ID by guessing an identifier.

## Abuse controls
Rate limit expensive operations and cap concurrent queries.
