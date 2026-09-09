# Performance Engineering & Benchmark Harness

## Benchmark matrix

### Sizes
- 10 MB
- 100 MB
- 1 GB
- larger if infrastructure permits

### Formats
- CSV
- Parquet
- JSON/NDJSON

### Providers
- S3
- MinIO
- Azure Blob

### Operations
- full scan/count
- filtered scan
- aggregation
- sort
- 1D analysis
- 2D analysis
- 3D analysis
- two-way join
- three-way join
- export

## Metrics
Measure:
- wall-clock duration
- throughput
- rows processed
- rows returned
- bytes read where available
- memory
- CPU where available
- storage latency
- failure/timeout rate

## Harness requirements
- repeatable
- configurable dataset
- warm/cold run distinction
- multiple iterations
- machine/environment metadata
- result persistence

Never fabricate numbers.

## Performance acceptance
Define thresholds after measuring the actual deployment environment. Do not use arbitrary universal thresholds.

## Optimization experiments
Compare:
- CSV vs Parquet
- single file vs partitioned files
- full scan vs predicate filtering
- high-cardinality vs bounded Top-N
- repeated profile vs cached profile

## User-facing benchmark
A “Benchmark” action should explain that it runs real work and may consume resources. Display measured results and methodology.
