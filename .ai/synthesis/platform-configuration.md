# Synthesis -- Platform Configuration

Companion to `.ai/grooming/platform-configuration.md`. Paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

Platform Configuration is four screens that crossed at four different qualities. Kafka Connections
crossed brilliantly and grew a whole subsystem the old app never had -- server-side certificate
validation, store generation, protocol-driven forms, 66 unit assertions. Lookups crossed as a
better shape -- two routes collapsed into one expandable tree -- and lost one specific safeguard on
the way, with expensive consequences. The XML builder crossed and gained six validation rules. And
Source Task Types crossed structurally but its **Kafka binding did not**: the rewrite moved routing
from a column on the type to a pair of route endpoints, and the move is half-finished on both sides
of the wire. The result is that the three defects an operator would notice first are all in that
one seam -- editing any task type silently clears its broker binding, the console can never read a
route back because the endpoint returns a bare id where the caller expects an object, and a binding
chosen while creating a type is dropped because the create response carries no id. Alongside those
sits an independent and equally serious regression in Lookups: the edit dialog pre-fills an
encrypted value with the server's `••••••••` mask and posts it back, so editing an encrypted lookup
re-encrypts the mask and destroys the secret -- something the old app deliberately got right. Three
narrower problems are inherited rather than introduced: the status cascade writes `UPPER()` into a
title-case enum column, `lookup_data.lookup_type` is globally unique on a tenant-scoped table, and
`deleteLookupData` is the one lookup mutator that never asks whether the caller owns the row. The
work is one contract decision (where a task type's Kafka binding lives), about a dozen focused
frontend edits, four narrow service changes, two migrations, and the first tests this feature has
ever had at the service and dialog layer. The order that matters is: settle the binding contract
before touching either side of it, and fix the encrypted-lookup dialog before anybody edits one.

### The crossing, exactly

Status is `partial`, so the boundary is the point. What follows is per capability, not per screen.

**Source Task Types**

| Capability | Old | New | Verdict |
|---|---|---|---|
| List, search, status filter | `setting.component.html:46-122` | `task-types.html:135-220` | crossed, improved (tiles, cards, authors, real states) |
| Topic / partition editing | one hidden field recomposed from two (`source-task-type.component.ts:199-206`) | shared `topic.ts`, two visible columns | crossed, improved |
| Kafka profile on the type | select in the dialog, sent as `kafkaConnectionProfileId` (`source-task-type.component.html:69-82`) | select in the dialog, **not sent**; written through `setKafkaRoute` instead (`task-type-dialog.ts:161-167, 192-211`) | **did not cross** -- the old write path was removed and the new one is broken end to end |
| Kafka profile shown on the list | `kafkaConnectionProfileName` from the row (`setting.component.html:73-78`) | route id read as `data.kafkaConnectionProfileId` off a bare number (`task-types.ts:155`) | **did not cross** -- the column always reads "default" |
| Per-row topic reachability | `testTopic` (`setting.component.ts:93-113`) | replaced by a profile test that cannot fire (`task-types.ts:165-185`) | **did not cross** |
| Linked-tasks browser | modal, search **+ group dropdown**, Select (`setting.component.html:147-232`) | inline panel, search only (`task-types.html:224-281`) | crossed, one filter lost |
| Export as JSON | `CommomService.createFile` | `task-types.ts:111-121` | crossed |
| Delete with cascade warning | static text (`setting.component.html:136`) | `confirmWith`, names the linked count (`task-types.ts:234-243`) | crossed, improved |

**Kafka Connections**

| Capability | Old | New | Verdict |
|---|---|---|---|
| Profile CRUD, default, per-row test, in-dialog test | `kafka-connection-profile.component.ts` (447 lines) | `kafka-connections.ts` + `kafka-dialog.ts` | crossed |
| TLS material | uploaded through the generic object endpoint under a browser-chosen prefix (`:118-170`) | `kafkaSecret.json` -- parsed, validated, server-chosen key, store generation (`kafka-secret.service.ts`, `kafka-tls-section.ts`, 1,059 lines) | crossed and replaced by something materially safer |
| Protocol-conditional form, combination summary, JSON property parse, clear flags | none | `kafka-profile-form.ts` + 66 spec assertions | new |
| **Scope filter and Scope column** (platform admin) | `kafka-connection-profile.component.html:7-13, 60, 76-78` | absent | **did not cross** |
| `canManage(profile)` row gate | `:87-92` | unnecessary -- a tenant now only ever sees its own rows (`KafkaConnectionProfileRepository.java:23-38`) | crossed by becoming moot |

**Lookups**

| Capability | Old | New | Verdict |
|---|---|---|---|
| Parent list, child list | two routes (`setting/lookup`, `setting/subLookup`) | one expandable tree (`lookup.html:110-248`) | crossed, improved |
| Add / edit parent and child | `lookup.component.ts` | `lookup-dialog.ts` | crossed |
| Delete a child | immediate, no confirmation (`sub-lookup.component.html:83-89`) | `confirmWith`, names the child count | crossed, improved |
| **Blank the value field for an encrypted row** | `lookup.component.ts:103`, placeholder at `lookup.component.html:27` | absent -- the mask is pre-filled and posted back | **did not cross** -- and its absence destroys data |
| Ownership shown per row | none | `canModify` + a "shared" pill on children (`lookup.ts:187-193`) | new |
| Parent-row ownership gate | n/a (no delete on a parent existed) | still absent, but Delete is now offered | new control, missing its gate |

**XML Configuration**

| Capability | Old | New | Verdict |
|---|---|---|---|
| ~~Six tag rows, +/-, build, download~~ | ~~`xml-configuration.component.ts`~~ | ~~`xml-builder.ts`~~ | ~~crossed~~ **both sides now gone, on two different dates** -- the old app's screen was removed 2026-09-07 (part of the same pass that dropped the `PIPELINE_IDS` lookup, see `.ai/grooming/platform-configuration.md` §2.8/§2.9/§12.19); the new app's was already gone before that, removed 2026-09-05 in commit `889ae2e`, unrelated (see §7 below and grooming §12.20) |
| ~~Reachable from the navigation~~ | ~~no -- `setting/lookpXml`, linked from nothing (`app.routing.ts:151`)~~ | ~~Tools → XML Configuration (`shell.ts:81`)~~ | ~~crossed and fixed~~ **moot -- neither side is reachable because neither side exists** |
| ~~Six client-side validity checks, parent `datalist`, copy, reset~~ | none | ~~`xml-builder.ts:34-59`~~ | ~~new~~ **gone with the screen, 2026-09-05** |
| ~~Listed on the settings hub~~ | n/a | ~~**no** -- nine cards, not one of them (`settings-hub.ts:50-69`)~~ | ~~new inconsistency~~ **moot -- there is no settings hub either, removed the same 2026-09-05 commit** |

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | The edit payload omits `kafkaConnectionProfileId` (`task-type-dialog.ts:161-167`) and `updateSourceTaskType` writes what it is sent (`SettingServiceImpl.java:326`) | Editing a description leaves the broker binding alone | Every edit nulls `source_task_type.kafka_connection_profile_id`; for a platform admin nothing replaces it | Settle the binding contract (see 3.1), then send the field and make the server treat an absent key as "unchanged" | M | **High -- silent data loss on the commonest action** |
| 2 | `fetchKafkaRoute` returns a bare id as `data` (`SettingServiceImpl.java:387`); both callers read `data.kafkaConnectionProfileId` (`task-types.ts:155`, `task-type-dialog.ts:147`) | The console can read a route back | The Kafka column always says "default", the dialog never pre-selects, and saving then deletes the unseen route | Wrap the id in `{ kafkaConnectionProfileId }` server-side; keep the client's `??` fallback for one release | S | Medium -- a response-shape change |
| 3 | `lookup-dialog.ts:95` pre-fills `lookupValue` with the server's `••••••••` mask and posts it; `updateLookupData` re-encrypts it (`:496-504`) | Blank means "keep the stored value", as the old app had it | Editing an encrypted lookup destroys the secret irrecoverably | Blank the control and drop `required` when `encrypted`; add the hint; make the server reject the mask string outright | S | **High -- irrecoverable** |
| 4 | `addSourceTaskType` returns no `data` (`:294`); the dialog needs an id to apply a route (`task-type-dialog.ts:181, 194`) | A Kafka connection chosen on create is applied | Choosing one on the New dialog does nothing, silently | Return the saved DTO as `data` from `addSourceTaskType` | S | Low |
| 5 | Topic validator is `/^[a-zA-Z-]+$/` with a hint blaming the server (`task-type-dialog.ts:131-132`) | The client rule is the server rule | `orders-v2`, `etl.jobs`, `job_events` cannot be entered, and the operator is told the server refuses them | Replace with `/^[a-zA-Z0-9._-]{1,249}$/`, rewrite the hint and the error | S | Low |
| 6 | `testTopic` is called from nowhere; the row action tests the profile and, because of gap 2, always short-circuits (`task-types.ts:165-185`) | An operator can ask whether *this type's* topic exists | The one Kafka answer that is about the topic is unreachable from either console | Point the row action at `testTopic` with `topicOf(row)` | S | Low |
| 7 | `statusChangeSourceJobLinkWithSourceTaskTypeId` writes `UPPER(?2)` (`SourceJobRepository.java:57`) | `Active` / `Inactive` / `Delete`, matching the enum | Editing or deleting a task type re-creates the exact data corruption `V16` was written to repair | Drop the `UPPER`, matching the sibling at `:64`; add a data-repair changeset | S | Medium -- touches live job rows |
| 8 | `deleteLookupData` runs only `refuseModification` (`SettingServiceImpl.java:586`), which passes when both tenant ids are null | A caller carrying no tenant owns nothing | A null-tenant `TENANT_ADMIN` can hard-delete a platform-owned `BUCKET_LIST` / ~~`PIPELINE_IDS`~~ / `TASK_GROUPS` child, for every tenant (`PIPELINE_IDS` itself no longer exists as a target, removed 2026-09-07 -- see the addendum in §8) | Add the `isLookupOwnedByCaller` guard `updateLookupData` already has; and make `refuseModification` refuse a null caller tenant explicitly | S | Low to fix, Medium in consequence |
| 9 | `lookup_data.lookup_type VARCHAR(255) UNIQUE` (`V1__creating_shedlock_schema.sql:16`, `LookupData.java:53-55`) on a table carrying `tenant_id` | Two tenants can hold entries of the same name | The second tenant gets a unique violation as a 500, and can probe what names are taken | Tenant-qualify the constraint (see 3.5 and the open question) | M | Medium -- schema change on a live constraint |
| 10 | "New lookup" and parent-row Edit/Delete are offered to everyone (`lookup.html:14-16, 174-186`); the server refuses a tenant admin every time (`:451-456`, `:129-133`) | The console does not offer what the server will refuse | An operator is invited to do something impossible and learns from a toast | Reuse the existing `canModify` on the parent rows; gate "New lookup" on `auth.isPlatformAdmin()` | S | Low |
| 11 | The Kafka list shows every tenant's profiles to a platform admin with no owner column and no scope filter | Rows say whose they are, and can be narrowed | The old tab had both (`kafka-connection-profile.component.html:7-13, 60, 76-78`); on a multi-tenant install the list is unreadable | Add an Owner column and a Scope filter, both behind `auth.isPlatformAdmin()` | S | Low |
| 12 | `TASK_GROUPS` is in `TENANT_OWNED_LOOKUPS` (`SettingServiceImpl.java:70-72`, was `:68` before `PIPELINE_IDS`'s 2026-09-07 removal shifted the set's own line -- see §8) and read by the task editor (`task-edit.ts:18`) but seeded by no changelog | The Group dropdown is populated on a fresh install | A tenant admin cannot create the family (gap 10) and so cannot use groups at all | One insert changeset plus the `setval` V9 established | S | Low |
| 13 | The create dialog offers a Status select; `getSourceTaskType` forces `Status.Active` (`:626`) | The chosen status is honoured | A control that lies | Honour `dto.getStatus()`, defaulting to `Active` | S | Low |
| 14 | Description is required by `addSourceTaskType` (`:271-272`), by neither the update path (`:300-306`) nor the dialog (`task-type-dialog.ts:130`), into a `NOT NULL` column | One rule, stated in one place, mirrored on the client | A create fails with a toast the field did not predict | Require it in the dialog and in `updateSourceTaskType` | S | Low |
| 15 | `lookup.ts:74-83` issues one `fetchSubLookupByParentId` per parent on every load, swallowing failures (`:78`) | The Entries count is known without N requests, and a failure is visible | Grows linearly with families; a failed child fetch is indistinguishable from a parent with no children | Return a child count on `appSetting`'s parents; keep the per-parent fetch for expansion only | M | Low |
| 16 | Neither `SettingServiceImpl` nor `KafkaConnectionProfileServiceImpl` calls `TenantFilterHelper.enableIfNeeded`, though their entities declare `tenantFilter` | The declarations describe what happens | A future reader assumes the filter is protecting these paths | Either call it, or record the exemption in `TenantFilterDeclarationTest` beside `LookupData`'s | S | Low |
| 17 | The linked-tasks panel lost the old modal's group dropdown (`setting.component.html:169-176`) | Filter linked tasks by group | `groupLabel` is already on every row (`task-types.ts:19-24`) | Add a select beside the existing search | S | Low |
| 18 | ~~The settings hub lists nine areas; XML Configuration is not one (`settings-hub.ts:50-69`), though its nav hint calls the hub "Every area in one place" (`shell.ts:118-119`)~~ **Moot, 2026-09-05 (§7).** Both the settings hub and the XML builder were removed in commit `889ae2e`, before and unrelated to this table's other gaps; there is neither a hub nor a card to add one to | ~~The hub is what it says it is~~ n/a | ~~A screen reachable from one menu only~~ n/a | ~~Add the card, or change the hint~~ Nothing to do | S | Low |
| 19 | No test touches `SettingServiceImpl`'s twelve service methods, `refuseModification`, `KafkaConnectionProfileServiceImpl`'s eight, or any of the five components on these routes | Each guard has a refusal and a positive control | Gaps 1, 3, 4, 5, 8 and 13 would all have been caught by tests that do not exist | `SettingGuardTest` + `lookup-dialog.spec.ts` + `task-type-dialog.spec.ts` | M | Low |
| 20 | Three bindings decide which cluster a type publishes to (`KafkaConnectionResolver.java:49-82`); the console shows at most one | "Which cluster will this actually use?" answerable from the screen | An operator checks three places and infers the precedence | A resolved-connection field on the `appSetting` task-type DTO | M | Low |

---

## 3. Solution detail

### 3.1 Where a task type's Kafka binding lives (gaps 1, 2, 4)

This is the decision the rest of the task-type work hangs off, so it is worth stating what is
actually there before choosing.

There are **two** persisted bindings and the server uses both:

- `source_task_type.kafka_connection_profile_id` -- the type's own default. Written by
  `addSourceTaskType`/`updateSourceTaskType`, validated for visibility by
  `validateKafkaProfileOwnership` (`SettingServiceImpl.java:630-642`), returned on every
  `appSetting` row along with the profile's name (`:251-264`).
- `tenant_task_type_kafka_route` -- a per-tenant override, unique on
  `(tenant_id, source_task_type_id)`, written by `setKafkaRoute` and refused to a platform admin
  (`:393-417`).

`KafkaConnectionResolver.resolve` reads them in that priority: route, then type default, then tenant
default, then platform default (`config/KafkaConnectionResolver.java:49-82`). Both are real; neither
is legacy.

The old console wrote only the first. The new console writes only the second, and deliberately --
the dialog's comment says "Routing lives behind its own endpoints, so it is a second call after the
type is saved" (`task-type-dialog.ts:191`). That is a defensible reading for a tenant admin, whose
override is genuinely per-tenant. It is the wrong reading for a **platform admin**, who has no
tenant and for whom `canRoute()` is false: for them the dialog renders an explanatory note instead
of a control (`:83-91`), sends no `kafkaConnectionProfileId`, and `applyRoute` returns immediately
(`:194`). So a platform admin has no way at all to bind a shared task type to a cluster, and every
edit they make erases the binding somebody set before the rewrite.

**The change.** Keep both bindings and let the dialog write the one the caller can actually own:

- Send `kafkaConnectionProfileId` in the payload again, from the same select, for **every** caller.
  For a platform admin that is the only binding available, so the control must be rendered for them
  too -- replacing the note at `task-type-dialog.ts:83-91`, whose premise ("routing is a per-tenant
  override") is true of the route table and false of the column.
- In `updateSourceTaskType`, treat an **absent** key as "leave it alone" and an explicit `null` as
  "clear it". Jackson cannot tell the two apart on a primitive wrapper, so the DTO needs a
  `clearKafkaConnectionProfile` boolean, exactly the pattern
  `KafkaConnectionProfileDto.clearSaslPassword` already establishes
  (`KafkaConnectionProfileServiceImpl.java:637-639`). That way no other client -- including anything
  that posts a partial DTO -- can erase a binding by omission.
- Keep `applyRoute` for the tenant admin, and only for them, unchanged.
- Have `addSourceTaskType` return the saved DTO as `data` (`:294` currently returns a two-argument
  `ResponseDto`), so the dialog's `applyRoute` has an id on create.

**The alternative I rejected: make the route table the only binding, and drop the column.** It is
tempting -- one place, one rule, and `TenantTaskTypeKafkaRoute` is the newer and better-shaped
table. It fails on the platform admin. `setKafkaRoute` refuses them by design because the row
requires a non-null `tenant_id` (`TenantTaskTypeKafkaRoute.java:48`), and a platform-owned task type
belongs to no tenant. Under a route-only model a shared task type could never be bound to anything
but the platform default. Dropping the column would also silently repoint every task type that
currently carries one, at deploy time, with no migration able to guess a tenant for it. The column
is what a platform admin has; the route is what a tenant has; both stay.

**The second alternative I rejected: fix only the client, leaving the server writing what it is
sent.** That fixes today's symptom and leaves the trap armed for the next caller. `updateSourceTaskType`
is a full-replacement update on a partial DTO, and the same shape has already cost this feature the
`sslEndpointIdentificationAlgorithm` column once -- `applyProfileDto` writes it unconditionally
(`KafkaConnectionProfileServiceImpl.java:669`) and the new Kafka dialog carries a control purely so
the key is present in the body, with a comment recording that its absence "overwrote the stored
setting with null" (`kafka-dialog.ts:215-219`). The same bug, in the same feature, twice. Fix it at
the server this time.

### 3.2 The route response shape (gap 2)

`fetchKafkaRoute` returns `route.getKafkaConnectionProfileId()` -- a bare `Long` -- as the envelope's
`data` (`SettingServiceImpl.java:387`). Both consumers read a property off it. Neither has ever
worked.

Change the server to `new ResponseDto(SUCCESS, "Route fetched.", Collections.singletonMap(
"kafkaConnectionProfileId", route.getKafkaConnectionProfileId()))`, matching what both callers
already expect and what the `?? response.data?.profileId` fallback was clearly written against.

**Rejected: change the client to read the bare number.** It is a one-character fix and it makes the
endpoint the only one in the API whose `data` is a scalar. `appSetting` returns a map,
`fetchSubLookupByParentId` returns a map, `fetchAllProfiles` returns a list of DTOs. A scalar `data`
is also unextendable: the next thing anyone wants from this endpoint is the profile's *name*, so
the console can label the column without cross-referencing `fetchAllProfiles` -- and an object can
carry it. Leave the two `??` fallbacks in the client for one release so a stale bundle against a new
server, or the reverse, degrades to "default" rather than to a crash.

### 3.3 The encrypted lookup value (gap 3)

Two changes, and the second is the one that matters.

**Client.** `lookup-dialog.ts:92-99` becomes conditional on `data.lookup?.encrypted`, mirroring
`lookup.component.ts:103` from the old app: value control starts empty, `Validators.required` is
dropped, and a hint on the field says blank keeps the stored value. Add the same wording the old
placeholder used (`lookup.component.html:27`), which is already in the product's voice.

**Server.** `updateLookupData` must refuse the mask outright. Compare the incoming value against
`MASKED_LOOKUP_VALUE` (`SettingServiceImpl.java:154`) and, when they match on a row that is already
encrypted, treat it as "no new value" rather than as a new one -- or return an error naming the
field. Either is fine; what is not fine is that the string the server emits as a redaction is a
string the server will accept as a secret.

**Rejected: fix the client only.** The mask is the server's own invention and any client that
round-trips a DTO -- a future bulk editor, a script, a retry after a partial failure -- will hit
this. The server is the only place the rule can be stated once. It is also the cheaper of the two to
test: one service test, no component harness.

**Rejected: stop masking and return nothing at all for an encrypted value.** Cleaner in principle,
and it breaks the list rendering, which distinguishes "encrypted" from "empty" by the `encrypted`
flag but still prints `lookupValue` in the old app and in the new cards' child rows
(`lookup.html:99`). The mask is doing display work; leave it and make it inedible.

### 3.4 The `UPPER()` status cascade (gap 7)

`statusChangeSourceJobLinkWithSourceTaskTypeId` (`SourceJobRepository.java:55-60`) is called from
exactly two places, both in this feature: `updateSourceTaskType` when a status is supplied
(`SettingServiceImpl.java:328-331`) and `deleteSourceTaskType` (`:354`). Its sibling
`statusChangeSourceJobWithSourceTaskId` (`:64`) does the same job without `UPPER`.

Drop the `UPPER(...)` so the parameter is written as given -- both callers already pass
`Status.name()`, which is title-case. Add a repair changeset in the shape of
`V16__fix_source_job_status_casing.sql`, which already documents precisely what an all-caps value
does: excluded from every typed query, and an `IllegalArgumentException` on any path that hydrates
the row as an entity.

**Rejected: leave the query and normalise on read.** The casing is already normalised on read in one
place -- `SourceTaskTypeRepository`'s projection re-cases `task_type_status` with
`CONCAT(UPPER(SUBSTR(...)))` (`:28`) -- and that is exactly the sort of accumulated compensation
that makes the underlying inconsistency permanent. V16 chose to fix the data; fix the writer that
re-creates it.

### 3.5 Lookup ownership and uniqueness (gaps 8, 9, 10)

**Gap 8** is two lines. `deleteLookupData` gets the `isLookupOwnedByCaller` check that
`updateLookupData` already has at `:486`, and `refuseModification` gets an explicit early refusal
when `TenantContext.getTenantId()` is null and the caller is not a platform admin. Both are needed:
the first closes the specific hole, the second states the rule the grooming document's context
line -- *a caller carrying no tenant owns nothing* -- in the one predicate that decides it, so the
next family added to `TENANT_OWNED_LOOKUPS` inherits it.

**Gap 10** reuses what is already there. `lookup.ts:187-193` `canModify` is applied to child rows
(`lookup.html:217-232`) and not to parents (`:174-186`). Apply it to the parent kebab as well, and
gate the header's "New lookup" on `auth.isPlatformAdmin()`, since `addLookupData` refuses a tenant
admin any parentless row (`SettingServiceImpl.java:451-456`). No new concept, no server change.

**Gap 9** needs a decision, which is in section 6. Whatever the key, the migration is the same
shape: drop the unique constraint that `V1__creating_shedlock_schema.sql:16` created and
`LookupData.java:53-55` re-declares, remove `unique = true` from the entity so `ddl-auto` does not
put it back, and add a partial or composite unique index in its place. It must be a changeset rather
than an entity change alone, because `ddl-auto=update` never drops a constraint.

**Rejected: drop the uniqueness entirely.** The parent families are looked up by name -- 
`LookupDataCacheService.getParentLookupById(String lookupType)` keys the process-wide cache on it
(`LookupDataCacheService.java:70-72`), and two parents called `BUCKET_LIST` would make that cache
non-deterministic. Uniqueness is real at the family level; it is only the *scope* that is wrong.

### 3.6 The topic validator (gap 5)

`task-type-dialog.ts:131-132` becomes `Validators.pattern(/^[a-zA-Z0-9._-]{1,249}$/)`, and the two
strings that explain it -- the field hint and the `errorMessages.pattern` entry -- are rewritten to
describe that rule rather than the old one. `shared/ui/topic.spec.ts:22-25` already carries a test
naming this as a past bug; add the dialog-level case so the comment becomes true.

**Rejected: remove the client pattern and let the server answer.** The server's refusal is
`SourceTaskType queueTopicPartition format invalid, expected topic=<name>&partitions=[<n>|*].`
(`SettingServiceImpl.java:278`), which names a composite field the operator never typed. Two
controls, one message about a third thing, arriving as a toast. Keeping a client rule that mirrors
the server is right; keeping one that contradicts it is the bug.

### 3.7 Topic reachability (gap 6)

`testRoute` (`task-types.ts:165-185`) becomes a call to
`GET /kafkaConnectionProfile.json/testTopic?topicName=<topicOf(type.queueTopicPartition)>`, which is
what `setting.component.ts:93-113` did and what the endpoint is for. Two details make it better than
the old one: the topic comes from the shared parser rather than a per-screen regex, and the action
no longer needs to be hidden from a platform admin -- `testTopicConnection` resolves a null tenant
to the platform's own profile (`KafkaConnectionProfileServiceImpl.java:372-375`), so it works for
them.

Keep the profile-level test where it is, on the Kafka screen. The two answer different questions and
the grooming document's acceptance criteria 24 and 25 test them separately.

**Rejected: one combined action that tests the profile and then the topic.** It reads well and it
doubles the latency of the commoner case; `testTopic` already fails with a cluster-level reason when
the cluster is the problem (`:389`), so the combined form adds a round trip to tell the operator
something the single call already told them.

### 3.8 Kafka profile ownership on screen (gap 11)

`KafkaConnectionProfileDto` already carries `tenantId` and `getProfileDto` already sets it
(`:702`). Add an Owner column to `kafka-connections.html`, rendered under
`@if (auth.isPlatformAdmin())`, showing `Platform-wide` for a null tenant and the tenant otherwise;
and a Scope select beside the protocol filter, on the same condition. This is a restoration of
`kafka-connection-profile.component.html:7-13, 60, 76-78`, not an invention.

Showing the tenant *name* rather than its id needs either a join in
`findVisibleToPlatformAdmin` or a second call to `tenant.json/listTenants`. The old app showed
`Tenant #N` and that was enough; do the id first, and treat the name as a separate small
improvement.

### 3.9 The lookups N+1 (gap 15)

`appSetting` already builds a `LookupDataDto` per parent (`SettingServiceImpl.java:213-228`).
`LookupDataDto` has no child count; `LookupData` has a lazy `children` set
(`LookupData.java:79-80`) and `LookupDataRepository` already carries a per-tenant count
(`countByTenantIdAndParent_LookupType`, cited in `.ai/discovery/database.md` §8.4). Adding a
`childCount` to the DTO -- filtered by the same family rules `fetchSubLookupByParentId` applies at
`:547-563`, or the count will disagree with the list -- lets `lookup.ts:53-90` drop the `forkJoin`
entirely and fetch children only when a row is expanded. `LookupData` in the client interface
already declares `childCount` (`lookup-dialog.ts:28`), so the field was anticipated.

Also stop swallowing the per-parent failure at `lookup.ts:78`: an expansion that fails should say so
in the row rather than render as "no entries".

**Rejected: leave it.** ~~Eight~~ **Seven** families today (one fewer since `PIPELINE_IDS` was
removed 2026-09-07 -- see `.ai/grooming/platform-configuration.md` §2.9 and this document's §8), and
the comment at `lookup.ts:70-73` reasons from that number, whatever it is at the time. ~~`PIPELINE_IDS`,~~
`PIPELINE_HOME_PAGES`, `TASK_GROUPS` and `BUCKET_LIST` are all families a tenant is *expected* to
extend, and nothing stops a platform admin adding more. The cost is a `forkJoin` that scales with
configuration.

### 3.10 Tests (gap 19)

Three files, and they are chosen to catch the six defects above rather than to raise a coverage
number.

- `process/src/test/java/process/model/service/impl/SettingGuardTest.java`, in the style of the
  existing `TenantOwnedLookupTest`: `refuseModification` for each of the five branches with a
  positive control on the same fixture; `deleteLookupData` refusing a null-tenant caller;
  `updateLookupData` refusing the mask string; `updateSourceTaskType` preserving a binding it was
  not sent; the ownership checks on update and delete.
- `scheduler1/next/src/app/features/settings/lookup/lookup-dialog.spec.ts`: the encrypted case --
  empty control, no `required`, and a payload that omits the value when untouched.
- `scheduler1/next/src/app/features/settings/task-types/task-type-dialog.spec.ts`: the payload
  carries `kafkaConnectionProfileId`; the topic pattern accepts `orders-v2` and `etl.jobs.inbound`
  and rejects `has space`; `applyRoute` fires on create once an id is returned.

The existing `kafka-profile-form.spec.ts` and `kafka-tls-section.spec.ts` are the model: rules
extracted from the dialog so they can be tested without a component harness. `task-type-dialog.ts`
and `lookup-dialog.ts` would each need a small extraction of the same kind -- a `taskTypePayload`
and a `lookupPayload` -- which is worth doing for its own sake.

### 3.11 The resolved connection (gap 20)

Deferred, but worth writing down while the reasoning is fresh. `appSetting`'s task-type DTO could
carry a `resolvedProfileName` computed by calling `KafkaConnectionResolver.resolve(tenantId, id)`
per row and reading the profile's name -- the resolver is already injected into `SettingServiceImpl`
(`:164`) and already used on every save (`:291-293`). The column then answers "which cluster will
this publish to?" outright, and the Kafka column's route/default distinction becomes a detail in the
dialog rather than the only thing on the list.

It is deferred because it is a per-row resolve on a cached endpoint, and `appSetting` is
`@Cacheable` keyed on the tenant (`:207-208`) -- a resolved name would go stale whenever a profile's
status changed, which does not evict that cache. Getting that right is its own piece of work and it
should not hold up gaps 1 and 2.

---

## 4. Ordering

**First, and before anything else touches a task type: gap 3 (encrypted lookups).** It is the only
defect here that destroys data that cannot be reconstructed, it is confined to two files, and it
does not depend on any decision. Every day it stays is a day somebody might edit an encrypted
lookup.

**Second: the binding contract, 3.1.** Gaps 1, 2, 4 and 13 all touch `task-type-dialog.ts`,
`SettingServiceImpl.addSourceTaskType`/`updateSourceTaskType` and the `SourceTaskTypeDto`. Doing
them as one change is both cheaper and safer than four passes over the same seam -- and gap 2 alone
is dangerous, because a client that can suddenly *read* a route while the dialog still omits
`kafkaConnectionProfileId` will start faithfully round-tripping a value into a column that is then
nulled. Land them together, with the tests from 3.10 in the same change.

**Third, in parallel, the two independent server fixes: gaps 7 and 8.** Neither touches the
frontend. Gap 7 needs its repair changeset run against existing data, so it wants a maintenance
window; gap 8 does not.

**Fourth: gap 9, the lookup uniqueness migration.** It is the only schema change with any risk and
it blocks nothing above it. It does block onboarding a second tenant that wants its own
`BUCKET_LIST` entries, so it should not slip far. Answer the open question first.

**Fifth, the cheap visible ones, in any order: gaps 5, 6, 10, 11, 12, 14, 17, 18.** Each is under a
day. Gap 6 depends on gap 2 only in that its acceptance criterion (25) reads better once the Kafka
column is honest; the code does not.

**Sixth: gaps 15, 16, 20.** Improvements, not repairs.

What unblocks what: 3.1 unblocks the whole of the task-type screen being trustworthy, which is what
`source-tasks` and `source-jobs` sit on -- `.ai/discovery/features.md` names
`platform-configuration → source-tasks → source-jobs` as the critical path. Gap 12 unblocks task
groups for every tenant. Gap 9 unblocks the second tenant on any installation.

---

## 5. Out of scope

**The old app.** No fix in this document is applied to `scheduler1/src`. The old Kafka form is
already stale against its own server -- it sends no `sslEndpointIdentificationAlgorithm`, so
`applyProfileDto` nulls the column on every save it makes (`KafkaConnectionProfileServiceImpl.java:669`)
-- and repairing that is work on a codebase being retired.

**`setting.json/dynamicQueryResponse`.** It lives on `SettingRestApi` and is the only method with a
`PLATFORM_ADMIN` override (`:43`), but it belongs to `query-and-search-engines` by
`.ai/discovery/features.md` row 11. Not touched here.

**Whether a `TENANT_ADMIN` should be able to exist with a null tenant.** Gap 8 closes the hole this
feature has regardless of the answer. The path that creates such a user is `AppUserServiceImpl.updateUser`
demoting a platform admin without naming a tenant (`:292-299`), which is `tenants-and-users`'
decision to make.

**`LOOKUP_ENCRYPTION_KEY`'s literal default in `process/docker-compose.yml`.** Recorded in
`.ai/discovery/risks.md` as an infrastructure risk. Every encrypted lookup and every Kafka secret in
this feature depends on it, and none of them can fix it.

**Server-side validation of the XML builder's six rules.** The endpoint accepts any list of tag
descriptors (`SettingRestApi.java:176-181`). Because nothing is persisted and the output is a file
the operator inspects before using, a bad document costs one confusing download. Worth stating, not
worth building now.

**Renaming `kafka_connection_profile.sasl_password` to carry the `_enc` suffix its three siblings
have.** A real inconsistency (`.ai/discovery/risks.md` #45) and a column rename on a table holding
live credentials, for a naming convention. Not now.

**Making `deleteLookupData` and `deleteProfile` actual DELETEs.** Both are declared `PUT`
(`SettingRestApi.java:161`, `KafkaConnectionProfileRestApi.java:51`) and both consoles comply with
comments explaining why. Changing them means changing every caller for tidiness.

---

## 6. Open questions

**Q1. What should `lookup_data.lookup_type` be unique on?**

Three candidates:

(a) `(tenant_id, lookup_type)` -- the obvious tenant-qualification, matching `uq_tenant_task_type`.
(b) `(coalesce(tenant_id, 0), coalesce(parent_lookup_id, 0), lookup_type)` -- unique within a family
and a tenant, so two tenants may each have an `ETL Bucket` under `BUCKET_LIST`, and one tenant may
also have an `ETL Bucket` under a different family of its own (`PIPELINE_IDS` was the example here
when this question was written; it no longer exists, removed 2026-09-07 -- see §8 -- but the
principle the example illustrated is unaffected: `PIPELINE_HOME_PAGES` or `TASK_GROUPS` would make
the same point today).
(c) Parents globally unique, children unique within `(tenant_id, parent_lookup_id)` -- two partial
indexes.

**Recommendation: (c).** It is the only one that matches what the code actually does.
`LookupDataCacheService` keys its process-wide map on the parent's `lookup_type`
(`LookupDataCacheService.java:48-52, 70-72`) and `SettingServiceImpl`'s three family sets are sets
of parent type strings (`:66, 82, 93`) -- so parent names must stay globally unique or both break.
Children are a different thing entirely: `fetchSubLookupByParentId` scopes them per parent and per
tenant already (`:547-563`), and nothing looks a child up by name across families. Option (a) would
let a second `BUCKET_LIST` parent exist under a tenant and quietly corrupt the cache; option (b)
does not, but states a rule wider than anything relies on. Two partial unique indexes --
`WHERE parent_lookup_id IS NULL` on `lookup_type`, and one over
`(tenant_id, parent_lookup_id, lookup_type)` for the rest -- say exactly what is true.

**Q2. Should a platform admin be able to bind a shared task type to a Kafka profile from the
console at all?**

Today the dialog says no, with a note explaining that routing is a per-tenant override
(`task-type-dialog.ts:83-91`). But `source_task_type.kafka_connection_profile_id` exists, the
resolver reads it (`KafkaConnectionResolver.java:58-72`), `validateKafkaProfileOwnership` passes any
profile for a platform admin (`SettingServiceImpl.java:634-636`), and 3.1 depends on the answer.

**Recommendation: yes, render the control for a platform admin.** The note is accurate about the
route table and inaccurate about the screen it is on -- a platform admin's binding is the column,
not the route, and the column is the only binding a platform-owned task type can have. Leaving the
control hidden means a shared task type can never be pointed at anything but the platform default,
and means the value already sitting in that column for pre-rewrite rows is invisible and
unmaintainable. Keep the note for tenant admins, reworded to say that *their* choice is recorded as
a per-tenant override.

**Q3. Should the Kafka route survive when the type-level binding changes, or should setting one
clear the other?**

With both bindings live, a tenant admin who sets a route and a platform admin who later changes the
column produce a row whose effective connection is the route, invisibly.

**Recommendation: leave both, change nothing, and make the precedence visible instead (gap 20).**
Clearing one from the other would mean a platform admin's edit silently discarding a tenant's
override -- which is the same class of surprise as gap 1, in the opposite direction. The resolver's
order is deliberate and documented on the method (`KafkaConnectionResolver.java:34-48`); the fix for
"invisibly" is to show it, not to remove a layer.

**Q4. Does XML Configuration belong on the settings hub?**

It sits in Tools (`shell.ts:81`) and not among the hub's nine cards (`settings-hub.ts:50-69`), while
the hub's own nav hint calls it "Every area in one place" (`shell.ts:118-119`).

**Recommendation: add the card.** It is `settings/xml`, it is `TENANT_ADMIN`, and it is grouped in
this feature by every other measure. Two lines against a hint that currently overpromises. Leave the
Tools entry as well -- somebody composing a task payload reaches for Tools.

**Q5. Should the per-row Kafka action test the topic, the profile, or both?**

The old app tested the topic; the new one tries to test the profile and cannot.

**Recommendation: the topic (3.7).** The profile is already testable from its own screen with a
richer result -- cluster id, broker count, a persisted pass/fail on the row
(`KafkaConnectionProfileServiceImpl.java:331-343, 291-296`). The question a task-type row raises is
the one only `testTopic` answers: the cluster can be perfectly reachable and the topic still absent,
and that answer already exists and is currently reachable from nowhere.

**Q6. Should `SettingServiceImpl` and `KafkaConnectionProfileServiceImpl` start calling
`TenantFilterHelper.enableIfNeeded` (gap 16)?**

Thirteen other services do; these two hand-write the predicate instead.

**Recommendation: no -- record the exemption instead.** The hand-written queries here are more
precise than the filter could be: `findVisibleToTenant` deliberately excludes platform rows
(`KafkaConnectionProfileRepository.java:23-38`) while the entity's filter admits them
(`KafkaConnectionProfile.java:26`), and turning the filter on would not change that but would make
two rules where there is one. The real problem is that the declarations imply protection they do not
give. Add both services to `TenantFilterDeclarationTest`'s documented-exemption list, beside
`LookupData`'s, so the next reader is told rather than left to grep.

---

## 7. Resolved, 2026-09-05

**Q2 -- resolved as recommended.** `TaskTypeDialog` now renders a "Default Kafka connection" field
to every role, separated from the tenant-only "Your override" field below it: the type's own
`kafkaConnectionProfileId` (shared with every tenant that uses the type, since the column is not
tenant-scoped) saves through the ordinary `addSourceTaskType`/`updateSourceTaskType` payload, and
the tenant's per-tenant route is a second, distinct control that still only appears for a tenant
admin (`canRoute()`). The dialog's own hint text was reworded to describe the two layers rather
than implying only one exists. `Source Task Types` (the list screen) shows the effective name via a
new `kafkaDisplay()` -- the tenant's route if one is set, else the type's own default -- and that
pill now deep-links straight to Kafka Connections filtered to that one profile
(`kafka-connections.ts`'s new `?profileId=` query param, read on `ngOnInit` and cleared by
`clearFilters()`), so the two screens read as one system instead of a name with nothing behind it.
`testRoute()` was widened to match: it now tests the type's own default when no tenant override
exists, and only declines when neither layer names a profile (the bare cluster-default case, which
still has nothing to test against).

**A related, independently-confirmed fix landed alongside this**: the topic-name field's client-side
validator (`Validators.pattern(/^[a-zA-Z-]+$/)`) was stricter than the server's own pattern
(`KafkaTopicPartitionUtil`'s `^topic=([a-zA-Z0-9._-]{1,249})&partitions=\[([0-9]+|\*)\]$`), so a
genuinely valid topic name with a digit, dot, or underscore (`orders-v2`, `etl.jobs`) was rejected
in the browser before ever reaching the server's own, more permissive check. Widened to match
exactly.

**Q4 is now moot.** `admin/settings` (the settings hub) and `settings/xml` (the XML builder) were
both removed in full this session (frontend routes, nav entries, and -- for the hub -- its
component), independent of this question; there is no longer a hub to add a card to, and no XML
builder page to add it for.

Q1, Q3, Q5 and Q6 remain open -- none were touched by this pass.

---

## 8. Resolved, 2026-09-07 -- `PIPELINE_IDS` removed from this feature's lookup families

This is not a resolution of any open question this document itself posed -- none of Q1, Q3, Q5 or
Q6 above are about pipelines -- but it is a real, unannounced change to a fact several parts of this
document and the gap table rest on: `TENANT_OWNED_LOOKUPS` had four members (`BUCKET_LIST`,
`PIPELINE_IDS`, `PIPELINE_HOME_PAGES`, `TASK_GROUPS`); it now has three
(`SettingServiceImpl.java:70-72`). `PIPELINE_IDS` and every row under it (`lookup_id 1015` and its
children) were deleted outright by migration `V28__drop_pipeline_ids_lookup.sql`, which removes by
`parent_lookup_id = 1015` rather than a hardcoded child list -- a live dev environment had
accumulated more children than the four `V10` originally seeded (test pipelines added through the
app), and a hardcoded list left orphans blocking the parent row's own delete on `lookup_data`'s
self-referencing FK, caught by actually running the migration against that database, fixed, and
rerun. `TenantOwnedLookupTest.java` had `"PIPELINE_IDS"` dropped from its three array literals
(`:34, 72, 118`) to match.

**Why this belongs here and not only in `source-tasks`.** The decision this document would have
been the natural place to weigh in on -- should a fourth tenant-owned lookup family keep existing at
all -- was made without this document's gap table (rows 8, 12) or its "eight families" reasoning
(§3.9, now seven) being consulted, because the instruction that drove it came from the Source Task
side: "we all configure a pipeline with pipeline form now," not from anything wrong with the lookup
mechanism itself. `source-tasks`'s own synthesis document carries the full account of *why* --
`.ai/synthesis/source-tasks.md` §3.3's addendum and §6 Q1 -- including the option this document's
sibling grooming section (`.ai/grooming/platform-configuration.md` §2.9) would have recommended had
it been asked (keep the lookup, migrate the representation) versus what shipped (remove the lookup
entirely, since a `TaskForm` row already has to exist for every real pipeline choice and a second,
parallel catalogue of the same ids was redundant). This document's role is narrower: recording what
the removal costs and reduces on **this** feature's own accounting, which follows.

**What changes here, concretely:**

- Gap 8's blast radius shrinks by one family: a null-tenant `TENANT_ADMIN` exploiting
  `deleteLookupData`'s missing ownership check can no longer reach `PIPELINE_IDS` children, because
  there are none. `BUCKET_LIST`, `PIPELINE_HOME_PAGES` and `TASK_GROUPS` remain exposed; the fix in
  §3.5 is unchanged and still needed for those three.
- Gap 12's citation moved (`SettingServiceImpl.java:68` → `:70-72`); the underlying gap --
  `TASK_GROUPS` unseeded -- is untouched.
- §3.9's "eight families" becomes seven, and the `forkJoin` gap 15 describes now scales over one
  fewer parent on a fresh install.
- Q1's `PIPELINE_IDS` example (the `(b)` candidate) no longer names a family that exists; the
  uniqueness question itself, and the recommendation of `(c)`, are unaffected -- the example just
  needs a different family to illustrate the same point, which `PIPELINE_HOME_PAGES` or
  `TASK_GROUPS` do equally well.
- A new endpoint this document's own `5.1`-equivalent table in the grooming document did not
  previously carry: `GET taskForm.json/listPipelines` (`TaskFormRestApi.java`, `TENANT_USER`),
  which replaces the deleted lookup as the way Source Task's Pipeline picker, in both frontends,
  populates itself. It belongs to `TaskFormRestApi`, not `SettingRestApi`, so it is not this
  feature's endpoint to own -- it is named here only because its existence is the reason removing
  the lookup was safe to do at all.
- `ProducerBulkEngine.getSourceJobDetail` (`process/src/main/java/process/engine/`), which used to
  resolve a task's `pipelineId` through `findLookupValueByLookupId` the same way it still resolves
  `homePageId`, now passes the string straight through -- `SourceTask.pipelineId` is no longer a
  lookup row id, it is the pipeline's own id string. This is `source-tasks`' and `source-jobs`'
  runtime to describe in full; noted here only because it is further confirmation that no code path
  left in this feature still expects `PIPELINE_IDS` rows to exist.

**Not decided or verified by this addendum:** whether any `source_task` row written before
2026-09-07 still holds an old numeric `PIPELINE_IDS` lookup id in its `pipeline_id` column, and if
so how many. No migration was written to backfill or repoint such rows -- deliberately, per the
`TENANT_OWNED_LOOKUPS` javadoc's own long-standing precedent that a task keeps running when the
lookup row behind its stored id disappears, it just stops resolving to a friendly name. Whether that
precedent is acceptable for this codebase's actual data was not audited before the change shipped;
`source-tasks`' synthesis document records the same gap from its side.
