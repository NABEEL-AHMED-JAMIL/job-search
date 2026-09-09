# Grooming -- Content and AI Tools

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

Status from Discovery: **partial** (`.ai/discovery/features.md:46`). Five old routes
(`documentConverter`, `audioTranscriptExtractor`, `contentCleaner`, `aiAgent`, `ollamaModels`),
five new routes (`tools/converter`, `tools/transcript`, `tools/cleaner`, `ai/agents`,
`ai/models`), eighteen backend endpoints across five controllers.

This is not one feature; it is five screens that share a backend theme ("do something to a file or
a model") and share two dependencies (`object-browser` for bucket access, `storage-connections`
for the buckets themselves). Each screen crossed to the new app in a different state. The point of
this document is to say exactly which parts crossed and which did not, screen by screen, because
"partial" applied to a five-screen feature is otherwise useless to whoever picks it up.

**The boundary in one table.** Every row below is evidenced in section 2.

| Screen | Crossed intact | Crossed changed | Did not cross |
|---|---|---|---|
| Document Converter | upload source, format reference, target picker, save-to-bucket, download, task list, task delete | bucket source is now **root-only** (no folder navigation); save folder is free text, not a browser; task preview is now the shared `PreviewDialog` | inline preview of the just-converted result, download-the-input, task search, input/output byte totals |
| Audio Transcript | upload source, bucket source **with folder navigation**, timestamps toggle, copy transcript | timestamp rendering replaced by three readings (timeline / table / console), plus per-timestamp copy | **save the transcript back to a bucket**, **reopen a saved `.txt` transcript**, suggested folder name |
| Content Cleaner | paste, clean, copy | -- | **bucket source**, **in-browser PDF text extraction**, raw-vs-cleaned comparison, chars-saved counter, source label |
| AI Agents | list, add, edit, delete, Ollama-only JSON mode, blank-key-keeps-stored-key | list gained search, "only mine", persisted table/cards toggle, created/updated-by; provider and status dropdown filters replaced by one free-text search | **clone**, **Copy tool URL**, the four KPI tiles, the client rule "a custom provider needs an endpoint", the client rule "a new agent needs a key", and `xlsx` as a selectable target file type |
| Ollama Models | list, pull by tag, delete | catalogue grew from 14 flat entries to 16 with purpose/note/installed state and one-click pull; stats grew from 3 tiles to 4 plus a disk-share bar | the Family column and its colour coding |

One thing that crossed **broken** rather than intact, and it is the single most consequential
defect in the feature: the new AI Agents screen reads the provider list from a field the
`appSetting` endpoint never sends, so the `AI_PROVIDER` lookup is silently ignored and the
dropdown is always the three hard-coded fallbacks. Evidence in section 12.1.

---

## 1. Purpose

Five small tools that exist because the people running this platform kept doing the same five
things by hand.

**Document Converter.** "I have a `.docx` and the pipeline wants a PDF." A LibreOffice conversion
without a LibreOffice install on anyone's laptop, run against a file you uploaded or a file
already sitting in a bucket, with the option to write the result back into a bucket so the next
job can pick it up and so the conversion is still there tomorrow.

**Audio Transcript Extractor.** "Someone sent a recording and I need the words." Speech-to-text
over `.mp3` and `.m4a`, either uploaded or read from a bucket, optionally with timestamps so a
moment can be cited rather than described.

**Content Cleaner.** "This text came out of a PDF and it is full of layout garbage." Smart quotes,
hyphen-wrapped words, tab noise, runs of blank lines -- stripped, so the result can be pasted into
a prompt without the model spending its attention on formatting artifacts.

**AI Agents.** "Define the model once; use it everywhere." A named agent carries a provider, a
model, an endpoint, an encrypted API key and a system prompt. The Object Browser's file chat and
the Job Assistant both pick an agent rather than each screen holding its own model configuration
and its own copy of the key.

**Ollama Models.** "Which models are actually on this box, and what are they costing me in disk?"
Local models are free to run and expensive to store; this is the screen that pulls one, shows what
is installed, and deletes the one nobody uses.

The first three are stateless tools that happen to touch storage. The last two are configuration
screens: AI Agents owns a tenant-scoped table, Ollama Models owns nothing at all and is a thin
window onto one host's model directory.

---

## 2. Existing behaviour

### 2.1 Document Converter

#### Old app -- `DocumentConverterComponent`

738 lines of TypeScript, 418 of template
(`scheduler1/src/app/_component/document-converter/document-converter.component.ts`, `.html`).
Route `documentConverter`, `AuthGuard` only, no role check
(`scheduler1/src/app/app.routing.ts:266-271`). Linked from the top nav
(`scheduler1/src/app/app.component.html:35`).

On init it fires three calls: `supportedFormats`, `storage.json/buckets`, and `fetchAllTasks`
(`:111-115`).

**Source, two modes** (`:51`). *Upload* is a file input (`:197-201`). *Browse* is a bucket
`<select>` plus a real folder walk: `loadBrowseObjects` lists one level, `selectBrowseEntry`
descends into a folder and pushes a breadcrumb, `goToBrowseBreadcrumb` jumps back
(`:263-314`). Entries are filtered to folders plus files whose extension appears in some family's
`inputFormats` (`visibleBrowseObjects`, `:280-287`). Choosing a non-convertible file raises a
toast naming the file (`:297-300`). `runBrowseSelectedEntry` downloads the object as an
`ArrayBuffer` and wraps it in a `File`, so from that point the two modes are identical
(`:316-331`).

**Format handling.** `currentFamily` finds the first family whose `inputFormats` contains the
source extension (`:180-186`). Picking a file auto-selects a target: the first output format that
is not the input's own extension (`:241-244`).

**Save to bucket.** A checkbox, a bucket `<select>`, a task name, and a *folder browser* --
`toggleSaveBrowse` opens a second, folder-only listing with its own breadcrumbs, and
`useCurrentSaveFolder` writes the current prefix into `saveFolder` (`:333-406`).

**Preview.** `PREVIEWABLE_EXTENSIONS` (`:17-21`) maps pdf/jpg/jpeg/png/gif/svg/bmp to `image` or
`pdf`, txt/csv/tsv to `text`, html to `html`. On selecting a file the component builds an *input*
preview client-side -- `FileReader` for text, `URL.createObjectURL` for the rest, sanitised
through `DomSanitizer` (`:221-239`). After a conversion it builds an *output* preview from the
returned base64 (`:458-477`). A two-button toggle shows either side (`:494-500`,
`.html:234-268`). Both object URLs are revoked on destroy and on replacement (`:717-736`).

**Result.** `downloadResult` turns the base64 back into a Blob and triggers a download
(`:479-485`); `downloadInputFile` does the same for the source file (`:487-492`). `startOver`
clears every field including the save target and both previews (`:545-569`).

**Task list.** `fetchAllTasks`, rendered as a table with a client-side `searchFilter` pipe
(`:123-125`) and two summary tiles computed from the rows -- total input bytes and total output
bytes (`:133-139`, `.html:278-291`). Each row can open a side panel previewing either the stored
input or the stored output, fetched through `storage.json/previewObject` (`:591-624`). Delete goes
through a Bootstrap modal (`:659-686`).

#### New app -- `Converter`

320 lines of TypeScript, 272 of template
(`scheduler1/next/src/app/features/tools/converter/converter.ts`, `.html`). Route
`tools/converter`, `authGuard` only (`scheduler1/next/src/app/app.routes.ts:166-168`). Nav entry
at `features/shell/shell.ts:79`.

Same three calls on init (`converter.ts:152-165`). Same two modes, same auto-target selection --
now as an `effect` that also fires for the bucket mode, which the old handler did not do; the
comment at `:173-177` records that a bucket pick used to leave the format empty.

**The bucket source lost its folder walk.** `onBucketChange` calls `storage.listObjects(value, '')`
and nothing else (`:117-130`); `convertibleObjects` drops every folder row
(`:95-102`, `if (o.folder) return false`). There is no second `listObjects` call in the file. A
bucket whose files live under a prefix -- which is what the transcript screen's own comment says is
normal here (`transcript.ts:140-142`: *"ours sits two levels down, under audio_text/input"*) --
presents an empty file picker.

**Save to bucket** keeps the checkbox, the bucket select and the name, but the folder is a free-text
input with a `converted/` placeholder (`converter.html:104-109`). The folder browser is gone.

**Preview.** There is no client-side preview of the source and no preview of the converted result;
the result renders as a filename and a Download button (`converter.html:130-139`). Previewing a
*saved* task is better than it was: `view()` opens the shared `PreviewDialog`
(`converter.ts:296-310`), the same viewer the Object Browser uses, rather than a bespoke panel.

**Task list.** Gains a `dateCreated` column and a deep link into the Object Browser at the output
folder (`converter.html:230-238`, `outputFolderOf` at `converter.ts:313-317`; the target reads
`bucket` and `prefix` from the query string at `features/objects/objects.ts:179-183`, so the link
works). Loses the search box and both byte totals. Delete uses the shared `confirmWith` dialog
(`:272-290`).

The screen does **not** use `TableShell`, which is the new app's shared loading/error/empty
chrome. `tasksLoading` is declared and set but the template only branches on
`!tasks().length` (`converter.html:193`), so a load in flight and a load that failed both render
"Nothing converted yet."

### 2.2 Audio Transcript Extractor

#### Old app -- `AudioTranscriptExtractorComponent`

458 lines of TypeScript, 205 of template
(`scheduler1/src/app/_component/audio-transcript-extractor/audio-transcript-extractor.component.ts`).
Route `audioTranscriptExtractor`, `AuthGuard` only (`app.routing.ts:272-276`).

Upload or browse (`:26`). The browse mode walks folders with breadcrumbs (`:133-198`) and shows
folders, supported audio, *and* `.txt` files -- because a `.txt` in a bucket is treated as an
already-saved transcript (`visibleObjects`, `:150-154`; `isSavedTranscript`, `:184-186`).
`runSelectedEntry` branches on that: a `.txt` is read back through `previewObjectText` and shown as
a transcript, anything else is transcribed (`:173-182`, `loadSavedTranscript`, `:208-221`).

Client-side extension check on upload against `AUDIO_SUPPORTED_EXTENSIONS = ['mp3','m4a']`
(`_models/audio-transcript.model.ts:2`), with the message naming the accepted list
(`:94-98`).

**Timestamp rendering.** `highlightedTranscript` escapes the text, wraps every
`[HH:MM:SS.mmm]` in a `<span class="transcript-timestamp">` and bypasses the sanitiser
(`:261-269`).

**Save back to a bucket.** The whole second half of the component. `suggestFolderName` builds
`<stem>_<iso-timestamp>` from the source name (`:298-305`); a folder browser with breadcrumbs picks
an existing folder instead (`:337-398`); `saveTextToBucketFolder` creates the folder when it is new
and then uploads `transcript.txt` into it (`:413-441`). On success the saved path is shown
(`:314-322`).

**Error handling** is the one place the old app does better than its own convention: the comment at
`:248-255` records that these two endpoints return failures as HTTP 400 with a `ResponseDto` body,
so the useful message is at `error.error.message`, not `error.message`.

#### New app -- `Transcript`

213 lines of TypeScript, 194 of template
(`scheduler1/next/src/app/features/tools/transcript/transcript.ts`). Route `tools/transcript`,
`authGuard` only (`app.routes.ts:170-172`).

The bucket picker **does** walk folders -- `browse()` with a breadcrumb list, folder buttons, and a
`browseTicket` guard so a slow response for an abandoned level cannot overwrite the current one
(`:145-165`). This is the same navigation the converter is missing, in the same codebase.

Upload mode adds `accept=".mp3,.m4a"` (`transcript.html:22`) but has no code-level extension check;
the server refuses with "Unsupported file type -- expected .mp3 or .m4a."
(`AudioTranscriptServiceImpl.java:72-74`).

**Timestamp rendering became three readings.** `segments` splits the text on the markers
(`:39-66`), and `view` switches between a timeline, a table and a console
(`:75-80`, `transcript.html:134-191`). A timestamp is itself a button that copies just that
timestamp (`copyStamp`, `:204-207`). When timestamps were switched off, the parser falls back to
splitting on line breaks so the table and timeline still have rows to number (`:48-54`).

**Nothing saves.** There is no `uploadObject` call and no `createFolder` call in the file; `copy()`
is the only way the transcript leaves the tab (`:209-212`). There is no `.txt` reopen path -- the
bucket picker offers only `mp3`/`m4a` (`AUDIO_EXTENSIONS` at `:9`, `audioObjects` at `:97-98`).

`consoleText()` (`:85-89`) is declared, documented as "Plain text for the clipboard, matching
whichever reading is on screen", and called from nowhere -- `copy()` copies the raw transcript.

### 2.3 Content Cleaner

#### Old app -- `ContentCleanerComponent`

229 lines of TypeScript, 106 of template
(`scheduler1/src/app/_component/content-cleaner/content-cleaner.component.ts`). Route
`contentCleaner`, `AuthGuard` only (`app.routing.ts:260-264`).

Two modes: paste, or browse a bucket (`:25`). The browse mode walks folders with breadcrumbs
(`:97-139`) and accepts `pdf`, `csv`, `txt`, `json`, `xlsx`, `xml` (`:8`). A PDF is extracted
**in the browser** through `extractPdfText` (`_helpers/pdf-text-extractor.ts`, imported at `:4`);
everything else is fetched as text through `previewObjectText` (`:153-155`). Empty extraction is
reported as "No text could be extracted from this file." (`:160`).

The result panel shows the cleaned text, the character count, and how many characters the clean
removed (`charsSaved`, `:190-192`; `.html:93`), under a "Source: ..." label naming what was cleaned
(`.html:80`).

#### New app -- `Cleaner`

40 lines of TypeScript, 32 of template
(`scheduler1/next/src/app/features/tools/cleaner/cleaner.ts`). Route `tools/cleaner`, `authGuard`
only (`app.routes.ts:174-176`).

A textarea, a Clean button, a read-only textarea, a Copy button. No bucket, no storage import, no
PDF extraction, no comparison, no counter. It is the smallest screen in the new app and it is
smaller than the screen it replaces.

### 2.4 AI Agents

#### Old app -- `AiAgentComponent`

359 lines of TypeScript, 367 of template
(`scheduler1/src/app/_component/ai-agent/ai-agent.component.ts`). Route `aiAgent`, `AuthGuard`
only, no role guard (`app.routing.ts:248-252`) -- deliberately, because `fetchAllAgents` is
`TENANT_USER` and the write controls are gated in-template on `canManageAgents`
(`:55-58`, `.html:116`, `:123`, `:198`, `:202`).

**Providers come from the `AI_PROVIDER` lookup, in two calls.** `loadProviders` fetches
`setting.json/appSetting`, finds the parent whose `lookupType` is `AI_PROVIDER`, then fetches
`setting.json/fetchSubLookupByParentId` with that parent's id and maps the children to the dropdown
(`:105-137`). When there are none, the template says so and names where to add them
(`.html:279`).

**One modal, three uses.** `openAddAgent` resets the form; `openEditAgent` fills it and adds a
`status` control; `openCloneAgent` fills it from an existing agent with `" (Copy)"` appended to the
name and no id, so saving creates a second agent (`:177-214`).

**Client-side rules on save** (`:243-259`): a provider that is not OpenAI/Anthropic/Ollama must
have an `apiEndpoint`; at least one target file type must be selected; a *new* agent must have an
API key unless the provider is Ollama. A blank key on edit is deleted from the payload so the
stored key survives (`:265-267`).

Target file types are checkboxes over `AI_AGENT_FILE_TYPE_LIST = ['pdf','csv','txt','json','xlsx','xml']`
(`_models/ai-agent.model.ts:4`), joined into a CSV (`:263`).

`jsonMode` is only offered when the provider is Ollama (`.html:331`).

**Copy tool URL** builds `<apiUrl>/aiAgent.json/fetchToolByUuid?uuid=<toolUuid>` and copies it
(`:304-327`). It is **not** gated on `canManageAgents` -- the button sits outside the
`*ngIf` (`.html:120-122`, `:198-200`) -- which matches the endpoint, which is `TENANT_USER`.

The list has provider and status dropdown filters (`:80-85`), a search box, a table/cards toggle
(`:44`, `:173-175`), and four KPI tiles: agent count, active count, distinct providers, keys
configured (`:91-97`, `.html:7-35`).

#### New app -- `Agents` + `AgentDialog`

158 + 106 lines of TypeScript
(`scheduler1/next/src/app/features/ai/agents/agents.ts`, `agent-dialog.ts`). Route `ai/agents`,
`authGuard` only, with a comment at `app.routes.ts:133-134` recording why there is no role guard.
Write controls gated on `auth.canManageAgents()` (`agents.html:11`, `:49`, `:135`), which is
`hasAtLeast('TENANT_ADMIN')` (`core/auth/auth.service.ts:92`).

Uses `TableShell` for loading, error and empty states (`agents.html:16-20`), a `ViewToggle`
persisted per screen under `etl.view.agents` (`:22`), a free-text search over name, provider and
model (`agents.ts:58-66`), and a `MineFilter` narrowing to rows the caller created (`:151-157`).
The table shows created-by and updated-by, which the old app had no concept of.

`keyState` (`:135-143`) renders three states rather than a boolean: **Configured**, **Not needed**
for Ollama, **Not set** for anything else -- a real improvement, because "no key" is only a problem
for some providers.

**The provider list is read wrongly.** `loadProviders` fetches `setting.json/appSetting` and reads
`lookup?.children` off the `AI_PROVIDER` entry (`:89-99`). `appSetting` builds each
`LookupDataDto` through `fillLookupDateDto`, which sets eight fields and never `children`
(`SettingServiceImpl.java:605-616`); the DTO is `@JsonInclude(NON_NULL)`
(`LookupDataDto.java:13`), so the field is absent from the response. `values.length` is therefore
always 0 and the fallback fires: the dropdown is permanently
`['OpenAI', 'Anthropic', 'Ollama']` (`:96`, `:98`).

The dialog drops three of the old client rules: no endpoint-required check for a custom provider,
no key-required check for a new agent, no `xlsx` in the file-type list. `FILE_TYPES` is
`['pdf','docx','txt','md','csv','json','xml','png','jpg','mp3','m4a']` (`agent-dialog.ts:10`) --
six additions and one removal. A blank key is still deleted from the payload, with the reason in a
comment (`:82-83`).

There is no clone and no Copy tool URL. Neither `toolUuid` nor `fetchToolByUuid` appears anywhere
in `scheduler1/next/src`.

### 2.5 Ollama Models

#### Old app -- `OllamaModelsComponent`

130 lines of TypeScript, 138 of template
(`scheduler1/src/app/_component/ollama-models/ollama-models.component.ts`). Route `ollamaModels`,
`AuthGuard` + `RoleGuard` with `roles: ['PLATFORM_ADMIN','TENANT_ADMIN']`
(`app.routing.ts:254-259`).

Three KPI tiles (installed count, disk used, family count), a table with Name / Family /
Parameters / Quantization / Size, colour-coded family pills from `CATEGORY_PALETTE`
(`:40-48`), a pull box offering either a 14-entry `OLLAMA_POPULAR_MODELS` dropdown
(`_models/ollama.model.ts:18-35`) or a typed tag, and a delete modal.

#### New app -- `Models`

196 lines of TypeScript, 169 of template
(`scheduler1/next/src/app/features/ai/models/models.ts`). Route `ai/models`, `authGuard` +
`roleGuard` with `minRole: 'TENANT_ADMIN'` (`app.routes.ts:160-164`); nav entry flagged
`adminOnly` (`features/shell/shell.ts:98`).

Four stat tiles (installed, disk used, average, largest), a per-model disk-share bar
(`diskShare`, `:93-104`), and a 16-entry catalogue that is a filterable table with purpose, note,
approximate size and an installed/Pull column, so a model can be pulled without retyping its name
(`CATALOGUE` at `:36-53`, `pullNamed` at `:120-123`). The installed table uses `TableShell`
(`models.html:137-141`) and drops the Family column -- `family` survives only inside the stats.

### 2.6 Backend

All five controllers are thin: try, delegate, catch, log, return.

`DocumentConverterServiceImpl` (`process/src/main/java/process/model/service/impl/`) enforces its
own 50 MB ceiling because the output is base64-encoded into the JSON response at roughly four
times the file size in heap (`:48-54`, `:116-121`), resolves the family from
`DocumentConverterFormatRegistry` (`util/DocumentConverterFormatRegistry.java:47-70`), converts
through jodconverter to a temp file, and -- when `save=true` -- writes a task row, then uploads
input and output under `<folder>/<taskId>/input|output/` and writes the keys back (`:201-242`).
Markdown gets a hand-written `DocumentFormat` because jodconverter's registry has no entry for it
(`:246-257`).

`AudioTranscriptServiceImpl` posts the audio to an external worker at
`audio.extract.service.base.url` (default `http://host.docker.internal:8100`). The comment at
`:95-110` records the important decision: `extractFromBucket` used to hand the bucket and key
straight to the worker, which fetches with the platform's own credentials and would therefore read
anything; it now downloads the object through `storageBrowserService.downloadObject` -- the same
guarded path the Object Browser uses -- and posts only the bytes.

`TextCleanerRestApi` is the one controller in the codebase with no service dependency at all; it
calls `TextCleanerUtil.clean` inline (`api/TextCleanerRestApi.java:28-31`). The cleaner normalises
CRLF, strips control characters, rejoins hyphen-wrapped words, folds smart quotes, dashes and
ellipses to ASCII, tabs to spaces, collapses runs of spaces, trims line ends, and caps blank runs
at two (`util/TextCleanerUtil.java:20-38`).

`AiAgentServiceImpl` holds the agent CRUD, `resolveRuntimeConfig` (which decrypts the API key for
one request) and `processAdHoc`. `processAdHoc` is where the SSRF guard lives: `validateEndpoint`
refuses anything that is not a public https host unless the operator named the host in
`ai.allowed-endpoint-hosts`, checking *every* address the name resolves to and adding
carrier-grade NAT and IPv6 unique-local to what `InetAddress` classifies (`:313-394`). Both the
file chat and the job assistant reach the provider through `processAdHoc`
(`FileChatServiceImpl.java:194-223`, `JobAssistantServiceImpl.java:92-110`), so the guard covers
them too.

`OllamaServiceImpl` is a three-method OkHttp client over `/api/tags`, `/api/pull` and
`/api/delete` against `ollama.base.url`, with a 30-minute read timeout on the pull.

### 2.7 Tests

| Area | Tests | Where |
|---|---|---|
| AI agent tenant isolation + SSRF guard | 11 | `process/src/test/java/process/model/service/impl/AiAgentServiceImplTenantIsolationTest.java` |
| Audio transcript bucket guard | present | `process/src/test/java/process/model/service/impl/AudioTranscriptBucketGuardTest.java` |
| Transcript segment parsing | 7 | `scheduler1/next/src/app/features/tools/transcript/transcript.spec.ts` |
| Document converter (any layer) | **none** | -- |
| Text cleaner | **none** | -- |
| Ollama service | **none** | -- |
| Any old-app component | **none** | `scheduler1/src` contains no `.spec.ts` files |
| Any new-app component in this feature except `transcript` | **none** | -- |

The transcript spec is a copy, not a test of the component: lines 3-11 say *"Mirrors the
component's parser"*, and `Transcript.segments` is not exported, so the real implementation can
drift without a failure. This is already recorded as finding 24 in `.ai/discovery/risks.md:92`.

---

## 3. Expected behaviour

Where this differs from today it is called out explicitly.

**Document Converter.** A user picks a source -- an upload, or any file in any bucket they can
read, **including inside folders** (today: root only). They pick a target format from the set the
server says is reachable from that input. They may preview both sides before and after converting
(today: neither). They download the result, or save it to a bucket, choosing the folder by browsing
(today: by typing a path). Past conversions are listed with a distinguishable loading, error and
empty state (today: all three render as "Nothing converted yet"), searchable, and each row opens
either side in the shared viewer.

**Audio Transcript.** A user transcribes an upload or a bucket object, with or without timestamps,
and reads the result in whichever of the three views suits them. They may **save the transcript
back into a bucket** and **reopen a saved transcript** later (today: neither). Copy should copy
what is on screen, not the raw string, or `consoleText()` should be deleted.

**Content Cleaner.** A user pastes text, or **picks a `pdf`/`csv`/`txt`/`json`/`xlsx`/`xml` file
from a bucket** (today: paste only), sees the cleaned output beside the original with the character
count and how much was removed (today: output only), and copies it.

**AI Agents.** A tenant admin defines an agent. The provider list is **whatever the `AI_PROVIDER`
lookup holds** -- the platform's three plus anything the tenant added (today: always exactly the
three hard-coded fallbacks). A custom provider must be given an endpoint before the form will
submit (today: the client allows it and the server refuses on save). A new agent must be given a
key unless it is Ollama (today: neither client nor server checks, and the failure surfaces later,
on a different screen). An agent may be **cloned** and its **tool URL copied** (today: neither).
`xlsx` is selectable again.

Two fields deserve a decision rather than a restatement. `instructions` is `nullable = false`
(`model/pojo/AiAgent.java:83`) and required by the validator
(`AiAgentServiceImpl.java:547-549`), yet neither the file chat nor the job assistant uses it --
both build their own system prompt (`FileChatServiceImpl.java:264-289`,
`JobAssistantServiceImpl.java:103`). `targetFileTypes` is likewise required
(`:544-546`) and read by nothing: the old app's `agentsForFile` helper
(`_models/ai-agent.model.ts:43-50`) is exported and never called, and the new file chat filters
only on status and key (`features/objects/chat/file-chat.ts:216-218`). Both fields are only ever
returned, never consumed -- `fetchToolByUuid` hands them to an external caller
(`AiAgentServiceImpl.java:213-222`), and that endpoint has no UI in the new app because Copy tool
URL did not cross. Expected behaviour is that either the tool URL comes back and these fields have
a purpose, or the fields stop being mandatory. Section 6 recommends the former.

**Ollama Models.** Unchanged from today, except that Family should return to the installed table:
it is already parsed (`OllamaServiceImpl.java:61`), already carried on the DTO, and already used
for the "families" stat -- it is simply not rendered.

---

## 4. Frontend requirements

### 4.1 Routes

| Route | Component | Guard | Minimum role |
|---|---|---|---|
| `tools/converter` | `features/tools/converter/converter.ts` `Converter` | `authGuard` | TENANT_USER |
| `tools/transcript` | `features/tools/transcript/transcript.ts` `Transcript` | `authGuard` | TENANT_USER |
| `tools/cleaner` | `features/tools/cleaner/cleaner.ts` `Cleaner` | `authGuard` | TENANT_USER |
| `ai/agents` | `features/ai/agents/agents.ts` `Agents` | `authGuard` | TENANT_USER (write controls gated on `canManageAgents`) |
| `ai/models` | `features/ai/models/models.ts` `Models` | `authGuard` + `roleGuard`, `data.minRole = 'TENANT_ADMIN'` | TENANT_ADMIN |

`ai/agents` must stay open to `TENANT_USER`. It is not an oversight: `fetchAllAgents` is
`TENANT_USER` (`api/AiAgentRestApi.java:62-63`) and the Object Browser's file chat calls it
(`features/objects/chat/file-chat.ts:212`). A role guard on the page would break file chat for
every non-admin. The comment at `app.routes.ts:133-134` already records this; keep it.

### 4.2 Components and shared chrome

Every list on these five screens should use `TableShell`
(`shared/ui/data-table`), which is the single source of the loading / error / empty triad. Today
`Agents` and `Models` do; **`Converter`'s task list does not**, and is the one list in the feature
where a failed load is indistinguishable from an empty one.

Every form field should use `Field` (`shared/ui/field`), which is the single source of validation
messages. `AgentDialog` does. The converter, transcript and cleaner forms are bare inputs; that is
acceptable for a two-field tool form and not worth churning, but any new required field on them
should go through `Field`.

Bucket navigation is needed on three screens (converter source, transcript source, cleaner source)
and two save targets (converter, transcript). Today exactly one implementation exists and it is
private to `Transcript` (`transcript.ts:145-165`, with the stale-response `browseTicket` guard).
It should be lifted into a shared picker rather than copied twice more -- see synthesis §3.

### 4.3 Forms

| Screen | Fields |
|---|---|
| Converter | mode (upload/bucket), file **or** bucket + prefix + key, target format (`<select>`, scoped to the family), save-to-bucket (checkbox), save bucket (`<select>`), folder (browser + text), task name |
| Transcript | mode, file **or** bucket + prefix + key, timestamps (checkbox); after a result: save bucket, save folder |
| Cleaner | mode, textarea **or** bucket + prefix + key |
| Agent dialog | agent name*, provider* (`<select>` from `AI_PROVIDER`), description, model*, API endpoint (required when the provider is not built-in), API key (required for a new non-Ollama agent), target file types (multi-select, at least one), instructions*, status, JSON mode (Ollama only) |
| Models | pull name (text, or a catalogue row's Pull button) |

`*` = required today.

### 4.4 Tables and dialogs

| Table | Columns |
|---|---|
| Converter -- recent conversions | Name (+ input filename), Conversion (`from → to` pills), Size (`in → out`), Location (deep link to `/objects`), Created, actions (view input, view output, delete) |
| Converter -- supported formats | Family, From (pills), To (pills) |
| Transcript -- table view | #, Time (when any segment has one), Text |
| Agents -- table | Agent (+ description), Provider, Model (+ JSON pill), File types, API key state, Created by, Updated by, Status, actions menu |
| Models -- installed | Model, Family *(to be restored)*, Parameters, Quantization, Size, delete |
| Models -- catalogue | Model, Purpose, Size, Note, Installed/Pull |

Dialogs: `AgentDialog` (`FormDialog` shell), `PreviewDialog` (shared, reused by the converter),
and `confirmWith` for both deletes. No Bootstrap modals; the old app's
`#agentModal` / `#deleteAgentModal` / `#deleteModelModal` pattern does not exist in the new app.

### 4.5 Loading, empty and error states

| Surface | Loading | Empty | Error |
|---|---|---|---|
| Converter task list | **missing today** -- shows the empty state | "Nothing converted yet..." | **missing today** -- shows the empty state |
| Converter formats | none needed (collapsed by default) | -- | toast, "Could not load the supported formats." |
| Converter bucket file picker | placeholder option "Reading the bucket…" | "Nothing convertible in this bucket" | silent (`converter.ts:128`) |
| Transcript bucket picker | "Looking…" + inline "looking…" | "No audio here" / "Open a folder below" | silent (`transcript.ts:158-161`) |
| Transcript result | "Extracting…" + a note that it takes a minute | -- | inline card, `error()` |
| Agents list | `TableShell` skeleton | "No agents configured yet." / "No agents match your search." | `TableShell` error + Retry |
| Models installed | `TableShell` skeleton | "No models installed on this host yet." | `TableShell` error + Retry, "Could not reach Ollama." |

The two "silent" rows are the requirement gap: a bucket listing that 403s leaves the picker looking
merely empty on both screens.

### 4.6 Dark and light mode

The new app is token-based (`core/theme.service.ts`, `src/styles.css`); the old app has no dark
mode at all. All five new screens use tokens rather than literal colours, with one exception worth
naming: `models.html:48` hard-codes `[style.background]="'var(--color-brand-500)'"` on the
disk-share bar, which is a token and therefore fine, and `converter.html` uses
`text-warn-500` / `bg-sunken` throughout, also tokens. No new literal hex values should be
introduced by any work here.

### 4.7 Responsive behaviour

`form-grid` collapses to one column on narrow screens; the converter and transcript both use it.
Wide tables sit inside `overflow-x-auto` wrappers (`converter.html:150`, `:201`). The models
stat row is `grid-cols-2 md:grid-cols-4` (`models.html:12`). The agents card view is
`sm:grid-cols-2 xl:grid-cols-3` (`agents.html:35`). Any restored control -- a folder browser, a
clone button -- must not break these; in particular a folder browser must scroll inside its own
container rather than widening the page.

### 4.8 Accessibility

Three segmented controls in this feature are bare `div`s of buttons with no `role="tablist"`:
`converter.html:10`, `transcript.html:121`, and the transcript mode switch at
`transcript.html:10`. This is already recorded in `.ai/discovery/frontend.md:638-643`. Restoring
lost functionality should not add a fourth.

---

## 5. Backend requirements

No new endpoints are required to close the migration gaps except one, and even that one exists --
see the note below the table.

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `documentConverter.json/supportedFormats` | TENANT_USER | Returns the five format families with their input and output extensions (`DocumentConverterFormatRegistry.allFamilies()`) |
| GET | `documentConverter.json/fetchAllTasks` | TENANT_USER | The caller's tenant's non-deleted conversion tasks, newest id first |
| GET | `documentConverter.json/fetchTaskById` | TENANT_USER | One task; refuses a task belonging to another tenant. **Called by neither frontend** |
| POST | `documentConverter.json/convert` | TENANT_USER | Multipart convert. Optionally writes input and output into `bucketName` under `<targetFolder>/<taskId>/` and records a task row |
| DELETE | `documentConverter.json/deleteTask` | TENANT_USER | Soft-deletes a task row (`Status.Delete`). Bucket objects are left in place |
| POST | `audioTranscript.json/extractFromUpload` | TENANT_USER | Multipart `.mp3`/`.m4a` → external worker → transcript string |
| POST | `audioTranscript.json/extractFromBucket` | TENANT_USER | Same, reading the object through the guarded download path first |
| POST | `textCleaner.json/clean` | TENANT_USER | Pure function over `{ text }` |
| GET | `aiAgent.json/fetchAllAgents` | TENANT_USER *(method override)* | The tenant's non-deleted agents, with `apiKeyConfigured`, `createdByName`, `updatedByName` |
| GET | `aiAgent.json/fetchAgentByAgentId` | TENANT_USER *(method override)* | One agent. **Called by neither frontend** |
| GET | `aiAgent.json/fetchToolByUuid` | TENANT_USER *(method override)* | The agent behind a tool uuid, tenant-checked and active-only. **Called by the old frontend's Copy tool URL only** |
| POST | `aiAgent.json/processAdHoc` | TENANT_USER *(method override)* | Runs a prompt through a provider. **Called by no frontend**; called internally by file chat and the job assistant |
| POST | `aiAgent.json/addAgent` | TENANT_ADMIN *(class level)* | Creates an agent, stamps `tenantId` and a `toolUuid`, encrypts the key |
| PUT | `aiAgent.json/updateAgent` | TENANT_ADMIN *(class level)* | Updates one it owns; a blank key leaves the stored key alone |
| DELETE | `aiAgent.json/deleteAgent` | TENANT_ADMIN *(class level)* | Soft-deletes one it owns |
| GET | `ollama.json/listModels` | TENANT_ADMIN | `GET /api/tags` on the configured Ollama host |
| POST | `ollama.json/pullModel` | TENANT_ADMIN | `POST /api/pull`, 30-minute read timeout, returns when the pull finishes |
| DELETE | `ollama.json/deleteModel` | TENANT_ADMIN | `DELETE /api/delete` |

Restoring the Content Cleaner's bucket source and the transcript's save-back needs **no new
endpoint**: both are compositions of `storage.json/previewObject`, `storage.json/uploadObject`
and `storage.json/createFolder`, which the object-browser feature already exposes and which the old
app already used this way (`content-cleaner.component.ts:153-155`,
`audio-transcript-extractor.component.ts:413-441`).

The one thing that *would* need a server change is making the provider list work at its source
rather than in the client -- see §12.1 and synthesis §3.1 for the two options and the
recommendation.

### 5.1 Services

| Service | Responsibility | Notes |
|---|---|---|
| `DocumentConverterServiceImpl` | Format validation, jodconverter call, optional bucket write, task record | Own 50 MB ceiling because the output is base64ed into the response (`:48-54`) |
| `AudioTranscriptServiceImpl` | Guarded bucket read, temp file, multipart post to the worker | 250 MB upload ceiling, 500 MB bucket ceiling, 30-minute read timeout |
| `TextCleanerUtil` | Pure string cleaning | Static; no service class |
| `AiAgentServiceImpl` | Agent CRUD, key encryption, `resolveRuntimeConfig`, `processAdHoc`, endpoint allow-listing | The allow-list is the SSRF guard for the whole product's outbound AI traffic |
| `OllamaServiceImpl` | OkHttp over the Ollama HTTP API | Host-global; carries no tenant concept |
| `StorageBrowserServiceImpl` | Every bucket read and write these screens make | Owned by `object-browser`; the guarded `uploadObject(bucket, key, …)` overload is the one the converter uses (`:296-299`) |

---

## 6. Database requirements

Two tables, both tenant-scoped, both already present.

### `ai_agent` (`model/pojo/AiAgent.java`)

| Column | Type | Notes |
|---|---|---|
| `ai_agent_id` | bigint PK | sequence `ai_agent_Seq`, initial 1000 |
| `tenant_id` | bigint, FK → `tenant` | null means platform-owned. Indexed: `idx_ai_agent_tenant_id` |
| `agent_name` | varchar, not null | |
| `description` | text | |
| `provider` | varchar, not null | free text; not FK'd to `lookup_data` |
| `api_endpoint` | varchar | |
| `api_key` | varchar(1000) | encrypted at `AiAgentServiceImpl.java:559`, decrypted at `:246` |
| `model` | varchar, not null | |
| `target_file_types` | varchar, not null | CSV. Required and read by nothing (§3) |
| `instructions` | text, not null | Required and read by nothing but `fetchToolByUuid` (§3) |
| `status` | varchar, not null | `Status` enum; delete is soft |
| `json_mode` | boolean | |
| `date_created` | timestamp | |
| `tool_uuid` | varchar(36), unique | backfilled lazily by `ensureToolUuid` (`:585-591`) |
| `created_by`, `updated_by` | bigint | added by V22 (`V22__audit_columns.sql:33-34`) |

### `document_converter_task` (`model/pojo/DocumentConverterTask.java`)

| Column | Type | Notes |
|---|---|---|
| `document_converter_task_id` | bigint PK | sequence `document_converter_task_id_Seq` |
| `tenant_id` | bigint, FK → `tenant` | Indexed: `idx_document_converter_task_tenant_id` |
| `task_name` | varchar, not null | |
| `input_file_name`, `input_format` | varchar, not null | |
| `input_content_type`, `input_file_size` | varchar / bigint | |
| `output_format` | varchar, not null | |
| `output_file_name`, `output_content_type`, `output_file_size` | | |
| `bucket_name` | varchar, not null | |
| `target_folder` | varchar | **write-only**: set at `DocumentConverterServiceImpl.java:216`, `getTargetFolder()` has no caller in `src/main/java` (`.ai/discovery/database.md:637-641`) |
| `input_storage_key`, `output_storage_key` | varchar, not null | written "pending", then overwritten after upload (`:218-233`) |
| `status` | varchar, not null | `Status` enum; delete is soft |
| `date_created` | timestamp, not null | set in `@PrePersist` |

Neither table carries `created_by`/`updated_by` on `document_converter_task` -- only `ai_agent`
does. If the converter's task list ever needs a "created by" column, that is a migration.

**Migrations needed for the work in this document: none.** Every gap named here is a frontend gap
or a service-level validation gap. The one caveat: neither table has a creation changeset --
Liquibase creates six tables and Hibernate owns the rest, and `ddl-auto=validate` on stage and prod
means a genuinely fresh database has no path to these two either
(`.ai/discovery/database.md:546-556`). That is a platform-wide risk owned elsewhere, not something
this feature can fix, but any Execution phase that assumes it can create a table here should know
it cannot.

`AI_PROVIDER` lives in `lookup_data`, seeded by
`db/changelog/changelog-sets/V9.0-ai-provider-bucket-list/V9__insert_ai_provider_and_bucket_list.sql`
(parent `lookupId` 1020, children OpenAI / Anthropic / Ollama). It is a **tenant-extendable**
family: a tenant sees the platform's rows and may add its own, which are stamped with its tenant id
(`SettingServiceImpl.java:73-83`, tested at
`process/src/test/java/process/model/service/impl/TenantOwnedLookupTest.java:104-109`).

---

## 7. Validation

`C` = client, `S` = server, `C+S` = both.

### Document Converter

| Rule | Where | Evidence |
|---|---|---|
| A source file must be chosen | C | old `:409-412`; new `canConvert` `:111-115` |
| A target format must be chosen | C+S | old `:417-420`; new `:192`; server `DocumentConverterServiceImpl.java:122-124` |
| The input extension must belong to a known family | C+S | old `:413-416`; new shows a warning line and hides the form (`converter.html:58-59`); server `:129-132` |
| The target must be in that family's output list | S only | server `:133-137`. Neither client can offer an invalid target, so this is a backstop |
| File ≤ 50 MB | **S only** | `:116-121`. Neither client checks; a 200 MB upload is transmitted in full before being refused |
| `bucketName` required when `save=true` | C+S | old `:421-424`; new `canConvert` `:113`; server `:139-141` |
| `taskName` required when `save=true` | C+S (weaker on the new client) | old `:425-428` refuses an empty name; new **defaults** it to the filename stem (`converter.ts:206`) so the server rule at `:142-144` can never fire |
| The caller may write to that bucket | S only | `storageBrowserService.uploadObject` → `resolveServiceForCaller` (`StorageBrowserServiceImpl.java:296-299`) |

### Audio Transcript

| Rule | Where | Evidence |
|---|---|---|
| A source must be chosen | C | old `:89-93`; new `canExtract` `:110-111` |
| Extension is `.mp3` or `.m4a` | C+S (old), **S + `accept` only** (new) | old `:94-98` refuses with the accepted list named; new relies on `accept=".mp3,.m4a"` (`transcript.html:22`), which a user can override in the file dialog; server `AudioTranscriptServiceImpl.java:72-74` and `:121-123` |
| Upload ≤ 250 MB | S only | `:75-80`, with a message telling the user to use a bucket instead |
| Bucket object ≤ 500 MB | S only | `:137-141` |
| The caller may read that object | S only | `:127-132`, delegating to the guarded download |
| A save target must be named | C only (old) | old `validateSaveTarget` `:400-411`. No successor -- the new screen cannot save |

### Content Cleaner

| Rule | Where | Evidence |
|---|---|---|
| Text must be non-blank | C only | old `:62-65`; new disables the button on `!input().trim()` (`cleaner.html:16`) and returns early (`cleaner.ts:20`). The server accepts null and returns `""` (`TextCleanerUtil.java:21-23`) |
| Bucket file extension in the supported six | C only (old) | old `:122-126` and again at `:143-147`. No successor |

### AI Agents

| Rule | Where | Evidence |
|---|---|---|
| `agentName` required | C+S | old `:162`; new `agent-dialog.ts:46`; server `:527-529` |
| `provider` required | C+S | old `:164`; new `:48`; server `:530-532` |
| `model` required | C+S | old `:167`; new `:49`; server `:541-543` |
| `instructions` required | C+S | old `:168`; new `:52`; server `:547-549` |
| At least one target file type | C+S | old `:252-255`; new `:73-76`; server `:544-546` |
| A non-built-in provider needs an `apiEndpoint` | **C+S (old), S only (new)** | old `:248-251`; server `:534-540`. The new dialog has no such check, so the refusal now arrives as a toast after a round trip |
| A new agent needs an API key unless Ollama | **C only (old), nowhere (new)** | old `:256-259`. The server's `validateAgent` has no key rule; the check only exists in `validateAdHoc` (`:290-292`), which runs at *use* time. A keyless OpenAI agent saves cleanly today and fails the first time someone chats with it |
| A blank key on edit keeps the stored key | C+S | old `:265-267`; new `agent-dialog.ts:82-83`; server `applyAgentDto` only writes a non-blank key (`:558-560`) |
| `apiEndpoint` must be an allowed address | **S, at use time only** | `validateEndpoint` (`:327-359`) is called from `validateAdHoc` (`:307-309`) and **not** from `validateAgent`. An unreachable-by-policy endpoint saves; the refusal appears later, on the file chat or job assistant screen |
| `status` may only be Active/Inactive from the UI | C | new `agent-dialog.html:80-83`; old `statusList` filters out `Delete` (`ai-agent.component.ts:27`). The server accepts any `Status` value on update (`:142-144`) |

### Ollama Models

| Rule | Where | Evidence |
|---|---|---|
| A model name must be given | C only | old `:82-86`; new `:144-145` and `[disabled]` on the button (`models.html:64`) |
| The name is a real Ollama tag | Neither | the pull fails at Ollama and the message is surfaced (`OllamaRestApi.java:48-52`) |

**Client-only rules are findings, and there are five:** the file-size checks on the converter and
the transcript (both server-only in reality, which is the safe direction), the content cleaner's
extension check (old app, client-only, gone), the transcript's save-target check (old app,
client-only, gone), and -- the one that matters -- the AI agent **API-key-required** rule, which
exists on no server path at save time and on no client at all in the new app.

---

## 8. Security

Four layers, per screen. `PLATFORM_ADMIN > TENANT_ADMIN > TENANT_USER`, wired through
`RoleHierarchyImpl` at `config/MethodSecurityConfig.java:29`. None of these endpoints is
`permitAll` -- `config/SecurityConfig.java:36-55` lists the exemptions and none of them matches
`/aiAgent.json`, `/ollama.json`, `/documentConverter.json`, `/audioTranscript.json` or
`/textCleaner.json`; they all fall to `.anyRequest().authenticated()`.

### 8.1 Document Converter

| Layer | Rule |
|---|---|
| Frontend guard | `authGuard` only (`app.routes.ts:166-168`). Any signed-in user opens it |
| Controller | `@PreAuthorize("hasRole('TENANT_USER')")` at class level, no method overrides (`api/DocumentConverterRestApi.java:20`) |
| Service | `fetchTaskById` and `deleteTask` call `TenantOwnership.isOwnedByCaller(task.getTenantId())` after `findById` (`:104`, `:275`). `convert`'s bucket write goes through the guarded `uploadObject` overload |
| Hibernate filter | `DocumentConverterTask` declares `tenantFilter` on `tenant_id = :tenantId` (`model/pojo/DocumentConverterTask.java:22-23`), enabled by `tenantFilterHelper.enableIfNeeded` before every read. It does **not** apply to `findById`, which is why the two service checks above exist |

Per role: a **TENANT_USER** converts, saves into any bucket their tenant can write, lists and
deletes their tenant's tasks. A **TENANT_ADMIN** has exactly the same rights here -- nothing on
this screen is admin-only. A **PLATFORM_ADMIN** has the filter disabled
(`security/TenantFilterHelper.java:28-33`), so `fetchAllTasks` returns **every tenant's**
conversions in one undifferentiated list, with no tenant column to tell them apart.

### 8.2 Audio Transcript / Content Cleaner

| Layer | Rule |
|---|---|
| Frontend guard | `authGuard` only |
| Controller | class-level `TENANT_USER` (`api/AudioTranscriptRestApi.java:21`, `api/TextCleanerRestApi.java:20`) |
| Service | Transcript: the bucket read is `storageBrowserService.downloadObject`, which applies the object browser's own bucket-and-key guard; the comment at `AudioTranscriptServiceImpl.java:95-110` explains why this is not the worker's job. Cleaner: no state, nothing to own |
| Hibernate filter | Not applicable -- neither owns an entity |

Per role: identical for all three roles. A PLATFORM_ADMIN gains nothing here except whatever the
storage guard grants them.

### 8.3 AI Agents -- the layer that actually disagrees with itself

| Layer | Rule |
|---|---|
| Frontend guard | `authGuard` only on `ai/agents`. Write controls hidden behind `auth.canManageAgents()` = `hasAtLeast('TENANT_ADMIN')` (`core/auth/auth.service.ts:92`). **Hiding is not enforcement** -- the endpoints below are what stops a TENANT_USER writing |
| Controller | `@PreAuthorize("hasRole('TENANT_ADMIN')")` at class level (`api/AiAgentRestApi.java:21`). Four methods carry their own annotation, which **replaces** the class one: `fetchAllAgents` (`:62`), `fetchAgentByAgentId` (`:73`), `fetchToolByUuid` (`:84`) and `processAdHoc` (`:95`) are all `TENANT_USER`. `addAgent`, `updateAgent` and `deleteAgent` inherit `TENANT_ADMIN` |
| Service | `updateAgent`, `deleteAgent`, `fetchAgentByAgentId`, `fetchToolByUuid` and `resolveRuntimeConfig` each call a **local** `isOwnedByCaller` (`AiAgentServiceImpl.java:100-105`), not `TenantOwnership`. `fetchAllAgents` relies on the filter alone |
| Hibernate filter | `AiAgent` declares `tenantFilter` (`model/pojo/AiAgent.java:22-23`). Applies to `findByStatusNotOrderByAiAgentIdDesc`; does not apply to `findById` or `findByToolUuid`, which is why every by-id path re-checks |

Per role:

- **TENANT_USER** may list every agent in their tenant, including each one's `instructions`,
  `apiEndpoint` and `toolUuid` -- `getAiAgentDto` returns all three
  (`AiAgentServiceImpl.java:573`, `:577`, `:581`). They may resolve any of those uuids through
  `fetchToolByUuid`. They may not create, edit or delete. The old UI showed them a Copy tool URL
  button, consistent with the endpoint; the new UI shows them nothing, but the payload still
  carries the data.
- **TENANT_ADMIN** may additionally create, edit and delete agents **in their own tenant**. The
  service check refuses an agent whose `tenantId` differs, and the refusal wording is identical to
  "not found" so it does not confirm the row exists (`:138`, `:158`).
- **PLATFORM_ADMIN** short-circuits `isOwnedByCaller` to `true` (`:101-102`) and has the filter
  disabled, so they see and may edit every tenant's agents. An agent they *create* is stamped
  `TenantContext.getTenantId()`, which for them is null (`:115`) -- a platform-owned row that no
  tenant's filter (`tenant_id = :tenantId`) will ever match. It is therefore invisible to, and
  unusable by, every tenant's file chat, while remaining visible to them. That is consistent with
  the codebase's stated reading of a null `tenant_id` (`security/TenantOwnership.java:16-18`), and
  it is a trap for a platform admin who thinks they are creating a shared agent.

**The divergence.** `AiAgentServiceImpl`'s private `isOwnedByCaller` is not the same rule as
`TenantOwnership.isOwnedByCaller`. The shared class refuses a caller carrying no tenant outright:
`callerTenantId != null && Objects.equals(...)` (`security/TenantOwnership.java:35-41`), with the
reason spelled out at `:16-18`. The local copy compares directly, so a non-platform-admin caller
with a null `tenantId` and a platform-owned agent satisfies `Objects.equals(null, null)` and is
granted ownership. Today this needs a `TENANT_ADMIN` row with a null `tenant_id` to reach, which
should not exist; the point is that the check has drifted from the one place the codebase created
to stop it drifting, in the one service where a second reading is most expensive.

### 8.4 Ollama Models -- the one with no tenancy at all

| Layer | Rule |
|---|---|
| Frontend guard | `authGuard` + `roleGuard` with `minRole: 'TENANT_ADMIN'` (`app.routes.ts:160-164`). Old app: `RoleGuard` with `roles: ['PLATFORM_ADMIN','TENANT_ADMIN']` (`app.routing.ts:257-258`). Equivalent |
| Controller | class-level `TENANT_ADMIN`, no overrides (`api/OllamaRestApi.java:19`) |
| Service | **none**. `OllamaServiceImpl` has no tenant concept and no ownership check |
| Hibernate filter | not applicable -- no entity |

Per role: a **TENANT_USER** cannot reach it at any layer. A **TENANT_ADMIN** of *any* tenant may
list, pull and delete models on the shared host. A **PLATFORM_ADMIN** has the same rights.

The consequence is worth stating plainly, because three of the four layers are silent about it:
tenant A's admin can delete a model that tenant B's agents depend on, and B's file chat will start
failing with a provider error naming a model that no longer exists. Nothing in the product warns
either party. Disk is also a shared, unbounded resource: any tenant admin can pull a 9 GB model.

---

## 9. Error handling

| Failure | What the user sees today | Where |
|---|---|---|
| Supported formats fails to load | Toast: "Could not load the supported formats." The whole target-format form stays hidden, with no explanation | `converter.ts:163` |
| Conversion is refused (unsupported target, missing bucket) | Toast with the server's own message | `converter.ts:222` |
| Conversion fails inside LibreOffice | Toast: "Conversion failed -- the file may be corrupt or password-protected: <detail>", or, on a timeout, a message explaining that conversions run one at a time | `DocumentConverterServiceImpl.java:169-178` |
| File over 50 MB | Toast naming the actual size and the limit, and suggesting splitting it | `:117-121` |
| Converter task list fails to load | **Nothing.** The flag is cleared and the empty state renders | `converter.ts:268` |
| Converter bucket listing fails | **Nothing.** The picker shows "Nothing convertible in this bucket" | `converter.ts:128` |
| Bucket source cannot be read | Toast: "Could not read that file from the bucket." | `converter.ts:145` |
| Task delete fails | Toast with the server message, or "Delete failed." | `converter.ts:288` |
| Transcription fails | Inline error card with the server's message, or "The extraction failed." | `transcript.ts:185`, `transcript.html:107-109` |
| Transcript bucket listing fails | **Nothing.** "No audio here" | `transcript.ts:158-161` |
| Audio too large / wrong type | The worker's or the service's message, surfaced in the same inline card. The controller returns HTTP 400 with `ex.getMessage()` -- flagged as finding 10 in `.ai/discovery/risks.md:62` for returning a raw exception message | `api/AudioTranscriptRestApi.java:40`, `:50` |
| Clean fails | Toast with the server message, or "The clean-up failed." | `cleaner.ts:31` |
| Agents list fails | `TableShell` error panel with a Retry button | `agents.ts:81`, `agents.html:16-20` |
| Agent save is refused by the server | Toast with the server's message -- which for a custom provider with no endpoint is "This provider requires an apiEndpoint (only OpenAI/Anthropic/Ollama have a built-in one)." The offending field is not highlighted | `agent-dialog.ts:97`, server `:539` |
| Agent form is locally invalid | Toast: "Check the highlighted fields." plus per-field messages from `Field` | `agent-dialog.ts:70` |
| Agent delete fails | Toast with the server message, or "Delete failed." | `agents.ts:130` |
| Ollama is unreachable | `TableShell` error: "Could not reach Ollama." The server's own message is "Could not reach Ollama: <detail>" | `models.ts:138`, server `api/OllamaRestApi.java:37-38` |
| Model pull fails | Toast: the server's "Could not pull model: <detail>", or "The pull failed." | `models.ts:163` |
| A stored endpoint is refused at chat time | On the **file chat** screen, not the agents screen: "That apiEndpoint is not an allowed AI provider address." | `AiAgentServiceImpl.java:61-62`, reached via `FileChatServiceImpl.java:223` |
| A keyless non-Ollama agent is used | On the file chat screen: "apiKey missing (required unless provider is Ollama)." | `AiAgentServiceImpl.java:290-292` |
| An AI provider call fails for any other reason | "The AI provider request failed." -- deliberately detail-free, with the provider's own response body going to the log only | `:268-275` |

The pattern to hold onto: **five of these say nothing at all**, and four of the five are bucket or
list loads. The new app's own convention (`TableShell`, whose header comment is the reason 19 other
screens have three distinguishable states) is not applied to the converter's task list or to either
bucket picker.

---

## 10. Dependencies

| Depends on | For what | Evidence |
|---|---|---|
| `object-browser` | Every bucket read and write: `storage.json/buckets`, `/listObjects`, `/previewObject`, `/uploadObject`, `/createFolder`. In the new app, also the `StorageService` class and the `PreviewDialog` component | `converter.ts:7-8`, `transcript.ts:6`, `.ai/discovery/frontend.md:327` |
| `storage-connections` | The buckets themselves. With no connection configured, all three tool screens' bucket modes are empty by design | `.ai/discovery/features.md:46` |
| `platform-configuration` | The `AI_PROVIDER` lookup family that should populate the agent provider dropdown | `SettingServiceImpl.java:73-83` |
| LibreOffice | In-image, port 2002, driven by jodconverter 4.4.7. The converter is inert without it | `.ai/discovery/application-inventory.md:81`, `:203` |
| Ollama | `ollama.base.url`, default `http://host.docker.internal:11434`. External to every compose file | `.ai/discovery/application-inventory.md:80` |
| Audio transcription worker | `audio.extract.service.base.url`, default `http://host.docker.internal:8100`. **External and not described anywhere in this repo** -- Discovery marks it "not verified" | `.ai/discovery/backend.md:924` |
| Hosted AI providers | OpenAI and Anthropic at fixed URLs; anything else at the agent's own endpoint, subject to the allow-list | `AiAgentServiceImpl.java:396-407` |

And what depends on *this* feature: `object-browser`'s file chat calls
`aiAgent.json/fetchAllAgents` (`features/objects/chat/file-chat.ts:212`), and `job-assistant` calls
`resolveRuntimeConfig` (`JobAssistantServiceImpl.java:92`). This is the cycle Discovery records at
`.ai/discovery/features.md:452` -- `object-browser` and `content-and-ai-tools` are mutually
dependent -- and it is the reason `ai/agents` must stay open to `TENANT_USER`.

---

## 11. Acceptance criteria

Fixtures assumed throughout: tenant **A** and tenant **B**; `alice_user` (TENANT_USER, tenant A),
`alice_admin` (TENANT_ADMIN, tenant A), `bob_admin` (TENANT_ADMIN, tenant B), `pat` (PLATFORM_ADMIN,
no tenant). Bucket `a-bucket` is reachable by tenant A and holds `report.docx` at the root and
`nested/report2.docx` one level down, plus `talk.mp3` under `audio_text/input/`. Agent `A-agent`
belongs to tenant A; `B-agent` to tenant B.

### Document Converter

1. `alice_user` opens `/tools/converter`, uploads `report.docx`, and the "Convert to" select is
   populated from the TEXT family and pre-selects a format that is not `docx`.
2. `alice_user` converts `report.docx` to `pdf` without ticking save, and a Download button
   appears; clicking it saves a file named `report.pdf`.
3. `alice_user` chooses "From a bucket", selects `a-bucket`, and **`nested/report2.docx` is
   reachable** -- either listed directly or through a folder the picker offers. *(Fails today: the
   picker lists the root only and hides folders.)*
4. Positive control for 3 on the same fixture: `report.docx`, at the root of `a-bucket`, is listed
   and convertible. *(Passes today.)*
5. `alice_user` ticks "Save the result to a bucket", picks `a-bucket`, and can choose the
   destination folder **by browsing it**, not only by typing a path. *(Fails today.)*
6. `alice_user` converts with save on; the row appears in "Recent conversions" with the input and
   output sizes, and its Location link opens `/objects` at the bucket and folder the output was
   written to.
7. While the conversion list is loading, `alice_user` sees a loading state, **not** the
   "Nothing converted yet" empty state. *(Fails today.)*
8. With the list endpoint returning an error, `alice_user` sees an error message and a retry
   control, **not** the empty state. *(Fails today.)*
9. Positive control for 7 and 8: with the endpoint returning an empty array, `alice_user` sees
   "Nothing converted yet". *(Passes today.)*
10. `alice_user` deletes a conversion; the row disappears, and opening `/objects` at that folder
    shows the converted file is **still there**.
11. `bob_admin` calls `documentConverter.json/deleteTask` with tenant A's task id and is refused
    with a "not found" message; the task still appears in `alice_user`'s list.
12. Positive control for 11: `alice_admin` deletes the same task id successfully.
13. `alice_user` uploads a 60 MB file; the refusal names the actual size and the 50 MB limit.
14. `alice_user` uploads a `.zip`; the screen states that `.zip` is not a convertible format before
    any request is sent.

### Audio Transcript

15. `alice_user` opens `/tools/transcript`, chooses `a-bucket`, walks into `audio_text/input/` via
    the folder buttons, selects `talk.mp3`, and extracts a transcript.
16. With "Include timestamps" ticked, the timeline view shows one row per `[HH:MM:SS.mmm]` marker
    and clicking a timestamp copies just that timestamp.
17. With "Include timestamps" unticked, all three views still render -- the table's Time column is
    absent and each line is its own row.
18. `alice_user` saves a finished transcript into a **new** folder in `a-bucket`; the folder is
    created, `transcript.txt` is written into it, and the saved path is shown. *(Fails today: no
    save path exists.)*
19. `alice_user` later selects that saved `.txt` from the bucket picker and its contents load as a
    transcript without re-running transcription. *(Fails today.)*
20. Positive control for 18 and 19 on the same fixture: extracting `talk.mp3` and copying the
    transcript to the clipboard works. *(Passes today.)*
21. `alice_user` uploads a `.wav`; the refusal names `.mp3` and `.m4a` and no request is sent.
    *(Fails today: the `accept` attribute can be bypassed and only the server refuses.)*
22. `bob_admin` posts `extractFromBucket` with `a-bucket` and `audio_text/input/talk.mp3`; the
    request is refused by the storage guard and no transcript is returned.
23. Positive control for 22: `alice_user` posts the identical body and receives a transcript.

### Content Cleaner

24. `alice_user` pastes text containing smart quotes, an em dash, a hyphen-wrapped word and four
    consecutive blank lines; the output has ASCII quotes, an ASCII hyphen, the word rejoined, and
    at most one blank line between paragraphs.
25. `alice_user` picks `report.pdf` from `a-bucket` and its text is extracted and cleaned without
    leaving the screen. *(Fails today: there is no bucket source.)*
26. Positive control for 25: pasting the same text into the box and clicking Clean produces the
    same cleaned output. *(Passes today.)*
27. The screen shows the cleaned character count and how many characters were removed.
    *(Fails today.)*
28. `alice_user` clicks Copy and the clipboard holds the cleaned text, not the input.

### AI Agents

29. `alice_admin` opens the New agent dialog and the Provider select offers **every child of the
    `AI_PROVIDER` lookup visible to tenant A**, including a provider `alice_admin` added under
    Settings → Lookup. *(Fails today: always exactly OpenAI, Anthropic, Ollama.)*
30. Positive control for 29: with the `AI_PROVIDER` children being exactly the three seeded rows,
    the select offers exactly those three. *(Passes today, for the wrong reason.)*
31. `alice_admin` selects a provider that is not OpenAI/Anthropic/Ollama, leaves API endpoint blank,
    and **the form refuses to submit**, marking the endpoint field. *(Fails today: it submits and
    the server's refusal arrives as a toast.)*
32. `alice_admin` creates an OpenAI agent with no API key and is told a key is required **before**
    the agent is saved. *(Fails today at every layer: it saves, and the failure surfaces later in
    file chat.)*
33. Positive control for 32: an Ollama agent with no API key saves successfully and the key column
    reads "Not needed".
34. `alice_admin` edits an agent that has a stored key, leaves the key field blank, saves, and the
    key column still reads "Configured".
35. `alice_admin` selects `xlsx` as a target file type. *(Fails today: `xlsx` is not in the new
    dialog's list.)*
36. An agent created in the old app with `targetFileTypes = "pdf,xlsx"` is opened in the new edit
    dialog: both types are visible as selected, and deselecting `xlsx` is possible. *(Fails today:
    `xlsx` is retained in the payload but has no button, so it can be neither seen nor removed.)*
37. `alice_admin` clones `A-agent`; a dialog opens pre-filled with `A-agent (Copy)` and saving
    creates a second, independent agent. *(Fails today.)*
38. `alice_user` copies `A-agent`'s tool URL and a GET on it returns that agent's name, model and
    instructions. *(Fails today in the UI; the endpoint works.)*
39. `bob_admin` GETs `aiAgent.json/fetchToolByUuid` with `A-agent`'s uuid and is refused with
    "Tool not found or not active."
40. Positive control for 39: `alice_user` GETs the same uuid and receives the agent.
41. `alice_user` opens `/ai/agents`; the list renders and **no** New agent / Edit / Delete control
    is present.
42. Positive control for 41: `alice_admin` opens the same page and all three controls are present.
43. `alice_user` POSTs `aiAgent.json/addAgent` directly and receives 403.
44. `bob_admin` PUTs `aiAgent.json/updateAgent` with `A-agent`'s id and receives a "not found"
    message; `A-agent` is unchanged when `alice_admin` reloads.
45. Positive control for 44: `alice_admin` PUTs the same id with a new description and the change
    is visible on reload.
46. `pat` opens `/ai/agents` and sees agents from both tenants; each row indicates which tenant it
    belongs to. *(Fails today: they are shown in one list with no owner column.)*
47. `alice_admin` sets an agent's status to Inactive; the file chat agent picker in
    `/objects` no longer offers it.

### Ollama Models

48. `alice_admin` opens `/ai/models`, expands the catalogue, filters for "coder", and pulls
    `qwen2.5-coder:7b` with one click; when it finishes the row reads "Installed" and the model
    appears in the installed table.
49. The installed table shows each model's family. *(Fails today: the column was dropped.)*
50. `alice_user` navigates to `/ai/models` and lands on `/unauthorized`.
51. Positive control for 50: `alice_admin` navigates to `/ai/models` and the page loads.
52. `alice_user` GETs `ollama.json/listModels` directly and receives 403.
53. With Ollama stopped, `alice_admin` opens `/ai/models` and sees an error panel with a Retry
    button, not an empty table.
54. `bob_admin` deletes a model that `A-agent` names; the deletion succeeds, and this is recorded
    as the known shared-host behaviour rather than a bug in the test. *(See §12.6 -- if the
    Execution phase adopts a warning or a guard, this criterion becomes "…and is warned that
    agents in other tenants reference it".)*

---

## 12. Known issues

Each with the evidence for it. None of these is fixed here.

### 12.1 The AI agent provider dropdown ignores the `AI_PROVIDER` lookup entirely

`agents.ts:93-96` reads:

```ts
const lookup = (response.data?.lookupDatas ?? []).find((l: any) => l.lookupType === 'AI_PROVIDER');
const values = (lookup?.children ?? []).map((c: any) => c.lookupValue).filter(Boolean);
this.providers.set(values.length ? values : ['OpenAI', 'Anthropic', 'Ollama']);
```

`appSetting` populates each `LookupDataDto` through `fillLookupDateDto`, which sets `lookupId`,
`encrypted`, `lookupValue`, `lookupType`, `description`, `dateCreated` and `tenantId` -- and never
`children` (`SettingServiceImpl.java:605-616`). `LookupDataDto` is
`@JsonInclude(JsonInclude.Include.NON_NULL)` (`LookupDataDto.java:13`), so the field does not appear
in the JSON at all. `values` is therefore always empty and the fallback always fires.

Consequences, in order of how much they cost:

- A tenant admin who adds a provider under Settings → Lookup -- exactly what
  `TENANT_EXTENDABLE_LOOKUPS` exists to let them do (`SettingServiceImpl.java:70-83`) -- will never
  see it in the dropdown.
- An existing agent whose provider is not one of the three (created in the old app, which read the
  lookup correctly) opens in the edit dialog with a `<select>` that has no matching `<option>`. The
  `FormControl` still holds the real value, so saving without touching the select preserves it; but
  the field renders blank, and one click on the select silently rewrites the provider.
- The comment above the method -- *"Providers come from the `AI_PROVIDER` lookup so the list stays
  configurable"* (`:86`) -- states the opposite of what the code does.

The old app got this right by making two calls: `appSetting` to find the parent's `lookupId`, then
`setting.json/fetchSubLookupByParentId` for the children
(`ai-agent.component.ts:105-137`). `fetchSubLookupByParentId` does return children, with the
tenant-extendable visibility rule applied (`SettingServiceImpl.java:538-560`).

### 12.2 The converter cannot reach a file that is not at a bucket's root

`onBucketChange` calls `storage.listObjects(value, '')` (`converter.ts:123`) and no other listing
call exists in the file; `convertibleObjects` returns `false` for every folder row
(`:98`). There is no prefix state, no breadcrumb, no folder button.

This is not a hypothetical: the transcript screen in the same codebase carries a comment saying the
project's own audio *"sits two levels down, under audio_text/input"* and that listing only the root
*"showed an empty picker on a bucket holding forty files"* (`transcript.ts:140-142`). The converter
has the bug that comment describes being fixed.

### 12.3 The converter's task list has no loading and no error state

`tasksLoading` is declared (`converter.ts:81`), set true before the request and false after
(`:261`, `:265`, `:268`), and used only to disable the Refresh button and spin its icon
(`converter.html:188-190`). The list itself branches on `!tasks().length`
(`converter.html:193`). The error callback sets no message (`converter.ts:268`).

So a first paint, a 500 and a genuinely empty list are the same screen. Every other list in the new
app uses `TableShell` for precisely this reason; the converter is one of the few that does not.

### 12.4 A stored `apiEndpoint` is validated at use time, never at save time

`validateAgent` (`AiAgentServiceImpl.java:526-551`) checks name, provider, endpoint-presence for a
custom provider, model, target file types and instructions. It does **not** call `validateEndpoint`.
`validateAdHoc` does (`:307-309`).

The security consequence is nil -- `processAdHoc` is the only path to the network, and both
`FileChatServiceImpl.java:223` and `JobAssistantServiceImpl.java:107` go through it, so the SSRF
guard holds. The usability consequence is real: an agent pointed at `http://10.0.0.5:8080` saves
with a success toast, and the refusal appears days later on the Object Browser's file chat panel,
worded as a provider problem, on a screen whose author cannot fix it.

The tests confirm the split: `AiAgentServiceImplTenantIsolationTest` has seven cases for the
endpoint rule and all seven drive `processAdHoc`, none `addAgent`
(`:125-198`).

### 12.5 A non-Ollama agent can be saved with no API key, by any path

The old client refused it (`ai-agent.component.ts:256-259`). The new dialog has no such check. The
server's `validateAgent` has no key rule at all. The first thing that notices is
`validateAdHoc` at use time: "apiKey missing (required unless provider is Ollama)."
(`AiAgentServiceImpl.java:290-292`).

The new agents list does flag it -- `keyState` returns "Not set" with the hint "This provider needs
an API key to work" (`agents.ts:142`) -- which is good, and is a warning after the fact rather than
a rule.

### 12.6 Ollama models are a shared host resource with no tenant boundary

`OllamaServiceImpl` has no tenant parameter, no ownership check and no entity. `OllamaRestApi` is
`TENANT_ADMIN` at the class level with no method overrides. So a `TENANT_ADMIN` of any tenant can
delete any model on the host, including one another tenant's agents name, and can pull models onto
shared disk without limit.

The new UI's delete confirmation says *"Any agent using it will stop working until you pull it
again"* (`models.ts:171`) -- true, and it does not say *whose* agents.

### 12.7 `deleteTask` reports success for a task that does not exist

```java
if (task.isPresent() && !this.isOwnedByCaller(task.get())) { return ERROR "not found"; }
if (task.isPresent()) { ...soft delete... }
return new ResponseDto(SUCCESS, String.format("DocumentConverterTask deleted with %s.", id));
```

(`DocumentConverterServiceImpl.java:267-283`.) A nonexistent id falls past both branches and gets
the success message. A *cross-tenant* id is correctly refused, so this is not an isolation hole --
it is a false confirmation, and it makes the endpoint's own success message untrustworthy as a test
oracle.

### 12.8 `AiAgentServiceImpl` keeps a private copy of the tenant-ownership rule, and it differs

`AiAgentServiceImpl.java:100-105` vs `security/TenantOwnership.java:35-41`. The shared class
requires `callerTenantId != null` before comparing; the local copy does not, so a tenant-less
non-platform caller is granted ownership of a platform-owned agent by `Objects.equals(null, null)`.
`TenantOwnership`'s own header comment (`:6-8`) says it exists because *"every service had grown
its own private copy of it, and the copies had begun to disagree about the rows that carry no
tenant at all"*. This is one of those copies, still disagreeing, in the service that holds
decryptable API keys.

`.ai/discovery/database.md:678-680` records the same pattern in `SettingServiceImpl`.

### 12.9 `instructions` and `targetFileTypes` are mandatory and read by nothing in either app

Both are `nullable = false` (`model/pojo/AiAgent.java:80`, `:83`) and both are required by
`validateAgent` (`:544-549`). Neither is consumed:

- File chat builds its own system prompt and never reads the agent's `instructions`
  (`FileChatServiceImpl.java:264-289` -- the prompt is assembled from the filename, the file text
  and the history).
- The job assistant does the same (`JobAssistantServiceImpl.java:103`).
- File chat filters agents on `status` and `apiKeyConfigured` only, never on `targetFileTypes`
  (`features/objects/chat/file-chat.ts:216-218`; old app identically at
  `object-browser.component.ts:957-959`).
- The old app's `agentsForFile` helper, which *would* have used `targetFileTypes`, is exported and
  called from nowhere (`_models/ai-agent.model.ts:43-50`; a repo-wide grep finds only its own
  definition).

The one reader is `fetchToolByUuid` (`AiAgentServiceImpl.java:219-221`), whose only UI was the old
app's Copy tool URL button -- which did not cross. So in the new app these two required fields have
no consumer at all.

### 12.10 The transcript's `consoleText()` is dead

Declared and documented at `transcript.ts:84-89` as the clipboard text "matching whichever reading
is on screen"; `copy()` at `:209-212` copies `this.transcript()` instead. No caller in
`transcript.html`. Either the copy should use it or it should go.

### 12.11 The transcript spec tests a copy of the parser

`transcript.spec.ts:3-11` says so outright. `Transcript.segments` is not exported, so the seven
tests cannot fail when the component changes. Already recorded as finding 24 in
`.ai/discovery/risks.md:92`.

### 12.12 The audio controller returns raw exception messages with HTTP 400

`api/AudioTranscriptRestApi.java:40` and `:50` both return `new ResponseDto(ERROR_MESSAGE,
ex.getMessage())`. Already recorded as finding 10 in `.ai/discovery/risks.md:62`, noting that this
is the opposite of the policy `KafkaSecretRestApi` states for itself. In this feature's favour: the
old client's error handler was written specifically to dig that message out
(`audio-transcript-extractor.component.ts:248-255`), and the new one does the same
(`transcript.ts:185`), so the messages are load-bearing for the UI today.

### 12.13 A hand-maintained model catalogue with nothing to keep it honest

`models.ts:36-53` lists 16 models with approximate sizes, and the comment above it says outright
that Ollama publishes no catalogue endpoint this backend proxies. Nothing will tell anyone when a
tag is retired or a size is wrong. Recorded as finding 13 in `.ai/discovery/frontend.md:807-810`.

### 12.14 `document_converter_task.target_folder` is written and never read

`DocumentConverterServiceImpl.java:216` sets it; `getTargetFolder()` has no caller in
`src/main/java`. The new frontend does read it, but only as a fallback when the output key has no
slash (`converter.ts:316`). Recorded at `.ai/discovery/database.md:637-641`.

---

## 13. Missing functionality

What is absent, and what it would take. Sizes are engineering days at the granularity Execution
plans in; the reasoning for each choice is in the synthesis document.

| Missing | Where it was | What it would take |
|---|---|---|
| **Content Cleaner bucket source + PDF extraction** | `content-cleaner.component.ts:97-170`, `_helpers/pdf-text-extractor.ts` | A shared bucket picker on the cleaner, plus PDF text extraction. `pdfjs-dist` is already a dependency of the new app (used by `features/objects/preview/pdf-viewer.ts`), so the extractor is a port, not a new capability. M |
| **Transcript save-back to a bucket** | `audio-transcript-extractor.component.ts:307-441` | `createFolder` + `uploadObject` (both already on `StorageService`), a folder picker, and the `<stem>_<timestamp>` suggestion. M |
| **Transcript reopen of a saved `.txt`** | `audio-transcript-extractor.component.ts:184-221` | Widen the bucket picker's filter to `.txt` and branch `extract()` on it, reading through `previewText`. S -- but only worth doing if save-back lands first, since without it there is nothing to reopen |
| **Converter folder navigation on the bucket source** | `document-converter.component.ts:263-331` | The shared picker from the transcript. S once the picker is shared |
| **Converter save-folder browser** | `document-converter.component.ts:333-406` | The same picker in "folders only" mode. S once shared |
| **Converter inline preview of input and output** | `document-converter.component.ts:221-239`, `:458-477` | Client-side blob/`FileReader` previews for the seven previewable extensions. The saved-task case is already better than the old app's; this is only about the pre-save result. M |
| **Converter task search and byte totals** | `document-converter.component.ts:123-139` | A filter over the loaded rows and two reduces. S |
| **Converter task-list loading and error states** | never existed | Wrap the list in `TableShell`. S |
| **AI agent clone** | `ai-agent.component.ts:199-214` | Open `AgentDialog` with a copy of the row, no id, `" (Copy)"` on the name. S |
| **AI agent Copy tool URL** | `ai-agent.component.ts:304-327` | A row action building `<API_BASE>/aiAgent.json/fetchToolByUuid?uuid=`, plus surfacing `toolUuid` in the list model. S. Needs the decision in synthesis §6 about whether the tool concept survives at all |
| **AI provider list from the lookup** | `ai-agent.component.ts:105-137` | Either a second call to `fetchSubLookupByParentId` from the client, or populating `children` in `appSetting`. S either way; the choice is in synthesis §3.1 |
| **AI agent client validation parity** | `ai-agent.component.ts:248-259` | Two conditional validators in `AgentDialog`, plus the server-side key rule that never existed. S |
| **`xlsx` as a target file type** | `_models/ai-agent.model.ts:4` | One array entry, plus a decision on the six the new app added. XS |
| **Ollama Family column** | `ollama-models.component.html:67-73` | One column; `family` is already on the DTO and already in the stats. XS |
| **Per-tenant awareness of Ollama models** | never existed | A real design decision, not a port. See synthesis §6 |
| **Any test for the converter, the cleaner or the Ollama service** | never existed | Server: a format-matrix test and a save-path test. Client: a `TableShell` state test on the converter. M |
| **Exporting `Transcript.segments` so its spec tests the real thing** | never existed | Export the parser as a pure function and import it in the spec. XS |
