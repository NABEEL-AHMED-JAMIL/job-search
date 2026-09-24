# The usage-reporting contract (etl-meter v1)

Who may report usage as whom, what the meter answers, and what it will never do. Three
implementations speak this today:
- the Java reporter every service uses (platform-commons `org.barco.platform.meter.MeterReporter`);
- the Python pipelines' `etl.util.meter.Meter`;
- process's `MeterClient` for reads.

`tests/test_meter_reporting_contract.py` holds one test per clause below. process's
`MeterVerifyRunContractTest` holds the console's side of clause 2. (MIG-190)

## 1. Callers

There are two kinds of caller. Each event records which kind vouched for it, in
`meter.usage_event.vouched_by`, permanently.

| Caller | Sends | May report as |
|---|---|---|
| A **service** (the console, storage-service, media-service, the nightly measurer) | `X-Service-Key` | **any** workspace. The event's `tenantId` is required, and an event without it is rejected by itself. |
| A **run** (a pipeline worker) | `X-Worker-Token` **and** `X-Job-Id` **and** `X-Job-Queue-Id` | **only its own workspace.** The body's `tenantId` and `jobQueueId` are **ignored** in favour of the verified run's own. |

- Neither credential: **401**.
- A token without its `X-Job-Id` / `X-Job-Queue-Id`: **400**.
- A token the console refuses: **401**.
- An unknown service key: **401**.

## 2. The meter never decides whose run it is

For a run, the meter asks the console, `POST {console}/meter.json/verifyRun` with body
`{"jobId", "jobQueueId"}` and header `X-Worker-Token`. The console answers:

- **200**: `{"status":"SUCCESS","message":"Run verified.","data":{"tenantId":…,"jobId":…,"jobQueueId":…}}`. The meter bills `data.tenantId`.
- **401**: `{"status":"ERROR","message":"Unauthorized worker callback."}` for a token that is not this run's live token.
- **401**: `{"status":"ERROR","message":"This run belongs to no workspace."}` for a job with no tenant.

This is Billing's only way to learn a run's tenant. A split must keep it byte for byte, or the meter
mis-bills.

## 3. Reads and the rate card are the service's

The following require a valid `X-Service-Key`:
- `GET /v1/usage`, `/v1/usage/subjects`, `/v1/usage/events`
- `GET /v1/ratecard`, `/v1/ratecards`
- `PUT /v1/ratecard`
- `POST /v1/rollup`

A run token can write usage but can **never** read the ledger, roll it up, or set a rate card:
**401**.

## 4. The key

- The key is compared in constant time (`hmac.compare_digest`).
- An **empty configured key refuses everything**, so the meter fails closed: an unconfigured meter
  takes no service writes and answers no reads.

## 5. A batch

- At most **500** events (`MAX_BATCH`). A 501-event batch is a **422**, and **none** of it is kept.
- An event is refused as part of the whole batch (**422**) when:
  - its `dedupeKey` is missing, empty or longer than **200** characters (`meter.usage_event.dedupe_key varchar(200)`);
  - it is not shaped like an event.
- An event is rejected **by itself**, in the 200 answer's `rejected: [{index, reason}]`, when:
  - its meter is unknown;
  - its quantity is 0;
  - a service's event has no `tenantId`.
- `dedupeKey` is the caller's promise that this exact event is reported once. A repeat is a
  **duplicate**, counted in `duplicates` and never a second row. Keys are built from what the usage
  is about, never from a random value.
- The answer is `{"accepted": n, "duplicates": n, "rejected": [...]}`.

What a client does with each answer (MIG-15):
- The Java reporter parks events it knows would be refused (no usable `dedupeKey`) before sending, so
  one bad event never takes its batch down.
- It parks rejected events and 400/422 batches under its spool's `dead/`, with the reason.
- It spools what it could not deliver, and replays it oldest first.
- The Python client does the same under its own spool.

## 6. Numbers

- Every quantity is `numeric(24,6)`, from the ledger to the invoice line (MIG-197).
- Decimals leave the meter as exact JSON numbers in plain notation, never through a float.

## 7. The open surface

`GET /health` is the **only** route that answers without a credential. There are no generated docs:
no `/docs`, `/redoc` or `/openapi.json`.
