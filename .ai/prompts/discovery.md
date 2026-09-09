# Prompt — Discovery

> Understand the area completely before anything is changed. **Do not modify application code during Discovery.**

## The prompt

```
You are doing DISCOVERY on <area>. Do not change any application code.

Read the real code and write down what is actually there. Rules:

1. Every claim must be traceable. Cite paths relative to the workspace root, with
   line numbers for anything specific. A claim without a citation cannot be checked
   by the next person, so it is not worth writing.

2. Never invent. If you cannot verify something, write "not verified" and say what
   you looked at. An admitted gap is useful; a confident guess costs somebody a day.

3. Distinguish what the code DOES from what a comment or a README SAYS it does.
   Where they disagree, that disagreement is itself a finding — record both.

4. Look for what is missing as hard as you look for what is there: a route with no
   guard, a service with no test, a column nothing reads, a documented feature with
   no code behind it.

Cover, in this order:
  - What this area is and how it is built
  - Its entry points (routes / endpoints / topics / jobs), as a table
  - Its internal structure
  - Its dependencies, in and out
  - Cross-cutting behaviour: validation, authorization, error handling,
    loading / empty / error states, dark mode, responsive layout
  - Test coverage, naming exactly what is untested
  - Risks: anything broken, dead, undocumented or dangerous

Write it to .ai/discovery/<name>.md and report what you could not determine.
```

## What "discovered" means for this system

Take the answer down to the layer that actually decides, not the first layer that mentions the subject.

**Frontend** — routes, components, forms, tables, modals, navigation, the API calls each screen makes, validation, loading/empty/error states, dark/light mode, responsive behaviour.

**Backend** — controllers and their exact `@PreAuthorize`, services, repositories, entities and queries, authentication and authorization, background jobs, external integrations, error handling.

**Data** — tables, relationships, which rows are tenant-scoped and which are platform-owned (`tenant_id` null), which entities declare a Hibernate filter and which do not, which columns hold ciphertext.

**Infrastructure** — containers, ports, environment variables, how each part is started and verified.

## Traps that have already caught someone here

**Authorization is decided in four places, and they can disagree.** The frontend guard, the controller annotation, the service rule and the data-layer filter are four separate answers to the same question. Read all four before concluding what a role can do — the frontend hiding a button is not enforcement.

**A class-level `@PreAuthorize` is replaced, not combined, by a method-level one.** The annotation is not repeatable. A method that looks more permissive than its class *is* more permissive.

**A Hibernate `@Filter` does not apply to `findById`,** and it silently does nothing on an entity that never declared the `@FilterDef`. "It is filtered by tenant" is a claim about a specific query, never about an entity in general.

**A null `tenant_id` means platform-owned, not ownerless.** Comparing two tenant ids with `Objects.equals` makes a caller who has no tenant the owner of every platform row. That has been a real defect here more than once.

**Storage keys carry identity.** `kafka-secrets/{appUserId}/...` and `{appUserId}/profile/...` encode who owns the object, so a string-prefix comparison is an authorization decision — and `"12480/"` starts with `"1248"`.
