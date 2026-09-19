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

## Phase 4 -- the calculation (in progress)

The user's rule: an admin can change the billing calculation at any time; bills already issued
keep the calculation they were priced with; new bills use the new one; and the calculation can
differ per workspace. The generic shape: versioned rate cards with an effective date, a card per
workspace where one is assigned (else the default), per-line calculation (price per N units, a
monthly included allowance, graduated tiers), a period priced with the card in effect at its
start, and every invoice frozen to the version, the name and every line's rate. An editor at
`/administration/billing/rates`.
