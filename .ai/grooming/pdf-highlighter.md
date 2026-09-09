# Grooming -- PDF Highlighter

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

Status from Discovery: **not-migrated** (`.ai/discovery/features.md:48`). Old routes
`pdfHighlighter`, `pdfHighlighter/new`, `pdfHighlighter/:pdfHighlighterTaskId`; **no route, no
component and no service in `scheduler1/next`** -- a case-insensitive search of the whole of
`scheduler1/next/src` for `highlighter` returns zero files. The backend is complete and live: nine
endpoints on `PdfHighlighterTaskRestApi`, two entities, two tables.

This is the only whole-feature gap in the migration, and it is the one that decides when the old
app can be switched off (`.ai/execution/README.md:40`).

> **DECISION (2026-09-07): removed, not migrated** -- see the banner at the top of
> `.ai/synthesis/pdf-highlighter.md` for the full reasoning and the change list. This document's
> analysis below is kept as the historical record; it does not reflect the final outcome.

---

## 1. Purpose

"I have four thousand PDFs that all look the same. Show me one of them, let me draw a box round
each thing I need out of it, name the boxes, and hand that to the thing that will read the other
three thousand nine hundred and ninety-nine."

That is the whole job. A PDF Highlighter task is a **template**: one sample document, plus a named
list of rectangles on it. The rectangles are what a batch process later crops out of every
document of the same shape to produce a table -- one row per file, one column per box.

The batch process is not hypothetical and it is not somewhere else. Two ETL pipelines in this
repository consume exactly this shape:

- **F768925 -- PDF Highlighter Text Extraction** (`job-search/etl/tasks/pdf_highlighter_f768925.py`)
  reads every PDF under a MinIO prefix, resolves each mapped field on each file, and writes one
  CSV/XLSX/JSON row per file (`:240-271`, `:273-299`).
- **F768924 -- PDF Highlighter Form Fill**
  (`job-search/etl/tasks/pdf_highligter_form_fill_F768924.py:126-128`) takes F768925's output and
  drives a form-filling API with it.

Both are routed by pipeline id in the Kafka listener
(`job-search/etl/tpd/tpd_scrapping_listener.py:139-144`) and both are seeded as `PIPELINE_IDS`
lookup rows and as a `source_task_type` description
(`process/src/main/resources/db/changelog/changelog-sets/V10.0-fix-task-types-pipelines/V10__fix_source_task_type_and_pipeline_ids.sql:27-31`,
`:41-47`).

So the screen is an **authoring tool for a running pipeline**, not a viewer. Its output is not a
picture; it is a contract:

```json
[ { "label": "Invoice No", "page": 1, "x": 412, "y": 96, "width": 118, "height": 18,
    "useXpathFirst": true,
    "selector": { "path": "page[1]/text()[13:13]", "text": "INV-40912",
                  "prefix": "Invoice number", "suffix": "Date issued" } } ]
```

Every key in that object is read by name in the Python
(`job-search/etl/tasks/pdf_highlighter_f768925.py:251-270`), and the `path` grammar is parsed by a
regex on the Python side -- `^page\[(\d+)\]/text\(\)\[(\d+):(\d+)\]$` (`:36`) -- that matches the
Angular editor's output string character for character
(`scheduler1/src/app/_component/pdf-highlighter/pdf-highlighter-detail/pdf-highlighter-detail.component.ts:434`).
The two halves were built to fit each other.

The one thing that does **not** line up is where the pipeline fetches the mapping from. See §2.6.

---

## 2. Existing behaviour

### 2.1 Old app -- routing, navigation and models

| What | Where |
|---|---|
| Three routes, all guarded only by `AuthGuard` | `scheduler1/src/app/app.routing.ts:198-212` |
| Declarations | `scheduler1/src/app/app.module.ts:37-38`, `:107-108` |
| One nav entry, no role condition | `scheduler1/src/app/app.component.html:33` |
| `STATUS_LIST` (Active/Inactive/**Delete**) | `scheduler1/src/app/_models/object.ts:121-133` |
| `PdfHighlighterTask` interface | `scheduler1/src/app/_models/object.ts:136-146` |
| `PdfHighlighterFieldSelector` interface | `scheduler1/src/app/_models/object.ts:148-153` |
| `PdfHighlighterField` interface | `scheduler1/src/app/_models/object.ts:155-171` |
| `HIGHLIGHTER_STATUS_LIST` (Draft/Ready) | `scheduler1/src/app/_models/object.ts:173-182` |
| Nine service methods | `scheduler1/src/app/_services/pdf-highlighter.service.ts:13-49` |
| ~242 lines of feature-specific LESS | `scheduler1/src/app/_content/app.less:3989-4216` |
| pdf.js worker, shipped as a static asset | `scheduler1/src/assets/pdf.worker.min.js` (1.1 MB), wired at `pdf-highlighter-detail.component.ts:8-9` |

`AuthGuard` checks only that somebody is signed in; it never reads a role
(`scheduler1/src/app/_helpers/auth.guard.ts:16-23`). Every role therefore sees the nav entry and
can open every route.

Line counts, measured: list component 134 TS + 142 HTML; detail component 602 TS + 207 HTML;
service 51 TS. (Discovery's "943 lines of TS" at `.ai/discovery/frontend-old.md:835` overstates it;
the true figure is 736 lines of component TS, 787 including the service. Its "349 lines of HTML" is
correct.)

### 2.2 Old app -- the list screen (`PdfHighlighterComponent`)

`scheduler1/src/app/_component/pdf-highlighter/pdf-highlighter.component.ts`,
`.html`.

- Loads every task on init through `fetchAllPdfHighlighterTask` behind the global spinner
  (`:38-40`, `:59-75`).
- Three client-side filters, all computed live: a free-text `searchFilter` pipe, a Highlighter
  Status select (Draft/Ready) and a Status select (Active/Inactive) (`:24-57`, HTML `:8-29`). Rows
  whose `status === 'Delete'` are dropped in `filteredPdfHighlighterTasks` (`:42-47`) -- redundant,
  because the server already excludes them (§2.4).
- The `searchFilter` pipe (`scheduler1/src/app/_helpers/search-filter.ts:19-102`) supports
  field-scoped (`taskName:invoice`), quoted and negated (`-draft`) tokens and recurses into nested
  objects.
- Eight columns: id, Task Name, Description, **Path**, Highlighter Status, Status, Created, Action
  (HTML `:45-56`).
- The Path column shows `pdf-highlighter/<taskId>/<fileName>` with a copy-to-clipboard button, or
  an em dash when nothing has been uploaded (`:94-106`, HTML `:62-70`).
- Per-row View (opens the editor with `?mode=view`), Edit, and a kebab menu holding Delete
  (`:81-92`, HTML `:85-110`).
- Delete opens a Bootstrap modal; confirming calls `deletePdfHighlighterTask`, splices the row out
  locally and dismisses the modal by clicking a `@ViewChild` close button (`:108-133`, HTML
  `:126-142`).
- Empty state distinguishes "nothing matches your filter" from "add your first task"
  (HTML `:113-121`).

### 2.3 Old app -- the editor (`PdfHighlighterDetailComponent`)

`scheduler1/src/app/_component/pdf-highlighter/pdf-highlighter-detail/pdf-highlighter-detail.component.ts`
(602 lines), `.html` (207 lines). This is the feature.

**Mode.** `pdfHighlighterTaskId` comes from the route param and `readOnly` from
`?mode=view`, both read once from the snapshot (`:101-107`). With no id the screen is a blank new
task; with an id it loads the task, then the fields, then -- if a file is recorded -- downloads and
renders the stored PDF (`:115-141`).

**File intake.** A dropzone accepts a click-to-browse or a drag-and-drop, both refusing anything
whose MIME type is not `application/pdf` (`:252-280`, HTML `:62-69`). The file is read into an
`ArrayBuffer` in the browser (`:30-37`) and handed to pdf.js; it is **not** uploaded until the task
is saved (`:226-232`).

**Rendering.** `renderPage()` (`:342-369`) fits the page to the scroll container's width, clamped
to 320-1100 px, multiplies by the zoom, renders to a `<canvas>` at `devicePixelRatio`, and sizes an
absolutely-positioned overlay `<div>` to match. Page navigation `:441-451`; zoom 0.5-3.0 in 0.25
steps with a reset `:453-470`.

**Drawing.** Mouse-down/move/up on the overlay draw a dashed draft rectangle; a drag under 6 px in
either dimension is discarded as a click (`:472-498`). The surviving rectangle is divided by the
current scale to give **unscaled PDF-point coordinates with a top-left origin**, rounded to whole
points, and pushed as a new field labelled `Field N` (`:500-518`). Existing boxes are re-projected
each change-detection pass by `fieldStyle()` multiplying back up by the scale (`:555-562`).

**Selector derivation** -- `buildSelector` (`:415-439`). Discovery records this as the most recently
added part of the feature, from a commit `4c07a7a pdf highlighter xpath added`
(`.ai/discovery/features.md:107-109`). **Not verified here:** the `Old-School` checkout carries a
single squashed commit, `5e8dbe7 first commit`, so that history cannot be re-read from this working
copy; the hash belongs to the sibling `io-frontend` checkout.

1. `getPageTextItems` (`:384-413`) pulls the page's text layer via pdf.js `getTextContent()`,
   discards blank items, and converts each item's transform into a viewport-space box.
2. Every item whose **centre** falls inside the drawn rectangle is collected (`:417-423`).
3. The first and last matching indices become the path `page[<n>]/text()[<start>:<end>]` (`:434`).
4. `text` is the matched items joined and whitespace-collapsed; `prefix` is the last 30 characters
   of the six items before, `suffix` the first 30 characters of the six items after (`:428-437`).
5. A box with no text under it gets no selector at all (`:424`), and the UI says so
   (HTML `:178-180`).

`enrichFieldSelectors` (`:371-382`) runs after every render and back-fills selectors for fields on
that page that arrived from the server without one.

**Field list panel** (HTML `:131-184`): per field, a label input, up/down reorder buttons
(`:533-549`), a delete button, four number inputs for x/y/w/h, a `useXpathFirst` checkbox (disabled
when there is no selector), the selector path in a `<code>` with the matched text as its `title`,
and a copy-path button.

**Mapping JSON** (HTML `:187-207`): a live `<pre>` of the payload, with Copy
(`:575-577`) and Download (`:592-600`, filename `<pdfname>-field-mapping.json`).

**Save** (`:171-246`), in strict order:

1. Refuse a blank task name, client-side only (`:173-176`).
2. `addPdfHighlighterTask` or `updatePdfHighlighterTask`.
3. `syncPdfHighlighterFields` with the whole field list, `displayOrder` set from array position.
4. `uploadPdfHighlighterFile`, only if a file was picked in this session.
5. Toast, navigate back to the list.

### 2.4 Backend

`process/src/main/java/process/api/PdfHighlighterTaskRestApi.java` (149 lines) and
`process/src/main/java/process/model/service/impl/PdfHighlighterTaskServiceImpl.java` (257 lines).

The class carries `@PreAuthorize("hasRole('TENANT_USER')")` (`:28`) and **no method-level
`@PreAuthorize` anywhere**, so nothing replaces it -- the one case where the non-repeatable
annotation cannot bite. With the hierarchy at
`process/src/main/java/process/config/MethodSecurityConfig.java:29`, TENANT_ADMIN and
PLATFORM_ADMIN pass it too.

Service behaviour worth knowing:

- `fetchAllPdfHighlighterTask` (`:67-74`) enables the tenant filter and returns everything except
  `Status.Delete`, newest id first. Inactive rows are included.
- `fetchPdfHighlighterTaskById` (`:76-88`) uses `findById`, which the Hibernate filter does **not**
  reach, then checks ownership by hand. A miss and a refusal produce the identical message,
  `PdfHighlighterTask not found with <id>.`
- `addPdfHighlighterTask` (`:90-106`) requires a non-blank `taskName`, stamps the caller's tenant
  (which is `null` for a platform admin, making the row platform-owned), defaults
  `highlighterStatus` to `Draft` and `status` to `Active`, and returns the saved entity so the
  client can read the new id.
- `updatePdfHighlighterTask` (`:108-135`) requires id and name; writes name, description, and
  `highlighterStatus`/`status` when present. It **cannot** touch `fileName`, `fileSize` or
  `fileContentType` -- `PdfHighlighterTaskDto` has no such fields
  (`process/src/main/java/process/model/dto/PdfHighlighterTaskDto.java:17-22`).
- `deletePdfHighlighterTask` (`:137-153`) is a soft delete: `status = Delete` on the row, nothing
  else. Fields and the stored object are untouched.
- `fetchPdfHighlighterFields` (`:155-170`) checks task ownership first, then returns the fields
  ordered by `display_order`.
- `syncPdfHighlighterFields` (`:172-207`) checks ownership, **deletes every field row for the
  task**, and re-inserts the incoming list. `displayOrder` falls back to array position and
  `useXpathFirst` to `false`. No validation of anything else.
- `uploadPdfHighlighterFile` (`:209-235`) checks ownership, strips the path off the filename with
  `Paths.get(...).getFileName()`, and writes through `StorageBrowserService.uploadForWorkflow` --
  the *trusted* resolver -- to `etl-bucket` under `pdf-highlighter/<taskId>/`. The comment at
  `:224-228` explains why that is safe: ownership was checked above and the key is built from the
  task id, so no part of the destination came from the request. The row then records `fileName`,
  `fileSize` and `fileContentType`.
- `downloadPdfHighlighterFile` (`:237-251`) resolves the same key and streams it back via
  `readForWorkflow`. Missing task or foreign task raises `IllegalArgumentException`; a task with no
  file raises `IllegalStateException`. The controller turns both into HTTP 400 carrying the message
  (`:140-142`) -- one of only two places in the codebase that does this
  (`.ai/discovery/backend.md:980`).

### 2.5 Storage layout

Key: `etl-bucket` / `pdf-highlighter/<pdfHighlighterTaskId>/<fileName>`
(`PdfHighlighterTaskServiceImpl.java:253-255`, `:247`).

`etl-bucket` is a **platform bucket** by name, not by configuration:
`StorageBrowserServiceImpl.isPlatformBucketName` (`:465-467`) compares against the avatar bucket
and `KafkaSecretService.SECRET_BUCKET`, which is the literal `"etl-bucket"`
(`process/src/main/java/process/model/service/KafkaSecretService.java:27`). Every browse-path
request for it from a caller below PLATFORM_ADMIN is refused with `Unknown bucket: etl-bucket.`
(`StorageBrowserServiceImpl.java:431-437`). The highlighter's own upload and download bypass that
guard deliberately, through `uploadForWorkflow` (`:243-245`) and `readForWorkflow` (`:310-313`),
both of which still run `requireSafeKey` (`:399-403`).

Since task ids are globally unique, two tenants cannot collide inside the prefix.

### 2.6 What actually reads a field mapping

`job-search/etl/tasks/pdf_highlighter_f768925.py`:

1. Authenticates against `session.auth` from the task XML (`:75-95`).
2. Fetches the mapping from `pdfHighlighter.fieldMappingUrl` (`:97-120`), which the worked example
   in `job-search/etl/util/xml_parser.py:77` gives as
   `http://localhost:9999/v1/api/organizations/{organizationUuid}/pdf-highlighters/by-name/{organizationsTask}`.
3. Expects the envelope `{"data": {"task": {"uuid": ...}, "fields": [...]}}` (`:146`, `:172-176`).
4. Lists PDFs under `etl-bucket` / `<targetInputFileFolder>/<organizationsTask>` -- the sample XML
   gives `highlighter/input` (`:137`, `job-search/etl/util/xml_parser.py:78`).
5. Per field: if `useXpathFirst` is truthy and `selectorPath` is set, resolve by indexing into
   PyMuPDF's text spans (`:216-238`); otherwise, or on failure, crop the bounding box with
   pdfplumber using `(x, y, x+width, y+height)` (`:266-268`).
6. Writes one row per file, keyed by `label` (`:270`), to
   `<targetOutputFileFolder>/job_<id>_queue_<id>/<task uuid>/` (`:178-183`, `:273-299`).

**Three mismatches with `process`, all verified:**

| The pipeline expects | `process` provides |
|---|---|
| `GET .../organizations/{uuid}/pdf-highlighters/by-name/{taskName}` on port 9999 | `GET /pdfHighlighter.json/fetchPdfHighlighterFields?pdfHighlighterTaskId=` on port 9098 |
| `data.task.uuid` | `PdfHighlighterTask` has no `uuid` column (`PdfHighlighterTask.java:27-78`) |
| `data.fields` alongside `data.task` | `data` is a bare `List<PdfHighlighterField>` (`PdfHighlighterTaskServiceImpl.java:169`) |

Whatever serves `localhost:9999` is **not in this repository** -- `service-3` runs on 9099
(`service-3/src/main/resources/application.properties:1`) and has no organizations or highlighter
surface. Nor does the pipeline read the sample PDF the console uploads: its input prefix is
`highlighter/input/<taskName>`, while the console writes to `pdf-highlighter/<taskId>/`. Treat the
relationship as: **the console authors mappings in exactly the format the pipeline consumes, but
today nothing carries one to the other except the Copy/Download JSON buttons.**

### 2.7 New app

Nothing. No route in `scheduler1/next/src/app/app.routes.ts`, no nav entry in
`scheduler1/next/src/app/features/shell/shell.ts`, no service, no model, no spec.

The one relevant asset that does exist is `pdfjs-dist ^6.2.108`
(`scheduler1/next/package.json:28`) and the read-only canvas viewer built on it,
`scheduler1/next/src/app/features/objects/preview/pdf-viewer.ts` (176 lines): page navigation, zoom
clamped to 0.5-3.0, fit-to-width, `devicePixelRatio` scaling, render cancellation, and proper
loading and error states. It has no overlay and keeps `scale` private (`:76`), so it renders a PDF
but cannot host a field editor as it stands.

### 2.8 Tests

**None, at any level.**

- `PdfHighlighterTaskRestApi` is on the list of twenty controllers with no test of any kind
  (`.ai/discovery/backend.md:1058-1062`).
- `PdfHighlighterTaskServiceImpl` appears in the test tree exactly once, inside a comment:
  `process/src/test/java/process/model/service/impl/StorageBrowserServiceImplTenantIsolationTest.java:269`.
- The old Angular app contains **zero** `.spec.ts` files.
- The new app has specs, but none for a feature that does not exist there.

---

## 3. Expected behaviour

Everything in §2.2 and §2.3 should exist in `scheduler1/next`, plus the following, each of which is
a departure from today.

1. **The screen tells the truth while it is working.** Opening a task with a 20 MB stored PDF shows
   a spinner and then either the document or a stated failure. Today three state flags are
   maintained and none is rendered (§12.7).
2. **A save that failed says so.** The update, sync and upload legs of the save all check the
   response envelope before the "Saved" toast, exactly as the create leg already does (§12.3).
3. **Field labels are unique within a task, and the UI enforces it.** The extract is a dictionary
   keyed by label (`job-search/etl/tasks/pdf_highlighter_f768925.py:270`); two boxes with the same
   name silently become one column (§12.2).
4. **Geometry is validated before it is sent.** Four NOT NULL columns are currently reachable with
   nulls from four number inputs (§12.5).
5. **Removing the PDF removes the PDF.** Today the button clears the screen and the file is still
   attached after a reload (§12.4).
6. **Replacing the PDF does not leave the old one behind** (§12.6).
7. **The server decides what a PDF is.** Today only the browser does, and the download endpoint
   serves whatever was stored back inline with a content type derived from its extension (§12.9).
8. **There is a ceiling on the upload** below the global 500 MB multipart limit, as the converter
   and transcript features already have (§12.10).
9. **A tenant-less principal owns nothing**, which is what `TenantOwnership` exists to guarantee and
   what this service's private copy of the rule does not do (§12.1).
10. **`Draft` and `Ready` mean something.** Today the enum is a coloured label that no code branches
    on -- `HighlighterStatus` appears nowhere in `process/src/main/java` outside the highlighter's
    own files and the enum declaration. Proposal: `Ready` opens locked, with an explicit unlock, and
    replaces the `?mode=view` URL contract (see Synthesis Q4).
11. **A box can be adjusted by dragging it**, not only by typing four numbers (§13).
12. **The feature has tests** (§13).

Everything else -- the drawing model, the coordinate space, the selector grammar, the JSON shape --
must be preserved **byte for byte**, because a running pipeline parses it.

---

## 4. Frontend requirements

Target: `scheduler1/next`. Angular standalone components, signals, Tailwind, the shared UI kit.

### 4.1 Routes

Added to `scheduler1/next/src/app/app.routes.ts` inside the `Shell` children, beside the other
tools (`:166-176`):

| Path | Component | Guards |
|---|---|---|
| `tools/pdf-highlighter` | `PdfHighlighter` (list) | inherited `authGuard` + `passwordChangeGuard` only |
| `tools/pdf-highlighter/new` | `PdfHighlighterEditor` | same |
| `tools/pdf-highlighter/:taskId` | `PdfHighlighterEditor` | same |

**No `roleGuard`, no `minRole`.** Every endpoint behind this screen is `TENANT_USER`
(`PdfHighlighterTaskRestApi.java:28`), so gating the route would deny a page the API serves --
the mistake `auth.guard.ts:19-31` documents. This matches `/objects` and `/tools/converter`, which
are also ungated.

Nav entry in `scheduler1/next/src/app/features/shell/shell.ts`, in the **Tools** group beside
Document Converter (`:71-88`), with a `hint` of "Map fields on a PDF template". No `adminOnly`.

### 4.2 Components and files

```
scheduler1/next/src/app/features/tools/pdf-highlighter/
  pdf-highlighter.ts / .html          list screen
  pdf-highlighter-editor.ts / .html   the editor
  highlighter-canvas.ts               pdf.js canvas + drag-to-draw overlay
  field-list.ts / .html               the right-hand field panel
  pdf-highlighter.service.ts          the nine endpoints
  pdf-highlighter.models.ts           task, field, selector interfaces
  selector.ts                         buildSelector + text-item extraction, pure
  selector.spec.ts
  pdf-highlighter.spec.ts
```

`selector.ts` must be a pure function over `(pageNumber, items, rect)` so the grammar the pipeline
parses can be pinned by a unit test without a browser.

Reused from the shared kit, all verified to exist:

| Need | Use |
|---|---|
| List chrome, loading/empty/error | `shared/ui/data-table.ts` (`app-table-shell`) |
| Delete confirmation | `shared/ui/confirm.ts` `confirmWith()` |
| Toasts | `shared/ui/toast.service.ts` |
| Draft/Ready and Active/Inactive chips | `shared/ui/status-pill.ts` -- **needs two new `LOOK` entries**, `draft` and `ready`; it currently knows `active`, `inactive` and `delete` only (`:55-60`) |
| File sizes | `shared/ui/format-size.ts:9` |
| Copy to clipboard | `shared/ui/clipboard.util.ts:9` (returns whether the copy happened, so the toast can tell the truth) |
| Icons | `shared/ui/icon.ts` |
| API base and envelope | `core/api/api.config.ts:6-15` |

### 4.3 List screen

Columns: Id, Task Name, Description, Fields (count), File, Highlighter Status, Status, Created,
Actions.

- **Fields** is a count, which the old list did not show and which is the first thing anyone wants
  to know about a mapping. It costs one `fetchPdfHighlighterFields` per row, so it is deferred:
  render `—` and fill in lazily, or drop the column if the round trips are judged too expensive
  (see Synthesis, Out of scope).
- **File** shows the file name and its size via `formatSize`, with a copy-path button for
  `pdf-highlighter/<id>/<name>`. The button's toast must say *storage key*, not "path you can open"
  -- that key is inside a platform bucket the Object Browser refuses to every caller below
  PLATFORM_ADMIN (§12.11).
- Filters: free-text over name and description, Highlighter Status, Status, plus a Clear button
  disabled when nothing is set. Counts in the `app-table-shell` heading are `shown of total`.
- Actions: Open, Duplicate (see §13), and Delete behind `confirmWith`.
- Toolbar: Refresh and "New highlighter task".

### 4.4 Editor screen

Three regions, top to bottom on narrow viewports, and 8/4 columns from `lg` up, as the old screen
was (HTML `:75-76`, `:131`).

**Header card.** Task Name (required), Highlighter Status, Status (only when editing), Description.
Cancel/Back and Save/Create. Breadcrumb `PDF Highlighter / New | Edit | View`.

**Viewer card.** File name, page previous/next with `Page n / m`, zoom out / percentage-resets /
zoom in clamped to 0.5-3.0, Remove. Under it the hint "Click and drag on the page to draw a box
around a field". Then the scrolling canvas with the overlay.

**Field panel.** One row per field: reorder handles, label input, delete, `p<n>` and four number
inputs, the strategy checkbox, the selector path with its matched text on hover and a copy button.
Under the two, the JSON payload card with Copy and Download.

Behaviour that must carry over exactly:

- Coordinates are stored **unscaled, top-left origin, whole PDF points**, derived as
  `round(pixels / scale)` where `scale = fitScale × zoom`
  (`pdf-highlighter-detail.component.ts:500-506`, `:342-351`). The pipeline crops
  `(x, y, x+width, y+height)` in exactly that space
  (`job-search/etl/tasks/pdf_highlighter_f768925.py:267`).
- A drag under 6 px in either dimension is a click, not a box (`:498`).
- New fields are labelled `Field N` -- but `N` must continue from the highest existing `Field N`,
  not restart at 1 (§12.2).
- The selector path string, the 30-character context windows and the six-item look-around are
  fixed (`:428-437`).

### 4.5 Dialogs

Two, both `confirmWith`:

1. **Delete task** -- from the list. Danger styling, names the task.
2. **Discard unsaved changes** -- when leaving the editor with dirty fields. The old app had no such
   guard: `cancel()` navigates away immediately (`:248-250`) and everything drawn since the last
   save is lost silently.

Removing a single field needs no dialog; it is one click to redraw.

### 4.6 Loading, empty and error states

| Moment | What is shown |
|---|---|
| List loading | `app-table-shell` spinner |
| List empty, no filter | "No highlighter tasks yet" + New button |
| List empty, filter set | "Nothing matches your filter" + Clear |
| List request failed | `app-table-shell` error row with the envelope's `message` and a Retry |
| Editor loading task/fields | Skeleton over the header card |
| Stored PDF downloading | Spinner in the viewer card, "Loading the stored PDF…" |
| Stored PDF failed | "Could not load the stored PDF. You can upload it again below." with the dropzone reinstated -- the message the old app composes but never renders (`:306`, `:310`) |
| Page rendering | The existing dimmed-canvas treatment plus a small spinner, as `pdf-viewer.ts:43-45` does |
| PDF unreadable on pick | "Could not read that PDF. Please try a different file." (`:292`) |
| No file yet, editable | Dropzone |
| No file yet, read-only | "No PDF has been uploaded for this task yet." |
| No fields | "No fields yet. Draw a box on the PDF to add one." |
| Saving | Save button disabled, spinner glyph |

### 4.7 Dark and light mode

The old app is light-only; `scheduler1/src/app/_content/app.less` has no dark rules for any of the
highlighter classes, and three colours are hard-coded: the viewer gutter `#eceff1` (`:4046`), the
JSON preview `#2b2f36` on `#d7dde3` (`:4159-4160`), and the reorder button borders `#d3dade`
(`:4196`, `:4215`).

In the new app the theme is a `dark` class on `<html>` (`core/theme.service.ts:16-17`), so:

- Every surface uses the existing tokens -- `card`, `bg-raised`, `bg-sunken`, `border-subtle`,
  `var(--text-muted)` -- and no literal hex.
- The **canvas is the exception**: a PDF page is white in both themes and must not be inverted or
  tinted, or the drawn boxes stop lining up with what the reader sees. The gutter around it takes
  `bg-sunken`; the page itself keeps its own colours with a `shadow-sm`, as
  `pdf-viewer.ts:61` already does.
- Field boxes and the draft rectangle need a border colour that survives on both white paper and a
  dark gutter. Use the brand token at full opacity for the border and a low-alpha fill; do not rely
  on a light-mode-only grey.
- The JSON block uses the shared code surface rather than its own palette.

### 4.8 Responsive behaviour

- `lg` and up: viewer 8 columns, field panel 4, side by side.
- Below `lg`: stacked, viewer first, field panel under it, JSON last.
- The canvas container is the only horizontally scrolling element on the page
  (`overflow-x: auto`); the body must never scroll sideways.
- Fit-to-width recomputes on container resize, which the old app does not do -- it fits once per
  render and only re-renders on page or zoom change (`:342-351`). Rotating a tablet leaves the
  canvas at the old width and every field box misaligned.
- **Touch.** The overlay is mouse-only today (`mousedown`/`mousemove`/`mouseup`, `:472-498`), so
  drawing a box on a tablet is impossible. Either add pointer events, or state on narrow viewports
  that the editor is a desktop screen and offer the field list read-only. Do not ship a canvas that
  silently does nothing when touched.
- The field panel's four number inputs must wrap rather than shrink below a usable width.

---

## 5. Backend requirements

### 5.1 Endpoints as they exist

All on `process/src/main/java/process/api/PdfHighlighterTaskRestApi.java`, prefix
`/pdfHighlighter.json`, class-level `@PreAuthorize("hasRole('TENANT_USER')")` (`:28`), no
method-level override.

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/fetchAllPdfHighlighterTask` | TENANT_USER | Tenant-filtered list, `Status.Delete` excluded, newest id first (`:39-47`, service `:67-74`) |
| GET | `/fetchPdfHighlighterTaskById?pdfHighlighterTaskId=` | TENANT_USER | One task by id; `findById` plus a hand-written ownership check (`:49-58`, service `:76-88`) |
| POST | `/addPdfHighlighterTask` | TENANT_USER | Creates one, stamps the caller's tenant, returns the saved entity (`:60-69`, service `:90-106`) |
| PUT | `/updatePdfHighlighterTask` | TENANT_USER | Updates name, description, highlighter status, status. Cannot touch the file columns (`:71-80`, service `:108-135`) |
| DELETE | `/deletePdfHighlighterTask?pdfHighlighterTaskId=` | TENANT_USER | Soft delete: `status = Delete`. Fields and object untouched (`:82-91`, service `:137-153`) |
| GET | `/fetchPdfHighlighterFields?pdfHighlighterTaskId=` | TENANT_USER | The task's fields by `display_order`, after an ownership check on the task (`:93-102`, service `:155-170`) |
| POST | `/syncPdfHighlighterFields` | TENANT_USER | Delete-all-then-insert replacement of the field set (`:104-113`, service `:172-207`) |
| POST | `/uploadPdfHighlighterFile?pdfHighlighterTaskId=` (multipart `file`) | TENANT_USER | Writes to `etl-bucket`/`pdf-highlighter/<id>/` through the trusted resolver and records name/size/type (`:115-125`, service `:209-235`) |
| GET | `/downloadPdfHighlighterFile?pdfHighlighterTaskId=` | TENANT_USER | Streams the stored object inline; `IllegalArgument`/`IllegalState` become 400 carrying the message (`:127-147`, service `:237-251`) |

### 5.2 Endpoints this grooming requires that do not exist

| Method | Path | Role | What it does |
|---|---|---|---|
| DELETE | `/deletePdfHighlighterFile?pdfHighlighterTaskId=` | TENANT_USER | Deletes the stored object and clears `file_name`/`file_size`/`file_content_type`. Closes §12.4 -- today the Remove button is a lie |

The rest of the repairs are behaviour changes inside existing endpoints, not new ones:

- `uploadPdfHighlighterFile` deletes the previously recorded object when the name changes (§12.6),
  enforces a configured size ceiling (§12.10), and refuses anything that is not a PDF by extension
  and by magic bytes (§12.9).
- `downloadPdfHighlighterFile` pins its response to `application/pdf` rather than deriving it from
  the key (§12.9).
- `syncPdfHighlighterFields` validates each field before it writes any of them (§12.5) and refuses
  duplicate labels (§12.2).
- Every ownership check moves to `process.security.TenantOwnership.isOwnedByCaller` (§12.1).

A `by-name` / uuid-shaped read endpoint for the ETL is **not** required by this document; it is
Synthesis Q1.

### 5.3 Services

| Class | Role here |
|---|---|
| `PdfHighlighterTaskServiceImpl` | All nine operations. 257 lines, no test |
| `StorageBrowserService` | `uploadForWorkflow(bucket, prefix, file)` (`StorageBrowserServiceImpl.java:243-245`) and `readForWorkflow(bucket, key)` (`:310-313`) -- the trusted pair. A `deleteForWorkflow` does not exist; §5.2 needs one, or the existing `deleteObject` (`:331-335`) called with the platform-bucket guard understood |
| `TenantFilterHelper` | `enableIfNeeded` before every repository call (`:19-39`) |
| `TenantContext` | Tenant, role and user id for the request (`:22-40`) |
| `TenantOwnership` | The rule this service should be using and is not (`:35-41`) |

---

## 6. Database requirements

### 6.1 `pdf_highlighter_task`

`process/src/main/java/process/model/pojo/PdfHighlighterTask.java`. Comment on the table from
`.../V17.0-table-descriptions/V17__table_descriptions.sql:75-76`.

| Column | Type | Null | Notes |
|---|---|---|---|
| `pdf_highlighter_task_id` | bigint PK | no | `pdf_highlighter_task_id_Seq`, initial 1000 (`:29-41`) |
| `tenant_id` | bigint | **yes** | Null = platform-owned. FK to `tenant` from V12 (`.../V12__add_tenant_user_fk_constraints.sql:21`). Indexed, `idx_pdf_highlighter_task_tenant_id` (`:17-19`) |
| `task_name` | varchar | no | `:50-52`. **Not unique** |
| `description` | varchar | yes | `:54-55` |
| `highlighter_status` | varchar | no | enum `Draft`/`Ready` (`:57-60`, `process/src/main/java/process/model/enums/HighlighterStatus.java:6-8`) |
| `status` | varchar | no | enum `Inactive`/`Active`/`Delete` (`:62-65`) |
| `date_created` | timestamp | no | `@PrePersist` (`:67-69`, `:82-85`) |
| `file_name` | varchar | yes | `:71-72` |
| `file_size` | bigint | yes | `:74-75` |
| `file_content_type` | varchar | yes | `:77-78`. Written at `PdfHighlighterTaskServiceImpl.java:232` and **never read**: `getFileContentType()` has no caller anywhere in `process/src/main/java` (verified by grep), because the download derives its type from the key instead (§12.9) |

### 6.2 `pdf_highlighter_field`

`process/src/main/java/process/model/pojo/PdfHighlighterField.java`. Comment from
`V17__table_descriptions.sql:78-79`.

| Column | Type | Null | Notes |
|---|---|---|---|
| `pdf_highlighter_field_id` | bigint PK | no | `pdf_highlighter_field_id_Seq`, initial 1000 (`:19-31`) |
| `pdf_highlighter_task_id` | bigint | no | FK from V14 (`.../V14__add_remaining_fk_constraints.sql:12`). **No index** -- see below |
| `label` | varchar | **no** | `:41-43` |
| `page` | int | **no** | `:45-47` |
| `x`, `y`, `width`, `height` | double | **no** | `:49-59` |
| `display_order` | int | yes | `:61-62` |
| `selector_path` | varchar | yes | `:64-65` |
| `selector_text` | text | yes | `:67-69` |
| `selector_prefix`, `selector_suffix` | varchar | yes | `:71-75` |
| `use_xpath_first` | boolean | no, default false | `:77-80` |

The entity declares **no** `@FilterDef`/`@Filter`; it inherits its tenant through the task
(`.ai/discovery/database.md:343`).

### 6.3 Migrations needed

1. **`idx_pdf_highlighter_field_task` on `pdf_highlighter_field(pdf_highlighter_task_id)`.**
   `V18__foreign_key_indexes.sql` indexed the other FK columns and contains no `pdf` line at all
   (verified by grep). Every read and every sync in this feature filters on that column.
2. **Drop the redundant `unique = true` on both primary keys** (`PdfHighlighterTask.java:39`,
   `PdfHighlighterField.java:29`), which makes Hibernate build a second unique index beside the PK
   on a fresh schema (`.ai/discovery/database.md:536-540`).
3. **A `uuid` column on `pdf_highlighter_task`, and a per-tenant unique constraint on `task_name`**
   -- required only if Synthesis Q1 is answered "yes, `process` serves the mapping", since the
   pipeline addresses a task by name and reads back a uuid (§2.6).

Nothing else is needed to make the feature work. What is needed to make it *deployable* is not
specific to it:

> **Neither table has a creation path on stage or prod.** No changeset creates them -- V12, V14 and
> V17 only `ALTER`/`COMMENT` -- and `ddl-auto` is `validate` there
> (`process/src/main/resources/application-stage.properties:90`,
> `application-prod.properties:92`) against `update` in dev (`application-dev.properties:87`). This
> is the whole-database risk already recorded at `.ai/discovery/database.md:547-556`; it is
> mentioned here because a fresh environment stood up for this migration will hit it.

---

## 7. Validation

| # | Rule | Client | Server | Verdict |
|---|---|---|---|---|
| 1 | Task name is required and non-blank | yes -- `saveTask` refuses (`pdf-highlighter-detail.component.ts:173-176`) | yes -- add `:93-95`, update `:113-115` | **Both.** Correct |
| 2 | Task id is required on update, delete, fields, sync, upload | no | yes (`:111-112`, `:140-142`, `:158-160`, `:175-177`, `:212-214`) | **Server.** Fine -- the client always has one |
| 3 | Task name is unique | no | no | **Neither.** Harmless today; blocking if the pipeline ever addresses a task by name (§2.6) |
| 4 | Uploaded file is a PDF | yes -- MIME check on pick and on drop (`:265-268`, `:277-280`) | **no** -- `uploadPdfHighlighterFile` checks only that the file is non-empty (`:215-217`) | **Client only. A finding** -- §12.9 |
| 5 | Uploaded file is under a size ceiling | no | only the global 500 MB multipart limit (`application.properties:40-41`) | **Neither in any meaningful sense. A finding** -- §12.10. Compare `document.converter.max-file-size-mb` (`:77`) and `audio.extract.max-file-size-mb` (`:81`) |
| 6 | Uploaded file name has no path in it | n/a | yes -- `Paths.get(...).getFileName()` (`:223`) then `requireSafeKey` (`StorageBrowserServiceImpl.java:399-403`) | **Server.** Correct |
| 7 | Field label is non-blank | no -- the input accepts `""` | no -- `""` satisfies NOT NULL | **Neither. A finding.** An empty label becomes an empty column name in the extract (`pdf_highlighter_f768925.py:270`) |
| 8 | Field labels are unique within a task | no -- the counter restarts at 1 (`:89`, `:510`) | no | **Neither. A finding** -- §12.2 |
| 9 | `page`, `x`, `y`, `width`, `height` are present | no -- four `<input type="number">` that can be cleared to null (HTML `:160-163`) | no -- copied straight through (`:191-195`) into NOT NULL columns (`PdfHighlighterField.java:45-59`) | **Neither. A finding** -- §12.5, a 500 |
| 10 | `page` is within the document | no | no | **Neither.** The pipeline handles it -- it logs and writes null (`pdf_highlighter_f768925.py:253-256`) -- so this is a warning, not a refusal |
| 11 | `width` and `height` are positive | partly -- the 6 px drag floor (`:498`); typing a negative into the input is unchecked | no | **Client only, partially. A finding.** pdfplumber raises on an inverted bbox |
| 12 | `x`/`y` are inside the page | no | no | **Neither.** Same class as 10 |
| 13 | `useXpathFirst` requires a selector | yes -- the checkbox is disabled without one (HTML `:167`) | no -- defaults to false but accepts true (`:201`) | **Client only.** Low consequence: the pipeline falls back to coordinates (`pdf_highlighter_f768925.py:261-268`) |
| 14 | `highlighterStatus` is a known enum value | via a select | yes -- Jackson refuses an unknown enum | **Both** |
| 15 | The caller owns the task | the client only ever sends ids it was given | yes, on all seven id-taking operations | **Server.** §8 |

Every "client only" row in that table is reachable with `curl` and a valid TENANT_USER token.

---

## 8. Security

### Layer 1 -- the frontend guard

**Old app:** `AuthGuard` on all three routes (`app.routing.ts:198-212`), which checks
`isLoggedIn()` and nothing else (`_helpers/auth.guard.ts:16-23`). No role is consulted anywhere in
the feature; the nav entry has no condition (`app.component.html:33`). Every signed-in role sees
and can use every control.

**New app:** nothing exists. The requirement in §4.1 is `authGuard` only, deliberately -- adding
`roleGuard` would hide a page the API serves to TENANT_USER.

This layer enforces nothing. It decides what is worth rendering.

### Layer 2 -- the controller `@PreAuthorize`

One annotation, at class level: `hasRole('TENANT_USER')`
(`PdfHighlighterTaskRestApi.java:28`). **No method carries its own**, so the
"a method-level annotation replaces the class-level one" trap does not fire here -- unusually for
this codebase, and worth preserving deliberately if anyone adds a tenth endpoint.

The hierarchy at `MethodSecurityConfig.java:29` (`PLATFORM_ADMIN > TENANT_ADMIN > TENANT_USER`)
means all three roles pass. `SecurityConfig.java:55` requires authentication for the prefix; it is
not in any `permitAll` list (`:36-54`).

This layer separates *signed in* from *not signed in*, and nothing else. It draws no line between
the three roles for this feature.

### Layer 3 -- the service rule

This is where the entire decision is made, in one private method:

```java
private boolean isOwnedByCaller(PdfHighlighterTask t) {          // :60-65
    if (TenantContext.isPlatformAdmin()) return true;
    return t != null && Objects.equals(t.getTenantId(), TenantContext.getTenantId());
}
```

Called on `fetchPdfHighlighterTaskById` (`:84`), `updatePdfHighlighterTask` (`:119`),
`deletePdfHighlighterTask` (`:145`), `fetchPdfHighlighterFields` (`:164`),
`syncPdfHighlighterFields` (`:180`), `uploadPdfHighlighterFile` (`:220`) and
`downloadPdfHighlighterFile` (`:242`). Seven of nine; the list is covered by layer 4 instead, and
`addPdfHighlighterTask` has no row to own yet.

It is a **local copy** of `process.security.TenantOwnership.isOwnedByCaller`
(`process/src/main/java/process/security/TenantOwnership.java:35-41`) that drops the shared
version's second clause -- `callerTenantId != null`. The javadoc on the shared class (`:6-25`)
exists because of exactly this divergence. Consequence in §12.1.

`PdfHighlighterField` has no ownership rule of its own; both field operations reach it only after
the task check, and both key on `pdfHighlighterTaskId` (`:167-168`, `:183`). That is correct as
written -- and it is also the reason §12.1 reaches the field data too.

### Layer 4 -- the Hibernate filter

`PdfHighlighterTask` declares `tenantFilter` with the strict predicate
`tenant_id = :tenantId` (`PdfHighlighterTask.java:23-24`), the eleven-entity group at
`.ai/discovery/database.md:319`. `TenantFilterHelper.enableIfNeeded` (`:19-39`) is called at the
top of all eight read/write service methods.

Three things follow, and all three matter:

1. **The filter reaches exactly one query in this feature**:
   `findByStatusNotOrderByPdfHighlighterTaskIdDesc` (`:71-72`). Every other path is `findById`,
   which the filter does not apply to. Seven of the nine endpoints are protected by layer 3 alone.
2. **`PdfHighlighterField` declares no filter at all.** Enabling `tenantFilter` for the session has
   no effect on `findByPdfHighlighterTaskIdOrderByDisplayOrderAsc` or on
   `deleteByPdfHighlighterTaskId` -- it silently no-ops on an entity that never declared it. The
   task check above is the only thing standing there.
3. **The filter is turned off, not tightened, when the caller has no tenant** (`:28-33`). A
   tenant-less caller therefore gets an *unfiltered* list.

A row with `tenant_id IS NULL` -- which is what a platform admin's own task is, since
`addPdfHighlighterTask` stamps `TenantContext.getTenantId()` (`:97`) and the seeded platform admin
carries no tenant -- satisfies no tenant's filter and is correctly invisible in every tenant's list.

### Role by role

| Actor | List | Read one | Create | Update | Delete | Fields | Sync | Upload | Download |
|---|---|---|---|---|---|---|---|---|---|
| Anonymous | 401 | 401 | 401 | 401 | 401 | 401 | 401 | 401 | 401 |
| TENANT_USER, tenant A | A's tasks only | A's only | Creates in A | A's only | A's only | A's only | A's only | A's only | A's only |
| TENANT_ADMIN, tenant A | Identical to TENANT_USER | | | | | | | | |
| PLATFORM_ADMIN | **All tenants'** (filter disabled, `:28-33`) | Any (`:61-62`) | Creates a **platform-owned** row, `tenant_id = null` | Any | Any | Any | Any | Any | Any |
| Any non-admin principal with **no** tenant claim | **All tenants'** | Platform-owned rows | Creates a platform-owned row | Platform-owned rows | Platform-owned rows | Platform-owned rows | Platform-owned rows | Platform-owned rows | Platform-owned rows |

There is **no distinction between TENANT_USER and TENANT_ADMIN anywhere in this feature**, at any
of the four layers. Whether that is right is a product decision, not an oversight to fix silently
-- see Synthesis, Out of scope.

### Storage authorization

The upload and download deliberately bypass the browse-path guard by using the trusted resolver
(`StorageBrowserServiceImpl.java:243-245`, `:310-313`), because `etl-bucket` is a platform bucket
(`:465-467`) that no tenant may address by name. The comments at
`PdfHighlighterTaskServiceImpl.java:224-228` and `:248-249` state the justification: ownership is
checked first, and the key is composed from the task id and the name recorded on the row, so no
part of the destination came from the request. `requireSafeKey` (`StorageBrowserServiceImpl.java:399-403`)
still runs on both paths -- on the composed key during the upload (`:263`, and on the prefix itself
at `:386`) and on the key during the read (`:311`).

That reasoning is sound **and it is downstream of layer 3**. If §12.1 is reachable, the storage
guard is reachable with it.

---

## 9. Error handling

### What the server sends

| Situation | Response |
|---|---|
| No/expired token | HTTP 401 "Unauthorized" (`SecurityConfig.java:33-34`) |
| Role below TENANT_USER | HTTP 403 from Spring Security |
| Missing `pdfHighlighterTaskId` on a required param | HTTP 400 from Spring's parameter binding, before the method runs |
| Task not found, or not the caller's | HTTP **200** with `{status:"ERROR", message:"PdfHighlighterTask not found with 1002."}` on seven endpoints; HTTP **400** with the same message on `downloadPdfHighlighterFile` (`:140-142`) |
| Blank task name | HTTP 200, `{status:"ERROR", message:"PdfHighlighterTask taskName missing."}` |
| Empty upload | HTTP 200, `{status:"ERROR", message:"Uploaded file is empty."}` (`:216`) |
| Task has no file | HTTP 400, "No file uploaded for this task yet." (`:245`) |
| Anything else | HTTP 500 with the generic `ProcessUtil.INTERNAL_ERROR_500`; the real cause is logged, not sent (`:43-46` and the eight siblings) |

Not-found and refused are deliberately indistinguishable, on both the 200 and the 400 path. That is
correct and must be preserved: telling a caller "that id exists but is not yours" is an id oracle.

### What the user must see

| Failure | Message |
|---|---|
| List load failed | Error row in `app-table-shell` carrying the envelope's `message`, with Retry |
| Task not found or not yours | "That highlighter task could not be found." and a return to the list. **Not** a blank editor |
| Stored PDF missing | "No PDF is attached to this task yet." with the dropzone -- the `IllegalState` 400 case |
| Stored PDF unreadable | "Could not load the stored PDF. You can upload it again below." with the dropzone reinstated |
| Picked file is not a PDF | "Please select a PDF file." -- and after §12.9, the same message when the *server* refuses it |
| Picked file is too large | "That PDF is larger than the <n> MB limit." Client-side check before the request, server-side refusal behind it |
| PDF unparseable by pdf.js | "Could not read that PDF. Please try a different file." |
| Save failed at the task leg | The envelope's `message` in an error toast, stay on the page, keep the drawn boxes |
| Save failed at the sync leg | "The task was saved but its field mapping was not: `<message>`." Stay on the page. The distinction matters -- one succeeded and one did not |
| Save failed at the upload leg | "The task and mapping were saved but the PDF was not uploaded: `<message>`." Stay on the page |
| Duplicate label | Inline, on the offending row, before the request |
| Empty geometry | Inline, on the offending input, before the request |
| Clipboard refused | "Could not copy to clipboard" -- `copyText` reports it honestly (`clipboard.util.ts:9`) |
| 500 | "Something went wrong saving this task. Please try again." Do not surface `INTERNAL_ERROR_500` verbatim |

Three of these are impossible today because the client never inspects the envelope on the update,
sync or upload legs (§12.3).

---

## 10. Dependencies

**Outbound -- what this feature needs.**

| Dependency | Why | Where |
|---|---|---|
| `authentication-and-access` | A signed-in principal with a tenant claim; every guard reads `TenantContext` | `security/JwtAuthenticationFilter.java:36-48`, `util/JwtUtil.java:68-70` |
| `storage-connections` | `etl-bucket` must resolve to a working backend, whether through a `storage_connection` row or the `BUCKET_LIST` lookup seeded at `V9__insert_ai_provider_and_bucket_list.sql:27` | `StorageBrowserServiceImpl.resolveService:523-567` |
| `object-browser` | Shares `StorageBrowserService` and `ObjectContentDto`. A change to `requireSafeKey`, `resolveService` or the platform-bucket rule changes this feature's upload and download | `StorageBrowserServiceImpl.java` |
| pdf.js | The whole editor. Old: `pdfjs-dist ^2.16.105` + a checked-in 1.1 MB worker (`scheduler1/package.json:31`, `scheduler1/src/assets/pdf.worker.min.js`). New: `^6.2.108`, worker resolved through the bundler (`scheduler1/next/package.json:28`, `features/objects/preview/pdf-viewer.ts:101-105`). **A major-version jump the migration has to absorb** |
| The shared UI kit | §4.2 |

**Inbound -- what needs this feature.**

Nothing inside the two applications. `PdfHighlighterTask` and `PdfHighlighterField` are read by
their own service and by nothing else in `process/src/main/java` (verified by grep; the only other
mention is `TenantSeedService.java:37`, `:47`, which holds the repository purely to run
`backfillTenantId`). No dashboard tile, no report, no job. Discovery reaches the same conclusion
(`.ai/discovery/features.md:466-469`).

**Downstream, outside the applications -- and this is the part that matters.**

| Consumer | Reads | Where |
|---|---|---|
| F768925 PDF Highlighter Text Extraction | `label`, `page`, `x`, `y`, `width`, `height`, `selectorPath`, `useXpathFirst`; the `page[n]/text()[a:b]` grammar | `job-search/etl/tasks/pdf_highlighter_f768925.py:36`, `:251-270` |
| F768924 PDF Highlighter Form Fill | F768925's output file | `job-search/etl/tasks/pdf_highligter_form_fill_F768924.py:126-128` |
| Kafka listener | Routes both by pipeline id | `job-search/etl/tpd/tpd_scrapping_listener.py:139-144` |
| `PIPELINE_IDS` lookup + `source_task_type` 1011 | Seeds both ids | `V10__fix_source_task_type_and_pipeline_ids.sql:27-31`, `:41-47` |

...but connected today through a service on port 9999 that is not in this repository (§2.6).

---

## 11. Acceptance criteria

**Fixtures.** Tenants **A** and **B**. Users `userA` (TENANT_USER, tenant A), `adminA`
(TENANT_ADMIN, tenant A), `userB` (TENANT_USER, tenant B), `platformAdmin` (PLATFORM_ADMIN, no
tenant). Task **1001** "Invoice Template" owned by A, `invoice.pdf` uploaded (3 pages, text layer
present), four fields named `Invoice No`, `Date`, `Total`, `Vendor`, all on page 1, all with
selectors. Task **1002** "Claim Form" owned by B, one file, two fields. Task **1003** "Platform
Sample" with `tenant_id` NULL, created by `platformAdmin`. On disk: `receipt.pdf` (2 pages, text
layer), `scanned.pdf` (1 page, image only, no text layer), `notes.txt`, `evil.html`, and
`huge.pdf` at 300 MB.

### List

1. `userA` opens `/tools/pdf-highlighter` and sees task 1001 and no other task; 1002 and 1003 are
   absent.
2. `userB` opens the same page and sees 1002 and no other task. *(Positive control for 1.)*
3. `platformAdmin` opens the same page and sees 1001, 1002 and 1003.
4. `userA` with no tasks at all sees "No highlighter tasks yet" and a New button, and no table
   header.
5. `userA` types `invoice` into the filter and only 1001 remains; typing `zzz` shows "Nothing
   matches your filter" and a Clear that restores the row.
6. `userA` sets Highlighter Status to `Ready` while 1001 is `Draft`; the table empties. Setting it
   back to All restores 1001.
7. The Clear button is disabled with no filter set and enabled the moment one is.
8. 1001's row shows `invoice.pdf`, its size formatted by `formatSize`, its field count, a `Draft`
   chip and an `Active` chip -- both chips rendered by `status-pill`, not by ad-hoc markup.
9. `userA` clicks the copy-key button on 1001; the clipboard holds
   `pdf-highlighter/1001/invoice.pdf` and the toast calls it a storage key, not an openable path.
10. A task with no file shows an em dash in the File column and no copy button.
11. `userA` deletes 1001, confirms, and the row disappears; reloading confirms it is gone;
    `platformAdmin` sees 1001 with `status = Delete` in the database.
12. `userA` clicks Delete and then Cancel; no request is issued and the row stays.

### Create and edit

13. `userA` clicks New, leaves the name blank and presses Create; an inline error appears and **no**
    request is issued.
14. `userA` enters "Receipts", presses Create, and lands back on the list with a "Receipts" row,
    `Draft`, `Active`, no file, zero fields.
15. `userA` opens "Receipts", changes the description, saves, reopens it, and the new description is
    there.
16. `userA` opens 1001, blanks the name and saves; an inline error appears and the existing name is
    unchanged after a reload.
17. `userA` opens 1001, draws a box, then clicks Cancel; a "discard changes?" confirmation appears.
    Confirming loses the box; cancelling stays on the page with the box intact.
18. `userA` opens `/tools/pdf-highlighter/1002` directly and sees "That highlighter task could not
    be found", not a blank editor and not B's data.
19. `userA` opens `/tools/pdf-highlighter/1001` directly and the editor loads with the PDF and four
    fields. *(Positive control for 18.)*
20. `platformAdmin` opens `/tools/pdf-highlighter/1002` and the editor loads B's task.

### Upload and viewer

21. `userA` opens "Receipts" and drops `receipt.pdf` on the dropzone; page 1 renders and the toolbar
    reads `Page 1 / 2`.
22. `userA` drops `notes.txt`; an error toast says a PDF is required, the dropzone stays, and no
    request is issued.
23. `userA` bypasses the browser and POSTs `notes.txt` to `uploadPdfHighlighterFile` with a valid
    token; the server refuses it with a stated reason and `file_name` on the row is unchanged.
24. `userA` POSTs `receipt.pdf` the same way and it is accepted. *(Positive control for 23.)*
25. `userA` selects `huge.pdf` (300 MB); the client refuses it before uploading, naming the limit;
    POSTing it directly is refused by the server with the same limit named.
26. `userA` uploads `scanned.pdf` (no text layer), draws a box, and the field is created with
    coordinates and **no** selector; the panel says "No text detected under this box".
27. `userA` clicks next page and page 2 renders; previous returns to page 1; the buttons are
    disabled at each end.
28. `userA` zooms in twice and the percentage reads 150%; zoom out is disabled at 50% and zoom in at
    300%; clicking the percentage returns to fit.
29. After zooming, every existing field box still sits exactly over the same text it did before.
30. `userA` reloads the page for task 1001 and the stored PDF is fetched and rendered without the
    file being re-picked.
31. While the stored PDF is downloading, a spinner and "Loading the stored PDF…" are visible; a
    blank card is a failure of this criterion.
32. With the object deleted from storage behind its back, opening 1001 shows "Could not load the
    stored PDF. You can upload it again below." and the dropzone, not a silent blank.
33. `userA` clicks Remove on 1001, saves, reloads, and 1001 has **no** file: the File column is an
    em dash and `downloadPdfHighlighterFile` returns the "No file uploaded" 400.
34. `userA` uploads `receipt.pdf` over 1001's existing `invoice.pdf`, saves, and
    `pdf-highlighter/1001/invoice.pdf` no longer exists in `etl-bucket` while
    `pdf-highlighter/1001/receipt.pdf` does.

### Drawing and fields

35. `userA` drags a box over the invoice number on page 1; a new field appears in the panel with the
    next unused `Field N` label -- with `Field 1`..`Field 4` already renamed, the new one is
    `Field 5`, never `Field 1`.
36. `userA` clicks without dragging (under 6 px); no field is created.
37. `userA` drags a box over text; the field's selector reads `page[1]/text()[a:b]` for some
    `a <= b`, and hovering the path shows the matched text.
38. `userA` renames a field to `Total` while another field is already `Total`; an inline duplicate
    error appears and Save is blocked until one is changed.
39. `userA` clears the `x` input on a field and saves; an inline error appears on that input and
    **no** request is issued. Restoring a number lets the save through.
40. `userA` types `-40` into `width`; an inline error appears.
41. `userA` moves the third field up twice; the panel order changes, and after save-and-reload the
    fields come back in that order.
42. `userA` deletes a field, saves, reloads, and it is gone; the other three are intact.
43. `userA` unchecks `useXpathFirst` on a field with a selector, saves, reloads, and it is still
    unchecked.
44. The `useXpathFirst` checkbox is disabled on a field with no selector.
45. `userA` copies a selector path and the clipboard holds exactly the `page[n]/text()[a:b]` string
    with no surrounding whitespace.

### Mapping JSON

46. With four fields present, the JSON panel shows an array of four objects, each carrying `label`,
    `page`, `x`, `y`, `width`, `height`, `useXpathFirst`, and `selector` with `path`, `text`,
    `prefix`, `suffix` -- and no other keys.
47. `x`, `y`, `width` and `height` in that JSON are whole numbers.
48. Download produces `invoice-field-mapping.json` whose contents parse as JSON and match the panel.
49. Feeding that JSON's `fields` array to
    `job-search/etl/tasks/pdf_highlighter_f768925.py:240` (`extract_fields_from_pdf`) against
    `invoice.pdf` returns one non-null value per field. **This is the criterion that says the
    migration preserved the contract**; every other JSON criterion is a proxy for it.

### Security

50. `userB` calls `fetchPdfHighlighterTaskById?pdfHighlighterTaskId=1001` and gets
    `status: ERROR`, message `PdfHighlighterTask not found with 1001.` -- the same body as for an id
    that has never existed.
51. `userB` calls the same endpoint for 1002 and gets the task. *(Positive control for 50.)*
52. `userB` calls `fetchPdfHighlighterFields?pdfHighlighterTaskId=1001` and is refused; for 1002 it
    returns two fields.
53. `userB` POSTs `syncPdfHighlighterFields` for task 1001 with one field and is refused; 1001 still
    has its four fields. The same call for 1002 replaces B's fields.
54. `userB` POSTs `uploadPdfHighlighterFile?pdfHighlighterTaskId=1001` and is refused; nothing new
    appears under `pdf-highlighter/1001/`. The same call for 1002 succeeds.
55. `userB` GETs `downloadPdfHighlighterFile?pdfHighlighterTaskId=1001` and gets HTTP 400 with
    `PdfHighlighterTask not found with 1001.`; for 1002 it gets the PDF bytes.
56. `userB` DELETEs task 1001 and is refused; 1001 is still `Active`. Deleting 1002 succeeds.
57. `userA` calls `fetchPdfHighlighterTaskById?pdfHighlighterTaskId=1003` (the platform-owned row)
    and is refused; 1003 does not appear in `userA`'s list either.
58. `platformAdmin` calls the same for 1003 and gets it. *(Positive control for 57.)*
59. A principal whose JWT carries `userRole=TENANT_USER` and **no** `tenantId` claim calls
    `fetchAllPdfHighlighterTask` and receives an **empty** list -- not every tenant's tasks.
60. The same principal calls `fetchPdfHighlighterTaskById?pdfHighlighterTaskId=1003` and is refused.
    *(59 and 60 fail today -- §12.1.)*
61. `adminA` can do everything `userA` can on task 1001, and nothing more; there is no control
    visible to one and not the other.
62. An unauthenticated request to any of the nine endpoints returns 401.
63. `userA` opens `/objects`, and `etl-bucket` is not offered; entering it by URL is refused.
    *(Positive control: `platformAdmin` can browse it.)*
64. `userA` uploads a file named `../../escape.pdf`; the stored key is
    `pdf-highlighter/<id>/escape.pdf` and nothing is written outside that prefix.
65. `userA` uploads `evil.html` renamed to `evil.pdf`; the server refuses it on content, not just on
    extension. If it is nonetheless stored, `downloadPdfHighlighterFile` serves it as
    `application/pdf`, never `text/html`.

### Presentation

66. The list and the editor are legible in both themes; the PDF page itself is never inverted or
    tinted, and every field box is visible against both a white page and a dark gutter.
67. At 375 px wide the editor stacks viewer-then-fields-then-JSON and the page body does not scroll
    horizontally; only the canvas container does.
68. Resizing the window with a document open re-fits the page and every field box stays over its
    text.
69. On a touch device, either drawing works by touch, or the screen states that the editor needs a
    pointer and shows the field list read-only. A canvas that silently ignores touch fails.
70. Every interactive control is reachable by keyboard and has an accessible name; the canvas is
    exempt from being *drawable* by keyboard but its toolbar is not.

---

## 12. Known issues

Severities are this document's judgement, stated against the evidence.

### 12.1 A tenant-less caller owns platform rows and sees every tenant's tasks -- **major (latent)**

`PdfHighlighterTaskServiceImpl.java:60-65` compares tenants with bare `Objects.equals`. When the
caller's tenant is `null` and a row's tenant is `null`, that is `true`. `TenantOwnership`
(`process/src/main/java/process/security/TenantOwnership.java:35-41`) exists precisely to refuse
this and adds the missing clause; the javadoc at `:6-25` says so in as many words, and
`AppUserServiceImpl.java:115-118` documents the same bug and its fix. This service does not use it.

The list is worse than the by-id path. `TenantFilterHelper.enableIfNeeded:28-33` **disables** the
filter for a null tenant rather than tightening it, so `fetchAllPdfHighlighterTask` returns every
tenant's tasks to such a caller.

Reachability: it needs a non-PLATFORM_ADMIN principal whose JWT has no `tenantId` claim.
`JwtUtil.tenantIdOf` returns null when the claim is absent (`process/src/main/java/process/util/JwtUtil.java:68-70`),
`app_user.tenant_id` is nullable (`AppUser.java:56`), and the seeded platform admin is documented as
carrying no tenant (`.ai/discovery/database.md:255-257`). I have not found a live non-admin account
in that state, so this is latent rather than exploited -- which is exactly why it should be closed
before anyone creates one. Twelve other services carry the same private copy of the rule
(`ConnectionProfileServiceImpl.java:62-67`, `AiAgentServiceImpl.java:100-105`,
`SourceTaskServiceImpl.java:113-118` and nine more), so this is a codebase pattern; the fix here is
one line and should not wait for the sweep.

### 12.2 New field labels restart at `Field 1`, and duplicates silently collapse the extract -- **major**

`nextFieldNumber` is initialised to 1 (`pdf-highlighter-detail.component.ts:89`) and never seeded
from the loaded fields (`loadFieldsFromServer:143-169` does not touch it). Reopening task 1001,
whose fields are already `Field 1`..`Field 4` (or renamed from them), and drawing a fifth box names
it `Field 1` (`:510`).

Nothing de-duplicates: `syncPdfHighlighterFields:187-204` writes what it is given, and
`pdf_highlighter_field` has no unique constraint on `(pdf_highlighter_task_id, label)`. The
consumer builds its row as a dictionary keyed by label --
`row[label] = value` (`job-search/etl/tasks/pdf_highlighter_f768925.py:270`) -- so two fields with
the same name become **one column, the last one wins**, across every file in the batch, with no
error anywhere.

### 12.3 A failed save still reports success and navigates away -- **major**

The create branch checks the envelope (`:190-197`). The update branch does not:

```ts
this.pdfHighlighterService.updatePdfHighlighterTask(payload).subscribe(() => {
    this.afterTaskSaved(this.pdfHighlighterTaskId);          // :183-184
}, ...)
```

An `{status: "ERROR"}` body arrives with HTTP 200, so the success callback runs. The same omission
repeats on `syncPdfHighlighterFields` (`:225`) and `uploadPdfHighlighterFile` (`:227`). The user
gets "PDF highlighter task saved" and is returned to the list while the mapping was rejected.

### 12.4 "Remove" does not remove -- **major**

`removeFile()` (`:327-340`) clears the local state. There is no endpoint that clears the file
columns and no way for the update to do it: `PdfHighlighterTaskDto` has no `fileName`, `fileSize`
or `fileContentType` (`process/src/main/java/process/model/dto/PdfHighlighterTaskDto.java:17-22`)
and `updatePdfHighlighterTask:122-131` never writes them. Reload the page and the PDF is back, the
list still shows the path, and the object is still in the bucket.

### 12.5 Cleared geometry inputs produce a 500 -- **major**

`x`, `y`, `width`, `height` and `page` are NOT NULL (`PdfHighlighterField.java:45-59`). The panel
binds them to `<input type="number">` (HTML `:160-163`), which yields `null` when cleared. Nothing
validates: not the client, and not `syncPdfHighlighterFields:191-195`. The constraint violation
surfaces at the controller's catch-all (`PdfHighlighterTaskRestApi.java:109-112`) as HTTP 500 with
the generic message. The user sees "Internal server error" for a blank box in a form.

### 12.6 Delete keeps everything, and replace orphans the old object -- **major**

`deletePdfHighlighterTask:137-153` sets `status = Delete` on the task and stops. The field rows stay
(`pdf_highlighter_field` has no cascade -- the FK from `V14__add_remaining_fk_constraints.sql:12`
has no `ON DELETE`), and the object under `pdf-highlighter/<id>/` stays.

Worse is replace: `uploadPdfHighlighterFile:229-233` writes the new object and overwrites
`file_name` on the row without deleting the previous key. Upload `a.pdf`, then `b.pdf`, and
`pdf-highlighter/<id>/a.pdf` is now unreferenced by anything and unreachable through any UI --
`etl-bucket` is a platform bucket that no tenant can browse (§12.11). The prefix grows without
bound and nothing can be told to clean it.

### 12.7 The editor has no loading state at all -- **major**

Three flags are maintained and none is rendered:

| Flag | Assigned at | Rendered at |
|---|---|---|
| `loadingTask` | `:116`, `:134`, `:138`, `:145`, `:166` | nowhere |
| `loading` | `:281`, `:290`, `:295`, `:300`, `:304`, `:307`, `:311` | nowhere |
| `setupError` | declared `:65` | never assigned, never rendered |

The template references only `errorMessage` (HTML `:60`) and `rendering` (`:113`). `SpinnerService`
is injected (`:96`) and never called -- the list screen uses it, the editor does not. Opening a task
with a large stored PDF therefore shows a header card over empty space, for as long as the download
and the first render take, with no indication that anything is happening.

### 12.8 The selector help text promises more than the selector delivers -- **major**

The panel says the selector lets a box "still be located by content if the PDF is regenerated and
coordinates drift" (HTML `:136-138`), and the checkbox tooltip says "resolve this field by its text
selector first" (`:166`).

The selector's `path` is not content. It is a pair of **positional indices** into the page's
non-blank text items, `page[<n>]/text()[<start>:<end>]` (`:434`). The consumer resolves it by
indexing into PyMuPDF's spans and its own docstring is candid about the limit -- it keeps working
"as long as the spans before it on the page stay the same in count and order"
(`job-search/etl/tasks/pdf_highlighter_f768925.py:216-224`). A regenerated document with one extra
line above the field shifts every index after it.

The parts that *are* content -- `text`, `prefix`, `suffix` -- are captured (`:428-437`), stored
(`PdfHighlighterField.java:64-75`) and **never used by anything**: the Python reads only
`selectorPath` (`:260`). So the screen sells a robustness the implementation does not have, using
data it does have but does not use.

### 12.9 The server accepts any bytes and serves them back inline -- **major**

`uploadPdfHighlighterFile:215-217` checks only that the file is non-empty. The PDF check exists in
the browser alone (`:265-268`, `:277-280`). A signed-in TENANT_USER can therefore store
`evil.html` on their own task with `curl`.

`downloadPdfHighlighterFile` then sets `Content-Disposition: inline`
(`PdfHighlighterTaskRestApi.java:134`) and takes its content type from
`ObjectContentDto.getContentType()` (`:137`), which on all four storage backends is derived from the
**key's extension** -- `MinioObjectStorageServiceImpl.java:109`,
`S3ObjectStorageServiceImpl.java:120`, `AzureBlobObjectStorageServiceImpl.java:116` and
`FtpObjectStorageServiceImpl.java:379`, all calling `ContentTypeUtil.contentTypeFor`. That map
contains `html -> text/html` (`process/src/main/java/process/util/ContentTypeUtil.java:34-35`,
`:86-89`).

So the endpoint will serve attacker-authored HTML, inline, with `text/html`, to any authenticated
caller who opens the URL. Mitigations, stated honestly: the attacker must already have a valid
token; the API is served from a different origin than the SPA
(`scheduler1/next/src/app/core/api/api.config.ts:6` puts the API on port 9098), so the SPA's own
storage is not directly reachable; and the Angular client fetches the response as a blob and never
navigates to the URL. It is still a stored-content-served-inline channel that nothing closes.

### 12.10 No size ceiling on the upload -- **major**

The only limit is the global multipart cap of 500 MB
(`process/src/main/resources/application.properties:40-41`). The two comparable features both
declare their own, with the reasoning written down: `document.converter.max-file-size-mb` defaults
to 50 (`:75-77`) and `audio.extract.max-file-size-mb` to 250 (`:79-81`). The highlighter declares
nothing.

The browser side makes it worse: `readFileAsArrayBuffer` (`:30-37`) loads the whole file into
memory before pdf.js sees it, and `loadStoredFile` does the same to the downloaded blob (`:302-303`).
A 300 MB PDF is a hung tab.

### 12.11 The copied path names a bucket the copier cannot open -- **minor**

`filePathFor` builds `pdf-highlighter/<id>/<name>` and offers it as a copyable path
(`pdf-highlighter.component.ts:94-106`, HTML `:62-70`). The bucket is not named in the string and
is `etl-bucket`, which `StorageBrowserServiceImpl.resolveServiceForCaller:431-437` refuses to
everyone below PLATFORM_ADMIN because `isPlatformBucketName:465-467` matches it against
`KafkaSecretService.SECRET_BUCKET` (`:27`). Pasting the copied value into the Object Browser gets
`Unknown bucket: etl-bucket.` The affordance implies an access the product does not grant.

### 12.12 Responses return the JPA entity, including its tenant association -- **minor**

`fetchAllPdfHighlighterTask` and `fetchPdfHighlighterTaskById` put `PdfHighlighterTask` itself in
the envelope (`:73`, `:85`), and `addPdfHighlighterTask` and `uploadPdfHighlighterFile` do the same
(`:104-105`, `:234`). The entity exposes a lazy `getTenant()` (`PdfHighlighterTask.java:46-48`,
`:99-101`) with no `@JsonIgnore`, no `Hibernate5Module` is registered anywhere in `process`, and
`spring.jpa.open-in-view` is not set in any profile -- so Spring Boot's default of `true` applies
and the proxy initialises during serialization. The tenant row (name, code, uuid, status) would then
ride along on every task in the list. **Not verified against a running server**; verified are the
absent `@JsonIgnore`, the absent Jackson module and the absent property.

### 12.13 Field ids are not stable across saves -- **minor**

`syncPdfHighlighterFields:183-205` deletes every row for the task and inserts fresh ones. Every save
burns ids from `pdf_highlighter_field_id_Seq` proportional to the field count, and no external
reference to a `pdf_highlighter_field_id` can survive a save. Nothing depends on that today -- the
client keys on a local `field-<timestamp>-<n>` string (`:39-43`) and the pipeline keys on `label` --
but it is a contract worth knowing before anyone adds one.

### 12.14 Selector back-fill races the field load -- **minor**

`loadTask` starts `loadStoredFile` (`:128-130`) and then, synchronously, `loadFieldsFromServer`
(`:132`). `enrichFieldSelectors` runs at the end of `renderPage` (`:368`) over
`this.fields` (`:372`). If the render wins the race -- likely with a small cached PDF -- the field
list is still empty and nothing is enriched, and no later render happens until the user changes page
or zoom. Only fields stored without a selector are affected.

### 12.15 Redundant unique indexes on both primary keys -- **cosmetic**

`unique = true` on `pdf_highlighter_task_id` (`PdfHighlighterTask.java:39`) and
`pdf_highlighter_field_id` (`PdfHighlighterField.java:29`) makes Hibernate build a second unique
index beside each primary key on a fresh schema. Recorded across the codebase at
`.ai/discovery/database.md:536-540`.

---

## 13. Missing functionality

**The entire new-app implementation.** Three routes, a nav entry, a service over nine endpoints,
two screens, a canvas editor, and the two `status-pill` entries for `Draft` and `Ready`. Estimated
from the old app's 787 lines of TS and 349 of HTML, and from the new app's tighter shared kit:
roughly 600-800 lines of new TypeScript plus templates. **L.** The canvas editor is the bulk of it
and none of it is boilerplate.

**A pdf.js major-version jump.** `^2.16.105` to `^6.2.108`
(`scheduler1/package.json:31` vs `scheduler1/next/package.json:28`). The old code uses
`require('pdfjs-dist/legacy/build/pdf.js')` with a checked-in worker asset; the new app uses a
dynamic `import('pdfjs-dist')` and resolves the worker through the bundler
(`features/objects/preview/pdf-viewer.ts:101-105`). The APIs the editor depends on --
`getViewport`, `convertToViewportPoint`, `getTextContent`, and the shape of a text item's
`transform`/`width`/`height` (`:394-408`) -- must be re-verified against 6.x, because
`buildSelector`'s indices are derived from that item list and a change in what pdf.js considers an
item changes every stored selector's meaning. **M, and it is the risk in the whole migration.**

**No way to delete or replace the stored PDF properly.** §12.4, §12.6. One new endpoint and a
delete inside the upload. **S.**

**No box manipulation after drawing.** A box can only be adjusted by typing into four number inputs
(HTML `:160-163`). There are no drag handles, no move, no snap, no nudge -- verified: the overlay
handlers (`:472-526`) only ever create. For a screen whose entire job is placing rectangles
accurately, this is the largest usability gap in the feature. **M.**

**No extraction preview.** The panel shows the text the selector matched, in a `title` attribute
(HTML `:173`), but nothing shows what the *coordinate* crop would yield, and there is no dry run
against a second document. Someone drawing a mapping for four thousand files cannot check it against
two. **M**, and the highest-value addition beyond parity.

**No task duplication.** Every mapping starts from an empty page. Templates differ from each other
by a few boxes far more often than they differ entirely. **S.**

**No pagination or server-side search.** `fetchAllPdfHighlighterTask` returns everything
(`:71-72`), filtered in the browser. Fine at tens, not at thousands. **S** to add a client-side
pager from `shared/ui/pager.ts`; **M** to push it to the server.

**No audit columns.** `pdf_highlighter_task` has no `created_by`/`updated_by`; V22 added them to
other tables and did not touch this one (verified by grep over
`process/src/main/resources/db/changelog`). "Who drew this box" is unanswerable. **S.**

**No `uuid`, no per-tenant unique `task_name`, and no `by-name` read.** Required only if `process`
is to serve the mapping the pipeline fetches (§2.6, Synthesis Q1). **M.**

**No tests, anywhere.** Nine untested endpoints, an untested service holding the only real
authorization rule in the feature, and an untested 602-line canvas component. What is needed, at
minimum:

- `PdfHighlighterTaskServiceImplTenantIsolationTest`, modelled on the eight existing
  `*TenantIsolationTest` files, covering criteria 50-60 -- refusals **and** their positive controls.
- A unit test over `selector.ts` pinning the `page[n]/text()[a:b]` grammar, the 30-character
  context windows and the six-item look-around, so the string the Python regex parses cannot drift
  unnoticed.
- A component spec for the editor covering the drag floor, the label counter, and the three save
  legs' error handling.

**M**, and it is the difference between a migration and a rewrite nobody can verify.
