# Prompt — QA

> Test one feature end to end, as a user would meet it. Findings go to `.ai/qa/<feature>.md`.

QA is not "run the suites" — Execution already did that. QA is the pass where somebody uses the feature, on both themes, at a narrow width, as each role, and writes down everything that is wrong including the things that are merely ugly.

## The prompt

```
You are doing QA on the feature: <feature>.

Read .ai/grooming/<feature>.md first — its acceptance criteria are your checklist,
and every one must be individually exercised and marked pass or fail.

Then go beyond the criteria. Work through the four groups below. Use the app: click
the buttons, submit the empty form, put a quote in the text field, request the other
tenant's record by id.

Write findings to .ai/qa/<feature>.md. For each:
  - What you did, precisely enough for someone to repeat it
  - What you expected
  - What happened
  - Severity: blocker / major / minor / cosmetic
  - Evidence: a screenshot, a response body, a log line

Rules:
- Report what you observed, not what you assume the code does.
- A cosmetic finding is still a finding. Write it down; let a human triage it.
- Do not fix anything during QA. Finding and fixing in one pass is how a finding
  gets quietly dropped when the fix turns out to be hard.
- If you could not test something, say so and say why. Untested is not passed.
```

## The four groups

**Functional** — create, read, update, delete; search, filters, sorting, pagination; permissions per role; validation; error handling. Include the empty case, the one-item case, and the many-items case.

**UI/UX** — alignment, spacing, typography, icons, colour; **dark and light mode**; responsive layout at a narrow width; loading, empty and error states. A screen with no empty state is a finding — most screens are empty on the first day a tenant uses them.

**Backend** — status codes, request validation, authentication, authorization, database behaviour, and any query that will be slow once a table is real.

**End to end** — `Login → open feature → create → verify → edit → verify → delete → verify`, as each role that should be able to do it, and as one that should not.

## Authorization is tested by attacking it

The frontend hiding a control proves nothing. For every rule, try to break it **at the API**, with a real token:

- Request another tenant's record **by id** — the list query being filtered does not mean the row is unreachable, because a Hibernate filter does not apply to `findById`.
- Call the endpoint as the role one step below the one it requires.
- Name a storage key belonging to another user: `1249/profile/avatar.png` as user 1248, and `12480/...` as user 1248, which is the same attack with a longer id.
- Send a token with no tenant claim at all. A null `tenant_id` means platform-owned, and a caller with no tenant must own nothing.

## Getting a refusal for the right reason

A refusal proves nothing until you know **which** refusal it is. `400 Unknown bucket` from a guard and `400 Unknown bucket. Add a storage connection for it first.` from an unconfigured environment are the same status code and completely different facts.

So: **match the message, not just the status**, and check that the same call succeeds for the role that should be allowed. If both the allowed and the refused case fail, the fixture is broken and neither result means anything.

## Recording a finding

> **QA-07 · major · Kafka profiles**
>
> **Did:** signed in as the Ajwa LLC tenant admin, opened Settings → Kafka, pressed *Test connection* on the "Ajwa SSL" profile.
> **Expected:** a success or a broker error naming the host.
> **Got:** `500 internal error`, no detail. Server log shows `Could not fetch MinIO object content` — the truststore object had been removed from the bucket, and the one failure the user could have fixed was the one they were told nothing about.
> **Evidence:** `process_app` log 14:22:31; response body in `.ai/reports/qa-07-response.json`.
