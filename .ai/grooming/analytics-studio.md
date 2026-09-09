# Grooming -- Analytics Studio

Feature `analytics-studio`, row 19 of [../discovery/features.md](../discovery/features.md). Status
**new** -- the old application has no analytics screen, so nothing below is a parity question. The
question is whether what was built is complete, correct, correctly authorized, and honest about
what it is not.

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

*Written 2026-09-08, the day phase one was designed, built, tested and deployed. Everything in
§2 was read from the source after the deployment; everything in §11 that is marked verified was
observed through the real API and the real UI against MinIO on the same day.*

**Read §2.4 before anything else if you are picking this up.** Phase one is a slice. It ships a
reader and a governor and nothing else -- no user-written SQL, no profiling, no charts, no
dashboards, no saved queries, no benchmarks. Those are phases two to five. A document that reads
as though the whole module shipped would mislead somebody within a month, so the boundary is
stated in its own subsection rather than left to be inferred from what the other sections do not
mention.

---

## 1. Purpose

"Show me what is actually in that file, without moving it anywhere."

Every other screen in this console that touches a file treats it as an opaque thing: the Object
Browser lists it, previews the first part of it and lets you download it; the converter turns it
into a different opaque thing; the file chat reads its text and asks a model about it. None of
them can answer the questions people actually have about a data file, which are boring and
structural:

> "How many rows is that? What are the columns called? What types did they come out as? Is the
> partition folder the pipeline wrote last night one dataset or forty broken ones?"

Analytics Studio answers those by pointing a query engine at the file **where it already lives**.
Nothing is copied into Postgres, nothing is staged on the application's disk, nothing streams
through Spring. A user picks a storage connection, walks the folders, clicks a file, and gets
Overview and Data with the columns beside the rows. A whole folder can be read as **one** dataset
by pattern, which is the case that made the feature worth building: a folder holding a file per
day or per partition is only meaningful read together.

The engine is DuckDB, embedded in the backend JVM, reading object storage over the S3 protocol
through its `httpfs` extension (`process/pom.xml:273-281`). It is deliberately not a second
application database, and the comment in the POM says so.

The feature owns no storage of its own. A dataset is a **connection alias plus a path inside it**,
and the connections come entirely from `storage-connections` (a `storage_connection` row). It
creates nothing, changes nothing and deletes nothing. It is a read.

---

## 2. Existing behaviour

### 2.1 The old app

**There is none.** `analytics` matches zero files in the whole of `scheduler1/src`, searched
case-insensitively on 2026-09-08, and `scheduler1/src/app/app.routing.ts` declares no analytics
route. This matches `.ai/discovery/features.md:285`. Nothing was migrated and nothing was lost;
§2.2 and §2.3 describe the whole of the feature.

### 2.2 The new app -- frontend

Three files under `scheduler1/next/src/app/features/analytics/`: `analytics.ts` (310 lines),
`analytics.html` (308) and `analytics.service.ts` (59). **No spec file.** No other file in
`scheduler1/next/src` references the feature.

*The screen changed materially later on 2026-09-08, after the deployment and after row 19 of
`features.md` was written. The Schema tab was folded into a columns rail that sits beside the rows
inside the Data tab, and a folder filter was added to the storage rail. §2.2.3 records the change.
`features.md:285` described three tabs when this was written; **it was corrected the same day**,
so the two no longer disagree.*

#### 2.2.1 The storage rail

The left column is the same connection → folder → file walk the Object Browser does, driven by
**that screen's own service**, not a second copy of it: `analytics.ts:7` imports `BucketSummary`,
`ObjectSummary` and `StorageService` from `../objects/storage.service`, and calls `buckets()`
(`:123`) and `listObjects()` (`:169`) on it.

- **Connection picker.** A `<select>` fed by `storage.json/buckets`, showing `label · provider`
  (`analytics.html:21-26`). On load the screen opens on the **first** connection rather than an
  empty shell, with a comment saying why (`analytics.ts:128-130`).
- **Breadcrumbs.** `root` plus one button per prefix segment, rebuilt by the `crumbs` computed
  (`analytics.ts:66-69`, template `analytics.html:29-36`).
- **Folder filter.** A search input filtering the current folder by name (`analytics.html:38-44`,
  `analytics.ts:63`, `:72-80`). It is local to the folder and the label says so -- "Filter this
  folder" -- because `listObjects` returns one prefix at a time and a bucket-wide search would be
  a request the API does not offer (comment at `analytics.ts:56-62`). Cleared on every navigation:
  `pickConnection` (`:141`), `openFolder` (`:148`), `goToCrumb` (`:154`), `goToRoot` (`:160`).
- **Entries.** Folders first, then files (`analytics.ts:78-79`). A file the reader cannot open is
  **shown but inert** rather than hidden -- greyed, `disabled`, with a title saying why
  (`analytics.html:64-84`) -- on the stated reasoning that knowing an unreadable file is there
  beats it vanishing (`analytics.html:65-66`). `readable()` tests the same extension set the
  backend accepts (`analytics.ts:88-90`).
- **"Read the folder as one dataset."** A row of buttons, one per extension actually present in
  the folder (`folderFormats`, `analytics.ts:203-210`; template `analytics.html:97-113`). Clicking
  `all *.csv` loads `<prefix>*.csv` as a single dataset (`openFolderAsDataset`, `:197-200`).
- **Empty state.** "Nothing in this folder matches …" when a filter is set, "This folder is empty."
  when it is not (`analytics.html:86-93`) -- the two facts are distinguished, with a comment saying
  that is the point.

#### 2.2.2 The dataset panel

With no dataset chosen: a card saying "Pick a file to read it." and naming the four formats
(`analytics.html:119-126`).

With one chosen:

- **Header.** Dataset name (the last path segment, or the pattern itself -- `datasetName`,
  `analytics.ts:110-114`), a format pill, a `folder dataset` pill when the path is a pattern, and
  the `connection/path` in mono (`analytics.html:130-138`).
- **The figures strip.** Rows and columns carry weight; size on disk and modified time are
  metadata beside them, and the multi-file note is a sentence rather than a tile
  (`analytics.html:144-170`). A comment at `:140-143` records that this replaced four
  `app-stat-tile`s and why -- "CSV" and "208 B" rendered at 20px read as numbers that are not
  numbers.
- **Tabs.** Overview and Data (`analytics.html:172-185`, type `Tab` at `analytics.ts:17`).
- **Overview.** A "What this is" note stating the file is not copied, imported or cached, and a
  definition list of Location / Rows / Columns / Modified (`analytics.html:188-224`). When the
  dataset is multi-file it adds a paragraph explaining that every figure covers every matching
  file, that columns present in only some files are still included, and that a row carries the
  file it came from (`:217-222`).
- **Data.** A two-column grid: the rows in a `TableShell` on the left, a Columns rail on the right
  (`analytics.html:229`, `:281-301`). The comment at `:227-228` gives the reasoning -- "what type
  is this column" is asked *while* looking at the values, and a Schema tab made that a round trip.
  A `null` cell renders as an italic muted `null`, deliberately distinguished from an empty string
  (`:249-255`).
- **Paging.** Previous / Next plus "Page N of M · K rows a page", shown only when there is more
  than one page (`analytics.html:263-278`; `nextPage` / `previousPage`, `analytics.ts:261-269`).
  The pager sits **outside** the `TableShell`, as a sibling.

#### 2.2.3 What changed later on 2026-09-08

| Change | Evidence | What it closed |
|---|---|---|
| Schema tab → a columns rail inside Data | `analytics.ts:10-17` (the `Tab` type's own doc records it), `analytics.html:227-228`, `:281-301` | Reading a value and reading its type were mutually exclusive |
| Four stat tiles → a figures strip | `analytics.html:140-170` | Three of the four tiles held short strings, not figures, and the row stood 101px tall to say four short things |
| Folder filter added | `analytics.html:38-44`, `analytics.ts:56-80` | No way to find a file in a folder of a hundred |
| Filter cleared on every navigation | `analytics.ts:141`, `:148`, `:154`, `:160` | The defect §12.5 of `object-browser.md` records against the Object Browser, avoided here rather than repeated |
| Modified time formatted | `modifiedAt()`, `analytics.ts:290-295`, used at `analytics.html:161` and `:210-213` | The raw ISO string rendered as `2026-09-08T14:55:40.779Z` |
| `StatTile` and `ToastService` imports dropped | Neither survives in the import block (`analytics.ts:3-8`), the `imports` array (`:36`) or the injected fields (`:41-45`) | Two dead imports left behind by the two changes above |

The last three of these were the same day's second pass, and they close A3, A4 and A5 -- all three
of which this document recorded as open before the pass landed. They are kept in §12, marked, rather
than deleted, so the record of what the first build shipped survives.

#### 2.2.4 The service

`analytics.service.ts` -- two methods, `schema()` (`:46-50`) and `preview()` (`:52-58`), against
`{API_BASE}/analytics.json`. Three interfaces mirror the server DTOs. Two comments carry design
decisions: rows are arrays rather than objects because that halves the payload on a wide file and
preserves column order (`:22-26`), and there is **no bucket parameter to pass**, because the
bucket comes from the connection record on the server (`:34-40`). `preview()` omits `pageSize`
when it is absent rather than sending a size the server would only clamp (`:55-56`).

### 2.3 The backend

Eight new classes in `process/src/main/java/process/analytics/` (951 lines including DTOs) plus
one controller.

| File | Lines | What it is |
|---|---|---|
| `AnalyticsLimits.java` | 93 | `@Component` reading six properties. The whole policy in one bean, "so it can be read in one sitting, asserted in one test, and changed per environment without hunting" (`:16-17`) |
| `DuckDbSessionFactory.java` | 239 | Builds the only kind of DuckDB session the application is allowed to have. See §8 |
| `DatasetRef.java` | 130 | A location the server has agreed to read. `Format` enum CSV/TSV/JSON/PARQUET (`:25-52`); **package-private constructor** (`:59`) |
| `DatasetResolver.java` | 110 | The only way to obtain a `DatasetRef` |
| `AnalyticsException.java` | 24 | A failure whose message was written for a person |
| `AnalyticsQueryService.java` | 225 | The only place in the application an analytics query runs |
| `dto/ColumnDto.java` | 29 | Name + DuckDB's own type name, kept untranslated on purpose (`:6-8`) |
| `dto/DatasetSchemaDto.java` | 44 | bucket, path, format, multiFile, columns |
| `dto/DatasetPreviewDto.java` | 57 | columns, rows, page, pageSize, totalRows, multiFile |
| `api/AnalyticsRestApi.java` | 109 | Two GETs |

**`DatasetRef` is the type that makes one rule structural rather than remembered.** Its
constructor is package-private and `DatasetResolver` is its only caller, so the tenant, path and
format checks cannot be skipped at a call site -- there is no call site that can skip them
(`DatasetRef.java:12-19`, `DatasetResolver.java:15-18`). `url()` (`:94-97`) emits `s3://` for both
S3 and MinIO (the endpoint that separates them lives on the secret, not in the URL) and `azure://`
for Azure Blob. `scanExpression()` (`:107-122`) picks the reader from the format and turns on
`union_by_name` and `filename` for a multi-file dataset, so a folder whose files gained a column
over time still reads as one table and a row can be traced back to its file.

**`AnalyticsQueryService`** exposes three operations: `schemaOf` (`:71-84`, a `DESCRIBE SELECT *`),
`preview` (`:93-128`) and `rowCount` (`:131-134`). All three go through one private `run()`
(`:150-179`) which takes a semaphore permit, opens a session, sets the statement timeout and closes
both. `preview` has **no ORDER BY**, with the reasoning in a comment at `:100-101`. `explain()`
(`:189-218`) maps DuckDB failures to human sentences.

`AnalyticsRestApi` is `@RequestMapping("/analytics.json")` with class-level
`@PreAuthorize("hasRole('TENANT_USER')")` (`:42-43`) and no method-level override. Its javadoc
(`:22-41`) states the API's central property and records that there is deliberately no endpoint
accepting SQL.

### 2.4 What phase one deliberately does **not** do

This list is not a backlog of oversights. Each item was decided against for phase one and is
scheduled for a later phase of the plan the user approved.

| Not built | Phase |
|---|---|
| User-written SQL of any kind. No endpoint accepts a query string; `AnalyticsRestApi:36-38` says so | three |
| Column profiling -- distinct counts, null counts, min/max, histograms | two |
| Data quality checks | two |
| Charts built from a dataset | four |
| Dashboards | four |
| Saved queries, query history | three |
| Benchmarks | five |
| Persisting a dataset. There is no `AnalyticsDataset` row; a selection lives only in the component's signals | -- |

**The governor and the session lock-down were built first, before any of the above, precisely so
phase three has somewhere safe to land.** That is the load-bearing decision of this phase: when
user SQL arrives it arrives at `AnalyticsQueryService`, against a session already locked down by
`DuckDbSessionFactory`, under the same semaphore and the same timeout, rather than opening a
second door beside this one (`AnalyticsQueryService.java:29-31`, `AnalyticsRestApi.java:36-38`).

---

## 3. Expected behaviour

Phase one's expected behaviour is what §2 describes; it was built to a plan rather than migrated
from a predecessor, so this section is a list of **deltas** -- places where what is there today
falls short of what phase one itself claimed, plus the two properties phase two must not break.

1. **A connection offered in the picker must be readable, or the refusal must explain the real
   reason.** Today the picker is fed by `storage.json/buckets`, which includes legacy `BUCKET_LIST`
   lookup buckets (`StorageBrowserServiceImpl.java:114-133`), and the resolver only looks up
   `storage_connection` rows (`DatasetResolver.java:74-82`). The reader is told "Storage connection
   not found." about a connection sitting in front of them. See §12, A2.
2. **What Analytics Studio may read must be no wider than what the Object Browser may read.**
   Today it is wider in two ways -- a platform-owned connection (A1) and an `Inactive` connection
   (A21). Both are §8 questions, not cosmetic ones.
3. **A page turn must show the page.** A stale error currently covers it. See A6.
4. **A folder listing must either be complete or say it is not.** The rail stops at 100 entries
   with no continuation and no notice. See A9.
5. **A reader must be told that paging is unordered**, or the paging must be ordered. Today
   neither: the absence of `ORDER BY` is documented in the service comment
   (`AnalyticsQueryService.java:100-101`) and nowhere on the screen. See A11.
6. **A dataset read must leave a record.** The spec asked for an audit-log entry and a Kafka event.
   Neither exists; the only trace is a debug log line. See A18 and §13.
7. **Azure must be tested before it is offered.** The branch exists and has never run against a
   real container. See A16.

Everything else -- two tabs rather than three, a strip rather than four tiles, a columns rail
rather than a Schema tab -- is a deliberate design decision recorded in §2.2.3 and is not a gap.

---

## 4. Frontend requirements

### 4.1 Route and navigation

| | Value |
|---|---|
| Route | `analytics`, lazy, a child of the shell (`app.routes.ts:129-135`) |
| Guard | **No `roleGuard` and no `data.minRole`.** Only the shell's own `canActivate: [authGuard]` and `canActivateChild: [passwordChangeGuard]` apply |
| Why | A comment above the route says so (`app.routes.ts:130-132`): open to `TENANT_USER` like the Object Browser it reads from, because which connections a caller may reach is settled per request against each connection's own tenant, not by a role on the route |
| Nav | `features/shell/shell.ts:94-95` -- "Analytics Studio", icon `chart`, hint "Read a file as data, where it lives", inside the **Object Browser** group beside "Browse files" |
| Why there | The group comment (`shell.ts:88-89`): "Both screens are the same bucket, seen two ways: one browses the objects, the other reads what is inside them. They share a storage service, so they share a menu" |

Unlike `/reports`, whose openness is undocumented (`reports.md` §4.1), this route carries the
comment. That is the right pattern and is worth keeping.

### 4.2 Components and reuse

| Thing | File | Note |
|---|---|---|
| `Analytics` | `features/analytics/analytics.ts` + `.html` | Standalone, signals throughout, `OnInit` |
| `AnalyticsService` | `features/analytics/analytics.service.ts` | `schema()`, `preview()` |
| `StorageService` | `features/objects/storage.service.ts` | **Reused, not copied.** This is now its second consumer |
| `TableShell` | `shared/ui/data-table.ts` | The rows table and its loading / error / empty states |
| `Icon` | `shared/ui/icon.ts` | `folder`, `file`, `chart`, `search` |
| `formatSize` | `shared/ui/format-size.ts` | Bound as `humanSize` (`analytics.ts:44`) |
| `compactNumber` | `shared/charts/number-format.ts` | Bound as `compact` (`analytics.ts:45`) |
| ~~`StatTile`~~ | `shared/ui/stat-tile.ts` | Used for four tiles in the first build; replaced by the figures strip and the import removed the same day. See A3 |

**No new UI primitive was introduced.** That is the point of the screen's shape and is the second
edge in the dependency graph (`.ai/discovery/features.md:567-573`). The practical consequence
recorded there holds: `storage.service.ts` now has two consumers, and this one is the one without
a spec.

The one thing built by hand rather than reused is the pager (`analytics.html:263-278`). That is
correct -- `shared/ui/pager.ts` is a **client-side** pager that slices an array already in memory
(`:20-24`), and this paging is server-side.

### 4.3 Controls

| Control | Where | Behaviour |
|---|---|---|
| Connection `<select>` | `analytics.html:21-26` | `pickConnection` resets prefix, filter and dataset, then lists the root (`analytics.ts:138-144`) |
| `root` / breadcrumb buttons | `analytics.html:30-35` | `goToRoot` / `goToCrumb`; both clear the filter |
| Folder filter | `analytics.html:38-44` | Client-side, over the loaded page only, `includes` on the lowercased name (`analytics.ts:72-76`) |
| Folder button | `analytics.html:54-63` | `openFolder`, clears the filter |
| File button | `analytics.html:67-84` | `openFile`; a no-op guarded twice -- `disabled` in the template and an early return at `analytics.ts:185` |
| `all *.<ext>` | `analytics.html:105-110` | `openFolderAsDataset`; clears `selected` so the strip shows no file size |
| Overview / Data tabs | `analytics.html:172-185` | `tab.set(...)`; `load()` resets to `overview` (`analytics.ts:214`) |
| Previous / Next | `analytics.html:270-275` | Disabled at the ends and while `loading()` |
| Try again | inside `TableShell` (`shared/ui/data-table.ts:51-53`) | `retry()` → `load(path())`, which re-reads the schema **and returns to page 0** (A7) |

There are **no dialogs and no forms** on this screen. Nothing is created, edited or deleted, so
there is nothing to confirm.

### 4.4 States

| State | Rendering |
|---|---|
| Connections loading | None. The `<select>` is empty until `buckets()` resolves (`analytics.ts:122-134`) |
| Connections failed | `browseError` line in the rail, `role="alert"` (`analytics.html:46-48`) |
| No connections at all | **Nothing.** The picker is an empty `<select>` and the panel says "Pick a file to read it." See A22 |
| Folder listing | "Reading…" in the rail (`analytics.html:51-52`) |
| Folder empty | "This folder is empty." (`analytics.html:91`) |
| Folder filtered to nothing | `Nothing in this folder matches "<term>".` (`analytics.html:90`) |
| Folder listing failed | `browseError` line (`analytics.html:46-48`) |
| No dataset chosen | Card: "Pick a file to read it." + the four formats (`analytics.html:119-126`) |
| Dataset loading | `TableShell` spinner, "Loading…" (`data-table.ts:42-46`) |
| Dataset failed | `TableShell` error panel + "Try again" (`data-table.ts:47-54`), showing the server's own message unchanged (`analytics.ts:226`, and the comment above it) |
| Dataset empty | "This dataset has no rows." (`analytics.html:235`) |
| No columns | "No columns detected." in the rail (`analytics.html:295-297`) |

### 4.5 Dark and light mode

Every colour on this screen is a token: `var(--text-muted)`, `var(--text-secondary)`,
`var(--surface-sunken)`, `var(--focus-ring)`, `var(--chart-0)`, `border-subtle`, `text-crit-500`,
`pill-neutral`, `pill-brand`. There is no literal colour anywhere in `analytics.html`. Verified
live on 2026-09-08: dark mode correct, no console errors.

### 4.6 Responsive behaviour

- The page is a two-column grid, `lg:grid-cols-[260px_minmax(0,1fr)]`, stacking below `lg`
  (`analytics.html:14`).
- The Data tab is `xl:grid-cols-[minmax(0,1fr)_220px]`, so the columns rail drops beneath the rows
  below `xl` (`analytics.html:229`).
- The rail's entry list is a `scroll-table` box (`analytics.html:50`), and the rows table scrolls
  inside `TableShell`'s own `overflow-x-auto` (`data-table.ts:66`).
- The figures strip and the header are `flex-wrap` (`analytics.html:130`, `:144`).
- Every `min-w-0` that a truncating flex child needs is present (`:17`, `:117`, `:230`, `:281`,
  `:289`). Verified live: no page overflow.

---

## 5. Backend requirements

### 5.1 Endpoints

`AnalyticsRestApi` -- `@RequestMapping("/analytics.json")`, class-level
`@PreAuthorize("hasRole('TENANT_USER')")` (`:43`), **no method-level override on either method**,
so the class annotation stands for both. Because `@PreAuthorize` is not repeatable, that is the
thing to check on every controller in this codebase; it is clean here.

| Method | Path | Params | Role | Returns |
|---|---|---|---|---|
| GET | `/analytics.json/schema` | `connection` (required), `path` (required) | TENANT_USER | `DatasetSchemaDto` -- bucket, path, format, multiFile, columns |
| GET | `/analytics.json/preview` | `connection`, `path`, `page` (default `0`), `pageSize` (optional) | TENANT_USER | `DatasetPreviewDto` -- columns, rows, page, pageSize, totalRows, multiFile |

**The caller names a CONNECTION and a path inside it. It never names a bucket and it never names a
URL.** This is the feature's central design point and it belongs wherever the API is described.
The bucket comes from the `StorageConnection` record -- `getBucketName()`, falling back to the
alias, which is what `StorageBrowserServiceImpl` already does (`DatasetResolver.java:89-93`,
against `StorageBrowserServiceImpl.java:544-546`). So *"use these credentials against a different
bucket"* is not a request this API can express.

That was a mid-build change. The first design took `storageConnectionId + bucket + path`. Moving
to the alias both matched the Object Browser -- so the two screens now address storage identically
-- and removed a whole class of request. One test became obsolete as a result and was replaced by
one asserting the stronger property:
`DatasetResolverTest.takesTheBucketFromTheConnectionRecord_notFromTheRequest` (`:157-170`), whose
own comment calls it "the strongest property this class has".

**Business failures are HTTP 200 with a `ResponseDto` of status `ERROR`**, per house convention
(`AnalyticsRestApi.java:71-75`, `:100-102`, with the comment at `:72-73` saying the message was
written for a reader by whoever threw it and is returned as-is). Only an unexpected exception
produces a 500, and that one returns `ProcessUtil.INTERNAL_ERROR_500` after logging the stack
(`:76-80`, `:103-107`).

### 5.2 Classes and responsibilities

| Class | Responsibility |
|---|---|
| `DatasetResolver` | The gate. Path allow-list, `..` check, alias lookup, status, tenancy, provider, bucket, format. Throws `AnalyticsException` with a message for a user |
| `DatasetRef` | An agreed location. Package-private constructor; produces the URL and the scan expression |
| `DuckDbSessionFactory` | Builds and locks down a session. Decrypts the connection's credentials and attaches them as a SECRET |
| `AnalyticsQueryService` | The governor and the only executor. Semaphore, timeout, session-per-query, error mapping |
| `AnalyticsLimits` | Six properties in one bean |
| `AnalyticsException` | The distinction between a failure the user can fix and one they cannot (`:5-11`) |

### 5.3 Configuration

Six properties, declared in **all three** of `application-dev.properties` (`:137-142`),
`application-stage.properties` (`:140-145`) and `application-prod.properties` (`:140-145`), each as
`${ENV_VAR:default}`, under a shared comment saying DuckDB runs inside this JVM.

| Property | Default | Consumed at |
|---|---|---|
| `analytics.query.timeout-seconds` | 30 | `AnalyticsQueryService.java:167`, `:195` |
| `analytics.query.max-rows` | 10000 | `AnalyticsQueryService.java:139` only -- see A13 |
| `analytics.query.max-concurrent` | 4 | `AnalyticsQueryService.java:62` |
| `analytics.preview.page-size` | 100 | `AnalyticsQueryService.java:138` |
| `analytics.duckdb.memory-limit` | 512MB | `DuckDbSessionFactory.java:101` |
| `analytics.duckdb.threads` | 2 | `DuckDbSessionFactory.java:102` |

All six were added to the existing `ApplicationPropertiesDeclarationTest` (`:46-51`), under a
comment giving the reason: **an absent limit is an unlimited one**, and DuckDB runs in this JVM,
so a missing memory ceiling is the container's OOM killer taking the ETL dispatcher down with the
query (`:43-45`). None is a secret, so none appears in that test's `SECRETS` list.

**Dependency added:** `org.duckdb:duckdb_jdbc:1.1.3` in `process/pom.xml:277-281`, with a comment
at `:273-276` recording that it is embedded, reads object storage over S3 through `httpfs`, and is
deliberately not a second application database. The jar is roughly 70 MB and ships native
libraries. Runtime verified 2026-09-08: Java 17 Temurin, linux/aarch64, Ubuntu 26.04.

---

## 6. Database requirements

**None. Phase one adds no database objects at all** -- no table, no column, no migration, no seed
row. `features.md:53` records the same.

No `AnalyticsDataset`, `SavedQuery`, `QueryHistory`, `Dashboard` or `BenchmarkResult` entity
exists. A dataset is not persisted; a selection lives only in the component's signals
(`analytics.ts:94-103`) and is gone on reload.

The one table the feature reads, it reads through another feature's repository:

| Table | Columns read | Owner |
|---|---|---|
| `storage_connection` | `alias`, `bucket_name`, `provider`, `status`, `tenant_id`, plus the encrypted credential columns `access_key`, `secret_key_enc`, `region`, `endpoint`, `azure_connection_string_enc` | `storage-connections` |

Read via `StorageConnectionRepository.findByAlias` (`DatasetResolver.java:74-75`) and, for the
credentials, off the same entity inside `DuckDbSessionFactory.s3Secret` (`:144-169`) and
`azureSecret` (`:171-179`).

When phase two or three needs to persist a dataset or a saved query, **that is the point at which
this feature acquires a schema**, and it should acquire a tenant column and a Hibernate
`tenantFilter` at the same time, because it currently has neither and cannot -- see §8, layer 4.

---

## 7. Validation

Every rule, and where it is enforced.

| # | Rule | Client | Server | Verdict |
|---|---|---|---|---|
| V1 | A connection must be named | The picker always has one selected (`analytics.ts:130`) | `"Pick a storage connection first."` (`DatasetResolver.java:57-59`) | Both |
| V2 | A path must be named | `load()` is only called with one; `loadPage` returns early on an empty path (`analytics.ts:243`) | `"Pick a file or a folder pattern first."` (`:60-62`) | Both |
| V3 | Leading `/` is stripped | none | `path.trim().replaceAll("^/+", "")` (`:64`) | **Server only** -- and correctly so. This is what confines an absolute path like `/etc/passwd.csv` into the connection's bucket |
| V4 | The path matches `[A-Za-z0-9._*?/=+ -]+` | none | `SAFE_PATH` (`:36`, `:65-67`) | **Server only** -- correctly. An allow-list, deliberately: the comment at `:31-35` says a deny-list "invites the reader to think of one more encoding". No quote, no backslash |
| V5 | The path contains no `..` | none | A separate check **after** the allow-list (`:70-72`), because `..` is made of permitted characters | **Server only** |
| V6 | The connection exists, is not soft-deleted, and is visible to the caller | The picker only lists the caller's own | `findByAlias` + `status != Delete` + `TenantOwnership.isVisibleToCaller` (`:74-82`) | **Server only** -- and see A1 and A21 |
| V7 | The provider is an object store | none | `provider.isObjectStore()` (`:84-87`), and again by name in the session factory's `default:` branch (`DuckDbSessionFactory.java:135-141`) | **Server only**, twice |
| V8 | The bucket name matches `[A-Za-z0-9._-]+` | n/a -- the client cannot send a bucket | `SAFE_BUCKET` (`:39`, `:94-97`) | **Server only.** It guards a value that came from the database, not from the request, which is the right instinct: the bucket is interpolated into SQL |
| V9 | The extension is one of csv/tsv/json/jsonl/ndjson/parquet | `readable()` (`analytics.ts:88-90`) disables the row | `Format.of` returning null → `"Analytics Studio does not read this file type yet."` (`DatasetResolver.java:99-103`) | Both. The two lists agree, character for character -- unlike the Object Browser's preview lists, which do not (`object-browser.md` §12.3) |
| V10 | `page` ≥ 0 | Buttons disabled at the ends (`analytics.html:271`, `:274`) | `Math.max(0, page)` (`AnalyticsQueryService.java:97`) | Both |
| V11 | `pageSize` ≤ `analytics.query.max-rows` | The client never sends one (`analytics.service.ts:55-56`) | `pageSize()` clamps (`AnalyticsQueryService.java:137-140`) | **Server only**, and the controller's javadoc says the page size is "a request, not an instruction" (`AnalyticsRestApi.java:86-87`) |
| V12 | `analytics.duckdb.memory-limit` looks like `512MB` | n/a | `sanitiseSetting` regex `[0-9]+[A-Za-z]{0,3}`, throwing rather than escaping (`DuckDbSessionFactory.java:221-227`) | **Server only.** This validates a *property*, not user input -- see §8 |
| V13 | A credential cannot end its SQL literal | n/a | `quote()` doubles single quotes (`DuckDbSessionFactory.java:210-212`) | Server only |
| V14 | A path cannot end its SQL literal | V4 already forbids the quote | `scanExpression()` doubles it anyway (`DatasetRef.java:108`) | Server only, **belt and braces** |

**Findings.** Every rule that matters is enforced on the server, and most are enforced *only*
there, which is the correct side. The two client-side checks (V9's `readable()`, V10's disabled
buttons) are cosmetic by design -- their job is to stop offering a click that returns a refusal.
Nothing in this feature is client-only in a way that matters.

Two things are worth naming as unusually good practice, because they are the pattern to copy:

- **V4 is an allow-list and V5 is a separate check.** The comment at `DatasetResolver.java:68-69`
  explains exactly why the second exists: `..` is made of permitted characters, so it is the one
  shape the allow-list cannot exclude.
- **V12 validates a configuration property before interpolating it.** The value comes from a
  properties file rather than a user, but a mistyped `analytics.duckdb.memory-limit` of
  `512MB'; SET lock_configuration=false` would otherwise be a configuration file that unlocks the
  engine. There is a test for it (`DuckDbLockdownTest:166-178`).

---

## 8. Security

**This is the most important section in this document.** The feature's whole purpose is to point a
query engine at a file a user chose, and phase three will let users write the SQL. What follows is
what makes that safe to build.

### 8.1 The threat is inverted

Normally a database is trusted and the input is not. Here the **engine is the dangerous
component**. DuckDB can read and write local files, open network sockets and install extensions,
and it does all of that **inside this JVM, as the backend process**. A session handed unguarded to
a feature whose point is running user-chosen queries is arbitrary file access from inside the
application, running with the application's own privileges: the deployment's `.env`, the
application jar, mounted secrets, `/proc`.

Both class javadocs state this explicitly and it is the correct frame to hold while reading the
rest of this section: `DuckDbSessionFactory.java:18-23` and `DuckDbLockdownTest.java:31-36`.

The consequence for the four-layer model this document family uses: **layers 1 and 2 are close to
irrelevant here, layer 3 carries everything, and layer 4 does not exist.** That is the same
conclusion `object-browser.md` §8 reaches for the same underlying reason -- buckets are not rows,
so a row filter could never have decided bucket access.

### 8.2 Layer 1 -- Frontend guard

`app.routes.ts:129-135`. **No `roleGuard`, no `data.minRole`.** Only the shell's `authGuard` and
`passwordChangeGuard` apply, so any signed-in user with a changed password reaches the screen.

This is deliberate and the comment above the route says so (`:130-132`). It matches
`/ai/agents`, which is left open for a comparable reason. **The frontend never decides who may
read what** -- it decides whether the page is worth rendering. Every actual decision is made per
request in layer 3.

Note the asymmetry with `/objects`, which *does* carry `roleGuard` with `minRole: 'TENANT_USER'`
(`object-browser.md` §8, layer 1). The two screens read the same connections through the same
service and reach the same server floor, so one of them is guarded on the route and one is not.
Neither is wrong -- the guard is not the enforcement in either case -- but the inconsistency is
worth knowing before somebody "fixes" one of them.

### 8.3 Layer 2 -- Controller `@PreAuthorize`

`AnalyticsRestApi.java:43` -- class-level `hasRole('TENANT_USER')`, no method-level override on
`schema` (`:63-66`) or `preview` (`:89-94`).

The hierarchy is `ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN > ROLE_TENANT_USER`
(`config/MethodSecurityConfig.java:29`), so all three roles pass. **The role is only a floor**, and
the controller's javadoc says so in as many words (`:32-34`): which connections a caller may reach
is not a question a role can answer.

The floor matches the Object Browser's (`StorageBrowserRestApi.java:36`) on purpose, so the
analytics API is not a privilege-escalation path around the screen it reads from.

### 8.4 Layer 3 -- The service rule, in two halves

Everything real happens here, and it happens in two separate places for two separate reasons.

#### 8.4.1 `DatasetResolver` -- before a session is opened

In order (`DatasetResolver.java:56-105`):

1. **Blank connection / blank path** → `"Pick a storage connection first."` /
   `"Pick a file or a folder pattern first."` (`:57-62`).
2. **Leading slashes stripped** (`:64`). This is what confines an absolute path: `/etc/passwd.csv`
   becomes `etc/passwd.csv`, which is a key *inside the connection's bucket*.
3. **Allow-list on the path**, `[A-Za-z0-9._*?/=+ -]+` (`:36`, `:65-67`). Notably absent: the quote
   that would end a SQL literal, and the backslash that would escape one.
4. **A separate `..` check** (`:70-72`), because `..` is made of permitted characters.
5. **`findByAlias`, then `status != Delete`, then `TenantOwnership.isVisibleToCaller`** (`:74-82`).
6. **`provider.isObjectStore()`** (`:84-87`) -- FTP and FTPS refused with a reason.
7. **The bucket from the record**, `getBucketName()` falling back to the alias, then checked
   against `SAFE_BUCKET` (`:89-97`).
8. **Format from the extension** (`:99-103`).

Only then is a `DatasetRef` constructed (`:104`), and its constructor is package-private, so
nothing else in the application can construct one.

**The refusals are deliberately uniform.** A connection that belongs to another workspace and a
connection that does not exist produce the identical string, `"Storage connection not found."`,
with the comment at `:79-80` giving the reason: a different message for each would let a caller
walk the alias space and learn which connections other workspaces own. Both cases are pinned by
tests that assert the same literal (`DatasetResolverTest:98-117`).

#### 8.4.2 `DuckDbSessionFactory` -- what the session may do once it exists

`open()` (`:76-98`) performs five steps **in this order, and the order is load-bearing**:

| # | Step | Code | Why it is where it is |
|---|---|---|---|
| 1 | `SET memory_limit` / `threads` / `preserve_insertion_order=false` | `:100-106` | Bounds what a query can consume. `preserve_insertion_order=false` and no `temp_directory` together mean a spill cannot quietly create files beside the application (`:103-104`) |
| 2 | `INSTALL` + `LOAD` `httpfs` (S3, MinIO) or `azure` (Azure Blob) | `:123-134` | Must precede step 4: installing an extension is itself a local-filesystem write. FTP/FTPS hit the `default:` branch and are **refused by name** (`:135-141`) rather than failing later inside a scan |
| 3 | `CREATE OR REPLACE SECRET analytics_store (…)` | `:128`, `:133`, built at `:144-179` | Credentials are attached as a SECRET, **never interpolated into query text**, so they cannot surface in a query plan or an error message. The javadoc at `:32-34` names the difference from the older `SET s3_access_key_id` style, whose values turn up in anything that echoes a statement |
| 4 | `SET disabled_filesystems='LocalFileSystem'` | `:191` | Removes the local reader **entirely**, so a query naming a path on disk fails at the filesystem layer rather than being caught by a validator somebody could later forget to call (`:183-186`) |
| 5 | `SET lock_configuration=true` | `:192` | **Last**, so nothing downstream can loosen any of the above -- including a user's SQL, once phase three exists (`:186-188`) |

Three further properties of the factory:

- **A session that fails part-way through configuration is closed rather than returned**
  (`:87-97`). The comment says why: a half-configured session is an unlocked one and must never
  escape the method. This is the kind of thing that is obvious in hindsight and absent in most
  implementations.
- **The driver is loaded in a static block** (`:53-60`) rather than by JDBC auto-discovery, so a
  native-library failure names itself at startup instead of surfacing as a `ClassNotFound` inside
  the first request after a restart.
- **The memory-limit property is regex-restricted before interpolation** (`:221-227`), because it
  is the one value in the whole factory that is interpolated into SQL rather than parameterised or
  quoted.

#### 8.4.3 `AnalyticsQueryService` -- the governor

`run()` (`:150-179`) applies three limits together, and the comment at `:143-148` explains the
ordering:

- **A fair `Semaphore`** sized from `analytics.query.max-concurrent` (`:62`). `tryAcquire` waits
  2 seconds (`:52`, `:153`) and then **refuses rather than queues** -- "a caller who waits behind
  five one-gigabyte scans has already lost, and telling them so is kinder than a request that
  eventually times out" (`AnalyticsLimits.java:49-52`). Taking the slot first means a rejected
  caller never pays for a session.
- **`setQueryTimeout`** from `analytics.query.timeout-seconds` (`:167`), bounding how long a query
  may hold the permit.
- **One session per query, closed with it** (`:164-165`, try-with-resources). **This is not a
  pool, deliberately** (`:33-37`): the in-memory catalogue and the attached credentials die with
  the connection, so one caller's dataset cannot be visible to another's, and a query that wedges
  cannot poison a pooled connection for the next caller.

And `explain()` (`:189-218`) maps DuckDB's messages to human sentences, **logging anything
unmapped in full rather than leaking it** (`:216-217`) -- because "an unmapped engine message is
exactly the kind of string that carries a path or a host name" (`:186-187`).

### 8.5 Layer 4 -- Hibernate filter

**It contributes nothing, and it cannot.**

`DatasetResolver` holds no `EntityManager` and no `TenantFilterHelper` (`:41-45` is its entire
state), so it never calls `TenantFilterHelper.enableIfNeeded`. Even if it did,
`StorageConnection` declares `@Filter(name = "tenantFilter", condition = "(tenant_id = :tenantId
or tenant_id is null)")` (`model/pojo/StorageConnection.java:44`) -- deliberately permissive on a
null tenant -- so a platform-owned row would pass the filter anyway.

This is the same conclusion `object-browser.md` §8 reaches, and it is defensible for the same
reason. But it means **the whole of this feature's isolation rests on
`TenantOwnership.isVisibleToCaller` at `DatasetResolver.java:77`**, and any refactor that moves
work out of `DatasetResolver` removes the only guard.

### 8.6 By role

| Role | Own tenant's connections | Another tenant's | A platform-owned connection (`tenant_id` null) | Legacy `BUCKET_LIST` bucket |
|---|---|---|---|---|
| PLATFORM_ADMIN | Yes | Yes -- `isOwnedByCaller` short-circuits (`TenantOwnership.java:41-43`) | Yes | **No** -- not a `storage_connection` row, so `findByAlias` finds nothing (A2) |
| TENANT_ADMIN | Yes | No | **Yes** -- and the Object Browser refuses the same thing (A1) | **No** (A2) |
| TENANT_USER | Yes | No | **Yes** -- identical to TENANT_ADMIN here; the tenant/platform line is not the admin line | **No** (A2) |
| No tenant, not platform admin | Nothing -- `isOwnedByCaller` requires a non-null caller tenant (`TenantOwnership.java:44-45`) | No | **Yes** -- `isVisibleToCaller` returns true for a null owner regardless of the caller | **No** |

The last row is the shape this codebase already treats as a live threat elsewhere
(`StorageConnectionTenantlessCallerTest` exists for nothing else). It is untested here.

### 8.7 Test coverage

Two test classes, 20 tests, both new on 2026-09-08.

**`process/src/test/java/process/analytics/DatasetResolverTest.java`** -- 13 tests. Its javadoc
(`:22-28`) states why they are worth pinning hard: `DatasetRef`'s constructor is package-private
and this class is its only caller, so a regression here "is not a wrong answer on a screen, it is
the analytics engine pointed somewhere it should not be."

| Test | Line | Pins |
|---|---|---|
| `resolvesAFileTheCallersOwnTenantOwns` | `:67` | The happy path -- **the positive control for every refusal below** |
| `treatsAGlobAsOneMultiFileDataset` | `:79` | `isMultiFile`, `read_parquet`, `union_by_name`, `filename` |
| `refusesAConnectionBelongingToAnotherWorkspace` | `:97` | Cross-tenant refusal, exact wording |
| `refusesAConnectionThatDoesNotExistWithTheSameWords` | `:109` | **The same wording**, which is the actual security property |
| `refusesASoftDeletedConnection` | `:119` | `Status.Delete` |
| `refusesAPathThatClimbsOutOfTheBucket` | `:133` | `..` |
| `refusesAPathCarryingAQuoteThatWouldEndTheSqlLiteral` | `:143` | `a.csv'); DROP TABLE x; --` |
| `takesTheBucketFromTheConnectionRecord_notFromTheRequest` | `:156` | The bucket comes from the record. **The replacement for the test the mid-build redesign made obsolete** |
| `fallsBackToTheAliasWhenTheConnectionNamesNoBucket` | `:172` | Agreement with `StorageBrowserServiceImpl` |
| `refusesAFileTypeItCannotRead` | `:185` | `.pdf` |
| `refusesAProviderDuckDbCannotRead` | `:195` | FTP, by name |
| `asksForWhatIsMissingRatherThanFailingGenerically` | `:207` | Null / blank connection, blank path |
| `detectsEveryFormatItClaimsToRead` | `:219` | All six extensions, plus two nulls |

**`process/src/test/java/process/analytics/DuckDbLockdownTest.java`** -- 7 tests **against a real
DuckDB, not a mock**, because the claim being made is about what a specific engine refuses to do
and a stubbed engine refuses whatever the stub says (`:26-29`). A temp file holding
`DB_PASSWORD=hunter2` stands in for anything on the deployment's disk worth stealing (`:59-64`).

| Test | Line | Asserts |
|---|---|---|
| `aSessionCannotReadAFileFromTheLocalDisk` | `:76` | `read_csv_auto('<temp file>')` fails, and the message names the filesystem rule |
| `aSessionCannotWriteAFileToTheLocalDisk` | `:99` | `COPY … TO '<path>'` fails **and the file is absent afterwards** |
| `aSessionCannotRaiseItsOwnMemoryCeiling` | `:115` | `SET memory_limit='64GB'` fails |
| `aSessionCannotPutTheLocalFilesystemBack` | `:127` | `SET disabled_filesystems=''` fails |
| `aSessionStillDoesTheJobItExistsFor` | `:137` | **The positive control.** A `GROUP BY` returns the right numbers -- "a session that refused everything would pass all of them while being useless" (`:139-140`) |
| `anFtpConnectionIsRefusedByNameRatherThanFailingInsideAScan` | `:156` | The `default:` branch, by message |
| `aMalformedMemoryLimitIsRejectedRatherThanInterpolatedIntoSql` | `:166` | `512MB'; SET lock_configuration=false; --` throws `IllegalArgumentException` |

**Suite totals after this work: backend 607 passing, up from 587. Frontend 580 passing,
unchanged** -- no frontend unit test was added for the Studio.

**What is *not* covered.** Three gaps, each recorded again in §12:

- `AnalyticsQueryService` has **no test at all** -- not the semaphore, not the timeout, not
  `explain()`'s mapping table (A19, A12).
- The Azure branch of `DuckDbSessionFactory` has no test; every lockdown test uses a MINIO
  connection (`DuckDbLockdownTest:71`) (A16).
- `DuckDbSessionFactory`'s javadoc asserts **three** properties of a locked-down session
  (`:27-30`): no local filesystem, no further extension, no loosening. The suite tests the first
  and the third. **"Cannot install or load a further extension" is asserted in a comment and
  nowhere in a test** (A23).

---

## 9. Error handling

Every business failure is HTTP 200 with `status: ERROR` and a message written for a person; the
client renders the server's message unchanged (`analytics.ts:225-226`, and the comment above it).

| Failure | Message the user sees | Thrown at |
|---|---|---|
| No connection named | `Pick a storage connection first.` | `DatasetResolver.java:58` |
| No path named | `Pick a file or a folder pattern first.` | `:61` |
| Path fails the allow-list | `That path contains characters this reader does not accept.` | `:66` |
| Path contains `..` | `A dataset path cannot contain "..".` | `:71` |
| Connection missing, another tenant's, or soft-deleted | `Storage connection not found.` | `:81` -- **one message for three causes, on purpose** |
| Connection is FTP/FTPS | `Analytics Studio reads object storage. This connection is FTP.` | `:85-86` |
| Bucket name unusable | `This connection's bucket name cannot be read by the analytics engine.` | `:95-96` |
| Unsupported extension | `Analytics Studio does not read this file type yet. It reads CSV, TSV, JSON and Parquet.` | `:101-102` |
| Governor full | `Too many analytics queries are running right now. Try again in a moment.` | `AnalyticsQueryService.java:159-160` |
| Thread interrupted | `The query was interrupted.` | `:156` |
| Query exceeded the timeout | `That query took longer than 30 seconds and was stopped. Narrow the dataset, or filter it down.` | `:193-197` |
| Nothing at that path | `Nothing to read at etl-bucket/…. The connection worked, so check the path.` | `:198-202` -- note it distinguishes "reached the store" from "wrong path", which is the distinction the user needs |
| Store refused the read | `The storage connection reached <bucket> but was not allowed to read it.` | `:203-206` |
| Out of memory | `That query needed more memory than analytics is allowed to use. Try a narrower dataset, or Parquet instead of CSV.` | `:207-210` |
| Malformed file for its extension | `This file could not be read as CSV. It may be malformed, or a different format.` | `:211-215` |
| **Anything else from the engine** | `The dataset could not be read.` | `:216-217` -- **and the real error is logged with its stack**, never returned |
| Credentials undecryptable | `The stored credentials for this connection could not be read.` | `DuckDbSessionFactory.java:205`, and the cause's message is **deliberately excluded** because it can carry ciphertext fragments (`:202-203`) |
| Azure connection with no connection string | `Azure connection <alias> has no connection string, so Analytics Studio cannot read it.` | `:174-175` |
| Connection with no provider | `Storage connection <alias> has no provider.` | `:121` |
| Unexpected exception | `INTERNAL_ERROR_500`, HTTP 500, stack logged | `AnalyticsRestApi.java:76-80`, `:103-107` |
| HTTP transport failure | `The dataset could not be read.` (client fallback) | `analytics.ts:236`, `:256` |
| Connection list failed | `Could not load your storage connections.` | `analytics.ts:132` |
| Folder listing failed | `Could not list this folder.`, or the server's message | `analytics.ts:177` |

Five refusal paths were exercised live on 2026-09-08 against MinIO and each returned a friendly
ERROR, never a stack trace. **No stack trace or engine message reaches a screen on any mapped
path**, and the unmapped path is generic by construction.

Two weaknesses in this table are recorded in §12: the mapping is keyed on DuckDB's English message
text and is untested (A12), and a stale error can outlive the failure that produced it (A6).

---

## 10. Dependencies

**Hard, upstream:**

- **`storage-connections` (feature 9)** -- the strongest dependency in the graph
  (`.ai/discovery/features.md:552-565`). A connection is not merely where the data happens to be;
  it is the **only vocabulary in which data can be named at all**. With none configured, the screen
  has nothing to offer. It also inherits that feature's provider rules: an FTP or FTPS connection
  is refused by name.
- **`object-browser` (feature 8)** -- code reuse, not data flow. The rail calls `buckets()` and
  `listObjects()` on `features/objects/storage.service.ts`, and `storage.json/buckets` /
  `/listObjects` are served by `StorageBrowserRestApi`. Changing `storage.service.ts` or either
  endpoint's payload now touches two screens.
- **`authentication-and-access` (feature 1)** for `TenantContext`, which `TenantOwnership` reads
  on every resolve.
- **`platform-configuration` (feature 15)**, indirectly and unhappily: it owns the `BUCKET_LIST`
  lookup family, whose entries appear in this screen's picker and cannot be read. See A2.

**Infrastructure:**

- **DuckDB `1.1.3`**, embedded (`process/pom.xml:277-281`). ~70 MB, ships native libraries. No
  server to operate; also no separate process to blame when it consumes memory.
- **DuckDB's `httpfs` extension**, installed at session open (`DuckDbSessionFactory.java:126-127`).
  **This is a network fetch on a cold container** unless the extension is already in the
  extension directory.
- **DuckDB's `azure` extension** for Azure Blob (`:131-132`) -- see A16.
- **`EncryptionUtil`** for the stored credentials (`DuckDbSessionFactory.java:200`).
- **The object store itself** -- MinIO in dev, S3 or Azure Blob in a real deployment.

**Downstream:** **nothing depends on this feature.** It persists no row, raises no notification and
publishes no Kafka event, so no other feature has anything of its to read
(`.ai/discovery/features.md:575-577`). That is a fact about phase one, not a design goal.

**Not a dependency, contrary to what the feature's future implies:** Monaco is not in the project.
The SQL editor decision for phase three is still open.

---

## 11. Acceptance criteria

Fixtures assumed: two workspaces **A** and **B**. Connection `etl-store` (MinIO, `bucketName =
etl-bucket`) owned by A; connection `other-store` owned by B; a platform-owned connection
`shared-store` with `tenant_id` null; an `Inactive` connection `retired-store` owned by A; a
legacy `BUCKET_LIST` lookup child `legacy-bucket` owned by A; an FTP connection `ftp-store` owned
by A. Users `userA` (TENANT_USER, workspace A), `adminA` (TENANT_ADMIN, workspace A),
`platformAdmin`. In `etl-bucket`: `etl-demo/sales.csv` (7 rows, 4 columns -- region, rep, product
VARCHAR and amount DOUBLE), `etl-demo/orders.parquet`, `notes/report.pdf`, and
`etl-demo/F768945/out/` holding three partition CSVs which together hold 7 rows over 5 columns.

Criteria marked **VERIFIED 2026-09-08** were observed through the real API and the real UI against
MinIO on the build day.

**Reading a file**

1. `userA` opens `/analytics` and the connection picker lists `etl-store` and the screen opens on
   it with the bucket root listed, without a further click.
2. `userA` clicks `etl-demo/`, then `sales.csv`, and the header reads `sales.csv` with a `CSV`
   pill, the strip reads **7 rows** and **4 columns**, and the Overview tab is selected.
   **VERIFIED 2026-09-08.**
3. `userA` switches to Data and sees seven rows and a Columns rail listing `region VARCHAR`,
   `rep VARCHAR`, `product VARCHAR`, `amount DOUBLE`. **VERIFIED 2026-09-08.**
4. `userA` opens `orders.parquet` and gets a schema and rows, with the format pill reading
   `PARQUET`. **VERIFIED 2026-09-08.**
5. `userA` in `etl-demo/F768945/out/` clicks `all *.csv`; the header shows a `folder dataset` pill,
   the strip reads **7 rows** and **5 columns**, and every row's fifth column holds
   `s3://etl-bucket/etl-demo/F768945/out/<file>.csv`. **VERIFIED 2026-09-08.**
6. `userA` opens a dataset with more than one page; "Page 1 of N · 100 rows a page" appears, Next
   loads page 2, Previous returns to page 1, and Previous is disabled on page 1.
7. `userA` selects a dataset with no rows and sees "This dataset has no rows.", not an error.
8. `userA` clicks `notes/report.pdf` in the rail and **nothing happens** -- the button is disabled,
   greyed, and its title reads "Analytics Studio does not read this file type". No request is made.
   *(Positive control: `sales.csv` in the same folder is clickable and opens.)*
9. `userA` types `sal` into the folder filter; only `sales.csv` remains. Clearing it restores every
   row. Typing `zzz` shows `Nothing in this folder matches "zzz".` rather than "This folder is
   empty."
10. `userA` sets a filter, then opens a subfolder; the filter is cleared and the full listing of
    the new folder is shown.
11. `userA` in a folder holding both `.csv` and `.parquet` files sees exactly two buttons,
    `all *.csv` and `all *.parquet`, and no button for a format the folder does not contain.

**Refusals -- each paired with a positive control on the same fixture**

12. `userA` calls `GET /analytics.json/schema?connection=etl-store&path=etl-demo/sales.csv` and
    receives `SUCCESS` with four columns. *(The positive control for 13-20.)*
    **VERIFIED 2026-09-08.**
13. The same call with `path=../../etc/passwd.csv` returns HTTP **200** with `status: ERROR` and
    the message `A dataset path cannot contain "..".` **VERIFIED 2026-09-08.**
14. The same call with `path=a.csv'); DROP TABLE x; --` returns `ERROR` and
    `That path contains characters this reader does not accept.` No SQL is executed and no session
    is opened. **VERIFIED 2026-09-08.**
15. The same call with `path=notes/report.pdf` returns `ERROR` and `Analytics Studio does not read
    this file type yet. It reads CSV, TSV, JSON and Parquet.` **VERIFIED 2026-09-08.**
16. The same call with `path=etl-demo/nope.csv` returns `ERROR` and
    `Nothing to read at etl-bucket/etl-demo/nope.csv. The connection worked, so check the path.` --
    the message distinguishes a working connection from a wrong path.
    **VERIFIED 2026-09-08.**
17. The same call with `path=/etc/passwd.csv` (absolute, no `..`) does **not** read `/etc/passwd`.
    The leading slash is stripped and the read is attempted at `etl-bucket/etc/passwd.csv`, which
    does not exist, so the caller gets criterion 16's message. **Two independent layers must both
    be observed:** the path was confined *inside the connection's bucket*, **and** separately the
    session has no local filesystem to reach even had it escaped. **VERIFIED 2026-09-08, both
    layers.**
18. `userB` calls the same URL with `connection=etl-store` and receives `ERROR` and
    `Storage connection not found.` *(Positive control: `userB` with `connection=other-store`
    succeeds, in the same session.)*
19. `userA` calls it with `connection=does-not-exist` and receives the **identical** message,
    character for character, to criterion 18's. Comparing the two responses must reveal nothing
    about whether `etl-store` exists.
20. `userA` calls it with `connection=ftp-store` and receives `Analytics Studio reads object
    storage. This connection is FTP.` *(Positive control: `etl-store`, an object store, succeeds.)*
21. `userA` calls it with `connection=legacy-bucket` -- a bucket their own picker offers -- and the
    refusal names the real reason rather than saying the connection was not found.
    **FAILS TODAY**, see A2.
22. `userA` calls it with `connection=shared-store`, a platform-owned connection, and is refused.
    *(Positive control: `platformAdmin` calling the same succeeds.)* **FAILS TODAY** -- the
    tenant user succeeds, see A1.
23. `userA` calls it with `connection=retired-store`, an `Inactive` connection, and is refused.
    *(Positive control: `etl-store`, which is `Active`, succeeds.)* **FAILS TODAY**, see A21.
24. A request with a valid token carrying no tenant claim and no platform-admin role is refused for
    `etl-store` **and** for `shared-store`. **FAILS TODAY for `shared-store`**, see A1.
25. A request with no `Authorization` header returns 401/403 from both endpoints and opens no
    DuckDB session.

**The engine's lock-down**

26. A DuckDB session built by `DuckDbSessionFactory.open()` cannot read a file from the local disk:
    `read_csv_auto('<a real local file>')` raises, and the message names the filesystem rule.
    *(Positive control: criterion 30.)*
27. The same session cannot write one: `COPY (SELECT 1) TO '<path>'` raises **and no file exists at
    that path afterwards**. Asserting the exception alone is not sufficient.
28. The same session cannot raise its own memory ceiling: `SET memory_limit='64GB'` raises.
29. The same session cannot re-enable the local filesystem: `SET disabled_filesystems=''` raises.
30. The same session still answers a real query correctly -- a `GROUP BY` over inline values
    returns the right groups in the right order. **This is the positive control for 26-29 and must
    run on the same fixture**: a session that refused everything, including its own purpose, would
    pass all four refusals while being useless.
31. `DuckDbSessionFactory.open()` on an FTP connection raises before any session is configured,
    with a message naming S3 and MinIO -- and **not** Azure, which `DatasetResolver` gates as
    unverified before a request can reach the factory, so naming it here would restate the
    overclaim the gate removes (changed 2026-09-08 with gap 13). *(Positive control: a MINIO
    connection opens.)*
32. `DuckDbSessionFactory.open()` with `analytics.duckdb.memory-limit` set to
    `512MB'; SET lock_configuration=false; --` raises `IllegalArgumentException` naming
    `memory-limit`, and no session is opened. *(Positive control: `256MB` opens a working session.)*
33. A session whose configuration fails at any step is **closed**, not returned. Observable as: no
    DuckDB connection leaks after a run of criteria 31 and 32.
34. The same session cannot install or load a further extension. **NOT TESTED TODAY**, see A23 --
    the property is asserted in `DuckDbSessionFactory.java:29-30` and nowhere else.

**The governor**

35. With `analytics.query.max-concurrent=1`, a second concurrent query receives
    `Too many analytics queries are running right now. Try again in a moment.` after approximately
    2 seconds, not after the first query finishes. *(Positive control: the same second query
    succeeds once the first has completed.)* **NOT TESTED**, see A19; the ceiling being per JVM
    rather than per tenant is A20.
36. A query exceeding `analytics.query.timeout-seconds` returns `That query took longer than 30
    seconds and was stopped…` and **releases its permit**, so a following query succeeds.
    **NOT TESTED**, see A19.
37. A caller requesting `pageSize=1000000` receives at most `analytics.query.max-rows` rows.
    *(Positive control: `pageSize=5` returns exactly 5.)*
38. A caller sending no `pageSize` receives `analytics.preview.page-size` rows, and the response's
    `pageSize` field says so.

**Configuration**

39. Each of the six `analytics.*` properties is present in `application-dev.properties`,
    `application-stage.properties` and `application-prod.properties`, and
    `ApplicationPropertiesDeclarationTest` fails if any is removed from any of them.
40. None of the six appears in that test's `SECRETS` list, and none carries a committed secret.

**The screen**

41. `userA` on a dataset whose read fails sees the server's own sentence in the panel with a
    "Try again" button, and no stack trace anywhere. **VERIFIED 2026-09-08.**
42. `userA` clicks "Try again" on a failed page and the dataset reloads. *(Today it reloads at page
    0 regardless of which page failed -- A7.)*
43. `userA` turns to a page that fails, then back to a page that succeeds, and **sees the rows**.
    **FAILS TODAY**, see A6.
44. A `null` cell renders as an italic muted `null` and an empty-string cell renders as blank; the
    two are distinguishable at a glance.
45. `userA` switches the app to dark mode and every element on the screen remains legible, with no
    hard-coded colour. **VERIFIED 2026-09-08.**
46. At 375px width nothing overflows horizontally; the rail stacks above the dataset panel and the
    rows table scrolls inside its own box. **VERIFIED 2026-09-08** (no page overflow).
47. Opening the screen and reading a dataset produces **no console error**.
    **VERIFIED 2026-09-08.**
48. `userA` with no storage connections configured is told so and pointed at where to add one.
    **FAILS TODAY**, see A22.

---

## 12. Known issues

Each was a defect present in the code when it was recorded, with the evidence. **Three -- A3, A4
and A5 -- were closed by a second pass over the frontend later on 2026-09-08 and are marked
`FIXED`; they are kept rather than deleted, because what the first build shipped is part of the
record.** The other twenty are open. Nothing here is fixed by this document; the fixes belong to
Execution, where they can be tested.

Numbered `A1`-`A23` so they can be referenced from synthesis and QA without colliding with
`reports.md`'s `K` series. Twenty open: **thirteen major, four minor, three cosmetic.**

### A1 -- A platform-owned connection is readable by any tenant user -- **major. FIXED 2026-09-08**

`DatasetResolver.java:77` narrows with `TenantOwnership.isVisibleToCaller(c.getTenantId())`, and
that method returns **true for a null owner regardless of the caller**:

```java
public static boolean isVisibleToCaller(Long ownerTenantId) {
    return ownerTenantId == null || isOwnedByCaller(ownerTenantId);
}
```

(`process/src/main/java/process/security/TenantOwnership.java:52-54`.)

The Object Browser refuses exactly this. `resolveServiceForCaller`
(`StorageBrowserServiceImpl.java:431-437`) throws `"Unknown bucket"` when `isPlatformBucket` is
true and the caller is not a platform admin, and `isPlatformBucket` (`:455-464`) is true when a
`storage_connection` row with that alias has a null `tenant_id`. The comment above it (`:439-453`)
sets out at length why the platform/tenant line matters more than the admin line.

So a `TENANT_USER` who names a platform-owned connection's alias cannot browse it and **can read
every row of every CSV, TSV, JSON and Parquet file in it**.

Two things bound the blast radius, and neither removes the defect:

- The alias is not in the caller's picker. `collectBuckets` narrows with `belongsToCaller`
  (`:105-112`, `:477-479`), which requires **both** ids to be non-null, so a tenant-less connection
  never appears. The alias must be guessed or known -- and connection aliases are not secrets.
- ~~The two shipped platform buckets are **not** reachable this way: `etl-avatar` is a property
  and `etl-bucket` ships as a `BUCKET_LIST` lookup, so neither has a `storage_connection` row.~~
  **Struck 2026-09-08 -- this was wrong, and it was the bullet holding the severity down.** It
  was reasoned from `isPlatformBucket`'s comment rather than from the data. Queried directly:

  ```
  etl-avatar|NULL->platform|Active|MINIO       test-user-3-bucket|NULL->platform|Active|S3
  etl-bucket|NULL->platform|Active|MINIO       test-user-4-bucket|NULL->platform|Active|S3
  test-user-1-bucket|NULL->platform|Active|S3  test-user-5-bucket|NULL->platform|Active|S3
  test-user-2-bucket|NULL->platform|Active|S3
  ```

  All **seven** connections in this environment have a row and **every one is platform-owned**,
  so the exposure was not to a hypothetical operator-created row -- it was to the entire storage
  estate, `etl-bucket` included, which `resolveServiceForCaller`'s own comment (`:425-429`)
  describes as holding "Kafka key material, PDF uploads and other tenants' documents", and
  `etl-avatar`, which holds every user's profile picture. There is no `BUCKET_LIST` parent row in
  the database at all, so the legacy mechanism the bullet appealed to is not in use here.

`TenantOwnership`'s own javadoc (`:19-28`) says `isVisibleToCaller` "exists for the one kind of
read that still deliberately admits a platform-owned row: resolving a *default* to fall back on
when a tenant has none of its own", and names `KafkaConnectionResolver` as the one live example.
Reading another workspace's data file is not that kind of read. `isOwnedByCaller` is the method
this call site wants.

**Fixed 2026-09-08** in `DatasetResolver.java:74-89`: `isVisibleToCaller` became
`isOwnedByCaller`, with the reasoning recorded at the call site so the next reader does not
"simplify" it back. Two tests pin both halves --
`refusesAPlatformOwnedConnectionToATenantUser` and, as its control,
`readsAPlatformOwnedConnectionForAPlatformAdmin`, because a rule that refused everyone would
satisfy the first assertion while breaking the admin. A tenant user now sees an empty picker in
Analytics Studio, which is exactly what the Object Browser already showed them.

### A2 -- A bucket the picker offers cannot be read, and the refusal misdescribes why -- **major**

The connection `<select>` is fed by `storage.json/buckets` (`analytics.ts:123`,
`analytics.html:21-26`), and `collectBuckets` returns **two** kinds of entry: `storage_connection`
aliases (`StorageBrowserServiceImpl.java:105-112`) and `BUCKET_LIST` lookup children
(`:114-133`).

`DatasetResolver.resolve` knows only the first kind -- `storageConnectionRepository.findByAlias`
(`:74-75`). A legacy bucket therefore resolves to `"Storage connection not found."` about a
connection the reader can see in the dropdown in front of them, and which the Object Browser reads
perfectly well.

The message is not merely unhelpful, it is wrong for this case, and it is deliberately the same
string used for a cross-tenant refusal (§8.4.1), so the one message now covers three genuinely
different situations of which only two should be indistinguishable.

### A3 -- `StatTile` was imported and unused -- **cosmetic. FIXED 2026-09-08**

When the figures strip replaced the four stat tiles (§2.2.3), `StatTile` was left in the
component's `imports` array with no `<app-stat-tile` element left in the template. Angular does not
error on an unused standalone import; it simply pulls the component into the bundle for nothing.

Closed the same day: `analytics.ts:36` now reads `imports: [Icon, TableShell]`, and the only
remaining occurrence of the string is inside the comment at `analytics.html:140-143` that explains
why the tiles went.

### A4 -- `ToastService` was injected and never used -- **cosmetic. FIXED 2026-09-08**

The component injected `ToastService` and never called it; every failure on this screen is
rendered in-panel instead, which is the right choice for a screen with one thing on it, but left
the injection dead. Closed the same day -- neither the import nor the field survives in
`analytics.ts`, and `toast` now matches nowhere in the file.

*If a toast is ever wanted back here, the case for it is a storage-rail failure that does not
belong in the dataset panel.*

### A5 -- The same timestamp was rendered two different ways on the same screen -- **minor. FIXED 2026-09-08**

`modifiedAt()` (`analytics.ts:290-295`) exists precisely to stop a raw ISO string reaching the
reader, and its own javadoc names the defect: the storage API answers with a raw string that
"rendered as `2026-09-08T14:55:40.779Z` on the overview -- precise, and not what anybody reads a
modified date for."

It was applied to the figures strip (`analytics.html:161`) and not to the Overview definition list,
which went on rendering `selected()!.lastModified` raw. Closed the same day: `analytics.html:210-213`
now calls `modifiedAt()` too, and the row is conditional on it rather than on the raw field, so the
two places agree.

### A6 -- A stale error hides a page that loaded -- **major**

`loadPage` (`analytics.ts:241-259`) sets `error` on failure and **never clears it on success**;
only `load()` clears it (`:216`). `TableShell` renders `@else if (error())` **before** the rows
(`shared/ui/data-table.ts:47-54`), and the pager sits outside the shell as a sibling
(`analytics.html:263-278`), so Previous and Next stay clickable while the error panel is up.

Sequence: page 5 times out → the error panel appears → the reader clicks Previous → page 4 loads
successfully and `preview()` is updated → **the error panel is still what is on screen**. The rows
are in memory and invisible. The only escape is "Try again", which reloads from page 0 (A7).

### A7 -- Retry silently returns to page 0 -- **minor**

`retry()` (`analytics.ts:271-273`) calls `load(this.path())`, which resets the tab to `overview`
(`:214`), clears the columns and preview (`:217-218`), re-reads the schema, and calls `loadPage(0)`
(`:232`). A reader on page 40 who hits "Try again" loses their place, their tab, and pays for a
schema read they did not need, with nothing on screen saying so.

### A8 -- One dataset open costs three sessions and three permits; a page turn costs two -- **major**

Every call to `run()` takes a semaphore permit (`AnalyticsQueryService.java:153`) and opens a fresh
DuckDB session (`:164`). The call graph:

- `load()` → `schema()` → `schemaOf` → **one** `run()` (`:72`).
- then `loadPage(0)` → `preview` → `rowCount()` → **one** `run()` (`:98`, `:132`), then the page
  query → **one** `run()` (`:106`).

So opening a file is **three** permits and three sessions in quick succession, and each subsequent
page turn is **two** -- because `preview` recomputes `count(*)` on every call, for a number that
cannot change between pages of the same read.

With the shipped `analytics.query.max-concurrent=4`, **two readers opening a file at the same
moment can saturate the ceiling**, and a third is refused after a 2-second wait with a message
that tells them to try again in a moment without saying why. This is the first thing to look at if
that refusal starts appearing in a deployment.

The obvious fix -- carry the row count on the schema response, or cache it per dataset for the life
of a paging session -- is a phase-two conversation, but the cost should be known now.

### A9 -- The storage rail lists at most 100 entries, with no continuation and no notice -- **major**

`analytics.ts:169` calls `this.storage.listObjects(connection, this.prefix())`. The service's
signature is `listObjects(bucket, prefix = '', continuationToken?, maxKeys = 100)`
(`features/objects/storage.service.ts:35`), so `maxKeys` is 100 and no continuation token is ever
sent. `browse()` reads `response.data?.objects` (`:173`) and **nothing reads
`nextContinuationToken`**, which `BrowseResponse` declares (`storage.service.ts:24`).

A folder holding 250 files shows 100 of them and says nothing. The Object Browser has a "Load more"
for exactly this case. Two consequences ride along:

- `folderFormats()` (`analytics.ts:203-210`) computes the "read the folder as one dataset" buttons
  from `files()`, i.e. the first page only. A folder whose Parquet files all sort after the
  hundredth CSV offers no `all *.parquet` button.
- The folder filter (`:72-76`) filters the loaded page, so `Nothing in this folder matches "x"` can
  be false: the match may be in the 150 entries that were never fetched. The message is honest
  about the *folder* and wrong about the *facts*.

### A10 -- "Read the folder as one dataset" is not recursive, and cannot be told to be -- **minor**

`openFolderAsDataset` builds `${this.prefix()}*.${extension}` (`analytics.ts:197-200`). A single
`*` matches within one path segment, so a Hive-style layout -- `out/dt=2026-09-01/part-0.csv` --
produces nothing when read from `out/`, and the reader is shown criterion 16's "Nothing to read
at…" message for a folder that visibly contains data.

The server would accept the recursive form: `SAFE_PATH` (`DatasetResolver.java:36`) permits `*`,
`?` and `/`, and `=` and `+` are in the allow-list precisely because partition keys use them. The
UI simply never constructs `out/*/*.csv`.

### A11 -- Paging is unordered and the screen does not say so -- **major (honesty)**

`preview` deliberately emits no `ORDER BY`, with the reasoning in the comment at
`AnalyticsQueryService.java:100-101`: object storage has no natural row order to promise, and an
`ORDER BY` would sort the whole dataset to return a hundred rows. That reasoning is sound.

What follows from it is not stated anywhere the reader can see. The count query and the page query
are **separate statements in separate sessions** (`:98` then `:106`), and for a multi-file dataset
DuckDB is free to enumerate the files differently between them. So paging can repeat a row, skip
one, or report a total that does not match what paging through actually yields. The screen presents
"Page 3 of 40" with the confidence of a database cursor.

Either the pages need a stable order, or the pager needs one sentence saying the order is not
guaranteed. The second is a one-line honesty fix and is what I would do first.

### A12 -- The engine error mapping is untested and coupled to DuckDB's English -- **major**

`explain()` (`AnalyticsQueryService.java:189-218`) branches on lowercased substrings of DuckDB's
own message: `"no files found"`, `"404"`, `"nosuchkey"`, `"does not exist"`, `"403"`,
`"access denied"`, `"forbidden"`, `"out of memory"`, `"memory limit"`, `"invalid input error"`,
`"could not convert"`, `"sniffing"`, `"csv error"`, `"timeout"`, `"interrupt"`.

There is **no test for any of them.** A DuckDB upgrade that rewords one string turns a specific,
actionable refusal into `"The dataset could not be read."` with the real reason visible only in the
server log -- and the failure is silent, because both paths return the same HTTP status and the
same DTO shape. Every one of the five refusal paths verified live on 2026-09-08 depends on a string
match that nothing pins.

The dependency is also a version pin in disguise: `process/pom.xml:280` fixes `1.1.3`, and moving
off it is a behavioural change to the error surface, not just to the engine.

### A13 -- `analytics.query.max-rows` does less than its name and its javadoc claim -- **cosmetic today**

`AnalyticsLimits.java:37-38` says the limit is "Enforced by rewriting the query with a LIMIT rather
than by reading everything and truncating afterwards, so the work is never done in the first
place."

In phase one its **only** consumer is `pageSize()` (`AnalyticsQueryService.java:139`), where it
clamps the requested page size. `schemaOf` and `rowCount` carry no `LIMIT` and need none, and
there is no other query to bound. The javadoc describes phase three's behaviour in the present
tense.

Harmless now; a trap for whoever reads it in three months and assumes a ceiling that is not there.

### A14 -- The page size is fixed at the server default, with no control -- **cosmetic**

`analytics.service.ts:55-56` omits `pageSize` when it is falsy, and `analytics.ts:245` never passes
one. So every preview is `analytics.preview.page-size` rows, and the `pageSize` parameter the API
exposes has no caller. Recorded so nobody hunts for a rows-per-page control that was never built.

### A15 -- Three renderings of the same figure on one screen -- **cosmetic**

The row count is shown as `compact(rowCount())` in the strip (`analytics.html:146`), as
`rowCount().toLocaleString()` in the Overview list (`:204`), and raw and unformatted inside
`TableShell`'s "(shown of total)" heading, which interpolates the numbers directly
(`shared/ui/data-table.ts:19-21`). A million-row dataset reads `1M`, `1,000,000` and `1000000` on
one screen. The third is `TableShell`'s to fix, not this feature's, but this screen is where it
shows.

### A16 -- Azure is untested and must not be described as working -- **major**

The code branches for it: `DuckDbSessionFactory.java:130-134` installs and loads the `azure`
extension and calls `azureSecret` (`:171-179`), and `DatasetRef.url()` (`:95`) emits `azure://` for
`StorageProvider.AZURE`.

**It has never been exercised against a real Azure container.** Every lockdown test uses a MINIO
connection (`DuckDbLockdownTest.java:71`), and there is no integration test for the feature at all.
S3 and MinIO share the S3 protocol and were both verified; Azure needs a separate DuckDB extension,
a different secret shape, and a different URL scheme -- three things that were written from the
documentation and never run.

An Azure connection *will* appear in this screen's picker, because the picker lists every
connection the caller owns. If the branch is broken, the reader gets whatever DuckDB says, mapped
through the untested `explain()` (A12) and most likely landing on the generic
`"The dataset could not be read."`

### A17 -- No frontend test of any kind -- **major**

Zero specs in `scheduler1/next/src` reference `analytics`. The 580-test frontend figure is
unchanged by this feature. Nothing pins the route, the reuse of `StorageService`, the `readable()`
predicate, the filter, the crumbs, the glob construction, the paging arithmetic, or the error
rendering. `pageCount()` (`analytics.ts:116-120`) in particular is arithmetic with a guard, which
is exactly the shape a unit test is cheap for.

### A18 -- A dataset read leaves no record anybody can query -- **major**

The specification asked for an audit-log entry and a Kafka event on a dataset read. **Neither is
built.** No `JobAuditLogs` row, no `Notification`, no Kafka publish anywhere in
`process/src/main/java/process/analytics/`.

The only trace is `logger.debug("Analytics query on {} for tenant {} took {} ms", …)`
(`AnalyticsQueryService.java:170-171`). That line does fire -- the `process` logger is at `debug`
(`process/src/main/resources/logback.xml:24`) -- and `DatasetRef.toString()` (`:124-129`) names
provider, bucket, path and format without the credentials that reach it, so it is safe to log. But
it is an application log line, not a queryable record, and:

- it is written **only on success**; a refused read logs nothing at all unless the engine error was
  unmapped (`:216`), so the refusals in §11 leave no trace;
- it names the tenant, not the user.

So "which of my users read that file, and when" is a question this feature cannot answer. For a
feature whose entire function is reading other people's data files, that is the gap I would close
first.

### A19 -- `AnalyticsQueryService` has no test at all -- **major**

No `AnalyticsQueryServiceTest` exists. Untested: the semaphore's capacity, its fairness, the
2-second wait and the refusal that follows it, permit release on the timeout path (the `finally` at
`:176-178`), `setQueryTimeout`, `pageSize()`'s clamp, the offset arithmetic at `:97`, and every
branch of `explain()` (A12).

This is the class the javadoc calls "the only place in this application where an analytics query
runs" (`:22`) and the class phase three's user SQL will arrive at. It is the least tested of the
three.

### A20 -- The concurrency ceiling is per JVM, not per tenant -- **major**

`AnalyticsQueryService:62` constructs **one** `Semaphore` for the whole application, and nothing
anywhere partitions it by tenant, user or connection. One workspace scanning a large Parquet folder
can occupy all four permits, and every other workspace is refused with
`"Too many analytics queries are running right now. Try again in a moment."` (`:159-160`) -- a
message that gives the victim no way to tell a busy system from a noisy neighbour.

The ceiling is doing its job (it protects the JVM, and the ETL dispatcher sharing it), so this is
not an argument for removing it. It is an argument for a per-tenant sub-limit, and for saying more
in the message.

### A21 -- An `Inactive` connection is readable here and nowhere else -- **minor. FIXED 2026-09-08**

**Fixed 2026-09-08** alongside A1, in the same filter chain: `!Status.Delete` became
`Status.Active`, matching `collectBuckets :104`. Pinned by `refusesADeactivatedConnection`.

`DatasetResolver.java:76` filters only `!Status.Delete.equals(c.getStatus())`. `Status` has three
values -- `Inactive, Active, Delete` (`model/enums/Status.java:6`) -- so an **`Inactive`**
connection passes.

The Object Browser does not allow this twice over: `collectBuckets` keeps only
`connection.getStatus() == Status.Active` (`StorageBrowserServiceImpl.java:106`), and
`resolveService` looks the alias up with `findByAliasAndStatus(bucket, Status.Active)` (`:530`).

So a connection an admin deliberately deactivated -- rotated credentials, decommissioned store,
suspended vendor -- disappears from the object browser and from this screen's own picker, and
keeps serving data to anyone who names the alias against `/analytics.json`.

### A22 -- There is no empty state for "no connections configured" -- **minor**

If `buckets()` returns an empty list, `analytics.ts:130` does not call `pickConnection`, so no
listing is attempted and no error is set. The result is an **empty `<select>`** beside a panel
reading "Pick a file to read it." with nothing to pick, and no explanation and no link.

The Object Browser handles this properly: a full empty card with an "Add a connection" link to
`/admin/storage` (`object-browser.md` §4.5). Given that a storage connection is the *only*
vocabulary in which this feature can name data (§10), it is the screen that needs the empty state
most.

### A23 -- The lock-down suite tests two of the three properties the javadoc asserts -- **major. FIXED 2026-09-08, and the finding changed shape**

**Fixed 2026-09-08**, but writing the test showed the property is narrower than "no extension can
be loaded", so the suite now asserts what is actually true rather than what was assumed:

- `aSessionCannotReachForAnExtensionThatIsNotAlreadyBundled` -- `INSTALL spatial` and `LOAD
  spatial` both fail with `Permission Error: File system LocalFileSystem has been disabled by
  configuration`. The mechanism is the filesystem rule, not an extension rule: an unbundled
  extension has to be read from the extension directory, and there is no local disk to read it
  from. Each verb runs on its **own** statement -- the first draft chained them, and `LOAD`
  merely inherited `"Statement was closed"` from the failed `INSTALL`, asserting nothing.
- `anExtensionCompiledIntoTheDriverIsStillLoadable` -- `LOAD json` **succeeds**, because `json`
  ships inside `duckdb_jdbc`. Written down so the first test is not read as a stronger claim than
  it makes. The bundled set are format readers that reach the outside world only through the
  filesystem rules already asserted here, so this is acceptable -- but as a judgement about a
  known list, not because the door is shut.

`DuckDbSessionFactory.java:27-30` states three things a configured session cannot do:

> * read or write the local filesystem …
> * install or load a further extension, so the allow-listed httpfs is the only one present;
> * change any of these settings back, because lock_configuration is set last.

`DuckDbLockdownTest` covers the first (`:76`, `:99`) and the third (`:115`, `:127`). **Nothing
tests the second.** There is no assertion anywhere that `INSTALL <anything>` or `LOAD <anything>`
fails after `lock_configuration=true`.

That matters more than the other two, not less: extension loading is how a DuckDB session acquires
capabilities it did not start with, and it is the property that most directly determines whether
phase three's user SQL is safe. The claim is currently carried by a comment. It needs the same
treatment the other four claims got -- a real engine, a real attempt, and a positive control on the
same session.

---

## 13. Missing functionality

Things phase one does not have. Everything scheduled for a later phase is in §2.4 and is
**not** repeated here; this section is what is missing from *phase one as built*. "Effort" is the
work required now.

| # | Missing | Evidence | What it would take |
|---|---|---|---|
| 1 | **Any audit trail for a dataset read** | No audit, notification or Kafka code in `process/src/main/java/process/analytics/`; only `AnalyticsQueryService.java:170-171` | A `JobAuditLogs`-shaped row, or the platform's existing audit path, written on both the success and the refusal branch of `run()`, naming the user and not only the tenant. The spec asked for this and for a Kafka event. **M** |
| 2 | **Any frontend test** | Zero specs reference analytics (A17) | At minimum: `readable()`, `crumbs`, `folderFormats`, `pageCount`, the glob construction in `openFolderAsDataset`, and the error/loading interaction with `TableShell`. **M** |
| 3 | **Any test of `AnalyticsQueryService`** | No such file (A19) | Semaphore capacity and release, timeout, `pageSize` clamp, offset arithmetic, and a table-driven test over every branch of `explain()`. **M** |
| 4 | **A test that a further extension cannot be loaded** | `DuckDbSessionFactory.java:29-30` asserts it; `DuckDbLockdownTest` does not (A23) | One test in the existing class, in the shape of the four already there, with the positive control it already has. **S** |
| 5 | **Any Azure verification** | The branch at `DuckDbSessionFactory.java:130-134`, `:171-179`, never run (A16) | A container, a connection string, and one read. Until then Azure must not be described as working anywhere. **S to try, unknown to fix** |
| 6 | **Continuation in the storage rail** | `analytics.ts:169`, `features/objects/storage.service.ts:35` (A9) | Thread `nextContinuationToken` through `browse()` and add a "Load more", as `/objects` has. **S** |
| 7 | **A "no connections configured" empty state** | `analytics.ts:130` (A22) | The Object Browser's card, with its `/admin/storage` link. **S** |
| 8 | **Recursive folder datasets** | `analytics.ts:197-200` (A10) | Offer `<prefix>**/*.<ext>` alongside `<prefix>*.<ext>` when the folder has subfolders, and confirm the double-star against `SAFE_PATH` (`DatasetResolver.java:36`) before promising it. **S** |
| 9 | **Any caching** | Nothing caches. `schemaOf` and `rowCount` are recomputed per request (A8) | Carry `totalRows` on the schema response, or cache schema + count per (connection, path, etag) for a short TTL. Redis is already in the stack for `fileChatExtract`. **M** |
| 10 | **A per-tenant share of the concurrency ceiling** | One JVM-wide `Semaphore` (`AnalyticsQueryService.java:62`) (A20) | A permit map keyed by tenant beneath the global ceiling, and a message that distinguishes the two refusals. **M** |
| 11 | **Stable paging, or an admission that it is not stable** | `AnalyticsQueryService.java:100-101` (A11) | One sentence beside the pager. The real fix -- a stable sort key -- is a phase-two design question, not a phase-one omission. **S for the sentence** |
| 12 | **A row-count that does not cost a full query per page** | `AnalyticsQueryService.java:98` (A8) | Follows from #9. **S once #9 lands** |
| 13 | **Any e2e/MockMvc test of the two endpoints** | No `AnalyticsRestApi` test of any kind; the tenancy matrix in §11 (criteria 18-25) is verified only through `DatasetResolverTest`'s unit-level mocks | A `BucketAccessE2EIT`-shaped class, per role and per endpoint. That is the pattern the object browser already has, and it is what would have caught A1. **M** |
| 14 | **Download the result** | Absent. `DatasetPreviewDto` goes to the screen and no further | An export endpoint, reusing the report exporter's shape. Likely belongs with phase three rather than here. **M** |
| 15 | **A dataset the user can name and come back to** | No persistence at all (§6) | A table, a tenant column and a `tenantFilter` — which is also the moment this feature acquires layer 4. Phase two or three. **L** |

---

*Grooming written 2026-09-08 against the deployed phase one. §2.2 re-read after the frontend
changes made later the same day; §2.2.3 records what moved. Nothing in this document was taken
from the plan rather than from the code, except the phase numbering in §2.4 and the suite totals
in §8.7, both of which are recorded as of the 2026-09-08 build.*
