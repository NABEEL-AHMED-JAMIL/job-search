# Verification record — Analytics Studio, phase one

**This file sits in `qa/` and is not a QA pass. Read that sentence twice before citing anything
below as tested.**

`.ai/qa/README.md` describes a phase: use the feature as a user, as each role, on both themes, at a
narrow width, against the acceptance criteria in `grooming/<feature>.md`, recording rather than
fixing. None of that happened here. What happened is that Analytics Studio phase one was designed,
built and deployed on **2026-09-08**, and while it was being built its author exercised it — through
a probe against the running API and through the browser against the running UI, both on the dev
stack against MinIO. Those checks are worth keeping, because they are real observations against a
real engine and a real object store, and because they are the only evidence the feature has. They
are recorded here so that the next person can see exactly what was and was not looked at.

They are not a QA pass, and the difference is not a formality:

- **Every observation was made by the person who wrote the code.** That is the specific bias the QA
  phase exists to remove. Someone checking their own work checks the paths they built, in the order
  they built them, and confirms what they already expect. Five refusals were walked below and all
  five refused — but they are the five refusals the author had just written, which is a different
  claim from "the refusals hold".
- **There was no checklist.** The other files in this directory mark acceptance criteria from a
  grooming document; there was no criteria list in front of the person doing the checking, so
  nothing here can be reported as a criterion passed. When `grooming/analytics-studio.md` carries
  one, that list is what a real pass marks, and this record is an input to it, not a substitute.
- **One role, one workspace, one browser, one theme sweep by eye.** No second tenant, no negative
  control, no refused role, no narrow viewport.

**Numbering.** No `QA-nn` numbers are issued by this file, because nothing in it is a finding: the
verification produced no defect entries. The project's continuous sequence therefore still stands at
`QA-35` (`qa/source-jobs.md`), and the next real pass continues at **`QA-36`**. The file-local set in
`qa/reports.md` is cited as `reports/QA-nn` and is unaffected.

**A note on what the screen looked like.** The verification was done against a dataset pane with
three tabs — Overview, Data and Schema. The component was still being edited the same day:
`scheduler1/next/src/app/features/analytics/analytics.ts` now types its tabs as
`'overview' | 'data'` and the columns have moved into a rail beside the rows, on the reasoning that
"what type is this column" is asked while looking at the values in it. The observations below are
about the data on the screen rather than its furniture, but a reader who opens the screen and finds
two tabs is looking at something later than this record, not at a contradiction of it.

---

## What phase one is, so a pass does not go looking for the rest

Analytics Studio reads a file **where it already lives** in object storage, using DuckDB as an
embedded query engine. Nothing is copied into Postgres. The user picks a storage connection, walks
folders, clicks a file, and gets an overview, the rows and the schema. A whole folder can be read as
one dataset by pattern.

Deliberately **not built**, and therefore not testable, not broken, and not to be reported as
missing:

| Not in phase one | Where it is meant to go |
|---|---|
| User-written SQL | phase three — and it is why the session lock-down and the governor were built first |
| Profiling, data quality | phase two |
| Charts, dashboards | phases four and five |
| Saved queries, query history, benchmarks | later phases |
| Any database table at all | nothing is persisted; a selection lives in the component and dies with it |
| Caching | schema and row counts are recomputed per request |
| Kafka events, audit-log entries for a dataset read | the specification asked for both; neither is built |
| Monaco, or any SQL editor | not in the project; the editor decision is open |

The surface that exists is two endpoints (`process/api/AnalyticsRestApi.java`):

```
GET /analytics.json/schema   ?connection=<alias>&path=<path>
GET /analytics.json/preview  ?connection=<alias>&path=<path>&page=0&pageSize=<optional>
```

Both `@PreAuthorize("hasRole('TENANT_USER')")` at class level (`AnalyticsRestApi.java:43`), matching
the Object Browser they read from. Business failures are **HTTP 200 with a `ResponseDto` of status
`ERROR`** (`:74`, `:101`), per house convention — which matters to whoever automates against this
later, because a refusal is not an HTTP failure and a test asserting a 4xx will pass for the wrong
reason.

The property worth restating wherever this API is described: **the caller names a connection and a
path inside it, never a bucket and never a URL.** The bucket comes from the `StorageConnection`
record — `getBucketName()`, falling back to the alias, which is what `StorageBrowserServiceImpl` does
(`DatasetResolver.java:91-93`, `StorageBrowserServiceImpl.java:544-546`). "Use these credentials
against a different bucket" is not a request this API can express.

---

## Fixtures

The dev stack's own MinIO. `sales.csv`; a Parquet file; and three CSV partition files under
`etl-demo/F768945/out/` — named for the ETL pipeline added earlier the same day, and documented with
that work rather than here; it is mentioned only because it is where the multi-file fixture came
from.

This record does not say which of those were made for the purpose and which were left behind by
other work, and none of them should be assumed to still be there. A real pass should expect to
provide its own fixtures, and will need several this one never had — see the last section.

---

## What was observed

Through the real API and the real UI, on 2026-09-08. Everything in this table is an observation;
nothing in it is a criterion, because there were no criteria.

| # | What was done | What was seen |
|---|---|---|
| 1 | Opened `sales.csv` from the MinIO connection | 7 rows, 4 columns, format CSV |
| 2 | Read its schema | `region`, `rep`, `product` as `VARCHAR`; `amount` as `DOUBLE` |
| 3 | Read a folder of three partition files as **one** dataset by pattern | one dataset, 7 rows, **5** columns — the fifth being the filename column DuckDB adds — with each row carrying `s3://etl-bucket/etl-demo/F768945/out/<file>.csv` |
| 4 | Opened a Parquet file | schema and rows both read |
| 5 | Walked five refusal paths | each returned a friendly `ERROR`; no stack trace reached the screen |
| 6 | Asked for the absolute path `/etc/passwd.csv` | confined inside the connection's own bucket, **and** separately with no local filesystem to reach |
| 7 | Looked at the screen in dark mode | correct; no page overflow; no console errors |

### The refusals (observation 5)

Four of the five messages are recorded verbatim. Each is quoted below beside the code that produces
it, so a later reader can tell an intended refusal from a coincidence:

> A dataset path cannot contain "..".

`DatasetResolver.java:71` — checked **after** the allow-list rather than instead of it, because `..`
is made entirely of permitted characters.

> That path contains characters this reader does not accept.

`DatasetResolver.java:66`, from the allow-list `[A-Za-z0-9._*?/=+ -]+` at `:36`. Notably absent from
that class: the quote that would end a SQL literal and the backslash that would escape one.

> Analytics Studio does not read this file type yet. It reads CSV, TSV, JSON and Parquet.

`DatasetResolver.java:101-102`, from extension detection at `DatasetRef.Format.of`.

> Nothing to read at etl-bucket/… The connection worked, so check the path.

`AnalyticsQueryService.explain`, `:200-201`. The only one of the four that comes from the engine
rather than from the resolver: DuckDB's own "no files found" / 404 / `NoSuchKey` is mapped to a
sentence that tells the reader which half of the problem to look at.

**The fifth message was not written down.** The refusal paths that exist and are unaccounted for
here are the uniform "Storage connection not found." (`DatasetResolver.java:81`, returned identically
for a connection that does not exist and one belonging to another workspace) and the provider refusal
at `:85-86`. Which of them was walked is not recorded, and this record will not guess. It is a small
hole and it is the reason a record like this should be written while the browser is still open.

### The two layers under observation 6

`/etc/passwd.csv` was refused by two independent mechanisms, and both were observed rather than
inferred:

1. **Confinement.** `DatasetResolver.java:64` strips leading slashes, so the path can only ever be
   interpreted relative to the bucket the connection record names. There is no request shape that
   reaches outside it.
2. **No local filesystem at all.** `DuckDbSessionFactory.lockDown` (`:190-193`) sets
   `disabled_filesystems='LocalFileSystem'` and then `lock_configuration=true`, in that order, so a
   query naming a path on disk fails in the reader rather than at a validator someone could later
   forget to call — and nothing that runs afterwards can put the filesystem back.

Defence in depth is easy to claim and hard to demonstrate; this is one of the few places in these
documents where both layers were actually watched to fail separately.

---

## The automated evidence standing behind this record

These are not observations of the running feature and are not a substitute for one. They are
recorded here because two of them assert things a manual pass cannot easily reach, and because the
security claims made for this feature rest on them rather than on anything in this file.

**`DatasetResolverTest` — 13 tests, all passing** (`process/target/surefire-reports`:
`Tests run: 13, Failures: 0, Errors: 0`). The happy path; a glob as one multi-file dataset; a
connection belonging to another workspace refused; a non-existent connection refused **with the same
words**, so an alias cannot be used as an enumeration oracle; a soft-deleted connection; `..`; a SQL
metacharacter (`a.csv'); DROP TABLE x; --`); the bucket coming from the record and not the request;
the alias fallback when `bucketName` is null; an unreadable file type; FTP refused; the
missing-argument messages; and format detection across every extension it claims to read.

That eighth case — `takesTheBucketFromTheConnectionRecord_notFromTheRequest`, asserting
`s3://locked-bucket/sales.csv` for a connection whose alias is `reports-store` — **replaced a test
that the mid-build API change made obsolete.** The first design took `storageConnectionId + bucket +
path`; switching to the alias both matched the Object Browser and removed a whole class of request.
The replacement asserts the stronger property rather than the removed one. Flagged because a
suite that loses a test during a redesign is exactly where a guarantee quietly stops being checked.

**`DuckDbLockdownTest` — 7 tests, all passing** (`Tests run: 7, Failures: 0, Errors: 0`), against a
**real DuckDB**, not a mock, because the claim is about what a specific engine refuses to do:

| Assertion | Why it is there |
|---|---|
| cannot read a local file | a fake secret (`DB_PASSWORD=hunter2`) is written to a temp file and the read attempted; the refusal must name the filesystem rule |
| cannot write a local file | and the file is asserted **absent** afterwards, not merely the statement failed |
| cannot raise its own memory ceiling | `SET memory_limit='64GB'` throws — `lock_configuration` is set last for this reason |
| cannot re-enable the local filesystem | `SET disabled_filesystems=''` throws |
| **still works** | the positive control: a `GROUP BY` returning `North 2000.50`. A session that refused everything, including its own purpose, would pass the other four while being useless |
| refuses FTP by name | `hasMessageContaining("S3, MinIO and Azure Blob")`, so a caller is told why rather than failing inside a scan |
| rejects a malformed memory-limit | `512MB'; SET lock_configuration=false; --` in a properties file would otherwise unlock the engine |

Two limits of that class, which matter to anyone reading it as proof: the fixture is a MinIO
connection **with no endpoint**, so no network call is made — these assert the session's own posture,
not the S3 path — and the whole file says nothing about Azure.

**Suite totals: backend 607 passing (was 587). Frontend 580 passing, unchanged.** That second figure
is the honest one: **no frontend unit test was added for the Studio component at all.** Not for the
storage walk, not for the paging arithmetic, not for the folder-as-dataset pattern building.

**Configuration.** Six properties, declared in `application-dev`, `-stage` and `-prod`
(`:137-142` / `:140-145`) and added to `ApplicationPropertiesDeclarationTest` (`:46-51`), on the
standing rule that an absent limit is an unlimited one: `analytics.query.timeout-seconds=30`,
`analytics.query.max-rows=10000`, `analytics.query.max-concurrent=4`,
`analytics.preview.page-size=100`, `analytics.duckdb.memory-limit=512MB`,
`analytics.duckdb.threads=2`. Dependency `org.duckdb:duckdb_jdbc:1.1.3` in `process/pom.xml:277-281`
— a ~70 MB jar shipping native libraries. Runtime verified on Java 17 Temurin, linux/aarch64,
Ubuntu 26.04, and nowhere else.

---

## Read from the source, not exercised

None of the following was observed. Each is a reading of a file, cited, and each is here because it
is the kind of thing this record's method could not have caught and a real pass will walk straight
into. They are flags, not findings, and no `QA-nn` is spent on them.

**A preview costs two queries, not one.** `AnalyticsQueryService.preview` calls `rowCount(dataset)`
before every page (`:98`), and `run()` takes a permit and opens a fresh session per **statement**
(`:150-179`), not per request. So one page of rows is a `count(*)` plus a `SELECT`, each with its own
DuckDB session, and opening a file is three of them (`DESCRIBE`, count, page). They run one after
another, so a single request never holds two permits at once — but it queues for a permit three
times, which means a load can be refused part-way through after already having answered, and it
means paging through a CSV re-counts the whole file on every click.

**The refusal at the ceiling is a specific sentence.** A caller that waits more than
`SLOT_WAIT_SECONDS = 2` (`:52`) is turned away rather than queued, with *"Too many analytics queries
are running right now. Try again in a moment."* (`:159-160`). The semaphore is fair (`:62`). The
ceiling is **per JVM, not per tenant**: one workspace can hold all four permits.

**Paging has no `ORDER BY`, on purpose** (`:100-103`) — object storage has no natural row order to
promise, and sorting a dataset to return a hundred rows would be worse. The consequence is that
page stability is only as good as the reader's own ordering, and the multi-file case is where that
is most likely to show.

**The storage rail does not page, and does not guard against an out-of-order listing.**
`Analytics.browse()` ignores `nextContinuationToken`, while `storage.service.ts:36` lists with
`maxKeys = 100`. The Object Browser it reuses does both: a **Load more** control
(`features/objects/objects.html:270-273`) and a `listTicket` guard whose comment records the exact
defect being guarded against — clicking a large folder then a small one left the slow response
landing last (`features/objects/objects.ts:214-236`). Neither came across. Two things follow: a
folder of more than 100 objects shows its first 100 silently, and `folderFormats()` — which decides
which "all `*.csv`" buttons appear — is computed from the **visible** files, so on a truncated
listing the folder-as-dataset offer is derived from a partial view. The dataset the button then
builds is still resolved server-side over the full pattern, so the reading is right even when the
offer is incomplete.

**A refusal may have nowhere to render.** `error()` is bound in exactly one place in
`analytics.html` — the `app-table-shell` on the **Data** view — while `load()` sets the tab back to
`overview` before it issues the schema request (`analytics.ts`). On that reading, a refusal arriving
while Overview is showing leaves a dataset card with no message on it. The refusals in observation 5
were read from the API response, so this is not what was being checked at the time. It is either a
real gap or already gone — the component was under edit the same day — and a browser is the only
thing that will settle it. First thing to try: a path with `..` in it, then look at Overview
without clicking anything.

**A tenant-less storage connection is visible to everybody.** `DatasetResolver.java:77` filters with
`TenantOwnership.isVisibleToCaller`, which returns true for a row whose `tenantId` is null — that is
its documented "shared catalogue" behaviour, not a defect in it — and true for any row when the
caller is a platform admin. There is also no equivalent here of the Object Browser's
`resolveServiceForCaller` / `isPlatformBucket` guard (`StorageBrowserServiceImpl.java:431-432`,
`:455-464`), which refuses the two named platform buckets to browser-originated requests because
`etl-bucket` holds Kafka key material and other tenants' documents. The shapes differ — Analytics
attaches the caller's own connection's credentials rather than handing out the platform's client, so
it is not the same hole — but "which connections are reachable through this endpoint, and what can
they name" is precisely the question a two-tenant pass exists to answer, and this record does not
answer it.

**Azure has never run.** `DuckDbSessionFactory` branches for it (`:130-134`, `azureSecret` at
`:171-179`), and DuckDB's `azure` extension is a different extension from `httpfs`. S3 and MinIO
share the S3 protocol and were both verified; Azure was not exercised against a real container by
anything, manual or automated. **Do not describe Azure as working.**

**The page-size clamp is unexercised.** `pageSize` is accepted by the endpoint (`:94`) and clamped in
`AnalyticsQueryService.pageSize` (`:137-140`) to `max-rows`; the browser never sends the parameter
at all (`analytics.service.ts:55-56`), so nothing has ever driven that path.

**`explain()` maps a fixed set of strings.** Anything DuckDB says that is not in the list at
`:193-215` becomes the generic *"The dataset could not be read."* and is logged in full (`:216-217`).
That is the intended trade — an unmapped engine message is exactly the kind of string that carries a
path or a host name — but it means an unfamiliar failure looks identical to every other unfamiliar
failure on screen, and the log is the only place to tell them apart.

---

## What a real QA pass still has to cover

Not a wish list. Each of these is a case this record could not reach, with what it is expected to
prove.

**Both themes at a narrow width.** Dark mode was looked at and no page overflow was seen; the width
at the time is not recorded, so a narrow-width claim cannot be made from it. The layout is a
two-column grid (`lg:grid-cols-[260px_minmax(0,1fr)]`) with a wide, scrolling data table inside the
right column: 375px is where the rail, the breadcrumbs and the table's own horizontal scroll have to
be checked, in both themes.

**Every role, including one that should be refused.** The endpoints are `TENANT_USER` at class level
and nothing else. A pass needs the role that should *not* reach `/analytics` at all, and the route
carries **no `roleGuard`** by deliberate decision (`app.routes.ts:129-135`), on the same reasoning as
the Object Browser: the per-connection tenant check is the real gate. That reasoning has never been
tested from the outside.

**Two tenants, for isolation.** The single most important untested thing in the feature. Tenant B's
connection alias against tenant A's session must give *"Storage connection not found."* — the same
wording as an alias that does not exist. `DatasetResolverTest` asserts this against a mocked
repository; nothing has asserted it against the running application. While there, settle the
tenant-less connection question above.

**An empty bucket, and an empty folder.** The rail has an explicit empty state; the dataset pane's
behaviour when a glob matches nothing is the engine's "no files found" mapped to the
*"Nothing to read at …"* sentence, which is a different path from an empty listing.

**A malformed CSV.** The one place `explain()`'s format branch (`:211-215`) can be provoked: a file
whose contents disagree with its extension is deliberately allowed to fail in the scan with DuckDB's
own message rather than being guessed at up front (`DatasetRef.Format` comment). Confirm the reader
gets *"This file could not be read as CSV…"* and not the generic sentence.

**A very large file.** Nothing here has ever approached the 30-second timeout, the 512 MB DuckDB
ceiling or the 10,000-row cap. The timeout's own message names the limit and tells the reader to
narrow the dataset (`:193-197`); it has never been seen. This is also where the "one page of rows"
claim in the page's own subtitle gets tested rather than asserted.

**A file with a very large number of columns.** The preview renders every column of every row with
`whitespace-nowrap`, and the schema list renders one row per column. A thousand-column Parquet file
is the case that finds out whether the table scrolls or the page does — and, at the API, whether a
`DESCRIBE` of that width is still the cheap call the design assumes.

**Concurrent users at the four-slot ceiling.** Four permits, per JVM, consumed per statement rather
than per request; a two-second wait and then a refusal. Worth doing with two workspaces at once,
because that is the arrangement in which one tenant occupying every slot is visible as a policy
question rather than as a slow page.

Additionally, and cheaply: paging past the last page and back; a glob whose files disagree on their
columns (`union_by_name=true` is on for multi-file datasets, so a folder that gained a column should
still read as one table); an FTP or FTPS connection picked in the rail, whose folders still browse —
the rail is the Object Browser's own service — but whose files must be refused with *"Analytics
Studio reads object storage. This connection is FTP."* (`DatasetResolver.java:85-86`) rather than
failing inside a scan; and a file with an uppercase extension, which both the client regex and the
server's lowercasing claim to accept.

---

## Status

**Findings issued: none.** That is a statement about the method, not a verdict on the code. A single
author checking the paths they have just written, once, in one browser, as one role, in one workspace,
with no checklist, is not an instrument that produces findings at the rate a QA pass does — the
three passes in this directory that ran the real method produced `QA-01`–`QA-35` between them.

What this record does establish is narrower and still worth having: the read path works end to end
against a real object store for CSV, multi-file CSV and Parquet; the refusals that were walked
refused, with sentences written for a person; and the engine lock-down was demonstrated to fail
closed on two independent layers, with a positive control proving the session still does its job.
The lock-down is the part with the strongest evidence behind it, because most of that evidence is
in `DuckDbLockdownTest` against a real DuckDB rather than in this record.

Everything else — isolation, roles, presentation, scale, concurrency, Azure — is untested. Analytics
Studio phase one is **deployed and unvalidated**, and it should be described that way until somebody
who did not write it has used it.
