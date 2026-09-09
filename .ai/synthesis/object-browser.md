# Synthesis -- Object Browser

Companion to `.ai/grooming/object-browser.md`. All paths relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

The Object Browser migrated well: the new screen is smaller, safer and faster than the 1,904-line
component it replaced, and it fixed two real defects on the way -- downloads no longer go through
the preview endpoint (which made non-previewable files undownloadable in the old app), and model
output is no longer rendered through a sanitizer bypass. What it needs now is not a rebuild but a
repair list. Two defects are serious enough to be worth doing before anything cosmetic: the chat
panel is a single reused component instance whose inputs change underneath it, so opening a chat on
a second file binds the first file's transcript to the second file's key and writes it into that
file's storage slot; and the chat's conversation history is sent under a JSON key the server does
not read, so every question is answered as if it were the first. After those, the work is a short
list of things the rewrite quietly dropped -- folders can no longer be selected, bulk-deleted or
emailed, upload takes one file at a time, the per-folder size column and the sub-folder chart are
gone, and the insight tiles now describe only the rows currently loaded while looking like they
describe the folder. Underneath all of it, the security model is sound and well tested on the
server: every guard lives in `StorageBrowserServiceImpl`, and the Hibernate filter contributes
nothing here at all -- which is fine, but must be understood before anyone refactors that class.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | `<app-file-chat>` is one instance whose `[bucket]`/`[fileKey]` inputs mutate; `ngOnInit` never re-runs, the transcript is not cleared, and the persist effect writes the old transcript into the new file's `sessionStorage` key (`objects.html:280-283`, `objects.ts:374-376`, `file-chat.ts:75-77`, `:100-103`, `:204-209`) | Opening a chat on a different file (or changing bucket) starts a chat about *that* file | Stale transcript shown and sent as history under a different file's name; wrong coverage notice; cross-file leakage into session storage | Key the `@if` block so Angular destroys and recreates the panel, and confirm before discarding a non-empty transcript | S | **High** -- correctness and a data-leak shape |
| 2 | History is posted as `{role, content}` (`file-chat.ts:258`); `FileChatHistoryItemDto` reads `text` and ignores unknown keys (`FileChatHistoryItemDto.java:10`, `:14-15`); `buildInstructions` skips null-text turns (`FileChatServiceImpl:349-352`) | The model sees the recent turns | File chat has no memory at all | Send `text`; slice before pushing the new message; exclude `error` turns | S | Low -- one-line change, but invisible until tested |
| 3 | Client previews `tsv`, `log`, `ndjson`, `wav`, `webm` (`preview-dialog.ts:22`, `:127-128`); server refuses them outside a `.gz` (`ContentTypeUtil.java:74-76`, `:113-114`) | Anything the dialog offers to render, the server serves | A `.log` opens into an error panel | Widen the server list to match, and have the client read `ObjectMetadataDto.previewable` instead of re-deriving | S / M | Medium -- touches a security-adjacent allow-list |
| 4 | Folders have no checkbox (`objects.html:195-199`) and no Email entry (`:237-239`) | A folder can be selected, bulk-deleted and emailed, as in the old app | Deleting ten folders takes ten confirmations; a working server capability (folder→ZIP email) has no caller | Render the checkbox for folders; split `removeSelected` by kind; drop the Email condition | S | Low |
| 5 | `onUpload` takes `files[0]` (`objects.ts:340`), no `multiple` (`objects.html:102`), no busy state | A whole selection uploads, with progress | Silent data loss -- four of five files simply do not arrive | Loop the `FileList` sequentially with a busy signal and a failure summary | S | Low |
| 6 | `remove()` leaves the deleted key in `selected()` (`objects.ts:285-311`); filters survive navigation (`:195-202`, `:237-255`); the counts line ignores filters (`:85-92`); Download uses `filtered()` while Delete/Email use `selected()` (`:464` vs `:314`, `:439`) | Selection and filter state track the rows on screen | Bulk bar counts ghosts; a filter set in one folder silently hides rows in the next; two buttons act on different sets | Prune on delete, reset filters on navigation, compute counts from `filtered()`, pick one set for all three bulk actions | S | Low |
| 7 | No per-folder size/contents column and no Sub-folder Sizes chart; insights are computed from loaded rows (`objects.ts:106-146`) while looking like folder totals | Insights describe what they claim to describe | A folder of 4,000 files shows charts of the first 100 and says nothing about it | **Label the tiles honestly first**; restore the per-folder pass behind the existing `isSlowProvider()` guard only if it earns its cost | S then M | Medium -- the fan-out is what made the old screen slow on FTP |
| 8 | Two byte formatters live on the same screen (`objects.ts:151` and `:478-486`, used at `objects.html:163` vs `:125`/`:218`) | One | The same file reads `15.0 KB` in a chart and `15 KB` in the table | Delete `formatBytes`, use `formatSize` | S | None |
| 9 | Chat `prepare()` runs once (`file-chat.ts:211-226`); switching agent does not re-run it; an empty picker value becomes `0` | The coverage notice matches the chosen provider | A truncation warning that is wrong after switching agents | Re-run `prepare()` on `agentId` change; guard `0` alongside `null` | S | Low |
| 10 | Bulk download fires every request simultaneously (`objects.ts:468`); the old app staggered 350 ms (`object-browser.component.ts:53`) | Twenty selected files produce twenty saves | Browsers throttle or drop concurrent programmatic downloads | Restore the stagger | S | Low |
| 11 | No preview for `doc`/`docx` (`preview-dialog.ts:121-130`); no rendered markdown (`preview-dialog.html:121-131` has no `markdown` case) | Both render, as they did in the old app | Two file types the old app showed now say "no inline preview" | Markdown: reuse `shared/ui/markdown.ts`. Word: route the blob through the converter into `PdfViewer` | S / M | Low |
| 12 | Copy current path and the "search covers loaded rows only" hint are gone (`object-browser.component.ts:313-336`, `.html:223-226`) | Both present | Small, real losses in a diagnostic screen | Two small template additions | S | None |
| 13 | `objectMetadata()` and `previewUrl()` have no callers in `scheduler1/next/src` (`storage.service.ts:43-47`, `:97-99`) | No dead code, especially not an unauthenticated URL builder | `previewUrl` is a 401 waiting for a caller | Delete `previewUrl`; keep `objectMetadata` only if #3 uses it | S | None |
| 14 | No component test for `Objects`, `PreviewDialog`, `FileChat` or `StorageService`; the only specs are the route guard and the fence grammar (`.ai/discovery/frontend.md:661`, `:677-678`) | The behaviours above are pinned | Every fix here is unverifiable and every one of them can regress silently | Add specs alongside each fix, starting with #1 and #2 | M | Low, high value |
| 15 | Security rests entirely on `StorageBrowserServiceImpl`; the Hibernate filter is never enabled on this path and would be permissive on `tenant_id IS NULL` anyway (`StorageConnection.java:44`, `TenantFilterHelper.java:28-32`, `LookupData.java` has no filter) | Understood and documented, not "fixed" | A refactor that moves bucket resolution out of that class removes the only guard | No code change. A comment at the top of `StorageBrowserServiceImpl` naming it as the sole guard, and a note in the execution brief | S | **High if ignored**, none if respected |

---

## 3. Solution detail

### Row 1 -- Rebind the chat panel instead of mutating it

**Change.** In `scheduler1/next/src/app/features/objects/objects.html:280-283`, key the block on the
file so a different file produces a different component instance:

```html
@if (chatFile(); as file) {
  @for (bound of [file.key]; track bound) {
    <app-file-chat [bucket]="bucket()" [fileKey]="file.key" … />
  }
}
```

or, more legibly, move the panel behind a `@switch`/`ng-container` keyed on
`bucket() + ':' + file.key`. In `objects.ts:374-376`, `openChat` gains the confirmation the old app
had: when a chat is already open on a *different* file and its transcript is non-empty, ask before
replacing it (`confirmWith` is already imported at `:9`). `onBucketChange` (`:195-202`) clears
`chatFile` for the same reason.

**Why this rather than the alternative.** The obvious alternative is to keep the single instance and
have `FileChat` react to its own input changes -- an `effect` on `fileKey()` that clears
`messages()`, re-runs `restoreHistory()` and re-runs `prepare()`. I rejected it. That path has to
get the ordering exactly right against the `persist` effect, which itself reads `fileKey()`
(`file-chat.ts:75-77`, `:100-103`): the persist effect and the reset effect would both be triggered
by the same input change, in an order Angular does not promise, and one of the two possible orders
writes the old transcript into the new key -- which is the bug we are fixing. `close()` already has
a comment about exactly this hazard (`file-chat.ts:145-147`: "stop the effect re-saving on the way
out, then clear, then close"). A destroy-and-recreate has no ordering to get wrong: the old
instance's effects are torn down with it, and the new instance's `ngOnInit` runs on a clean slate.
The cost is losing an in-flight request on the old file, which is the correct outcome anyway.

**Also fix here:** `prepare()` should be called when the panel is created regardless of whether the
agent list resolves, which it already is (`file-chat.ts:224`), and `endSession` should fire for the
file being abandoned, not just on an explicit close.

### Row 2 -- Send the field the server reads

**Change.** `scheduler1/next/src/app/features/objects/chat/file-chat.ts:253-258` becomes: build the
history from the messages *before* pushing the new user turn, filter to `user`/`assistant`, take the
last eight, and map to `{ role, text }`.

**Why this rather than the alternative.** The alternative is to change the server -- add a `content`
alias to `FileChatHistoryItemDto` with `@JsonAlias`. I rejected it because the DTO is the contract
and `text` is the name the field has had since the feature was written; the old frontend sends
`text` (`object-browser.component.ts:1022`) and the job assistant reaches the same service. Adding
an alias makes two spellings correct forever and leaves the next client free to pick either. The
frontend is the side that is wrong, so the frontend is the side that changes.

**Test to add with it:** a spec that asserts the posted body's history items carry `text`, that the
current message is not duplicated into history, and that an `error` bubble is excluded. This is the
one behaviour that is completely invisible in the UI -- the chat *looks* like it works.

### Row 3 -- Make the two preview allow-lists agree, from the server side

**Change.** Add `tsv`, `log`, `ndjson`, `wav`, `webm` to
`process/src/main/java/process/util/ContentTypeUtil.java:74-76` (and content types for `log`,
`ndjson`, `wav`, `webm` in `EXTENSION_CONTENT_TYPES`). Then have `PreviewDialog` stop re-deriving
previewability at all: call `objectMetadata` -- which already returns a computed `previewable`
boolean (`ObjectMetadataDto.java:19`, populated by every adapter) -- and use it to choose between a
renderer and the "no inline preview" panel, keeping the extension only to pick *which* renderer.

**Why this rather than the alternative.** The alternative is to shrink the client list to match the
server. That fixes the error but leaves a `.log` file -- the single most common thing an operator
wants to read in a bucket while diagnosing a pipeline -- unreadable in the browser, which is a worse
product. It also leaves the underlying fault in place: two lists in two languages that must be kept
in step by hand, which is exactly how this drifted. The server already publishes the answer; the
client should ask instead of guessing. Note this is a security-adjacent list --
`isPreviewable` is what keeps `previewObject` from being a general-purpose read channel with an
`inline` disposition -- so the additions must all be text or media types that are safe to serve
inline, and `html`/`svg`/`xhtml` must stay off it. `svg` is already on the previewable list
(`:76`) and is served as `image/svg+xml`; that predates this work and is called out in row 3's risk
rather than changed here.

### Row 4 -- Give folders back their checkbox and their Email entry

**Change.** Remove the `@if (!entry.folder)` around the row checkbox
(`objects.html:195-199`) and around the Email menu item (`:237-239`). `allSelected` and
`toggleSelectAll` (`objects.ts:153-156`, `:265-268`) stop filtering to files. `removeSelected`
(`:313-336`) splits the selection: `deleteObjects` for the file keys in one call, then one
`deleteFolder` per folder key, exactly as `confirmDelete` did
(`object-browser.component.ts:1660-1701`), and the confirmation body names both counts.
`downloadSelected` keeps skipping folders and keeps saying so.

**Why this rather than the alternative.** The alternative is to leave folders unselectable and add a
"Delete folder" batch elsewhere. Rejected: the old app proved the mixed selection works, the server
supports every leg of it, and a checkbox that is present on some rows and absent on others is a
worse affordance than one that is always there. The one thing worth adding that the old app did not
have is a distinct confirmation when the selection contains a folder -- a recursive delete deserves
different words from "3 files will be deleted".

### Row 5 -- Upload the whole selection

**Change.** `objects.html:102` gains `multiple`; `objects.ts:338-357` loops the `FileList`
sequentially (not in parallel -- an FTP connection is one at a time, and the old app's sequential
`uploadNext` recursion at `object-browser.component.ts:1852-1877` was written for exactly that),
sets an `uploading` signal that disables the control and labels it, and reports failures as a count
rather than one toast per file.

**Why sequential rather than parallel.** `FtpObjectStorageServiceImpl` opens a connection per
request; five parallel uploads to an FTP mirror is five logins and, on servers with a connection
cap, four failures. The object stores would tolerate parallelism, but the screen does not know which
it is talking to at that point beyond `isSlowProvider()`, and the sequential version is simpler and
correct everywhere. If throughput matters later, parallelise only when `!isSlowProvider()`.

### Row 6 -- Make selection and filters follow the rows

**Change.** All in `objects.ts`: `remove()` prunes the key from `selected()` on success;
`onBucketChange`, `openFolder` and `goToCrumb` call `clearFilters()`; `counts()` reads `filtered()`;
`removeSelected` and `share()` intersect `selected()` with `filtered()` so all three bulk actions
act on the rows the user can see.

**Why intersect rather than widen Download.** The other direction -- have Download act on the whole
`selected()` set including hidden rows -- is defensible and is what Delete does today. I rejected it
because a destructive action that reaches rows the user cannot see is the worse of the two failure
modes. Everything the bulk bar does should be about what is on screen; if a user wants the hidden
rows they can clear the filter, and the count in the bar tells them how many there are.

### Row 7 -- Tell the truth about the insights before restoring the fan-out

**Change, phase one (small).** Retitle or subtitle the four tiles so they say what they measure:
"of the N entries loaded". `objects.ts:106-146` already computes from `objects()`, so this is
copy only. Add the same note the old app had when a listing is capped.

**Change, phase two (medium, only if wanted).** Restore the per-folder `listObjects(folderKey, …,
1000)` fan-out that produced the Size column and the Sub-folder Sizes chart
(`object-browser.component.ts:585-621`), guarded by the `isSlowProvider()` computed that already
exists (`objects.ts:60`) so FTP/FTPS does not pay for it until the user opens Insights.

**Why phase one first, and why not simply restore everything.** The old implementation is the reason
the old screen was slow: a directory with fifteen subfolders became sixteen round trips, measured at
14 s against a real FTP mirror (the comment at `object-browser.component.ts:342-358` records this).
The new screen is fast because it does none of that. Restoring the fan-out buys one column and one
chart at that price. The honest labelling costs nothing and removes the actual harm -- a chart that
looks like it describes a folder and describes a page. Do that first, then decide whether anyone
misses the column enough to pay for it. I would guess not for the chart and yes for the column, but
that is a product call, not a code one (see Open questions).

### Row 8 -- One formatter

**Change.** Delete `formatBytes` (`objects.ts:478-486`) and replace its three template uses
(`objects.html:125`, `:218`, and the chart already uses the shared one at `:163`) with `humanSize`.

**Why not the reverse.** `formatBytes` is arguably the nicer output (`15 KB` rather than `15.0 KB`).
But `formatSize` is the shared helper five other screens already use, and its own header comment
(`shared/ui/format-size.ts:1-8`) records that it was extracted precisely to end this drift. If the
rounding is wrong, change it in the shared helper for everyone; do not keep a private copy.

### Row 9 -- Recompute coverage when the agent changes

**Change.** `file-chat.ts`: an `effect` on `agentId()` re-runs `prepare()` (cheap -- the extraction
is cached in Redis for 7 days under `fileChatExtract`, so only the limit arithmetic re-runs); the
picker's change handler maps an empty value to `null` rather than `0`; `send()` guards
`agentId() == null || agentId() === 0`.

**Why an effect rather than a handler on the select.** `agentId` is also set programmatically when
the agent list resolves (`:219`), and that is the first call that should trigger `prepare()`. One
effect covers both entry points; a change handler covers only the user's.

### Row 10 -- Restore the download stagger

**Change.** `objects.ts:463-476` schedules each `download()` at `index * 350` ms, as
`object-browser.component.ts:757-766` did. Keep the single-summary error toast, which is better than
what the old app did.

### Row 11 -- Markdown and Word previews

**Markdown.** Add `@case ('markdown')` to `preview-dialog.html` rendering `<app-markdown
[source]="text()" />`, with the existing Edit path untouched so a user can still edit the source.
This is strictly better than the old app, which rendered markdown through `marked` into
`[innerHTML]` -- `shared/ui/markdown.ts:14-20` cannot inject markup at all.

**Word.** `preview-dialog.ts` gains a `doc`/`docx` branch that fetches the blob, posts it to
`documentConverter.json/convert` with `pdf`, and feeds the resulting bytes to the existing
`PdfViewer`, mirroring `loadDocPreview` (`object-browser.component.ts:1476-1508`).

**Why keep them separate.** Markdown is a template case and half an hour. Word drags in the
converter dependency, a second failure mode ("could not convert this file for preview") and a
LibreOffice round trip. They should not be one change, and if only one gets done it should be
markdown.

### Row 15 -- Write down that layer 3 is the only layer

**Change.** No behaviour. A comment at the head of `StorageBrowserServiceImpl` stating that this
class is the sole enforcement point for bucket and key authorisation: the controller's
`@PreAuthorize` is a floor that admits all three roles through the hierarchy
(`MethodSecurityConfig.java:29`), the Hibernate `tenantFilter` is never enabled on this path (no
caller of `TenantFilterHelper.enableIfNeeded` here) and would admit `tenant_id IS NULL` rows anyway
(`StorageConnection.java:44`), and `LookupData` declares no filter at all so the legacy
`BUCKET_LIST` half is narrowed only by `belongsToCaller` at `:121`.

**Why a comment and not a mechanism.** The temptation is to "fix" the asymmetry by enabling the
filter in this class. It would do nothing useful: the filter narrows `storage_connection` rows, and
the thing being authorised is a *bucket*, which is not a row -- the platform buckets ship as a
property and a lookup entry, with no connection row at all (the comment at `:441-451` explains
this). Adding the filter would give a false sense that the ORM is helping while every real decision
stayed in the same eight methods. The honest move is to name the class as the guard and keep the
18-test unit suite and the 20-test E2E suite pointed at it.

---

## 4. Ordering

1. **Rows 1 and 2 first** (chat rebind, chat history). They are the only two defects that make the
   feature give wrong answers rather than merely look wrong, and row 1 has a data-leak shape --
   one file's transcript written under another's key. Row 1 unblocks nothing else, but nothing else
   should ship before it.
2. **Row 14's first tests, alongside 1 and 2.** Both fixes are invisible in the UI when they work
   and invisible when they break; without a spec each, the next refactor undoes them silently.
3. **Row 15 next**, because it is a comment and because every subsequent change to
   `StorageBrowserServiceImpl` (row 3 touches its neighbourhood) should be made by someone who has
   read it.
4. **Row 3** (preview allow-lists). Touches the server, so it wants its own review pass. It also
   settles whether `objectMetadata()` survives, which row 13 depends on.
5. **Rows 4, 5, 6** together -- the dropped table behaviours. They share `objects.ts`'s selection
   and listing code and are cheaper as one change than three. Row 4 needs row 6's selection pruning
   to be correct, so do 6 first within the batch.
6. **Rows 8, 10, 12, 13** -- the small tidy-ups. Any order, and they can ride along with 4-6.
7. **Row 7 phase one** (honest labels), any time; **phase two** (the fan-out) last, and only after
   the Open question below is answered.
8. **Rows 9 and 11** last. Row 11's Word half is the single most droppable item on this list.

Nothing here blocks another feature. `storage-connections` blocks *this* one -- there is nothing to
test against without a connection -- and `content-and-ai-tools` must have at least one Active,
usable agent before rows 1, 2 or 9 can be exercised at all.

---

## 5. Out of scope

- **Rebuilding the screen.** The migration is done and the new implementation is better. Everything
  above is a repair.
- **Server-side search** (grooming §13, #12). The client-side filter over loaded rows is the
  behaviour both apps have always had; the fix for the confusion it causes is the one-line hint in
  row 12, not a new query parameter and five provider implementations.
- **Move, copy, and folder-download-as-ZIP** (grooming §13, #14, #15). Neither app has ever had
  them, no user has asked in the evidence available, and each needs new service methods with
  per-provider semantics. Note only that the ZIP machinery already exists behind email
  (`FileShareServiceImpl:188-207`) if this is wanted later.
- **Restructuring the four-layer authorisation.** It works, it is tested by 18 unit tests and 20
  E2E tests, and the asymmetry is documented rather than changed (row 15).
- **The `fileChatExtract` cache key.** `FileChatExtractionServiceImpl:94` keys on
  `bucket:key:etag` with no caller identity, unlike `getObjectMetadataCached`
  (`StorageBrowserServiceImpl:152-159`) which deliberately includes the caller. Every caller passes
  `validateBucketAccess` first, so I could not construct a case where this is exploitable, and I am
  not going to change a cache key on a hunch. Recorded here so the next person sees it was
  considered and not verified either way.
- **The old app.** Nothing in `scheduler1/src/app/_component/object-browser/` is being changed. Its
  two defects (grooming §12.7, §12.8) are recorded because they are evidence of what the rewrite
  fixed, not as work.
- **`svg` on the previewable list.** It predates this work and is served `inline` as
  `image/svg+xml` (`ContentTypeUtil.java:32`, `:76`). Row 3 does not add to that list's risk and
  does not remove it either; if it should come off, that is its own decision with its own blast
  radius across avatars.

---

## 6. Open questions

**Q1. Should the per-folder size column and the Sub-folder Sizes chart come back (gap 7,
phase two)?**

- **Option A -- restore both**, guarded by `isSlowProvider()` as the old app was. Costs one
  `listObjects` per folder row on every listing for object stores; the old comment records 14 s for
  sixteen round trips on FTP, which is why the guard exists.
- **Option B -- restore neither**, and ship only the honest labelling from phase one.
- **Option C -- restore the column, drop the chart.** The column answers "is this folder empty or
  does it have 4,000 files in it", which is a real diagnostic question. The chart answers "which
  subfolder is biggest", which the "Largest files" tile the new app added already half-answers.

**Recommendation: C.** The column is the part with a job; the chart was decoration built on the same
expensive data. Ship phase one's labels now regardless, then add the column behind the existing slow
provider guard and leave the chart out. If somebody misses it, the data will already be in hand.

**Q2. Should the preview allow-list live on the server (`ContentTypeUtil`) or be dropped in favour
of "try it and fall back" (gap 3)?**

- **Option A -- widen the server list and have the client read `previewable`.** One authority, one
  place to change, and the client stops guessing.
- **Option B -- remove the server-side gate entirely** and let `previewObject` serve anything, with
  the client deciding what to render. Simpler, but `previewObject` sets
  `Content-Disposition: inline` (`StorageBrowserRestApi:219`), and an ungated inline channel over
  arbitrary uploaded bytes is a different security posture from the one the codebase currently has.
- **Option C -- shrink the client to match the server.** Smallest change, leaves `.log` unreadable.

**Recommendation: A.** It is the only option that removes the duplicated list rather than moving it,
and it keeps the inline gate the current design relies on. B should be refused outright.

**Q3. When a chat is open and the user opens a chat on a different file, confirm or just switch
(gap 1)?**

- **Option A -- confirm**, as the old app did (`object-browser.component.ts:922-932`).
- **Option B -- switch silently**, relying on the 30-minute `sessionStorage` restore
  (`file-chat.ts:73-120`) to bring the old conversation back if the user returns to that file.

**Recommendation: B, with one qualification.** The persistence the new app added is exactly what
makes the old confirmation unnecessary -- the conversation is not lost, it is parked, and a
confirmation on every file switch is the kind of dialog people learn to click through. The
qualification: the *close* confirmation must stay, because closing genuinely deletes
(`file-chat.ts:129-153`), and the restore must be verified to actually work across a switch before
the confirmation is dropped. If it does not, fall back to A.

**Q4. Should `doc`/`docx` preview be restored at all (gap 11, Word half)?**

- **Option A -- restore it**, routing through `documentConverter.json/convert` into `PdfViewer`.
- **Option B -- leave it saying "no inline preview", with a working Download.**

**Recommendation: B for now, A if anyone complains.** It is the only dropped behaviour on this list
that costs a LibreOffice round trip per preview and adds a second failure mode to a dialog that
currently has one. The current state is honest and offers a working alternative in the same panel.
Put it behind the others and see whether it is ever asked for.
