# QA — Source Tasks

Companion to `.ai/grooming/source-tasks.md` (acceptance criteria) and `.ai/synthesis/source-tasks.md`
(the change this pass follows up on: the pipeline/Pipeline-Forms fix landed 2026-09-07, grooming §12.7).

**Scope of this pass.** This QA pass focuses on the area that actually changed 2026-09-07 —
the pipeline picker, the pipeline-form-driven task editor, and Pipeline Forms — not the whole
`source-tasks` feature. The acceptance criteria below are marked individually; everything not
listed was **not exercised in this pass** and must not be read as passing. This is the first QA
pass recorded in this project (`.ai/qa/README.md` had none before it).

**Fixtures used.** A real tenant admin was created for this pass rather than relying only on the
seeded Platform Admin, specifically to get genuine tenant-scoped coverage instead of marking every
tenant-level criterion untested: `QA Test Admin` (`qa-test-admin@example.com`), `TENANT_ADMIN`,
tenant **Acme Analytics**. Left in place — see `feedback_leave_test_data_in_place.md`; delete it
under Administration → Users if you don't want it kept. Also created for this pass: a Pipeline
Form (`QA-TEST-PIPE` / "QA Verification Pipeline", one field `search_term`) and one task on it
(`QA Verification Task`, `#1287`) under that same tenant — both also left in place.

---

## Acceptance criteria exercised (grooming §11)

| # | Criterion | Result |
|---|---|---|
| 21 (partial) | A caller requesting another tenant's task by id gets a "not found" refusal indistinguishable from a missing id; the same caller's own task by id succeeds | **PASS** — see QA-03 below for both calls and their bodies |
| 32 | Creating a Pipeline Form for a pipeline, then opening the task editor and selecting that pipeline, shows the form's fields as the only configuration surface | **PASS**, and changed since the criterion was written: there is no tag table to show fields "above" any more (12.7) — the fields **are** the whole surface. See QA-04. |
| 33 | Filling a form field and saving produces a tag/payload matching that answer | **PASS**, verified at the actual stored payload, not just the UI: saving with `search_term = hurricanes-qa-verify` produced `taskPayload = <search_term>hurricanes-qa-verify</search_term>` exactly. See QA-04. |
| 35 | Opening an existing task on a pipeline with a form prefills the form's fields from the task's existing tags, not the fields' defaults | **PASS** — reopened `#1287` and Search term read back `hurricanes-qa-verify`, not blank/default. See QA-05. |
| 36 | Selecting a pipeline with no form shows no form section and no error | **PASS** (Platform Admin, pipeline `F768923`, before the tenant-matching fix below — see QA-01) |

**Not exercised in this pass** (untested, not passed — see grooming §11 for the full list):
1–20, 22–31, 34, 37–43. Notably not covered: paging/the ten-row cap (12.1), the platform-admin
tenant-picker gap (12.2, though its *symptom* was hit incidentally — see QA-06), bulk import/export,
clone, delete, status transitions, and every Pipeline Forms criterion about shared/cross-tenant
form ownership (39–40).

---

### QA-01 · major · Source Tasks — a Platform Admin's Pipeline picker offered a form that then failed to load

**Did:** Signed in as the seeded Platform Admin (no tenant context). Opened `/tasks/new`, selected
pipeline `F768923` ("E2E CSV Validation Intake") from the Pipeline dropdown — a pipeline that
demonstrably has a form, with 12 fields, 7 required, per Configuration → Pipeline Forms.

**Expected:** The form's 12 fields render below the Pipeline field.

**Got:** No form section appeared at all — the screen fell back to the "no form" state (a plain
required Task payload textarea), identical to what criterion 36 describes for a pipeline that
genuinely has none. `GET taskForm.json/formForPipeline?pipelineId=F768923` returned
`{"status":"SUCCESS","message":"No form is defined for this pipeline."}` — a false negative, not a
crash, which is what made it easy to miss: it looks exactly like the correct behaviour for the
one case it is not.

**Cause found (`TaskFormServiceImpl.formForPipeline`, backend):** the query matched the pipeline
against `TenantContext.getTenantId()`, which is `null` for a tenant-less Platform Admin. The form
itself belongs to a real tenant (the seeded "default" tenant, since that's where a platform
admin's own new forms are filed — see `TaskFormServiceImpl.saveForm`'s own comment). `null` never
equals a real tenant id, so the match always failed for this caller, for every pipeline that had a
form.

**Fixed in this pass**, not deferred: `formForPipeline` now matches across every tenant's forms
when the caller is a platform admin (mirroring how `listForms` and `saveForm` already treat that
role), rather than comparing against a tenant id that does not exist. Added
`TaskFormServiceImplTenantIsolationTest.aPlatformAdminsRequestMatchesThePipelineAcrossEveryTenant`
and its positive-control sibling `aPlatformAdminGetsNothingForAPipelineNoTenantHasDefined`;
mutation-tested (reverted the fix, watched both go red — one failed the assertion, one threw an
unnecessary-stubbing error — then restored). Re-verified live after the fix: selecting `F768923`
as the same Platform Admin now renders its full 12-field form.

**Evidence:** `GET .../formForPipeline?pipelineId=F768923` response body quoted above (pre-fix);
post-fix, the same call and a screenshot of the rendered form are described in the session record
that produced this fix (not re-captured as a separate file here — the live re-verification is the
evidence).

---

### QA-02 · cosmetic · Pipeline Forms — a lone field card left half the dialog empty

**Did:** Opened the "New pipeline" / "Edit pipeline form" dialog with exactly one field defined,
at a viewport wide enough to trigger the dialog's two-column field-card grid (`xl:` breakpoint,
≥1280px — the grid was widened to `xwide`/two columns in the same 2026-09-07 pass that removed the
old tag table).

**Expected:** The single field card fills the row, or the layout otherwise looks intentional.

**Got:** The card sat in the grid's first column only; the second column, exactly as wide as the
card itself, was empty — a large, obviously-unintentional blank gap beside a form that has nothing
else to show. Flagged by the user via an annotated screenshot of the live dialog.

**Fixed in this pass:** the last field card now spans both grid columns whenever the total field
count is odd (`task-form-dialog.ts`, `[class.xl:col-span-2]="i === fields.length - 1 &&
fields.length % 2 === 1"`), so a lone field — or any trailing odd-one-out — fills the row instead
of leaving its mirror-image gap. Verified via computed style after the fix: at a 1400px viewport
with one field, the grid's own two columns are still `576.5px 576.5px` (unchanged, so a genuine
pair of fields still lays out two-up), but the single card's `grid-column` is `span 2 / span 2`
and its rendered width (1163px) equals the full grid width, not half of it.

**Evidence:** computed-style dump, before: card width 576.5px = one column. After: card width
1163px = full grid width, `gridColumn: "span 2 / span 2"`.

---

### QA-03 · pass · Source Tasks — cross-tenant task access, by id, at the API

**Did**, as `QA Test Admin` (tenant Acme Analytics), with a real bearer token, not through the UI:
- `GET sourceTask.json/fetchSourceTaskWithSourceTaskId?sourceTaskId=1200` (a task id from well
  outside this tenant's own range — the pre-existing 133-task fixture data another tenant owns).
- The same call with `sourceTaskId=1287` (this session's own task, created under this tenant).

**Expected:** The foreign id is refused with wording that does not confirm or deny the row exists;
the own id succeeds. Acceptance criterion 21's shape.

**Got:** Exactly that.
- `1200` → `{"status":"ERROR","message":"SourceTask not found with 1200."}` — HTTP 200 (the app's
  own convention of carrying the real status in the body), no `data`.
- `1287` → `{"status":"SUCCESS","data":{"taskName":"QA Verification Task","pipelineId":"QA-TEST-PIPE",...}}`.

The refusal and the success use the same wording shape for "not found" as the grooming document's
own criterion 21 describes, and the positive control confirms the refusal is the tenant filter
working, not the endpoint being broken for everyone.

**Evidence:** both response bodies quoted above, captured via `fetch` with the session's own
stored token.

---

### QA-04 · pass · Source Task editor — payload generated from a Pipeline Form's answers, verified at the stored value

**Did:** As `QA Test Admin`, created a task on pipeline `QA-TEST-PIPE` (which has one field,
`search_term`), typed `hurricanes-qa-verify` into it, and saved. Then expanded the task's
"Show payload" panel on the Tasks list.

**Expected:** `taskPayload` is generated from the field's answer automatically — no manual
preview/"use as payload" step exists any more (12.7) — and reads as valid, correctly-nested XML.

**Got:** Exactly `<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n<search_term>hurricanes-qa-verify</search_term>`.
Matches the field's tag and value precisely, generated with no user action beyond typing the
answer and pressing "Create task".

**Evidence:** screenshot of the expanded "Task payload" panel on the Tasks list, `#1287`.

---

### QA-05 · pass · Source Task editor — existing answers win over field defaults on reopen

**Did:** Reopened `#1287` for edit (`/tasks/1287/edit`) as the same tenant admin.

**Expected:** The Pipeline Form's `search_term` field shows the task's saved answer
(`hurricanes-qa-verify`), not the field's own default (none was set, but the point of criterion
35 is that a saved value must win if one exists).

**Got:** Exactly that — the field read `hurricanes-qa-verify` on open, before any edit.

**Evidence:** screenshot of the Edit task screen with the field populated.

---

### QA-06 · pass (incidental) · Source Task editor — a tenant admin is not blocked by the Platform Admin's missing tenant picker

**Did:** As `QA Test Admin` (a real tenant, unlike the seeded Platform Admin), completed the full
create flow above end to end: name, type, pipeline, field answer, Create task.

**Expected:** Succeeds — the "Tenant is required when creating a source task as Platform Admin."
refusal (grooming §12.2, a known, already-documented, unrelated blocker) applies only to a
tenant-less caller.

**Got:** Succeeded on the first attempt, no tenant field shown or needed, task `#1287` created.
Confirms 12.2 is specific to the Platform Admin path and does not regress a real tenant's ability
to create tasks — this was hit incidentally while reproducing the same flow as the Platform Admin
earlier in the same session (that attempt got the 12.2 refusal, by design, not by accident of this
change).

**Evidence:** "Task created." toast and the task appearing in the Acme Analytics tenant's list,
immediately after the Platform Admin's own attempt at the identical flow was refused for the
already-known reason.

---

## UI/UX — both themes, narrow viewport

Checked on the Edit Task screen (form-driven, i.e. the state that changed 2026-09-07):

- **Dark mode:** clean. Every token-based surface, border and text colour switched correctly;
  the "Defined for QA-TEST-PIPE" pill stayed legible (light text on the brand-tinted dark
  background). No literal colour found that stayed light-mode-only.
- **375px viewport (mobile preset):** clean single-column layout, no horizontal overflow, the
  pill wraps naturally beside the section heading instead of overlapping it, Save/Cancel remain
  reachable at the bottom. Native `<select>` values truncate with no visible affordance
  (`QA Verification Pipeline (QA-TEST-PIP…`) — this is the browser's own native select rendering,
  not a app style, and is pre-existing/out of scope for this pass.

Not checked in this pass: any other screen in the feature (the Tasks list, Pipeline Forms list,
the Pipeline Forms dialog itself past the one bug in QA-02) at a narrow viewport, or in dark mode
beyond the one screen above.

---

## Known issue re-confirmed live (not a new finding — recorded already in grooming §12.22)

Task `#1287`'s Pipeline column on `/tasks` reads "—" despite the task plainly having
`pipelineId: "QA-TEST-PIPE"` (confirmed via the API call in QA-03). This is the exact regression
grooming §12.22 predicted from reading the code (`QueryService.java:89`'s join against
`lookup_data`, now empty of `PIPELINE_IDS` rows) — this QA pass is the first live confirmation of
it actually happening, on a task created after the fix, not just a theoretical read of the SQL.
Not re-recorded as a new QA item since it already has a grooming entry with the fix it needs; flagged
here only so the two documents point at the same evidence.
