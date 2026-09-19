# Cost & billing

The design is the artifact **https://claude.ai/artifact/NfRLMsexSUHJa5dJvekEHe** (Cost & Billing
Blueprint, 19 Sep 2026): the meters, the separate metering service every pipeline reports to,
the data model, the month-end flow, five screens, the APIs and jobs, roles, three phases, and the
seven open questions. This file records the decisions and what each phase delivered.

## Decisions

| Question | Answer | Where |
|---|---|---|
| Tax | Applied only when the billing account carries a VAT/GST number; otherwise skipped | Phase 2, `billing_account.tax_id` |
| Payments | Manual payment slips uploaded by the workspace and verified by a platform admin; a payment method later | Phase 3 |
| Deleted bytes | Billed at the write rate as data churn (default, revisit) | rate card `storage.bytes.deleted` |
| Model pricing | Flat per-model-family rates on the card (default; provider pass-through later) | `ai.tokens.*` |
| Seats | Every Active user (default) | `seats.user_days` |
| Backfill | None for storage (nothing recorded it); the rest starts at go-live | -- |
| Topics | Counted when *in use* -- an active topic with a live task -- not the whole catalogue | `countTopicsInUse` |

## Phase 1 -- meter and show (done 2026-09-19)

See `execution/README.md`, row "Cost & billing, Phase 1". Service `etl_meter`, client
`etl/util/meter.py`, console `MeterClient` + hooks + `UsageMeasurerCron`, page
`/administration/billing`.

## Phase 2 -- invoice and document (done 2026-09-19)

`billing_account`, `invoice`, `invoice_line`, `billing_document`; the `etl-billing` bucket;
month close → draft → issue (PDF via pdfbox, email); Invoices, Invoice detail (read side),
Documents; the late-usage rule; void; credit note.

## Phase 3 -- pay, verify, analyse (done 2026-09-19, except the rate-card editor)

`payment`; slip upload → verify/reject → receipt; statements; dunning; Billing analytics; the
rate-card editor and per-workspace pins.

## Phase 4 -- the calculation, versioned

The user's rule: an admin can change the billing calculation at any time; bills already issued
keep the calculation they were priced with; new bills use the new one; and the calculation can
differ per workspace.

**The shape.** A *rate card* is one version of the calculation: a name, an effective date, a
currency, an optional workspace, an optional `based_on_version`, a note, and one item per meter.
An item is `unit_price` per `per` units, plus a monthly `included_quantity` (the first N units of
a period are free) and optional `tiers` (`[{from, unit_price}, …]`: graduated bands, each pricing
the units that fall in it). Versions are never edited: a change is a new version, drafted from
an existing one, and only the items in the request need naming -- the rest carry over. The
default card (`tenant_id` null) prices every workspace that has none of its own; a workspace's
card wins for it from its effective date.

**Which card prices a bill.** The card in effect on the first day of the period, for that
workspace (`rate_card_for(period_start, tenant_id)`): a version dated mid-month therefore
applies from the next period, which is the rule a customer can be told. A period is priced as a
whole -- allowance first, then bands -- so `GET /v1/usage?groupBy=meter&tenantId=` answers the
period's lines with `includedQuantity`, `billableQuantity`, `tiers` (the bands applied) and the
`rateCard` it used; by-day figures stay flat (the chart's shape, not the bill).

**Frozen on the invoice.** `invoice.rate_card_version` and `rate_card_name` (V49), and on each
line `included_quantity`, `billable_quantity` and `pricing_detail` (the bands, as JSON). The PDF
and the invoice page show the allowance and each band under the line. A later version cannot
touch an existing bill because nothing about it is recomputed after the draft.

**Who may.** The platform admin lists versions (`billing.json/rateCards`), reads one by number
or the one in effect for a workspace on a day (`rateCard?version=` | `?tenantId=&day=`) and saves
a version (`PUT rateCard`). A tenant admin reads only the card that prices their own workspace
(any `tenantId` asked for is replaced by their own) and is refused the list, versions by number
and the PUT. The editor at `/administration/billing/rates` is platform-only in the nav and the
route guard.

**Screens.** *Rate cards*: tiles (default card today, workspaces on their own card, versions
not yet in effect); the versions list (default / workspace chips, search, "in effect" pill,
based-on); the selected version's items grouped by service with price, allowance and bands, and
"Changed from vN: …". The editor is a wide side panel: name, for (every workspace / one),
effective from (the 1st of next month by default), note, and the eighteen meters with price,
per, included, and tier bands; changed rows are marked. *Cost & usage* names the card that
priced the month ("this workspace's card" when it is one) and shows "N included · M billable"
and the bands. *Invoice* names the card by name and version.

**Not done, by choice.** A percentage discount on the billing account (a workspace card does
it more honestly, line by line); a card's currency other than the account's; a "compare two
versions" view beyond the changed-meter list; deleting a version (never -- an invoice may name
it).
