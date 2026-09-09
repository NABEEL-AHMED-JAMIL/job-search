# Synthesis -- Query and Search Engines

Paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`. Every claim here is carried over from
`.ai/grooming/query-and-search-engines.md`, where it is cited to a file and line.

---

## 1. Summary

Discovery filed this feature as **migrated**, and by route coverage it is: both screens exist in
both applications. Reading the code says something narrower. The rewrite carried across the shape of
the Query Engine -- three tabs, the same four resources, better states, a proper role split that the
old app never had -- and dropped the **Run dialog**, which was the only place the destination bucket
and file name were collected. The server has required both since it was written
(`QueryExecutionServiceImpl.java:68-73`), so the new Run now button posts `{ queryId }` and gets back
`outputBucket missing.` every single time. The other half of the same story is the query editor: the
list endpoint deliberately omits the SQL (`QueryDefinitionServiceImpl.java:341-357`) and the new app
never calls `queries/fetchById`, so Edit opens with an empty SQL box. Between them, **the two things
a person comes to this screen to do are both broken**, and neither was broken in the old app.

Everything else is smaller and of one kind: places where the new client and the server disagree about
a contract that only the server enforces. The preview grid iterates rows as arrays against a server
that sends objects. The update payload omits the `version` the server would have used for optimistic
locking. The schedule dialog allows an interval the server rejects and permits an empty template the
server requires. Three field hints describe formats the server does not parse -- one of them
`sslmode`, silently discarded. Two confirmations describe outcomes that do not happen. And two
filters the old screen had -- database type on connections, status on runs -- did not come across.

Underneath the client there is one real server bug worth the same attention: soft-deleting a query
does not stop its schedule, so a query a user believes they deleted keeps running every interval and
keeps writing files. The new app's own confirmation text promises the opposite.

The work is therefore: **restore the run dialog and the SQL fetch; align eight client contracts with
the server; fix the delete-cascade; restore two filters; and decide four things a human has to
decide** -- chiefly whether the Search Engine's unvalidated SQL path stays as it is.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | Run now posts `{ queryId }`; server requires `outputBucket` and `outputFileName`, so every run fails with `outputBucket missing.` (`query-engine.ts:187-190` vs `QueryExecutionServiceImpl.java:68-73`) | Run asks where the output goes and then runs | The whole run dialog was dropped in the rewrite | New `QueryRunDialog` on `FormDialog`: bucket select fed by `StorageService.buckets()`, optional prefix, required file name defaulted from the query name | M | **Blocker.** Low technical risk -- the old app's dialog is a working reference |
| 2 | Edit opens with an empty SQL box; the list DTO carries no `queryText` and `queries/fetchById` is called nowhere in `scheduler1/next/src` | Edit shows the query's SQL | The detail fetch was never wired | `editQuery` fetches by id, then opens the dialog with the detail row | S | **Blocker.** Adds one request to opening a dialog |
| 3 | Preview iterates each row with `@for (cell of row)` against `List<Map<String,Object>>` (`query-dialog.ts:90-92`, `QueryPreviewResponseDto.java:15`) | Preview shows the rows | Client row type is `any[][]`; server sends objects | Change `PreviewResult.rows` to `Record<string, unknown>[]` and index by column | S | Low. Contained to one dialog |
| 4 | `queries/update` sends no `version`, so the optimistic-lock check never fires (`query-dialog.ts:127-133` vs `QueryDefinitionServiceImpl.java:144-146`) | A concurrent edit is refused, not silently lost | The field was dropped from the form | Carry `version` through the dialog and surface the server's refusal | S | Low. Depends on #2 -- the version has to come from the detail fetch |
| 5 | `run by` on the Runs tab is always blank; `toDtoWithoutQueryName` never copies `createdBy`/`createdByName` (`QueryExecutionServiceImpl.java:180-193`) | A manual run names who ran it | Two missing lines in one mapper | Set both, using the `UserNameResolver` the sibling services already inject | S | Low |
| 6 | Soft-deleting a query leaves its schedule `Active`, and `executeForSchedule` finds the query by id regardless of status -- so a deleted query keeps running | Deleting a query stops its schedule, as the confirmation already claims | No cascade in `deleteQuery` | Soft-delete the query's schedules in the same transaction | S | **Major.** Touches the cron's input; needs a test |
| 7 | The delete-connection confirmation promises orphaned queries; the server refuses the delete outright (`query-engine.ts:132-135` vs `ConnectionProfileServiceImpl.java:133-139`) | The dialog states the rule that will actually be applied | Confirmation text written against an imagined server | Rewrite the body; when dependants exist, offer no destructive confirm at all | S | Low |
| 8 | Additional-properties hint says "One key=value per line, appended to the JDBC URL"; the server parses the column as JSON and silently ignores anything else (`db-connection-dialog.ts:87` vs `DatabaseConnectionFactory.java:59-76`) | The hint describes JSON; a malformed value is reported | Hint written against an imagined parser; server swallows the error | Fix the hint and placeholder; add a client-side JSON parse check; have the service reject unparseable input on save rather than at connect time | S | Low, but it is the field people use for `sslmode` |
| 9 | Schedule dialog offers `{timestamp}`; the runner substitutes `{date}` only, so the literal string lands in the object key and every run overwrites (`query-schedule-dialog.ts:52` vs `QueryExecutionRunner.java:125-131`) | The hint names the placeholder that exists | Hint invented a placeholder | Change the placeholder and hint to `{date}`; state the yyyy-MM-dd format | S | Low |
| 10 | Schedule interval is `min(1)` on the client, `>= 5` on the server; the file-name template is optional on the client, required on the server | Client bounds match server bounds | Two validators drifted | `Validators.min(5)`, `min="5"`, `Validators.required` on the template with the old app's `<name>_{date}` default | S | Low |
| 11 | Password shows a required asterisk on a new connection but has no validator, so the form submits and the server refuses | The marker and the rule agree | `[required]` drives the label only | Add a conditional `Validators.required` for the create case | S | Low |
| 12 | Schedule dialog's bucket is free text; the old app used a dropdown from `storage.json/buckets` | The bucket is chosen, not typed | Picker dropped in the rewrite | Reuse the bucket select built for #1 | S | Low -- folds into #1 |
| 13 | No database-type filter on Connections; no status filter on Runs. The old app had both (`query-engine.component.html:115-121`, `:193-199`) | An operator can narrow a history by outcome | Two toolbar controls dropped | Add the status filter now; add the type filter when a second `DatabaseType` exists | S | Low |
| 14 | Any one of the four loads failing replaces **all three** tables with one error (`query-engine.ts:92-107`, `data-table.ts:47-54`) | A panel reports its own failure | One shared error signal | Four error signals, mapped per tab; schedules failing degrades the Schedule column rather than blanking the table | S | Low |
| 15 | A truncated-but-successful export writes its notice into `errorMessage` and the UI renders any `errorMessage` in crit red | A capped result reads as a warning | One field used for two meanings | Add `truncated` to `QueryExecutionDto` (or detect the prefix) and render a warn pill | S | Low |
| 16 | History is capped at the newest 50 (`QueryExecutionRepository.java:16`) with no disclosure, and the "Failed runs" tile counts inside that window | The cap is visible | Undocumented server limit | Say so in the tile foot and the table heading now; server-side paging later | S | Low now, M if paged |
| 17 | `Inactive` on a query and on a connection is stored and never read; only a schedule's status is honoured | A status a user can set means something | Enum applied inconsistently | Refuse to execute an `Inactive` query or through an `Inactive` connection -- see §6, Q2 | S | Medium: it changes runtime behaviour for anyone who set the flag believing it inert |
| 18 | A platform admin sees every tenant's connections and queries in one list with no tenant column, and is offered New buttons the service always refuses | A platform admin can tell whose row it is and is not offered impossible creates | Filter disabled for platform admins by design (`TenantFilterHelper.java:28-33`); UI never accounted for it | Add `tenantName` to both DTOs, render a column when `isPlatformAdmin()`; gate the New buttons on having a tenant | M | Medium. Delete is one menu item from another tenant's query |
| 19 | `setting.json/dynamicQueryResponse` runs its argument through `createNativeQuery` with no parser, while `QueryValidator` sits in the same codebase (`QueryService.java:58-63`) | A read-only console is read-only on the server too | Validator never applied to this path | Route the string through `QueryValidator` -- see §6, Q1 | S | Medium: it will reject queries a platform admin runs today |
| 20 | No Liquibase changeset creates `database_connection_profile`, `query_definition`, `query_schedule`, `query_execution`; they exist only via `ddl-auto=update` in dev, and V14 alters them | A fresh stage/prod database builds | Repository-wide baseline gap; four of the missing tables are ours | Baseline changeset creating the four with `IF NOT EXISTS`, ordered before V14 | M | Medium, and it is not this feature's problem alone -- see §5 |
| 21 | Zero frontend tests for either screen in either app; zero controller-level authorization tests for the 22 `QueryEngineRestApi` methods | The role split is asserted, not just read | Never written | Component specs for the run dialog, the role gating and the preview shape; a `@WebMvcTest` per role over the thirteen overrides | M | Low. Highest value per hour of anything here |
| 22 | The Runs tab shows `bucket/key` as text; the object browser accepts `?bucket=&prefix=` and the jobs screen already links that way | A run's output is one click away | Never wired | `routerLink="/objects"` with query params on the Output cell | S | Low |

---

## 3. Solution detail

### 3.1 The run dialog (#1, #12)

**What changes.** A new `features/tools/query-engine/query-run-dialog.ts`, built on the same
`FormDialog` + `Field` pair as the three existing dialogs. Three controls: `outputBucket` (a select
populated from `StorageService.buckets()`, required), `outputPrefix` (text, optional),
`outputFileName` (text, required, defaulted to the old app's sanitisation --
`query.queryName.replace(/[^a-zA-Z0-9_-]+/g, '_') + '_export'`, from
`query-engine.component.ts:414`). `query-engine.ts`'s `runQuery` becomes an `openRunDialog` that
posts all four fields on confirm and keeps the existing success path -- switch to the Runs tab and
reload (`query-engine.ts:193`).

The bucket list is loaded once, in `loadAll`, not per dialog: the schedule dialog needs the same list
(#12) and two dialogs each fetching it is two requests for one answer. Its failure must be
distinguishable -- an empty select with no explanation is what the old app shipped, because
`loadBuckets` swallowed its error (`query-engine.component.ts:100`).

**Why this rather than the alternative.** The obvious cheaper fix is to make the server default the
destination: if `outputBucket` is absent, fall back to the tenant's first bucket and a generated file
name. It is one method in `QueryExecutionServiceImpl` and it would make Run now work today. It was
rejected for three reasons. It writes a file to a location the user did not choose and cannot
predict, which is worse than an error. It makes the manual path silently different from the
scheduled path, where the destination is explicit and mandatory. And it moves a UI decision into the
service, so the next client to call `execute` inherits a default it did not ask for. The dialog is
maybe forty more lines and it is the shape the feature was designed with.

A second alternative -- reuse the schedule dialog with the interval hidden -- was rejected because
the two differ in the field that matters: a schedule takes a **template** with `{date}` in it, a run
takes a literal name. Merging them would mean explaining templating to somebody running a query once.

### 3.2 Fetching the SQL before editing (#2, #4)

**What changes.** `editQuery(query)` in `query-engine.ts:161-164` currently passes the list row
straight into `QueryDialog`. It becomes a GET of `queryEngine.json/queries/fetchById?queryId=…`
whose detail row -- which carries the decrypted `queryText` and the `version`
(`QueryDefinitionServiceImpl.java:359-363`, `:341-357`) -- is what opens the dialog. The dialog's
form gains a `version` control seeded from that row and sent on update, so the check at
`QueryDefinitionServiceImpl.java:144-146` starts firing. Its refusal message is already written for a
human ("This query was changed by someone else since you opened it -- reload and try again") and
should be surfaced as-is.

The row's SQL preview line (`query-engine.html:73-75`) and the "Search name or SQL" placeholder
(`:56`) have to be reconciled with a list that carries no SQL. Two honest options: drop the SQL line
and change the placeholder to "Search name", or widen `toSummaryDto` to include the SQL.

**Why fetch-by-id rather than widening the list DTO.** Widening looks tidier -- one request instead
of two, and the search box would then work as advertised. It was rejected because `query_text` is
encrypted at rest (`QueryDefinitionServiceImpl.java:110`) and the summary/detail split is the reason
a list of fifty queries does not decrypt fifty ciphertexts on every page load, nor put fifty pieces
of somebody's SQL into a response that only needed names. `fetchById` exists precisely for this, the
old app used it (`query-engine.component.ts:287`), and it is a `TENANT_USER` endpoint so nothing is
gated behind it. The row line and the placeholder should therefore lose their claim to SQL rather
than the DTO gaining one.

### 3.3 The preview row shape (#3)

**What changes.** `types.ts:60-64` becomes `rows: Record<string, unknown>[]`, and the dialog's inner
loop becomes `@for (col of p.columns; track col) { <td>{{ row[col] }}</td> }` -- the old app's shape
(`query-engine.component.html:424-426`), which is also the only shape that keeps cells aligned to
their headers when a driver returns columns in a different order.

**Why not change the server.** Returning `List<List<Object>>` would be smaller on the wire and would
make the current client work untouched. Rejected: `QueryPreviewResponseDto` is a public response
shape, the old app consumes it as objects and is still live, and the response is capped at 100 rows
so the wire saving is worth nothing. The client is wrong; fix the client.

### 3.4 The delete cascade (#6)

**What changes.** `QueryDefinitionServiceImpl.deleteQuery` (`:159-174`) currently sets the query's
status and returns. It gains a lookup of that query's non-deleted schedules and soft-deletes them in
the same transaction. This needs a `findByQueryIdAndStatusNot` on `QueryScheduleRepository` (or a
reuse of the existing `findByStatusNotOrderByScheduleIdDesc` filtered in memory, which is worse) and
a service-level test alongside the existing eight in
`QueryScheduleServiceImplTenantIsolationTest`.

**Why cascade rather than filter at the cron.** The alternative is to leave `deleteQuery` alone and
teach `executeForSchedule` to skip a query whose status is `Delete` -- three lines, no repository
change. It was rejected because it leaves the data lying: `findDueSchedules` keeps returning the row
every sixty seconds forever, the schedule keeps appearing wherever schedules are listed, and the next
person to read `query_schedule` sees an active schedule for a query that no longer exists. Cascading
makes the delete mean what the confirmation already says it means. The cron guard is worth adding
**as well**, cheaply, as a belt-and-braces against any other path that soft-deletes a query.

### 3.5 The eight contract mismatches (#7--#11, #14, #15, #22)

These share one cause and should be done as one piece of work, because doing them one at a time costs
eight reviews of the same three files. Each is a line or two:

- **#7** -- rewrite the confirm body to state the server's rule
  (`ConnectionProfileServiceImpl.java:136-138`). When `dependents > 0` the honest dialog is not a
  destructive confirm at all but an explanatory one with a single Close button, since the answer is
  already known before the request is sent.
- **#8** -- hint and placeholder become JSON; add a `JSON.parse` check in the dialog; and make
  `ConnectionProfileServiceImpl.validate` reject an unparseable `additionalProperties` on save. That
  last part matters more than the hint: today `DatabaseConnectionFactory.mergeAdditionalProperties`
  catches, logs at WARN and continues (`:73-75`), so a mistyped `sslmode` is a silently unencrypted
  connection.
- **#9, #10, #11** -- literal edits to `query-schedule-dialog.ts:52`, `:84`, `:87` and
  `db-connection-dialog.ts:123`.
- **#14** -- four error signals in `query-engine.ts` instead of one, wired to the three
  `TableShell` instances. The schedules load is the odd one: it feeds a *column*, not a table, so its
  failure should render as `schedule unknown` in that column rather than as a table-level error.
- **#15** -- the cleanest fix is a `truncated` boolean on `QueryExecutionDto` set by the runner,
  because sniffing the message prefix in the client is a string comparison that breaks the next time
  the wording changes.
- **#22** -- a `routerLink` on the Output cell, matching `features/jobs/jobs.html:317-323`.

**Why not just leave the hints.** Because two of them are not cosmetic. `{timestamp}` produces the
exact failure the hint warns about -- silent overwriting -- and `key=value` in the properties box
produces a connection without the TLS setting the operator thought they had configured. Wrong hints
on fields with silent failure modes are more dangerous than no hints.

### 3.6 Platform-admin scoping (#18)

**What changes.** `QueryDefinitionDto` and `DatabaseConnectionProfileDto` gain a `tenantName`,
resolved the same way `createdByName` already is. `query-engine.html` renders a Tenant column on both
tables when `auth.isPlatformAdmin()`. The New connection / New query buttons gain a second condition
alongside `canManageQueries()` -- that the session has a tenant -- so a platform admin is not offered
a create the service will refuse (`ConnectionProfileServiceImpl.java:81-83`).

**Why show the tenant rather than hide the rows.** The alternative is to scope a platform admin's
list to nothing, or to make it choose a tenant first. Rejected: the filter is disabled for platform
admins deliberately and consistently across the whole application
(`TenantFilterHelper.java:28-33`), and the existing tests assert that a platform admin **can** read
any tenant's profile (`ConnectionProfileServiceImplTenantIsolationTest`, "platformAdminCanFetchAnyTenantsConnectionProfile").
Changing that here would make this one screen disagree with the rest of the system. Labelling the
rows costs a column and removes the actual hazard, which is not seeing them -- it is not knowing
whose they are while a Delete sits in the row menu.

### 3.7 Tests (#21)

Three groups, in value order:

1. **A `@WebMvcTest` over `QueryEngineRestApi`**, one case per role per endpoint group, asserting
   that the thirteen `TENANT_USER` overrides admit a tenant user and the nine class-level methods do
   not. This is the layer with the most load-bearing logic and the least coverage: `@PreAuthorize` is
   not repeatable, so every one of those thirteen replaces the class rule, and a single deleted
   annotation would silently promote an endpoint to admin-only or demote it to user-visible with
   nothing failing.
2. **Component specs for the new run dialog** -- that it will not submit without a bucket, that the
   file name defaults from the query name, and that it posts all four fields.
3. **A spec for the role gating** -- that a `TENANT_USER` session renders Run now and renders no
   Edit / Schedule / Delete, and that a `TENANT_ADMIN` session renders all of them. This is the one
   claim the whole new design rests on and `app.routes.spec.ts:36-43` only tests the routing half of
   it.

The service layer already has 49 tests and needs two more: the delete-cascade (#6) and, if Q2 is
answered yes, the `Inactive` refusal (#17).

---

## 4. Ordering

**First, and in parallel -- the two blockers.** #1 (run dialog) and #2 (fetch SQL before editing) are
independent of each other and of everything else. Nothing else on this list matters while the
screen's two verbs are broken. #1 brings the shared bucket list, which #12 then consumes for free.

**Second -- what #2 unblocks.** #4 (version / optimistic locking) cannot be done before #2, because
the version has to arrive on the same detail row as the SQL. Do them together.

**Third -- the server-side correctness fix.** #6 (delete cascade) is independent of all frontend work
and should go in early, because it is the only item on this list that is actively wrong in production
data rather than on a screen: a query somebody deleted last week is still writing files.

**Fourth -- the contract sweep.** #7--#11, #14, #15 and #22 as one change across three dialog files
and `query-engine.ts`. #3 (preview shape) belongs in the same sweep -- it is one file, and doing it
alongside #2 means the query dialog is opened and reviewed once.

**Fifth -- restored and disclosed.** #13 (the status filter) and #16 (say the 50-run cap out loud).
Both are toolbar-and-label work, both are safe, and both stop the Runs tab misleading an operator.

**Sixth -- scoping and tests.** #18 (platform-admin tenant column) needs two DTO changes and so is a
backend-plus-frontend item; #21 (tests) should be written against the behaviour as it ends up, not
as it starts, so it goes last of the code work -- with the exception of the `@WebMvcTest`, which
tests annotations nothing in this list changes and can be written on day one by anyone blocked.

**Not gated on any of the above, and not ours alone.** #20 (the baseline migration) blocks nothing on
this screen but blocks every fresh stage or prod build. It should be raised as its own piece of work
covering all the tables in the same position, not just these four.

**Decisions before code.** #17 and #19 must not be implemented until §6 Q1 and Q2 are answered.
Both change behaviour for somebody who is relying on today's behaviour.

---

## 5. Out of scope

**Making execution asynchronous, and cancelling a run.** `execute` is synchronous and holds the HTTP
request for up to the 300-second statement timeout (`QueryExecutionRunner.java:112-113`).
`QueryExecutionStatus.CANCELLED` exists and nothing can produce it. Making runs async would change
the run dialog's contract from "here is your result" to "here is your run id, watch the Runs tab",
which means polling or a WebSocket topic, a new status transition, and a rewrite of the success path.
That is a feature, not a repair, and this pass is a repair.

**A second database engine.** `DatabaseType` has one value and
`DatabaseConnectionFactory.openConnection` throws for anything else (`:35-39`). Adding one means a
driver, a URL builder, and a preview wrapper that is not PostgreSQL's `LIMIT` syntax
(`QueryDefinitionServiceImpl.java:251-252`). The Connections tab's dropped type filter (#13) is
deliberately deferred to that work, because a filter over one value is furniture.

**Output formats other than CSV.** `CsvExportService` is the only exporter and `.csv` is appended
unconditionally (`QueryExecutionRunner.java:119-121`). No user need has been recorded.

**Notifying anyone when a scheduled run fails.** It is recorded and logged
(`ProcessCron.java:100-101`) and visible in the Runs tab. A `Notification` entity exists elsewhere in
the system. Wiring it is a cross-feature decision about what this platform notifies on, not a
Query Engine decision.

**Server-side paging of run history.** #16 discloses the 50-row cap; raising or paging it needs a
page parameter on `executions/fetchAll`, a total count, and pagination on the tab. Worth doing, worth
doing after the blockers.

**Any change to the old Angular 8 screens.** `scheduler1/src/app/_component/setting/query-engine/`
and `.../search-engine/` are being retired with the old app. Two real defects live there -- the
route carrying `AuthGuard` alone so a tenant user sees write controls that all 403
(`app.routing.ts:163-168`), and Validate validating the stored SQL rather than the edited SQL
(`query-engine.component.ts:317-319` against `QueryDefinitionServiceImpl.java:297-307`) -- and both
are recorded in the grooming document so that nobody rediscovers them. Neither should be fixed. Any
hour spent in Angular 8 here is an hour not spent on the screen that survives.

**Saving a query from the Search Engine.** By design: that is the Query Engine. Recorded so the
absence reads as a decision.

---

## 6. Open questions

### Q1. Should `dynamicQueryResponse` run its SQL through `QueryValidator`?

Today it does not. `SettingServiceImpl` checks the role twice, then
`QueryService.executeQueryResponse` calls `createNativeQuery` on the string as given
(`QueryService.java:58-63`). The only SELECT check anywhere is the client-side regex in
`search-engine.ts:16-18`, which `curl` skips. Discovery files this as risk 15. Meanwhile
`QueryValidator` is applied on five separate Query Engine paths in the same codebase.

- **(a) Leave it.** It is `PLATFORM_ADMIN` at three layers; that role can already do anything.
- **(b) Apply `QueryValidator`.** The screen calls itself read-only, the parser exists, and the
  change is a handful of lines.
- **(c) Apply it with a documented break-glass** -- a second endpoint or a flag for the case where a
  platform admin genuinely needs to run DML.

**Recommendation: (b).** The argument for (a) -- "that role can already do anything" -- is true of the
role and false of the endpoint. A platform admin who wants to run DML has database access; what this
endpoint adds is a path from a stolen or borrowed browser session to arbitrary writes, with no audit
beyond a log line. (b) closes that at the cost of rejecting queries somebody may be running today,
which is why it needs an answer from a person rather than a commit: the honest risk is that a
platform admin has been using this box for maintenance DML and will find it stops working. (c) is
worse than both -- it is (a) with more code and a false sense of having done something. If (b) breaks
somebody's workflow, that is exactly the workflow that should have been visible.

### Q2. Should `Inactive` be honoured on a query and on a connection, or removed from the dialogs?

Both new dialogs offer the select and the server stores it; nothing reads it. Only a schedule's
status has an effect (`QueryScheduleRepository.java:19-20`).

- **(a) Honour it** -- `execute` and `executeForSchedule` refuse an `Inactive` query or an `Inactive`
  connection.
- **(b) Remove the select** from both dialogs and leave `Delete` as the only meaningful non-Active
  status.

**Recommendation: (a).** An admin who sets a connection to Inactive means "stop using this" -- most
plausibly because it is being decommissioned or its credentials are being rotated -- and today the
system keeps dialling it. The risk is real and belongs in the answer: anybody who set the flag while
it was inert will find their query stops running, so this cannot ship quietly. It wants a release
note and a one-off query to find rows currently `Inactive` before the change lands. (b) is the safe
answer and the wrong one: it removes a control people have already used to express an intention,
rather than starting to respect it.

### Q3. Should the run dialog remember its destination?

The old app defaulted the file name from the query name and left bucket and prefix empty every time
(`query-engine.component.ts:409-416`). Somebody running the same export weekly re-picks the same
bucket weekly.

- **(a) Match the old app** -- defaults from the query name, nothing remembered.
- **(b) Pre-fill from the query's schedule** when it has one, since that is a destination somebody has
  already chosen for this exact query.
- **(c) Persist the last-used destination per query** in `localStorage`.
- **(d) Store a default destination on `query_definition`** -- new columns, and it is genuinely
  shared rather than per-browser.

**Recommendation: (b), falling back to (a).** It needs no storage, no schema and no new state: the
schedule row is already loaded on the page (`query-engine.ts:106`) and its bucket, prefix and template
are the best available guess at where this query's output belongs. (c) makes one person's browser the
source of truth for a shared query and produces different behaviour for two admins on the same team.
(d) is the right answer if this becomes a recurring complaint, and is three columns and a migration
too many for a repair pass.

### Q4. Who owns the missing baseline migration (#20)?

No Liquibase changeset creates the four Query Engine tables; they exist only because dev runs
`ddl-auto=update`, while stage and prod run `validate` and Liquibase runs first -- so V14's
`ALTER TABLE query_definition ADD CONSTRAINT` has nothing to alter on a fresh database.

- **(a) This feature writes a baseline for its own four tables.**
- **(b) A separate piece of work audits every entity against the changelog and writes one baseline
  for all of them.**

**Recommendation: (b), with this feature contributing the four table definitions.** Writing a
baseline for four tables while an unknown number of others are in the same state produces a database
that fails at a different `ALTER` instead of this one, which is not a fix -- it is a moved error
message. The audit is a day's work and is the only version that ends with a fresh prod database that
builds. This feature should hand over the four `CREATE TABLE` statements, taken from
`DatabaseConnectionProfile.java`, `QueryDefinition.java`, `QuerySchedule.java` and
`QueryExecution.java`, and let that work sequence them before V14.

### Q5. Should the query list keep claiming to search SQL?

Once #2 is done, Edit works but the list still carries no `queryText`, so the row's SQL line and the
"Search name or SQL" placeholder remain untrue.

- **(a) Drop the SQL line and rename the placeholder to "Search name".**
- **(b) Add `queryText` to `toSummaryDto`** so both work as advertised.

**Recommendation: (a).** (b) means decrypting every saved query on every page load and putting every
query's SQL into a response that only needed names -- the summary/detail split exists precisely to
avoid that, and it is the same instinct that keeps the connection password out of `toDto`
(`ConnectionProfileServiceImpl.java:295`). The row line is a nicety; searching by name is what people
actually do. If searching SQL turns out to matter, the right shape is a server-side search endpoint,
not a wider list.

---

## 8. Resolved, 2026-09-05 -- the feature was removed whole, not repaired

Every open question above is now moot: at the product owner's explicit call, Query Engine and Search
Engine were removed in full rather than fixed -- both frontend apps, the backend, and the database.
This closes Q1-Q5 by removing the thing they were questions about, not by picking an option for any
of them; if either feature is rebuilt later, the options and reasoning above are still the right
starting point (the missing Run dialog destination fields, the Inactive-connection dispatch gap, and
Q4's baseline-migration debt all still describe real gaps in what existed).

**What was removed:**

- **Frontend, `scheduler1/next`** -- `features/tools/query-engine/*` (5 files: `query-engine.ts`/`.html`,
  `query-dialog.ts`, `query-schedule-dialog.ts`, `db-connection-dialog.ts`, `types.ts`) and
  `features/tools/search-engine/*` (2 files), their routes (`/tools/query`, `/tools/search`) and nav
  entries, `AuthService.canManageQueries`, the Query Engine docs bullet, and the matching spec
  assertions in `app.routes.spec.ts`/`auth.guard.spec.ts`/`auth.service.spec.ts`.
- **Frontend, `scheduler1/src` (legacy)** -- the same two screens (`_component/search-engine/`,
  `_component/setting/query-engine/`), `query-engine.service.ts`, `query-engine.model.ts`, both
  routes (`setting/searchEngine`, `setting/queryEngine`), the nav links, and `SettingService`'s
  `dynamicQueryResponse` method -- this legacy app had its own live, separately-routed copies of both
  screens, discovered only once the removal was underway, and had to be removed in the same pass or
  the backend/database change below would have broken it.
- **Backend** -- `QueryEngineRestApi`; the `ConnectionProfileService`/`QueryDefinitionService`/
  `QueryExecutionService`/`QueryScheduleService` interfaces and impls, plus `QueryExecutionRunner`;
  the `DatabaseConnectionProfile`/`QueryDefinition`/`QueryExecution`/`QuerySchedule` entities,
  repositories and DTOs; `DatabaseType`/`QueryExecutionStatus`; the `engine/query/*` helpers
  (`DatabaseConnectionFactory`, `QueryValidator`, `CsvExportService`, `CsvExportResult`); `ItemResponse`
  and `SettingService`/`SettingServiceImpl`/`SettingRestApi`'s `dynamicQueryResponse` (Search Engine's
  only endpoint -- everything else in that shared controller/service stays); `ProcessCron`'s
  `pollDueQuerySchedules` poller (the cron component itself, and its other, unrelated jobs, stay);
  and the 7 tests exclusive to these features. `QueryService` itself -- the generic native-SQL helper
  Dashboard, Source Task listing, the job-queue log search and Report export all also depend on --
  was kept; only its one Search-Engine-only method (`executeQueryResponse`) was removed with the
  rest.
- **Database** -- `database_connection_profile`, `query_definition`, `query_execution` and
  `query_schedule`, dropped via `V27__drop_query_engine.sql` (children before parents, following the
  same `IF EXISTS` pattern as the dynamic-forms drop in `V26`, since none of these four were ever
  Liquibase-created either -- Hibernate `ddl-auto=update` artifacts, consistent with Q4 above). All
  four were confirmed empty in this environment before dropping. Q4's baseline-migration debt is
  moot for these four specifically now; it still stands for whatever other entities share the same
  gap.

**Verified:** backend compiles clean and 530 tests pass (down from 586, the difference being the 7
deleted test files); both frontend apps type-check clean; the `next` app's 468 tests and the legacy
app's production build both pass. Confirmed live: all three services rebuilt and redeployed, the
Liquibase changeset (`27.0-drop-query-engine`) recorded as applied, all four tables gone from the
running database, and both apps' nav menus show neither screen with no console errors on load.
