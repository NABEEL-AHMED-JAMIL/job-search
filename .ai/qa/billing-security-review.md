# Billing, QR and meter -- engineering and security review (19 Sep 2026)

Scope: the billing surface end to end (`billing.json/*`, `meter.json/verifyRun`, the meter
service, the five billing screens), read against the Lookups / Kafka patterns, plus the
cross-cutting pieces every request passes through (JWT filter, `GlobalExceptionHandler`, CORS,
headers). Probed live on the local stack only (`scratchpad/billing-sec-probe.py`, 57 checks:
tenant isolation from MedAxis to CareBridge, role gates for tenant admin / tenant user /
anonymous / garbage token, input abuse, upload abuse, QR abuse, the meter's key and run token).

## Held before the review
Tenant isolation on every billing read and write (invoice by number, document bytes, QR,
`?tenantId=` on invoices/documents/usage/subjects/account/statement, payment against another
workspace's invoice, account body with a foreign `tenantId`); every platform action refused to a
tenant admin (issue, void, credit note, line, draft, verify, analytics, close month, measure,
rate cards); a tenant user refused everything; anonymous and forged tokens 401; HTML in a
description stored as text and rendered escaped; SQL-looking input is just text; the meter
refuses no key, a wrong key and a forged run token.

## Found and fixed

| # | Severity | Issue | Fix | Test |
|---|---|---|---|---|
| 1 | **High** | A credit note for any amount was accepted -- 99,999 against a 3.19 invoice flipped it to paid and put the balance below zero. | `creditNote` refuses more than total minus what was already credited; a credit note itself can neither be credited nor paid against. | `BillingServiceTest` (credit cap, kind) · probe |
| 2 | Medium | A payment slip could promise any amount (10× the balance), two slips could together exceed it, and a slip could be filed against a credit note. | Amount ≤ balance − slips awaiting verification; kind must be invoice; method from a fixed list; reference/note lengths. | `BillingServiceTest` · probe |
| 3 | Medium | A manual line took a zero or negative quantity, an absurd price, and a description longer than the column (Hibernate's message came back to the client). | quantity > 0, |price| ≤ 1,000,000, description 1..300 (a negative price stays -- a discount line). | `BillingServiceTest` · probe |
| 4 | Medium | A draft could be built for a tenant id that does not exist. | `draft` checks the workspace exists. | `BillingServiceTest` |
| 5 | **High** | The payment slip was stored under the browser's content type and served back `inline` -- a `text/html` "slip" would have been rendered from the API origin. No size cap (the global multipart limit is 500 MB). | The bytes decide: PDF / PNG / JPEG by magic number or refused; 10 MB cap; a safe file name (no traversal, no leading dot, the sniffed extension); `X-Content-Type-Options: nosniff` on document and QR responses. | `BillingServiceTest.aSlipIsWhatItsBytesSayItIs` · probe (HTML, fake PNG, 12 MB, traversal name) |
| 6 | Medium | Internal exception text reached clients: `could not execute statement; SQL [n/a]…`, `Unable to obtain YearMonth from TemporalAccessor…`, `Failed to convert value of type 'java.lang.String'…`. | `BillingRestApi.refused(what, ex)`: only `IllegalArgument`/`IllegalState`/date-parse messages are repeated, the rest logged and answered in one sentence; `GlobalExceptionHandler` answers a type mismatch with "The value of 'x' is not valid." (400) and never repeats a 5xx message. | `GlobalExceptionHandlerTest` · probe |
| 7 | Low | `/invoice?number=%00` reached the database and 500ed. | The number's format is checked first (`[A-Z]{2,3}-\d{4}-\d{2}-\d{4}`), for `/invoice` and `/invoice/qr`. | probe |
| 8 | Low | The meter compared the service key with `!=`. | `hmac.compare_digest`. | `test_meter_service` |
| 9 | Medium | The UI's nginx sent no browser guards. | `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy` on every response (repeated in the locations that set Cache-Control, since `add_header` does not inherit). | `curl -I` |
| 10 | Low | One `err: any` in `invoices.ts`. | `HttpErrorResponse`. | build |

## Found, not changed here (recommendations)

| Severity | Issue | Where | Recommendation |
|---|---|---|---|
| High | No rate limiting anywhere: `/auth.json/login`, `/auth.json/refresh`, `/tenantRequest.json/submit`, the billing writes. Brute force and slip-upload floods are only bounded by the server. | `SecurityConfig`, all controllers | A filter with a per-IP and per-account bucket (bucket4j or a Redis counter -- Redis is already configured) on login/refresh/submit first; a per-user bucket on `billing.json` writes. Lock an account after N failed logins with a cooldown. |
| Medium | `@CrossOrigin(origins = "*")` on all 47 controllers. Low risk today (JWT in a header, no cookies, so `*` cannot carry credentials), but it is 47 places to forget and it names no trusted origin. | every `*RestApi` | One `CorsConfigurationSource` bean from `app.allowed-origins` (the WebSocket config already reads such a list) and remove the annotations. |
| Medium | No `Content-Security-Policy` and no HSTS on the UI. | `nginx.conf` | Try `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' fonts.googleapis.com; font-src fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self' <api> <ws>; worker-src 'self' blob:; frame-ancestors 'none'` in report-only first; HSTS at the TLS terminator. |
| Medium | Access and refresh tokens live in `localStorage` (`etl_auth_user`). Readable by any script on the origin; the CSP above is the mitigation without changing the auth model. | `core/auth` | Keep, with CSP; or move the refresh token to an httpOnly cookie with CSRF protection -- a larger change. |
| Low | `window.prompt` for a void reason and a rejection note (also in file chat and report destination). | `invoice-detail.ts` | An inline reason form like the credit-note form, when the pattern is retired everywhere. |
| Low | `GET billing.json/document` streams the object; a very large statement is held in memory as `byte[]` when made. | `BillingService.statement` | Fine at these sizes; stream to the bucket if statements grow. |
| Info | The billing API is action-style (`/invoice/issue`, `/payment/verify`) rather than resource REST. | `BillingRestApi` | It matches every other controller in the console (`setStatus`, `setDefault`, `renameQuery`); changing one module would make it the odd one out. |
| Info | Kafka: profiles are per tenant (`KafkaConnectionResolver.resolve(tenantId, taskTypeId)` only returns a profile the tenant owns or a platform default), secrets encrypted at rest and never returned, TLS/SASL per profile, topics belong to the profile they were added under. Consumers are the pipelines' own (`job-search`), reporting back under the run's token. Not re-tested in this pass. | `config/KafkaConnectionResolver`, `features/settings/kafka` | The Kafka IT matrix (`./run-kafka-matrix.sh`) remains the test of record. |
| Info | Lookups: tenant-scoped rows, encrypted values never echoed (`af4ed12`), the rail + pane pattern the billing screens now follow. | `features/settings/lookup` | -- |

## Verified after the changes
`billing-sec-probe.py` 57/57; suites Java 1774, UI 1638, Python 92; Playwright billing 5/5.
Test data left in place: CareBridge draft/issued invoices from the probe, CN-2026-09-0002 (a
99,999 credit note issued *before* the fix against INV-2026-09-0004 -- it is what the fix
prevents; void or delete it), payment slips of 0.01 and 1.00 against INV-2026-09-0004/-0005.
