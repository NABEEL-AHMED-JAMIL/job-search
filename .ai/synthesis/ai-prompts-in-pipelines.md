# Synthesis -- AI prompts in pipelines

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`. Grooming:
`grooming/ai-prompts-in-pipelines.md`. Design page (wireframes, ER, sequence, cases):
https://claude.ai/artifact/2eopPUECven7kHmHNHFUbt. Delivered 2026-09-18 in two phases; this is
what exists now and why it is shaped this way.

## 1. Summary

An "AI agent" was one row bundling a provider connection with one fixed prompt, reachable from
nowhere but the file chat. It is now three things: a **model connection** (where prompts run),
a **prompt** (what is said, with `{{variables}}` and an expected output, versioned), and an
**AI step** on a pipeline (which prompt, fed from which fields, writing to which tag). A step
runs on the server before each dispatch, so the worker receives an ordinary tag and needs no
change; every call is a row with its tokens and time.

## 2. The model

| Table | Holds | Notes |
|---|---|---|
| `ai_model_connection` (V44) | tenant, name, provider, api_endpoint, api_key (encrypted), default_model, is_default, max_concurrency, daily_token_budget, status, last test + models listed | one default per workspace; the first connection a workspace makes becomes it |
| `ai_prompt` (V44) | prompt_uuid, tenant, name, connection_id (null = default), model (null = connection default), system_instructions, user_template, variables (JSON), output_mode text\|json, output_schema, temperature, max_tokens, tags, version, status | Inactive until "Save & activate"; every save bumps `version` |
| `ai_prompt_version` (V44) | the snapshot per version | what a run pinned to that version sent |
| `ai_prompt_run` (V44) | kind try\|run, job_queue_id, step_tag, rendered_input, output, tokens, latency, attempts, status, error | unique on (job_queue_id, step_tag): a retried dispatch reuses the answer |
| `pipeline_field` (V45) | + prompt_id, variable_map (JSON {var: sourceTag}), on_error fail\|continue | `field_type = 'ai'` |
| `lookup_data` (V46) | AI_PROVIDER family removed | providers are a fixed set the console carries |

Page grants `ai-agents` → `ai-prompts` (V44). `ai_agent` stays in place, unread.

## 3. Backend (`process`)

- `process/ai/AiProviderGateway` -- the one place that speaks to a provider (OpenAI, Anthropic,
  Ollama, AzureOpenAI, OpenAI-compatible), returns text + usage, lists models for a test.
- `process/ai/AiEndpointPolicy` -- the endpoint allow-list (public https, or a named host).
- `process/ai/PromptRunner` -- render (refuse an empty required variable before any call),
  budget check before the call, per-connection semaphore (`max_concurrency`), 429/5xx retry ×3
  with backoff, "Answer with a JSON object only, with these keys: …" appended for JSON output,
  one repair round, the run row (tokens counted on failure too).
- `process/ai/AiStepService` + `PayloadXml` -- at dispatch (`ProducerBulkEngine.pushMessageToQueue`)
  runs a pipeline's AI steps in position order with the job's tenant (no TenantContext on the
  scheduler thread), writes each answer as the step's tag through the XML parser (escaped, not
  concatenated), fails the run or leaves the tag empty per `on_error`, writes an audit line per
  step. Idempotent per (job queue, tag).
- APIs: `aiConnection.json/{list,save,setDefault,test,delete}` (TENANT_ADMIN);
  `aiPrompt.json/{list,get,runs,runsForJob,versions}` (TENANT_USER) and
  `{save,setStatus,delete,try}` (TENANT_ADMIN); `aiAgent.json` reads answer from prompts so the
  file chat and job assistant are unchanged; its writes are gone.
- Guards: a connection prompts name, or the default prompts rely on, cannot be deleted; a prompt
  a live pipeline runs cannot be deactivated or deleted; a pipeline save checks the step's prompt
  (own workspace, active) and its variable map (every required variable reads a field above).

## 4. Console (`scheduler1/next`)

- Assistants › **Model connections** (`features/ai/connections`, admin): Kafka-style rail + pane;
  Test connection lists the provider's models; today's spend against the budget; 30-day usage.
- Assistants › **Prompts** (`features/ai/prompts`): list ("Used by N pipelines"); full-page
  editor with the Try it pane; a placeholder typed into the template adds its variable row; a
  missing row blocks save and try.
- Configuration › Pipelines: field type "AI prompt (runs before dispatch)"; its configuration
  (`ai-step-panel.ts`) opens in the shared side drawer.
- Source Tasks › task editor: an AI step is a read-only card, never an input.
- Run logs: "AI steps" card per run.
- Access profiles: key `ai-prompts` "Prompts" under Assistants; `/ai/agents`, `/ai/models`
  redirect. Docs page section "Let a model do part of the work"; landing names it.

## 5. What is deliberately not there

- Worker-side steps (`<ai_step>` in the payload for a step that must run after the worker has
  produced something). The server-side step covers inputs the task carries; the worker-side
  contract (`aiPrompt.json/run` behind the per-run token) waits for the worker's owner.
- A full JSON-schema validator: the check is `required` / `properties` keys.
- A file variable read from a storage connection by the server (a `file` type exists on a
  variable, but a step maps it to a field's text today).
- Per-workspace monthly caps and an "AI tokens" measure on Reports (phase 3).

## 6. Tests

Backend: `AiEndpointPolicyTest` 8, `AiProviderGatewayTest` 4, `PromptRunnerTest` 5,
`AiAgentAliasTest` 3, `AiStepServiceTest` 5, `PipelineAiStepTest` 4, `TopicsForProfileTest` 8.
Frontend: `prompt-edit.spec.ts` 4. E2E: `ai-prompts.spec.ts` (connection → prompt tried → AI
step → task → run carries the answer, 56 s against the local Ollama).
