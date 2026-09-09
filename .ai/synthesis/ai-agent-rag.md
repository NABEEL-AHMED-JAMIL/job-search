# Synthesis — AI Agent, File Chat and RAG

Executed 2026-09-04, in direct response to a product request covering three things: the Provider field on the AI Agent screen, the AI Models screen managing local models, and "design and implement a complete flow for the AI Agent + Chatbot + RAG process." This document records what was found already built, what was genuinely missing, what was built to close it, and what remains open.

**Read [`../grooming/content-and-ai-tools.md`](../grooming/content-and-ai-tools.md) first** for the wider context — `ai/agents`, `ai/models` and file chat are all part of the `content-and-ai-tools` feature, and this document only covers the delta from that day's work.

---

## 1. Summary

The request read as "build RAG from scratch." Reading the actual code first found something closer to 70% already there: file chat already lets a user pick an agent, already resolves that agent's provider/model/key dynamically, already caches extracted file text in Redis keyed by etag (the exact "don't reprocess an unchanged file" mechanism the request asked for — just not backed by OpenSearch). The Provider dropdown already read from the `AI_PROVIDER` lookup table. The AI Models screen already listed, pulled and deleted local Ollama models by name.

What was genuinely missing, and built:

1. **The agent's own `instructions` never reached the model.** `AiAgentRuntimeConfigDto` — the one DTO everything routes through — carried provider, model, key and endpoint, and stopped there. Structurally impossible for any caller to apply an agent's configured behaviour, no matter what an admin typed into that field.
2. **No RAG.** Large files were truncated to a flat per-provider character budget and the rest of the document was simply never seen by the model. No chunking, no embeddings, no OpenSearch.
3. **The Agent dialog's Model field was free text even for Ollama**, where the AI Models screen already knows exactly what is installed.
4. **A provider-key casing bug**, found while reading the code that decides how much of a file a hosted model gets: `"AzureOpenAI"` (the real lookup spelling) never matched a map key spelt `"AZURE-OPENAI"`, so every Azure OpenAI agent silently got the 24,000-character budget meant for a small local model instead of its real 250,000.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | `AiAgentRuntimeConfigDto` has no `instructions` field | An agent's own instructions apply to every request through it | Structural — the field cannot reach the prompt no matter what is stored | Added the field; `resolveRuntimeConfig` populates it; `FileChatServiceImpl.buildInstructions` prepends it ahead of the file-chat mechanics (grounding, refusal, export contract), additively, not as a replacement | S | Low |
| 2 | Large files are truncated to a flat char budget; content past the cut is invisible to the model | The model can answer from anywhere in a large file | No chunking, embeddings, or retrieval existed | `TextChunker` + `EmbeddingServiceImpl` (Ollama, `nomic-embed-text`, 768-dim) + `OpenSearchRagClient` (new `file-rag-chunks` index, k-NN mapping). Wired into `FileChatServiceImpl.resolveContext`: skip entirely for a file that already fits; index-if-missing + retrieve for one that does not | L | Medium — new infrastructure dependency (embedding model + OpenSearch), mitigated by graceful degradation (§3) |
| 3 | Re-asking about the same large file re-extracts and re-truncates every time (the Redis `fileChatExtract` cache saves the extraction step, not the reasoning-over-content step) | A second question about an unchanged file reuses prior work | No etag-keyed skip specifically for RAG | `OpenSearchRagClient.isIndexed(bucket, key, etag)` — real per-file check before any chunking or embedding runs | Included in #2 | Low |
| 4 | Agent dialog's Model field is free text for every provider, including Ollama | Ollama models are picked from what is actually installed, sourced from the same list the AI Models screen manages | The two screens did not share data | Model field becomes a `<select>` sourced from `ollama.json/listModels` when provider is Ollama; free text unchanged for every other provider (no local install list exists for a hosted API); a saved value not currently installed is preserved in the option list rather than silently dropped | S | Low |
| 5 | `PROMPT_FILE_CHARS_BY_PROVIDER` keyed `"AZURE-OPENAI"`, the lookup spells it `"AzureOpenAI"` | Azure OpenAI gets its real 250,000-char budget | Case/punctuation mismatch never matched | `providerKey()` strips all non-alphanumerics before matching; map key corrected to `"AZUREOPENAI"` | S | Low — found and fixed while reading the code for #2, unrelated to the original request |

---

## 3. Solution detail

### 3.1 RAG runs for every file it can reach — **changed 2026-09-04, see §6.2**

`resolveContext` tries RAG *first*, for any file size, whenever `ragAvailable()` — indexing a file whenever OpenSearch and the embedding model can reach it, so a repeat question, this session or a later one, is answered from OpenSearch instead of the raw extracted text. Only when RAG is unavailable (or fails, or genuinely finds nothing) does the provider's char budget decide whether the text goes through whole or truncated — the same fallback this method always had. A short file typically chunks into one or two pieces well inside `RAG_TOP_K`, so its retrieval comes back *complete*; `buildInstructions` frames a complete retrieval as `--- FILE CONTENT ---`, the same as the old direct-content path, rather than `--- RELEVANT EXCERPTS ---` with a "there may be more" caveat that would be false for it. (Original design, superseded: RAG only ran for a file too large to send whole, on the reasoning that indexing a file nobody needed indexed was itself the "unnecessary file processing" to avoid — see §6.2 for why that changed.)

### 3.2 Why retrieval is scoped to one file, not a corpus

The request describes retrieval as "what does THIS file say," always in the context of one open chat session against one object. A single file's chunk count is small — tens to a few hundred. Rather than reach for OpenSearch's k-NN filtered-query DSL (version-sensitive, and overkill at this scale), `OpenSearchRagClient.searchRelevantChunks` fetches a file's chunks by an exact term filter (`bucket` + `key` + `etag`) and ranks them by cosine similarity in application code. The vectors are still stored in a real `knn_vector` field with a proper k-NN index mapping (`index.knn: true`, `dimension: 768`), so a future cross-file search does not require a reindex — only a different query shape.

### 3.3 Graceful degradation, not a hard dependency

`FileChatServiceImpl.ragAvailable()` checks two independent things: `OpenSearchRagClient.isEnabled()` (is `opensearch.url` configured) and `EmbeddingService.isAvailable()` (a real call to the embedding model, not just a config check — the model being configured is not the same as it being pulled). Either being false silently degrades to the old truncation behaviour rather than breaking file chat. Any exception inside the RAG path itself is caught and degrades the same way — a tenant asking a second question about a large file must not see an error because one embedding call timed out.

### 3.4 Reindexing on change, not accumulation

`indexChunks` deletes every previous version's chunks for a `bucket`+`key` (any etag) before writing the new ones. A file's old content is never queried again once a new version lands, so keeping it would be pure dead weight, growing forever with every edit to a frequently-changed file.

### 3.5 Chunk IDs are deterministic, not random

Each chunk's OpenSearch `_id` is a SHA-256 hash of `bucket|key|etag|chunkIndex`. A retried or duplicated indexing call overwrites the same document rather than accumulating a second copy — idempotent by construction, not by a delete-then-insert transaction OpenSearch does not offer here.

---

## 4. What was set up, not just written

- **`nomic-embed-text` was pulled** into the local Ollama (274 MB, 768-dimension output, confirmed live). Before this work, exactly one model was installed (`qwen3:8b`, a chat model with no embedding capability) — RAG could not have run against the environment as it stood.
- **The `file-rag-chunks` OpenSearch index** is created lazily, on first real use, with its k-NN mapping — not at application startup, so an environment that never opens a RAG-eligible file never pays for it and the feature cannot fail a boot.

---

## 5. Verified, not assumed

| What | How |
|---|---|
| `TextChunker` — every character survives chunking, overlap is real, pathological input terminates | 9 unit tests, `TextChunkerTest` |
| `AiAgentRuntimeConfigDto.instructions` actually reaches a caller | 2 unit tests, mutation-checked: removing the one line that populates it turns the test red |
| The Azure OpenAI provider-casing fix | 1 unit test, mutation-checked against the original bug |
| **Real semantic retrieval** — a question about revenue retrieves the revenue chunk over cafeteria/parking chunks | `OpenSearchRagClientIT`, against the live OpenSearch and live Ollama, not a mock |
| **Real skip-reindexing** — the same etag reports already-indexed; a different etag does not; reindexing a file removes its previous version's chunks | Same suite, 6 tests total, all against live infrastructure |
| **The whole decision tree** in `FileChatServiceImpl` — a small file with RAG available is indexed and retrieved too, not bypassed; a complete retrieval is framed as file content, not excerpts; RAG unavailable (any size) never touches OpenSearch or the embedding model and falls back to the old direct/truncated behaviour; an already-indexed file skips straight to retrieval; empty retrieval falls back to direct content rather than an empty prompt; a RAG exception degrades the answer rather than failing the request | `FileChatRagDecisionTest`, 8 tests, all mocked (no live LLM calls), mutation-checked |
| The Ollama Model dropdown — fetches only for Ollama, preserves a saved-but-uninstalled value, does not refetch on a second switch back | `agent-dialog.spec.ts`, 8 tests, two mutation-checked |
| Nothing else broke | Full suites re-run after every change: backend 537 (up from 519), frontend 460 (up from 452) |
| The live loop, end to end | Both containers rebuilt and redeployed; `AI_PROVIDER` lookup confirmed to hold 21 real rows in the running database, not just in test fixtures |

**Not verified**: a full authenticated browser walkthrough (sign in → open AI Agents → create an Ollama agent → open a large file → chat → confirm the second question skips reindexing) was not completed. This session does not have, and does not guess at, the platform admin's login credentials. The live-infrastructure integration test (`OpenSearchRagClientIT`) is the closer proof for the RAG mechanics specifically, since it exercises the real embedding model and real OpenSearch rather than a UI click path; it does not exercise the browser or the authentication chain.

---

## 6. Out of scope

- **Cross-file / corpus-wide RAG search.** The index and its k-NN mapping support it; nothing in this pass builds the retrieval query shape for it, because the request describes retrieval scoped to one open file, not a search across everything a tenant has ever uploaded.
- **`Cohere`** remains in the lookup and routes through the generic OpenAI-compatible caller. Cohere's own documented API (`/v1/chat`) is not OpenAI-shaped, but Cohere now publishes a `/compatibility/v1/chat/completions` endpoint that is — usable today by an admin who points `apiEndpoint` at that specific path, the same way LM Studio, vLLM or LlamaCpp already require. Not fixed natively: unlike Bedrock/Gemini (below), this one already works for anyone who configures the right URL, so it did not meet the bar that got AzureOpenAI a dedicated implementation.

### 6.1 Resolved, 2026-09-05 — acted on the flagged decisions

**Chat history stays in `sessionStorage`.** The recommendation in §7 was to leave it — a considered, documented privacy choice already in the code, not an oversight. No change made.

**`AWSBedrock` and `GoogleGemini` were removed** from the `AI_PROVIDER` lookup (`lookup_id` 1113 and 1111). Verified first: zero existing agents used either provider, so nothing was orphaned. Verified second: neither row came from a Liquibase changeset — `V9.0-ai-provider-bucket-list` seeded only the original three (OpenAI, Anthropic, Ollama); all 18 others, including these two, were added later by hand through the same path an admin would use (Settings → Lookup), so removing two of them the same way is an ordinary administrative edit, not a schema change, and needs no migration. `setting.json/appSetting` is not Redis-cached, so the removal took effect immediately with no redeploy.

**`AzureOpenAI` turned out to be broken too, more subtly than Bedrock or Gemini — and was fixed rather than removed.** Re-reading `callGenericOpenAiCompatible` while verifying the Bedrock/Gemini removal found that it sends `Authorization: Bearer <key>`. Azure OpenAI's REST API authenticates a plain resource key through an `api-key` header instead — `Bearer` is only accepted there for Azure AD OAuth tokens, a separate setup almost nobody configures for a simple integration. Every `AzureOpenAI` agent set up the ordinary way (a resource key, the common case) would have failed authentication on every request, silently, since the generic path's only validation is that an endpoint was supplied at all. Unlike Bedrock (needs full SigV4 request signing) this was a small, well-scoped fix: `AiAgentServiceImpl.callAzureOpenAi` is now a dedicated branch in `callProvider`, same OpenAI-shaped request body, `api-key` header instead of `Authorization: Bearer`, `apiEndpoint` still required (there is no sensible default the way `api.openai.com` is for plain OpenAI, since a deployment URL is tenant- and deployment-specific).

Verified against a real local HTTP server (`AzureOpenAiAuthHeaderTest`, JDK's built-in `HttpServer`, no mock of the HTTP layer) — the actual outgoing request carries `api-key` and carries no `Authorization` header at all, mutation-checked. 539 backend tests (up from 537), all green; backend redeployed.

### 6.2 Changed, 2026-09-04 — RAG now runs for every file, not only large ones

**What prompted it.** A live test of the flow (select a file, ask a question) showed nothing indexed in OpenSearch afterward. Investigation (Redis `fileChatExtract` cache empty, `file-rag-chunks` doc count zero, no backend log activity of any kind since the last restart, but OpenSearch and Ollama both confirmed reachable from inside the container) traced this to the actual test file: a 33KB PDF resume, which extracts to well under Ollama's 24,000-character budget — exactly the case §3.1's original design skipped RAG for entirely, by design. Not a bug; the RAG-only-for-large-files design working as built. The request that followed was explicit: index every file, so a repeat question is answered from OpenSearch instead of the raw file.

**What changed.** `resolveContext` no longer checks file size before deciding whether to use RAG. It tries RAG first whenever `ragAvailable()`, for any size; the size budget now only governs the fallback path (RAG unavailable, or it ran and found nothing). See §3.1 for the mechanics, including the new `RetrievalResult.complete` flag that keeps a fully-retrieved short file framed as `--- FILE CONTENT ---` rather than misleadingly labelled excerpts.

**Trade-off, noted not resolved:** a short file that used to go to the model whole now goes through chunking (typically one chunk, since `TextChunker` only splits past `DEFAULT_CHUNK_SIZE`) and a retrieval round trip before reaching the model — one extra OpenSearch + embedding call pair per first-ever question against a given file version, always. For a file already fitting the budget this buys nothing in answer quality on that first question; what it buys is the reuse the original request asked for on every question after it, including in a later session. No user-facing behaviour regresses — a complete retrieval reads identically to the old direct-content path.

Verified: `FileChatRagDecisionTest` rewritten for the new decision tree (8 tests, including the two above), mutation-checked — reverting the size-gate removal turns exactly the new "small file still indexes" test red and nothing else. `OpenSearchRagClientIT`'s `searchRelevantChunks` call sites updated for the new `RetrievalResult` return shape — no behaviour change to the live-infra tests themselves, all still green against real OpenSearch and Ollama.

---

### 6.3 Resolved/Changed, 2026-09-05 — embedding provenance, lazy extraction, vision model, image-leak fix, and a follow-up review pass

A dense session covering five separate reports/requests in sequence, then a full 8-angle code review of everything below plus everything in §6.1/§6.2. Recorded together since each built on the last.

**`embeddingModel` recorded on every indexed chunk.** `OpenSearchRagClient.indexChunks` gained a 7th parameter, written as a `keyword` field per chunk doc; `EmbeddingService`/`EmbeddingServiceImpl` gained a `model()` accessor to supply it. Purpose: so a later change of `embedding.model` (swapping which Ollama embedding model is configured) is at least visible per-chunk after the fact, rather than indistinguishable from the original model's vectors. **Not yet enforced or read back** — `searchRelevantChunks` still ranks every chunk matching bucket/key/etag regardless of which model embedded it; a genuine mid-life model swap would still silently mix incompatible vectors in the same cosine-similarity search with no detection. Flagged again by this session's own review pass (§6.3.5) as a real, unresolved gap — deliberately not fixed in this pass, since the fix (filter search by current model, or version-tag and re-embed stale chunks) is a design decision, not a one-line change, and the field exists now specifically so that decision has data to work from later.

**Audio RAG was investigated after two separate user reports, both resolved as not-bugs.** "Audio file rag not added in the OpenSearch" traced to a timing artifact — the data was present, just checked before an async transcription completed. A follow-up "mp3 chat shows 'Reading the file…'" traced to a genuine, in-progress ~43-second chunk-by-chunk transcription completing normally with `200 OK` — real, but a UX gap (no progress indicator), not a functional bug, and not fixed (offered, not taken up).

**Eager extraction defeating the point of RAG reuse — fixed.** Both `prepareContext` and `sendMessage` extracted the raw file unconditionally before ever checking OpenSearch, so an already-fully-indexed audio file was re-transcribed (40+ seconds) on every single visit — the exact "don't reprocess an unchanged file" case RAG exists for, silently not happening. Fixed two ways: `prepareContext` gained a fast path (`isEnabled() && isIndexed()`, skipping extraction entirely once true) and `sendMessage` now threads a lazy, memoized `TextSupplier` through `resolveContext` instead of extracting up front — extraction happens at most once per request, and only when something downstream actually needs the raw text. Verified: `FileChatLazyExtractionTest`, 6 tests, including one that specifically asserts the availability check is never reached on the fast path.

**Vision model was misconfigured — fixed.** `ollama.vision.model` defaulted to bare `"llava"`, which Ollama does not resolve to any locally pulled model (only a real tag like `llava:7b` does); the only vision model actually pulled in this environment is `llava:7b`. Fixed via both the Java `@Value` default and `docker-compose.yml`'s `OLLAMA_VISION_MODEL` env var.

**Customer-facing information leak in the Vision Assistant — fixed.** A real chat transcript showed an image description volunteering the raw MinIO bucket/path and an internal content-hash-style filename, then inviting the user to "download it in a specific format" — both sourced from the document-chat prompt's unconditional "Filename: X. Source location: Y." fact and its CSV/PDF/Excel export instructions, applied to every file regardless of type. Fixed via a dedicated `buildImageInstructions` prompt, dispatched on content type, that never hands the model the bucket, path, or filename at all (not merely instructed to withhold them) and omits the export machinery entirely. Verified: `FileChatImageInstructionsTest`, 4 tests, using the exact bucket/key from the reported leak; mutation-checked against the original bug (disabling the dispatch reproduced the leaked bucket/path and `TARGET_FORMAT` verbatim in the captured prompt).

**Follow-up review pass — "generic code for all code," read/tested/fixed.** The image fix above was itself an `isImage ? imagePrompt : documentPrompt` special case; a review across 8 angles (line-by-line, removed-behaviour, cross-file, reuse, simplification, efficiency, altitude, conventions) found it hadn't generalized far enough, plus a real correctness bug the same session's own memoization refactor had introduced. Fixed in this pass:

1. **An extraction failure could crash the request instead of degrading it.** `resolveContext`'s RAG-failure catch assumes any non-`UnsupportedFileTypeException` means "transient RAG hiccup, fall back to direct content" — but when the failure originated in extraction itself (a vision-model call or transcription genuinely throwing, confirmed real via `FileChatExtractionServiceImpl`'s `callVisionModel`/`transcribeAudio`), the memoized fallback call rethrows the identical cached exception, unguarded, straight out of `sendMessage` as an unhandled exception instead of the promised graceful degrade. Fixed by having `memoizedExtraction` wrap any such failure as `UnsupportedFileTypeException`, which `sendMessage` already knows how to turn into a plain `ResponseDto(ERROR, ...)`. Verified: `FileChatExtractionFailureTest`, 2 tests, mutation-checked (reverting the wrap reproduced the escape as an uncaught `IllegalStateException`).
2. **Audio inherited the exact leak just fixed for images.** `isImage(key)` correctly returns `false` for `.mp3`/`.m4a`, so a transcript — itself model-generated, not literal file text, same as an image description — fell straight through to the document prompt's bucket/path fact and export instructions. Generalized the dispatch from a single boolean into `ContentTypeUtil.ContentCategory` (`IMAGE` / `AUDIO` / `DOCUMENT`), gzip-aware (folding in the separate gzip-awareness gap `isImage` had relative to `acceptsFileType`), with a new `buildAudioInstructions` mirroring the image prompt's rules for a transcript. Verified: `FileChatAudioInstructionsTest`, 3 tests, mutation-checked (reverting to the old boolean reproduced the same leaked-bucket-and-export-instructions pattern for audio).
3. **`.jpeg`/`.webp`/`.tiff` were classified as images but had no extraction path.** `ContentTypeUtil` maps all three to `image/*`, but `DocumentConverterFormatRegistry`'s `DRAWING` family only listed `jpg`/`tif` — so these functionally-identical files failed outright as unsupported. Added `jpeg`/`tiff` to the family's input/output lists (JODConverter's own default format registry maps both spellings to the same JPEG/TIFF format, so this only unblocks this project's own `familyOfInput` gate). `webp` deliberately left unadded — WebP import support varies by LibreOffice version and needs verifying against the actual deployed LibreOffice before being wired in, not guessed at.
4. **`buildImageInstructions` duplicated two blocks verbatim from `buildInstructions`** (the agent-instructions preamble and the entire history-rendering loop) — extracted into shared `appendAgentPreamble`/`appendHistory` helpers, used by all three prompt builders (document/image/audio) now.
5. **The legacy Angular app never sent `aiAgentId` to `prepareContext`** (`file-chat.service.ts`), so the backend's target-file-type mismatch check there could never fire from that UI — the readiness panel always said "Ready" even for a mismatched agent/file, with the mismatch only surfacing once the user typed a question and `sendMessage`'s separate check rejected it. Fixed: the service now accepts an optional `aiAgentId`, and both call sites pass the component's already-tracked `chatSelectedAgentId`.

**Found and deliberately not fixed in this pass**, each with a reason:

- **`embeddingModel` still unenforced at retrieval** (above) — needs a design decision (filter vs. re-embed), not a mechanical fix.
- **Three hardcoded "image extension" lists across both frontend apps have drifted from the backend's image set** (`object-browser.component.ts`, `document-converter.component.ts`, `next/preview-dialog.ts` all omit `tif`/`tiff`; one also omits `webp`) — cosmetic (preview/icon selection only), lower urgency than the correctness fixes above, and touching three files for a currently-rare extension combination was judged disproportionate to bundle into this pass.
- **`prepareContext` and `sendMessage` redundantly re-check "already indexed" and re-resolve agent config per message** when the `next/` frontend calls `refreshCoverage()` (→ `prepareContext`) right after every `sendMessage` response — real duplicated I/O, but a frontend wiring change with its own regression risk, left for a dedicated pass.
- **`prepareContext`'s fast path reports readiness from `isEnabled() && isIndexed()` alone**, not the full `ragAvailable()` `resolveContext` itself gates on (which also pings the embedding model) — by original design (no question to embed yet at readiness-check time), but can let the UI promise retrieval a transiently-unreachable embedding service won't actually deliver moments later. Documented, not changed, since narrowing this trades a cheap readiness check for a live network call on every panel open.

Verified: full backend suite re-run after every change (574 tests, up from 539 in §6.1 plus this pass's 11 new tests across `FileChatExtractionFailureTest`, `FileChatAudioInstructionsTest`, and `ContentTypeUtilTest`), all green; each behavioral fix mutation-checked (revert, confirm exactly the expected test(s) go red, restore); backend rebuilt and redeployed, container healthy with no startup errors; the legacy Angular frontend change type-checked cleanly (`tsc --noEmit`) but was not walked through live in the browser (no test credentials/data set up for a full authenticated click-through, consistent with §5's "Not verified" note).

---

## 7. Open questions

**Q1 and Q2 are resolved — see §6.1.**

**Q1 — Should chat history move into Redis, reversing the existing privacy-motivated design?**
Options: (a) leave it in `sessionStorage` as-is; (b) move it to Redis with a short TTL, matching the request literally; (c) Redis-backed but opt-in per agent or per tenant.
**Recommendation: (a), unless there is a specific reason for (b) not covered above** — cross-device continuity, an audit/compliance requirement, or a product decision that the privacy tradeoff is acceptable. The current design was a considered choice, documented in the code, made for files that can carry real personal data; reversing it changes what the platform retains about what a user asked their files, which is a decision with more weight than "use Redis for short-lived data" alone conveys. This is exactly the kind of call this document exists to surface rather than override silently.

**Q2 — Should `AWSBedrock` and `GoogleGemini` be removed from the `AI_PROVIDER` lookup until they have real implementations, or built out now?**
Options: (a) remove them from the lookup so nothing selectable currently fails; (b) build native support for both; (c) leave them selectable with no further action.
**Recommendation: (a) now, (b) later if there is real demand.** Leaving them selectable (c) is the one option that produces a worse outcome than either alternative — an admin can configure an agent against either provider today, and it will fail at the first message with no warning at save time.

**Q3 — Chunk size and top-K are fixed constants (`TextChunker.DEFAULT_CHUNK_SIZE` = 1000, `RAG_TOP_K` = 8). Worth making configurable?**
**Recommendation: not yet.** Both are reasonable defaults reasoned about in code comments, and there is no evidence yet — no real usage against real large files — that either needs tuning. Making them configurable before that evidence exists is speculative generality; add the property when a real case asks for it.
