> **ARCHIVED — the feature this document plans no longer exists.** This is `grooming/dynamic-forms.md` as it stood
> before 2026-09-03, kept as a record of how dynamic forms worked and what was planned for it. The
> feature was removed whole that day — screens, routes, controller, service, entities — at the
> product owner's explicit call. Nothing below should be acted on; it describes a plan for a
> feature that was overridden by a "we don't need this" decision, not superseded by better
> information. See [README.md](README.md) and [`../discovery/features.md`](../discovery/features.md)
> §2 (row 13) for what actually happened.

---

# Grooming -- Dynamic Forms

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

Migration status: **partial**. Section 2.1 is the boundary table -- exactly which capability crossed,
which did not, and which crossed in a shape that is *incompatible with the data the old app wrote*.
That last category is the one that costs a day if it is missed, and there are three rows in it.

---

## 1. Purpose

Dynamic Forms is the part of the console that lets an administrator ask people questions without
anybody writing code.

Somebody who runs pipelines needs information from other people -- the connection details for a
customer's SFTP drop, the column mapping for a new feed, the sign-off for a migration window. Today
that arrives as an email thread and gets retyped into a task. Dynamic Forms replaces the thread: an
administrator builds a form ("Feed onboarding": name, host, port, a dropdown of formats, a notes
box), shares one link, and the answers come back in one place, in one shape, attached to the form
that asked for them.

Two things follow from that and explain most of the design.

- **The link is the product.** A form is worth nothing if the person answering it has to be given a
  console account first. The share handle is an unguessable `uuid` on the form row
  (`process/src/main/java/process/model/pojo/DynamicForm.java:77`), and the endpoint that resolves
  it is one of only two in the whole API marked `permitAll()`
  (`process/src/main/java/process/api/DynamicFormRestApi.java:88-90`,
  `process/src/main/java/process/config/SecurityConfig.java:44`).
- **The answers are the point, and they are personal.** A submission holds whatever the form asked
  for. The controller says so in its own comment and gates the whole class on `TENANT_ADMIN`
  because of it (`DynamicFormRestApi.java:22-27`).

There is a third idea, and it is the only reason this feature touches the rest of the product: a
submission can be turned into a **source task's configuration**. Someone fills in "Feed onboarding",
an administrator opens the submission, presses one button, and the answers become the XML payload of
a real task (`scheduler1/next/src/app/features/forms/submission-to-task-dialog.ts:1-278`). That is
the only edge between Dynamic Forms and the pipeline, and it exists only in the new application.

Dynamic Forms is **not** Task Forms. `settings/forms` (Task Forms) describes what a *pipeline*
expects so that a task can be filled in instead of hand-written; it stores no data of its own.
`settings/dynamic-forms` (this feature) collects answers *from people* and stores every one of them.
Different tables, different endpoints, adjacent in the navigation
(`scheduler1/next/src/app/features/shell/shell.ts:108-111`) and easy to confuse. They must not be
merged.

---

## 2. Existing behaviour

### 2.1 The migration boundary, in one table

`--` in the New app column means the capability has no counterpart in `scheduler1/next/src`,
verified by searching the whole tree for the endpoint or the concept.

| Capability | Old app | New app | Crossed? |
|---|---|---|---|
| Form list, table | `scheduler1/src/app/_component/dynamic-form/dynamic-form-list/dynamic-form-list.component.html:36-113` | `scheduler1/next/src/app/features/forms/dynamic-forms.html:111-171` | yes |
| Form list, card view | -- | `dynamic-forms.html:59-109` | **new** |
| Summary tiles (forms / fields / active / empty) | -- | `dynamic-forms.html:20-30`, `dynamic-forms.ts:59-67` | **new** |
| Status filter (All / Active / Inactive) | `dynamic-form-list.component.ts:24-42` | `dynamic-forms.html:40-45` | yes |
| Free-text search | `dynamic-form-list.component.html:10-11` + `searchFilter` pipe | `dynamic-forms.ts:49-57` (name + description) | yes |
| "Only mine" filter | -- | `dynamic-forms.html:51`, `dynamic-forms.ts:239-245` | **new** |
| Created by / Updated by columns | -- | `dynamic-forms.html:137-142` | **new** |
| Loading / error / empty states | spinner + toast only (`dynamic-form-list.component.ts:53-67`) | `TableShell` (`dynamic-forms.html:32-37`) | **new** |
| Create a form | two-step: create, redirect to builder (`cu-dynamic-form.component.ts:111-129`) | one dialog (`dynamic-form-dialog.ts:305-370`) | yes, reshaped |
| Edit name / description / status | `cu-dynamic-form.component.ts:130-149` | `dynamic-form-dialog.ts:29-48` | yes |
| Delete a form (soft) | `dynamic-form-list.component.ts:103-127` | `dynamic-forms.ts:118-134` | yes |
| Add / edit / delete a field | modal per field (`cu-dynamic-form.component.ts:171-322`) | inline rows in the same dialog (`dynamic-form-dialog.ts:69-170`) | yes, reshaped |
| 17 field types | `scheduler1/src/app/_models/dynamic-form.model.ts:1-40` | `features/forms/dynamic-form.model.ts:51-55` | yes |
| **Option-based fields' option format** | JSON `[{label,value}]` (`cu-dynamic-form.component.ts:245`) | newline-separated plain strings (`dynamic-form.model.ts:86-88`) | **incompatible -- 2.5** |
| **`checkbox` = multi-select group** | `_models/dynamic-form.model.ts:42-45`, `fill-dynamic-form.component.ts:190-203` | `checkbox` is a single boolean (`dynamic-form.model.ts:67`, `form-renderer.ts:159`) | **incompatible -- 2.5** |
| Reorder fields | swap two `fieldOrder`s, two `updateField` calls (`cu-dynamic-form.component.ts:324-352`) | reorder the array, re-index every field on save (`dynamic-form-dialog.ts:256-263, 282`) | yes, better |
| Field width | free 1--12, validated (`cu-dynamic-form.component.ts:166`) | four choices: 12 / 6 / 4 / 3 (`dynamic-form-dialog.ts:108-113`) | narrowed |
| Live preview of the form being built | -- | `dynamic-form-dialog.ts:173-183` + `FormRenderer` | **new** |
| Duplicate `fieldName` refused | `cu-dynamic-form.component.ts:235-241` | `dynamic-form.model.ts:107-122` | yes |
| **Fill a form from inside the console** | route `dynamicForm/fill/:dynamicFormId` (`scheduler1/src/app/app.routing.ts:228-232`) | -- (only the public `/f/:uuid` page) | **no -- 2.4** |
| **Section-nested submission payload** | `fill-dynamic-form.component.ts:205-223` | flat map keyed by `fieldName` (`form-renderer.ts:184-189`) | **incompatible -- 2.5** |
| Public, sign-in-free form page | -- (old fill page is behind `AuthGuard`) | `scheduler1/next/src/app/app.routes.ts:41-45`, `form-fill.ts` | **new** |
| Share the form | copies a raw API URL (`_models/dynamic-form.model.ts:159-163`) | copies a real page URL `/f/{uuid}` (`dynamic-forms.ts:137-145`) | yes, better |
| Submissions list for one form | own page (`dynamic-form-submissions.component.html`) | inline panel under the table (`dynamic-forms.html:174-248`) | yes, reshaped |
| One-line preview of a submission | first two values (`dynamic-form-submissions.component.ts:148-161`) | first three, with `password` masked (`dynamic-forms.ts:199-216`) | yes, better |
| View one submission rendered as its form | `view-dynamic-form-submission.component.html` | read-only `FormRenderer` beside the list (`dynamic-forms.html:232-244`) | yes, reshaped |
| Delete a submission | `dynamic-form-submissions.component.ts:122-146` | `dynamic-forms.ts:174-196` | yes |
| **Edit an existing submission** | route `dynamicForm/fill/:dynamicFormId/edit/:submissionId`, `fill-dynamic-form.component.ts:73-98, 241-247` | -- `updateSubmission` appears nowhere in `scheduler1/next/src` | **no -- 2.4** |
| **Dedicated per-submission page + sibling switcher** | `view-dynamic-form-submission.component.ts:39-51, 111-117` | -- `fetchSubmissionBySubmissionId` appears nowhere in `scheduler1/next/src` | **no -- 2.4** |
| **Submission share URL / raw share token** | `_models/dynamic-form.model.ts:153-157`, `view-dynamic-form-submission.component.ts:141-169` | -- `fetchSubmissionByUuid` appears nowhere in `scheduler1/next/src` | **no -- 2.4** |
| Use a submission as task configuration | -- | `submission-to-task-dialog.ts:1-278` | **new** |
| Role gate on the entry point | none: nav link shown to everyone (`scheduler1/src/app/app.component.html:34`), route guarded only on being signed in (`scheduler1/src/app/_helpers/auth.guard.ts:16-22`) | `adminOnly` in the nav (`shell.ts:110`) and `roleGuard` with `minRole: 'TENANT_ADMIN'` on the route (`app.routes.ts:192-197`) | yes, and it fixes a defect |
| Dark mode | -- | token-based, `html.dark` (`scheduler1/next/src/styles.css:140-170`) -- **except on `/f/:uuid`, see 12.7** | new, incomplete |

### 2.2 The server, which both applications share unchanged

`process/src/main/java/process/api/DynamicFormRestApi.java` carries a class-level
`@PreAuthorize("hasRole('TENANT_ADMIN')")` (`:27`) with a comment explaining the reasoning and
explicitly noting that `@PreAuthorize` is not repeatable, so each override replaces it rather than
adding to it (`:22-26`). Four methods override it:

- `fetchFormByUuid` -- `permitAll()` (`:88`), also matched in `SecurityConfig.java:44`.
- `fetchSubmissionByUuid` -- `permitAll()` (`:191`), same matcher.
- `submitForm` -- `hasRole('TENANT_USER')` (`:139`), with a javadoc at `:129-138` saying why it is
  deliberately *not* anonymous: it reads the tenant from `TenantContext`, an anonymous caller has
  none, and an unauthenticated write endpoint would need a rate limit and its own matcher first.
- `updateSubmission` -- `hasRole('TENANT_USER')` (`:150`).

Everything else -- `addForm`, `updateForm`, `deleteForm`, `fetchAllForms`, `fetchFormByFormId`,
`addField`, `updateField`, `deleteField`, `deleteSubmission`, `fetchSubmissionsByFormId`,
`fetchSubmissionBySubmissionId` -- inherits `TENANT_ADMIN`. The role hierarchy
`ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN > ROLE_TENANT_USER`
(`process/src/main/java/process/config/MethodSecurityConfig.java:29`) means a platform admin passes
every one of them.

`DynamicFormServiceImpl` (468 lines) holds the rules. Every id-addressed path does the same two
things: `tenantFilterHelper.enableIfNeeded(entityManager)` and then an explicit ownership check,
because a Hibernate `@Filter` does not apply to `findById`. `DynamicForm` declares the filter
(`DynamicForm.java:24-25`); `DynamicFormField` and `DynamicFormSubmission` declare none and inherit
ownership through the parent form (`DynamicFormServiceImpl.java:249-260, 327-337`).

Three behaviours in the service are worth naming because the UI depends on them:

- **`deleteForm` is a soft delete.** It sets `Status.Delete` (`:134`). Fields and submissions stay
  in the database untouched. `fetchAllForms` excludes deleted rows server-side
  (`:143-144`).
- **`fetchAllForms` writes.** Any listed form with a blank `uuid` gets one generated and saved on
  the spot (`:146`, `ensureUuid` at `:180-186`), so legacy rows acquire a share handle the first
  time anyone opens the list.
- **`fetchFormByFormId` and `fetchFormByUuid` include fields; `fetchAllForms` does not** -- it sends
  only `totalFields` (`:399-414`). The new list therefore re-reads a form before editing it or
  rendering a submission against it (`dynamic-forms.ts:96-104`).

### 2.3 The old application, end to end

Seven routes, all guarded only by `AuthGuard`, which checks nothing but whether someone is signed in
(`scheduler1/src/app/app.routing.ts:213-247`, `scheduler1/src/app/_helpers/auth.guard.ts:16-22`).

**List** (`dynamic-form-list.component.ts`) -- fetches all forms, filters `Delete` out again on the
client (`:39-42`), offers a status filter and a search box, and per row: Fill, Edit fields, and a
dropdown with View submissions, Copy API link and Delete. "Copy API link" copies
`{apiUrl}/dynamicForm.json/fetchFormByUuid?uuid=…` (`_models/dynamic-form.model.ts:159-163`) -- a raw
JSON endpoint, not a page a human can fill in.

**Builder** (`cu-dynamic-form.component.ts`) -- `dynamicForm/new` shows name and description only;
saving redirects to `dynamicForm/edit/:id` (`:123`), where the fields table appears. Fields are
edited in a Bootstrap modal: 17 types, placeholder, default, mandatory, regex pattern, min/max
length, width 1--12 (`:166`), and an options editor for the four option-based types
(`_models/dynamic-form.model.ts:42-45`). A `section` field has its mandatory/placeholder/default/
pattern/length blanked on save (`:247-255`). Duplicate `fieldName` is refused client-side
(`:235-241`), as is an option-based field with no usable options (`:231-234`). Reordering swaps two
`fieldOrder` values and issues two sequential `updateField` calls (`:324-352`).

**Fill** (`fill-dynamic-form.component.ts`) -- builds a `FormGroup` at runtime from the field
definitions (`:111-130`), attaching `required`, `email`, `pattern`, `minLength` and `maxLength`
validators per field (`:132-150`). Checkbox groups live outside the form in `Set`s
(`:190-203`) and are checked separately on submit (`:231-237`). The payload nests each answer under
the `fieldName` of the nearest preceding `section` field (`:205-223`, `sectionKeyFor` at
`_models/dynamic-form.model.ts:104-118`). The same component handles editing: with a `submissionId`
in the route it loads the submission, seeds every control (`:73-98`), and submits through
`updateSubmission` instead of `submitForm` (`:241-247`).

**Submissions list** (`dynamic-form-submissions.component.ts`) -- table of submissions for one form
with a two-value preview line (`:148-161`), and per row Edit, View, Copy API link, Delete.

**One submission** (`view-dynamic-form-submission.component.ts`) -- renders the submission
field-by-field against the form definition, offers a sibling-submission switcher driven by
re-reading the whole list (`:101-117`), a share URL and a raw share token copy (`:141-169`), Edit
and Delete.

### 2.4 What did not cross

Three capabilities, all on the submission side. Each verified by searching the whole of
`scheduler1/next/src` for the endpoint name and getting zero matches.

| Lost | Old location | Evidence |
|---|---|---|
| Editing an existing submission | `app.routing.ts:233-237`, `fill-dynamic-form.component.ts:73-98, 241-247` | `updateSubmission` appears nowhere in `scheduler1/next/src`; `form-fill.ts:199-200` only ever calls `submitForm` |
| A dedicated per-submission page with a sibling switcher | `app.routing.ts:243-247`, `view-dynamic-form-submission.component.ts` | `fetchSubmissionBySubmissionId` appears nowhere in `scheduler1/next/src`; the new UI renders `viewing()` from the list it already has (`dynamic-forms.ts:73`, `dynamic-forms.html:233-238`) |
| Share URL and raw share token for one submission | `_models/dynamic-form.model.ts:153-157`, `view-dynamic-form-submission.component.ts:141-169` | `fetchSubmissionByUuid` appears nowhere in `scheduler1/next/src` -- while the endpoint is still `permitAll` on the server (`DynamicFormRestApi.java:191`) |

A fourth is easy to miss because nothing in the UI mentions it: **there is no way to fill a form
from inside the console.** The old app had a Fill button on every row
(`dynamic-form-list.component.html:65-68`). The new list's row menu has Edit form, Submissions, Copy
share link and Delete (`dynamic-forms.html:150-165`) -- an administrator wanting to answer their own
form has to copy the link and open it in another tab.

### 2.5 What crossed in a shape the old data does not fit

This is the category the boundary table flags and the one that will look like a bug report rather
than a migration note.

**Option format.** The old builder serialises options as JSON objects with separate label and value:
`JSON.stringify(this.optionsDraft.filter(o => o.label && o.value))`
(`cu-dynamic-form.component.ts:245`), read back with `JSON.parse` (`:215-224`) and resolved through
`optionLabelFor` (`_models/dynamic-form.model.ts:99-102`). The new app treats the same column as
newline-separated plain strings: `optionsOf` does
`(field.fieldOptions ?? '').split('\n').map(o => o.trim()).filter(Boolean)`
(`features/forms/dynamic-form.model.ts:86-88`). A select built in the old application therefore
renders in the new one as a **single option whose text is the raw JSON array**, and choosing it
stores that JSON string as the answer. The reverse is also true: a form built in the new app and
opened in the old one gets `JSON.parse` failing and falling back to zero options
(`cu-dynamic-form.component.ts:219-223`), i.e. an empty dropdown.

**`checkbox`.** The old app lists `checkbox` among the option-based types
(`_models/dynamic-form.model.ts:42-45`) and renders it as a group of tickboxes whose answer is an
array (`fill-dynamic-form.component.ts:190-203, 211-213`). The new app puts `checkbox` in
`BOOLEAN_TYPES` (`features/forms/dynamic-form.model.ts:67`) and renders a single tickbox whose
answer is `true`/`false` (`form-renderer.ts:94-101, 159`). An old checkbox field loses its options
entirely, and an old submission's array answer is read by `!!valueOf(field)` -- a non-empty array is
truthy, so every historical answer displays as "ticked" regardless of what was chosen.
`fieldOptions` is also not sent for `checkbox` on save (`dynamic-form-dialog.ts:293`), so
round-tripping an old checkbox field through the new editor **erases its options**.

**Section nesting.** The old payload nests: `{"contact": {"email": "a@b.c"}}`
(`fill-dynamic-form.component.ts:214-220`). The new payload is flat: `{"email": "a@b.c"}`
(`form-renderer.ts:186`). Nothing in the new app implements `payloadValueFor`
(`_models/dynamic-form.model.ts:120-130`), so for any old submission to a form that has a `section`
field, every answer after that section reads as absent -- blank in the read-only renderer
(`dynamic-forms.html:237-238`), skipped by `summaryOf` (`dynamic-forms.ts:205-206`), and skipped by
the submission-to-task mapping (`submission-to-task-dialog.ts:181-182`). The submissions are intact
in the database; the new app simply looks for the answers one level too high.

### 2.6 Tests

- **Backend: none.** `grep -rl -i dynamicform process/src/test` returns nothing across 71 test
  files. Every rule in `DynamicFormServiceImpl` -- ownership, the two public reads, the field-type
  allow-list -- is untested.
- **Frontend (new): one, and it is about the route.**
  `scheduler1/next/src/app/core/auth/auth.guard.spec.ts:132-144` asserts
  `settings/dynamic-forms` carries `minRole: 'TENANT_ADMIN'`. There is no spec anywhere under
  `features/forms/`; `validateForm`, `missingRequired`, `optionsOf` and the renderer are untested.
- **Frontend (old): none.**

---

## 3. Expected behaviour

Where this differs from section 2, it is marked **[differs]**.

1. An administrator builds a form: name, description, Active/Inactive, and an ordered list of
   fields with a type, a label, a storage name, an optional placeholder, default, width, and --
   where the type takes them -- choices, a length range and a pattern.
2. The builder shows what the form will actually look like while it is being built.
3. The administrator copies one link. Anyone with that link opens a real page and reads the form
   without an account.
4. Anyone who may answer the form can answer it from that page. **[differs]** Today only a
   `TENANT_USER` *of the form's own tenant* can submit: `submitForm` requires the role
   (`DynamicFormRestApi.java:139`) and the service additionally requires that the caller's tenant
   owns the form (`DynamicFormServiceImpl.java:274`). So the link opens for the world and submits
   for a handful of colleagues. Whichever way that is settled -- see the open questions in the
   synthesis -- the page must say the same thing the server will do, and today it does not: it
   offers "Sign in to submit" to a visitor who, if they belong to another tenant, will still be
   refused.
5. Answers are validated against the definition the administrator wrote -- required, length,
   pattern, and for a choice field, that the answer is one of the choices. **[differs]** None of
   this is enforced on the server (`DynamicFormServiceImpl.java:262-286` checks only that a form id
   is present, that the payload is non-empty, and that the form is owned), and on the client the
   length and pattern checks run **only on mandatory fields** (`form-renderer.ts:197`).
6. An administrator sees every submission to their forms, reads one rendered as the form that was
   answered, corrects one, and deletes one. **[differs]** Correcting is gone (2.4).
7. A form and its submissions are visible only inside the tenant that owns them. A platform admin
   may see across tenants, and when they do the screen must say which tenant each row belongs to.
   **[differs]** `DynamicFormDto` carries no tenant field at all and the table has no tenant column
   (`dynamic-forms.html:113-117`), so a platform admin gets every tenant's forms in one
   undifferentiated list.
8. Field definitions and submission payloads written by either application are readable by the
   other, for as long as both are deployed. **[differs]** Three incompatibilities, section 2.5.
9. Everything in the feature works in dark mode. **[differs]** The public form page does not
   (12.7).
10. Deleting a form is reversible-ish -- it stops accepting answers, keeps the submissions, and says
    so. This is what the code does today (`DynamicFormServiceImpl.java:134`,
    `dynamic-forms.ts:121`).

---

## 4. Frontend requirements

### 4.1 Routes

| Route | Component | Guard | Purpose |
|---|---|---|---|
| `settings/dynamic-forms` | `features/forms/dynamic-forms.ts` `DynamicForms` | `authGuard` + `roleGuard`, `minRole: 'TENANT_ADMIN'` (`app.routes.ts:192-197`) | The builder, the list, and the submissions panel |
| `f/:uuid` | `features/forms/form-fill.ts` `FormFill` | none -- outside the shell and outside `authGuard` (`app.routes.ts:41-45`) | The public form page |

Entry points: the Configuration group in the sidebar (`shell.ts:110`, `adminOnly: true`) and the
settings hub card (`features/settings/hub/settings-hub.ts:63`).

Required additions:

- A route for filling a form as a signed-in administrator without leaving the console, or an action
  on the list that opens `/f/{uuid}` in a new tab. Today neither exists (2.4).
- If submission editing is restored, either a route or a mode on the public page; the old shape was
  `dynamicForm/fill/:id/edit/:submissionId` (`app.routing.ts:233-237`).

### 4.2 Components

| Component | File | Responsibility |
|---|---|---|
| `DynamicForms` | `features/forms/dynamic-forms.ts` / `.html` | List, filters, tiles, submissions panel |
| `DynamicFormDialog` | `features/forms/dynamic-form-dialog.ts` | Create/edit a form and all its fields in one dialog, with a live preview |
| `FormRenderer` | `features/forms/form-renderer.ts` | The single renderer used by the preview, the public page and the read-only submission view (`:8-14`) |
| `FormFill` | `features/forms/form-fill.ts` | The public page |
| `SubmissionToTaskDialog` | `features/forms/submission-to-task-dialog.ts` | Turn a submission into a source task payload |
| `dynamic-form.model.ts` | same folder | Shapes, type lists, `optionsOf`, `validateField`, `validateForm` |

Keeping one renderer for all three callers is deliberate and should stay: a field cannot look one
way while being built and another while being filled in.

### 4.3 Forms and dialogs

- **Form dialog** (`dynamic-form-dialog.ts`) -- reactive, `size="wide"`. Form-level: name
  (required), status, description. A `FormArray` of field rows, each with move up / move down /
  remove, and per type: choices (`:117-122`), min/max length and pattern (`:124-139`), required and
  default (`:141-152`). A `password` field shows a standing warning that submissions are stored as
  plain text (`:154-162`). A footer count of inputs (`:186-188`) and a live preview (`:173-183`).
  **Required fix:** the `fieldName` control has no `Validators.required` (`:225`) while
  `fieldLabel` does (`:226`), so a missing name is reported as a toast from `validateForm` rather
  than inline on the row that is wrong.
- **Delete confirmations** -- `confirmWith` for both the form (`dynamic-forms.ts:119-124`) and a
  submission (`:175-180`). The form copy correctly states that submissions are kept.
- **Submission-to-task dialog** -- new/existing task, root tag, a mapping table, and a server-built
  XML preview (`submission-to-task-dialog.ts:36-148`). It must keep warning that updating an
  existing task replaces its whole configuration (`:93-99`).

### 4.4 Tables, list states and the submissions panel

- `TableShell` supplies loading, error-with-retry, and empty states
  (`shared/ui/data-table.ts:41-60`), with a filter-aware empty message
  (`dynamic-forms.html:34-36`). This is the single biggest improvement over the old screen, where a
  failed load and an empty result were indistinguishable.
- Table columns: Form, Fields, Share link, Created, Created by, Updated by, Status, actions
  (`dynamic-forms.html:113-117`). **A tenant column is required for a platform admin** (12.5).
- The submissions panel opens below the table for one form (`dynamic-forms.html:174-248`): a list on
  the left, the chosen submission rendered read-only on the right. Its three states are handled --
  loading (`:186-187`), empty with a nudge to share the link (`:188-192`), and populated.
- **Missing:** paging and sorting on both the form list and the submissions list. Neither the old
  nor the new screen has either; `fetchSubmissionsByFormId` returns every submission for a form
  (`DynamicFormServiceImpl.java:350-351`) and the panel renders all of them.

### 4.5 The public page

`form-fill.ts` renders four states: loading (`:30-34`), error with retry (`:35-45`), thank-you with
a reference uuid (`:46-60`), and the form (`:61-109`). It disables the submit button when the form
is inactive, has no inputs, or the visitor is not signed in (`:99`), and explains the last case in
place (`:75-84`).

Required fixes, all evidenced in section 12: the sign-in link uses the wrong query parameter
(12.6), the page never instantiates `ThemeService` so it ignores dark mode (12.7), and its promise
that answers survive signing in is not kept (12.8).

### 4.6 Dark and light mode

The console is token-based: every colour resolves through custom properties defined for light on
`:root` and redefined under `html.dark` (`scheduler1/next/src/styles.css:125-170`), toggled by
`ThemeService` (`core/theme.service.ts:6-21`). Both Dynamic Forms surfaces use tokens rather than
literal colours -- `bg-page`, `bg-inset`, `border-subtle`, `var(--text-muted)` -- so both would
theme correctly. The public page does not, only because nothing on it constructs the service (12.7).
Every other public page injects it: `landing.ts:206`, `docs.ts:266`,
`request-workspace.ts:120`, `shell.ts:34`.

### 4.7 Responsive behaviour

- The renderer's grid is the interesting part: each field's declared width becomes a CSS custom
  property, and the same field spans its declared columns on large, double that on medium, and the
  full row on small (`form-renderer.ts:18-31, 143-151`). A quarter-width field on a tablet would be
  about 160px, which is too narrow for an email address -- the comment says so and the breakpoints
  exist for that reason.
- The public page widens with the viewport rather than staying at reading width
  (`form-fill.ts:25-28`).
- The list's card grid is 1 / 2 / 3 columns (`dynamic-forms.html:60`); the submissions panel is one
  column below `lg` and two above (`:194`); the submissions table scrolls inside its own container
  (`:195`).

---

## 5. Backend requirements

No new endpoints are required by the migration itself. The table is the current surface, verified
against `DynamicFormRestApi.java`.

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/dynamicForm.json/addForm` | TENANT_ADMIN (class, `:27`) | Creates a form in the caller's tenant, Active, with a fresh `uuid` (`DynamicFormServiceImpl.java:78-94`) |
| PUT | `/dynamicForm.json/updateForm` | TENANT_ADMIN | Name, description and status of an owned form (`:96-120`) |
| DELETE | `/dynamicForm.json/deleteForm?dynamicFormId=` | TENANT_ADMIN | Soft delete: `Status.Delete` (`:122-137`) |
| GET | `/dynamicForm.json/fetchAllForms` | TENANT_ADMIN | Non-deleted forms, newest first, **without** fields; backfills a missing `uuid`; attaches author names (`:139-152`) |
| GET | `/dynamicForm.json/fetchFormByFormId?dynamicFormId=` | TENANT_ADMIN | One owned form **with** fields (`:154-166`) |
| GET | `/dynamicForm.json/fetchFormByUuid?uuid=` | **anonymous** `permitAll()` (`:88`) | One non-deleted form with fields, by share handle; no tenant check (`:168-178`) |
| POST | `/dynamicForm.json/addField?dynamicFormId=` | TENANT_ADMIN | Appends a field to an owned form; returns the form with fields (`:188-211`) |
| PUT | `/dynamicForm.json/updateField` | TENANT_ADMIN | Updates a field whose owning form the caller owns (`:213-233`) |
| DELETE | `/dynamicForm.json/deleteField?dynamicFormFieldId=` | TENANT_ADMIN | Hard delete of one field (`:235-247`) |
| POST | `/dynamicForm.json/submitForm` | **TENANT_USER** (`:139`) | Stores a submission against an owned form; generates its `uuid` (`:262-286`) |
| PUT | `/dynamicForm.json/updateSubmission` | **TENANT_USER** (`:150`) | Replaces a submission's payload (`:288-309`) |
| DELETE | `/dynamicForm.json/deleteSubmission?dynamicFormSubmissionId=` | TENANT_ADMIN | Hard delete of one submission (`:311-325`) |
| GET | `/dynamicForm.json/fetchSubmissionsByFormId?dynamicFormId=` | TENANT_ADMIN | Every submission for an owned form, newest first (`:339-356`) |
| GET | `/dynamicForm.json/fetchSubmissionBySubmissionId?dynamicFormSubmissionId=` | TENANT_ADMIN | One owned submission (`:358-371`) |
| GET | `/dynamicForm.json/fetchSubmissionByUuid?uuid=` | **anonymous** `permitAll()` (`:191`) | One submission by share handle, **no tenant check and no status check** (`:373-384`) |

Every response is the standard `ResponseDto` envelope; `status` is the real success signal, not the
HTTP code (`scheduler1/next/src/app/core/api/api.config.ts:8-13`). Errors from the service arrive as
HTTP 200 with `status: "ERROR"`; only an unhandled exception produces a 500
(`DynamicFormRestApi.java:42-45` and identically in every method).

Services: `DynamicFormService` / `DynamicFormServiceImpl` only. Collaborators: `TenantFilterHelper`,
`TenantContext`, `TenantOwnership`, `UserNameResolver` (`DynamicFormServiceImpl.java:22-24, 59`).
`TenantSeedService.backfillTenantIds` assigns any tenant-less form to the Default tenant at startup
(`process/src/main/java/process/model/service/impl/TenantSeedService.java:129-136`, repository query
at `DynamicFormRepository.java:19-22`).

Work the migration does require on the server:

- Server-side validation of a submission against its form definition (section 7).
- A tenant identifier on `DynamicFormDto` so the platform-admin view can be honest (12.5).
- An ownership check on `fetchAllForms` that does not rely solely on the Hibernate filter (12.1).
- A decision on `fetchSubmissionByUuid`, which is open to the world and used by nothing (12.2).

---

## 6. Database requirements

Three tables. All are created by Hibernate's `ddl-auto=update` in development
(`process/src/main/resources/application-dev.properties:87`) and validated in stage and production
(`application-stage.properties:90`, `application-prod.properties:92`); Liquibase carries only the
constraints, comments and audit columns.

**`dynamic_form`** (`DynamicForm.java`)

| Column | Type | Notes |
|---|---|---|
| `dynamic_form_id` | bigint PK | sequence `dynamic_form_Seq`, initial 1000 (`:43-55`) |
| `tenant_id` | bigint | FK to `tenant` (`V12__add_tenant_user_fk_constraints.sql:18`); indexed (`DynamicForm.java:18-20`); the Hibernate filter keys on it (`:24-25`) |
| `form_name` | varchar not null | `:64-65` |
| `description` | varchar | `:67-68` |
| `form_status` | varchar not null | `Status` enum as string: `Inactive`, `Active`, `Delete` (`:70-72`, `process/src/main/java/process/model/enums/Status.java:6`) |
| `date_created` | timestamp | `:74-75` |
| `uuid` | varchar unique | the share handle (`:77-78`) |
| `created_by`, `updated_by` | bigint | `V22__audit_columns.sql:24-25`; stamped by `AuditListener` (`process/src/main/java/process/model/pojo/AuditListener.java:23-51`) |

**`dynamic_form_field`** (`DynamicFormField.java`)

| Column | Type | Notes |
|---|---|---|
| `dynamic_form_field_id` | bigint PK | sequence `dynamic_form_field_Seq` (`:19-31`) |
| `dynamic_form_id` | bigint | written by the unidirectional `@JoinColumn` on the parent (`DynamicForm.java:80-83`). **No FK constraint and no index** -- absent from `V12`, `V14` and `V18__foreign_key_indexes.sql` |
| `field_order` | int not null | `@OrderBy("fieldOrder asc")` on the parent (`DynamicForm.java:82`) |
| `field_type` | varchar not null | one of 17, enforced only in the service (`DynamicFormServiceImpl.java:41-45`) |
| `field_name` | varchar not null | the key an answer is stored under |
| `field_label` | varchar not null | |
| `place_holder`, `default_value`, `pattern` | varchar | |
| `mandatory` | boolean | forced false for `section` (`DynamicFormServiceImpl.java:447`) |
| `min_length`, `max_length`, `field_width` | int | `field_width` defaults to 12 when absent (`:451`); no bounds check |
| `field_options` | text | **format is contested** -- see 2.5 |

**`dynamic_form_submission`** (`DynamicFormSubmission.java`)

| Column | Type | Notes |
|---|---|---|
| `dynamic_form_submission_id` | bigint PK | sequence `dynamic_form_submission_Seq` (`:20-32`) |
| `dynamic_form_id` | bigint not null | FK added in `V14__add_remaining_fk_constraints.sql:11`; **not indexed** -- `fetchSubmissionsByFormId` reads on it every time (`DynamicFormSubmissionRepository.java:15`) |
| `uuid` | varchar unique | public share handle (`:41-42`) |
| `payload` | text not null | Gson-serialised map (`DynamicFormServiceImpl.java:280`) |
| `date_created` | timestamp | `:47-48` |

Table comments exist for all three (`V17__table_descriptions.sql:66-73`).

Migrations needed:

1. **`created_by` on `dynamic_form_submission`.** The entity is not `Audited` and has no
   `@EntityListeners`, and `V22__audit_columns.sql:24-25` touches only `dynamic_form`. Nothing
   records who answered a form, which is why any tenant user can edit any submission (8.4) and why
   an "Only mine" filter is impossible on the submissions panel.
2. **Index on `dynamic_form_submission.dynamic_form_id`.** Every open of the submissions panel is a
   sequential scan today.
3. **FK and index on `dynamic_form_field.dynamic_form_id`**, matching what `V14` did for
   submissions.
4. **A data migration for `field_options` and for `checkbox`**, if the decision in the synthesis is
   to make old forms readable rather than to teach the new app both formats.
5. Optional: a `date_updated` on `dynamic_form_submission`, if submission editing is restored --
   today `updateSubmission` leaves `date_created` alone (`DynamicFormServiceImpl.java:303-305`) and
   there is no other timestamp, so an edited submission is indistinguishable from an untouched one.

---

## 7. Validation

| Rule | Client | Server | Verdict |
|---|---|---|---|
| Form name present | `dynamic-form-dialog.ts:210` and `dynamic-form.model.ts:108`; old at `cu-dynamic-form.component.ts:61` | `DynamicFormServiceImpl.java:80-82, 102-104` | both |
| Form id present on update | -- | `:99-101` | server |
| `fieldType` is one of the 17 | `dynamic-form.model.ts:95-97`; the picker offers only those (`dynamic-form-dialog.ts:61`) | `:387-389` against `ALLOWED_FIELD_TYPES` (`:41-45`) | both |
| `fieldName` present | `dynamic-form.model.ts:98` -- **but no control validator** (`dynamic-form-dialog.ts:225`), so it surfaces as a toast, not inline | `:390-392` | both, badly reported |
| `fieldLabel` present | `dynamic-form-dialog.ts:226` + `dynamic-form.model.ts:99` | `:393-395` | both |
| `fieldName` unique within a form | `dynamic-form.model.ts:110-119`; old at `cu-dynamic-form.component.ts:235-241` | **nothing** | **client only** |
| An option-based field has at least one option | old only, `cu-dynamic-form.component.ts:231-234` | nothing | **client only, and lost** -- the new dialog accepts a select with an empty Choices box |
| `fieldWidth` within 1--12 | old `Validators.min(1)/max(12)` (`:166`); new offers only 12/6/4/3 (`dynamic-form-dialog.ts:108-113`); the renderer clamps at display time (`form-renderer.ts:146`) | `:451` only defaults a null to 12 | **client only** |
| `minLength <= maxLength` | nowhere | nowhere | **absent** |
| `pattern` is a compilable regular expression | nowhere | nowhere | **absent** -- and it throws at submit time (12.4) |
| Submission has a form id and a non-empty payload | implicit | `:265-270`, `:291-296` | both |
| Required answers present | `form-renderer.ts:197-205`; old `Validators.required` (`fill-dynamic-form.component.ts:134-136`) plus a separate check for mandatory checkbox groups (`:231-237`) | **nothing** | **client only** |
| Answer length within min/max | `form-renderer.ts:206-210`, **mandatory fields only** | nothing | **client only, and narrowed** |
| Answer matches `pattern` | `form-renderer.ts:211-212`, **mandatory fields only, unanchored** | nothing | **client only, narrowed and changed** |
| Answer of an `email` field looks like an email | old `Validators.email` (`fill-dynamic-form.component.ts:137-139`); **new: nothing** | nothing | **lost entirely** |
| A choice answer is one of the declared choices | nowhere | nowhere | **absent in both** |
| Answer keys correspond to real fields | nowhere | nowhere | **absent** -- `submitForm` stores whatever map it is given (`:280`) |

Three findings follow from this table, and all three are worth stating plainly.

**The whole of submission validation is client-side.** `submitForm` performs no check against the
form definition. A `TENANT_USER` who can reach the endpoint can store any JSON object at all against
any form their tenant owns -- no required fields, keys that match nothing, values of any length.
Everything the builder promises about the shape of its answers is a decoration on the browser.

**The pattern check changed meaning.** The old app passes the stored pattern to
`Validators.pattern`, which anchors a string pattern with `^` and `$`
(verified in this repo at `scheduler1/node_modules/@angular/forms/fesm2015/forms.js:1358-1373`), so
`\d{4}` required a four-digit answer and nothing else. The new app calls
`new RegExp(field.pattern).test(answer)` (`form-renderer.ts:211`), which is a substring test, so
`\d{4}` now accepts `my pin is 1234 ok`. The same stored form has become more permissive without
anyone editing it.

**Optional fields are unvalidated.** `missingRequired` returns early for any field that is not
mandatory (`form-renderer.ts:197`), so an optional field's length range and pattern are never
applied. The old app attached those validators regardless of `mandatory`
(`fill-dynamic-form.component.ts:132-150`).

---

## 8. Security

Four layers, checked separately, because they do disagree.

### 8.1 Frontend guard

- New app: `settings/dynamic-forms` carries `data: { minRole: 'TENANT_ADMIN' }` and `roleGuard`
  (`app.routes.ts:192-197`), which compares against the same hierarchy the server uses
  (`core/auth/auth.guard.ts:33-42`). The nav entry and the hub card are `adminOnly` /
  role-filtered (`shell.ts:110`, `settings-hub.ts:63`). Asserted by
  `auth.guard.spec.ts:132-144`.
- New app: `f/:uuid` has **no guard at all** (`app.routes.ts:41-45`), deliberately, matching
  `permitAll()` on the endpoint behind it.
- Old app: `AuthGuard` only checks that someone is signed in
  (`scheduler1/src/app/_helpers/auth.guard.ts:16-22`), and the nav link is shown to every role
  (`scheduler1/src/app/app.component.html:34`). A `TENANT_USER` could open every Dynamic Forms
  screen in the old console and get nothing but 403s.
- The frontend hiding a control is not enforcement. It only decides what is worth rendering, which
  is what the guard's own comment says (`auth.guard.ts:31`).

### 8.2 Controller `@PreAuthorize`

Section 2.2 and the table in section 5. The single most important property: **`@PreAuthorize` is not
repeatable, so each of the four method-level annotations replaces the class-level `TENANT_ADMIN`
outright.** `submitForm` and `updateSubmission` are `TENANT_USER`, not "TENANT_ADMIN and also
TENANT_USER"; `fetchFormByUuid` and `fetchSubmissionByUuid` are open to everyone, not "open to
everyone who is also a tenant admin". The class comment states this explicitly
(`DynamicFormRestApi.java:22-26`).

### 8.3 Service rule

`TenantOwnership.isOwnedByCaller` (`process/src/main/java/process/security/TenantOwnership.java:35-41`):
a platform admin owns everything; anyone else must carry a tenant of their own and match exactly.
A **caller with no tenant owns nothing** and is refused rather than compared equal to the rows that
also have no tenant; and a row with a null `tenant_id` is **platform-owned, not ownerless**
(`TenantOwnership.java:9-23`).

Applied in `DynamicFormServiceImpl` at: `updateForm:107`, `deleteForm:130`, `fetchFormByFormId:162`,
`addField:200`, `updateField:226` (via `isFieldOwnedByCaller:249-260`), `deleteField:242` (same),
`submitForm:274`, `updateSubmission:300` (via `isSubmissionOwnedByCaller:327-337`),
`deleteSubmission:320` (same), `fetchSubmissionsByFormId:347`,
`fetchSubmissionBySubmissionId:367`.

Not applied at: `fetchAllForms` (relies on the filter alone -- 12.1), `fetchFormByUuid` and
`fetchSubmissionByUuid` (public by design).

### 8.4 Hibernate filter

`DynamicForm` declares `@Filter(name = "tenantFilter", condition = "tenant_id = :tenantId")`
(`DynamicForm.java:24-25`). It is the plain equality form, so **a null-tenant row satisfies it for
nobody** -- Dynamic Forms is not one of the shared catalogues that publish platform-owned rows to
every tenant (`TenantOwnership.java:19-23`).

Two properties matter and are easy to forget:

- **The filter does not apply to `findById`.** Every one of the twelve call sites above is there for
  that reason. `enableIfNeeded` is called first at `:105, 128, 142, 160, 198, 223, 241, 271, 297,
  317, 345, 364` and the ownership check second.
- **`DynamicFormField` and `DynamicFormSubmission` declare no filter at all**, so it silently
  no-ops on them. Their protection is entirely the parent-form lookup in `isFieldOwnedByCaller` and
  `isSubmissionOwnedByCaller`. Those two methods are the only thing standing between a submission
  and another tenant.

`TenantFilterHelper.enableIfNeeded` **disables** the filter when the caller's tenant id is null or
the caller is a platform admin (`TenantFilterHelper.java:28-33`). For a platform admin that is
correct. For a tenant-less non-platform caller it is the hole described in 12.1.

### 8.5 Who may do what

| Actor | May | May not |
|---|---|---|
| Anonymous (link only) | Read any form by `uuid`, including all its field definitions, whatever its status short of `Delete`; read **any submission** by `uuid` | Create, edit or delete anything; list forms; submit |
| `TENANT_USER` of the owning tenant | Submit an answer to their tenant's form; edit **any** submission in their tenant (not just their own) | List, read, build or delete forms; list or delete submissions |
| `TENANT_USER` of another tenant | Read the form through the share link | Submit -- `submitForm` requires the caller's tenant to own the form (`:274`) |
| `TENANT_ADMIN` of the owning tenant | Everything on their own tenant's forms, fields and submissions | Touch another tenant's rows -- refused as "not found" |
| `TENANT_ADMIN` of another tenant | Nothing on those forms through the id-addressed endpoints; still reads the form and any submission through the two public uuid endpoints, like anyone else | |
| `PLATFORM_ADMIN` | Everything, across every tenant, with the filter disabled | -- |

Three security observations to carry into execution:

- **A submission is editable by anyone in the tenant.** `updateSubmission` is `TENANT_USER`
  (`:150`) and checks only tenant ownership of the parent form (`:300`). There is no author on a
  submission row, so there is no finer check available. The old app exposed this through a UI; the
  new app does not call the endpoint at all, which is concealment rather than a fix.
- **`fetchSubmissionByUuid` is a world-readable window onto answers.** No tenant check, no status
  check, no expiry (`:373-384`). It is still routed and still `permitAll`
  (`SecurityConfig.java:44`), and the new frontend never generates such a link -- so the surface
  exists with nobody watching it.
- **`password` fields are stored and returned in clear text.** `submitForm` serialises the payload
  as-is (`:280`); the read paths return it as-is. The new builder warns about this at the point of
  authoring (`dynamic-form-dialog.ts:154-162`) and masks the value in the submissions list
  (`dynamic-forms.ts:207-211`) -- but the read-only renderer beside it uses
  `[type]="inputType(field)"` (`form-renderer.ts:103-104`), which for `password` is a masked input,
  while `fetchSubmissionByUuid` returns the plain value to anyone with the uuid.

---

## 9. Error handling

| Failure | What the user sees | Where |
|---|---|---|
| Form list fails to load | The card shows an alert icon, the server's message, and a "Try again" button | `TableShell` (`shared/ui/data-table.ts:46-54`), wired at `dynamic-forms.html:32-37` and `dynamic-forms.ts:88-91` |
| Form list is empty, no filters | "No forms yet. Create one to start collecting answers." | `dynamic-forms.html:34-36` |
| Form list is empty because of filters | "No forms match the current filters." | same |
| Re-reading a form before editing fails | Toast: "Could not read that form." Dialog does not open | `dynamic-forms.ts:113` |
| Form save fails | Toast with the server's message; the dialog stays open with the work in it | `dynamic-form-dialog.ts:328, 368` |
| Form saved but some fields failed | Toast: "Form saved, but N field(s) failed: <first message>" -- deliberately not implying nothing saved | `dynamic-form-dialog.ts:359-361` |
| Form saved but returned no id | Toast: "The form saved but returned no id, so its fields were not written." | `:334` |
| Delete a form fails | Toast with the server's message or "The form could not be deleted." | `dynamic-forms.ts:131-132` |
| Submissions fail to load | Toast; the panel shows no list. **There is no retry** -- unlike the form list | `dynamic-forms.ts:161-164` |
| No submissions yet | "Nobody has filled this form in yet. Share /f/{uuid} to start collecting answers." | `dynamic-forms.html:188-192` |
| Delete a submission fails | Toast with the message or "The submission could not be deleted." | `dynamic-forms.ts:194` |
| Public link is wrong or the form withdrawn | Full-card state: "This form is not available", the server's message, "Try again" | `form-fill.ts:35-45, 160-161, 176-178` |
| Public link has no uuid | "This link is missing its form reference." | `form-fill.ts:151-155` |
| Form is Inactive | Rendered read-only with "This form is not accepting answers at the moment." | `form-fill.ts:70-74, 88, 99` |
| Visitor is not signed in | Inline notice with a Sign in link; submit disabled | `form-fill.ts:75-84, 99` -- but the link is broken, 12.6 |
| Answers fail validation | Per-field messages under each field plus "Some answers still need attention." | `form-renderer.ts:112-117`, `form-fill.ts:187-192` |
| Submit returns 401 | "Sending answers needs an account. Sign in and submit again -- what you have typed is kept." | `form-fill.ts:209-211` -- the promise is not kept, 12.8 |
| Submit fails otherwise | The server's message, or "Your answers could not be sent. Please try again." | `form-fill.ts:211` |
| Submit succeeds | Thank-you card with the submission uuid as a reference | `form-fill.ts:46-60, 204-205` |
| Any endpoint throws | HTTP 500 with "Some internal error occurred contact with support." and a server-side log line | `DynamicFormRestApi.java:42-45` (identical in all fifteen methods), `ProcessUtil.INTERNAL_ERROR_500` |
| A 200 with an empty body | Turned into `{status:'ERROR', message:'The server returned an empty response.'}` so the ninety-eight envelope readers show a message instead of crashing | `core/auth/auth.interceptor.ts:28-39` |

Gaps: the submissions panel has no retry affordance; a failed `withFields` inside `openSubmissions`
is swallowed to `null` (`dynamic-forms.ts:96-104, 152`), after which the submissions list renders
with `summaryOf` returning "(no answers)" for every row and the read-only pane rendering nothing --
an empty-looking result rather than an error.

---

## 10. Dependencies

- **`authentication-and-access`** -- the hard dependency. Roles, the hierarchy
  (`MethodSecurityConfig.java:29` and its mirror in `AuthService.hasAtLeast`), `TenantContext`
  population (`JwtAuthenticationFilter.java:31-59`), `TenantOwnership`, `TenantFilterHelper`, and
  the two guards. Every security statement in section 8 is really a statement about that feature.
- **`source-tasks`** -- outbound, one direction only. `submission-to-task-dialog.ts` calls
  `sourceTask.json/listSourceTask` (`:198-199`), `setting.json/appSetting` for task types
  (`:203-210`), `setting.json/xmlCreateChecker` to build the payload (`:219-220`) and
  `addSourceTask` / `updateSourceTask` to write it (`:248-265`). Changing the tag-row contract or
  `xmlCreateChecker` breaks this dialog.
- **Shared UI** -- `TableShell`, `StatTile`, `StatusPill`, `ViewToggle`, `MineFilter`, `Field`,
  `FormDialog`, `Icon`, `ToastService`, `confirmWith`, `copyText`. All under
  `scheduler1/next/src/app/shared/ui/`.
- **`ThemeService`** (`core/theme.service.ts`) -- required by the public page and not currently
  injected there (12.7).
- **Nothing depends on Dynamic Forms.** No other service references `DynamicFormRepository` except
  `TenantSeedService` for the startup backfill. Deleting the feature would break the one dialog
  described above and nothing else.

---

## 11. Acceptance criteria

Fixtures, referred to by name below.

- **TA-admin**, **TA-user** -- `TENANT_ADMIN` and `TENANT_USER` in tenant A.
- **TB-admin** -- `TENANT_ADMIN` in tenant B.
- **P-admin** -- `PLATFORM_ADMIN`, no tenant.
- **FA** -- Active form in tenant A with: a `section` "Contact"; a required `text` "full_name"; an
  optional `text` "ref" with pattern `\d{4}`; a `select` "format" with choices; an `email` field
  "email"; a `password` field "secret".
- **FI** -- Inactive form in tenant A.
- **FB** -- Active form in tenant B.
- **FL** -- a form created by the **old** application, containing one `select` whose `field_options`
  is JSON `[{"label":"CSV","value":"csv"}]` and one `checkbox` with two options, plus a `section`
  followed by one text field.
- **SA1** -- a submission to FA, made by TA-user. **SB1** -- a submission to FB.
- **SL1** -- a submission to FL made by the old application, so its payload nests the post-section
  answer under the section's `fieldName`.

Access and navigation

1. TA-admin opens `/settings/dynamic-forms` and sees the form list. Positive control for 2 and 3.
2. TA-user navigates to `/settings/dynamic-forms` and is redirected to `/unauthorized`; the sidebar
   never showed them the link.
3. P-admin opens `/settings/dynamic-forms` and the page loads.
4. An anonymous visitor opens `/f/{FA.uuid}` and sees FA's fields rendered, with no sidebar and no
   sign-out control.
5. An anonymous visitor opens `/f/deadbeef-not-a-real-uuid` and sees "This form is not available"
   with a Try again button -- not a blank page and not a redirect to login.

Building a form

6. TA-admin creates a form with a name and no fields; it appears in the list with 0 fields, status
   Active, and a non-empty share link.
7. TA-admin saves a form containing two non-section fields both named `email`; the save is refused
   with a message naming the duplicate, and no request is sent.
8. TA-admin saves a field with a label and a blank name; the save is refused. **The name box itself
   is marked invalid**, not only a toast. (Fails today -- 12.3.)
9. TA-admin adds four fields, moves the third to the top, saves, reopens the form, and the order is
   the one they left: reordering survives a round trip.
10. TA-admin adds a `password` field and sees the plain-text warning in the dialog before saving.
11. TA-admin sets a `select` field's Choices to three lines, saves, reopens, and the three choices
    are still there, one per line.
12. TA-admin saves a `select` field with an empty Choices box; the save is refused with a message
    about needing at least one choice. (Fails today -- section 7.)
13. TA-admin saves a field whose pattern is `[unclosed`; the save is refused where it is typed.
    (Fails today -- 12.4.)
14. The preview pane in the dialog shows the same controls, in the same order and at the same
    widths, as `/f/{uuid}` shows for the saved form.

Filling a form

15. TA-user opens `/f/{FA.uuid}` while signed in, fills every required field, submits, and sees the
    thank-you card with a reference. Positive control for 16--20.
16. TA-user submits FA leaving `full_name` blank; the submit is refused, the message "Some answers
    still need attention." appears, and `full_name` carries a per-field error.
17. TA-user enters `my pin is 1234` in `ref` and submits; the submit is **refused**, because a
    pattern is a whole-value rule. (Fails today -- section 7, unanchored regex.)
18. TA-user enters `abcd` in `ref` -- optional, pattern-violating -- and submits; the submit is
    **refused**. (Fails today -- optional fields are unvalidated, `form-renderer.ts:197`.)
19. TA-user enters `not-an-email` in `email` and submits; the submit is **refused**. (Fails today --
    the email check was lost.)
20. A caller POSTs `submitForm` directly with `{dynamicFormId: FA, payload: {"nonsense": 1}}` and a
    valid TA-user token; the request is **refused** by the server naming the missing required
    field. (Fails today -- no server-side validation at all.)
21. An anonymous visitor opens `/f/{FA.uuid}`: the submit button is disabled and an inline notice
    explains that answering needs an account.
22. That visitor clicks Sign in, authenticates, and lands **back on `/f/{FA.uuid}`**, not on the
    dashboard. (Fails today -- 12.6.)
23. TB-admin, signed in, opens `/f/{FA.uuid}` and submits; the page reports that they cannot answer
    this form. (Today the server refuses with "Form not found with …" -- see the open question in
    the synthesis; whichever answer is chosen, the page must not offer a control that is going to
    be refused.)
24. Anyone opens `/f/{FI.uuid}`: the form renders read-only with "This form is not accepting answers
    at the moment." and the submit button disabled.
25. An anonymous visitor opens `/f/{uuid}` with the console's dark theme stored and the page renders
    dark. (Fails today -- 12.7.)

Submissions

26. TA-admin opens the submissions panel for FA and sees SA1 with a one-line summary of its first
    three answered fields.
27. That summary shows `••••••` where the `secret` field's value would be, and the plain value
    appears nowhere in the page source of the list.
28. TA-admin selects SA1 and it renders read-only against FA's fields, in FA's order.
29. TA-admin deletes SA1, confirms, and it disappears from the list; the toast repeats the server's
    message.
30. TA-admin **edits** SA1, changes one answer, saves, and the submissions list shows the new value.
    (Fails today -- editing does not exist.)
31. TA-admin opens SA1 and copies a link that lets a named colleague read that submission, or the
    feature explicitly no longer offers one. (Today: no such control, while
    `fetchSubmissionByUuid` remains open to the internet.)
32. TA-admin uses SA1 as a task configuration: the dialog lists every answered non-section field as
    a tag under the chosen root, shows a server-built XML payload, and creating the task succeeds.
33. TA-admin opens the same dialog for a submission with no answers and the confirm is refused with
    "There are no answers to write."

Tenancy and refusals

34. TB-admin calls `fetchSubmissionsByFormId` for **FA** and is refused with "Form not found with
    …". Positive control: TB-admin calls it for **FB** and gets SB1.
35. TB-admin calls `updateForm` for FA and is refused. Positive control: the same call for FB
    succeeds.
36. TB-admin calls `deleteField` for a field of FA and is refused. Positive control: the same call
    for a field of FB succeeds.
37. TA-user calls `deleteSubmission` for SA1 and is refused with a 403 -- `deleteSubmission`
    inherits `TENANT_ADMIN`. Positive control: TA-admin makes the same call and it succeeds.
38. TA-user calls `fetchAllForms` and is refused with a 403. Positive control: TA-admin gets the
    list.
39. P-admin opens the list and sees forms from tenants A and B, **each row naming its tenant**.
    (Fails today -- 12.5.)
40. A `TENANT_ADMIN` whose `tenant_id` is null calls `fetchAllForms` and receives an empty list or a
    refusal -- **not** every tenant's forms. Positive control: the same account with a tenant
    assigned sees exactly that tenant's forms. (Fails today -- 12.1.)

Old data

41. TA-admin opens FL's builder: the `select` shows its choices as "CSV", not as a line of raw JSON.
    (Fails today -- 2.5.)
42. TA-admin opens FL's builder, changes only the form's description, saves, reopens: the `checkbox`
    field still has its two options. (Fails today -- 2.5; the options are dropped on save.)
43. TA-admin selects SL1 in the submissions panel and every answer, including the ones after the
    section, shows its stored value. (Fails today -- 2.5, section nesting.)

States and chrome

44. With the API returning an error for `fetchAllForms`, the list card shows an error message and a
    working Try again button -- distinguishable from an empty list.
45. With the API returning an error for `fetchSubmissionsByFormId`, the submissions panel shows an
    error with a retry, not a silently empty list. (Fails today -- section 9.)
46. Every screen in the feature renders correctly in both themes at 360px, 768px and 1440px, with no
    horizontal page scroll; wide tables scroll inside their own container.

---

## 12. Known issues

**12.1 `fetchAllForms` trusts the Hibernate filter alone, and the filter is switched off for a
caller with no tenant.**
`fetchAllForms` (`DynamicFormServiceImpl.java:139-152`) enables the filter and then runs
`findByStatusNotOrderByDynamicFormIdDesc` with **no `isOwnedByCaller` check** -- the only read path
in the class that omits one. `TenantFilterHelper.enableIfNeeded` disables the filter outright when
`TenantContext.getTenantId()` is null (`TenantFilterHelper.java:28-33`). A `TENANT_ADMIN` whose
`tenant_id` is null therefore receives **every form of every tenant**, including each form's `uuid`
-- with which they can then read the full field definitions anonymously through
`fetchFormByUuid`. `app_user.tenant_id` is nullable (`AppUser.java:56-57`), and while
`AppUserServiceImpl` refuses to *update* a non-platform user to a null tenant
(`AppUserServiceImpl.java:302`) and refuses a platform-admin actor who omits one on create
(`:168-171`), a non-platform actor's create simply inherits `TenantContext.getTenantId()`
(`:174-175`). Reachability is narrow; the missing check is not.

**12.2 `fetchSubmissionByUuid` is open to the internet, checks nothing, and is used by nothing.**
`@PreAuthorize("permitAll()")` (`DynamicFormRestApi.java:191`) plus the matcher at
`SecurityConfig.java:44`. The service performs no tenant check, no status check and no expiry
(`DynamicFormServiceImpl.java:373-384`); it returns the whole payload, including any `password`
field, in clear text. The new frontend never produces such a link -- `fetchSubmissionByUuid` appears
nowhere in `scheduler1/next/src` -- so an open read surface exists that no screen documents.

**12.3 A missing `fieldName` is reported as a toast, not on the field.**
`fieldLabel` gets `Validators.required` (`dynamic-form-dialog.ts:226`); `fieldName` gets none
(`:225`). The check lives in `validateForm` (`dynamic-form.model.ts:98`) and surfaces through
`this.toast.error(problem)` (`dynamic-form-dialog.ts:317`). On a form with twelve fields, the toast
does not say which one.

**12.4 An invalid regular expression in `pattern` throws at submit time on the public page.**
`missingRequired` calls `new RegExp(field.pattern)` with no guard (`form-renderer.ts:211`). Nothing
validates the pattern when it is saved -- not the dialog (`:135-138` is a plain text input), not
`validateField` (`dynamic-form.model.ts:94-101`), not the server (`DynamicFormServiceImpl.java:386-397`).
An administrator who types `[unclosed` produces a form whose Submit button throws, with the error
escaping `submit()` (`form-fill.ts:182-214` has no try/catch around the validation call).

**12.5 A platform admin sees every tenant's forms in one list with nothing saying which is which.**
`isPlatformAdmin` disables the filter (`TenantFilterHelper.java:28-33`) and satisfies every ownership
check (`TenantOwnership.java:36-38`), so `fetchAllForms` returns the whole platform.
`DynamicFormDto` has no `tenantId` or tenant name (`process/src/main/java/process/model/dto/DynamicFormDto.java:15-31`)
and the table has no tenant column (`dynamic-forms.html:113-117`). Two tenants with a form called
"Onboarding" are indistinguishable, and Delete is one menu item away.

**12.6 The public page's Sign in link uses the wrong query parameter, so the return path is lost.**
`form-fill.ts:81` builds `'/login?next=' + currentPath()`. The login screen reads `returnUrl`
(`features/login/login.ts:43`), as does `authGuard` when it redirects (`core/auth/auth.guard.ts:14`).
`next` is ignored, so a visitor who signs in from a form link lands on the dashboard and has to find
their way back to the link.

**12.7 The public form page ignores the dark theme entirely.**
`ThemeService` applies `html.dark` from an effect in its constructor (`core/theme.service.ts:14-19`),
so it only ever runs if something injects it. `landing.ts:206`, `docs.ts:266`,
`request-workspace.ts:120` and `shell.ts:34` all do; `form-fill.ts` does not, and neither does the
root component (`app.ts:1-15`). Opening `/f/{uuid}` as the first page of a session therefore renders
in light mode whatever the stored preference or the OS setting says. There is also no theme toggle
on the page, which every other public page has.

**12.8 "What you have typed is kept" is not true.**
The 401 branch of `submit()` tells the visitor to sign in and submit again, promising their answers
survive (`form-fill.ts:209-211`). Signing in navigates away from the component; `answers` is a plain
signal with no persistence (`:131`), so everything typed is lost.

**12.9 `copyLink` claims success unconditionally.**
`copyText` returns whether the copy actually happened, and its own documentation says it does so
"that callers can tell the truth rather than claim success unconditionally"
(`shared/ui/clipboard.util.ts:5-9`). `dynamic-forms.ts:143-144` calls it without awaiting and toasts
success regardless. In a non-secure context with `execCommand` unavailable, the user is told the
link is on their clipboard when it is not.

**12.10 Listing forms writes to the database and rewrites the audit trail.**
`fetchAllForms` maps every row through `ensureUuid`, which saves any form with a blank `uuid`
(`DynamicFormServiceImpl.java:146, 180-186`). The save fires `AuditListener.onUpdate`
(`AuditListener.java:41-51`), stamping `updated_by` with whoever merely opened the list. The "Updated
by" column (`dynamic-forms.html:140-142`) then names someone who changed nothing.

**12.11 An unfinished save leaves the form and its fields out of step.**
`dynamic-form-dialog.save()` sends the form, then loops through deletes and then adds/updates
(`:344-356`), collecting failures. A failure part-way leaves some fields written and some not; the
dialog closes with `ref.close(true)` in both branches (`:365`), so the list reloads and the
half-applied state becomes the new truth. The message is honest about it (`:359-361`) but there is
no way back.

**12.12 The old reorder is not atomic either.**
`moveField` mutates the in-memory array first, then issues `updateField(current)` and, in its
success callback, `updateField(target)` (`cu-dynamic-form.component.ts:324-352`). If the second call
fails, two fields share one `fieldOrder` and the on-screen order no longer matches the stored one.
Recorded because the old app is still in production, not because the new one inherits it -- the new
dialog re-indexes every field on save (`dynamic-form-dialog.ts:282`).

**12.13 `updateForm` can resurrect a deleted form.**
It applies any non-null status from the DTO (`DynamicFormServiceImpl.java:113-115`) with no check
that the current status is not `Delete`, so a caller who kept a `dynamicFormId` from before the
delete can set it back to Active. Neither UI offers the path, since deleted forms are excluded from
the list (`:143-144`).

**12.14 The submissions panel has no error state.**
Covered in section 9: a failed `fetchSubmissionsByFormId` produces a toast and an empty panel
(`dynamic-forms.ts:161-164`), and a failed `withFields` produces a panel that renders every
submission as "(no answers)" (`:96-104, 152`). The list above it has a full error state; the panel
below it does not.

**12.15 No test covers any of this.**
Section 2.6. One route-level assertion (`auth.guard.spec.ts:132-144`) is the entire coverage of a
feature with fifteen endpoints, two public ones, and a tenancy model with four layers.

---

## 13. Missing functionality

Ordered by what it would take, not by how loudly it is missed.

**Editing a submission.** The endpoint exists and works (`updateSubmission`,
`DynamicFormServiceImpl.java:288-309`); no client calls it. Restoring it means a mode on the public
page (or an admin-side variant) that seeds the renderer from an existing payload and PUTs instead of
POSTing -- roughly what `fill-dynamic-form.component.ts:73-98, 241-247` did. **Small.** The real
question is not effort but authorisation: the endpoint is `TENANT_USER` with no author on the row,
so restoring it restores "any tenant user may rewrite any answer anyone gave".

**Filling a form from inside the console.** No route, no button. The cheapest version is an "Open
form" item in the row menu that opens `/f/{uuid}` in a new tab -- one line beside
`copyLink` (`dynamic-forms.ts:141-145`). **Trivial.**

**A per-submission page and a sibling switcher.** The new panel shows one submission beside the list
and covers most of the need. What is genuinely gone is a linkable address for a single submission
and the ability to walk through them one at a time. `fetchSubmissionBySubmissionId` is ready
(`:358-371`). **Small.**

**Submission-level sharing.** Deliberately absent from the new app while the endpoint stays open to
the world (12.2). Either build the UI for it -- and give the handle an expiry and a revocation --
or close the endpoint. Doing neither is the worst of the three.

**Server-side validation of submissions.** The largest missing piece, and the one that makes every
promise the builder shows a decoration: required fields, length ranges, patterns, choice membership,
and rejecting keys that match no field. It belongs in `submitForm` and `updateSubmission`
(`:262-309`), reading the form's own `fields`, which those methods already have in hand.
**Medium.**

**Tenant identity on the platform-admin view.** A `tenantId`/`tenantName` on `DynamicFormDto` and a
column that appears only for a platform admin (12.5). **Small**, and the same shape as the fix in
other features.

**Compatibility with the data the old app wrote.** Three separate incompatibilities (2.5): the
option format, `checkbox`, and section nesting. The options can be handled by a tolerant reader (a
line that parses as a JSON array of `{label,value}` becomes those options; otherwise split on
newlines) or by a one-off migration. Section nesting needs a reader that looks one level down when
the flat key is absent, which is exactly `payloadValueFor` (`_models/dynamic-form.model.ts:120-130`)
ported across. `checkbox` needs a decision, not code. **Medium**, and it is the item most likely to
be discovered by a user rather than by us.

**Author on a submission.** A `created_by` column plus `Audited` on `DynamicFormSubmission`
(section 6). Unblocks a per-author edit rule, an "Only mine" filter on submissions, and a "submitted
by" column. **Small** on its own; it is a prerequisite for doing submission editing safely.

**Paging on both lists.** Neither list pages. A form with a few thousand submissions renders every
one of them into the DOM. **Medium**, and not urgent at current volumes.

**Tests.** Nothing exists. The first ones worth writing are pure functions with no framework
around them: `validateForm`, `missingRequired`, `optionsOf` against both option formats, and the
section-nesting reader if one is added. Then a server-side ownership matrix across the four roles
for all fifteen endpoints -- the fixture set in section 11 is exactly that matrix.
