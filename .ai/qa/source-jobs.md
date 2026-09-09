# QA — Source Jobs

Companion to `.ai/grooming/source-jobs.md` (acceptance criteria in its §11; known issues in its §12).
That grooming document already static-read the frontend (`features/jobs/jobs.ts`/`.html`,
`features/jobs/edit/job-edit.ts`/`.html`) and backend (`SourceJobServiceImpl.java`,
`ProcessTimeUtil.java`) line-by-line and pre-identified ten known issues (§12.1–12.10) plus a list of
missing functionality (§13). This pass exists to exercise those claims against the live, running app
(`http://localhost:4400`, backend `http://localhost:9098`, both already running in Docker) rather
than to re-derive them from source, per `.ai/prompts/qa.md`'s four groups.

**This pass was cut short by a live infrastructure failure, not by choice.** Partway through
functional testing, the backend container (`process_app`) stopped answering any HTTP request at
all — confirmed independently via the browser, via `curl` from the host, and via Docker's own health
check — and did not recover for the remainder of the session. Per the task's own instruction not to
start or stop the already-running containers, it was left alone rather than restarted. See QA-32 for
full evidence. Every acceptance criterion below that needed a live request after that point is
**untested**, not passed — the majority of the 44-item checklist falls in that bucket. What was
completed before the crash still produced nine concrete defects, two of them severe.

**Scope of this pass.** The `source-jobs` feature only (`/jobs`, `/jobs/new`, `/jobs/:id/edit`) — the
list, the add/edit form, row actions, and the backend endpoints in `SourceJobRestApi`. Where a job
links into `source-tasks` (the task dropdown, the linked-task facts) only the link itself was
checked, not the destination screen.

**Fixtures used.** Signed in as `qa-test-admin@example.com` (`TENANT_ADMIN`, tenant **Acme
Analytics**) — the account already existed from an earlier QA pass this session, owning one task
(`QA Verification Task`, `#1287`, pipeline `QA-TEST-PIPE`) and no jobs (`/jobs` read "No jobs yet."
at the start of this pass, confirmed live). **Created for this pass, left in place** per
`feedback_leave_test_data_in_place.md`:
- Job `#2144` "QA Manual Job" — Manual execution, against task `#1287`. Currently `Active` (it was
  briefly toggled Inactive and back to Active during testing).
- Job `#2145` "QA Auto Daily" — created Auto/Daily, later edited to Weekly on Mon+Thu (see QA-31 for
  why that edit is itself evidence of a defect). It was run once (`Run now`), which failed almost
  immediately (unrelated to this feature — task execution belongs to `source-tasks`/Kafka, not
  `source-jobs`); its Run status currently reads `Failed`.

**Platform Admin was never reached.** The task brief asked for coverage as both `admin@platform.local`
and the tenant admin specifically to get real cross-tenant attack coverage. The backend crashed
before this pass got to logging in as the Platform Admin at all, so **every cross-tenant / role
/ STOMP-authorization criterion in the checklist below is untested**, not merely "partial" as it
would be with a same-tenant-only fixture — there is no negative control here at all, for either
account or endpoint. This is the single biggest gap in this pass and is called out per-row below
rather than left implicit.

---

## Acceptance criteria exercised (grooming §11)

| # | Criterion | Result |
|---|---|---|
| 1 | `au` sees only its tenant's jobs; `bu` sees only its own (positive control) | **untested** — no second tenant/account reached before the crash |
| 2 | `pa` sees all jobs across tenants | **untested** — Platform Admin never reached |
| 3 | `nt` (no-tenant token) gets an empty list, not an error or `B1` | **untested** |
| 4 | `bu` fetch-by-id refused; `au` fetch-by-id succeeds | **partial** — `au`'s own fetches succeeded throughout (implicitly, every edit-page load); no cross-tenant negative control obtained |
| 5 | Delete `A2` → absent from list and from fetch-by-id | **untested** — crash occurred before Delete was exercised |
| 6 | Newest job appears first | **FAIL** — see QA-26 |
| 7 | Numeric-id search narrows to one row | **untested** |
| 8 | State (Active/Inactive) filter exists and works | **FAIL** — confirmed absent from the toolbar; only "All types" (execution) and "All statuses" (run status) selects exist, matching grooming §13's "no" verdict live |
| 9 | Manual job: no schedule shown, `scheduler` count 0 | **PASS, with a serious caveat** — see QA-24 |
| 10 | State=Inactive on create is honoured | **FAIL** — see QA-25 |
| 11 | Task dropdown limited to Active tasks | **partial** — only one task exists in this tenant, and it correctly appears; no inactive task was available to confirm the negative side |
| 12 | Weekly Mon+Thu → `days_of_week='MON,THU'`, `next_run_at` lands on Mon/Thu | **FAIL** — see QA-31 |
| 13 | Reopening shows the Mon/Thu chips selected | **untested** — the edit page for this exact job hung (QA-32) before this could be checked |
| 14 | Weekly with no day picked is a valid, savable schedule | **FAIL** — see QA-30 |
| 15 | Monthly "Last day" reachable, `day_of_month=0` | **untested** — crash occurred before this was reached |
| 16 | End date set then cleared → actually cleared | **untested** |
| 17 | Priority 99 remains editable | **untested** live (only the client-side `min=1 max=9` DOM attributes were inspected, confirming the form itself cannot display 99 — consistent with grooming §12.5 — but no priority-99 fixture was created and re-opened before the crash) |
| 18 | End date before start date refused, marks the field; positive control after start date saves | **untested** |
| 19 | Auto → Manual keeps the job from running its old timetable | **untested** — this is the single most important scenario in the whole document (grooming §12.1) and the crash happened right as this pass was working toward it |
| 20 | Manual → Auto gets a real, working schedule | **untested** |
| 21 | `bu` update refused; `au` update succeeds | **untested** |
| 22 | Run now queues the job, toast confirms, row goes to `Queue` | **PASS** — see QA-34 |
| 23 | Run/Skip both disabled while in flight, both with an explanatory tooltip | **partial FAIL** — Run: pass; Skip: no tooltip at all — see QA-27 |
| 24 | Run/Skip disabled on an Inactive job with a tooltip naming the state; positive control after activating | **FAIL** (first half), **PASS** (positive control) — see QA-28 and QA-34 |
| 25 | Skip next run writes a `Skip` row, advances next-run | **untested** |
| 26 | Skip not offered on a Manual job; positive control on an Auto job | **PASS** — see QA-34 |
| 27 | Deactivate → State reads Inactive; no queue rows past a scheduled slot while off | **partial** — the State change itself was confirmed correct after a reload; "no queue row past a slot" needs the cron still running, which the crash makes impossible to keep confirming |
| 28 | Reactivate → `next_run_at` in the future, no `Missed` backfill | **untested** |
| 29 | `bu` toggle refused; `bu` can toggle `B1` | **untested** |
| 30 | Duplicate → `"X (copy)"`, starts Inactive, carries task/execution/priority/emails/schedule | **untested** — this is exactly where grooming §12.2 predicts the toast lies about the result; not reached before the crash |
| 31 | Delete → row leaves list, history still readable | **untested** |
| 32 | Bulk run selected → one toast, N queued | **untested** |
| 33 | Bulk delete refused with an in-flight row selected, named in the message; succeeds after deselecting | **untested** |
| 34 | Email notifications dialog: tick one, persists, rest of the job unchanged | **untested** |
| 35 | Live status update (Queue→Start→Running) with no reload, no scroll jump | **partial PASS** — a live Queue→Failed transition was directly observed with no reload (see QA-34); the intermediate Start/Running frames specifically were not each individually caught |
| 36 | Another session's deactivate reflects live on this screen | **untested** — needs two concurrent sessions, not attempted before the crash |
| 37 | `bu` refused on tenant A's STOMP topic; positive control on its own | **untested** |
| 38 | `au` refused on `/topic/jobs.all`; `pa` succeeds | **untested** |
| 39 | Stalled pill after 30 minutes; not shown for a 2-minute-old run | **untested** |
| 40 | Failed list request shows an error + Try again, not an empty table | **see QA-33** — a real (if extreme) natural instance of "the request never resolves" was observed, and the result is neither an error state nor an empty table: an infinite spinner. The "normal" fast-failure case (a 4xx/5xx) was not separately tested |
| 41 | "No jobs yet." vs "No jobs match the current filters.", distinguishable | **partial PASS** — see QA-35 for "No jobs yet."; the filtered-empty case was not separately provoked |
| 42 | Failed payload/run-history fetch shown distinctly from a genuinely empty one | **untested** |
| 43 | Both themes render correctly on list and edit, nothing unreadable | **partial** — dark mode confirmed clean on the list screen's chrome (header, tiles, toolbar) while it was in its loading state (no data ever rendered — see QA-32); the edit form and a populated table were never seen in dark mode |
| 44 | 375px: no horizontal page scroll, tiles 2-col, table scrolls in its own box | **partial** — confirmed via `scrollWidth === clientWidth === 375` and a 2-column tile layout, but again only against the loading/empty shell, never against a populated table |

**Not exercised at all in this pass:** 1–3, 5, 7, 13, 15, 16, 18–21, 25, 28–34, 36–39, 42 — all for
the same reason (the backend crash, QA-32), not because they were judged out of scope.

---

### QA-24 · blocker · New/Edit job — a Manual job cannot be saved through the UI at all, and the error gives no clue why

**Did:** As `qa-test-admin@example.com`, opened `/jobs/new`, named it "QA Manual Job", selected task
`QA Verification Task`, set Execution to **Manual — on demand** (the Schedule section correctly
disappeared from the page), left State at Active, and pressed **Create job**.

**Expected:** The job is created with no scheduler row (criterion 9).

**Got:** Toast: **"Check the highlighted fields."** — but no field on the visible form was
highlighted red, and `document.querySelectorAll('.ng-invalid')` found exactly one invalid element:
the `<form>` itself, with every individual leaf control (`jobName`, `taskDetailId`,
`executionType`, `priority`, `jobStatus`, all three email checkboxes) reporting `ng-valid`. No
`POST addSourceJob` was ever sent — confirmed via the network log, which showed only the page's own
`GET listSourceJob` after the failed submit.

**Cause, read from source:** `job-edit.ts:58-77` builds one `FormGroup` with a nested `scheduler`
group that is **always part of the form** — `startDate: ['', Validators.required]` starts empty and
required regardless of execution type. `job-edit.html:62`, `@if (isScheduled())`, only controls
whether the scheduler's *inputs are rendered*; it does not disable or remove the `scheduler`
`FormGroup` itself. So `scheduler.startDate` stays required-and-empty, `this.form.invalid` stays
`true`, and `save()` (`job-edit.ts:186-191`) refuses to submit — with nothing in the DOM for the
`app-field` wrapper to mark, because that control was never rendered for the user to see or fix.

**Confirmed reproducible, and found a workaround that reveals the real bug:** with execution still
set to **Auto**, typing a Start date (any date) into the now-visible Schedule section, and *then*
switching Execution to Manual, lets the same form submit successfully — because `scheduler.startDate`
is no longer empty, even though the field is invisible and irrelevant for a Manual job. `save()`
correctly omits `schedulers` from the payload when `isScheduled()` is false
(`job-edit.ts:210-216`), so the job that gets created this way genuinely is Manual with no
scheduler — job `#2144` was created exactly this way and reads "On demand" / no scheduler in the
list, so criterion 9's actual *server-side* behaviour is fine. The defect is entirely client-side:
**a user who goes straight to Manual without ever having visited Auto first, or who is editing an
existing Manual job (`loadJob` only patches `scheduler` `if (job.scheduler)` — a Manual job has
none, so `startDate` stays `''`), can never save**, and the toast tells them to check fields that
were never shown.

**Severity:** blocker. This is not an edge case — it is the direct, straight-line path for the
second of the feature's two execution types, and the edit path is affected identically (any
existing Manual job is equally stuck the moment its edit page shows the same "Check the highlighted
fields." with no field to check).

**Evidence:** `.ng-invalid` DOM scan (only the `<form>` element, no leaf control) quoted above;
network log showing no `addSourceJob` request on the direct attempt; job `#2144` created
successfully only via the fill-then-switch workaround, confirmed present in the list as "Manual" /
"On demand" with no scheduler.

---

### QA-25 · major · New job — the State control is decorative; a job created Inactive comes back Active

**Did:** On the same `/jobs/new` form, with State explicitly set to **Inactive**, created job
`#2144` ("QA Manual Job") using the workaround from QA-24.

**Expected:** The job appears in the list with State = Inactive (criterion 10).

**Got:** The list showed `#2144`'s State as **Active** immediately after creation, with no error or
warning anywhere that the chosen state was not honoured.

**Cause, read from source:** `SourceJobServiceImpl.addSourceJob:148` hard-codes
`sourceJob.setJobStatus(Status.Active)` and never reads `sourceJobDto.getJobStatus()` — exactly
grooming §12.2. This live reproduction confirms the State select on the create form
(`job-edit.html:52-58`) does nothing at all; the toast still says "Job created." with no indication
the chosen state was discarded.

**Severity:** major — a form control that is fully present, required, and silently ignored is worse
than not offering the control at all, since it actively tells the user something false about what
they just did.

**Evidence:** screenshot of the New job form with State = Inactive selected at submit time;
screenshot of the resulting list row reading "Active" immediately after.

---

### QA-26 · minor · Jobs list — newest job is not first

**Did:** Created `#2144` and then `#2145` in that order (a few seconds apart) and read the resulting
list top-to-bottom with no sort/filter applied.

**Expected:** The most recently created job appears first (criterion 6, and grooming's own framing:
"a console where the job you just created is on page 4 is a console people press Refresh on").

**Got:** `#2144` (older) listed **above** `#2145` (newer) — plain ascending `jobId` order, never
reversed. Matches grooming §2.6/§12.10.b exactly (`SourceJobRepository.java:45`'s `Sort ASC jobId`,
nothing in `jobs.ts:340` reverses it).

**Severity:** minor on a 2-job fixture; grooming is right that this compounds badly at real scale
(a newly created job would sit on the last page of a long list, not the first).

**Evidence:** screenshot of the list with `#2144` above `#2145`, both timestamped "7 Sep 2026" and
created seconds apart in that order.

---

### QA-27 · minor · Row menu — "Skip next run" gives no explanation when disabled for an in-flight job

**Did:** Ran `#2145` ("Run now"), then, while its Run status was `Queue`, opened its row menu and
inspected the "Skip next run" button's DOM attributes directly
(`disabled`, `title`).

**Expected:** Per criterion 23, both Run now and Skip next run are disabled while a job is in
flight, **each with a tooltip saying so**.

**Got:** `outerHTML` showed `disabled=""` and **`title=""`** — genuinely empty, not merely
whitespace. "Run now" in the same menu correctly relabels itself to the sentence "This job is
already queued or running" and carries the matching title; "Skip next run" just sits there disabled
with its ordinary label and no explanation at all.

**Cause, read from source:** `jobs.html:233-235` —
```html
<button cdkMenuItem class="menu-item" [disabled]="isInFlight(job) || !job.scheduler"
        [title]="!job.scheduler ? 'Only scheduled jobs have a next run' : ''"
        (cdkMenuItemTriggered)="skipNext(job)"><app-icon name="skip" />Skip next run</button>
```
The `title` binding only ever covers the "no scheduler" reason; when the button is disabled purely
because `isInFlight(job)` is true (the job has a scheduler and is simply mid-run), the ternary falls
through to `''`.

**Severity:** minor — the control is correctly disabled, just silently so in this one case.

**Evidence:** `outerHTML` dump of the button (`disabled=""`, `title=""`) captured while `#2145` was
in `Queue`; `jobs.html:233-235` quoted above.

---

### QA-28 · major · Row menu — Run now is offered on an Inactive job, and refused with a message that says the job does not exist

**Did:** Deactivated `#2144` ("QA Manual Job"), then opened its row menu and inspected "Run now"
(not disabled, plain label, no title), then clicked it.

**Expected:** Per criterion 24, Run now (and Skip) should be disabled on an Inactive job, with a
tooltip naming the state.

**Got:** "Run now" was fully enabled, with an empty title — the client performs no `jobStatus`
check at all before offering it (matches grooming §12.7 exactly: `jobs.html:230` disables only on
`isInFlight(job)`). Clicking it produced the toast **"SourceJob not found with jobId."** — read
literally: the server's message contains the literal word "jobId", not the actual number. Confirmed
at the API directly, bypassing the UI entirely:
```
POST sourceJob.json/runSourceJob  body {"jobId": 2144}
→ 200 {"status":"ERROR","message":"SourceJob not found with jobId."}
```
**Positive control:** re-activated `#2144` (dialog: "'QA Manual Job' will resume running on its
schedule." — see QA-29 for why that wording is itself off for a Manual job) and reopened the row
menu — "Run now" was enabled again with no disabled state, and "Skip next run" correctly showed
"Only scheduled jobs have a next run" (disabled for the *right* reason this time — this job
genuinely has no scheduler, being Manual).

**Severity:** major — the message actively misleads an operator into thinking the job they are
looking at on their own screen does not exist, when the real, fixable cause is that it is switched
off. `SourceJobServiceImpl.java:344-346`'s `findByJobIdAndJobStatus(jobId, Active)` lookup is the
root cause per grooming §12.7; this pass adds the exact live wording and confirms the client offers
the control with zero gating.

**Evidence:** DOM dump of the enabled "Run now" button before the click; toast text and the direct
`fetch()` response body quoted above verbatim; screenshot sequence of deactivate → click → toast →
reactivate → menu re-enabled.

---

### QA-29 · cosmetic · Deactivate/Activate dialog wording assumes every job has a schedule

**Did:** Opened the "Activate job" confirm dialog on `#2144`, a **Manual** job with no scheduler.

**Expected:** Wording that is true for the job in front of the user.

**Got:** `"QA Manual Job" will resume running on its schedule.` — this job has no schedule; it only
ever runs when someone presses Run now. The Deactivate dialog has the same issue in reverse
(`"will stop running"` is fine, but the "Slots that pass while it is off are recorded as Missed"
clause presumes a scheduler that a Manual job never has).

**Cause:** `jobs.ts:582-584` hard-codes the wording by `activating` alone, with no branch on
`job.execution`.

**Severity:** cosmetic — the dialog's functional behaviour (activate/deactivate) is correct; only
the sentence is wrong for one of the two execution types.

**Evidence:** screenshot of the "Activate job" dialog on `#2144` reading the quoted sentence;
`jobs.ts:582-584`.

---

### QA-30 · minor · Weekly schedule with no day selected is refused by the client, though the platform supports it

**Did:** Edited `#2145`, set Frequency to Weekly, left every day chip unticked, and pressed Save.

**Expected:** Per the grooming document's own "Expected behaviour" (§3): "Weekly without named days
is a valid schedule ... the backend supports it; the new form refuses it" — i.e. this criterion
(14) exists specifically to confirm that refusal is wrong and should be removed.

**Got:** Toast: **"Pick at least one day of the week."** — the save was blocked client-side, exactly
as grooming §7/§12 describe (`job-edit.ts:192-195`), with the summary panel correctly rendering
"Every 1 week at 00:00 — pick at least one day." beforehand as a preview of the same refusal.

**Severity:** minor by itself (a working schedule variant is simply unreachable from this form); the
grooming document treats it as more significant precisely because it is one of three client-only
rules that actively contradicts the backend's own accepted behaviour.

**Evidence:** screenshot of the Weekly section with no day selected and the "pick at least one day"
preview text; toast text on Save.

---

### QA-31 · major · Weekday chips write digit codes the scheduler cannot parse — confirmed at the stored value, with the resulting wrong schedule

**Did:** Edited `#2145`, set Frequency to Weekly, ticked **Mon** and **Thu**, and saved. The preview
text correctly read "Every 1 week on Mon, Thu at 00:00." before saving. Then read the job's stored
scheduler directly via the API (bypassing the UI) using the session's own bearer token:
```
GET sourceJob.json/fetchSourceJobDetailWithSourceJobId?jobId=2145
```

**Expected:** Per criterion 12, `scheduler.days_of_week` should hold `'MON,THU'`, and `next_run_at`
should land on a Monday or a Thursday **because of** that rule.

**Got:**
```json
{"schedulerId":1216,"startDate":"2026-09-07","frequency":"Weekly","intervalValue":"1",
 "daysOfWeek":"1,4","nextRunAt":"2026-09-14T00:00:00","expired":false}
```
`daysOfWeek` is **`"1,4"`** — the chip values (`job-edit.ts:20-24` defines Mon=`'1'` … Sun=`'7'`),
not `MON`/`THU`. `nextRunAt` is exactly **7 days after** the start date (2026-09-07, itself a
Monday, +7 days = 2026-09-14, also a Monday) — the flat weekly-fallback step
(`ProcessTimeUtil.nextByDaysOfWeek` returning `from.plusWeeks(1)` when no day code is recognised),
**not** a computation that picked the nearer Thursday (2026-09-10). The result happens to land on a
Monday, which technically satisfies criterion 12's literal wording ("falls on a Monday or a
Thursday"), but only by coincidence of the start date already being a Monday — the day-of-week rule
itself was completely discarded, exactly as grooming §12.4 predicts ("Every 3 weeks on Mon and Thu"
becomes "every 1 week from the start date").

**Severity:** major — this is silent and compounding exactly as grooming describes: nothing in the
UI, the toast, or the preview text (which correctly showed "Mon, Thu" before saving) gives any
indication that the days chosen were not the days actually saved. A job an operator believes runs
twice a week on specific days in fact runs once a week on whatever day the start date happens to
fall on.

**Severity note:** criterion 13 (reopening the job shows the Mon/Thu chips still selected) could not
be checked — the edit page for this exact job hung indefinitely on the next load attempt, which is
QA-32. Grooming §12.4 predicts this would have *appeared* to work correctly on reopen for a job
created through this same form (since the stored digit codes match the chips' own comparison
vocabulary) while being wrong on any job whose schedule came from the old app or the bulk importer.

**Evidence:** full JSON response quoted above verbatim, captured via `fetch()` with the session's
own stored token; screenshot of the pre-save preview reading "Mon, Thu".

---

### QA-32 · blocker, fixed 2026-09-07 · The backend became completely unresponsive mid-pass, halting the remainder of this QA pass

**Did:** Immediately after QA-31's save, navigated to `/jobs/2145/edit` to check criterion 13 (the
reopened form should show Mon/Thu selected). The page hung indefinitely on "Loading…". Investigated
rather than assuming a one-off:
- Repeated the navigation three times, full page reloads each time, waiting 5+ seconds: identical
  "Loading…" every time, never resolving.
- Ran a `fetch()` from the page's own console against `fetchSourceJobDetailWithSourceJobId` and
  separately against `listSourceJob`, each with an 8-second `AbortController` timeout: both aborted
  with no response.
- Ran `curl --max-time 8 http://localhost:9098/api/v1/sourceJob.json/listSourceJob` directly from
  the host shell, bypassing the browser entirely: `HTTP 000` — no response at all within the
  timeout.
- Checked `docker ps`: `process_app` reported **`Up 50 minutes (unhealthy)`**.
- Checked `docker inspect process_app`'s health-check log: every check since **2026-09-08T01:30:44Z**
  reported `"Health check exceeded timeout (10s)"` with **zero bytes received**, not a slow
  response — a `FailingStreak` that climbed from 8 to 12 over roughly six minutes of continued
  observation, with no recovery.
- Checked `docker logs process_app`: immediately before the outage window, two things happened in
  quick succession — `WebSocket offline: qa-test-admin@example.com (session 5ggz1bsj)` (a STOMP
  disconnect, the same live-update channel `source-jobs` uses for `/topic/jobs.{tenantId}`),
  followed by an **uncaught exception on Tomcat's own I/O poller thread**:
  ```
  Exception in thread "http-nio-9098-ClientPoller" java.lang.NullPointerException:
  Cannot invoke "java.nio.channels.SocketChannel.keyFor(java.nio.channels.Selector)" because the
  return value of "org.apache.tomcat.util.net.NioChannel.getIOChannel()" is null
      at org.apache.tomcat.util.net.NioEndpoint$Poller.events(NioEndpoint.java:613)
      at org.apache.tomcat.util.net.NioEndpoint$Poller.run(NioEndpoint.java:729)
  ```
  After that, the cron threads (`ProcessCron`, a separate thread pool) kept ticking normally every
  minute in the log — so the JVM itself was alive and the database reachable — but the HTTP
  connector's own event loop appears to have died with it, consistent with every subsequent request
  (from three independent clients: the browser, its own JS console, and `curl` from the host)
  receiving literally nothing back.

**Expected:** The backend keeps answering requests for the duration of a QA pass; a WebSocket client
disconnecting (an ordinary event — every page navigation on this SPA disconnects and reconnects the
STOMP session) does not take down the HTTP listener for every tenant.

**Got:** A full, unrecovered backend outage. Per the task's explicit instruction not to start or stop
the already-running containers, `process_app` was **not** restarted. As a direct consequence, this
QA pass stops here: every criterion in the table above that needed a live request after this point
is marked **untested**, not passed, including all of criteria 13, 15–21, 25, 28–34, 36–39, 42, and
the Platform Admin role in its entirety.

**Severity:** blocker — both for the immediate reason (it stopped this QA pass) and for what it
implies: this crash was triggered by ordinary interaction with `source-jobs`'s own live-update
mechanism (navigating between its list and edit pages, which opens and closes the STOMP connection
each time), and it took down the backend for every tenant and every feature, not just this one.

**Evidence:** `docker ps` output (`process_app` `Up 50 minutes (unhealthy)`); full `docker inspect
process_app --format '{{json .State.Health}}'` log (five consecutive `"Health check exceeded timeout
(10s)"` entries, 0 bytes, quoted above in summary; `FailingStreak` rising from 8 at first
observation to 12 roughly six minutes later); `docker logs process_app` excerpt showing the
`WebSocket offline` line immediately followed by the `NioEndpoint$Poller` `NullPointerException`
stack trace, quoted above verbatim; `curl -w` timing output (`HTTP 000 in 8.006871s` and again
`in 5.005481s` several minutes apart); browser network log showing `GET
fetchSourceJobDetailWithSourceJobId`, `GET listSourceJob`, `POST listSourceTask`, and `GET
notification.json/list` all sitting with no recorded status at the same moment.

**Fixed:** root cause was Spring Boot 2.3.2's default embedded Tomcat (9.0.37), which carries this
exact NIO-poller race as a real, uncaught bug — an ordinary STOMP disconnect closing a channel at
the same moment the poller processed a queued event for it. `process/pom.xml` now overrides
`tomcat.version` to `9.0.83` (same 9.0.x line Spring Boot already manages, no `javax.servlet` API
change), a patch well past where this was fixed upstream. Verified live: rebuilt, redeployed,
then deliberately repeated the exact navigation pattern that crashed it (list → edit → list,
several cycles) — stayed healthy throughout, no new poller exceptions in the logs, all 548 backend
tests still green. See `process` repo commit "Fix a live Tomcat crash, and let a platform admin's
pipeline picks match its form".

**Follow-up still needed:** the ~30 criteria this crash left untested (13, 15-21, 25, 28-34, 36-39,
42, and the entire Platform Admin role) were never re-run after the fix — this entry only closes
the crash itself, not the coverage gap it caused. A continuation QA pass should pick up exactly
where this one stopped, per the fixture/session state already described earlier in this document.

---

### QA-33 · major · With the backend down, the list screen spins forever instead of ever showing an error

**Did:** With the outage from QA-32 in progress, navigated to `/jobs` and waited over a minute.

**Expected:** Per criterion 40, a failed list request shows a red alert with a "Try again" button,
not an indefinitely empty/loading table.

**Got:** The centred spinner and "Loading…" text (`TableShell`'s loading state, correctly rendered)
stayed on screen for the entire observed period with **no transition to an error state at any
point** — no alert, no "Try again" button, nothing. This is a different failure shape than
criterion 40 anticipates (a fast 4xx/5xx that flips the panel to its error branch); here the request
never resolves at all — the browser's own connection is accepted at the TCP level then simply never
answered (matching the `curl`/health-check evidence in QA-32), and neither Angular's `HttpClient`
nor this component appears to apply any client-side request timeout that would eventually surface an
error. An operator watching this screen during a real outage would see nothing to tell them "this is
broken" versus "this is just slow" — the tab would look identical either way, indefinitely.

**Severity:** major — this is a real, live-observed gap even though it arose from an unusual
(if realistic) failure mode rather than a designed test; the "normal" fast-failure half of criterion
40 (e.g. a 500 response) was not separately exercised and remains untested on its own terms.

**Evidence:** screenshots of the list page's spinner taken roughly a minute apart, pixel-identical;
network log entries for the pending requests showing no resolution (see QA-32's evidence in full).

---

### QA-34 · pass · Run now, and the Inactive-job positive control, behave as specified

**Did:** As `qa-test-admin@example.com`, on job `#2145` (Auto, Active, scheduled): opened the row
menu and chose **Run now**.

**Expected:** A toast confirms it, the row's Run status becomes `Queue` (criterion 22); while in
flight, both Run now and Skip next run are disabled (criterion 23, first half); on a Manual job with
no scheduler, Skip next run is not offered (criterion 26).

**Got:**
- Toast: **"QA Auto Daily queued to run."**; the row's Run status column changed to `Queue`
  immediately, and the "Queued" summary tile incremented from 0 to 1 while "Never run" decremented —
  all without a page reload.
- With the job in `Queue`, reopening its row menu showed "Run now" **relabelled** to the disabled
  menu item "This job is already queued or running" — exactly the required wording.
- A short time later, with no action taken and no manual refresh, the same row's Run status changed
  on its own from `Queue` to `Failed` (the underlying task run failed almost immediately — a
  `source-tasks`/Kafka-side outcome, out of scope for this feature's own QA) — a live,
  unprompted update, consistent with the socket-driven `applyEvent` path described in grooming §2.6.
- On job `#2144` (Manual, no scheduler), the row menu's "Skip next run" item correctly appeared
  disabled with the title "Only scheduled jobs have a next run" — the control is effectively not
  offered, satisfying criterion 26's intent even though the mechanism is "no scheduler" rather than
  an explicit execution-type check.
- Positive control for criterion 24: after deactivating and then re-activating `#2144` (see QA-28),
  its "Run now" menu item returned to a plain, fully enabled state with no disabled reason — the
  Active/Inactive gate (such as it is, i.e. absent — see QA-28) is at least consistent in both
  directions.

**Evidence:** toast text and tile-count screenshots immediately after clicking Run now; DOM dump of
the relabelled disabled "Run now" item while queued; before/after screenshots of the Run status
column changing from `Queue` to `Failed` with no intervening navigation; DOM dump of the disabled
"Skip next run" item on `#2144`.

---

### QA-35 · pass · The empty-tenant "No jobs yet." state renders correctly

**Did:** Opened `/jobs` as `qa-test-admin@example.com` at the very start of this pass, before any job
existed for this tenant.

**Expected:** Per criterion 41, a tenant with no jobs sees "No jobs yet.", distinct from a
filtered-to-nothing result.

**Got:** Exactly that — an icon, "No jobs yet.", all five summary tiles at 0, and the toolbar fully
interactive with no jobs to act on. The "no jobs match the current filters" variant was not
separately provoked in this pass (no filter combination was tried against a populated, filtered-to-
zero result).

**Evidence:** screenshot of `/jobs` reading "No jobs yet." with all tiles at 0, captured at the very
start of this session.

---

## UI/UX — both themes, narrow viewport

**Severely limited by the backend outage (QA-32).** Every screen that needed real job data to render
meaningfully — the populated list table, the expanded row panel, a loaded edit form — was unavailable
for the second half of this pass. What could be checked:

- **Dark mode**, list screen chrome only (header, summary tiles, toolbar, the loading spinner
  itself), with **no job data ever rendered in the table area** in dark mode: clean. Every surface —
  header bar, the five tiles, "Refresh"/"Bulk import"/"New job" buttons, the two filter selects, the
  search box, "Only mine" — switched to dark tokens correctly with no leftover light-mode fill
  found.
- **375px viewport (mobile preset)**, same limitation (loading/empty shell only): the five tiles
  correctly collapsed to a 2-column grid (`grid-cols-2`), the toolbar controls stacked to full width
  rather than overflowing, and `document.documentElement.scrollWidth === clientWidth === 375` — no
  horizontal page scroll. The New/Edit job form (seen only in light mode, desktop width, before the
  crash) read cleanly with no obvious alignment issues, but was never tested at 375px or in dark
  mode specifically.

**Not checked at all in this pass:** the populated table at either narrow width or in dark mode; the
expanded row panel in either dimension; the New/Edit job form's Schedule section, weekday chips, or
summary preview in dark mode or at 375px; any dialog (Deactivate/Activate/Delete/Bulk/Email
notifications) in dark mode or at 375px.

---

## Backend — additional notes

- `SourceJobRestApi`'s class-level `@PreAuthorize("hasRole('TENANT_USER')")` was not independently
  re-verified this pass (e.g. a bare unauthenticated call to confirm 401) — every call made was
  already carrying the tenant admin's own valid token, so this pass adds no new evidence either way
  beyond what grooming §8 already documents from source.
- The one piece of authorization-adjacent evidence obtained live: `#2144` and `#2145` were created,
  edited, toggled, and run entirely by `qa-test-admin@example.com` acting on its own tenant's own
  task — consistent with, but not a stress test of, the tenant-ownership rules in
  `TenantOwnership.isOwnedByCaller`.
- The exact wording of the "Inactive job" refusal was captured verbatim at the API in QA-28:
  `{"status":"ERROR","message":"SourceJob not found with jobId."}` — matching grooming §9's own
  table exactly, now with live confirmation of the literal string (the message does **not**
  interpolate the actual job id, despite the grooming document's own illustrative example writing it
  as "not found with `<A1>`").
- The backend crash in QA-32 is, itself, the most consequential backend finding of this pass: an
  ordinary client action (navigating away from a page, which tears down its STOMP subscription)
  appears to have triggered an unhandled `NullPointerException` on Tomcat's I/O poller thread, after
  which the HTTP connector stopped answering requests for any tenant, any feature, and any account —
  confirmed to persist for at least six minutes with no self-recovery.

---

## Known issues from grooming §12 — live status

| # | Grooming's claim | This pass |
|---|---|---|
| 12.1 | Auto↔Manual switch is broken in both directions | **not independently re-verified live** — the crash (QA-32) happened while this pass was working toward exactly this scenario (criteria 19–20); still believed true per the static reading, but no fresh live evidence was obtained |
| 12.2 | State on create is ignored, server always sets Active | **confirmed live** — see QA-25 |
| 12.3 | An end date cannot be cleared | **not exercised** — crash occurred first |
| 12.4 | Weekday chips write digit codes the server cannot read | **confirmed live, with concrete evidence** — see QA-31 (`daysOfWeek:"1,4"`, `nextRunAt` landing on a flat +7-day fallback) |
| 12.5 | Priority 99/100 cannot be edited | **partially confirmed** — the client's own `min="1" max="9"` DOM attributes were verified directly; no live priority-99 fixture was created and reopened before the crash |
| 12.6 | `job.updated`/`job.toggled`/`job.deleted` never published over the socket | **not independently re-verified live** — would need two concurrent sessions, not attempted before the crash |
| 12.7 | Run/Skip offered on jobs the server will refuse, with a misleading message | **confirmed live, with exact wording** — see QA-28 |
| 12.8 | (Pre-existing platform issue) `source_job`/`scheduler` have no non-dev creation path | not exercised — a deployment characteristic, not observable in this environment |
| 12.9 | (Pre-existing platform issue) task-type edits can corrupt `job_status` casing | not exercised — would require editing a task type, out of this feature's scope |
| 12.10.a | `Start` missing from the run/skip refusal list, API-only | not exercised — would need a job caught in the `Start` status at the moment of the call |
| 12.10.b | List ordered oldest-first, never reversed | **confirmed live** — see QA-26 |
| 12.10.c | `fetchSourceJobDetailWithSourceJobId` skips `attachNames`, so a `refreshOne`'d row shows `—` for Created/Updated by until a full reload | not exercised — not specifically checked this pass |
| 12.10.e | "Only mine" always reads "(0 hidden)" | not exercised |
| 12.10.h | The summary preview compares the interval against the string `'1'`, breaking after any edit | not exercised |
| 12.10.j | `updateSourceJob` sends stale day/month rules regardless of the chosen frequency | not exercised |

---

## Summary

Nine concrete defects were confirmed live in the roughly half of this pass that got to run before
the backend failed: one **blocker** in the add/edit form itself (QA-24, a Manual job cannot be saved
through the UI without an undocumented workaround), one **blocker** at the infrastructure level
(QA-32, the backend crashed and did not recover), one **major** confirming grooming §12.2 live
(QA-25), one **major** confirming grooming §12.7 live with exact wording (QA-28), one **major**
confirming grooming §12.4 live with the exact stored value and its consequence (QA-31), one
**major** newly observed as a consequence of the outage (QA-33, no client-side request timeout), two
**minor** findings (QA-26 list ordering, QA-27 Skip's missing tooltip, QA-30 the over-strict
weekly-days rule), and one **cosmetic** wording issue (QA-29). Two items passed cleanly (QA-34 Run
now and its related mechanics, QA-35 the empty state).

Of the acceptance checklist's 44 criteria, **9 were fully or partially exercised** (6, 8, 9, 10, 22,
23, 24, 26, 35, 40, 41 — several only partially) and **the remaining roughly three-quarters are
untested**, not passed, almost entirely because of the mid-pass backend outage (QA-32) rather than
by choice or by being judged out of scope. In particular, **no cross-tenant attack was completed**
(criteria 1–5, 21, 29, 37–38) and **the Platform Admin role was never reached** — the two things the
task brief most specifically asked this pass to cover for real authorization coverage. This pass
should be treated as a first, partial sweep: the defects found are real and reproducible, but a
second pass is needed once the backend is restarted (by the user or their own process — not done
here, per instruction) to cover the cross-tenant/role matrix, the execution-switch scenarios (12.1),
delete/duplicate/bulk actions, and both themes/narrow-viewport against actual populated data.
