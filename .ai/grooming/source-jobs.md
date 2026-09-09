# Grooming -- Source Jobs

Feature `source-jobs`, row 3 of [../discovery/features.md](../discovery/features.md). Migration
status **partial**.

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`. Line numbers are from the files
as they stand on branch `ai-bot` at commit `c3089a8`.

---

## 1. Purpose

A **job** is the thing an operator actually manages. A task says *what work to do*; a job says
*when to do it, how urgently, and who to tell about the outcome*. Everything else in the ETL console
either feeds a job or reports on one.

What someone comes to this screen to do, in their words:

- "Make this task run every night at two."
- "Run it now, I don't want to wait for the schedule."
- "Skip tonight's run, we're doing maintenance."
- "Turn this off for a week without losing the setup."
- "Copy that job and point it at a different schedule."
- "Which of my jobs is running right now, and which one has been stuck since this morning?"
- "Email me when this one fails. I don't need to hear about the successes."
- "This one's finished with -- get rid of it, but keep the history."

The job list is also where the console is *watched*. It is the only screen in either application
that reflects run state as it changes rather than when someone presses Refresh.

---

## 2. Existing behaviour

### 2.1 What crossed and what did not

`partial` means part of the old capability has no successor. The exact boundary:

| Capability | Old app | New app | Crossed? |
|---|---|---|---|
| List, search, filter, page | `source-job.component.*` | `features/jobs/jobs.*` | yes, with changes -- see 2.4 |
| Add / edit job | `source-job/job/job.component.*` | `features/jobs/edit/job-edit.*` | yes, with losses -- see 2.5 |
| Run now | `runSourceJob` (`source-job.component.ts:177-191`) | `runNow` (`jobs.ts:547-549`) | yes |
| Skip next run | `skipNextSourceJob` (`:467-483`) | `skipNext` (`jobs.ts:551-553`) | yes |
| Activate / deactivate | `toggleSourceJobStatus` (`:266-283`) | `toggleStatus` (`jobs.ts:578-601`) | yes, now behind a confirm |
| Delete | `processDeleteSourceJob` (`:508-529`) | `remove` (`jobs.ts:603-624`) | yes, now behind a confirm |
| Clone | `cloneSourceJob` (`:285-340`) | `clone` (`jobs.ts:432-487`) | yes |
| Bulk run / bulk delete | `:370-465` | `runSelected` / `deleteSelected` (`jobs.ts:657-694`) | yes, improved |
| Expandable row: linked task + run-duration bars | `:531-632`, `linked-task-panel` | `jobs.html:267-411` | yes, improved |
| Live status over STOMP | `/user/queue/reply` (`:78-97`) | `/topic/jobs.{tenantId}` (`core/socket/job-events.service.ts`) | yes, different transport |
| **Table / card view toggle** | `:54,56,101-116`, `source-job.component.html:50-57,60-149` | -- | **no** |
| **`tabActive` gate on History** | `:235-237`, `.html:129` | -- | **no** |
| **Filter by Active / Inactive** | `.html:21-31` over `job.jobStatus` | filter is over `jobRunningStatus` instead | **no** |
| **Field-aware deep search** (`name:foo`, `-bar`) | `_helpers/search-filter.ts:40-102` | three fields, substring only (`jobs.ts:194-206`) | **no** |
| **Newest-first ordering** | `.reverse()` (`:492`) | server order, `jobId` ascending | **no** |
| **Read-only task facts on the form** | `job.component.html:183-249` | -- | **no** |
| **Priority 99 and 100** | `global-config.ts:1` | `Validators.max(9)` (`job-edit.ts:63`) | **no** |
| **Day of month = "Last day"** | `global-config.ts:60-63` | `monthDays` is 1..31 (`job-edit.ts:48`) | **no** |
| **Weekly with no day selected** | days optional | rejected client-side (`job-edit.ts:192-195`) | **no** |
| **Interval constrained per frequency** | `FREQUENCY_DETAIL` (`global-config.ts:22-43`) | free `type="number"`, `min=1` | **no** |
| **Execution locked in edit mode** | `job.component.ts:231-234` | editable in both modes | **no** -- and its loss is a defect, see 12.1 |
| **Task dropdown limited to Active tasks** | `job.component.ts:180-183` | unfiltered (`job-edit.ts:90-95`) | **no** |
| Run / skip refused client-side on an Inactive job | `:200-215` | not checked (`jobs.html:230-235`) | **no** |

Things the new app gained that the old never had are listed in 2.6; they are not part of the
`partial` verdict.

### 2.2 The backend, which both applications share

`process/src/main/java/process/api/SourceJobRestApi.java`. One class-level annotation at line 29,
`@PreAuthorize("hasRole('TENANT_USER')")`, and **no method-level `@PreAuthorize` anywhere in the
class** -- so every endpoint on it, including create, update, delete, run and skip, is open to any
authenticated `TENANT_USER`.

The service is `process/model/service/impl/SourceJobServiceImpl.java` (699 lines).

**`addSourceJob` (`:114-179`).** Requires `jobName`, `taskDetail.taskDetailId` and `execution`.
Resolves the task by `findById` and refuses it unless `TenantOwnership.isOwnedByCaller` passes
(`:128-133`); the job inherits the *task's* tenant (`:134-137`), which is what keeps a job from
being created in a tenant the caller does not own. The assignee defaults to the caller
(`:138-139`). **`jobStatus` is hard-coded to `Status.Active` at line 148 -- whatever the client
sends is discarded.** Schedulers, when present, are created one per entry with
`ProcessTimeUtil.applyInitialSchedule` deciding the first `next_run_at` (`:158-177`).

**`updateSourceJob` (`:183-259`).** Enables the tenant filter, then `findById`. Refuses a job
owned by another tenant or already `Delete` (`:196-199`). The task is re-resolved with
`findByTaskDetailIdAndTaskStatus(id, Status.Active)` (`:203-211`) -- so **update requires an Active
task where create does not**. `jobStatus`, `execution` and `priority` are applied only when
non-null (`:212-220`); the three email flags are applied unconditionally (`:221-223`). The
scheduler branch (`:234-255`) only ever **updates an existing** row -- `findSchedulerByJobId`, then
`if (scheduler.isPresent())` with no `else`. It never creates one and never deletes one. `endDate`
and `intervalValue` are guarded by `StringUtils.isEmpty` (`:240-247`), so a null cannot clear
either.

**`deleteSourceJob` (`:263-290`).** Soft delete: `jobStatus = Delete`, then a best-effort cascade
marking the job's `job_queue` and `job_audit_logs` rows `Delete` inside its own try/catch
(`:277-285`). The scheduler row is left in place, which is safe because `findDueSchedulers` filters
on `job_status = 'Active'`.

**`toggleSourceJobStatus` (`:294-335`).** Refuses a deleted job (`:306-308`). Honours an explicit
`jobStatus` of Active or Inactive and only flips when neither is given (`:312-318`) -- deliberately
idempotent. On activation it re-seeds the schedule with `applyInitialSchedule` (`:322-333`) so a
paused job does not fire immediately and back-fill every slot it missed as `Missed`.

**`runSourceJob` (`:339-354`).** `findByJobIdAndJobStatus(jobId, Status.Active)` -- so an Inactive
or Deleted job is reported as `"SourceJob not found with jobId."` Refuses when the running status
is `Queue` or `Running` (`:347-350`); note `Start` is **not** in that list. Then
`ProducerBulkEngine.addManualJobInQueue` (`engine/ProducerBulkEngine.java:58-65`), which sets
`jobRunningStatus = Queue`, writes a `job_queue` row, stamps `last_job_run` and pushes a socket
notification.

**`skipNextSourceJob` (`:358-388`).** Same Active-only lookup and same Queue/Running refusal, plus
`execution` must be `Auto` (`:369-371`) and a scheduler must exist (`:372-376`). Refuses when there
is no further flight (`:378-383`). Otherwise writes a `Skip` queue row and advances `next_run_at`.

**`listSourceJob` (`:482-511`).** Enables the tenant filter, then
`findAllActiveAndInactiveJobs(Active, Inactive, Sort ASC jobId)` -- a JPQL query, so the Hibernate
`tenantFilter` applies. Deleted jobs never appear. Schedulers and queue counts are batched
(`:487-492`); `tabActive` is set from the queue count (`:500`); `createdByName` / `updatedByName`
are resolved in one lookup by `UserNameResolver.attachNames` (`:495`); the task's XML payload is
stripped from every row (`:505-507`).

**`fetchSourceJobDetailWithSourceJobId` (`:443-453`).** `findById` -- which the Hibernate filter
does **not** cover -- guarded explicitly by `.filter(this::isOwnedByCaller)` and a Delete check.
Note it does *not* call `attachNames`, so `createdByName` and `updatedByName` come back absent.

The dispatcher is `ProducerBulkEngine.addJobInQueue` (`:142-182`), driven every minute from
`engine/cron/ProcessCron.java:37-47` under a ShedLock. What it dispatches is
`SchedulerRepository.findDueSchedulers` (`model/repository/SchedulerRepository.java:17-22`):

```sql
select scheduler.* from scheduler
inner join source_job on scheduler.job_id = source_job.job_id
where scheduler.next_run_at <= ?1 and scheduler.expired = false
  and source_job.job_status = 'Active'
```

**There is no `execution = 'Auto'` condition.** A scheduler row is dispatched on the strength of
the job being Active, whatever its execution mode says.

### 2.3 The recurrence rules

`process/util/ProcessTimeUtil.java`.

- Frequencies are `Mint, Hr, Daily, Weekly, Monthly` (`model/enums/Frequency.java`).
- Days of the week are the seven codes `MON TUE WED THU FRI SAT SUN` and nothing else --
  `DAY_CODE_MAP` at `:32-41`, and `parseDaysOfWeek` (`:203-210`) drops anything it does not
  recognise.
- An unrecognised or empty day list is treated as *no constraint*: `hasDayRule` returns false
  (`:172-178`) and `nextByDaysOfWeek` falls back to `from.plusWeeks(1)` (`:250-263`), **ignoring
  `intervalValue` entirely**. There is a test for exactly this fallback,
  `ProcessTimeUtilTest.unrecognisedDayCodesFallBackRatherThanLooping` (`:181-188`).
- `dayOfMonth <= 0` means "the last day of the month" (`:196-197`, `:265-270`); a day past the end
  of a short month clamps to the last day.
- `computeMissedRuns` (`:116-138`) replays at most 50 missed slots after an outage.

### 2.4 The old list screen

`scheduler1/src/app/_component/source-job/source-job.component.ts` (650 lines) and
`.html` (346 lines).

Loads the whole list with one GET and reverses it so the newest job is first (`:485-506`, reverse
at `:492`), filters out `Delete` rows client-side (`:120`), then applies `SearchFilterPipe` and a
status filter over `jobStatus` (`:118-125`). Client paging at 50/100/150/200 (`:58-60`). A
table/card switch persisted in `localStorage` under `sourceJobViewMode` (`:54-56,101-116`).

Per row the guards are explicit methods -- `canRunJob`, `canSkipJob`, `canCloneJob`,
`canViewHistory`, `canDeleteJob` (`:200-243`). `canViewHistory` reads `tabActive`, the server-side
"this job has at least one run" flag, so History is not offered on a job that has never run.

Bulk select refuses to tick a queued/starting/running row with a toast (`:342-355`); bulk run and
bulk delete fire one unthrottled request per selected job and toast per failure
(`:370-465`). Bulk delete refuses the whole batch if any selected row is Queue/Start/Running/Failed
(`:418-428`).

The expanded row loads `fetchSourceJobQueueListWithJobId`, caches it per job, and draws every run
that has both a start and an end as a duration bar coloured by outcome; clicking a bar routes to
that run's logs (`:531-632`).

Live update: the component opens the STOMP connection in its constructor and patches
`jobRunningStatus`, `jobStatus`, `lastJobRun` and `scheduler.nextRunAt` from `/user/queue/reply`
(`:78-97`). That queue is per-user (`socket/NotificationService.java:34`) and only the job's
**assigned user** receives it (`engine/BulkAction.java:225-238`).

### 2.5 The old add/edit form

`scheduler1/src/app/_component/source-job/job/job.component.ts` (397 lines).

Loads every Active source task into the dropdown (`:173-194`, filter at `:180-183`). Selecting one
copies its service name, topic/partition string, payload, home page and pipeline into a nested
read-only `taskDetail` group (`:310-320`), which the template renders as a labelled block with a
copy button on the payload (`job.component.html:183-249`).

The `scheduler` group is added when execution is `Auto` and removed when it is `Manual`
(`:322-332`). In **edit** mode the execution control is created disabled (`:231-234`) -- so an
existing job's execution mode cannot be changed from this screen at all.

Schedule inputs: start date, optional end date, a 1440-entry time select, an interval select whose
options come from `FREQUENCY_DETAIL` for the chosen frequency (`:334-339`), a seven-chip weekday
picker for Weekly, and a day-of-month select for Monthly whose first option is "Last day" (value 0).
A plain-English preview is recomputed as you type (`:361-395`).

### 2.6 The new list screen

`scheduler1/next/src/app/features/jobs/jobs.ts` (789 lines) and `jobs.html` (455 lines).

Five live count tiles across the top -- Running, Queued, Completed, Failed, Never run -- computed
from the same rows the socket patches, so they move on their own (`jobs.ts:112-124`,
`jobs.html:41-64`). A warning banner counts runs that have been in flight for over thirty minutes
(`stalled.ts:17,43-46`; banner at `jobs.html:26-38`).

Filters are: execution type, run status, a three-field substring search (`jobId`, `jobName`,
`taskDetail.taskName` -- `jobs.ts:194-206`) and an "Only mine" toggle matched on `createdBy`
(`shared/ui/mine-filter.ts:47-49`). Paging reuses the legacy sizes (`shared/ui/pager.ts:4`).

The row menu offers Run now, Skip next run, Edit, Run history, Ask about this job, Duplicate, Email
notifications, Activate/Deactivate and Delete (`jobs.html:224-263`). Run and Skip are disabled while
`isInFlight`; Skip is additionally disabled when the job has no scheduler.

The expanded panel shows task type, pipeline, bucket, output folder, home page, assignee, start and
end dates, a link to the task, the Kafka topic, a "View in bucket" link, an email-notification
sentence with the three chips and a Change button, the task payload (fetched lazily and cached **by
task**, not by job -- `jobs.ts:362-377`) and the last 24 run-duration bars (`jobs.ts:391-422`).

Socket handling is where the new screen is genuinely different. `applyEvent` (`jobs.ts:284-308`)
patches a row in place on `job.status`, drops it on `job.deleted`, and re-reads that one job on
`job.toggled` / `job.updated`. A constructor effect (`:270-281`) re-reads the whole list after a
*gap* in the connection, because a dropped socket loses events with no replay.

Bulk actions confirm first, run at most four requests at a time (`BULK_CONCURRENCY`, `:95`) and
report once (`:702-753`).

### 2.7 The new add/edit form

`scheduler1/next/src/app/features/jobs/edit/job-edit.ts` (239 lines), `job-edit.html` (154 lines).

One reactive form (`:58-77`): name, task, execution, priority (`min 1, max 9`), state, and a nested
`scheduler` group with a cross-field validator refusing an end date before the start date
(`:27-31`). The schedule section is hidden entirely when execution is `Manual` (`:82`). Weekly
renders seven day chips whose values are the strings **`'1'` through `'7'`** (`:20-24`); Monthly
renders a 1..31 select. A plain-English summary is recomputed from the form (`:153-183`).

`save` (`:185-238`) posts to `addSourceJob` or puts to `updateSourceJob`, then routes back to
`/jobs`.

### 2.8 Tests that exist today

| Suite | File | Covers |
|---|---|---|
| Frontend | `features/jobs/job-actions.spec.ts` | that all four actions send the id in the body, not the query string |
| Frontend | `features/jobs/stalled.spec.ts` (101 lines) | the in-flight / stalled thresholds |
| Frontend | `features/jobs/notify-summary.spec.ts` (52 lines) | the chip and sentence wording |
| Backend | `src/test/java/process/model/service/impl/SourceJobServiceImplTenantIsolationTest.java` | delete and toggle refused cross-tenant, allowed same-tenant, platform admin reaches every tenant, a tenant-less context reaches nothing |
| Backend | `src/test/java/process/util/ProcessTimeUtilTest.java` | every frequency's step, month-end clamping, `dayOfMonth = 0`, weekly-by-days, end-date expiry, unrecognised day codes, missed-run replay |

**There is no test at all for `Jobs` (`jobs.ts`, 789 lines) or `JobEdit` (`job-edit.ts`).** There is
no backend test for `addSourceJob`, `updateSourceJob`, `runSourceJob` or `skipNextSourceJob`, and
nothing in `src/test/java/process/e2e/` mentions `sourceJob`.

---

## 3. Expected behaviour

Everything in section 2 that works stays. What follows is where expected diverges from today.

**A job's execution mode and its schedule must agree.** Setting a job to Manual must leave it with
no live schedule; setting it to Auto must give it one. Today the new editor lets a job be switched
either way and the server does neither (12.1).

**Every field the form offers must be honoured, or not offered.** The State control on the create
form is ignored by the server (12.2). The end-date field cannot be cleared once set (12.3). The
weekday chips write codes the server cannot read (12.4).

**The day-of-week vocabulary is `MON`..`SUN` and nothing else.** It is what the column holds, what
`ProcessTimeUtil` parses, and what the old app and the bulk importer both write.

**Priority accepts what the platform accepts** -- 1..9 plus 99 and 100
(`ProcessTimeUtil.priority:26-27`). A job at priority 99 must remain editable.

**"Last day of the month" must be reachable from the UI.** The backend implements it, the old app
offered it, the new one does not.

**Weekly without named days is a valid schedule** -- "every 2 weeks from the start date". The
backend supports it; the new form refuses it.

**An action the server will refuse should not be offered, and when it is refused the message should
say why.** Run on an Inactive job is offered and comes back "SourceJob not found with jobId."

**Filtering by Active / Inactive comes back.** It is the state an operator changes; being able to
filter run status instead is not a substitute.

**The list is newest-first.** A console where the job you just created is on page 4 is a console
people press Refresh on.

**The events the client already handles must actually be sent.** `job.updated`, `job.toggled` and
`job.deleted` are handled in `jobs.ts` and published by nothing (12.6).

**The card view returns, or is dropped on the record.** Two of the three screens that had it kept
it; jobs is the odd one out and there is no note saying why.

---

## 4. Frontend requirements

### 4.1 Routes

| Route | Component | Guard | Notes |
|---|---|---|---|
| `/jobs` | `features/jobs/jobs.ts` | `authGuard` on the shell; no `minRole` | Correct: every endpoint it calls is `TENANT_USER` |
| `/jobs/new` | `features/jobs/edit/job-edit.ts` | as above | Correct, same reason |
| `/jobs/:jobId/edit` | same component, `jobId` via `withComponentInputBinding` | as above | |

No `roleGuard` belongs on any of the three. Contrast `tasks/new`, which carries
`minRole: 'TENANT_ADMIN'` (`app.routes.ts:103-107`) because `addSourceTask` is admin-only. Jobs are
not.

### 4.2 The list

- Header: title, subtitle, Live indicator when the socket is up, Refresh, Bulk import, New job.
- Stalled banner above the tiles when `stalledCount() > 0`.
- Five live count tiles; `grid-cols-2 sm:grid-cols-3 lg:grid-cols-5`.
- Toolbar: execution filter, run-status filter, **an Active/Inactive state filter (to be added)**,
  search, Only mine, Clear.
- Selection bar, shown only when something is selected: count, Run selected, Delete selected,
  Clear selection.
- Table columns: select, expand, Job (name, `#id`, `P{priority}`), Task, Type, Schedule, Next/last
  run, Created, Run status (+ stalled pill), Created by, Updated by, State, actions.
- Row menu as in 2.6. Run and Skip must additionally be disabled when `jobStatus !== 'Active'`,
  with a title explaining why.
- Expanded panel as in 2.6.
- Pagination outside the scroll box.
- The assistant panel is feature 5's; the list only opens it.

**Loading / empty / error.** All three come from `shared/ui/data-table.ts` (`TableShell`):
a centred spinner (`:42-46`), a red alert with a "Try again" button wired to `retry` (`:47-54`),
and an empty state with an icon and a message that distinguishes "no jobs yet" from "no jobs match
the current filters" (`jobs.html:68-70`). Keep all three.

**Dark and light mode.** The app switches on `html.dark`, set by `core/theme.service.ts:17` from
either the stored `etl_theme` value or `prefers-color-scheme`. Every colour in `jobs.html` is a
token (`var(--text-muted)`, `bg-raised`, `pill-brand`, …) rather than a literal, and status colours
come from `shared/charts/status-color.ts`. Anything added must do the same.

**Responsive.** `page-head` is `flex flex-wrap` (`styles.css:1169`), the tiles collapse 5 → 3 → 2,
and the table scrolls horizontally inside `TableShell`'s `overflow-x-auto` (`data-table.ts:66`).
`jobs.html` sets `[scrollRows]="false"`, so the page scrolls rather than the rows -- deliberate, and
worth keeping for a list this wide. The detail panel's `dl` is `grid-cols-2 lg:grid-cols-4`.

### 4.3 The add/edit form

Sections: Basics (name, task, execution, priority, state), Schedule (only when execution is Auto),
Email me when (three checkboxes), then Save / Cancel.

Changes required against what is there today:

| Control | Required |
|---|---|
| Task | Only Active tasks. Label them `#id -- name`, since the id is what appears in every error message |
| Priority | Accept 1..9, 99, 100. A select is the honest control here, as it was in the old app |
| Execution, edit mode | Changing it must either carry the schedule with it (create on Manual→Auto, remove on Auto→Manual) or be locked, as it was before. It must not be a control that silently does nothing |
| Weekday chips | Values `MON`..`SUN` |
| Day of month | A "Last day" option carrying `0`, ahead of 1..31 |
| Weekly with no day | Allowed; the summary should say "every N weeks from the start date" |
| Interval | Keep the free number input, but bound it. `0` must be refused client-side and server-side |
| End date | Clearing it must clear it (needs the server change in 12.3) |
| Read-only task facts | Restore service, topic, partitions, home page, pipeline and payload-with-copy, so the person choosing a task can see what they picked |

Validation messages come from `shared/ui/field.ts`; the form must keep using `app-field` so the
messages stay consistent with the other 17 reactive forms.

### 4.4 Dialogs

| Dialog | Where | Purpose |
|---|---|---|
| Confirm activate / deactivate | `confirmWith`, `jobs.ts:578-601` | Names the job and states that missed slots are recorded as Missed rather than replayed |
| Confirm delete | `jobs.ts:603-624` | States the run history is kept |
| Confirm bulk run / bulk delete | `jobs.ts:696-700` | Names the count |
| Email notifications | `features/jobs/notify-dialog.ts` | The three switches, reachable from the row without opening the whole form |

---

## 5. Backend requirements

### 5.1 Endpoints

All on `SourceJobRestApi`, base path `/api/v1/sourceJob.json`. The Role column is what is
**enforced today**: the class-level `@PreAuthorize` at line 29, since no method on this controller
overrides it. `PLATFORM_ADMIN` and `TENANT_ADMIN` reach all of them through the hierarchy
`ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN > ROLE_TENANT_USER` (`config/MethodSecurityConfig.java:29`).

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/listSourceJob` | `TENANT_USER` | Every Active/Inactive job in the caller's tenant, `jobId` ascending, with scheduler, `tabActive`, author names, and the task payload stripped |
| GET | `/fetchSourceJobDetailWithSourceJobId?jobId=` | `TENANT_USER` | One job with its scheduler. Refuses another tenant's job and a deleted job |
| POST | `/addSourceJob` | `TENANT_USER` | Creates a job under the *task's* tenant. Always Active (see 12.2). Creates schedulers when given |
| PUT | `/updateSourceJob` | `TENANT_USER` | Replaces the whole job. Requires an **Active** task. Updates an existing scheduler only |
| PUT | `/deleteSourceJob` | `TENANT_USER` | Soft delete; best-effort cascade over `job_queue` and `job_audit_logs` |
| PUT | `/toggleSourceJobStatus` | `TENANT_USER` | Honours an explicit Active/Inactive, else flips. Re-seeds the schedule on activation. Refuses a deleted job |
| POST | `/runSourceJob` | `TENANT_USER` | Queues a manual run. Active jobs only; refused when Queue or Running |
| POST | `/skipNextSourceJob` | `TENANT_USER` | Skips the next slot and advances it. Active + Auto + has a scheduler + has a further flight |
| GET | `/fetchSourceJobQueueListWithJobId?jobId=` | `TENANT_USER` | The job's runs, newest first. Used by the expanded row (and by feature 4) |
| POST | `/listSourceTask` (`SourceTaskRestApi`) | `TENANT_USER` (`SourceTaskRestApi.java:69`) | Fills the editor's task dropdown |
| GET | `/fetchSourceTaskWithSourceTaskId` (`SourceTaskRestApi`) | `TENANT_USER` (`:120`) | Fills the expanded row's payload block |

All four write endpoints take a `SourceJobDto` **in the body**. Sending the id as a query parameter
with a null body produces a 400 from Spring; `features/jobs/job-actions.ts` exists to make that
un-repeatable and `job-actions.spec.ts` asserts it.

STOMP: `/topic/jobs.{tenantId}` and `/topic/jobs.all`
(`socket/JobEventPublisher.java:28-30,81-92`). Subscription is checked against the token in
`security/StompAuthChannelInterceptor.java:68-104`.

### 5.2 Services

| Class | Responsibility |
|---|---|
| `SourceJobServiceImpl` | Everything above. Owns the ownership checks and the tenant-filter enablement |
| `ProducerBulkEngine` | `addManualJobInQueue` (`:58-65`), `skipManualJobInQueue` (`:67-78`), the scheduled `addJobInQueue` (`:142-182`), `reconcileStalledRuns` (`:103-`) at a six-hour threshold (`:88`) |
| `ProcessTimeUtil` | All recurrence arithmetic. Static, no state, fully unit-tested |
| `BulkAction` | Writes queue rows, audit lines, status changes; fans out the per-user socket push and the notification-centre entry (`:221-255`) |
| `JobEventPublisher` | The tenant-topic push. `publishStatus` and `publishLog` are live; `publishChanged` (`:70-79`) is called by nothing |
| `TenantFilterHelper` / `TenantOwnership` | Layer 4 and layer 3 of the authorization stack |
| `UserNameResolver` | `created_by` / `updated_by` → display names, one query per list |

---

## 6. Database requirements

### 6.1 `source_job`

Owned by Hibernate (`model/pojo/SourceJob.java`), not created by Liquibase -- see 12.9.

| Column | Type | Notes |
|---|---|---|
| `job_id` | bigint PK | sequence `source_job_source_Seq`, from 1000 |
| `tenant_id` | bigint | `@Filter tenantFilter: tenant_id = :tenantId` (`:28-29`); indexed `idx_source_job_tenant_id` |
| `assigned_user_id` | bigint | FK to `app_user`; indexed |
| `job_name` | varchar(1000) NOT NULL | |
| `task_detail_id` | bigint | FK to `source_task`; indexed (`V18__foreign_key_indexes.sql:11`) |
| `job_status` | varchar NOT NULL | `Active` / `Inactive` / `Delete`, case-sensitive |
| `job_running_status` | varchar | `Queue, Start, Running, Failed, Completed, Skip, Interrupt, Missed` |
| `last_job_run` | timestamp | |
| `execution` | varchar NOT NULL | `Auto` / `Manual` |
| `priority` | integer NOT NULL | |
| `date_created` | timestamp NOT NULL | |
| `complete_job`, `fail_job`, `skip_job` | boolean | the three email switches |
| `created_by`, `updated_by` | bigint | `V22__audit_columns.sql:12-13`; stamped by `AuditListener` |

### 6.2 `scheduler`

`model/pojo/Scheduler.java`. **No `tenant_id` and no Hibernate filter** -- a schedule is reached
only through its job, which is where the tenant check lives.

| Column | Type | Notes |
|---|---|---|
| `scheduler_id` | bigint PK | sequence from 1001 |
| `job_id` | bigint NOT NULL | FK `fk_scheduler_source_job` (`V13:9`), indexed `idx_scheduler_job_id` (`V18:8`) |
| `start_date` | date NOT NULL | |
| `end_date` | date | optional, inclusive |
| `start_time` | time NOT NULL | |
| `frequency` | varchar NOT NULL | |
| `interval_value` | varchar | renamed from `recurrence` by V15 |
| `days_of_week` | varchar(30) | CSV of `MON`..`SUN`. Added by V15 |
| `day_of_month` | smallint | `<= 0` means the last day. Added by V15 |
| `next_run_at` | timestamp | indexed `idx_scheduler_next_run_at`; what the dispatcher polls |
| `expired` | boolean NOT NULL default false | |
| `date_created`, `date_updated` | timestamp | |

### 6.3 Migrations this feature needs

**None for the schema.** Every column the expected behaviour needs already exists; the gaps are in
the code that writes them.

**One data repair is likely.** Any job whose `days_of_week` was written by the new form since it
shipped holds `'1'`..`'7'` rather than `MON`..`SUN`, and has been running weekly from its start date
rather than on the chosen days. Whoever fixes 12.4 should first run
`select scheduler_id, job_id, days_of_week from scheduler where days_of_week ~ '[0-9]'` and decide
per row whether to translate (1→MON … 7→SUN, matching the new form's own labels at
`job-edit.ts:20-24`) or to null the column. Translating is the better default: it is what the person
who filled the form meant.

---

## 7. Validation

`C` = client, `S` = server, `C+S` = both.

| Rule | Where | Evidence |
|---|---|---|
| `jobName` required | C+S | `job-edit.ts:60`; `SourceJobServiceImpl.java:115-116` |
| `taskDetailId` required | C+S | `job-edit.ts:61`; `:117-120` |
| `execution` required | C+S | `job-edit.ts:62`; `:121-126` |
| Task must exist and belong to the caller's tenant | S | `:128-133` |
| Task's tenant must not be null | S | `:134-137` |
| Task must be **Active** -- on update only | S | `:203-211`. Create does not check (`:128`) |
| Assignee must be in the job's tenant, or be a platform admin | S | `validateAssignee`, `:513-526` |
| `jobId` required for update/delete/toggle/run/skip | C+S | ids come from the row; `:184-185, 264-266, 295-297, 340-342, 359-361` |
| Job must not be Deleted (update, toggle, detail, queue list) | S | `:196-199, 306-308, 447, 467-469` |
| Run refused while Queue or Running | C+S | `jobs.html:230-232` via `isInFlight`; `:347-350`. **`Start` is missing from the server list** |
| Skip refused while Queue or Running | C+S | same |
| Skip requires `execution = Auto` | S only | `:369-371`. The client checks only for a scheduler (`jobs.html:233-235`) |
| Skip requires a scheduler and a further flight | S | `:372-383` |
| Run/skip require an Active job | S only | `findByJobIdAndJobStatus(..., Active)`. **The new client does not check** -- the old one did (`source-job.component.ts:205,214`) |
| Toggle refused on a deleted job | S | `:306-308` |
| Bulk delete refused if any row is in flight or Failed | C only | `jobs.ts:681-687`. The server has no batch endpoint and no such rule per row |
| `priority` in 1..9 | **C only, and wrong** | `job-edit.ts:63`. The platform's own list is 1..9, 99, 100 (`ProcessTimeUtil.java:26-27`). The server does not validate at all |
| `startDate`, `startTime`, `frequency`, `intervalValue` required when scheduled | **C only** | `job-edit.ts:70-74`. `start_date`/`start_time`/`frequency` are NOT NULL columns, so omitting them is a constraint violation at commit, not a named error |
| `endDate >= startDate` | **C only** | `endAfterStart`, `job-edit.ts:27-31`. The server accepts an end date before the start date and marks the schedule expired on the first `applyInitialSchedule` |
| Weekly requires at least one day | **C only, and it should not exist** | `job-edit.ts:192-195`. The backend treats an empty day list as "no constraint" and steps by whole weeks -- a valid schedule the form refuses |
| `daysOfWeek` values | **enforced nowhere** | The server silently drops unknown codes (`ProcessTimeUtil.java:203-210`) rather than refusing them. This is what makes 12.4 silent |
| `intervalValue` numeric and > 0 | **enforced nowhere** | `stepFunction` does `Long.parseLong` (`:79`). `0` makes every walk hit its guard and the schedule ends up expired; a non-numeric string throws inside the cron |
| `dayOfMonth` range | **enforced nowhere** | Out-of-range values clamp harmlessly (`:196-197`), so this one is benign |

Six client-only rules, three of which the server contradicts (priority, weekly-without-days,
end-date ordering) and three of which are the only thing standing between a caller and a bad row
(interval, required schedule fields, bulk-delete state). A caller with `curl` and a token bypasses
all six.

---

## 8. Security

Four layers, checked separately.

### Layer 1 -- the frontend guard

`/jobs`, `/jobs/new` and `/jobs/:jobId/edit` sit under the shell's `authGuard`
(`app.routes.ts:47-49`) and `passwordChangeGuard`, and carry **no `minRole`**. Any signed-in user of
any role opens all three. That matches the API, and is correct.

Nothing in the jobs UI is hidden by role. `AuthService` is used on this screen only for "Only mine"
(`jobs.ts:786`), not for gating.

### Layer 2 -- the controller annotation

`SourceJobRestApi.java:29` -- `@PreAuthorize("hasRole('TENANT_USER')")` at class level, **no
method-level annotation anywhere in the file**. Since `@PreAuthorize` is not repeatable and a
method-level annotation would *replace* the class one, the absence is what keeps the rule uniform
here. With the hierarchy at `MethodSecurityConfig.java:29`, all three roles pass.

So: **role decides nothing within this feature beyond being signed in.** A `TENANT_USER` may create,
edit, run, skip, deactivate and delete jobs exactly as a `TENANT_ADMIN` may. That is a deliberate
design -- a job is operational work, not configuration -- but it is worth stating plainly, because
the sibling feature `source-tasks` is `TENANT_ADMIN` for its writes and the two screens sit next to
each other in the navigation.

### Layer 3 -- the service rule

`TenantOwnership.isOwnedByCaller` (`security/TenantOwnership.java:35-41`):

- `PLATFORM_ADMIN` → true for everything.
- Any other caller must carry a tenant. `callerTenantId != null && Objects.equals(ownerTenantId, callerTenantId)`.
- A row with `tenant_id = null` is platform-owned; a tenant caller does **not** own it, and a caller
  with no tenant owns nothing.

Applied in `SourceJobServiceImpl` at `:130` (the task, on create), `:196`, `:205`, `:269`, `:300`,
`:345`, `:364`, `:399`, `:446`, `:461`. Every read-by-id and every write path is covered.

`validateAssignee` (`:513-526`) additionally refuses an assignee from another tenant, exempting
`PLATFORM_ADMIN`.

### Layer 4 -- the Hibernate filter

`SourceJob` declares `@FilterDef`/`@Filter` on `tenant_id = :tenantId`
(`model/pojo/SourceJob.java:28-29`). `TenantFilterHelper.enableIfNeeded` turns it on for a tenant
caller and off for a platform admin or a caller with no tenant
(`security/TenantFilterHelper.java:28-33`).

Two things follow, and both matter:

1. **The filter does not apply to `findById`.** `updateSourceJob`, `deleteSourceJob`,
   `toggleSourceJobStatus`, `findSourceJobAuditLog`, `fetchSourceJobDetailWithSourceJobId` and
   `fetchSourceJobQueueListWithJobId` all use it, and every one of them is guarded by an explicit
   `isOwnedByCaller`. Layer 3 is load-bearing here, not decorative.
2. **`Scheduler` never declares the filter**, so it does not have one to no-op. Every scheduler read
   in this feature goes through `findSchedulerByJobId` after the job's ownership has been
   established, so the boundary holds -- but it holds by call ordering, not by the data layer.
   `SchedulerRepository.findByJobIdIn` (used by `listSourceJob:488`) is fed ids that came from an
   already-filtered query, which is the same argument.

### Per role, concretely

| | `PLATFORM_ADMIN` (no tenant of its own) | `TENANT_ADMIN` | `TENANT_USER` |
|---|---|---|---|
| List jobs | every tenant's -- the filter is disabled for it | its own tenant's | its own tenant's |
| Open a job by id | any | only its own tenant's; another tenant's answers "SourceJob not found with %d" | same |
| Create | yes, into whatever tenant the chosen task belongs to | yes, only against its own tenant's tasks | **yes -- same as its admin** |
| Edit / delete / toggle | any | own tenant only | **own tenant only, any job in it -- not just its own** |
| Run / skip | any | own tenant only | **own tenant only, any job in it** |
| Assign a job to a user | any user | only users of its own tenant (`:522-524`) | same |
| STOMP feed | `/topic/jobs.all`, the only role allowed on it (`StompAuthChannelInterceptor.java:86-92`) | `/topic/jobs.{ownTenantId}` only | same |

The one thing worth flagging: a `TENANT_USER` may delete a job created by their `TENANT_ADMIN`.
There is no per-row author or assignee check on any write path, at any of the four layers.

### Secrets

Nothing in this feature carries one. The task payload shown in the expanded row is XML written by a
tenant admin; the Kafka topic string is a name, not a credential. `queueTopicPartition` reaches the
client as-is and is parsed for display (`shared/ui/topic.ts`).

---

## 9. Error handling

| What fails | What the user sees today | Evidence |
|---|---|---|
| The list request fails | The table area is replaced by a red alert with the server's message (or "Could not load jobs.") and a "Try again" button | `jobs.ts:343-346`, `data-table.ts:47-54` |
| The list returns `ERROR` | Same alert, carrying `response.message` | `jobs.ts:341` |
| Nothing matches the filters | "No jobs match the current filters." | `jobs.html:68-69` |
| No jobs exist | "No jobs yet." | same |
| Run on a job already in flight | The menu item is disabled with the title "This job is already queued or running" | `jobs.html:230-232` |
| Run on an Inactive job | Toast: **"SourceJob not found with jobId."** -- wrong, and the control was not disabled | `jobs.html:230`, `SourceJobServiceImpl.java:344-346` |
| Skip on a Manual job that still has a scheduler | Toast: "SourceJob skip only work with 'auto' source job." | `:369-371` |
| Skip when the schedule has ended | Toast: "No more flight skip." | `:381-383` |
| Toggle a deleted job | Toast: "Can't change status of a deleted job." Not reachable from the list, which never shows deleted rows | `:306-308` |
| Save with an invalid form | Toast "Check the highlighted fields." and every control marked touched | `job-edit.ts:187-191` |
| Save a job whose task is now Inactive | Toast: "Selected sourceTask not active." | `:206,210` |
| Save a job at priority 99 | Toast "Check the highlighted fields." **with nothing the user can see wrong** -- the priority input shows 99 and is out of its own range | `job-edit.ts:63` |
| Save fails on the network | Toast: `err.error.message` or "The job could not be saved." | `job-edit.ts:233-236` |
| Any unhandled server exception | HTTP 500 with `ProcessUtil.INTERNAL_ERROR_500` -- "Some internal error occurred contact with support." The real cause is only in the log | every catch block in `SourceJobRestApi.java` |
| Bulk action, some rows fail | One toast: "`N` queued, `M` failed: `#id message`; `#id message`" -- first two named | `jobs.ts:740-745` |
| Bulk action, all succeed | One toast: "`N` jobs queued." | `:744` |
| Clone fails | Toast: "That job could not be read." or "The copy could not be created." | `jobs.ts:439,478` |
| Payload fetch fails | The panel says "This task has no payload configured." -- **a failed read is shown as an absent payload** | `jobs.ts:370`, `jobs.html:371-372` |
| Run-history fetch fails | The panel says "This job has not completed a run yet." -- same conflation | `jobs.ts:417-420`, `jobs.html:402-405` |
| The socket drops | The Live indicator disappears; on reconnect the whole list is re-read | `jobs.html:10-15`, `jobs.ts:270-281` |
| A run stops reporting | After 30 minutes a "stalled" pill on the row and a banner above the table, both naming the likely cause | `stalled.ts:17`, `jobs.html:26-38` |

Two of these are wrong in kind rather than in wording: a failed payload fetch and a failed
run-history fetch are both rendered as "there is nothing here". The `TableShell` pattern the rest of
the app uses distinguishes the two, and these panels should too.

---

## 10. Dependencies

| Depends on | Why |
|---|---|
| `authentication-and-access` | The token, the shell guard, and the STOMP `CONNECT`/`SUBSCRIBE` credentials |
| `source-tasks` | A job cannot exist without a task. Create resolves the task and inherits its tenant; update requires the task to be **Active**; the dropdown and the expanded row's payload both come from `SourceTaskRestApi` |
| `platform-configuration` | Through the task: the task type supplies `queueTopicPartition`, which is what the dispatcher routes on. A job against a mis-scoped task type dispatches to the wrong broker silently |
| `tenants-and-users` | `assigned_user_id`, `created_by`, `updated_by`; `validateAssignee` reads `app_user` |
| Kafka + `ProducerBulkEngine` | Where a queued run actually goes |
| ShedLock + `ProcessCron` | The minute cycle that turns `next_run_at` into a queue row |
| STOMP / SockJS | `core/socket/job-events.service.ts`, `JobEventPublisher`, `StompAuthChannelInterceptor` |

| Depended on by | Why |
|---|---|
| `job-runs-and-queue` | Every `JobQueue` and `JobAuditLogs` row is a job's run |
| `dashboard`, `reports` | Both aggregate over `JobQueue` joined to `SourceJob` |
| `job-assistant` | Answers are composed from a job's own record and runs |
| `bulk-transfer` | `uploadSourceJob` creates jobs and schedulers by a second code path (`SourceJobBulkServiceImpl.java:221-249`) |
| `own-account-and-notifications` | `myActivity`; job completion and failure raise notification-centre entries (`BulkAction.java:240-255`) |

---

## 11. Acceptance criteria

Fixtures assumed: tenant **A** with jobs `A1` (Auto, Active, scheduled Daily), `A2` (Manual,
Active), `A3` (Auto, Inactive), and tenant **B** with job `B1`. Users: `pa` (`PLATFORM_ADMIN`, no
tenant), `aa` (`TENANT_ADMIN` of A), `au` (`TENANT_USER` of A), `bu` (`TENANT_USER` of B), and
`nt` (a token carrying no tenant claim).

### Listing and reading

1. `au` opens `/jobs` and sees `A1`, `A2` and `A3` and does not see `B1`. **Positive control on the
   same fixture:** `bu` opens `/jobs` and sees `B1` and none of `A1`–`A3`.
2. `pa` opens `/jobs` and sees all four of `A1`, `A2`, `A3`, `B1`.
3. `nt` calls `GET /sourceJob.json/listSourceJob` and receives an empty `data` array, not `B1` and
   not an error.
4. `bu` calls `GET /fetchSourceJobDetailWithSourceJobId?jobId=<A1>` and receives status `ERROR` with
   "SourceJob not found with <A1>." **Positive control:** the same call by `au` returns `SUCCESS`
   and `A1`'s record.
5. `au` deletes `A2`, then reloads `/jobs`; `A2` is absent from the list, and
   `GET /fetchSourceJobDetailWithSourceJobId?jobId=<A2>` returns "SourceJob not found".
6. The jobs list places the most recently created job on the first page, above older ones.
7. `au` types a job's numeric id into the search box and that job is the only row shown.
8. `au` selects "Active" in the state filter; `A1` and `A2` are shown and `A3` is not. Selecting
   "Inactive" shows `A3` and neither of the others.

### Creating and editing

9. `au` opens `/jobs/new`, fills name and task, chooses **Manual**, and saves. The schedule section
   was never shown, the job is created, and `select count(*) from scheduler where job_id = <new>`
   returns 0.
10. `au` creates a job with State set to **Inactive**. After saving, the list shows that job's State
    as Inactive. (Today it shows Active -- see 12.2.)
11. `au` opens `/jobs/new`; the task dropdown contains only tasks whose `taskStatus` is `Active`.
    **Positive control:** an admin deactivates a task, `au` reloads the page, and that task is gone
    from the dropdown while the others remain.
12. `au` edits `A1`, sets Frequency to Weekly with **Mon and Thu** ticked, and saves. `scheduler`
    for `A1` holds `days_of_week = 'MON,THU'`, and its `next_run_at` falls on a Monday or a
    Thursday.
13. `au` re-opens `A1` after 12. The Mon and Thu chips are shown as selected.
14. `au` edits `A1`, sets Frequency to Weekly and ticks **no** day, and saves. The save succeeds and
    the schedule steps by whole weeks from the start date.
15. `au` edits `A1`, sets Frequency to Monthly and Day of month to **Last day**, and saves.
    `day_of_month` is `0`, and `next_run_at` is the last day of a month.
16. `au` edits `A1`, sets an end date, saves; re-opens it, **clears** the end date, saves. `end_date`
    is null and the Schedule column no longer shows an end.
17. `au` edits a job whose priority is `99`. The priority control shows 99 as a valid value, and
    saving with no other change succeeds.
18. `au` edits `A1` and enters an end date **before** the start date. The form refuses to save and
    marks the end-date field. **Positive control:** the same form with an end date after the start
    date saves successfully.
19. `au` edits `A1` (Auto, scheduled) and changes Execution to **Manual**, then saves. After the
    save, `A1` does not run on its former timetable -- verified by
    `select count(*) from scheduler s join source_job j on j.job_id = s.job_id where j.job_id = <A1> and s.expired = false`
    returning 0, or by the row no longer appearing in `findDueSchedulers`. **Positive control:**
    `A1` still runs when `au` presses Run now.
20. `au` edits `A2` (Manual) and changes Execution to **Auto**, fills in a schedule, and saves. A
    `scheduler` row now exists for `A2` with the entered values, and the list's Schedule column
    shows it.
21. `bu` calls `PUT /updateSourceJob` with `A1`'s `jobId` and receives "SourceJob not found with
    <A1>", and `A1`'s name in the database is unchanged. **Positive control:** the same call by
    `au` renames `A1`.

### Actions

22. `au` chooses Run now on `A1`. A toast confirms it, the row's Run status becomes `Queue`, and a
    new `job_queue` row exists for `A1`.
23. `au` opens the row menu on `A1` while a run is in flight; Run now and Skip next run are both
    disabled and their tooltip says the job is already queued or running.
24. `au` opens the row menu on `A3` (Inactive); Run now and Skip next run are disabled with a
    tooltip naming the job's state. **Positive control:** `au` activates `A3`, and both become
    enabled on the same row.
25. `au` chooses Skip next run on `A1`. A `Skip` row appears in `A1`'s run history and the Next-run
    time moves to the following slot.
26. `au` chooses Skip next run on `A2` (Manual). The control is not offered. **Positive control:**
    it is offered on `A1`.
27. `au` deactivates `A1`, confirms the dialog, and the State column reads Inactive. Waiting past a
    scheduled slot produces no new `job_queue` row for `A1`.
28. `au` re-activates `A1`. `next_run_at` is in the future, and no `Missed` rows are written for the
    slots that passed while it was off.
29. `bu` calls `PUT /toggleSourceJobStatus` with `A1`'s id and receives "SourceJob not found with
    <A1>"; `A1`'s `job_status` is unchanged. **Positive control:** `bu` toggles `B1` successfully.
30. `au` chooses Duplicate on `A1`. A new job appears named `A1 (copy)`, its State is **Inactive**,
    and it carries `A1`'s task, execution, priority, email flags and schedule.
31. `au` chooses Delete on `A1` and confirms. The row leaves the list, and `A1`'s existing
    `job_queue` rows are still readable through feature 4's history for a job that is not deleted --
    i.e. the delete did not remove history from the database.
32. `au` selects three jobs, chooses Run selected, confirms; exactly one toast appears reporting
    three queued, and three new `job_queue` rows exist.
33. `au` selects a job that is Running plus two idle ones and chooses Delete selected. Nothing is
    deleted, and the message names the running job. **Positive control:** deselecting the running
    job and repeating deletes the other two.
34. `au` opens the Email notifications dialog on `A1`, ticks only "When it fails", saves, and
    re-opens it: only that box is ticked. `A1`'s schedule, task and priority are unchanged in the
    database.

### Live behaviour

35. With `/jobs` open as `au`, a run of `A1` started elsewhere moves that row's Run status through
    Queue → Start → Running without the page being reloaded and without the scroll position moving.
36. With `/jobs` open as `au`, another session deactivates `A1`; the State column on `au`'s screen
    updates without a reload. (Today it does not -- see 12.6.)
37. `bu` subscribes to `/topic/jobs.<A's tenantId>` with `bu`'s token; the subscription is refused
    and no event from tenant A arrives. **Positive control:** `bu` subscribes to
    `/topic/jobs.<B's tenantId>` and receives `B1`'s status events.
38. `au` (not a platform admin) subscribes to `/topic/jobs.all`; the subscription is refused.
    **Positive control:** `pa` subscribes to `/topic/jobs.all` and receives events from both
    tenants.
39. A run of `A1` sits in `Start` for over thirty minutes. `A1`'s row shows a "stalled" pill, and
    the banner above the table counts it. **Positive control:** a run started two minutes ago shows
    no pill and is not counted.

### States and presentation

40. With the list request failing, `/jobs` shows an error message and a "Try again" button, not an
    empty table. Pressing it re-issues the request.
41. On a tenant with no jobs, `/jobs` shows "No jobs yet." With filters that match nothing, it shows
    "No jobs match the current filters." The two are distinguishable.
42. A job whose task payload cannot be read shows an error in the payload block, distinct from the
    "This task has no payload configured." shown for a task that genuinely has none.
43. `/jobs` and `/jobs/:id/edit` render correctly in both themes: toggling the theme changes every
    surface, text and status colour with no element left unreadable.
44. At a 375px viewport, `/jobs` shows no horizontal page scrollbar; the table scrolls inside its
    own container and the toolbar controls wrap rather than overflow.

---

## 12. Known issues

Each is a defect that exists today. None is fixed here.

### 12.1 Switching a job between Auto and Manual is broken in both directions

**Auto → Manual leaves the job running.** `job-edit.ts` renders the Execution select enabled in edit
mode (`job-edit.html:40-43`) and `save()` reads it with `getRawValue()` (`:197`). When execution is
`Manual`, `isScheduled()` is false and **no `schedulers` key is put in the payload** (`:210-216`).
`updateSourceJob` sets `execution = Manual` (`SourceJobServiceImpl.java:215-217`) and its scheduler
branch is skipped entirely because `schedulers` is null (`:234`). The `scheduler` row survives with
its `next_run_at` and `expired = false`. `findDueSchedulers`
(`SchedulerRepository.java:17-22`) selects on `job_status = 'Active'` **and nothing about
`execution`** -- so the job keeps firing on a timetable the UI says it does not have.

**Manual → Auto gives the job no schedule.** The same form sends `schedulers: [...]` with
`schedulerId` null. `updateSourceJob:237-253` does `findSchedulerByJobId`, finds nothing, and
`if (scheduler.isPresent())` has no `else`. The job is now `Auto` with no scheduler row: the list's
Schedule column shows `—`, `skipNext` is disabled, and it never runs.

The old app made both states unreachable by creating the execution control **disabled** in edit mode
(`job.component.ts:231-234`). Removing that lock without giving the server the two missing branches
is what opened this.

### 12.2 The State control on the create form is ignored

`addSourceJob` hard-codes `sourceJob.setJobStatus(Status.Active)` at
`SourceJobServiceImpl.java:148` and never reads `sourceJobDto.getJobStatus()`.

Two consequences. First, `job-edit.html:52-58` offers a State select on the new-job form that does
nothing. Second, `Jobs.clone` sets `jobStatus: 'Inactive'` (`jobs.ts:449`) with the comment
"cloning a live schedule should not silently double the runs", and then tells the user
`"Copied as … — it starts inactive."` (`:469`). **The clone starts Active and its schedule runs.**
The toast states something the server did not do.

### 12.3 An end date cannot be cleared

`updateSourceJob` guards the end date with `if (!StringUtils.isEmpty(schedulerDto.getEndDate()))`
(`SourceJobServiceImpl.java:240-242`). `getEndDate()` returns a `LocalDate`; Spring's deprecated
`StringUtils.isEmpty(Object)` is true for null, so a null end date **skips the setter** and the
previous value stays. `intervalValue` has the same guard at `:245-247`.

The new form presents End date as optional and clearable (`job-edit.html:92-97`). Clearing it and
saving reports success and changes nothing.

### 12.4 The weekday picker writes codes the server cannot read

`job-edit.ts:20-24` defines the seven chips with values `'1'` … `'7'`. `save()` joins the selected
values into `daysOfWeek` (`:213`). `ProcessTimeUtil.DAY_CODE_MAP` (`:32-41`) knows only
`MON`…`SUN`, and `parseDaysOfWeek` (`:203-210`) drops everything else.

The result is silent and compounding:

- `hasDayRule` returns false (`:172-178`), so the first run is not aligned to the chosen days.
- `stepFunction` still takes the `nextByDaysOfWeek` branch, because `daysOfWeek` is non-null
  (`:87-89`), and that function returns `from.plusWeeks(1)` when the set is empty (`:252-254`) --
  **discarding `intervalValue` as well**. "Every 3 weeks on Mon and Thu" becomes "every 1 week from
  the start date".
- `ProcessTimeUtilTest.unrecognisedDayCodesFallBackRatherThanLooping` (`:181-188`) asserts exactly
  this fallback, so the behaviour is known and tested at the utility level; nothing tests that the
  form sends codes the utility understands.

There is a second face to it. A schedule written by the old app or by the bulk importer holds
`MON,THU`; `loadJob` puts those strings into `selectedDays` (`job-edit.ts:137`) and the chips
compare against `'1'`…`'7'`, so **no chip highlights** and the form appears to have no days chosen.
Clicking one appends a digit, producing a mixed list like `MON,THU,1`.

### 12.5 A job at priority 99 or 100 cannot be edited

`job-edit.ts:63` -- `Validators.min(1), Validators.max(9)`, and `job-edit.html:49` sets `max="9"`.
The platform's own priority list is `1..9, 99, 100` (`ProcessTimeUtil.java:26-27`), which the old
form offered (`global-config.ts:1`) and which the bulk-upload template still offers as a dropdown
(`SourceJobBulkServiceImpl.java:81`).

`loadJob` patches the stored priority in (`job-edit.ts:120`). A job at 99 therefore loads into an
invalid form; `save()` refuses with "Check the highlighted fields." and the only way to save any
other change to that job is to lower its priority.

### 12.6 `job.updated`, `job.toggled` and `job.deleted` are never published

`JobEventPublisher.publishChanged` (`socket/JobEventPublisher.java:70-79`) is the only producer of
those three event types, and `grep -rn "publishChanged" process/src` matches **only its own
declaration**. `SourceJobServiceImpl` injects `JobEventPublisher` (field `:49`, constructor
parameter `:68`, assignment `:82`) and never calls it.

`Jobs.applyEvent` handles all three (`jobs.ts:284-308`), and `refreshOne` (`:316-330`) exists to
service `job.toggled` and `job.updated`. None of that code can ever run. In practice: an edit,
a toggle or a delete made in one browser tab is invisible in another until a manual Refresh, even
though the screen advertises itself as Live.

`discovery/frontend.md:773-777` records the type-union mismatch; the dead publisher behind it is
recorded here.

### 12.7 Run and Skip are offered on jobs the server will refuse

`jobs.html:230-235` disables both only on `isInFlight(job)` (and Skip additionally on a missing
scheduler). Neither checks `jobStatus`. The server requires Active
(`SourceJobServiceImpl.java:344, 363`) and returns **"SourceJob not found with jobId."** -- which
tells the user the job does not exist when the truth is that it is switched off.

The old screen disabled both on `jobStatus === 'Inactive'` (`source-job.component.ts:205, 214`).

### 12.8 A failed sub-fetch is drawn as an absent thing

Two places in the expanded panel:

- `loadPayload`'s error handler writes `''` into the cache (`jobs.ts:370`), and `''` is exactly the
  value the template reads as "This task has no payload configured." (`jobs.html:371-372`).
- `loadRuns`'s error handler writes `[]` (`jobs.ts:419`), which the template reads as "This job has
  not completed a run yet." (`jobs.html:402-405`).

A network failure and an empty result are indistinguishable. The rest of the app draws that
distinction through `TableShell`.

### 12.9 Pre-existing platform issues that this feature sits on

Recorded in `discovery/database.md` §8; repeated here because they bite jobs specifically and
whoever works on this feature will meet them.

- **`source_job` and `scheduler` have no creation path outside development.** Both are Hibernate-
  owned; Liquibase creates only six tables, and `ddl-auto` is off on stage and prod
  (`database.md:550-556`).
- **`SourceJobRepository.statusChangeSourceJobLinkWithSourceTaskTypeId` (`:57-60`) writes
  `UPPER(?2)`**, re-creating the all-caps `job_status` corruption that
  `V16__fix_source_job_status_casing.sql` was written to repair. Its two callers are in
  `SettingServiceImpl` (task-type save and delete), so editing a task type today corrupts the status
  of every job linked to it. Corrupted rows vanish from `listSourceJob` -- whose JPQL matches
  `Active`/`Inactive` case-sensitively -- and from `findDueSchedulers`, which compares
  `job_status = 'Active'` literally. **A job can disappear from this screen, and stop running,
  because someone edited a task type.**
- `V15__scheduler_recurrence_rules.sql`'s `RENAME COLUMN recurrence TO interval_value` is not
  idempotent against a Hibernate-built `scheduler`, which already has `interval_value`.

### 12.10 Smaller things

| # | Issue | Evidence |
|---|---|---|
| a | `runSourceJob` and `skipNextSourceJob` refuse `Queue` and `Running` but **not `Start`** -- a run that has been dispatched can be re-run from the API. The client blocks it (`IN_FLIGHT` includes `start`, `stalled.ts:14`), so this is API-only | `SourceJobServiceImpl.java:347-350, 366-368` |
| b | The list is ordered `jobId` ascending and never reversed, so a newly created job lands on the last page. The old screen reversed it | `SourceJobRepository.java:45` + `jobs.ts:340`; old `source-job.component.ts:492` |
| c | `fetchSourceJobDetailWithSourceJobId` does not call `UserNameResolver.attachNames`, so a row added to the list by `refreshOne` -- a clone, or a job created elsewhere -- shows `—` in Created by and Updated by until a full reload | `SourceJobServiceImpl.java:443-453` vs `:495` |
| d | The new id after a create is recovered by regexing `/jobId (\d+)/` out of the response *message*. Any change to the server's wording silently breaks the clone flow | `jobs.ts:471`; message built at `SourceJobServiceImpl.java:178` |
| e | `MineFilter` accepts a `hidden` count and `jobs.ts` never sets it, so "Only mine" always reads "(0 hidden)" on this screen | `shared/ui/mine-filter.ts:30-32`, `jobs.ts:782-788` |
| f | `Jobs.selectable` tests `job.jobStatus !== 'Delete'` on a list the server never puts deleted rows into | `jobs.ts:216`, `SourceJobServiceImpl.java:484-485` |
| g | Client and server disagree about when a run is stranded: 30 minutes in `stalled.ts:17`, 6 hours in `ProducerBulkEngine.java:88`. Both are defensible; the banner will warn about runs the server is still waiting on | |
| h | `summary()` compares the interval against the **string** `'1'` (`job-edit.ts:158`), but `<input type="number">` binds through Angular's `NumberValueAccessor`, which yields a number once the user edits the field. After any edit the preview reads "Every 1 days" | `job-edit.ts:158`, `job-edit.html:78-79` |
| i | The expanded row's "View in bucket" uses `outputFolder` only; the old panel fell back to `inputFolder`, so an input-only task now links to the bucket root | `jobs.ts:762-766` vs `linked-task-panel.component.html:45-49` |
| j | `updateSourceJob` sends `daysOfWeek` and `dayOfMonth` regardless of the chosen frequency, leaving stale day rules on a schedule switched from Weekly to Daily | `job-edit.ts:211-215` |

---

## 13. Missing functionality

Absent from the new app. Each says what it would take.

**The table/card view toggle.** `shared/ui/view-toggle.ts` exists and eleven screens use it,
including `tasks` and `ai/agents` -- the other two screens that had the toggle in the old app.
`features/jobs/jobs.ts` does not import it. Restoring it is a card template plus `ViewToggle` bound
to a storage key; the card layout can follow `tasks`. Half a day. Whether it is wanted at all is
open question Q1.

**The `tabActive` gate on run history.** The server still computes it
(`SourceJobServiceImpl.java:500`) and sends it on every list row; nothing in `scheduler1/next/src`
reads it. Adding it is one disabled attribute and one tooltip in `jobs.html:238`. An hour.

**Filtering by Active / Inactive.** The list has an execution filter and a run-status filter; it has
no filter over the field the State column shows. One `signal`, one `<select>`, one clause in
`filtered()`. An hour.

**Field-aware search.** The old `SearchFilterPipe` (`_helpers/search-filter.ts:40-102`) supported
`field.path:term`, quoted phrases and `-negation` across the whole object graph. The new search
covers three fields with a plain `includes`. Porting the tokenizer as a shared helper would benefit
every list screen, not just this one -- which is also the argument for not doing it inside this
feature.

**The read-only task facts on the editor.** Service, topic, partitions, home page, pipeline and the
payload with a copy button (`job.component.html:183-249`). Everything needed is already on the
`listSourceTask` response the editor loads, except the payload, which needs
`fetchSourceTaskWithSourceTaskId` on selection -- the same call `jobs.ts:362` already makes. Half a
day.

**Reassigning a job.** `assigned_user_id` decides who receives the run emails and whose "My
activity" the job appears in, and `validateAssignee` (`:513-526`) is written and unused: **neither
frontend has ever sent `assignedUserId`** (`grep -rn assignedUserId scheduler1/src scheduler1/next/src`
returns nothing). A job is permanently owned by whoever created it. The new list *displays*
"Assigned to" in the expanded panel and the notification sentence names the assignee -- so the
console shows a field it gives no way to change. A user picker on the edit form and one field in
the payload. A day, plus the question of who may reassign (Q4).

**Any test of the two screens.** `jobs.ts` is 789 lines and `job-edit.ts` is 239, and neither has a
spec; the four helper modules do. Every defect in section 12 except 12.9 would be caught by a test
somebody could have written: 12.1 by a component test asserting the payload for an
Auto→Manual save, 12.2 and 12.3 by a service test on `addSourceJob`/`updateSourceJob`, 12.4 by one
assertion that the emitted `daysOfWeek` parses under `ProcessTimeUtil`, 12.5 by loading a
priority-99 fixture. There is also no E2E coverage: `src/test/java/process/e2e/` has eight files and
none mentions `sourceJob`.
