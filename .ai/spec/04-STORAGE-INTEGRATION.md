# Generic Object Storage Integration

## Interface
Conceptual contract:

```text
ObjectStorageProvider
  listContainers()
  listObjects(connection, container, prefix, pageToken)
  getMetadata(ref)
  openStream(ref)
  exists(ref)
  write(ref, stream, contentType)
```

Implement/reuse:
- S3 adapter
- MinIO adapter
- Azure Blob adapter

Analytics receives:
```text
connectionId
container/bucket
path
pattern
format
```

It never receives secrets.

## Path semantics
Treat bucket/container + prefix/path as provider-neutral logical coordinates.

## Read strategy
Prefer streaming/range access and DuckDB-compatible remote access where safe. If temporary materialization is required, use managed ephemeral storage with cleanup and encryption according to platform policy.

## Write strategy
Generated output is written through the same provider abstraction.

## Consistency
After write-back, verify object metadata and persist the output artifact reference.

## Security
Every provider operation must validate tenant and connection authorization before access.
