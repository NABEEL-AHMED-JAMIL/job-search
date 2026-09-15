# `.ai/` — the engineering workflow for this workspace

**Discovery → Grooming → Synthesis → Execution → QA → Regression**

The golden rule: **nothing goes straight from a requirement to code.** A feature earns its way through the phases, and each phase leaves a document behind so the next person — or the next session — starts from evidence instead of from memory.

## Where to start

| I want to… | Go to |
|---|---|
| Understand the system | [discovery/application-inventory.md](discovery/application-inventory.md) |
| **Understand how it runs** — the path a request or a job run takes | [discovery/module-workflows.md](discovery/module-workflows.md) |
| See every feature and its status — migrated, partial, or built new | [discovery/features.md](discovery/features.md) |
| **Know what is already broken** | [discovery/risks.md](discovery/risks.md) — 46 ranked findings, 5 of them P0 |
| Pick up a specific feature | `grooming/<feature>.md`, then `synthesis/<feature>.md` |
| Know what to build next | [execution/README.md](execution/README.md) |
| Know what to test | [qa/README.md](qa/README.md) and [regression/regression.md](regression/regression.md) |
| Reuse a phase prompt | [prompts/](prompts/) |
| Read a superseded document | [old-scope/](old-scope/) |

## The phases

**Discovery** — understand the whole application without changing it. Done once, then kept current. Output: [discovery/](discovery/), including the [risk register](discovery/risks.md).

**Grooming** — make one feature ready: purpose, current and expected behaviour, requirements per layer, validation, security, acceptance criteria, known issues, what is missing. One document per feature.

**Synthesis** — decide what actually changes, as *current → expected → gap → solution*, with sizes, risks and an order. This is where the reasoning is kept, including the options that were rejected.

**Execution** — implement one groomed feature. `Implement → Test → Fix → Review → Retest`, then the next feature.

**QA** — use the feature as a user, as each role, on both themes, at a narrow width. Findings recorded, not silently fixed.

**Regression** — protect what already works. [regression/regression.md](regression/regression.md) is the standing checklist.

## Layout

```
Old-School/
├── scheduler1/          FRONTEND
│   ├── src/               old app (Angular, webpack + nginx)
│   └── next/              new app (Angular 22, Tailwind 4)   ← the rewrite
├── process/             BACKEND (Spring Boot, Java)
├── job-search/          Python Kafka workers   — out of scope this phase
└── .ai/
    ├── project.md         the specification
    ├── discovery/         what exists, and how it runs
    ├── grooming/          what each feature needs      (one per feature)
    ├── synthesis/         what changes and why         (one per feature)
    ├── execution/         the running order and progress
    ├── qa/                test findings
    ├── regression/        the standing checklist
    ├── reports/           run outputs, evidence, artefacts
    ├── prompts/           reusable prompts, one per phase
    └── old-scope/         superseded documents, kept rather than deleted
```

## Scope of the current phase

**In scope:** the `scheduler1/next` frontend and the `process` backend, feature by feature.

**Out of scope for now:** the `job-search` Python workers, and `my-user-redux-frontend` / `service-3`, which are separate projects in this workspace.

The old frontend (`scheduler1/src`) is in scope **as a source of truth**, not as something to change: it is the reference for what the rewrite still has to carry over. [discovery/features.md](discovery/features.md) records, per feature, whether it made the crossing.

**Not every feature in scope is a migration.** The scope is the two codebases, not the crossing between the old app and the new one. Since 2026-09-08 one feature has no old-app counterpart at all — `analytics-studio`, which was designed and built new in `scheduler1/next` and `process`, and so is in scope by exactly the same rule as everything else. For a module like that, "did it make the crossing" is not a question with an answer, and the phases mean what they say instead: grooming is what it has to do, synthesis is what to build and in what order, execution is what landed **and what did not**. Read its execution record with that in mind: what shipped on 2026-09-08 was a deliberate slice — phase one, read a file where it already lives — with phases two to five planned and not started. See [execution/README.md](execution/README.md).

## Conventions

- Feature names are kebab-case and stable. `grooming/<feature>.md` and `synthesis/<feature>.md` share the name with the row in `features.md`.
- Every claim about behaviour cites a file path; anything specific cites a line.
- Unknowns are written down as unknown, with what was checked.
- Superseded documents move to [old-scope/](old-scope/) rather than being deleted, so the reasoning behind an old decision survives it.
