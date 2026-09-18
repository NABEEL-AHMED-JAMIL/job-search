# QA — AI prompts in pipelines

Companion to `.ai/grooming/ai-prompts-in-pipelines.md` and `.ai/synthesis/ai-prompts-in-pipelines.md`.
Exercised live on 2026-09-18 against `http://localhost:4400` / `http://localhost:9098` with the
workers from `job-search` branch `ai-prompt-steps` (containers `tpd_test_listener`,
`tpd_scrapping_listener`), the local Ollama (`gemma3:1b`) and MinIO. Signed in as
`emily.rodriguez@medaxiscare.demo` (TENANT_ADMIN, MedAxis) and, for isolation, as
`michael.thompson@everwellmedical.demo` (EverWell). Every run below made a real model call.

**Fixtures created and left in place** (per `feedback_leave_test_data_in_place.md`): connection
"Ollama · local box" (default, cap 2 in flight, 50,000 tokens/day); prompts "Summarise claim" (JSON,
v2), "One-line verdict", "Tiny JSON (5 tokens)", "Chain verdict"; topic "AI worker test 753866"
(11763, `test-topic`); pipelines `AIUI001`, `AIW753866`, `L…00–49`, `M…001–100` with a task and a job
each (the 27 scheduled jobs deactivated at the end of the pass); MinIO object
`etl-bucket/claims/in/CLM-2026-00418.txt`.

## Acceptance checklist

| # | Criterion | Result |
|---|---|---|
| 1 | Connection: add, test lists the provider's models, default set, key never returned | pass (5 models listed; `apiKeyConfigured` only) |
| 2 | Another workspace cannot see, default or delete a connection | pass (Michael: empty list, "Connection not found") |
| 3 | Default cannot be deleted while a prompt relies on it | pass |
| 4 | Prompt: template placeholder without a variable refused (server and editor) | pass |
| 5 | Try it runs the page as it is; answer, tokens, time shown; recorded as a try | pass (0.5 s, 101→23) |
| 6 | Save is a version; Save & activate makes it live; versions listed | pass (v1, v2) |
| 7 | Another workspace cannot read a prompt; file chat lists only its own | pass |
| 8 | Pipeline: AI step refused without a prompt, with a required variable unmapped, reading a field below it, `file:` on a server step, a server step reading a worker step's tag | pass (each message named the step and the variable) |
| 9 | Prompt in use by a pipeline cannot be deactivated or deleted; "Used by" counts it | pass |
| 10 | Task shows the step as a read-only card, no input, no tag from the browser | pass |
| 11 | Dispatch runs server steps and the Kafka message carries the answer tag | pass (`<summary>{…}</summary>` seen in the sent payload) |
| 12 | Worker steps: `<ai_step>` handed over, worker resolves tag and file variables, console runs it under the run token, tag written, audit line | pass (139→24 tokens, 2.3 s, file text in the rendered input) |
| 13 | Chained steps, server→server and server→worker | pass (step 2's input carries step 1's JSON) |
| 14 | Empty required variable fails before any call | pass |
| 15 | JSON never validating: one repair round, then failed; `continue` completes the run with the tag empty | pass (5-token prompt) |
| 16 | Daily budget: refusal before the call; fail vs continue per step | pass (overshoot = in-flight calls only) |
| 17 | Idempotent per (run, tag); a replayed Kafka message after a worker restart is skipped | pass after fix (`job-search` `3d60fd1a`) |
| 18 | Run logs show an "AI steps" card; job history and prompt runs agree | pass |
| 19 | Access profile: `ai-prompts` grants Prompts; member without it sees no Assistants | pass (`access-profiles.spec.ts`) |
| 20 | Scheduler: scheduled jobs with AI steps fire, skip-next skips, deactivate stops | pass (30 jobs, two slots) |
| 21 | Bucket in, bucket out: a worker step over each object under the task's input folder writes each answer to the output folder, on a real object-storage pipeline | pass (F768939: 5 in → 5 `.summary.json` out + the `.gz` archives) |

## Findings

| Id | Severity | Finding | Status |
|---|---|---|---|
| AI-1 | high | The worker re-ran a replayed message end to end (model call, bucket write, three refused callbacks) after a restart | fixed, `job-search` `3d60fd1a` |
| AI-2 | high | The Python worker sent only the shared secret; with per-run tokens every status callback was a 401 and runs stayed at Start | fixed, `job-search` `c40d08d7` |
| AI-3 | medium | A topic test said "reachable" for a topic no worker reads; a run dispatched to one strands at Start for 6 h (runs 5715, 5716) | fixed, `process` `0f27b52`, `scheduler1` `df48860` |
| AI-4 | medium | The test listener container had no MinIO credentials, so a worker step reading a file failed | fixed, compose |
| AI-5 | low | AI budget day counted from UTC midnight while run rows are in the server's clock (rolled 5 h early) | fixed, `process` `0f27b52` |
| AI-6 | low | Worker-run steps left no audit line | fixed, `job-search` `1d5914df` |
| AI-7 | low | The AI step drawer's "reads field" select lost its saved value on reopen | fixed, `scheduler1` `0ffcf12` |
| AI-8 | low | Expected refusals logged a full stack on the server | fixed, `process` `0f27b52` |
| AI-12 | high | `<ai_step>` for a per-object step was emitted with no `<var>` children (built, never appended), so the worker had nothing to loop over | fixed, `process` `df29b4a` |
| AI-9 | observation | One notification per run: 296 in a day of testing; the bell reads 99+ | open — a digest is the obvious change |
| AI-10 | observation | Server-side steps run one after another inside the dispatch tick (~0.65 s each); ≤2× to gain with a cap of 2 | open, by design for now |
| AI-11 | observation | The worker's MinIO (`:9000`) and the console's buckets (LocalStack `:4566`) are different stores in this dev setup; a file variable reads the worker's | open — environment |

### AI-13 · major, fixed 2026-09-18 · The file chat could not read a `.log` -- the one file type "Log triage" was written for

**Observed.** Chatting with the worker's `docs/logs/worker.log` (216 bytes of plain text) from the
bucket: "Couldn't get any readable content out of this .log file." `.txt`, `.md`, `.csv`, `.json`
beside it all read fine. **Cause.** `NATIVE_TEXT_EXTENSIONS` stopped at md/txt/csv/json/xml; every
other extension went to the document converter, which has no "log" family and answers null -- the
same null that means "no reader for this type". **Fixed.** `process` `c6698ad`: log, tsv, yaml/yml,
jsonl/ndjson, properties, ini, sql, toml, env read as themselves; pinned by
`FileChatExtractionServiceImplTest.plainTextFormatsWithoutAConverterFamilyAreReadAsThemselves`.

### AI-14 · minor, fixed 2026-09-18 · An empty file was reported as an unsupported format

**Observed.** The whisper step's transcript of a test tone -- a legitimate zero-byte `.txt` -- and
the tone `.mp3` itself both answered "Couldn't get any readable content out of this … file", which
sends the reader looking for a format problem. **Cause.** Two `ProcessUtil.isNull` calls used as
null checks (`truncate()` in the extractor, the supplier in `FileChatServiceImpl`); that helper is
also true for `""`, so an empty read collapsed into the extractor's "unsupported" null.
**Fixed.** Same commit: both are `== null`; an empty file now says "tone.txt is empty -- there is
nothing in it to ask about". Two tests pin it (extractor returns `""`; service names the file).

### Checklist addendum -- the chat bot on bucket files (2026-09-18)

Through a new storage connection to the workers' MinIO (`worker-store`), every output the twenty
pipelines wrote was opened in the file chat, from the panel and through `fileChat.json` directly:
CSV, JSON, `.txt`, `.md`, `.txt.gz`, `.log` (after AI-13), spoken `.m4a` (synthesised with `say`,
uploaded through the console, transcribed by `audio_extract_service`), the empty transcript (after
AI-14). The prompt tags drive the agent picker as intended: a `.csv` opens on "CSV analyst", a
`.log` on "Log triage", and the wrong pairing is refused by name in both directions.

### Checklist addendum -- prompts on S3 files of every type (2026-09-18)

Twenty-six objects in Emily's S3 bucket, one generic prompt, every reader the file chat has:
25 answered, one (parquet) refused by name. Two things changed to make that true: any variable
can now be filled from any object (the object picker + `aiPrompt.json/objectText`), and a file
with no reader by name is read as text when its bytes are text. What is *not* solved: an image
whose content is text -- llava describes it and gets the numbers wrong; OCR is the missing reader.
