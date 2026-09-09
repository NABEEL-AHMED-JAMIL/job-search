# Synthesis -- Job Assistant

Feature `job-assistant`, status **new**. Reads with
[../grooming/job-assistant.md](../grooming/job-assistant.md); issue codes below (K-1 … K-11) are
that document's Known issues section.

Paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

The job assistant is the most complete of the three features the rewrite added, and the only one
with an adversarial test suite -- 75 cases across three spec files, all passing. The core is sound:
answers are composed from one job's own record and runs rather than generated, so there is no path
that invents a figure, and the two reads behind it are properly ownership-checked on the server.
What it needs is not a rebuild. It needs four things fixed and one decision taken.

The four fixes, in order of consequence: a failed run-history load is currently reported to the user
as **"this job has never run"** (K-3), which is the one place the feature contradicts its own
premise; the scope guard, which is the whole product promise, has at least two regex bypasses that
produce a confident answer about the bound job under a question naming a different one (K-1); the
same guard refuses questions it can answer because the words "user" or "account" appear anywhere in
them (K-2); and the export controls are hidden in exactly the two mounts most people use (K-7).

The decision is `askAssistant`. A 227-line service and a POST endpoint exist that answer the same
question through a real model, decrypting a stored API key to do it. **Nothing calls them** -- zero
matches for `askAssistant` in either frontend -- nothing tests them, and the service carries a
private copy of the tenant-ownership rule that omits the null-caller clause, so a caller with no
tenant is served every platform-owned job (K-4a). That copy is the exact drift
`TenantOwnership`'s javadoc was written to end. Whether the model path is wired up or deleted, that
ownership hole has to close in this pass, because it is live code behind a live endpoint today.

Everything else -- theming, responsiveness, the CSV injection defence, the load-race ticket, the
per-job microphone -- is already right and should be left alone.

---

## 2. Gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | Run-history request errors are discarded (`job-assistant.ts:181`); run-derived answers then state "This job has never run" | A failed run load is visible, and run-derived answers are not offered as fact | The feature's central claim -- every number is real -- is false on this path (K-3) | `runsError` signal; suppress or caveat the four run-derived answers; a line in the empty state | **S** | Low |
| 2 | `askAssistant` + `JobAssistantServiceImpl` exist, are called by nothing, are tested by nothing, and grant every platform-owned job to a null-tenant caller | One assistant. Whatever survives is reachable, ownership-correct and tested | Live endpoint, broken authorization, no coverage (K-4, K-4a, K-6) | **Fix ownership + `Delete` guard now; then delete the path** (§3.2) | **M** | **High** |
| 3 | `OTHER_JOB_ID` misses `job # 1300` and any id under 100; `jobs 1300 and 1301` falls to the guide | Any question naming another job by id is refused, whatever the spacing | Confident wrong-labelled answer under the one promise the feature makes (K-1) | Widen the pattern, scan **all** id matches, add the bypasses to the spec | **S** | Medium |
| 4 | `OTHER_SUBJECT` refuses any question containing user/tenant/account | Refuse questions *about* other subjects, not questions containing a word | Refuses "which user is this assigned to" while Summary prints the answer (K-2) | Narrow to subject phrasings; add an `assignee` intent answering from `facts.assignedUsername` | **S** | Medium |
| 5 | Export buttons live in `page-head`, hidden when `compact()` | Export reachable wherever the assistant is | The two panels -- how the feature is actually reached -- cannot download (K-7) | Move the buttons out of the hidden block | **S** | Low |
| 6 | "Next run" prints `2026-09-01T09:00:00`; "Last run" two rows below reads `19 Aug 2026, 00:01` | Both read the same way | The defect `humanMoment` was written to fix, unfixed on the adjacent row (K-5) | `humanMoment(s.nextRunAt)`; pin it in the spec | **S** | Low |
| 7 | 75 tests, all on two pure modules. No component spec, no route case, no `JobAssistantServiceImpl` test | The component, its two calls, its error paths and its export are covered | Every defect above lives in the untested half (K-9) | `job-assistant.spec.ts` with `HttpTestingController`; one `app.routes.spec.ts` case | **M** | Low |
| 8 | No `aria-live`, no label on the composer, panel is not a dialog, no `Escape` | Answers announced, input named, panel dismissible | Not usable without a mouse or without sight | `aria-live="polite"`, `aria-label`, `role="dialog"`, `(keydown.escape)` | **S** | Low |
| 9 | `history` and `failures` claim "most recent first" without sorting; `slowestRuns` lacks the non-negative guard `computeStats` has | Pure functions do not depend on their caller's ordering; the two duration paths agree | Correct today only because the server sorts (K-10, K-11) | Sort inside `answerFor`; add the `>= 0` guard | **S** | Low |
| 10 | Not in the shell nav, not in `/docs`; `closed` output bound nowhere | Findable; no dead API | Reachable only from a row menu or a URL (K-8, §13) | A docs line; delete `closed` | **S** | Low |
| 11 | Discovery row 5 lists `askAssistant` as the feature's endpoint and `JobAuditLogs` as an entity | Discovery matches the code | The feature's own index misdescribes it | Correct the row | **S** | Low |
| 12 | Success rate counts only `Completed + Failed` as a verdict | Agreed definition | Not a defect -- a product question | Open question Q3; no code change until answered | -- | -- |

---

## 3. Solution detail

### 3.1 Gap 1 -- make the failed run load visible

**Change.** In `scheduler1/next/src/app/features/jobs/assistant/job-assistant.ts`: add
`readonly runsError = signal(false)`, clear it in the effect beside `runs.set([])` (`:147-148`), set
it in the handler at `:181` and on a non-`SUCCESS` envelope at `:179`. In
`job-assistant.answers.ts`, give `answerFor` a fifth parameter -- `runsKnown: boolean` -- and have
the four run-derived intents (`stats`, `failures`, `history`, and the run-count row and stat block
of `summary`) return "The run history could not be read, so I cannot count runs for this job. Try
again." instead of a figure when it is false. In `job-assistant.html`, add a warning line to the
empty-state card at `:93-104`.

**Why this rather than the alternatives.** Two other options were considered.

*Rejected: treat the runs failure like the detail failure and show the error card.* It throws away
answers the assistant can still give correctly. The schedule, the target folder and the task are all
from the detail call, which succeeded; blanking the whole screen because the run count is unknown is
a worse trade than the current behaviour in every case except the one that is wrong. The comment at
`job-assistant.ts:181` is right about the intent and wrong only about the consequence.

*Rejected: retry the runs call silently.* It converts a visible wrong answer into an invisible
delay, and a job whose run history genuinely 500s -- the case worth surfacing -- would spin forever
producing the same false sentence.

Threading a `runsKnown` flag keeps the composition pure and testable, which matters because the
answer functions are the only part of this feature that currently has tests. The alternative of
having the component filter presets by `runsError` was rejected for putting the rule in the template
where nothing can assert it.

### 3.2 Gap 2 -- `askAssistant`: fix, then delete

**Recommended: fix the ownership hole immediately, then remove the path in the same pass.** Two
commits, in that order, so that the security fix stands on its own and is reviewable even if the
removal is deferred.

*Commit 1 -- close K-4a and K-6.* In
`process/src/main/java/process/model/service/impl/JobAssistantServiceImpl.java`, delete the private
`isOwnedByCaller` at `:118-123` and call
`process.security.TenantOwnership.isOwnedByCaller(job.getTenantId())` at `:85`. Add a
`Status.Delete` guard beside it, matching `SourceJobServiceImpl.java:467-469`. Add
`JobAssistantServiceImplTenantIsolationTest` in the shape of
`process/src/test/java/process/model/service/impl/SourceJobServiceImplTenantIsolationTest.java`.

*Commit 2 -- remove.* Delete `JobAssistantServiceImpl`, `JobAssistantRequestDto`, the
`askAssistant` method (`SourceJobRestApi.java:169-177`), the constructor argument and field
(`:35,38-42`) and the two imports (`:11-12`).

**Why deletion rather than wiring it up.** The rule-based assistant is not a stopgap for a model; it
is a different product with a stronger guarantee, and the class comment at `job-assistant.ts:27-34`
says so explicitly -- "a scope rule enforced in code cannot be talked out of it the way a prompt
can", and "the thing works without any AI provider configured". Wiring `askAssistant` up would
reintroduce exactly what that decision removed: a scope rule that is a sentence in a prompt
(`JobAssistantServiceImpl.java:136-138`), an answer whose figures nobody can verify against the
screen, a dependency on a tenant having configured an Active agent with a key, and a per-question
cost. It would also widen the data path -- one job's full record, its failure messages and forty
runs to a third-party endpoint -- for questions the client already answers offline.

*Rejected: keep it dormant.* This is the current state and it is the worst of the three. A reachable
POST endpoint that decrypts an API key, has a broken ownership check and no test is a liability that
grows quietly. Dormant code is not free; it is code that will be discovered by someone who assumes
it works.

*Rejected: wire it as an optional "ask the model" mode behind the existing answers.* Defensible, and
the only reason it is not recommended is that it is a product decision rather than a cleanup -- it
needs an agent picker, a cost owner, a story for tenants with no agent, and its own prompt-injection
test suite. It is raised as **Q1**; if the answer is yes, commit 2 is replaced by that work and
commit 1 still lands first.

Note the asymmetry that makes commit 1 urgent regardless: `TenantFilterHelper.enableIfNeeded`
*disables* the Hibernate filter for a null-tenant caller (`TenantFilterHelper.java:28-33`), the read
is `findById` which the filter would not have covered anyway, and `JobQueue` declares no filter at
all. The service check is the entire boundary, and it is the broken copy.

### 3.3 Gaps 3 and 4 -- the scope guard

**Change**, all in `job-assistant.intents.ts`:

- Widen `OTHER_JOB_ID` (`:25`) to allow whitespace after the hash and to accept one or more digits:
  roughly `/(?:jobs?\s*#\s*|jobs?\s+|#\s*)(\d+)\b/gi`. Then, in `classify` (`:56-62`), iterate
  **every** match rather than testing only the first, and refuse on the first id that is not the
  bound one -- which also fixes `what about jobs 1300 and 1301`.
- Narrow `OTHER_SUBJECT` (`:28`) from "the word appears" to "the question is about it": phrasings
  such as `(how many|which|list|show me|all|other)\s+(users?|tenants?|accounts?)`, plus the existing
  `FLEET_WORDS`. Add an `assignee` intent matching `assigned|owner|who owns|responsible` that
  answers from `facts.assignedUsername` -- the value Summary already prints
  (`job-assistant.answers.ts:167`).
- Extend `job-assistant.intents.spec.ts` and `chatbot-suite.spec.ts` with the four bypasses in K-1
  and the three false refusals in K-2, each paired with the positive control named in grooming
  criteria 20, 21 and 23.

**Why regex rather than something cleverer.** *Rejected: send the question to the server and let a
model decide scope.* That is gap 2's rejected option wearing a different hat, and it makes the
promise weaker, not stronger. *Rejected: replace the patterns with a small keyword scorer.* It would
trade a set of failures you can enumerate in a table for a set you cannot, and the current tests --
the best asset this feature has -- are written against enumerable behaviour. The regexes are the
right tool; they are simply under-specified in two known places, and both are one-line changes with
a test each.

Keep the severity honest while doing this: a bypass mislabels an answer, it does not leak. No other
job's data is ever fetched (grooming §8.3). That is why gap 3 is Medium and gap 2 is High.

### 3.4 Gap 5 -- export from the panel

**Change.** In `job-assistant.html`, lift the two buttons (`:22-32`) out of the
`[class.hidden]="compact()"` block at `:9` into their own row that renders in both modes -- in
compact mode as `btn-xs` icon-only buttons on the composer card at `:49-51`, where the presets
already live.

*Rejected: repeat the buttons in each panel header* (`jobs.html:430`, `job-history.html:394`). It
would put the export in two templates that do not own the runs, forcing either an output event or a
duplicate of `runsToCsv`'s call site -- and the component comment at `job-assistant.ts:49-53` is
explicit that the whole reason page and panel share one component is "so the answers, exports and
scope rules cannot drift apart".

### 3.5 Gap 6 -- one date format

**Change.** `job-assistant.answers.ts:194` becomes
`value: s.expired ? 'Expired — no further runs' : (s.nextRunAt ? humanMoment(s.nextRunAt) : 'Not scheduled')`.
Add a spec case beside the existing Last-run one at `job-assistant.intents.spec.ts:185-191`.

`humanMoment` rather than Angular's `DatePipe` because the value is composed inside a pure function
that has no injector, and `humanMoment` already handles the naive-stamp and unparseable cases
(`answers.ts:108-115`). Leave the `Starts` row (`:192`) alone: `LocalDate` serialises as
`2026-09-01`, which reads correctly as a date.

### 3.6 Gap 7 -- tests

**Add** `features/jobs/assistant/job-assistant.spec.ts`. The nearest existing model is
`features/admin/storage/storage-connections.spec.ts`, which uses `TestBed` with a stubbed
`HttpClient` returning `of(...)`; cases 1, 5 and 7 below assert the *request*, so those want
`provideHttpClientTesting` and `HttpTestingController` instead. Either way the cases are:

1. Both GETs are issued with the right `jobId`.
2. Detail `ERROR` envelope -> `error()` set, retry re-issues both.
3. **Runs failure -> `runsError()` set, and a `stats` answer does not say "never run"** (gap 1's
   regression test).
4. Changing `jobId` clears turns, question and runs before reloading -- the bug
   `job-assistant.ts:136-141` records as already having happened once in the panel.
5. A stale response from the previous `jobId` is dropped (`loadTicket`).
6. `exportRuns('csv')` with no runs toasts and issues no request; with runs it produces the CSV
   without a request.
7. `exportRuns('xlsx')` posts `{sourceFormat:'csv', targetFormat:'xlsx'}` to
   `fileChat.json/exportFile`; an `ERROR` envelope clears `exporting()` and toasts.

**Add** one case to `app.routes.spec.ts` recording that `jobs/:jobId/assistant` deliberately carries
no `minRole`, with the reason -- the same shape as the `/tools/query` case at `:38-42`. This is not
ceremony: the file exists precisely to pin the two routes whose gating is a decision rather than an
oversight, and after Q2 this is a third.

### 3.7 Gap 8 -- accessibility

`aria-live="polite"` on the transcript container (`job-assistant.html:106-108`) and an
`aria-label="Ask about this job"` on the composer input (`:54`). On both panel hosts
(`jobs.html:421`, `job-history.html:384`): `role="dialog"`, an `aria-label` naming the job,
`(keydown.escape)` closing, focus moved in on open and restored on close.

`aria-live` on the container rather than on each turn: turns are prepended
(`job-assistant.ts:192`), so the newest is always the first child, and a live region on the list
announces it once. Marking each turn would re-announce the whole transcript on every question.

### 3.8 Gaps 9, 10 and 11 -- small corrections

- `job-assistant.answers.ts:245` and `:235`: sort by `startTime`/`dateCreated` descending inside
  `answerFor` before slicing, so "most recent first" is true of the function and not just of the
  current caller.
- `job-assistant.ts:126`: add the `seconds >= 0` guard `computeStats` already has
  (`answers.ts:77-82`), so the two duration paths agree.
- Delete `readonly closed = output<void>()` (`job-assistant.ts:55`).
- Add the assistant to the `/docs` "watch" step (`features/docs/docs.ts`).
- Correct Discovery row 5 (`.ai/discovery/features.md:39`): entities SourceJob, JobQueue,
  **Scheduler**; endpoints `fetchSourceJobDetailWithSourceJobId`,
  `fetchSourceJobQueueListWithJobId`, `fileChat.json/exportFile`, with a note that `askAssistant` is
  declared and uncalled. Section 3's row at `:226` should lose "Nine intents" in favour of "seven
  answerable intents, six with presets".

---

## 4. Ordering

**First, alone, and mergeable on its own: gap 2 commit 1** -- the ownership fix and its isolation
test. It is a live authorization defect on a live endpoint and it does not depend on, or block,
anything else here. Everything below can proceed in parallel with it.

**Then, in this order:**

1. **Gap 1** (failed run load). The largest correctness defect, and it changes `answerFor`'s
   signature, which gaps 3, 4, 6 and 9 also touch. Doing it first means one signature change rather
   than a merge conflict across four small branches.
2. **Gaps 3 and 4** (the scope guard) together -- both are `job-assistant.intents.ts` and both need
   cases in the same two spec files.
3. **Gap 6 and gap 9** -- one-liners in `job-assistant.answers.ts`, cheapest once (1) has settled
   the file.
4. **Gap 7** (component spec). Deliberately after 1-3 rather than before: written first it would
   pin the current wrong behaviour and then need rewriting. The three regression cases named in
   §3.6 are what it exists for.
5. **Gap 5** (export from the panel) and **gap 8** (accessibility) -- independent of everything
   above, touch only templates, can be done by a second pair of hands at any point.
6. **Gap 2 commit 2** (removal) **last**, once Q1 is answered. If Q1 comes back "wire it up", this
   slot becomes that work instead and everything above still stands.
7. **Gaps 10 and 11** (docs line, dead output, Discovery correction) at the end, as tidying.

What unblocks what: commit 1 unblocks nothing but must not wait. Gap 1 unblocks 3, 4, 6 and 9 by
settling `answerFor`'s shape. Gaps 1-4 unblock gap 7. Q1 blocks only gap 2 commit 2.

---

## 5. Out of scope

**Persisting conversations.** Turns die with the component (`job-assistant.ts:146`). Storing them
needs a table, a retention policy for failure messages that may carry customer data, and a view to
read them back. There is no evidence anyone has asked, and the feature reads correctly as
stateless -- you ask about the job in front of you.

**Replacing the answers with a model.** Argued in §3.2. If Q1 returns "yes", it is new work with its
own grooming, not a fix inside this one.

**Reworking the loading and empty chrome onto `TableShell`.** The assistant hand-rolls three cards
that nineteen other screens get from the shared component (grooming §4.4). It is real
inconsistency, but the assistant is not a list and `TableShell`'s vocabulary does not fit a
transcript. Left as a note rather than a task.

**A question-length cap** (grooming V2) and a **client-side export size check** (V7). Both are
guards against costs that do not exist while the assistant is offline and the export is bounded by
one job's run count. V7 becomes worth doing if a tenant appears with a job over roughly 1,500 runs;
V2 becomes worth doing only if Q1 returns "yes".

**Changing what counts as a success.** `computeStats` measures against `Completed + Failed` only
(`answers.ts:85`). Raised as Q3; no code moves until a human answers it, because either reading is
defensible and changing it silently would move a number people have started to trust.

**The `\d{3,}` floor's lower half.** `SourceJob`'s sequence starts at 1000
(`SourceJob.java:47-53`), so a live id is always four digits and the "job 88" case in K-1 names a
job that does not exist. It is fixed for free by the `\d+` change in §3.3, but it is not a reason to
do that work -- the `job # 1300` case is.

---

## 6. Open questions

### Q1 -- Delete `askAssistant`, or wire it up as a second mode?

The endpoint, its DTO and a 227-line service are live and unreferenced.

- **(a) Delete.** Removes a model-calling endpoint, a decrypted API key on an unused path, and 280
  lines nobody tests. Costs the option of a free-text assistant later, though the code is in git.
- **(b) Wire it up** behind an agent picker as an optional "ask the model" mode alongside the
  composed answers. Gains genuinely open-ended questions. Costs an agent picker, a per-question
  bill, a story for tenants with no configured agent, a prompt-injection suite, and it weakens the
  scope guarantee from *enforced* to *instructed*.
- **(c) Leave it dormant.** The status quo.

**Recommendation: (a), after the ownership fix lands.** The rule-based assistant was chosen over a
model deliberately and the reasoning is recorded in the code
(`job-assistant.ts:27-34`); nothing has changed to reverse it, and (c) is strictly worse than either
of the others. If the product owner wants (b), it is a new feature with its own grooming, and the
ownership fix and its test land first either way.

### Q2 -- Should the assistant route carry `minRole: 'TENANT_USER'`?

Today it carries no `roleGuard` and relies on the shell's `authGuard` (`app.routes.ts:78-82`). The
endpoints behind it are `TENANT_USER`, which every signed-in role reaches through the hierarchy, so
the behaviour is correct -- but implicitly.

- **(a) Add it**, matching `/objects` (`app.routes.spec.ts:26-30`). Makes the floor explicit and
  catches the case `authGuard` cannot see: a stored session whose token carries no readable role,
  which would otherwise land on a page of refused calls.
- **(b) Leave it**, matching every other job screen -- `/jobs`, `/jobs/:id/edit`,
  `/jobs/:id/history` all rely on `authGuard` alone.

**Recommendation: (b), with the route-spec case from §3.6 recording *why*.** Consistency inside the
jobs family is worth more than a guard that changes no outcome, and the deliberate absence
documented in a test is what stops the next reader treating it as an oversight -- the same treatment
`/tools/query` already gets.

### Q3 -- Does an `Interrupt` or `Missed` run count against the success rate?

`computeStats` counts only `Completed + Failed` as having reached a verdict
(`answers.ts:85,:94`), so a job with 10 completed, 5 interrupted and 0 failed reports 100%.
`HUMAN_STATUS` (`:63-67`) knows six other states.

- **(a) Keep as is.** An interrupted run was stopped by a person or the platform, not by the job
  failing; counting it would blame the job for an operator's action. Consistent with the reasoning
  in the test at `job-assistant.intents.spec.ts:99-102`.
- **(b) Count `Interrupt` and `Missed` as failures.** "Success rate" then means "of the runs that
  should have produced output, how many did", which is closer to what an operator asks.
- **(c) Report both**, as "100% of completed runs; 67% of all scheduled runs".

**Recommendation: (a), and say so on screen.** Change the Success rate tile's caption to "Success
rate (of finished runs)" (`job-assistant.html:146`). The number is defensible; what is missing is
that its denominator is stated nowhere, so a reader supplies their own. (c) is the honest answer and
costs a tile the four-across grid does not have room for.

### Q4 -- Should the assistant appear in the shell navigation?

It is in no nav group (`features/shell/shell.ts`) and no docs step, reachable only from a job row
menu, run history, or a typed URL.

- **(a) Leave it out of the nav, add it to `/docs`.** The route needs a job id, so a nav entry would
  have to guess one or lead to a picker.
- **(b) Add a nav entry** that lands on a job picker.

**Recommendation: (a).** The assistant is an action on a job, not a destination; its two natural
entry points already sit exactly where the question occurs. A docs line in the "watch" step is
enough to make it discoverable without inventing a screen whose only job is to ask which job.
