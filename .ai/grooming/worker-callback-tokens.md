# Grooming -- `worker-callback-tokens`

Backend-only; no feature row of its own in `features.md` (it is listed under **§3 New in the
rewrite**). Groomed after the fact on 2026-09-17. Engineer's reference:
`process/ext-detail/md/WORKER_CALLBACK_TOKENS.md`.

## 1. Purpose

The worker callbacks -- `/changeState`, `/addLogs`, `/addLogsBatch` -- sit outside the JWT chain
(`SecurityConfig` permits them). Until 2026-09-17 the only proof a caller was a worker was
`WORKER_CALLBACK_TOKEN`: one shared secret in every worker's environment, for every tenant, for
ever. Anyone holding it could mark any run Failed or append log lines to it, and rotating it meant
redeploying every worker at once. Per-tenant or per-user secrets would only have shrunk the blast
radius; they would still be standing credentials living in worker environments.

## 2. Current behaviour (as built)

| Step | Where | What |
|---|---|---|
| Dispatch | `process/src/main/java/process/engine/ProducerBulkEngine.java:491` → `security/RunCallbackTokens.issue` (`:80`) | Mints `cbt_<attempt>.<jobQueueId>.<32 random bytes, base64url>`; stores **only the SHA-256** plus attempt and expiry (`now + worker.callback.budget-hours`, default 24) on the `job_queue` row (V42); puts the token in the Kafka message as `callbackToken` with `attempt`. Saved before the send |
| Callback | `api/NotifyResetApi.java:54` → `RunCallbackTokens.verify` (`:97`) | Looks the run up; refuses if the job id does not match, the run is already over (Failed/Completed/Skip/Interrupt/Missed, however it got there), no token was issued, it expired, or the hash mismatches (constant-time). Every refusal is the same `401 Unauthorized worker callback.`; the reason is logged only |
| Retry | dispatch again | Re-mints; the previous attempt's token stops working |
| End of run | `NotifyResetApi.changeState` → `RunCallbackTokens.retire` (`:131`) | On an accepted Failed/Completed, clears hash and expiry |
| Legacy | `worker.callback.token` | Honoured **only** for a run with no hash (dispatched before V42) and only while set. Startup no longer requires it |

## 3. Requirements

1. A token is good for exactly one run and attempt; nothing to distribute, nothing to rotate.
2. A finished run's token is dead whoever ended the run -- worker, UI cancel, dispatcher.
3. The token itself is never stored server-side; a database dump yields hashes only.
4. Refusals do not tell a caller which check failed.
5. Existing workers keep working through the legacy secret until they echo the run token.

## 4. Worker contract

Read `callbackToken` from the run message; send it back unchanged as `X-Worker-Token` on every
callback for that run; report `Running` before `Failed`/`Completed` (the state machine refuses
`Start → Completed`). Do not persist it beyond the run. The `job-search` Python workers are out
of scope this phase and still send the shared secret -- which the legacy path accepts only for
runs that carry no hash, i.e. **not for runs dispatched after V42**. See §6.

## 5. Acceptance (verified live 2026-09-17, MedAxis job 2422 / runs 5710–5713, Default job 2423 / run 5712)

| Presented | Result |
|---|---|
| no header / wrong token / legacy secret on a tokened run / right token with the wrong `jobId` | 401 |
| right token: `addLogs`, `addLogsBatch`, `Running`, `Completed` | 200; hash cleared after `Completed` |
| same token replayed after `Completed`; token of a run cancelled from the UI; token of another run | 401 |
| run with no hash + legacy secret | 200 (fallback) |

Tests: `RunCallbackTokensTest` (10), `NotifyResetApiTest` (8).

## 6. Known issues / open

- **The live Python workers do not echo the run token yet.** A run they pick up after V42 carries a hash, so their shared-secret callbacks are refused and the run sits at `Start` until the budget expires. This is the intended end state for the future Java worker; for the Python ones it is a migration step that has to happen before the next real run through them. Out of this phase's scope, recorded here so it is not a surprise.
- `ProducerBulkEngine` logs the full message it sent at INFO, token included. Mask before production.
- The message does not carry the callback base URL; a tenant-owned pipeline has to be told it.
- Budget is global, not per tenant.
