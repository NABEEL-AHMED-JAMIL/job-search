# Synthesis

One document per feature: `synthesis/<feature>.md`. The name matches its row in [../discovery/features.md](../discovery/features.md).

Discovery says what is there. Grooming says what the feature needs. **Synthesis is where those two meet a decision** — and it is the document a reader will come back to, because it is the only one that records *why*.

The shape is always:

**Current behaviour → Expected behaviour → Gap → Solution**

Use [../prompts/synthesis.md](../prompts/synthesis.md).

## Required sections

1. **Summary** — what has to happen to this feature
2. **Gap table** — `| # | Current | Expected | Gap | Solution | Size | Risk |`
3. **Solution detail** — per row of substance: what changes, in which files, and why that approach
4. **Ordering** — what comes first, and what it unblocks
5. **Out of scope** — what you are deliberately not doing
6. **Open questions** — decisions needing a human, each with a recommendation

## What makes these worth writing

**Keep the rejected option.** The most valuable line in a synthesis document is usually *"the obvious fix was X; it was rejected because Y."* Six months on, somebody will propose X again. This is what stops the same ground being covered twice.

**A gap is a difference that matters.** "The old app used a table, the new one uses cards" is only a gap if something was lost. Say what was lost, or leave it out.

**"Not migrated" is an answer when it is a decision.** It is not an answer when it is an oversight. Every old-app capability with no successor gets an explicit call: migrate, drop, or defer — with the reason.

## Status

Empty — Discovery is in progress.
