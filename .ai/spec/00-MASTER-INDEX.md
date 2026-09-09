# Analytics Studio — Master Specification
Version 1.0

## Purpose
This documentation set is the authoritative end-to-end engineering specification for Analytics Studio inside the existing ETL platform.

## Architecture
Angular + Tailwind UI → Spring Boot Analytics APIs → Analytics Services → DuckDB → Generic Object Storage Adapter → S3 / MinIO / Azure Blob.

PostgreSQL stores metadata; object storage stores datasets and generated files; existing Kafka/event infrastructure handles events; existing authentication and tenant authorization remain authoritative.

## Required document order
1. Discovery and Architecture
2. Product Requirements
3. End-to-End Flow
4. Storage Integration
5. DuckDB Integration
6. Dataset Workspace UX
7. Analytics Canvas
8. SQL Studio
9. API Contracts
10. Database Model
11. Security and Multi-Tenancy
12. Performance and Benchmarking
13. Testing and QA
14. Deployment and Operations
15. V2 Hardening and V3 Roadmap

## Golden workflow
Storage connection → bucket/container → folder/path → file/pattern → dataset registration → schema detection → preview → profile → quality → dimensions/measures → interactive analysis → SQL/chart → save → dashboard → export → write-back → event/audit → benchmark.

## Agent rule
Inspect the existing codebase first. Reuse existing storage, authentication, scheduler, Kafka, database, UI, charts, tables, and design-system capabilities. Do not build parallel infrastructure.
