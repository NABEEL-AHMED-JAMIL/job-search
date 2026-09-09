# Synthesis -- Source Jobs

Decisions for feature `source-jobs`, from
[../grooming/source-jobs.md](../grooming/source-jobs.md). Paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

The jobs screen is the best-built screen in the new application and the one with the most dangerous
defects, and those two facts are connected. The rewrite added live counts, a stalled-run detector, a
notification dialog, an assistant panel, real loading and error states and a genuinely better bulk
path -- and while doing it, quietly dropped a guard the old form had for a reason. The old editor
locked the Execution control once a job existed; the new one does not, and neither the client nor
the server carries the schedule across the change. The result is a job the console describes as
"Manual -- on demand" that goes on firing every night, and a job switched the other way that says
Auto and never runs again. That is the work: **six correctness defects where the form writes
something the server does not honour** -- execution mode (12.1), create state (12.2), end-date
clearing (12.3), weekday codes (12.4), priority range (12.5), and a live-update path whose publisher
was never wired up (12.6). Around them sit two smaller correctness items on the same surface
(Run/Skip offered on Inactive jobs; failed sub-fetches drawn as empty results) and four capabilities
that did not make the crossing at all -- the card view, the `tabActive` gate, the Active/Inactive
filter and the read-only task facts on the editor. Underneath everything, `jobs.ts` and
`job-edit.ts` are 1,028 lines with no test between them, which is why five of the six defects are
the kind a single assertion would have caught. Fix the correctness set first, put tests under it as
it lands, then decide the four migration gaps -- one of which (the card view) is a genuine
"drop it and record that" candidate rather than work.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | Auto→Manual leaves the scheduler row live and the job keeps firing; Manual→Auto creates no scheduler and the job never fires (12.1) | Execution mode and schedule always agree | The editor sends no `schedulers` for Manual, and `updateSourceJob` neither deletes nor creates a scheduler | Give `updateSourceJob` the two missing branches: expire+delete the scheduler when execution is Manual, create one when it is Auto and none exists. Keep the control enabled | M | **High** -- changes what runs |
| 2 | `addSourceJob` hard-codes `Status.Active`; the create form's State control and the clone's "starts inactive" toast are both untrue (12.2) | The State sent on create is honoured | One ignored DTO field | Read `sourceJobDto.getJobStatus()`, default Active when absent, refuse `Delete` | S | Low |
| 3 | Clearing an end date silently does nothing; same for `intervalValue` (12.3) | Clearing clears | `StringUtils.isEmpty` treats null as "leave alone" | Set `endDate` unconditionally on update. Keep the guard on `intervalValue`, which is NOT NULL in effect | S | Low |
| 4 | Weekday chips emit `'1'`..`'7'`; the server understands only `MON`..`SUN`, drops them, and falls back to "every week", discarding the interval too (12.4) | The chips write `MON`..`SUN` | A vocabulary mismatch, invisible because the server drops unknown codes rather than refusing them | Change the chip values to the day codes; make the server **refuse** an unparseable day list; repair existing rows | S (+data) | Medium -- silently wrong schedules already exist |
| 5 | Priority is capped at 9 on the client; a job at 99 or 100 cannot be saved at all (12.5) | 1..9, 99, 100, as the platform defines | The new form invented a narrower range | Replace the number input with a select over the platform list; validate the same list on the server | S | Low |
| 6 | `publishChanged` is called by nothing, so `job.updated` / `job.toggled` / `job.deleted` never arrive; the client handles all three (12.6) | An edit, toggle or delete reaches other viewers | A wired-in-name-only publisher | Call `publishChanged` from update, toggle, delete and add in `SourceJobServiceImpl` | S | Low |
| 7 | Run and Skip are offered on Inactive jobs and refused with "SourceJob not found with jobId." (12.7) | Not offered; and when refused, a message that names the reason | Two missing client guards and one misleading server message | Add the `jobStatus` guards to `jobs.html`; split the server's "not found" into "not found" and "not active" | S | Low |
| 8 | A failed payload or run-history fetch renders as "nothing here" (12.8) | A failure says it failed | Error handlers write the same value as an empty success | Add an error state per panel, as `TableShell` does elsewhere | S | Low |
| 9 | `jobs.ts` (789 lines) and `job-edit.ts` (239) have no spec; no backend test for add/update/run/skip; no E2E for jobs | Tests that fail when the behaviour is removed | Zero coverage on the two largest files in the feature | A spec per gap as it lands, plus a payload-shape spec for the editor and a service test for add/update | M | Low |
| 10 | Card view absent; `ViewToggle` exists and 11 screens use it, including the other two that had it in the old app | Present, or dropped on the record | Unexplained inconsistency | **Drop.** Record the decision. See Q1 | S (as a note) | Low |
| 11 | `tabActive` is sent on every row and read by nothing; History is offered on jobs with no runs | History disabled on a job that has never run | One unread field | Bind it in `jobs.html`, with a tooltip | S | Low |
| 12 | No Active/Inactive filter; the status filter is over run status | Both filters | The state column has no filter | One signal, one select, one clause | S | Low |
| 13 | The editor shows nothing about the task it just bound | Service, topic, partitions, home page, pipeline, payload with copy | Dropped in the rewrite | A read-only block fed by the already-loaded task, plus one payload fetch on selection | S | Low |
| 14 | Weekly refuses to save with no day selected | Allowed -- "every N weeks from the start date" | A client-only rule the server contradicts | Delete the check in `save()`; make the summary say what it does | S | Low |
| 15 | Day of month offers 1..31; "Last day" (`0`) is implemented server-side and unreachable | "Last day" offered | Dropped option | One option in the select | S | Low |
| 16 | List is `jobId` ascending; a new job lands on the last page | Newest first | Ordering not carried over | Reverse in `listSourceJob` (`Sort.Direction.DESC`) | S | Low |
| 17 | Interval accepts any number ≥ 1, including values that make the schedule expire on save; nothing validates it anywhere | A bounded, positive integer | No validation at any layer | Client `min`/`max` per frequency; server refuses non-numeric and `< 1` | S | Low |
| 18 | Search covers three fields, substring only; the old app had `field:term`, quoted phrases and `-negation` | Parity, ideally shared | A narrower search | **Defer.** Belongs in `shared/ui` across all list screens, not in this feature. See Q2 | M | Low |
| 19 | `assigned_user_id` decides email recipients and My Activity; neither frontend has ever set it; `validateAssignee` is written and unused | A job can be reassigned | Never built, in either app | **Defer** pending Q4 | M | Medium -- changes who gets alerted |
| 20 | `SettingServiceImpl` writes `UPPER(job_status)` via `statusChangeSourceJobLinkWithSourceTaskTypeId`, corrupting jobs so they vanish from the list and stop running (12.9) | Editing a task type does not break jobs | Pre-existing platform defect | **Out of scope here** -- it belongs to `platform-configuration`, which owns both callers. Flag it | S | High if left |

---

## 3. Solution detail

### Row 1 -- make execution mode and schedule agree

**What changes.** `process/src/main/java/process/model/service/impl/SourceJobServiceImpl.java`,
`updateSourceJob` (`:183-259`), and `SchedulerRepository`.

Today the scheduler branch (`:234-255`) runs only when `schedulers` is non-empty, and inside it
only when a row already exists. Two branches are missing:

- `execution == Manual` on save: find the scheduler by job id and **delete it**. The job's runs are
  in `job_queue` and survive; the `scheduler` row is the timetable, and a manual job has none.
- `execution == Auto` with `schedulers` given but no existing row: **create one**, exactly as
  `addSourceJob:158-177` does, `applyInitialSchedule` included.

Add `deleteByJobId` to `SchedulerRepository` (it currently exposes only
`findSchedulerByJobId`, `findByJobIdIn` and `findDueSchedulers`). The FK
`fk_scheduler_source_job` points from `scheduler` to `source_job`, so deleting the child is safe.

**Why this rather than the alternatives.**

*Rejected: restore the old lock -- disable Execution in edit mode, as `job.component.ts:231-234`
did.* It is one line and it closes the hole immediately, which is genuinely tempting. It was
rejected because it does not fix the feature, it removes it: the only way to turn a nightly job into
an on-demand one becomes "delete it and build it again", losing the job id that every run in
`job_queue`, every audit line and every report row is keyed on. The old app's lock was a workaround
for a server that could not do the transition, and the rewrite's authors were right to want it gone
-- they were wrong only to remove it before the server could.

*Rejected: set `expired = true` instead of deleting the scheduler row.* Cheaper, and
`findDueSchedulers` filters on `expired = false`, so it stops the job firing. But `expired` already
means something specific -- "this recurring job passed its end date", per V15's own header -- and
`SchedulerDto.expired` drives the "Expired — no further runs" note in the list
(`jobs.ts:541`). Overloading it would make a Manual job report an expired schedule it never had.
Delete is the honest state.

*Rejected: add `and source_job.execution = 'Auto'` to `findDueSchedulers` and leave the row.* This
is the smallest possible change and it does stop the wrong runs. It was rejected because it leaves a
stale scheduler row behind: switching back to Auto would silently resurrect a timetable the user
last saw months ago, and `skipNextSourceJob` -- which only checks that a scheduler exists
(`:372-376`) -- would keep operating on it. **The query should get the condition anyway**, as
defence in depth, but it is not the fix.

**Risk.** This changes what runs. It needs the Manual→Auto and Auto→Manual acceptance criteria
(#19, #20) verified against a live stack, not fixtures.

### Row 2 -- honour the State sent on create

`addSourceJob:148` becomes a read of `sourceJobDto.getJobStatus()`, defaulting to `Status.Active`
when null and refusing `Status.Delete` with a named error. That keeps every existing caller working
-- the old form never sent a status on create, and `SourceJobBulkServiceImpl:226` sets Active
directly on the entity and does not go through this method.

It also makes `Jobs.clone` honest: `jobs.ts:449` already sends `Inactive` and already tells the user
so. Nothing on the client changes.

*Rejected: change the clone toast instead.* Cheaper, and it would stop the console lying. But the
clone's reasoning is right -- copying a live nightly schedule should not silently double the runs --
and the create form offers the control regardless. Fixing the message would leave two callers still
unable to do the thing the API appears to offer.

### Row 3 -- let an end date be cleared

`updateSourceJob:240-242`: drop the `StringUtils.isEmpty` guard around `setEndDate` and set it
unconditionally. Keep the guard on `intervalValue` at `:245-247`: an interval of null makes
`computeNextRun` return null immediately (`ProcessTimeUtil.java:220-222`), so a caller that omits it
would expire the schedule -- the guard there is doing real work.

*Rejected: a `clearEndDate` boolean on the DTO.* It distinguishes "not sent" from "sent as null",
which is the correct general answer for a partial-update API. Rejected because `updateSourceJob` is
not a partial update -- it replaces the whole job, which is exactly why `NotifyDialog` has to read
the record back before changing three checkboxes (`notify-dialog.ts:91-125`). Adding
tri-state semantics to one field of a full-replacement endpoint would make it less predictable, not
more.

### Row 4 -- one weekday vocabulary

`features/jobs/edit/job-edit.ts:20-24` changes to `MON`…`SUN`, matching
`ProcessTimeUtil.DAY_CODE_MAP` (`:32-41`), `global-config.ts:50-58` in the old app and the
`days_of_week` values already in the column. The labels are already `Mon`…`Sun`, so the template
does not change.

Then make the failure loud. `parseDaysOfWeek` (`:203-210`) drops unknown codes and every caller
treats the empty result as "no day rule", which is why this ran for as long as it did without anyone
noticing. Validate `daysOfWeek` in `addSourceJob` and `updateSourceJob`: if the string is non-empty
and parses to an empty set, return `ERROR` naming the codes it could not read. The tolerant parse
stays where it is -- `ProcessTimeUtil` is called from the cron, and a bad row already in the database
must not take a dispatch pass down with it.

**Data.** Any schedule written by the new form holds digits. Before deploying the fix:

```sql
select scheduler_id, job_id, frequency, interval_value, days_of_week
from scheduler where days_of_week ~ '[0-9]';
```

Translate `1`→`MON` … `7`→`SUN`, which is what the form's own labels meant
(`job-edit.ts:20-24`). Every one of those jobs has been running weekly from its start date rather
than on the chosen days, so the repair changes when they fire -- it needs to be a decision somebody
makes with the list in front of them, not a blind `UPDATE` in a changeset.

*Rejected: teach `DAY_CODE_MAP` the digits as aliases.* One line, no data migration, nothing breaks.
Rejected because it makes the column bilingual for ever: `days_of_week` would then hold `MON,THU` in
rows written by the old app and the bulk importer and `1,4` in rows written by the new form, and
every future reader -- a report, an export, a support query -- has to know both. The mismatch is a
mistake in one file; it should be fixed in that file.

### Row 5 -- priority

Replace the number input (`job-edit.html:46-50`) with a select over `[1..9, 99, 100]`, which is what
`ProcessTimeUtil.priority` (`:26-27`) defines, the old form offered (`global-config.ts:1`) and the
bulk template still offers (`SourceJobBulkServiceImpl.java:81`). Validate the same list in
`addSourceJob` and `updateSourceJob`, where today nothing is checked at all.

*Rejected: widen `Validators.max(9)` to `100`.* Two characters. Rejected because it makes 10 through
98 look valid when they are not part of the platform's vocabulary, and the dispatcher orders by this
column -- 99 and 100 are sentinels, not "very high". A select says that; a range does not.

### Row 6 -- publish the change events

`SourceJobServiceImpl` already holds `JobEventPublisher` (`:49, :68, :82`) and never uses it. Call
`publishChanged(tenantId, jobId, type)` at the end of `updateSourceJob` (`job.updated`),
`toggleSourceJobStatus` (`job.toggled`), `deleteSourceJob` (`job.deleted`) and `addSourceJob`
(`job.updated`, so `Jobs.refreshOne` adds the row -- it already handles an unknown id,
`jobs.ts:324-326`).

`publishChanged` swallows its own failures (`JobEventPublisher.java:88-91`), so a push nobody
receives cannot fail the write that triggered it.

Then reconcile `JobEvent`'s union with reality (`core/socket/job-events.service.ts:9`): it names
`job.log` -- which nothing consumes -- and omits `job.updated`, which `jobs.ts` handles. The
`| string` widening hides both from the compiler.

*Rejected: drop the three event types and the client handlers that service them.* Defensible -- less
code, and the reconnect-gap reload (`jobs.ts:270-281`) already covers the case where a viewer misses
something. Rejected because the screen advertises itself as Live, and "live" that misses a
deactivation until someone presses Refresh is worse than a screen that never claimed it. The
publisher exists, the handlers exist, and the wiring is four lines.

### Row 7 -- do not offer what will be refused, and say why when refusing

Client: add `job.jobStatus !== 'Active'` to the disabled conditions on Run now and Skip next run
(`jobs.html:230-235`), with a title naming the state -- the old screen's `canRunJob` / `canSkipJob`
(`source-job.component.ts:200-215`) is the reference.

Server: `runSourceJob:344-346` and `skipNextSourceJob:363-365` both answer "SourceJob not found with
jobId." for a job that exists and is switched off. Look the job up by id first, refuse an
unowned one as not-found, and refuse an owned-but-inactive one as "This job is not active." The
distinction is safe: it is only made *after* ownership has been established, so it leaks nothing
across a tenant boundary.

While in there, add `Start` to the in-flight refusal at `:347-350` and `:366-368`. The client's
`IN_FLIGHT` already includes it (`stalled.ts:14`); the API does not.

### Row 8 -- a failed fetch is not an empty one

`loadPayload`'s error handler writes `''` (`jobs.ts:370`) and `loadRuns`'s writes `[]` (`:419`), and
both values are what the template reads as "there is nothing here"
(`jobs.html:371-372`, `:402-405`). Give each panel a third state -- a signal holding the failed
task/job ids is enough -- and render a short message with a retry, the way `TableShell` does for the
list itself.

### Row 9 -- tests

Not a phase at the end; one spec per gap, landing with it.

| Test | Catches |
|---|---|
| `job-edit.spec.ts`: the payload for an Auto→Manual save, and for Manual→Auto | Row 1, client half |
| `SourceJobServiceImplScheduleTest`: update with Manual removes the scheduler; update with Auto and no existing row creates one | Row 1, server half |
| `SourceJobServiceImplTest`: `addSourceJob` honours an Inactive status; defaults to Active when absent | Row 2 |
| the same: update with a null `endDate` clears it | Row 3 |
| `job-edit.spec.ts`: the emitted `daysOfWeek` parses to a non-empty set under the day codes | Row 4 |
| `SourceJobServiceImplTest`: a `daysOfWeek` of `"1,4"` is refused | Row 4, server half |
| `job-edit.spec.ts`: a job loaded at priority 99 produces a valid form | Row 5 |
| `SourceJobServiceImplTest` with a mocked publisher: update/toggle/delete each publish once | Row 6 |
| `jobs.spec.ts`: Run and Skip disabled on an Inactive fixture, enabled on an Active one | Row 7 |

The existing `SourceJobServiceImplTenantIsolationTest` is the right shape to extend -- it already
builds the cross-tenant fixtures and drives `TenantContext`.

### Rows 11, 12, 13, 14, 15, 16 -- the small restorations

Each is contained enough not to need its own argument:

- **11** `[disabled]="job.tabActive === false"` on the Run-history menu item, plus a tooltip. The
  field is already on every row (`SourceJobServiceImpl.java:500`).
- **12** A `stateFilter` signal, a `<select>` beside the existing two, one clause in `filtered()`
  (`jobs.ts:194-206`).
- **13** A read-only block on the editor fed by the selected task from `listSourceTask`, plus one
  `fetchSourceTaskWithSourceTaskId` on selection for the payload. Use `shared/ui/topic.ts` to split
  `queueTopicPartition`, as the list already does (`jobs.ts:757-760`).
- **14** Delete the weekly-days check at `job-edit.ts:192-195` and let the summary say "every N weeks
  from the start date" when no day is picked.
- **15** A `{ value: 0, label: 'Last day' }` option ahead of 1..31 (`job-edit.ts:48`). The backend
  reads `<= 0` as the last day (`ProcessTimeUtil.java:196-197, 268`).
- **16** `Sort.by(DESC, "jobId")` in `listSourceJob` (`SourceJobServiceImpl.java:484-485`).
  Server-side rather than a `.reverse()` on the client, so the bulk export and any future paged
  version agree with the screen.

### Row 17 -- bound the interval

Client: `min` and `max` per frequency, following `FREQUENCY_DETAIL` (`global-config.ts:22-43`) as
guidance rather than as a closed set -- the old app's select was more restrictive than the backend
needs. Server: refuse a non-numeric or `< 1` `intervalValue` in `addSourceJob` and
`updateSourceJob`. Today `stepFunction` does `Long.parseLong` unguarded (`ProcessTimeUtil.java:79`)
inside a cron pass, and an interval of `0` walks every guard in `resolveInitialNextRun` and
`computeNextRun` before the schedule quietly ends up expired.

*Rejected: restore the old per-frequency select.* It is the safest control and it is what the old
app had. Rejected because it is genuinely too narrow -- "every 7 days" was not offerable in the old
UI, and the backend has always supported it. A bounded number input keeps the flexibility and closes
the actual hole, which is the absence of any server-side check.

---

## 4. Ordering

**First, and blocking everything else: rows 1, 2, 3, 4, 5 -- the six correctness defects.** They
share `SourceJobServiceImpl.updateSourceJob` and `job-edit.ts`, and touching those files twice is
how a conflict gets resolved by picking one side. Within the group, order by blast radius:

1. **Row 4** (weekday codes) and its data repair. It is the only one with rows already wrong in the
   database, and every day it stays wrong adds more. The repair query has to be run before the code
   change, not after.
2. **Row 1** (execution mode). The largest behaviour change and the one that needs a live stack to
   verify. Everything else in `updateSourceJob` should land on top of it, not underneath.
3. **Rows 2, 3, 5** (create state, end date, priority). Small, independent, same two files.
4. **Row 9's specs for each**, landing with the fix rather than after it.

**Second: rows 6, 7, 8** -- the socket wiring, the guards and the error states. Independent of each
other and of the first group; safe to parallelise.

**Third: rows 11–16** -- the restorations. Purely additive, none blocks anything, each is an hour or
two. Row 13 (task facts on the editor) is the one users will notice; do it first of the six.

**Row 17** rides along with whichever of rows 1–5 touches the schedule validation.

**Unblocks.** Row 1 unblocks any honest QA of this feature at all: until it lands, "does this job
run when it should" has no stable answer, which makes `job-runs-and-queue`, `dashboard` and
`reports` unverifiable end to end -- all three read `JobQueue` rows that a mis-scheduled job
produces. Row 4 unblocks the same question for weekly schedules specifically. Row 6 unblocks the
Live claim on the list, and with it any QA criterion phrased as "without reloading".

**Not in this feature's order at all, but urgent:** row 20 -- `UPPER(job_status)` in
`SourceJobRepository:57-60`, whose two callers are in `SettingServiceImpl` (`:329`, `:354`). A job
corrupted by it disappears from `listSourceJob` and from `findDueSchedulers` at the same moment.
Whoever grooms `platform-configuration` owns it; this document names it so it is not lost between
the two.

---

## 5. Out of scope

**The whole of `job-runs-and-queue` (feature 4).** Run history, the logs screen, the queue screen
and `fetchSourceJobQueueListWithJobId`'s own consumers. This feature calls that endpoint for the
expanded row's bars and stops there.

**The job assistant (feature 5).** `jobs.ts` opens the panel and passes a job id; the panel's
behaviour, its intents and its refusals are that feature's.

**Bulk import/export (feature 7).** `SourceJobBulkServiceImpl` is a second, independent path that
creates jobs and schedulers -- and it hard-codes `Status.Active` (`:226`) and `Execution.Auto`
(`:234`), which is fine for a template-driven import and would be wrong to change here without
groomed requirements for that feature.

**The `UPPER(job_status)` corruption (row 20).** Real, dangerous, and owned by
`platform-configuration`, which holds both callers. Fixing it from here means editing a repository
method two other services depend on, with no test for either of them.

**The Liquibase / Hibernate table-ownership problem.** `source_job` and `scheduler` have no creation
path outside development (`discovery/database.md:550-556`). It affects every feature equally and is
an infrastructure decision, not a jobs one.

**Deep field-aware search (row 18).** The old `SearchFilterPipe` is worth having back, but as a
shared helper across all nineteen list screens. Doing it inside this feature would either produce a
jobs-only implementation that the next screen copies, or a shared one that lands with no
cross-screen testing.

**Reassigning a job (row 19).** Deferred, not dropped -- see Q4.

**The card view (row 10).** Recommended for a decision, not for work -- see Q1.

**Anything about who may do what.** The four authorization layers agree today, and the grooming
document's section 8 says so with evidence. `TENANT_USER` having the same reach as `TENANT_ADMIN`
over jobs is a design position, not a defect, and changing it is a product decision affecting every
existing tenant -- see Q3.

---

## 6. Open questions

**Q1 -- Does the jobs list get its card view back?**
Of the three old screens with a table/card toggle, `tasks` and `ai/agents` kept it and `jobs` did
not; `shared/ui/view-toggle.ts` exists and thirteen files reference it, so restoring it is a card
template and one import.
*Options:* (a) restore it, half a day; (b) drop it and record the decision; (c) leave it undecided,
which is where it is now.
**Recommendation: (b), drop it.** The jobs table carries thirteen columns including live run status,
stalled state, next and last run, and both author columns -- the old card layout showed six fields
and no run status, and the new expandable row does everything the card was reaching for and more.
Restoring it would mean maintaining a second, poorer view of the screen people watch. Record it in
`discovery/features.md` §2.6 as a deliberate drop so the inconsistency stops reading as an
oversight.

**Q2 -- Where does field-aware search live?**
The old `SearchFilterPipe` supported `field.path:term`, quoted phrases and `-negation` over the whole
object graph; nineteen new list screens have a substring match over two or three fields.
*Options:* (a) port it into `jobs.ts` now; (b) build it as a shared `shared/ui/search-query.ts` and
adopt it screen by screen; (c) leave the simple search everywhere.
**Recommendation: (b), as its own piece of work, not inside this feature.** The old pipe's real value
was that one syntax worked everywhere; a jobs-only copy loses that and guarantees a second
implementation later. Raise it as a cross-cutting item once the correctness set is done.

**Q3 -- Should a `TENANT_USER` be able to delete a job created by its `TENANT_ADMIN`?**
Today it can: `SourceJobRestApi` is `TENANT_USER` at class level with no method-level override, and
no write path checks the row's author or assignee at any of the four layers.
*Options:* (a) leave it -- a job is shared operational work within a tenant; (b) put
`@PreAuthorize("hasRole('TENANT_ADMIN')")` on `addSourceJob`, `updateSourceJob` and
`deleteSourceJob`, leaving run and skip open; (c) an ownership rule -- creator or assignee or a
tenant admin.
**Recommendation: (a), leave it, and write it down.** It is the current behaviour of both
applications, changing it would lock existing users out of jobs they use daily, and the sibling
asymmetry people notice -- tasks are admin-only -- is defensible: a task defines what runs against
the platform's Kafka topics, a job only says when. If it is revisited, (c) is the right shape and
(b) is not: run and skip are the operations that actually cost something, and (b) leaves both open
while blocking a rename.

**Q4 -- Do jobs become reassignable?**
`assigned_user_id` decides who receives the completion, failure and skip emails and whose "My
activity" the job appears in. `validateAssignee` (`SourceJobServiceImpl.java:513-526`) is written and
correct, and **no frontend has ever sent the field** -- so a job belongs permanently to whoever
created it, while the new list *displays* "Assigned to" and the notification sentence names the
assignee.
*Options:* (a) add a user picker to the edit form, tenant admins only; (b) add it for everyone; (c)
leave it and remove "Assigned to" from the panel so the console stops showing an unchangeable field.
**Recommendation: (a), in a later pass.** The server side is done and tested-by-construction, the
notification machinery already exists (`notifyTaskAssigned`, `:92-102`, creates a TASK_ASSIGNED
entry), and "the person who set this up has left and nobody gets the failure emails" is a real
operational problem with no workaround short of a database update. Restricting it to tenant admins
matches who is answerable for a tenant's alerting. It is deferred rather than done because it
changes who gets paged, and that should not land in the same release as six schedule fixes.

**Q5 -- What happens to the schedules already written with digit day codes?**
Every one has been running weekly from its start date, ignoring both the chosen days and the
interval (`ProcessTimeUtil.java:87-89, 250-263`).
*Options:* (a) translate `1`→`MON` … `7`→`SUN` and let the schedules move to the days that were
asked for; (b) null the column, leaving them on the weekly cadence they have actually had; (c) leave
them and let the new validation refuse the next edit.
**Recommendation: (a), run by hand with the list in front of you, before the code change ships.**
The digits meant Mon…Sun to the person filling the form, so translating delivers what they asked
for. It is by hand rather than in a changeset because it changes when live jobs fire, and the count
is almost certainly small enough to read -- run the `select` in §3 row 4 first. (c) is the worst
option: it leaves wrong schedules running *and* blocks the person who tries to correct one.
