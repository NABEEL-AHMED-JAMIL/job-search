# Reusable prompts

Six prompts, one per phase of the workflow. Paste the relevant one at the start of a session, or point a coding agent at the file.

| Prompt | Use it when |
|---|---|
| [discovery.md](discovery.md) | You need to understand an area before touching it |
| [grooming.md](grooming.md) | A feature is about to be worked on and needs to be made ready |
| [synthesis.md](synthesis.md) | You need to decide what actually has to change, and why |
| [execution.md](execution.md) | You are implementing one groomed feature |
| [qa.md](qa.md) | A feature is implemented and needs testing end to end |
| [code-review.md](code-review.md) | Code exists and needs a second pair of eyes |

## Why these are written the way they are

Every one of them makes the agent **look before it writes**, because the failure mode that costs the most time here is not a wrong edit — it is a confident answer built on an assumption nobody checked.

A few rules appear in more than one prompt because they have each already cost this project real time:

- **A green test suite is not evidence a rule is enforced.** A test can pass because an unstubbed mock refused the call, because the row it asserts about does not exist, or because the value it checks was already empty before the code ran. Every one of those has happened here. The fix is always the same: break the production rule on purpose and confirm the test goes red.
- **Run the project's own command.** `npx vitest` is not `ng test`; `mvn test` is not `run-e2e.sh`; the Kafka matrix cannot pass from the host at all. Each of those produced a screen of failures that had nothing to do with the code.
- **Verify the thing you claim, not a proxy for it.** A deploy script that prints success is not a deployed jar — compare the checksum.
- **`@PreAuthorize` is not repeatable.** A method-level annotation *replaces* the class-level one rather than adding to it.
- **A Hibernate `@Filter` does not apply to `findById`,** and silently does nothing on an entity that never declared it.

## House style for documents

Write for the engineer who arrives in six months with no memory of the conversation that produced the file:

- Say what is true, then where to see it. A claim with a path and a line number can be checked; a claim without one has to be trusted.
- Prefer a table when the content is a set of things with the same shape, prose when the content is a reason.
- Record **why**, not only what. The what is recoverable from the code; the why is not.
- When something is unknown, write that it is unknown and what you looked at. A confident guess is worse than an admitted gap.
