# Grooming -- AI prompts in pipelines

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`. Design page with the
wireframes, ER and sequence diagrams: https://claude.ai/artifact/2eopPUECven7kHmHNHFUbt
(private; shared on request). Asked on 2026-09-18: "review `/ai/agents` -- is it generic,
with a prompt? If not, design the page and the workflow, say I want to use the model in a
pipeline."

## What is there (reviewed 2026-09-18)

- `process/src/main/java/process/model/pojo/AiAgent.java` -- one row = provider + endpoint +
  encrypted key + model + `instructions` (system prompt) + `json_mode` + `target_file_types` +
  `tool_uuid`, tenant-scoped, audited.
- `AiAgentServiceImpl.java` -- CRUD, `fetchToolByUuid`, `resolveRuntimeConfig` (decrypts the key
  for a server-side caller), `processAdHoc` (provider/key/prompt in the request body; endpoint
  allow-list against SSRF), `callProvider` → OpenAI / Anthropic / Ollama / AzureOpenAI /
  OpenAI-compatible.
- Consumers: `FileChatServiceImpl` (builds its own prompt, appends the agent's as a preamble),
  `JobAssistantServiceImpl` (builds its own prompt; takes only provider/model/key).
- `scheduler1/next/src/app/features/ai/agents` -- list (table/cards, search, only mine) + one
  flat dialog. 0 agents in every workspace today.

## Verdict

- **Not generic.** Connection and behaviour are one row; the file-chat use case is baked in
  (`target_file_types`). Two agents on one key store it twice.
- **Half a prompt.** A system prompt only: no message template, no `{{variables}}`, no output
  schema, no params, no versions, no run record; both consumers mostly ignore it.
- **Not reachable from a pipeline.** `PipelineField.field_type` is text/textarea/number/url/
  select/checkbox/date; the task payload is XML tags; the worker never calls a model.
- **Keep:** provider dispatch, endpoint allow-list, key encryption, tenant scoping, `tool_uuid`.

## Proposal (see the design page for the screens)

Three concepts instead of one:

1. **Model connection** (`ai_model_connection`): provider, endpoint, key, default model,
   `is_default`, test. Screen: Assistants › Model connections, the Kafka-style rail + pane
   (`features/settings/kafka` pattern). Ollama Models folds into "Test connection → models".
2. **Prompt** (`ai_prompt` + `ai_prompt_variable`, versioned): connection (or default), model,
   system instructions, message template with `{{variables}}`, variables (name/type/required/
   sample), output text|json (+schema), temperature/max tokens. Screen: Assistants › Prompts,
   list + a full-page editor with a **Try it** pane (rendered input, output, tokens, latency).
   "Used by N pipelines"; a prompt a pipeline names refuses delete (the topic rule).
3. **AI step** on a pipeline: `PipelineField.field_type = 'ai'` with `prompt_id`, `variable_map`
   (prompt var ← pipeline field, `as="text"` for a file), `output_tag`, `on_error`
   (fail | continue). Generated payload gains `<ai_step prompt= version= output= on_error=>
   <var name= from=/></ai_step>`. No new screen.

Runtime: worker → `POST aiPrompt.json/run {promptUuid, version, variables, jobQueueId}` with
the per-run callback token (`RunCallbackTokens`) → server loads prompt + connection, decrypts,
renders, calls the provider, validates JSON, writes `ai_prompt_run` (tokens in/out, latency,
status) → `{output, runId, usage}` → worker writes the tag → job history shows the step.
The key never reaches the worker; the version is pinned at dispatch.

Migration: `ai_agent` → one connection per distinct (provider, endpoint, key) + one prompt per
agent (`instructions` as system, template `{{text}}`, file types as a tag). `aiAgent.json/*`
kept as aliases until file chat and the job assistant pick a prompt.

## Cases walked through (2026-09-18, second pass) -- four change the design

1. **The worker may not know `<ai_step>`** (Python consumer, outside these repos). So two
   execution points: **before dispatch** (default -- the server runs steps whose inputs are task
   fields or files in a storage connection and writes the output tags into the payload; the
   worker needs no change) and **in the worker** (opt-in per step, only for topics whose
   profile says the worker runs AI steps). Phase 2 ships the first.
2. **Tampered payload.** The browser never writes `<ai_step>`; the server appends the pipeline's
   steps at dispatch from the definition. The run token is scoped to the prompts in that
   dispatch.
3. **Worker retry after the model answered.** `aiPrompt.json/run` is idempotent on
   `(jobQueueId, stepTag)` -- a second call returns the stored run, no provider call.
4. **A scheduled job with 1,000 files.** Per-connection concurrency cap (default 4, queued),
   retry with backoff on 429/5xx (3 attempts, recorded), and a per-workspace daily token budget
   that fails the step before the call once spent -- budget in phase 1, not phase 3.

Also settled: input past the window → file variable mode (whole | head N | relevant sections,
reusing the file chat's chunker), rendered input stored on the run; no JSON mode on a provider
→ strip fences, validate, one repair round, then `on_error`; chained steps run in field order
and may read an earlier step's tag (forward/circular refs refused at save); an empty required
variable fails before any call; the version pinned at dispatch runs; a connection or prompt in
use refuses delete/deactivation and lists the pipelines.

Console side: the AI step's config opens in the side drawer (the pipeline dialog is full); on
a task it renders as a read-only card, not an input; Try it picks a file sample from the Object
Browser; TENANT_ADMIN writes, TENANT_USER reads; the job history run card shows prompt,
version, tokens, latency, attempts, output preview, rendered input one click away.

## Status

- **Phase 1 delivered 2026-09-18** -- see `execution/README.md` (row "AI prompts in pipelines -- phase 1"). Differences from the plan: a prompt's states are Active/Inactive (no separate Draft; "Save" leaves it Inactive, "Save & activate" makes it Active); the JSON check is `required`/`properties` keys, not a full JSON-schema validator (no library in the build); the runner appends "Answer with a JSON object only, with these keys: …" so a small model answers in shape; the budget is per connection, checked before the call.
- Phase 2 not started.

## Phases

1. V44 tables + migration; Connections screen; Prompts list + editor with Try it; aliases.
2. AI field type in the pipeline editor; `<ai_step>` in the payload; `aiPrompt.json/run`
   behind the run token; worker call + tag; job-history card.
3. Usage on the connection pane; "AI tokens" in Reports; version compare; monthly token cap;
   job assistant on a prompt; retire `aiAgent.json`.

## Open questions

- Who owns the Python worker's `ai_step` handling (it is outside these two repos)?
- Is a per-workspace monthly token cap wanted from phase 1, or is visibility enough first?
- Should a prompt be able to name a *file* variable that the server reads from a storage
  connection itself (so the worker sends a key, not 12k characters of text)?
