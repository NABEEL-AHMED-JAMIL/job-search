# Synthesis -- Source Tasks

Companion to `.ai/grooming/source-tasks.md`. Every claim here is cited there; paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

Source Tasks looks migrated and is not, quite. The list, the editor, clone and delete all crossed,
and several of them crossed *better* -- real loading/error/empty states, authorship columns, an
"Only mine" filter, and a delete that refuses with a reason instead of quietly taking three hundred
jobs with it. What did not cross is a short list with three items on it that stop the feature
working at all: the new list asks the server for tasks without a `limit` and so receives **ten
rows**, whatever the tenant actually holds; the new editor has no tenant picker, so a
`PLATFORM_ADMIN` -- who belongs to no tenant and must name one -- **cannot create a task**; and
the flagship addition of the rewrite, Task Forms, keyed on the pipeline **label** while the task
editor sent the pipeline **lookup id**, so no form ever matched a task and the whole subsystem was
inert. **The third of those is now fixed (2026-09-07), and not the way this document
recommended** -- see §3.3's addendum and §6 Q1: rather than pick a winning representation, the
`PIPELINE_IDS` lookup was removed altogether and Task Forms became the sole catalogue of which
pipelines exist, which in turn forced the removal of the old "Configuration tags" tag table (a
second, hand-editable configuration surface stopped making sense once a pipeline's form was the
only place a pipeline could be defined at all) and made generating the payload from a form's
answers on save mandatory rather than the optional improvement gap 4 originally described.
Underneath those sit a set of validation rules that were
client-only in the old app and are now enforced nowhere -- a required payload, an Active-only task
type, a tag key that is a legal XML name -- plus a scattering of smaller losses (status filter,
payload search, the bucket deep link, per-row JSON export, group and home page on the list) and one
tenancy hole shared with the rest of the platform, where a caller carrying no tenant is treated as
a caller allowed to see everything. The work is: fix the three blockers, restore the four validation
rules on both sides, put back the list affordances that were dropped, and write the first test any
part of this feature has ever had on the frontend.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | `tasks.ts:246` posts `listSourceTask` with no params; `PagingUtil` defaults `limit` to 10 | The list shows every task in the tenant | Only the first 10 tasks exist as far as the new console is concerned -- and the header claims that is the total | Send `page`/`limit`/`columnName`/`order`; read `response.paging` for the true total; do the same at the three other call sites | **M** | **High** -- silent data loss across four screens |
| 2 | No tenant control anywhere in `task-edit.*`; `resolveTenantIdForCreate` refuses a platform admin with no `tenantId` | A platform admin picks the owning tenant when creating | `PLATFORM_ADMIN` cannot create or clone a task | Add a required Tenant select, create-mode only, `auth.isPlatformAdmin()` only, fed by `tenant.json/listTenants`; send it from `save()` and `clone()` | **S** | Med -- untestable without a platform-admin fixture |
| 3 | Editor sends `pipelineId = "1030"` (lookup id); forms are created with `"F768926"` (lookup label) | A form defined for a pipeline drives every task on it | Task Forms never fires; the failure looks identical to "this pipeline has no form" | **Fixed 2026-09-07 -- not the way recommended below.** The lookup was removed from the equation entirely rather than choosing a winning representation; see §3.3's addendum and §6 Q1's resolution | **M** (as predicted) | Realised: also required removing the "Configuration tags" table and generating the payload on save (12.3) -- see §3.3 |
| 4 | `taskPayload` has no client validator; server rejects empty | The form refuses before the request | Server error on save for a form that looked valid; and `bucket`/`input_folder`/`output_folder` silently stay null | **Fixed 2026-09-07**, exactly as recommended (Q2 option (b)), and folded into the gap 3 work rather than done separately: `Validators.required`, toggled off while a pipeline form generates the payload instead | S (as predicted) | Low (as predicted) |
| 5 | Task-type dropdown lists Inactive and Deleted types | Only Active, visible types offered | "Provided sourceTaskTypeId not found." on save, with no clue which field is wrong | Filter on `status === 'Active'` at `task-edit.ts:85`, as `task.component.ts:179` did | S | Low |
| 6 | Tag keys validated nowhere -- not client, not server | An illegal XML name is refused where it is typed | A bad tag saves fine and 500s later when anything renders it | Client validator on `tagKey`/`tagParent`; server check in `add`/`updateSourceTask` returning a named error | S | Low |
| 7 | `addSourceTask` hard-codes `Status.Active`; `tasks.ts` toasts "it starts inactive" | A clone is created inactive | A half-configured copy is live immediately, and the console says the opposite | Honour `taskStatus` on create when it is `Active` or `Inactive`, defaulting to `Active` | S | Med -- changes create semantics for bulk import too |
| 8 | No status filter; search covers 4 fields | Filter by status; search reaches payload, group and bucket | Two everyday narrowing operations lost | Add a status `<select>`; widen the `filtered` computed. Becomes server-side once #1 lands | S | Low |
| 9 | Storage renders as text; group, home page and partitions render nowhere | The list shows what the old expand panel showed, and storage links into the object browser | An operator has to open the editor to see a task's group or home page | Restore the detail block in the expanded row, including the `/objects` link with `{bucket, prefix}`; add the two columns | S | Low |
| 10 | No per-row export | Download a task as JSON, as `downloadSourceTask` did | The one list affordance `settings/task-types` kept and `tasks` dropped | A `download(task)` method building a `Blob` from the row already in memory | S | Low |
| 11 | Task-forms UI offers Edit/Delete on shared forms; server refuses | The UI offers only what the server will accept | A tenant admin gets "That form belongs to another tenant." on a row that looked editable | Gate both on `form.tenantId != null \|\| auth.isPlatformAdmin()` | S | Low |
| 12 | Dialog preview nests by parent; `XmlOutTagInfoUtil` makes the **first** row the root | Preview matches the document the server builds | The preview lies for any form whose first field is not the root | Model the server's rule in `preview`, or preview through `xmlCreateChecker`; fix `TaskFormValidationTest.parentMayComeLater`, which enshrines the divergence | **M** | Med -- one existing test asserts the current behaviour |
| 13 | `listForms` never calls `setUpdatedByName`; the column renders it | Updated by shows the last editor | A permanently empty column | Use `userNameResolver.attachNames(forms)` instead of the hand-rolled `namesFor` loop | S | Low |
| 14 | `tenantClause` returns `""` and `enableIfNeeded` disables the filter when the tenant is null; `isOwnedByCaller` treats `null == null` as ownership | A caller carrying no tenant owns nothing | A non-platform-admin with a null tenant sees every tenant's tasks | Split "platform admin" from "no tenant": platform admin → unfiltered; no tenant and not platform admin → `tenant_id is null` only | **M** | **High** -- shared with every other feature; must not be fixed here alone |
| 15 | `deleteSourceTask` returns SUCCESS while skipping the status change when `taskStatus` is absent | A delete either deletes or says why not | A caller can be told a task was deleted when it was not | Drop the `if` at `SourceTaskServiceImpl.java:276-278`; the endpoint's only purpose is to delete | S | Low |
| 16 | `updateSourceTask` accepts `taskStatus: Delete`, bypassing the live-job guard | Deletion happens only through `deleteSourceTask` | Live jobs can be left pointing at a deleted task | Reject `Delete` in `updateSourceTask` with a message pointing at the delete endpoint | S | Med -- the old UI offered it, so old data may exist |
| 17 | Zero frontend tests for this feature; zero tests for `XmlOutTagInfoUtil` and task CRUD | The intricate parts are tested | `syncFormToTags` is the most complex logic in the feature and nothing guards it | Vitest specs for `syncFormToTags`/`findTag`/`controlName` and the dialog's `validate`/`preview`; JUnit for `makeXml` and the delete guard | **M** | Low |
| 18 | `tasks.ts:260-264` has a private `topicOf` regex beside a tested shared `parseTopicPartition` | One implementation | Partitions are dropped and a third parsing of the same string exists | Import `shared/ui/topic.ts`; delete `topicOf` | S | Low |
| 19 | `TaskForm` declares a Hibernate filter nothing enables | The declaration reflects reality | Reads as protection that is not there | Either enable it in `TaskFormServiceImpl` and drop the manual `removeIf`, or delete the annotation | S | Med -- enabling a filter changes read behaviour app-wide |
| 20 | Editor renders a blank saveable form when the task fails to load; old "Clear" button breaks edit mode | A failed load shows an error, not a form | Save from that state PUTs a null id | Gate the form on a `loaded` signal and render the `TableShell`-style error panel with a retry | S | Low |

---

## 3. Solution detail

### 3.1 Gap 1 -- paging (the ten-row cap)

**What changes.** `features/tasks/tasks.ts` gains request state -- page, size, sort column, sort
order, search term -- and `load()` sends them as query parameters. `ApiResponse` in
`core/api/api.config.ts` gains the optional `paging` block the server has always returned
(`PagingUtil.convertEntityToPagingDTO`), and the table header reads `paging.totalRecord` instead of
`tasks().length`. The `filtered`/`paged` computeds stop being the source of truth and become a thin
pass-through. The same change is needed at `features/settings/forms/task-forms.ts:89`,
`features/jobs/edit/job-edit.ts:90` and `features/forms/submission-to-task-dialog.ts:198`, which are
pickers rather than lists.

**Why this rather than the alternative.** The obvious cheaper fix is to send `limit: 5000` and keep
everything client-side, exactly as the old app did (`source-task.component.ts:71-76`). Rejected,
but only for the main list: the endpoint already implements paging, sorting with an allow-listed
column (`QueryService.java:188-199`) and a search body, and the new app has a `Pagination` component
and a `createPager` helper sitting there doing client-side work over a page the server already
paged. Fetching five thousand rows to show fifty is the shape of problem the rewrite exists to
remove, and it degrades the moment a tenant is large -- which is precisely when the bug bites. **For
the three pickers, `limit: 5000` is the right answer** and is what I would do: they are dropdowns
that need every option, not lists, and giving each of them a paging UI would be worse than the
problem. This split is deliberate and should be stated in the change.

**A caveat worth naming.** Moving search to the server changes its behaviour: `SearchTextDto`
supports one `itemName`/`itemValue` pair over a fixed set of columns
(`QueryService.java:103-115`), not the free-text-across-everything the client does today. Gap 8's
"search the payload" therefore needs a new branch in that `if` chain (`task_payload`), not just a
client change.

### 3.2 Gap 2 -- the platform-admin tenant picker

**What changes.** `task-edit.ts` gains a `tenants` signal, loaded from `tenant.json/listTenants`
only when `auth.isPlatformAdmin()` and only in create mode; a `tenantId` control added
conditionally with `Validators.required`; and `save()` includes it in the payload when present.
`task-edit.html` gains one `app-field` with a `@if (auth.isPlatformAdmin() && !isEdit())` guard.
`tasks.ts` `clone()` needs the same value -- which it does not have, because the list row does not
carry `tenantId`.

**Why this rather than the alternative.** Three options were considered.

- *Copy the old app's shape* -- a select on the create form. Chosen. It is what the server's error
  message literally asks for, it is what the old app did, and it keeps the tenant decision in the
  one place a task's tenant is ever decided.
- *Have the server infer the tenant from the task type* when the caller is a platform admin.
  Rejected: a platform-owned task type has no tenant to infer, which is the common case
  (`SourceTaskType` allows a null tenant by design), so the inference fails exactly where it is
  needed.
- *Block the "New task" button for platform admins.* Rejected as dishonest -- it converts a bug into
  a missing capability, and a platform admin creating a task on a tenant's behalf during setup is a
  real workflow the old app supported.

For `clone()`, the honest fix is to read the tenant off the task being cloned: `fetchSourceTask...`
already loads the full record, so the clone can send `tenantId` from `source.tenantId` when the
caller is a platform admin. That requires `SourceTaskDto` to carry `tenantId` on the way out -- it
has the field (`SourceTaskDto.java:21`) but `fetchSourceTaskWithSourceTaskId` never sets it
(`SourceTaskServiceImpl.java:447-467`). One added line, and it is better than a second dialog.

### 3.3 Gap 3 -- the pipelineId representation, which is the interesting decision

**The mismatch.** `source_task.pipeline_id` stores the lookup **id** (`"1030"`) because both editors
bind `[value]="option.lookupId"`. `task_form.pipeline_id` stores the lookup **label** (`"F768926"`)
because the forms screen suggests values harvested from `listSourceTask`, whose SELECT is
`ld2.lookup_type as pipeline_id` (`QueryService.java:79-80`). `formForPipeline` matches on exact
string equality (`TaskFormRepository.java:27-30`), so the two never meet.

**Recommended: make the editor send the label.** Change the pipeline `<option>` binding to
`[value]="option.lookupType"`, and have `fetchSourceTaskWithSourceTaskId` return the resolved label
rather than the raw id -- or, less invasively, resolve id → label in `loadFormForPipeline` before
calling the endpoint.

**Why, and what was rejected.**

- *Store the id in `task_form` instead* (rewrite existing form rows, change the forms screen to
  offer a lookup dropdown). Rejected on three grounds. First, `pipeline_id` is what the **worker**
  routes on -- `V10__fix_source_task_type_and_pipeline_ids.sql:32-35` says the Python router
  recognises `F768924`/`F768925`/`F768926`/`F768927` and raises on anything else -- so the label is
  the value with meaning outside this database, and the lookup id is an internal surrogate. Second,
  bulk-imported tasks already store free text, which in practice is the label
  (`SourceTaskServiceImpl.java:615`), so the label is already the value some rows hold. Third, the
  form dialog's placeholder, its help text and `task-edit.ts:44-45`'s own comment all describe the
  key as `F768926`; the code and the documentation already agree that the label is the intended key.
- *Make `formForPipeline` accept either and try both.* Rejected. It hides the inconsistency instead
  of removing it, and the next feature that keys on `pipelineId` inherits the same trap.

**What the recommendation costs.** Changing the option value changes what new tasks store in
`source_task.pipeline_id`, so the list's `left join lookup_data ld2 on cast(ld2.lookup_id as
varchar(10)) = st.pipeline_id` (`QueryService.java:89`) would stop matching for new rows and start
matching for none -- the Pipeline column would empty out. That join has to change to match on
`ld2.lookup_type` in the same commit, and existing `source_task` rows holding ids need a one-off
`UPDATE ... SET pipeline_id = ld.lookup_type FROM lookup_data ld WHERE ...`. That is a real
migration and it is why this row is sized **M** rather than S. The same argument applies to
`home_page_id` and `group_id`, which have the identical id/label split -- but nothing keys off
those, so **leave them alone** rather than widening the change (see section 5).

**Addendum, 2026-09-07 -- what actually shipped, and why it is not the recommendation above.**

The instruction that landed this fix was not "pick a representation" -- it was to remove
`PIPELINE_IDS` from the lookup table entirely and have Source Task's Pipeline field read from
Task Forms instead, because "we all configure a pipeline with pipeline form" now. That is a fourth
option this section did not consider when it was written, and it is a better one than any of the
three above:

- **(a), this section's recommendation** (editor sends the label, `task_form` unchanged, existing
  rows migrated, list join changed to match on `lookup_type`) keeps a lookup family alive purely
  so a `<select>` has options, when a `TaskForm` row already exists for every real choice and
  already has to be created for the form to mean anything.
- **(b)** (migrate `task_form` to hold lookup ids) was already rejected above and stays rejected.
- **(c)** (try both representations) was already rejected above and stays rejected.
- **(d), what shipped:** delete the lookup family; `task_form.pipeline_id` -- unchanged in shape,
  a free-text string an admin types when creating a form -- becomes the **sole** catalogue of
  which pipelines exist; Source Task's Pipeline picker, in both frontends, reads that catalogue
  directly via a new `GET taskForm.json/listPipelines` (`TaskFormRestApi.java`, `TENANT_USER`, the
  same role `formForPipeline` already used and for the same reason); the option value **is** the
  pipeline's own id string, so there is no representation left to disagree about. See
  `platform-configuration`'s own documents for the lookup-removal side of this
  (`SettingServiceImpl.TENANT_OWNED_LOOKUPS`, migration `V28__drop_pipeline_ids_lookup.sql`) --
  that half is out of scope here and belongs to that feature.

(d) costs strictly less than (a): no data migration for `task_form` (its column never changes
shape), and the `QueryService.java:89` join's breakage (12.22 in the grooming document) is a
pre-existing display-only join going stale, not a new migration this change has to write -- it was
never touched, on the reasoning that it belongs to `source-jobs`'/`source-tasks`' shared
`QueryService` and fixing it is "drop the join, render the column directly" rather than anything
this pass needs to own. **No migration was written for existing `source_task.pipeline_id` values
still holding an old numeric id**, on the same "a task keeps running, it just stops resolving to a
name" precedent `platform-configuration`'s own `TENANT_OWNED_LOOKUPS` comment already establishes
for this exact class of change -- old tasks simply will not match a Pipeline Form until
re-pointed at one that exists. Whether that is acceptable for this codebase's real data was not
verified before the change shipped.

**A second scope change this addendum should name plainly:** the fix did not stop at the
representation. Removing the lookup also removed the last reason to keep a manually-editable
"Configuration tags" tag table on the task screen at all -- if a pipeline's payload is always
authored by its form, a parallel hand-editing surface for the same tags is not a fallback, it is a
second way to configure the same thing that can silently disagree with the first. That table
(rows, add/insert/remove, storage-tag highlighting, the bucket-help panel, and the "Show the
XML"/"Use as payload" preview) was removed in the same pass, and `save()` now generates the
payload from a pipeline form's own tags automatically rather than waiting for a manual preview
click -- which is gap 4 (§2, row 4), done as a forced consequence of this one rather than as
independent work. See grooming §12.7 for the full account and grooming §12.3/§4.3 for gap 4's
side of it.

### 3.4 Gaps 4, 5, 6 -- the validation rules that are enforced nowhere

All three are the same shape: the old app enforced them on the client only, and the rewrite dropped
the client half without anyone adding the server half.

**Payload required (4).** Add `Validators.required` to `taskPayload`. Better still, make Save
generate it: if the payload box is empty and there are tag rows, call `xmlCreateChecker` and use the
result. That removes a step operators currently have to remember, and it fixes the second-order
problem -- `bucket`/`input_folder`/`output_folder` are parsed from the **payload**, not the tags
(`TaskPayloadLocationUtil.java:48-65`), so a task with a `bucket` tag and a stale payload reports no
bucket at all. The alternative -- parse the tags on the server instead of the payload -- was
rejected because the payload is what the worker actually receives, so the derived columns should
describe the payload and not somebody's intent.

**Active-only task types (5).** One `.filter()` at `task-edit.ts:85`. Note the server already
enforces this; the client change is purely so the failure is prevented rather than reported.

**Tag key validation (6).** Client-side, port `noWhitespaceValidator` from
`task.component.ts:38-43` and re-add the "disable the XML button while a row is invalid" behaviour
(`task.component.html:206`). Server-side, add a check in `addSourceTask`/`updateSourceTask` against
the XML `Name` production before saving. Doing only the client half would repeat the mistake this
document is about: the endpoint is reachable from bulk import and from `submission-to-task-dialog`,
neither of which would run the validator.

### 3.5 Gaps 14, 19 -- tenancy, and why they are not fixed here

`tenantClause` returning `""` for a null tenant (`QueryService.java:213-215`) and
`enableIfNeeded` disabling the filter on the same condition (`TenantFilterHelper.java:28-33`) are
platform-wide: `QueryService` builds the SQL for jobs, the dashboard and the queue as well, and
`TenantFilterHelper` is injected into most services. Changing either of them from inside this
feature's work would change behaviour in features nobody is testing in the same pass.

**The correct shape of the fix.** This document previously specified a third and incompatible
version of it, and it was wrong; the version below is the one that holds across the whole project.

`QueryService.tenantClause` (`QueryService.java:212-217`) currently returns `""` — *no clause at
all* — for a platform admin **and** for a caller with no tenant, so the tenant-less caller reads
every row of every tenant. Three conditions are collapsed into two, and the fix is to separate them:

| Caller | Clause |
|---|---|
| `PLATFORM_ADMIN` | `""` — sees everything, by design |
| Any role, with a tenant | `and <alias>.tenant_id = :tenantId` |
| Any role, **no** tenant | `and 1 = 0` — **sees nothing** |

An earlier draft of this section said the tenant-less caller should get `tenant_id is null`, on the
reasoning that a null-tenant row is platform-owned and so is the natural thing for a caller with no
tenant to see. That reasoning is backwards. A row with a null tenant is platform-owned **and
therefore reserved to the platform admin** — `TenantOwnership.java:13-18` states it directly: such a
caller is *"refused outright rather than being compared equal to the tenant-less rows."* Giving it
`tenant_id is null` hands it exactly the platform's own records, which is the more valuable set.

`and 1 = 0` is also what `synthesis/dashboard.md`, `synthesis/job-runs-and-queue.md` and
`synthesis/dynamic-forms.md` specify, so all four documents now agree.

> **Owner.** `tenantClause`, `TenantFilterHelper.enableIfNeeded` and the per-service
> `isOwnedByCaller` copies are **one change with one owner**, and that owner is
> [`synthesis/authentication-and-access.md`](authentication-and-access.md). Four features defer to
> it and none of them should restate the fix — this section cites it rather than re-specifying it.
> Note in particular that the sentinel-parameter approach alone does **not** close the four
> shared-catalogue entities; that document names them. `isOwnedByCaller` (`SourceTaskServiceImpl.java:113-118`) needs the matching
guard: return `false` outright when `TenantContext.getTenantId()` is null and the caller is not a
platform admin, rather than letting `Objects.equals(null, null)` grant ownership.

Gap 19 (`TaskForm`'s unused filter) is the same argument in miniature: enabling it would change how
`findAllByFormStatusNot` behaves and the manual `removeIf` would become redundant, but `@FilterDef`
is registered globally under one name and the change is not local. Deleting the annotation and
keeping the hand-written scoping is the smaller, safer move, and it makes the code honest about
where the rule actually lives.

**What this feature should do instead:** write acceptance criterion 43 as a failing test, record the
cross-tenant leak, and hand it to whoever owns the platform-wide tenancy pass.

### 3.6 Gap 12 -- the form preview

`task-form-dialog.ts:323-341` builds a correct nested document. `XmlOutTagInfoUtil.makeXml` builds a
different one: the first row is the root and everything parentless goes inside it
(`:62-67, 91-96`). Two ways to close it.

- **Model the server's rule in the preview.** Cheap, no round trip, and the preview stays live as
  the author types. Rejected as the sole fix, because it creates a second implementation of the XML
  rule in the browser -- the exact thing `task-edit.ts:196-206` explains it is deliberately avoiding
  by asking the server.
- **Preview through `xmlCreateChecker`, debounced.** Recommended. The dialog is already an
  admin-only screen making requests, the endpoint exists and is already called from two other
  places, and it guarantees the preview and the document can never disagree. Cost: a request per
  edit burst, and a preview that is briefly stale.

Either way, `TaskFormValidationTest.parentMayComeLater` (`:119-126`) has to change. It currently
asserts that a form ordered `[tables under tenant, tenant at root]` is valid -- true by the
validator's rules, and misleading, because `makeXml` will make `<tables>` the root. The honest
version either adds a rule ("the first field must be the root") or renames the test to say that
ordering is not validated and the preview is where you will see the consequence.

### 3.7 Gap 7 -- clone status

`addSourceTask` at `SourceTaskServiceImpl.java:171` overwrites whatever the client sent. Honouring
`Active`/`Inactive` (and only those two) is three lines. The reason to be careful is that bulk
import goes through a different path (`:617`) which also hard-codes Active, and the two should not
drift -- either both honour an incoming status or the change is scoped explicitly to
`addSourceTask` and said so in a comment. Recommended: change `addSourceTask` only, and leave the
spreadsheet path alone, because the upload template has no status column
(`SourceTaskServiceImpl.java:139-141`) and there is nothing for it to honour.

---

## 4. Ordering

**Wave 0 -- unblock, in this order.**

1. **Gap 1 (paging).** Everything else is verified against a list, and today the list is a lie.
   Nothing can be acceptance-tested at scale until this lands. Unblocks criteria 1, 2, 8, 9 and the
   job editor's task picker in `source-jobs`.
2. **Gap 2 (tenant picker).** Unblocks every platform-admin criterion (24-27) and, with the same
   `tenantId`-in-the-DTO change, the platform-admin path in `bulk-transfer`.
3. **Gap 3 (pipelineId) -- done 2026-09-07.** Unblocked all six task-form criteria (32-37) and
   remains the prerequisite for ever counting how many tasks a form drives (Q6). Landed as
   described in this document's shipped ordering: backend (lookup removal, new endpoint) before
   either frontend, both frontends' Pipeline picker before the "Configuration tags" table removal,
   since removing the fallback before the replacement worked would have left no way to configure
   a task at all.

**Wave 1 -- correctness, once the list is real.** Gaps 4, 5, 6 (validation, client and server
together), 7 (clone status), 15 and 16 (the two delete/update holes). These are independent of one
another and can go in any order; 4 and 6 are worth doing in one commit because both touch
`task-edit.ts`'s form construction and both need a matching server rule.

**Wave 2 -- restore what was dropped.** Gaps 8, 9, 10, 18. All client-only, all independent. Gap 8's
payload search depends on gap 1 if it is done server-side, so either do it client-side first and
move it later, or sequence it after wave 0.

**Wave 3 -- the forms screen.** Gaps 11, 12, 13, 19. Independent of everything above except that
gap 3 must land first or none of it is observable.

**Wave 4 -- tests (gap 17) and the editor's failed-load state (gap 20).** Written last only because
the shapes they test are still moving; if `syncFormToTags` is going to be touched by gap 3, its spec
should be written in the same commit rather than after.

**Handed off, not scheduled here.** Gap 14. It is a platform-wide tenancy change and belongs to a
pass that can regression-test jobs, the dashboard and the queue at the same time. Write the failing
test, record it, move on.

---

## 5. Out of scope

- **The bulk import/export screen** (`tasks/bulk`, `downloadListSourceTask`,
  `downloadSourceTaskTemplate`, `uploadSourceTask`). It is feature 7, `bulk-transfer`, and has its
  own document. The one overlap -- a platform admin cannot upload either, for the same missing
  `tenantId` -- is named here so the two documents do not both quietly assume the other fixed it.
- **`home_page_id` and `group_id`'s id-versus-label split.** Identical in shape to gap 3 and
  identical in cause, but nothing keys off either value: they are displayed and never matched.
  Changing them would mean two more data migrations for no behavioural gain, and would make the
  gap 3 change harder to review. If a future feature ever keys on them, this decision should be
  revisited as one piece of work.
- **Server-side bulk actions on tasks.** The jobs list has bulk operations; the tasks list has never
  had them in either app. Adding them is new capability, not migration, and the old app's approach
  (N parallel requests from the browser) is already recorded as a mistake in
  `.ai/discovery/frontend-old.md` §12.13.
- **A `position` column on `source_task_payload`.** Tag order currently rides on the id sequence and
  survives only because every save deletes and re-inserts the whole set. That works today and the
  fix is a migration plus an `@OrderBy`; it belongs with any future work that makes tag updates
  incremental, not with this pass.
- **A read-only task detail page for `TENANT_USER`.** Genuinely missing in both apps, and worth
  building -- but it is new scope, and the expanded row plus gap 9's restored detail block covers
  most of the need.
- **Rewriting `SourceTaskServiceImpl.listSourceTask`'s 80-line index-counting result mapper**
  (`:296-370`). Ugly, and untouched by anything above. Rewriting it while also changing the SELECT
  for gap 3 would make the diff unreviewable.
- **`TagInfo.compareTo`'s broken comparator** (12.18). Real, but harmless while every
  `task_payload_id` is distinct and non-null, and the honest fix is the `position` column that is
  itself out of scope. Record it; do not touch it in this pass.

---

## 6. Open questions

Each needs a human decision. A recommendation follows every one.

**Q1. Which representation of `pipelineId` wins -- the lookup label or the lookup id?
Resolved 2026-09-07, by a human decision this document did not have as an option on the table.**
Options considered when this was written: (a) the editor sends the label, `task_form` is
unchanged, existing `source_task.pipeline_id` rows are migrated from ids to labels and the list's
join changes to match on `lookup_type`; (b) `task_form.pipeline_id` is migrated to hold lookup ids
and the forms screen offers a dropdown instead of free text; (c) `formForPipeline` accepts either
and tries both. Recommended then: **(a)**, on the reasoning that the label is the value the Python
worker routes on, it is what bulk-imported rows already hold, and it is what every comment and
placeholder in the code already assumed; (b) was rejected for making the form key an internal
surrogate with no meaning outside this database, (c) for hiding the inconsistency for the next
feature to trip over.

**What was actually decided: neither.** The instruction was to remove `PIPELINE_IDS` from the
lookup table outright and have Source Task read its pipeline list from Task Forms -- a fourth
option, "(d)", that dissolves the question rather than answering it: there is no lookup
representation left to pick between, because there is no lookup. See §3.3's addendum for the full
account, including why (d) costs less than (a) despite this document recommending against
touching the lookup at all. Kept here, not deleted, because the reasoning for (a) over (b)/(c) was
sound on its own terms and remains a fair record of what would have been built had the scope
stayed inside the question this document was asked to answer.

**Q2. Should the task payload be generated from the tags on save, or merely required?
Resolved 2026-09-07: (b), as recommended below -- see §3.3's addendum.** It shipped as a forced
consequence of Q1's resolution rather than as independent work: removing the "Configuration tags"
table removed the last chance for a human to press "Use as payload" by hand, so generating it
automatically stopped being optional.
Options: (a) add `Validators.required` and leave "Use as payload" a manual step; (b) generate it on
save whenever the box is empty; (c) generate it on save always, and make the payload box read-only.
**Recommendation: (b).** (a) leaves the derived `bucket`/`input_folder`/`output_folder` columns
wrong whenever somebody edits tags and forgets the button, which is the failure mode that made
`TaskPayloadLocationUtil` necessary in the first place. (c) is tempting and wrong: the payload is
free text on purpose, and there are tasks whose payload was hand-written and does not correspond to
any tag rows -- making the box read-only would strand them.

**Q3. Is a `TENANT_ADMIN` or `TENANT_USER` with a null `tenant_id` a state the system permits?**
Not verified in this pass -- the tenant id comes straight from the JWT
(`JwtAuthenticationFilter.java:40`) and whether `app_user` allows such a row is
`tenants-and-users`' question. It matters because if it is possible, `listSourceTask` returns every
tenant's tasks to that session (12.16).
**Recommendation: fix the code regardless, and treat "it cannot happen" as unverified.** The fix
is small and local (`tenantClause`, `enableIfNeeded`, `isOwnedByCaller` each need to separate
"platform admin" from "no tenant"), and relying on a data invariant nobody has checked is how a
tenancy leak survives a rewrite. Schedule it with the platform-wide tenancy pass, not here.

**Q4. Should the form dialog's preview call the server, or model the server's rule in the browser?**
Options: (a) debounced `xmlCreateChecker` call; (b) reimplement `makeXml`'s ordering rule in the
preview computed.
**Recommendation: (a).** `task-edit.ts:196-206` already argues this case for the task editor -- a
second implementation drifts, and the nesting rules are more intricate than they look. The dialog is
admin-only and already makes requests; a debounce is cheaper than a divergence.

**Q5. Should `addSourceTask` honour an incoming `taskStatus`, and should bulk import do the same?**
Options: (a) honour `Active`/`Inactive` on `addSourceTask` only; (b) honour it on both paths;
(c) leave both hard-coded and change `tasks.ts` to stop claiming the clone is inactive.
**Recommendation: (a).** A clone genuinely should land inactive -- that is the whole reason
`tasks.ts:155` asks for it. (b) has nothing to honour: the upload template has five columns and none
of them is status (`SourceTaskServiceImpl.java:139-141`). (c) is the cheapest and the worst: it
keeps a copy live before anyone has checked it.

**Q6. Do task forms want a "which tasks use this form" count on the forms list?**
It is the obvious next question once forms actually work, and it is one join through
`source_task.pipeline_id` -- which cannot be written until Q1 is settled.
**Recommendation: defer, and revisit once Q1 has landed and real forms exist.** Building it now
means writing the join twice.

**Q7. Should the "Delete" option be removed from `Status` on the server as well as the client?**
The new editor offers only Active and Inactive, but `updateSourceTask` still writes whatever arrives
(`:244-246`), which skips the live-job guard and the job cascade.
**Recommendation: reject `Delete` in `updateSourceTask` with a message naming `deleteSourceTask`.**
Deleting through the update path was possible in the old UI, so some tasks may already be in that
state with live jobs pointing at them -- worth a one-off query to find out before the change lands,
because after it those rows can no longer be created but the existing ones still need explaining.

---

## 7. Landed since this synthesis (2026-09-18)

**A pipeline belongs to a topic.** `task_form` became `pipeline` (V43) with a required
`source_task_type_id`; the task editor picks the topic first and offers only that topic's
pipelines (`pipelinesForTopic` in `features/tasks/edit/task-edit.ts`), clearing a pipeline the
new topic does not carry; the Source Tasks list filters by topic then pipeline. The
`Pipeline` picker's catalogue is `pipeline.json/listPipelines` (the whole caller's set, filtered
client-side by topic) -- `listForTopic` exists server-side for a future server-filtered picker.

