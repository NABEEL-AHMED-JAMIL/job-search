# Existing documentation -- triage

Assessment only. Nothing has been moved, edited or deleted. Every claim below was checked against the
code and config in the working tree on 2026-09-01; paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

Two words are used for the actions, and they mean different things:

- **replace** -- the document has real content worth carrying forward; correct it in place and move the
  superseded parts to `.ai/old-scope/`.
- **rewrite** -- there is nothing to carry forward; whatever goes at that path has to be written fresh.

## Verdicts

| # | Document | Lines | Verdict | Action | One-line reason |
|---|---|---|---|---|---|
| 1 | `README.md` | 1 | wrong | rewrite | Names the workspace after `job-search`, which is one of five unrelated sibling repos and is also checked out as its own subdirectory. |
| 2 | `scheduler1/README.md` | 2 | boilerplate | rewrite | A title and a blank line; carries no knowledge of a repo that now holds two separate frontends. |
| 3 | `scheduler1/DEPLOYMENT.md` | 45 | partly-stale | replace | Build and container steps are accurate, but the verify URL is wrong and it silently documents only the superseded Angular 8 app. |
| 4 | `scheduler1/next/README.md` | 59 | boilerplate | rewrite | Verbatim Angular CLI scaffold. Accurate, but says nothing this project would not share with any other Angular 22 app. |
| 5 | `process/README.md` | 206 | partly-stale | replace | Overview, scheduler types, diagrams and the port/context path are correct; the endpoints, the bootstrap SQL, the actuator dump and the tech stack are not. |

## What the workspace actually is

This matters for reading verdict 1. `Old-School/` is not a monorepo. It is a directory holding five
independent git checkouts, each with its own remote:

| Directory | Remote |
|---|---|
| `job-search/` | `github.com/NABEEL-AHMED-JAMIL/job-search.git` |
| `my-user-redux-frontend/` | `github.com/NABEEL-AHMED-JAMIL/my-user-redux-frontend.git` |
| `process/` | `github.com/NABEEL-AHMED-JAMIL/process.git` |
| `scheduler1/` | `github.com/NABEEL-AHMED-JAMIL/scheduler1.git` |
| `service-3/` | `github.com/NABEEL-AHMED-JAMIL/service-3.git` |

The root directory is *itself* a sixth checkout: `git remote -v` at the root returns
`job-search.git`, `git log` shows a single commit ("first commit"), and `git ls-files` returns exactly
one tracked path -- `README.md`. There is no root `.gitignore`. In other words, a `job-search` clone
became the parent folder that the other projects were later dropped into, and the same project is
*also* present as the `job-search/` subdirectory.

---

## 1. `README.md`

**Verdict: wrong. Action: rewrite.**

The entire content is `# job-search`. As a record of the `job-search` repo it is technically consistent
with that repo's remote, but as documentation of this directory it is wrong: the two projects under
active work here are `scheduler1` and `process`, neither of which the root repo tracks, and
`job-search` is a sibling folder alongside them rather than the thing this directory is.

Nothing to preserve. Rewrite it as a workspace index -- one line per project, saying what it is and
where its own documentation lives -- and state explicitly that these are independent checkouts, because
the current file leads a reader to the opposite conclusion.

## 2. `scheduler1/README.md`

**Verdict: boilerplate. Action: rewrite.**

Fourteen bytes: `# scheduler`, then a blank line. It carries no project knowledge at all, which is a
real loss here because this repository is not one application but two, and nothing at the front door
says so:

| Path | What it is | Last commit touching it |
|---|---|---|
| `scheduler1/src/` | Angular 8 + Webpack 4, built by `webpack.config.js`, the app the Docker image ships | `f132065` 2026-08-22 |
| `scheduler1/next/` | Angular 22 standalone + Angular CLI, `next/angular.json` | `864daea` 2026-08-29 |

The last fifteen commits in `scheduler1` all touch `next/src`; four of them also touch the old tree.
The two trees cover overlapping ground -- `src/app/_component/` has `login`, `tenants`, `source-job`,
`source-task`, `object-browser`, `ai-agent`, `dynamic-form`, `document-converter`, and
`next/src/app/features/` has `login`, `tenant-request`, `jobs`, `tasks`, `objects`, `ai`, `forms`,
`tools` -- so `next/` reads as a rewrite in progress rather than a second product.

Nothing to preserve. A rewrite should at minimum name both trees, say which one is current, and say
which one deploys today (the old one -- see below).

One incidental inconsistency worth fixing while in there: `scheduler1/package.json` declares
`repository.url` as `https://github.com/NABEEL-AHMED-JAMIL/scheduler`, but the checkout's actual remote
is `scheduler1.git`.

## 3. `scheduler1/DEPLOYMENT.md`

**Verdict: partly-stale. Action: replace.**

The mechanics check out. `docker-compose.yml` defines an `angular-app` service building `Dockerfile`
target `production` and publishing `80:80`; the Dockerfile's stage 1 runs
`./node_modules/.bin/webpack --mode production` on Node 14 for Angular 8 / Webpack 4, and stage 2
copies the build into an `nginx:1.27-alpine` image. So `docker-compose build --no-cache` and
`docker-compose up -d` (lines 17-20 and 36-38) are correct, as is line 43's description of the build
stage and the caching advice at line 45.

Two things are not right.

**The verify URL at line 28 is wrong.** It says to open `http://localhost/`. The Dockerfile does
`rm -rf /usr/share/nginx/html/*` and then copies the build to
`/usr/share/nginx/html/scheduler`, and `nginx.conf` serves the app from `location /scheduler/` with a
`location = /scheduler` redirect in front of it. Nothing is left at the document root, so the `/`
location's `try_files ... /index.html` has no file to fall back to. The working URL is
`http://localhost/scheduler/`. This is the single most costly line in the file -- it sends a reader to
a 404 on their first attempt.

**It documents the superseded frontend without saying so.** The compose build has `context: .` and
runs webpack, so what it deploys is `scheduler1/src` -- the Angular 8 app. `next/` has no Dockerfile,
no compose service and no entry in this document, which means the app under active development has no
documented deployment path at all.

Worth preserving: the prerequisites, both `docker-compose` blocks, the rebuild-after-changes section
and the notes. Replace by fixing line 28 to `http://localhost/scheduler/`, adding a sentence at the top
scoping the file to the legacy webpack app, and recording that `next/` is not yet covered. There is
also an undocumented `location /health` returning `200 OK`, used by both the Dockerfile `HEALTHCHECK`
and the compose healthcheck, that is worth a line.

## 4. `scheduler1/next/README.md`

**Verdict: boilerplate. Action: rewrite.**

This is the stock Angular CLI scaffold README, unmodified. Its claims are accurate, which is why the
verdict is boilerplate rather than wrong:

| Claim | Check |
|---|---|
| Generated with Angular CLI 22.1.5 (line 3) | `next/package.json` has `@angular/cli` `^22.1.5` -- consistent |
| `ng serve` on `http://localhost:4200/` (lines 11, 13) | `next/angular.json` defines a `serve` target with no port override, so the CLI default applies -- correct |
| `ng build` outputs to `dist/` (line 37) | Correct in spirit; `angular.json` sets no `outputPath`, so `@angular/build:application` writes `dist/next/`, which is what the directory contains |
| `ng test` runs Vitest (line 41) | Correct -- the `test` target uses `@angular/build:unit-test`, `vitest ^4.0.8` is a devDependency, and there are 31 `*.spec.ts` files under `next/src` |
| `ng e2e` (line 52) | No e2e builder is configured in `angular.json`; the file itself concedes no framework ships by default, so this section is inert |

The reason to rewrite rather than keep is that none of it is about *this* application. The app has a
real shape worth documenting -- `src/app/core/` (auth service, guard, interceptor, each with specs),
`src/app/shared/` (ui and charts primitives), and twenty feature folders under `src/app/features/`
including `admin`, `jobs`, `queue`, `reports`, `settings`, `tenant-request` -- and a reader needs to be
told this is the replacement for `scheduler1/src`, not a fresh project. Only the `ng test` line is
worth carrying over verbatim, since Vitest instead of Karma is genuinely non-obvious.

## 5. `process/README.md`

**Verdict: partly-stale. Action: replace.**

The longest and most useful of the five, and the one where stale content is most likely to cost
someone real time, because several passages are written as instructions rather than description.

### Accurate -- worth preserving

| Section | Lines | Evidence |
|---|---|---|
| Overview and the five scheduler types | 3-13 | `src/main/java/process/model/enums/Frequency.java` is exactly `Mint, Hr, Daily, Weekly, Monthly` |
| Kafka as the backbone | 5, 24-27 | `spring-kafka` in `pom.xml`; `process/config/KafkaProducerConfig.java`, `KafkaTemplateProvider.java`, `KafkaTopicProvisioner.java`, `process/engine/ProducerBulkEngine.java`; `docker-compose.yml` runs `confluentinc/cp-kafka:7.5.0` and `cp-zookeeper:7.5.0` |
| Port 9098 and context path `/api/v1` | 69-71 | `application.properties` lines 6-7: `server.port=9098`, `server.servlet.context-path=/api/v1` |
| Swagger UI URL | 70 | `process/config/SwaggerConfig.java` is `@EnableSwagger2` with springfox 2.9.2 on Spring Boot 2.3.2, so `/api/v1/swagger-ui.html` resolves |
| Local build commands | 51-54 | `spring-boot-maven-plugin` is declared at `pom.xml:281` |
| All four diagrams | 83, 85, 117, 121 | `ext-detail/old-etl.png`, `new-etl.png`, `Topic-Detail.png`, `new-dbdesing.png` all present |

### Stale or wrong -- do not carry forward as-is

| Section | Lines | Problem |
|---|---|---|
| "Uses `ThreadPoolExecutor` with a `PriorityBlockingQueue`" | 21 | Not verified, and probably no longer true. `grep` across `src/main/java` for `PriorityBlockingQueue`, `ThreadPoolExecutor`, `ThreadPoolTaskExecutor`, `ExecutorService`, `Executors.` and `@Async` returns nothing. The concurrency that does exist is Spring's own scheduler pool, sized by `spring.task.scheduling.pool.size` in `application.properties` |
| "PostgreSQL -- (Optional)" | 32 | Not optional. `docker-compose.yml` defines a `postgres:15` service, points the app at `jdbc:postgresql://postgres:5432/etl_job`, and gives `process_app` a `depends_on` for it; Liquibase is enabled in `application-dev.properties` |
| Clone command | 45 | `https://github.com/.../process/tree/split-mono-to-microservice` is a GitHub browse URL, not a clonable one. The remote is `.../process.git`, and the checked-out branch is `new-screen-2026`, not `split-mono-to-microservice` |
| Link to `DOCKER_SETUP.md` | 77 | The file does not exist anywhere in the repository. Dead link |
| "Before run this project execute the below script" | 89-98 | Superseded, and would now fail. Schema is managed by Liquibase (`src/main/resources/db/changelog/`, V1.0 through V25.0), and `ModelApplication.java:47-57` seeds `SCHEDULER_LAST_RUN_TIME` itself on startup and logs that it will not overwrite an existing value. The positional 5-value `INSERT INTO lookup_data` no longer matches the table -- `LookupData.java` has added `created_by`, `updated_by`, `is_encrypted` and `tenant_id` -- and the 4-column `source_task_type` insert omits `tenant_id`, `task_type_status` and `kafka_connection_profile_id` from `SourceTaskType.java` |
| "Process Endpoint" | 100-105 | Both endpoints are gone. There is no `bulk.json` controller in `src/main/java/process/api/`. The equivalents today are `/api/v1/sourceJob.json/downloadSourceJobTemplateFile` (`SourceJobRestApi.java:191`) and `/api/v1/sourceJob.json/uploadSourceJob` (`SourceJobRestApi.java:219`), plus `/sourceTask.json/downloadSourceTaskTemplate` and `/sourceTask.json/uploadSourceTask` in `SourceTaskRestApi.java` |
| Actuator HAL index | 123-205 | The pasted JSON advertises `beans`, `env`, `configprops`, `loggers`, `liquibase`, `caches`, `heapdump`, `threaddump`, `scheduledtasks`, `mappings` and `shutdown`. `application.properties` now sets `management.endpoints.web.exposure.include=health,info,metrics,prometheus` and `management.endpoint.shutdown.enabled=false`, with a comment explaining that the others leak secrets. Only four of the sixteen listed links still resolve |
| Tech stack | 29-32 | Three entries, where the dependency set is much wider: `spring-boot-starter-data-redis`, `minio`, `liquibase-core` and `jodconverter` are all in `pom.xml`, and `docker-compose.yml` additionally runs `redis`, `kafka_ui` and `redisinsight` -- none named in the "Start all services (PostgreSQL, Kafka, Zookeeper, Application)" comment at line 62 |

### The bigger gap

The README describes a Kafka scheduler engine. `src/main/java/process/api/` holds 27 REST controllers,
and the scheduler is one part of what is now a much larger application: AI agents and Ollama, a PDF
highlighter, object storage browsing and sharing, multi-tenancy and tenant requests, audio
transcription, document conversion, dynamic form building, a query engine, notifications and file
chat. A replacement should either widen its scope to match or say plainly that it covers the ETL
scheduler only.

Replace: keep the overview, scheduler types, Kafka architecture, diagrams and the port/context-path
facts; correct the clone command, the endpoint list and the tech stack; delete the bootstrap SQL and
the actuator dump, moving both here to `.ai/old-scope/` since they are a useful record of how the
service used to be operated.

## Out of scope, but noted

Five further markdown files exist that were not part of this triage and have had no verification pass:
`process/ext-detail/md/DATABASE_CONNECTION_GUIDE.md`, `REFACTORING_SUMMARY.md`, `SQL_UPDATE_GUIDE.md`,
`QUICK_REFERENCE.md`, and `process/docs/design/kafka-dynamic-configuration.md`. None of them is linked
from `process/README.md`. They are flagged only so that a decision on the five documents above is not
mistaken for a decision on the repository's documentation as a whole.
