# Grooming -- Object Browser

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

Status from Discovery: **migrated** (`.ai/discovery/features.md:42`). Old route `objectBrowser`,
new route `objects`. This document compares the two implementations behaviour by behaviour and
records what the rewrite dropped, what it fixed, and what neither app ever got right.

---

## 1. Purpose

"Show me what is actually in the bucket, and let me do something about it."

Every other screen in this product talks about files indirectly -- a job writes somewhere, a
converter reads from somewhere, a transcript is saved somewhere. The Object Browser is the one
screen where a person can open the storage a connection points at and see the files themselves:
walk the folders, find the file that was supposed to arrive last night, look inside it without
downloading it, fix a typo in a config file, email a colleague a copy, delete the mess a failed
run left behind, and -- because reading a 40-page PDF to answer one question is not a good use of
anybody's afternoon -- ask a model about a file's contents in a chat panel beside it.

It is deliberately a *browser*, not a file manager: there is no move, no copy, no drag-and-drop
between folders. The operations it offers are the ones an operator actually needs while
diagnosing a pipeline.

The buckets it browses are not its own. They come entirely from the `storage-connections` feature
(a `storage_connection` row) or from the legacy `BUCKET_LIST` lookup family. The Object Browser
owns no table of its own.

---

## 2. Existing behaviour

### 2.1 Old app -- `ObjectBrowserComponent`

One component, 1,904 lines of TypeScript and a 694-line template
(`scheduler1/src/app/_component/object-browser/object-browser.component.ts`, `.html`). Route
`objectBrowser`, guarded by `AuthGuard` only -- no role check
(`scheduler1/src/app/app.routing.ts:188-192`). Linked from the top nav at
`scheduler1/src/app/app.component.html:20`, and deep-linked into from the source-task screen and
the linked-task panel (`_component/source-task/source-task.component.html:273`,
`_component/linked-task-panel/linked-task-panel.component.html:46`).

**Bucket selection and navigation.** A `<select>` fed by `storage.json/buckets`
(`:249-265`), showing `label (provider)`. When the list is empty it shows an inline
"No buckets configured yet" hint with a link to `/setting/storageConnection`
(`.html:19-25`). `?bucket=&prefix=` deep-links straight into a folder, ignoring a bucket that is
not in the fetched list (`:267-283`). Breadcrumbs are rebuilt from the prefix. Changing bucket,
opening a folder, or clicking a breadcrumb all clear the preview panel, the selection and the
search filters (`:284-299`, `:654-663`, `:665-680` -- each calls `resetSearch()` at `:293`,
`:661`, `:678`).

**Listing.** `listObjects` with `maxKeys = 50` (`_services/storage.service.ts:17`), and infinite
scroll: `onTableScroll` fires another page when within 120 px of the bottom (`:635-641`). A
response for a bucket/prefix the user has since left is discarded and re-issued (`:527-531`).

**Per-folder size column.** For every folder row the component issues its own
`listObjects(bucket, folderKey, null, 1000)` and shows "N files, M folders" in the Size column,
with `1000+ entries, showing ` prefixed when the page was capped (`loadFolderStats`, `:585-621`;
`folderStatLabel`, `:623-633`). On FTP/FTPS this fan-out is deliberately skipped until the user
opens Folder Insights, because a request there costs a full connect + login (`:342-358`, with a
comment recording 14 s measured against a real mirror).

**Folder Insights.** Four echarts donuts -- Files vs Folders, Sub-folder Sizes, File Types,
Upload Age -- built from a *separate* `listObjects(..., 1000)` stats pass over the current prefix
(`loadDirectoryStats`, `:354-406`), plus the per-folder byte totals for the Sub-folder Sizes tile
(`:459-481`). Shown by default, except on FTP/FTPS (`:290-293`). A "Showing stats for the first
N+ entries" note appears when the stats page was capped (`.html:108-111`).

**Filters.** Name contains (case-insensitive) plus a modified-from / modified-to date range,
applied client-side over the rows already loaded (`filteredObjects`, `:682-704`). Folders are
exempt from the date range. A "Clear" button appears while any filter is set, and a standing help
line says "Search applies to files loaded so far -- scroll down first to load more, then search"
(`.html:223-226`).

**Selection and bulk actions.** A checkbox per row -- **files and folders alike** -- plus a
select-all over the filtered rows (`:716-750`). The bulk bar offers Download (files only; folders
are silently skipped, and the tooltip says so -- `.html:117-120`), Email (the whole selection as a
ZIP), Delete, and Clear selection. Bulk download is staggered at 350 ms per file
(`BULK_DOWNLOAD_STAGGER_MS`, `:53`, `:757-766`).

**Row actions.** A "Robot action" lightning button opens the chat, and a kebab menu offers View,
Download, Email, Rename (folders), Copy path, Copy ETag (files with an etag), and Delete
(`.html:161-215`). Email is offered on folders as well as files.

**Preview modal.** `objectPreviewModal` loads `objectMetadata` first, then the content
(`selectObject`, `:1367-1390`). Kinds: json (pretty-printed), csv/txt/xml (`<pre>`), md (rendered
through `marked`), pdf/mp3/m4a/mp4/image (blob URL through `bypassSecurityTrustResourceUrl`), and
**doc/docx converted to PDF on the fly** through `documentConverter.json/convert`
(`loadDocPreview`, `:1476-1508`). `.gz` files preview as their inner type
(`effectivePreviewExtension`, `:1392-1400`). Text kinds json/csv/txt/xml/md are **editable**: an
Edit/View toggle, a textarea, and a Save that writes the file back through `uploadObject` and then
re-reads the metadata to refresh the row (`savePreview`, `:1554-1600`). A Copy button copies the
whole content.

**Email share.** A modal taking recipient + optional message, posting `fileShare.json/send` with
either `key` (single) or `keys` (bulk) (`:1783-1826`).

**File chat.** A floating, minimisable widget bound to one file (`.html:236-390`). Agent picker
filtered to `status === 'Active' && (apiKeyConfigured || provider === 'Ollama')` (`:951-970`);
`prepareContext` reports how much of a long file the model will see; suggested prompts;
`webkitSpeechRecognition` dictation (`:815-850`); a Stop button and an 8-second "still working"
hint; copy-message; and the fenced-file protocol that turns ```` ```csv ```` + `TARGET_FORMAT: xlsx`
into a real download via `fileChat.json/exportFile` (`:1108-1205`). Switching to a different file
while a chat is open raises a **"Leave this chat?"** confirmation
(`confirmLeaveChatIfNeeded`, `:922-932`; modal at `.html:600-624`); closing a non-empty chat
raises a **"Close this chat?"** confirmation (`:900-910`; modal at `.html:628-654`). Files the
model produced can be previewed before download in `chatFilePreviewModal`, which renders markdown
and raw HTML through `bypassSecurityTrustHtml` (`:1236-1252`).

Eight modals in total, matching `.ai/discovery/frontend-old.md:672`.

### 2.2 New app -- `Objects`

`scheduler1/next/src/app/features/objects/objects.ts` (487 lines) plus `objects.html` (283),
`storage.service.ts` (132), `chat/file-chat.ts` (413) + `.html` (183) + `chat-export.ts` (186),
`preview/preview-dialog.ts` (264) + `.html` (135) + `pdf-viewer.ts` (176) + `audio-player.ts`
(104), and two small dialogs. Route `objects` with `data: { minRole: 'TENANT_USER' }` and
`roleGuard` (`scheduler1/next/src/app/app.routes.ts:270-282`); nav entry at
`features/shell/shell.ts:69`.

**What it does the same or better.**

- **Connection picker as cards.** With no bucket chosen the screen renders every connection as a
  clickable card with a provider icon and pill, and an empty state linking to `/admin/storage`
  (`objects.html:23-68`).
- **Stale-response guard.** `load()` carries a monotonic ticket; a response whose ticket is stale
  is dropped rather than allowed to overwrite the current folder (`objects.ts:204-235`). The old
  app re-issued the request instead.
- **Download actually works.** `StorageService.download()` calls
  `storage.json/downloadObject` through `HttpClient`, so the interceptor attaches the token
  (`storage.service.ts:62-75`). The old app downloaded through
  `previewObjectArrayBuffer` -- i.e. the *preview* endpoint -- for every download in the browser
  (`object-browser.component.ts:1714-1715`), which the server refuses for any non-previewable type.
- **A real PDF viewer** drawing to a canvas with page nav and zoom (`preview/pdf-viewer.ts`) and a
  themed audio player (`preview/audio-player.ts`), replacing an `<iframe>` and a native `<audio>`.
- **Safe markdown.** `shared/ui/markdown.ts` parses to blocks and renders through templates, never
  `innerHTML` -- so model output cannot inject markup. The old chat-file preview called
  `bypassSecurityTrustHtml` on model-produced HTML (`object-browser.component.ts:1245`).
- **CSV formula defusal.** A `csv`/`tsv` fence has cells starting `= + - @` prefixed with an
  apostrophe before it becomes a downloadable file (`chat/chat-export.ts:80-95`), with tests
  (`chat/csv-injection.spec.ts`).
- **`endSession`.** Closing the chat posts `fileChat.json/endSession`, dropping the extracted text
  from the Redis cache (`chat/file-chat.ts:150-151`). The old app had no such call at all
  (`scheduler1/src/app/_services/file-chat.service.ts` has only three methods).
- **Chat transcript survives a reload** for 30 minutes in `sessionStorage`
  (`chat/file-chat.ts:73-120`).
- **Retry / Regenerate** on the last exchange (`chat/file-chat.ts:175-183`).
- **`prepareContext` passes `aiAgentId`** (`chat/file-chat.ts:232`), so the truncation warning is
  computed against the chosen provider's limit rather than always the smallest.

**What it dropped or changed.** Enumerated with evidence in §12 and §13; in summary: folder
selection and folder bulk actions, emailing a folder, multi-file upload, the per-folder size
column, the Sub-folder Sizes chart, the separate 1,000-key insights pass, copy-current-path,
the "leave this chat?" confirmation, doc/docx preview, rendered markdown preview, filter reset on
navigation, and the "search only covers loaded rows" hint.

### 2.3 Backend

`process/src/main/java/process/api/StorageBrowserRestApi.java` -- eleven endpoints, class-level
`@PreAuthorize("hasRole('TENANT_USER')")` at `:36` with no method-level override anywhere, so the
class annotation stands for all eleven. `previewObject`/`downloadObject` share `streamObject`,
which honours an HTTP `Range` header and answers `206` with `Content-Range` (`:210-243`).

`process/src/main/java/process/model/service/impl/StorageBrowserServiceImpl.java` (569 lines) is
where the real authorisation lives -- see §8.

`FileChatRestApi` / `FileChatServiceImpl` / `FileChatExtractionServiceImpl` back the chat panel;
`FileShareRestApi` / `FileShareServiceImpl` back the email share.

---

## 3. Expected behaviour

The new app is the product going forward; the old one is the specification of what the feature was
understood to do. Expected behaviour is therefore "everything the old app did, in the new app's
shape, minus what was deliberately dropped, plus the things the new app already does better".

Where expectation differs from today:

1. **A folder must be selectable and bulk-deletable.** Today the new app renders a checkbox only
   for files (`objects.html:195-199`), so the only way to remove a folder is one at a time from
   the kebab menu. The old app allowed a mixed selection and fanned out
   `deleteObject`/`deleteObjects`/`deleteFolder` accordingly
   (`object-browser.component.ts:1660-1701`). The backend supports it (`deleteFolder` is recursive).
2. **A folder must be emailable.** `FileShareServiceImpl.emailSelection` already zips a folder
   recursively when the single key ends in `/` (`:88-93`, `:139-153`), and the old app exposed
   that (`.html:184-189`). The new app offers Email only on files (`objects.html:237-239`), so a
   working server capability has no caller.
3. **Upload must accept more than one file at a time.** `onUpload` reads `input.files?.[0]`
   (`objects.ts:340`) and the input carries no `multiple` (`objects.html:102`). The old app
   uploaded a whole selection sequentially (`object-browser.component.ts:1841-1878`).
4. **A deleted file must leave the selection.** After `remove()` the key stays in `selected()`
   (`objects.ts:285-311`), so the bulk bar keeps counting a row that no longer exists. The old app
   removed it (`object-browser.component.ts:1695`).
5. **Changing bucket or folder must reset the filters, or the UI must say it did not.** The new
   `onBucketChange` clears `search` but not `dateFrom`/`dateTo` (`objects.ts:195-202`), and neither
   `openFolder` nor `goToCrumb` clears anything (`:237-255`). A date range set in one folder
   silently hides rows in the next.
6. **The chat panel must be rebound, not reused, when the file or bucket changes.** See §12.1 --
   this is the most serious defect in the feature today.
7. **Chat history must reach the model.** See §12.2.
8. **The preview must only offer kinds the server will actually serve**, or must fall back
   gracefully. See §12.3.
9. **One byte formatter per screen.** See §12.6.

Everything else -- infinite scroll versus a "Load more" button, four insight tiles versus four
different insight tiles, a modal versus a CDK dialog -- is a deliberate restyling and is not a gap.

---

## 4. Frontend requirements

### 4.1 Routes

| App | Route | Guard | Notes |
|---|---|---|---|
| Old | `objectBrowser` | `AuthGuard` (`app.routing.ts:190`) | Signed-in only; no role check |
| New | `objects` | `roleGuard`, `data.minRole = 'TENANT_USER'` (`app.routes.ts:278-281`) | Mirrors the API floor; a token with no readable role lands on `/unauthorized` instead of a page of refused calls |

Both accept `?bucket=` and `?prefix=` for deep entry (`object-browser.component.ts:267-283`,
`objects.ts:178-193`). `features/notifications/notification-links.ts:13` rewrites a stored
`/objectBrowser` notification target to `/objects`.

### 4.2 Components (new app)

| Component | File | Role |
|---|---|---|
| `Objects` | `features/objects/objects.ts` + `.html` | The screen: picker, breadcrumbs, filters, insights, table, bulk bar |
| `StorageService` | `features/objects/storage.service.ts` | All eleven `storage.json` calls; also used by `/tools/converter`, `/tools/transcript`, `/profile` |
| `PreviewDialog` | `features/objects/preview/preview-dialog.ts` + `.html` | Modal preview + inline edit + save |
| `PdfViewer` | `features/objects/preview/pdf-viewer.ts` | Canvas PDF render, page nav, zoom |
| `AudioPlayer` | `features/objects/preview/audio-player.ts` | Themed transport, seek, rate |
| `FileChat` | `features/objects/chat/file-chat.ts` + `.html` | Floating chat panel |
| `chat-export.ts` | `features/objects/chat/chat-export.ts` | Fence grammar, CSV defusal, export routing |
| `PromptDialog` | `features/objects/dialogs/prompt-dialog.ts` | New folder / rename |
| `ShareDialog` | `features/objects/dialogs/share-dialog.ts` | Email recipient + message |

### 4.3 Forms and dialogs

| Dialog | Fields | Client validation | Submit |
|---|---|---|---|
| New folder | Folder name | non-empty after trim (`prompt-dialog.ts:30`, `:44-45`) | `createFolder` |
| Rename folder | New name (prefilled) | non-empty after trim; no-op when unchanged (`objects.ts:424`) | `renameFolder` |
| Email | Recipient (email), Message (optional) | `/\S+@\S+\.\S+/` (`share-dialog.ts:44`) | `fileShare.json/send` |
| Delete (file/folder/selection) | -- | -- | `confirmWith(...)` then `deleteObject` / `deleteFolder` / `deleteObjects` |
| Preview | Textarea when editing | Save disabled while unchanged (`preview-dialog.html:33`) | `uploadObject` |
| Close chat | -- | Only raised when the transcript is non-empty (`file-chat.ts:133`) | `endSession` |

### 4.4 Table

Columns: select, Name, Modified, Size, Type, actions (`objects.html:178-189`). Folders sort ahead
of files -- the object stores do this naturally and `FtpObjectStorageServiceImpl:302-305` sorts
explicitly to match. Folders show `—` for Size and Type
(`objects.html:218`, `:221`) because the DTO omits them for a directory
(`MinioObjectStorageServiceImpl.toObjectSummaryDto:202-215`).

### 4.5 Loading, empty and error states

| State | Old | New |
|---|---|---|
| Buckets loading | "Loading buckets..." in the select (`.html:16`) | No dedicated state; picker is empty until resolved |
| No buckets | Inline hint + "Add a connection" (`.html:19-25`) | Full empty card + `/admin/storage` link (`objects.html:54-68`) |
| Listing | "Loading..." row (`.html:219-221`) | Full-panel "Loading…" only when nothing is loaded yet (`objects.html:173-174`) |
| Empty folder | "This folder is empty." (`.html:216-218`) | Same (`objects.html:259`) |
| Filtered to nothing | "No files match your search." | `Nothing matches "<term>"` -- **only when the name filter is set**; a date-only filter falls through to "This folder is empty." (`objects.html:257-260`) |
| Listing failed | Toast | In-panel message + "Try again" (`objects.html:168-172`) |
| Preview failed | `previewError` line (`.html:414`) | Centred error + "Try again" + "Download instead" (`preview-dialog.html:66-78`) |
| Not previewable | "Preview isn't available for this file type -- use the Download action" | "No inline preview for this file type" + Download (`preview-dialog.html:81-95`) |
| Chat preparing / failed | "Preparing this file for chat…" / error line | "Reading the file…" / error line (`file-chat.html:33-36`) |

### 4.6 Dark and light mode

Only the new app has themes. `core/theme.service.ts` toggles `html.dark` from
`localStorage['etl_theme']`, falling back to `prefers-color-scheme`
(`.ai/discovery/frontend.md:563-571`). Every colour on this screen is a token
(`var(--text-muted)`, `var(--text-secondary)`, `bg-sunken`, `border-subtle`, `pill-warn`,
`text-crit-500`), and the two `color-mix` tints in the chat panel derive from
`--color-warn-500` / `--color-crit-500` / `--accent-text`
(`file-chat.html:43`, `:80`, `:94`). The old app is light-only.

### 4.7 Responsive behaviour

- Header stacks; the connection picker is `w-full sm:w-72` (`objects.html:9`).
- Connection cards: `sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4` (`objects.html:36`).
- Insights: `md:grid-cols-2 xl:grid-cols-4` (`objects.html:142`).
- Breadcrumb and toolbar rows are `flex-wrap` (`objects.html:72`, `:74`, `:111`).
- The table scrolls in its own `overflow-x-auto scroll-table` box (`objects.html:176`).
- Dialogs are `max-w-[calc(100vw-2rem)]` (`preview-dialog.html:1`, `prompt-dialog.ts:16`).
- The chat panel is `fixed bottom-4 right-4 w-[32rem] max-w-[calc(100vw-2rem)]` with height
  `min(38rem, calc(100vh - 3rem))` (`file-chat.html:1-3`).

---

## 5. Backend requirements

### 5.1 Endpoints

`StorageBrowserRestApi` -- `@RequestMapping("/storage.json")`, class-level
`@PreAuthorize("hasRole('TENANT_USER')")` (`:36`), no method-level override.

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/storage.json/buckets` | TENANT_USER | Buckets this caller may see: active storage connections plus non-shadowed `BUCKET_LIST` lookups (`StorageBrowserServiceImpl:86-135`) |
| GET | `/storage.json/listObjects` | TENANT_USER | One page; `maxKeys` defaults to 50 at the controller (`:64`), defaults to 50 and is capped at 500 in the service (`:47-49`, `:139-141`) |
| GET | `/storage.json/objectMetadata` | TENANT_USER | name, key, size, lastModified, etag, contentType, `previewable` (`ObjectMetadataDto`) |
| GET | `/storage.json/previewObject` | TENANT_USER | `Content-Disposition: inline`; honours `Range` (206 + `Content-Range`); refuses a non-previewable extension; inflates a previewable `.gz` whole, capped at 8 MB (`:161-212`) |
| GET | `/storage.json/downloadObject` | TENANT_USER | Same stream, `attachment`, no previewable gate (`:219-223`) |
| POST | `/storage.json/uploadObject` | TENANT_USER | Multipart into `bucket` + `prefix`; strips any path from the filename; transcodes audio to AAC where needed (`:249-292`) |
| POST | `/storage.json/createFolder` | TENANT_USER | Zero-byte `prefix/name/` marker; `/` and `\` stripped from the name (`:315-329`) |
| DELETE | `/storage.json/deleteObject` | TENANT_USER | One key |
| POST | `/storage.json/deleteObjects` | TENANT_USER | `{bucket, keys[]}` body; every key safety-checked (`:337-346`) |
| DELETE | `/storage.json/deleteFolder` | TENANT_USER | Recursive; key must end `/` (`:348-353`) |
| POST | `/storage.json/renameFolder` | TENANT_USER | Copy-then-delete within the same parent; no-op when the name is unchanged (`:355-376`) |

`FileChatRestApi` -- `@RequestMapping("/fileChat.json")`, class-level TENANT_USER (`:22`).

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/fileChat.json/prepareContext` | TENANT_USER | Extracts the file's text and reports `{truncated, charsUsed, totalChars, limit}` against the chosen agent's provider (`FileChatServiceImpl:141-169`) |
| POST | `/fileChat.json/endSession` | TENANT_USER | Evicts the cached extraction for bucket+key+etag; succeeds when there was nothing cached (`:128-139`) |
| POST | `/fileChat.json/sendMessage` | TENANT_USER | One turn: resolves the agent, re-extracts, builds the instruction block, calls the provider (`:171-233`) |
| POST | `/fileChat.json/exportFile` | TENANT_USER | `csv\|txt\|html\|md` → `xlsx\|docx\|pdf` through LibreOffice, returned base64; content capped at 200,000 chars (`:235-262`) |

`FileShareRestApi` -- `@RequestMapping("/fileShare.json")`, class-level TENANT_USER (`:20`).

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/fileShare.json/send` | TENANT_USER | Emails one file as an attachment, or a folder / multi-key selection as a ZIP (`FileShareServiceImpl:53-117`) |

`AiAgentRestApi` -- class-level TENANT_ADMIN (`:21`), with `fetchAllAgents` **overridden** to
TENANT_USER (`:62-63`). This is the one place the non-repeatable-`@PreAuthorize` rule matters for
this feature, and it is what lets the chat panel populate its agent picker.

### 5.2 Services

| Service | File | Responsibility |
|---|---|---|
| `StorageBrowserServiceImpl` | `model/service/impl/StorageBrowserServiceImpl.java` | Bucket resolution, per-request authorisation, key safety, gzip preview, upload normalisation |
| `StorageClientFactory` | `config/StorageClientFactory.java` | A configured client per `StorageConnection` |
| `BucketRewritingStorageService` | `model/service/impl/BucketRewritingStorageService.java` | Maps the alias the caller names onto the real bucket/container name (`StorageBrowserServiceImpl:540-546`) |
| `MinioObjectStorageServiceImpl` / `S3…` / `AzureBlob…` / `FtpObjectStorageServiceImpl` | same package | Provider adapters |
| `FileChatExtractionServiceImpl` | same package | Text out of a file: native text, `.gz`, audio transcript, PDF text layer, LibreOffice→PDF for everything else, vision-model fallback. Cached in Redis under `fileChatExtract` for 7 days (`:91-128`) |
| `FileChatServiceImpl` | same package | Session lifecycle, per-provider prompt budget, instruction block, export |
| `FileShareServiceImpl` | same package | Zip + email, with a 20 MB / 500-file ceiling (`:41-43`) |

---

## 6. Database requirements

**This feature owns no tables.** Buckets are external; the rows it reads belong to other features.

| Table | Columns this feature reads | Owner |
|---|---|---|
| `storage_connection` | `alias`, `connection_name`, `provider`, `bucket_name`, `status`, `tenant_id` | `storage-connections` (`.ai/discovery/database.md:155`) |
| `lookup_data` (`BUCKET_LIST` children) | `lookup_type`, `lookup_value` (the bucket name), `description` (the provider), `tenant_id` | `platform-configuration`; seeded by `V9.0-ai-provider-bucket-list.yaml` with ids 1024--1027 (`.ai/discovery/database.md:114`) |
| `ai_agent` | via `aiAgent.json/fetchAllAgents` only, for the chat picker | `content-and-ai-tools` (`.ai/discovery/database.md:158`) |

**No migration is needed for this feature.** Anything that changes here changes code, not schema.

Two properties are load-bearing and are not schema: `StoragePropertyDefaults.AVATAR_BUCKET` (the
avatar bucket name) and `KafkaSecretService.SECRET_BUCKET` -- both are named directly in
`StorageBrowserServiceImpl.isPlatformBucketName` (`:503-505`).

---

## 7. Validation

| Rule | Client | Server | Verdict |
|---|---|---|---|
| A bucket must be chosen before listing | `objects.ts:208` returns early | `resolveService` throws on a null bucket (`:520-524`) | Both |
| Folder name non-empty after trim | `prompt-dialog.ts:30`, `:44` | `createFolder` throws "Folder name is required." (`:317-319`) | Both |
| Folder name may not contain a separator | none | `/` and `\` stripped, then `requireSafeKey` on the composed key (`:322-327`) | **Server only** |
| Rename target non-empty / no separator | `prompt-dialog.ts:30` | `:361-366`, then `requireSafeKey(newPrefix)` (`:373`) | Both (separator: server only) |
| A folder key must end with `/` | implied by the data | `requireFolderKey` (`:378-382`) | Server only |
| No `.` / `..` segment, no `\`, no leading `/` in any key | none | `requireSafeKey` / `isSafeKey` on every path that names a key (`:394-411`) | **Server only** -- and correctly so |
| Uploaded file non-empty and named | none | `:251-258` | **Server only** |
| Uploaded filename carries no path | none | `Paths.get(name).getFileName()` then `requireSafeKey` on the composed key (`:259-263`) | **Server only** |
| Recipient email well-formed | `/\S+@\S+\.\S+/` (`share-dialog.ts:44`) | `^[^\s@]+@[^\s@]+\.[^\s@]+$` (`FileShareServiceImpl:39`, `:62-64`) | Both; the client comment says outright that the server is the authority |
| Email payload ≤ 20 MB and ≤ 500 files | none | `checkLimits` (`FileShareServiceImpl:176-186`) | **Server only** |
| Single file ≤ 20 MB to email | none | `:124-127` | **Server only** |
| Preview only for a supported extension | `preview-dialog.ts:121-130` decides the renderer | `ContentTypeUtil.isPreviewable` gates the stream (`StorageBrowserServiceImpl:163-165`) | Both -- **and the two lists disagree**; see §12.3 |
| Inflated `.gz` ≤ 8 MB | none | `MAX_GZIP_PREVIEW_BYTES` (`:51`, `:190-196`) | Server only |
| An agent must be chosen before sending | `file-chat.ts:248-251` | "Pick an AI Agent first." (`FileChatServiceImpl:179-181`) | Both |
| Message non-empty | `file-chat.ts:247` and the disabled Send (`file-chat.html:180`) | `:182-184` | Both |
| Export source ∈ {csv,txt,html,md}, target ∈ {xlsx,docx,pdf} | `chat-export.ts:24` only produces those | `:245-250` | Both |
| Export content ≤ 200,000 chars | none | `:240-242` | Server only |

**Findings.** Every client-only rule in this feature is cosmetic (a disabled button). Every rule
that matters -- key traversal, filename normalisation, size ceilings, format allow-lists -- is
enforced on the server, and several are enforced *only* there, which is the correct side. The one
genuine problem is the reverse: the client's preview allow-list is *wider* than the server's, so
the client offers something the server refuses (§12.3).

---

## 8. Security

Four layers, checked individually.

### Layer 1 -- Frontend guard

- **Old app:** `AuthGuard` only (`app.routing.ts:190`). Any signed-in user reaches the screen.
- **New app:** `roleGuard` with `minRole: 'TENANT_USER'` (`app.routes.ts:278-281`), tested at
  `app.routes.spec.ts:26-30`. `AuthService.hasAtLeast` applies the same hierarchy the server's
  `RoleHierarchy` does, so a TENANT_ADMIN and a PLATFORM_ADMIN both pass.
- Neither guard hides a bucket. **The frontend never decides who may read what** -- it only decides
  whether the page is worth rendering. The route comment says so explicitly
  (`app.routes.ts:274-277`).

### Layer 2 -- Controller `@PreAuthorize`

- `StorageBrowserRestApi:36`, `FileChatRestApi:22`, `FileShareRestApi:20` -- all class-level
  `hasRole('TENANT_USER')`, and **no method in any of the three overrides it**, so the class
  annotation stands. Because `@PreAuthorize` is not repeatable, this was the thing to check; it is
  clean here.
- `AiAgentRestApi` is the counter-example the chat depends on: class-level TENANT_ADMIN (`:21`)
  with `fetchAllAgents` **replaced** by TENANT_USER (`:62-63`). If that method-level annotation
  were ever removed, the chat panel would silently lose its agent list for every non-admin.
- Hierarchy: `ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN > ROLE_TENANT_USER`
  (`config/MethodSecurityConfig.java:29`). So `hasRole('TENANT_USER')` admits all three roles. **The
  role is only a floor.**

### Layer 3 -- Service rule (where the real decision is made)

`StorageBrowserServiceImpl.resolveServiceForCaller` (`:427-433`) is on the path of every
request-named bucket/key, and it refuses a **platform bucket** to anyone who is not a platform
admin, with exactly one exception.

- `isPlatformBucket` (`:452-460`) is true when the bucket is the avatar bucket, is
  `KafkaSecretService.SECRET_BUCKET`, **or** a `storage_connection` row with that alias has
  `tenant_id IS NULL`. The two default buckets are named literally, not merely inferred, because
  no migration creates a connection row for either -- and without that a tenant admin could add a
  `BUCKET_LIST` lookup child called `etl-bucket` and be handed the platform client
  (comment at `:441-451`).
- `isOwnProfileObject` (`:474-495`) is the one exception: the avatar bucket, a non-folder key,
  starting with `<callerAppUserId>/profile/`. The trailing separator is what stops user `1248`
  from matching `12480/profile/`, and the traversal check is what stops the key being redirected
  afterwards. A folder key is refused outright, which is what closes `deleteFolder` and
  `renameFolder` against the caller's own avatar folder.
- `resolveService` (`:516-568`) additionally refuses a connection whose `tenant_id` is non-null and
  different from the caller's. Note it does **not** refuse a null `tenant_id` -- which is precisely
  why `resolveServiceForCaller` must wrap it, and why the workflow entry points
  (`uploadForWorkflow`, `readForWorkflow`) are documented as never reachable from a request
  (`:228-241`).
- `collectBuckets` (`:86-135`) narrows the visible list with `belongsToCaller(rowTenantId,
  callerTenantId)` (`:465-467`), which requires **both** ids to be non-null. A caller with no
  tenant therefore owns nothing.
- `FileChatServiceImpl.validateBucketAccess` (`:384-398`) and
  `FileShareServiceImpl.emailFile` (`:65-70`) each re-derive the same answer by asking
  `listBuckets()` whether the named bucket is in the caller's own list, so the chat and the email
  share cannot be used as a side door into a bucket the browser would refuse.

Per role:

| Role | Own tenant's buckets | Another tenant's bucket | Platform bucket (`etl-avatar`, Kafka secrets, any tenant-less connection) | Own avatar object |
|---|---|---|---|---|
| PLATFORM_ADMIN | Yes -- `isPlatformAdmin()` short-circuits `collectBuckets` and `resolveService` | Yes | Yes | Yes |
| TENANT_ADMIN | Yes | No (`resolveService:531-535`) | **No** -- identical to TENANT_USER here; the tenant/platform line is not the admin line | Yes |
| TENANT_USER | Yes | No | **No** | Yes, and nothing else in that bucket |
| No tenant (unauthenticated context, background thread) | Nothing (`belongsToCaller` needs both ids) | No | No | No -- `getAppUserId()` is null |

### Layer 4 -- Hibernate filter

This is where the layers disagree, and it matters twice.

1. **`StorageBrowserServiceImpl` never enables the filter.** `TenantFilterHelper.enableIfNeeded`
   is called from twelve services (`AiAgentServiceImpl`, `SourceJobServiceImpl`,
   `StorageConnectionServiceImpl`, …) and **not** from `StorageBrowserServiceImpl` -- it holds no
   `EntityManager` and no `TenantFilterHelper` at all. So every
   `storageConnectionRepository` call this feature makes runs with the filter off unless something
   else in the same persistence context happened to enable it, which for a `/storage.json` request
   nothing does. **Layer 4 contributes nothing to this feature.**
2. **Even when enabled, the filter would let platform rows through.**
   `StorageConnection` declares `@Filter(name = "tenantFilter", condition = "(tenant_id = :tenantId
   or tenant_id is null)")` (`model/pojo/StorageConnection.java:44`) -- deliberately permissive on
   `tenant_id IS NULL`. So a tenant-less connection is visible at the ORM layer to everyone; the
   Java `belongsToCaller` / `isPlatformBucket` tests are the only thing that excludes it.
3. **`LookupData` declares no filter at all**, and the `BUCKET_LIST` half of the bucket list is
   served from `LookupDataCacheService`'s process-wide `HashMap`, built at `@PostConstruct` with
   no tenant context (`model/service/impl/LookupDataCacheService.java:24`, `:44-56`, `:70-72`).
   The legacy bucket path therefore has **zero** database-level isolation -- the
   `belongsToCaller(child.getTenantId(), …)` filter at `StorageBrowserServiceImpl:121` is all of it.
4. `TenantFilterHelper:28-32` disables the filter entirely when `tenantId` is null or the caller is
   a platform admin. So a tenantless caller sees every row at the ORM layer, and again only the
   service test saves it.

**Conclusion: the security of this feature rests entirely on layer 3.** That is a defensible
design -- buckets are not rows, so a row filter could never have decided bucket access -- but it
means any refactor that moves work out of `StorageBrowserServiceImpl` removes the only guard.

### Existing security coverage

| Test | Count | What it pins |
|---|---|---|
| `process/src/test/java/process/model/service/impl/StorageBrowserServiceImplTenantIsolationTest.java` | 18 | Platform-bucket refusals per verb, the `12480`/`1248` prefix trap, `..` and `\` traversal, workflow vs request resolution, tenantless caller owns nothing, upload filename normalisation |
| `.../PlatformBucketAccessTest.java`, `.../PlatformBucketNamedGuardTest.java`, `.../OwnAvatarFolderGuardTest.java` | ~3 files | The named-bucket guard and the own-avatar exception |
| `process/src/test/java/process/e2e/BucketAccessE2EIT.java` | 20 | The same matrix end to end through MockMvc, per role and per endpoint |
| `.../PromptFileLimitTest.java` | 4 | Per-provider prompt budget |
| `scheduler1/next/src/app/app.routes.spec.ts` | 1 of 2 | `/objects` minRole and guard |
| `scheduler1/next/src/app/features/objects/chat/chat-export.spec.ts`, `csv-injection.spec.ts` | 18 + 3 | Fence grammar, CSV formula defusal |

**There is no test of any kind for `Objects`, `PreviewDialog`, `FileChat` or `StorageService` as
components**, and none for the old `ObjectBrowserComponent`. Every behaviour in §2.1 and §2.2 is
unverified by automation.

---

## 9. Error handling

| Failure | What the server returns | What the user sees (new app) | What the user saw (old app) |
|---|---|---|---|
| Unknown / forbidden bucket | 400, `"Unknown bucket: X."` (`StorageBrowserServiceImpl:431`, `:552-554`) | In-panel error + "Try again" (`objects.html:168-172`) | Red toast (`.component.ts:534`) |
| Bad key (`..`, `\`, leading `/`) | 400, `"Invalid key: <key>."` (`:396`) | Same in-panel error | Toast |
| Bucket list fails | 500 | Toast "Could not load storage connections." (`objects.ts:168`) | Toast with the raw error |
| Preview of an unsupported type | 400, `"Preview is not supported for this file type; use download instead."` (`:164`) | Error panel + "Download instead" (`preview-dialog.html:74-76`) -- **but only if the client attempted it; for `.log`/`.tsv`/`.wav`/`.webm` it does, wrongly** | `previewError`, "Could not load preview for this file." |
| `.gz` that inflates past 8 MB | 400, `"This file is too large to preview once decompressed -- download it instead."` (`:194-195`) | Error panel with that message | Generic preview error |
| `.gz` that is not gzip | 400, `"This file has a .gz name but isn't valid gzip data -- download it instead."` (`:207-208`) | Same | Generic |
| Download fails | 4xx/5xx | Toast `Could not download <name>.` (`objects.ts:273`) | Toast |
| Bulk download partly fails | -- | **One** toast "Some files could not be downloaded.", not one per file (`objects.ts:470-474`) | Per-file toast |
| Upload fails | 400 / 500 | Toast with the server message (`objects.ts:352-355`) | Toast, and the loop continues to the next file |
| Delete fails | 400 / 500 | Toast "Delete failed." or the server message | Joined messages from a `forkJoin` (`.component.ts:1697-1699`) |
| Email: no recipient | 400 body `ERROR`, "Enter a valid recipient email address." | Toast | Toast |
| Email: too large / too many | `ERROR` + a sized message (`FileShareServiceImpl:177-185`) | Toast with that message | Toast |
| Email: empty folder | `ERROR`, "This folder is empty -- nothing to email." | Not reachable -- folders cannot be emailed in the new app | Toast |
| Chat: file unreadable | `ERROR`, `"Couldn't get any readable content out of this .<ext> file."` (`FileChatServiceImpl:377-382`) | Red line in the panel body (`file-chat.html:36`) | Red line |
| Chat: no agent configured | -- | Picker shows "No usable agents" and Send is refused with a toast (`file-chat.html:25`, `file-chat.ts:249`) | Picker shows "No AI Agents configured" and the input is disabled |
| Chat: model fails / times out | `ERROR` + provider message | Error bubble with a **Retry** button (`file-chat.html:78-87`) | Error bubble, no retry |
| Chat: user stops the reply | -- | "Stopped." appended as an error bubble (`file-chat.ts:308`) | The pending bubble simply disappears |
| Export conversion fails | `ERROR`, `"The export failed: …"` | Toast | Toast |
| Preview save fails | 400 / 500 | Error line inside the dialog (`preview-dialog.ts:203`, `:211`) | Toast |

---

## 10. Dependencies

**Hard, upstream:**

- **`storage-connections` (feature 9).** A connection is what makes a bucket exist. With none
  configured this screen has nothing to show, and its empty state links straight to
  `/admin/storage` (`objects.html:64`).
- **`platform-configuration` (feature 15)** for the legacy `BUCKET_LIST` lookup family, which is
  still a first-class source of buckets (`StorageBrowserServiceImpl:113-133`).
- **`content-and-ai-tools` (feature 12)** for `aiAgent.json/fetchAllAgents`. This is the cycle
  Discovery records at `.ai/discovery/features.md:452-456`, and it is why `/ai/agents` is left
  ungated in the new app.
- **`authentication-and-access` (feature 1)** for `TenantContext`, which every guard reads.

**Soft, upstream:**

- **`content-and-ai-tools`** again, for `documentConverter.json/convert` -- used by the *old*
  preview for doc/docx, and used server-side by `FileChatExtractionServiceImpl` for any file it
  has to route through LibreOffice.
- **Redis** for `fileChatExtract` (7 days) and `fileChatMetadata` (30 s)
  (`.ai/discovery/backend.md:916`).
- **LibreOffice** for `exportFile` and for chat extraction of office formats.
- **Ollama** for the vision fallback on an image-only PDF
  (`FileChatExtractionServiceImpl:63-67`).

**Downstream (things that depend on this feature's code):**

- `/tools/converter` and `/tools/transcript` import `StorageService` and `PreviewDialog`
  (`features/tools/converter/converter.ts:7-8`, `features/tools/transcript/transcript.ts:6`).
- `/profile` imports `StorageService` (`features/profile/profile.ts:12`).
- `/admin/users` imports `PromptDialog` from `features/objects/dialogs`
  (`features/admin/users/users.ts:22`).
- `features/jobs/assistant/chatbot-suite.spec.ts:16` tests the job assistant against
  `objects/chat/chat-export`.

Changing anything in `storage.service.ts`, `preview-dialog.ts`, `prompt-dialog.ts` or
`chat-export.ts` therefore touches four other screens.

---

## 11. Acceptance criteria

Fixtures assumed: two tenants **A** and **B**; connection `bucket-a` owned by A, `bucket-b` owned
by B; the platform buckets `etl-avatar` and the Kafka secret bucket; users `userA`
(TENANT_USER, tenant A, appUserId 1248), `adminA` (TENANT_ADMIN, tenant A), `platformAdmin`; a
second user in tenant A with appUserId 12480. `bucket-a` contains `notes.txt`, `data.json`,
`report.pdf`, `archive.zip`, `audit.json.gz`, `photo.png`, `brief.docx`, `server.log`, and a folder
`runs/` holding three files.

**Listing and navigation**

1. `userA` opens `/objects` with no connection selected and sees one card per bucket in
   `listBuckets()`, each showing the connection name, the alias and the provider.
2. `userA` with **no** connections configured sees the "No storage is connected yet" card and an
   "Add a connection" link that navigates to `/admin/storage`.
3. `userA` selects `bucket-a` and the table lists its top-level entries with `runs/` above the
   files, `runs/` showing `—` for Size and Type, and each file showing a human byte size and a
   content type.
4. `userA` clicks `runs/`; the breadcrumb reads `bucket-a / runs` and the table shows the three
   files in it. Clicking `bucket-a` in the breadcrumb returns to the root.
5. `userA` opens `/objects?bucket=bucket-a&prefix=runs/` directly and lands inside `runs/` with the
   breadcrumb already built. *(Positive control for 6.)*
6. `userA` opens `/objects?bucket=bucket-b&prefix=` and lands on the connection picker with nothing
   selected -- `bucket-b` is not in their list, so the deep link is ignored rather than attempted.
7. In a folder with more entries than one page, a "Load more" button appears; clicking it appends
   the next page and the button disappears when no continuation token comes back.

**Filters**

8. `userA` types `rep` into the name filter and only `report.pdf` remains; clicking Clear restores
   every row.
9. `userA` sets Modified-from to tomorrow's date; every *file* row disappears and `runs/` stays
   visible, because a folder carries no modified date.
10. `userA` sets a name filter that matches nothing and sees `Nothing matches "<term>"` rather
    than "This folder is empty."
11. `userA` sets a date range that matches nothing, with the name filter blank, and sees a message
    that names the filter as the reason -- **fails today**, see §12.5.
12. `userA` sets a name filter, then opens `runs/`; the filter is cleared, or the UI states that
    it is still applied -- **fails today**, see §12.5.

**Create, rename, upload**

13. `userA` clicks New folder, enters `2026`, and a folder `2026/` appears in the current folder
    after the listing refreshes.
14. `userA` clicks New folder and enters `   ` (spaces only); the Create button stays disabled.
15. `userA` clicks New folder and enters `a/b`; the server strips the separator and a single
    folder named `ab/` is created -- no folder is created at `a/b/`.
16. `userA` renames `runs/` to `runs-2026`; the row's name changes and its contents are still
    reachable underneath.
17. `userA` renames `runs/` to the name it already has; no request is issued and no toast appears.
18. `userA` uploads one file into `runs/`; it appears in that folder, not at the root.
19. `userA` selects three files in the OS file picker in one go and all three are uploaded --
    **fails today**, see §12.4.
20. `userA` uploads a file whose name is `../escape.txt`; the server stores `escape.txt` in the
    current prefix and nothing is written outside it.

**Preview and edit**

21. `userA` opens `data.json`; the dialog shows the JSON pretty-printed with two-space indentation.
22. `userA` opens `audit.json.gz`; the dialog shows the decompressed JSON, not binary noise.
23. `userA` opens `report.pdf`; the dialog renders page 1 on a canvas with working next/previous
    and zoom controls.
24. `userA` opens `photo.png`; the image renders and clicking it toggles between fit and 2×.
25. `userA` opens `archive.zip`; the dialog shows "No inline preview for this file type" with a
    working Download button, and **no request to `previewObject` is made**.
26. `userA` opens `server.log`; the dialog shows the file's text -- **fails today**, see §12.3.
27. `userA` opens `brief.docx`; the dialog either renders it or says plainly it cannot, and in
    either case offers Download. *(Old app rendered it as PDF; new app says "no inline preview".)*
28. `userA` opens `notes.txt`, clicks Edit, changes a line, clicks Save; the dialog leaves edit
    mode, and after closing it the row's Size and Modified have been refreshed from the server.
29. `userA` opens `notes.txt`, clicks Edit, and the Save button is disabled until the text differs
    from what was loaded.

**Download**

30. `userA` downloads `notes.txt` from the row menu and receives a file named `notes.txt`.
31. `userA` downloads `archive.zip` and receives it. *(This is the positive control for the old
    app's download-through-preview defect, §12.7.)*
32. `userA` selects three files and clicks Download 3; three files are saved and at most one error
    toast appears if any of them fail.

**Delete**

33. `userA` deletes `notes.txt` from the row menu, confirms, and the row disappears.
34. `userA` cancels the delete confirmation and the row is still there and no request was sent.
35. `userA` deletes `runs/`, confirms, and the folder **and its three files** are gone.
36. `userA` selects two files, deletes them, and both disappear and the bulk bar disappears with
    them.
37. `userA` selects two files, deletes **one** of them from its row menu, and the bulk bar then
    counts **one** remaining selected item, not two -- **fails today**, see §12.5.
38. `userA` can tick a checkbox on the `runs/` folder row and include it in a bulk delete --
    **fails today**, see §13.

**Email**

39. `userA` emails `report.pdf` to `someone@example.com`; a success toast names the recipient and
    the mail arrives with the file attached.
40. `userA` opens the email dialog and types `not-an-address`; Send stays disabled.
41. `userA` selects four files and emails them; one mail arrives with a single
    `selected-files.zip` containing four entries.
42. `userA` emails `runs/` as a folder and receives `runs.zip` containing its three files --
    **fails today**, see §13.
43. `userA` emails a selection totalling more than 20 MB and sees the server's
    "larger than 20.0 MB combined" message rather than a generic failure.

**File chat**

44. `userA` opens the chat on `notes.txt`; the panel shows the file name, an agent picker listing
    only Active agents that are keyed or Ollama, and the prompt "Ask something about this file".
45. `userA` asks a question and receives a rendered markdown answer attributed to the assistant,
    with a working Copy button.
46. `userA` asks a second question that can only be answered from the first answer, and the reply
    shows the model had the earlier turns -- **fails today**, see §12.2.
47. `userA` asks for the data "as a CSV"; a download chip appears, the fenced block does **not**
    also render as raw text in the bubble, and the downloaded CSV has any leading `=`/`+`/`-`/`@`
    cell prefixed with an apostrophe.
48. `userA` asks for the same data "as an Excel file"; the chip downloads a real `.xlsx` produced
    by `exportFile`.
49. `userA` opens the chat on a very long file and sees a notice naming how many of the file's
    characters the model will read, and that number matches the chosen agent's provider budget
    (400,000 for Anthropic, 24,000 for Ollama).
50. `userA` switches the agent picker from an Ollama agent to an Anthropic one and the coverage
    notice updates -- **fails today**, see §12.9.
51. `userA` with a chat open on `notes.txt` opens the chat on `data.json`; either the transcript is
    cleared for the new file or a confirmation is raised first, and the new file is prepared --
    **fails today, and is the most serious defect in the feature**, see §12.1.
52. `userA` closes a non-empty chat, confirms, and the panel disappears, the transcript is gone,
    and `fileChat.json/endSession` was called.
53. `userA` closes an *empty*, just-opened chat and it closes immediately with no confirmation.
54. `userA` reloads the page within 30 minutes and reopens the chat on the same file; the previous
    transcript is restored. After 30 minutes it is not.

**Security -- refusals, each paired with a positive control on the same fixture**

55. `userA` calls `GET /storage.json/listObjects?bucket=bucket-a` and gets `SUCCESS` with rows.
    *(Positive control for 56-60.)*
56. `userA` calls the same with `bucket=bucket-b` and gets `400` / `"Unknown bucket: bucket-b."`
57. `userA` calls `GET /storage.json/buckets` and `bucket-b` is **not** in the response, while
    `bucket-a` is.
58. `adminA` -- a tenant **admin** -- calls `listObjects` on the Kafka secret bucket and is refused
    with `"Unknown bucket"`. `platformAdmin` calls the same and succeeds. *(The paired control
    proves the refusal is about the bucket, not about the endpoint being broken.)*
59. `userA` calls `GET /storage.json/downloadObject?bucket=<avatarBucket>&key=1248/profile/pic.png`
    and succeeds (it is their own avatar); the same call with `key=12480/profile/pic.png` is
    refused. Both against the same bucket, in the same session.
60. `userA` calls `DELETE /storage.json/deleteFolder?bucket=<avatarBucket>&key=1248/profile/` and
    is refused, even though it is their own folder -- the own-profile exception is for objects, not
    prefixes. The upload of `1248/profile/pic.png` in the same session still succeeds.
61. `userA` calls `listObjects` with `prefix=runs/../../` and gets `400` /
    `"Invalid key: runs/../../."`; the same call with `prefix=runs/` succeeds.
62. `userA` calls `listObjects` with `prefix=a\b` and is refused; `prefix=a/b/` is accepted.
63. `userA` posts `fileShare.json/send` with `bucket=bucket-b` and gets
    `"Unknown bucket: bucket-b."`; the same request with `bucket=bucket-a` succeeds.
64. `userA` posts `fileChat.json/prepareContext` with `bucket=bucket-b` and gets
    `"Unknown bucket: bucket-b."`; with `bucket=bucket-a` it returns `Ready.`
65. A request whose token carries a valid signature but no tenant claim gets an empty list from
    `GET /storage.json/buckets` and `"Unknown bucket"` from every other endpoint, for every bucket
    including the platform ones.
66. A user whose token carries no readable role opens `/objects` in the browser and lands on
    `/unauthorized`; `userA` opening the same URL lands on the browser.
67. `POST /storage.json/uploadObject` with no `Authorization` header returns 401/403 and writes
    nothing.

---

## 12. Known issues

Each is a defect that exists **today**, with the evidence. None are fixed here.

### 12.1 The chat panel is reused across files and buckets, so it binds a stale conversation to a new key -- **blocker**

`objects.html:280-283` renders `<app-file-chat [bucket]="bucket()" [fileKey]="file.key"
[fileName]="file.name" …>` inside `@if (chatFile(); as file)`, and `openChat(entry)` merely sets
the signal (`objects.ts:374-376`). Because the `@if` condition stays truthy, Angular **keeps the
same component instance** and only updates its inputs.

Consequences, all following from `file-chat.ts`:

- `ngOnInit` (`:204-209`) does not run again, so `restoreHistory()` and `prepare()` are never
  called for the second file. `preparing()` is already `false` and `coverage()` still describes the
  *first* file, so the truncation notice is wrong and the input is enabled against an unprepared
  file.
- `messages()` is untouched, so the first file's transcript is displayed under the second file's
  name, and is sent as `history` on the next turn.
- The `persist` effect (`:100-103`) reads `messages()` and calls `historyKey()`, which reads
  `bucket()` and `fileKey()` (`:75-77`). Both are signals, so the effect is re-run on the input
  change and **writes the first file's transcript into the second file's `sessionStorage` slot**.
- The same applies to changing the connection while a chat is open: `onBucketChange`
  (`objects.ts:195-202`) never clears `chatFile`, so `bucket()` changes underneath a chat still
  bound to a key in the old bucket.

The old app raised a "Leave this chat?" modal for exactly this
(`object-browser.component.ts:922-932`, template `.html:600-624`); the rewrite dropped the modal
and did not replace it with a rebind.

### 12.2 File chat has no conversation memory -- **major**

`file-chat.ts:258` builds history as `{ role: m.role, content: m.text }`.
`FileChatHistoryItemDto` has fields `role` and **`text`** (`model/dto/FileChatHistoryItemDto.java:14-15`)
and is annotated `@JsonIgnoreProperties(ignoreUnknown = true)` (`:10`), so `content` is discarded
and `text` deserialises to `null`. `FileChatServiceImpl.buildInstructions` then skips every turn
whose text is null (`:349-352`):

```java
if (turn == null || isNull(turn.getText())) {
    continue;
}
```

So the "Recent conversation so far:" block is always empty and every question is answered as if it
were the first. The old app sent `{ role, text }` (`object-browser.component.ts:1022`) and worked.

Two smaller faults ride along on the same line: the slice is taken **after** the new user message
has been pushed (`:253` then `:258`), so the current question would be duplicated into the history,
and `role: 'error'` bubbles are included as history items -- neither of which the old app did
(`object-browser.component.ts:1015-1019` filters to user/assistant and slices before pushing).

### 12.3 The client's preview allow-list is wider than the server's -- **major**

`preview-dialog.ts:22` lists `TEXT_LIKE = ['txt','csv','tsv','log','xml','ndjson']` and `:127-128`
add `wav` and `webm`. The server's `ContentTypeUtil.PREVIEWABLE_EXTENSIONS`
(`process/src/main/java/process/util/ContentTypeUtil.java:74-76`) is
`json,csv,txt,xml,md,pdf,mp3,m4a,mp4` plus images plus `doc,docx` -- `tsv`, `log`, `ndjson`, `wav`
and `webm` appear **only** in `GZIP_PREVIEWABLE_INNER` (`:113-114`), i.e. only under a `.gz`
wrapper. `StorageBrowserServiceImpl:163-165` therefore answers a plain `.log` or `.tsv` preview
with `400 "Preview is not supported for this file type; use download instead."`, and the dialog
renders that as a failure for a file it just told the user it could show.

The old app has the same shape of bug from the other direction: `loadPreview`
(`object-browser.component.ts:1402-1404`) accepts an extension found in either list, so a plain
`.log` is attempted and fails identically.

### 12.4 Upload is single-file, silently -- **major**

`objects.ts:340` reads `input.files?.[0]` and `objects.html:102` has no `multiple` attribute. A
user who drags in five files gets one. The old app uploaded the whole `FileList` sequentially and
showed an "Uploading…" state throughout (`object-browser.component.ts:1841-1878`). There is also no
progress or busy state on the new button.

### 12.5 Selection and filter state are not maintained across the actions that change them -- **minor**

- `remove(entry)` (`objects.ts:285-311`) reloads the listing but never removes the deleted key from
  `selected()`, so the bulk bar keeps counting a row that no longer exists, and a subsequent
  "Delete N" posts a key that is already gone. The old app deleted the key
  (`object-browser.component.ts:1695`).
- `onBucketChange` (`objects.ts:195-202`) clears `search` but not `dateFrom` / `dateTo`.
- `openFolder` and `goToCrumb` (`:237-255`) clear the selection but no filter at all. The old app
  called `resetSearch()` on all three transitions (`object-browser.component.ts:293`, `:661`,
  `:678`).
- The empty-state message branches on `search()` alone (`objects.html:258`), so a date-only filter
  that matches nothing reads "This folder is empty."
- The counts line (`objects.html:122-126`) is computed from `objects()`, not `filtered()`
  (`objects.ts:85-92`), so it reports the unfiltered folder while the table shows a filtered
  subset.
- `downloadSelected` operates on `filtered()` (`objects.ts:464`) while `removeSelected` and
  `share()` operate on the raw `selected()` set (`:314`, `:439`). With a filter active, Download
  and Delete act on different sets from the same checkboxes.

### 12.6 Two byte formatters on one screen -- **minor**

`objects.ts:151` binds the shared helper (`humanSize = formatSize`) and `:478-486` declares a
second, divergent `formatBytes`. Both are live: the "Largest files" chart uses `humanSizeFn` →
`formatSize` (`objects.html:163`) while the counts line and the Size column use `formatBytes`
(`objects.html:125`, `:218`). They round differently -- `formatSize` always prints one decimal
(`15.0 KB`), `formatBytes` drops it at or above 10 (`15 KB`), uses one decimal rather than two for
GB, and adds a TB step `formatSize` does not have. This is the exact drift
`shared/ui/format-size.ts:1-8` says the extraction was meant to end. Also recorded independently at
`.ai/discovery/frontend.md:812-819`.

### 12.7 (Old app) Every download goes through the preview endpoint -- **major, already fixed in the new app**

`object-browser.component.ts:1714-1715`:

```ts
private triggerDownload(bucket: string, key: string): void {
    this.storageService.previewObjectArrayBuffer(bucket, key)
```

`previewObjectArrayBuffer` calls `previewObject` (`_services/storage.service.ts:43-45`), which
`StorageBrowserServiceImpl:163-165` refuses for any extension outside `PREVIEWABLE_EXTENSIONS`. So
in the old app a `.zip`, `.xlsx`, `.parquet` or `.tar` could be listed but never downloaded --
including through the bulk Download button. `downloadObjectUrl` existed in the same service
(`:35-37`) and was used only by the Document Converter (`_component/document-converter/document-converter.component.ts:654`).
The new app calls `downloadObject` correctly (`storage.service.ts:71-75`).

### 12.8 (Old app) Model-produced HTML is rendered with the sanitizer bypassed -- **major, already fixed in the new app**

`object-browser.component.ts:1245` calls `this.sanitizer.bypassSecurityTrustHtml(file.content)` on
the raw contents of an ```` ```html ```` fence the model wrote, and binds it with `[innerHTML]`
(`.html:678-679`). The new app has no such surface: `shared/ui/markdown.ts:14-20` parses to blocks
and renders through templates, and the chat-file preview modal does not exist.

### 12.9 The chat's coverage notice is computed once and never recomputed -- **minor**

`prepare()` runs from `loadAgents()`'s callback (`file-chat.ts:211-226`) and nowhere else. Changing
the agent in the picker (`file-chat.html:23`) updates `agentId()` but does not re-run `prepare()`,
so a user who switches from an Ollama agent (24,000 chars) to an Anthropic one (400,000) keeps
being told the file is truncated when it no longer is. The picker also coerces an empty value to
`0` (`+''`), and `send()` only guards against `null` (`:248`), so a `0` reaches the server and
fails at `resolveRuntimeConfig` instead of at the "Choose an agent first" check.

### 12.10 Bulk download fires every request at once -- **minor**

`downloadSelected` (`objects.ts:468`) issues one `HttpClient` GET per file with no spacing. The old
app deliberately staggered them 350 ms apart (`BULK_DOWNLOAD_STAGGER_MS`,
`object-browser.component.ts:53`, `:762-764`) because browsers throttle or drop simultaneous
programmatic downloads. Selecting twenty files is the case that shows it.

### 12.11 Dead code in the new `StorageService` -- **cosmetic**

`objectMetadata()` (`storage.service.ts:43-47`) and `previewUrl()` (`:97-99`) have no callers
anywhere in `scheduler1/next/src`. `previewUrl` is actively dangerous if it is ever used: it builds
a bare URL with no `Authorization` header, which is precisely the failure the `download()` comment
above it describes (`:62-70`).

### 12.12 The server's `previewable` flag is computed and never used -- **cosmetic**

`ObjectMetadataDto` carries a `previewable` boolean (`model/dto/ObjectMetadataDto.java:19`),
populated by every provider adapter (e.g. `FtpObjectStorageServiceImpl:321`). Neither frontend
reads it; both re-derive the answer from the extension, which is how §12.3 came about.

---

## 13. Missing functionality

Things the rewrite dropped, or that neither app ever had. "Effort" is the work in the new app.

| # | Missing | Evidence it is gone | What it would take |
|---|---|---|---|
| 1 | **Folder selection and folder bulk actions** | `objects.html:195-199` renders the checkbox only `@if (!entry.folder)`; the old app had no such condition (`object-browser.component.ts:716-750`) | Render the checkbox for folders; in `removeSelected`, split the keys and fan out `deleteObjects` for files and one `deleteFolder` per folder, as `confirmDelete` did (`object-browser.component.ts:1660-1701`). **S** |
| 2 | **Emailing a folder** | `objects.html:237-239` offers Email only `@if (!entry.folder)`; the old menu item had no condition (`.html:184-189`). The server already handles it (`FileShareServiceImpl:88-93`, `:139-153`) | Drop the condition and let `share(entry)` pass the folder key. The dialog copy needs a folder variant. **S** |
| 3 | **Multi-file upload** | `objects.ts:340`, `objects.html:102` | Add `multiple`, loop the `FileList`, add a busy state and a per-file failure summary. **S** |
| 4 | **The per-folder contents/size column** | Nothing in `objects.ts` issues a per-folder `listObjects`; the folder row prints `—` (`objects.html:218`). Old: `loadFolderStats` (`object-browser.component.ts:585-621`) | Re-add the fan-out, guarded on `isSlowProvider()` exactly as the old app was. Worth weighing against the request cost -- see the synthesis. **M** |
| 5 | **The Sub-folder Sizes chart** | New insights are What is here / File types / Last modified / **Largest files** (`objects.html:144-164`); the old set had Sub-folder Sizes (`.html:92-95`). It depended on #4 | Follows from #4. **S once #4 lands** |
| 6 | **Insights over the whole folder rather than the loaded page** | Old made a dedicated `listObjects(..., 1000)` stats pass and flagged when it was capped (`loadDirectoryStats`, `:354-406`; note at `.html:108-111`). New computes from `objects()` -- the rows currently loaded (`objects.ts:106-146`) | Either restore the stats pass, or label the tiles "of the N entries loaded". The second is a one-line honesty fix and is what I would do first. **S / M** |
| 7 | **Copy current folder path** | Old toolbar button `copyCurrentPath` (`object-browser.component.ts:313-336`, `.html:39-42`). No equivalent in `objects.html` | One button plus the existing `copy()` helper (`objects.ts:277-283`). **S** |
| 8 | **"Leave this chat?" confirmation** | `confirmLeaveChatIfNeeded` (`object-browser.component.ts:922-932`) has no counterpart; `openChat` just reassigns (`objects.ts:374-376`) | Part of the fix for §12.1. **S** |
| 9 | **doc/docx preview** | `preview-dialog.ts:121-130` returns `'none'` for `doc`/`docx`; the old app converted them to PDF for display (`loadDocPreview`, `object-browser.component.ts:1476-1508`). The server *does* stream them (`ContentTypeUtil:76`) | Route the blob through `documentConverter.json/convert` to PDF and feed the existing `PdfViewer`. **M** |
| 10 | **Rendered markdown in the preview** | `kindFor` produces `'markdown'` (`preview-dialog.ts:123`) but `preview-dialog.html:121-131` has no `@case ('markdown')`, so it falls to `@default` and shows the source. Old rendered it (`object-browser.component.ts:1451-1453`) | Reuse `shared/ui/markdown.ts` in the `markdown` case -- and it is safe, unlike the old `marked` + `innerHTML`. **S** |
| 11 | **"Search applies to files loaded so far" hint** | `object-browser.component.ts` template `.html:223-226`; no equivalent in `objects.html` | One line. It matters: the filter is client-side over loaded pages in both apps, and a user who filters before loading more gets a confidently wrong empty result. **S** |
| 12 | **Server-side search** | Neither app has it. `listObjects` takes only `bucket`, `prefix`, `continuationToken`, `maxKeys` (`StorageBrowserRestApi:59-64`) | A real change: a `nameContains` parameter honoured per provider, or accept that the client filter is over loaded rows and say so (#11). **L** |
| 13 | **Any frontend test for this screen** | `.ai/discovery/frontend.md:661`, `:677-678` -- the only specs touching this feature are the route guard and the fence grammar. No spec exists for `Objects`, `PreviewDialog`, `FileChat` or `StorageService` | At minimum: the deep link, the stale-ticket guard, the filter predicate, the selection/delete interaction, and the chat rebind. **M** |
| 14 | **Move / copy an object** | Absent from both apps and from `StorageBrowserService` -- only `renameFolder` exists, and only within the same parent (`StorageBrowserServiceImpl:355-376`) | New service method plus per-provider copy semantics. Out of scope unless asked for. **L** |
| 15 | **Download a folder as a ZIP** | Absent from both. The zip machinery exists but only behind email (`FileShareServiceImpl:188-207`) | A `downloadFolder` endpoint streaming the same ZIP. **M** |
