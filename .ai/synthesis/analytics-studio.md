# Synthesis -- Analytics Studio

Feature `analytics-studio`. Status **new** -- the old application never had it, and neither did the
rewrite until 2026-09-08, so nothing below is a parity question.
Grooming: [../grooming/analytics-studio.md](../grooming/analytics-studio.md).

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

Analytics Studio is a module that lets a person read a file where it already lives. A user picks a
storage connection, filters or walks the folders, clicks a file, and gets Overview / Data -- and
nothing has been copied into Postgres to make that happen. DuckDB is embedded in the backend and
reads the object store directly, so a gigabyte file costs the browser one page of rows and costs
Spring no streaming at all. A whole folder can be read as **one** dataset by pattern, which is the
case the feature exists for: a partitioned output directory is only meaningful read together.

**This document is unusual, and it is worth saying so before the table.** Phase one of the module
was designed, built, tested and deployed on 2026-09-08, so the gap table below is not a list of
things to do to code that already works. It is the whole module as specified -- five phases -- with
the phase-one rows **marked closed and dated**, and everything else carrying an honest size. The
**Current** column on a closed row describes the state *before* 2026-09-08; the **Status** column
says it has since been answered. That makes this a plan for phases two to five rather than a
retrospective, which is what it has to be, because the interesting decisions are all still ahead.

**What phase one deliberately does not ship: user-written SQL.** No SQL editor, no profiling, no
data quality, no charts, no dashboards, no saved queries, no history, no export, no benchmarks.
That is not an omission and must not be read as one. The two things that *were* built first are the
engine lock-down and the governor -- the parts that make user SQL survivable -- and they were built
first precisely so that phase three has somewhere safe to land. `DuckDbSessionFactory` and
`AnalyticsQueryService` both say this in their own headers, and `AnalyticsRestApi.java:36-38` states
it as a rule: *"There is deliberately no endpoint here that accepts SQL."*

**The security model is the part of this feature worth understanding before anything else**, because
the threat is inverted from the usual one. Normally the database is trusted and the input is not.
Here the **engine** is the dangerous component: DuckDB can read and write local files, open sockets
and install extensions, all as the backend process. Section 3.2 records what was done about that and
why the order of operations matters. `DuckDbLockdownTest` proves seven of those claims against a
real DuckDB rather than a mock, including a positive control, because a session that refused
everything would pass the other assertions while being useless.

**What this pass found that phase one did not.** Four disagreements between what the storage rail
offers a user and what `DatasetResolver` will accept, one of which was a genuine tenancy hole: the
resolver admitted a **platform-owned** storage connection to any tenant user who named its alias,
using the one ownership predicate whose own javadoc warns against being used this way. That is
gap 9, and it was **fixed on 2026-09-08** -- one identifier, `isVisibleToCaller` to
`isOwnedByCaller`, plus a control test so a rule that refused everybody could not pass for a fix.

**The severity was understated when first written, and the correction is the lesson.** The
original entry reasoned from `isPlatformBucket`'s comment that the two shipped platform buckets
had no `storage_connection` row, so the exposure was limited to a row an operator might create.
The database says otherwise: **all seven connections in this environment are platform-owned**,
`etl-bucket` and `etl-avatar` included -- the former holding, by `resolveServiceForCaller`'s own
description, Kafka key material and other tenants' documents. Every tenant user could read the
entire storage estate. A claim about what is in a table is worth a query, not an inference from a
comment about that table.

Gap 10 was the same shape one size down -- a connection an administrator had switched off was
invisible in the rail and still readable through the API -- and was **fixed in the same filter
chain**. The remaining two are cosmetic by comparison, but each one produces a control the user
can click and a refusal they cannot act on.

---

## 2. The gap table

Rows 1-8 are phase one, closed. Rows 9-22 are what phase one left open, all found or confirmed on
2026-09-08. Rows 23-33 are phases two to five, none of them started.

> **One caveat about the frontend citations.** `features/analytics/` was being edited while this
> document was written -- the file timestamps moved twice during the pass. Frontend line numbers
> below are as read on 2026-09-08 and record **where a finding was made, not where the code lives
> today**; every frontend claim also names its symbol, which is the durable half. Backend citations
> were stable throughout. See the note at the end of 2.1 for the one change that landed mid-pass.

| # | Status | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|---|
| 1 | **Done 2026-09-08** | The Object Browser can hand back a file's bytes or its text (`storage.json/previewObject`); nothing reads one as a table | A file in object storage can be read as rows and columns without being copied anywhere | No analytical read of any file, anywhere in the console | DuckDB embedded in the backend, reading the object store directly; `process.analytics` and `analytics.json/schema` + `/preview` | L | Medium -- new engine in the JVM |
| 2 | **Done 2026-09-08** | -- (no engine existed) | An analytics session cannot read or write local files, cannot load a further extension, and cannot undo any of that | An embedded engine with filesystem and socket access, running as the backend | `DuckDbSessionFactory.open` applies limits, then credentials by `CREATE SECRET`, then `disabled_filesystems`, then `lock_configuration=true` **last**; a half-configured session is closed rather than returned | M | **High if wrong** -- this is the whole safety case |
| 3 | **Done 2026-09-08** | -- | One careless request cannot take the backend down with it | An unbounded scan competing for memory with the ETL dispatcher in the same container | `AnalyticsLimits` as one bean; fair `Semaphore`, 2s wait then refuse; `setQueryTimeout`; DuckDB `memory_limit` and `threads` per session | M | Medium |
| 4 | **Done 2026-09-08** | -- | The caller names a connection and a path inside it, never a bucket and never a URL | "Use these credentials against a different bucket" would otherwise be an expressible request | `DatasetResolver` is the only source of a `DatasetRef`; package-private constructor; path allow-list, `..` check, tenant check, provider check, format detection | M | **High if wrong** -- see 3.3 |
| 5 | **Done 2026-09-08** | -- | A folder of partition files reads as one dataset | A per-day output directory would have to be opened a file at a time | Glob in the path; `union_by_name=true, filename=true` on multi-file scans (`DatasetRef.scanExpression:107-122`) | S | Low |
| 6 | **Done 2026-09-08** | -- | A refusal is a sentence a user can act on, never a stack trace and never an engine string | An unmapped engine message is exactly the kind of string that carries a path or a host name | `AnalyticsException` for user-facing failures; `AnalyticsQueryService.explain:189-218` maps DuckDB errors and logs anything unmapped in full | S | Low |
| 7 | **Done 2026-09-08** | -- | Every limit is discoverable by an operator, in all three profiles | An absent limit is an unlimited one | Six properties in `application-dev/stage/prod.properties:136-145`, all six added to `ApplicationPropertiesDeclarationTest:46-51` | XS | Low |
| 8 | **Done 2026-09-08** | -- | The storage walk is the Object Browser's, not a second copy of it | Two implementations of connection → folder → file that have to be kept in step | The rail drives the existing `features/objects/storage.service.ts`; `TableShell`, `StatTile`, `Icon`, `formatSize`, `compactNumber` reused; **no new UI primitives** | S | Low |
| 9 | **Done 2026-09-08** | `DatasetResolver.java:77` filtered on `TenantOwnership.isVisibleToCaller`, which returns **true for a null owner** (`TenantOwnership.java:52-54`) | A platform-owned connection is unreachable by a tenant user, exactly as the Object Browser decided (`StorageBrowserServiceImpl.java:100-104`, `:430-437`) | Measured, not inferred: **all seven** connections in this environment are platform-owned, so every tenant user could read the whole estate including `etl-bucket` | `isOwnedByCaller` (`:74-89`), with `refusesAPlatformOwnedConnectionToATenantUser` and its control `readsAPlatformOwnedConnectionForAPlatformAdmin` | XS | **High** -- tenancy |
| 10 | **Done 2026-09-08** | The resolver accepted any status but `Delete`; the browser resolves `findByAliasAndStatus(alias, Active)` (`StorageBrowserServiceImpl.java:530`) | The two agree on which connections are live | An `Inactive` connection was invisible in the rail and readable through the API | Filters on `Status.Active` (`:88`), pinned by `refusesADeactivatedConnection` | XS | Medium |
| 11 | **Done 2026-09-08** | The rail lists `storage.json/buckets`, which includes `BUCKET_LIST` lookup entries with no connection row (`StorageBrowserServiceImpl.java:114-132`); the resolver only does `findByAlias` | Every connection offered in the rail can be read, or is visibly not offered | A legacy-configured bucket is selectable and every file in it answers "Storage connection not found." | Either resolve `BUCKET_LIST` too, or filter the rail to connections -- see 3.5 | S | Low |
| 12 | **Done 2026-09-08** | The rail offers FTP and FTPS connections; the resolver refuses them at the first file click (`DatasetResolver.java:84-87`) | An unreadable connection is visibly unreadable before a file is clicked | A user browses a whole FTP tree and is refused on every file | Disable the option with the reason on it, the way an unreadable *file* already is (`analytics.html:71-75`) | XS | Low |
| 13 | **Done 2026-09-08** | The Azure branch exists (`DuckDbSessionFactory.java:130-134`, `:171-179`) and **has never been run against a real container** | Azure Blob is either verified or not claimed | S3 and MinIO were verified; Azure needs DuckDB's separate `azure` extension and is untested | Verify against a real container, or say so on screen -- see Q4 | S | Medium |
| 14 | **Done 2026-09-08** | `analytics.query.max-rows` is read in exactly one place: as the ceiling on the preview page size (`AnalyticsQueryService.pageSize:137-140`) | The property means what `AnalyticsLimits.java:36-40` says it means | The javadoc promises "enforced by rewriting the query with a LIMIT"; no code does that, and phase three is where it will matter | Apply it in the SQL path when that path exists; until then, correct the javadoc | XS | Low |
| 15 | **Done 2026-09-08** | Only `DatasetResolver` and `DuckDbSessionFactory` have tests (20 of the 607) | The governor, `explain()` and the controller's role floor are asserted | The semaphore, the timeout, the page clamp and the whole error mapping are unproven | `AnalyticsQueryServiceTest` and `AnalyticsRestApiTest` | M | Low, high value |
| 16 | **Done 2026-09-08** | No spec file exists under `features/analytics/` | The Studio's states are pinned | The component, its service and its template are wholly untested; the suite stands at **580, unchanged** | `analytics.spec.ts` | M | Low |
| 17 | **Done 2026-09-08** | Nothing is cached; opening a file costs **three** sessions and three governor slots (schema, count, page), a page turn **two** (`Analytics.load`/`loadPage`, `AnalyticsQueryService.preview:93-128`) | A page turn does not re-count a dataset it counted a moment ago | Four concurrent users paging cost twelve acquisitions against a ceiling of four | Carry the count forward; cache schema and count per `DatasetRef` -- see 3.7 | S | Medium |
| 18 | **Done 2026-09-08** | The preview has no `ORDER BY`, deliberately (`AnalyticsQueryService.java:100-101`) | Paging is stable, or is described as not being so | Object storage has no natural row order, so page 2 is only as stable as the reader's own ordering | Say it on screen; revisit when a sort control arrives in phase three | XS | Low |
| 19 | Open | The `Semaphore` is one per JVM (`AnalyticsQueryService.java:62`) | One workspace cannot occupy the whole ceiling | Four slots, and one tenant can hold all four | Per-tenant permits, or a per-tenant sub-limit -- see Q3 | S | Medium |
| 20 | **Done 2026-09-08** | `explain()` matches a fixed set of DuckDB substrings (`AnalyticsQueryService.java:193-215`) | An unrecognised failure is still actionable | Anything unmapped becomes "The dataset could not be read." | Accepted for now; the log line carries the original. Widen as real failures are seen | XS | Low |
| 21 | **Largely done 2026-09-08** | A dataset read wrote nothing: no audit row, no Kafka event. `analytics_query_run` now records every query attempt INCLUDING refusals, and a completed query publishes on `analytics.query.completed`. Still open for `/schema`, `/preview` and `/profile`, which write only a log line | "Who read what, and when" is answerable | The spec asked for both; neither is built | Deferred -- see Q5 | -- | -- |
| 22 | **Done 2026-09-08** | `ToastService` was injected and never used (`analytics.ts:3`, `:44`); the Schema tab bound `[shown]` and `[total]` to the same expression | No dead injection; a count that means something or is absent | Two small blemishes | Injection deleted; the duplicate binding went with the Schema tab, which became a columns rail | XS | None |
| 23 | **Done 2026-09-08** | **No database change at all.** No `AnalyticsDataset`, `SavedQuery`, `QueryHistory`, `Dashboard` or `BenchmarkResult` entity exists; a selection lives only in the component's signals | A dataset, a query and a result can outlive a page load | Nothing in phases three, four or five can be saved, shared or scheduled | One changelog set and the entities the phase that needs them requires -- see 3.8 | M | Medium -- the enabler |
| 24 | **Done 2026-09-08** | Overview reports row count, column count, format and location, and nothing about the values | Per-column statistics: null counts, distinct counts, min/max, mean, the shape of a distribution | Phase two, "understand it" | DuckDB `SUMMARIZE`, one query, rendered on a Profile tab | M | Low |
| 25 | **Done 2026-09-08** | Nothing describes data quality | Nulls, blanks, duplicates, outliers and type surprises are named | Phase two | Derived from the profile in 24; no second scan | M | Low |
| 26 | **Done 2026-09-08** | No endpoint accepts SQL, deliberately (`AnalyticsRestApi.java:36-38`) | A user can ask the dataset a question they write themselves | Phase three, and the reason phases one's lock-down and governor exist | A `query` endpoint through `AnalyticsQueryService`, under the same session and the same semaphore; an editor -- see Q1 | L | **High** -- the whole safety case is spent here |
| 27 | **Done 2026-09-08** | A query cannot be named, saved or found again; nothing records that one ran | Saved queries and a history a user can re-run from | Phase three | Depends on 23 | M | Low |
| 28 | **Done 2026-09-08** | A `DatasetRef` is one location; two datasets cannot be read together | Two datasets can be joined in one query | Phase three | Falls out of 26; the scan expressions compose in one `FROM` | M | Medium |
| 29 | **Done 2026-09-08** | A result is a table and nothing else | A result can be drawn | Phase four, "get answers out" | Reuse `shared/charts` -- but see **Q2**, which is not settled | M | Low |
| 30 | **Done 2026-09-08** | A result cannot leave the browser | A result can be downloaded, or written back to a bucket | Phase four | `ReportExportServiceImpl` is the shape to follow, and its four open security gaps are the shape to avoid | M | Medium |
| 31 | **Done 2026-09-08** | Analytics reads and never writes | A derived dataset can be written back to object storage | Phase four | Needs `disabled_filesystems` to stay as it is and the write to go through the S3 secret, never a local path | M | **High** -- reintroduces a write |
| 32 | **Done 2026-09-08** | Nothing is published when a query completes | A completed query can drive downstream work | Phase four | The platform already has Kafka profiles and a producer; see 21 and Q5 | S | Low |
| 33 | **Harness built 2026-09-08, claim still unmeasured** | No measurement of anything | CSV versus Parquet measured, on this deployment, with the numbers written down | Phase five, "prove it is fast" | A harness that reads the same data both ways and records it; depends on 23 for `BenchmarkResult` | M | Low |

---

## 2.1 What was verified live on 2026-09-08

Recorded here rather than in the grooming document because it is the evidence the closed rows above
rest on. All of it was run through the real API and the real UI against MinIO, not against a mock.

**Reading.** `sales.csv` read as **7 rows, 4 columns, CSV**, with a schema of `region`, `rep` and
`product` as `VARCHAR` and `amount` as `DOUBLE`. A Parquet file was read for both schema and rows.

**The folder as one dataset.** A glob over three partition files returned **one** dataset of 7 rows
and **5** columns -- the fifth being the filename column `filename=true` adds -- each row carrying
`s3://etl-bucket/etl-demo/F768945/out/<file>.csv`. That output directory is the one written by ETL
pipeline `F768945` (`csv_partition`), added to `job-search` earlier the same day; it is named here
only because it is where the evidence came from.

**Refusals.** Five refusal paths were exercised, each returning a friendly `ERROR` and never a stack
trace. The messages recorded were:

> A dataset path cannot contain "..".
> That path contains characters this reader does not accept.
> Analytics Studio does not read this file type yet. It reads CSV, TSV, JSON and Parquet.
> Nothing to read at etl-bucket/… The connection worked, so check the path.

**Defence in depth, both layers observed.** An absolute path of `/etc/passwd.csv` is confined
*inside* the connection's bucket by `DatasetRef.url()`, which builds `s3://<bucket>/<path>` and has
no way to express anything else -- **and, separately**, has no local filesystem to reach, because
`disabled_filesystems='LocalFileSystem'` removed the reader. Either alone would have been enough;
both were checked, because the point of the second layer is that somebody may one day change the
first.

**The screen.** Dark mode correct, no page overflow at a narrow width, no console errors.

**The suites.** Backend **607 passing**, up from 587 -- the 20 new tests being `DatasetResolverTest`
(13) and `DuckDbLockdownTest` (7). Frontend **580 passing, unchanged**, because no frontend unit
test was written for the Studio; that is gap 16 and it is stated rather than glossed.

**The runtime.** Java 17 Temurin, `linux/aarch64`, Ubuntu 26.04, with
`org.duckdb:duckdb_jdbc:1.1.3` added to `process/pom.xml:277-281` -- a ~70 MB jar, because it ships
native libraries for every platform it supports.

> **One change landed mid-pass, 2026-09-08**, and the prose above has since been corrected to
> match. What was verified live and was described throughout this document as
> **Overview / Data / Schema** is now **Overview / Data**: `type Tab` declares two
> members, and the columns-and-types table was folded into the Data tab beside the rows, with the
> reason written into the template -- *"The question 'what type is this column' is asked while
> looking at the values in it, and the old Schema tab made that a round trip."* **No capability was
> removed**: the schema still comes from `analytics.json/schema` and every column is still listed
> with its type. `StatTile` is no longer imported by the component, so row 8's claim about reuse now
> rests on `TableShell`, `Icon`, `formatSize` and `compactNumber`. Recorded rather than silently
> corrected above, because the three-tab shape is what was tested and deployed.

---

## 3. Solution detail

### 3.1 Why DuckDB rather than loading the data into Postgres

**What was decided.** The engine reads the file where it lives. Nothing is copied, imported, staged
or cached into the application database, and no table is created for a dataset.

**Why not Postgres.** The obvious design is the one every reporting feature reaches for first: pull
the file into a staging table and query it with the database that is already there, already
connection-pooled, already backed up and already understood. It was **rejected**, and the reasons
are worth keeping because the proposal will come back.

First, it inverts the cost. A load is proportional to the size of the file; a scan is proportional
to the part of it the query touches. The user's question here is nearly always "what is in this
file" -- schema, row count, first hundred rows -- and answering that by first writing a gigabyte
into Postgres does the most expensive possible work to answer the cheapest possible question. On
Parquet the difference is starker still: `count(*)` is answered from the file's own footer metadata
without reading a row, which is why `AnalyticsQueryService.preview` counts separately rather than
inferring the total from the page (`:86-92`).

Second, it makes the application database the analytics database, and those two have opposite
failure modes. `job_queue` is the largest table in this system and the `reports` synthesis records
what an unbounded scan of it costs (`reports.md` gaps 5 and 6). Adding an arbitrary-width, arbitrary-
depth staging table beside it, written by whichever user happened to click a file, puts a workload
nobody can size into the same instance that runs the dispatcher.

Third, it creates a lifecycle nobody asked for. A staged table has to be named, owned, scoped to a
tenant, expired, and cleaned up after a failure -- five problems, all of them permanent, in service
of a screen whose entire purpose is a read. Reading in place has none of them, and it is the reason
row 23 can honestly say phase one made **no database change at all**.

**What was traded away, stated plainly.** An embedded engine runs in the backend's own JVM and its
own memory, which is exactly why `AnalyticsLimits` exists and why the class javadoc opens by saying
these are "not tuning knobs bolted on afterwards" (`AnalyticsLimits.java:6-18`). And the jar is ~70
MB, because it ships native libraries. Both costs were accepted knowingly.

### 3.2 The lock-down, and why the order is the design

**What it does.** `DuckDbSessionFactory.open` (`:76-98`) configures a fresh in-memory session in a
fixed order and returns it only if every step succeeded:

1. `SET memory_limit` / `threads` / `preserve_insertion_order=false`
2. `INSTALL` + `LOAD` `httpfs` for S3 and MinIO, or `azure` for Azure Blob -- **FTP and FTPS are
   refused by name** in the `default` branch (`:135-141`) rather than being left to fail inside a
   scan
3. `CREATE OR REPLACE SECRET analytics_store (…)` -- credentials attached as a secret, never
   interpolated into query text, so they cannot surface in a query plan or an error message
4. `SET disabled_filesystems='LocalFileSystem'`
5. `SET lock_configuration=true` -- **last**

**Why the order is not incidental.** Every step above is reversible by SQL right up until step 5,
and irreversible afterwards. Putting `lock_configuration` last is what makes steps 1-4 permanent for
the life of the connection; putting it anywhere else would mean the remaining steps could not run.
So the ordering is not a tidy way of writing five statements, it is the mechanism. The javadoc says
so at `:22-23` and `:181-188`, and it should stay said, because a future edit that adds a sixth
setting has exactly one correct place to put it.

**Why a half-configured session is closed rather than returned.** `open()` tracks `handedOver` and
closes the connection in a `finally` if configuration threw (`:87-97`). A session that failed
part-way through is an **unlocked** session; the natural shape -- try-with-resources at the call site
only -- would let one escape whenever step 2 or 3 failed, which is precisely when something is
already wrong.

**Why the driver loads in a static block.** `Class.forName("org.duckdb.DuckDBDriver")` at `:53-59`
rather than JDBC auto-discovery. DuckDB unpacks a native library on first use; doing that inside a
request thread makes the first analytics call after a restart mysteriously slow, and a failed unpack
produces a `ClassNotFound` instead of a message naming the real problem.

**Why a property is restricted rather than escaped.** `sanitiseSetting` (`:221-227`) requires
`[0-9]+[A-Za-z]{0,3}` before the memory limit is interpolated. These values come from application
properties and not from a user -- but a property is a string an operator can mistype, and
`512MB'; SET lock_configuration=false` would otherwise be a configuration file that unlocks the
engine. `DuckDbLockdownTest.aMalformedMemoryLimitIsRejectedRatherThanInterpolatedIntoSql:167` pins
it.

**Why `DuckDbLockdownTest` runs a real DuckDB.** It is the one test in the suite that would be
worthless as a mock: the claim is about what a *specific engine* refuses to do, and a stubbed engine
refuses whatever the stub says. Seven tests: cannot read a local file (a fake secret is written to a
temp file and the read attempted), cannot write one (and the file is asserted absent afterwards),
cannot raise its own memory ceiling, cannot re-enable the local filesystem, **still works** -- the
positive control, without which the other four would pass against a session that did nothing -- FTP
refused by name, and the malformed memory limit above.

### 3.3 Why the API takes a connection alias and not a bucket

**What it does.** `GET /analytics.json/schema` and `/preview` take `connection` (an alias) and
`path`. They do not take a bucket, and they do not take a URL. The bucket comes from the
`StorageConnection` record -- `getBucketName()`, falling back to the alias when it is null, which is
what `StorageBrowserServiceImpl` does at `:544-547` (`DatasetResolver.java:89-93`). Both endpoints
carry `@PreAuthorize("hasRole('TENANT_USER')")` at **class** level (`AnalyticsRestApi.java:43`),
matching the Object Browser, and a business failure is an HTTP 200 with a `ResponseDto` of status
`ERROR`, per house convention.

**The role is only the floor, and the header says so** (`AnalyticsRestApi.java:32-34`): *"which
connections a caller may reach is not a question a role can answer, and is settled per request
against the connection's own tenant."* That is why gap 9 is a gap -- the per-request check is the
real gate, so it has to be the right one.

**This was a mid-build correction, and that is the part worth recording.** The first design took
`storageConnectionId + bucket + path`. Switching to the alias did two things at once: it matched how
the Object Browser addresses storage, so the two screens now speak the same language and the rail
could be driven by the existing `StorageService` unchanged (row 8); and it **removed a whole class of
request**. "Use these credentials against a different bucket" is not a request the API can express
any more -- not because a validator refuses it, but because there is no field to put it in.

**One test became obsolete as a result.** The original suite asserted that a caller could not name a
bucket other than the connection's own -- a test of a validator. With the parameter gone the
validator went too, so the test was asserting the absence of a code path rather than a property.
It was replaced by `takesTheBucketFromTheConnectionRecord_notFromTheRequest`
(`DatasetResolverTest.java:157`), which asserts the *stronger* thing: that the resolved URL is built
from `getBucketName()` regardless of anything in the request. A sibling,
`fallsBackToTheAliasWhenTheConnectionNamesNoBucket` (`:173`), covers the null case.

**Why the type carries the rule rather than a convention.** `DatasetRef`'s constructor is
package-private (`DatasetRef.java:59`) and `DatasetResolver` is the only thing that calls it. So the
tenant check, the path check and the format check cannot be forgotten at a call site, because there
is no call site that can skip them -- the only way to obtain a `url()` is to hold a `DatasetRef`, and
the only way to hold one is to have passed. That is a structural guarantee rather than a remembered
one, and it is why `AnalyticsQueryService` can interpolate `scanExpression()` into SQL without
re-validating anything.

**Why the path check is an allow-list and the `..` check is separate.** `SAFE_PATH` is
`[A-Za-z0-9._*?/=+ -]+` (`DatasetResolver.java:36`). A deny-list of `../` and its encodings invites
the reader to think of one more encoding; an allow-list permits the characters object keys actually
use plus the two glob characters a multi-file dataset needs, and refuses everything else -- notably
the quote that would end a SQL literal and the backslash that would escape one. The `..` test is
then applied *after* it, not instead of it, because `..` is made entirely of permitted characters and
is the one shape an allow-list cannot exclude.

**Why "not found" and "not yours" say the same words.** Both produce `"Storage connection not
found."` (`:78-82`). Distinct messages would let a caller walk the alias space and learn which
connections other workspaces own. `refusesAConnectionBelongingToAnotherWorkspace:98` and
`refusesAConnectionThatDoesNotExistWithTheSameWords:110` assert the two paths agree, which is a test
that would otherwise be very easy to lose in a refactor.

### 3.4 Why a session per query rather than a connection pool

**What it does.** `AnalyticsQueryService.run` opens a session, runs one statement, and closes both
with try-with-resources (`:164-178`). There is no pool.

**Why not a pool.** Pooling is the reflex for anything JDBC, and for Postgres it is correct: a
connection is expensive, stateless between transactions, and shared safely. A DuckDB session is none
of those things. It carries an **in-memory catalogue** and, more importantly, the **attached
credentials** for one storage connection. Pooling it would mean either re-attaching a different
secret to a recycled session -- which is a `CREATE OR REPLACE SECRET` on a connection whose
configuration is locked, so it would have to run *before* the lock, which is to say the lock would
have to move -- or handing one caller a session still holding another tenant's credentials.

The narrow version of the same point: a query that wedges cannot poison a pooled connection for the
next caller, because there is no next caller. The catalogue and the credentials die with the
connection.

**What it costs, stated honestly.** A fresh session per request, which is milliseconds against a scan
measured in hundreds. That trade is fine for one query and less fine at three per file open -- which
is gap 17, and is a caching problem rather than a pooling one.

**Why the governor sits where it does.** The three limits are applied in a deliberate order
(`:142-149`): the slot is taken **first**, so a rejected caller never pays for a session; the
session's own memory ceiling bounds what the query can consume once it starts; and the timeout bounds
how long it may hold the slot, so one wedged scan cannot occupy a permit for ever and shrink the
ceiling for everyone else. The semaphore is **fair** (`:62`) so a steady trickle of small queries
cannot starve one that has been waiting, and the wait is two seconds and then a refusal rather than a
queue -- `AnalyticsLimits.java:47-53` gives the reason: *"a caller who waits behind five one-gigabyte
scans has already lost, and telling them so is kinder than a request that eventually times out."*

### 3.5 Gaps 9, 10, 11, 12 -- the rail and the resolver disagree in four ways

These four are one change and should be one commit. Each is a place where the storage rail offers a
control the resolver will not honour, or -- in the first case -- honours something the rail
deliberately withheld.

**Gap 9 is the one that matters, and it is a tenancy hole.** `DatasetResolver.java:77` filters with
`TenantOwnership.isVisibleToCaller`. That predicate returns **true whenever the owning tenant is
null** (`TenantOwnership.java:52-54`), and a null `tenant_id` on a `StorageConnection` means
*platform-owned*, not ownerless. The Object Browser settled this exact question and settled it the
other way: `collectBuckets` was changed so that platform connections belong to the platform admin
alone, and the comment records why -- *"A connection with no tenant used to be treated as
platform-wide and offered to every tenant, which is how etl-bucket and etl-avatar showed up in every
workspace's object browser"* (`StorageBrowserServiceImpl.java:100-104`) -- while
`resolveServiceForCaller` (`:430-437`) refuses a platform bucket to every non-platform caller on
every verb, with one narrow exception for a user's own avatar.

So a `TENANT_USER` who names a platform connection's alias reaches it through `analytics.json`, while
the same alias is absent from their rail and refused by the browser. `TenantOwnership`'s own javadoc
is unusually direct about this being the wrong predicate for this job: `isVisibleToCaller` exists
*"for the one kind of read that still deliberately admits a platform-owned row: resolving a default
to fall back on … That is a narrow, internal fallback, not a 'list/read screen shows the platform's
rows too' catalogue"* (`:19-28`). Analytics Studio is the second kind.

**The fix is one identifier**: `isOwnedByCaller` instead of `isVisibleToCaller`, which answers no for
a platform-owned row and no for a caller with no tenant, so both fail closed. It needs a test,
because the reason this survived review is that `DatasetResolverTest` has thirteen cases and **none
of them uses a null tenant** -- `connection(Long tenantId, …)` at `:49` is always called with
`TENANT_A` or `TENANT_B` (`:98`, `:110`, `:120`).

**Two honest qualifications, so nobody over- or under-reads this.** The two buckets named in the
Object Browser's guard, `etl-bucket` and `etl-avatar`, ship as a `BUCKET_LIST` lookup entry and a
property respectively, and no migration creates a connection row for either (`:456-464`). Since the
resolver only does `findByAlias`, *those two specific names* are refused by analytics anyway -- by
accident, through gap 11, not by the tenancy check. What is genuinely reachable is any
platform-owned **StorageConnection** row, which `isPlatformBucket:462-463` exists precisely to
recognise. Whether such a row exists on this deployment was not checked against the database; the
claim here is about the code path, and the code path is the thing a future row would arrive into.

**Gap 10 is the same shape, smaller.** The resolver accepts every status except `Delete` (`:76`);
`resolveService` looks up `findByAliasAndStatus(bucket, Status.Active)` (`:530`). `Status` has three
values (`Status.java:6`), so the difference is exactly `Inactive`: a connection an administrator has
deliberately switched off stays readable through analytics. Same fix, same test file, one line.

**Gap 11 is a control that cannot work.** The rail is populated from `storage.json/buckets`, which
merges storage connections with `BUCKET_LIST` lookup children that have no connection row
(`StorageBrowserServiceImpl.java:114-132`) -- the older mechanism, kept working so jobs pointing at
those buckets keep resolving. `DatasetResolver` knows only about connections. So such a bucket is
selectable in the Connection dropdown, browses correctly (because browsing goes through the storage
service, which understands both), and then answers *"Storage connection not found."* for every file
in it -- a message that is actively misleading, because the connection is right there in the picker.

Two options. **Resolve `BUCKET_LIST` as well** is more work than it looks: a lookup child carries no
credentials of its own, so the analytics session would have to get them from wherever
`resolveService` gets them, and that path ends in `storageClientFactory`, not in something
`DuckDbSessionFactory` can turn into a `CREATE SECRET`. **Filter the rail** is small and honest:
Analytics reads connections, so the picker should offer connections. Recommended, and it makes gap 12
free, since the same filter can exclude non-object-store providers.

**Gap 12 is the cheapest of the four.** `DatasetResolver.java:84-87` refuses any provider where
`isObjectStore()` is false -- FTP and FTPS (`StorageProvider.java:14-16`) -- but only once a file has
been clicked. A user can pick an FTP connection, walk its whole tree, and be refused on every file.
The screen already knows how to do this properly one level down: an unreadable *file* is rendered but
inert, with the reason in its `title` (`analytics.html:69-75`), on the stated principle that *"knowing
the file is there and unreadable is more useful than it vanishing."* The same treatment for the
connection option.

### 3.6 Gap 13 -- Azure

**State it as untested, everywhere it is described.** `DuckDbSessionFactory` branches for Azure
(`:130-134`), builds an `AZURE`-type secret from the decrypted connection string (`:171-179`), and
`DatasetRef.url()` emits `azure://` (`:94-97`). None of it has been exercised against a real
container. S3 and MinIO were verified live and they share the S3 protocol, so one verification covers
both; Azure uses a **different DuckDB extension** (`azure`, not `httpfs`), a different secret shape
and a different URL scheme, which means it shares none of the evidence.

**Do not describe Azure as working.** That is the whole of the requirement here. `StorageProvider.
isObjectStore()` returns true for `AZURE`, so the resolver admits it and a user with an Azure
connection will get as far as an engine error nobody has ever seen -- which will land in `explain()`'s
unmapped branch and read "The dataset could not be read." (gap 20). See Q4 for the decision.

### 3.7 Gap 17 -- what a file open actually costs

**The measurement, from the code.** Opening a file in the Studio issues `schema()` and then, on
success, `loadPage(0)` (`Analytics.load`, `analytics.ts:223-234`). `schemaOf` is one query. `preview` is **two** --
`rowCount(dataset)` at `:98` and the page itself at `:106` -- and each of the three goes through
`run`, which independently acquires a semaphore permit and opens its own locked-down session
(`:150-178`). So a file open is **three sessions and three acquisitions**, and every subsequent page
turn is **two**, because the count is recomputed.

Against a default ceiling of four concurrent queries (`analytics.query.max-concurrent=4`), two users
opening a file at the same moment can exhaust it, and the third gets "Too many analytics queries are
running right now."

**The fix, in order of value.** First, **carry the count forward**: a page turn already knows the
total from the previous response and `preview()` could take it as a parameter, halving every page
turn for one optional argument. Second, **cache schema and count per `DatasetRef`** -- short-lived and
keyed on connection + path + tenant. Neither changes the security model, because a cache hit skips no
check: `DatasetResolver.resolve` still runs first, on every request, and the cache would sit behind
it.

**Why not cache the rows.** **Rejected**: a page of a dataset a user is actively paging through is the
one thing they most want to be current, the payload is the largest thing in the system to hold, and
the count and schema -- which are cheap to hold and are what get recomputed pointlessly -- give
almost all of the benefit. Note also that the caching question is the same one `reports` answered by
not caching either; if a caching mechanism is introduced here it should be the platform's, not a
private one.

### 3.8 Gap 23 -- nothing is persisted, and that is the phase-two blocker

**Say this plainly wherever the module is described.** Phase one made **no database change of any
kind**. There is no `AnalyticsDataset`, no `SavedQuery`, no `QueryHistory`, no `Dashboard` and no
`BenchmarkResult`. Datasets are not registered, named or owned. A selection lives in three signals in
one component (the `path` / `selected` / `preview` signals) and is gone on reload -- there is not even a route parameter, so
a dataset a user is looking at cannot be sent to a colleague.

**Why that was right for phase one and is wrong from phase two on.** For "read a dataset" it was
right: a read that persists nothing has no lifecycle, no ownership, no cleanup and no migration, and
that is the whole argument in 3.1. But rows 27, 29, 31 and 33 all need somewhere to put something,
and three of the five phases are therefore blocked behind one changelog set.

**Recommended shape, so the same decision is not made four times.** The first entity should be the
**dataset**, not the query: a saved query, a chart and a benchmark result all refer to a dataset, and
if each phase invents its own way of naming one there will be three ways to say "the CSVs in that
folder". A dataset row is small -- tenant, connection alias, path, format, a name, the audit columns
`Audited`/`AuditListener` already stamp automatically (`AuditListener.java:22-40`) -- and it is
exactly the `DatasetRef` inputs, so `DatasetResolver` remains the only thing that turns one into a
readable location.

**What must not happen.** A dataset row must not become a *second* source of truth for the bucket. It
stores the connection alias and the path; the bucket still comes from the connection record at
resolve time. Otherwise a connection repointed at a different bucket leaves saved datasets reading
the old one, and 3.3's central property quietly stops being true.

### 3.9 Phase two -- gaps 24 and 25, profiling and quality

**One scan, two tabs.** DuckDB's `SUMMARIZE` returns per-column count, null count, approximate
distinct, min, max, mean, standard deviation and quartiles in a single statement over the same
`scanExpression()` the schema and preview already use. Both the Profile tab (24) and the Quality tab
(25) should be derived from that one result rather than issuing a query each -- given gap 17, adding
two more sessions per file open is the wrong direction.

**Why this is the cheapest phase and should still not be started first.** It touches no new
infrastructure: no persistence, no SQL from a user, no writes. It is one more `run()` call, one more
DTO and one more tab, and it is genuinely useful on its own. But everything in section 4 that
precedes it is a correctness or tenancy fix on code that is already deployed, and shipping a new tab
on top of gap 9 would be the wrong order to explain later.

### 3.10 Gap 26 -- phase three, and why phase one shipped no SQL at all

**The decision.** Phase one accepts no SQL from anybody. Not a `WHERE` clause, not a filter
expression, not an `ORDER BY` -- the preview deliberately has none (`AnalyticsQueryService.java:100-
101`). Everything executed is built server-side from a `DatasetRef`.

**Why, when the engine could obviously do it on day one.** Because the safety case had not been
proven yet. The order in which this module was built is the argument: the lock-down and the governor
came **first**, and `DuckDbLockdownTest` exists so that the claim "a user's SQL cannot read
`/etc/passwd`" is a tested property of the running engine rather than a reasonable belief about a
configuration string. Shipping an editor in the same release as the sandbox that contains it would
have meant both were new at once, and the failure mode of getting it wrong is arbitrary file access
from inside the backend, running as the backend.

There is a second, less dramatic reason: an editor is the most visible part of a module and the least
useful one on its own. A user who can write SQL against a dataset they cannot yet profile, save,
chart or export has a worse experience than one who was told the feature reads files, which is what
it does.

**What phase three inherits, and what it must not do.** It inherits a session it cannot loosen, a
semaphore it cannot bypass and a timeout it cannot extend -- provided the SQL goes through
`AnalyticsQueryService`. That is stated as a rule in two class headers
(`AnalyticsQueryService.java:29-31`, `AnalyticsRestApi.java:36-38`) and it is the single most
important constraint in this document: **a query endpoint that opens its own connection is a second
door beside the locked one.**

Three things phase three has to add that phase one did not need:

- **Enforce `analytics.query.max-rows`.** Gap 14. Today the property clamps the preview page size and
  nothing else, while `AnalyticsLimits.java:36-40` describes it as a `LIMIT` rewrite. A user query
  with no `LIMIT` is exactly the case that javadoc was written for, and the code to match it does not
  exist yet.
- **Refuse the statements that are not reads.** `lock_configuration` stops a session being
  *reconfigured*; it does not stop `COPY … TO`, `ATTACH`, or an `INSTALL` of an extension that is
  already available. `disabled_filesystems` removes the local target for most of that, which is the
  defence in depth 2.1 records -- but "the filesystem is gone" is a weaker statement than "we only run
  `SELECT`", and phase three should be able to make the stronger one.
- **Decide what a syntax error looks like.** `explain()` (gap 20) currently maps engine strings to
  human sentences precisely *because* the user never sees the SQL. Once they write it, DuckDB's own
  message is the better answer for a syntax error and the worse answer for everything else, and
  `explain()` will need to tell those apart.

**The editor itself is Q1 and is not settled.**

### 3.11 Gaps 29, 30, 31, 32 -- phase four

**Charts (29) should reuse `shared/charts`, and where they should *live* is Q2.** The mechanical
question is easy: `shared/charts` already provides `BarChart`, `Donut`, `Histogram`, `daySeries`,
`statusColor` and `compactNumber`, the last of which this screen already imports (`analytics.ts:6`),
and phase one added no UI primitives on principle (row 8). The hard question is whether Analytics
Studio should have charts *of its own* at all, given `/reports` already has a ten-kind chart builder
over a pivot. That is Q2, the user has been warned about it, and it has not been decided.

**Export (30) has a worked example and a cautionary tale in the same file.**
`ReportExportServiceImpl` does download, bucket-write and endpoint-submit, and the shape is right.
But `reports` gaps 1-4 record that its submit destination is an outbound-request primitive available
to `TENANT_USER`, behind an address guard weaker than its sibling's, with no timeouts on the
`RestTemplate` and one of its properties undeclared -- and **all four are still open**. Analytics
export should not be built until those are closed, or it will inherit them by copy.

**Write-back (31) is the one to be careful with**, and it is marked High for a reason. Everything in
3.2 assumes analytics never writes. A derived dataset written back to a bucket has to go out through
the S3 secret, into the connection's own bucket, with `disabled_filesystems` still set -- a write to a
local path must remain impossible. If write-back ever needs `disabled_filesystems` relaxed, the
answer is no; the `DuckDbLockdownTest` assertion `aSessionCannotWriteAFileToTheLocalDisk:100` is the
line that must not move.

**Kafka events (32) are small but should be decided together with the audit question**, gap 21 and
Q5, because "a query finished" and "a dataset was read" are the same event seen from two sides.

### 3.12 Gap 33 -- phase five, and what would make it worth doing

**The claim to be proven.** The module's premise is that reading in place beats loading in (3.1), and
that Parquet beats CSV by enough to be worth telling users about. Neither is measured. The
`explain()` message *"Try a narrower dataset, or Parquet instead of CSV"*
(`AnalyticsQueryService.java:209`) already gives that advice to users, which is a good reason to know
whether it is true on this deployment.

**What a harness needs.** The same data written both ways, at more than one size, read through the
same path a user's request takes -- so through `AnalyticsQueryService`, under the same governor,
rather than a bare JDBC connection that would measure something else. Results want persisting (row
23) or the comparison is only ever against a number somebody remembers.

**Note the confound before it produces a wrong answer.** Gap 17 means a file open costs three
sessions. A benchmark that measures "opening a dataset" measures the session cost three times, and a
benchmark that measures one query does not measure what a user experiences. Whichever is chosen has
to be said in the result.

### 3.13 Gaps 15 and 16 -- the tests that are not there

**Backend (15).** Twenty tests were added and they cover the two classes whose correctness is a
security property. Nothing covers `AnalyticsQueryService` -- so the semaphore's refusal path, the
timeout, the page-size clamp and the whole of `explain()`'s mapping are unasserted -- and nothing
covers `AnalyticsRestApi`, so the `TENANT_USER` floor and the "business failure is a 200 with status
ERROR" convention are unproven. `AnalyticsQueryServiceTest` can be written with a mocked
`DuckDbSessionFactory` for the governor and the clamp, and with real `SQLException` messages for
`explain()`, which is the part most likely to be edited carelessly later.

**Frontend (16).** There is no `analytics.spec.ts`. The 580 figure is unchanged and this is why. What
is worth pinning: the four states of the dataset pane (nothing selected, loading, error, loaded), that
`readable()` and the server's format list agree, that `openFolderAsDataset` builds the pattern it
claims to, and that `pageCount`/`nextPage`/`previousPage` do not run off either end. Note `readable()`
(`Analytics.readable`, `analytics.ts:90-92`) is a **second copy** of the extension list that `DatasetRef.Format.of`
(`DatasetRef.java:42-50`) owns; the two agree today, and a test is the only thing that will notice
when they stop.

---

## 4. Ordering

**First, and before anything new: gaps 9, 10, 11, 12.** One commit, all in `DatasetResolver` and the
rail's connection list, and gap 9 is a tenancy hole in deployed code. Gap 9 must land with its test,
because the reason it survived review is that thirteen resolver tests never used a null tenant. Doing
these first means everything below can be scheduled rather than rushed.

**Second: gaps 22, 18, 14 and 20 -- the honesty pass.** Delete the dead `ToastService` injection; say
on screen that preview paging is unordered; correct the `max-rows` javadoc so it stops promising
something no code does. None of it is more than a few lines, and all of it is the difference between
a module that reads as finished and one that is.

**Third: gap 13, Azure.** Not because it is urgent but because it is a claim, and a claim decays. Q4
asks for a decision: verify it, or gate it and say so. Either answer is fine; leaving it is not.

**Fourth: gaps 15 and 16, the tests.** Before phase two adds a tab and before phase three adds a
door. `AnalyticsQueryServiceTest` first, because the governor is the thing phase three most depends
on and least visibly exercises.

**Fifth: gap 17, the caching.** Carry the count forward first -- it is one parameter and halves every
page turn. Cache schema and count only if the measurement still justifies it afterwards.

**Then phase two: gaps 24 and 25.** One `SUMMARIZE`, two tabs, no new infrastructure. This is where
new capability should start, and it is deliberately after everything above.

**Then gap 23, the persistence, on its own.** It blocks 27, 29, 31 and 33, it is the one change that
touches the database, and it should be reviewed as a schema decision rather than as part of whichever
feature happened to need it first.

**Then phase three: gaps 26, 27, 28.** In that order -- SQL, then the history and saved queries that
give it a memory, then joins. Gap 26 carries the three obligations in 3.10 and should not be
considered done without them.

**Then phase four: gaps 29, 30, 32, then 31.** Charts and export before write-back, and write-back
last because it is the only one that reopens a question the lock-down closed. Gap 29 must not start
until **Q2 is answered**, and gap 30 should not start until `reports` gaps 1-4 are closed.

**Last: gap 33, the benchmark.** It needs 23 for somewhere to put results and 17 closed so it is not
measuring the session cost three times.

**Gap 21 stays deferred at Q5.**

---

## 5. Out of scope

**Loading data into Postgres, in any form -- staging tables, materialised extracts, an import
button.** See 3.1. This is the decision the whole module rests on and it should be re-argued, not
quietly reversed by a feature that adds "just one small table" of file contents.

**A second copy of the storage walk.** The rail drives `features/objects/storage.service.ts` and
should keep doing so. If Analytics needs something the Object Browser's service does not offer, the
change belongs in that service, where both screens get it.

**A general-purpose SQL console over the application database.** Analytics Studio reads *files*.
The console had a Query Engine that read databases, and it was removed whole -- `V27.0-drop-query-
engine`, see `../discovery/risks.md` #46. Rebuilding it inside this module because there is now a
convenient engine to hand would be re-adopting a feature that was deliberately deleted, and it would
do so with a query engine chosen for object storage.

**Making DuckDB available to anything else in the backend.** `AnalyticsQueryService` is described in
its own header as *"the only place in this application where an analytics query runs"*, and
`DuckDbSessionFactory` as building *"the one kind of DuckDB connection this application is allowed to
have"*. Both statements are cheap to keep true today and expensive to recover once they are false. A
second consumer -- an ETL step, a converter, a report -- wants its own review, not a `@Autowired`.

**Closing the gap between `readable()` in the browser and `DatasetRef.Format.of` on the server.**
Two copies of the extension list, in two languages, and there is no shared artefact to put them in.
Recorded, and a test is the answer (3.13) rather than a refactor.

**Per-tenant storage of DuckDB extensions, or a warmed extension cache.** `INSTALL httpfs` runs on
every session open. It is idempotent and cheap after the first, but it is a real per-session cost
that a pool would have amortised and a session-per-query does not. Left alone deliberately: measuring
it belongs to gap 33, and optimising it before measuring it is how the pooling decision in 3.4 would
get reversed for the wrong reason.

---

## 6. Open questions

**Q1 -- Monaco, or a lighter editor, for phase three?**

Phase three needs somewhere to type SQL. Monaco is the obvious choice -- it is what VS Code uses, it
has real SQL syntax highlighting, bracket matching, multi-cursor and a completion API that could
eventually be fed the dataset's own column names. It is also roughly **2 MB** added to the bundle,
against a frontend that today declares four dependencies it never imports (`../discovery/risks.md`
#27) and hand-builds every chart as SVG rather than shipping ECharts. **Monaco is not in the project
today.**

The alternatives are CodeMirror 6 (far smaller, tree-shakeable, a real SQL mode, a less familiar API),
or a plain `<textarea>` with a monospace font and no highlighting at all.

**No recommendation yet, deliberately, but two things should inform it.** First, the route is already
lazy (`app.routes.ts:133-135`), so the cost lands on people who open Analytics Studio and nobody else
-- which makes 2 MB much easier to justify than it would be in the shell. Second, and cutting the
other way: the console has consistently chosen the smaller, hand-built option, and a 2 MB editor
would be the largest single dependency in the frontend by a wide margin. This wants a decision from
whoever owns the bundle budget, before phase three starts rather than during it.

**Q2 -- should Analytics Studio's charts land in the existing `/reports` pivot rather than becoming a
second dashboard system?**

**This is the most consequential open question in this document and it is not settled.** The user has
been warned about it and has not decided.

`/reports` already has a chart builder: four dimensions, sixteen measures, ten chart kinds, cell
drill-through and three export destinations, with the additivity rules worked out and tested
(`reports.md` 3.4). Phase four proposes charts over an analytics result. If those are built
separately, this codebase acquires **two** charting-and-export systems in two features -- which is
the exact duplication `reports.md` section 5 already records for `report-chart.ts` versus
`shared/charts`, one level up.

Three shapes are possible. (a) Analytics gets its own charts, and the console has two. (b) An
analytics result becomes a source the *existing* pivot can read, so there is one builder over two
kinds of data. (c) Analytics gets charts but no dashboard -- a chart of a result, never saved,
never assembled into a page -- which keeps only one dashboard system and gives up the least.

**A note on (b), which is the tempting one.** It is not as clean as it sounds: the reports pivot is
built around a **run** -- a `job_queue` row with known dimensions and a fixed measure list -- and an
analytics dataset has arbitrary columns of arbitrary types. Making the pivot generic is a real piece
of work on a screen that currently has four open security gaps of its own. So (b) is the right
long-term answer and the wrong immediate one, which is precisely why it needs deciding before phase
four starts and not during it.

**Q3 -- should the concurrency ceiling be per tenant?**

`analytics.query.max-concurrent=4` is a single JVM-wide `Semaphore` (`AnalyticsQueryService.java:62`).
One workspace can occupy all four slots and every other workspace gets "Too many analytics queries
are running right now." Gap 17 makes this easier to hit than the number suggests: a file open costs
three.

Options: (a) leave it, and raise the number; (b) a per-tenant sub-limit inside the global one; (c) a
permit pool per tenant.

**Recommendation: (b), and not yet.** (a) does not fix the shape -- it just moves the tenant who
loses. (c) means holding state per tenant for a bound that exists to protect a single JVM's memory,
which is over-engineering a ceiling of four. (b) -- a global ceiling with a per-tenant maximum of, say,
half of it -- keeps one bean and one refusal message. But this should wait until gap 17 is closed,
because halving the cost of a file open may make the whole question academic, and adding fairness
machinery to a limit that is being hit for an avoidable reason is fixing the wrong thing.

**Q4 -- Azure: verify it, or gate it?**

Gap 13. The branch exists and has never run against a real container.

Options: (a) stand up a container and verify it, closing the gap; (b) refuse `AZURE` in
`DatasetResolver` with an honest message ("Analytics Studio has not been verified against Azure Blob
yet") until somebody does; (c) leave it and let a user discover it.

**Recommendation: (a) if an Azure container can be had cheaply, otherwise (b). Not (c).** The cost of
(c) is that an Azure user's first experience of the module is a generic "The dataset could not be
read." from `explain()`'s unmapped branch -- the one failure mode this feature spent the most effort
avoiding everywhere else. (b) is four lines and turns an unknown into a stated limitation, which is
worse for the user than (a) and better than (c) for everyone reading this document in a month.

**Q5 -- does a dataset read need an audit trail, and whose is it?**

Gap 21. Reading a dataset writes nothing: no audit row, no Kafka event, only a `logger.debug` line
carrying the dataset and tenant (`AnalyticsQueryService.java:170-171`). The specification asked for
both.

This is the **same question `reports` Q3 asks**, and the recommendation there was: an info-level log
line now, and raise the real thing as a platform item because a scheme invented for one consumer will
not fit the others. That question named three remaining consumers -- the Object Browser's file share,
the document converter, and Reports. **Analytics Studio is now the fourth**, and it is the one with
the strongest case, because reading a dataset is a read of *customer data through a credential*
rather than a read of run metadata.

**Recommendation: raise it as a platform item with four named consumers, and do not invent a scheme
here.** In the meantime the `debug` line should probably be `info`: it already names the dataset and
the tenant, and `DatasetRef.toString()` was deliberately written to name the location without the
credentials that reach it (`DatasetRef.java:124-129`), so it is safe to log. That is a one-word change
and it makes "who read what" answerable by someone with log access, which is the realistic near-term
need.

**Q6 -- who owns the decision that phase three actually happens?**

Worth asking explicitly, because this document has recorded the same reasoning several times from
different directions: the lock-down, the governor, the narrow `run()` path, the "no second door"
rule, the `AnalyticsQueryService` header, and `DuckDbLockdownTest` all exist **for a feature that has
not been approved to be built beyond a plan.** That is the right order and the effort was not wasted
-- the phase-one module is safer for it regardless. But if phase three is never going to be built,
several things in this document become over-engineering rather than foresight, and somebody should
say so rather than leaving the module in a permanent state of preparing for something.

**No recommendation.** It is a product decision, not an engineering one. What engineering can assert
is the cost of the two answers: if phase three is going ahead, nothing here needs undoing. If it is
not, nothing here needs undoing either -- but the module should stop being described as phase one of
five, and rows 26 to 33 of the table above should move to `../old-scope/` with the reason attached,
rather than sitting open indefinitely.
