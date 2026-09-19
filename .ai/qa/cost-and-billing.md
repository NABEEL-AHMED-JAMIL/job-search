# QA — Cost & billing

Companion to `.ai/grooming/cost-and-billing.md` (the decisions) and the design artifact
(https://claude.ai/artifact/NfRLMsexSUHJa5dJvekEHe). Cite findings as **`billing/QA-nn`**.

**Scope of this pass (2026-09-19).** Phase 1 -- the meter service, the pipeline client, the
console's reporting and the Cost & usage page -- run end to end the way the design said it would
be tested (`scratchpad/meter-e2e-full.py`, 18 checks), plus the Playwright journey
(`next/e2e/billing.spec.ts`). Every finding below was found by that run and fixed the same day; the
observation is kept separate from the fix, as `qa/README.md` asks.

## The end-to-end run (18 of 18)

| | Check | Result |
|---|---|---|
| A | N = 4 files of S = 4,096 bytes through a compress-and-delete task: the worker's events are vouched by the run's token; `bytes.deleted = N×S` exactly; `ops.delete = N`; `bytes.read ≥ N×S`; `ops.read ≥ N + 1` (the list); `ops.write = N + 1` (the manifest); worker minutes > 0 reported once; the console reported the run once | PASS |
| B | The run's batch replayed to the meter: all duplicates, nothing accepted, the ledger did not grow | PASS |
| C | `etl_meter` stopped, a run made: the run completed; its batch was spooled on the worker; the meter started, another run made: the spooled batch arrived under its own run with the exact delete count; the spool is empty | PASS |
| D | A file uploaded and deleted from the console by Emily: on the Cost & usage drill-down with its size and her name; the priced month reads back | PASS |

## Findings

### QA-01 · major, fixed 2026-09-19 · A byte meter stored as GB rounded a small write to nothing
**Observed.** The replayed batch (B) came back with eight events *rejected: quantity is 0* -- the
compressed archives (≈40 bytes) and the manifest, stored as `0.000000` GB in `numeric(18,6)`.
A write that happened was a write the meter could not hold. **Fixed.** Byte meters carry bytes
(`unit = byte`) and the rate card prices them per GB (`per = 1073741824`); client, console and
page follow. `job-search` `4a4d1698`, `process` `b2eb34e`, `scheduler1` `18d546a`.

### QA-02 · major, fixed 2026-09-19 · A batch spooled through a meter outage was refused when it arrived
**Observed.** (C) the run completed and spooled as designed; when the next run sent the spool the
meter answered 401 and the worker dropped it: `verifyRun refused for run 6080: NOT_ISSUED`.
`NotifyResetApi` retires a run's token on Completed/Failed by clearing its hash, so nothing could
prove the late batch was that run's -- a lost line on the bill, not a defence, since the
RUN_OVER check already refuses callbacks on a finished run whatever the row carries.
**Fixed.** `retire` keeps the hash and sets the expiry to 24 h; `verifyForReport` is `verify`
without RUN_OVER, and only `/meter.json/verifyRun` uses it. Pinned by `RunCallbackTokensTest`.

### QA-03 · minor, fixed 2026-09-19 · The drill-down said "user #4385"
**Observed.** (D) the delete appeared with the object's name and an id. The design says "who".
**Fixed.** `billing.json/subjects` and `/events` resolve actor ids to names through
`UserNameResolver`; the page shows the name and falls back to the id.

### QA-04 · minor, noted · The archive pipeline's job did not delete its sources
**Observed.** The first exact-quantity run reported no deletes at all: job 2578's task carries no
`delete_source`, and the compress task treats absent as *no*. Not a defect -- the flag is the
task's -- but the design's test needs a task that deletes, so the run now creates "Meter test
(archive + delete)" (task 1654, job 2600) with `delete_source = true`. Left in place.

## Not exercised
Transcript minutes (the audio service reports no duration), analytics bytes scanned, a spool
older than a day, two workers reporting the same run, a rate-card change from the console (no
editor until Phase 3), the nightly cron firing on its own (the measurer was run by hand through
`billing.json/measure`), a platform admin on the page in Playwright (unit-tested only).
