# Discovery -- Backend (process)

What the `process` service actually contains, read from the source on the current `main` working
tree (last commit `eed6a4b`, "Author tag on every class, and remove what is actually dead").
Every claim below cites the file it came from; anything specific cites a line. Where the code did
not answer a question, the section says "not verified" and names what was looked at.

Paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---


> **Superseded 2026-09-17 on two points.** (1) Every mention below of `NotifyResetApi` throwing
> at `@PostConstruct` when `WORKER_CALLBACK_TOKEN` is unset is out of date: the callbacks are now
> proved per run by `security/RunCallbackTokens` and the variable is an optional legacy fallback
> -- see [features.md §3](features.md) and
> [../grooming/worker-callback-tokens.md](../grooming/worker-callback-tokens.md). (2) The
> controller count is now 28: `api/PageAccessRestApi.java` (`/pageAccess.json/*`) was added on
> 2026-09-17 with `security/PageAccessInterceptor` registered in `WebConfig`; see
> [../grooming/page-access-profiles.md](../grooming/page-access-profiles.md). Also new since
> this inventory: `security/RunCallbackTokens`, `security/PageAccessCache`,
> `model/enums/PageKey`, entities `PageAccessProfile` and `UserPageAccess` (30 `@Entity`
> classes), Liquibase V40–V42. Deleted 2026-09-16: `SmtpMailSender`, `AzureBlobConfig`, the
> `spring.mail.*` and `minio.*` / `aws.s3.*` properties.

## 1. Stack, module layout and conventions

### 1.1 Stack

| Thing | Value | Evidence |
|---|---|---|
| Framework | Spring Boot 2.3.2.RELEASE (parent POM) | `process/pom.xml:9-13` |
| Language level | Java 8 (`java.version` 1.8) | `process/pom.xml:22` |
| Build/run JDK | 17, pinned by the maven-toolchains-plugin | `process/pom.xml:319-345`, `process/Dockerfile:2` (`eclipse-temurin:17-jdk`) |
| Persistence | Spring Data JPA / Hibernate, PostgreSQL driver, Liquibase changelogs | `process/pom.xml`, `process/src/main/resources/db/changelog/` |
| Security | spring-boot-starter-security + jjwt 0.11.5 (HS256) | `process/pom.xml`, `process/src/main/java/process/util/JwtUtil.java:52` |
| Messaging | spring-kafka 2.5.12 (**producer only**, see §5) | `process/pom.xml`, `process/src/main/java/process/config/KafkaProducerConfig.java` |
| Cache / presence | spring-boot-starter-data-redis, `@EnableCaching` | `process/src/main/java/process/config/RedisConfig.java` |
| Realtime | spring-boot-starter-websocket, STOMP over SockJS | `process/src/main/java/process/config/WebSocketConfig.java` |
| Scheduling | Spring `@Scheduled` + ShedLock 4.9.3 (JDBC lock provider) | `process/src/main/java/process/config/ProcessConfig.java` |
| Docs | springfox-swagger2 2.9.2 | `process/src/main/java/process/config/SwaggerConfig.java` |
| Object storage | minio 8.5.17, AWS SDK v2 `s3` 2.25.60, azure-storage-blob 12.25.3, commons-net (FTP/FTPS) | `process/pom.xml` |
| Documents | jodconverter 4.4.7 (local LibreOffice), PDFBox 2.0.31, Apache POI 3.15 | `process/pom.xml` |
| Query engine | commons-csv 1.10.0, jsqlparser 4.6 | `process/pom.xml` |
| Analytics engine | duckdb_jdbc 1.1.3 — **embedded, running inside this JVM** (added 2026-09-08) | `process/pom.xml:273-281`; §4, "Analytics Studio" |
| Templating / mail | Velocity 1.7 + spring-boot-starter-mail | `process/src/main/java/process/emailer/` |
| Misc | Gson 2.8.6, libphonenumber 8.13.50, micrometer-prometheus | `process/pom.xml` |

The application serves on port **9098** under context path **`/api/v1`**
(`process/src/main/resources/application.properties:5-6`). Every path in §2 is relative to that
prefix. The default JVM time zone is forced to `America/Chicago` in `main()`
(`process/src/main/java/process/ModelApplication.java:31`).

### 1.2 Module layout

```
process/src/main/java/process/
├── ModelApplication.java     Spring Boot entry point; seeds SCHEDULER_LAST_RUN_TIME on boot
├── analytics/                Analytics Studio's engine, governor and resolver (§2.29, §3.7, §4)
│   └── dto/                  ColumnDto, DatasetSchemaDto, DatasetPreviewDto
├── api/                      27 REST controllers, 181 endpoints  (§2)
│                             + AnalyticsRestApi and its 2, added 2026-09-08 (§2.29)
├── config/                   19 @Configuration / bootstrap classes (§6)
├── emailer/                  Velocity templates + JavaMailSender wrapper
├── engine/                   the ETL dispatcher: BulkAction, ProducerBulkEngine
│   ├── cron/                 ProcessCron, AuditLogSyncCron  (§5)
│   ├── dto/                  JobPayloadDTO -- the Kafka message body
│   └── query/                CsvExportService, DatabaseConnectionFactory, QueryValidator
├── model/
│   ├── converter/            JPA AttributeConverters for the three status enums
│   ├── dto/                  60 request/response DTOs, incl. ResponseDto
│   ├── enums/                13 enums (UserRole, JobStatus, Status, StorageProvider, ...)
│   ├── pojo/                 30 JPA entities + AuditListener/Audited
│   ├── projection/           6 interface/class projections for native queries
│   ├── repository/           26 Spring Data repositories
│   └── service/              29 interfaces, service/impl/ holds 42 implementations (§4)
├── security/                 JwtAuthenticationFilter, TenantContext, TenantFilterHelper,
│                             TenantOwnership, StompAuthChannelInterceptor  (§3)
├── socket/                   JobEventPublisher, presence, STOMP event listeners
└── util/                     29 helpers (JwtUtil, EncryptionUtil, ProcessUtil, ...)
```

Note the brief said `src/main/java/process/rest/**`; there is no `rest` package. The controllers
live in **`process/src/main/java/process/api/`**.

### 1.3 Conventions the code actually follows

**The `ResponseDto` envelope.** Every controller returns `ResponseEntity<?>` whose body is a
`ResponseDto` (`process/src/main/java/process/model/dto/ResponseDto.java`) with four nullable
fields: `status`, `message`, `data`, `paging`. `@JsonInclude(NON_NULL)` drops the empty ones
(line 11). `status` is one of two string constants, both literally `"ERROR"`/`"SUCCESS"`:

```java
public static String ERROR_MESSAGE = "ERROR";   // ProcessUtil.java:13
public static String ERROR         = "ERROR";   // ProcessUtil.java:27
public static String SUCCESS       = "SUCCESS"; // ProcessUtil.java:28
```

Two constants for the same value is a wart, not a distinction: controllers use `ERROR_MESSAGE`,
services use `ERROR`. A four-argument constructor exists for paged responses
(`ResponseDto.java:37-43`) and is used by the paged `sourceTask` listings.

**Controller shape.** Every controller is the same eleven lines per endpoint: a `try` that
delegates to one service call and wraps the result in `HttpStatus.OK`, and a `catch (Exception)`
that logs and returns `INTERNAL_ERROR_500` with HTTP 500. `AiAgentRestApi.java:32-40` is the
canonical example. Consequences are covered in §7.

**`@PreAuthorize` on the class, overridden on the method.** Every controller except
`AuthRestApi`, `NotifyResetApi` and `TenantRequestRestApi` carries a class-level `@PreAuthorize`
naming the *least* role that may reach the controller. A method-level `@PreAuthorize` **replaces**
the class-level one outright -- the annotation is not repeatable and Spring's metadata source
prefers the method. The code says this explicitly at `DynamicFormRestApi.java:22-26`. Every
override is called out in §2.

**`TenantContext`.** A four-slot `ThreadLocal` holder (`tenantId`, `userRole`, `appUserId`,
`username`) populated by `JwtAuthenticationFilter` and cleared in its `finally`
(`process/src/main/java/process/security/JwtAuthenticationFilter.java:44,57`). Services read it
rather than taking the principal as a parameter. §3 covers it in full.

**`EncryptionUtil`.** AES-256-GCM with a random 12-byte IV prefixed to the ciphertext,
Base64-encoded (`process/src/main/java/process/util/EncryptionUtil.java:20-57`). The key comes
from `LOOKUP_ENCRYPTION_KEY`; a blank key throws rather than falling back
(`EncryptionUtil.java:59-65`). It protects: lookup values marked encrypted, database connection
profile passwords, Kafka profile credentials, storage connection secrets and AI agent API keys.

**Fail-closed on missing secrets.** Three components refuse to start or run without their key:
`JwtUtil.secretKey()` (`JwtUtil.java:81-87`), `EncryptionUtil.secretKey()`, and
`NotifyResetApi.requireCallbackToken()` (`process/src/main/java/process/api/NotifyResetApi.java:56-63`),
which throws at `@PostConstruct` if `WORKER_CALLBACK_TOKEN` is unset.

**Author tag.** Every class carries `@author Nabeel Ahmed`. Longer classes carry a real prose
javadoc explaining the decision behind them; those are the best in-repo documentation there is and
several are quoted below.

---

## 2. Every REST endpoint

**181 endpoints across 27 controllers.** All paths below are relative to the `/api/v1` context
path. "Role" is the effective requirement after the role hierarchy in §3 is applied; rows marked
**(override)** carry a method-level `@PreAuthorize` that replaces the class-level one.

`AnalyticsRestApi` and its two endpoints were added on **2026-09-08** and are written up as
**§2.29**, after the anonymous-endpoint summary rather than in alphabetical position, so that every
section number a reader has already cited stays where they left it. The count above has not been
re-derived; add two to it.

### 2.1 `AiAgentRestApi` -- `/aiAgent.json` (class: `TENANT_ADMIN`)

`process/src/main/java/process/api/AiAgentRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/aiAgent.json/addAgent` | TENANT_ADMIN | Creates an AI agent (provider, endpoint, model, encrypted API key). |
| PUT | `/aiAgent.json/updateAgent` | TENANT_ADMIN | Updates one. |
| DELETE | `/aiAgent.json/deleteAgent` | TENANT_ADMIN | Deletes by `aiAgentId`. |
| GET | `/aiAgent.json/fetchAllAgents` | TENANT_USER **(override, :62)** | Lists the tenant's agents. |
| GET | `/aiAgent.json/fetchAgentByAgentId` | TENANT_USER **(override, :73)** | One agent by id. |
| GET | `/aiAgent.json/fetchToolByUuid` | TENANT_USER **(override, :84)** | Resolves an agent "tool" by uuid. |
| POST | `/aiAgent.json/processAdHoc` | TENANT_USER **(override, :95)** | Sends a free-form prompt through a configured agent. |

### 2.2 `AppUserRestApi` -- `/appUser.json` (class: `TENANT_ADMIN`)

`process/src/main/java/process/api/AppUserRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/appUser.json/listUsers` | TENANT_ADMIN | Users in the caller's tenant; all non-deleted users for a platform admin (`AppUserServiceImpl.java:127-136`). |
| POST | `/appUser.json/addUser` | TENANT_ADMIN | Creates a user; role escalation rules in §3.4. Emails a welcome/temporary password. |
| PUT | `/appUser.json/updateUser` | TENANT_ADMIN | Updates another user's profile. |
| PUT | `/appUser.json/changeUserStatus` | TENANT_ADMIN | Activate/deactivate/soft-delete. |
| PUT | `/appUser.json/resetPassword` | TENANT_ADMIN | Resets another user's password. |
| GET | `/appUser.json/me` | TENANT_USER **(override, :92)** | The signed-in user's own record. |
| GET | `/appUser.json/avatar` | TENANT_USER **(override, :111)** | Streams a user's picture bytes; 404 when there is none. Ownership decided in the service. |
| PUT | `/appUser.json/updateOwnProfile` | TENANT_USER **(override, :131)** | Own name/phone/position. |
| PUT | `/appUser.json/changeOwnPassword` | TENANT_USER **(override, :147)** | Body is a raw `Map` with `currentPassword`/`newPassword`; the catch deliberately logs no request detail (:156-157). |
| PUT | `/appUser.json/updateOwnAvatar` | TENANT_USER **(override, :163)** | Sets own avatar bucket/key. |

### 2.3 `AudioTranscriptRestApi` -- `/audioTranscript.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/AudioTranscriptRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/audioTranscript.json/extractFromUpload` | TENANT_USER | Multipart upload → external transcription service; `timestamps` flag. Returns 400 with `ex.getMessage()` on failure (:40). |
| POST | `/audioTranscript.json/extractFromBucket` | TENANT_USER | Same, reading the audio from a storage bucket/key instead. |

### 2.4 `AuthRestApi` -- `/auth.json` (**no `@PreAuthorize`**; `permitAll` matcher)

`process/src/main/java/process/api/AuthRestApi.java`; matcher at
`process/src/main/java/process/config/SecurityConfig.java:37`.

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/auth.json/login` | anonymous | Username/password → access + refresh token, plus profile fields and `mustChangePassword`. |
| POST | `/auth.json/refresh` | anonymous | Body `{"refreshToken": ...}` → a new access token; re-checks account and tenant status. |

### 2.5 `DashboardRestApi` -- `/dashboard.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/DashboardRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/dashboard.json/jobStatusStatistics` | TENANT_USER | Job counts by status over an optional date range. |
| GET | `/dashboard.json/userStatistics` | TENANT_USER | Per-user totals for the people dashboard. |
| GET | `/dashboard.json/jobRunningStatistics` | TENANT_USER | Running-job rollup. |
| GET | `/dashboard.json/weeklyRunningJobStatistics` | TENANT_USER | Weekly series; `startDate`/`endDate` **required**. |
| GET | `/dashboard.json/weeklyHrsRunningJobStatistics` | TENANT_USER | Weekly hours series; both dates required. |
| GET | `/dashboard.json/weeklyHrRunningStatisticsDimension` | TENANT_USER | One weekday/hour cell; `targetDate` + `targetHr` required. |
| GET | `/dashboard.json/weeklyHrRunningStatisticsDimensionDetail` | TENANT_USER | Drill-down rows for a cell, filterable by `jobStatus`/`jobId`. |

### 2.6 `DocumentConverterRestApi` -- `/documentConverter.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/DocumentConverterRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/documentConverter.json/supportedFormats` | TENANT_USER | Format matrix from the LibreOffice registry. |
| GET | `/documentConverter.json/fetchAllTasks` | TENANT_USER | The tenant's saved conversion tasks. |
| GET | `/documentConverter.json/fetchTaskById` | TENANT_USER | One task. |
| POST | `/documentConverter.json/convert` | TENANT_USER | Multipart convert via LibreOffice; optionally writes to `bucketName`/`targetFolder` and records a task when `save=true`. |
| DELETE | `/documentConverter.json/deleteTask` | TENANT_USER | Deletes a task row. |

### 2.7 `DynamicFormRestApi` -- `/dynamicForm.json` (class: `TENANT_ADMIN`)

`process/src/main/java/process/api/DynamicFormRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/dynamicForm.json/addForm` | TENANT_ADMIN | Creates a form. |
| PUT | `/dynamicForm.json/updateForm` | TENANT_ADMIN | Updates one. |
| DELETE | `/dynamicForm.json/deleteForm` | TENANT_ADMIN | Deletes one. |
| GET | `/dynamicForm.json/fetchAllForms` | TENANT_ADMIN | Lists forms. |
| GET | `/dynamicForm.json/fetchFormByFormId` | TENANT_ADMIN | One form by id. |
| GET | `/dynamicForm.json/fetchFormByUuid` | **anonymous** `permitAll()` **(override, :88)** | Opens a share link without an account. Also matched in `SecurityConfig.java:44`. |
| POST | `/dynamicForm.json/addField` | TENANT_ADMIN | Adds a field to a form. |
| PUT | `/dynamicForm.json/updateField` | TENANT_ADMIN | Updates a field. |
| DELETE | `/dynamicForm.json/deleteField` | TENANT_ADMIN | Deletes a field. |
| POST | `/dynamicForm.json/submitForm` | TENANT_USER **(override, :139)** | Answers a form. Deliberately **not** anonymous -- the javadoc at :129-138 says it reads the tenant from `TenantContext` and would need a rate limit and a matcher first. |
| PUT | `/dynamicForm.json/updateSubmission` | TENANT_USER **(override, :150)** | Edits a submission. |
| DELETE | `/dynamicForm.json/deleteSubmission` | TENANT_ADMIN | Deletes a submission. |
| GET | `/dynamicForm.json/fetchSubmissionsByFormId` | TENANT_ADMIN | All submissions for a form. |
| GET | `/dynamicForm.json/fetchSubmissionBySubmissionId` | TENANT_ADMIN | One submission. |
| GET | `/dynamicForm.json/fetchSubmissionByUuid` | **anonymous** `permitAll()` **(override, :191)** | A submission by its uuid, no account. Matched in `SecurityConfig.java:44`. |

### 2.8 `FileChatRestApi` -- `/fileChat.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/FileChatRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/fileChat.json/prepareContext` | TENANT_USER | Extracts a bucket object's text and readies a chat session against an agent. |
| POST | `/fileChat.json/endSession` | TENANT_USER | Drops the cached extraction for that bucket/key. |
| POST | `/fileChat.json/sendMessage` | TENANT_USER | One turn of the conversation with the model. |
| POST | `/fileChat.json/exportFile` | TENANT_USER | Turns the model's answer into xlsx/docx/pdf via LibreOffice. |

### 2.9 `FileShareRestApi` -- `/fileShare.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/FileShareRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/fileShare.json/send` | TENANT_USER | Emails a bucket file/folder to a recipient. |

### 2.10 `KafkaConnectionProfileRestApi` -- `/kafkaConnectionProfile.json` (class: `TENANT_ADMIN`)

`process/src/main/java/process/api/KafkaConnectionProfileRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/kafkaConnectionProfile.json/addProfile` | TENANT_ADMIN | Creates a broker profile (bootstrap servers, security protocol, SASL/SSL material). |
| PUT | `/kafkaConnectionProfile.json/updateProfile` | TENANT_ADMIN | Updates one. |
| **PUT** | `/kafkaConnectionProfile.json/deleteProfile` | TENANT_ADMIN | Deletes by id -- declared `RequestMethod.PUT`, not DELETE (:51). |
| GET | `/kafkaConnectionProfile.json/fetchAllProfiles` | TENANT_ADMIN | Profiles visible to the caller. |
| POST | `/kafkaConnectionProfile.json/setAsDefault` | TENANT_ADMIN | Marks one the tenant default. |
| POST | `/kafkaConnectionProfile.json/clearDefault` | TENANT_ADMIN | Clears the default. |
| POST | `/kafkaConnectionProfile.json/testConnection` | TENANT_ADMIN | Opens an AdminClient against the supplied profile. |
| GET | `/kafkaConnectionProfile.json/testTopic` | TENANT_ADMIN | Describes one topic on the resolved profile. |

### 2.11 `KafkaSecretRestApi` -- `/kafkaSecret.json` (class: `TENANT_ADMIN`)

`process/src/main/java/process/api/KafkaSecretRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/kafkaSecret.json/uploadSecret` | TENANT_ADMIN | Uploads a CA/cert/key file, typed by `KafkaSecretKind`, into object storage. |
| POST | `/kafkaSecret.json/generateTruststore` | TENANT_ADMIN | Builds a PKCS#12 truststore from a list of stored CA object keys. |
| POST | `/kafkaSecret.json/generateKeystore` | TENANT_ADMIN | Builds a keystore from a stored certificate + private key pair. |

### 2.12 `MessageQRestApi` -- `/message.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/MessageQRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/message.json/fetchLogs` | TENANT_USER | Paged/filterable queue-message log search. |
| DELETE | `/message.json/failJobLogs` | TENANT_USER | Marks a queue entry failed. |
| DELETE | `/message.json/interruptJobLogs` | TENANT_USER | Marks a queue entry interrupted. |
| PUT | `/message.json/changeJobStatus` | TENANT_USER | Sets a queue message's status. |

Worth flagging: three of the four mutate run state and are open to any signed-in user.

### 2.13 `NotificationRestApi` -- `/notification.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/NotificationRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/notification.json/list` | TENANT_USER | Own notifications, `unreadOnly`/`page`/`limit`. |
| GET | `/notification.json/unreadCount` | TENANT_USER | Badge count. |
| POST | `/notification.json/markRead/{notificationId}` | TENANT_USER | Marks one read. |
| POST | `/notification.json/markAllRead` | TENANT_USER | Marks all read. |

### 2.14 `NotifyResetApi` -- worker callbacks (**no `@PreAuthorize`**; shared-secret header)

`process/src/main/java/process/api/NotifyResetApi.java`. All three are `permitAll` in
`SecurityConfig.java:42` and authenticate instead with a constant-time comparison of the
`X-Worker-Token` header (`NotifyResetApi.java:73-91`). The class refuses to start when
`WORKER_CALLBACK_TOKEN` is unset (:56-63).

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/changeState/jobId/{jobId}/jobQueueId/{jobQueueId}/jobStatus/{jobStatus}` | `X-Worker-Token` | Worker reports a run's status. Only `Running`/`Failed`/`Completed` accepted (:109); `jobStatusMessage` required; sets `endTime` on terminal states. |
| POST | `/addLogsBatch/jobId/{jobId}/jobQueueId/{jobQueueId}` | `X-Worker-Token` | Many log lines in one request; body `{"messages": [...]}`. Added because per-line posting was ~97% of a 500-job run's elapsed time (:125-131). |
| POST | `/addLogs/jobId/{jobId}/jobQueueId/{jobQueueId}` | `X-Worker-Token` | One log line. |

`SecurityConfig.java:39-42` carries the note that `"/addLogs/**"` does not match
`/addLogsBatch/...` -- an Ant pattern does not cross a segment boundary -- which is why the batch
path is listed separately.

### 2.15 `OllamaRestApi` -- `/ollama.json` (class: `TENANT_ADMIN`)

`process/src/main/java/process/api/OllamaRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/ollama.json/listModels` | TENANT_ADMIN | `GET /api/tags` on the configured Ollama. |
| POST | `/ollama.json/pullModel` | TENANT_ADMIN | `POST /api/pull` (30-minute read timeout). |
| DELETE | `/ollama.json/deleteModel` | TENANT_ADMIN | `DELETE /api/delete`. |

All three return HTTP 400 with the upstream error text on failure rather than 500 (:37-39, :50-52,
:63-65) -- the only controller in the codebase that does this uniformly.

### 2.16 `PdfHighlighterTaskRestApi` -- `/pdfHighlighter.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/PdfHighlighterTaskRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/pdfHighlighter.json/fetchAllPdfHighlighterTask` | TENANT_USER | The tenant's highlighter tasks. |
| GET | `/pdfHighlighter.json/fetchPdfHighlighterTaskById` | TENANT_USER | One task. |
| POST | `/pdfHighlighter.json/addPdfHighlighterTask` | TENANT_USER | Creates one. |
| PUT | `/pdfHighlighter.json/updatePdfHighlighterTask` | TENANT_USER | Updates one. |
| DELETE | `/pdfHighlighter.json/deletePdfHighlighterTask` | TENANT_USER | Deletes one. |
| GET | `/pdfHighlighter.json/fetchPdfHighlighterFields` | TENANT_USER | The task's field/xpath definitions. |
| POST | `/pdfHighlighter.json/syncPdfHighlighterFields` | TENANT_USER | Replaces the field set in one call. |
| POST | `/pdfHighlighter.json/uploadPdfHighlighterFile` | TENANT_USER | Attaches the PDF to a task. |
| GET | `/pdfHighlighter.json/downloadPdfHighlighterFile` | TENANT_USER | Streams the PDF inline; `IllegalArgument`/`IllegalState` become 400 with the message (:140-142). |

### 2.17 `QueryEngineRestApi` -- `/queryEngine.json` (class: `TENANT_ADMIN`)

`process/src/main/java/process/api/QueryEngineRestApi.java`. The largest controller: four
services behind one prefix. Twelve of its twenty-two methods lower the bar to `TENANT_USER`.

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/queryEngine.json/connections/add` | TENANT_ADMIN | New database connection profile. |
| PUT | `/queryEngine.json/connections/update` | TENANT_ADMIN | Update one. |
| DELETE | `/queryEngine.json/connections/delete` | TENANT_ADMIN | Delete one. |
| GET | `/queryEngine.json/connections/fetchAll` | TENANT_USER **(override, :75)** | List profiles. |
| GET | `/queryEngine.json/connections/fetchById` | TENANT_USER **(override, :86)** | One profile. |
| POST | `/queryEngine.json/connections/testConnection` | TENANT_USER **(override, :100)** | Test a *saved* profile as it stands; testing an unsaved profile or altered host/password is held to TENANT_ADMIN inside the service (:97-99). |
| POST | `/queryEngine.json/queries/add` | TENANT_ADMIN | Save a query definition (SQL encrypted at rest). |
| PUT | `/queryEngine.json/queries/update` | TENANT_ADMIN | Update one. |
| DELETE | `/queryEngine.json/queries/delete` | TENANT_ADMIN | Delete one. |
| GET | `/queryEngine.json/queries/fetchAll` | TENANT_USER **(override, :141)** | List queries. |
| GET | `/queryEngine.json/queries/fetchById` | TENANT_USER **(override, :152)** | One query. |
| POST | `/queryEngine.json/queries/validate` | TENANT_USER **(override, :165)** | Validate a saved query by id; ad-hoc SQL on the body is TENANT_ADMIN in the service (:163-164). |
| POST | `/queryEngine.json/queries/preview` | TENANT_USER **(override, :178)** | Same split as validate (:176-177). |
| POST | `/queryEngine.json/executions/execute` | TENANT_USER **(override, :189)** | Runs a query, streams the result to CSV in a bucket. |
| GET | `/queryEngine.json/executions/fetchAll` | TENANT_USER **(override, :200)** | Execution history. |
| GET | `/queryEngine.json/executions/fetchById` | TENANT_USER **(override, :211)** | One execution. |
| GET | `/queryEngine.json/executions/fetchByQueryId` | TENANT_USER **(override, :222)** | Executions for one query. |
| POST | `/queryEngine.json/schedules/add` | TENANT_ADMIN | New recurring schedule. |
| PUT | `/queryEngine.json/schedules/update` | TENANT_ADMIN | Update one. |
| DELETE | `/queryEngine.json/schedules/delete` | TENANT_ADMIN | Delete one. |
| GET | `/queryEngine.json/schedules/fetchAll` | TENANT_USER **(override, :263)** | List schedules. |
| GET | `/queryEngine.json/schedules/fetchById` | TENANT_USER **(override, :274)** | One schedule. |

### 2.18 `ReportRestApi` -- `/report.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/ReportRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/report.json/runs` | TENANT_USER | The run rows a report is built from; grouping happens in the browser (:38). |
| POST | `/report.json/export` | TENANT_USER | Builds the file server-side and sends it to one of three destinations (download / bucket / configured endpoint). |

### 2.19 `SettingRestApi` -- `/setting.json` (class: `TENANT_ADMIN`)

`process/src/main/java/process/api/SettingRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/setting.json/dynamicQueryResponse` | **PLATFORM_ADMIN (override, :43)** | Runs the SQL it is given, as given. The service refuses non-platform-admins too (`SettingServiceImpl.java:197`); the annotation exists so an auditor sees it (:38-42). |
| GET | `/setting.json/appSetting` | TENANT_ADMIN | Task types + lookups the console needs; cached per tenant (`SettingServiceImpl.java:208`). |
| POST | `/setting.json/addSourceTaskType` | TENANT_ADMIN | New task type (topic/partition, Kafka profile). |
| PUT | `/setting.json/updateSourceTaskType` | TENANT_ADMIN | Update one. |
| DELETE | `/setting.json/deleteSourceTaskType` | TENANT_ADMIN | Delete one. |
| GET | `/setting.json/fetchKafkaRoute` | TENANT_ADMIN | The tenant→task-type→profile binding. |
| PUT | `/setting.json/setKafkaRoute` | TENANT_ADMIN | Bind a task type to a Kafka profile for this tenant. |
| DELETE | `/setting.json/deleteKafkaRoute` | TENANT_ADMIN | Remove the binding. |
| POST | `/setting.json/addLookupData` | TENANT_ADMIN | New lookup row (value optionally encrypted). |
| PUT | `/setting.json/updateLookupData` | TENANT_ADMIN | Update one. |
| GET | `/setting.json/fetchSubLookupByParentId` | TENANT_ADMIN | Children of a lookup parent. |
| **PUT** | `/setting.json/deleteLookupData` | TENANT_ADMIN | Delete -- declared `RequestMethod.PUT` with a body (:161). |
| POST | `/setting.json/xmlCreateChecker` | TENANT_ADMIN | Builds a task-payload XML from tag descriptors. Declared as `path = "xmlCreateChecker"` with **no leading slash** (:172); Spring still resolves it under the class prefix. |

### 2.20 `SourceJobRestApi` -- `/sourceJob.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/SourceJobRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/sourceJob.json/addSourceJob` | TENANT_USER | Creates a job + its scheduler row. |
| PUT | `/sourceJob.json/updateSourceJob` | TENANT_USER | Updates a job. |
| **PUT** | `/sourceJob.json/deleteSourceJob` | TENANT_USER | Soft-deletes (body-carrying PUT). |
| PUT | `/sourceJob.json/toggleSourceJobStatus` | TENANT_USER | Active/inactive. |
| GET | `/sourceJob.json/myActivity` | TENANT_USER | Own recent activity; `limit` clamped to 1..50 and `windowDays` to 1..90 in the controller (:101-102). Takes no user parameter on purpose (:90-93). |
| GET | `/sourceJob.json/listSourceJob` | TENANT_USER | The job list; strips `taskPayload` from each row for size (`SourceJobServiceImpl.java:500-506`). |
| GET | `/sourceJob.json/fetchSourceJobDetailWithSourceJobId` | TENANT_USER | One job with its task. |
| GET | `/sourceJob.json/fetchSourceJobQueueListWithJobId` | TENANT_USER | The job's run history. |
| POST | `/sourceJob.json/runSourceJob` | TENANT_USER | Queues a manual run. |
| POST | `/sourceJob.json/skipNextSourceJob` | TENANT_USER | Skips the next scheduled occurrence. |
| POST | `/sourceJob.json/askAssistant` | TENANT_USER | Asks a configured AI agent about one job; facts gathered server-side from the id (:164-168). |
| GET | `/sourceJob.json/findSourceJobAuditLog` | TENANT_USER | Audit lines for one run. |
| GET | `/sourceJob.json/downloadSourceJobTemplateFile` | TENANT_USER | xlsx upload template. |
| GET | `/sourceJob.json/downloadListSourceJob` | TENANT_USER | xlsx export of the job list. |
| POST | `/sourceJob.json/uploadSourceJob` | TENANT_USER | Bulk-creates jobs from an xlsx. |

### 2.21 `SourceTaskRestApi` -- `/sourceTask.json` (class: `TENANT_ADMIN`)

`process/src/main/java/process/api/SourceTaskRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/sourceTask.json/addSourceTask` | TENANT_ADMIN | New task (pipeline, home page, XML payload). |
| PUT | `/sourceTask.json/updateSourceTask` | TENANT_ADMIN | Update one. |
| **PUT** | `/sourceTask.json/deleteSourceTask` | TENANT_ADMIN | Soft-delete (body-carrying PUT). |
| **POST** | `/sourceTask.json/listSourceTask` | TENANT_USER **(override, :69)** | Paged/sorted/date-filtered list; search text in the body, paging in query params. |
| **POST** | `/sourceTask.json/fetchAllLinkJobsWithSourceTaskId` | TENANT_USER **(override, :88)** | Paged jobs linked to one task. |
| GET | `/sourceTask.json/fetchAllLinkSourceTaskWithSourceTaskTypeId` | TENANT_USER **(override, :108)** | Tasks of a task type. |
| GET | `/sourceTask.json/fetchSourceTaskWithSourceTaskId` | TENANT_USER **(override, :120)** | One task. |
| GET | `/sourceTask.json/downloadListSourceTask` | TENANT_ADMIN | xlsx export. |
| GET | `/sourceTask.json/downloadSourceTaskTemplate` | TENANT_ADMIN | xlsx template. |
| POST | `/sourceTask.json/uploadSourceTask` | TENANT_ADMIN | Bulk import. |

### 2.22 `StorageBrowserRestApi` -- `/storage.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/StorageBrowserRestApi.java`. The class comment (:30-35) is
explicit that the role is only the floor -- which bucket and key a caller may reach is settled per
request inside `StorageBrowserServiceImpl` (§3.5).

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/storage.json/buckets` | TENANT_USER | Buckets the caller may see (storage connections + legacy `BUCKET_LIST` lookups). |
| GET | `/storage.json/listObjects` | TENANT_USER | Paged listing; `maxKeys` default 50, capped in the service. |
| GET | `/storage.json/objectMetadata` | TENANT_USER | Size/content-type/etag for one key. |
| GET | `/storage.json/previewObject` | TENANT_USER | Streams `inline`, honours HTTP `Range` (206 + `Content-Range`). |
| GET | `/storage.json/downloadObject` | TENANT_USER | Same but `attachment`. |
| POST | `/storage.json/uploadObject` | TENANT_USER | Multipart upload into `bucket`+`prefix`. |
| POST | `/storage.json/createFolder` | TENANT_USER | Zero-byte folder marker. |
| DELETE | `/storage.json/deleteObject` | TENANT_USER | One key. |
| POST | `/storage.json/deleteObjects` | TENANT_USER | Bulk delete from a body. |
| DELETE | `/storage.json/deleteFolder` | TENANT_USER | Recursive prefix delete. |
| POST | `/storage.json/renameFolder` | TENANT_USER | Copy-then-delete rename. |

### 2.23 `StorageConnectionRestApi` -- `/storageConnection.json` (class: `TENANT_ADMIN`)

`process/src/main/java/process/api/StorageConnectionRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/storageConnection.json/addConnection` | TENANT_ADMIN | New connection (provider, endpoint, encrypted secret, alias). |
| POST | `/storageConnection.json/cloneConnection` | TENANT_ADMIN | Copies `sourceId` into a new alias. |
| PUT | `/storageConnection.json/updateConnection` | TENANT_ADMIN | Update one. |
| DELETE | `/storageConnection.json/deleteConnection` | TENANT_ADMIN | Delete one. |
| GET | `/storageConnection.json/fetchAllConnections` | TENANT_ADMIN | List connections. |
| GET | `/storageConnection.json/fetchConnectionById` | TENANT_ADMIN | One connection. |
| POST | `/storageConnection.json/testConnection` | TENANT_ADMIN | Live check of a saved connection. |
| POST | `/storageConnection.json/discoverBuckets` | TENANT_ADMIN | Enumerates buckets the supplied credentials can see. |

### 2.24 `TaskFormRestApi` -- `/taskForm.json` (class: `TENANT_ADMIN`)

`process/src/main/java/process/api/TaskFormRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/taskForm.json/listForms` | TENANT_ADMIN | All form definitions -- "a map of the tenant's whole pipeline surface" (:20-22). |
| GET | `/taskForm.json/formForPipeline` | TENANT_USER **(override, :51)** | The single form for a pipeline the caller is editing. |
| POST | `/taskForm.json/saveForm` | TENANT_ADMIN **(override, :62 -- restates the class value)** | Creates/updates a definition. |
| DELETE | `/taskForm.json/deleteForm` | TENANT_ADMIN **(override, :73 -- restates the class value)** | Deletes a definition. |

### 2.25 `TenantRequestRestApi` -- `/tenantRequest.json` (**no class-level `@PreAuthorize`**)

`process/src/main/java/process/api/TenantRequestRestApi.java`. The javadoc at :41-48 explains why:
adding a class-level annotation would silently close sign-up.

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/tenantRequest.json/submit` | **anonymous** `permitAll()` (:49) | Records a workspace request; everything in the body treated as unverified. Also matched in `SecurityConfig.java:47`. |
| GET | `/tenantRequest.json/listRequests` | PLATFORM_ADMIN (:60) | Lists pending requests. |
| POST | `/tenantRequest.json/approve` | PLATFORM_ADMIN (:71) | Creates the tenant, its first `TENANT_ADMIN` and that account's password. |
| POST | `/tenantRequest.json/reject` | PLATFORM_ADMIN (:84) | Rejects with an optional note. |

### 2.26 `TenantRestApi` -- `/tenant.json` (class: `PLATFORM_ADMIN`)

`process/src/main/java/process/api/TenantRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/tenant.json/listTenants` | PLATFORM_ADMIN | All tenants. |
| POST | `/tenant.json/addTenant` | PLATFORM_ADMIN | Creates a tenant. |
| PUT | `/tenant.json/updateTenant` | PLATFORM_ADMIN | Updates one. |
| PUT | `/tenant.json/changeTenantStatus` | PLATFORM_ADMIN | Active/suspended/deleted. A suspended tenant's users are refused at login and refresh (`AuthServiceImpl.java:101-112`). |

There is **no tenant delete endpoint** on this controller -- status change is the only removal
path. (Checked the whole file; `TenantServiceImpl` exposes only the four methods above.)

### 2.27 `TextCleanerRestApi` -- `/textCleaner.json` (class: `TENANT_USER`)

`process/src/main/java/process/api/TextCleanerRestApi.java`

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/textCleaner.json/clean` | TENANT_USER | Pure function over the request text (`TextCleanerUtil.clean`); the one controller with no service dependency at all. |

### 2.28 Endpoints reachable without a token

Collected from `SecurityConfig.java:36-54`:

| Pattern | Note |
|---|---|
| `OPTIONS /**` | CORS preflight. |
| `/auth.json/**` | login + refresh. |
| `/ws/**` | STOMP handshake; the token is checked on the STOMP frame instead (§3.6). |
| `/changeState/**`, `/addLogs/**`, `/addLogsBatch/**` | Worker callbacks, gated by `X-Worker-Token`. |
| `/dynamicForm.json/fetchFormByUuid`, `/dynamicForm.json/fetchSubmissionByUuid` | Public share links. |
| `POST /tenantRequest.json/submit` | Sign-up. |
| `/actuator/health`, `/actuator/health/**`, `/actuator/info` | Liveness. Everything else under `/actuator/**` requires `PLATFORM_ADMIN` (:52). |
| `/swagger-ui/**`, `/swagger-ui.html`, `/v2/api-docs`, `/swagger-resources/**`, `/webjars/**` | API docs -- open in every profile. |

Everything else is `anyRequest().authenticated()` (:55).

Analytics Studio adds nothing to this list. Both of its endpoints are authenticated, and
`SecurityConfig` was not touched for it.

### 2.29 `AnalyticsRestApi` -- `/analytics.json` (class: `TENANT_USER`) — added 2026-09-08

`process/src/main/java/process/api/AnalyticsRestApi.java` (109 lines). Phase one of Analytics
Studio: read a dataset where it already lives in object storage. Two endpoints, both GET, both
under the class-level `@PreAuthorize("hasRole('TENANT_USER')")` at :43 — the same floor as
`StorageBrowserRestApi` (§2.22) and for the same stated reason (:32-34): which connections a
caller may reach is not a question a role can answer, and is settled per request against the
connection's own tenant.

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/analytics.json/schema` | TENANT_USER | `?connection=<alias>&path=<path>`. The dataset's columns and their DuckDB types, without reading its rows. |
| GET | `/analytics.json/preview` | TENANT_USER | `?connection=<alias>&path=<path>&page=0&pageSize=<optional>`. One page of rows plus the total row count. `pageSize` is a request, not an instruction — it is clamped in the service (:86-88). |

**The caller names a connection and a path. It never names a bucket, and it never names a URL.**
This is the API's central security property rather than a convention, and it is worth restating
wherever these endpoints are described. The bucket comes from the `StorageConnection` record —
`getBucketName()`, falling back to the alias when that is null, which is what
`StorageBrowserServiceImpl` already does (`DatasetResolver.java:89-93`). So "use these credentials
against a different bucket" is not a request this API can express.

That was a mid-build change, and it is recorded here because the reasoning outlives it: the first
design took `storageConnectionId` + `bucket` + `path`. Switching to the alias both matched the
Object Browser — the two screens now address storage identically — and removed a whole class of
request rather than validating it. One test became obsolete as a result and was replaced by one
asserting the stronger property
(`DatasetResolverTest.takesTheBucketFromTheConnectionRecord_notFromTheRequest`, :155-170).

**Failures follow the house convention** (§7.1): a business failure is HTTP **200** with a
`ResponseDto` of status `ERROR`, carrying the `AnalyticsException` message verbatim because that
message was written for a reader (:71-75, :100-102). Anything else is logged with its stack and
returned as the generic `INTERNAL_ERROR_500` at 500 (:76-80, :103-107). The wordings a user can
actually reach are listed in §4 under "Analytics Studio".

**There is deliberately no endpoint here that accepts SQL** (:36-38). Phase one ships no
user-written SQL at all — see §4 for what else phase one does not include.

---

## 3. The authorization model

### 3.1 The three roles and the hierarchy

`process/src/main/java/process/model/enums/UserRole.java` defines exactly three values:
`PLATFORM_ADMIN`, `TENANT_ADMIN`, `TENANT_USER`.

`process/src/main/java/process/config/MethodSecurityConfig.java:29` wires them into a
`RoleHierarchyImpl`:

```
ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN
ROLE_TENANT_ADMIN  > ROLE_TENANT_USER
```

`createExpressionHandler()` (:19-24) installs that hierarchy on the
`DefaultMethodSecurityExpressionHandler`, which is what makes `hasRole('TENANT_USER')` admit an
admin. Every `@PreAuthorize` in the application names the **least** role that may reach the
endpoint and relies on this. The hierarchy is pinned by
`process/src/test/java/process/config/MethodSecurityConfigRoleHierarchyTest.java`, which
instantiates the real config object rather than restating the string (:32, and the reasoning at
:14-25).

`@PreAuthorize` appears **only** in `process/src/main/java/process/api/` -- no service or
repository carries one (verified by grepping the whole of `src/main/java` excluding `api`).

What each role may do, in the aggregate:

| | PLATFORM_ADMIN | TENANT_ADMIN | TENANT_USER |
|---|---|---|---|
| Tenants (`/tenant.json`), tenant requests, `dynamicQueryResponse` | yes | no | no |
| Actuator beyond health/info | yes | no | no |
| Users, AI agents, task types, lookups, forms, Kafka profiles/secrets, storage connections, query authoring, task authoring | yes | yes | no |
| Jobs, dashboards, storage browsing, file chat, reports, notifications, message queue, PDF highlighter, document converter, audio transcript, text cleaner, query execution/reading | yes | yes | yes |
| Own profile, password, avatar | yes | yes | yes |
| Cross-tenant visibility | yes (see 3.3) | own tenant only | own tenant only |

The role alone is never the whole answer: within a role, `TenantContext` + the Hibernate filter +
`TenantOwnership` decide *which rows*.

### 3.2 `TenantContext`

`process/src/main/java/process/security/TenantContext.java` -- four `ThreadLocal`s
(`TENANT_ID`, `USER_ROLE`, `APP_USER_ID`, `USERNAME`), a `set(...)`, per-field getters, an
`isPlatformAdmin()` convenience (:38-40) and a `clear()` that removes all four (:42-47).

It is populated in `process/src/main/java/process/security/JwtAuthenticationFilter.java`:

- Reads `Authorization: Bearer ...`, parses the claims, and **skips refresh tokens** (:39) so a
  refresh token cannot be used as an access token.
- Sets `TenantContext` and a `UsernamePasswordAuthenticationToken` whose single authority is
  `"ROLE_" + userRole` straight from the claim (:44-47).
- An invalid token is logged at debug and the request continues **unauthenticated** (:50-53) --
  it does not 401 there; `authorizeRequests()` does that later.
- `TenantContext.clear()` runs in a `finally` around `filterChain.doFilter` (:54-58), which is
  what keeps a pooled thread from leaking one caller's tenant into the next request.

Consequence worth stating plainly: **role and tenant come from the token, not from a per-request
database read.** An access token issued before a user was deactivated or moved keeps working until
it expires (default 30 minutes, `jwt.access-token.expiry-minutes`). Status is re-checked only at
`/auth.json/login` and `/auth.json/refresh` (`AuthServiceImpl.java:60,93`).

Background threads carry no `TenantContext` at all. Two places set it deliberately:
`ProcessCron.pollDueQuerySchedules` sets it per schedule and clears it before advancing
`nextRunAt`, so the audit listener does not stamp a human author on a machine run
(`process/src/main/java/process/engine/cron/ProcessCron.java:96,103-106`). Everything else on a
scheduler thread uses the "trusted"/workflow paths described in 3.5.

### 3.3 The Hibernate tenant filters

`process/src/main/java/process/security/TenantFilterHelper.java` unwraps the `EntityManager` to a
Hibernate `Session` and either enables `tenantFilter` with the caller's `tenantId`, or **disables**
it when the tenant is null or the caller is a platform admin (:28-33). It is called explicitly at
the top of service methods -- there is no aspect or interceptor doing it globally. Roughly 60 call
sites across `QueryScheduleServiceImpl`, `SourceJobServiceImpl`, `ConnectionProfileServiceImpl`,
`AiAgentServiceImpl`, `DocumentConverterServiceImpl` and others.

Fifteen entities declare the filter. Two conditions are in use:

| Condition | Entities |
|---|---|
| `tenant_id = :tenantId` | `SourceJob`, `SourceTask`, `DocumentConverterTask`, `PdfHighlighterTask`, `QueryDefinition`, `QueryExecution`, `QuerySchedule`, `DatabaseConnectionProfile`, `DynamicForm`, `AiAgent`, `TenantTaskTypeKafkaRoute` |
| `(tenant_id = :tenantId or tenant_id is null)` | `SourceTaskType`, `KafkaConnectionProfile`, `TaskForm`, `StorageConnection` |

The second form is the "shared catalogue" case: a null-tenant row is platform-owned and published
to every tenant to read and link to.

`process/src/test/java/process/model/pojo/TenantFilterDeclarationTest.java` enforces this. Its
`everyTenantColumnIsEitherFilteredOrListedHere` test (:75-90) scans every `pojo/*.java` source for
a `tenant_id` column and fails if it has no `tenantFilter` and is not on an explicit exemption
list. The exemptions, with the reasons given at :34-48:

- **`Tenant`** -- `tenant_id` is its own primary key.
- **`AppUser`** -- the login lookup and the created-by name resolver both read outside the
  caller's tenant, and login runs before there is a tenant.
- **`LookupData`** -- parent rows are engine state and the tree is loaded into a process-wide
  cache from inside tenant requests; a filtered rebuild would serve one tenant's view to everyone.
- **`Notification`** -- read by recipient, which is narrower than by tenant.

Note the class comment at :19-28: an entity carrying `tenant_id` *without* the declaration reads
as scoped at every call site and silently returns every tenant's rows. That test exists because
nothing throws or logs when that happens. `StorageConnection` carries the *shared* condition
(`StorageConnection.java:44`) even though `StorageBrowserServiceImpl.collectBuckets` deliberately
does **not** share tenant-less connections with tenants (:99-105); the service-level rule is the
narrower of the two.

### 3.4 `process.security.TenantOwnership`

`process/src/main/java/process/security/TenantOwnership.java` is the single place the ownership
rule lives. Its own javadoc (:6-25) explains that every service had grown a private copy and the
copies had begun to disagree about tenant-less rows. Two methods:

```java
public static boolean isOwnedByCaller(Long ownerTenantId) {      // :35-41
    if (TenantContext.isPlatformAdmin()) return true;
    Long callerTenantId = TenantContext.getTenantId();
    return callerTenantId != null && Objects.equals(ownerTenantId, callerTenantId);
}

public static boolean isVisibleToCaller(Long ownerTenantId) {    // :47-49
    return ownerTenantId == null || isOwnedByCaller(ownerTenantId);
}
```

The rules, stated precisely:

1. A platform admin owns everything.
2. **A caller with no tenant of its own owns nothing** -- refused outright rather than compared
   equal to null-tenant rows. This is the case that used to fall open: `null == null` handed a
   tenant-less caller a platform admin's data. `AppUserServiceImpl.readAvatar` documents exactly
   that bug and its fix at :113-118.
3. A `null` tenantId means **platform-owned, not ownerless**. For the eleven entities with the
   plain-equality filter such a row is invisible in list queries, so `isOwnedByCaller` keeps it
   unreachable by id too.
4. For the four shared catalogues, read paths ask `isVisibleToCaller` (published to everyone)
   while write paths keep asking `isOwnedByCaller` (only a platform admin may change them).

Pinned by `process/src/test/java/process/security/TenantOwnershipTest.java` (10 tests).

Beyond the shared helper, services apply their own rules. The ones worth knowing:

- **`AppUserServiceImpl.addUser`** (`:155-163`): a non-platform-admin cannot create a
  `PLATFORM_ADMIN`, and cannot create a `TENANT_ADMIN` either -- "a second administrator is a
  second set of keys to everything the workspace holds, so who gets one is the platform's
  decision". A tenant admin may only create `TENANT_USER`s, always in its own tenant (:175).
- **`ConnectionProfileServiceImpl`** (`:63-70`, helper at `:69`) and **`QueryDefinitionServiceImpl`** (`:77-84`, helper at `:83`)
  both expose a private `isTenantAdmin()` used to gate the ad-hoc/unsaved branches that the
  controller lowered to `TENANT_USER`.
- **`KafkaSecretServiceImpl.canUseObject`** (`:202-224`): a platform admin may point at any stored
  object; otherwise the caller must be a `TENANT_ADMIN` **with** a tenant, and the object's owner
  must not be a `TENANT_USER`.
- **`SourceJobServiceImpl.validateAssignee`** (`:513-530`): a job may be assigned to a
  `PLATFORM_ADMIN` regardless of tenant; any other assignee must be in the job's tenant.
- **`SettingServiceImpl.dynamicQueryResponse`** (`:195-198`): refuses anyone but a platform admin
  in the method body as well as in the annotation.
- **`TaskFormServiceImpl`** (`:53`, `:211`) and **`SourceTaskServiceImpl`** (`:92`, `:114`,
  `:127`) implement the shared-catalogue read/write split described above.

### 3.5 Storage: the guard that a role cannot express

`process/src/main/java/process/model/service/impl/StorageBrowserServiceImpl.java` carries the
richest authorization logic in the codebase, because "which bucket" is not a role question.

- **`collectBuckets(trusted)`** (`:91-133`) narrows the bucket list to the caller unless the caller
  is a platform admin or the call is a trusted workflow. A tenant-less storage connection is
  platform-owned and is **not** offered to tenants (:100-104) -- the comment records that
  `etl-bucket`/`etl-avatar` used to appear in every workspace.
- **`resolveServiceForCaller(bucket, key)`** (`:431-437`) refuses a platform bucket to anyone but
  a platform admin, on every verb, with one exception: the caller's own avatar object
  (`isOwnProfileObject`, key prefixed `"<appUserId>/profile/"`, :497-512).
- **`isPlatformBucket`** (`:455`) names `etl-bucket` and `etl-avatar` literally rather than
  inferring them from a tenant-less connection row, because no migration creates a connection for
  either. The comment (:440-454) records the consequence of the old version: a tenant admin could
  add a `BUCKET_LIST` lookup entry called `etl-bucket` and be handed the platform's own client,
  "and with it every tenant's Kafka key material and every user's picture".
- **`isSafeKey`** (`:405-419`) rejects backslashes, leading `/`, and any `.`/`..` path segment.
- **`resolveService(bucket, trusted)`** (`:523`) does the tenant comparison for connection-backed
  buckets and wraps the client in `BucketRewritingStorageService` when the alias differs from the
  real bucket name.
- The **`*ForWorkflow`** methods (`uploadForWorkflow`, `readForWorkflow`, :243, :303, :310) are the
  trusted path used by scheduler/startup threads that have no `TenantContext`. They are never
  reachable from a request that named its own bucket.

This is the most heavily tested area of the codebase: `StorageBrowserServiceImplTenantIsolationTest`
(20 tests), `PlatformBucketAccessTest` (10), `PlatformBucketNamedGuardTest` (5),
`OwnAvatarFolderGuardTest` (5), plus the `BucketAccessE2EIT` suite (21).

### 3.6 WebSocket authorization

`process/src/main/java/process/security/StompAuthChannelInterceptor.java`:

- On `CONNECT`, parses the `Authorization` native header and sets the principal; a frame with no
  header connects **unauthenticated** (:56-58).
- On `SUBSCRIBE` to `/topic/jobs.{tenantId}` (`checkSubscribe`, :68-103): a missing or refresh
  token drops the frame (returns `null`); a `PLATFORM_ADMIN` may watch any tenant and is the only
  role allowed on the cross-tenant `/topic/jobs.all` feed (:84-93); anyone else must have a token
  whose `tenantId` matches the destination (:94-97).
- Destinations that do not start with `/topic/jobs.` pass through unchecked (:70-72). `/queue` and
  `/user` are enabled on the broker (`WebSocketConfig.java:43`); their authorization is Spring's
  default user-destination scoping, **not verified** beyond reading `WebSocketConfig` and
  `NotificationService.sendNotificationToSpecificUser` (`socket/NotificationService.java:34`).

### 3.7 Analytics: the engine is the untrusted component (added 2026-09-08)

Everything above this point defends rows from callers. Analytics Studio inverts that, and it is
worth stating in the authorization model rather than only in the package inventory: DuckDB can read
and write local files, open sockets and install extensions, and it runs **inside this JVM, as the
backend**. The engine is the dangerous part; the caller is merely the way it gets pointed at
something. `DuckDbSessionFactory`'s class javadoc says so directly (`:18-23`), and the ordered
lock-down that follows from it is set out in §4 under "Analytics Studio", where the order is
load-bearing rather than incidental.

The tenant half of the story reuses what §3.4 already established.
`process/src/main/java/process/analytics/DatasetResolver.java` is the **only** way to obtain a
`DatasetRef` — the DTO's constructor is package-private (`DatasetRef.java:59`) — so the checks
cannot be skipped at a call site, because there is no call site that can skip them. In order
(`DatasetResolver.java:56-104`):

1. an **allow-list** on the path, `[A-Za-z0-9._*?/=+ -]+` (`:36`), which notably excludes the quote
   that would end a SQL literal and the backslash that would escape one;
2. a **separate `..` check** (`:70-72`), because `..` is made entirely of permitted characters and
   is the one shape an allow-list cannot exclude;
3. `findByAlias`, then `status != Delete`, then **`TenantOwnership.isVisibleToCaller`** (`:74-77`) —
   the shared helper from §3.4, not a private copy;
4. `provider.isObjectStore()` (`:84`, and `StorageProvider.java:14-16`), so an FTP or FTPS
   connection is refused with a reason rather than failing later inside a scan;
5. the bucket taken from the record, never from the request (§2.29);
6. format detection from the extension (`:99-103`).

**"Does not exist" and "belongs to another workspace" are given identical wording** — literally
`"Storage connection not found."` for both (`:78-82`, with the reasoning at `:79-80`). Telling the
two apart is how an alias becomes an enumeration oracle. A test named for exactly that property —
`refusesAConnectionThatDoesNotExistWithTheSameWords` (`DatasetResolverTest.java:110`) — exists to
keep the two messages from drifting apart later.

---

## 4. Services -- what each is responsible for

29 interfaces in `process/src/main/java/process/model/service/`, 42 implementations in
`.../service/impl/` (13,789 lines). Grouped by what they own.

### Identity and tenancy

| Class | Responsibility |
|---|---|
| `AuthServiceImpl` (136) | Login and refresh. Checks account status **and** tenant status (`:101-112`), stamps `lastLoginAt`, returns access+refresh tokens plus `mustChangePassword` so the console can force a change at sign-in (:127-132). |
| `AppUserServiceImpl` (633) | User CRUD, status change, admin password reset, own-profile/own-password/own-avatar, avatar byte streaming. Role-escalation rules, phone normalisation via libphonenumber, generated temporary passwords, welcome email. |
| `TenantServiceImpl` (166) | Tenant list/add/update/status. |
| `TenantRequestServiceImpl` (242) | Public workspace requests; approval creates the tenant, its first `TENANT_ADMIN` and that account's password (:134-210). Nothing in a submitted request is trusted (class javadoc). |
| `TenantSeedService` (152) | `@PostConstruct` bootstrap: ensures a `default` tenant, seeds `admin@platform.local` from `PLATFORM_ADMIN_BOOTSTRAP_PASSWORD` (skipped, with a log line, when unset -- `:104-125`), backfills `tenant_id` and `assigned_user_id` on pre-multi-tenant rows. |

### The ETL surface

| Class | Responsibility |
|---|---|
| `SourceJobServiceImpl` (699) | Job CRUD, run/skip, status toggle, run history, audit-log lookup, `myActivity`, the job list (with `taskPayload` stripped for size). Owns `validateAssignee`. |
| `SourceJobBulkServiceImpl` (256) | xlsx template, xlsx export of the job list, bulk upload. |
| `SourceTaskServiceImpl` (647) | Task CRUD, the paged/sorted task list, task-type linkage, xlsx export/template/import. Enforces the shared-catalogue rules for `SourceTaskType`. |
| `SettingServiceImpl` (644) | Source task types, tenant→task-type→Kafka-profile routes, lookup data (with optional encryption), `appSetting` (cached per tenant), and the platform-admin-only `dynamicQueryResponse`. |
| `MessageQServiceImpl` (233) | Queue-message log search, and the fail/interrupt/status-change actions on a queue entry. |
| `NotifyServiceImpl` (187) | The worker-callback side: `changeState`, `addLogs`, `addLogsBatch`. |
| `TransactionServiceImpl` (210) | The shared persistence façade the engine and crons use -- audit log writes (single and batched), job/scheduler/queue saves, due-scheduler and stalled-run queries, lookup reads. Applies its own platform-admin/tenant filter on `findByTaskDetailIdAndTaskStatus` (:193) and `findAllSourceTask` (:197). |
| `QueryService` (471) | Not a business service: a native-SQL builder. Every dashboard/report/log query is assembled here as a string and executed through the `EntityManager` (:36-58). Applies tenant narrowing inside the SQL itself (:213). |
| `LookupDataCacheService` (91) | Process-wide lookup cache, built at `@PostConstruct` (:34) and rebuilt on lookup writes; decrypts encrypted values on the way in. |

### Query engine

| Class | Responsibility |
|---|---|
| `ConnectionProfileServiceImpl` (307) | Database connection profiles; passwords encrypted; live `testConnection` with an admin-only branch for unsaved/altered profiles. |
| `QueryDefinitionServiceImpl` (365) | Saved queries (SQL encrypted at rest), validate and preview, with the saved-vs-ad-hoc role split. |
| `QueryExecutionServiceImpl` (195) | Starts an execution, reads execution history, and `executeForSchedule` for the cron. |
| `QueryExecutionRunner` (141) | Does the work in `REQUIRES_NEW` (:55): decrypts the SQL, **re-validates it** before running (:74-77), opens the JDBC connection, streams to CSV, writes the file to a bucket, records the row. |
| `QueryScheduleServiceImpl` (243) | Schedule CRUD, `findDueSchedules`, `advanceNextRun`. |

Supporting these: `process/src/main/java/process/engine/query/QueryValidator.java` (read-only SQL
enforcement via jsqlparser), `CsvExportService.java`, `DatabaseConnectionFactory.java`,
`CsvExportResult.java`.

### Analytics Studio (added 2026-09-08)

`process/src/main/java/process/analytics/` — **not** under `model/service/impl`, and not part of the
29/42 counted above. It is its own package because what it protects is not a row but an engine
(§3.7). Six classes (821 lines) plus three DTOs (130).

Analytics Studio reads a file **where it already lives** in object storage: nothing is copied into
Postgres, and no entity, repository or changeset was added for it (see the phase-one boundary at
the end of this section).

| Class | Lines | Responsibility |
|---|---|---|
| `AnalyticsLimits` | 93 | `@Component` reading the six `analytics.*` properties. The whole policy in one bean, "so the policy can be read in one sitting, asserted in one test, and changed per environment without hunting" (`:16-17`). Defaults and what each protects against are in `discovery/infrastructure.md` §3.2. |
| `DuckDbSessionFactory` | 239 | Builds the only kind of DuckDB session this application is allowed to have. The ordering below is the point of the class. |
| `DatasetRef` | 130 | A location the server has agreed to read — connection, bucket, path, `Format`. Nested `Format` enum: `CSV`, `TSV`, `JSON`, `PARQUET`, detected from the extension (`:35-51`); `.jsonl` and `.ndjson` both map to `JSON`. Owns `url()` (`s3://` for S3 and MinIO, `azure://` for Azure) and `scanExpression()`, which picks the reader and turns `union_by_name`/`filename` on for a multi-file dataset (`:107-122`). **Its constructor is package-private** (`:59`) — that is what makes the resolver unavoidable. |
| `DatasetResolver` | 110 | The only way to obtain a `DatasetRef`. Path allow-list, `..` check, tenant visibility, provider check, bucket-from-the-record, format detection — all six set out in §3.7. |
| `AnalyticsException` | 24 | A failure whose message was written for a person. The type draws the distinction the platform's error handling gets wrong elsewhere (§7): some failures are the user's to fix and some are ours, and only the first kind should reach a screen (`:6-11`). |
| `AnalyticsQueryService` | 225 | The only place in the application an analytics query runs. `schemaOf`, `preview`, `rowCount`; the governor; the error mapping. |
| `dto/ColumnDto` | 29 | One column, carrying DuckDB's own type name (`VARCHAR`, `BIGINT`, `TIMESTAMP`) rather than a normalised one, because that is what a user would write in SQL later. |
| `dto/DatasetSchemaDto` | 44 | Bucket, path, format, `multiFile`, columns. |
| `dto/DatasetPreviewDto` | 57 | Columns, rows, page, pageSize, totalRows, `multiFile`. Rows are lists of **strings**, not maps: it halves the payload on a wide file, keeps the column order the file had, and avoids handing a browser a `DECIMAL` or a big integer that a JavaScript double has already rounded (`:8-14`). |

**The order inside `DuckDbSessionFactory.open()` is load-bearing, not incidental** (`:76-98`, with
the individual steps at `:100-106`, `:116-142` and `:190-193`). A reader changing this class needs
to know that reordering it silently removes the protection:

1. `SET memory_limit` / `SET threads` / `SET preserve_insertion_order=false`. Nothing is written, so
   no temp directory is configured either — an unset one keeps a spill from quietly creating files
   beside the application (`:103-104`).
2. `INSTALL` + `LOAD` **httpfs** (S3, MinIO) or **azure** (Azure Blob). FTP and FTPS are refused
   **by name** in the `default` branch, so the caller can be told why instead of failing later
   inside a scan (`:135-140`).
3. `CREATE OR REPLACE SECRET analytics_store (...)`. Credentials are attached as a DuckDB SECRET and
   **never interpolated into query text**, so they cannot surface in a query plan or an error
   message — an explicit difference from the older `SET s3_access_key_id` style (`:32-34`). Decrypted
   here and nowhere else, via `EncryptionUtil`; a decryption failure logs without the cause's message
   because that message can carry ciphertext fragments (`:195-207`).
4. `SET disabled_filesystems='LocalFileSystem'`. This removes the local reader outright, so a query
   naming a path on disk fails at the filesystem layer rather than at a validator somebody might
   later forget to call (`:184-186`).
5. `SET lock_configuration=true` — **last**, so nothing downstream can loosen any of the four steps
   above, including user SQL once a later phase allows it (`:186-188`).

Three further properties of that method:

- **A session that fails part-way through configuration is closed rather than returned** (`:87-97`).
  A half-configured session is an unlocked one and must never escape `open()`.
- **The driver is loaded in a `static` block** (`:53-60`) rather than by JDBC auto-discovery, so a
  native-library failure names itself at startup instead of surfacing as a `ClassNotFoundException`
  on the first analytics request after a restart.
- The memory-limit property is **regex-restricted before interpolation**, `[0-9]+[A-Za-z]{0,3}`
  (`sanitiseSetting`, `:221-227`), because it is a setting value spliced into SQL and a mistyped
  property of `512MB'; SET lock_configuration=false` would otherwise be a configuration file that
  unlocks the engine.

**`AnalyticsQueryService` is the governor.** Callers hand in a `DatasetRef` and never SQL; the SQL
is built here from the ref's own scan expression, so there is exactly one place to read when the
question is "what can this feature execute" (`:21-27`). It applies, in this order (`:150-179`):

- a **fair `Semaphore`** sized to `analytics.query.max-concurrent`, with a **2-second** wait and then
  a refusal rather than a queue (`SLOT_WAIT_SECONDS`, `:52`; the reasoning at `:46-51` — a caller
  waiting behind five one-gigabyte scans has already lost, and saying so is kinder than a request
  that eventually times out). Taking the slot first means a rejected caller never pays for a session;
- `statement.setQueryTimeout(...)` from `analytics.query.timeout-seconds`;
- **one session per query, closed with it.** Explicitly *not* a pool (`:33-37`): DuckDB's in-memory
  catalogue and the attached credentials die with the connection, so one caller's dataset cannot be
  visible to another's, and a wedged query cannot poison a pooled connection for the next caller.

`explain()` (`:189-218`) maps a fixed set of DuckDB error strings to sentences a person can act on —
timeout, no-files-found/404/NoSuchKey, 403/access-denied, out-of-memory, and the CSV-sniffing family.
**Anything unmapped is logged in full with its stack and reported as the generic
"The dataset could not be read."**, because an unrecognised engine message is exactly the kind of
string that carries a path or a host name.

**The refusal wordings a user can actually reach.** Five paths were exercised live on 2026-09-08 and
each returned a friendly `ERROR`, never a stack trace. Quoted here because they are the feature's
whole visible error surface, and because four of the five are pinned by an assertion on the message
itself, not merely on the exception type:

| Message | Thrown at | Asserted by |
|---|---|---|
| `A dataset path cannot contain "..".` | `DatasetResolver.java:71` | `DatasetResolverTest:140` |
| `That path contains characters this reader does not accept.` | `DatasetResolver.java:66` | `DatasetResolverTest:153` |
| `Analytics Studio does not read this file type yet. It reads CSV, TSV, JSON and Parquet.` | `DatasetResolver.java:101-102` | `DatasetResolverTest:192` |
| `Storage connection not found.` — for absent **and** for another workspace's, deliberately identical (§3.7) | `DatasetResolver.java:81` | `DatasetResolverTest:106, 116, 128` — exact-match, three times |
| `Nothing to read at <bucket>/<path>. The connection worked, so check the path.` | `AnalyticsQueryService.java:200-201` | nothing — the `explain()` mapping is untested (§9, entry 17) |

An absolute path such as `/etc/passwd.csv` is stopped **twice**, and both layers were observed
separately: `DatasetResolver` strips the leading slashes and confines it inside the connection's own
bucket (`:64`), and the session it would have run in has no local filesystem to reach at all. That
is defence in depth rather than one check doing double duty — either alone would be enough, and
neither is relied on to be.

**What phase one deliberately does not include.** Stated here because a document that reads as
though the whole module shipped will mislead somebody in a month:

- **no user-written SQL** — there is no endpoint that accepts a query (`AnalyticsRestApi.java:36-38`).
  Nor is an editor chosen: Monaco is not in the project, and that decision is still open for the
  phase that needs it;
- **no profiling, no charts, no dashboards, no saved queries, no benchmarks.** Those are later
  phases of the approved plan. The governor and the session lock-down were built *first*, precisely
  so a later phase has somewhere safe to land (`AnalyticsQueryService.java:29-31`);
- **no database changes at all.** No `AnalyticsDataset`, `SavedQuery`, `QueryHistory`, `Dashboard` or
  `BenchmarkResult` entity exists, and no Liquibase changeset was added. A dataset is not persisted;
  a selection lives only in the browser;
- **no caching.** Schema and row counts are recomputed per request; nothing in this package touches
  Redis;
- **no Kafka event and no audit-log entry** for a dataset read or a query. The specification asked
  for both; neither is built. The only trace of a query is a `logger.debug` line
  (`AnalyticsQueryService.java:170-171`);
- **the preview has no `ORDER BY`** (`:100-103`), deliberately: object storage has no natural row
  order to promise, and sorting a whole dataset to return a hundred rows would be worse. Paging is
  therefore only as stable as the reader's own ordering;
- **the Azure branch has never been exercised against a real container.** See §9.

### Storage

| Class | Responsibility |
|---|---|
| `StorageBrowserServiceImpl` (569) | The authorization-bearing façade over every provider -- see 3.5. Also the `*ForWorkflow` trusted path. |
| `StorageConnectionServiceImpl` (623) | Connection CRUD, clone, live test, bucket discovery. Reserves the platform aliases against non-platform-admins (:209, :422). Refuses to delete a connection a Kafka profile depends on. |
| `MinioObjectStorageServiceImpl` / `S3ObjectStorageServiceImpl` / `AzureBlobObjectStorageServiceImpl` (225/218/221) | The nine-method `ObjectStorageService` contract per provider. |
| `FtpObjectStorageServiceImpl` (557) | The same contract over FTP/FTPS: prefix→directory, key→relative path, everything confined under the connection's base directory (`requirePath`). Opens and closes a connection per call, because FTP control connections are stateful and idle-timeout (class javadoc :5-11). |
| `BucketRewritingStorageService` (76) | A delegating adapter that swaps a connection's alias for its real bucket/container name, so the translation lives in one place rather than fifteen call sites. |

### Documents, media and AI

| Class | Responsibility |
|---|---|
| `DocumentConverterServiceImpl` (294) | LibreOffice conversion via jodconverter; optional bucket write and task record. Own file ceiling (`document.converter.max-file-size-mb`, default 50MB) because the output is base64ed into the JSON response at roughly 4× heap (:44-54). |
| `FileChatExtractionServiceImpl` (320) | Pulls a PDF's text layer with PDFBox; rasterizes a page for the vision fallback when there is no text layer; caches extractions in Redis (`fileChatExtract`, 7-day TTL). |
| `FileChatServiceImpl` (400) | The chat session itself: 8-message history window, a **per-provider** prompt budget (Anthropic 400k / OpenAI + Azure 250k / Ollama 24k chars, default the smallest, :52-63; `MAX_HISTORY_MESSAGES` at :38), and export to xlsx/docx/pdf. |
| `AiAgentServiceImpl` (593) | Agent CRUD with the API key encrypted, `resolveRuntimeConfig` (used by file chat and the job assistant), ad-hoc prompts, and endpoint allow-listing: anything not on `ai.allowed-endpoint-hosts` must be a public https host, with one deliberately uninformative refusal message (:61-62, allow-list field at :83). |
| `JobAssistantServiceImpl` (227) | Answers a question about one job. The scope guarantee is structural: the caller sends a `jobId` and the service gathers the facts itself, so there is no other job's data in the context to leak (class javadoc). |
| `OllamaServiceImpl` (113) | Thin OkHttp client for `/api/tags`, `/api/pull` (30-min read timeout), `/api/delete`. |
| `AudioTranscriptServiceImpl` (224) | Posts audio to an external transcription service. 250MB upload ceiling, 500MB bucket ceiling, 30-minute read timeout. |
| `PdfHighlighterTaskServiceImpl` (257) | Highlighter task + field CRUD, PDF upload/download through the storage layer. |
| `ReportExportServiceImpl` (355) | Builds the report file once (CSV, converted to xlsx through the same LibreOffice route) and delivers it to one of three destinations, so all three carry byte-identical content (class javadoc). |
| `TaskFormServiceImpl` (226) | Task-payload form definitions. Writes no tasks -- a definition is metadata about tags, so changing one never alters an existing task (class javadoc). |
| `DynamicFormServiceImpl` (468) | Standalone forms, fields and submissions, including the two uuid-addressed public reads. |

### Cross-cutting

| Class | Responsibility |
|---|---|
| `DashboardServiceImpl` (340) | Seven dashboard aggregations, each delegating to a `QueryService` SQL string. |
| `NotificationCenterServiceImpl` (161) | Persisted in-app notifications: create, list, unread count, mark read/all-read. |
| `KafkaConnectionProfileServiceImpl` (734) | The largest service: broker profile CRUD, default management, live connection and topic tests, and the credential handling behind them. |
| `KafkaSecretServiceImpl` (343) | Certificate upload and truststore/keystore generation, plus the per-object `canUseObject` guard. |
| `FileShareServiceImpl` (227) | Emails a bucket file or folder. |

---

## 5. Background work

### 5.1 Schedulers

`@EnableScheduling`, `@EnableAsync` and `@EnableSchedulerLock(defaultLockAtMostFor = "10m")` are
all on `process/src/main/java/process/config/ProcessConfig.java:19-21`, with a ShedLock
`JdbcTemplateLockProvider` bean (:26-33). The scheduler pool is sized to 5
(`application.properties:90`); the comment at :82-89 records why -- five `@Scheduled` methods on
Spring's default single thread meant a slow query sweep *stopped* the minute crons for its whole
duration, since `fixedDelay` only starts counting after the previous run returns.

`process/src/main/java/process/engine/cron/ProcessCron.java`:

| Method | Cadence | Lock | Work |
|---|---|---|---|
| `addJobInQueue` (:37-47) | every 60s, 5s initial delay | `addJobInQueue`, 5S/10M | Reads due `Scheduler` rows; either queues the job or records a Skip when one is already in flight; advances the scheduler; publishes a status event. |
| `startJobInCurrentTimeSlot` (:49-59) | every 60s | `startJobInCurrentTimeSlot`, 5S/10M | Dispatches queued runs to Kafka. |
| `reconcileStalledRuns` (:66-74) | every 15 min, 30s initial delay | `reconcileStalledRuns`, 5S/5M | Closes runs stuck in flight for over 6 hours. |
| `pollDueQuerySchedules` (:76-120) | every 60s, 10s initial delay | `pollDueQuerySchedules`, 5S/10M | Runs due query schedules, one `TenantContext` per schedule, always advancing `nextRunAt` in a `finally`; a failure to advance is left un-advanced on purpose so the schedule is retried rather than skipped (:110-115). |

`process/src/main/java/process/engine/cron/AuditLogSyncCron.java`:

| Method | Cadence | Lock | Work |
|---|---|---|---|
| `syncAuditLogsFromOpenSearch` (:46-93) | every 4 hours, 15s initial delay | `syncAuditLogsFromOpenSearch`, 5S/**5M** | No-op unless OpenSearch is configured (:49). Reads a watermark from `LookupData` (`AUDIT_LOG_SYNC_LAST_RUN_TIME`), scans from watermark minus a 10-minute overlap, upserts hits into `job_audit_logs`, and only advances the watermark when nothing failed to parse (:81). |

### 5.2 The dispatcher

`process/src/main/java/process/engine/ProducerBulkEngine.java` (335 lines) holds the actual work:

- **`addJobInQueue()`** (:142-181) -- due schedulers → `JobQueue` rows, with a 50ms sleep between
  each and a `Skip` + optional email when the job is already queued.
- **`startJobInCurrentTimeSlot()`** (:183-224) -- reads a batch bounded by the `QUEUE_FETCH_LIMIT`
  lookup, sleeps 100ms per job, and stops at a **7-minute dispatch budget**
  (`DISPATCH_BUDGET_MS`, :36) so the pass cannot outlive its 10-minute ShedLock. The comment at
  :193-200 is explicit: a full 5,000-row fetch takes 8m20s at 100ms each, which would let a second
  instance claim the same rows and dispatch them twice.
- **`pushMessageToQueue()`** (:226-...) -- resolves the Kafka template through
  `KafkaConnectionResolver` + `KafkaTemplateProvider`, parses `queueTopicPartition`, and sends with
  an async success/failure callback. `*` in the partition means "let Kafka choose".
- **`reconcileStalledRuns()`** (:104-140) -- `STALLED_AFTER_MINUTES = 6 * 60` (:88), justified
  against measured data in the comment at :81-87 (median 3 min, p99 30 min, one 5-hour outlier).
  Stalled runs are marked **`Interrupt`**, not Completed or Failed, and the job's own copy of the
  status is only cleared when the job has nothing else in flight (:124-129).
- **`handleSendSuccess` / `handleSendFailure` / `changeStatusForLastJob`** (:277-...) -- status
  transitions, audit lines, WebSocket notification, and the fail/skip emails.

`process/src/main/java/process/engine/BulkAction.java` (271) holds the small state transitions the
engine composes.

### 5.3 Kafka: producer only

**There are no Kafka consumers in this codebase.** Grepping `src/main/java` for `@KafkaListener`,
`KafkaListener` and `ConsumerFactory` returns nothing. The application is a producer: it publishes
job payloads and the Python workers in `job-search/` consume them and report back over the
`NotifyResetApi` callbacks.

- `KafkaProducerConfig` builds a global fallback `KafkaTemplate` from Spring Boot's
  `KafkaProperties`, running the same durability defaults as a profile template so a fallback send
  is not quietly less safe (:28-34).
- `KafkaTemplateProvider` (568 lines) builds and caches a per-profile producer, resolving SASL/SSL
  material, downloading truststores/keystores from object storage into a private cache directory
  (`0700`, `OWNER_ONLY`, :91-93), escaping JAAS values, and refusing a denied client property list
  (`DENIED_CLIENT_PROPERTIES`, :442).
- `KafkaTopicProvisioner` is an `ApplicationRunner` that, at startup, ensures a topic exists for
  every active `SourceTaskType` (:33-48). It catches and only warns on failure (:44-47).

### 5.4 Other startup hooks

| Hook | Class | Work |
|---|---|---|
| `@PostConstruct` | `ModelApplication:39-62` | Initialises `SCHEDULER_LAST_RUN_TIME` if absent; never overwrites on restart. |
| `@PostConstruct` | `NotifyResetApi:56-63` | Refuses to start without `WORKER_CALLBACK_TOKEN`. |
| `@PostConstruct` | `TenantSeedService:61` | Default tenant, platform admin, tenant-id/assignee backfill. |
| `@PostConstruct` | `LookupDataCacheService:34` | Builds the lookup cache. |
| `@PostConstruct` | `VelocityManager:25` | Initialises the Velocity engine. |
| `@PostConstruct` | `XmlOutTagInfoUtil:40` | Loads the XML tag metadata. |
| `ApplicationRunner` | `KafkaTopicProvisioner` | See above. |
| `ApplicationRunner` | `StorageConnectionBootstrap` | Idempotent migration of bucket config from env vars into `storage_connection`, each step in its own `REQUIRES_NEW` transaction with the catch *outside* it -- the javadoc at :81-97 explains that the previous `@Transactional` version could not honour its own catch because the INSERT happened at commit, after the method returned. |
| `@EventListener` | `WebSocketEventListener:26,38` | Presence tracking on STOMP connect/disconnect. |

### 5.5 Async executors

`@EnableAsync` is declared (`ProcessConfig.java:19`) but **there is not a single `@Async` method in
the application** -- grepping `src/main/java` for `Async` returns only that import and annotation.
There is no custom `TaskExecutor`, `ThreadPoolTaskExecutor` or `ExecutorService` bean either. The
only concurrency is the scheduler pool (5 threads), Kafka's producer callback threads, and the
servlet container's request threads.

---

## 6. External integrations

| Integration | How it is reached | Configuration | Notes |
|---|---|---|---|
| **PostgreSQL** | Spring Data JPA + Liquibase | `spring.datasource.*` from `SPRING_DATASOURCE_*` | `ddl-auto=update` in dev, `validate` in stage/prod (`application-dev.properties:82-87` explains the split). 25 changelog sets under `db/changelog/changelog-sets/`. |
| **Kafka** | spring-kafka producer + `AdminClient` | Per-tenant `KafkaConnectionProfile` rows; fallback from `KafkaProperties` | `confluentinc/cp-kafka:7.5.0` in `docker-compose.yml:51`. Topics auto-created at startup; `kafka.topic.default-replication-factor` defaults to 1. |
| **Redis** | `spring-boot-starter-data-redis`, `@EnableCaching` | `RedisConfig` | Caches: default 10 min; `fileChatExtract` 7 days; `fileChatMetadata` 30s; `ftpListing` 45s -- sized in the comment at `RedisConfig.java:50-56` against measured latencies (~1.5s plain FTP, ~2.3s FTPS, ~55ms MinIO). Also backs WebSocket presence. |
| **MinIO** | `io.minio` 8.5.17 via `MinioConfig` (`@Lazy`) | `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | Refuses to build an anonymous client when keys are blank (:34-39) -- the comment records that the silent fallback surfaced as a 403 on the first object rather than as the config error behind it. **Not in `docker-compose.yml`**; it is an external dependency. |
| **AWS S3** | AWS SDK v2 `S3Client` via `S3Config` (`@Lazy`) | `AWS_S3_ACCESS_KEY/SECRET_KEY/REGION` | Also per-connection through `StorageClientFactory`. `storage.allow-instance-role` (default **false**) decides whether a keyless platform connection may fall through to the host IAM role. |
| **Azure Blob** | `azure-storage-blob` 12.25.3 via `AzureBlobConfig` (`@Lazy`) | `AZURE_STORAGE_CONNECTION_STRING` | Same per-connection story. |
| **FTP / FTPS** | `commons-net` 3.6, `FtpObjectStorageServiceImpl` + `SessionReusingFtpsClient` | Per `StorageConnection` row | Connection-per-call; listings cached 45s in Redis. |
| **LibreOffice** | jodconverter-local 4.4.7 driving the binary in the image | `jodconverter.local.*` in `application.properties:61-74` | Installed in `Dockerfile:25-27` (`libreoffice-core/writer/calc/impress/draw`). One listener process on port 2002, recycled every 100 tasks, 90s queue timeout, `existing-process-action=kill`. |
| **ffmpeg** | `ProcessBuilder` in `AudioTranscodeUtil` | Binary from `Dockerfile:26` | Transcodes non-browser-safe audio (e.g. ALAC) to AAC before upload; 15-minute timeout, 30s probe timeout. |
| **Ollama** | OkHttp in `OllamaServiceImpl` and `AiAgentServiceImpl` | `ollama.base.url`, default `http://host.docker.internal:11434` | External to the compose stack. |
| **Audio transcription service** | OkHttp in `AudioTranscriptServiceImpl` | `audio.extract.service.base.url`, default `http://host.docker.internal:8100` | External; not in the compose file and not otherwise described in this repo -- **not verified** what it is. |
| **Hosted AI providers** | OkHttp in `AiAgentServiceImpl` / `FileChatServiceImpl` | Per-agent endpoint + encrypted key | Provider names seen in the prompt-budget map: `ANTHROPIC`, `OPENAI`, `AZURE-OPENAI`, `OLLAMA` (`FileChatServiceImpl.java:55-58`). Endpoints are allow-listed. |
| **OpenSearch** | `RestTemplate` in `OpenSearchAuditLogClient` | `OPENSEARCH_URL`; blank disables everything (`:52-54`) | Index `job-audit-logs`, max 5,000 hits, 3s connect / 5s read timeouts. Bulk index with per-item failure reporting (`indexAllReturningFailures`, :102). Read back by `AuditLogSyncCron`. **Present and wired**, though external to the compose stack. |
| **SMTP** | `JavaMailSender` + Velocity templates | `spring.mail.*` from `MAIL_*` | Six templates in `emailer/TemplateType.java`: complete/fail/skip job, file share, tenant welcome, user welcome. `management.health.mail.enabled=false` keeps a flaky SMTP account from marking the container unhealthy (`application.properties:18-25`). |
| **Prometheus** | micrometer-registry-prometheus | `/actuator/prometheus` | Requires `PLATFORM_ADMIN` (`SecurityConfig.java:52`). |

`docker-compose.yml` ships only: `postgres:15`, `confluentinc/cp-zookeeper:7.5.0`,
`confluentinc/cp-kafka:7.5.0`, `redis:7-alpine`, `provectuslabs/kafka-ui`, `redis/redisinsight`,
and `process_app`. MinIO, OpenSearch, Ollama and the transcription service are all expected to
exist outside it.

---

## 7. Error handling

### 7.1 The three layers

**Layer 1 -- the service returns a `ResponseDto` with `status = "ERROR"` and HTTP 200.** This is
the normal path for every business failure: validation, not-found, refused-by-ownership. Example:
`AppUserServiceImpl.addUser` returns `new ResponseDto(ERROR, "Username missing.")` (:143) and the
controller wraps it in `HttpStatus.OK`. **A caller cannot distinguish success from a refusal by
status code alone; it has to read `status`.**

**Layer 2 -- the controller's `catch (Exception)`.** Every one of the 181 endpoints has one. The
dominant form logs and returns:

```java
new ResponseEntity<>(new ResponseDto(ProcessUtil.ERROR_MESSAGE, ProcessUtil.INTERNAL_ERROR_500),
    HttpStatus.INTERNAL_SERVER_ERROR)
```

**Layer 3 -- `GlobalExceptionHandler`** (`process/src/main/java/process/config/GlobalExceptionHandler.java`),
a `@RestControllerAdvice`:

- `AccessDeniedException` → **403** with `"You don't have permission to perform this action."` (:24-30).
- `Exception` → **500** with `INTERNAL_ERROR_500` (:32-38).
- `handleExceptionInternal` override → the framework's own status, but with the body reshaped into
  a `ResponseDto` carrying `ex.getMessage()` (:40-45). This is what turns a malformed body or a
  missing required parameter into a `ResponseDto`-shaped 400.

Because `@PreAuthorize` is enforced by an AOP interceptor *before* the controller body runs, an
authorization failure never enters the controller's `try` and reaches the advice as a 403 -- which
is the only reason the pattern works.

**A variation, added 2026-09-08.** `AnalyticsRestApi` (§2.29) reaches Layer 1 from the *controller*
rather than from a service: it catches the checked `AnalyticsException` separately and returns its
message verbatim at HTTP 200 with status `ERROR`, then catches `Exception` for the usual generic
500 (`AnalyticsRestApi.java:71-80`). The effect on the wire is identical to Layer 1 — a caller still
cannot tell success from refusal by status code — but the type is what carries the promise: an
`AnalyticsException` message has been written for a reader, and anything else has not
(`AnalyticsException.java:6-11`). It is the **only controller** that draws that line with a type
rather than by convention. The codebase holds exactly one other custom exception —
`FileChatServiceImpl.UnsupportedFileTypeException` (`:528-535`) — and it is a private nested class
that never leaves its service; `FileChatRestApi` catches only `Exception` (:39, 50, 60, 70).

### 7.2 Where it is inconsistent

1. **Two constants for one value.** `ProcessUtil.ERROR_MESSAGE` and `ProcessUtil.ERROR` are both
   `"ERROR"` (`ProcessUtil.java:13,27`). Controllers use the first, services the second. Nothing
   distinguishes them on the wire; it is one concept spelled twice.

2. **Four different failure shapes across controllers.**

   | Shape | Where |
   |---|---|
   | 500 + generic `INTERNAL_ERROR_500` | the large majority |
   | **400 + `ex.getMessage()`** | `AudioTranscriptRestApi:40,50` -- both endpoints, for *any* exception |
   | **400 + `ex.getMessage()` for `IllegalArgument`/`IllegalState` only**, 500 otherwise | `StorageBrowserRestApi` (7 methods), `PdfHighlighterTaskRestApi.downloadPdfHighlighterFile:140` |
   | **400 + upstream message, with `ProcessUtil.ERROR`** | `OllamaRestApi:37,50,63` |

   `AudioTranscriptRestApi` is the outlier that matters: it returns the raw exception message of an
   arbitrary internal failure to the caller with a 400, where every comparable endpoint withholds
   it. `KafkaSecretRestApi:50-51` documents the opposite policy explicitly ("The message is
   withheld deliberately").

3. **HTTP verbs that contradict the action.** `deleteProfile` is a **PUT**
   (`KafkaConnectionProfileRestApi:51`), so are `deleteLookupData` (`SettingRestApi:161`),
   `deleteSourceJob` (`SourceJobRestApi:68`) and `deleteSourceTask` (`SourceTaskRestApi:59`).
   `listSourceTask` and `fetchAllLinkJobsWithSourceTaskId` are **POST** reads
   (`SourceTaskRestApi:70,89`). Every one is a working choice, but a client cannot infer semantics
   from the verb here.

4. **Only one endpoint uses a non-200 success status**: `previewObject`/`downloadObject` return
   206 for a satisfied `Range` (`StorageBrowserRestApi:225`). `AppUserRestApi.avatar` returns a
   bare 404 for "no picture", explicitly noted as not an error (:116-118). Everything else is 200.

5. **`GlobalExceptionHandler`'s `Exception` handler is nearly unreachable** from controllers,
   because each catches `Exception` itself. It exists for what escapes the dispatch — filter and
   converter failures — and for the handful of controller methods that delegate before the try
   (none found; verified by reading all 27 controllers).

6. **A refusal thrown from a service inside a controller `try` becomes a 500, not a 403.** No
   service throws `AccessDeniedException` -- grepping `src/main/java` finds it only in
   `GlobalExceptionHandler`. Services signal refusal with a `ResponseDto(ERROR, ...)` at HTTP 200
   or with `IllegalArgumentException`/`IllegalStateException` (42 such throws in `service/impl/`),
   which becomes a generic 500 on most controllers and a 400 on the storage ones.

7. **Silent-failure paths, by design and documented as such**: an invalid JWT logs at debug and
   the request continues unauthenticated (`JwtAuthenticationFilter:50-53`); a refused STOMP
   SUBSCRIBE drops the frame with no error to the client (`StompAuthChannelInterceptor:77,92,99`);
   `KafkaTopicProvisioner` and `StorageConnectionBootstrap` swallow their failures so a migration
   problem cannot stop the application from starting.

---

## 8. Test coverage

The brief states 516 unit tests and 86 end-to-end tests passing. **`mvn -o test` was re-run on
2026-09-02: 516 run, 0 failures, 0 errors, 0 skipped.** On **2026-09-08** the same command reported
**587**, and then **607** once Analytics Studio's twenty landed (§8.4). The counts in the
sub-sections below are as of 2026-09-02 and were not re-derived. The e2e suite still was not executed
(it needs the `process_app` container up -- see `process/run-e2e.sh`), but 86 is the number of
`@Test` methods in the five files `run-e2e.sh` selects (`*E2EIT` plus `HarnessSmokeIT`).

What was counted from the source: **476 `@Test` annotations outside `src/test/java/process/e2e`,
88 inside it, and 7 `@ParameterizedTest`** across 71 test files. The 88 exceeds the 86 above
because `ContextProbeIT` and `AjwaKafkaProvisioningDriver` sit in that package and neither is
selected by `run-e2e.sh`.

### 8.1 What is tested

The suite is overwhelmingly a **security and tenant-isolation** suite. Twelve files have
"TenantIsolation", "Guard", "Access", "RoleScope", "FailClosed" or "Ownership" in the name.

| Area | Files |
|---|---|
| Tenancy and roles | `security/TenantOwnershipTest` (10), `model/pojo/TenantFilterDeclarationTest` (3), `config/MethodSecurityConfigRoleHierarchyTest` (4) |
| Storage authorization | `StorageBrowserServiceImplTenantIsolationTest` (20), `PlatformBucketAccessTest` (10), `PlatformBucketNamedGuardTest` (5), `OwnAvatarFolderGuardTest` (5), `StorageConnectionAliasDisclosureTest` (3), `StorageConnectionTenantlessCallerTest` (5), `StorageConnectionKafkaDependencyTest` (7), `config/StorageAmbientCredentialTest` (5), `config/MinioAnonymousClientTest` (4), `config/DefaultBucketBootstrapTest` (6), `config/AvatarBucketPropertyTest` (4) |
| Kafka | `KafkaTemplateProviderSecurityTest` (22), `KafkaConnectionProfileServiceImplTenantIsolationTest` (23), `KafkaSecretAccessTest` (12), `KafkaCertificateUtilTest` (12), `KafkaCertificateWorkflowTest` (8), `KafkaSecurityMatrixIT` (7), `KafkaTopicPartitionUtilTest` (8), `KafkaProtocolCredentialLifetimeTest` (5), `KafkaTemplateProviderSecretCacheTest` (4), `KafkaConnectionResolverTenantIsolationTest` (6), `KafkaConnectionResolverProfileOwnershipTest` (2), `KafkaSecretUnreadableObjectTest` (2), `KafkaSecretPathTest`, `KafkaCertificateStoreAliasTest` (1) |
| Users and auth | `AppUserServiceImplRoleScopeTest` (20), `AppUserServiceImplFailClosedTest` (6), `AuthServiceImplMustChangePasswordTest` (3) |
| Query engine | `QueryValidatorTest` (11), `QueryDefinitionServiceImplTenantIsolationTest` (8), `QueryScheduleServiceImplTenantIsolationTest` (8), `QueryExecutionServiceImplTenantIsolationTest` (5), `QueryDefinitionAdHocSqlRoleTest` (4), `ConnectionProfileServiceImplTenantIsolationTest` (8), `ConnectionProfileTestConnectionSafetyTest` (5) |
| ETL | `SourceJobServiceImplTenantIsolationTest` (10), `SourceTaskServiceImplTenantIsolationTest` (6), `MessageQServiceImplTenantIsolationTest` (8), `NotifyServiceImplTest` (11), `TransactionServiceImplAuditLogTest` (8), `api/NotifyResetApiTest` (9), `engine/FallbackMessageTest` (5), `util/ResumeScheduleTest` (4), `util/CatchUpBoundsTest` (5) |
| Utilities | `ProcessTimeUtilTest` (34), `PhoneNumberValidatorTest` (8), `PagingUtilTest` (6), `OpenSearchAuditLogBulkFailureTest` (4) |
| Email templates | `JobEmailTemplateTest` (5), `TenantWelcomeTemplateTest` (3), `UserWelcomeTemplateTest` (4) |
| Other services | `AiAgentServiceImplTenantIsolationTest` (10), `TenantOwnedLookupTest` (10, covers `SettingServiceImpl`), `TaskFormValidationTest` (10), `ReportExportServiceImplTest` (16), `UserStatisticsQueryTest` (11), `AudioTranscriptBucketGuardTest` (5), `PromptFileLimitTest` (4, covers `FileChatServiceImpl`) |
| Config declarations | `ApplicationPropertiesDeclarationTest` (6) |

**End-to-end** (`src/test/java/process/e2e/`, driven over real HTTP against the dev database by
`process/run-e2e.sh`): `UserManagementE2EIT` (32), `BucketAccessE2EIT` (21),
`TenantLifecycleE2EIT` (20), `KafkaSecretE2EIT` (10), `HarnessSmokeIT` (3), `ContextProbeIT` (1),
`AjwaKafkaProvisioningDriver` (1), plus the `E2ESupport` harness.

### 8.2 Controllers with no test of their own

Exactly one controller has a unit test: **`NotifyResetApi`** (`api/NotifyResetApiTest`, 9 tests).
The e2e suites exercise 27 endpoints over HTTP, spanning six controllers: `AppUserRestApi`,
`TenantRestApi`, `StorageBrowserRestApi`, `StorageConnectionRestApi`,
`KafkaConnectionProfileRestApi`, `KafkaSecretRestApi`, and one `DashboardRestApi` endpoint.

**The 20 controllers with no test at any level -- no unit test, and no endpoint touched by an e2e
suite:**

`AiAgentRestApi`, `AudioTranscriptRestApi`, `AuthRestApi`, `DocumentConverterRestApi`,
`DynamicFormRestApi`, `FileChatRestApi`, `FileShareRestApi`, `MessageQRestApi`,
`NotificationRestApi`, `OllamaRestApi`, `PdfHighlighterTaskRestApi`, `QueryEngineRestApi`,
`ReportRestApi`, `SettingRestApi`, `SourceJobRestApi`, `SourceTaskRestApi`, `TaskFormRestApi`,
`TenantRequestRestApi`, `TextCleanerRestApi`, and `DashboardRestApi` (only
`jobStatusStatistics` is reached, and only incidentally).

Their *services* are often well tested — the gap is that the controller wiring itself, including
the `@PreAuthorize` values in §2, is never asserted end to end for these. `QueryEngineRestApi`'s
twelve method-level `TENANT_USER` overrides are the largest untested authorization surface.

**`AnalyticsRestApi` joins that list** (2026-09-08). Its two collaborators are the best-tested new
code in the repository (§8.4), but the controller itself has no unit test and no e2e suite touches
it, so the class-level `TENANT_USER` in §2.29 is asserted nowhere. That makes twenty-one.

### 8.3 Services with no test file referencing them

Determined by grepping each `service/impl` class name across `src/test/java`. **Seventeen
implementations are referenced by no test at all:**

`AzureBlobObjectStorageServiceImpl`, `BucketRewritingStorageService`, `DashboardServiceImpl`,
`DocumentConverterServiceImpl`, `DynamicFormServiceImpl`, `FileChatExtractionServiceImpl`,
`FileShareServiceImpl`, `FtpObjectStorageServiceImpl`, `JobAssistantServiceImpl`,
`MinioObjectStorageServiceImpl`, `NotificationCenterServiceImpl`, `OllamaServiceImpl`,
`S3ObjectStorageServiceImpl`, `SourceJobBulkServiceImpl`, `TenantRequestServiceImpl`,
`TenantSeedService`, `TenantServiceImpl`.

Two more are named only inside a comment or an unrelated assertion, so they are effectively
untested as well:

- **`PdfHighlighterTaskServiceImpl`** -- its only mention is a comment at
  `StorageBrowserServiceImplTenantIsolationTest.java:269`.
- **`QueryExecutionRunner`** -- reached only through `QueryExecutionServiceImplTenantIsolationTest`.

Worth calling out from that list: `TenantServiceImpl` and `TenantRequestServiceImpl` create
tenants and their first administrators, `TenantSeedService` creates the platform admin, and
`FtpObjectStorageServiceImpl` (557 lines, with its own path-confinement logic) is the largest
untested class in the codebase. `TenantLifecycleE2EIT` covers the tenant *endpoints* over HTTP,
which mitigates the first two but does not unit-test their branches.

### 8.4 Analytics Studio's suites (added 2026-09-08)

Twenty tests in two files, `process/src/test/java/process/analytics/`. They took the backend total
from 587 to **607 passing**.

| File | Tests | What it pins |
|---|---|---|
| `DatasetResolverTest` (230 lines) | 13 | The happy path; a glob read as one multi-file dataset; a connection belonging to another workspace; a connection that does not exist, asserted to be **refused in the same words** (:110); a soft-deleted connection; a path containing `..`; a path carrying a SQL metacharacter; **the bucket coming from the record rather than the request** (:156); the alias fallback when `bucketName` is null; an unreadable file type; an FTP provider refused; the missing-argument messages; and format detection across every extension it claims to read. |
| `DuckDbLockdownTest` (179 lines) | 7 | Whether a real, configured DuckDB session actually refuses what the factory claims it refuses. |

`DuckDbLockdownTest` runs against a **real DuckDB, not a mock**, and that is the point of it: the
claim under test is about what a specific engine will and will not do, and a mock would only assert
that the strings in `DuckDbSessionFactory` are the strings in `DuckDbSessionFactory`. The seven:

- `aSessionCannotReadAFileFromTheLocalDisk` (:77) — a fake secret is written to a temp file and a
  read is attempted;
- `aSessionCannotWriteAFileToTheLocalDisk` (:100) — and the file is asserted **absent** afterwards,
  rather than trusting that the statement threw;
- `aSessionCannotRaiseItsOwnMemoryCeiling` (:116);
- `aSessionCannotPutTheLocalFilesystemBack` (:128);
- `aSessionStillDoesTheJobItExistsFor` (:138) — the positive control, without which a session that
  refused *everything* would pass the four above while being useless;
- `anFtpConnectionIsRefusedByNameRatherThanFailingInsideAScan` (:157);
- `aMalformedMemoryLimitIsRejectedRatherThanInterpolatedIntoSql` (:167).

**No frontend unit test was added for the Studio component.** The frontend suite is unchanged at
580 — see `discovery/frontend.md`.

---

## 9. Risks and rough edges observed

Everything here is traceable to a file; nothing is speculation about intent.

1. **`@CrossOrigin(origins = "*")` on every controller.** All 27 carry it, `AuthRestApi` included
   (`AuthRestApi.java:18`). `SecurityConfig` enables `.cors()` (:31) but registers no
   `CorsConfigurationSource`, and `WebConfig` is an empty `WebMvcConfigurer`
   (`WebConfig.java:9-11`), so the annotation is the whole CORS policy. Any origin may call the
   API with a bearer token the page already holds.

2. **Swagger is open in every profile.** `/swagger-ui/**` and `/v2/api-docs` are `permitAll`
   (`SecurityConfig.java:53-54`) and the Docket selects every handler
   (`SwaggerConfig.java:28-30`), publishing the full 181-endpoint surface unauthenticated. There
   is no profile guard on it.

3. **A token outlives a status change.** Role and tenant come from the JWT claims with no
   per-request user read (`JwtAuthenticationFilter.java:40-47`). Deactivating a user, suspending a
   tenant or changing a role takes effect only when the access token expires (default 30 minutes).
   There is no token revocation or denylist anywhere in the codebase.

4. **`MessageQRestApi` mutations are open to `TENANT_USER`.** `failJobLogs`, `interruptJobLogs`
   and `changeJobStatus` all sit under the class-level `TENANT_USER`
   (`MessageQRestApi.java:21,43,54,65`), so any signed-in user can rewrite run state.
   `SourceJobRestApi` is the same shape -- create, update, delete, run and skip are all
   `TENANT_USER` (`SourceJobRestApi.java:29`).

5. **`AudioTranscriptRestApi` returns raw exception messages.** Both endpoints answer
   `new ResponseDto(ProcessUtil.ERROR_MESSAGE, ex.getMessage())` with 400 for *any* exception
   (:40, :50), which is the opposite of the policy `KafkaSecretRestApi:50-51` states explicitly.

6. **`@EnableAsync` with no `@Async` anywhere.** `ProcessConfig.java:19` enables it and nothing
   uses it — dead configuration, and misleading to anyone assuming work is offloaded.

7. **`StorageConnection`'s Hibernate filter and its service guard disagree.** The entity declares
   the shared-catalogue condition `(tenant_id = :tenantId or tenant_id is null)`
   (`StorageConnection.java:44`), which publishes platform connections to every tenant, while
   `StorageBrowserServiceImpl.collectBuckets` deliberately refuses them (:100-104). The service is
   narrower, so the outcome is safe, but the two statements of the rule contradict each other and
   only one is enforced by `TenantFilterDeclarationTest`.

8. **`spring.jpa.properties.hibernate.enable_lazy_load_no_trans=true`**
   (`application-dev.properties:80`). Lazy loads outside a transaction silently open their own,
   which hides N+1s and makes the tenant-filter state at load time harder to reason about — the
   filter is enabled per `EntityManager` by explicit call, so a lazy load on a fresh session may
   not carry it. **Not verified** whether any current lazy path escapes the filter this way.

9. **`SettingRestApi.dynamicQueryResponse` runs supplied SQL.** It is `PLATFORM_ADMIN` at both the
   annotation and the service (`SettingRestApi.java:43`, `SettingServiceImpl.java:197`), and
   `QueryService.executeQueryResponse` runs the string as given (`QueryService.java:58`). Correct
   as designed, and the highest-value endpoint in the API for anyone who obtains a platform-admin
   token.

10. **`SettingRestApi.xmlCreateChecker` is mapped without a leading slash**
    (`path = "xmlCreateChecker"`, :172) — the only endpoint in the codebase declared that way. It
    resolves, but it will not match a naive path-prefix rule someone adds later.

11. **Apache POI 3.15 and Velocity 1.7** (`pom.xml`) are both several major versions behind. POI
    parses genuinely untrusted input -- user-uploaded xlsx through
    `process/src/main/java/process/util/excel/BulkExcel.java` (`XSSFWorkbook`, :31). Velocity's
    exposure is narrower: templates are loaded from the classpath only
    (`ClasspathResourceLoader`, `VelocityManager.java:29-30`), and only the *values* merged into
    them come from user data (`getResponseMessage`, :41-46).

12. **`ddl-auto=update` in dev, `validate` in stage/prod.** Deliberate and documented
    (`application-dev.properties:82-87`), but it means a missing Liquibase changeset is invisible
    locally and only fails at the stage boot.

13. **The audio transcription service is undocumented.** `audio.extract.service.base.url` defaults
    to `http://host.docker.internal:8100` (`AudioTranscriptServiceImpl.java:42`) and nothing in
    this repository says what runs there, how it is deployed, or what happens when it is absent
    beyond a 400. Checked: `docker-compose.yml`, `Dockerfile`, `README.md`, all four properties
    files.

The five below were added on **2026-09-08** with Analytics Studio.

14. **Analytics Studio's Azure branch is untested.** `DuckDbSessionFactory` branches for it
    (`:130-134`, `azureSecret` at `:171-179`) and `DatasetRef.url()` emits `azure://` for it
    (`:94-97`), but S3 and MinIO share the S3 protocol and are the two that were verified against a
    running store. The Azure path needs DuckDB's separate `azure` extension and has **never been
    exercised against a real container**. Nothing in `DuckDbLockdownTest` or `DatasetResolverTest`
    reaches it. Do not describe Azure as working.

15. **DuckDB runs inside the backend JVM, and the concurrency ceiling is per JVM, not per tenant.**
    `AnalyticsQueryService`'s `Semaphore` is a single instance field sized to
    `analytics.query.max-concurrent` (`:56, 62`), so one workspace can occupy all four slots and
    every other workspace is refused with "Too many analytics queries are running right now"
    (`:159-160`) until it lets go. There is no per-tenant fairness anywhere in the class. The
    operational half of this — that the same JVM runs the ETL dispatcher — is in
    `discovery/infrastructure.md` §2.6.

16. **A dataset read leaves no audit trail.** Nothing in `process.analytics` writes a
    `job_audit_logs` row, publishes a Kafka event, or calls `TransactionServiceImpl`. The only
    record that a query ran is a `logger.debug` line naming the dataset and the tenant
    (`AnalyticsQueryService.java:170-171`), which is below the default level. The specification for
    this feature asked for both an audit entry and an event; neither is built. So "who read which
    file, and when" is currently unanswerable for this module — unlike every other data-reading
    surface in the application.

17. **An unmapped DuckDB error becomes an unhelpful sentence.** `explain()` matches a fixed set of
    substrings (`AnalyticsQueryService.java:193-215`); everything else becomes
    "The dataset could not be read." (`:217`). That is the right default — the alternative leaks a
    path or a host name into a browser — but it means an engine upgrade that rewords a message
    silently degrades the diagnostics, and only the log will say what actually happened. Nothing
    tests the mapping.

18. **The preview pages without an `ORDER BY`.** Deliberate and documented
    (`AnalyticsQueryService.java:100-103`): object storage has no natural row order, and sorting a
    whole dataset to return one page would be worse. The consequence to hold onto is that paging is
    only as stable as the reader's own ordering, so a row can in principle appear on two pages or on
    none if the underlying objects change between requests. There is no caching to hide this —
    schema and row count are recomputed per request.
