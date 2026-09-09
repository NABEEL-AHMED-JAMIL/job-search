> **ARCHIVED — the feature this document plans no longer exists.** This is `synthesis/dynamic-forms.md` as it stood
> before 2026-09-03, kept as a record of how dynamic forms worked and what was planned for it. The
> feature was removed whole that day — screens, routes, controller, service, entities — at the
> product owner's explicit call. Nothing below should be acted on; it describes a plan for a
> feature that was overridden by a "we don't need this" decision, not superseded by better
> information. See [README.md](README.md) and [`../discovery/features.md`](../discovery/features.md)
> §2 (row 13) for what actually happened.

---

# Synthesis -- Dynamic Forms

Companion to `.ai/grooming/dynamic-forms.md`. Every claim here is cited there; paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

Dynamic Forms crossed further than most `partial` features and broke in a quieter way. The builder,
the list, the submissions view, deletion and sharing all made it, and several of them improved
sharply: the share "link" is now a real public page instead of a copied JSON endpoint
(`features/forms/dynamic-forms.ts:137-145` against `_models/dynamic-form.model.ts:159-163`), the list
finally distinguishes a failed load from an empty one, and the route is properly gated on
`TENANT_ADMIN` where the old app showed the menu item to everybody
(`scheduler1/src/app/app.component.html:34`). What did not cross is the submission half: editing a
submission, a linkable per-submission page, and submission-level sharing are all gone, and there is
no longer any way to fill a form without leaving the console. Sitting underneath both halves are
three **silent data incompatibilities** -- the new app reads `field_options` as newline-separated
text where the old app wrote JSON label/value pairs, it treats `checkbox` as a single boolean where
the old app treated it as a multi-option group, and it reads submission payloads as a flat map where
the old app nested answers under their section. None of the three produces an error; they produce
empty dropdowns, "ticked" boxes and blank answers on data that is perfectly intact in the database.
Beside them sits a validation story that is worse than it was: the email check is gone, patterns
went from anchored to substring, optional fields are checked not at all, and the server has never
validated a submission against its form in either application. Two tenancy defects complete the
picture: `fetchAllForms` is the one read path in the service with no ownership check, and a platform
admin gets every tenant's forms in a list with no column saying whose they are. The work is:
settle the data shape and migrate, close or build the open submission-share endpoint, put validation
on the server, restore the two submission capabilities that are worth restoring, and write the first
test this feature has ever had.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | Old app writes `field_options` as JSON `[{label,value}]` (`cu-dynamic-form.component.ts:245`); new app reads it as newline-separated text (`features/forms/dynamic-form.model.ts:86-88`) | A form built in either app reads correctly in the other | An old `select` renders as one option whose text is raw JSON; a new one opens empty in the old app | Tolerant reader in `optionsOf` plus a one-off migration of the column | **M** | **High** -- silent, and the wrong answer stores JSON as a user's answer |
| 2 | `checkbox` is option-based with an array answer in the old app (`_models/dynamic-form.model.ts:42-45`); a single boolean in the new one (`dynamic-form.model.ts:67`, `form-renderer.ts:159`) | One meaning per type | Old options are dropped on save (`dynamic-form-dialog.ts:293`); old array answers all display as "ticked" | Migrate old multi-option `checkbox` fields to `multi-select`; keep `checkbox` boolean | **M** | **High** -- destructive on save, and irreversible once saved |
| 3 | Old payloads nest answers under the preceding section (`fill-dynamic-form.component.ts:205-223`); new app reads a flat map (`form-renderer.ts:186`) | Every stored answer is readable | Every answer after a `section` reads as blank in the new app -- viewer, list summary and task mapping alike | Port `payloadValueFor` as a fallback reader; keep writing flat | **S** | **High** -- looks like data loss to a user |
| 4 | `updateSubmission` exists on the server (`DynamicFormServiceImpl.java:288-309`), called from nowhere in `scheduler1/next/src` | An administrator can correct a submission | A typo in an answer can only be fixed by deleting and re-collecting | Add an edit mode that seeds the renderer and PUTs; gate it on `TENANT_ADMIN` until submissions carry an author | **M** | Med -- the endpoint is `TENANT_USER` with no author, see 3.4 |
| 5 | `fetchSubmissionByUuid` is `permitAll` (`DynamicFormRestApi.java:191`, `SecurityConfig.java:44`) and called from nowhere | No unauthenticated read surface without a screen behind it | Any submission, including cleartext `password` answers, is readable by anyone holding a uuid; nothing in the product issues or revokes one | Remove the annotation and the matcher; revisit only with an expiring handle | **S** | Med -- removing a public endpoint could break an external integration nobody has told us about |
| 6 | `submitForm` validates only "form id present, payload non-empty, form owned" (`:262-286`) | Answers are checked against the definition they answer | Required, length, pattern and choice membership are decorations; any JSON map is accepted | Validate the payload against the form's `fields` in `submitForm` and `updateSubmission` | **M** | Med -- will reject payloads that the old app is still sending |
| 7 | `missingRequired` skips every non-mandatory field (`form-renderer.ts:197`), tests patterns unanchored (`:211`) and has no email check | Client checks match the old app's and the server's | An optional pattern field accepts anything; `\d{4}` accepts `pin 1234 ok`; `email` accepts `nonsense` | Rework `missingRequired`: run format checks on any answered field, anchor string patterns, add an email check | **S** | Low |
| 8 | `fetchAllForms` has no `isOwnedByCaller` check (`:139-152`) and `TenantFilterHelper` disables the filter for a null tenant (`TenantFilterHelper.java:28-33`) | A caller carrying no tenant owns nothing and sees nothing | A tenant-less `TENANT_ADMIN` lists every tenant's forms, `uuid`s included | Refuse a tenant-less non-platform caller in the service, and filter the result by ownership | **S** | Med -- the same shape of hole exists in other features; fix consistently |
| 9 | `DynamicFormDto` carries no tenant (`DynamicFormDto.java:15-31`); the table has no tenant column (`dynamic-forms.html:113-117`) | A platform admin can tell whose form a row is | Two tenants' "Onboarding" forms are indistinguishable, with Delete one menu item away | Add `tenantId`/`tenantName` to the DTO; render a Tenant column only for a platform admin | **S** | Low |
| 10 | No affordance to fill a form from the console (`dynamic-forms.html:150-165`) | An administrator can answer their own form | The only route in is to copy the link and paste it into another tab | Add "Open form" to the row menu, opening `/f/{uuid}` in a new tab | **S** | Low |
| 11 | No per-submission address; the panel renders `viewing()` from the list (`dynamic-forms.ts:73`) | One submission can be linked to and stepped through | Cannot send a colleague "look at this one"; no next/previous | Deep-link the panel via a query param and add prev/next over the loaded list | **S** | Low |
| 12 | `form-fill.ts:81` links to `/login?next=…`; login reads `returnUrl` (`login.ts:43`) | Signing in from a form link returns to the form | The visitor lands on the dashboard and has to find the link again | Rename the parameter | **S** | Low |
| 13 | `ThemeService` is never injected on `/f/:uuid` (`form-fill.ts`, `app.ts:1-15`) | The public page honours the stored theme | Opening a form link in a fresh tab always renders light | Inject the service in `FormFill` and add the toggle the other public pages have | **S** | Low |
| 14 | The 401 message promises typed answers are kept (`form-fill.ts:209-211`); nothing persists them (`:131`) | Either keep them or do not promise it | Someone loses a page of typing and was told they would not | Persist `answers` under the form uuid in `sessionStorage`; restore on load | **S** | Low |
| 15 | `fieldName` has no control validator (`dynamic-form-dialog.ts:225`) while `fieldLabel` does (`:226`) | A missing name is marked on the field | On a twelve-field form the toast does not say which row is wrong | Add `Validators.required` and let `Field` render it | **S** | Low |
| 16 | Nothing validates that `pattern` compiles; `new RegExp` runs unguarded at submit (`form-renderer.ts:211`) | A bad pattern is refused where it is typed | A saved form's Submit button throws for every visitor | Validate in `validateField` and on the server; wrap the runtime call | **S** | Med -- breaks the public page, which is the least supervised screen |
| 17 | A `select` with an empty Choices box saves; the old app refused (`cu-dynamic-form.component.ts:231-234`) | A choice field has choices | A dropdown with nothing in it reaches the public page | Restore the check in `validateForm` and add it server-side | **S** | Low |
| 18 | The submissions panel toasts and empties on failure (`dynamic-forms.ts:161-164`); a failed `withFields` renders every row as "(no answers)" (`:96-104, 152`) | The panel has the states the list above it has | A failed load is indistinguishable from a form nobody answered | Give the panel its own loading/error/empty states with retry | **S** | Low |
| 19 | `copyLink` toasts success without awaiting `copyText` (`dynamic-forms.ts:143-144`) | The message matches what happened | The user is told the link is copied when it is not | Await the boolean and branch | **S** | Low |
| 20 | `fetchAllForms` saves rows to backfill `uuid` (`:146, 180-186`), stamping `updated_by` (`AuditListener.java:41-51`) | Reading a list does not rewrite the audit trail | "Updated by" names whoever opened the list | Backfill once in a migration; drop `ensureUuid` from the read path | **S** | Low |
| 21 | `dynamic_form_submission` has no `created_by`; the entity is not `Audited` | Every answer has an author | No per-author rule is possible, no "submitted by" column, no "Only mine" on submissions | Migration plus `Audited` + `@EntityListeners` on the entity | **S** | Low -- but it gates row 4 |
| 22 | `dynamic_form_submission.dynamic_form_id` is unindexed; `dynamic_form_field.dynamic_form_id` has neither FK nor index (`V14__add_remaining_fk_constraints.sql:11`, `V18__foreign_key_indexes.sql`) | Both join columns are constrained and indexed like their peers | Every submissions-panel open is a sequential scan; orphan field rows are possible | One migration adding two indexes and one FK | **S** | Low |
| 23 | No test anywhere except one route assertion (`auth.guard.spec.ts:132-144`) | The rules that matter are held by tests | Every change to fifteen endpoints and a four-layer tenancy model is verified by hand | Unit tests for the pure functions; a server-side ownership matrix | **M** | Low, and it is what makes everything above safe |

---

## 3. Solution detail

### 3.1 Rows 1--3: the data incompatibilities

These are one piece of work with three parts, and they must go first because every day the new app
is used on old data it writes more of the wrong thing.

**Row 1 -- `field_options`.** The change is in `optionsOf`
(`features/forms/dynamic-form.model.ts:86-88`) and in whatever writes the column
(`dynamic-form-dialog.ts:293`). Make the reader tolerant: attempt `JSON.parse`, and if the result is
an array of objects carrying `label`/`value`, use it; otherwise fall back to the newline split.
Then run a one-off migration converting stored JSON into the newline form, so that the tolerant
reader is a safety net rather than the mechanism.

The alternative I rejected was migrating only, with no tolerant reader. It is cleaner and it is
wrong here, because the old application is still deployed and still writing JSON into the same
column (`cu-dynamic-form.component.ts:245`). A migration alone fixes the rows that exist on the day
it runs and nothing written afterwards. The tolerant reader costs about eight lines and removes the
deployment ordering constraint entirely.

I also rejected the reverse -- teaching the new app to *write* JSON label/value pairs. It would
restore two-way compatibility at the cost of keeping a richer format than the new UI exposes: the
dialog collects one string per line and has no label/value distinction to offer
(`dynamic-form-dialog.ts:117-122`). Writing `{"label":"CSV","value":"CSV"}` for every choice is a
lie about how much the new builder knows.

**Row 2 -- `checkbox`.** The two readings cannot both be right, and the new one is the better one:
`checkbox` maps onto a single HTML checkbox, which is what the type name means everywhere else, and
`multi-select` already covers "choose several" (`form-renderer.ts:73-80`). So: keep the new meaning,
and **migrate every existing `checkbox` field that carries options into a `multi-select`**. That
preserves both the options and the array shape of the answers already stored, because a
`multi-select` answer is an array (`form-renderer.ts:180`) exactly as the old checkbox group's was
(`fill-dynamic-form.component.ts:211-213`).

The alternative -- restoring the multi-option checkbox group in the new renderer -- was rejected
because it forks the type into two meanings depending on whether `field_options` happens to be
populated, and every downstream reader (`summaryOf`, the task mapping, `missingRequired`) would have
to make the same guess. One migration is cheaper than three permanent conditionals.

Until the migration runs, the destructive part must stop: `dynamic-form-dialog.ts:293` drops
`fieldOptions` for any type outside `CHOICE_TYPES`, so merely opening an old checkbox field and
saving the form erases its options. Preserving an unrecognised `fieldOptions` rather than nulling it
is a one-line change and should land immediately, ahead of the rest.

**Row 3 -- section nesting.** Keep writing flat payloads: the flat map is simpler, and the sections
are presentation, not structure -- the renderer already draws them as headings that collect nothing
(`form-renderer.ts:37-46`). Add a **read-side fallback** shaped like `payloadValueFor`
(`_models/dynamic-form.model.ts:120-130`): look for `payload[fieldName]`, and if it is absent, look
under the `fieldName` of the nearest preceding `section`. One function, used by `FormRenderer.valueOf`
(`form-renderer.ts:176-182`), `summaryOf` (`dynamic-forms.ts:205`) and the task mapping
(`submission-to-task-dialog.ts:181`).

I rejected migrating the payloads themselves. `payload` is free-form text
(`DynamicFormSubmission.java:44-45`) whose shape depends on the field list at the time it was
written, and a field can have been renamed or deleted since. Flattening it in SQL is a rewrite of
user data based on a guess about a definition that may have moved. A reader that falls back costs
nothing and is reversible.

### 3.2 Rows 6 and 7: validation

Row 7 is the client and is straightforward: in `missingRequired` (`form-renderer.ts:193-217`), stop
returning early for non-mandatory fields -- skip the *emptiness* check for them but still run
length, pattern and email once an answer is present. Anchor a string pattern the way
`Validators.pattern` does (`scheduler1/node_modules/@angular/forms/fesm2015/forms.js:1358-1373`), so
a form written against the old app keeps meaning what it meant. Add the email check the old app had
(`fill-dynamic-form.component.ts:137-139`).

Row 6 is the server and is the one that matters. `submitForm` and `updateSubmission` already hold
the owning `DynamicForm` (`DynamicFormServiceImpl.java:272-276, 298-302`), and it carries its
`fields` (`DynamicForm.java:80-83`), so the definition is in hand at exactly the moment the payload
arrives. Add a `validateSubmission(form, payload)` beside the existing `validateField`
(`:386-397`) checking: every mandatory non-section field has a non-empty answer; string answers
respect `min_length`/`max_length`; string answers match an anchored `pattern`; an answer to a choice
field is one of that field's declared options; and -- separately, as a warning rather than a
rejection -- no key in the payload matches no field.

Two decisions inside that. First, **anchor the pattern on the server too**, so the client and server
agree; an unanchored server rule would accept what the client refuses and make the client look
broken. Second, **reject unknown keys or not?** Recommendation: do not reject, at least initially.
The old application nests answers under sections, so every old-shaped payload has keys that match no
field name, and a strict rule would break the old app's submit path on day one. Log and store.

I rejected doing this validation only on the client and calling the server's silence acceptable. The
grooming document's section 7 lists nine rules that live in the browser and nowhere else; a form
whose promises are enforced only by the page that renders it is not a form, it is a suggestion.

### 3.3 Rows 5, 8 and 9: the security work

**Row 8** is the smallest and the most important. In `fetchAllForms`
(`DynamicFormServiceImpl.java:139-152`), refuse outright when `TenantContext.getTenantId()` is null
and the caller is not a platform admin -- the reading `TenantOwnership` already documents
(`TenantOwnership.java:9-23`) -- and additionally filter the returned list through
`isOwnedByCaller`, so the result does not depend on whether the Hibernate filter was switched on.
Every other read in the class already does the second half; this is the one that does not.

I rejected changing `TenantFilterHelper` instead. Its behaviour for a null tenant is shared by every
feature in the platform (`TenantFilterHelper.java:28-33`), and it is right for a platform admin. The
per-service ownership check is the layer that is supposed to catch this, and here it is simply
missing.

**Row 9.** Add `tenantId` and a resolved `tenantName` to `DynamicFormDto` and populate them in
`getDynamicFormDto` (`:399-414`); render a Tenant column in `dynamic-forms.html` behind
`auth.isPlatformAdmin()`. Not behind a filter toggle -- the point is that the platform admin cannot
*avoid* seeing whose row it is before pressing Delete.

**Row 5.** Delete `@PreAuthorize("permitAll()")` from `fetchSubmissionByUuid`
(`DynamicFormRestApi.java:191`) and drop the path from the matcher (`SecurityConfig.java:44`), so it
falls back to the class-level `TENANT_ADMIN`. The endpoint then still works for the people who
should have it, and stops being an unauthenticated read of other people's answers.

The alternative -- build the submission-sharing UI the old app had and keep the endpoint open -- is
the one I would choose if anyone were asking for the feature. Nobody is: `fetchSubmissionByUuid`
appears nowhere in `scheduler1/next/src`, and its old callers
(`view-dynamic-form-submission.component.ts:141-169`) copied a raw API URL rather than a page.
Rebuilding it properly means an expiring, revocable handle, which is a feature, not a fix. Close it
now; open a considered version later if it is asked for. Note the risk honestly: an integration
outside this repository may be polling that URL, and nothing in the codebase would tell us.

### 3.4 Rows 4, 11 and 21: the submission half

**Row 21 first.** Add `created_by`/`updated_by` to `dynamic_form_submission`, make the entity
`Audited` with `@EntityListeners(AuditListener.class)` as `DynamicForm` already is
(`DynamicForm.java:28-40`). This is small and it unblocks everything else: it is what lets
`updateSubmission` ask "is this yours?" instead of only "is this your tenant's?"

**Row 4** then becomes safe. Restore editing as a mode on the fill page -- seed `answers` from the
existing payload, PUT `updateSubmission` instead of POSTing `submitForm`, which is exactly the shape
`fill-dynamic-form.component.ts:241-247` used. The authorisation rule to add in
`updateSubmission` (`DynamicFormServiceImpl.java:288-309`): a `TENANT_ADMIN` of the owning tenant may
edit any submission; a `TENANT_USER` may edit only one they created. Until `created_by` is populated
for historical rows, treat a null author as admin-only.

I rejected restoring editing without row 21. The endpoint as it stands is `TENANT_USER` and checks
only tenant ownership (`:300`), so shipping a UI for it hands every tenant user the ability to
rewrite anyone's answers -- which is what the old application did, and is not a reason to do it
again.

**Row 11** is deliberately the cheap version: a `?submission=<id>` query parameter that selects a row
in the existing panel, plus previous/next over the loaded list. That gives back the linkable address
and the sibling walk (`view-dynamic-form-submission.component.ts:101-117`) without rebuilding a page
whose only other content is a renderer the panel already shows. `fetchSubmissionBySubmissionId`
(`:358-371`) exists if a direct read is ever wanted; the panel does not need it, because it has the
list.

### 3.5 Row 23: tests

Three tiers, in this order. **Pure functions first**, because they need no framework and cover the
riskiest logic: `optionsOf` against both option formats, the new section-aware payload reader,
`missingRequired` for optional-field format checks and anchored patterns, and `validateForm` for
duplicate names and empty choice lists. These sit beside the existing specs under
`features/forms/`, of which there are currently none.

**Server-side ownership second.** The fixture set in the grooming document's section 11 is exactly
the matrix: four actors against fifteen endpoints, every refusal paired with a positive control on
the same fixture. `process/src/test/java/process/security/TenantOwnershipTest.java` is the pattern to
follow, and there is not a single Dynamic Forms test in the whole 71-file suite today.

**Route and guard assertions last**, because one already exists
(`auth.guard.spec.ts:132-144`) and it is the least likely thing to regress.

---

## 4. Ordering

**Stop the bleeding (first, and independently deployable).** Preserve an unrecognised `fieldOptions`
on save rather than nulling it (`dynamic-form-dialog.ts:293`). One line. Every day without it,
another old `checkbox` field loses its options the first time someone opens the form to change its
description. Nothing else depends on it and nothing can break because of it.

**Decide the data shape (blocks everything in the next step).** The two questions in section 6 --
what `checkbox` means, and whether the old application stays deployed -- decide the migrations. No
code should be written against a guess at either.

**Data compatibility (rows 1, 2, 3).** Tolerant `optionsOf`, the section-aware payload reader, and
the `checkbox` → `multi-select` migration. Unblocks honest testing of everything below, because
until this lands, any test using old-shaped data is testing the wrong thing.

**Tenancy and the open endpoint (rows 5, 8, 9).** Independent of the data work and of each other;
all three are small. Row 8 should not wait, because it is the one with no UI in front of it.

**Validation (rows 6, 7, 16, 17).** Server-side first, then the client, then the two authoring-time
checks. The order matters: writing the client checks first tempts everyone to declare the job done.
Row 16 (invalid regex) belongs here because the server check and the client check are the same
check.

**The submission half (rows 21, 4, 11).** Strictly in that order -- the `created_by` migration is a
prerequisite for a safe edit rule, and the edit rule is what makes restoring the UI defensible.

**Everything else (rows 10, 12--15, 18--20, 22).** Independent, small, and each one improves a
screen someone is looking at. Row 22 (the two indexes and the FK) can ride along with whichever
migration lands first.

**Tests (row 23) are not a phase.** The pure-function tests belong in the same commits as rows 1--3
and 7; the ownership matrix belongs with row 8.

---

## 5. Out of scope

- **Changing the old application.** Everything recorded about `scheduler1/src` is context for
  compatibility, not a work item. The one place this bites is `moveField`
  (`cu-dynamic-form.component.ts:324-352`), which can leave two fields sharing a `fieldOrder`; the
  new dialog re-indexes on save (`dynamic-form-dialog.ts:282`) and will heal any form it touches.
- **Paging and sorting on either list.** Neither application has ever had them, and the volumes do
  not demand them. Worth revisiting when a single form has thousands of submissions; the index in
  row 22 is the part of that work that is worth doing now.
- **New field types.** File upload is the obvious absence in a form builder, and it is a feature,
  not a migration gap. `ALLOWED_FIELD_TYPES` (`DynamicFormServiceImpl.java:41-45`) stays as it is.
- **Encrypting `password` answers at rest.** The right answer is probably to remove the `password`
  type altogether, since a form that collects credentials into a plain-text column is a bad idea
  however it is stored. Both are product decisions; the standing warning
  (`dynamic-form-dialog.ts:154-162`) and the masked list value (`dynamic-forms.ts:207-211`) are what
  we have and they stay.
- **Anonymous submission, unless section 6 Q1 says otherwise.** The server's own comment sets the
  price: a tenant resolved without a `TenantContext`, a rate limit, and a `SecurityConfig` matcher
  (`DynamicFormRestApi.java:129-138`). That is a piece of work in its own right.
- **Merging Dynamic Forms with Task Forms.** They sit next to each other in the navigation
  (`shell.ts:108-111`) and share nothing -- different tables, different endpoints, different
  purposes. Deliberately left apart.
- **A full audit trail on submissions.** Row 21 adds an author. Who read what, and when, is a
  platform concern and not this feature's.

---

## 6. Open questions

**Q1. Should answering a shared form require an account?**
Today the link opens for anyone and the submit is refused for everyone except a `TENANT_USER` of the
form's own tenant (`DynamicFormRestApi.java:139`, `DynamicFormServiceImpl.java:274`). Three options:
(a) leave it, and change the public page to say so honestly rather than offering a Sign in link that
will not help a stranger; (b) open `submitForm` to anonymous callers, resolving the tenant from the
form rather than from `TenantContext`, with a rate limit and the matcher the server's comment asks
for; (c) a per-form "accept answers from anyone" flag, defaulting off, with (b)'s machinery behind
it.

**Recommendation: (c).** The feature's whole purpose is collecting answers from people who do not
have accounts -- a share link that only colleagues can act on is an internal form with extra steps.
But making every form world-writable by default turns fifteen endpoints into an unauthenticated
write surface overnight. A flag keeps existing forms exactly as they are, makes the choice visible
at the moment someone shares a link, and gives the rate limiter a natural scope. If (c) is too much
for this round, do (a) properly -- the honest message costs nothing and today's page is misleading.

**Q2. What does `checkbox` mean?**
(a) A single boolean, as the new app has it (`dynamic-form.model.ts:67`); (b) a multi-option group,
as the old app had it (`_models/dynamic-form.model.ts:42-45`); (c) both, switched on whether
`field_options` is populated.

**Recommendation: (a), with a migration of existing multi-option `checkbox` fields to
`multi-select`.** It matches the control the name describes, `multi-select` already covers the other
case, and the migration preserves both the options and the array shape of every answer already
stored. (c) is the tempting one and the one to avoid: it forks the type permanently and every
downstream reader has to re-derive the guess.

**Q3. Tolerant reader, migration, or both, for `field_options`?**
**Recommendation: both.** Migrate so the stored data is in one format, and keep the tolerant reader
permanently. The reader is what makes the deployment order not matter and what protects against the
old application writing JSON again the day after the migration runs. If Q4 answers "the old app is
retired", the reader can be dropped a release later -- but not before.

**Q4. Does `scheduler1/src` stay deployed alongside `scheduler1/next`?**
This is not a Dynamic Forms decision, but it changes this feature's answer more than most: it decides
whether compatibility has to be two-way (rows 1--3) or only one-way, and whether row 6's server-side
validation can afford to reject old-shaped nested payloads.

**Recommendation: assume yes until told otherwise, and design for two-way.** The extra cost is the
tolerant reader and the section-aware fallback -- perhaps thirty lines between them. The cost of
assuming wrong in the other direction is a migration that has to be run twice and a week of "the
dropdown is empty" reports.

**Q5. Who may edit a submission?**
(a) Nobody -- leave the capability retired; (b) `TENANT_ADMIN` of the owning tenant only;
(c) the author plus a `TENANT_ADMIN`, which needs row 21 first; (d) any `TENANT_USER` in the tenant,
which is what the endpoint allows today (`DynamicFormRestApi.java:150`,
`DynamicFormServiceImpl.java:300`).

**Recommendation: (c), reached through (b).** Ship the admin-only rule with the `created_by`
migration in the same release, then allow authors once the column is populated. (d) is the status
quo of the endpoint and should be closed regardless of whether the UI comes back -- an endpoint that
lets any tenant user rewrite any answer is a defect whether or not a screen calls it.

**Q6. Do we close `fetchSubmissionByUuid` now, or wait?**
**Recommendation: close it now** (section 3.3), and announce it, because an integration outside this
repository could be using it and nothing in the code would tell us. The endpoint has no screen, no
expiry and no revocation, and it returns other people's answers to anyone holding a uuid. If the
announcement turns up a real consumer, that is the moment to build the expiring handle properly --
with a consumer to design it for.
