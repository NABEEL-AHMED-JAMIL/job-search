# Project specification

## Application

**ETL Console** — a multi-tenant scheduler and data-pipeline platform. Tenants define **tasks** (a unit of work) and **jobs** (a schedule that runs tasks), and the platform dispatches them through Kafka to workers, tracks every run, and stores the artefacts.

Around that core it carries the machinery a tenant needs to actually operate it: storage connections, Kafka connection profiles with their certificates, dynamic forms, AI agents, document and audio tooling, a query engine, reporting, and the administration of tenants and users.

**The work in progress is a frontend rewrite.** An older Angular application is being replaced by a new Angular 22 one, feature by feature. Both talk to the same backend. The rewrite is the reason this workflow exists: the question that has to be answered for every feature is *"has this made the crossing, and completely?"*

## Technology

| Part | Stack |
|---|---|
| **New frontend** | Angular 22.1.5, standalone components, signals, `@if`/`@for`, Tailwind CSS 4, ECharts, `@stomp/stompjs`, vitest 4.1.11 |
| **Old frontend** | Angular 8, Webpack 4 (Node 14), ngx-echarts, ng2-toastr, served by nginx 1.27-alpine |
| **Backend** | Spring Boot 2.3.2, Java 8 source level on a JDK 17 runtime, Maven, Spring Security + JWT, Spring Data JPA / Hibernate |
| **Database** | PostgreSQL 15, schema managed by Liquibase (`V1.0` … `V25.0`) |
| **Messaging** | Apache Kafka (`kafka-clients` 2.5.0) with ZooKeeper |
| **Object storage** | MinIO, with S3 and Azure Blob also supported per connection |
| **Cache** | Redis |
| **Search** | OpenSearch 2.10 |
| **AI** | Ollama |
| **Documents** | LibreOffice via jodconverter |

## Where things run

| | URL | Notes |
|---|---|---|
| Old frontend | `http://localhost/scheduler/` | Port 80 via nginx — **not** the root path |
| New frontend | `http://localhost:4200` | Angular CLI default — `angular.json` sets no port. Sessions here have also used `ng serve --port 4400` |
| Backend API | `http://localhost:9098/api/v1` | `src/app/core/api/api.config.ts` |
| PostgreSQL | `localhost:5433` | Published by the backend's compose file |
| MinIO | `localhost:9000` / console `9001` | Runs outside the backend's compose file |
| OpenSearch | `localhost:9200` | |
| Kafka UI | see `process/docker-compose.yml` | |
| Kafka test broker | `localhost:19092`–`19098` | Seven listeners, one per security configuration |

## Repository layout

```
Old-School/
├── scheduler1/
│   ├── src/     old frontend      — reference only, not being changed
│   └── next/    new frontend      — IN SCOPE
├── process/     backend           — IN SCOPE
├── job-search/  Python Kafka workers   — out of scope this phase
├── my-user-redux-frontend/, service-3/   — unrelated projects
└── .ai/         this workflow
```

## Main modules

Authentication and RBAC · tenants and tenant requests · users · jobs, queue and run history · tasks and task types · task forms and dynamic forms · storage connections and the object browser · Kafka connection profiles and certificates · AI agents and models · document converter, audio transcript, text cleaner, PDF highlighter · query engine · reports and dashboard · notifications · user profile and activity · bulk transfer · lookup and settings administration.

The authoritative list, with migration status per feature, is [discovery/features.md](discovery/features.md).

## Roles

Three roles, in a hierarchy — `PLATFORM_ADMIN` > `TENANT_ADMIN` > `TENANT_USER`.

| Role | Reach |
|---|---|
| `PLATFORM_ADMIN` | Everything, across every tenant. Carries no `tenant_id` of its own |
| `TENANT_ADMIN` | Everything **within its own tenant**, including managing that tenant's users. Cannot see or touch another tenant, or another tenant's admin |
| `TENANT_USER` | Its own records within its tenant |

A row with a null `tenant_id` is **platform-owned, not ownerless** — a caller carrying no tenant must own nothing.

## Migration goals

1. Every capability of the old frontend either exists in the new one or has been **explicitly decided against** — recorded, not merely absent.
2. Authorization enforced at all four layers: frontend guard, controller annotation, service rule, data filter. The frontend hiding a control is not enforcement.
3. No secret — private key, password, store location — exposed through the UI, an API response, or a log.
4. The new frontend is a genuine improvement, not a transliteration: real loading, empty and error states; dark and light mode; responsive layout.
5. Every feature carries tests that fail when the behaviour they name is removed.

## Non-functional requirements

**Security.** Secrets encrypted at rest (AES-GCM via `EncryptionUtil`). Tenant isolation enforced at the data layer as well as above it. Storage keys carry identity (`kafka-secrets/{appUserId}/…`, `{appUserId}/profile/…`), so key comparison is an authorization decision and must be numeric, never a string prefix.

**Testing.** Three suites, all green before a feature is called done:

| Suite | Command | Current |
|---|---|---|
| Backend unit | `mvn -o test` | 516 |
| Backend E2E | `./run-e2e.sh` | 86 |
| Frontend | `npx ng test --watch=false` | 445 |
| Kafka security matrix | `./run-kafka-matrix.sh` | 17, against a real broker |

**Reliability.** A bootstrap or migration failure must never stop the application from starting. Background work must not be able to take the web tier down with it.

**Observability.** A failure a user can fix must say so. An opaque 500 where the code already knows the reason is a defect, not a rough edge.

## Working method

**Discovery → Grooming → Synthesis → Execution → QA → Regression**, one feature at a time. See [README.md](README.md) for the phases and [prompts/](prompts/) for the prompt used at each.

Nothing goes straight from a requirement to code.
