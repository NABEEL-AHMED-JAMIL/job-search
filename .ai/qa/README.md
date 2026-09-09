# QA

Findings from using the application, one file per feature: `qa/<feature>.md`.

QA runs **after** Execution has the suites green. Those suites prove the code does what its author expected; this phase is where somebody finds out what the author did not expect. The two do not substitute for each other.

Use [../prompts/qa.md](../prompts/qa.md) for the full method. The short version:

- The acceptance criteria in `grooming/<feature>.md` are the checklist. Every one gets exercised and marked.
- Then go past them: the empty list, the 500-row list, the quote in the text field, the other tenant's id in the URL.
- Both themes. A narrow viewport. Every role that should be able to do it, and one that should not.
- **Record, do not fix.** A finding fixed in the same pass is a finding that quietly disappears when the fix turns out to be hard.

## Severity

| | Meaning |
|---|---|
| **blocker** | Data loss, a security hole, or the main path is broken |
| **major** | Wrong behaviour a user will hit |
| **minor** | Wrong behaviour on an edge case |
| **cosmetic** | Visual or wording. Still worth writing down |

## Finding format

```markdown
### QA-nn · severity · feature

**Did:**       what you did, precisely enough to repeat
**Expected:**  what should have happened
**Got:**       what actually happened
**Evidence:**  screenshot, response body, or log line
```

Keep the numbering continuous across the whole project (`QA-01`, `QA-02`, …) so a finding can be referred to in a commit message without ambiguity.

## Status

| Pass | Date | Findings | Note |
|---|---|---|---|
| [source-tasks.md](source-tasks.md) | 2026-09-07 | `QA-01`–`QA-06` | The first pass recorded in this project. Scoped to the pipeline/Pipeline-Forms change, not the whole feature |
| [dashboard.md](dashboard.md) | 2026-09-07 | `QA-07`–`QA-23` | Both accounts, both themes, 375px |
| [source-jobs.md](source-jobs.md) | 2026-09-07 | `QA-24`–`QA-35` | Cut short by a live backend outage (`QA-32`); roughly three-quarters of its checklist is untested |
| [reports.md](reports.md) | 2026-09-08 | `QA-01`–`QA-13`, **file-local** | Two departures from the method, both stated in the document: findings were **fixed in the same pass**, and the numbering restarts at `QA-01`. Cite these as `reports/QA-nn` |
| [analytics-studio.md](analytics-studio.md) | 2026-09-08 | none issued | **Not a QA pass.** A verification record for Analytics Studio phase one: the author's own checks during the build, kept because they are the only evidence the feature has. No criteria were marked and no `QA-nn` spent; the continuous sequence still stands at `QA-35`, so a real pass on this feature starts at `QA-36` |
