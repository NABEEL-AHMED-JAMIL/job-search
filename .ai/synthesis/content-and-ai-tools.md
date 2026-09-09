# Synthesis -- Content and AI Tools

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

Companion to [../grooming/content-and-ai-tools.md](../grooming/content-and-ai-tools.md), which
carries the evidence for every claim restated here.

> **AI Agent, file chat and RAG were substantially reworked on 2026-09-04** — the Provider
> dropdown, the Model field, agent instructions actually reaching the model, and a new
> OpenSearch-backed RAG pipeline for large files. See
> [../synthesis/ai-agent-rag.md](../synthesis/ai-agent-rag.md) for what changed, what was found
> already built, and what remains open. This document's own findings about those three screens
> below are what the code looked like *before* that pass.

---

## 1. Summary

Five screens crossed to the new app in four different states, and calling the feature "partial"
hides that. **Ollama Models crossed clean and improved** -- nothing to do but restore one column.
**AI Agents crossed with more list chrome and fewer rules**, and one of its two configuration
sources is silently ignored: the provider dropdown reads a `children` field that
`setting.json/appSetting` has never sent, so the `AI_PROVIDER` lookup -- the whole reason that
lookup family was made tenant-extendable -- has no effect on the screen. **Document Converter
crossed with its bucket source crippled**: it lists a bucket's root and hides folders, so a file one
level down is unreachable, in a codebase where the sibling transcript screen carries a comment about
having fixed exactly that. **Audio Transcript crossed better in every respect except that it can no
longer save anything** -- the transcript exists only in the tab that produced it. **Content Cleaner
did not really cross**: 335 lines of paste-or-browse-a-bucket-and-extract-a-PDF became 72 lines of
paste box.

The work divides cleanly into three bands. First, two defects that make features silently wrong
rather than merely smaller -- the provider lookup and the converter's root-only picker. Second, one
shared component that three screens need and one already has: a bucket path picker. Extracting it
turns the converter fix, the cleaner's bucket source and the transcript's save target from three
jobs into one plus three small consumers. Third, the itemised losses, each of which is small once
the picker exists.

Two things want a human decision rather than a plan, and both are in §6: whether the AI agent "tool"
concept (`toolUuid`, `fetchToolByUuid`, `instructions`, `targetFileTypes`) survives at all, and what
to do about Ollama being a shared host that any tenant admin can delete models from.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | `agents.ts:93-96` reads `lookup.children` off `appSetting`; `fillLookupDateDto` never sets it and the DTO is `NON_NULL`, so the list is always the hard-coded `['OpenAI','Anthropic','Ollama']` | The dropdown offers every `AI_PROVIDER` child visible to the tenant, including ones the tenant added | The `AI_PROVIDER` lookup has no effect on the screen that documents itself as reading it; a custom provider on an existing agent renders as a blank select | Client makes the same two calls the old app made: `appSetting` for the parent id, then `fetchSubLookupByParentId` for the children | S | Low |
| 2 | `converter.ts:117-130` lists prefix `''` only and `:95-102` drops every folder row | Any readable file in the bucket is selectable, at any depth | A bucket whose files live under a prefix shows an empty picker; the tool looks broken | Extract the transcript's path picker into `shared/ui` and consume it here | M | Low |
| 3 | `cleaner.ts` is 40 lines: paste, POST, copy. No storage import, no PDF extraction, no comparison | Paste **or** pick a `pdf`/`csv`/`txt`/`json`/`xlsx`/`xml` file from a bucket; see raw beside cleaned with a chars-removed count | The screen is smaller than the one it replaces and drops its only non-trivial capability | Add the shared picker + a ported `extractPdfText` (pdfjs-dist is already a dependency) + a two-pane result | M | Low |
| 4 | `transcript.ts` has no `uploadObject` and no `createFolder`; the transcript lives in one browser tab | A finished transcript can be written into a bucket folder, and a saved `.txt` reopened later | The tool produces something with no way to keep it; closing the tab loses minutes of transcription | Port the old save path (`createFolder` when new, then `uploadObject`) using the shared picker in folder mode; widen the source filter to `.txt` | M | Low |
| 5 | Converter task list branches only on `!tasks().length`; the error callback sets no message (`converter.ts:268`) | Loading, error and empty are three distinguishable states with a retry | A failed load is indistinguishable from an empty result -- the exact problem `TableShell` exists to solve, on one of the few lists that does not use it | Wrap the list in `TableShell` and set an `error` signal | S | Low |
| 6 | `AgentDialog` has no endpoint-required rule and no key-required rule; the server has the first at save time and the second only at *use* time | A custom provider without an endpoint, and a non-Ollama agent without a key, are both refused before the agent is saved | An unusable agent saves with a success toast; the failure surfaces days later on the file chat screen, worded as a provider fault | Conditional validators in the dialog; add the key rule to `validateAgent` server-side | S | Low |
| 7 | `validateAgent` never calls `validateEndpoint`; only `validateAdHoc` does (`AiAgentServiceImpl.java:307-309`) | An endpoint the policy will refuse is refused when it is saved | Same failure mode as #6, on a different field. Not a security hole -- `processAdHoc` is the only network path -- but a misdirected error | Call `validateEndpoint` from `validateAgent` for the providers that dial the request's endpoint | S | **Medium** -- can invalidate agents that exist today |
| 8 | No clone; no Copy tool URL. `toolUuid` and `fetchToolByUuid` appear nowhere in `scheduler1/next/src` | Both restored, or the tool concept explicitly retired | An agent must be retyped to be varied; a working, tested, tenant-checked endpoint has no client | Clone: reopen the dialog with a copy. Tool URL: a row action. Both gated on the §6.1 decision | S | Low |
| 9 | `FILE_TYPES` (`agent-dialog.ts:10`) dropped `xlsx` and added six. An agent carrying `xlsx` keeps it in the payload but has no button for it | Every type an existing agent can carry is visible and removable | A stored value is invisible and unremovable through the UI | Add `xlsx`; render any unknown stored type as an extra removable chip | XS | Low |
| 10 | Agents list has one free-text search; the old screen had provider and status dropdowns and four KPI tiles | Filtering that scales past a handful of agents | Below ~20 agents the search is adequate; above it, "show me the inactive ones" has no answer | Two `<select>` filters in the `TableShell` toolbar. KPI tiles: **not** restored -- see §5 | S | Low |
| 11 | Converter has no task search and no input/output byte totals | Both restored | A long conversion history is unsearchable | A `computed` filter and two `reduce`s | S | Low |
| 12 | Converter has no preview of the just-converted result and no download-the-input | Both sides previewable before the file is saved anywhere | The only way to check a conversion is to download it | Client-side blob/`FileReader` preview for the seven previewable extensions | M | Low |
| 13 | Installed-models table has no Family column; `family` is parsed, carried and used in the stats | The column returns | A parsed field is thrown away in the one view where it is per-row information | One column | XS | Low |
| 14 | `OllamaRestApi` is `TENANT_ADMIN` with no service-level tenancy; any tenant admin deletes any model | A tenant admin cannot silently break another tenant's agents | Cross-tenant blast radius with no warning at any of the four layers | **Decision required** -- see §6.2 | -- | **High** |
| 15 | `instructions` and `targetFileTypes` are `nullable = false` and required by `validateAgent`, and read by nothing in either app | Either they have a consumer or they stop being mandatory | Two mandatory fields users must invent values for, that change no behaviour | **Decision required** -- see §6.1 | -- | Medium |
| 16 | `AiAgentServiceImpl.java:100-105` keeps a private ownership rule that differs from `TenantOwnership` on the tenant-less caller | One rule, in the one class that exists to hold it | The exact drift `TenantOwnership`'s header comment says it was created to stop, in the service holding decryptable API keys | Replace the private method with `TenantOwnership.isOwnedByCaller` | XS | **Medium** -- changes behaviour for a tenant-less caller |
| 17 | `deleteTask` returns SUCCESS for an id that does not exist (`DocumentConverterServiceImpl.java:267-283`) | A nonexistent id is reported as not found | The endpoint's success message is not a usable test oracle | Move the not-found return out of the `isPresent()` branch | XS | Low |
| 18 | `transcript.spec.ts` tests a copy of the parser; `Transcript.segments` is not exported | The spec tests the shipped parser | Seven passing tests that cannot fail when the component changes | Export the parser as a pure function; import it | XS | Low |
| 19 | `consoleText()` is declared, documented and called from nowhere | Copy matches what is on screen, or the method goes | Dead code with a comment asserting a behaviour that does not happen | Wire `copy()` to it, or delete it | XS | Low |
| 20 | No test at any layer for the converter, the cleaner or the Ollama service | The conversion matrix and the save path are pinned | The largest service in the feature (294 lines) has no test | Server: format-matrix + save-path tests. Client: a `TableShell` state test | M | Low |
| 21 | Three segmented controls are bare `div`s of buttons with no `role="tablist"` (`converter.html:10`, `transcript.html:10`, `:121`) | Keyboard-navigable segmented controls | Already logged platform-wide at `.ai/discovery/frontend.md:638-643` | **Out of scope** here -- see §5 | -- | -- |

---

## 3. Solution detail

### 3.1 Row 1 -- the provider list (the one that changes behaviour most for the least work)

**What changes.** `features/ai/agents/agents.ts`, `loadProviders()` only.

Replace the single `appSetting` call with the old app's two-step: fetch `appSetting`, find the entry
whose `lookupType` is `AI_PROVIDER`, take its `lookupId`, then fetch
`setting.json/fetchSubLookupByParentId?parentLookUpId=<id>` and map
`data.lookupDatas[].lookupValue`. Keep the three-provider fallback for the case where the lookup is
genuinely absent, but log it rather than letting it look like success.

**Why this and not the alternative.** The obvious server-side fix is to make `appSetting` populate
`children`, which would make the existing client code correct with no client change and save a round
trip. It was rejected on three grounds:

1. `appSetting` is `@Cacheable` keyed on tenant-or-platform (`SettingServiceImpl.java:207-208`) and
   is called on nearly every screen. Widening its payload to carry every child of every lookup
   family widens a hot, cached response for the benefit of one dropdown.
2. `fetchSubLookupByParentId` is not a naive children-getter. It applies the tenant-owned /
   tenant-extendable visibility rules per child (`:543-560`) -- for `AI_PROVIDER` specifically, a
   tenant sees the platform's rows plus its own and not another tenant's. Reimplementing that
   filtering inside `appSetting`'s loop duplicates the rule in a second place, which is how
   `SettingServiceImpl` already ended up with a private copy of `TenantOwnership`
   (`.ai/discovery/database.md:678-680`).
3. The old app already made these two calls and the pattern is proven against this data.

The cost is one extra request on a screen that already makes two. That is the right trade.

**A second, smaller change in the same file.** When an agent's stored provider is not in the fetched
list, prepend it as an option rather than rendering a blank select. Today an old-app agent on a
custom provider shows an empty control that rewrites the field on first interaction.

### 3.2 Rows 2, 3, 4 -- one shared bucket path picker

**What changes.** A new `shared/ui/bucket-path-picker` (name to be settled in Execution), lifted
from `features/tools/transcript/transcript.ts:92-165` -- the prefix signal, the crumbs computed, the
folders computed, `browse()` with its `browseTicket` stale-response guard, and the template block at
`transcript.html:55-86`.

It needs three inputs: the bucket, a file-extension filter, and a `foldersOnly` mode for save
targets. It emits a selected key (or, in `foldersOnly` mode, a prefix).

Consumers, in order: `Transcript` (replace the inline copy, no behaviour change),
`Converter` source picker (row 2), `Converter` save-folder picker (part of row 4's sibling gap),
`Cleaner` source picker (row 3), `Transcript` save-folder picker (row 4).

**Why extract rather than copy.** There are five call sites. The old app copied this logic five
times -- the converter alone has two near-identical breadcrumb implementations
(`document-converter.component.ts:263-314` and `:365-397`) -- and they had already drifted: the
browse mode filters by extension, the save mode filters to folders, and only one of them clears its
selection on a breadcrumb jump. The `browseTicket` guard exists in exactly one of the six
implementations across both apps. Copying it a third and fourth time guarantees the same divergence
in the new codebase.

**Why not reuse the Object Browser's own listing component.** `features/objects/objects.ts` is
~500 lines carrying infinite scroll, per-folder size stats, upload, delete, rename, share and the
chat panel. Nothing in it is separable as a picker without a refactor larger than the feature work
it would serve. The transcript's picker is 70 lines and already does exactly the job.

**Row 3's PDF extraction specifically.** The old `_helpers/pdf-text-extractor.ts` walks the pdf.js
text layer. `pdfjs-dist` is already a dependency of the new app and already loaded by
`features/objects/preview/pdf-viewer.ts`, so this is a port of ~40 lines, not a new dependency.

The rejected alternative was doing the extraction server-side, reusing
`FileChatExtractionService` -- which already extracts text from bucket objects for the file chat and
would give one extraction implementation instead of two. It was rejected for this round because it
needs a new endpoint (`fileChat.json/prepareContext` returns coverage metadata, not the text) and
because the extraction the cleaner wants is the *browser's* reading of the PDF, which is what the
old screen's users were cleaning. It is the better long-term shape and is recorded here as the
option to revisit if a second consumer appears.

### 3.3 Rows 6 and 7 -- validation, and why the endpoint rule is the risky one

**Row 6 is safe.** Two conditional validators in `agent-dialog.ts`: `apiEndpoint` required when
`provider` is not one of the three built-ins; `apiKey` required when creating and `provider` is not
Ollama. Plus one server rule in `validateAgent` for the key, because today no server path enforces
it at save time and the client is not enforcement. Both mirror rules the old app already had
(`ai-agent.component.ts:248-259`), so no new policy is being invented.

**Row 7 is not safe and should be staged.** Calling `validateEndpoint` from `validateAgent` is three
lines. The risk is that agents already in the database may hold endpoints the policy refuses -- an
internal model server on a private address that the operator never added to
`ai.allowed-endpoint-hosts`. Today such an agent saves and fails at chat time; after the change it
cannot be saved *at all*, so an admin editing an unrelated field on it is blocked with a message
about a field they did not touch.

The recommended sequencing is therefore: (a) survey `ai_agent.api_endpoint` on the target
environments; (b) if any would be refused, add those hosts to `ai.allowed-endpoint-hosts` first --
which is what that property exists for (`AiAgentServiceImpl.java:74-83`); (c) then turn the
validation on. Doing it in the other order turns a deferred error into an immediate outage on the
edit screen.

The alternative -- warn in the UI rather than refuse on the server -- was rejected because a
client-only warning is exactly the class of rule §7 of the grooming document flags as a finding, and
because the check is a pure function already written and already tested
(`AiAgentServiceImplTenantIsolationTest.java:125-198`).

### 3.4 Row 5 -- `TableShell` on the converter's task list

Three-line change in the template plus an `error` signal in `converter.ts`. The reason it is called
out separately rather than folded into "polish": it is the difference between a 500 on
`fetchAllTasks` reading as "you have never converted anything" and reading as "this failed, retry".
The new app has this right on 19 lists; the converter is one of the few where it is wrong, so this
is a consistency fix as much as a bug fix.

The same two-line treatment applies to the two silent bucket-listing failures
(`converter.ts:128`, `transcript.ts:158-161`) and should ride along with the shared picker in §3.2 --
the picker should own its own error state so no consumer can forget it.

### 3.5 Row 8 -- clone and Copy tool URL

**Clone** is unconditional and small: open `AgentDialog` with `{...agent, aiAgentId: null,
agentName: agent.agentName + ' (Copy)'}`. The dialog's `isEdit()` computed already keys off
`data.agent`, so it needs a third mode or -- simpler -- clone passes the row under a different key
so `isEdit()` stays false and the dialog POSTs. That is the shape the old app used
(`ai-agent.component.ts:199-214`).

**Copy tool URL** is conditional on §6.1. If the tool concept stays, the row action is ten lines:
surface `toolUuid` on the list model (the server already returns it,
`AiAgentServiceImpl.java:581`), build `${API_BASE}/aiAgent.json/fetchToolByUuid?uuid=`, and use the
existing `copyText` helper. Note the endpoint is `TENANT_USER`, so the action should **not** be
gated on `canManageAgents` -- the old app deliberately put this button outside the admin `*ngIf`
(`ai-agent.component.html:120-122`), and matching the endpoint is the correct reading.

### 3.6 Row 9 -- the file-type list

Add `xlsx` back. The six the new app added (`docx`, `md`, `png`, `jpg`, `mp3`, `m4a`) should stay --
they match what the file chat can actually extract and what the transcript handles, so the new list
is more honest than the old one, minus the one drop.

Separately, render any stored type not in the canonical list as an extra chip that can be
deselected. Without that, a value written by the old app can be neither seen nor removed, which is
how `xlsx` became invisible rather than lost.

Note this whole row is moot if §6.1 decides `targetFileTypes` stops being mandatory.

### 3.7 Row 16 -- the duplicated ownership rule

Replace `AiAgentServiceImpl`'s private `isOwnedByCaller` with
`TenantOwnership.isOwnedByCaller(aiAgent.getTenantId())`, as `DocumentConverterServiceImpl` already
does (`:77-79`).

Risk is medium and worth stating precisely: the two rules differ only for a **non-platform-admin
caller carrying a null `tenantId`**, acting on an agent with a null `tenantId`. Today that caller is
granted ownership; after the change they are refused. Such a caller should not exist -- a
`TENANT_ADMIN` row with no tenant is a data fault -- but "should not exist" is why it needs checking
against the target environments before the change lands, not why it can be skipped.

The alternative, leaving it alone because it is unreachable, was rejected: this is the service that
decrypts API keys, `TenantOwnership` exists specifically because copies of this rule had begun to
disagree, and the fix is one line.

### 3.8 Row 20 -- the tests worth writing

The converter is the largest service in the feature and has none. Two server tests earn their
keep:

- **The format matrix.** `familyOfInput` returns the *first* family containing the extension, and
  the families overlap (`pdf` is an input to DRAWING; `txt` to TEXT; `csv` to SPREADSHEET). The
  order of `LinkedHashMap` insertion at `DocumentConverterFormatRegistry.java:47-70` is therefore
  load-bearing and nothing pins it. A reorder would silently change what `report.pdf` converts to.
- **The save path.** `convert(save=true)` writes a task row with `"pending"` keys, uploads twice,
  then overwrites the keys (`DocumentConverterServiceImpl.java:218-233`). If the second upload
  throws, the row survives with `outputStorageKey = "pending"` and the task list renders a row whose
  View button points nowhere. Worth pinning what is meant to happen there before anyone changes it.

On the client, one test that the converter's task list renders three distinguishable states, which
is the regression #5 fixes.

---

## 4. Ordering

**Stage 0 -- unblockers.** Nothing depends on these and everything is easier after them.

1. Row 1, the provider lookup. Independent, small, and the largest behaviour change per line in the
   feature. Do it first so the AI Agents work in stage 2 is done against a correct dropdown.
2. Row 18, export the transcript parser, and row 19, resolve `consoleText()`. Both XS, both in the
   file stage 1 is about to move code out of.

**Stage 1 -- the shared picker.** Row 2's extraction, with `Transcript` as the first consumer
(a pure refactor with no behaviour change, so a regression there is obvious). Unblocks rows 2, 3, 4
and the converter's save-folder browser. This is the critical path: three of the four "did not
cross" items in the feature are waiting on it.

**Stage 2 -- consumers and itemised losses**, all parallel once stage 1 lands:

- Converter: bucket navigation (row 2), save-folder browser, `TableShell` (row 5), search and
  totals (row 11), result preview (row 12).
- Cleaner: bucket source and PDF extraction (row 3), two-pane result.
- Transcript: save-back (row 4), then `.txt` reopen -- in that order, since reopening needs
  something to have been saved.
- Agents: validation parity (row 6), clone and tool URL (row 8), file types (row 9), filters
  (row 10).
- Models: the Family column (row 13). XS, independent of everything.

**Stage 3 -- backend hygiene**, each independently shippable and each needing an environment check
first:

- Row 7, the endpoint rule, after the `ai.allowed-endpoint-hosts` survey in §3.3.
- Row 16, the ownership rule, after the null-tenant survey in §3.7.
- Row 17, the `deleteTask` false success. No survey needed.

**Stage 4 -- tests** (row 20). Deliberately last for the client test, which should be written
against the fixed converter rather than the broken one; the two server tests can be written at any
point and would ideally precede stage 2's converter work.

**Blocked on a human**: rows 14 and 15 (§6). Row 15 blocks row 9's usefulness and part of row 8, so
it wants an answer before stage 2's agent work, not after.

---

## 5. Out of scope

**The KPI tile rows** on AI Agents (four tiles) and Ollama Models (three). The models screen already
replaced its three with four plus a per-model disk-share bar, which is strictly more information.
The agents screen dropped its four, and the two that carried real signal -- active count and
keys-configured count -- are now per-row: `TableShell` prints the shown/total counts and `keyState`
prints a three-state key pill on every row. Restoring the tiles would re-add a summary of data that
is already on screen. Not a loss; excluded from the gap table on the README's rule that a difference
is only a gap if something was lost.

**The `role="tablist"` work** on the three segmented controls. It is real and it is logged at
`.ai/discovery/frontend.md:638-643`, but it is one instance of a platform-wide pattern that also
covers the job-logs view switch and the query-engine tabs. Fixing three of five leaves the
inconsistency and does the work twice. It belongs to a single accessibility pass across the app.

**The `document_converter_task.target_folder` write-only column.** Recorded at
`.ai/discovery/database.md:637-641`. The new frontend does read it as a fallback
(`converter.ts:316`), so it is not entirely dead, and dropping a column is a migration on a table
with no creation changeset. Not worth touching for tidiness.

**The audio worker's raw-exception responses** (`api/AudioTranscriptRestApi.java:40`, `:50`,
risks.md finding 10). Both clients are written to dig the message out of `error.error.message` and
both display it usefully; changing the controller to a generic message would make the transcript
screen worse before something better replaces it. This belongs with a product-wide error-envelope
decision, not to this feature.

**The hand-maintained Ollama catalogue** going stale (grooming §12.13). There is no upstream
endpoint to replace it with; the alternative is deleting the catalogue, which is worse than a list
that drifts. Accepted as-is.

**Anything about the transcription worker itself.** `audio.extract.service.base.url` points at a
service that Discovery marks "not verified" and that appears in no compose file in this repo
(`.ai/discovery/backend.md:924`). Whatever it is, it is not this feature's to change.

**The `ddl-auto=validate` / Liquibase gap** that means neither of this feature's two tables has a
creation path on a fresh stage or prod database
(`.ai/discovery/database.md:546-556`). Platform-wide, owned elsewhere. Noted here only so that
nobody plans a migration in this feature assuming they can create a table.

---

## 6. Open questions

### 6.1 Does the AI agent "tool" concept survive?

Four things stand or fall together: the `tool_uuid` column, `aiAgent.json/fetchToolByUuid`, the
mandatory `instructions` field and the mandatory `targetFileTypes` field. In the new app **none of
them has a consumer**. File chat and the job assistant each build their own system prompt and ignore
the agent's `instructions` (`FileChatServiceImpl.java:264-289`,
`JobAssistantServiceImpl.java:103`); neither filters on `targetFileTypes`
(`features/objects/chat/file-chat.ts:216-218`); and the only UI that ever resolved a tool uuid was
the old app's Copy tool URL button, which did not cross.

**Option A -- restore the tool concept.** Bring back Copy tool URL; keep both fields mandatory. The
endpoint already exists, is tenant-checked, refuses inactive agents, and has passing isolation tests
(`AiAgentServiceImplTenantIsolationTest.java:98-123`). Cost: the row action in §3.5, ~10 lines.

**Option B -- retire it.** Drop the row action idea, make `instructions` and `targetFileTypes`
optional, and mark `fetchToolByUuid` for deletion alongside the other four endpoints Discovery
already flags as dead in both clients (`.ai/discovery/features.md:75-77`). Cost: a nullable
migration on two `not null` columns, plus removing the validator rules.

**Recommendation: Option A.** Three reasons. The endpoint is *not* dead in the way the other four
are -- it had a caller in the old app and lost it in the rewrite, which is a migration gap rather
than an unused API. The old app's own tooltip says what it was for -- *"paste into a Source Task's
XML to call this agent from an external consumer"* (`ai-agent.component.html:120`) -- which is an
integration path, and an integration path is exactly the kind of thing that has users you cannot see
from inside the app. And the asymmetry of the two options is stark: A is ten lines of client code, B
is a migration on two `not null` columns plus an endpoint deletion, on a guess that nobody outside
the app is calling it. If a later phase confirms nothing external uses it, B stays available at the
same cost; the reverse is not true.

The one thing Option A does **not** settle is that `instructions` remains mandatory while the two
in-app consumers ignore it. That is worth a sentence of UI copy on the field -- something naming
where the prompt is actually used -- rather than a code change.

### 6.2 What is done about Ollama being one host with no tenant boundary?

`OllamaRestApi` is class-level `TENANT_ADMIN` with no overrides; `OllamaServiceImpl` has no tenant
parameter, no ownership check and no entity. Tenant A's admin can delete a model tenant B's agents
name, and B's file chat then fails with a provider error naming a model that no longer exists.
Nothing at any of the four layers says a word about it. Any tenant admin can also pull a 9 GB model
onto shared disk.

**Option A -- do nothing, document it.** The delete confirmation already warns that agents will
break; widen the wording to say it affects every workspace on this host. Zero code beyond a string.

**Option B -- make the delete dependency-aware.** Before deleting, query `ai_agent` across all
tenants for `model = <name>` and refuse, or warn with a count. There is precedent in this codebase:
`storageConnection.json/deleteConnection` already refuses when a `KafkaConnectionProfile` depends on
the connection (`.ai/discovery/features.md:42`, row 9). Cost: one repository method, one check, and
a decision about whether the count of *other tenants'* agents may be shown to a tenant admin -- it
is a small cross-tenant disclosure, so the message should be a count and never a name.

**Option C -- raise the whole controller to `PLATFORM_ADMIN`.** Models become platform
infrastructure that tenants consume but do not manage. One annotation, one route-guard change, one
nav flag.

**Recommendation: C now, B later if C is refused.** Option C matches what the resource actually is.
Every other genuinely shared, host-level thing in this product is platform-scoped; a model directory
on one host is not tenant data by any reading, and the current annotation lets a tenant admin take a
destructive action whose blast radius crosses tenants -- which no other `TENANT_ADMIN` endpoint in
the codebase does. The cost is honest and small: a tenant admin who wants a new model asks a
platform admin, the same way they would for anything else on the host.

It is a **role reduction on a shipped screen**, so it needs the product owner rather than an
engineer, and it needs a check on who is actually using `/ai/models` today. If that check says
tenant admins depend on pulling their own models, Option B is the fallback -- it keeps the
capability and removes the silent part of the failure, which is the half that actually hurts. Option
A alone is not enough: a warning that names no consequence anyone can act on is not a control.

### 6.3 Should the Content Cleaner's bucket source come back at all, or is the Object Browser the right home for it?

Row 3 assumes the old shape: a picker inside the cleaner. The alternative is that "clean the text in
this file" becomes a *file action* in the Object Browser -- where the file already is, next to
preview, download and chat -- and the cleaner keeps its paste box for text that has no file.

**Recommendation: restore it in the cleaner, as row 3 describes.** Two reasons. The Object Browser
is already the largest screen in the new app and its row-action set is the thing most likely to
sprawl; adding a fourth verb there to avoid adding a picker here trades a contained change for an
uncontained one. And the shared picker from §3.2 has to exist anyway for the converter and the
transcript, so the cleaner's version is the cheapest of the three consumers, not an extra cost.

Worth revisiting only if a second file-verb appears -- at two, "send this file to a tool" becomes a
pattern worth building once in the browser rather than a picker built three times in the tools.
