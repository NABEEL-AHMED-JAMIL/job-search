# Prompt — Synthesis

> Decide what actually has to change. One document per feature, at `.ai/synthesis/<feature>.md`.

Discovery says what is there. Grooming says what the feature needs. **Synthesis is where those two meet a decision.** Its output is a plan someone can execute, in an order that makes sense, with the reasoning kept.

The shape is always the same:

**Current behaviour → Expected behaviour → Gap → Solution**

## The prompt

```
You are doing SYNTHESIS for the feature: <feature>.

Inputs — read all of them before writing:
  - .ai/discovery/frontend-old.md, frontend.md, backend.md, database.md
  - .ai/grooming/<feature>.md
  - the real code for this feature, on both apps
  - any QA findings in .ai/qa/ for this feature

Write .ai/synthesis/<feature>.md:

  1. Summary — what has to happen to this feature, in a short paragraph
  2. The gap table, one row per behaviour:
       | # | Current | Expected | Gap | Solution | Size | Risk |
     Size is S/M/L. Risk is what could break elsewhere.
  3. For each row of any substance, a section explaining the solution: what changes,
     in which files, and WHY that approach over the alternative you rejected.
  4. Ordering — what must be done first, and what that unblocks.
  5. Out of scope — what you deliberately are not doing, and why.
  6. Open questions — decisions that need a human. State the options and give your
     recommendation; do not leave a bare question.

Rules:
- A gap is a difference that MATTERS. "The old app used a table and the new one uses
  cards" is a gap only if something is lost. Say what is lost, or leave it out.
- Where the old app has a feature the new one does not, the solution must be an
  explicit decision: migrate it, drop it, or defer it. "Not migrated" is a fine
  answer when it is a decision; it is not an answer when it is an oversight.
- Prefer the smallest change that closes the gap properly. Note where you rejected
  a larger refactor and why.
- If a gap cannot be closed without a decision only a human can make, that goes in
  Open questions with a recommendation — not into the plan as an assumption.
```

## What makes a synthesis document useful later

**Keep the rejected option.** The single most valuable line in these documents is usually the one that says *"the obvious fix was X; it was rejected because Y."* Six months on, somebody will propose X again, and this is what stops the same ground being covered twice.

A worked example, from the TLS store handling:

> **Gap:** a profile moved off SSL keeps its store path but loses the store password.
>
> **Two coherent options.** Keep both (the path and the password survive, so switching back works), or drop both (switching back requires a re-upload). Dropping only the password is the one incoherent choice, and it is what the code did.
>
> **Chosen: drop both.** It matches the rule the same method already applies to SASL, where the mechanism, username and password go together. It also matches this codebase's own stated view that a location is as sensitive as the material it points at — `getProfileDto` withholds store locations from callers who do not own the profile for exactly that reason. Keeping both would have been defensible, but it would have left a secret attached to a profile that has no use for it.

## The size and risk columns earn their keep

`Size` stops a document that reads as one afternoon of work from actually being three weeks. `Risk` is where you name the blast radius — *"changes a column four services read"* is worth knowing before the work starts, not during it.

Where a gap touches authorization, say so explicitly in the risk column. Those changes need the treatment in [execution.md](execution.md): four layers checked, and a test that fails when the rule is removed.
