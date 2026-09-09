# Old-School — workspace

**This is not a monorepo.** It is a directory holding six independent git checkouts, each with its own remote. Cloning one does not get you the others, and a commit in one has nothing to do with a commit in another.

The root directory is itself a checkout of `job-search.git` that the other projects were later dropped into — which is why `job-search` also appears as a subdirectory. The root repo tracks exactly one file: this README.

## Projects

| Directory | What it is | Documentation |
|---|---|---|
| **`scheduler1/`** | The ETL Console frontend — **two** applications: `src/` (Angular 8, currently deployed) and `next/` (Angular 22, the rewrite) | [scheduler1/README.md](scheduler1/README.md) |
| **`process/`** | The ETL Console backend — Spring Boot, Kafka, PostgreSQL | [process/README.md](process/README.md) |
| `job-search/` | Python Kafka workers | `job-search/doc/` |
| `my-user-redux-frontend/` | Unrelated project | — |
| `service-3/` | Unrelated project | — |

`scheduler1` and `process` are one system and are worked on together. The rest are independent.

## Active work

The ETL Console is being migrated from the Angular 8 frontend to the Angular 22 one, **feature by feature**. That work is planned and tracked in [`.ai/`](.ai/):

| | |
|---|---|
| [.ai/project.md](.ai/project.md) | What the system is, its stack, its roles, its goals |
| [.ai/discovery/features.md](.ai/discovery/features.md) | Every feature and whether it has made the crossing |
| [.ai/README.md](.ai/README.md) | The workflow: Discovery → Grooming → Synthesis → Execution → QA → Regression |

Start there rather than in the code.

## Running the system locally

| Part | From | Command |
|---|---|---|
| Backend and its stack | `process/` | `docker-compose up -d` |
| Old frontend | `scheduler1/` | `docker-compose up -d` → **`http://localhost/scheduler/`** |
| New frontend | `scheduler1/next/` | `ng serve` → `http://localhost:4200` |

The backend API is at `http://localhost:9098/api/v1`. MinIO and OpenSearch run outside the backend's compose file. Full detail, including ports and environment variables, is in [.ai/discovery/infrastructure.md](.ai/discovery/infrastructure.md).
