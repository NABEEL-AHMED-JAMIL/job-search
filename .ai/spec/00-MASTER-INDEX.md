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

## Written during the work, not planned before it

These are not numbered because they are not specification — they are the record of what was found
and decided. `DEFECT-SWEEP.md` is the one to read first if you are picking this up cold.

- **DEFECT-SWEEP.md** — 58 verified defects across seven areas (2026-09-14), what each actually
  broke, and what was deliberately left open. Includes the honest answer to "why is the RAG not
  using a vector database".
- **HARDENING-PASS.md** — the full correctness pass over seven areas to a zero-known-bugs bar
  (in progress). Written as the work happens; wrong findings stay in the record with their
  correction.
- **REALTIME-AND-UI-SWEEP.md** — 32 verified findings (2026-09-14) on live updates, the chart
  palette and the widget tile. The socket transport was healthy throughout; almost nothing was ever
  published, and the "Live" log screen polled exactly once. Section 4 records a finding that was
  WRONG and the fix shipped on it — the application pins its own timezone in main(), which neither
  the investigation nor I checked — plus the scheduler that ran real jobs out of every test run.
- **RAG-CHAT-REVIEW.md** — the RAG/Redis/file-chat review (2026-09-14). 26 verified findings.
  The headline: the OpenSearch `_bulk` body was sent as ISO-8859-1, so every indexed chunk had
  its text mangled and any chunk carrying a U+0080..U+00FF character was rejected outright and
  lost from the middle of its file. Records what is still Latin-1 damaged in the live index.
- **JOB-ASSISTANT-QA.md** — the job assistant / chat bot QA pass (2026-09-14). Eleven defects,
  the worst of which answered "tell me about job 99" with a summary of the job in view. Records
  two non-defects that cost real time, and two mutations that caught flaws in the tests first.
- **REPORTS-REVIEW.md** — the reports/analytics review, F1–F7.
- **REPORTS.md** — the seeded report catalogue and how its numbers were independently validated.
- **PROGRESS.md** — the working tracker; a line moves to done only with evidence.
- **SECRET-SCAN.md** — the history scan and its triage. **Three credentials still need rotating.**
- **E2E-FLOW.md**, **AUDIT.md**, **LIQUIBASE-FROM-SCRATCH.md**.

## Golden workflow
Storage connection → bucket/container → folder/path → file/pattern → dataset registration → schema detection → preview → profile → quality → dimensions/measures → interactive analysis → SQL/chart → save → dashboard → export → write-back → event/audit → benchmark.

## Agent rule
Inspect the existing codebase first. Reuse existing storage, authentication, scheduler, Kafka, database, UI, charts, tables, and design-system capabilities. Do not build parallel infrastructure.
