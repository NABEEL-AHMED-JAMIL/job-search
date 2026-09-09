# Synthesis -- PDF Highlighter

Companion to `.ai/grooming/pdf-highlighter.md`. All paths relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

---

> **DECISION (2026-09-07): removed, not migrated.** Everything below this line is this
> document's own analysis and recommendation ("Migrate it") and is kept as the historical
> record of that reasoning -- it was not silently overridden. The product owner made the
> opposite call explicitly, after being shown this document's argument (the `job-search`
> ETL dependency on the editor's selector-grammar output) and a follow-up finding that
> `pdf_highlighter_f768925.py` calls `http://localhost:9999/...`, a port/URL shape that
> matches nothing this repo actually serves -- meaning that dependency's real, current
> health could not be confirmed one way or the other from this repo alone. Removed: both
> DB tables (`process/.../db/changelog/yaml/V29.0-drop-pdf-highlighter.yaml`), the 11
> dedicated backend Java files plus a `TenantSeedService` edit, and the legacy
> `scheduler1/src` screen, service, models and routes. The `job-search/etl/tasks/
> pdf_highlighter_f768925.py`/`pdf_highligter_form_fill_F768924.py` pair and their
> `source_task_type`/pipeline-id dispatch were deliberately left untouched -- this
> migration removed only the authoring UI and its own tables, not that ETL pipeline pair,
> which is a separate, larger decision this change does not make. See
> `.ai/execution/README.md`'s progress log for the full change list.

## 1. Summary

**Migrate it.** This is the migration's only whole-feature gap and the one item that decides when
the old Angular app can be switched off (`.ai/execution/README.md:40`), and the case for building
it is stronger than the route list suggests: the capability at stake is not "a screen for looking at
PDFs", it is *the only tool that exists for authoring a field mapping*, and the thing that consumes
a field mapping is in this repository, routed and seeded. `job-search/etl/tasks/pdf_highlighter_f768925.py`
parses the editor's selector grammar with a regex that matches the editor's output string character
for character (`:36` against
`scheduler1/src/app/_component/pdf-highlighter/pdf-highlighter-detail/pdf-highlighter-detail.component.ts:434`),
reads six field keys by the names the editor emits (`:251-270`), and feeds
`job-search/etl/tasks/pdf_highligter_form_fill_F768924.py`. Both are dispatched by pipeline id at
`job-search/etl/tpd/tpd_scrapping_listener.py:139-144` and seeded into `PIPELINE_IDS` and
`source_task_type` 1011 at
`process/src/main/resources/db/changelog/changelog-sets/V10.0-fix-task-types-pipelines/V10__fix_source_task_type_and_pipeline_ids.sql:27-31`, `:41-47`.
Drop the screen and those two pipelines have no authoring tool; the mapping would have to be written
by hand, one `x`/`y`/`width`/`height` quadruple and one `page[n]/text()[a:b]` index pair at a time,
against a PDF nobody can see while typing.

The backend does not need rebuilding. Nine endpoints, two entities and two tables are complete,
tenant-filtered and live, and Discovery records the two commits that extended them --
`86c2269 PDF Highlighter` and `4c07a7a pdf highlighter xpath added` -- as the most recent on the
branch while the rewrite was running (`.ai/discovery/features.md:107-109`). That history is **not
re-verifiable from this checkout**: `Old-School` holds one squashed commit, `5e8dbe7 first commit`,
and the hashes belong to the sibling `io-frontend` working copy, where a third commit now sits on
top of both. Take it as Discovery's finding, not as this document's. What the
work is, then, is: **rebuild two screens in `scheduler1/next`, and repair eleven defects that the
old app shipped with** -- among them a save that reports success when it failed, a "Remove" button
that removes nothing, a field-label counter that restarts at 1 and silently collapses two columns
into one in the extract, four NOT NULL columns reachable with nulls from four number inputs, and a
copy of the tenant-ownership rule that hands a tenant-less caller every tenant's tasks.

One thing is deliberately **not** in this plan, and it is the largest open question: the pipeline
fetches its mapping from `http://localhost:9999/v1/api/organizations/{uuid}/pdf-highlighters/by-name/{name}`
(`job-search/etl/util/xml_parser.py:77`), expects an envelope of `{task:{uuid}, fields:[...]}`
(`pdf_highlighter_f768925.py:146`, `:172-176`), and reads its input PDFs from `highlighter/input/<name>`
rather than the `pdf-highlighter/<taskId>/` prefix the console writes to. `process` serves none of
that shape and has no `uuid` column, and whatever answers on port 9999 is not in this repository --
`service-3` runs on 9099 (`service-3/src/main/resources/application.properties:1`) and has no such
surface. Until somebody says what serves 9999, the console is an authoring tool whose output leaves
by the Copy and Download JSON buttons. Build it to that reality, and treat wiring it up as a separate,
small, testable change (Q1).

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | No route, component, service or model for this feature anywhere in `scheduler1/next/src` (case-insensitive grep for `highlighter` returns zero files); nav has no entry (`features/shell/shell.ts:71-88`) | Three routes under `tools/pdf-highlighter`, a list, a canvas editor, a nine-method service | The only tool for authoring a mapping exists solely in the app being retired | Build `features/tools/pdf-highlighter/` on the shared UI kit; split the pdf.js bootstrap out of `features/objects/preview/pdf-viewer.ts` into a shared helper | **L** | **Medium** -- the canvas editor is real work, and the selector grammar must not drift |
| 2 | `pdfjs-dist ^2.16.105` with a checked-in worker (`scheduler1/package.json:31`, `src/assets/pdf.worker.min.js`) vs `^6.2.108` resolved through the bundler (`scheduler1/next/package.json:28`) | The editor runs on 6.x and produces byte-identical selector strings | `buildSelector`'s indices come from pdf.js's own text-item list (`pdf-highlighter-detail.component.ts:394-408`); a change in what 6.x calls an item silently changes every stored selector's meaning | Pin the grammar with a unit test on a fixture PDF, run it against both versions before porting anything else | M | **High** -- a silent, data-level regression with a running consumer downstream |
| 3 | `isOwnedByCaller` is a private copy without the null-caller clause (`PdfHighlighterTaskServiceImpl.java:60-65`); `TenantFilterHelper` *disables* the filter for a null tenant (`:28-33`) | A caller with no tenant owns nothing and sees nothing, per `TenantOwnership.java:35-41` | A non-admin principal with no `tenantId` claim gets every tenant's task list and can read, edit, upload to and delete every platform-owned row | Call `TenantOwnership.isOwnedByCaller(task.getTenantId())`; add a tenant-isolation test | **S** | **High if reachable**, none once closed |
| 4 | `nextFieldNumber` starts at 1 and is never seeded from loaded fields (`:89`, `:143-169`, `:510`); nothing de-duplicates labels client- or server-side | Labels are unique within a task and the next box gets the next unused number | The consumer keys its row by label (`pdf_highlighter_f768925.py:270`), so two `Field 1`s become one column, last-wins, across the whole batch, with no error | Seed the counter from existing labels; refuse duplicates in the panel and in `syncPdfHighlighterFields` | **S** | Medium -- silent wrong output today |
| 5 | Update, sync and upload legs ignore the response envelope (`:183-188`, `:225`, `:227`); only create checks it (`:190-197`) | A rejected save says which leg failed and stays on the page | "PDF highlighter task saved" over a mapping the server refused, then a navigation away that loses the drawn boxes | Check `status === API_SUCCESS` on each leg with a leg-specific message | **S** | Low -- but it hides every other server-side refusal on this list |
| 6 | `removeFile()` is local-only (`:327-340`); `PdfHighlighterTaskDto` has no file fields (`PdfHighlighterTaskDto.java:17-22`) and `updatePdfHighlighterTask` never writes them (`:122-131`) | Remove detaches the PDF and deletes the object | The button is a lie: reload and the file is back | New `DELETE /deletePdfHighlighterFile`; clear the three columns and delete the key | **S** | Low |
| 7 | `uploadPdfHighlighterFile` overwrites `file_name` without deleting the previous key (`:229-233`); soft delete touches neither fields nor storage (`:137-153`) | Replacing a PDF leaves one object per task | `pdf-highlighter/<id>/` accumulates unreferenced objects in a bucket no tenant can browse, so nothing can be told to clean it | Delete the recorded key before writing the new one, in the same method | **S** | Low |
| 8 | Five NOT NULL columns (`PdfHighlighterField.java:45-59`) fed by clearable number inputs (`.html:160-163`) with no validation on either side (`:191-195`) | Blank geometry is refused inline, before the request | A cleared `x` produces HTTP 500 and "Internal server error" for a blank box in a form | Validate in the panel and in `syncPdfHighlighterFields`; return the ERROR envelope, not a 500 | **S** | Low |
| 9 | PDF-ness is checked in the browser only (`:265-268`, `:277-280`); the server takes any bytes (`:215-217`) and the download serves them inline with a key-derived content type (`RestApi:134`, `:137`; `ContentTypeUtil.java:34-35`) | The server decides what a PDF is, and the download is always `application/pdf` | An authenticated user can store `evil.html` and have the API serve it back as `text/html`, inline | Check extension and magic bytes on upload; pin the download's content type | **S** | Medium -- authenticated, cross-origin from the SPA, but a real inline channel |
| 10 | Only the global 500 MB multipart cap applies (`application.properties:40-41`), while the converter and transcript declare 50 MB and 250 MB with reasons (`:75-81`); the browser reads the whole file into an `ArrayBuffer` (`:30-37`, `:302-303`) | A stated ceiling, enforced on both sides | A 300 MB PDF is a hung tab and an unbounded heap spike | Add `pdf.highlighter.max-file-size-mb`, default 50; check client-side before the POST | **S** | Low |
| 11 | `loadingTask`, `loading` and `setupError` are maintained and never rendered (`:63-65` vs the template, which uses only `errorMessage` and `rendering`); `SpinnerService` is injected and never called (`:96`) | Every wait has a spinner and every failure has words | Opening a task with a large stored PDF shows a header card over empty space with no signal | Ship the new screens with real states from `shared/ui/data-table.ts`; do not port the dead flags | **S** | None -- it disappears with the rewrite |
| 12 | The panel claims a box "can still be located by content if the PDF is regenerated" (`.html:136-138`); the selector's `path` is a pair of positional indices (`:434`) and `text`/`prefix`/`suffix` are stored but read by nothing (`pdf_highlighter_f768925.py:260`) | The screen describes what the selector actually does | People turn on `useXpathFirst` believing it survives a reflow that shifts one line above the field | Reword to describe index-and-order stability; leave the data model alone | **S** | None -- but it is the sentence people act on |
| 13 | The copy button hands out `pdf-highlighter/<id>/<file>` (`pdf-highlighter.component.ts:94-106`) in `etl-bucket`, which the Object Browser refuses below PLATFORM_ADMIN (`StorageBrowserServiceImpl.java:431-437`, `:465-467`) | The label matches the access | An affordance that implies a door the product does not open | Call it a storage key in the toast and the header; keep the button | **S** | None |
| 14 | No test at any level: `PdfHighlighterTaskRestApi` is on the twenty-untested-controllers list (`.ai/discovery/backend.md:1058-1062`), `PdfHighlighterTaskServiceImpl` appears only in a comment (`StorageBrowserServiceImplTenantIsolationTest.java:269`), the old Angular app has zero `.spec.ts` | Isolation covered, the selector grammar pinned, the save legs covered | Every repair above is unverifiable and can regress silently | Three test files; see §3 row 14 | **M** | Low, high value |
| 15 | Neither table has a creation path on stage or prod: no changeset creates them (V12/V14/V17 only `ALTER`/`COMMENT`), and `ddl-auto` is `validate` there (`application-stage.properties:90`, `application-prod.properties:92`) | A fresh environment can be built | Not this feature's bug -- it is the whole-database risk at `.ai/discovery/database.md:547-556` -- but it is what a fresh migration environment will hit first | Out of scope here; flag it to whoever stands the environment up | S | Medium, and shared |
| 16 | The pipeline fetches its mapping from a service on port 9999 in a shape `process` does not serve, and reads PDFs from a prefix the console does not write to (`xml_parser.py:77`, `pdf_highlighter_f768925.py:137`, `:146`, `:172-176`) | Somebody states whether `process` is meant to become that source | Today the console authors a mapping in exactly the consumed format and nothing carries it across except a Download button | Decide first (Q1), then either add `uuid` + a `by-name` read, or write down that Copy/Download is the handoff | M-L | **High** -- it decides whether the feature is load-bearing or a convenience |

---

## 3. Solution detail

### Row 1 -- Build it in `features/tools/pdf-highlighter/`, and split the pdf.js bootstrap

New files under `scheduler1/next/src/app/features/tools/pdf-highlighter/`: `pdf-highlighter.ts/.html`
(list), `pdf-highlighter-editor.ts/.html`, `highlighter-canvas.ts`, `field-list.ts/.html`,
`pdf-highlighter.service.ts`, `pdf-highlighter.models.ts`, `selector.ts`. Three routes added to
`app.routes.ts` beside the other tools (`:166-176`) with `authGuard` only, and one nav child in the
Tools group of `features/shell/shell.ts` (`:71-88`). Two entries added to the `LOOK` map in
`shared/ui/status-pill.ts:55-60` for `draft` and `ready`.

**Why no `roleGuard`:** every endpoint behind the screen is `TENANT_USER`
(`PdfHighlighterTaskRestApi.java:28`, no method-level override anywhere), so a `minRole` on the
route would deny a page the API serves -- precisely the failure `core/auth/auth.guard.ts:19-31`
documents. `/objects` and `/tools/converter` are ungated for the same reason.

**The canvas decision.** `features/objects/preview/pdf-viewer.ts` already does most of what the
viewer half needs: worker bootstrap, `devicePixelRatio` scaling, render cancellation, zoom clamped
to 0.5-3.0, fit-to-width, real loading and error states (`:97-159`).

- **Rejected: extend `PdfViewer` with a projected overlay.** It keeps `scale` private (`:76`) and
  owns its own fit; the editor needs the scale in the parent's hands, because field boxes are stored
  in unscaled points and drawn at `x * scale`
  (`pdf-highlighter-detail.component.ts:555-562`). Exposing `scale` as an output and accepting
  projected content turns one component into two half-components, and every future change to the
  object-browser preview becomes a possible regression in the editor. The two screens have genuinely
  different jobs: one displays, one measures.
- **Chosen: a small shared `pdf-render.ts` helper** holding the worker URL setup
  (`pdf-viewer.ts:101-105`) and the cancel-safe draw dance (`:129-159`), with `PdfViewer` and the new
  `HighlighterCanvas` as two thin components on top. The duplication that remains is the toolbar,
  which is cheap and which the two screens will want to diverge on anyway.

**Two behaviours to add that the old screen never had**, both cheap once the canvas is ours:
re-fit on container resize (the old code fits once per render, `:342-351`, so rotating a tablet
leaves every box misaligned), and pointer events instead of mouse events so the overlay is not inert
on touch (`:472-498`).

### Row 2 -- Pin the selector grammar before porting, not after

`selector.ts` must be a pure function of `(pageNumber, items, rect)` returning the same
`{path, text, prefix, suffix}` shape, with no Angular and no DOM, so `selector.spec.ts` can assert
the exact output string against a fixture without a browser.

The sequence matters. Do this **first**, against pdf.js 2.16 in the old app, capturing the
`getTextContent()` item list for a real PDF as the fixture. Then port and run the same spec against
6.x. If the item lists differ -- a merged run, a differently split ligature, a whitespace item that
is now non-blank -- then every `page[n]/text()[a:b]` already stored in `pdf_highlighter_field` points
somewhere else, and that is a data migration question, not a porting question.

**Rejected: port first and eyeball the result.** The failure mode is not a crash. It is an index that
is off by one on a document nobody re-checks, producing a wrong column in a batch of four thousand
files six weeks later. The consumer's own docstring is explicit that it matched pdf.js index-for-index
against a real ticket PDF (`pdf_highlighter_f768925.py:199-206`); that verification is the thing
being put at risk, and it costs one afternoon to preserve.

### Row 3 -- Use the shared ownership rule

Replace the private helper (`PdfHighlighterTaskServiceImpl.java:60-65`) with
`TenantOwnership.isOwnedByCaller(task.getTenantId())` at all seven call sites (`:84`, `:119`, `:145`,
`:164`, `:180`, `:220`, `:242`), and let a null-tenant caller fall through to a refusal.

The list needs its own line, because `TenantFilterHelper.enableIfNeeded:28-33` turns the filter
**off** for a null tenant rather than tightening it, so `fetchAllPdfHighlighterTask` would still
return everything. Add an explicit guard in `fetchAllPdfHighlighterTask`: a non-platform-admin with
no tenant gets an empty list.

**Rejected: fix `TenantFilterHelper` so a null tenant means "match nothing".** That is the right
shape and the wrong change to make inside a feature migration -- `enableIfNeeded` is called 72 times
across 12 service classes (`.ai/discovery/database.md:367-372`), and turning its tenant-less case
from permissive to empty would change eleven other features' behaviour in one commit, unreviewed by
any of their owners. Fix it here, and raise the sweep separately; twelve other services carry the
same private copy of the ownership rule (`ConnectionProfileServiceImpl.java:62-67`,
`AiAgentServiceImpl.java:100-105`, `SourceTaskServiceImpl.java:113-118` among them).

### Row 4 -- Seed the label counter, and make labels unique

Client: derive the next number from the existing labels rather than from a field initialised to 1
(`:89`), and refuse a duplicate inline before the request. Server: refuse a duplicate label in
`syncPdfHighlighterFields:187-204` with an ERROR envelope naming the offending label.

**Rejected: a unique constraint on `(pdf_highlighter_task_id, label)`.** It would be the strongest
guarantee, and it would turn every existing task that already carries duplicates into a row that can
never be saved again -- with the failure arriving as a constraint violation through the controller's
catch-all as HTTP 500 (`PdfHighlighterTaskRestApi.java:109-112`), which is exactly the experience
row 8 is trying to remove. Validate in the service, where the message can be useful, and consider
the constraint only after a survey of live data.

**Rejected: silently renaming duplicates to `Total (2)`.** The label is a column name in someone's
output file. Renaming it without saying so moves the breakage downstream to a spreadsheet.

### Row 5 -- Check every leg of the save

`saveTask` is a chain of three requests (`:171-246`). Each leg gets its own envelope check and its
own message, because they fail differently and the user's next move differs:

- Task leg fails: nothing was saved; stay, show the message.
- Sync leg fails: the task exists, the mapping does not. "The task was saved but its field mapping
  was not: `<message>`." Stay -- the drawn boxes are still in memory and are the only copy.
- Upload leg fails: task and mapping are saved, the PDF is not. Stay, offer a retry of just the
  upload.

**Rejected: making the whole save atomic on the server** with one endpoint taking task, fields and
file together. It is a better API and it is a bigger change: it duplicates three existing endpoints,
needs a new multipart-plus-JSON contract, and leaves the old three in place for the old app until it
is retired. The three-leg chain works; it just needs to report.

### Rows 6 and 7 -- One new endpoint, and one deletion inside the upload

`DELETE /pdfHighlighter.json/deletePdfHighlighterFile?pdfHighlighterTaskId=`, TENANT_USER, same
ownership check as its siblings: delete `pdf-highlighter/<id>/<file_name>` and null the three file
columns. In `uploadPdfHighlighterFile:229-233`, delete the previously recorded key before writing the
new one when the name differs.

Both need a trusted delete on the storage side. `StorageBrowserServiceImpl.deleteObject:331-335`
routes through `resolveServiceForCaller`, which refuses `etl-bucket` to every non-platform caller
(`:431-437`) -- so it cannot be used as-is. Add a `deleteForWorkflow(bucket, key)` beside
`uploadForWorkflow` (`:243-245`) and `readForWorkflow` (`:310-313`), with `requireSafeKey` and the
same comment explaining why it is trusted: ownership was checked by the caller and the key is
composed from the task id and the name on the row.

**Rejected: hard-deleting the object when the task is soft-deleted.** `updatePdfHighlighterTask` can
set `status` back to `Active` (`:128-130`), so a soft delete is reversible and destroying the object
would make the undelete open an editor with a missing file. Soft delete should not destroy. The
storage growth this leaves is bounded by *deleted tasks*, not by *every save*, and the unbounded case
-- replace -- is the one being closed. A reaper over `pdf-highlighter/<id>/` for tasks that have been
in `Delete` for N days is the right long-term answer and is out of scope.

**Rejected: deleting the field rows on soft delete.** Same reasoning: an undelete that returns an
empty mapping is worse than a few orphan rows behind a soft-deleted task.

### Row 8 -- Validate the field before writing any of it

In `syncPdfHighlighterFields`, before the delete-and-reinsert (`:183`): iterate the incoming list and
refuse the whole request with a message naming the field and the problem if any of `label` (blank),
`page`, `x`, `y`, `width`, `height` (null) or `width`/`height` (non-positive) is bad. Refuse the
whole batch, not the bad rows -- a partial mapping written over a good one is worse than no write.
Mirror the same checks inline in the field panel so the request is not made.

Note the ordering hazard: the current method deletes every row before it inserts anything
(`:183-205`), so a validation failure *after* the delete would destroy a working mapping. Validate
first.

### Row 9 -- Decide what a PDF is on the server, and stop deriving the download's type

Two independent changes; do both.

1. `uploadPdfHighlighterFile`: refuse a name that is not `.pdf`, and refuse content whose first bytes
   are not `%PDF-`. Extension alone is not enough -- the whole point is that the extension is what
   `ContentTypeUtil.contentTypeFor` trusts (`:86-89`).
2. `downloadPdfHighlighterFile`: replace `MediaType.parseMediaType(content.getContentType())`
   (`PdfHighlighterTaskRestApi.java:137`) with a literal `application/pdf`. The endpoint has exactly
   one job and knows what it is serving; deriving the type from the key inherits
   `html -> text/html` (`ContentTypeUtil.java:34-35`) from a map built for the general object browser.

**Rejected: `Content-Disposition: attachment`.** It would blunt the inline channel, and it is the
wrong lever. The Angular client fetches the response as a blob and never navigates to the URL
(`pdf-highlighter.service.ts:47-49`), so the disposition is close to cosmetic here, while pinning the
content type closes the hole for every caller including one who pastes the URL into a tab.

**Rejected: doing only the upload check.** Objects already stored bypass it.

### Row 10 -- A stated ceiling, on both sides

`pdf.highlighter.max-file-size-mb`, defaulting to 50, in `application.properties` beside
`document.converter.max-file-size-mb` (`:77`) and `audio.extract.max-file-size-mb` (`:81`), with a
comment saying why, as those two do. Checked in `uploadPdfHighlighterFile` and mirrored in the client
before the file is read into memory.

50 rather than 250: the client reads the whole file into an `ArrayBuffer` before pdf.js sees it
(`:30-37`) and does the same to the downloaded blob (`:302-303`), so the browser pays the cost twice,
and a template document is a sample of one, not an archive.

### Row 12 -- Say what the selector does

Replace the panel's sentence (`.html:136-138`) with what is true: the selector records the text under
the box and its position in the page's reading order, so a field can still be found when the box
moves, as long as the amount of text before it on the page has not changed. Reword the checkbox
tooltip (`:166`) the same way.

No data-model change. `text`, `prefix` and `suffix` are captured and stored
(`PdfHighlighterField.java:64-75`) and read by nothing (`pdf_highlighter_f768925.py:260` uses only
`selectorPath`), which makes a genuine content-based resolver a real future option -- and the reason
to leave the columns alone rather than delete them.

**Rejected: implementing content-based resolution now.** It changes the pipeline, not the console,
and the pipeline is not this migration's to change.

### Row 14 -- Three test files

1. **`PdfHighlighterTaskServiceImplTenantIsolationTest`**, modelled on the eight existing
   `*TenantIsolationTest` files under `process/src/test/java/process/model/service/impl/`. Grooming
   criteria 50-60: every refusal with its positive control on the same fixture, plus the tenant-less
   caller from row 3 and the platform-owned row 1003.
2. **`selector.spec.ts`**, pinning the grammar (row 2).
3. **A component spec for the editor**: the 6 px drag floor, the label counter continuing from
   existing labels, and each of the three save legs surfacing its own failure.

**Rejected: an e2e test through the HTTP layer.** The `@PreAuthorize` on this controller is one
class-level annotation with no method-level overrides -- the least likely authorization surface in
the codebase to be wrong. The service is where the decision is made and where the tests belong.

---

## 4. Ordering

**Phase 0 -- decide, and pin.** Q1 (does `process` become the mapping source?), then row 2's grammar
fixture captured against pdf.js 2.16 while the old app is still running. Nothing else starts until
the fixture exists; it is the only artefact that survives the port and proves it was faithful.

**Phase 1 -- backend repairs, on the old app.** Rows 3, 4 (server half), 5's server-side
preconditions, 6, 7, 8, 9, 10, plus row 14's isolation test. These are independent of the frontend
and testable today against the screen that exists, which is the whole reason to do them first --
the regression note already says the old screen must keep working while the decision is open
(`.ai/regression/regression.md:72`). Unblocks: a frontend that can trust its errors.

**Phase 2 -- the new screens.** Row 1, with rows 4 (client half), 5, 11, 12 and 13 built in rather
than ported. The list first -- it is small, it exercises the new service end to end, and it proves
the route, nav and status-pill additions. Then the editor.

**Phase 3 -- retire the old.** Delete `_component/pdf-highlighter/**`, `_services/pdf-highlighter.service.ts`,
the four model interfaces and `HIGHLIGHTER_STATUS_LIST` (`_models/object.ts:136-182`), the routes
(`app.routing.ts:198-212`), the nav entry (`app.component.html:33`), the ~242 lines of LESS
(`_content/app.less:3989-4216`) and the 1.1 MB `src/assets/pdf.worker.min.js`. This is the last
feature standing between the old app and deletion, so this phase is the migration's finish line, not
a tidy-up.

**Phase 4, only if Q1 says yes -- the mapping-fetch endpoint.** Row 16: `uuid` column, per-tenant
unique `task_name`, a `by-name` read returning `{task:{uuid}, fields:[...]}`, and a decision about
the `highlighter/input/<name>` prefix. Separable from everything above by design.

---

## 5. Out of scope

**The TENANT_USER / TENANT_ADMIN distinction.** There is none, at any of the four layers: the
controller is `TENANT_USER` throughout, the service rule is tenant equality only, and the old app's
routes carry `AuthGuard` with no role check (`app.routing.ts:198-212`). Whether an ordinary user
should be able to delete a colleague's mapping is a product question with a real answer either way,
and inventing one during a migration would ship a behaviour change disguised as a port. Raise it;
do not decide it here.

**Fixing `TenantFilterHelper`'s tenant-less case, and the twelve other private copies of the
ownership rule.** Row 3's reasoning. One-line fix here, sweep separately.

**Creating the tables on stage and prod.** Row 15 is the whole-database risk at
`.ai/discovery/database.md:547-556`; twenty-two tables share it, and solving it for two of them
solves nothing.

**Content-based selector resolution.** Row 12. It is a pipeline change.

**A storage reaper for soft-deleted tasks.** Rows 6-7's reasoning: the unbounded case is replace, and
that is being closed. The bounded case can wait for someone to measure it.

**Server-side pagination and search on the list.** `fetchAllPdfHighlighterTask` returns everything
(`:71-72`). At the volumes a template list reaches, a client-side filter and `shared/ui/pager.ts` are
enough; revisit if a tenant passes a few hundred.

**Extraction preview and box drag-handles.** Both named in Grooming §13 as the highest-value
additions beyond parity, and both are additions. Ship parity plus the repairs first; a migration that
grows features is a migration nobody can say is finished.

---

## 6. Open questions

**Q1. Is `process` meant to become the source the ETL fetches its mapping from?**

The pipeline calls `GET .../organizations/{organizationUuid}/pdf-highlighters/by-name/{organizationsTask}`
on port 9999 and expects `{task:{uuid}, fields:[...]}` (`job-search/etl/util/xml_parser.py:77`,
`job-search/etl/tasks/pdf_highlighter_f768925.py:146`, `:172-176`). `process` serves
`fetchPdfHighlighterFields?pdfHighlighterTaskId=` on 9098, returns a bare list
(`PdfHighlighterTaskServiceImpl.java:169`), and has no `uuid` column
(`PdfHighlighterTask.java:27-78`). It also reads its input PDFs from `highlighter/input/<name>`
(`:137`) while the console writes to `pdf-highlighter/<taskId>/` (`:253-255`). Whatever serves 9999
is not in this repository.

- **Option A -- yes.** Add `uuid` to `pdf_highlighter_task`, a per-tenant unique constraint on
  `task_name`, and a `by-name` read returning the envelope the pipeline expects. Then decide whether
  the console's uploaded PDF becomes the batch input or stays a template. One backend change,
  independently testable.
- **Option B -- no.** The console is an authoring tool; Copy and Download JSON are the handoff, and
  someone pastes the mapping into whatever serves 9999. Zero backend change. Requires saying so on
  the screen, because nothing there currently suggests a manual step.
- **Option C -- neither.** Retire the `process`-side highlighter entirely and let the 9999 service
  own authoring too. This is the "drop" answer, and it is only available if that service already has
  an editor.

**Recommendation: A, staged as Phase 4, and B in the meantime.** A is where this is obviously going
-- the grammar, the six field names and the envelope keys were built to fit
(`pdf_highlighter_f768925.py:36` against `pdf-highlighter-detail.component.ts:434`), and a mapping
tool whose output has to be copied by hand into another system is a half-built feature. But A depends
on a service nobody in this repository can see, and guessing its contract would be inventing an
endpoint. So: build Phases 1-3 against the endpoints as they stand, ship B's honest wording, and hold
A until whoever runs 9999 confirms the shape. C should be refused unless that service is shown to
have its own editor -- dropping the only authoring tool for two routed, seeded pipelines on the
assumption that something else covers it is the expensive mistake on this page.

**Q2. Extend `PdfViewer`, fork it, or share a helper?**

- **Option A -- extend** `features/objects/preview/pdf-viewer.ts` with an optional projected overlay
  and an exposed `scale`.
- **Option B -- fork** it into a separate `HighlighterCanvas` and accept the duplication.
- **Option C -- extract** the worker bootstrap and the cancel-safe draw into `pdf-render.ts`, with
  two thin components on top.

**Recommendation: C.** A couples the object browser's preview dialog to the editor: `scale` is
private and the fit logic is its own (`pdf-viewer.ts:76`, `:120-127`), and the editor needs both in
the parent because fields are stored unscaled and drawn at `x * scale`. B duplicates the two genuinely
fiddly parts -- the worker URL and the render-cancellation dance (`:101-105`, `:129-159`) -- which are
exactly the parts that break silently when pdf.js moves. C shares what is version-sensitive and
separates what is job-specific.

**Q3. Where does it live in the navigation?**

- **Option A -- Tools**, beside Document Converter (`features/shell/shell.ts:71-88`).
- **Option B -- its own top-level entry**, as it had in the old app (`app.component.html:33`).

**Recommendation: A.** The Tools group is described in the shell's own comment as "the things that
take a file and give one back", which is this exactly. A top-level entry made sense in a flat
Bootstrap menu; in a grouped nav it would be the only ungrouped tool.

**Q4. Keep `?mode=view`?**

The old list has separate View and Edit buttons opening the same route, one with `?mode=view`
(`pdf-highlighter.component.ts:81-87`), and `readOnly` is read once from the snapshot (`:103`).
Nothing gates it -- any user can delete the query parameter.

- **Option A -- keep it as-is.**
- **Option B -- drop it.** One Open action; the screen is always editable. A read-only mode nobody is
  held to is chrome, not a permission.
- **Option C -- drop the URL contract and give `Ready` the job.** A task whose `highlighterStatus` is
  `Ready` opens locked with an explicit "Edit mapping" control; a `Draft` opens editable.

**Recommendation: C.** It costs about what B costs and it solves a second problem: `HighlighterStatus`
is decorative today -- `Draft` and `Ready` are a coloured chip that no code in
`process/src/main/java` branches on outside the enum's own declaration. C gives the flag a
consequence, protects the mappings that are actually feeding a pipeline from an accidental drag on
the canvas, and removes a URL parameter that promised an access control it never enforced. If it is
judged too much behaviour change for a migration, fall back to B -- not A.

**Q5. Should the list show a field count per task?**

It is the first thing anyone wants to know about a mapping, and there is no endpoint for it: it costs
one `fetchPdfHighlighterFields` per row (`PdfHighlighterTaskRestApi.java:93-102`).

- **Option A -- fan out** one request per row, lazily, showing `—` until each lands.
- **Option B -- omit the column.**
- **Option C -- add a `fieldCount` to the task DTO** and populate it with one grouped count query in
  `fetchAllPdfHighlighterTask`.

**Recommendation: C.** It is a few lines in a service that already runs one query, and it avoids the
fan-out that made the old Object Browser slow enough to need a provider guard
(`.ai/synthesis/object-browser.md:38`, gap 7). If C is judged out of scope for a migration, take B
over A -- an N+1 on a list screen is a harder thing to remove later than a column is to add.
