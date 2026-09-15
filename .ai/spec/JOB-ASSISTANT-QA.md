# Job assistant — QA pass (2026-09-14)

Route: `/jobs/:jobId/assistant`, and the same component in panel mode. Triggered by a report that
"seems like [there is] some issue with chat bot" on job #2395. Fifty-plus cases, eleven defects,
all fixed and each one mutation-proven.

## What was actually wrong

The assistant answers from the job's own record: seven regex patterns map a question to an intent,
and `answerFor` composes the reply out of real figures. Nothing about that design was broken. What
was broken was the *table* — and the consequence of a miss, which nobody had thought through.

**A missed pattern does not degrade to "I don't know."** `JobAssistant.ask` hands every `unknown`
question to whichever AI agent is configured (three are, on this install). So a phrasing the table
failed to recognise stopped being answered from the record and started being answered by a model,
about a job whose exact figures were sitting one match away. Every gap below was therefore a
correctness problem, not a coverage nicety.

Measured by running 55 realistic phrasings through `classify` and reading the output rather than
guessing which ones would be wrong.

### Wrong answers

| Asked | Answered with | Why |
|---|---|---|
| "what time does it run" | the task's name, type and topic | no pattern owned the clock; `task` caught it on `what.*(does\|do)` |
| "what state is it in" | a block of run counts | `\bstat` is unbounded, so it matches **state** and **status** |
| "show me the log file" | the bucket and folders | `target` owned the word "file" and ran before `history` |
| "how many runs failed" | a tile of counts, no reasons | `stats` owned "how many" and ran before `failures` |
| "tell me about job 99" | **a summary of job #2395** | see scope, below |

### Sent to a model instead of answered

"how long does it take", "what is the average duration", "list the runs", "show me the last 5 runs",
"what went wrong", "who owns this job", "what is the priority", "is it healthy", "does it run every
day", "hi", "help", "what can you do".

`priority` is the sharp one: it is collected into `JobFacts`, rendered nowhere, and so the only way
to learn it was to ask a model that had never been told it.

### The scope hole

`OTHER_JOB_ID` required **three or more digits**. Any job with a shorter id was invisible to the
guard that is the whole reason this assistant exists:

- "tell me about job 99" → classified `summary` → **answered with job #2395's summary**
- "what about job 12" → classified `unknown` → handed to the model with #2395's facts attached

The three-digit floor was there to stop a year reading as an id ("since 2024"), but the
`(?:job\s*#?|#)` prefix already does that — a bare year has neither. The floor was protecting
nothing and hiding this.

Fixed by splitting the two forms: **where the word "job" is present any length counts**, because
the number is then unambiguously an id; a bare `#` keeps the three-digit floor, because "the #1
failure reason" is prose. Both directions are pinned by tests.

Also: `FLEET_WORDS` needed an adjective (`all`/`every`/`other`), so "how many jobs are there" was
answered as statistics about this one. The plural alone now counts.

### Two questions it should answer about itself

- **Greetings and "what can you do"** cost a model round-trip to be told what the buttons already
  say. Now a `capability` intent, answered locally. Anchored to the whole message, so "help me with
  the failures" is still a failures question.
- **"run it now", "trigger the job", "delete this job"** were handed to a model that has no way to
  run anything and every incentive to reply as though it had. Now an `action` intent that says
  plainly it only reads. The verbs require an object (`delete this`, `run it now`) because they are
  ordinary words in a question *about* an ETL job — "does it delete old files" describes the
  pipeline and is left alone.

## Component defects

1. **Every page load fetched the job twice, and wiped the transcript doing it.** The reload effect
   ended `if (!this.agents().length) this.loadAgents()`, which made `agents` one of its
   dependencies. When the agent response landed, the effect re-ran: a second fetch of the detail
   *and the entire run history*, and — because the effect also clears state — any answer already on
   screen and whatever the reader had half-typed, gone, at whichever moment that response happened
   to arrive. Confirmed on the running app before and after: four job requests per load became two.
   The agent list is the same for every job, so it now loads once in the constructor.

2. **Enter bypassed the in-flight guard.** The Ask button disables itself while `asking()`; the
   `(keydown.enter)` binding did not, so holding the key queued requests behind a single shared
   flag that settles once.

3. **A success with an empty body rendered nothing at all.** `data ?? null` left `loading` false,
   `error` empty and `facts` null, and the template's `@else if (facts(); as f)` has no `@else` —
   a blank page with no *Try again* on it.

4. **The transcript replayed to the agent could stop alternating.** It was filtered one line at a
   time, so an answer with no prose lost its `Assistant:` line and left the question standing;
   the model then read two `User:` turns in a row. Not reachable through any answer `answerFor`
   builds today — every case leads with a text block — so the test sets the turn up directly and
   says so, rather than pretending a preset produces one.

## Two things that looked like defects and were not

Recorded because both cost real time, and the next person will suspect them too.

- **"Pressing Enter does nothing."** Reproduced repeatedly through the browser-automation harness:
  the input kept its text, no turn appeared. It is the harness — its synthetic key event does not
  reach Angular's `keydown.enter`. A `KeyboardEvent` dispatched by hand works, and so does a real
  keyboard. Nearly reported as the headline bug.
- **The input not clearing after Enter.** Only when the `input` event and the Enter are dispatched
  in the same tick: `[value]="question()"` is dirty-checked against the last value Angular *wrote*,
  and no change detection ran in between. Insert one frame of pause — which any human typing
  provides — and it clears. Left alone; fixing an unreachable state is how reachable ones get
  introduced.

## Evidence

- `job-assistant.qa.spec.ts` — 50 numbered cases plus component integration, 67 tests.
- Frontend unit suite **1445 passing** (1378 before this pass).
- **Every fix mutation-proven**: reverted one at a time, each made at least one test fail (6, 3, 2,
  1, 5, 4, 8, 1, 1, 1, 1 failures respectively). Two mutations exposed flaws in the tests
  themselves before they exposed anything about the code:
  - the duplicate-load test passed with the bug put back, because a zoneless TestBed runs an effect
    only when something pumps it and the test never called `detectChanges` after the flush;
  - the transcript test asserted a premise that was false — it assumed the `history` preset
    produces a prose-free answer, and no preset does.
- Verified on the running app after rebuilding `next-app`: one detail fetch per load, and nine
  previously-broken phrasings answered locally and correctly.

## Left open, deliberately

- Run timestamps here render a naive server stamp through `DatePipe`, so a browser outside
  `America/Chicago` reads them in its own zone. **The job history page this assistant links to does
  exactly the same**, so fixing only the assistant would make the two disagree about the same run.
  It is one app-wide change against `core/instant.ts`, not a chatbot change. See
  REALTIME-AND-UI-SWEEP.md §4.
- "export the runs" / "download the runs as csv" stay `unknown`. The honest answer is "use the CSV
  and Excel buttons above", which is neither a data answer nor an action refusal; inventing a
  fourth kind of reply for two phrasings was not worth the risk to the other fifty.
- The agent picker defaults to the first agent in the list, which on this install is the Vision
  Assistant. It works — `JobAssistantServiceImpl` supplies its own job instructions and ignores the
  agent's stored ones — but the name on the answer reads oddly.
