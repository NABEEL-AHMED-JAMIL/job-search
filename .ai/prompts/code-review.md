# Prompt — Code review

> Review as the engineer who will be on call for this code, not as a linter.

A review that returns a list of style opinions has cost more than it saved. The findings worth writing are the ones where **you can name the input that produces the wrong output**.

## The prompt

```
You are REVIEWING <diff / files / feature>.

Read the code and the tests around it. For each finding, you must be able to state
a concrete failure: specific inputs or state, leading to a specific wrong result.
If you cannot, it is not a finding — drop it.

Report, most severe first:
  - What the defect is, in one sentence
  - Where: file and line
  - The failure scenario: these inputs → this wrong output
  - Why it happens
  - What you would do about it

Look for, in roughly this order of value:

  1. Correctness — wrong results, unhandled failures, races, resource leaks
  2. Authorization — the four layers, and whether the test would notice if one
     were removed
  3. Tests that pass for the wrong reason (see below — this is the highest-value
     category in this codebase)
  4. Half-states — a value cleared while its partner survives, an object written
     before the thing that makes it usable is computed
  5. Error paths — a fixable failure reported as an opaque 500
  6. Simplification — code that would be shorter and clearer, where the change is
     genuinely worth making
  7. Comments that no longer describe the code

Rules:
- Verify before reporting. Read the callers. A finding that turns out to be wrong
  costs the reader more than the finding would have saved.
- Say when you are unsure, and say what you checked.
- Do not report style unless it actually impedes reading.
```

## Tests that pass for the wrong reason

Give this its own pass. It is invisible in a green run, and every instance found here was found by asking one question of each test:

> **If I delete the rule this test is named after, does it go red?**

If you cannot answer that by reading, delete the rule and run it. Known shapes:

| Shape | How it hides | Real example from this repo |
|---|---|---|
| Unstubbed mock | Mockito returns `Optional.empty()` / `null`, which looks like a refusal | A download-refused test satisfied by a mock, not the guard |
| Fixture that does not exist | `doesNotContain("X")` holds because nothing ever created X | Two profile-visibility tests resting on a hand-made local row |
| Value already empty | The assertion held before the code ran | `expect(location).toBeFalsy()` on a control initialised to `''` |
| Mirrored logic | The test re-implements the rule and asserts against its copy | A guard test that never loaded the class it was named after — and the copy had drifted |
| Ambiguous refusal | Two different causes produce the same status | `400` from the guard vs `400` from an unconfigured bucket |

Two habits that close most of these: **assert the message, not only the status**, and **pair every refusal with a positive control on the same fixture.**

## Where the bodies are buried in this codebase

- **`@PreAuthorize` is not repeatable.** A method-level annotation replaces the class-level one.
- **A Hibernate `@Filter` does not apply to `findById`,** and no-ops silently on an entity that never declared it.
- **`Objects.equals(null, null)` is `true`.** Comparing tenant ids that way makes a tenant-less caller the owner of every platform row.
- **A sequence-backed `save()` does not insert.** The INSERT — and any constraint violation — arrives at **commit**, which is after a `@Transactional` method's own `try/catch` has returned.
- **Prefix comparisons on ids.** `"12480/"` starts with `"1248"`.
- **Encrypting an already-encrypted value.** `encrypt(ciphertext)` produces a store nothing can open; look for the `*Enc` passthrough fields.
- **Ordering around a secret.** Write the object *after* the password that opens it is safely computed, or a failure leaves an unopenable orphan.

## Severity

**Blocker** — data loss, a security hole, or a broken main path.
**Major** — wrong behaviour a user will hit, or a test that would not catch a regression it is named for.
**Minor** — wrong behaviour on an edge case, or a misleading comment.
**Cosmetic** — everything else. Report it, briefly, and let a human triage.
