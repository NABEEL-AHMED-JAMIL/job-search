# Regex, constants and reusable patterns -- placement review (19 Sep 2026)

Scanned: every `Pattern.compile` / `matches` / `replaceAll` in the console, every string state
and number literal in billing and metering, every `Intl.NumberFormat` / byte / day literal in the
UI's billing feature, regex literals across UI components, the meter service's seed. Placed by
the rule "what is it, who uses it, what scope, which layer owns it"; kept local what is used
once and reads as itself.

## Moved

| What | Was | Now | Why |
|---|---|---|---|
| Invoice statuses `draft/issued/partially_paid/paid/overdue/void` | `static final String` in `BillingService`; literals in tests | `process.model.enums.InvoiceStatus` (`value()`, `is()`, `isOpen()`, `isCreditable()`, `values(...)`) | A fixed business state -- an enum, in the package every other state lives in. Column stays a string; `value()` is stored. |
| Invoice kinds `invoice/credit_note` and their number prefixes `INV/CN` | literals in `BillingService`, API, cron | `InvoiceKind` (`value()`, `numberPrefix()`) | One place says a credit note is `CN-`. |
| Payment statuses `submitted/verified/rejected` | literals | `PaymentStatus` | Fixed state. |
| Payment methods `bank/card/cash/manual` + the console's own `credit_note` | `Arrays.asList` in the service, `<option>`s in the UI template | `PaymentMethod` (`chosen()`, `chosenList()`); UI `PAYMENT_METHODS` in `billing.service.ts` | A fixed set, offered and validated from the same list on each side. |
| Document kinds `invoice/credit_note/receipt/statement/payment_slip` + prefixes `RCP/STM` | literals | `BillingDocumentKind`; UI `DOCUMENT_KINDS` | Fixed set; `store()` now takes the enum. |
| Invoice-number format regex + `INV-yyyy-MM-nnnn` building | a `Pattern` in `BillingRestApi`, `String.format` in `BillingService` | `process.billing.BillingNumber` (`isValid`, `base`, `format`) | A domain-specific validator, owned by billing, used by the API and the service. |
| QR size default/min/max `160/64/1024` | literals in the controller | `InvoiceQr.DEFAULT_SIZE/MIN_SIZE/MAX_SIZE`, `sizeOf(requested)` | The renderer owns its bounds; the controller passes what it was asked. |
| Meter keys `storage.bytes.deleted`, … and their units | 17 string pairs across 7 classes | `process.billing.Meter` enum (`key()`, `unit()`); `UsageEvent.of(tenant, Meter, qty, dedupe)` | A cross-service contract with the meter's rate card; a name and a unit can no longer be paired by hand. |
| Hours per day `24` in the nightly measurer | literal ×2 | `UsageMeasurerCron.HOURS_PER_DAY` | Reads as itself. |
| E-mail regex | two different patterns in `TenantRequestServiceImpl` and `FileShareServiceImpl` | `process.util.validation.EmailValidator.isValid` | Duplicate, and they disagreed. |
| Tenant code from a name | two slugifiers (`TenantServiceImpl`, `TenantRequestServiceImpl`) | `process.util.TenantCode.from` | One rule for the same field. |
| Money, unit price, price digits, bytes, quantities, days overdue, month arithmetic | six copies across `billing.ts`, `invoice-detail.ts`, `invoices.ts`, `documents.ts`, `rate-cards.ts`, `billing-analytics.ts` | `features/billing/billing-format.ts` (`formatMoney`, `formatMoneyRound`, `priceDigits`, `formatUnitPrice`, `formatBytes`, `formatGb`, `formatQuantity`, `daysOverdue`, `firstOfMonth`, `daysInMonth`, `yearMonth`, `BYTES_PER_GB`, `HOURS_PER_DAY`, `MS_PER_DAY`) | Feature-level shared helpers; the byte style was two different ones ("122.00 GB" vs "122 GB"). |
| `billing.json/usage`, `/subjects`, `/refresh` and `tenant.json/listTenants` called from the Cost & usage component | `HttpClient` + `API_BASE` in the component | `BillingApi.usageByMeter/usageByDay/subjects/refreshUsage` with a `UsageQuery`; the workspace list from `WorkspacePicker` like the other billing pages | Component → service → HTTP, the module's own pattern; the picker was duplicated. |
| `MeterLine`, `PricedWith`, `DayRow`, `SubjectRow`, `SERVICES`, `INVOICE_STATUSES` | in the component | `billing.service.ts` beside the other API models and label maps | API models next to the API. |
| `25` subjects, `7`-day forecast window | literals | `SUBJECTS_SHOWN`, `FORECAST_WINDOW_DAYS` in `billing.ts` | Local, but not obvious without a name. |
| `1073741824` in the meter's seed | literal ×3 | `rates.BYTES_PER_GB` | Reads as itself. |

## Kept local, on purpose
`TextCleanerUtil`, `StatementGate`, `FilterCompiler`, `ReportExportServiceImpl` (`FORMULA_LEAD`),
`KafkaTopicPartitionUtil`, `KafkaSecretPath`, `AnalyticsQueryLibraryServiceImpl.LOCATION`,
`PipelineServiceImpl.WHITESPACE`, `AiPromptServiceImpl` variable-name check,
`StorageConnectionServiceImpl` alias check, `KafkaConnectionProfileServiceImpl` broker host check,
`QueryService` date check -- each a single-use rule of the class it sits in, already a named
`Pattern` where compiled. `BillingService`'s `DESCRIPTION_MAX`, `NOTE_MAX`, `REFERENCE_MAX`,
`UNIT_PRICE_MAX`, `QUANTITY_MAX`, `SLIP_MAX_BYTES` stay in the service that enforces them (the
column widths they mirror are in V48). UI regexes (`users.ts` phone digits, `tenants.ts`
plurals, `reports.ts` reason keys, `analytics.ts` trailing zeros) are one-off string massaging.
Cron expressions, the meter URL and key, the config bucket, JWT lifetimes are already
properties.

## Left as they are, noted
- 44 UI components call `HttpClient` directly with `${API_BASE}/x.json/...` -- the app's
  established pattern (Lookups, Kafka, Users, Tenants all do it). Billing has a service; the
  rest was not moved in this pass. A `TenantApi.listTenants()` would remove ten copies of one call.
- `tenant-dialog.ts` slugifies a name with the same rule as `TenantCode` and validates with
  `^[a-z0-9][a-z0-9._-]*$`, looser than the server's normalisation (`.` and `_` become `-`). Harmless
  (the server normalises), but the pattern could match the server's.
- `86_400_000` appears in `profile.ts`, `reports.ts`, `objects.ts`, `day-series.ts` (named there).
  A `shared/time.ts` `MS_PER_DAY` would take four literals; billing's own is in `billing-format.ts`.

## Verified
Java 1774, UI 1642 (`billing-format.spec.ts` +4), Python 92; live `billing-sec-probe.py` 57/57,
`ratecards-e2e.py` 17/17, Playwright billing 5/5.
