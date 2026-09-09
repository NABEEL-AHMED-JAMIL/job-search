# Grooming -- Bulk Transfer

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Purpose

Two screens for people who have more work to set up than they are willing to type into a form.

A source task describes one unit of ETL work; a source job binds a task to a timetable. Creating
either one at a time is fine for three of them and unbearable for eighty. Bulk Transfer gives an
operator three moves against each of those two entities:

- **Get the shape** -- download a spreadsheet that already carries the right column headings, and,
  for jobs, dropdowns holding the ids and enumerations the importer will accept.
- **Take stock** -- download everything that already exists as a spreadsheet, to read, to hand to
  someone, or to diff against what was expected.
- **Put many in at once** -- upload a filled-in spreadsheet and have every row become a real task or
  a real job with its schedule.

It is a data-loading tool, not a data-editing one. Nothing here updates or deletes: every accepted
row is a new record. "Bulk Transfer" is the rewrite's name for it; the old app called both screens
**Batch Action**.

---

## 2. Existing behaviour

### 2.1 One component, two entities, in both applications

Both apps implement the two screens with a single component that branches on route data.

| | Old app | New app |
|---|---|---|
| Component | `SourceBatchActionComponent`, `scheduler1/src/app/_component/batch-action/batch-action.component.ts` (203 lines) + `.html` (122 lines) | `BulkTransfer`, `scheduler1/next/src/app/features/bulk/bulk-transfer.ts` (171 lines) + `.html` (100 lines) |
| Job route | `jobList/jobBatchAction`, `data: { router: '/jobList', action: 'sourceJob' }` (`app.routing.ts:87-94`) | `jobs/bulk`, `data: { kind: 'job' }` (`app.routes.ts:211-214`) |
| Task route | `taskList/taskBatchAction`, `data: { router: '/taskList', action: 'sourceTask' }` (`app.routing.ts:63-70`) | `tasks/bulk`, `data: { kind: 'task', minRole: 'TENANT_ADMIN' }`, `canActivate: [roleGuard]` (`app.routes.ts:215-223`) |
| How the branch reaches the component | `ActivatedRoute.data.subscribe` in the constructor (`batch-action.component.ts:52-61`) | `input.required<Kind>()` fed by `withComponentInputBinding()` (`bulk-transfer.ts:45`, `app.config.ts:11`) |
| Entry point | "Batch Action" button on both lists, ungated: `source-job.component.html:44`, `source-task.component.html:36` | "Bulk import" button: `features/jobs/jobs.html:19` (ungated), `features/tasks/tasks.html:16-19` (behind `auth.canManageTasks()`) |

The old component holds a `ROUTES`-equivalent as two `if` branches on `this.action`
(`batch-action.component.ts:122-124, 155-157, 171-173`); the new one holds it as a lookup table
(`bulk-transfer.ts:18-33`) keyed by `kind`, carrying the three endpoint paths, the noun and a
back-target.

### 2.2 Upload -- old app

- Hidden `<input type="file">` with an `accept` hint of the two Excel MIME types
  (`batch-action.component.html:9-10`); the dropzone click opens it.
- Drag-and-drop with `isDragging` styling (`batch-action.component.ts:87-107`). **The drop handler
  performs no file-type check at all** -- `onDrop` takes `dataTransfer.files[0]` and uploads it
  (`:99-107`).
- Platform Admin uploading **tasks** must first pick a tenant. `needsTenantPicker` is
  `isPlatformAdmin && action === 'sourceTask'` (`:67-69`); `ngOnInit` then loads
  `tenant.json/listTenants` into a `<select>` (`:71-85`, `batch-action.component.html:38-44`), and
  `uploadBulk` refuses with a toast if nothing is selected (`:113-116`). The chosen id is appended
  to the multipart body as `tenantId` (`_services/source.task.service.ts:66-72`).
- A full-screen `SpinnerService` overlay covers the request (`:120, 128`).
- On `status === 'SUCCESS'`: success toast, `lastUploadOk = true`, message shown in the Results
  panel (`:130-134`, `batch-action.component.html:95-97`).
- On `status === 'ERROR'`: `this.errors = response.data || []` and the Results panel renders a
  two-column **Row / Error** table, one row per server-reported failure, each cell bound with
  `[innerHTML]` because the server's strings carry `<br>` (`:135-136`,
  `batch-action.component.html:102-117`).
- The file input is cleared either way (`:138-140, 147-149`).

### 2.3 Upload -- new app

- Same dropzone, plus a visible "Choose a file" label wrapping a `sr-only` input
  (`bulk-transfer.html:43-51`).
- **Both** paths -- pick and drop -- go through `accept()`, which checks the *filename* ends
  `.xlsx` or `.xls` and otherwise raises a toast (`bulk-transfer.ts:91-99`). This is stricter than
  the old drop handler and looser than the server (see §12, KI-5).
- The picked file is held, named, sized and shown before anything is sent, with a **Remove** button
  (`bulk-transfer.ts:51, 57-63, 101-105`; `bulk-transfer.html:26-42`). The old app uploaded the
  instant a file was chosen -- there was no confirm step and no way to change your mind.
- Upload is `reportProgress: true, observe: 'events'` and drives a real percentage bar
  (`bulk-transfer.ts:117-122`, `bulk-transfer.html:30-32`). The old app had only a blocking spinner.
- On success: toast, the file is cleared, and an inline result card is shown
  (`bulk-transfer.ts:126-129`, `bulk-transfer.html:54-61`).
- On failure: the same card in the critical colour. **The `data` array of per-row errors is never
  read** -- `bulk-transfer.ts:125-129` takes `status` and `message` and nothing else.
- **No tenant picker exists anywhere on the page.** `upload()` builds a `FormData` containing
  exactly one part, `file` (`bulk-transfer.ts:110-111`).

### 2.4 Download -- both apps

Both offer the same two buttons: the blank **template** and the full **export**.

- Old: `downloadList()` and `downloadSourceTemplate()` (`batch-action.component.ts:153-183`) each
  show the blocking spinner, then hand the blob to `downLoadFile`, which re-wraps it with the xlsx
  MIME type and forces the filename to `JobList.xlsx` / `JobTemplate.xlsx` / `TaskList.xlsx` /
  `TaskTemplate.xlsx` (`:161, 177, 189-201`).
- New: one `download(which)` (`bulk-transfer.ts:141-169`). Per-button spinner rather than a page
  overlay (`downloading` signal, `bulk-transfer.html:74-96`). It reads the server's
  `Content-Disposition` and uses that filename, falling back to `jobs-template.xlsx` /
  `jobs-export.xlsx` / `tasks-template.xlsx` / `tasks-export.xlsx` only when the header is absent
  (`:143-156`). The header is exposed cross-origin by `@CrossOrigin(exposedHeaders = {CONTENT_DISPOSITION, CONTENT_LENGTH})`
  on both controllers (`SourceJobRestApi.java:27`, `SourceTaskRestApi.java:26`).

### 2.5 What the server actually does

**Job template** -- `SourceJobBulkServiceImpl.downloadSourceJobTemplateFile()` (`:69-90`) opens the
bundled workbook `process/src/main/resources/Scheduler.xlsx`, which has two sheets: `Job-Add`
carrying the 11 headings, and `Scheduler-Detail`, a human-readable field guide. It then injects
Excel data validations over rows 1-999: column 1 gets every active task id the caller may see, and
columns 5, 7, 8, 9, 10 get frequency, priority and True/False (`:78-84`,
`BulkExcel.fillDropDownValue`, `util/excel/BulkExcel.java:106-115`).

**Task template** -- `SourceTaskServiceImpl.downloadSourceTaskTemplate()` (`:514-525`) writes a
brand-new one-sheet workbook holding **only** the five headings. No dropdowns, no guide sheet.

**Job export** -- `downloadListSourceJob()` (`SourceJobBulkServiceImpl.java:93-142`) reads
`findAll()` for a platform admin and `findByTenantId(...)` otherwise (`:95-97`), drops
`Status.Delete` rows, and writes 15 columns to a sheet named `SourceJob`. The task column is
formatted `"%d [%s]"` -- id and name together (`:110`). The scheduler columns come from a separate
`findSchedulerByJobId` per row (`:116`).

**Task export** -- `downloadListSourceTask()` (`SourceTaskServiceImpl.java:483-511`) runs a native
query, `downloadListSourceTask()` for a platform admin and `downloadListSourceTaskForTenant(tenantId)`
otherwise (`:484-486`, `SourceTaskRepository.java:36-52`), and writes 8 columns to a sheet named
`ListSourceTask`.

**Job import** -- `uploadSourceJob(FileUploadDto)` (`SourceJobBulkServiceImpl.java:144-255`):

1. Content type must be exactly the xlsx MIME (`:146-149`).
2. Workbook must have a sheet named `Job-Add`, at least one data row, and `getLastRowNum() <= 1001`
   (`:152-162`).
3. Row 0 must match `ProcessUtil.HEADER_FILED_BATCH_FILE` cell for cell, else the whole file is
   rejected (`:167-174`).
4. Each later row becomes a `JobDetailValidation`, validated by `isValidJobDetail()`
   (`util/validation/JobDetailValidation.java:161-205`), then checked against
   `transactionService.findByTaskDetailIdAndTaskStatus(taskId)` -- which is where tenancy is
   enforced (`TransactionServiceImpl.java:191-194`).
5. **If any row failed, nothing is written**: the method returns
   `ERROR, "Total %d source jobs invalid.", errors` with the list in `data` (`:218-220`).
6. Otherwise every row is saved: a `SourceJob` with `Execution.Auto` hardcoded, `Status.Active`,
   `tenantId` copied from the linked task and `assignedUserId` set to the caller (`:221-235`), then
   a `Scheduler` seeded by `ProcessTimeUtil.applyInitialSchedule` (`:236-248`).
7. A `BATCH_DONE` notification is raised with link `/jobList` (`:250-252`) -- the new app rewrites
   that path to `/jobs` (`features/notifications/notification-links.ts:11-12`), so the stale link is
   harmless.

**Task import** -- `uploadSourceTask(FileUploadDto)` (`SourceTaskServiceImpl.java:527-635`): same
shape, sheet `ListSourceTask`, header row must have exactly 5 physical cells and match
`UPLOAD_SOURCE_TASK_HEADER` (`:552-561`). Per row it resolves the task type by `findById` and gates
it on `isSourceTaskTypeVisibleToCaller` (`:580-591`, helper at `:126-131`), refuses `Delete` and
`Inactive` types, then runs `SourceTaskValidation.isValidSourceTask()`
(`util/validation/SourceTaskValidation.java:117-134`), which also parses the XML payload into tag
rows. Errors abort before any write (`:600-602`). The owning tenant comes from
`resolveTenantIdForCreate(object.getTenantId(), ...)` (`:603-608`, helper at `:91-104`): a tenant
caller gets their own id and the request `tenantId` is ignored; a platform admin **must** supply
one and it must exist. Each row is saved as an Active `SourceTask` plus its `SourceTaskPayload`
tag rows, with bucket / input / output folders derived from the payload by `applyDerivedLocation`
(`:609-629`, helper at `:106-111`).

### 2.6 Behaviour-by-behaviour comparison

| Behaviour | Old | New | Verdict |
|---|---|---|---|
| Template download | yes | yes | kept |
| Export download | yes | yes | kept |
| Drag-and-drop upload | yes | yes | kept |
| Click-to-browse upload | yes | yes | kept |
| Client-side file-type check | on browse only (`accept` attribute); **none on drop** | on both paths, by extension (`bulk-transfer.ts:92-96`) | improved |
| Confirm step before sending | none -- uploads on pick | file held, sized, Upload / Remove | improved |
| Upload progress | blocking spinner | real % bar (`bulk-transfer.ts:121-122`) | improved |
| Server-chosen filename | discarded, renamed client-side | honoured (`bulk-transfer.ts:154-156`) | changed; see KI-11 |
| **Per-row error table** | Row / Error table from `response.data` (`batch-action.component.html:102-117`) | **absent** | **lost** |
| **Tenant picker for Platform Admin** | `<select>` + client refusal + `tenantId` part (`batch-action.component.ts:67-69, 113-116, 124`) | **absent** | **lost** |
| **Tenancy scoping notice** | three role-specific paragraphs (`batch-action.component.html:12-26`) | **absent** | **lost** |
| **Breadcrumb / explicit back target** | `Home / Job List / Batch Action` + `navigateByUrl(data.router)` (`batch-action.component.html:1-7`, `.ts:185-187`) | `Location.back()` (`bulk-transfer.ts:65-67`) | **weakened** |
| Empty "Results" placeholder | `Upload a file to see results here.` (`batch-action.component.html:119-121`) | none -- card simply absent | changed, acceptable |
| Route role gate on the task page | none; `AuthGuard` only | `minRole: 'TENANT_ADMIN'` + `roleGuard` (`app.routes.ts:221-222`) | improved |
| Entry button hidden for a tenant user | no | yes on tasks (`features/tasks/tasks.html:16`) | improved |
| Dark mode | none in the old app | full token-based theming | improved |

---

## 3. Expected behaviour

Where this differs from §2 it is called out explicitly.

1. **The page states, before anything is uploaded, whose records the import will create and whose
   the export will contain.** A tenant user should read "these become jobs in your workspace"; a
   platform admin should read "each job takes its tenant from the task it links to". *Differs from
   today:* the old app said all of this and the new app says none of it.

2. **A Platform Admin can import tasks.** The screen asks which tenant the tasks belong to, will not
   let the upload start until the question is answered, and sends the answer.
   *Differs from today:* the new app cannot do this at all -- every attempt is refused by
   `resolveTenantIdForCreate` after the whole file has been parsed.

3. **A rejected import tells the operator which rows were wrong and why, on the page, in a form they
   can work from.** The server already produces exactly this; it is being thrown away.
   *Differs from today* in the new app only.

4. **A file the server will refuse is refused by the browser first.** `.xls` is not an xlsx and the
   server never accepts one; offering it as a choice is a promise the API does not keep.
   *Differs from today.*

5. **A bad id in a cell is a row error, not a crashed request.** Non-numeric `Task Detail Id` or
   `TaskTypeId` must be reported like any other row problem. *Differs from today in both apps.*

6. **An import is all-or-nothing.** The validate-then-save split already gives this for validation
   failures; a database failure part-way through the save loop must not leave half a file imported.
   *Differs from today in both apps* -- neither upload method is `@Transactional`.

7. **The bulk job path enforces the same rules as the single-job form.** Specifically: a task with
   no owning tenant is refused, and the caller chooses Auto or Manual rather than always getting
   Auto. *Differs from today in both apps.*

8. **The XML in a task payload cell is parsed by a hardened parser.** *Differs from today* -- see
   §8 and KI-18.

9. **The export and the import template are visibly different things.** Either the export round-trips
   into the importer, or the page says plainly that it does not. *Differs from today* -- today the
   new page's own copy implies a round trip that fails.

10. **Everything already true stays true**: both templates, both exports, drag-and-drop, the progress
    bar, the confirm step, the role gate on `tasks/bulk`, dark mode, the responsive two-column
    layout.

---

## 4. Frontend requirements

### 4.1 Routes

| Route | Component | Route data | Guards |
|---|---|---|---|
| `jobs/bulk` | `BulkTransfer` | `{ kind: 'job' }` | shell `authGuard` + `passwordChangeGuard` |
| `tasks/bulk` | `BulkTransfer` | `{ kind: 'task', minRole: 'TENANT_ADMIN' }` | shell guards + `roleGuard` |

Both stay children of the shell. `kind` must keep arriving through `withComponentInputBinding()`
(`app.config.ts:11`) into `input.required<Kind>()`; a route that forgets `data.kind` throws at
construction rather than rendering a half-configured page, which is the desired failure.

### 4.2 Page structure

One page, unchanged in outline: page head with Back / title / subtitle, then a two-card grid --
**Import** on the left, **Export** on the right (`bulk-transfer.html:14`, `grid gap-4 lg:grid-cols-2 items-start`).

Additions:

- **A scope banner** above the grid, one line, three states, driven by
  `auth.isPlatformAdmin()` and `kind()`:
  - tenant caller, either kind -- everything created belongs to your workspace; the export contains
    only your workspace's records.
  - platform admin, `kind === 'job'` -- each job inherits its tenant from the task it links to; the
    export spans every tenant.
  - platform admin, `kind === 'task'` -- choose the owning tenant below; the export spans every
    tenant.
- **A tenant `<select>` inside the Import card**, rendered only when
  `auth.isPlatformAdmin() && kind() === 'task'`, populated from `tenant.json/listTenants`, required
  before Upload is enabled.
- **A row-error table** below the result card, columns **Row** and **Message**, rendered when the
  failed response carried a non-empty `data` array. Render each message as **text**, not
  `innerHTML`: the server's `<br>` separators should be split on and turned into real lines rather
  than injected as markup (the old app bound `[innerHTML]`, `batch-action.component.html:113`).
- **A file-size ceiling** checked in `accept()`, alongside the extension check.
- **An explicit back target** from a per-kind config value (`/jobs`, `/tasks`) instead of
  `Location.back()`.

### 4.3 Forms

There is no `FormGroup` and there does not need to be one: the page's whole input is a file plus,
for one role on one kind, a tenant id. Keep it on signals as it is today. The tenant select is the
only field, and its only rule is "required, when shown".

### 4.4 Tables

One table, the row-error table described above. It carries the same chrome as every other list in
the new app -- it is a plain `.table` inside an `overflow-x-auto` wrapper; it does not need
`TableShell`, because it has no independent loading or error state of its own.

### 4.5 States

| State | What is on screen |
|---|---|
| Initial | Both cards. Import shows the empty dropzone; Export shows two enabled buttons. Nothing is fetched on entry, so there is no page-level loading state -- except when the tenant select is shown, which does load, and must show a disabled select reading "Loading tenants…" until it resolves. |
| File chosen | Filename, formatted size, **Upload** and **Remove** (`bulk-transfer.ts:57-63`). |
| Uploading | Progress bar and `{{ progress() }}% uploaded`; both action buttons replaced by the bar. |
| Upload succeeded | Green-bordered result card with the server's message; the file is cleared. |
| Upload failed, no row detail | Red-bordered result card with the server's message. |
| Upload failed, row detail | The same card, plus the Row / Message table. |
| Download in flight | That one button disabled with a spinning icon; the other stays live (`bulk-transfer.html:74-77, 86-89`). |
| Download failed | Toast. There is no persistent surface for a failed download and none is needed -- nothing on the page depends on it having succeeded. |
| Tenant not chosen (platform admin, tasks) | Upload disabled, with the reason under the select. |

### 4.6 Dark and light mode

Everything on the page already resolves through theme tokens: `.dropzone` and `.dropzone-active`
(`scheduler1/next/src/styles.css:692-701`), `.progress` / `.progress-bar` (`:703-707`), `.card`,
`--text-muted`, and the two icon classes `icon-ok` / `icon-crit`. The one place a colour is written
inline is the result card's border, and it is written as a token
(`bulk-transfer.html:56`). The new table and the new banner must follow the same rule: no literal
hex, no colour defined only inside `html.dark`.

The old app has no dark mode at all (`.ai/discovery/features.md` §3), so there is nothing to port.

### 4.7 Responsive behaviour

`lg:grid-cols-2` stacks the two cards below the `lg` breakpoint, Import first -- correct, since
Import is the reason to open the page. Requirements for what is added:

- The scope banner wraps rather than truncating.
- The tenant select is full-width inside its card at every size.
- The row-error table scrolls horizontally inside its own container; the page body never does.
- The dropzone's `px-6 py-10` is comfortable on a phone and needs no change.

---

## 5. Backend requirements

### 5.1 Endpoints

Effective role is the class-level `@PreAuthorize` unless a method-level one replaces it. **None of
these six declares a method-level annotation**, so all six inherit the class value. Role hierarchy is
`ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN > ROLE_TENANT_USER` (`config/MethodSecurityConfig.java:29`),
so "TENANT_USER" below means "TENANT_USER and above".

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/sourceJob.json/downloadSourceJobTemplateFile` | TENANT_USER (`SourceJobRestApi.java:29`) | Returns the bundled `Scheduler.xlsx` with task-id, frequency, priority and True/False dropdowns injected. Filename `BatchDownload-<yyyy-MM-dd>-<uuid>.xlsx` (`:191-203`). |
| GET | `/sourceJob.json/downloadListSourceJob` | TENANT_USER | 15-column export of live jobs, sheet `SourceJob`. Platform admin gets every tenant; anyone else gets their own (`:205-217`). |
| POST | `/sourceJob.json/uploadSourceJob` | TENANT_USER | Multipart `file`. Creates `SourceJob` + `Scheduler` per row (`:219-231`). |
| GET | `/sourceTask.json/downloadSourceTaskTemplate` | TENANT_ADMIN (`SourceTaskRestApi.java:28`) | Five headings, sheet `ListSourceTask`, no dropdowns (`:145-157`). |
| GET | `/sourceTask.json/downloadListSourceTask` | TENANT_ADMIN | 8-column export, sheet `ListSourceTask` (`:131-143`). |
| POST | `/sourceTask.json/uploadSourceTask` | TENANT_ADMIN | Multipart `file`, plus optional `tenantId` bound onto `FileUploadDto` (`model/dto/FileUploadDto.java:28-29`). Creates `SourceTask` + `SourceTaskPayload` rows (`:159-170`). |

`FileUploadDto` is bound as a command object, not `@RequestBody` -- `MultipartFile file` and
`Long tenantId` are read from the multipart parts by name.

### 5.2 Services

| Service | Where | Owns |
|---|---|---|
| `SourceJobBulkService` / `Impl` | `model/service/SourceJobBulkService.java`, `model/service/impl/SourceJobBulkServiceImpl.java` (256 lines) | All three job operations. Injects `TransactionServiceImpl`, `SourceJobRepository`, `SchedulerRepository`, `BulkExcel`, `NotificationCenterService` (`:50-60`). |
| `SourceTaskService` / `Impl` | `model/service/impl/SourceTaskServiceImpl.java:483-635` | All three task operations, sharing the class with the single-task CRUD. |
| `BulkExcel` | `util/excel/BulkExcel.java` | POI plumbing. Workbook, sheet and `DataFormatter` are `ThreadLocal` -- the class comment (`:12-25`) records the concurrent-export bug that made them so. |
| `JobDetailValidation` | `util/validation/JobDetailValidation.java` | Per-row job rules, §7. |
| `SourceTaskValidation` | `util/validation/SourceTaskValidation.java` | Per-row task rules **and** the XML-to-tag-rows parse (`:136-175`). Used by nothing but `uploadSourceTask`. |
| `ProcessTimeUtil` | `util/ProcessTimeUtil.java` | The frequency / priority / True-False vocabularies (`:25-28`) and `applyInitialSchedule` (`:212-217`). |

Required changes:

- Mark both upload methods `@Transactional`.
- Parse the id cells defensively and report a row error instead of throwing.
- Harden `SourceTaskValidation`'s `DocumentBuilderFactory`, matching
  `util/TaskPayloadLocationUtil.java:53-54`.
- Guard the null `getContentType()`.
- Bring the bulk job path level with `SourceJobServiceImpl.addSourceJob` on the no-owning-tenant
  refusal.

---

## 6. Database requirements

Read and written through JPA; no schema change is required by this feature.

| Table | Entity | Role here |
|---|---|---|
| `source_job` | `model/pojo/SourceJob.java` | Written one row per accepted job row. Import sets `job_name`, `task_detail_id`, `job_status='Active'`, `tenant_id` (copied from the task), `assigned_user_id`, `priority`, `execution='Auto'`, `complete_job`, `fail_job`, `skip_job`. Export reads those plus `last_job_run`, `job_running_status`, `date_created`. |
| `scheduler` | `model/pojo/Scheduler.java` | One row per accepted job row: `start_date`, `end_date`, `start_time`, `frequency`, `interval_value`, `job_id`, and `next_run_at` / `expired` seeded by `applyInitialSchedule`. **`days_of_week` and `day_of_month` are never written by the bulk path** -- the template has no column for them, and its own guide sheet says so (`Scheduler.xlsx`, sheet `Scheduler-Detail`, row 8). |
| `source_task` | `model/pojo/SourceTask.java` | Written one row per accepted task row: `tenant_id`, `task_name`, `task_payload`, `pipeline_id`, `home_page_id`, `task_status='Active'`, `source_task_type_id`, and `bucket` / `input_folder` / `output_folder` derived from the payload. **`group_id` is never written** -- no column in the upload header, though `addSourceTask` sets it (`SourceTaskServiceImpl.java:170`). Also read by both exports and by the job template's dropdown. |
| `source_task_payload` | `model/pojo/SourceTaskPayload.java` | One row per XML tag: `tag_key`, `tag_parent`, `tag_value`, FK `payload_id` → `source_task.task_detail_id`. |
| `source_task_type` | `model/pojo/SourceTaskType.java` | Read only, to validate and bind `TaskTypeId`. |
| `tenant` | `model/pojo/Tenant.java` | Read only: `existsById` in `resolveTenantIdForCreate`, and `listTenants` for the picker. |
| `notification` | `model/pojo/Notification.java` | One `BATCH_DONE` row per successful import. |

Tenancy: `source_job`, `source_task` and `source_task_type` carry `tenant_id` and declare
`tenantFilter`; `scheduler` and `source_task_payload` carry no tenant column and inherit scope
through their parent (`.ai/discovery/database.md:337-340`).

**Migration needed: none for the behaviour above.** Two candidates that the fixes in §13 would
create, if those fixes are taken:

- A unique index on `source_job.job_name` (scoped per tenant) if the template's documented "Job Name
  must be unique" rule is to become real. Today `SourceJob.java:75-77` declares no uniqueness and
  the column is `length = 1000`, which is too wide for a plain B-tree unique index on MySQL's
  default charset -- it would need a prefix or a shorter column. **Recommend not doing this** (§13).
- Nothing else. Adding `days_of_week` / `day_of_month` to the importer needs no migration; the
  columns already exist (`V15.0-scheduler-recurrence-rules.yaml`, per
  `.ai/discovery/database.md:120`).

---

## 7. Validation

### 7.1 Client

| Rule | Where | Also on the server? |
|---|---|---|
| Filename ends `.xlsx` or `.xls` | new: `bulk-transfer.ts:92-96`. old: `accept` attribute on browse only, nothing on drop (`batch-action.component.html:9-10`) | Partly -- the server accepts **only** the xlsx MIME (`SourceJobBulkServiceImpl.java:146`, `SourceTaskServiceImpl.java:530`). `.xls` passes the client and fails the server: KI-5. |
| A tenant must be chosen before a platform admin uploads tasks | old: `batch-action.component.ts:113-116` | **Yes** -- `resolveTenantIdForCreate` (`SourceTaskServiceImpl.java:96-98`). Correctly enforced on both sides in the old app; **client half is missing entirely in the new app**, which is why the new app's platform-admin import fails. |
| File size | **nowhere in either client** | Only the 500 MB multipart ceiling (`process/src/main/resources/application.properties:40-41`). See KI-15. |

No rule in either client is enforced client-only in the sense that matters -- the server re-checks
everything the client checks. The finding runs the other way: the server enforces rules the client
does not mirror, so the operator learns about them late.

### 7.2 Server -- file level

| Rule | Job | Task |
|---|---|---|
| Content type is exactly `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `SourceJobBulkServiceImpl.java:146-149` | `SourceTaskServiceImpl.java:530-533` |
| Workbook has at least one sheet | `:152-154` | `:536-538` |
| A sheet with the expected name exists (`Job-Add` / `ListSourceTask`) | `:155-157` | `:539-541` |
| At least one data row | `:158-159` | `:542-543` |
| `getLastRowNum() <= 1001`, reported as "File support 1000 rows at a time." | `:160-162` | `:544-546` |
| Header row matches the expected headings cell for cell | `:167-174` (11 columns, `ProcessUtil.java:31-35`) | `:552-561` (exactly 5 physical cells, then `UPLOAD_SOURCE_TASK_HEADER`, `SourceTaskServiceImpl.java:139-141`) |

A file-level failure aborts immediately and returns a single message with no `data` list.

### 7.3 Server -- per row, jobs

`JobDetailValidation.isValidJobDetail()` (`util/validation/JobDetailValidation.java:161-205`), then
`isValidDetail()` (`:207-225`) and `dateTimeValidation` (`:253-283`):

| Rule | Line |
|---|---|
| `Job Name` present | `:162-164` |
| `Task Detail Id` present | `:165-167` |
| `Start Date` present, and matches `^[0-9]{4}-(0[1-9]\|1[0-2])-(0[1-9]\|[1-2][0-9]\|3[0-1])$` | `:168-170, 180-182` |
| `Start Time` present, and matches `^(0[0-9]\|1[0-9]\|2[0-3]):([0-5][0-9])$` | `:171-173, 183-185` |
| `Frequency` present, and one of `Mint, Hr, Daily, Weekly, Monthly` | `:174-176, 186-188` (`ProcessTimeUtil.java:28`) |
| `Priority` present, and one of `1..9, 99, 100` | `:177-179, 192-194` (`ProcessTimeUtil.java:26-27`) |
| `End Date`, if present, matches the date pattern | `:189-191` |
| The three email flags, if present, are `True` or `False` (case-insensitive, capitalised before comparison) | `:195-203, 239-241` |
| `Recurrence`, if present, is one of the values allowed for that frequency | `:209-213` (`ProcessTimeUtil.java:43-71`) |
| `Start Date` is today or later | `:261, 280-282` |
| `End Date` is not before `Start Date` | `:267-268` |
| Weekly needs ≥ 7 days between start and end; Monthly needs ≥ 31 | `:269-273` |
| `Start Time` is not already past on today's date | `:276-279` |
| The referenced task exists, is `Active`, and belongs to the caller's tenant (or the caller is a platform admin) | `SourceJobBulkServiceImpl.java:206-210` → `TransactionServiceImpl.java:191-194` |

**Not validated, and it should be:** that `Task Detail Id` is numeric. `Long.valueOf` at
`SourceJobBulkServiceImpl.java:207` throws `NumberFormatException` on anything else -- KI-4.

**Documented but not enforced anywhere:** "Job Name must be unique", stated in the bundled
template's `Scheduler-Detail` sheet, row 2 -- KI-10.

### 7.4 Server -- per row, tasks

| Rule | Line |
|---|---|
| `TaskTypeId` present | `util/validation/SourceTaskValidation.java:118-120` |
| `Task Name` present | `:121-123` |
| `Task Payload` present | `:124-126` |
| `Task Payload` parses as XML; the parse result becomes the tag rows | `:127-133, 136-175` |
| The task type exists **and** is visible to the caller -- same message for both, so the sheet is not an id oracle | `SourceTaskServiceImpl.java:580-585`, helper `:126-131`. The comment at `:582-583` records the intent. |
| The task type is not `Delete` | `:586-587` |
| The task type is not `Inactive` | `:588-589` |
| Owning tenant resolves: caller's own for a tenant user; supplied, present and existing for a platform admin | `:603-607` → `:91-104` |

`PipelineId` and `HomePage` are read but never validated (`:574-578`).

**Not validated, and it should be:** that `TaskTypeId` is numeric -- `Long.valueOf` at
`SourceTaskServiceImpl.java:581`, KI-4.

**Ordering flaw:** the tenant check at `:603` runs *after* every row has been read, validated and
XML-parsed. A platform admin who forgot the tenant pays for the whole file first.

---

## 8. Security

### 8.1 `jobs/bulk` -- all four layers

| Layer | What it says |
|---|---|
| **Frontend guard** | `authGuard` on the shell, `passwordChangeGuard` as `canActivateChild`. No `minRole`, and `auth.guard.spec.ts:157-163` asserts that on purpose. Any signed-in user reaches the page, and the "Bulk import" button on `/jobs` is ungated (`features/jobs/jobs.html:19`). Correct: every endpoint behind it is TENANT_USER. |
| **Controller `@PreAuthorize`** | Class-level `hasRole('TENANT_USER')` (`SourceJobRestApi.java:29`). None of the three methods overrides it, so all three are TENANT_USER-and-above. |
| **Service rule** | Export: `TenantContext.isPlatformAdmin() ? findAll() : findByTenantId(TenantContext.getTenantId())` (`SourceJobBulkServiceImpl.java:95-97`). Import: every row's task must come back from `TransactionServiceImpl.findByTaskDetailIdAndTaskStatus`, which applies `isPlatformAdmin() \|\| Objects.equals(task.getTenantId(), TenantContext.getTenantId())` (`TransactionServiceImpl.java:191-194`). The created job's tenant is then *copied from the task*, never taken from the request (`SourceJobBulkServiceImpl.java:228`). Template: the task-id dropdown comes from `findAllSourceTask()`, which branches the same way (`TransactionServiceImpl.java:196-200`). |
| **Hibernate filter** | Declared on `SourceJob` (`SourceJob.java:28-29`) and `SourceTask` (`SourceTask.java:23-24`), **and never enabled on this path**. `SourceJobBulkServiceImpl` does not inject `TenantFilterHelper` at all (`:50-60`) -- confirmed by grepping `enableIfNeeded` across the backend, which lists no hit in that file. Layer 4 contributes nothing here; the explicit repository predicates are the whole of the enforcement. |

Per role:

- **TENANT_USER** -- may download the template (dropdown scoped to their tenant's active tasks),
  download the export (their tenant's jobs only), and import jobs against their own tenant's active
  tasks. A row naming another tenant's task id fails as *"Deleted sourceTask is not linked with
  source job at row N"* -- an imprecise message but a correct refusal.
- **TENANT_ADMIN** -- identical. Nothing on this page distinguishes the two.
- **PLATFORM_ADMIN** -- template dropdown lists every tenant's active task ids; export spans every
  tenant; import may link any task, and each created job lands in that task's tenant.
- **A caller with a null `tenant_id` who is not a platform admin** -- `Objects.equals(null, null)`
  is `true`, so such a caller would pass the ownership check against a *platform-owned* task
  (`tenant_id` NULL) and create a job under a null tenant. Whether such an account can exist depends
  on `AppUser`/JWT issuance, which is outside this feature. Recorded here because the trap is
  real; **not verified** that any such account exists.

### 8.2 `tasks/bulk` -- all four layers

| Layer | What it says |
|---|---|
| **Frontend guard** | `roleGuard` with `data.minRole = 'TENANT_ADMIN'` (`app.routes.ts:219-223`); `auth.guard.spec.ts:148-154` asserts it. The route comment (`app.routes.ts:216-218`) explains why it is gated where its jobs twin is not. The entry button is behind `auth.canManageTasks()` (`features/tasks/tasks.html:16`), which is `hasAtLeast('TENANT_ADMIN')` (`core/auth/auth.service.ts:87, 53-56`). |
| **Controller `@PreAuthorize`** | Class-level `hasRole('TENANT_ADMIN')` (`SourceTaskRestApi.java:28`). The three bulk methods declare nothing of their own, so they keep TENANT_ADMIN -- unlike `listSourceTask`, `fetchAllLinkJobsWithSourceTaskId`, `fetchAllLinkSourceTaskWithSourceTaskTypeId` and `fetchSourceTaskWithSourceTaskId`, whose method-level `hasRole('TENANT_USER')` **replaces** the class value (`:69, 88, 108, 120`). |
| **Service rule** | Export: `isPlatformAdmin() ? downloadListSourceTask() : downloadListSourceTaskForTenant(tenantId)` (`SourceTaskServiceImpl.java:484-486`), both native queries carrying their own `where` (`SourceTaskRepository.java:45-52`). Import: `isSourceTaskTypeVisibleToCaller` per row (`:584`, helper `:126-131` -- a NULL-tenant type is platform-owned and shared with everyone), and `resolveTenantIdForCreate` for the owning tenant, which ignores a tenant caller's supplied id entirely (`:91-104`). |
| **Hibernate filter** | Declared on `SourceTask` and on `SourceTaskType` with the shared-catalogue variant `(tenant_id = :tenantId or tenant_id is null)` (`SourceTaskType.java:26`). **Not enabled on any of the three bulk methods** -- `SourceTaskServiceImpl` calls `enableIfNeeded` at `:209, :254, :440` only, none of which is on this path. It would not help the export anyway: that query is `nativeQuery = true`, which a Hibernate `@Filter` does not touch. And `findById` at `:581` is exempt by definition -- which is precisely why `isSourceTaskTypeVisibleToCaller` is hand-written beside it. |

Per role:

- **TENANT_USER** -- refused at the frontend guard (redirected to `/unauthorized`), never shown the
  button, and refused with 403 by the class-level `@PreAuthorize` on all three endpoints if they
  call them directly. All three layers agree.
- **TENANT_ADMIN** -- full use. Export and template are scoped to their tenant. Import may bind only
  their own or a platform-owned task type; the owning tenant is forced to their own regardless of
  what the request says.
- **PLATFORM_ADMIN** -- passes the guard by hierarchy. Export spans every tenant, may bind any
  tenant's task type -- and **cannot import at all through the new UI**, because the tenant part the
  server demands is never sent. See KI-1.

### 8.3 The one genuine vulnerability

`SourceTaskValidation.parseXmlToRequest` (`util/validation/SourceTaskValidation.java:136-145`) builds
a `DocumentBuilderFactory` with `setNamespaceAware(true)` and **no** entity-resolution hardening,
then parses a string taken straight from a spreadsheet cell. The same repository hardens the very
next parser in the same request: `TaskPayloadLocationUtil.java:53-54` sets
`disallow-doctype-decl`. Ordering makes this reachable -- `isValidSourceTask()` runs at
`SourceTaskServiceImpl.java:592`, `applyDerivedLocation` only at `:619`.

`SourceTaskValidation` has exactly one caller, `uploadSourceTask` -- verified by grepping the
identifier across the backend, which returns only `SourceTaskServiceImpl.java:33, 547, 564`. So this
is a bulk-transfer-only exposure, reachable by any TENANT_ADMIN. Detail in KI-18.

---

## 9. Error handling

### 9.1 Import

| What went wrong | Server sends | Old app shows | New app shows |
|---|---|---|---|
| No `file` part | 400, `"File not found for process."` (`SourceJobRestApi.java:226`, `SourceTaskRestApi.java:165`) | error toast | red result card + toast, "The file could not be uploaded." (the message is nested where `err.error.message` finds it, so the real text does appear) |
| Wrong content type | 200 + `ERROR, "You can upload only .xlsx extension file."` | red banner + toast | red result card + toast, with the real message |
| No sheets / wrong sheet name / empty / > 1000 rows / header mismatch | 200 + `ERROR` and a specific message | red banner + toast | red result card + toast |
| **Rows failed validation** | 200 + `ERROR, "Total N source jobs invalid.", data: [ "…row 3.<br>", … ]` (`SourceJobBulkServiceImpl.java:219`, `SourceTaskServiceImpl.java:601`) | **Row / Error table listing every failure** (`batch-action.component.html:102-117`) | **"Total N source jobs invalid." and nothing else.** The operator is told how many rows are wrong and never which. |
| Platform admin, tasks, no tenant | 200 + `ERROR, "Tenant is required when creating a source task as Platform Admin."` | unreachable -- the client refused first with a clearer message | red result card with that message, after the whole file was uploaded and parsed |
| Non-numeric id in a cell | 400, `"Sorry, the file could not be uploaded. Please contact support."` (jobs) / `"Some internal error occurred contact with support."` (tasks) | error toast | red card + toast. Nothing points at the offending cell in either app. |
| 403 on `tasks/bulk` | Spring's default 403 page, no `message` field | error toast, likely rendering the JSON blob via `formatMessage`'s `JSON.stringify` fallback (`_services/alert.service.ts:39-43`) | `err?.error?.message` is undefined → generic "The file could not be uploaded." |
| 401 | -- | toast | interceptor refreshes once and replays; if the refresh fails the queued request errors properly (`core/auth/auth.interceptor.ts:7-19`) |
| Network drop mid-upload | -- | spinner hides, toast | progress freezes, then the error branch fires: card + toast |

### 9.2 Export and template

| What went wrong | Server sends | Old app | New app |
|---|---|---|---|
| Template resource missing | 400 + `ERROR, "Sorry, the file could not be downloaded. Please contact support."` (`SourceJobRestApi.java:199-202`) | toast | toast |
| Export blew up | 500 + `ERROR, "Some internal error occurred contact with support."` | toast | toast |
| 403 (a tenant user calling a task endpoint directly) | 403 | toast | **generic** toast -- the response was requested as a blob, so the JSON error body arrives as a `Blob` and `err?.error?.message` is undefined (`bulk-transfer.ts:165-168`). The fallback text is reasonable; the server's reason is lost. |
| Empty body, 200 | -- | would produce a 0-byte file | caught: `"The server returned an empty file."` (`bulk-transfer.ts:152`) |

Neither app shows a persistent error surface for a failed download, and neither needs one.

---

## 10. Dependencies

| Depends on | Why |
|---|---|
| `authentication-and-access` | The bearer token, the role the guards read, and `TenantContext` -- filled from the JWT by `security/JwtAuthenticationFilter.java:40-44` -- which every scoping decision in §8 reads. |
| `source-tasks` (feature 6) | A job row cannot exist without an Active task to point at; a task row cannot exist without a visible, Active task type. The job template's dropdown *is* the task list. |
| `source-jobs` (feature 3) | The export's shape is the job list's shape, and the import is a second write path into `source_job` + `scheduler` that must agree with `addSourceJob`. |
| `platform-configuration` (feature 15) | Owns `source_task_type`, whose id is column 1 of the task import. |
| `tenants-and-users` (feature 16) | `tenant.json/listTenants` populates the picker the new app needs to regain; `resolveTenantIdForCreate` checks `tenantRepository.existsById`. |
| `own-account-and-notifications` (feature 18) | Receives the `BATCH_DONE` notification each successful import raises. |

Depended on by: nothing. No other feature calls these six endpoints -- grepping the new frontend for
`jobs/bulk` / `tasks/bulk` returns only `app.routes.ts`, `auth.guard.spec.ts` and the two list
templates.

---

## 11. Acceptance criteria

**Fixture** used throughout. Tenant **A** and tenant **B** exist. Tasks: **TA-1** Active in A,
**TB-1** Active in B, **TP-0** Active with `tenant_id` NULL, **TA-DEL** soft-deleted in A. Task
types: **TTA** in A, **TTB** in B, **TTP** with `tenant_id` NULL, **TTA-INACT** Inactive in A.
Accounts: **userA** (TENANT_USER, tenant A), **adminA** (TENANT_ADMIN, tenant A), **adminB**
(TENANT_ADMIN, tenant B), **root** (PLATFORM_ADMIN, no tenant).

### Reaching the pages

1. **userA** opens `/jobs`, clicks **Bulk import**, and lands on `/jobs/bulk` with an Import card and
   an Export card visible.
2. **userA** opens `/tasks`: no **Bulk import** button is rendered.
3. **userA** types `/tasks/bulk` into the address bar and is redirected to `/unauthorized`.
4. **adminA** opens `/tasks`, sees **Bulk import**, clicks it, and lands on `/tasks/bulk`.
5. **root** opens `/tasks/bulk` directly and the page renders -- the role gate is a *minimum*, and
   `PLATFORM_ADMIN` clears `TENANT_ADMIN`.
6. **userA**, with a valid session, issues `GET /sourceTask.json/downloadListSourceTask` from a
   terminal and receives **403**. The same call as **adminA** returns **200** and a spreadsheet.
   (Refusal and positive control on the one fixture.)

### Scope banner

7. **userA** on `/jobs/bulk` reads a banner naming their own workspace as the destination of the
   import and the extent of the export.
8. **root** on `/jobs/bulk` reads a banner saying each job takes its tenant from the task it links
   to, and that the export spans every tenant.
9. **root** on `/tasks/bulk` reads a banner asking which tenant the tasks belong to; **adminA** on
   the same page reads the tenant-scoped wording and sees no tenant question.

### Templates

10. **adminA** clicks **Import template** on `/jobs/bulk` and receives an `.xlsx` whose first sheet
    is `Job-Add` with the 11 headings, and whose `Task Detail Id` column offers a dropdown
    containing `TA-1` and **not** `TB-1`.
11. **root** clicks the same button and the dropdown contains both `TA-1` and `TB-1`.
12. **adminA** clicks **Import template** on `/tasks/bulk` and receives an `.xlsx` whose sheet
    `ListSourceTask` holds exactly the five headings `TaskTypeId`, `Task Name`, `Task Payload`,
    `PipelineId`, `HomePage` and no data rows.
13. Both downloaded files have distinguishable names -- the job template and the job export do not
    both arrive as `BatchDownload-<date>-<uuid>.xlsx`.

### Exports

14. **adminA** clicks **Export all jobs** and the file contains A's live jobs and no row belonging
    to B. **adminB** performs the same click and gets B's jobs and none of A's.
15. **root** clicks **Export all jobs** and the file contains jobs from both A and B.
16. A job soft-deleted in A does not appear in A's export.
17. **adminA** clicks **Export all tasks** and gets `TA-1` but not `TB-1`.
18. While an export is downloading, that button shows a spinner and is disabled, and the other
    download button stays clickable.

### Importing jobs

19. **adminA** uploads a one-row `Job-Add` sheet naming `TA-1`, a start date of tomorrow, a valid
    start time, `Daily`, priority `5`: the page reports `Total 1 jobs saved successfully.`, a new
    Active job appears on `/jobs` with `tenant_id` = A, and a `scheduler` row exists for it with a
    `next_run_at` in the future.
20. **adminA** uploads a sheet naming `TB-1` and the import is refused with no `source_job` row
    created. Same file, `TB-1` replaced by `TA-1`, succeeds -- the refusal is about ownership, not
    about the file.
21. **adminA** uploads a sheet naming `TA-DEL` and the import is refused with no row created.
22. **adminA** uploads a three-row sheet in which rows 2 and 3 are each wrong in a different way
    (row 2: start date in the past; row 3: `Frequency` = `Fortnightly`). The page shows a table with
    **two** rows, each carrying a message that names the spreadsheet row number and the specific
    problem; **no** `source_job` row is created for row 1 either.
23. Taking the file from 22 and fixing both bad rows, the same upload creates three jobs.
24. **adminA** uploads a sheet whose `Task Detail Id` cell reads `abc`: the page shows a row-level
    message naming that cell, **not** a generic "contact support", and no job is created.
25. **adminA** uploads a `.csv` renamed to `.xlsx`: the upload is refused with the server's
    content-type message and no job is created.
26. **adminA** drags a `.pdf` onto the dropzone: the browser refuses it before any request is sent,
    and the network tab shows no POST.
27. `.xls` is either accepted end to end or offered nowhere on the page -- the dropzone caption, the
    `accept` attribute and the client-side check all say the same thing as the server.
28. **adminA** uploads a 1200-row sheet and gets the "1000 rows at a time" refusal with no partial
    import.
29. **adminA** uploads a valid sheet and, mid-upload, sees a progress percentage that increases; on
    completion the file is cleared from the dropzone.
30. **root** uploads a valid one-row job sheet naming `TA-1`: it succeeds and the created job's
    `tenant_id` is **A**, not null.
31. **root** uploads a sheet naming `TP-0` (the platform-owned task): the row is refused with a
    message naming the task's missing tenant -- matching `addSourceJob`'s behaviour
    (`SourceJobServiceImpl.java:135-137`) -- and no job with a null `tenant_id` is created.
32. A database failure injected on the fifth save of a ten-row import leaves **zero** new
    `source_job` rows, not four.

### Importing tasks

33. **adminA** uploads a one-row `ListSourceTask` sheet naming `TTA` with a well-formed XML payload:
    it succeeds, a new Active task appears on `/tasks` with `tenant_id` = A, and its
    `source_task_payload` rows match the XML's tag tree.
34. **adminA** uploads a sheet naming `TTB` and the row is refused with the same wording a
    non-existent id would produce -- the message must not reveal that `TTB` exists.
35. **adminA** uploads a sheet naming `TTP` (platform-owned type) and it succeeds -- a shared type
    is available to every tenant.
36. **adminA** uploads a sheet naming `TTA-INACT` and the row is refused as inactive.
37. **adminA** uploads a sheet whose `Task Payload` is not well-formed XML: the row is refused with
    "Task payload not valid at row 2" and no task is created.
38. **adminA** uploads a sheet whose `Task Payload` contains an XML `DOCTYPE` declaring an external
    entity pointing at a local file: the parse is refused, the file's contents appear nowhere in the
    response, and the server makes no outbound request. A well-formed payload with no `DOCTYPE`, in
    the same upload shape, still succeeds.
39. **root** opens `/tasks/bulk`, sees a tenant select, and **Upload** stays disabled until a tenant
    is chosen.
40. **root** chooses tenant **B**, uploads a one-row sheet naming `TTP`, and a new task appears with
    `tenant_id` = B.
41. **root** attempts to upload with no tenant chosen: nothing is sent, and the reason is shown next
    to the select rather than arriving as a server error after the whole file has been parsed.
42. **adminA** includes a `tenantId` of B in a hand-crafted multipart request: the created task's
    `tenant_id` is **A**. A tenant caller's own tenant always wins.

### Cross-cutting

43. On `/jobs/bulk`, the **Back** control returns to `/jobs` even when the page was opened by pasting
    the URL into a fresh tab; on `/tasks/bulk` it returns to `/tasks`.
44. The page renders correctly in both themes: switching theme leaves the dropzone, the progress bar,
    the result card and the row-error table legible, with no element keeping a light-mode colour.
45. At 375 px wide the two cards stack with Import first, the row-error table scrolls inside its own
    container, and the page body has no horizontal scrollbar.
46. A successful import produces one `BATCH_DONE` notification for the importing user, and clicking
    it from `/notifications` lands on `/jobs` (jobs) or `/tasks` (tasks), not on a 404.

---

## 12. Known issues

Ordered by severity. Every claim below was read in the file cited.

**KI-1 -- A Platform Admin cannot import tasks in the new app at all. (blocker)**
`upload()` builds a `FormData` with exactly one part: `body.append('file', file)`
(`scheduler1/next/src/app/features/bulk/bulk-transfer.ts:110-111`). There is no tenant control on the
page and no `tenantId` anywhere in the file. The server's
`resolveTenantIdForCreate` returns `ERROR, "Tenant is required when creating a source task as
Platform Admin."` when `requestedTenantId` is null and the caller is a platform admin
(`process/src/main/java/process/model/service/impl/SourceTaskServiceImpl.java:96-98`), and
`uploadSourceTask` calls it at `:603-607`. The role guard admits a platform admin to the page
(`app.routes.ts:221-222`, `roleGuard` is a minimum), so the failure is reachable, silent about its
cause on the way in, and total. The old app had the whole mechanism: the picker condition
(`scheduler1/src/app/_component/batch-action/batch-action.component.ts:67-69`), the tenant load
(`:71-85`), the `<select>` (`batch-action.component.html:38-44`), the client refusal (`:113-116`),
and the multipart part (`scheduler1/src/app/_services/source.task.service.ts:66-72`). The same
omission exists on the new task editor (`features/tasks/edit/task-edit.ts:407-418` sends no
`tenantId` to `addSourceTask`), which is feature 6's to fix but confirms this is a pattern, not a
one-line slip.

**KI-2 -- The new app throws away the per-row error list. (major)**
Both importers return the failures in `data`: `new ResponseDto(ERROR, String.format("Total %d source
jobs invalid.", errors.size()), errors)` (`SourceJobBulkServiceImpl.java:219`) and the task
equivalent (`SourceTaskServiceImpl.java:601`). `bulk-transfer.ts:125-129` reads `status` and
`message` only, and `bulk-transfer.html:54-61` renders one line. The operator learns *"Total 7 source
jobs invalid."* and has to guess which seven. The old app rendered a Row / Error table
(`batch-action.component.ts:135`, `batch-action.component.html:102-117`). This is the single largest
functional loss in the rewrite of this feature.

**KI-3 -- The tenancy scoping notice is gone. (major)**
`batch-action.component.html:12-26` carried three role-specific paragraphs explaining exactly whose
records an upload creates and whose an export contains. Nothing equivalent exists in
`bulk-transfer.html`; the closest is *"Everything in your tenant, as a spreadsheet"* on the export
button (`:92-94`), which is wrong for a platform admin, whose export spans every tenant
(`SourceJobBulkServiceImpl.java:95-97`, `SourceTaskServiceImpl.java:484-486`).

**KI-4 -- A non-numeric id crashes the import instead of reporting the row. (major, both apps)**
`Long.valueOf(jobDetailValidation.getTaskId())` (`SourceJobBulkServiceImpl.java:207`) and
`Long.valueOf(sourceTaskValidation.getSourceTaskTypeId())` (`SourceTaskServiceImpl.java:581`) are
called on raw cell text. Neither `JobDetailValidation.isValidJobDetail()`
(`util/validation/JobDetailValidation.java:161-205`) nor `SourceTaskValidation.isValidSourceTask()`
(`util/validation/SourceTaskValidation.java:117-134`) checks numeric form. The
`NumberFormatException` escapes to the controller catch (`SourceJobRestApi.java:227-230`,
`SourceTaskRestApi.java:166-169`) and the operator gets *"Sorry, the file could not be uploaded.
Please contact support."* The export makes this likely rather than exotic: the job export writes the
task column as `String.format("%d [%s]", …)` (`SourceJobBulkServiceImpl.java:110`), so a value copied
out of an export -- `1042 [Nightly load]` -- is exactly the input that triggers it.

**KI-5 -- The new page offers `.xls`, which the server always refuses. (major)**
`accept()` admits a filename ending `.xls` (`bulk-transfer.ts:92-96`), the caption says
*".xlsx or .xls"* (`bulk-transfer.html:46`) and the input's `accept` attribute lists both (`:49`).
The server compares `getContentType()` against `ProcessUtil.SHEET_NAME`, which is the xlsx MIME
alone (`ProcessUtil.java:24`, used at `SourceJobBulkServiceImpl.java:146` and
`SourceTaskServiceImpl.java:530`). A real `.xls` arrives as `application/vnd.ms-excel` and is
refused. POI would not read it as an `XSSFWorkbook` in any case.

**KI-6 -- A null content type is an unhandled NPE. (major, both apps)**
`object.getFile().getContentType().equalsIgnoreCase(SHEET_NAME)` --
`SourceJobBulkServiceImpl.java:146`, `SourceTaskServiceImpl.java:530`. `MultipartFile.getContentType()`
may legitimately return null. The result is a 400 or 500 with the generic support message.

**KI-7 -- Neither import is atomic. (major, both apps)**
`uploadSourceJob` (`SourceJobBulkServiceImpl.java:144`) and `uploadSourceTask`
(`SourceTaskServiceImpl.java:527-528`) carry no `@Transactional`, and neither does
`TransactionServiceImpl.saveOrUpdateJob` / `saveOrUpdateScheduler` (`:133-139`) or the class itself
(annotated `@Service` only). Their single-record siblings *are* transactional --
`SourceTaskServiceImpl.addSourceTask` at `:143-145`, `SourceJobServiceImpl.updateSourceJob` at
`:181-183`. Validation runs to completion before the first write, so a bad *row* cannot cause a
partial import -- but a constraint violation, a lost connection or a `Scheduler` insert failing after
its `SourceJob` was flushed leaves the file half applied with no signal.

**KI-8 -- The bulk job path skips two rules the single-job path enforces, and hardcodes a third.
(major, both apps)**
Comparing `SourceJobBulkServiceImpl.java:221-248` with `SourceJobServiceImpl.addSourceJob`
(`:114-179`):
 - `addSourceJob` refuses a task whose `tenantId` is null -- *"Selected sourceTask has no owning
   tenant…"* (`:135-137`). The bulk path does no such check and copies the null straight through
   (`SourceJobBulkServiceImpl.java:228`), producing a job that no tenant filter will ever return.
 - `addSourceJob` runs `validateAssignee(assignedUserId, tenantId)` (`:140-143`). The bulk path
   assigns `TenantContext.getAppUserId()` unchecked (`:229`).
 - `addSourceJob` requires the caller to name `Auto` or `Manual` and refuses without it (`:121-126`).
   The bulk path hardcodes `Execution.Auto` (`:234`), and the template has no column for it, so
   Manual jobs cannot be bulk-created at all.
 - `addSourceJob` calls `notifyTaskAssigned` (`:157`); the bulk path does not, so a bulk-created job
   raises no assignment notification.

**KI-9 -- Neither export can be fed back into its importer, and the new page's copy implies it can.
(major, both apps)**
Jobs: the export writes sheet `SourceJob` with 15 headings
(`SourceJobBulkServiceImpl.java:102, 105`, `ProcessUtil.java:37-41`); the importer looks for a sheet
named `Job-Add` (`:155`, `ProcessUtil.java:29`) with 11 different headings (`:31-35`). Re-uploading
an export gives *"Sheet not found with (Job-Add)"*. Tasks: both files use the sheet name
`ListSourceTask` (`SourceTaskServiceImpl.java:489, 517`), so the sheet lookup succeeds and the
*column* check fails instead -- `getPhysicalNumberOfCells() != 5` against an 8-column export
(`:552-554`, `:134-141`) -- giving *"File at row 1 heading missing."*, which reads as a corrupt file
rather than the wrong one. Meanwhile `bulk-transfer.html:20-22` says *"Start from the template"* and
`:68-71` says *"The export is every job you can currently see"*, with nothing to say the two are not
interchangeable.

**KI-10 -- "Job Name must be unique" is documented and enforced nowhere. (minor, both apps)**
The bundled template's `Scheduler-Detail` sheet, row 2, states it
(`process/src/main/resources/Scheduler.xlsx`). `SourceJob.java:75-77` declares
`@Column(name = "job_name", length = 1000, nullable = false)` with no `unique`, and neither
`uploadSourceJob` nor `addSourceJob` checks. An import of ten identically named rows creates ten
jobs.

**KI-11 -- Every download arrives with the same opaque filename. (minor)**
`"BatchDownload-" + yyyy-MM-dd + "-" + UUID + ".xlsx"` is built identically for the job template and
the job export (`SourceJobRestApi.java:196, 210`) and for the task template and the task export
(`SourceTaskRestApi.java:136, 150`). The new client honours the header (`bulk-transfer.ts:154-156`)
and so inherits the ambiguity; four different files land in Downloads with names distinguishable only
by their UUIDs. The old client discarded the header and named them `JobTemplate.xlsx`,
`JobList.xlsx`, `TaskTemplate.xlsx`, `TaskList.xlsx` (`batch-action.component.ts:161, 177`) -- less
correct, more useful.

**KI-12 -- Back can leave the application. (minor)**
`back()` is `this.location.back()` (`bulk-transfer.ts:65-67`). Opened from a bookmark or a pasted URL
in a new tab there is no history entry, so the control does nothing or leaves the app. The old
component navigated to an explicit route supplied by route data
(`batch-action.component.ts:185-187`, `app.routing.ts:66-69, 90-93`) and additionally rendered a
breadcrumb (`batch-action.component.html:1-7`). `ROUTES` in the new component already carries a
`backTo` value (`bulk-transfer.ts:24, 31`) and **nothing reads it**.

**KI-13 -- A job whose task row is missing NPEs the whole job export. (minor)**
`sourceJob.getTaskDetail().getTaskDetailId()` and `.getTaskName()` are dereferenced without a guard
(`SourceJobBulkServiceImpl.java:110`). `SourceJob.sourceTask` is a plain `@ManyToOne` with no
`optional = false` and the column has no `nullable = false` (`SourceJob.java:79-81`). One orphaned
job makes the export unavailable to everyone in that tenant.

**KI-14 -- The job export is N+1 over an unpaged read. (minor)**
`findAll()` / `findByTenantId(...)` loads every job entity (`SourceJobBulkServiceImpl.java:95-97`)
and the body then issues one `schedulerRepository.findSchedulerByJobId` per row (`:116`), plus a lazy
load of each `SourceTask`. The task export avoids all of this with a single native join
(`SourceTaskRepository.java:36-43`).

**KI-15 -- A 500 MB spreadsheet is accepted and parsed in memory. (minor)**
`spring.servlet.multipart.max-file-size=500MB` (`process/src/main/resources/application.properties:40-41`),
and the row cap is only checked *after* `new XSSFWorkbook(object.getFile().getInputStream())` has
built the whole workbook (`SourceJobBulkServiceImpl.java:151-162`,
`SourceTaskServiceImpl.java:535-546`). Neither client caps the size --
`bulk-transfer.ts:91-99` checks the extension only.

**KI-16 -- The job template's task dropdown may exceed Excel's list limit. (minor, not verified)**
`fillDropDownValue(sheet, 1, 999, 1, everyActiveTaskId)` (`SourceJobBulkServiceImpl.java:78`) builds
an explicit-list data validation (`util/excel/BulkExcel.java:106-115`). Excel's explicit list is
capped at 255 characters of formula, and a platform admin's list is every active task across every
tenant. **Not verified:** I did not generate a template against a large fixture, so I do not know
whether POI truncates, whether Excel drops the validation, or whether the file refuses to open.

**KI-17 -- The old app's template help text overstates what the task template contains. (minor, old
app only)**
`batch-action.component.html:83-85` promises *"a blank .xlsx pre-filled with the correct headers and
dropdown values (scoped to your tenant's own lookups)"* for both kinds.
`downloadSourceTaskTemplate` writes only `fillBulkHeader` -- no `fillDropDownValue` call anywhere in
`SourceTaskServiceImpl.java:514-525`. The new copy, *"Blank sheet with the expected columns"*
(`bulk-transfer.html:80-82`), is accurate for tasks and now understates the job template.

**KI-18 -- XXE on the task payload cell. (blocker, both apps, bulk-transfer only)**
`SourceTaskValidation.parseXmlToRequest` (`util/validation/SourceTaskValidation.java:136-145`):

```java
DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
factory.setNamespaceAware(true);
DocumentBuilder builder = factory.newDocumentBuilder();
Document doc = builder.parse(new InputSource(new StringReader(xml)));
```

No `setFeature("http://apache.org/xml/features/disallow-doctype-decl", true)`, no disabling of
external general or parameter entities, no `setXIncludeAware(false)`. The `xml` argument is the
`Task Payload` cell as typed (`SourceTaskServiceImpl.java:572-573` → `:592` →
`SourceTaskValidation.java:128-130`). The evidence that this is an oversight rather than a decision
is in the same request: `TaskPayloadLocationUtil.java:53-54` sets `disallow-doctype-decl` on its own
factory, and it runs on the *same string* a few lines later (`SourceTaskServiceImpl.java:619`) --
too late to matter. Grepping the backend for `disallow-doctype-decl` returns that one hit;
`DocumentBuilderFactory.newInstance()` appears three times. `SourceTaskValidation` has exactly one
caller (`SourceTaskServiceImpl.java:33, 547, 564`), so the exposure is specific to this feature and
reachable by any TENANT_ADMIN.

**KI-19 -- The row cap is off by its own message. (cosmetic, both apps)**
`sheet.getLastRowNum() > 1001` rejects (`SourceJobBulkServiceImpl.java:160`,
`SourceTaskServiceImpl.java:544`). `getLastRowNum()` is zero-based and row 0 is the header, so 1001
data rows are accepted by a check whose message reads *"File support 1000 rows at a time."*

**KI-20 -- A missing header cell is an NPE rather than the message written for it. (cosmetic, both
apps)**
`currentRow.getCell(i).getStringCellValue()` (`SourceJobBulkServiceImpl.java:170`,
`SourceTaskServiceImpl.java:557`). `getCell(i)` returns null for a cell that was never created --
a header a user deleted rather than blanked. The surrounding code has a perfectly good
*"heading missing"* message it never gets to use. The body rows do this correctly, via
`BulkExcel.getCellDetail`'s `MissingCellPolicy.CREATE_NULL_AS_BLANK` (`util/excel/BulkExcel.java:101-104`).

### Tests

**There are none for this feature, on any tier.**

- Backend: `process/src/test/java` contains no test naming `uploadSourceJob`, `uploadSourceTask`,
  `downloadListSourceJob`, `downloadListSourceTask`, `downloadSourceTaskTemplate`,
  `JobDetailValidation` or `SourceTaskValidation`. The one file that mentions `BulkExcel` is
  `model/service/impl/SourceTaskServiceImplTenantIsolationTest.java`, and it mocks it as a
  constructor dependency (`:24, 50`); its six tests (`:111-187`) all exercise `addSourceTask` and
  `updateSourceTask`. The bulk path's own tenant checks -- `isSourceTaskTypeVisibleToCaller` at
  `:584` and `resolveTenantIdForCreate` at `:604` -- are covered by nothing.
- New frontend: `bulk-transfer.ts` has no spec. The only assertions that touch the feature are two
  route-shape tests in `core/auth/auth.guard.spec.ts:148-163`, which check that `tasks/bulk` names
  `TENANT_ADMIN` and `jobs/bulk` names no minimum. Nothing tests the component.
- Old frontend: no `.spec.ts` files exist anywhere under `scheduler1/src`.

---

## 13. Missing functionality

Absent from both applications. These are gaps, not regressions.

**A dry run.** There is no way to ask "would this file import cleanly?" without importing it. The
server already computes the answer -- validation completes before the first write
(`SourceJobBulkServiceImpl.java:163-220`) -- so a `validateOnly` flag on the existing endpoints, or a
sibling endpoint sharing the method, would expose it for a few lines. This is the highest-value
missing capability, because it converts the round trip "upload, read errors, edit, upload" into one
that costs nothing when it fails.

**Bulk update.** Every accepted row is an insert. There is no "change the priority on these forty
jobs" path, and the export -- which is the only file that carries ids -- cannot be fed back in
(KI-9). Making the export round-trip would need an id column in the import header, an
update-or-insert branch per row, and per-row ownership checks on the update side. Substantial, and
worth its own grooming document rather than a line in this one.

**Weekly and monthly day rules.** `scheduler.days_of_week` and `scheduler.day_of_month` exist
(`Scheduler.java:58-62`) and the single-job form sets them (`SourceJobServiceImpl.java:171-172`); the
bulk template has no columns for them and the bulk path never sets them
(`SourceJobBulkServiceImpl.java:236-248`). The bundled template's guide sheet states the limitation
outright (`Scheduler-Detail`, row 8). A bulk-created Weekly job therefore runs on whatever day its
start date happens to be, because `hasDayRule` is false without `daysOfWeek`
(`util/ProcessTimeUtil.java:172-178`) and `resolveInitialNextRun` falls through to the plain interval
walk (`:165-168`). Two template columns and two lines of mapping.

**Manual jobs, and the `groupId` on a task.** Two columns the single-record forms have and the
templates do not: `execution` (KI-8) and `source_task.group_id`
(`SourceTaskServiceImpl.java:170` sets it on the single path, `:609-628` does not on the bulk path).

**Task status on import.** The task export carries a `Task Status` column
(`SourceTaskServiceImpl.java:134-138`); the importer forces `Status.Active` (`:617`). Importing
something as Inactive is impossible.

**A dropdown for `TaskTypeId`.** The job template gets five data-validation lists; the task template
gets none (`:514-525`). One `fillDropDownValue` call over the caller's visible task types would put
the two templates on the same footing.

**Any test at all.** See above. The row-level validation rules in `JobDetailValidation` and the
tenant decisions in `resolveTenantIdForCreate` / `isSourceTaskTypeVisibleToCaller` are pure functions
of their inputs and are the cheapest thing in this feature to cover.
