# Reports

Evidence and run outputs. Everything that is too big, too raw, or too transient to belong inside a phase document, but that a phase document needs to point at.

## What belongs here

- Test run outputs worth keeping — a full failure log, a baseline count before a large change
- Screenshots referenced by a QA finding
- Response bodies, request captures, log extracts cited as evidence
- Migration dry-run output, schema diffs
- Review reports from a code-review pass

## What does not

- **Secrets.** No `.env` files, no tokens, no keys, no passwords, no database dumps containing real credentials. If a log line contains one, redact it before the file lands here.
- Anything a phase document should have said itself. A report is evidence for a conclusion, not a substitute for writing the conclusion down.
- Scratch files. Use the session scratchpad for those.

## Naming

`<phase>-<subject>-<what>.<ext>`, e.g.:

```
qa-07-response.json
execution-kafka-profiles-baseline.txt
review-2026-09-storage-guard.md
```

Date-stamp only where the date is the point — a baseline, or a run being compared against a later one.

## Status

Empty. The first entries will arrive with the first Execution and QA passes.
- [api-load-review-2026-09-18.md](api-load-review-2026-09-18.md) — every read endpoint timed at the 10k-row seed; the two that mattered, what changed, what needs a decision.
