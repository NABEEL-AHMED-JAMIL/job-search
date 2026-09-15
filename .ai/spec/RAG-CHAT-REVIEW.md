# RAG, Redis and the file chat — review and repair (2026-09-14)

Triggered by a report that "seem like we are not creating the vector data", with the PDF chat
named as the broken one. Eight dimensions reviewed, 32 candidate findings, **26 survived
adversarial refutation, 6 were refuted.** The headline finding is a one-line encoding bug that
had been destroying text in every indexed file since the feature shipped.

## The vectors were fine. The text was not.

The first thing measured, before any code was read:

```
file-rag-chunks: 225 docs, index.knn=true, embedding = knn_vector dim 768
every one of the 225 has an embedding; sampled vectors are 768 non-zero floats, L2 norm 1.0000
```

So embeddings were being produced correctly. The defect was elsewhere, and the live index gave it
away:

```
chunks scanned:                                      225
chunks containing ANY character above U+00FF:          0
chunks containing a Latin-1 supplement character:      0
literal '?' characters across all chunk text:        108
```

Across CVs, PDFs, CSVs and Markdown, **not one character above U+007F**. No curly quote, no
em-dash, no accented letter, no currency symbol. That is impossible for real documents.

### Root cause

`OpenSearchRagClient` sent the `_bulk` body as `application/x-ndjson` **with no charset**. Spring's
`StringHttpMessageConverter.getContentTypeCharset` returns the content type's own charset if it has
one, else UTF-8 *only* if the type `isCompatibleWith(application/json)`, else its `DEFAULT_CHARSET`
— which is **ISO-8859-1**. `x-ndjson` is not compatible with `application/json`, so every bulk body
this platform has ever sent went out as Latin-1. Two distinct losses:

| character range | what Latin-1 did | consequence |
|---|---|---|
| above U+00FF | no byte exists → written as `?` | 108 question marks; text silently corrupted |
| U+0080–U+00FF | one byte 0x80–0xFF | **not valid UTF-8** → OpenSearch rejected the whole document → the chunk vanished |

The second is why `I-94_I-95 Official Website - Get Most Recent Response.pdf` holds `chunkIndex` 0
and 2 and no 1: its middle chunk contained a **U+00A7 SECTION SIGN**.

Every other call in that class uses `MediaType.APPLICATION_JSON`, which Spring special-cases to
UTF-8. That is why only the bulk write was affected, and why the bug survived a class that is
otherwise carefully written.

### Two things hid it, and both were fixed rather than left

1. **`logBulkErrors` swallowed the evidence.** A bulk response is HTTP 200 even when individual
   items were rejected, so the body is the only place the truth is written. The method logged one
   WARN reading "OpenSearch rejected some chunks while indexing {}/{}", naming neither how many nor
   which nor why, and returned `void` — so no caller could say so either. It is now
   `reportBulkOutcome`: it counts stored against attempted, names the lost chunk indexes and the
   first reason, and returns an `IndexOutcome` the caller acts on.

2. **Completeness was inferred from a document count.** `fetchInDocumentOrder` returned
   `complete = true` unconditionally, reasoning that the count which routed the call uses the same
   filter as the fetch, so nothing was left out. That is true of what OpenSearch holds and false of
   what the file contains: a chunk rejected at write time is missing from *both*, and the two agree
   perfectly about a document with a hole in it. The surviving chunks were handed to the model
   under the heading "FILE CONTENT" with no caveat, because `partial` is computed as
   `!result.complete`. Completeness now comes from **chunkIndex contiguity**.

## Everything else that survived verification

**Retrieval was never a k-NN query.** Despite `index.knn=true` and a `knn_vector` mapping, the
ranking path built a constant-score term filter, asked for `size: 2000`, and pulled every matching
chunk's full 768 floats back over HTTP to rank in Java. Measured: a question about a 20-chunk PDF
returned a **229,285-byte** response in which every hit carried the identical `_score`. Now a real
filtered `knn` query, with the Java cosine path kept as the fallback for a cluster that cannot
serve one (older OpenSearch, `index.knn` disabled, or an `embedding` field auto-created as
something else). New indexes are created with an `hnsw`/`lucene`/`cosinesimil` method, because the
default engine rejects a filtered knn query outright.

**Three embedding round trips per message.** `isAvailable()` was not a health check — it ran
`embed("ping")`, a real inference, cached 15 seconds, and `ragAvailable()` consults it three times
per message. It now asks `/api/tags`, caching a positive answer for minutes and a negative one for
seconds so recovery stays cheap to notice.

**A 588-chunk file was unindexable forever.** `embedAll` put every chunk in one `/api/embed`
request against a fixed 30-second read timeout, so the 95 MB CSV timed out and the whole
extract-embed-index cycle restarted on the next message, indefinitely. Now sliced into batches of
64 with a proportionate timeout, and a failed batch is reported rather than silently truncated —
`indexChunks` pairs texts and vectors positionally, so a short list would misalign every chunk.

**A Redis outage was an HTTP 500.** No `CacheErrorHandler` was registered, so Spring's default
rethrows; opening the chat panel returned 500 while MinIO, Ollama and the model endpoint were all
healthy. A cache that cannot be reached must mean "miss", never "fail". The FTP listing cache calls
`Cache.get/put/clear` **directly** rather than through `@Cacheable`, and `CacheErrorHandler` is only
consulted by `CacheInterceptor` — so it needed its own guard. Same failure, different mechanism.

**Deleting a file did not delete its text.** No write path carried `@CacheEvict`, so a deleted
document's full extracted plaintext (up to 500,000 characters) stayed in Redis for the remaining
seven days of its TTL, and a replaced file could answer from the previous version.

**A failed vision call became the file's content.** `describeFirstPageViaVisionModel` caught
everything and returned an apology sentence, which is non-null — so it was cached for seven days as
the file's text and chunked and embedded into the RAG index as though it were the document.

### The agent settings — the user's central point

`target_file_types` **is** genuinely enforced, in both `prepareContext` and `sendMessage`; the
column is not decorative. The agent's stored `instructions` **do** reach the provider, prepended
verbatim. Two real gaps:

- **`json_mode` was resolved and then dropped.** `resolveRuntimeConfig` populates it, and the
  file-chat path never called `setJsonMode`, so `Boolean.TRUE.equals(null)` was false and the
  provider never received `format=json`. Turning it on for an agent changed nothing.
- **For an image, neither the agent's model nor its instructions reached the model that looks at
  the pixels.** The vision call used a globally configured default (`llava:7b`) and a hardcoded
  prompt, so agent 1022 "Vision Assistant" — whose entire configuration is a model of its own and
  2,804 characters about what to look for in a medical image — had no effect whatsoever. Now
  carried through, with the agent's instructions in the cache key, since the description genuinely
  depends on them. Only an **Ollama** agent's model is used: the call goes to the local Ollama
  endpoint, where an OpenAI or Anthropic model name would turn a working default into a 404. And
  only for **vision-capable file types**, so a CSV is not re-extracted once per agent for an
  identical result.

## Email the export

The platform already emails stored files to an arbitrary validated recipient
(`FileShareServiceImpl.emailFile`, with bucket-ownership checks, a 20 MiB ceiling and a 500-file
cap), so this is not a new outbound path — it reuses an authorised one, and the recipient rule was
matched rather than reinvented.

A chat export is *generated*, not stored, so `emailFile`'s bucket/key path cannot carry it. Added
`FileShareService.emailGeneratedFile` and `POST /fileChat.json/emailExport`. The ceiling and the
address rule stay in `FileShareService`: a second copy of "20 MiB and a valid address" is a second
thing to keep in step, and the copy is what drifts. The recipient is collected in the app's own
share dialog, not `window.prompt`.

## Evidence

- **50 new tests** across `RagBulkEncodingTest` (29) and `FileChatEmailExportTest` (21), plus the
  tests each fix group carried.
- The encoding tests drive Spring's **real** `StringHttpMessageConverter` rather than asserting on
  a header, because the header is only interesting for what Spring does with it — and what Spring
  does with it is the bug. Tests 1–6 assert the framework premise itself, so the suite does not
  rest on an unverified belief about a dependency.
- **Mutation-proven.** Restoring the old content type fails 3 tests including the exact `§` case;
  hard-coding completeness back to `true` fails 3 more.
- Backend **1392** passing, frontend **1457** passing. Both containers rebuilt and healthy.

## Not verified, and why

**The end-to-end re-index through the deployed stack was not completed.** The browser session's JWT
had expired, so the chat request never reached the backend, and re-indexing only runs when a
question is asked about a file with no chunks. The fix is proven at unit level against the real
converter and the containers are deployed, but nobody has yet watched a real PDF go in and come
back with its `§` intact. **That is the first thing to do with a live login.**

## Live data changed during this work

The 20 chunks for `etl-bucket/test-file/Nabeel Ahmed Jamil Java Engineer.pdf` were **deleted** from
`file-rag-chunks` to force a clean re-index (they held 84 question marks and zero characters above
U+007F). That file currently has no index entries; it will re-index automatically the next time
anyone asks a question about it, which is the designed behaviour for a file with zero chunks.

**The other 205 chunks are still Latin-1 damaged.** The fix prevents new damage; it does not repair
what is already stored, because a chunk set is only rewritten when a file's etag changes or its
chunks are removed. Repairing the rest means deleting the index and letting it rebuild on demand —
a deliberate operation on live data, not something to do quietly.

## Refuted, so nobody re-investigates

- *tenantId is null on every real file because only the platform admin has indexed one* — the
  reading is right, the defect is unreachable: retrieval carries no tenant clause at all, and
  isolation rests on `validateBucketAccess` checking the bucket alias against the caller's own list.
- *Three chunks carry no embeddingModel because nothing detects or repairs pre-field documents* —
  the observation is real, the "undeletable by any code path" half is false.
- *The agent's instructions are included but not authoritative* — mechanically accurate, but in
  both live scenarios the hardcoded block is the guard, not the bug.
- *There is no way to email a file from this platform* — false; `FileShareServiceImpl` exists.
- *prepareContext re-extracts the whole file after every message* — false.
- *prepareContext responses are neither sequenced nor cancelled* — the shape is quoted accurately,
  the premise fails on three independent counts.
