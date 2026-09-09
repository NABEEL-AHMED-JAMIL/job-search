# Grooming and Synthesis -- completeness critique

**Scope.** All 18 rows of `.ai/discovery/features.md`, the 18 documents in `.ai/grooming/` and the
18 in `.ai/synthesis/`. Read in full: `grooming/pdf-highlighter.md` (the only `not-migrated`
feature), `grooming/tenants-and-users.md` (largest, 93 KB), `grooming/job-assistant.md` (smallest,
54 KB), `synthesis/platform-configuration.md` (largest, 40 KB),
`synthesis/authentication-and-access.md` (smallest, 24 KB), `synthesis/source-tasks.md`,
`synthesis/own-account-and-notifications.md`, `synthesis/dashboard.md`,
`synthesis/job-runs-and-queue.md`, `synthesis/storage-connections.md`,
`grooming/content-and-ai-tools.md`, `grooming/source-tasks.md`, `grooming/object-browser.md`.
Section-, path- and role-level checks were run mechanically over all 36.

## What holds

- **No feature is missing and no document is a stub.** 18 rows, 18 grooming files, 18 synthesis
  files, filenames matching the Feature column exactly. Every grooming document carries all 13
  required `##` sections; every synthesis document carries all 6. Smallest is 54 KB / 815 lines.
- **Citations are real.** 4,785 path-like citations across the 36 documents; 4,562 resolve to files
  that exist. The 223 that do not are proposed-new files (`shared/charts/timeline.ts`,
  `core/notifications/notification-store.ts`, twenty-odd `*.spec.ts` the plans say to write) or
  generated artefacts (`BatchDownload-<date>-<uuid>.xlsx`). Separately, **3,609 `file:line`
  citations were bounds-checked and zero point past the end of the file.**
- **The `not-migrated` feature gets a decision.** `synthesis/pdf-highlighter.md:9` opens with
  **"Migrate it"** and argues it from the consumer side (`job-search/etl/tasks/pdf_highlighter_f768925.py`)
  rather than from the route list. All ten losses itemised in `features.md` §2 get an explicit
  migrate / drop / defer somewhere: card view on `/jobs` → **drop** (`synthesis/source-jobs.md:45`),
  `testTopic` → **restore** (`synthesis/platform-configuration.md:90, :275`), per-row task JSON
  export → **restore** (`synthesis/source-tasks.md:43`), Gantt → **build, own commit**
  (`synthesis/job-runs-and-queue.md` Q1), Copy tool URL → **Option A, restore**
  (`synthesis/content-and-ai-tools.md` §6.1).
- **Every open question carries a recommendation.** 96 open questions across the 18 documents, 96
  recommendations. The only one that does not resolve is `synthesis/tenants-and-users.md` Q7, and it
  says why ("(a) if there is a CI system with a database available, (b) if the database is the
  obstacle").
- **The three authorization traps in the brief are handled correctly nearly everywhere.**
  `@PreAuthorize` non-repeatability is stated in 14 documents and applied correctly in 13 (the
  exception is item 1 below). "A `@Filter` does not apply to `findById`" appears in 20 places and is
  right in all 20. "A null `tenant_id` is platform-owned, not ownerless" is stated correctly in
  `grooming/dynamic-forms.md:561`, `grooming/storage-connections.md:409` and
  `synthesis/source-tasks.md:186`.
- **922 numbered acceptance criteria**, most paired: `grooming/content-and-ai-tools.md` alone
  carries 9 explicit "Positive control for N" lines.

**Verdict: sound, with fixes required.** The defects below are not stylistic. Four of them
(items 1--4) will produce wrong work if acted on as written, and two of those are in the two
documents that every other document defers its tenancy fix to.

---

## Items

| # | Sev | File (line) | Problem | What must change |
|---|---|---|---|---|
| 1 | **blocker** | `.ai/grooming/platform-configuration.md:511` and `:685` | **Wrong authorization claim, twice, and it is the exact error the document warns about.** Both say `sourceTask.json/fetchAllLinkSourceTaskWithSourceTaskTypeId` is `TENANT_ADMIN` "by the class-level annotation (`SourceTaskRestApi.java:28`, **no method-level override at `:109`**)". There *is* an override: `SourceTaskRestApi.java:108` is `@PreAuthorize("hasRole('TENANT_USER')")`; `:109` is the `@RequestMapping` it sits above. The doc read the mapping line and concluded nothing was there. `grooming/source-tasks.md:393` has it right (`TENANT_USER (:108)`), so the set contradicts itself on one endpoint. Consequence: §8.2, the authoritative role table for `settings/task-types`, understates the exposure of the linked-tasks panel — any `TENANT_USER` with a token can enumerate the task names bound to a task type, even though criterion 2 correctly sends them to `/unauthorized` at the *route*. | Correct both lines to `TENANT_USER (SourceTaskRestApi.java:108)`; delete the sentence "Every other method in these three controllers relies on the class level"; add an acceptance criterion for the endpoint (route refusal ≠ endpoint refusal), with its positive control. |
| 2 | **blocker** | `.ai/synthesis/authentication-and-access.md:34` (gap row 1) and `:70-80` | **The platform-wide filter fix does not do what the document claims, for four of the fifteen filtered entities.** It proposes `session.enableFilter(...).setParameter("tenantId", tenantId == null ? -1L : tenantId)` and asserts "`-1L` matches no `tenant_id` … so the read path now agrees with `TenantOwnership.isOwnedByCaller`". Four entities do not filter on `tenant_id = :tenantId`; they filter on `(tenant_id = :tenantId or tenant_id is null)` — `StorageConnection.java:44`, `KafkaConnectionProfile.java:26`, `SourceTaskType.java:26`, `TaskForm.java:30`. Binding `-1L` leaves the second disjunct live, so a tenant-less `TENANT_USER` still reads **every platform-owned storage connection, Kafka connection profile (with its bucket/alias and TLS material references), task type and task form**. That is the crown-jewel set. `TenantOwnership.isOwnedByCaller` returns `false` for those rows, so the two paths still disagree — the opposite of the stated goal. | Rewrite the fix: for a tenant-less non-platform caller the shared-catalogue filter must be narrowed too (a second named filter, or a `tenantId` parameter plus a `sharedVisible` boolean), and say which. State the four entities by name. Add an acceptance criterion asserting a tenant-less `TENANT_USER` sees **zero** `storage_connection` rows, not just zero `source_job` rows. |
| 3 | **blocker** | `.ai/synthesis/source-tasks.md:47` and `:184-188`, against `.ai/synthesis/dashboard.md:173-180`, `.ai/synthesis/job-runs-and-queue.md:75-90`, `.ai/synthesis/dynamic-forms.md:46` | **Three incompatible fixes for one shared method, `QueryService.tenantClause` (`QueryService.java:212-217`), and no document arbitrates.** `job-runs-and-queue` and `dashboard` both specify `and 1 = 0` — the tenant-less non-admin sees **nothing**. `dynamic-forms` gap 8 says the same in words ("owns nothing and sees nothing"). `source-tasks` §3.5 specifies the opposite: "A caller with neither role nor tenant gets `tenant_id is null`" — i.e. that caller sees **every platform-owned row**, which is what `TenantOwnership`'s own javadoc (`TenantOwnership.java:13-18`) explicitly refuses ("refused outright rather than being compared equal to the tenant-less rows"). Whoever implements first wins, and `job-runs-and-queue` §4 puts row 1 first and alone. | Pick one. Given `TenantOwnership` and `synthesis/authentication-and-access.md` row 1, `and 1 = 0` is the answer; rewrite `synthesis/source-tasks.md:184-188` to match and cross-reference the owning document. Whichever way it goes, name **one** owner for `tenantClause` + `enableIfNeeded` + the per-service `isOwnedByCaller` copies, and have the other four documents cite it instead of restating it. |
| 4 | **major** | `.ai/synthesis/own-account-and-notifications.md:235-247` (Gap 18) | **Self-contradiction inside one section.** It rejects a `link_url` backfill because "the old app is still live against this database … rewriting `/jobList` to `/jobs` in the table would break every click in the old client" — then, four lines earlier, prescribes exactly that outcome one row at a time: "The five `create` call sites pass the current routes (`/jobs`, `/tasks`)". `scheduler1/src/app/app.routing.ts` has no `jobs` or `tasks` path (verified: 42 routes, `**` at `:278`), so every notification the server writes after that change dead-ends at the old app's wildcard. The reasoning that killed the backfill kills the source change. | Either defer the server change until the old app is switched off (and say so), or keep writing legacy paths and let `notification-links.ts` stay the translation layer, or add the reverse map to the old app. Pick one and record the rejected option, which is what this section is otherwise good at. |
| 5 | **major** | `.ai/synthesis/storage-connections.md:307-309`; absent from all 18 synthesis documents | **A decision Discovery handed forward is refused by name and picked up by nobody.** `features.md:75-77` lists five endpoints "dead in both clients" that "want an explicit decision". `synthesis/storage-connections.md` explicitly punts `fetchConnectionById`: "It belongs to a cross-feature decision about five dead endpoints, not to this document." No document makes that decision. `aiAgent.json/fetchAgentByAgentId`, `documentConverter.json/fetchTaskById` and `queryEngine.json/executions/fetchByQueryId` appear only in grooming endpoint tables — in no gap table, no open question, no acceptance criterion. `grooming/query-and-search-engines.md:1017-1018` names three *more* (`connections/fetchById`, `executions/fetchById`, `schedules/fetchById`) with the same status and the same silence. Separately, Discovery's list is itself wrong: `processAdHoc` is not dead — `grooming/content-and-ai-tools.md:564` records that file chat and the job assistant both call it internally — and nothing corrects `features.md`. | One decision block, in one document (`platform-configuration` or a new cross-cutting note), covering all seven surviving endpoints: keep / delete / build a UI, with the reason. Correct `features.md:75-77` to drop `processAdHoc` from the dead list. |
| 6 | **major** | `.ai/discovery/features.md:471-473`, uncorrected by `.ai/grooming/own-account-and-notifications.md:971-977` | **The canonical document states something the grooming set has disproved, and nobody flags it.** `features.md` §5.3 says "Job completion, failure and skip, file shares, tenant approvals and user creation all raise notifications". Verified against source: there are five `create` call sites and four types — `JOB_COMPLETED`, `JOB_FAILED` (`engine/BulkAction.java:247, 251`), `TASK_ASSIGNED` (`SourceJobServiceImpl.java:98`), `BATCH_DONE` (`SourceJobBulkServiceImpl.java:250`, `SourceTaskServiceImpl.java:630`). `JOB_SKIPPED`, `USER_ADDED`, `FILE_SHARE_SENT`, `FILE_SHARE_FAILED`, `FILE_SHARED_WITH_YOU` and `KAFKA_TEST_FAILED` are raised nowhere. `grooming/own-account-and-notifications.md` K16 gets this exactly right but does not say it corrects Discovery — and `features.md` §2.6 shows this set knows how to record such a correction ("This corrects `frontend-old.md` §7.6"). A reader who trusts the canonical feature map will plan against notifications that do not exist. | Add the same style of correction note to `features.md:471-473`, or to `grooming/own-account-and-notifications.md` K16, naming the four types that are raised. `grooming/object-browser.md` and `grooming/workspace-requests.md` should each say that their feature raises **no** notification today, since Discovery says it does. |
| 7 | **major** | `.ai/discovery/features.md:477-483`, `.ai/grooming/own-account-and-notifications.md:700-704`, `.ai/synthesis/own-account-and-notifications.md:248-251` | **A cross-cutting obligation stated twice and discharged nowhere.** Both documents say "every feature whose route changed in the rewrite has to be represented in [`notification-links.ts`'s] map". The map has five entries (`/jobList`, `/taskList`, `/objectBrowser`, `/users`, `/tenants`). At least a dozen old routes changed and are not in it — `/home`, `/setting`, `/setting/queueMessage`, `/setting/storageConnection`, `/setting/queryEngine`, `/setting/searchEngine`, `/documentConverter`, `/audioTranscriptExtractor`, `/contentCleaner`, `/aiAgent`, `/ollamaModels`, `/dynamicForm`. **No other grooming document mentions the map at all**, so eleven features carry an obligation none of them names. The synthesis says the historical set "can be enumerated once" and then never enumerates it — even though this same set proposes exactly that kind of one-off count query twice elsewhere (`synthesis/dashboard.md` Q1, `synthesis/job-runs-and-queue.md` Q4). | Add `select distinct link_url from notification` as a named pre-step in `synthesis/own-account-and-notifications.md` §4, and either extend the map from its result or delete the "every feature" sentence from both documents and replace it with the two paths the server actually writes. |
| 8 | **major** | `.ai/grooming/tenants-and-users.md:921, :942, :945, :947` (criteria 32, 39, 40, 41) | **Acceptance criteria that cannot fail, and are now out of step with their own synthesis.** Each is disjunctive — "Either the change is persisted and a duplicate is refused, or the field is read-only", "Whether it is editable is the decision recorded in the synthesis". `synthesis/tenants-and-users.md` Q1 and Q2 have since *made* those decisions (email read-only; Status removed from create, honoured on update). The criteria were not narrowed, so a tester cannot write one assertion and the criteria pass under either behaviour. `tenants-and-users` has eight such lines, more than any other document. | Narrow 32, 39, 40 and 41 to the synthesis recommendation, with a one-line note that they change if the recommendation is overruled at sign-off. Criteria 12 and 22 are the same shape and want the same treatment. |
| 9 | **minor** | `.ai/grooming/content-and-ai-tools.md:970` and `:988`; `.ai/grooming/pdf-highlighter.md:959`; `.ai/grooming/object-browser.md:736`; `.ai/grooming/own-account-and-notifications.md:825` | **Refusals with no positive control on the same fixture** — the rule `grooming/README.md` calls one of "two rules that carry most of the weight". Criterion 43 (`alice_user` POSTs `addAgent` → 403) has none, and **no criterion anywhere in the set asserts that a permitted actor successfully creates an agent** — so a fixture in which agent creation is broken for everybody passes. Criterion 52 (`ollama.json/listModels` → 403), pdf-highlighter 62 (unauthenticated → 401 on all nine endpoints), object-browser 67 (`uploadObject` with no header → 401/403), own-account 40 (user `1248` cannot touch `12480/profile/`) are the same shape. The rest of the set is scrupulous about this — nine explicit "Positive control for N" lines in `content-and-ai-tools` alone — which makes these five look like oversights rather than judgements. | Add the paired positive to each: `alice_admin` POSTs `addAgent` and it is created; `alice_admin` GETs `listModels` and receives 200; an authenticated `userA` request to the same nine endpoints succeeds; `userA` uploads with a valid header and the object appears; user `1248` *can* write `1248/profile/`. |
| 10 | **minor** | `.ai/grooming/job-assistant.md:422` | Cites the class-level `@PreAuthorize` on `SourceJobRestApi` at `:28`. It is at `:29`; `:28` is the `@RequestMapping`. `.ai/grooming/bulk-transfer.md:475` cites the same annotation correctly as `SourceJobRestApi.java:29`. Trivial on its own, but it is the same off-by-one reading of an annotation stack that produced item 1. | Change to `:29`. |
| 11 | **minor** | `process/src/main/java/process/security/TenantOwnership.java:19-23`, relied on verbatim by `.ai/synthesis/authentication-and-access.md` and `.ai/grooming/source-tasks.md:939` | The javadoc that every document treats as the statement of record names **three** shared catalogues — `SourceTaskType`, `TaskForm`, `KafkaConnectionProfile`. The code has **four**: `StorageConnection.java:44` carries the same `(tenant_id = :tenantId or tenant_id is null)` condition. `grooming/storage-connections.md:534` and `grooming/object-browser.md:477` both know this; no document reconciles it with the javadoc, and item 2's error follows directly from trusting the list of three. | State the fourth entity wherever the three are listed, and open a one-line item to correct the javadoc. |
| 12 | **minor** | `.ai/grooming/storage-connections.md:169-175`, `.ai/grooming/own-account-and-notifications.md:99`, `.ai/grooming/object-browser.md:498-500`, `.ai/grooming/query-and-search-engines.md:270-275` | Roughly twenty citations use an elided path (`process/src/test/.../StorageConnectionGuardTest.java`, `scheduler1/next/.../clone-dialog.spec.ts`). The files exist, so these are not wrong — but they cannot be checked mechanically, and this set is otherwise machine-verifiable end to end (3,609 exact `file:line` citations, none out of range). | Expand the elisions. It costs nothing and keeps the whole corpus greppable. |

---

## The three weakest documents

Named as requested, in order.

1. **`.ai/synthesis/authentication-and-access.md`** — the smallest synthesis document (24 KB) for the
   feature every other feature declares a dependency on, and it owns the platform-wide tenancy fix
   that `dashboard`, `job-runs-and-queue`, `source-tasks`, `dynamic-forms`, `pdf-highlighter` and
   `storage-connections` all defer to. Its central change (item 2) does not achieve what it says for
   the four entities that matter most, and it never names them. Its summary calls this "the
   strongest migration in the project", which is true of the client and not of the fix.

2. **`.ai/grooming/platform-configuration.md`** — the largest grooming document (89 KB, 1,366 lines,
   five screens and four subsystems in one row) and the only one with a verified-wrong authorization
   claim, made twice (item 1), in the two places a reader would look for it. Size is the likely
   cause: it is the document where a per-endpoint check is most expensive and most necessary.

3. **`.ai/synthesis/source-tasks.md`** — it states the third and incompatible version of the shared
   tenancy fix (item 3), then declares the gap out of scope and hands forward acceptance criterion
   43 as a test written to fail with no named owner ("hand it to whoever owns the platform-wide
   tenancy pass"). A deliberately failing criterion with no owner is how a known cross-tenant leak
   becomes permanent.

Runner-up: **`.ai/synthesis/own-account-and-notifications.md`**, for item 4 — the only internal
self-contradiction found in the set, and in the section whose whole subject is not breaking the old
client.

---

## Resolution — 2026-09-01

Acted on after the critique was written. Each fix was re-verified against source first; the critic's
claims held in every case.

| # | Sev | Status | What changed |
|---|---|---|---|
| 1 | blocker | **fixed** | Verified `SourceTaskRestApi.java:108` is `@PreAuthorize("hasRole('TENANT_USER')")` and `:109` is the `@RequestMapping`. Corrected both places in `grooming/platform-configuration.md`, rewrote the §8.2 note to explain the off-by-one in the annotation stack that caused it, and added acceptance criteria 72–74 covering the endpoint the route guard does not reach — with positive controls |
| 2 | blocker | **fixed** | Verified all four entities read `condition = "(tenant_id = :tenantId or tenant_id is null)"` — `StorageConnection:44`, `KafkaConnectionProfile:26`, `SourceTaskType:26`, `TaskForm:30`. Rewrote the fix in `synthesis/authentication-and-access.md` to narrow both filter shapes, named the four entities in a table, and added criteria 51–54 to `grooming/authentication-and-access.md` that distinguish a working fix from the sentinel-only one |
| 3 | blocker | **fixed** | Verified `QueryService.tenantClause:212-217` returns `""` for a tenant-less caller. Rewrote `synthesis/source-tasks.md` to `and 1 = 0`, matching the other three documents, and named `synthesis/authentication-and-access.md` as the single owner of `tenantClause` + `enableIfNeeded` + the `isOwnedByCaller` copies |
| 6 | major | **fixed** | Verified 5 `create` call sites and 4 raised types against `NotificationType`'s 10 declared. Corrected `discovery/features.md` §5.3 with an explicit correction note naming the four |
| 10 | minor | **fixed** | Verified the annotation is at `SourceJobRestApi.java:29`. Corrected 3 citations in `grooming/job-assistant.md` |
| 11 | minor | **fixed** | The fourth shared catalogue is now named wherever the fix is specified. Correcting the `TenantOwnership` javadoc itself is folded into item 2's change rather than left as a tidy-up |
| 4, 5, 7, 8, 9, 12 | major/minor | **open** | Left for the feature that owns each. Item 5 (seven endpoints dead in both clients) and item 7 (the `notification-links.ts` map) each want one cross-cutting decision block; items 8 and 9 are narrowing exercises inside single documents |

The three blockers were all **cross-document** defects — a claim contradicted by another document, a
fix that did not achieve what it said, and three incompatible versions of one change. None was
findable by reading a single document, which is the argument for running this pass at all.
