# Database Model

PostgreSQL remains metadata storage.

## analytics_dataset
- id
- tenant_id
- storage_connection_id
- bucket/container
- path
- pattern
- format
- file_count
- total_size
- schema_snapshot
- last_profiled_at
- created_at
- updated_at

## analytics_saved_query
- id
- tenant_id
- owner_id
- name
- sql
- dataset_refs
- created_at
- updated_at

## analytics_query_history
- id
- tenant_id
- user_id
- status
- duration_ms
- rows_returned
- bytes_scanned if available
- error_code
- created_at

## analytics_analysis
Stores structured dimension/measure/filter configurations.

## analytics_dashboard
Stores dashboard metadata.

## analytics_dashboard_widget
Stores visualization configuration and references to saved queries/analyses.

## analytics_benchmark_result
Stores benchmark metadata and measured values.

## Indexing
Index all tenant-scoped lookup paths. Avoid indexes that duplicate existing platform indexes. Review cardinality and query plans before adding large indexes.
