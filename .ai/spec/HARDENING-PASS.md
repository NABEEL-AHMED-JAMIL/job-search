# Platform hardening pass — 2026-09-14 → in progress

A full correctness pass over seven areas, to a zero-known-bugs bar: No-RAG file chat, Analytics
Studio, Save Analysis, Notifications, Sources/Jobs/Tasks/Queue, Reports/Charts, and cross-cutting
frontend/backend correctness.

**This document is written as the work happens.** Sections below are marked with their real state.
Nothing is recorded as done until it has been run and the output read. Where a finding turns out to
be wrong, the wrong finding stays in the record with the correction — that has already paid for
itself once on this project (see REALTIME-AND-UI-SWEEP.md §4, where a wrong timezone diagnosis was
acted on before being caught).

## Method

Four waves, each verified before the next begins.

1. **Discovery.** One deep reader per area, then every candidate defect handed to a separate agent
   whose instruction is to REFUTE it. Only survivors are fixed. This ratio matters: the last sweep
   on this codebase produced 66 candidates of which 8 were refuted, and a previous one produced 32
   confirmed from a wider pool.
2. **Fix.** File-disjoint workers, one root cause at a time, each fix carrying a regression test.
3. **Test.** 50+ cases per flow as the brief requires, written against real behaviour rather than
   against the implementation.
4. **End-to-end.** Source → job → task → queue → processing → report → chart → save analysis →
   notification, verified as one lifecycle.

### Rules held throughout

- Reproduce, find the root cause, fix the root cause, add a regression test, re-run.
- **Every fix is mutation-proven**: the fix is reverted and the new test must fail. A test that
  passes with the fix removed is not a test. This has caught real gaps on this codebase before — a
  cell-budget fix that had no test at all, and a heartbeat guard that would have disabled the
  stalled-run check.
- No suppressed exceptions, no widened catch blocks, no test-only branches to make a suite pass.
- The containers are prebuilt images. A change is not verified until both are rebuilt — testing
  against a stale bundle has wasted a full suite run on this project before.
- The backend E2E suite and the browser suite are never run concurrently. They share one database
  and a four-permit query governor, and running them together produced 19 failures that were
  misread as a regression.

## Scope confirmed before starting

"No-RAG" was not a term in the codebase. Traced it rather than guessing: it is the FileChat path
that answers from a file's raw (possibly truncated) text when retrieval is not used —
`FileChatServiceImpl`, `EmbeddingServiceImpl`, `OpenSearchRagClient`, and
`features/objects/chat/file-chat.ts`, with `FileChatRagDecisionTest` describing the decision.

## Wave 1 — discovery

**Complete.** 56 agents, ~23 minutes. 49 candidates, **48 confirmed, 1 refuted.**

| area | confirmed | worst |
|---|---|---|
| No-RAG (file chat) | 7 | 1 critical |
| Analytics Studio | 5 | major |
| Save Analysis | 7 | major |
| Notifications | 7 | major |
| Sources/Jobs/Tasks/Queue | 8 | major |
| Reports/Charts | 7 | major |
| Cross-cutting | 7 | major |

**A 48-of-49 confirm rate is not a good sign about the verifiers.** The previous sweep on this
codebase refuted 8 of 66. Either this pass's finders were unusually disciplined or its refuters
were lenient, and the second is more likely. Treated accordingly: the one critical finding was
re-verified by hand against the live cluster before any code was touched, and the fix wave is
instructed to report a finding as refuted rather than invent a fix for it.

The single refuted candidate: a claim that the per-user WebSocket notification push has no
subscriber. Its load-bearing premise was false.

### The critical one, verified by hand

**RAG retrieval was dead on the live index.** `termsFilter` scopes every query with a `term` clause
on `embeddingModel`, but the live `file-rag-chunks` index maps that field as analyzed `text` — a
dynamic mapping predating the field — so the standard analyzer had split `nomic-embed-text` into
[nomic, embed, text] and the exact-term clause matched nothing.

Measured directly on the running cluster rather than taken on trust:

```
term embeddingModel          -> 0   of 222 chunks
term embeddingModel.keyword  -> 219 of 222 chunks
```

Consequence: every question about every file read as "not indexed yet", took the index lock,
re-extracted, re-chunked and re-embedded the **whole file**, wrote it back, searched again, still
found nothing, and answered from truncated raw text — on every single message, indefinitely.

`mappingComplaint` already diagnosed this precise condition, in precise words, and the only action
taken on it was a log line at ERROR saying it could not be repaired in place. For the two
vector-shaped complaints that is true. For this one it is not: the chunks and their vectors are
perfectly good, and only the query could not reach them.

**Fixed** by matching either field path (`embeddingModel` or `embeddingModel.keyword`) rather than
by reindexing — a term clause against a field the mapping does not define matches nothing instead
of erroring, so each side is inert on the index the other belongs to. `mappingComplaint` no longer
reports a retrievable index as broken, because a warning that fires on a working index is how
people learn to scroll past it.

Verified on the live cluster: the old clause counts 0, the new one counts 219. Three tests fail if
the fix is reverted.

## Wave 2 — fixes

**Complete. 47 of 48 defects fixed** (the 48th was the RAG retrieval one, fixed by hand in wave 1).
Seven file-disjoint groups. Nothing was refuted on closer inspection, which — given the wave 1
concern about lenient verifiers — is itself worth noting rather than celebrating.

### The run was interrupted, and that is instructive

A usage limit killed six of the seven agents mid-flight. One group had completed. The interrupted
tree was **not** safe to carry on from:

- **The frontend build was dead.** A killed agent had written a comment inside a component's
  `template:` literal containing backticks — `` `bounds().highX` `` — which terminates the template
  string, producing `NG5002: Unclosed block "else"` and a build that could not run. This is the
  same trap that broke `bar-chart.ts` earlier in the same session, so the relaunch prompt calls it
  out by name.
- **Two tests were left asserting designs that did not exist**, written for fixes never finished.

Those were deliberately NOT patched by hand. Completing another author's half-built design without
knowing its shape is how a plausible-looking wrong fix gets in. The relaunched agents were told the
tree was partial, told to reconcile before changing anything, and asked to report each finding as
already-done / half-done / untouched. They did: of 45, **25 were already-done, 7 half-done, 13
untouched** — the interrupted run had got considerably further than its failure notice implied.

### Two test defects found while verifying, both worth more than the fixes they hid

Neither was a product bug; both were tests that could not have failed for the right reason.

1. **A float-noise test whose fixture had no float noise.** The donut centre test asserted its own
   premise — "the raw sum really is noisy, so this is asserted rather than assumed" — and the
   premise was false. Floating-point addition is not associative, and the total folds left from
   zero: `33.33 + 0.49 + 0.17` is exactly `33.99`, while `0.49 + 0.17 + 33.33` is
   `33.989999999999995`. Written large-value-first, the fixture produced a clean total and the test
   measured nothing. The premise assertion is the only reason anyone found out; the fixture is now
   ordered small-first with the reason recorded on it.

2. **A "declines" test that was driving the confirm path.** `browser(confirms: boolean | undefined
   = true)` — and the test called `browser(undefined)` meaning "the reader dismissed the dialog".
   In JavaScript an explicit `undefined` argument triggers the default, so `confirms` was `true`:
   the reader confirmed, the chat closed, a new panel was built, and the identity assertion failed.
   The FIX was correct all along. The default is gone and every call site is explicit, because a
   union of true/false/undefined cannot express its third case behind a default.

### Cross-group work identified but not done

Each group was forbidden from editing another's files, and reported what it could not reach:

- `AnalysisQueryBuilder.drill()` compiles every drill step as an equality on the raw column
  regardless of grain. The Canvas now refuses a drill on a bucketed dimension with the reason on
  screen — the honest stop-gap — but the server half is what would make it work.
- The prepareContext/sendMessage state report needs a DTO field to carry what actually happened
  rather than what was predicted.
- The **legacy** Object Browser in `scheduler1/src/` (not `scheduler1/next/`) reads `sendMessage`'s
  `response.data` in the old shape.
- `file-chat.ts` has the second copy-button instance of the unchecked-clipboard defect.

## Verification after wave 2

| suite | before the pass | after |
|---|---|---|
| Backend unit | 1245 | **1297** |
| Frontend unit | 1251 | **1348** |

All passing. 149 tests added by the fix wave. Backend compiles, frontend builds, both containers
rebuilt and healthy.

## Wave 3 — test cases

Not started. Target per the brief: 50+ each for No-RAG, Analytics Studio, Save Analysis,
Notifications, Sources/Jobs/Tasks/Queue, Reports/Charts.

Existing coverage this builds on, measured today: backend 1245 unit + 102 E2E, frontend 1251 unit,
45 Playwright — all passing.

## Wave 4 — end-to-end

Not started.

## Final report

Not started. Will carry: bugs found, bugs fixed, root cause of each significant one, changes by
layer, test cases created/passed/failed, regression results, manual and end-to-end results, and
anything left open with the reason.
