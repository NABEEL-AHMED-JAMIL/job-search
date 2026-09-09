# Grooming

One document per feature: `grooming/<feature>.md`. The name matches its row in [../discovery/features.md](../discovery/features.md).

Grooming is where a feature stops being a name on a list and becomes something somebody could pick up on a Monday and finish. The test of a good grooming document:

> Someone who has never seen this codebase could implement the feature from it, and would know when they were done.

Use [../prompts/grooming.md](../prompts/grooming.md).

## Required sections

1. **Purpose** — what it is for, in the user's words
2. **Existing behaviour** — what the code does today, with file paths. Both apps, where both have it
3. **Expected behaviour** — what it should do
4. **Frontend** — routes, components, forms, tables, dialogs, states
5. **Backend** — endpoints, services, the exact role each requires
6. **Database** — tables, columns, migrations
7. **Validation** — every rule, and whether it is enforced on the client, the server, or both
8. **Security** — who may do what, at all four layers
9. **Error handling** — what the user sees when each thing fails
10. **Dependencies** — features, services, infrastructure
11. **Acceptance criteria** — numbered, independently checkable
12. **Known issues** — defects that exist today, with evidence
13. **Missing** — what is absent, and what it would take

## Two rules that carry most of the weight

**Acceptance criteria must be checkable by someone who did not write them.** "Works correctly" is not a criterion. Name the actor, the action, and the observable result.

**Pair every refusal with a positive control.** A test that only asserts "this is refused" cannot tell a working rule from a broken fixture — both produce a refusal. State the allowed case on the same fixture alongside it.

## Status

Empty — Discovery is in progress. The feature list it produces determines the files that go here.
