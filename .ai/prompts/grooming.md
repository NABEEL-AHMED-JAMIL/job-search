# Prompt — Grooming

> Make one feature ready to be worked on. One document per feature, at `.ai/grooming/<feature>.md`.

Grooming is where a feature stops being a name on a list and becomes something a person could pick up on a Monday morning and finish. The test of a good grooming document: **someone who has never seen this codebase could implement the feature from it, and would know when they were done.**

## The prompt

```
You are GROOMING the feature: <feature>.

Read the real code for this feature first — every file in .ai/discovery/features.md
for its row, on both the old frontend and the new one, and the backend endpoints it
calls. Do not write a line of the document before you have read the code.

Then write .ai/grooming/<feature>.md with these sections, in this order:

  1. Purpose            — what this feature is for, in the user's words, not the schema's
  2. Existing behaviour — what the code does TODAY. Cite files. Cover both the old app
                          and the new one where both have it.
  3. Expected behaviour — what it should do. Where this differs from today, say so.
  4. Frontend           — routes, components, forms, tables, dialogs, states
  5. Backend            — endpoints, services, the exact role each one requires
  6. Database           — tables, columns, migrations needed
  7. Validation         — every rule, and whether it is enforced on the client, the
                          server, or both. Client-only validation is a finding.
  8. Security           — who may do what, at all four layers: frontend guard,
                          controller annotation, service rule, data filter
  9. Error handling     — what the user sees when each thing fails
 10. Dependencies       — features, services and infrastructure this needs
 11. Acceptance criteria— numbered, each independently checkable
 12. Known issues       — defects that exist today, with evidence
 13. Missing            — what is absent, and what it would take

Rules:
- Acceptance criteria must be checkable by someone who did not write them. "Works
  correctly" is not a criterion. "A TENANT_USER who requests another user's avatar
  key receives 400 and the object is not returned" is.
- Every claim about current behaviour needs a file path.
- If you find a bug while reading, record it under Known issues with evidence. Do
  not fix it — this is grooming, and the fix belongs to Execution where it can be
  tested.
- Where the old app does something the new one does not, say precisely what is lost.
```

## Writing acceptance criteria that are worth having

Each criterion should name **the actor, the action, and the observable result**. Prefer the specific over the general, and cover refusals as carefully as successes — most of the defects found in this codebase have been on the refusal path, where nobody looks.

Good:

> 4. A `TENANT_ADMIN` of tenant A calling `GET /storageConnection.json/fetchAllConnections` receives only connections whose `tenant_id` is A. Platform-owned rows (`tenant_id` null) do not appear, including `etl-avatar` and `etl-bucket`.
>
> 5. The same call as a `PLATFORM_ADMIN` returns every connection, including both platform-owned rows.

Criterion 5 exists because a refusal that comes from the fixture being broken rather than from the rule looks exactly like a refusal that works. **Pair every "must be refused" with a positive control on the same fixture.**

Bad:

> 4. Tenant isolation works correctly.

## Known issues need evidence, not adjectives

Record what makes it a defect and how it can be seen:

> **The store password is dropped but the store path is kept.** `applyProfileDto`
> (`process/.../KafkaConnectionProfileServiceImpl.java:674`) nulls the three
> `ssl*PasswordEnc` columns when the protocol is not `SSL`/`SASL_SSL`, while writing
> the bucket and location back unconditionally. Reopening the profile shows
> "Keeping the truststore this profile was saved with" and the next connection
> fails at the handshake with no password for a store the row still names.

That entry tells the next person where to look, what to expect, and what the user sees — which is the whole job of the section.
