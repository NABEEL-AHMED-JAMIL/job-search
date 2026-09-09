# Synthesis -- Bulk Transfer

Paired with `.ai/grooming/bulk-transfer.md`. Paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`. "KI-n" refers to that document's §12.

---

## 1. Summary

Bulk Transfer migrated as a shape and lost its substance. The new page
(`scheduler1/next/src/app/features/bulk/bulk-transfer.ts`) is a better *upload widget* than the one
it replaces -- it validates the file before sending, holds it for confirmation, shows real progress,
and honours the server's filename -- and a worse *bulk import tool*, because it discards the two
things that made the old screen usable: the list of which rows failed, and the tenant question a
Platform Admin has to answer. The row list is thrown away in the client while the server is still
sending it, and the tenant part is simply never assembled, which means platform-admin task import in
the new console does not work at all -- it parses the whole file and then refuses. Underneath both
apps, the backend has one real vulnerability specific to this feature (an unhardened XML parser on
the task-payload cell, sitting one file away from the hardened parser the same request uses later),
two crash-instead-of-report paths where a spreadsheet cell is passed straight to `Long.valueOf`,
non-atomic writes on both importers, and a bulk job path that skips two of the rules its single-record
sibling enforces. The work therefore falls into three bands: restore what the rewrite dropped (a
frontend job, small), fix what was always broken (a backend job, mostly small edits in two files),
and close the gaps neither app ever had (dry run, day-of-week rules -- optional, and the honest place
to stop). There are no tests on this feature at any tier, so every fix below needs the test written
with it.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | New app sends only the `file` part; a Platform Admin's task import is refused by the server after the whole file is parsed (`bulk-transfer.ts:110-111`; `SourceTaskServiceImpl.java:96-98, 603-607`) | A Platform Admin picks the owning tenant, and cannot upload until they have | The tenant picker the old app had (`batch-action.component.ts:67-69, 113-116`) was not carried over | Add a `tenants` signal loaded from `tenant.json/listTenants`, a `<select>` rendered when `isPlatformAdmin() && kind()==='task'`, `Upload` disabled until it is set, and the id appended as a `tenantId` part | S | Low |
| 2 | A failed import shows only `"Total N source jobs invalid."`; the `data` array of row errors is dropped (`bulk-transfer.ts:125-129`) | Every failing row is listed with its number and reason | The old Row/Error table (`batch-action.component.html:102-117`) has no successor | Widen the `result` signal to carry `rows: string[]`, populate from `response.data`, render a Row / Message table under the result card, splitting on `<br>` into text nodes | S | Low |
| 3 | Nothing on the page says whose records an import creates or an export contains; the export button asserts "Everything in your tenant", which is wrong for a Platform Admin (`bulk-transfer.html:92-94`) | A one-line banner stating the real scope for this role and this kind | The old app's three-variant notice (`batch-action.component.html:12-26`) was dropped | Add a banner above the card grid, three states off `auth.isPlatformAdmin()` and `kind()`; correct the export button's sub-label to match | S | Low |
| 4 | `SourceTaskValidation.parseXmlToRequest` parses a user-supplied cell with an unhardened `DocumentBuilderFactory` (`util/validation/SourceTaskValidation.java:136-145`) | External entities and DOCTYPEs are refused | XXE reachable by any TENANT_ADMIN through task import | Set `disallow-doctype-decl` (and the two external-entity features, and `setXIncludeAware(false)`) exactly as `util/TaskPayloadLocationUtil.java:53-54` already does | S | Low |
| 5 | `Long.valueOf` on a raw cell throws to the controller catch; the operator gets "contact support" (`SourceJobBulkServiceImpl.java:207`, `SourceTaskServiceImpl.java:581`) | A non-numeric id is a row error naming the row | Numeric form is validated nowhere | Parse with `ProcessUtil.parseLongOrNull` (already exists, `ProcessUtil.java:47-56`) inside the per-row validators and set an error message on null | S | Low |
| 6 | Neither importer is `@Transactional`; a failure part-way through the save loop leaves the file half applied (`SourceJobBulkServiceImpl.java:144`, `SourceTaskServiceImpl.java:527`) | All rows or none | Missing annotation, where the single-record siblings have it | Add `@Transactional` to both methods | S | Medium |
| 7 | Bulk job creation skips the "task has no owning tenant" refusal and `validateAssignee`, and hardcodes `Execution.Auto` (`SourceJobBulkServiceImpl.java:228-234`) | Bulk and single-record creation obey the same rules | Two write paths into `source_job` that disagree | Add the null-tenant refusal as a row error; call the same assignee check; leave `Auto` hardcoded and say so in the template guide | M | Medium |
| 8 | Client accepts `.xls`, server never does (`bulk-transfer.ts:92-96` vs `ProcessUtil.java:24`) | One answer, given by the browser first | Client and server disagree about the accepted format | Drop `.xls` from `accept()`, the `accept` attribute and the caption; add a size ceiling in the same place | S | Low |
| 9 | `getContentType()` dereferenced without a null check (`SourceJobBulkServiceImpl.java:146`, `SourceTaskServiceImpl.java:530`) | A missing content type is refused with the same message as a wrong one | NPE → generic 400/500 | Null-safe comparison | S | Low |
| 10 | Back is `Location.back()` and does nothing from a fresh tab; `ROUTES.backTo` is declared and unread (`bulk-transfer.ts:24, 31, 65-67`) | Back always returns to the list the page belongs to | Regression from the old explicit target | `routerLink` to `config().backTo`; add the breadcrumb the old page had | S | Low |
| 11 | Template and export download with the same `BatchDownload-<date>-<uuid>.xlsx` name (`SourceJobRestApi.java:196, 210`; `SourceTaskRestApi.java:136, 150`) | Four distinguishable filenames | Server names them all identically; the new client faithfully reproduces that | Change the four server-side filename prefixes to `job-template-` / `job-export-` / `task-template-` / `task-export-` | S | Low |
| 12 | Exports cannot be re-imported, and the page's copy implies they can (`bulk-transfer.html:20-22, 68-71`; KI-9) | The page does not promise a round trip it cannot deliver | Copy overstates; the underlying asymmetry is by design | Reword both cards to name the template as the only importable file. Do **not** attempt to make the export round-trip -- see §5 | S | Low |
| 13 | A job whose task row is missing NPEs the whole export (`SourceJobBulkServiceImpl.java:110`) | One bad row does not take the file down | Unguarded dereference on a nullable association | Null-guard the two task cells, writing `""` | S | Low |
| 14 | Export is `findAll()` plus one scheduler query per job (`SourceJobBulkServiceImpl.java:95-97, 116`) | One query, as the task export already does | N+1 over an unpaged read | Batch the scheduler lookup by `jobId in (…)` into a map before the loop | M | Medium |
| 15 | 500 MB multipart ceiling; the row cap is checked after the workbook is fully in memory (`application.properties:40-41`) | A file too large to be a legitimate import is refused before it is parsed | No per-endpoint size limit | Client-side ceiling (gap 8) plus a `getSize()` check before `new XSSFWorkbook(...)` | S | Low |
| 16 | No tests anywhere on this feature | The tenancy decisions and the row validators are covered | Zero coverage on the only two write paths that create jobs and tasks in bulk | Unit tests for `JobDetailValidation`, `SourceTaskValidation`, `resolveTenantIdForCreate` and `isSourceTaskTypeVisibleToCaller`; a component spec for `BulkTransfer` | M | Low |
| 17 | Weekly/monthly bulk jobs cannot name their days; `Manual` execution and task `groupId` have no columns | Bulk creation reaches the same fields the forms do | Template columns that were never added | Two new template columns and two mapping lines for the scheduler; one for `groupId` | M | Medium |
| 18 | No way to check a file without importing it | An operator can validate first | Never built, though the server already computes it | `validateOnly` flag on both upload endpoints, returning the same error envelope and skipping the save loop | M | Low |
| 19 | "Job Name must be unique" is documented in the bundled template and enforced nowhere (KI-10) | Documentation and behaviour agree | Stale guidance | Delete the claim from the template's `Scheduler-Detail` sheet. Do **not** add the constraint -- see §6, Q3 | S | Low |

---

## 3. Solution detail

### Gap 1 -- the tenant picker

**Change.** `scheduler1/next/src/app/features/bulk/bulk-transfer.ts`: inject `AuthService`; add
`tenants = signal<Tenant[]>([])`, `tenantsLoading = signal(false)`,
`selectedTenantId = signal<number | null>(null)`, and a computed
`needsTenant = computed(() => this.kind() === 'task' && this.auth.isPlatformAdmin())`. Load the list
in a constructor `effect` (or `ngOnInit`) guarded on `needsTenant()`, from
`GET ${API_BASE}/tenant.json/listTenants` -- the same call `features/admin/users/users.ts:247`
already makes. In `upload()`, append the part when `needsTenant()` is true, and return early with a
toast if it is unset. In `bulk-transfer.html`, add the select above the dropzone inside the Import
card, and bind `[disabled]="needsTenant() && !selectedTenantId()"` on the Upload button.

**Why this and not the alternative.** The alternative considered was fixing it on the server: make
`resolveTenantIdForCreate` fall back to something for a platform admin rather than refusing. There is
nothing correct to fall back to. A platform admin belongs to no tenant, a task must belong to one
(`SourceTask.tenant_id` is what every read filters on), and the server cannot guess. `addSourceTask`
already made this decision explicitly and the shared helper enforces it for both paths
(`SourceTaskServiceImpl.java:91-104`) -- weakening it to make one client work would open a hole on
the other. The question genuinely belongs to the person uploading, which is exactly where the old app
put it. A second alternative -- a `tenantId` column in the spreadsheet, so one file could seed several
tenants -- was rejected because it moves an authorization input into user-supplied file content, and
because it would need per-row `existsById` checks and a per-row refusal path that does not exist
today. One tenant per upload matches both the old behaviour and the server's current contract.

Note that `features/tasks/edit/task-edit.ts:407-418` has the identical omission on
`addSourceTask`. That is feature 6's row, not this one, but whoever picks this up should say so in
their PR so the two are not fixed twice in two different ways -- the `AuthService`-driven select
built here is the pattern the task editor should reuse.

### Gap 2 -- the row-error table

**Change.** Widen the result signal to
`signal<{ ok: boolean; message: string; rows: string[] } | null>(null)`. In the `HttpEventType.Response`
branch, when `!ok`, set `rows` from `Array.isArray(response.data) ? response.data as string[] : []`.
Render a table beneath the result card, one row per entry, numbered by position -- which is what the
old app did (`batch-action.component.html:111-114`), and is honest: the server's strings carry the
real spreadsheet row number inside the message text, so the index column is a counter, not a claim
about the file.

**Why not `[innerHTML]`.** The old app bound the message with `[innerHTML]`
(`batch-action.component.html:113`) because the server separates multiple problems on one row with
`<br>` (`JobDetailValidation.java:163` and every sibling). Today those strings are composed from row
numbers and fixed vocabularies and echo no cell content, so the binding is currently safe. It is safe
by accident: the moment someone adds `"Task name '" + taskName + "' is…"` to a validator, the same
binding renders attacker-supplied markup, and Angular's sanitizer is a mitigation, not a design.
Splitting on `/<br\s*\/?>/i` and rendering each fragment as a text node costs one line and removes
the class of bug entirely. It also renders correctly if the server later stops emitting `<br>`.

### Gap 3 -- the scope banner

**Change.** One `<p>` in a `.card` above the two-column grid, three states, driven by
`auth.isPlatformAdmin()` and `kind()` -- the same three cases the old markup had
(`batch-action.component.html:12-26`), reworded for the new voice. Separately, fix
`bulk-transfer.html:92-94`, which currently tells a platform admin their export covers "your tenant"
when `SourceJobBulkServiceImpl.java:95-97` and `SourceTaskServiceImpl.java:484-486` both give them
every tenant.

**Why a banner rather than tooltips or help text on each control.** The scoping rule is one fact
about the whole page -- who owns what happens here -- not three facts about three buttons. Splitting
it across the controls is how the current page ended up with one control asserting something false.

### Gap 4 -- the XML parser

**Change.** In `util/validation/SourceTaskValidation.java:136-145`, before `newDocumentBuilder()`:

```java
factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
factory.setXIncludeAware(false);
factory.setExpandEntityReferences(false);
```

A `ParserConfigurationException` from any of these is already inside the caller's try/catch
(`:127-133`), which turns it into *"Task payload not valid at row N"* -- an acceptable failure for a
parser that cannot be secured.

**Why here and not a shared hardened factory.** A shared factory is the better end state and the
wrong first move. There are three `DocumentBuilderFactory.newInstance()` sites in the backend
(`util/XmlOutTagInfoUtil.java:43`, `util/TaskPayloadLocationUtil.java:53`,
`util/validation/SourceTaskValidation.java:138`) and only one of them is mine; extracting a utility
means touching the setting screen's XML preview, which is feature 15. Fix the reachable hole in the
file that owns it, and leave a note for whoever consolidates. The shape to copy is literally three
lines away in `TaskPayloadLocationUtil`, so there is no design question -- only a scope one.

**Why this is a blocker and not a "harden later".** `SourceTaskValidation` has exactly one caller
(`SourceTaskServiceImpl.java:33, 547, 564`), and it runs at `:592` -- *before* the hardened parser at
`:619` sees the same string. Any TENANT_ADMIN can reach it with a spreadsheet.

### Gap 5 -- numeric ids

**Change.** In `JobDetailValidation.isValidJobDetail()`, after the presence check on `taskId`
(`:165-167`), add a numeric check using the existing `ProcessUtil.parseLongOrNull`
(`util/ProcessUtil.java:47-56`), setting *"TaskId must be a number at row N"* on failure. Same for
`sourceTaskTypeId` in `SourceTaskValidation.isValidSourceTask()` (`:118-120`). Then change the two
call sites (`SourceJobBulkServiceImpl.java:207`, `SourceTaskServiceImpl.java:581, 618`) to use the
parsed value.

**Why validate rather than catch.** Wrapping the two `Long.valueOf` calls in a try/catch would stop
the 400 and still give a message that names no row, because the exception is thrown outside the
per-row loop's error accumulator in the job case. Validating puts the failure where every other row
failure already goes, which is the only place the operator will look. This also matters more than it
sounds: the job export writes the task column as `"%d [%s]"` (`SourceJobBulkServiceImpl.java:110`), so
`1042 [Nightly load]` pasted from an export is the *expected* accident, not an exotic one.

### Gap 6 -- transactions

**Change.** `@Transactional` on `SourceJobBulkServiceImpl.uploadSourceJob` and
`SourceTaskServiceImpl.uploadSourceTask`.

**Why the risk is Medium.** Both methods currently flush per row --
`TransactionServiceImpl.saveOrUpdateJob` calls `saveAndFlush` (`:133-135`) -- so a 1000-row import
becomes one transaction holding 2000 inserts. That is the correct semantics and a real change in
locking behaviour under the 1000-row cap. It wants a load check against a full-size file before it
ships, and it is the one item on this list I would not merge without one.

**Why not a batch-and-commit-every-N compromise.** That gives partial imports on purpose, which is
the thing being fixed, and leaves the operator with a message ("Total 1000 jobs saved") that is
sometimes a lie. If the single transaction proves too heavy, the honest fallback is to lower the row
cap, not to loosen atomicity.

### Gap 7 -- aligning the two job-creation paths

**Change.** In `SourceJobBulkServiceImpl.java` around `:221-235`: after resolving `linkedTask`, if
`linkedTask.getTenantId()` is null, record a row error mirroring `addSourceJob`'s wording
(`SourceJobServiceImpl.java:135-137`) instead of copying the null into `sourceJob.setTenantId(...)`.
Call the same assignee validation the single path uses (`:140-143`) -- currently
`validateAssignee` is private on `SourceJobServiceImpl`, so this means either promoting it or moving
both callers onto a shared helper.

**Why not extract the whole of `addSourceJob` and have the importer call it row by row.** That was
the first idea and it is wrong here. `addSourceJob` takes a `SourceJobDto`, returns a `ResponseDto`
per call, and raises a notification per job (`:157`); driving it from a loop would produce 1000
notifications and 1000 envelopes to reconcile, and would move the bulk path's carefully separated
validate-then-save shape into a save-as-you-go one -- undoing gap 6. Sharing the *rules* rather than
the *method* keeps both properties. The rules worth sharing are small: two checks.

**On `Execution.Auto`.** Leave it hardcoded (`:234`) and fix the documentation instead. A `Manual`
job has no schedule, and the template's every scheduling column is mandatory; adding an Execution
column means adding a conditional-requirement rule across six other columns, which is gap 17
territory and not worth it to satisfy a symmetry argument.

### Gap 10 -- Back

**Change.** Replace the `back()` method and its button with an `<a [routerLink]="config().backTo">`.
`backTo` is already in the config table and currently read by nothing
(`bulk-transfer.ts:24, 31`). Add the breadcrumb the old page had -- `Jobs / Bulk import` -- which is
the cheapest way to make a deep-linked page say where it sits.

**Why not keep `Location.back()` with a fallback.** "History if there is one, route otherwise" needs
the component to know whether the navigation had a predecessor inside the app, which Angular does not
hand you cleanly. The route target is right in every case a user can reach: this page has exactly two
callers and both are the list it points at.

### Gap 14 -- the export N+1

**Change.** Add `List<Scheduler> findByJobIdIn(Collection<Long> jobIds)` to `SchedulerRepository`,
build a `Map<Long, Scheduler>` once before the `forEach`, and read from it inside
(`SourceJobBulkServiceImpl.java:106-137`).

**Why not switch the whole export to a native projection like the task one.** The task export's
single-query shape (`SourceTaskRepository.java:36-43`) is the better design, and converting the job
export to match would mean writing a 15-column native join across `source_job`, `source_task` and
`scheduler`, plus a new projection interface, plus re-deriving the three boolean columns and the
`"%d [%s]"` formatting in SQL. That is a rewrite of a working export to fix a performance problem
nobody has reported, and it would land in the same file as gaps 7 and 13. Two queries instead of
N+1 gets most of the benefit for a tenth of the change; the native rewrite can happen when someone
has a slow export in front of them.

---

## 4. Ordering

**First, and independently of everything else -- gap 4 (XXE).** It is three lines in a file nothing
else on this list touches, it is the only item with a security consequence, and it blocks nothing.
Ship it on its own so it is not held up by anything below.

**Then the backend correctness band: gaps 5, 9, 13, 6.** In that order. 5 and 9 are contained edits
to the two upload methods and the two validators; 13 is one null guard in the export. 6 goes last of
the four because it is the one that needs a load check, and because doing it after 5 means the
transaction is wrapping a save loop that can no longer throw a `NumberFormatException` mid-flight --
which is precisely the failure that makes non-atomicity visible today. **Gap 6 unblocks acceptance
criterion 32**, and criterion 24 depends on gap 5.

**Then gap 7**, which sits in the same file as 13 and 6 and should follow them rather than collide
with them. It needs a decision on `validateAssignee`'s visibility first (§6, Q1).

**Then the frontend restoration band: gaps 3, 2, 1.** 3 first, because the banner is where the
tenant question is announced and it establishes the `auth`/`kind` branching the picker reuses. 2
second, because it is self-contained and is the highest-value single change on the list -- a failed
import stops being a dead end. **1 last of the three, and it depends on 3** for the wording and on
the `AuthService` injection 3 introduces. Gap 1 unblocks criteria 39-42; gap 2 unblocks 22 and 24;
gap 3 unblocks 7-9.

**Then the small alignment items, in any order: 8, 10, 11, 12, 15.** None blocks another. 8 and 15
are the same edit to `accept()` and should be one commit. 11 is server-side and touches two
controllers that nothing else on this list touches.

**Then gap 16 (tests).** Listed here rather than first because half of these fixes change the
behaviour a test would assert, and writing the suite twice is worse than writing it once. In
practice each fix above lands with its own test and this item is the sweep for what is left --
particularly `resolveTenantIdForCreate` and `isSourceTaskTypeVisibleToCaller` on the bulk path, which
`SourceTaskServiceImplTenantIsolationTest` covers only for the single-record path (`:111-187`).

**Last, and only if there is appetite: gaps 17, 18, 19.** 19 is trivial and can go any time. 18 (dry
run) is the one genuinely new capability worth building and it depends on nothing above except gap 6,
whose validate-then-save separation it reuses. 17 is a template change, and a template change means
regenerating `process/src/main/resources/Scheduler.xlsx`, which is a binary in the repository -- see
§6, Q2.

---

## 5. Out of scope

**Making the export round-trip into the importer (KI-9).** The export and the template answer
different questions -- "what exists" versus "what may be created" -- and only the second has a
sensible column set for an insert-only importer. Making them the same file means either dropping
columns from the export (losing information operators use for reporting) or teaching the importer to
skip columns it will not write (an implicit contract that breaks the moment a column is added). The
right fix for the confusion is gap 12, which is copy. A real round trip belongs with bulk *update*,
below.

**Bulk update and bulk delete.** Every row of every import is an insert today. Update needs an id
column, an update-or-insert branch, per-row ownership checks on the update side, and a decision about
what a blank cell means -- "leave alone" or "clear". That is a feature, not a fix, and it should be
groomed on its own rather than smuggled in behind "the export should import".

**The job export's native-query rewrite.** Rejected in §3, gap 14. Two queries, not one, for now.

**A unique constraint on `source_job.job_name`.** See §6, Q3 -- the recommendation is to delete the
claim rather than build the rule.

**Fixing the same missing-`tenantId` bug in the task editor**
(`features/tasks/edit/task-edit.ts:407-418`). Same root cause, different feature row (6
`source-tasks`). Named in gap 1 so the two fixes agree; not done here.

**Consolidating the three `DocumentBuilderFactory` sites into one hardened factory.** Two of the
three belong to other features. Gap 4 hardens the one that is mine and leaves a note.

**Run selected / Delete selected on the jobs list.** Both apps have them
(`scheduler1/src/app/_component/source-job/source-job.component.ts:370, 411`;
`scheduler1/next/src/app/features/jobs/jobs.html:96-107`), and despite the word "bulk" they belong to
feature 3 `source-jobs` -- they act on rows already on screen, share no endpoint with this feature,
and `.ai/discovery/features.md` §4 assigns `jobList` / `jobs` to row 3.

**Anything about the `BATCH_DONE` notification.** It works: the stale `/jobList` and `/taskList`
links the server stores (`SourceJobBulkServiceImpl.java:252`, `SourceTaskServiceImpl.java:632`) are
rewritten by `features/notifications/notification-links.ts:11-12`, which has a test
(`notification-links.spec.ts:5-11`). Leave it.

---

## 6. Open questions

**Q1 -- How should the bulk job path reuse `validateAssignee`?**
It is currently private on `SourceJobServiceImpl` and gap 7 needs it in `SourceJobBulkServiceImpl`.
Options: (a) make it package-private and inject `SourceJobServiceImpl` into the bulk service;
(b) move it and the null-tenant check into `TransactionServiceImpl`, which both services already
depend on; (c) copy the two checks into the bulk service.
**Recommendation: (b).** `TransactionServiceImpl` is already the shared surface between these two
services -- `findByTaskDetailIdAndTaskStatus` (`:191-194`) is exactly this kind of shared rule and
already lives there -- so the checks land next to their neighbours rather than creating a new
dependency edge between two service implementations. (c) guarantees the two copies drift, which is
how this gap arose.

**Q2 -- Gap 17 needs new columns in `Scheduler.xlsx`. Who regenerates the binary, and does the
importer stay strict?**
The template is a checked-in `.xlsx` (`process/src/main/resources/Scheduler.xlsx`) and the importer
compares the header row cell-for-cell against `ProcessUtil.HEADER_FILED_BATCH_FILE`
(`SourceJobBulkServiceImpl.java:167-174`), so adding a column invalidates every spreadsheet already
in circulation on the day it ships. Options: (a) strict as now -- new template, old files rejected;
(b) accept either header length, mapping by heading name rather than position; (c) build the template
in code like the task one does (`SourceTaskServiceImpl.java:514-525`) and drop the binary.
**Recommendation: (b), and treat (c) as the eventual destination.** Mapping by name rather than by
index is a small change to the header loop, it makes column order irrelevant, and it means gap 17
does not break anyone's saved file. (c) is right in the long run -- a binary that must be opened in
Excel to review is a bad thing to have in a repository -- but it means re-authoring the
`Scheduler-Detail` guide sheet in POI, which is a day of fiddly work for no user-visible gain, and it
should not be the price of adding two columns.

**Q3 -- "Job Name must be unique": enforce it or delete the claim?**
The bundled template asserts it (`Scheduler-Detail`, row 2) and nothing enforces it.
Options: (a) add a per-tenant unique constraint and a duplicate check in both create paths; (b)
delete the sentence.
**Recommendation: (b).** `source_job.job_name` is `length = 1000` (`SourceJob.java:75-77`), which is
too wide for a plain unique index on MySQL's default charset -- it needs a prefix index or a column
narrowing, which is a migration against live data. More to the point, nothing in the application
treats the name as an identifier: jobs are addressed by `jobId` everywhere, and duplicate names have
presumably existed for as long as the feature has. Enforcing it now would break existing imports to
satisfy a sentence in a spreadsheet nobody has complained about. Delete the sentence; if uniqueness
is genuinely wanted later, it is a `source-jobs` decision, not a bulk-import one.

**Q4 -- Should the 1000-row cap stay at 1000 once gap 6 makes the import one transaction?**
The cap is checked with an off-by-one against its own message (KI-19) and was chosen when each row
committed independently. Options: (a) keep 1000 and fix the off-by-one; (b) lower it -- 250 or 500 --
and keep the transaction comfortable; (c) raise it and stream.
**Recommendation: (a), then measure.** Fix `> 1001` to `> 1000` so the message is true, ship gap 6,
and time a full-size import against a realistic database. If a 1000-row transaction proves painful,
lower the cap -- that is a one-constant change and it keeps the atomicity guarantee, which is the
property worth protecting. (c) is premature: nobody has asked for more than 1000.

**Q5 -- Should the row-error table be paginated?**
A 1000-row file with every row wrong produces 1000 messages, and gap 2 renders all of them.
Options: (a) render everything, let the container scroll; (b) show the first 50 with a "and N more";
(c) show everything plus a "copy all" button.
**Recommendation: (c).** Truncation is exactly the behaviour the old app avoided and the reason this
gap is worth fixing at all -- an operator with 200 bad rows needs all 200, not the first 50. A
`max-height` with an internal scroll handles the layout, and a copy-to-clipboard button turns the
list into something that can be pasted beside the spreadsheet while it is being fixed. It also costs
about six lines more than (a).
