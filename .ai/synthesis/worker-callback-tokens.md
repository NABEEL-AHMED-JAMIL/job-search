# Synthesis -- `worker-callback-tokens`

Companion to [../grooming/worker-callback-tokens.md](../grooming/worker-callback-tokens.md).
Written 2026-09-17.

## 1. Current → expected

| | Current (to 2026-09-16) | Expected |
|---|---|---|
| Proof on a callback | One `WORKER_CALLBACK_TOKEN` for every worker, tenant and run; app refuses to start without it (`NotifyResetApi` `@PostConstruct`) | A credential that is born at dispatch, good for one run, and dead when the run ends |
| Blast radius of a leak | Every run of every tenant, until a coordinated rotation | One run, for at most the budget |
| Configuration | Same value in `process/.env` and every worker env | None |

## 2. Options weighed

| Option | Why not / why |
|---|---|
| Secret per tenant | Still a standing credential in a worker env; rotation still coordinated per tenant; a tenant's worker could still touch every run of that tenant |
| Secret per user | Same, and a run is not a user's |
| JWT signed by the server, carried in the message | Works, but the server would then need key management and the token is self-describing -- a leaked one is verifiable offline. A random token hashed in the row is simpler and reveals nothing |
| **Per-run random token, hash on the row** (chosen) | No config, no rotation, bounded by the run; the row already exists and dies with the run; one transaction at dispatch, one at retire |

## 3. Gap → solution

| Gap | Solution | Size |
|---|---|---|
| Nowhere to keep a per-run proof | V42: `job_queue.callback_token_hash`, `callback_token_attempt`, `callback_token_expires_at` -- nullable; no new table, no index (PK lookup) | S |
| Nothing mints | `RunCallbackTokens.issue` at dispatch; `JobPayloadDTO.callbackToken/attempt` | S |
| Nothing verifies per run | `RunCallbackTokens.verify`; `NotifyResetApi.rejectIfUntrusted(jobId, jobQueueId, token)` | M |
| A finished run's token lived on | `retire` on accepted terminal change **and** `verify` refuses any terminal run (a UI cancel never passes through retire -- found live, fixed in `2a9ec6c`) | S |
| Old workers break instantly | Legacy path for hash-less rows only, while the variable is set | S |

Redis and OpenSearch: untouched.

## 4. Order (as executed)

`889a09c` schema, service, dispatch, API, tests, docs → `2a9ec6c` refuse tokens of runs that ended without the worker.

## 5. Out of scope

- Teaching the `job-search` Python workers to echo the token (out of phase scope; grooming §6).
- Per-tenant budget; callback base URL in the message; a "callback" state column on the run history screen (proposed, not asked for).

## 6. Open questions

- Should the INFO line that logs the sent message mask `callbackToken` now, before anything ships?
