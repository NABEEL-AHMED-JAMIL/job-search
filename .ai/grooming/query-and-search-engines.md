# Grooming -- Query and Search Engines

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

This feature is two screens that share one idea and almost nothing else. **Query Engine** is a saved,
repeatable, tenant-owned reporting tool: register a database, save a SELECT against it, run it or
schedule it, and the result lands in a bucket as CSV. **Search Engine** is a platform-admin console
onto the application's own database: paste SQL, read the grid, leave. They are one feature because
they are one mental model -- "run SQL, look at rows" -- and because the old app filed them side by
side in the same menu (`scheduler1/src/app/app.component.html:29-32`) as the new app still does
(`scheduler1/next/src/app/features/shell/shell.ts:73-77`).

Migration status is **migrated**: both screens exist in both applications. That status is about
route coverage, not about correctness, and the comparison below finds that the rewrite carried the
shape of the Query Engine across while dropping the dialog that made its main verb work.

---

## 1. Purpose

**Query Engine.** "I have a reporting database. Once a week somebody asks me for the same extract.
I want to write that SELECT once, keep it, and either press a button or let it run itself every
hour -- and I want the CSV to appear in the bucket the rest of my pipeline already reads from, not
in my Downloads folder." Three nouns follow from that sentence and they are the three tabs:

- a **connection** -- where the data is, with a password the app keeps and never shows again;
- a **query** -- the SQL, named, so somebody who cannot write SQL can still run it;
- a **run** -- what happened: how many rows, which file, or why it failed.

A schedule is not a fourth noun. It is a property of a query -- "this one runs itself" -- which is
why both applications put it in the query's own row menu rather than giving it a tab.

The role split falls out of the same sentence. Writing the SQL and holding the database password is
an administrator's job. Pressing the button is not. That is exactly how the server is annotated
(`process/src/main/java/process/api/QueryEngineRestApi.java:26` against the overrides at `:75`,
`:141`, `:189` and elsewhere) and it is the single most important thing about this feature: **a
tenant user who cannot write a query can still run one somebody else wrote.**

**Search Engine.** A different job for a different person. "Something looks wrong in the console and
I need to see the row." It is a platform administrator reading the platform's own tables with no
saving, no scheduling and no output file -- the answer is on screen and then it is gone. The old app
titled its breadcrumb "Q-Result" (`scheduler1/src/app/_component/search-engine/search-engine.component.html:4`)
while the menu said "Search Engine"; the new app settled on Search Engine everywhere.

---

## 2. Existing behaviour

### 2.1 Old app -- Query Engine

Route `setting/queryEngine`, `QueryEngineComponent`, one component of 565 lines
(`scheduler1/src/app/_component/setting/query-engine/query-engine.component.ts`) plus a 536-line
template with six Bootstrap modals in it.

**Guarding.** `scheduler1/src/app/app.routing.ts:163-168` gives the route `canActivate: [AuthGuard]`
and nothing else -- no `RoleGuard`, no `data.roles`. Every other `/setting/*` route in that file is
admin-gated. The nav link at `app.component.html:32` is likewise unconditional. So any signed-in
user reaches the screen and sees every control on it, including New Query, Edit and Delete.

**Load.** `ngOnInit` (`:79-87`) fires five requests: connections, queries, executions, schedules and
the bucket list. Only the first shows the global spinner (`:104`); the rest load silently. Two of
them swallow their errors entirely -- `fetchAllSchedules` at `:255` and `loadBuckets` at `:100` both
have `() => { }` as their error handler.

**Tabs.** Three buttons at the top, each carrying a live count -- `Queries ({{activeQueries.length}})`,
`Connections`, `Execution History` (`query-engine.component.html:9-17`). Default tab is `queries`
(`:32` in the TS).

**Queries tab.** Search box, Refresh, and a New Query button that is `[disabled]` when there are no
connections, with a title explaining why and a help line beneath saying the same
(`query-engine.component.html:31-40`). The table columns are Id, Name, Connection, Schedule, Status,
Action (`:46-51`). The Schedule cell renders `every N min` or `None` from `scheduleForQuery()`
(`:60-62`, backed by `query-engine.component.ts:258-260`). Row actions are Run, Edit, and a
three-dot menu holding Schedule and Delete (`:71-97`).

- **Run** opens a modal (`:455-494`) with a **bucket dropdown fed from `storage.json/buckets`**, an
  optional prefix, and a file name pre-filled as `<sanitised query name>_export`
  (`query-engine.component.ts:409-416`). Submitting posts all four fields (`:427-432`), then
  refreshes history and switches to the Executions tab (`:440-442`).
- **Edit** calls `queries/fetchById` first (`:287`) precisely because the list rows carry no SQL, and
  builds the form from the detail response (`:296-300`).
- **Schedule** opens a modal (`:496-536`) pre-filled from any existing schedule, with the same bucket
  dropdown, a file-name **template** defaulting to `<name>_{date}`, and an interval defaulting to 60
  with `Validators.min(5)` (`query-engine.component.ts:452-458`). A "Remove Schedule" button sits in
  the footer when a schedule exists (`:527-530`) and deletes it **with no confirmation**
  (`query-engine.component.ts:498-518`).
- **Delete** opens a confirm modal whose body is one sentence (`:440-453`).

The query modal (`:359-438`) carries Validate and Preview buttons. Validate posts
`{ queryId, queryText }` when editing and `{ queryText }` when creating
(`query-engine.component.ts:317-319`). Preview posts `{ queryText, databaseConnectionProfileId }`
(`:338-341`) and renders the result into a scrolling grid, reading each cell as `row[col]`
(`query-engine.component.html:424-426`) -- which matches the server's row shape.

**Connections tab.** Search box **and a database-type filter dropdown**
(`query-engine.component.html:115-121`, backed by `query-engine.component.ts:542-549`). Columns are
Id, Profile Name, Type, Host (`host:port`), Database, Status, Action. Row actions are Edit and a
menu holding Delete. The connection modal (`:251-340`) has a Test Connection button that posts the
whole form -- including the profile id when editing (`query-engine.component.ts:167-170`) -- and
renders the result inline. An empty password is stripped from the save payload so an edit keeps the
stored one (`:189-191`), and the modal says so both in the placeholder and in a line that appears
when `passwordConfigured` is true (`query-engine.component.html:308-312`).

**Executions tab.** Search box **and a status filter dropdown** over
`['PENDING','RUNNING','SUCCESS','FAILED','CANCELLED']` (`query-engine.component.ts:65`,
`:530-536`). Columns are Id, Query, **Trigger** (`Scheduled` / `Manual`, derived from
`scheduleId`), Status, Rows, Started, Output (`bucket/key`), Message
(`query-engine.component.html:209-241`).

**Empty and error states.** Each tab has a one-line help-text empty state
(`:104-106`, `:182-184`, `:246-248`). There is no error state: a failed load produces a toast and an
empty table, so "the request failed" and "there is nothing here" look identical.

### 2.2 Old app -- Search Engine

Route `setting/searchEngine` with `AuthGuard` **and** `RoleGuard` for `['PLATFORM_ADMIN']`
(`scheduler1/src/app/app.routing.ts:156-162`); the nav link is hidden for everyone else
(`app.component.html:29-31`). The component is 63 lines
(`scheduler1/src/app/_component/search-engine/search-engine.component.ts`): one required `query`
textarea (`:34-36`), a POST to `setting.json/dynamicQueryResponse` (`:47`), and the response stashed
in `jsonPayload`. The template renders a fully dynamic table from `jsonPayload.column` and
`jsonPayload.data` (`search-engine.component.html:52-75`), with a client-side filter box, a
`No rows match "<term>"` row (`:67-72`), and cells longer than 60 characters wrapped in a scrolling
`cell-message` box (`:61-64`). A Clear button resets the form (`:27-29`). There is **no** client-side
check that the SQL is a SELECT -- the help line says "Only SELECT statements are supported" (`:19-22`)
and that is the whole of it.

### 2.3 New app -- Query Engine

Route `tools/query` (`scheduler1/next/src/app/app.routes.ts:229-236`), lazy-loaded, sitting under
the shell whose `canActivate` is `authGuard` (`:46-49`). The route carries **no** `minRole` and **no**
`roleGuard`, deliberately -- there is a comment saying so at `:230-232` and a test asserting it at
`app.routes.spec.ts:36-43`. The write controls are gated in the template instead, on
`auth.canManageQueries()`, which is `hasAtLeast('TENANT_ADMIN')`
(`scheduler1/next/src/app/core/auth/auth.service.ts:88-90`).

The screen is split into `query-engine.ts` (230 lines), `query-engine.html` (259 lines) and three
CDK dialogs: `db-connection-dialog.ts`, `query-dialog.ts`, `query-schedule-dialog.ts`.

**Load.** `loadAll()` (`query-engine.ts:92-107`) issues the same four GETs in parallel against a
shared countdown, and any one of them failing sets a single message,
`'Some Query Engine data could not be loaded.'` Nothing is swallowed.

**Chrome.** Four stat tiles above the tabs -- Queries, Connections, Scheduled (schedules whose status
is `Active`), Failed runs (`query-engine.ts:55-60`, `query-engine.html:27-36`) -- then the tab strip,
which is the only `role="tablist"` in the application (`query-engine.html:38`). The three tabs are
Queries, Connections and **Runs**. `setTab` clears the search box (`query-engine.ts:87-90`).

**Queries tab.** Columns are Query, Connection, Schedule, State and an action menu. The Query cell
shows the name, the SQL beneath it in mono, and an author line -- `Updated by X` or `Created by Y`
(`query-engine.html:71-82`), which the old app had nowhere. The Schedule cell shows `every Nm` plus
the next run time, or `manual only` (`:84-95`). The row menu offers **Run now** to everyone and
Edit / Schedule / Remove schedule / Delete only to `canManageQueries()`, with a comment at `:104-106`
explaining why Run stays (`:97-129`).

- **Run now** posts `{ queryId }` and nothing else (`query-engine.ts:187-190`). There is no dialog,
  no bucket, no prefix, no file name.
- **Delete** goes through `confirmWith` with body text that counts the schedules or dependants
  (`query-engine.ts:166-176`).
- **Remove schedule** likewise confirms (`:211-220`), which the old app did not.

**Connections tab.** Columns are Profile (with type and `added by`), Target (`host:port/database`),
User, **Password** (a `stored` / `not set` pill driven by `passwordConfigured`), State, and the
action menu -- which is hidden entirely for a tenant user, with a comment at `query-engine.html:178-180`
explaining that the rows stay visible because the Queries tab names its connection. There is a
search box and **no type filter**.

**Runs tab.** Columns are Query, Started, Rows, Output, Result. A scheduled run gets a `scheduled`
pill; a manual one shows `run by {{ e.createdByName }}` (`query-engine.html:230-234`). Error text
appears truncated under the start time (`:238-242`). There is a search box and **no status filter**.

**Dialogs.** All three use the shared `FormDialog` + `Field` chrome, so labels, required markers,
error text and the saving state are the same as everywhere else in the app. The query dialog carries
Validate and Preview in its footer (`query-dialog.ts:23-32`) and adds a **Status** select the old app
did not have (`:101-106`). The connection dialog adds a Status select too (`db-connection-dialog.ts:92-97`)
and moves Test Connection into the footer (`:24-30`). The schedule dialog has bucket, prefix, file
name template, interval and status (`query-schedule-dialog.ts:21-63`).

**States.** All three tables go through `TableShell`
(`scheduler1/next/src/app/shared/ui/data-table.ts:42-67`), which gives them a real loading spinner,
a real error panel with a Try again button, and a real empty state that distinguishes "no rows" from
"nothing matches your search" (`query-engine.html:51`, `:141`, `:208`).

### 2.4 New app -- Search Engine

Route `tools/search` with `data.minRole: 'PLATFORM_ADMIN'` and `canActivate: [roleGuard]`
(`app.routes.ts:257-263`); the nav entry is `platformOnly: true` (`shell.ts:76-77`). The component
(`scheduler1/next/src/app/features/tools/search-engine/search-engine.ts`, 113 lines) keeps the old
behaviour and adds four things:

- a **client-side write-keyword guard** -- a regex over insert/update/delete/drop/truncate/alter/
  create/grant/revoke/commit/rollback plus a "must start with SELECT or WITH" check, surfaced as an
  inline warning that disables the Run button (`:16-18`, `:51-59`);
- **Ctrl/⌘+Enter** to run (`search-engine.html:18`);
- **pagination** over the result rows (`search-engine.ts:33`, `:45`, `search-engine.html:100-101`);
- **Copy as TSV** (`search-engine.ts:104-109`).

The long-cell treatment survived (`:99-102`, `search-engine.html:79-84`) and so did the filter box
and the no-match row.

### 2.5 Backend -- what actually happens

`QueryEngineRestApi` is the largest controller in the codebase: four resource groups, 22 mapped
methods, one class-level `@PreAuthorize("hasRole('TENANT_ADMIN')")` at
`process/src/main/java/process/api/QueryEngineRestApi.java:26` and thirteen method-level overrides
that lower it to `TENANT_USER`. Because `@PreAuthorize` is not repeatable, each override **replaces**
the class rule rather than adding to it -- so those thirteen are genuinely `TENANT_USER`, and the nine
without an annotation are genuinely `TENANT_ADMIN`.

Two of the lowered ones are lowered only halfway, and the rest of the rule lives in the service:

- `connections/testConnection` is `TENANT_USER` at `:100`, but
  `ConnectionProfileServiceImpl.testConnection` refuses a tenant user who supplies a different host
  or any password (`:188-190`) and refuses one testing an unsaved profile at all (`:201-203`). The
  probe runs against a detached copy so an admin's override is never flushed onto the stored row
  (`:191-199`, `:273-284`).
- `queries/validate` and `queries/preview` are `TENANT_USER` at `:165` and `:178`, but
  `checkAdHocSqlAllowed` (`QueryDefinitionServiceImpl.java:287-295`) refuses any request without a
  `queryId` unless the caller is a tenant admin. A tenant user may validate or preview a **saved**
  query; nobody below tenant admin may hand the server SQL.

**Ownership.** Every service enables the Hibernate filter through `TenantFilterHelper.enableIfNeeded`
before listing, and re-checks ownership by hand after every `findById`, because the filter does not
apply to `findById` (`TenantOwnership.java:10-23`). All four entities declare
`tenant_id = :tenantId` (`QueryDefinition.java:22-23` and the same on the other three), so a
platform-owned (null-tenant) row would be invisible to every tenant -- and no code path can create
one: `addConnectionProfile` (`:81-83`), `addQuery` (`:95-97`) and `addSchedule`
(`QueryScheduleServiceImpl.java:70-72`) all refuse a caller with no tenant outright.

**SQL safety.** `QueryValidator` parses with JSqlParser and rejects anything that is not exactly one
`Select`, rejects `SELECT ... INTO`, walks into UNION branches and CTEs, and returns the parser's
own normalised text (`process/src/main/java/process/engine/query/QueryValidator.java:20-73`). The
normalised form -- not the user's original string -- is what gets encrypted and stored
(`QueryDefinitionServiceImpl.java:110`), which is what makes the trailing-comment trick in
`QueryValidatorTest` fail. The runner re-validates after decrypting, before executing
(`QueryExecutionRunner.java:74-77`), so a query tampered with in the database still cannot run.

**Execution.** `QueryExecutionServiceImpl.execute` requires `queryId`, **`outputBucket`** and
**`outputFileName`** (`:64-73`), resolves the connection, and hands off to `QueryExecutionRunner`,
which runs in `REQUIRES_NEW` so the execution row survives whatever happens
(`QueryExecutionRunner.java:55`). The runner decrypts, re-validates, streams to a temp CSV capped at
`query-engine.max-rows` (default 1,000,000) with a 300-second statement timeout (`:109-113`), uploads
to the bucket, and records row count and key. A truncated result is still `SUCCESS` but carries an
explanatory `errorMessage` (`:90-93`). The object key gets `.csv` appended if absent (`:115-123`) and
`{date}` -- **and only `{date}`** -- is substituted in the file name (`:125-131`).

**Scheduling.** `ProcessCron.pollDueQuerySchedules` runs every 60 seconds
(`process/src/main/java/process/engine/cron/ProcessCron.java:78-120`), takes schedules whose status
is `Active` and whose `nextRunAt` has passed (`QueryScheduleRepository.java:19-20`), sets a
`TenantContext` per schedule from the schedule's own tenant and creator (`:96`), runs it, then
clears the context **before** advancing `nextRunAt` so the advance is not attributed to a person
(`:102-109`). If the advance itself fails the row is deliberately left in the past so the schedule
retries rather than being skipped (`:110-115`).

**Search Engine's endpoint.** `SettingRestApi.dynamicQueryResponse` is `PLATFORM_ADMIN` at the
annotation (`:43`) and `SettingServiceImpl.dynamicQueryResponse` refuses a non-platform-admin again
in the body (`:195-198`) -- deliberately duplicated, with a comment at `SettingRestApi.java:38-42`
saying why. `QueryService.executeQueryResponse` then runs the string **as given** through
`createNativeQuery` with no validator anywhere near it (`QueryService.java:58-71`). The response is
an `ItemResponse` carrying `query`, a `column` set taken from the first row's keys, and `data`; when
the result set is empty none of the three are set, so the client receives `{}`.

### 2.6 Tests

Backend coverage for this feature is the best in the codebase -- 49 test methods across seven files:

| File | Tests | What it pins |
|---|---|---|
| `process/src/test/java/process/engine/query/QueryValidatorTest.java` | 11 (10 `@Test` + 1 `@ParameterizedTest`) | Rejects DML/DDL, multi-statement, `SELECT INTO`, a non-select hidden in a UNION branch, and a second statement hidden behind a trailing comment |
| `.../impl/QueryDefinitionServiceImplTenantIsolationTest.java` | 8 | Cross-tenant fetch/update/delete/validate/preview all refused; a new query cannot name another tenant's connection; a client-supplied `tenantId` is ignored |
| `.../impl/QueryScheduleServiceImplTenantIsolationTest.java` | 8 | Same for schedules, plus `findDueSchedules` being unscoped by design with each row carrying its own tenant |
| `.../impl/ConnectionProfileServiceImplTenantIsolationTest.java` | 8 | Same for connections, plus a platform admin reading any tenant's profile and being unable to own one |
| `.../impl/ConnectionProfileTestConnectionSafetyTest.java` | 5 | A tenant user cannot repoint a saved profile at another host, cannot overwrite a stored password through a test, cannot test an unsaved profile -- and an admin's override is probed on a copy |
| `.../impl/QueryDefinitionAdHocSqlRoleTest.java` | 4 | The saved-vs-ad-hoc split on validate and preview, both directions |
| `.../impl/QueryExecutionServiceImplTenantIsolationTest.java` | 5 | Cross-tenant execute refused, including overriding the connection profile; a positive control that a tenant can run its own |

What is **not** covered anywhere:

- **No controller-level test.** The thirteen `@PreAuthorize` overrides in `QueryEngineRestApi` are
  asserted by nothing. Their correctness rests on reading the file.
- **No test of `QueryExecutionRunner`'s own paths** -- filename templating, `.csv` appending, the
  truncation message, the upload -- except indirectly through the execution isolation test.
- **No frontend test of either screen, in either application.** The old app has **zero** `.spec.ts`
  files anywhere. The new app's only test touching this feature is `app.routes.spec.ts:36-43`, which
  asserts that `/tools/query` has no `minRole` -- it tests the routing decision, not the screen.
  There is no spec for `query-engine.ts`, the three dialogs, or `search-engine.ts`.

---

## 3. Expected behaviour

Numbered where section 11 needs to point at a rule. Where today differs, it is called out.

1. **Running a saved query must ask where the output goes.** A run writes a file into a bucket; the
   user chooses the bucket, optionally a folder, and the file name. **Differs today:** the new app
   sends no destination at all (`query-engine.ts:187-190`) against a server that requires two
   (`QueryExecutionServiceImpl.java:68-73`), so Run now always fails. The old app got this right.

2. **Opening a saved query for editing must show its SQL.** **Differs today:** the new app never
   calls `queries/fetchById`, and the list DTO deliberately omits `queryText`
   (`QueryDefinitionServiceImpl.java:341-357`), so the editor opens empty.

3. **Whatever the client says about SQL is a courtesy; the server decides.** Both apps may hint,
   neither may be trusted. This holds today -- `QueryValidator` runs on add, on update, on validate,
   on preview and again inside the runner.

4. **A tenant user may run and read; only a tenant admin may define.** Reads, `executions/execute`,
   and validate/preview *of a saved query* are `TENANT_USER`. Connection, query and schedule
   authoring is `TENANT_ADMIN`. Holds on the server today; the new frontend mirrors it, the old
   frontend does not.

5. **A control that will be refused should not be offered.** **Differs today** in three places: the
   old app offers every write control to every signed-in user; the new app offers New connection and
   New query to a platform admin, whose creates the service refuses by design
   (`ConnectionProfileServiceImpl.java:81-83`); and the new app's delete-connection confirmation
   describes an outcome the server will not perform.

6. **A field's hint must describe the format the server parses.** **Differs today:** the new
   connection dialog tells the user to write `key=value` per line into a column the server parses as
   JSON (`db-connection-dialog.ts:87` against `DatabaseConnectionFactory.java:59-76`), and the new
   schedule dialog offers `{timestamp}` into a substituter that only knows `{date}`
   (`query-schedule-dialog.ts:52` against `QueryExecutionRunner.java:125-131`).

7. **Client validation bounds must match server validation bounds.** **Differs today:** the schedule
   interval is `min(1)` on the client and `>= 5` on the server
   (`query-schedule-dialog.ts:84` against `QueryScheduleServiceImpl.java:209-211`), and the file
   name template is optional on the client and required on the server (`:87` against `:206-208`).

8. **A status a user can set must mean something.** `Active`/`Inactive` on a *schedule* is honoured
   -- `findDueSchedules` filters on it. On a *query* and on a *connection* it is decorative: neither
   `execute` nor `executeForSchedule` looks at it. Either honour it or stop offering it.

9. **A failure in one panel should not blank the others.** **Differs today:** any one of the four
   loads failing sets one shared error, and `TableShell` replaces the whole table with it
   (`query-engine.ts:100`, `data-table.ts:47-54`).

10. **A run's output should be reachable from the run.** The Runs tab knows the bucket and key; the
    object browser accepts `?bucket=&prefix=` (`features/objects/objects.ts:172-185`). Neither app
    links them. Not a regression -- a gap in both.

11. **A concurrent edit must not be lost silently.** The entity is `@Version`-ed and the service
    honours a supplied version (`QueryDefinitionServiceImpl.java:144-146`). **Differs today:** the
    new dialog does not send one (`query-dialog.ts:127-133`), so the check never fires. The old app
    sent it.

12. **History must not silently truncate.** `fetchAllExecutions` returns the newest 50 and says
    nothing about it (`QueryExecutionRepository.java:16`). Neither UI mentions the cap, and the new
    app's "Failed runs" tile counts failures only inside that window.

13. **Search Engine stays platform-admin-only and read-only.** Holds today at the route, the
    annotation and the service body. The one thing that does **not** hold is that the endpoint runs
    whatever it is given -- `QueryValidator` exists and is not applied to it.

---

## 4. Frontend requirements

### 4.1 Routes

| Route | Component | Guard today | Guard expected |
|---|---|---|---|
| `tools/query` | `features/tools/query-engine/query-engine.ts` `QueryEngine` | `authGuard` on the shell only; no `minRole` | unchanged -- correct, and asserted by `app.routes.spec.ts:36-43` |
| `tools/search` | `features/tools/search-engine/search-engine.ts` `SearchEngine` | `minRole: 'PLATFORM_ADMIN'` + `roleGuard` | unchanged |

The old routes `setting/queryEngine` and `setting/searchEngine` are retired with the old app.

### 4.2 Query Engine screen

**Header.** Title, one-line subtitle, Refresh, and one primary button whose label follows the active
tab -- New connection on the Connections tab, New query elsewhere (`query-engine.html:13-23`). Both
are gated on `canManageQueries()`. **Change:** also hide them when the session has no tenant, since
a platform admin cannot own either.

**Tiles.** Queries, Connections, Scheduled, Failed runs. Keep. **Change:** "Failed runs" needs a foot
label that admits the 50-run window, e.g. `in the last 50 runs`, or the count is a lie on a busy
tenant.

**Tabs.** Queries / Connections / Runs, `role="tablist"`, search cleared on change. Keep.

**Queries table.** Query (name + SQL + author), Connection, Schedule (interval + next run), State,
actions.

- The SQL line must actually have SQL in it -- see §12.2.
- The Schedule pill must distinguish an `Inactive` schedule from an `Active` one; today both render
  `every Nm` while only the Active one is counted in the tile.
- Row menu: Run now (everyone) → **opens a run dialog**; then, for `canManageQueries()`, Edit,
  Schedule / Edit schedule, Remove schedule, separator, Delete.

**New: Run dialog.** The single largest missing piece. Fields, matching what the server reads
(`QueryExecutionRequestDto`):

| Field | Control | Required | Default |
|---|---|---|---|
| Bucket | select, from `storage.json/buckets` via the existing `StorageService.buckets()` | yes | none; the dialog cannot be submitted without one |
| Folder / prefix | text | no | empty |
| File name | text | yes | `<query name sanitised to [A-Za-z0-9_-]>_export`, as the old app did (`query-engine.component.ts:414`) |

A hint must say two things the server does silently: `.csv` is appended if omitted
(`QueryExecutionRunner.java:119-121`), and the file is written by the server into the bucket rather
than downloaded here. On success, switch to Runs and reload -- the behaviour already in
`query-engine.ts:193`.

**Connections table.** Profile, Target, User, Password pill, State, actions (admin only).
**Change:** restore the database-type filter the old app had
(`query-engine.component.html:115-121`). It is a select over one value today (`POSTGRES` is the only
`DatabaseType`), so this is cheap and only earns its place when a second engine lands -- record it,
do it with the second engine.

**Runs table.** Query, Started, Rows, Output, Result. **Changes:**

- restore the **status filter** (`PENDING / RUNNING / SUCCESS / FAILED / CANCELLED`), which is the
  one control an operator actually reaches for on a history screen;
- restore an explicit **Trigger** signal for manual runs -- today a scheduled run gets a pill and a
  manual one gets `run by <name>`, which is blank because the server never fills it (§12.5);
- link the Output cell to `/objects?bucket=…&prefix=…`;
- state the 50-row cap in the table's empty/foot text.

**Dialogs.** Keep all three on `FormDialog` + `Field`. Required fixes are in §12.

### 4.3 Search Engine screen

Keep as built. The write-keyword guard, Ctrl/⌘+Enter, pagination, filter, copy-as-TSV and the
long-cell scroll box are all improvements over the old screen and none of them are enforcement --
the server check is (§8).

One addition worth its weight: the result panel should show the row count against the cap the query
itself set, and `copyResult` should copy the **filtered** rows, which it already does
(`search-engine.ts:106`) -- worth a line of UI text so the user knows.

### 4.4 Loading, empty and error

| State | Query Engine | Search Engine |
|---|---|---|
| Loading | `TableShell` spinner per tab (`data-table.ts:42-46`) | Run button shows `Running…` with a spinning icon (`search-engine.html:32`) |
| Empty (no data) | `No queries yet.` / `No database connections yet.` / `Nothing has run yet.` | result panel absent until a query runs |
| Empty (filtered) | `No <things> match that search.` | `No rows match "<term>".` (`search-engine.html:92`) |
| Error | `TableShell` panel + Try again (`data-table.ts:47-54`) | toast |

**Change:** the error must be per-panel, not per-screen -- see §12.7.

### 4.5 Dark and light mode

Both screens are token-based already: every colour is a `var(--…)` or a semantic class
(`text-[color:var(--text-muted)]`, `border-subtle`, `bg-sunken`, `icon-crit`, `pill-warn`), and the
inline `[style.border-color]` on the validate and test result cards uses `var(--color-ok-500)` /
`var(--color-crit-500)` (`query-dialog.ts:66`, `db-connection-dialog.ts:35`). Status colours come
from the shared `StatusPill` table (`shared/ui/status-pill.ts`), which has per-theme palettes. No new
work; the requirement is that any new control added here follows the same rule and adds no literal
hex.

One gap: `CANCELLED` has no entry in `LOOK` (`status-pill.ts:29-61`), so a cancelled run falls
through to the neutral `UNKNOWN`. No code writes `CANCELLED` today, so this is latent rather than
visible.

### 4.6 Responsive

Tiles are `grid-cols-2 md:grid-cols-4` (`query-engine.html:27`). Tables sit inside `TableShell`'s
`overflow-x-auto` scroll box (`data-table.ts:66`), so a wide row scrolls inside the card rather than
pushing the page sideways. The Search Engine result table has its own `overflow-x-auto`
(`search-engine.html:67`). The dialogs use `form-grid`, which collapses to one column below `sm`.
The run dialog being added must follow the same pattern. The header's button row wraps.

---

## 5. Backend requirements

No new endpoint is needed. The table below is what exists, verified against
`process/src/main/java/process/api/QueryEngineRestApi.java` and `SettingRestApi.java`. "Role" is the
**effective** annotation after the class-level rule is replaced by any method-level one; where the
service narrows it further, the narrowing is named.

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/queryEngine.json/connections/add` | TENANT_ADMIN (class, `:26`) | Creates a profile owned by the caller's tenant; encrypts the password. Refuses a caller with no tenant (`ConnectionProfileServiceImpl.java:81-83`) |
| PUT | `/queryEngine.json/connections/update` | TENANT_ADMIN | Updates a profile the caller owns; a blank password leaves the stored one alone (`:267-269`) |
| DELETE | `/queryEngine.json/connections/delete` | TENANT_ADMIN | Soft-deletes (`status = Delete`) -- **refused** while any non-deleted query names it (`:133-139`) |
| GET | `/queryEngine.json/connections/fetchAll` | TENANT_USER (`:75`) | All non-deleted profiles the tenant filter allows; passwords never returned, only `passwordConfigured` (`:295`) |
| GET | `/queryEngine.json/connections/fetchById` | TENANT_USER (`:86`) | One profile, ownership re-checked. **Called by neither frontend** |
| POST | `/queryEngine.json/connections/testConnection` | TENANT_USER (`:100`) | Opens a real JDBC connection and calls `isValid(5)`. Service narrows: overriding host or password, or testing an unsaved profile, needs TENANT_ADMIN (`:188-190`, `:201-203`) |
| POST | `/queryEngine.json/queries/add` | TENANT_ADMIN | Validates the SQL, checks the connection is owned, stores the **normalised** SQL encrypted (`QueryDefinitionServiceImpl.java:98-115`) |
| PUT | `/queryEngine.json/queries/update` | TENANT_ADMIN | Same, plus an optimistic-lock check when `version` is supplied (`:144-146`) |
| DELETE | `/queryEngine.json/queries/delete` | TENANT_ADMIN | Soft-delete. Does **not** cascade to the query's schedule |
| GET | `/queryEngine.json/queries/fetchAll` | TENANT_USER (`:141`) | Summary DTOs -- **no `queryText`** (`:341-357`) |
| GET | `/queryEngine.json/queries/fetchById` | TENANT_USER (`:152`) | Detail DTO **with** decrypted `queryText` (`:359-363`). **Called by the old app only** |
| POST | `/queryEngine.json/queries/validate` | TENANT_USER (`:165`) | Parser check. Service narrows: no `queryId` on the body ⇒ TENANT_ADMIN (`:287-295`) |
| POST | `/queryEngine.json/queries/preview` | TENANT_USER (`:178`) | Wraps the SQL in `SELECT * FROM (…) LIMIT 101`, 15s timeout, returns ≤100 rows as **objects keyed by column** plus `truncated` (`:251-277`) |
| POST | `/queryEngine.json/executions/execute` | TENANT_USER (`:189`) | **Requires `queryId`, `outputBucket`, `outputFileName`** (`QueryExecutionServiceImpl.java:65-73`). Runs synchronously and returns the finished execution |
| GET | `/queryEngine.json/executions/fetchAll` | TENANT_USER (`:200`) | Newest **50** executions (`QueryExecutionRepository.java:16`) |
| GET | `/queryEngine.json/executions/fetchById` | TENANT_USER (`:211`) | One execution. **Called by neither frontend** |
| GET | `/queryEngine.json/executions/fetchByQueryId` | TENANT_USER (`:222`) | All runs of one query. **Declared in the old service (`query-engine.service.ts:76-78`) and called by nothing, in either app** |
| POST | `/queryEngine.json/schedules/add` | TENANT_ADMIN | Validates, checks the query *and* the connection are owned, sets `nextRunAt = now + interval` (`QueryScheduleServiceImpl.java:64-87`) |
| PUT | `/queryEngine.json/schedules/update` | TENANT_ADMIN | Same; changing the interval resets `nextRunAt` (`:109-113`) |
| DELETE | `/queryEngine.json/schedules/delete` | TENANT_ADMIN | Soft-delete |
| GET | `/queryEngine.json/schedules/fetchAll` | TENANT_USER (`:263`) | All non-deleted schedules, each with its query's name (`:239`) |
| GET | `/queryEngine.json/schedules/fetchById` | TENANT_USER (`:274`) | One schedule. **Called by neither frontend** |
| POST | `/setting.json/dynamicQueryResponse` | PLATFORM_ADMIN (`SettingRestApi.java:43`) | Runs the supplied SQL as given, returns `{query, column, data}` |

### Services

| Service | Lines | Responsibility |
|---|---|---|
| `ConnectionProfileServiceImpl` | 307 | Profile CRUD, password encryption, the test-connection safety rules, the delete-dependency refusal |
| `QueryDefinitionServiceImpl` | 365 | Query CRUD, SQL validation, preview, the saved-vs-ad-hoc role split, summary/detail DTO split |
| `QueryExecutionServiceImpl` | 195 | Starts a run, reads history, `executeForSchedule` for the cron |
| `QueryExecutionRunner` | 141 | The work itself, in `REQUIRES_NEW`: decrypt, re-validate, connect, stream CSV, upload, record |
| `QueryScheduleServiceImpl` | 243 | Schedule CRUD, `findDueSchedules`, `advanceNextRun` |
| `QueryValidator` | 117 | The single SQL gate for the Query Engine |
| `DatabaseConnectionFactory` | 78 | Builds the JDBC URL and properties; POSTGRES only, 10s connect timeout |
| `QueryService.executeQueryResponse` | -- | Search Engine's executor. **No validation of any kind** |

Required backend change, and it is one line of mapping: `QueryExecutionServiceImpl.toDtoWithoutQueryName`
(`:180-193`) must set `createdBy` and `createdByName` -- the DTO has both fields
(`QueryExecutionDto.java:29-30`) and the entity stores `created_by` (`QueryExecutionRunner.java:65`),
but nothing copies them across, which is why the new Runs tab's `run by …` line is always blank.

---

## 6. Database requirements

Four tables, all tenant-scoped, all created by Hibernate rather than by a migration (see below).

| Table | Key columns | Notes |
|---|---|---|
| `database_connection_profile` | `database_connection_profile_id` PK, `tenant_id` NOT NULL, `profile_name`, `database_type` (enum string), `host`, `port`, `database_name`, `username`, `password_encrypted` (len 1000), `additional_properties` TEXT, `status`, audit columns | `DatabaseConnectionProfile.java:39-77`. `additional_properties` is parsed as **JSON** |
| `query_definition` | `query_id` PK, `tenant_id` NOT NULL, `query_name`, `query_text` TEXT NOT NULL, `database_connection_profile_id` NOT NULL, `status`, `version` (`@Version`), audit columns | `QueryDefinition.java:38-88`. `query_text` holds the **encrypted, normalised** SQL |
| `query_schedule` | `schedule_id` PK, `tenant_id` NOT NULL, `query_id` NOT NULL, `database_connection_profile_id` NOT NULL, `output_bucket` NOT NULL, `output_prefix` NOT NULL, `output_file_name_template` NOT NULL, `interval_minutes` NOT NULL, `next_run_at` NOT NULL, `status`, audit columns | `QuerySchedule.java:39-101`. `output_prefix` is NOT NULL and the service writes `""` rather than null (`QueryScheduleServiceImpl.java:219`) |
| `query_execution` | `execution_id` PK, `tenant_id` NOT NULL, `query_id` NOT NULL, `database_connection_profile_id` NOT NULL, `schedule_id` nullable, `status`, `started_at`, `completed_at`, `row_count`, `output_bucket`, `output_key`, `error_message` TEXT, `created_by`, `created_at` | `QueryExecution.java:39-101`. `created_by` only -- a run is not edited (`V22__audit_columns.sql:45-46`) |

Indexes: `idx_query_schedule_next_run_at` and `idx_query_execution_query_id` exist
(per `.ai/discovery/database.md:530`). Foreign keys across the four tables and to
`database_connection_profile` were added by
`process/src/main/resources/db/changelog/changelog-sets/V14.0-remaining-fk-constraints/V14__add_remaining_fk_constraints.sql:13-18`.

**Migration needed -- and it is not for a new feature.** No Liquibase changeset creates any of these
four tables. Grepping the whole of `db/changelog/changelog-sets` for their names returns only V12,
V14, V15 (a comment), V17 and V22 -- migrations that *alter* or *comment on* them. They exist only
because `application-dev.properties:87` sets `ddl-auto=update`. Stage and prod set
`ddl-auto=validate` (`application-stage.properties:90`, `application-prod.properties:92`), and
Liquibase runs before Hibernate, so on a genuinely fresh stage or prod database V14's
`ALTER TABLE query_definition ADD CONSTRAINT …` has no table to alter. This is a whole-repository
problem rather than this feature's alone -- discovery records it as risk 12 -- but these four tables
are among the ones missing, so the fix belongs partly here: a baseline changeset that creates them
with `IF NOT EXISTS`, ordered before V14.

No schema change is required by anything else in this document. Every fix in §12 is a mapping, a
payload or a label.

---

## 7. Validation

"Where" is the honest answer, not the intended one. **Client-only is a finding** and is marked.

### Query Engine -- connection

| Rule | Client | Server | Verdict |
|---|---|---|---|
| `profileName` required | `db-connection-dialog.ts:117` | `ConnectionProfileServiceImpl.java:236-238` | both |
| `host` required | `:119` | `:242-244` | both |
| `port` required | `:120` | `:245-247` | both |
| `port` between 1 and 65535 | — | `:245-247` | **server only** -- the client accepts `0` or `70000` and the user learns from a toast |
| `databaseName` required | `:121` | `:248-250` | both |
| `username` required | `:122` | `:251-253` | both |
| `password` required **on create** | marked required in the label only, via `[required]="!data.connection?.passwordConfigured"` (`:75`); the control itself has **no** `Validators.required` (`:123`) | `:254-256` | **label lies** -- the asterisk shows but the form submits |
| `databaseType` is a known enum | select with one option (`:49-51`) | Jackson enum binding + `DatabaseConnectionFactory.java:35-39` | both |
| `additionalProperties` parses as JSON | **nothing** -- and the hint actively recommends the wrong format (`:87`) | parsed leniently; an unparseable value is logged and **ignored** (`DatabaseConnectionFactory.java:73-75`) | **neither, effectively** -- a bad value silently does nothing |

### Query Engine -- query

| Rule | Client | Server | Verdict |
|---|---|---|---|
| `queryName` required | `query-dialog.ts:129` | `QueryDefinitionServiceImpl.java:321-323` | both |
| `queryText` required | `:130` | `:324-326` | both |
| `databaseConnectionProfileId` required | `:131` | `:327-329` | both |
| SQL is a single SELECT | **nothing** on this screen; the hint says "Read-only statements" (`:58`) | `QueryValidator` on add, update, validate, preview and again in the runner | server -- correct, and correctly the only place |
| Connection belongs to the caller | — | `:309-318` | server only -- correct |
| Optimistic lock on update | **not sent** (`:127-133`) | honoured **only if sent** (`:144-146`) | **dead** -- see §12.4 |

### Query Engine -- schedule

| Rule | Client | Server | Verdict |
|---|---|---|---|
| `outputBucket` required | `query-schedule-dialog.ts:85` | `QueryScheduleServiceImpl.java:203-205` | both -- but the client field is free text, not a bucket picker |
| `outputFileNameTemplate` required | **no validator** (`:87`) | `:206-208` | **server only** |
| `intervalMinutes` required | `:84` | `:209-211` | both |
| `intervalMinutes >= 5` | client says `>= 1` (`:84`, `min="1"` at `:26`) | `>= 5` (`:209-211`) | **disagree** |
| Query and connection both owned | — | `:184-194` | server only -- correct |

### Query Engine -- run

| Rule | Client | Server | Verdict |
|---|---|---|---|
| `queryId` present | implicit | `QueryExecutionServiceImpl.java:65-67` | both |
| `outputBucket` present | **nothing -- not collected at all** | `:68-70` | **server only, and always fails** |
| `outputFileName` present | **nothing -- not collected at all** | `:71-73` | **server only, and always fails** |

### Search Engine

| Rule | Client | Server | Verdict |
|---|---|---|---|
| `query` non-empty | `canRun` (`search-engine.ts:59`) | `SettingServiceImpl.java:200-202` | both |
| starts with SELECT / WITH | `:55` | **nothing** | **client only** -- a finding, though a mild one given the role |
| no write keywords | regex `:16-18`, `:53` | **nothing** | **client only** -- see §8 and §12.9 |
| caller is a platform admin | route `roleGuard` | `@PreAuthorize` **and** `SettingServiceImpl.java:196-198` | all three layers |

---

## 8. Security

Four layers, taken one role at a time. The layers are: (a) the frontend route guard, (b) the
controller `@PreAuthorize`, (c) the service rule, (d) the Hibernate `@Filter`. The role hierarchy is
`ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN > ROLE_TENANT_USER`
(`process/src/main/java/process/config/MethodSecurityConfig.java:27-29`), so `hasRole('TENANT_USER')`
admits all three and `hasRole('TENANT_ADMIN')` admits the top two.

### TENANT_USER

| Layer | Query Engine | Search Engine |
|---|---|---|
| (a) Frontend | **New app:** reaches `/tools/query`; every write control is hidden by `canManageQueries()` (`query-engine.html:13`, `:110`, `:181`) and Run now is deliberately left visible (`:104-109`). **Old app:** reaches `setting/queryEngine` and sees **every** control, because the route carries `AuthGuard` alone (`app.routing.ts:163-168`) | Blocked by `roleGuard` (new) / `RoleGuard` (old); the nav entry is hidden in both |
| (b) Controller | Reads, `executions/execute`, `queries/validate`, `queries/preview`, `connections/testConnection` -- all overridden to `TENANT_USER`. Everything else is the class-level `TENANT_ADMIN` and returns 403 | `@PreAuthorize("hasRole('PLATFORM_ADMIN')")` -- 403 |
| (c) Service | Narrows validate/preview: no `queryId` ⇒ refused (`QueryDefinitionServiceImpl.java:291-293`). Narrows testConnection: any host or password override, or an unsaved profile ⇒ refused (`ConnectionProfileServiceImpl.java:188-190`, `:201-203`). Ownership re-checked after every `findById` | Refused again in the body (`SettingServiceImpl.java:196-198`) |
| (d) Filter | `tenant_id = :tenantId` enabled for every list read on all four entities; `findById` is **not** filtered, which is why (c) matters | Not applicable -- native SQL, no entity, no filter |

The consequence worth stating plainly: **in the old app a tenant user sees a fully functional-looking
Query Engine and every write click returns 403.** The screen is not insecure -- (b) holds -- but it is
misleading, which is its own kind of defect. The new app fixed this.

### TENANT_ADMIN

| Layer | Query Engine | Search Engine |
|---|---|---|
| (a) Frontend | Full screen; all controls shown | Blocked at the route; nav entry hidden |
| (b) Controller | Everything, including the nine unannotated (class-level) methods | 403 |
| (c) Service | May author connections, queries and schedules **for its own tenant only**; may test an unsaved profile and override host/password on a saved one; may run ad-hoc SQL through validate/preview. Every write re-checks that the referenced connection and query are owned (`QueryDefinitionServiceImpl.java:309-318`, `QueryScheduleServiceImpl.java:184-194`) | Refused in the body |
| (d) Filter | Enabled -- lists are its own tenant's rows only | -- |

Cross-tenant reach is closed at (c) and pinned by 24 tests across the three isolation suites. A
client-supplied `tenantId` on an add is ignored -- the services always read
`TenantContext.getTenantId()` -- and there is a named test for that on each of the three entities.

### PLATFORM_ADMIN

| Layer | Query Engine | Search Engine |
|---|---|---|
| (a) Frontend | Full screen, including New connection and New query -- which it must not use | Full access, both apps |
| (b) Controller | Everything, by hierarchy | Allowed |
| (c) Service | `isOwnedByCaller` returns true for every row (`TenantOwnership.java:36-38`), so a platform admin may read, edit, delete, run and schedule **any tenant's** queries. It may **not create** a connection, query or schedule: all three refuse a null tenant (`ConnectionProfileServiceImpl.java:81-83`, `QueryDefinitionServiceImpl.java:95-97`, `QueryScheduleServiceImpl.java:70-72`) | Allowed. `QueryService.executeQueryResponse` runs the string as given |
| (d) Filter | **Disabled** for a platform admin (`TenantFilterHelper.java:28-33`), so `fetchAll` returns every tenant's rows | -- |

Two things follow, and both are UI problems rather than authorization holes:

- A platform admin opening `/tools/query` sees **every tenant's** connections and queries in one
  undifferentiated list, with no tenant column anywhere in `query-engine.html`. It cannot tell whose
  they are. On a multi-tenant install that is a real usability and blast-radius problem: Delete is
  one menu item away from another tenant's saved query.
- The New connection / New query buttons are offered and will always be refused.

**`dynamicQueryResponse` is the highest-value endpoint in the API.** It is correctly gated three
ways, but `QueryService.executeQueryResponse` runs its argument through `createNativeQuery` with no
parser between (`QueryService.java:58-63`) while a suitable parser -- `QueryValidator` -- sits in the
same codebase and is applied to every other SQL path. Anyone holding a platform-admin token has raw
SQL against the platform database. The client-side keyword guard is a courtesy that a `curl` skips.

---

## 9. Error handling

| Failure | Old app | New app | Wanted |
|---|---|---|---|
| Connections/queries/executions list fails | toast; empty table indistinguishable from no data (`query-engine.component.ts:114-117`) | `TableShell` error panel + Try again -- but for the **whole screen**, not the failing panel | per-panel error, per-panel retry |
| Schedule list fails | **silent** (`:255`) -- every query shows `None` | folded into the shared error | per-panel |
| Bucket list fails | **silent** (`:100`) -- the run and schedule dropdowns are simply empty | not applicable; there is no bucket list | the new run dialog must show `Could not list buckets` rather than an empty select |
| Save/delete returns `status: ERROR` | `alertService.showError(response.message)` | `toast.error(r.message)` | unchanged -- the server's message is the useful one |
| Save/delete throws HTTP | `showError(error)` -- passes the raw `HttpErrorResponse` | `toast.error(e?.error?.message \|\| '<sentence>')` (e.g. `query-engine.ts:147`) | the new app's shape; keep |
| Test connection fails | inline red line under the button (`query-engine.component.html:329-332`); the server has already sanitised the driver message to its first line, truncated at 200 chars (`ConnectionProfileServiceImpl.java:226-233`) | inline card with a red border and an X icon (`db-connection-dialog.ts:33-40`) | unchanged |
| Validate fails | inline red line | inline card (`query-dialog.ts:64-71`) | unchanged |
| Preview fails | toast (`query-engine.component.ts:352`) | inline card, same place as Validate (`query-dialog.ts:181`) | the new app's -- the message belongs next to the SQL |
| Run fails | toast with the server's message | toast -- today always `outputBucket missing.` | after §12.1, a real failure message; a failed run also appears in the Runs tab with `errorMessage` |
| Query truncated at the row cap | shows as `SUCCESS` with the cap message in the Message column | shows as `SUCCESS` with the message under Started, in crit red | the message should not be red on a successful run -- it is a warning, not a failure |
| Delete a connection that queries use | server refuses with a counted sentence (`ConnectionProfileServiceImpl.java:136-138`); toast | same refusal -- **but the confirm dialog has already promised the opposite** (`query-engine.ts:132-135`) | the dialog must state the refusal, not contradict it |
| Scheduled run fails | not visible on this screen | not visible on this screen | the run is recorded with its error and shows in the Runs tab; the cron logs it (`ProcessCron.java:100-101`). Notifying anybody is out of scope |
| Search Engine query fails | toast with the server message | toast; result cleared (`search-engine.ts:79-83`) | unchanged |
| Search Engine returns no rows | server sends `{}`; the table header renders empty and the count reads 0 | `The query ran but returned no columns.` (`search-engine.html:62-65`) | the new app's |

---

## 10. Dependencies

- **`authentication-and-access`** -- the whole role model. `canManageQueries()` reads the role from
  the JWT claim, not from the stored blob (`auth.service.ts:20-31`, `:53-56`), and `roleGuard` +
  `authGuard` decide who reaches `/tools/search` and the shell.
- **`storage-connections` / `object-browser`** -- a run has nowhere to write without a bucket.
  `QueryExecutionRunner.runAndRecord` calls `StorageBrowserService.uploadObject`
  (`QueryExecutionRunner.java:82-85`), and the run dialog being restored needs
  `StorageService.buckets()` (`features/objects/storage.service.ts:32-34`), already used by the
  converter and transcript screens.
- **The scheduler cron** -- `ProcessCron.pollDueQuerySchedules` is what makes a schedule mean
  anything (`ProcessCron.java:78-120`).
- **`EncryptionUtil`** -- both the connection password and the SQL itself. Losing
  `LOOKUP_ENCRYPTION_KEY` costs every saved query, not just every password (discovery risk 46).
- **JSqlParser** -- `QueryValidator` is the only thing standing between a saved query and arbitrary
  SQL on a customer database.
- **`platform-configuration`** -- only in that Search Engine's endpoint lives on `SettingRestApi`
  alongside unrelated settings work; nothing else is shared.

---

## 11. Acceptance criteria

Each is checkable by someone who did not write the code. Fixtures assumed: tenant **A** with a
connection `conn-A` and two saved queries `qA1` (unscheduled) and `qA2` (scheduled, 60 min); tenant
**B** with `conn-B` and `qB1`; users `userA` (TENANT_USER, tenant A), `adminA` (TENANT_ADMIN, tenant
A), `adminB` (TENANT_ADMIN, tenant B), `platform` (PLATFORM_ADMIN, no tenant); at least one storage
bucket visible to tenant A.

**Running a query**

1. `adminA` opens `/tools/query`, chooses **Run now** on `qA1`, and a dialog appears asking for a
   bucket, an optional folder and a file name; the file name is pre-filled from the query's name.
2. `adminA` submits that dialog with a bucket and file name `qa1_export`; the screen switches to the
   Runs tab, a new row appears with status `SUCCESS`, a row count, and an Output cell reading
   `<bucket>/qa1_export.csv`.
3. Opening the object browser at that bucket shows `qa1_export.csv`, and its content is the query's
   result. (Positive control that the run actually wrote a file, not just a row.)
4. `adminA` submits the run dialog with the file name `qa1_export.csv`; the object key is
   `qa1_export.csv` and **not** `qa1_export.csv.csv`.
5. `adminA` opens the run dialog and clears the bucket; the submit control is disabled and the
   request is never sent. (No `outputBucket missing.` toast should ever reach a user.)
6. `userA` -- a tenant user -- opens `/tools/query`, sees **Run now** on `qA1`, uses it, and gets a
   `SUCCESS` row. This is the feature's whole point and must be verified as carefully as any refusal.
7. `userA` sees no New query, no New connection, no Edit, no Schedule, no Delete anywhere on the
   screen, and the connections tab shows rows with no action menu.
8. With the frontend bypassed, `userA` POSTs `queryEngine.json/queries/add`; the response is 403.
   (Positive control: the same `userA` POSTing `executions/execute` with a valid body succeeds.)

**Editing a query**

9. `adminA` chooses **Edit** on `qA1`; the SQL box contains `qA1`'s SQL, not an empty box.
10. `adminA` changes only the query's name and saves; the save succeeds and the SQL is unchanged when
    the dialog is reopened.
11. `adminA` opens `qA1` for editing in two browser tabs, saves the first, then saves the second;
    the second save is refused with the message about somebody else having changed it, and the first
    save's content survives.
12. `adminA` types `DELETE FROM orders` into the SQL box and presses **Validate**; an inline failure
    appears naming the statement type. Pressing Save with the same text is also refused.
13. `adminA` types a valid `SELECT` and presses **Preview**; a table appears with a header row of
    column names **and at least one populated data row** (given a table with rows). Every cell shows
    its value; no cell is blank where the database has data.
14. A preview of a query returning more than 100 rows shows exactly 100 rows and a `truncated` pill.

**Connections**

15. `adminA` creates a connection with a valid host, port, database, username and password; **Test
    connection** in the dialog reports a success with an elapsed time, and the saved row's Password
    column reads `stored`.
16. `adminA` reopens that connection, leaves the password blank and saves; the row still reads
    `stored` and Test connection still succeeds. (The blank did not wipe the password.)
17. `adminA` enters port `70000` and saves; the port field shows an inline error **before** any
    request is sent.
18. `adminA` puts `{"sslmode":"require"}` into Additional properties and the field's hint describes
    that JSON format. Saving and testing succeeds; putting `sslmode=require` there produces a visible
    complaint rather than being silently discarded.
19. `userA` opens the Connections tab: the rows are listed (so the Queries tab's Connection column is
    readable) and there is no action menu on any row. (Positive control: `adminA` on the same tab has
    a menu on every row.)
20. `adminA` deletes `conn-A` while `qA1` and `qA2` still use it; the **confirmation dialog says the
    delete will be refused while queries use it**, and if confirmed, the server's refusal appears as
    a toast naming the count. `conn-A` is still in the list afterwards.
21. `adminA` deletes `qA1` and `qA2`, then deletes `conn-A`; it succeeds and disappears from the list.
    (Positive control for 20.)

**Schedules**

22. `adminA` schedules `qA1` with an interval of 3 minutes; the interval field shows an inline error
    saying the minimum is 5, before any request is sent.
23. `adminA` schedules `qA1` with an interval of 60 and a bucket, leaving the file name template
    empty; the template field is marked required and the dialog will not submit.
24. `adminA` schedules `qA1` with template `qa1_{date}`; within one interval the Runs tab shows a run
    tagged `scheduled` whose Output key contains today's date in `yyyy-MM-dd` form.
25. The file name template field's hint names `{date}` as the placeholder, and no other placeholder
    is offered in the hint or the example.
26. `adminA` sets `qA2`'s schedule to `Inactive`; the Queries tab stops showing it as an active
    schedule, the Scheduled tile drops by one, and no further scheduled run appears. Setting it back
    to `Active` resumes runs.
27. `adminA` chooses **Remove schedule** on `qA2`; a confirmation appears, and after confirming, the
    Schedule cell reads `manual only` and `qA2` can still be run by hand.

**Cross-tenant refusals, each with its positive control**

28. `adminB` requests `queryEngine.json/queries/fetchById?queryId=<qA1>`; the response is an error
    saying the query was not found. The same call with `<qB1>` succeeds.
29. `adminB` POSTs `executions/execute` naming `<qA1>`; refused. Naming `<qB1>` with a valid bucket
    and file name; succeeds.
30. `adminB` POSTs `schedules/add` with its own `qB1` but `conn-A`'s profile id; refused with a
    connection-not-found message. The same call with `conn-B`'s id succeeds.
31. `adminB` POSTs `queries/add` with an explicit `tenantId` of A in the body; the created row's
    `tenant_id` is B's.
32. `userA` POSTs `queries/preview` with `{queryText, databaseConnectionProfileId}` and no `queryId`;
    refused with the "only a tenant admin can run SQL that is not saved" message. The same `userA`
    POSTing `{queryId: qA1}` succeeds.
33. `userA` POSTs `connections/testConnection` with `conn-A`'s id and a different `host`; refused.
    The same call with only `{databaseConnectionProfileId: conn-A}` succeeds.
34. `userA` POSTs `connections/testConnection` with a full unsaved profile and no id; refused.
    `adminA` making the identical call succeeds.
35. After 33, `conn-A`'s stored host in the database is unchanged.

**Platform admin**

36. `platform` opens `/tools/query` and can tell which tenant each connection and each query belongs
    to. (Today it cannot; this is the criterion for the fix.)
37. `platform` is not offered New connection or New query; if it is offered and used, the refusal
    message explains that a platform admin cannot own one.
38. `platform` can run and can delete any tenant's query. (Positive control that the elevated role
    still works, since 36 and 37 restrict what it is shown.)

**Search Engine**

39. `platform` opens `/tools/search`, runs `SELECT job_id, job_name FROM source_job LIMIT 5`, and
    gets a table of five rows with those two column headers.
40. `adminA` navigating to `/tools/search` is redirected and never sees the screen; the Tools menu
    shows no Search Engine entry for `adminA`.
41. `adminA` POSTs `setting.json/dynamicQueryResponse` directly; the response is 403 or the service's
    refusal message -- not a result set. (Positive control: `platform` making the same call gets rows.)
42. `platform` types `DELETE FROM source_job` into the box; the Run button is disabled and an inline
    warning names the problem.
43. `platform` POSTs `DELETE FROM source_job WHERE 1=0` to `dynamicQueryResponse` directly, bypassing
    the box; the server refuses it. (This fails today -- see §12.9.)
44. `platform` runs a query returning 300 rows, sets the page size to 50, and pages through; the
    filter box narrows the rows and the count reads `<shown> of 300`.
45. `platform` presses Copy; the clipboard holds tab-separated text whose first line is the column
    names and whose remaining lines are the **currently filtered** rows.

**Shared states**

46. With the network blocked, `adminA` opens `/tools/query`; each of the three tabs shows an error
    panel with a Try again button, and pressing it after restoring the network loads the data.
47. With only `schedules/fetchAll` failing, the Queries table still renders its rows; the failure is
    reported against the schedule information alone and not by blanking the table.
48. `adminA` types a term matching nothing into the Queries search box; the empty state reads
    `No queries match that search.` and not `No queries yet.`
49. On a viewport of 375px, neither screen scrolls horizontally at the page level; the tables scroll
    inside their own cards.
50. Both screens render correctly in light and dark mode, including the validate/test result cards
    and every status pill, with no element using a literal colour.

---

## 12. Known issues

Each is a defect that exists **today**, with the evidence. None is fixed here.

### 12.1 Run now is broken in the new app -- the feature's main verb does not work

`query-engine.ts:187-190` posts:

```ts
this.http.post<ApiResponse>(`${API_BASE}/queryEngine.json/executions/execute`,
  { queryId: query.queryId })
```

`QueryExecutionServiceImpl.execute` (`:65-73`) checks, in order, `queryId`, then:

```java
if (isNull(request.getOutputBucket()) || request.getOutputBucket().trim().isEmpty()) {
    return new ResponseDto(ERROR, "outputBucket missing.");
}
```

So **every** press of Run now returns `status: ERROR, message: "outputBucket missing."`, which the
component surfaces as a toast (`:194`). No execution row is created, nothing is written, and the
Runs tab stays empty. The old app posted all four fields from its run modal
(`query-engine.component.ts:427-432`) and worked. Severity: **blocker** -- a tenant user's only
action on this screen is the one that fails.

### 12.2 A saved query cannot be edited in the new app, and its SQL is never shown

`fetchAllQueries` maps through `toSummaryDto`, which sets id, name, connection, status, version,
timestamps and author -- and **not** `queryText` (`QueryDefinitionServiceImpl.java:341-357`). Only
`toDetailDto` adds the decrypted SQL (`:359-363`), and only `queries/fetchById` returns it. Grepping
`scheduler1/next/src` for `queries/fetchById` returns **nothing**. Three consequences:

- `query-engine.html:73-75` renders `{{ q.queryText }}` under every query name -- always an empty
  line;
- `filteredQueries` searches `` `${q.queryName} ${q.queryText}` `` (`query-engine.ts:65-66`) behind a
  placeholder reading "Search name or SQL" -- the SQL half matches nothing, and searching for the
  literal `undefined` matches everything;
- `editQuery` passes the list row into the dialog, whose form seeds `queryText` from
  `this.data.query?.queryText ?? ''` (`query-dialog.ts:130`), so **the editor opens with an empty SQL
  box**. Saving from there is rejected by the server with `queryText missing.`
  (`QueryDefinitionServiceImpl.java:324-326`); saving after retyping silently replaces the SQL. The
  old app avoided all of this by calling `fetchQueryById` first
  (`query-engine.component.ts:287-300`). Severity: **blocker**.

### 12.3 The preview table in the new query dialog cannot render its rows

The server returns rows as `List<Map<String, Object>>` -- one JSON object per row, keyed by column
name (`QueryPreviewResponseDto.java:15`, built at `QueryDefinitionServiceImpl.java:263-276`). The new
client declares `rows: any[][]` (`types.ts:62`) and iterates each row as a collection:

```html
<tr>@for (cell of row; track $index) { <td …>{{ cell }}</td> }</tr>
```
(`query-dialog.ts:90-92`)

`@for` requires an array or an iterable, and a plain object is neither. The column headers render
(`p.columns` is a real array) and the row count pill renders, but the body cannot. The old app read
`row[col]` and matched the server (`query-engine.component.html:424-426`). The exact runtime symptom
-- a thrown `TypeError` during change detection versus an empty body -- is **not verified**; the shape
mismatch is verified from both ends. Severity: **major**.

### 12.4 The optimistic-lock check is dead in the new app

`QueryDefinition` is `@Version`-ed (`QueryDefinition.java:66-68`) and `updateQuery` compares a
supplied version against the stored one (`QueryDefinitionServiceImpl.java:144-146`) -- but only
`if (!isNull(dto.getVersion()))`. The new dialog's form has no `version` control
(`query-dialog.ts:127-133`) and `save()` sends `this.form.getRawValue()` (`:194`), so the field is
absent and the check is skipped every time. Two admins editing the same query silently overwrite
each other. The old app sent it (`query-engine.component.ts:367`). Severity: **major**.

### 12.5 "run by" on the Runs tab is always blank

`query-engine.html:232-234` renders `run by {{ e.createdByName }}` for any non-scheduled run.
`QueryExecutionDto` has both `createdBy` and `createdByName` (`QueryExecutionDto.java:29-30`), and
the runner stamps `created_by` on the row (`QueryExecutionRunner.java:65`) -- but
`toDtoWithoutQueryName` (`QueryExecutionServiceImpl.java:180-193`) copies ten fields and neither of
those two. Every manual run therefore renders the literal text `run by` with nothing after it. The
sibling services do resolve names (`QueryDefinitionServiceImpl.java:352-355`,
`ConnectionProfileServiceImpl.java:300-303`), so this is an omission, not a design choice.
Severity: **minor** (cosmetic, but it prints a dangling label).

### 12.6 The delete-connection confirmation promises the opposite of what happens

`query-engine.ts:132-135` builds the body as:

> `${dependents} queries run against this connection and will have nowhere to execute.`

`ConnectionProfileServiceImpl.java:133-139` refuses the delete outright while any non-deleted query
references the profile. So the dialog describes an orphaning that cannot occur, invites the user to
confirm it, and then shows a toast contradicting the dialog they just read. Severity: **minor**, but
it teaches the user to distrust confirmations.

### 12.7 One failing request blanks all three tables

`loadAll` runs four GETs against one shared `error` signal (`query-engine.ts:92-107`), and
`TableShell` renders `error()` **instead of** the table body (`data-table.ts:47-54`). If only
`schedules/fetchAll` fails, the Queries table -- whose own request succeeded -- is replaced by
`Some Query Engine data could not be loaded.` Severity: **minor**. Worth contrasting with the old
app, which had the opposite defect: the same failure was swallowed entirely
(`query-engine.component.ts:255`) and every query silently showed `None` in the Schedule column.

### 12.8 Three field hints describe formats the server does not accept

| Hint | Where | What the server does |
|---|---|---|
| "One key=value per line, appended to the JDBC URL." | `db-connection-dialog.ts:87`, placeholder `sslmode=require` at `:89` | `DatabaseConnectionFactory.mergeAdditionalProperties` parses the column as JSON with Gson and merges it into the connection `Properties` -- it is not appended to the URL. An unparseable value is caught, logged at WARN and **ignored** (`:63-75`), so following the hint produces no error and no effect |
| `orders-{timestamp}.csv` placeholder and "Without a timestamp placeholder each run overwrites the last file." | `query-schedule-dialog.ts:49-52` | `resolveFileNameTemplate` substitutes `{date}` and nothing else (`QueryExecutionRunner.java:125-131`). `{timestamp}` is written into the object key literally, so every run **does** overwrite -- the hint's own warning case |
| Password marked required on a new connection | `db-connection-dialog.ts:75` sets `[required]="!…passwordConfigured"`, which draws the asterisk; the control at `:123` has no validator | The server requires it on create (`ConnectionProfileServiceImpl.java:254-256`), so the form submits and the toast refuses |

Severity: **major** for the first (a silently ignored security-relevant setting -- `sslmode` is the
usual reason anyone touches that field), **minor** for the other two.

### 12.9 `dynamicQueryResponse` runs its argument with no validation

`SettingServiceImpl.dynamicQueryResponse` checks the role and that the string is non-null
(`:196-202`), then `QueryService.executeQueryResponse` does
`this._em.createNativeQuery(queryString)` (`QueryService.java:60`). `QueryValidator` -- which the
Query Engine applies on five separate paths -- is never invoked here. The new client's keyword regex
(`search-engine.ts:16-18`) is the only check anywhere, and it is client-side. A platform-admin token
plus `curl` is unrestricted SQL against the platform database, including forms that return a result
set and therefore survive `getResultList()`, such as `WITH d AS (DELETE FROM t RETURNING *) SELECT * FROM d`.
Discovery records this as risk 15. Severity: **major** by consequence, **accepted-by-design** by
role -- which is exactly why it needs a decision rather than a silent continuation (§6 of the
synthesis).

### 12.10 `Inactive` is decorative on a query and on a connection

The new dialogs both offer a Status select (`query-dialog.ts:101-106`,
`db-connection-dialog.ts:92-97`) and the server stores what they send
(`QueryDefinitionServiceImpl.java:150-152`, `ConnectionProfileServiceImpl.java:112-114`). Nothing
reads it: `execute` (`QueryExecutionServiceImpl.java:74-89`) and `executeForSchedule` (`:99-108`)
both resolve by id and run, whatever the status. Only `Delete` has an effect, via the `StatusNot`
list queries. A schedule's status **is** honoured (`QueryScheduleRepository.java:19-20`), which makes
the inconsistency sharper: the same word means something in one dialog and nothing in the next two.
Severity: **minor**, but it is a control that lies.

### 12.11 The old app's Validate button validates the wrong text when editing

`query-engine.component.ts:317-319` sends `{ queryId, queryText }` when editing.
`resolveQueryText` (`QueryDefinitionServiceImpl.java:297-307`) checks `queryId` **first** and returns
the stored, decrypted SQL, ignoring the `queryText` on the body entirely. So pressing Validate after
editing the SQL validates the *saved* version -- it will report valid on text the user has just
broken. The new app avoids this by always sending `queryText` and never `queryId`
(`query-dialog.ts:149-150`). Old app only; recorded because the old app is still live.

### 12.12 Smaller items, verified

- **History is capped at 50 with no indication.** `findTop50ByOrderByExecutionIdDesc`
  (`QueryExecutionRepository.java:16`). The new app's "Failed runs" tile
  (`query-engine.ts:59`) counts inside that window and reads as a fleet total.
- **`PENDING` and `CANCELLED` are never written.** `runAndRecord` sets `RUNNING`, then `SUCCESS` or
  `FAILED` (`QueryExecutionRunner.java:63`, `:86`, `:97`). The old app's status filter offers all
  five (`query-engine.component.ts:65`); two of them can never match. `CANCELLED` also has no entry
  in the new `StatusPill` table (`status-pill.ts:29-61`), so it would render as neutral `UNKNOWN`.
- **A truncated result is red.** `QueryExecutionRunner.java:90-93` writes the truncation notice into
  `errorMessage` on a row whose status is `SUCCESS`; `query-engine.html:239` renders any
  `errorMessage` in `text-crit-500`. A successful, capped export therefore looks like a failure.
- **Deleting a query leaves its schedule behind.** `deleteQuery` sets the query's status and stops
  (`QueryDefinitionServiceImpl.java:170-173`). The schedule row keeps `status = Active`, so
  `findDueSchedules` keeps returning it and `executeForSchedule` keeps finding the query --
  `findById` ignores the soft-delete -- so **a deleted query keeps running on its schedule**. The new
  app's delete confirmation even says "Deleting it stops the schedule as well" (`query-engine.ts:171`),
  which is not true. Severity: **major**; it is the one place where a UI claim and a data
  consequence diverge in a way a user will not notice for hours.
- **`executions/fetchByQueryId` is dead in both clients.** Declared at
  `scheduler1/src/app/_services/query-engine.service.ts:76-78` and called by nothing; absent from
  `scheduler1/next/src` entirely. `connections/fetchById`, `executions/fetchById` and
  `schedules/fetchById` are called by neither app either.
- **No controller-level authorization test exists** for any of the 22 `QueryEngineRestApi` methods.
  The thirteen overrides are load-bearing and unasserted.
- **The four tables have no creating migration** (§6).

---

## 13. Missing functionality

Absent from both applications, or absent from the new one and never present in the old. Ordered by
what an operator would miss first.

**Per-query run history.** `executions/fetchByQueryId` exists, is `TENANT_USER`, and is called by
nothing. The natural home is a "Runs" entry in the query's row menu that opens the Runs tab
pre-filtered, or a drawer. Cost: small -- the endpoint and the DTO already exist; it is a filter
signal and a menu item.

**A link from a run to its output.** The Runs tab has `outputBucket` and `outputKey`; the object
browser accepts `?bucket=&prefix=` and the jobs screen already links that way
(`features/jobs/jobs.html:317-323`). Today the user copies a path by eye. Cost: small.

**Pagination on the three Query Engine tables.** `Pagination` and `createPager` exist and the Search
Engine screen already uses them (`search-engine.ts:33`, `search-engine.html:100`). The Runs tab is
capped at 50 by the server so it does not need paging yet; queries and connections will. Cost: small
for the client. Making history longer than 50 needs a server-side page parameter -- medium.

**A "mine" filter.** Ten screens in the new app use `shared/ui/mine-filter.ts`; this one does not,
even though its DTOs now carry `createdBy` and `createdByName`. Cost: small, and it makes the author
line already on the row actionable.

**Sorting.** `shared/ui/sort.ts` is used by four screens. None of the three tables here sorts by
anything but the server's id-descending order. Cost: small.

**A tenant column for a platform admin.** §8 -- a platform admin sees every tenant's rows with no way
to tell them apart. The DTOs do not carry a tenant name today, so this needs a field on
`QueryDefinitionDto` and `DatabaseConnectionProfileDto` plus a conditionally-rendered column. Cost:
medium.

**Cancelling a running query.** `QueryExecutionStatus.CANCELLED` exists and nothing can produce it.
`execute` is synchronous -- the HTTP request is held open for up to 300 seconds
(`QueryExecutionRunner.java:112-113`) -- so cancellation would mean making execution asynchronous
first. Cost: large, and it changes the run dialog's contract from "here is your result" to "here is
your run id". Genuinely out of scope for this pass; recorded because the enum implies it exists.

**More than one database engine.** `DatabaseType` has a single value and
`DatabaseConnectionFactory.openConnection` throws for anything else
(`DatabaseConnectionFactory.java:35-39`). MySQL or SQL Server would need a driver, a URL builder and
a preview-wrapper that is not PostgreSQL's `LIMIT` syntax (`QueryDefinitionServiceImpl.java:251-252`).
Cost: large.

**Output formats other than CSV.** `CsvExportService` is the only exporter and `.csv` is appended
unconditionally (`QueryExecutionRunner.java:119-121`). Cost: medium per format.

**Anything at all when a scheduled run fails.** It is recorded and logged
(`ProcessCron.java:100-101`) and appears in the Runs tab if somebody looks. There is a `Notification`
entity in the codebase, and this feature uses none of it. Cost: medium.

**Saving a Search Engine query.** By design -- that is what the Query Engine is for. Recorded so the
absence is a decision rather than an oversight. The two screens sit next to each other in the menu
and a user will ask.
