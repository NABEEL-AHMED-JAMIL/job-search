# Prompt — Execution

> Implement **one** groomed feature. Not two, and never "the whole application".

The rule that makes this phase work: **Implement → Test → Fix → Review → Retest**, per feature, before moving to the next one. A branch carrying three half-finished features cannot be reviewed, cannot be tested, and cannot be reverted.

## The prompt

```
You are EXECUTING the feature: <feature>.

Read first: .ai/grooming/<feature>.md and .ai/synthesis/<feature>.md, then the code
they point at. Follow the ordering in the synthesis document.

Work through, for this feature only:
   1. Backend / API
   2. Database migration, if the synthesis document calls for one
   3. Frontend
   4. Validation — server side always; client side as well, for the message
   5. Authorization — all four layers
   6. Error handling
   7. Loading / empty / error states
   8. Dark and light mode
   9. Responsive behaviour
  10. Tests: unit, API, integration, E2E as appropriate

Then: run the suites, fix what breaks, review your own diff, run them again.

Rules:
- Match the surrounding code. Read a neighbouring file before writing a new one:
  its naming, its comment density, its idiom. Code that reads as an import from
  another project is a cost even when it works.
- Every new rule needs a test that FAILS when the rule is removed. Verify that by
  actually removing it and watching the test go red, then put it back. A test you
  have not seen fail is a test you have not written.
- Do not fix unrelated things you notice. Record them in the grooming document's
  Known issues and keep going.
- Report honestly. If a suite fails, say so and show the output. If you skipped
  something, say what and why.
```

## Run the project's own commands

Every one of these has been got wrong at least once, and each cost a round of false failures:

| What | Command | Note |
|---|---|---|
| Frontend tests | `npx ng test --watch=false` | **Not** `npx vitest` — that skips the Angular compiler plugin and produces dozens of fake failures |
| Backend unit | `mvn -o test` | From `process/` |
| Backend E2E | `./run-e2e.sh` | Reads DB credentials **and** the encryption key from the running container |
| Kafka matrix | `./run-kafka-matrix.sh` | **Must** run in a container: every broker listener is advertised as `host.docker.internal`, which the host cannot resolve. From the host you get metadata timeouts that look nothing like the cause |
| Frontend dev server | the Browser pane / `.claude/launch.json` | Never a bare `npm start` in a shell |

Before concluding that a failure is a regression, **check that you ran the right command against a healthy stack.** A stale container, a missing environment variable or the wrong runner has been the answer more often than the code has.

## Authorization changes: check four layers

The frontend hiding a button is not enforcement. When a change touches who may do what, verify all four:

1. **Frontend guard** — the route is not reachable
2. **Controller** — `@PreAuthorize`, remembering it is **not repeatable**, so a method-level annotation *replaces* the class-level one
3. **Service** — the ownership rule, via `TenantOwnership` rather than a private copy that will drift
4. **Data** — the Hibernate filter, remembering it does **not** apply to `findById`

Then write the test as a **request**, not a service call — a rule can be perfect in the service and undone by the annotation above it, and only a request finds that out.

## Tests that pass for the wrong reason

This is the failure mode that has cost this project the most, because it is invisible in a green run. Three shapes, all of which have occurred here:

- **The unstubbed mock.** A test asserted a download was refused. The refusal came from a mock nobody had stubbed, not from the guard — it kept passing with the guard deleted.
- **The row that does not exist.** A test asserted a response did *not* contain the platform's profile. No fixture ever created that profile, so the assertion held on an empty list, and would have held with the scoping removed.
- **The value that was already empty.** A test asserted a field was falsy after a refused upload. The field was `''` before the code ran.

The defence is the same in every case, and it is cheap:

> **Break the rule on purpose. Watch the test go red. Put it back.**

And where a test asserts a refusal, **add a positive control on the same fixture** — otherwise a refusal caused by the fixture failing to resolve is indistinguishable from the rule working.

## Before you call it done

- [ ] All three suites green, run with the commands above
- [ ] Every new rule has a test you have seen fail
- [ ] Every acceptance criterion in the grooming document is met, checked one by one
- [ ] Both themes and a narrow viewport actually looked at, not assumed
- [ ] The diff read start to finish, as a reviewer would
- [ ] Anything left undone stated plainly, with the reason
