# Grooming -- Source Tasks

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

Migration status: **partial**. Section 2 says exactly which half crossed and which did not; sections
12 and 13 carry the evidence.

---

## 1. Purpose

A source task is the answer to "what does this job actually do, and where does it read and write?"

A job is a schedule. It says *when*. The task it points at says *what*: which consumer picks the
work up (through the task type, which carries the Kafka topic), which pipeline script handles it,
and what configuration that script receives. The configuration is an XML document. Somebody who
knows the pipeline writes it as a list of tag rows -- `bucket` = `etl-bucket`, `input_folder` =
`incoming/2026`, `search_term` nested under `params` -- and the tags become the document the worker
is handed.

Three things follow from that, and they are the reason this screen exists rather than a text box:

- **A task is shared.** Many jobs point at one task. Changing a task changes every one of them, and
  deleting a task would stop all of them at once, so both operations have to say what they are
  about to affect.
- **Tag names are load-bearing and invisible when wrong.** `bucket` is read by the pipeline;
  `bukcet` is not, and nothing complains until the run fails hours later. The editor highlights the
  four keys the pipeline actually looks for and strips invisible whitespace out of the values.
- **The XML is generated, not typed.** The server owns the rule that turns tag rows into a
  document, so both applications ask it (`setting.json/xmlCreateChecker`) rather than assembling
  the string in the browser.

The new application adds one idea on top: a **task form**. Instead of every operator needing to
know that pipeline `F768926` wants a `search_term` under `params`, an administrator describes that
once under Settings, and the task editor then shows labelled fields. The form authors the tag rows;
it never stores a payload of its own, so a task filled in through a form and one typed by hand are
the same task (`process/src/main/resources/db/changelog/changelog-sets/V19.0-task-form-builder/V19__task_form_builder.sql:1-8`).

---

## 2. Existing behaviour

### 2.1 The migration boundary, in one table

This is the whole point of a `partial` document. Everything below is cited in the sections that
follow.

| Capability | Old app | New app | Crossed? |
|---|---|---|---|
| List tasks, table view | `_component/source-task/source-task.component.html:120-356` | `features/tasks/tasks.html:130-302` | yes |
| List tasks, card view | same file, `:52-118` | same file, `:43-128` | yes |
| Expand a row for the payload | `:280-291` | `:225-243` | yes |
| Expand a row for linked jobs | `:293-340` | `:244-295` | yes, and richer (last run, run status) |
| Clone a task | `source-task.component.ts:236-278` | `tasks.ts:140-180` | yes |
| Delete a task | `:280-309` | `tasks.ts:200-238` | yes, and now refuses when jobs are bound |
| Client-side paging 50/100/150/200 | `:50-52, 89-96` | `tasks.ts:85-89` + `shared/ui/pager.ts:4` | yes, but see 12.1 |
| Refresh | `:128-130` | `tasks.ts:242-257` | yes |
| Search box | `:31, 80-87` | `tasks.ts:74-83` | **narrowed** -- see 12.6 |
| **Status filter (All/Active/Inactive)** | `:33-34, 107-110`; markup `source-task.component.html:19-29` | absent from `tasks.html:30-41` | **no** |
| **Per-row JSON download** | `:311-315`; markup `:100-104, 200-204` | no download/export method in `tasks.ts` | **no** |
| **"View in Bucket" deep link** | `source-task.component.html:268-278` | `tasks.html:169-178` renders the bucket as text | **no** |
| **Home page / Group on the list** | `source-task.component.html:155-169, 243-254` | no column, no card row | **no** |
| **Topic partitions** | `:230-236` via `parseTopicPartition` | `tasks.ts:260-264` extracts the topic only | **no** |
| **Task-type detail modal from the type pill** | `:149-153` (`viewSourceTaskType`) | plain text, `tasks.html:159-161` | **no** |
| Editor: name, type, pipeline, group, home page | `task/task.component.html:15-98` | `edit/task-edit.html:18-82` | yes |
| Editor: tag rows with add/insert/remove | `task.component.html:143-198` | **removed 2026-09-07** -- see 12.7 | **no, deliberately** |
| Editor: trim invisible whitespace | `task.component.ts:126-154` | **removed 2026-09-07** along with the tag table it belonged to | **no, deliberately** |
| Editor: storage-tag highlighting + bucket help | `task.component.ts:122-165`; markup `:119-141` | **removed 2026-09-07** along with the tag table it belonged to | **no, deliberately** |
| Editor: XML from the tags | `task.component.ts:314-325` (writes straight into the payload) | **changed 2026-09-07**: generated automatically on save (`task-edit.ts:356-391`), not from a "Show the XML"/"Use as payload" click that no longer exists | yes, and no longer a manual step -- see 12.7 |
| **Editor: tenant picker for PLATFORM_ADMIN** | `task.component.ts:91, 98-101, 104-116, 290`; markup `:39-51` | nothing named `tenant` in `task-edit.ts` or `task-edit.html` | **no -- and it is a blocker, see 12.2** |
| **Editor: task payload required** | `task.component.ts:255, 284` (`Validators.required`) | **fixed 2026-09-07**: `task-edit.ts:73` (`Validators.required`), toggled off while a pipeline form is generating it instead (`:210-227`) | **yes now -- see 12.3** |
| **Editor: only Active task types offered** | `task.component.ts:179` | `task-edit.ts:85` sets them unfiltered | **no -- see 12.4** |
| **Editor: tag keys rejected if they contain spaces** | `task.component.ts:38-43, 299-300, 308-309` | no validator on `task-edit.ts:161-167` | **no -- see 12.5** |
| Editor: status dropdown | `task.component.html:78-85`, `_models/object.ts:121-134` -- includes **Delete** | `task-edit.html:75-81` -- Active/Inactive only | narrowed, deliberately (see 8.4) |
| Editor: "Clear" button | `task.component.html:210-212` | absent | **no** (and the old one was broken -- 12.11) |
| Pipeline Forms (`settings/pipeline-forms`, renamed from `settings/forms`) | does not exist | `features/settings/forms/` | **new** -- was inert (12.7), **fixed 2026-09-07**: see 12.7 |

### 2.2 Old application -- the list (`taskList`)

Route `taskList` → `SourceTaskComponent`, guarded by `AuthGuard` only
(`scheduler1/src/app/app.routing.ts:57-61`). There is no role check on the route, so a
`TENANT_USER` reaches `addTask` and `editTask/:id` too (`:71-80`) and only discovers the refusal
when the server answers.

On init it reads a persisted view mode from `localStorage` under `sourceTaskViewMode` and issues one
request with `page: 1, limit: 5000, order: 'DESC', columnName: 'st.task_detail_id'`
(`source-task.component.ts:65-78`). Everything after that is client-side: a deep search through
`SearchFilterPipe`, a status filter, and 50/100/150/200 paging (`:80-122`).

The service is a singleton that keeps `searchText` on itself and re-sends it when a later caller
omits one (`_services/source.task.service.ts:12, 28-31`), so a search typed on one screen can
silently filter another.

Expanding a row shows the task detail block -- type, topic and partitions, pipeline, home page as a
clickable link, group, status, a "View in Bucket" button that deep-links into
`/objectBrowser` with `{ bucket, prefix }`, and the payload with a copy button
(`source-task.component.html:219-291`) -- and then lazily fetches the linked jobs, cached per task
(`source-task.component.ts:184-207`).

Clone reads the task back in full and re-POSTs a reshaped subset -- `taskName`, task type id,
`taskPayload`, `taskStatus`, `homePageId`, `pipelineId`, `xmlTagsInfo`
(`:236-278`). It does not copy `groupId`, and it does not rename, so the copy carries the original's
name.

Delete opens a Bootstrap modal whose body says "On press 'Yes' all the source job will delete state
and will not run" (`source-task.component.html:386-388`) and then calls `deleteSourceTask`
(`source-task.component.ts:280-309`). That sentence has not been true since the server started
refusing a task that still has jobs (`SourceTaskServiceImpl.java:269-275`).

### 2.3 Old application -- the editor (`addTask` / `editTask/:taskDetailId`)

One component for both (`_component/source-task/task/task.component.ts`). `ngOnInit` reads the
route param, calls `appSetting()`, and branches: edit loads the task, create builds a blank form
and -- if the signed-in role is `PLATFORM_ADMIN` -- loads the tenant list (`:85-116`).

`appSetting()` filters the task types to `status == 'Active'` (`:179`) and then chains two
`fetchSubLookupByParentId` calls, one per parent lookup, for `PIPELINE_HOME_PAGES` and
`TASK_GROUPS` (`:191-224`). Each of those two dropdowns binds the option's **`lookupId`** as its
value and shows its **`lookupType`** as the label (`task.component.html:33, 94`).

**Pipeline is no longer one of the three** (fixed 2026-09-07, see 12.7). `PIPELINE_IDS` was
removed as a lookup family entirely; `loadPipelineForms()` (`task.component.ts:110-121`) instead
calls the new `TaskFormService.listPipelines()` (`_services/task-form.service.ts`), and the
Pipeline `<select>` binds `[value]="form.pipelineId"` -- the pipeline's own id string, the same
one `task_form.pipeline_id` is keyed on -- showing `form.formName` as the label
(`task.component.html:71-77`).

The create form seeds ten blank tag rows (`:291`) and makes `tenantId` required for a platform
admin (`:290`). The **edit** form group is built separately (`:251-262`) and has **no `tenantId`
control at all**, which is correct -- a task's tenant is fixed at creation -- and the template hides
the picker in edit mode anyway (`task.component.html:39`).

"Show Xml Output" posts the tag rows to `xmlCreateChecker` and writes the result straight into the
payload textarea (`:314-325`). The button is disabled while any tag row is invalid
(`task.component.html:206`), which is what the whitespace validator is wired to.

### 2.4 New application -- the list (`tasks`)

Route `tasks` is deliberately ungated: `listSourceTask` is `TENANT_USER`, and a job points at a
task, so reading the list is part of reading the console
(`scheduler1/next/src/app/app.routes.ts:118-123`). Every write control inside the page is gated on
`auth.canManageTasks()` (`tasks.html:16-21, 59, 187`), which resolves to `hasAtLeast('TENANT_ADMIN')`
(`core/auth/auth.service.ts:87`).

`load()` posts to `listSourceTask` with an empty body and **no query parameters at all**
(`tasks.ts:242-257`). The consequences are in 12.1.

The table carries ten columns, two of which the old app never had -- **Created by** and
**Updated by** (`tasks.html:139-140`), fed by `UserNameResolver.attachToDtos` on the server
(`SourceTaskServiceImpl.java:372-373`). There is an "Only mine" toggle matching on `createdBy`
identity rather than display text (`tasks.ts:272-278`, `shared/ui/mine-filter.ts:47-49`).

Delete is genuinely better. `inUse()` disables the menu item when the row reports linked jobs, the
tooltip names the number, and `remove()` explains the refusal rather than offering a confirm for
something the server will reject (`tasks.ts:196-217`). The confirm dialog then states plainly that
no jobs are bound.

Clone renames to `"<name> (copy)"` and asks for `taskStatus: 'Inactive'` (`tasks.ts:151-160`). The
server ignores that -- see 12.8. Like the old clone it drops nothing except what it forgets to copy;
here it copies `groupId`, which the old one did not.

### 2.5 New application -- the editor (`tasks/new`, `tasks/:taskDetailId/edit`)

Both routes carry `data: { minRole: 'TENANT_ADMIN' }` and `canActivate: [roleGuard]`
(`app.routes.ts:104-117`), with a comment explaining why: the editor is nothing but writes, and
being told "no" only at Save would lose the work.

`ngOnInit` fetches `appSetting`, then `forkJoin`s one `fetchSubLookupByParentId` per parent lookup
in `['TASK_GROUPS', 'PIPELINE_HOME_PAGES']` -- a real improvement on the old nested-subscribe
chain -- and each failure degrades to an empty option list rather than killing the others
(`task-edit.ts:88-118`, `LOOKUP_TYPES` at `:20`).

**Pipeline is fetched separately and is not a lookup** (fixed 2026-09-07, see 12.7): a second
request, `GET taskForm.json/listPipelines`, fills a `pipelines` signal with every `TaskForm` the
caller may see (`:120-126`), and the Pipeline `<select>` binds `[value]="option.pipelineId"`
(`task-edit.html:38-46`) -- the pipeline's own id string, not a lookup row id.

**There is no more tag table** (removed 2026-09-07, see 12.7): no manual rows, no "Show the XML
these tags make"/Copy/"Use as payload" preview, no storage-tag highlighting, no bucket-help panel.
When a pipeline form is driving the task, `save()` posts the tags the form authored to
`xmlCreateChecker` itself and uses the result as the payload (`task-edit.ts:319-391`) -- generating
what used to take a manual click, because there is no longer a click to make it with. When no form
applies, `taskPayload` reverts to a plain required textarea (`task-edit.html:161-174`), the same
hand-written-XML escape hatch the old app always offered, just without a tag table beside it.

**Pipeline Forms, integrated into the task itself (fixed and merged 2026-09-07, see 12.7).** When
the chosen pipeline has a form, `formForPipeline` returns it, the component builds one control per
field, seeds each from the task's existing tag rows (existing value wins over the field's
default), and writes every answer back into the tag rows on each keystroke
(`task-edit.ts:187-227, 241-254, 275-312`). There is no longer a raw tag table to collapse it into
view of, or a manual preview/payload button downstream of it: `save()` itself turns the form's
answers into the payload (12.7). The fields on this screen *are* the configuration; nothing else
on it configures a pipeline.

### 2.6 New application -- Pipeline Forms (`settings/pipeline-forms`, renamed 2026-09-07 from `settings/forms`)

`TENANT_ADMIN`, reached from the nav under Configuration as "Pipeline Forms"
(`features/shell/shell.ts:118-119`). The old path redirects (`app.routes.ts:183`).

Four stat tiles (now led by **Pipelines**, not Forms -- `task-forms.html:31-40`), table and card
views, search, "Only mine", and an **`xwide`** dialog (widened 2026-09-07 from `wide`,
`form-dialog.ts:56-62`) that edits the form and its fields -- add, remove, reorder, per-field type,
nesting parent chosen from the other fields' tag keys, default, help text, select choices,
required -- laid out as a responsive two-column grid of field cards past that width
(`task-form-dialog.ts:95`), plus a live payload preview (`task-forms.html:20-189`,
`task-form-dialog.ts:47-207`).

The dialog mirrors the server's validation rules before sending, using the server's own wording
(`task-form-dialog.ts:284-302` against `TaskFormServiceImpl.java:181-208`). **Pipeline is now
plain free text with no suggestions** (changed 2026-09-07): the old datalist harvested pipeline
ids already in use on real tasks, which became circular once Source Task started reading its
pipeline list from here instead of the other way around -- see 12.7.

### 2.7 Backend

`SourceTaskRestApi` is class-level `TENANT_ADMIN` (`api/SourceTaskRestApi.java:28`) with four reads
lowered to `TENANT_USER` by a method annotation (`:69, 88, 108, 120`). Because `@PreAuthorize` is not
repeatable, each of those **replaces** the class value rather than adding to it -- which is the
intent here, and a role hierarchy makes it safe: `MethodSecurityConfig.java:29` declares
`PLATFORM_ADMIN > TENANT_ADMIN > TENANT_USER`, and the JWT filter grants exactly one authority
(`security/JwtAuthenticationFilter.java:43-45`).

`TaskFormRestApi` is the mirror image: class-level `TENANT_ADMIN` with **two** methods lowered to
`TENANT_USER` -- `formForPipeline`, and (added 2026-09-07) `listPipelines`, the same rows
`listForms` returns, exposed at the lower role because Source Task's own screen carries no admin
gate and now needs the pipeline catalogue to populate its Pipeline picker -- while
`saveForm`/`deleteForm` restate `TENANT_ADMIN` redundantly
(`api/TaskFormRestApi.java:32, 61-70, 72, 83, 94`).

`SourceTaskServiceImpl` decides tenancy in three different ways depending on the path:

- **Writes and single reads** call `tenantFilterHelper.enableIfNeeded` and then `findById`
  (`:209-210, 254-255, 440-441`). The Hibernate filter does not apply to `findById`, so the call is
  decorative; the real check is `isOwnedByCaller` on the line after (`:113-118`).
- **The list and the linked-jobs read** go through hand-built SQL with
  `QueryService.tenantClause` appended (`QueryService.java:92, 137, 212-217`).
- **Exports and the task-type cross-reference** branch on `TenantContext.isPlatformAdmin()` and call
  a different repository method (`:473-481, 484-486`).

Linking a task to a task type is checked separately, because a type carries the Kafka topic and
connection profile the job later publishes with: `isSourceTaskTypeVisibleToCaller` allows the
caller's own types and platform-owned ones, and refuses another tenant's with the same wording used
for a missing id so the response is not an id oracle (`:126-131, 155-158, 205-208`). This is covered
by tests (`src/test/java/process/model/service/impl/SourceTaskServiceImplTenantIsolationTest.java`).

`TaskFormServiceImpl` does not use the Hibernate filter at all. `listForms` reads everything and
filters in memory (`:51-56`); `formForPipeline` and the duplicate check pass the tenant id into a
JPQL query whose `f.tenantId = ?2 or f.tenantId is null` clause does the scoping
(`TaskFormRepository.java:27-30`); writes go through `isOwnedByCaller`, which refuses a shared
(`tenant_id is null`) form to anyone but a platform admin (`:210-215`).

---

## 3. Expected behaviour

Where this differs from today, it is marked **[gap]**.

1. A signed-in user of any role can list the tenant's source tasks and open a row to see its
   payload, its storage location and the jobs bound to it. **[gap: the list returns at most ten
   rows -- 12.1]**
2. The list shows every stored attribute an operator needs to identify a task without opening the
   editor: id, name, type, topic and partitions, pipeline, group, home page, storage path, author,
   editor and status. **[gap: group, home page and partitions are on no screen in the new app]**
3. The list can be narrowed by status as well as by text, and the text search reaches the payload.
   **[gap: neither is true in the new app]**
4. Storage on a row is a link into the object browser at that bucket and prefix. **[gap: it is
   plain text]**
5. A `TENANT_ADMIN` creates, edits, clones and deletes tasks in their own tenant.
6. A `PLATFORM_ADMIN` does the same in any tenant, naming the tenant when creating, because a
   platform admin belongs to none. **[gap: creation is impossible from the new UI -- 12.2]**
7. A `TENANT_USER` can read and can do none of the above, and is told so before doing any work
   rather than after.
8. Saving a task requires a name, a task type that is visible to the caller and Active, and a
   payload. Every one of those is enforced on the server, and the client refuses first so nothing is
   lost. **[gap: the payload requirement and the Active-type filter are client-side only in the old
   app and absent in the new one -- 12.3, 12.4]**
9. A tag key that cannot be an XML element name is refused where it is typed. **[gap: the old app
   refused spaces on the client only; the new app refuses nothing, and nothing on the server refuses
   it either -- 12.5]**
10. Deleting a task that jobs still use is refused, and the message names how many and what to do.
    Deleting an unused one marks it deleted and it leaves the list.
11. A task form, once defined for a pipeline, drives the editor for every task on that pipeline.
    **[fixed 2026-09-07, was: it never matched, because the two sides keyed on different
    representations of `pipelineId` -- see 12.7]**
12. A form scoped to all tenants can be edited only by a platform admin; the UI does not offer an
    action the server will refuse. **[gap: it does -- 12.9]**
13. Cloning produces an inactive copy, so a half-configured duplicate cannot be picked up by a job
    before somebody has looked at it. **[gap: the server forces every new task Active -- 12.8]**

---

## 4. Frontend requirements

### 4.1 Routes

| Route | Component | Guard | Purpose |
|---|---|---|---|
| `tasks` | `features/tasks/tasks.ts` `Tasks` | `authGuard` (shell) only | The list. Reads are `TENANT_USER`; writes gated in-template. |
| `tasks/new` | `features/tasks/edit/task-edit.ts` `TaskEdit` | `roleGuard`, `minRole: TENANT_ADMIN` | Create. |
| `tasks/:taskDetailId/edit` | same component | `roleGuard`, `minRole: TENANT_ADMIN` | Edit. `taskDetailId` bound as a component input. |
| `settings/pipeline-forms` (renamed 2026-09-07 from `settings/forms`, which now redirects) | `features/settings/forms/task-forms.ts` `TaskForms` | `roleGuard`, `minRole: TENANT_ADMIN` | Pipeline definitions -- a pipeline no longer exists any other way (12.7). |
| `tasks/bulk` | `features/bulk/bulk-transfer.ts` | `roleGuard`, `minRole: TENANT_ADMIN` | Belongs to `bulk-transfer`; listed because the list page links to it. |

Notification rows written before the rewrite carry `/taskList`; the redirect map in
`features/notifications/notification-links.ts:12` rewrites it to `/tasks`, and that map is the one
tested part of the notification feature. Any route change here has to be represented in it.

### 4.2 The list page

**Header.** Title, one-sentence subtitle, Refresh, and -- only when `auth.canManageTasks()` -- Bulk
import and New task.

**Toolbar (inside `app-table-shell`).** View toggle persisted under `etl.view.tasks`; a search box;
"Only mine"; a Clear button that appears once a filter is set. **Add:** a status select (All /
Active / Inactive), and let the search reach `groupId`, `bucket` and `taskPayload`.

**Table.** Expander, Task (name + `#id`), Type, Topic, Pipeline, Storage, Created by, Updated by,
Status, actions. **Add:** Group and Home page, and the partitions beside the topic. Keep the
expander cell and the expanded row's `colspan` summing to the header count -- `tasks.html:222-224`
already carries a comment about this, because it broke once.

**Cards.** Icon, name, `#id`, status, actions menu; a definition list of Type / Topic / Pipeline /
Storage; a footer pill with the linked-job count or "No job uses this yet". **Add:** Group and Home
page.

**Expanded row.** Payload with a copy button that flips to a tick for 1.5s, and the linked-jobs
table (Job, Type, Last run, Run status, State) capped at `max-h-64` with its own scroll. **Add:** the
task-detail block the old app had -- type id, topic + partitions, pipeline, home page as a link,
group, and the bucket path as a link into `/objects` with `{ bucket, prefix }`.

**Row actions** (`TENANT_ADMIN` only): Edit, Duplicate, Delete. **Add:** Download JSON, which needs
no permission at all since the data is already on the client.

**States.** `app-table-shell` supplies all four -- loading spinner, error with the message and a
"Try again" button that re-runs `load()`, empty with an icon and a message that distinguishes "no
tasks yet" from "no tasks match your search", and the populated table
(`shared/ui/data-table.ts:41-60`). This is the single largest improvement over the old app, where a
failed load and an empty result were indistinguishable.

**Pagination.** `app-pagination` bound to `pager`, sizes 50/100/150/200 (`shared/ui/pager.ts:4`).
Once the server is asked for more than ten rows (12.1) this becomes meaningful; it should also
surface the server's true total rather than `tasks().length`.

### 4.3 The editor

Sections (**changed 2026-09-07** -- see 12.7): **Basics** (task name*, task type*, pipeline, group,
home page, status*), then either the **pipeline form** (when the chosen pipeline has one) or a
plain **Task payload** textarea (when it does not), then Save / Cancel. There is no longer a
**Configuration tags** section between them -- a pipeline's payload is configured by its form or
not at all; the two no longer coexist on screen.

- Every field is wrapped in `app-field`, which owns the label, the required asterisk, the hint, the
  error text and the invalid styling, and withholds the message until the control is touched or the
  form submitted (`shared/ui/field.ts:14-70`).
- **Add a Tenant select**, required, visible only when `auth.isPlatformAdmin()` and only in create
  mode, populated from `tenant.json/listTenants` -- mirroring `task.component.html:39-51`. Still
  open -- unaffected by the tag-table removal.
- ~~Mark Task payload required, or generate it from the tags on save.~~ **Done 2026-09-07**:
  `taskPayload` carries `Validators.required` (`task-edit.ts:73`) and is only ever shown, and only
  ever needs filling in by hand, when no pipeline form is driving the task; a form-driven task
  generates it in `save()` instead (`:319-391`), closing this gap for both paths at once.
- **Filter the task-type options to `status === 'Active'`.** Still open.
- ~~Reject a tag key or parent containing whitespace at the row, and disable the XML preview while
  any row is invalid.~~ **Moot for the removed table** -- there is no row to type one into any
  more. The underlying rule (an XML tag name cannot contain whitespace) still has no server-side
  check either, and now matters more, not less: a Pipeline Form author who types a bad `tagKey`
  when defining a field (`task-form-dialog.ts`) will not discover it until a task on that pipeline
  saves and 500s. See the platform-configuration documents for that surface, and 12.5 here for the
  original finding.

The pipeline-form block renders one `app-field` per field, switching on `fieldType` across
textarea / select / checkbox / number / date / url / text, and calls `syncFormToTags()` on every
change. Textareas span both grid columns. It is the **only** configuration surface when a form
exists -- there is no tag table beneath it any more to fall back to, and no preview button, because
`save()` is what turns its answers into the payload now.

### 4.4 Pipeline Forms page

Header with Refresh and **New pipeline** (renamed 2026-09-07 from "New form", matching the page's
elevated role -- see 12.7). Three stat tiles, **Pipelines** first (renamed 2026-09-07 from "Forms"
first, since a pipeline is now the primary noun): Pipelines, Forms, Fields. Table and card views
over the same rows, search across name / pipeline / description, "Only mine", and per row: Form
(name + description), Pipeline, Fields (`n (m required)`), Scope, Created by, Updated by, Status,
and a menu with Edit / Duplicate / Delete.

**Add:** hide or disable Edit, Duplicate and Delete on a shared (`Scope = All tenants`) form for
anyone who is not a platform admin, because the server refuses all three (12.9). **Add:** pagination
-- this page renders `filtered()` in full (`task-forms.html:56, 141`).

The dialog is `app-form-dialog` at **`size="xwide"`** (widened 2026-09-07 from `wide`, a new size
added to `form-dialog.ts` for a builder whose win is fitting two field cards across rather than
more form-grid columns): pipeline id and form name side by side, description, then a **two-column
grid** of field cards (past the `xl` breakpoint; one column below it) with move-up / move-down /
remove, and a live payload preview. **Pipeline is now plain free text with no datalist** (changed
2026-09-07 -- the old "pipelines already in use on tasks" suggestion list became circular once
Source Task started reading its pipeline list from here instead; see 12.7). Validation messages
are the server's own strings, produced client-side first (`task-form-dialog.ts:284-302`). **Fix**
the preview so it models the same rule the server's XML builder uses (12.10) -- unchanged by the
above and still open.

### 4.5 Dark and light mode, responsiveness

The new app is token-based throughout: every colour on these screens is a `var(--…)` or a semantic
utility (`bg-sunken`, `bg-code`, `border-subtle`, `text-crit-500`, `icon-muted`), so both themes come
from `core/theme.service.ts` and `src/styles.css` with nothing per-screen to maintain. Anything added
here must use the same tokens rather than a literal colour.

Responsiveness is already right on both screens and must stay so: the card grids are
`sm:grid-cols-2 xl:grid-cols-3` (`tasks.html:44`), the editor's `.form-grid` is container-query
driven, wide content scrolls inside its own container (`overflow-x-auto` on the tag table,
`task-edit.html:190`), and long values are `truncate` with a `title`. The tables themselves are the
weak spot: at ten columns `tasks.html` will need a horizontal scroll container on a narrow viewport,
and does not have one.

The old app has no dark mode at all -- there is no theme service and no dark styling in
`scheduler1/src`.

---

## 5. Backend requirements

### 5.1 Endpoints

Role is the **effective** minimum after the role hierarchy in `config/MethodSecurityConfig.java:29`.

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/sourceTask.json/listSourceTask` | TENANT_USER (`SourceTaskRestApi.java:69`) | Paged, sorted, date-filterable list. Search text in the body, paging in query params. Returns the lookup **labels** for home page / pipeline / group, plus derived `bucket`/`inputFolder`/`outputFolder` and a live linked-job count. |
| GET | `/sourceTask.json/fetchSourceTaskWithSourceTaskId` | TENANT_USER (`:120`) | One task with its tag rows, sorted by `taskPayloadId`. Returns the **raw stored ids** for home page / pipeline / group. |
| POST | `/sourceTask.json/fetchAllLinkJobsWithSourceTaskId` | TENANT_USER (`:88`) | The jobs bound to one task. Scoped on `sj.tenant_id`, not on the task's tenant. |
| GET | `/sourceTask.json/fetchAllLinkSourceTaskWithSourceTaskTypeId` | TENANT_USER (`:108`) | Tasks of one task type. Consumed by `settings/task-types`, not by this feature. |
| POST | `/sourceTask.json/addSourceTask` | TENANT_ADMIN (class, `:28`) | Creates. Requires name, payload and a visible Active task type; a platform admin must also send `tenantId`. Forces `taskStatus = Active`. |
| PUT | `/sourceTask.json/updateSourceTask` | TENANT_ADMIN | Updates. Never changes `tenantId`. Replaces the tag rows wholesale when `xmlTagsInfo` is present. |
| PUT | `/sourceTask.json/deleteSourceTask` | TENANT_ADMIN | Soft delete. Refuses while any non-deleted job points at the task. Body-carrying PUT. |
| GET | `/sourceTask.json/downloadListSourceTask` | TENANT_ADMIN | xlsx export. Owned by `bulk-transfer`. |
| GET | `/sourceTask.json/downloadSourceTaskTemplate` | TENANT_ADMIN | xlsx template. Owned by `bulk-transfer`. |
| POST | `/sourceTask.json/uploadSourceTask` | TENANT_ADMIN | Bulk import. Owned by `bulk-transfer`. |
| GET | `/taskForm.json/listForms` | TENANT_ADMIN (class, `TaskFormRestApi.java:32`) | Every non-deleted definition the caller may see. |
| GET | `/taskForm.json/listPipelines` | TENANT_USER (`:61`, added 2026-09-07) | The same rows as `listForms`, at a role Source Task's own (admin-less) screen actually has -- the pipeline catalogue for its Pipeline picker. |
| GET | `/taskForm.json/formForPipeline` | TENANT_USER (`:72`) | The one form for a pipeline; tenant row wins over shared. Absence is a `SUCCESS` with null data, not an error. |
| POST | `/taskForm.json/saveForm` | TENANT_ADMIN (`:83`) | Creates or updates. Fields replaced wholesale. |
| DELETE | `/taskForm.json/deleteForm` | TENANT_ADMIN (`:94`) | Soft delete; frees the pipeline's unique slot. |
| GET | `/setting.json/appSetting` | TENANT_ADMIN (class, `SettingRestApi.java:24`) | Parent lookups + task types with status and topic. |
| GET | `/setting.json/fetchSubLookupByParentId` | TENANT_ADMIN | The options under one parent lookup. |
| POST | `/setting.json/xmlCreateChecker` | TENANT_ADMIN | Renders tag rows as an XML document. **Returns the document in `message`, not `data`.** |

The three `setting.json` endpoints are `TENANT_ADMIN` because of the class annotation, which is why
the editor route is `TENANT_ADMIN` and not merely gated on its controls.

### 5.2 Services

| Class | Responsibility |
|---|---|
| `model/service/impl/SourceTaskServiceImpl.java` (647 lines) | All task CRUD, the list, the linked-jobs read, task-type linkage, xlsx import/export. Owns `resolveTenantIdForCreate` (`:91-104`), `applyDerivedLocation` (`:106-111`), `isOwnedByCaller` (`:113-118`) and `isSourceTaskTypeVisibleToCaller` (`:126-131`). |
| `model/service/impl/QueryService.java` | Hand-built SQL for the list and linked-jobs reads, with `tenantClause` (`:212-217`), a sort-column allow-list and `sqlEscape` on search terms. |
| `model/service/impl/TaskFormServiceImpl.java` (226 lines) | Form definitions. `validate` is package-private and static so the rules can be tested without a database (`:181-208`). Writes no task, ever. |
| `util/XmlOutTagInfoUtil.java` | Turns tag rows into a document. The **first** row becomes the root; a row naming a parent that does not yet exist gets that parent created as a child of the root (`:62-97`). |
| `util/TaskPayloadLocationUtil.java` | Parses `taskPayload` for `bucket`/`bucket_name`, `input_folder`, `output_folder` and stores them as columns, with doctype declarations disabled (`:54`). Reads the **payload**, not the tag rows. |
| `util/UserNameResolver.java` | Resolves `created_by`/`updated_by` to display names in one query per list (`:80-112`). |
| `model/pojo/AuditListener.java` | Stamps the acting user on persist and update; stamps nothing when there is no acting user. |

---

## 6. Database requirements

| Table | Key columns | Notes |
|---|---|---|
| `source_task` | `task_detail_id` PK (seq `task_detail_source_Seq`), `tenant_id`, `task_name`, `task_status`, `home_page_id`, `pipeline_id`, `group_id`, `task_payload` (text), `bucket`, `input_folder`, `output_folder`, `source_task_type_id`, `created_by`, `updated_by` | Created by Hibernate `ddl-auto`, not by a changeset (`.ai/discovery/database.md:56-60`). `bucket`/`input_folder`/`output_folder` are **derived** from `task_payload` on every write. `home_page_id` and `group_id` are still `varchar` holding a `lookup_data.lookup_id`. **`pipeline_id` no longer is** (fixed 2026-09-07, see 12.7): both editors now write the pipeline's own id string -- the same one `task_form.pipeline_id` holds -- not a lookup row id. An **existing** row written before the fix still holds its old numeric-looking id and simply will not match any `task_form.pipeline_id`, the same "keeps running, stops resolving to a name" outcome `platform-configuration`'s own `TENANT_OWNED_LOOKUPS` comment already documents for this class of change; no backfill was written; see `process/.../V28__drop_pipeline_ids_lookup.sql`'s own comment for why. |
| `source_task_payload` | `task_payload_id` PK (seq `source_task_payload_Seq`), `tag_key`, `tag_parent`, `tag_value` (text), `payload_id` FK → `source_task.task_detail_id` | No `tenant_id`; inherits through the parent. The FK column is called `payload_id`, which reads like a self-reference and is not (`V17__table_descriptions.sql`). Row order is `task_payload_id` order, and every update deletes and re-inserts the whole set (`SourceTask.java:97-99` `orphanRemoval = true`, `:207-210`). |
| `source_task_type` | `source_task_type_id`, `tenant_id` (nullable = platform-owned), `service_name`, `queue_topic_partition`, `task_type_status`, `kafka_connection_profile_id` | Owned by `platform-configuration`. Read-only here. |
| `lookup_data` | `lookup_id`, `lookup_type`, `lookup_value`, `parent_lookup_id` | Owned by `platform-configuration`. **`PIPELINE_IDS` and its children are gone** (removed 2026-09-07 by `V28__drop_pipeline_ids_lookup.sql`, which deletes by `parent_lookup_id = 1015` rather than a hardcoded child list, because a live environment had accumulated far more than the four `V10` seeded -- test pipelines added through the app -- and a hardcoded list left orphans blocking the parent's own delete on the self-referencing FK). `PIPELINE_HOME_PAGES` and `TASK_GROUPS` are unaffected. No `TASK_GROUPS` parent is seeded anywhere, so the Group dropdown is empty on a fresh install. |
| `task_form` | `task_form_id` PK (seq `task_form_source_seq`), `pipeline_id`, `form_name`, `description`, `tenant_id` (null = all tenants), `form_status`, `date_created`, `created_by`, `updated_by` | `V19__task_form_builder.sql:12-25`; `updated_by` added by `V22__audit_columns.sql:43`. Unique index `ux_task_form_pipeline_tenant` on `(pipeline_id, COALESCE(tenant_id, -1)) WHERE form_status <> 'Delete'` (`:45-47`). **This table is now the sole source of truth for which pipelines exist** (2026-09-07) -- there is no `Pipeline` entity and no lookup family behind it any more; `pipeline_id` is whatever string an admin typed when creating the form. |
| `task_form_field` | `task_form_field_id` PK (**shares** `task_form_source_seq`), `task_form_id` FK `ON DELETE CASCADE`, `tag_key`, `tag_parent`, `label`, `field_type`, `required`, `default_value`, `help_text`, `field_options`, `position` | `V19__task_form_builder.sql:27-42`. The only `ON DELETE` clause in the schema. `field_options` is newline-separated choices for a select. |

**Migrations needed by the work in this document:**

1. Nothing for the list, the editor or the tenant picker -- those are code-only.
2. ~~Deciding 12.7 one way requires a data migration~~ -- **done 2026-09-07**, and not the way this
   document's synthesis companion recommended. Rather than choose between "the editor sends the
   lookup label" and "the form stores the lookup id" (options (a)/(b) in `synthesis/source-tasks.md`
   §6 Q1), the product decision was to remove the lookup family from the equation entirely: neither
   side keys on `lookup_data` for a pipeline any more. See 12.7 for the full account, and the
   synthesis document's Q1 for the superseded recommendation kept for the record.
3. `source_task_payload` has no `position` column. Order is carried by the id sequence, which works
   only because every save re-inserts the whole set. If tag ordering is ever to survive a partial
   update, a `position` column is the honest fix.

---

## 7. Validation

`C` = enforced on the client, `S` = on the server. **A rule that is `C` only is a finding**, and each
one is repeated in section 12.

| Rule | Old app | New app | Server | Where |
|---|---|---|---|---|
| Task name required | C | C | S | `task.component.ts:253,282`; `task-edit.ts:64`; `SourceTaskServiceImpl.java:146-147, 192-193` |
| Task type required | C | C | S | `task.component.ts:254,283`; `task-edit.ts:65`; `:150-153, 196-199` |
| Task type must exist and be `Active` | C (filtered out of the dropdown, `:179`) | **none** | S | `:154-158, 200-208` |
| Task type must be visible to the caller | none | none | S | `:126-131`, tested |
| **Task payload required** | C (`:255,284`) | **C, fixed 2026-09-07** (`task-edit.ts:73`; toggled off in favour of server-side generation while a pipeline form applies, `:210-227`) | S | `:148-149, 194-195` -- server rejects `null` and `""` |
| `tenantId` required when a platform admin creates | C (`:290`) | **none -- no control exists** | S | `:91-104` |
| `tenantId` must name a real tenant | none | none | S | `:99-101` |
| **Tag key / parent must not contain whitespace** | C only (`:38-43, 299-300, 308-309`) | **moot 2026-09-07** -- no row to type one into; the risk moved to Pipeline Forms' own `tagKey` field, which has the same gap (see 4.3, 12.5) | **none** | -- |
| Tag values trimmed of surrounding whitespace | C (`:126-154`) | **moot 2026-09-07** -- no row to type one into; a Pipeline Form field's answer is trimmed by `syncFormToTags` regardless (`task-edit.ts:275-312`, unchanged) | none | -- |
| Tag rows with a blank key dropped before save | none | C (`task-edit.ts:submitTask`, unchanged by name, moved by line) | none | -- |
| A task with live jobs cannot be deleted | none | C (`tasks.ts:196-210`) | S | `:266-275` |
| Status limited to Active/Inactive | none -- `Delete` is offered (`_models/object.ts:130-133`) | C (`task-edit.html:78-79`) | **none** | `:244-246` accepts any `Status` |
| Form: pipeline required | -- | C | S | `task-form-dialog.ts:223`; `TaskFormServiceImpl.java:183` |
| Form: name required | -- | C | S | `:224`; `:184` |
| Form: at least one field | -- | C (`:285`) | S | `:185-187` |
| Form: every field has a tag and a label | -- | C (`:288-289`) | S | `:190-192` |
| Form: no two fields write one tag | -- | C (`:290-293`) | S | `:193-197` |
| Form: a named parent must be created by some field | -- | C (`:295-300`) | S | `:199-206` |
| Form: field type from the known set | -- | C (the select) | S | `TaskFormServiceImpl.java:38-39, 133` -- anything else silently becomes `text` |
| Form: one live form per pipeline per tenant | -- | none | S | `:104-112` + the unique index |

---

## 8. Security

Four layers, checked separately, because they can disagree.

### 8.1 `PLATFORM_ADMIN`

| Layer | Verdict |
|---|---|
| Frontend guard | Passes everything. `hasAtLeast` ranks it highest (`auth.service.ts:53-56`). |
| `@PreAuthorize` | Passes everything, via `ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN` (`MethodSecurityConfig.java:29`). |
| Service rule | `isOwnedByCaller` returns `true` unconditionally (`:114-116`); `isSourceTaskTypeVisibleToCaller` likewise (`:127-129`); `TaskFormServiceImpl.isOwnedByCaller` likewise (`:211`). Creating a task **requires** an explicit `tenantId` that names a real tenant (`:92-102`) -- correct: a platform admin carries no tenant and must not silently create an ownerless row. |
| Hibernate filter | `enableIfNeeded` explicitly **disables** the filter for a platform admin (`TenantFilterHelper.java:28-33`), and `tenantClause` returns an empty string (`QueryService.java:213-215`). Sees everything. |

**The one thing a platform admin cannot do is create a source task**, because the new editor sends no
`tenantId` (12.2). They can still edit, clone-fail, delete and list.

### 8.2 `TENANT_ADMIN` (with a tenant)

| Layer | Verdict |
|---|---|
| Frontend guard | `roleGuard` admits them to `tasks/new`, `tasks/:id/edit`, `settings/forms`, `tasks/bulk`. |
| `@PreAuthorize` | Satisfies every method on `SourceTaskRestApi`, `TaskFormRestApi` and `SettingRestApi`. |
| Service rule | `isOwnedByCaller` requires `Objects.equals(task.getTenantId(), TenantContext.getTenantId())` -- so a platform-owned task (`tenant_id is null`) is **not** theirs. Correct. A task type is linkable if it is theirs or platform-owned (`:126-131`). A form is editable only if `form.getTenantId() != null && equals(tenantId)` -- a shared form is not theirs (`TaskFormServiceImpl.java:210-215`). |
| Hibernate filter | Enabled for `SourceTask` (`condition = "tenant_id = :tenantId"`, `SourceTask.java:24`) on the two update paths and the single read -- but those paths use `findById`, which the filter does not touch, so it changes nothing. The real protection is `isOwnedByCaller`. `TaskForm` declares a filter too (`TaskForm.java:30`) and nothing ever enables it; `TaskFormServiceImpl` scopes by hand instead. |

**Disagreement:** the task-forms UI offers Edit / Duplicate / Delete on shared forms
(`task-forms.html:72-81, 166-175`) which the service refuses with "That form belongs to another
tenant." The frontend is not enforcement here, but it is also not honest.

### 8.3 `TENANT_USER`

| Layer | Verdict |
|---|---|
| Frontend guard | Old app: **nothing**. `taskList`, `addTask` and `editTask/:id` all carry `AuthGuard` alone (`app.routing.ts:57-80`), so a tenant user fills in the whole form and is refused at Save. New app: `roleGuard` sends them to `/unauthorized` before the editor loads, and every write control on the list is hidden behind `auth.canManageTasks()`. |
| `@PreAuthorize` | Reads pass (`listSourceTask`, `fetchSourceTaskWithSourceTaskId`, `fetchAllLinkJobsWithSourceTaskId`, `fetchAllLinkSourceTaskWithSourceTaskTypeId`, `formForPipeline`). Every write is refused with 403. `setting.json/appSetting`, `fetchSubLookupByParentId` and `xmlCreateChecker` are all refused, because that controller is `TENANT_ADMIN` at class level. |
| Service rule | Same tenant checks as a tenant admin; the role never reaches the write paths. |
| Hibernate filter / `tenantClause` | Same as a tenant admin. |

### 8.4 A caller carrying no tenant who is not a platform admin

This is the case the ground rules single out, and it is where the code is weakest.

- `TenantFilterHelper.enableIfNeeded` **disables** the filter when `tenantId == null`
  (`:28-33`) -- the same branch as a platform admin.
- `QueryService.tenantClause` returns an **empty string** when the tenant id is null
  (`:213-215`), so `listSourceTask` and `fetchAllLinkJobsWithSourceTaskId` return **every tenant's
  rows** to such a caller.
- `isOwnedByCaller` evaluates `Objects.equals(null, null)` to `true`, so such a caller owns every
  platform-owned task.
- `resolveTenantIdForCreate` takes the non-platform-admin branch and writes `tenant_id = null`
  (`:92-95`), minting a platform-owned task.
- The one place that gets it right is task-type linkage: `SourceTaskServiceImplTenantIsolationTest`
  has an explicit `aContextWithNoTenantCannotBindATenantOwnedTaskType` (`:137-147`).
- On the forms side, `findForPipeline(pipeline, null)` matches only the shared rows -- correct --
  but `saveForm` writes `tenant_id = null`, creating a form for every tenant, and
  `isOwnedByCaller` then refuses that same caller permission to edit what they just made
  (`TaskFormServiceImpl.java:114, 210-215`).

Whether such a session can exist is a question for `tenants-and-users`, not for this document; the
tenant id comes straight from the JWT (`JwtAuthenticationFilter.java:40`). **Not verified:** whether
`app_user` permits a `TENANT_ADMIN` or `TENANT_USER` row with a null `tenant_id`. What is verified is
that if one exists, the list endpoints leak across tenants.

### 8.5 What the type link protects

Binding a task to a task type is an authorization decision, not a label: the type carries
`queue_topic_partition` and `kafka_connection_profile_id`, so a task bound to another tenant's type
both discloses their topology on the task detail screen and publishes on their broker. This is
stated in the test's own header comment
(`SourceTaskServiceImplTenantIsolationTest.java:34-41`) and enforced at `:155-158` and `:205-208`
with wording identical to a genuinely missing id.

---

## 9. Error handling

| What fails | Old app | New app |
|---|---|---|
| Task list load fails | `alertService.showError` toast; the table renders empty and looks like "no tasks" (`source-task.component.ts:152-157`) | `app-table-shell` error panel: the message, an alert icon, and a "Try again" button wired to `load()` (`data-table.ts:46-53`, `tasks.ts:252-256`) |
| Task list is genuinely empty | An empty-state row inside the table (`source-task.component.html:345-353`) | Empty panel with an icon and a message that distinguishes "No tasks yet." from "No tasks match your search." (`tasks.html:27`) |
| Linked jobs fail to load | Toast; the panel keeps showing the loading text cleared and an empty table | The panel caches `[]` and renders "Could not read the jobs for this task." (`tasks.ts:120-123`, `tasks.html:289-293`) -- honest, though indistinguishable from "the count was stale" |
| Delete refused (jobs bound) | Never reached: the modal calls the endpoint, the server refuses, the message lands in a toast | Refused **before** the request, naming the count and the remedy (`tasks.ts:204-209`); the menu item is also disabled with the same explanation in its tooltip |
| Delete fails on the server | Toast | `toast.error(err?.error?.message ?? 'Delete failed.')`, spinner cleared |
| Clone fails | Toast at either step | Two distinct messages -- "That task could not be read." and "The copy could not be created." -- so the operator knows which half failed (`tasks.ts:147, 171`) |
| Task fails to load in the editor | Toast; the form never renders because `sourceTaskForm` stays undefined and the template is `*ngIf`-gated | `toast.error`, `loading` cleared, and the form renders **blank and saveable** (`task-edit.ts:129-133`) -- see 12.12 |
| Settings/lookups fail to load | Toast per failed call, dropdowns empty | One toast, "Could not load the task settings."; a single failed sub-lookup degrades to an empty option list without taking the others down (`task-edit.ts:102, 110`) |
| XML preview fails | Toast (`task.component.ts:322-323`) | Inline red text under the button, and an explicit "Add a tag first -- the first one becomes the root element." when there is nothing to render (`task-edit.ts:219, 231, 239`) |
| Save rejected by the server | Toast with the server's message; the route does not change | `toast.error(response.message)`, `saving` cleared, the route does not change, the form keeps its values |
| Client-side validation fails on save | `submitted = true`, per-field red text, silent return | `toast.error('Check the highlighted fields.')` plus `markAllAsTouched()`, so every offending field lights up at once |
| Form save rejected | -- | `toast.error` with the server's own wording, which the dialog already produced locally in most cases |
| Form delete rejected | -- | `toast.error(err?.error?.message ?? 'The form could not be deleted.')` |
| Any 500 | Toast reading the raw error object | `err?.error?.message` with a plain-language fallback per call site |

Two server behaviours the UI cannot currently distinguish and should: `xmlCreateChecker` returns its
document in `message` rather than `data`, so a `SUCCESS` with an empty `message` is treated as a
failure (`task-edit.ts:228-233`); and a tag key containing a space produces a bare 500 from the XML
builder rather than a named validation error.

---

## 10. Dependencies

**Hard, upstream:**

- `platform-configuration` -- supplies the task types (with the Kafka topic behind them) and the
  `PIPELINE_HOME_PAGES` and `TASK_GROUPS` lookups (`PIPELINE_IDS` was a third one; removed
  2026-09-07, see 12.7 -- pipelines are this feature's own concern now, via Pipeline Forms).
  `appSetting`, `fetchSubLookupByParentId` and `xmlCreateChecker` all live on `SettingRestApi` and
  are all `TENANT_ADMIN`. Nothing here can be exercised end to end until a task type exists with a
  real topic behind it.
- `authentication-and-access` -- the bearer token, the role, and the tenant id every check reads
  out of `TenantContext`.
- `tenants-and-users` -- `tenant.json/listTenants` for the tenant picker this document asks to
  restore; and `created_by`/`updated_by` resolve through `app_user`.

**Downstream, depends on this:**

- `source-jobs` -- a job runs exactly one task; `job-edit.ts:90` calls `listSourceTask`, so 12.1
  caps the job editor's task picker at ten as well.
- `bulk-transfer` -- `tasks/bulk` uses `downloadSourceTaskTemplate`, `downloadListSourceTask` and
  `uploadSourceTask` on this controller, and shares the missing-`tenantId` problem (12.2).
- `job-runs-and-queue`, `dashboard`, `reports` -- transitively, through jobs.

**Sideways:**

- `dynamic-forms` -- `features/forms/submission-to-task-dialog.ts:197-201` turns a form submission
  into a source task payload via `listSourceTask` + `xmlCreateChecker`. It inherits 12.1: the
  "update an existing task" picker sees ten tasks.
- `object-browser` -- the destination of the "View in Bucket" link this document asks to restore.
- `own-account-and-notifications` -- `notification-links.ts:12` rewrites stored `/taskList` paths.

---

## 11. Acceptance criteria

Each is checkable by someone who did not write the code. Refusals are paired with a positive control
on the same fixture.

**Fixtures.** Tenant A and tenant B. In tenant A: 60 tasks, of which one (`T-active`) is Active with
no jobs, one (`T-inactive`) is Inactive, one (`T-used`) has three Active jobs bound to it. Task type
`TT-A` belongs to tenant A and is Active; `TT-A-off` belongs to tenant A and is Inactive; `TT-shared`
has `tenant_id = null` and is Active; `TT-B` belongs to tenant B and is Active. A Pipeline Form
exists for pipeline `F768926` with one required field (there is no lookup fixture to set up any
more -- creating the form is what makes the pipeline exist, see 12.7). Users: `admin-A`
(TENANT_ADMIN, tenant A), `user-A` (TENANT_USER, tenant A),
`admin-B` (TENANT_ADMIN, tenant B), `root` (PLATFORM_ADMIN, no tenant).

### Listing and reading

1. `user-A` opens `/tasks` and sees **all 60** of tenant A's tasks accounted for -- the header count
   reads "50 of 60" on page 1, and page 2 shows the remaining 10.
2. `user-A` opens `/tasks` and sees **no** task belonging to tenant B, on any page.
3. `user-A` sees no "New task", no "Bulk import" and no per-row actions menu on `/tasks`.
4. `admin-A` sees "New task", "Bulk import" and a per-row actions menu on `/tasks`.
5. `user-A` navigates directly to `/tasks/new` and lands on `/unauthorized`; `admin-A` navigating to
   the same URL gets the editor.
6. `admin-A` expands `T-used` and sees its payload plus a table of exactly the three bound jobs, each
   linking to `/jobs/:jobId/edit`.
7. `admin-A` expands `T-active` (no jobs) and sees its payload and no linked-jobs table.
8. `admin-A` sets the status filter to Inactive and sees `T-inactive` and not `T-active`; setting it
   back to All shows both.
9. `admin-A` types a string that appears only inside one task's XML payload into the search box and
   that task is the only row left.
10. `admin-A` clicks the storage link on a task whose payload names `bucket` = `etl-bucket` and
    `output_folder` = `reports/2026`, and arrives at the object browser at that bucket and prefix.
11. `admin-A` uses the per-row "Download JSON" action on `T-active` and gets a `.json` file whose
    contents include that task's name, type, pipeline and payload.
12. With the API stopped, `admin-A` opens `/tasks` and sees an error panel with a "Try again"
    button -- **not** an empty table; clicking it with the API restored loads the list.

### Creating and editing

13. `admin-A` creates a task named `AC-13` with type `TT-A`, a `bucket` tag and a payload, and it
    appears in the list with status Active.
14. `admin-A` picks no pipeline (or one with no form), submits the create form with the payload box
    empty, and is stopped **client-side** with a message on the Task payload field; no request is
    sent. **[changed 2026-09-07: this is now the only path where the payload box exists at all,
    and it is the same path 36 covers -- see 12.7]**
15. `admin-A` opens the Task type dropdown and `TT-A` and `TT-shared` are offered while `TT-A-off`
    is not.
16. ~~`admin-A` types `my tag` into a tag key...~~ **Removed 2026-09-07 -- there is no tag-key field
    on this screen any more (12.7).** The equivalent risk now lives on Pipeline Forms' own field
    editor; see `platform-configuration`'s acceptance criteria for whether it has a matching one,
    and 12.5 here for the gap this left behind.
17. ~~`admin-A` types `  etl-bucket  ` into a tag value...~~ **Removed 2026-09-07 -- there is no
    tag-value field on this screen either.** A Pipeline Form field's answer is still trimmed before
    it becomes a tag (`syncFormToTags`, unchanged in that respect), just not by way of a blur event
    a test can trigger on a row that no longer exists.
18. `admin-A` fills in a Pipeline Form's fields (no tag table, no preview button exists to click)
    and saves; `POST setting.json/xmlCreateChecker` is called with exactly those answers as tag
    rows, and the task is created with `taskPayload` equal to the document that call returned --
    not whatever the (removed) payload textarea last held. **[replaces the old "Show the XML"/"Use
    as payload" criterion, 2026-09-07, see 12.7]**
19. `admin-A` edits `AC-13`, changes its name, saves, and the list shows the new name and `admin-A`
    in Updated by.
20. `admin-A` edits `AC-13` and cannot select `Delete` in the Status dropdown.
21. `admin-B` requests `GET /sourceTask.json/fetchSourceTaskWithSourceTaskId?sourceTaskId=<AC-13>`
    and receives an `ERROR` whose message is "SourceTask not found with <id>."; `admin-A` requesting
    the same id receives `SUCCESS` with the task.
22. `admin-B` PUTs `updateSourceTask` for `AC-13` and is refused with the same "not found" wording;
    the task's name is unchanged when `admin-A` reloads.
23. `admin-A` POSTs `addSourceTask` naming `TT-B` as the task type and is refused with "Provided
    sourceTaskTypeId not found."; the same request naming `TT-shared` succeeds.

### Platform admin

24. `root` opens `/tasks/new` and sees a required **Tenant** field.
25. `root` submits the create form without choosing a tenant and is stopped client-side.
26. `root` chooses tenant B, fills the form with type `TT-B`, saves, and the new task appears when
    `admin-B` opens `/tasks` -- and does **not** appear when `admin-A` does.
27. `root` opens `/tasks` and sees tasks from both tenant A and tenant B.

### Cloning and deleting

28. `admin-A` duplicates `T-active`; a new task appears named `<name> (copy)` with status
    **Inactive**, carrying the original's type, pipeline, group, home page, payload and tag rows.
29. `admin-A` opens the actions menu on `T-used`; Delete is disabled and its tooltip names three
    jobs. Attempting the request directly (`PUT deleteSourceTask` with that id) returns `ERROR`
    naming three jobs, and all three jobs are still Active afterwards.
30. `admin-A` deletes `T-active`; a confirm dialog states that no jobs are bound, and after
    confirming the row leaves the list and the total drops by one.
31. `admin-A` PUTs `deleteSourceTask` with `{ taskDetailId }` and **no** `taskStatus`, then reloads:
    either the task is gone, or the response was an `ERROR` -- it must not report success while
    leaving the task Active.

### Task forms

32. `admin-A` creates a Pipeline Form for pipeline `F768926` with one required field, then opens
    `/tasks/new`, selects that pipeline from the dropdown, and the form's fields appear as the
    **only** configuration surface on the screen -- no tag table, no payload textarea, in either
    order. **[changed 2026-09-07: there is nothing left to collapse into -- see 12.7]**
33. `admin-A` fills that field with `hurricanes` and saves; the request the server receives
    carries a `taskPayload` generated from that answer (criterion 18) -- there is no "Edit tags
    directly" toggle to expand and no tag row to inspect directly any more, so this is now
    verified through the network request or through 35, not through a table on screen.
    **[replaces the old toggle-and-inspect criterion, 2026-09-07, see 12.7]**
34. `admin-A` clears that required field and tries to save; the save is refused with the field
    highlighted, and no `xmlCreateChecker` or `addSourceTask` request is sent.
35. `admin-A` opens `/tasks/:id/edit` for a task already on pipeline `F768926` and the form's fields
    are prefilled from the task's existing tag rows, not from the fields' defaults.
36. `admin-A` selects a pipeline that has no form; no form section appears, and the **Task
    payload** textarea appears instead, required, empty, and with no error shown.
    **[changed 2026-09-07: "the tag table is open" is no longer the fallback -- there is no tag
    table at all -- see 12.7]**
37. `admin-A` tries to save a second form for `F768926` and is refused with a message naming the
    pipeline; editing the existing one succeeds.
38. `admin-A` creates a form with two fields both writing `<bucket>` and is refused before the
    request leaves the browser, with the same wording the server would have used.
39. `admin-A` looks at a form whose Scope reads "All tenants" and finds Edit, Duplicate and Delete
    unavailable; on a form whose scope is their own tenant, all three are available and Edit saves
    successfully.
40. `root` edits a shared form and the save succeeds.
41. `admin-A` deletes their own form; tasks already on that pipeline continue to open and save, now
    showing the raw tag table.
42. `admin-A` opens `/settings/forms` and the Updated by column shows a name for a form they have
    just edited.

### Cross-tenant, no-tenant

43. A session whose token carries a `TENANT_ADMIN` role and **no** tenant id calls
    `POST /sourceTask.json/listSourceTask` and receives only platform-owned tasks -- not tenant A's
    and not tenant B's. `admin-A` calling the same endpoint still receives tenant A's tasks.

---

## 12. Known issues

Each item is a defect that exists today, with the evidence for it. None are fixed here.

### 12.1 The new task list is silently capped at ten rows -- **blocker**

`tasks.ts:246` posts to `listSourceTask` with an empty body and no query parameters. The controller
passes those nulls to `PagingUtil.ApplyPaging(null, null, null, null)`
(`SourceTaskRestApi.java:80-81`), which substitutes `DEFAULT_MAX_NO_OF_ROWS = 10L`
(`PagingUtil.java:19, 45-47`) and applies it via `query.setMaxResults`
(`QueryService.java:47-55`). The old app sent `limit: 5000` explicitly
(`source-task.component.ts:71-76`).

The client then filters, searches, sorts and pages those ten rows locally, and reports
`[total]="tasks().length"` to the table header (`tasks.html:26`), so a tenant with 400 tasks is told
it has 10. `ApiResponse` does not even declare the `paging` block the server returns
(`core/api/api.config.ts:9-13`).

The same call, with the same omission, is made from `features/settings/forms/task-forms.ts:89`
(pipeline suggestions), `features/jobs/edit/job-edit.ts:90` (a job's task picker) and
`features/forms/submission-to-task-dialog.ts:198`.

### 12.2 A platform admin cannot create a source task from the new UI -- **blocker**

`resolveTenantIdForCreate` refuses a platform admin who sends no `tenantId`:
"Tenant is required when creating a source task as Platform Admin."
(`SourceTaskServiceImpl.java:92-98`). The old editor had a required tenant select for exactly this
(`task.component.ts:290`, markup `task.component.html:39-51`). Searching `task-edit.ts`,
`task-edit.html` and `tasks.ts` for `tenant` returns nothing. `clone()` (`tasks.ts:151-160`) omits it
too, so a platform admin cannot duplicate a task either. `features/bulk/bulk-transfer.ts` likewise
sends no tenant, so bulk import is blocked for the same role.

### 12.3 `taskPayload` is required by the server and optional in the new form -- **fixed 2026-09-07**

**Original defect, kept for the record.** `task-edit.ts:70` declared `taskPayload: ['']` with no
validator. `addSourceTask` and `updateSourceTask` both refuse a null-or-empty payload
(`SourceTaskServiceImpl.java:148-149, 194-195`; `ProcessUtil.isNull` treats `""` as null,
`ProcessUtil.java:43-45`). The old form had `Validators.required` on it (`task.component.ts:255,
284`). A user who filled in tags but never pressed "Use as payload" got a valid-looking form and a
server rejection.

**Fixed as a side effect of removing the "Configuration tags" table (12.7), not as a standalone
change.** `taskPayload` now carries `Validators.required` (`task-edit.ts:73`). That alone would
have broken the form-driven path -- there is no "Use as payload" button left to satisfy it by hand
-- so the validator is cleared while a pipeline form is active (`loadFormForPipeline`,
`:206-211`) and restored the moment it is not (`clearForm`, `:220-227`), and `save()` generates the
payload from the form's answers itself before the request goes out (`:319-391`), implementing
exactly what `synthesis/source-tasks.md`'s Q2 already recommended (option (b), "generate it on
save whenever the box is empty") -- it was optional before this pass and became necessary once the
manual escape hatch was removed. The second-order consequence below is closed for the form-driven
path (the payload is always freshly generated, so it can never be stale relative to the tags that
produced it) and unchanged for the hand-written path.

**Second-order consequence, still true for a hand-written payload.** `bucket`, `input_folder` and
`output_folder` are parsed out of the **payload**, not the tags (`TaskPayloadLocationUtil.java:48-
65`, called at `SourceTaskServiceImpl.java:106-111`). A task with no pipeline form, whose operator
hand-writes a payload that does not actually match what they intended, still stores `bucket =
null` with no warning -- this was never a tag-table problem specifically, and remains open.

### 12.4 The new editor offers task types the server will refuse

`task-edit.ts:85` does `this.taskTypes.set(response.data?.sourceTaskTypes ?? [])` with no filter.
`appSetting` returns every task type with its status
(`SourceTaskTypeRepository.java:26-28`, `SettingServiceImpl.java:230-232`), including Inactive and
Delete. Both write paths look the type up with
`findSourceTaskTypeBySourceTaskTypeIdAndStatus(id, Status.Active)`
(`SourceTaskServiceImpl.java:154-155, 200-201`) and refuse anything else. The old editor filtered the
dropdown at `task.component.ts:179`.

### 12.5 Tag keys are validated nowhere in the new app, and nowhere on the server -- **relocated, not fixed, 2026-09-07**

The old form applied `noWhitespaceValidator()` to `tagKey` and `tagParent`
(`task.component.ts:38-43, 299-300, 308-309`) and disabled the XML button while any row was invalid
(`task.component.html:206`). `task-edit.ts` built each row with no validators at all -- this is
now moot on this screen, since the tag table it described is gone (12.7), but the underlying risk
did not go away, it moved. Every tag key a task ever saves now originates from a Pipeline Form's
`tagKey` field (`task-form-dialog.ts`, see `platform-configuration`'s documents for that screen's
own validation), which has **exactly the same gap**: nothing stops an admin from defining a field
whose `tagKey` contains whitespace or is otherwise not a legal XML element name.

Nothing on the server checks it either. `XmlOutTagInfoUtil.makeXml` calls
`xmlDoc.createElementNS(BLANK, tagKey)` (`:64`) and `createElement(tagKey)` (`:77, 85, 93`), which
throw on an invalid XML name; the exception is caught by the controller and returned as a bare
`INTERNAL_ERROR_500` (`SettingRestApi.java:182-184`). This now surfaces one step earlier than it
used to: **every** task on a pipeline whose form has a bad `tagKey` fails to save from
2026-09-07 onward (`generatePayloadFromTags` calls `xmlCreateChecker` unconditionally on every
form-driven save, `task-edit.ts:360-391`), rather than only the tasks whose operator happened to
type the same bad key by hand. That is arguably an improvement -- the failure is now
deterministic and pipeline-wide rather than per-task-and-silent -- but it is still an
`INTERNAL_ERROR_500` with no named field, on every task, until the form is corrected. `TaskFormServiceImpl.validate` (`:181-208`) checks for duplicate and orphaned tags but not for
this.

### 12.6 The new search is much narrower than the old one

`tasks.ts:74-83` matches on four fields: id, name, `sourceTaskType.serviceName`, `pipelineId`. The
old app ran everything through `SearchFilterPipe` (`_helpers/search-filter.ts`), which walks every
value on the object recursively -- payload included -- and supports quoted phrases, `field.path:term`
scoping and `-term` negation (`:40-101`). Searching a task by something inside its payload is a real
workflow that no longer exists.

### 12.7 Task forms never match a task, because the two sides key on different values -- **blocker, fixed 2026-09-07**

**Original defect, kept for the record.** The whole feature was inert. Two representations of
`pipelineId` were in play:

- **The editor wrote and read the lookup id.** The pipeline `<option>` bound
  `[value]="option.lookupId"` (`task-edit.html:41`), and `fetchSourceTaskWithSourceTaskId` returned
  the raw stored column (`SourceTaskServiceImpl.java:451`). For the seeded Hurricanes pipeline that
  was the string `"1030"` (`V10__fix_source_task_type_and_pipeline_ids.sql:44-45`:
  `lookup_id = 1030`, `lookup_type = 'F768926'`).
- **The forms screen suggested the lookup label.** `loadPipelines()` harvested `task.pipelineId`
  from `listSourceTask` (`task-forms.ts:89-97`), whose SELECT was
  `ld2.lookup_type as pipeline_id` (`QueryService.java:79-80`) -- that was `"F768926"`. The
  dialog's placeholder was literally `F768926` (`task-form-dialog.ts:60`), and `task-edit.ts:44-45`
  described the feature as "you had to know that F768926 wants a `search_term`".

So `loadFormForPipeline` called `formForPipeline?pipelineId=1030` (`task-edit.ts:273-274`) against
`task_form` rows created with `pipeline_id = 'F768926'`. `findForPipeline` matched on exact equality
(`TaskFormRepository.java:27-30`), so it never found one, returned the "No form is defined for this
pipeline." success (`TaskFormServiceImpl.java:72-74`), and the editor silently fell back to raw
tags -- indistinguishable from the normal no-form case.

**What was actually done -- and it is not what this document's own synthesis companion
recommended.** `synthesis/source-tasks.md` §3.3/§6 Q1 argued the fix was to pick a winning
*representation* (its recommendation: the editor sends the lookup label, `source_task.pipeline_id`
rows migrated from ids to labels, the list's join changed to match on `lookup_type`) and explicitly
rejected removing the lookup from the equation as one of three options it considered. The actual
instruction that shipped this fix ("remove PIPELINE_IDS from the lookup and use PIPELINE_IDS from
the form") was broader than the question Q1 posed: not *which side's format wins*, but *whether a
lookup should be involved at all*. It should not have been, and now is not:

- `PIPELINE_IDS` is removed as a lookup family entirely -- no parent row, no children, no
  `TENANT_OWNED_LOOKUPS` entry (`process/.../SettingServiceImpl.java`, migration
  `V28__drop_pipeline_ids_lookup.sql`). See `platform-configuration`'s grooming/synthesis documents
  for the lookup side of this change.
- `task_form` (Pipeline Forms) is now the **sole catalogue** of which pipelines exist. Its
  `pipeline_id` column is unchanged in shape -- still a free-text string an admin types when
  creating a form -- but it is no longer matched against anything in `lookup_data`.
- Source Task's Pipeline picker, in **both** frontends, now reads that catalogue directly: a new
  `GET taskForm.json/listPipelines` endpoint (`TaskFormRestApi.java:61-70`, `TENANT_USER` --
  the same role `formForPipeline` already used, and for the same reason: this screen carries no
  admin gate) returns every `TaskForm` the caller may see, and the `<select>` binds the pipeline's
  own id string directly (`task-edit.ts:120-126` + `task-edit.html:38-46`; legacy
  `task.component.ts:110-121` + `task.component.html:71-77`, via a new `TaskFormService`).
  `formForPipeline` is then called with that exact string, which is by construction the same
  string `task_form.pipeline_id` holds -- there is no representation left to disagree.
- `SourceTask.pipelineId` itself changes meaning going forward: it used to store a lookup row id,
  resolved to a human string only at Kafka-dispatch time
  (`ProducerBulkEngine.getSourceJobDetail` called `findLookupValueByLookupId`); it now stores the
  real pipeline string directly, and that resolution step is deleted, not merely redirected.
- **No data migration was written** for existing `source_task` rows already holding an old
  numeric-looking id. This is a deliberate omission, not an oversight: `platform-configuration`'s
  own `TENANT_OWNED_LOOKUPS` comment already establishes the precedent that a task keeps running
  when the lookup row behind its stored id disappears, it just stops resolving to a friendly name
  -- and per that same precedent, an old task's pipeline simply will not match a Pipeline Form
  until it is re-pointed at one that exists. Whether that is acceptable for this codebase's actual
  data is unverified; nobody audited how many `source_task` rows hold a stale numeric id at the
  time of the change.
- The forms dialog's pipeline-suggestion datalist (`loadPipelines()` reading pipeline ids already
  in use on tasks, `task-forms.ts:87-101` in the original) is deleted rather than fixed: it is
  circular now that Source Task reads its options from here instead of the other way around.
  Pipeline is now a plain free-text field with a placeholder and a hint explaining what it becomes.

**Verified live**, not merely by the test suite: rebuilt and redeployed all three services against
the real dev database, confirmed via `read_page`/network-request inspection that both frontends'
Pipeline dropdowns list the pipelines actually defined in Pipeline Forms (not lookup rows), and
that selecting one calls `formForPipeline` with that exact string. One genuine new test
(`task-edit.spec.ts`), mutation-tested (the `LOOKUP_TYPES` fix was reverted, the test was watched
to fail, then restored).

**Two knock-on effects of the original mismatch, now moot for new rows but worth knowing.** A task
created by **bulk import** stores whatever text the spreadsheet held
(`SourceTaskServiceImpl.java:615`) -- that was already the "label" shape and continues to work
unchanged. The list's `left join lookup_data ld2 on cast(ld2.lookup_id as varchar(10)) =
st.pipeline_id` (`QueryService.java:89`) was written to resolve the **old** lookup-id shape into a
label for display; it was not touched by this change and now joins against a `lookup_data` table
that no longer has `PIPELINE_IDS` rows to match at all, so it renders nothing for every task
regardless of which `pipeline_id` shape the row holds. **This is a new, small, currently-unfixed
gap this change introduces** -- tracked as 12.22 below, since it is a display-only regression, not
a blocker, and this document's discipline is to record rather than quietly fix it here.

### 12.8 A cloned task is created Active while the UI says it is Inactive

`tasks.ts:155` sends `taskStatus: 'Inactive'` and `:165` toasts
`Copied as "<name> (copy)" — it starts inactive.` `addSourceTask` ignores the field entirely and
hard-codes `sourceTask.setTaskStatus(Status.Active)` (`SourceTaskServiceImpl.java:171`). The copy is
live the moment it is created, and the console says the opposite. The old clone passed the source's
status through and was ignored the same way (`source-task.component.ts:254`), but it made no claim
about the result.

### 12.9 The task-forms UI offers three actions the server refuses on shared forms

`listForms` returns platform-owned forms (`tenant_id is null`) to every tenant
(`TaskFormServiceImpl.java:53-56`), and `task-forms.html` renders Edit, Duplicate and Delete on every
row unconditionally (`:72-81` cards, `:166-175` table). `saveForm` and `deleteForm` both go through
`isOwnedByCaller`, which requires `form.getTenantId() != null` (`:210-215`), so a tenant admin gets
"That form belongs to another tenant." on Edit and Delete. Duplicate is fine -- it opens a new
dialog -- but it is the only one of the three that is.

### 12.10 The form dialog's payload preview does not model the XML the server builds

`task-form-dialog.ts:323-341` nests fields under their declared parents and emits every parentless
field as a top-level element. `XmlOutTagInfoUtil.makeXml` does something different: the **first**
row becomes the document root, every subsequent parentless row is appended **inside** it
(`:62-67, 91-96`), and a row naming a parent that does not exist yet gets that parent created as a
child of the root (`:81-90`).

So a form whose first field is not the root produces a document the preview never showed. This is
enshrined by a passing test: `TaskFormValidationTest.parentMayComeLater` (`:119-126`) asserts that a
form ordered `[tables under tenant, tenant at root]` is valid -- and it is, by the validator's rules,
but `makeXml` will make `<tables>` the root and put `<tenant>` inside it.

### 12.11 The old editor's "Clear" button breaks edit mode

`task.component.html:210-212` binds Clear to `addSourceTaskFormInit()`, which rebuilds the form group
from scratch with `taskDetailId: []` -- a null control (`task.component.ts:280-292`). The route
param `this.taskDetailId` is untouched, so `submitSourceTask` still takes the update branch
(`:349`) and PUTs `taskDetailId: null`, which the server refuses with "SourceTask taskDetailId
missing." (`SourceTaskServiceImpl.java:191-192`). Clear also re-adds ten blank tag rows and, for a
platform admin, a required tenant control that edit mode is not supposed to have.

### 12.12 A failed load leaves the new editor blank and saveable

`task-edit.ts:129-133` clears `loading`, toasts the error and returns. The form group is a field
initialiser (`:62-75`), so it already exists and the template renders it -- an empty, editable form
with the route's `taskDetailId` **not** patched into it. `isEdit()` reads the route input, so Save
still takes the update branch (`:420-422`) and PUTs `updateSourceTask` with
`taskDetailId: null`, which the server refuses with "SourceTask taskDetailId missing."
(`SourceTaskServiceImpl.java:191-192`). The old app rendered nothing at all in this case, because
its template was gated on `*ngIf="sourceTaskForm"` (`task.component.html:9`).

### 12.13 `deleteSourceTask` reports success while doing nothing if `taskStatus` is omitted

The task is marked deleted only inside
`if (!ProcessUtil.isNull(sourceTaskDto.getTaskStatus()))` (`SourceTaskServiceImpl.java:276-278`),
but the success message is returned unconditionally (`:281`). A caller who sends only
`{ taskDetailId }` gets "SourceTask successfully deleted with ID n." and the task is still Active.
Both current clients happen to send the field (`tasks.ts:221`; the old app posts the whole object),
which is why nobody has hit it.

### 12.14 The delete cascade is now unreachable

`statusChangeSourceJobWithSourceTaskId(id, 'Delete')` runs at `:280`, after the guard at `:269-275`
has already returned when any non-deleted job points at the task
(`SourceJobRepository.java:73-75`). By the time the cascade runs, there is nothing left to cascade
to. The comment block above `remove()` in `tasks.ts:189-194` still describes the old cascading
behaviour, and the modal text in the old app still promises it
(`source-task.component.html:386-388`).

### 12.15 `updateSourceTask` accepts `taskStatus: Delete`, bypassing the delete guard

`:244-246` writes whatever `Status` arrives. The old editor put `Delete` in the dropdown
(`task.component.html:81-83` over `_models/object.ts:130-133`), so a tenant admin could delete a task
through the update path -- skipping the "still has n jobs" check and skipping the job cascade,
leaving live jobs pointing at a deleted task. The new editor offers only Active and Inactive
(`task-edit.html:78-79`), which is a client-side narrowing of a server-side hole.

### 12.16 `tenantClause` and `enableIfNeeded` treat "no tenant" as "all tenants"

`QueryService.tenantClause` returns `""` when `TenantContext.getTenantId()` is null
(`:213-215`), and `TenantFilterHelper.enableIfNeeded` disables the filter on the same condition
(`:28-33`). For a platform admin that is correct. For a `TENANT_ADMIN` or `TENANT_USER` carrying no
tenant it means `listSourceTask` and `fetchAllLinkJobsWithSourceTaskId` return every tenant's rows.
`isOwnedByCaller` has the matching hole: `Objects.equals(null, null)` is `true`, so such a caller
owns every platform-owned task (`:117`). The type-linkage path is the only one that gets this right,
and it is the only one with a test for it
(`SourceTaskServiceImplTenantIsolationTest.java:137-147`).

### 12.17 The forms list never fills Updated by

`task-forms.html:129-130, 155-157` renders an Updated by column. `TaskFormServiceImpl.listForms`
resolves names only for `getCreatedBy` and only calls `setCreatedByName` (`:58-60`); nothing ever
calls `setUpdatedByName` on a `TaskForm`. The column is permanently an em dash.

### 12.18 `TagInfo.compareTo` is not a valid comparator

`ConfigurationMakerRequest.TagInfo.compareTo` compares boxed `Long`s with `==` (`:103`), which is
reference equality above the cache range, then falls through to `>` -- so two rows with equal ids
compare as `-1` in both directions. `Collections.sort` is called on this at
`SourceTaskServiceImpl.java:465`. It works today only because `task_payload_id` values are distinct
and non-null; a null id (a row the client sent back without one) would NPE inside the unboxing at
`:105`.

### 12.19 `TaskForm` declares a Hibernate filter that is never enabled

`TaskForm.java:27-30` declares `@FilterDef`/`@Filter` with
`(tenant_id = :tenantId or tenant_id is null)`. `TaskFormServiceImpl` never calls
`tenantFilterHelper.enableIfNeeded`; it scopes `listForms` with an in-memory `removeIf`
(`:53-56`) and the other reads with an explicit JPQL parameter. The annotation is dead, and it reads
as protection that is not there.

### 12.20 Smaller things

- `tasks.ts` carries its own `topicOf()` regex (`:260-264`) while the app already has a tested
  shared `parseTopicPartition` (`shared/ui/topic.ts:17-24`, `topic.spec.ts`). `topicOf` also drops
  the partitions, which no new screen shows.
- The `linked` branches in `tasks.ts:225-227` are dead: `remove()` returns early at `:204-210`
  whenever `linked` is non-zero, so the "and n jobs deleted" message can never render.
- `SourceTaskService` in the old app keeps `searchText` on the injectable singleton and re-sends it
  when a later caller omits one (`_services/source.task.service.ts:12, 28-31`).
- Changing the pipeline from one that has a form to one that does not leaves the previous form's tag
  rows in place; `clearForm()` (`task-edit.ts:296-302`) removes the controls but not the tags.
- No `TASK_GROUPS` parent lookup is seeded by any changeset, so the Group dropdown is empty on a
  fresh install in both applications.
- `task_form` and `task_form_field` share `task_form_source_seq` (`TaskForm.java:46`,
  `TaskFormField.java:25`), so both tables' ids are sparse and interleaved.

### 12.22 The tasks list's Pipeline column now renders empty for every row

`tasks.html`'s Pipeline cell (and `tasks.ts`'s search over `pipelineId`) trust a server-side join
that was written to resolve the **old** lookup-id shape into a display label:
`QueryService.java:89`'s `left join lookup_data ld2 on cast(ld2.lookup_id as varchar(10)) =
st.pipeline_id`. That join was never touched by the 2026-09-07 pipeline/lookup work (12.7,
`platform-configuration`'s documents) because it lives in `source-jobs`'/`source-tasks`' shared
`QueryService`, not in the code either change actually edited -- but its target table lost every
`PIPELINE_IDS` row that join could ever have matched. It now resolves to nothing for **every**
task, regardless of whether `pipeline_id` holds an old numeric id or a new real pipeline string,
because there is no `lookup_data` row of either shape left to join against. This is a
**display-only regression** introduced as a side effect of the lookup removal: no data is lost,
`fetchSourceTaskWithSourceTaskId` still returns the raw column, and the Pipeline `<select>` in the
editor is unaffected (it does not use this join) -- only the list's Pipeline cell and the search
term now silently show/match nothing. Recorded rather than fixed here per this document's own
discipline (grooming records, Execution fixes); the honest repair is to drop the join and render
`st.pipeline_id` directly, since it is now human-readable on its own.

### 12.21 Test coverage

| Area | Coverage |
|---|---|
| Task-type tenant isolation | `SourceTaskServiceImplTenantIsolationTest` -- 6 tests, including the no-tenant case and two positive controls. Good. |
| Task form validation rules | `TaskFormValidationTest` -- 10 tests over the static `validate`. Good, except that one of them enshrines 12.10. |
| Role hierarchy | `config/MethodSecurityConfigRoleHierarchyTest` |
| Tenant filter declarations | `model/pojo/TenantFilterDeclarationTest` |
| Pipeline picker reads Pipeline Forms, not a lookup (12.7) | `task-edit.spec.ts` -- 3 tests, added 2026-09-07, mutation-tested (the `LOOKUP_TYPES` fix was reverted, the test was watched to fail, then restored). Good, and the **first** frontend spec this feature has ever had. |
| Payload generated from the form's answers on save (12.3, 12.7) | `task-edit.spec.ts` -- 2 tests, added 2026-09-07, mutation-tested the same way. Covers the form-driven generation and the still-required hand-written path; does not cover a `xmlCreateChecker` failure mid-save. |
| **Task CRUD other than type linkage** | **none** -- no test covers `resolveTenantIdForCreate`, the delete guard, or the derived bucket columns |
| **`listSourceTask` / `QueryService` tenant scoping** | **none** |
| **`TaskFormServiceImpl` ownership and duplicate-pipeline rules** | **none** -- only the static validator is tested |
| **`XmlOutTagInfoUtil`** | **none** |
| **`TaskPayloadLocationUtil`** | **none** directly; exercised incidentally by the isolation test, which constructs a real one (`:69`) |
| **Every other frontend file in this feature** | **none** beyond the two `task-edit.spec.ts` additions above. Nothing covers `tasks.ts`, the forms list or dialog, `buildFormControls`, `findTag`, or `syncFormToTags` in isolation; the old app has **zero** spec files in total. |

---

## 13. Missing functionality

Absent from both applications, in rough order of how often the absence would be felt.

| Missing | What it would take |
|---|---|
| **Server-side search, sort and paging on the list.** The endpoint supports all three -- `SearchTextDto` in the body, `columnName`/`order`/`page`/`limit` as parameters, with a sort-column allow-list at `QueryService.java:188-199` -- and neither client has ever used them beyond `limit: 5000`. | Wire the toolbar and the column headers to the request; read `response.paging` for the total. Medium: the client-side `filtered`/`pager` computeds have to become request state instead. |
| **A read-only task detail page.** Both apps only ever show a task inside a list row or an edit form. A `TENANT_USER` -- who can read a task through `fetchSourceTaskWithSourceTaskId` -- has no way to see its tag rows at all. | A `tasks/:id` route rendering the same data the editor loads, without the form. Small. |
| **Bulk actions on tasks.** The jobs list has them; the tasks list does not, in either app. | Server-side would be new endpoints; client-side would repeat the old app's N-parallel-requests pattern, which section 12 of `frontend-old.md` already calls out as a mistake. |
| **A tag `position` column.** Order is currently the `task_payload_id` sequence, which only holds because every save deletes and re-inserts every row. Reordering a tag rewrites its id. | `ALTER TABLE source_task_payload ADD COLUMN position INT`, plus an `@OrderBy` and a backfill. Small, and it removes the reliance on 12.18's comparator. |
| **Server-side tag-key validation.** See 12.5. Today an invalid XML name is accepted on save and only fails when something renders it. | A check in `addSourceTask`/`updateSourceTask` against the XML `Name` production, returning a named error. Small. |
| **A form scoped to a task type as well as a pipeline.** `task_form` keys on `pipeline_id` alone, so two task types running the same pipeline with different payloads cannot each have a form. | Not needed until somebody asks; the unique index would have to widen. |
| **Any test of the frontend for this feature.** Neither the list, the editor, `syncFormToTags` nor the forms dialog has a spec, and `syncFormToTags` (`task-edit.ts:349-388`) is the most intricate piece of logic in the feature. | The project already has vitest and 31 specs; `syncFormToTags`, `findTag`, `controlName` and the dialog's `validate`/`preview` are all pure enough to test directly. Small, and it is the cheapest insurance against 12.10 recurring. |
| **A way to see which tasks a form is actually driving.** The forms list shows a field count and a scope but not how many tasks sit on that pipeline. | One count on `listForms`, joined through `source_task.pipeline_id` -- which cannot be written until 12.7 is settled. |
