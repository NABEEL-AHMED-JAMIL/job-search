# Discovery & Architecture Specification

## Discovery gate
Before implementation, inventory:
- backend modules and package boundaries
- frontend modules/routes/components
- storage connection model and adapters
- S3/MinIO/Azure support
- PostgreSQL schema and migration framework
- Redis
- Kafka/event conventions
- scheduler/ETL execution
- auth/RBAC/tenant context
- existing tables, charts, dialogs, editors and file browsers
- API/error conventions
- observability

Produce a reuse matrix: requirement → existing capability → reuse/refactor/new component.

## Target boundaries
### Storage layer
Owns object listing, metadata, streams, reads and writes.

### Dataset layer
Resolves a generic storage reference into a logical dataset and schema.

### Analytics layer
Owns DuckDB sessions, SQL, profiling, aggregations and query lifecycle.

### Presentation layer
Owns Angular workspace, interactions and visualization configuration.

### Metadata layer
Owns datasets, saved queries, analyses, dashboards, benchmarks and audit metadata.

## Non-negotiable
No browser credentials. No raw dataset copies in PostgreSQL. No provider-specific analytics code. No second scheduler. No second Kafka system.
