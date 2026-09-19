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

### QA-05 · fixed · A price of 0.045 read as "$0.05"
**Observed.** The first version saved through the editor set model tokens at 0.045 / 1k and the
list showed "$0.05 / 1,000 per token" -- the pages chose two decimals for anything at or above a
cent. **Fixed.** `priceDigits()` in `billing.service.ts`: as many decimals as the price has, two
at least, six at most; shared by Cost & usage, the invoice page and Rate cards.

### QA-06 · fixed · The invoice API did not carry the card's name
**Observed.** `rateCardName` was written on the draft but the invoice row left it out, so the
Phase 4 run's fourth check failed with a KeyError. **Fixed.** `invoiceRow` in `BillingRestApi`.

## Phase 4 run (`scratchpad/ratecards-e2e.py`, 17/17)
The platform lists versions and Emily cannot; Emily reads the card that prices her workspace
and gets her own whatever `tenantId` she asks for; a draft names the card that priced it; the
bill is issued (frozen); a nameless version is refused, Emily's PUT is refused; a new default
version with one changed item carries the other seventeen over; the issued bill still names the
old version and total; a new draft is priced with the new version, its seats line carries
`includedQuantity 5`, `billableQuantity 3`, one band, and the amount follows them; a card of
CareBridge's own puts CareBridge on it and leaves MedAxis on the default; CareBridge's usage
names its card as `tenantSpecific`; the list names the workspace; the issued PDF names the card
and shows "at no charge" and the band. Playwright `e2e/rate-cards.spec.ts` (2): the editor saves
a version that is listed with "Changed from vN: Images described" and prices only from next
month; the tenant admin is off the page and refused the API.

### QA-07 · fixed · The invoice PDF's "Rate card" label ran under a long card name
**Observed.** `rightPair` put the label at a fixed 130 pt left of the margin; "Seats: 5 free,
then tiered (run 2) v3" is wider. **Fixed.** The label sits left of the value's measured width.

### QA-08 · fixed · Cost & usage and Billing analytics tiles stacked one per row
**Observed.** Both used a `stat-grid` class that no stylesheet defines. **Fixed.** The
`grid grid-cols-2 md:grid-cols-4 gap-3` the other screens use.

### QA-09 · fixed · Billing analytics called workspaces without an invoice "Workspace 2901"
**Observed.** Names came from the invoiced-tenant rows only. **Fixed.** The workspace list
names them.

## Redesign run (19 Sep)
`scratchpad/qr-e2e.py` 4/4 (a fresh invoice's PDF and PNG; Emily scoped to her own; unknown
number 404); Playwright `e2e/invoices.spec.ts` (deep link, QR image loaded, tenant admin has no
Issue, rail pick changes the address, the document reads in the pdf.js viewer; the platform head
drafts), `e2e/billing.spec.ts`, `e2e/rate-cards.spec.ts` -- 5/5. Suites Java 1770, UI 1638.

## Calculation review (19 Sep, second pass)
Read: `rates.price`, `rates.price_item`, both stores' `rollup` and `rate_card_for`, `app._priced_period`
and the dirty-day marking on a saved card; `BillingService.total`, `settle`, `creditNote`,
`verifyPayment`, `analytics`, `statement`; the usage page's forecast, yesterday, seats, storage
and by-service figures. Rounding is consistent (5 dp on lines, 2 dp on totals, HALF_UP); byte
meters price per GB with the card's `per`; a period is priced with the card of its first day and
a mid-month card applies from the next period; a saved card marks the right days stale.

### QA-10 · fixed · A credit note against a partly paid bill could exceed what was owed
**Observed.** The cap was total minus credits: 100 billed, 80 paid, a 50 credit was accepted,
applied as a payment, and the bill went "paid" with 30 owed to the customer and no record of it.
**Fixed.** On an open bill a credit is capped at the balance; on a paid bill it is a refund note
capped at what was billed and not yet credited, applied to nothing (the bill stays paid, the
note stands on its own). `aCreditOnAPaidBillIsARefundOwedAndNeverCountsAsCollected`.

### QA-11 · fixed · "Collected" in analytics counted credit notes as money
**Observed.** Collected was `total - balance` per row: a credit applied to a bill counted as
collected on the bill, and the note's own negative total counted as negative collected -- 71 %
"collected" on the analytics page was one credit note. **Fixed.** Collected = verified payments
that were money (`moneyPaidOn`); a credit note row collects nothing; invoiced stays net of
credits. The invoice pane now shows *paid* and *credited* as two figures.

### QA-12 · fixed · The forecast paced the month at the last seven *rows*, not the last seven days
**Observed.** One burst day of $5.16 became a $5.16/day pace and a $59 forecast on a $2.66
month; "yesterday" was the second-to-last row, whichever day that was. **Fixed.** Seven calendar
days back from today, quiet days counting as zero; yesterday by date.

### QA-13 · fixed · "Storage kept" averaged over the days elapsed, not the nights measured
**Observed.** One night measured in a 19-day month showed 46 KB for 879 KB kept. **Fixed.**
Averaged over the nights the measurer ran, and the foot says how many.

## Not exercised
Transcript minutes (the audio service reports no duration), analytics bytes scanned, a spool
older than a day, two workers reporting the same run, the nightly cron firing on its own (the
measurer was run by hand through `billing.json/measure`), two tiers on a byte meter, a workspace
card dated before the default it is drafted from.
