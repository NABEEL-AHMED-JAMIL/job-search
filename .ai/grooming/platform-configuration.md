# Grooming -- Platform Configuration

Feature 15 in `.ai/discovery/features.md`. Status **partial**: old `setting` (two tabs),
`setting/lookup`, `setting/subLookup` and ~~`setting/lookpXml`~~ → new `settings/task-types`,
`settings/kafka`, `settings/lookup`. ~~`setting/lookpXml` → `settings/xml`, plus a new index at
`admin/settings`~~ -- **both halves of that one mapping are gone now, for two unrelated reasons on
two different dates.** The old app's `setting/lookpXml` screen (`XmlConfigurationComponent`, its
route, and its declarations) was deleted **2026-09-07** as part of the same pass that removed the
`PIPELINE_IDS` lookup family (see 2.8, 2.9 and 12.19). The new app's `settings/xml` and its
`admin/settings` index were already gone before that, removed **2026-09-05** in commit `889ae2e`
("Remove Dynamic Forms and Query/Search Engine; UI component refactors and fixes") -- unrelated to
and two days ahead of the 2026-09-07 work, and this document had simply not caught up to it until
now. Neither removal is new scope for this feature; both are recorded in place below rather than
silently dropped. See 2.1, 2.8 and 12.19/12.20.

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Purpose

This is where somebody says what the platform is made of, before anybody runs anything on it.

Four separate answers live here, and they are grouped together only because they are all
"settings":

- **Source Task Types.** A task type is a name for a downstream consumer and the Kafka topic that
  reaches it. Nothing in the product publishes a message without one: a job points at a task, the
  task points at a task type, and the task type carries `topic=…&partitions=[…]`. Creating one is
  what makes a new pipeline addressable. Delete one and every job built on it stops running.
- **Kafka Connections.** A task type says *which topic*; a Kafka connection profile says *which
  cluster, and how to log in to it*. Bootstrap servers, security protocol, SASL credentials, TLS
  material. One profile per tenant is the default, and a task type can be pinned to a specific
  profile so that, say, the archive pipeline publishes to a different broker from the live one.
  The screen also answers "is it actually reachable?" -- the connection test opens a real
  `AdminClient` and records the result on the row.
- **Lookups.** A two-level key/value tree the rest of the application reads at runtime: ~~the list of
  pipeline ids a task can pick from,~~ the home-page URL for each pipeline, the task groups, the
  buckets Object Browser offers, the AI providers an agent can name, and -- for a platform admin
  only -- the engine's own dials, such as how many queue rows the dispatcher pulls per cycle and
  the timestamp the scheduler resumes from. A value can be marked encrypted, which is how an API
  key gets stored here without being readable afterwards. **The list of pipeline ids is no longer
  part of this tree** (removed 2026-09-07, see 2.9) -- Pipeline Forms, a screen owned by
  `source-tasks`, is now the sole catalogue of which pipelines exist.
- **XML Configuration.** ~~A scratch tool. Type a list of tag keys, parents and values; the server
  assembles them into a master-data XML document; copy or download it. It writes nothing and reads
  nothing.~~ **Neither app still offers this as a standalone tool, for two unrelated reasons on two
  different dates (2.8, 12.19, 12.20)** -- the old app's scratch screen was removed 2026-09-07
  alongside the `PIPELINE_IDS` work above, and the new app's own version was already gone from
  2026-09-05. What survives is the capability underneath, unchanged: `setting.json/xmlCreateChecker`
  still turns a list of tag keys, parents and values into a master-data XML document; it just has no
  screen of its own to call it from any more, only the two call sites 2.8 names. It exists because a
  task payload is XML and somebody -- a person, or now a Pipeline Form's own answers -- has to
  compose one.

The one thing an operator would say ties them together: **a task type is useless without a Kafka
profile behind it, and** ~~a task is useless without a lookup entry to pick its pipeline from~~
**(2026-09-07: a task is useless without a Pipeline Form to pick its pipeline from instead -- the
lookup entry this used to mean no longer exists, see 2.9).** This is the screen you finish before
the Tasks screen will do anything for you.

---

## 2. Existing behaviour

### 2.1 Where each app puts it

| | Old | New |
|---|---|---|
| Source task types | `setting`, first of two tabs (`_component/setting/setting.component.html:13-20`) | `settings/task-types` |
| Kafka connections | `setting`, second tab -- the same route, a Bootstrap tab pane (`setting.component.html:234-238`) | `settings/kafka` |
| Lookups (parents) | `setting/lookup` | `settings/lookup`, parents and children on one screen |
| Lookups (children) | `setting/subLookup?lookupId=…`, a second route | -- merged into the row above |
| XML builder | ~~`setting/lookpXml` -- the typo is in the real path, and no navbar entry links to it~~ **removed 2026-09-07** -- the route, `XmlConfigurationComponent` and its template no longer exist (see 2.8, 12.19) | ~~`settings/xml`, linked from Tools (`features/shell/shell.ts:81`)~~ **removed 2026-09-05**, commit `889ae2e` -- `scheduler1/next/src` has no `xml-builder` directory left (see 2.8, 12.20) |
| An index of all of this | none | ~~`admin/settings`, nine cards (`features/settings/hub/settings-hub.ts:50-69`)~~ **removed 2026-09-05**, same commit as above (see 12.20) |

Old routes are guarded by `RoleGuard` with `data: { roles: ['PLATFORM_ADMIN', 'TENANT_ADMIN'] }`
(`app.routing.ts:109-113, 123-126, 130-133`) -- **three** routes now, not four:
`setting/lookpXml`'s guard is gone along with the route (removed 2026-09-07, see 2.8). New routes
are guarded by `roleGuard` with `data: { minRole: 'TENANT_ADMIN' }` and let the hierarchy in
`AuthService.hasAtLeast` admit the platform admin. Of the five routes this used to name
(`app.routes.ts:178-183, 238-243, 245-250, 251-256, 265-270`), two -- `settings/xml` and
`admin/settings` -- no longer exist (removed 2026-09-05, see 2.8); the citation is kept here for
the three that remain (`settings/task-types`, `settings/kafka`, `settings/lookup`) and the reader
should not expect all five guards to still be found at those five line ranges.

### 2.2 Source Task Types -- the old screen

`_component/setting/setting.component.ts` (217 lines) and its template.

- Loads from `setting.json/appSetting` and keeps `response.data.sourceTaskTypes`
  (`setting.component.ts:63-79`). Soft-deleted rows are filtered out in a getter
  (`:55-57`).
- Table columns: id, service name, topic (parsed out of `queueTopicPartition` by
  `global-config.ts:87-94`), description, link count, Kafka profile name, status, actions
  (`setting.component.html:46-122`).
- The Kafka profile cell shows `sourceTaskType.kafkaConnectionProfileName` or the literal
  `(tenant default)` (`setting.component.html:73-78`).
- Row actions: **test Kafka connection for this row's topic**, edit, and a kebab with Download
  (JSON, via `CommomService.createFile`) and Delete.
- The test button resolves the topic name out of `queueTopicPartition` with its own regex and calls
  `kafkaConnectionProfile.json/testTopic` (`setting.component.ts:85-113`). It answers the question
  "is *this task type's* topic reachable?".
- The link count opens a modal listing the tasks built on the type, from
  `sourceTask.json/fetchAllLinkSourceTaskWithSourceTaskTypeId`, with a search box **and a group
  dropdown**, and a Select button that navigates to `/editTask/:id`
  (`setting.component.ts:120-166`, `setting.component.html:147-232`).
- Delete confirms with "On press 'Yes' all the source job will delete state and will not run"
  (`setting.component.html:136`). On success the row's status is mutated to `Delete` in place
  rather than reloading (`setting.component.ts:201-208`).

The add/edit dialog is `_component/setting/source-task-type/source-task-type.component.ts` (216
lines):

- Fields: service name, topic name, partition (a select of `*` and 0–10), description, Kafka
  connection profile (a select of active profiles, blank = tenant default), and -- edit only --
  status (`source-task-type.component.html:11-82`).
- `queueTopicPartition` is a hidden control recomposed from the two visible fields immediately
  before submit (`source-task-type.component.ts:199-206`), and decomposed on edit by a regex
  (`:186-197`).
- Every field except the Kafka profile carries `Validators.required` (`:88-99`, `:129-143`).
- The payload includes `kafkaConnectionProfileId`, which the server writes to
  `source_task_type.kafka_connection_profile_id`.

### 2.3 Source Task Types -- the new screen

`features/settings/task-types/task-types.ts` (275 lines) and `task-types.html` (282 lines).

Everything above survives except the topic test, and a good deal is added:

- Four stat tiles: task types, linked tasks, unused, and the number of Kafka profiles available
  (`task-types.html:20-29`).
- `TableShell` gives real loading, error-with-retry and empty states (`shared/ui/data-table.ts:42-60`).
- A status filter, a search over name/description/topic, an "Only mine" author filter, a
  table/cards `ViewToggle`, and Created by / Updated by columns.
- Topic and Partitions are separate columns, both parsed through the shared
  `shared/ui/topic.ts` helper rather than a per-screen regex.
- The linked-tasks panel is rendered inline under the table rather than in a modal, with a search
  box. The **group dropdown is gone**; group is a column only (`task-types.html:224-281`).
- Export as JSON survives, with the comment "as the legacy screen's download did"
  (`task-types.ts:111-121`).
- Delete confirms through the shared `confirmWith` dialog and names the linked-task count
  (`task-types.ts:234-253`).
- The Kafka column and the "Test Kafka connection" action are hidden from a platform admin, on the
  correct reading that the route endpoints refuse one (`task-types.ts:134`, `:145-147`).

The dialog is `task-type-dialog.ts` (212 lines). It differs from the old one in three ways that
matter:

1. **Routing is written through the route endpoints, not the type.** The payload deliberately omits
   `kafkaConnectionProfileId` (`task-type-dialog.ts:161-167`); a second call afterwards does
   `setKafkaRoute` or `deleteKafkaRoute` (`:192-211`). Those three endpoints exist on the server and
   are declared in the old app's service (`_services/kafka-connection-profile.service.ts:48-59`) but
   **no old screen ever calls them** -- verified by searching `scheduler1/src` for the identifiers.
2. **Topic and partition carry client-side patterns** -- `/^[a-zA-Z-]+$/` and `/^(\*|10|[0-9])$/`
   (`task-type-dialog.ts:128-134`).
3. **Description is not required** (`:130`), where the old form required it.

### 2.4 Kafka Connections -- the old tab

`_component/setting/kafka-connection-profile/kafka-connection-profile.component.ts` (447 lines).

- Lists `kafkaConnectionProfile.json/fetchAllProfiles`, filtering out `Delete` in a getter
  (`:183-189`).
- Filters: **Scope** (Platform-wide / Tenant, platform admin only), security protocol, status,
  and a text search (`kafka-connection-profile.component.html:7-13`). A **Scope column** shows
  `Platform-wide` or `Tenant #N`, again platform-admin only (`:60`, `:76-78`).
- A `canManage(profile)` helper gates row actions on ownership (`component.ts:87-92`).
- The form covers profile name, environment label, bootstrap servers, security protocol, SASL
  mechanism/username/password, keystore bucket+location+passwords, truststore bucket+location+
  password, and additional properties (`:228-245`).
- TLS material is uploaded **through the generic object endpoint**: the component picks a bucket,
  generates a prefix `kafka-secrets/{epochMillis}-{random}/` itself, and calls
  `storage.json/uploadObject` (`:118-170`). Nothing validates the file; nothing builds a store.
- Per-row test, set-as-default, clear-default, delete, and an in-dialog test that probes the unsaved
  edits (`:280-318`, `:384-445`).
- Save strips blank password fields so a blank means "keep the stored one" (`:336-347`).

### 2.5 Kafka Connections -- the new screen

`features/settings/kafka/` -- 6 source files, 2 spec files, 2,995 lines in total. This is the
largest single gain in the rewrite.

- `kafka-connections.ts` (259): the list, four tiles (profiles, tested OK, failing, default), a
  banner when no profile is default, protocol/status filters, search, "Only mine", sorting, cards
  view, per-row test / set default / clear default / delete.
- `kafka-dialog.ts` (339): the form, with a protocol-driven layout -- SASL fields appear only for
  `SASL_*`, the whole TLS section only for `SSL`/`SASL_SSL` -- a plain-language summary of what the
  chosen combination asks for, an inline test-result card, and conditional validators wired to the
  same signals that draw the required asterisks (`:248-262`).
- `kafka-profile-form.ts` (254): the rules, extracted so they can be tested. `profilePayload`
  drops blank secrets, nulls fields the protocol no longer uses, and sets the `clear*` flags
  (`:92-117`). `additionalPropertiesJson` runs Gson's parse in the browser (`:62-81`).
- `kafka-tls-section.ts` (978): two independent routes for TLS material -- upload PEM certificates
  and have the server build the stores, or upload a store you built yourself -- with per-slot file
  pickers, certificate summaries, and removal semantics.
- `kafka-secret.service.ts` (81): `kafkaSecret.json/uploadSecret`, `/generateTruststore`,
  `/generateKeystore`. **None of these three exists in the old app** -- searching `scheduler1/src`
  for `kafkaSecret` returns nothing.
- Two spec files, 66 assertions between them, covering the rule modules only.

What the new screen does **not** have: the Scope filter and the Scope column. A platform admin sees
every tenant's profiles in one undifferentiated list with nothing saying whose they are.

### 2.6 Lookups -- old

Two routes and three components.

`setting/lookup` (`_component/setting/setting-lookup.component.ts`, 71 lines) lists the parents from
`appSetting`'s `lookupDatas` and offers Edit and a "Sub Lookup" button that navigates to
`setting/subLookup?lookupId=…` (`:54-61`). There is **no delete on a parent** and no add-child in
place.

`setting/subLookup` (`sub-lookup.component.ts`, 103 lines) reads
`setting.json/fetchSubLookupByParentId`, shows the parent's four fields as a detail panel, and lists
the children with Edit and Delete (`:76-93`, `:54-74`). Delete fires immediately -- there is no
confirmation, the kebab item is wired straight to `deleteLookupData` (`sub-lookup.component.html:83-89`).

The shared dialog (`lookup/lookup.component.ts`, 142 lines) has Type, Value (a 6-row textarea),
an **Encrypt this value** checkbox and Description. The important detail is `editLookupData`:

```
lookupValue: [isEncrypted ? '' : lookupData.lookupValue, isEncrypted ? [] : Validators.required],
```

(`lookup.component.ts:103`). For an encrypted row it **blanks the field and drops the required
validator**, and the placeholder says "Leave blank to keep the existing encrypted value"
(`lookup.component.html:27`).

### 2.7 Lookups -- new

`features/settings/lookup/lookup.ts` (194 lines), `lookup.html` (251), `lookup-dialog.ts` (126).
One screen, one route.

- `load()` reads `appSetting` for the parents, then `forkJoin`s a `fetchSubLookupByParentId` per
  parent so the Entries count is known before anything is expanded (`lookup.ts:53-90`). On a
  hundred parents that is a hundred requests.
- Parents are rows; children are indented rows revealed by a chevron. Both views (table and cards)
  render an encrypted value as a `lock` pill reading "encrypted" rather than as the masked string
  (`lookup.html:140-146`, `:198-204`).
- `canModify(entry)` returns true for a platform admin, or for a row whose `tenantId` matches the
  caller's, and gates the **child** row's edit and delete buttons; a row it refuses shows a
  "shared" pill instead (`lookup.ts:187-193`, `lookup.html:217-232`).
- The **parent** row's kebab offers Edit, Add entry and Delete with no such gate
  (`lookup.html:174-186`), and "New lookup" in the page header creates a top-level row
  (`lookup.html:14-16`).
- Delete confirms through `confirmWith` and names the child count (`lookup.ts:117-138`).
- The dialog prefills `lookupValue` from `data.lookup?.lookupValue` with an unconditional
  `Validators.required` (`lookup-dialog.ts:95`). There is no special case for an encrypted row.

### 2.8 XML Configuration

Old (`_component/setting/xml-configuration/xml-configuration.component.ts`, 84 lines) --
**removed entirely 2026-09-07**, in the same pass that dropped the `PIPELINE_IDS` lookup family
(2.9, 12.19). Confirmed by `ls`ing the directory (no longer exists) and grepping
`app.routing.ts`, `app.module.ts` and `_component/index.ts` for `XmlConfiguration` (no matches in
any of the three). What it used to be, for the record: six blank rows in a `FormArray`, each row
`tagKey` (required) / `tagParent` / `tagValue`; +/- buttons per row; submit posted
`{ xmlTagsInfo: [...] }` to `setting.json/xmlCreateChecker` and dropped `response.message` into a
textarea; a Download button saved it as `Raad-Master-Data {uuid}.xml`. There was a `file`/`addFile`
pair that nothing called. Nothing else in the old app read from or wrote to this screen, which is
why it was safe to delete outright rather than needing a replacement (12.19).

**The endpoint it called is not orphaned by the removal.** `setting.json/xmlCreateChecker` is
untouched and still fully live (`SettingRestApi.java:154-168`), and still has two real callers,
just not this one any more: the old app's Source Task editor, whose "Show the Xml Output" button
(`_component/source-task/task/task.component.html:210`) calls it through
`ConfigurationMakerService.getXmlData` inside a method named `submintTageForms` (typo intact in the
real code, `task.component.ts:83, 316-327`) -- **`ConfigurationMakerService` is very much alive**;
only the standalone screen above is gone, not the service every other consumer of this endpoint
still depends on -- and the next app's Task Edit, which now calls the same endpoint automatically
from `save()` whenever a pipeline form is driving the task, in place of the manual preview button
that screen used to have (`scheduler1/next/src/app/features/tasks/edit/task-edit.ts:372`; see
`.ai/grooming/source-tasks.md` §12.7 and §4.3 for the full account of that button's removal, which
belongs to that document, not this one).

New (`features/settings/xml-builder/xml-builder.ts`, 122 lines) -- ~~the same six starting rows and
the same endpoint, plus a `problems()` computed…~~ **This is a second, unrelated removal, and it
predates the one above: the screen was already gone before this document's last update, deleted
2026-09-05 in commit `889ae2e` ("Remove Dynamic Forms and Query/Search Engine; UI component
refactors and fixes"), two days ahead of and unconnected to the `PIPELINE_IDS` work.** Searching
`scheduler1/next/src` for `xml` and for `hub` turns up nothing: no `xml-builder` directory, no
`settings/xml` route, no `admin/settings` hub. What follows is kept only as the historical record of
what used to occupy this slot, not a description of anything reachable today: the same six starting
rows and the same endpoint, plus a `problems()` computed that checked, before the request left, for
an empty set, duplicate keys, names that were not valid XML names, a parent that was not itself a
tag, a self-parent, and the case where every tag had a parent so there was no root. Blank rows were
ignored rather than rejected. The parent field was a `datalist` of the other rows' keys. Copy and
Download; the filename was `master-data-YYYY-MM-DD.xml`. See 12.20 for what this removal means for
this document's other XML-builder references, most of which describe acceptance criteria and UI
states for a screen that is no longer there to check.

### 2.9 What the server does

`process/src/main/java/process/api/SettingRestApi.java` -- class-level
`@PreAuthorize("hasRole('TENANT_ADMIN'))` (`:24`). ~~one method-level override to `PLATFORM_ADMIN`
on `dynamicQueryResponse` (`:43`, which belongs to `query-and-search-engines`, not here)~~ --
**pre-existing staleness, unrelated to and predating the 2026-09-07 work in this section**:
`dynamicQueryResponse` no longer exists on this controller at all. It was removed 2026-09-05 in the
same `889ae2e` commit that removed the XML builder screen (2.8), for the reason its own message
names ("Remove Dynamic Forms and Query/Search Engine") -- nothing to do with `PIPELINE_IDS`. Every
method on `SettingRestApi` today is `TENANT_ADMIN` by the class annotation alone; there is no
method-level override left on this controller. Its removal also shifted every later line number
this document cites in `SettingRestApi.java`: `xmlCreateChecker` is now at `:154-168`, not
`:172-186` (5.1, 7, 12.17), and `deleteLookupData` is now at `:143`, not `:161` (5.1, 12.18).

`SettingServiceImpl.java` (644 lines) carries the whole of the tenancy model for this feature, and
it is worth reading as three sets rather than as methods:

- `TENANT_OWNED_LOOKUPS` = ~~`BUCKET_LIST`, `PIPELINE_IDS`, `PIPELINE_HOME_PAGES`,
  `TASK_GROUPS`~~ **`BUCKET_LIST`, `PIPELINE_HOME_PAGES`, `TASK_GROUPS`** (`:70-72`, `PIPELINE_IDS`
  removed 2026-09-07). The javadoc directly above the field now explains why: Task Forms "took over
  as the source of truth for which pipelines exist: a pipeline is now defined by creating its form
  (Configuration -> Pipeline Forms), not by adding a lookup row, and Source Task picks from that
  list instead" (`:55-58`), and it names the migration that removed the rows themselves --
  `V28__drop_pipeline_ids_lookup.sql`, which deletes by `parent_lookup_id = 1015` rather than a
  hardcoded child-id list, because a live dev environment had accumulated far more than the four
  `V10` seeded (test pipelines added through the app), and a hardcoded list left orphans blocking
  the parent row's own delete on `lookup_data`'s self-referencing FK -- caught by actually running
  the migration against that real database, fixed, and rerun. Its rollback block re-inserts the
  original V2/V10 seed rows as a best-effort undo, matching the style of `V25`-`V27`'s own rollback
  blocks. `TenantOwnedLookupTest.java` had `"PIPELINE_IDS"` removed from every array literal that
  used to list it beside the other three (`:34, 72, 118`). A tenant admin may add children to what
  remains of this set, sees only its own, and owns what it adds.
- `TENANT_EXTENDABLE_LOOKUPS` = `AI_PROVIDER` (`:86-87`). A tenant sees the platform's children as
  well as its own, may add its own, and may not touch the platform's.
- `PLATFORM_ONLY_LOOKUPS` = `QUEUE_FETCH_LIMIT`, `SCHEDULER_LAST_RUN_TIME`,
  `AUDIT_LOG_SYNC_LAST_RUN_TIME`, `EMAIL_RECEIVER` (`:97-100`). Hidden from `appSetting` for anyone
  but a platform admin and refused outright by `fetchSubLookupByParentId` (line numbers for both
  not re-verified in this pass -- see the note on file-wide citation drift at the end of 12.19).

`familyOf` reads a row's family from its **parent's** type, because a child carries its own
descriptive label (`:102-109`), and `refuseModification` is the single predicate that decides
whether the caller may change a row (`:122-144`).

For task types, `isSourceTaskTypeOwnedByCaller` (`:360-368`) requires a matching non-null tenant;
`isSourceTaskTypeVisibleToCaller` (`:370-375`) additionally admits a null-tenant platform row.
`appSetting` is `@Cacheable`, keyed `'platform'` or the tenant id (`:207-208`), and every mutator
evicts it.

`KafkaConnectionProfileServiceImpl.java` (734 lines) is the deepest file in the feature.
`scopedFind` (`:539-553`) refuses a deleted row and any row whose tenant does not match, for
anyone but a platform admin; `callerOwns` (`:560-566`) is kept separate because a platform admin
can reach a row it does not own. `getProfileDto` (`:699-732`) never returns a secret -- only
`*Configured` booleans -- and withholds the store bucket/location from a caller who does not own
the profile, on the stated ground that "where the key material sits is as good as the key material"
(`:713-715`). `refuseMovedCredential` (`:517-537`) refuses to reuse a stored SASL password when the
edit moves the brokers, protocol, mechanism or username, which is the rule that stops a caller who
has never seen the password pointing the profile at a broker they run and having the server
authenticate to it.

`KafkaSecretServiceImpl.canUseObject` (`:202-224`) decides who may attach a stored file to a
profile: the uploader themselves, or a tenant admin over a `TENANT_USER` in the same tenant --
explicitly not over a peer administrator. The key layout is
`kafka-secrets/{appUserId}/{uuid}/{yyyy-MM-dd}/{filename}`, entirely server-chosen, and
`KafkaSecretPath.parse` re-serialises what it parsed and compares it to the input, so `+1248` and
`01248` cannot be read as user 1248 (`util/KafkaSecretPath.java:91-102`).

### 2.10 Tests that exist

| File | What it covers |
|---|---|
| `process/src/test/java/process/model/service/impl/TenantOwnedLookupTest.java` | 9 tests over `isTenantOwned` / `isTenantExtendable` / `isPlatformOnly`, including that a child is judged by its family and that an unknown family defaults to platform-level |
| `process/src/test/java/process/util/KafkaTopicPartitionUtilTest.java` | The topic/partition grammar, including that `orders-v2`, `etl.jobs.inbound`, `job_events` and `TOPIC9` are accepted |
| `process/src/test/java/process/util/KafkaSecretPathTest.java` | The secret key layout and its parse |
| `process/src/test/java/process/model/pojo/TenantFilterDeclarationTest.java` | Which entities declare the tenant filter, and why `LookupData` is exempt |
| `process/src/test/java/process/config/KafkaConnectionResolver*Test.java` | Two files over the dispatch-time resolution order and its tenant isolation |
| `scheduler1/next/src/app/features/settings/kafka/kafka-profile-form.spec.ts` | 36 assertions: protocol rules, JSON properties, payload shape, clear flags |
| `scheduler1/next/src/app/features/settings/kafka/kafka-tls-section.spec.ts` | 30 assertions: upload slots, store fields, removal semantics |
| `scheduler1/next/src/app/shared/ui/topic.spec.ts` | The shared topic parser |

**Nothing tests:** `SettingServiceImpl`'s endpoints (only its three private predicates are
reached, by reflection); `refuseModification` itself; `KafkaConnectionProfileServiceImpl`'s eight
service methods; `task-types.ts`, `task-type-dialog.ts`, `lookup.ts`, `lookup-dialog.ts` or
`kafka-connections.ts`/`kafka-dialog.ts` (~~`xml-builder.ts`~~ removed from this list along with the
file itself, 2026-09-05, see 2.8, 12.20). The old app has **no** spec files at all.

---

## 3. Expected behaviour

Most of section 2 is already what is wanted. This section says only where it is not.

**A task type keeps its Kafka binding when it is edited.** Today the new dialog omits
`kafkaConnectionProfileId` from the payload and `updateSourceTaskType` writes whatever it was sent,
so editing a description clears the binding. Both bindings -- the type-level column and the
per-tenant route -- must survive an edit that did not touch them, and a binding chosen on the
create dialog must actually be applied.

**The Kafka column tells the truth.** `fetchKafkaRoute` returns a bare id as `data`; the console
reads `data.kafkaConnectionProfileId`, which is never there. Whichever side moves, the two must
agree, and the column must show the effective profile -- route first, type default second, tenant
default third -- because that is the order `KafkaConnectionResolver` will actually use at dispatch
time (`config/KafkaConnectionResolver.java:49-82`).

**Editing an encrypted lookup does not destroy it.** The value must not be pre-filled with the mask,
blank must mean "keep what is stored", and the field must say so. The old app got this right.

**The console does not offer a control that can only be refused.** A tenant admin sees Edit,
Delete and "New lookup" on parent rows that the server will refuse every time. Either the controls
are gated the way the child rows already are, or -- for a family a tenant genuinely owns -- the
server is widened. It cannot stay as it is.

**Topic validation on the client matches the server.** The server accepts
`[a-zA-Z0-9._-]{1,249}` (`util/KafkaTopicPartitionUtil.java:22-23`, with a test naming
`orders-v2`); the dialog rejects anything but letters and hyphens and tells the operator the server
does too. The client rule must be the server's rule or absent.

**Changing a task type's status does not corrupt its jobs.**
`statusChangeSourceJobLinkWithSourceTaskTypeId` writes `UPPER(?2)` into `source_job.job_status`
(`model/repository/SourceJobRepository.java:57`), producing `ACTIVE`/`DELETE` against a title-case
enum -- the exact data bug `V16.0-fix-source-job-status-casing` was written to repair.

**An operator can ask whether a topic is reachable.** The old per-row topic test answered a
question the profile-level test does not: the profile can be perfectly reachable while the topic
this type names does not exist on it. `testTopic` is still on the server and still returns the
specific answer "Topic X does not exist on the connected cluster"
(`KafkaConnectionProfileServiceImpl.java:386-388`).

**A platform admin can tell whose Kafka profile is whose.** `findVisibleToPlatformAdmin` returns
every tenant's rows (`model/repository/KafkaConnectionProfileRepository.java:20-21`) and the new
screen renders them with no owner column and no scope filter.

**Two tenants can both have a lookup entry called the same thing.** `lookup_data.lookup_type` is
globally `UNIQUE` on a table that carries `tenant_id`.

---

## 4. Frontend requirements

### 4.1 Routes and shell

| Route | Component | Guard | Nav |
|---|---|---|---|
| `settings/task-types` | `features/settings/task-types/task-types.ts` `TaskTypes` | `roleGuard`, `minRole: 'TENANT_ADMIN'` | Configuration → Source Task Types (`shell.ts:106`) |
| `settings/kafka` | `features/settings/kafka/kafka-connections.ts` `KafkaConnections` | same | Configuration → Kafka Connections (`shell.ts:116`) |
| `settings/lookup` | `features/settings/lookup/lookup.ts` `Lookup` | same | Configuration → Lookups (`shell.ts:112`) |
| ~~`settings/xml`~~ | ~~`features/settings/xml-builder/xml-builder.ts` `XmlBuilder`~~ | ~~same~~ | ~~**Tools** → XML Configuration (`shell.ts:81`)~~ **removed 2026-09-05**, before and unrelated to the 2026-09-07 work this document otherwise covers -- see 2.8, 12.20 |
| ~~`admin/settings`~~ | ~~`features/settings/hub/settings-hub.ts` `SettingsHub`~~ | ~~same~~ | ~~Configuration → All settings (`shell.ts:118`)~~ **removed 2026-09-05**, same commit -- see 12.20 |

~~The settings hub lists nine cards and filters `platformOnly` ones by role
(`settings-hub.ts:50-74`). **XML Configuration is not one of the nine** -- it is reachable from the
Tools menu only. Either add it to the hub or accept that the hub is a configuration index and the
XML builder is a tool; the two files should not disagree silently.~~ **Moot, 2026-09-05.** Neither
the settings hub nor the XML builder exists any more (`scheduler1/next/src/app/features` has no
`hub` and no `xml-builder` entry), so there is no longer a disagreement between the two to resolve --
see 12.20 and `synthesis/platform-configuration.md` §7, which records this same fact and marks its
own open question Q4 moot for the same reason.

### 4.2 Components

- `TableShell` (`shared/ui/data-table.ts`) supplies loading / error+retry / empty for all four list
  screens.
- `Field` (`shared/ui/field.ts`) supplies label, asterisk, hint and error text for every control in
  the three dialogs. Note that `[required]` only draws the asterisk; the validator must be set
  separately, which is what `kafka-dialog.ts:248-262` exists to keep in step.
- `FormDialog` supplies the dialog chrome and the saving state.
- `confirmWith` (`shared/ui/confirm.ts`) supplies every destructive confirmation.
- `StatTile`, `StatusPill`, `ViewToggle`, `MineFilter`, `Icon`, `createSort` are shared.
- `shared/ui/topic.ts` is the single parser/formatter for `queueTopicPartition` and must stay the
  only one; three screens each had their own before it (`topic.ts:7-16`).

### 4.3 Tables

**Task types** (`task-types.html:135-220`): Service (name + `#id`), Description, Topic, Partitions,
Kafka *(hidden for a platform admin)*, Tasks, Created by, Updated by, Status, kebab. Kebab: Edit,
Test Kafka connection *(tenant only)*, Linked tasks, Export as JSON, Delete.

**Kafka** (`kafka-connections.html`): profile name with a default pill, environment label,
bootstrap servers, protocol pill, test-result pill (OK / Failed / Untested) with the last test
time, status, kebab. Add an **Owner** column, rendered for a platform admin only, showing
`Platform-wide` or the tenant, restoring `kafka-connection-profile.component.html:60,76-78`.

**Lookups** (`lookup.html:110-248`): chevron, Type, Value (or an "encrypted" pill), Description,
Entries, Created by, Updated by, kebab; child rows indented under an expanded parent with their own
edit/delete buttons or a "shared" pill.

~~**XML** (`xml-builder.html`): a five-column editable grid -- #, Tag key, Parent (a `datalist` of the
other keys), Value, row +/- -- beside an output panel.~~ **Removed 2026-09-05** -- there is no
`xml-builder.html` any more; see 2.8, 12.20.

### 4.4 Cards

All three list screens offer a `ViewToggle` persisting under `etl.view.<key>` (`task-types`,
`kafka`, `lookup`). Cards carry the same actions as the kebab. Nothing is available in one view
and not the other, and that must stay true of anything added.

### 4.5 Filters and tiles

| Screen | Tiles | Filters |
|---|---|---|
| Task types | Task types (+ active), Linked tasks, Unused, Routed | status, search, Only mine |
| Kafka | Profiles (+ active), Tested OK, Failing, Default | protocol, status, search, Only mine, **owner scope (to add, platform admin only)** |
| Lookups | none -- a count in the subtitle | search, Only mine |
| ~~XML~~ | ~~none~~ | ~~none~~ **removed 2026-09-05** -- there is no XML screen left to have tiles or filters (2.8, 12.20) |

A Clear button appears when any filter is set. "Only mine" is deliberately not persisted
(`shared/ui/mine-filter.ts:13-16`).

### 4.6 Dialogs

- **Task type** (`task-type-dialog.ts`): Service name*, Description, Topic*, Partition, Kafka
  connection *(tenant only; a platform admin gets an explanatory note instead)*, Status.
- **Kafka profile** (`kafka-dialog.ts`): wide; Profile name*, Environment label, Bootstrap
  servers*, Security protocol*, SASL mechanism*/Username*/Password (conditional), the TLS section
  (conditional), Additional properties, Status (edit only). A **Test connection** button in the
  footer, and an inline result card.
- **Lookup** (`lookup-dialog.ts`): Type*, Value*, Description, Store encrypted. The heading is
  "New lookup", "New entry" or "Edit lookup" depending on whether a parent was passed.
- **Confirmations**: delete task type (names the linked-task count), delete Kafka profile (names
  whether it is the default), delete lookup (names the child count).

### 4.7 Loading, empty and error

Every list screen goes through `TableShell`, so: a centred spinner while loading; a crit-toned
message with a "Try again" button on error; a muted icon and a message on empty, with the message
distinguishing "nothing matches the filters" from "nothing exists yet". Row-level actions report
through `ToastService`. ~~The XML builder has no loading state of its own -- the Build button
disables itself while `building()` is true -- and renders its validation problems as a list rather
than blocking silently (`xml-builder.html:84-88`).~~ **Removed 2026-09-05** -- there is no XML
builder screen to have a loading state, or the lack of one (2.8, 12.20).

The lookups screen's per-parent child fetches fail silently by design (`lookup.ts:78`) so one bad
parent does not empty the page; that is right, but the count then reads 0 for a parent whose
children could not be read, which is indistinguishable from a parent with none.

### 4.8 Dark and light

Theming is token-based in `scheduler1/next/src/styles.css`, switched by
`core/theme.service.ts`. Every colour in ~~these five screens~~ **the three screens that remain**
(task types, Kafka, lookups -- the XML builder and the settings hub were removed 2026-09-05, before
this document's last update; see 2.8, 12.20) must come from a token (`var(--text-muted)`,
`var(--color-crit-500)`, the `pill-*` and `icon-*` classes) -- there is no per-theme branch in any of
them today and none should be introduced. The old app has no dark mode at all, so there is nothing
to port.

### 4.9 Responsive

- Stat tiles: `grid-cols-2` → `md:grid-cols-4`.
- Cards: 1 → `sm:grid-cols-2` → `xl:grid-cols-3`.
- Tables are wrapped in `overflow-x-auto`; the linked-tasks table is wrapped separately
  (`task-types.html:254`).
- ~~The XML builder is a two-column grid at `lg:` and stacks below it (`xml-builder.html:19`).~~
  **Removed 2026-09-05** -- moot (2.8, 12.20).
- The Kafka dialog is `size="wide"` and its TLS section is the tightest layout in the app; it is
  stated to work from 544 px to 1244 px.

---

## 5. Backend requirements

### 5.1 Endpoints

`SettingRestApi` -- class-level `TENANT_ADMIN` (`SettingRestApi.java:24`).

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `setting.json/appSetting` | TENANT_ADMIN | Top-level lookups (platform-only families filtered out for a tenant) plus every visible task type with its link count. `@Cacheable` per tenant (`SettingServiceImpl.java:207-249`) |
| POST | `setting.json/addSourceTaskType` | TENANT_ADMIN | Validates name/description/topic, checks profile ownership, saves with the caller's tenant (null for a platform admin), then `ensureTopicExists` on the resolved connection (`:268-295`) |
| PUT | `setting.json/updateSourceTaskType` | TENANT_ADMIN | Same validation, plus an ownership check; cascades status to every linked source job (`:299-341`) |
| DELETE | `setting.json/deleteSourceTaskType` | TENANT_ADMIN | Soft delete; cascades `Delete` to every linked source job (`:345-358`) |
| GET | `setting.json/fetchKafkaRoute` | TENANT_ADMIN | The caller tenant's override for one task type. Returns `null` data for a platform admin (`:378-389`) |
| PUT | `setting.json/setKafkaRoute` | TENANT_ADMIN | Upserts the override; refuses a platform admin outright (`:393-417`) |
| DELETE | `setting.json/deleteKafkaRoute` | TENANT_ADMIN | Removes it; refuses a platform admin (`:421-430`) |
| POST | `setting.json/addLookupData` | TENANT_ADMIN | Requires a tenant-owned or tenant-extendable parent unless the caller is a platform admin; encrypts when asked; rebuilds the process-wide cache (`:443-475`) |
| PUT | `setting.json/updateLookupData` | TENANT_ADMIN | Ownership check, then `refuseModification`; blank value means "keep" only when the row was already encrypted (`:479-522`) |
| GET | `setting.json/fetchSubLookupByParentId` | TENANT_ADMIN | Parent detail plus children, filtered by family rules (`:525-572`) |
| **PUT** | `setting.json/deleteLookupData` | TENANT_ADMIN | Hard delete, body-carried id. Declared PUT, not DELETE (`SettingRestApi.java:143`, was `:161` before the unrelated 2026-09-05 removal of `dynamicQueryResponse` shifted every later line -- see 2.9) |
| POST | `setting.json/xmlCreateChecker` | TENANT_ADMIN | Builds XML from tag descriptors. Returns the document in **`message`**, not `data` (`SettingRestApi.java:154-168`, was `:172-186`, same shift). Mapped as `path = "xmlCreateChecker"` with no leading slash. Still called by the legacy Source Task editor's tag-to-XML button and, since 2026-09-07, automatically from the next app's Task Edit `save()` -- see 2.8 |

`KafkaConnectionProfileRestApi` -- class-level `TENANT_ADMIN` (`:20`).

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/addProfile` | TENANT_ADMIN | Validates, stamps the caller's tenant, `UNTESTED`, not default (`KafkaConnectionProfileServiceImpl.java:93-112`) |
| PUT | `/updateProfile` | TENANT_ADMIN | `scopedFind`, validate, `validateSecretReferences`, `refuseMovedCredential`, then apply; invalidates the template cache (`:115-151`) |
| **PUT** | `/deleteProfile` | TENANT_ADMIN | Refuses while a task type or a route still references it; soft-deletes and **wipes the four secret columns** (`:154-180`) |
| GET | `/fetchAllProfiles` | TENANT_ADMIN | A tenant's own rows only; every row for a platform admin (`:183-192`) |
| POST | `/setAsDefault` | TENANT_ADMIN | Active rows only; clears the previous default within the same scope (`:195-217`) |
| POST | `/clearDefault` | TENANT_ADMIN | Takes no argument -- a tenant has one default (`:220-227`) |
| POST | `/testConnection` | TENANT_ADMIN | Probes a detached copy so unsaved edits never reach the row; records the result when the caller owns it (`:230-298`) |
| GET | `/testTopic` | TENANT_ADMIN | Describes one topic on the profile the resolver picks for the caller (`:368-391`) |

`KafkaSecretRestApi` -- class-level `TENANT_ADMIN` (`KafkaSecretRestApi.java:33`).

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/uploadSecret` | TENANT_ADMIN | Parses the bytes to check the claimed kind, then stores under a wholly server-chosen key (`KafkaSecretServiceImpl.java:68-103`) |
| POST | `/generateTruststore` | TENANT_ADMIN | PKCS#12 from one or more stored CA certificates, password encrypted before the bytes are written (`:106-144`) |
| POST | `/generateKeystore` | TENANT_ADMIN | PKCS#12 from a stored certificate and its key, refusing a mismatched pair by name (`:147-186`) |

`sourceTask.json/fetchAllLinkSourceTaskWithSourceTaskTypeId` -- **TENANT_USER**, by a method-level
override at `SourceTaskRestApi.java:108`. An earlier draft of this document read `:109` (the
`@RequestMapping`) and concluded the class-level TENANT_ADMIN applied; it does not, because
`@PreAuthorize` is not repeatable and the method-level annotation REPLACES the class-level one.
The consequence matters: any TENANT_USER holding a token can enumerate the task names bound to a
task type, even though the route guard correctly sends them to `/unauthorized`. **A route refusal
is not an endpoint refusal.** The query already
excludes `task_status = 'Delete'` and is tenant-scoped for a non-platform caller
(`SourceTaskServiceImpl.java:472-480`).

### 5.2 Services

- `SettingService` / `SettingServiceImpl` -- task types, Kafka routes, lookups, XML. Owns the three
  lookup family sets and `refuseModification`.
- `KafkaConnectionProfileService` / `…Impl` -- profiles, defaults, both tests.
- `KafkaSecretService` / `…Impl` -- files, stores, and `canUseObject`.
- `KafkaConnectionResolver` (`config/`) -- the dispatch-time answer to "which cluster", used by
  `ensureTopicExists` on every task-type save and by `testTopic`. Route → type default → tenant
  default → platform default, ignoring any binding whose owner does not match the scope
  (`:49-108`).
- `KafkaTemplateProvider` -- builds the client, caches store material on disk per profile id, and is
  invalidated on update, delete, set-default, and around a test that changed the store references.
- `LookupDataCacheService` -- a process-wide `Map<String, LookupDataDto>` rebuilt from inside a
  tenant request on every lookup add, update and delete. It **decrypts** encrypted values into the
  cache (`:84-86` of that file).

---

## 6. Database requirements

### 6.1 `source_task_type`

Created by `db/changelog/changelog-sets/V1.0-init/V1__creating_shedlock_schema.sql:27-35`; every
column added since is left to `ddl-auto=update`.

| Column | Type | Notes |
|---|---|---|
| `source_task_type_id` | bigint PK | sequence `source_task_type_source_Seq`, start 1000 |
| `tenant_id` | bigint null | null = platform-owned. Indexed `idx_stt_tenant_id` |
| `service_name` | varchar not null | |
| `description` | varchar **not null** | but `updateSourceTaskType` does not validate it |
| `queue_topic_partition` | varchar not null | `topic=<name>&partitions=[<n>\|*]` |
| `task_type_status` | varchar not null | `Active` / `Inactive` / `Delete`, `@Enumerated(STRING)` |
| `kafka_connection_profile_id` | bigint null | the type-level default. Indexed `idx_stt_kafka_profile_id` |
| `created_by`, `updated_by` | bigint | added by V22 |

Dropped by V11: `is_schema_register`, `schema_payload`.

### 6.2 `tenant_task_type_kafka_route`

Entity-created; `TenantTaskTypeKafkaRoute.java:15-22`.

| Column | Type | Notes |
|---|---|---|
| `tenant_task_type_kafka_route_id` | bigint PK | |
| `tenant_id` | bigint **not null** | |
| `source_task_type_id` | bigint not null | |
| `kafka_connection_profile_id` | bigint not null | |
| `date_created` | timestamp | `@PrePersist` |

Unique `uq_tenant_task_type (tenant_id, source_task_type_id)` -- correctly tenant-qualified. Three
indexes.

### 6.3 `kafka_connection_profile`

Entity-created; renamed `connection_active` → `is_default` by V11. Columns:
`kafka_connection_profile_id`, `tenant_id` (null = platform), `profile_name`, `environment_label`,
`bootstrap_servers` (TEXT), `security_protocol`, `sasl_mechanism`, `sasl_username`,
`sasl_password` (ciphertext, length 1000, **no `_enc` suffix** unlike its three siblings),
`ssl_keystore_bucket`, `ssl_keystore_location`, `ssl_keystore_password_enc`,
`ssl_key_password_enc`, `ssl_truststore_bucket`, `ssl_truststore_location`,
`ssl_truststore_password_enc`, `ssl_endpoint_identification_algorithm`, `additional_properties`
(TEXT), `is_default` not null, `status` not null, `connection_status`, `last_tested_at`,
`last_test_message` (TEXT), `date_created`, `created_by`, `updated_by`.

### 6.4 `lookup_data`

`V1__creating_shedlock_schema.sql:13-21`, plus `is_encrypted` from V8 and `tenant_id` from
`ddl-auto`.

| Column | Type | Notes |
|---|---|---|
| `lookup_id` | bigint PK | sequence `lookup_id_Seq`, start 1000 |
| `lookup_value` | text | ciphertext when `is_encrypted` |
| `lookup_type` | varchar(255) **UNIQUE** | global, not tenant-qualified -- see 12.9 |
| `description` | varchar(255) | |
| `date_created` | timestamp not null | |
| `parent_lookup_id` | bigint FK → `lookup_data` | inline in V1, self-referencing |
| `is_encrypted` | boolean not null default false | V8 |
| `tenant_id` | bigint null | null = platform-owned. Indexed `idx_lookup_data_tenant_id` |
| `created_by`, `updated_by` | bigint | V22 |

Seeded families: `SCHEDULER_LAST_RUN_TIME`, `QUEUE_FETCH_LIMIT`, ~~`PIPELINE_IDS`,~~
`PIPELINE_HOME_PAGES`, `EMAIL_RECEIVER` (V2, ids 1001–1019); `AI_PROVIDER` + three children and
`BUCKET_LIST` + three children (V9, ids 1020–1027); V10 replaces the `PIPELINE_IDS` children (which
themselves no longer exist -- **removed 2026-09-07** by `V28__drop_pipeline_ids_lookup.sql`, which
deletes parent 1015 and every row under it; see 2.9 for the reasoning and 12.19 for the full
account). **`TASK_GROUPS` is never seeded** although it is one of the ~~four~~ **three** tenant-owned
families that remain (`BUCKET_LIST`, `PIPELINE_HOME_PAGES`, `TASK_GROUPS` -- `PIPELINE_IDS` was the
fourth) and the task editor offers a Group dropdown backed by it
(`features/tasks/edit/task-edit.ts:18`).

### 6.5 Migrations needed

1. **Tenant-qualify `lookup_data.lookup_type`.** Drop the global unique constraint; replace with a
   unique index over `(tenant_id, lookup_type)` -- or, if the family namespace is meant to stay
   global for parents, over `(coalesce(tenant_id, 0), parent_lookup_id, lookup_type)`. See open
   questions.
2. **Seed the `TASK_GROUPS` parent** (a top-level row, no tenant), so that a tenant admin can add
   its own groups without a platform admin having to create the family first.

Neither is required to fix the defects in section 12; both are required for the feature to be
usable by more than one tenant.

---

## 7. Validation

| Rule | Client | Server | Where |
|---|---|---|---|
| Task type service name required | yes (`task-type-dialog.ts:126`) | yes | `SettingServiceImpl:269-270, 302-303` |
| Task type description required | **no** (`task-type-dialog.ts:130`) | **on create only** | `:271-272`; `updateSourceTaskType` does not check it |
| `queueTopicPartition` present | implied by topic being required | yes | `:273-274, 304-305` |
| `queueTopicPartition` grammar | `/^[a-zA-Z-]+$/` on topic, `/^(\*\|10\|[0-9])$/` on partition (`:131-134`) | `^topic=([a-zA-Z0-9._-]{1,249})&partitions=\[([0-9]+\|\*)\]$` | `util/KafkaTopicPartitionUtil.java:22-23` -- **the client is stricter than the server** |
| Partition index ≤ 10 | yes | yes | `KafkaTopicPartitionUtil.MAX_PARTITION_INDEX` |
| Kafka profile named on a task type is visible to the caller | no | yes | `SettingServiceImpl:630-642` |
| Task type ownership on update/delete | no | yes | `:319-321, 350-352` |
| Lookup type required | yes (`lookup-dialog.ts:94`) | yes | `SettingServiceImpl:446-448, 482-484` |
| Lookup value required | yes, **unconditionally** (`lookup-dialog.ts:95`) | on add always; on update only when the row was not encrypted | `:444-446, 496-500` |
| Lookup parent must be tenant-owned or extendable for a tenant admin | no | yes | `:451-456` |
| Lookup modification permitted | partly -- children only (`lookup.ts:187-193`) | yes | `:122-144`, called from `:490` and `:586` |
| Lookup platform-only family hidden | n/a | yes, list and by-id | `:214-216, 534-537` |
| Kafka profile name / bootstrap servers present | yes (`kafka-dialog.ts:184,186`) | yes | `KafkaConnectionProfileServiceImpl:398-403` |
| Bootstrap servers are `host:port` pairs | no | yes | `:599-624` |
| Security protocol in the set of four | select | yes | `:407-409` |
| SASL mechanism in the set of three | select + a hint when a stored value is not (`kafka-dialog.ts:264-276`) | yes | `:410-413` |
| SASL username and password present for SASL | yes, conditionally (`kafka-dialog.ts:248-255`) | yes, allowing "already stored" | `:414-421` |
| Truststore password without a truststore | no | yes | `:427-434` |
| Additional properties parse as a flat JSON object | yes (`kafka-profile-form.ts:62-81`) | yes, via Gson | `:436-443` |
| A stored SASL password is not carried to new brokers | no | yes | `:517-537` |
| TLS material belongs to the caller | no | yes | `:461-500`, `KafkaSecretServiceImpl:202-224` |
| Uploaded secret really is what it claims | no | yes, parsed before storing | `KafkaSecretServiceImpl:86-93, 227-252` |
| Uploaded secret ≤ 512 KB | no | yes | `:79-82` |
| ~~XML: at least one keyed tag, no duplicate keys, valid XML names, parents exist, no self-parent, a root exists~~ | ~~yes (`xml-builder.ts:34-59`)~~ **the client half is gone -- removed 2026-09-05, see 2.8, 12.20** | only `xmlTagsInfo != null` | `SettingRestApi.java:158-163`, was `:176-181` (2.9) |

**Client-only rules -- each is a finding:**

- ~~The XML builder's six checks exist only in the browser.~~ **Moot, 2026-09-05** -- there is no
  browser check left to be client-only, because there is no XML builder screen (2.8, 12.20). What
  remains true, and was already true before that screen existed: the endpoint accepts any list of
  tag descriptors and will happily build a document with duplicate keys or an orphaned parent.
  Every remaining caller -- the legacy Source Task tag-to-XML button and the next app's automatic
  save-time call -- sends it unchecked tag rows, so a bad key still surfaces only as whatever the
  caller does with a malformed document, not as a named validation error.
- The Kafka dialog's `additionalPropertiesJson` is a mirror of a server rule, which is the correct
  shape: the client's job is to move the complaint to the field.
- The task-type topic pattern is worse than client-only -- it is client-**contradictory**, refusing
  values the server accepts and telling the operator the server is the one refusing them.

---

## 8. Security

### 8.1 Frontend guard

~~All five routes~~ **All three remaining routes** carry `canActivate: [roleGuard]` with
`data: { minRole: 'TENANT_ADMIN' }` -- `settings/xml` and `admin/settings` are gone (removed
2026-09-05, see 2.8, 12.20), so only `settings/task-types`, `settings/kafka` and `settings/lookup`'s
guards remain to cite; line ranges for the two removed routes are not re-verified here since there
is nothing left at them. `roleGuard` reads `minRole` from its own snapshot and defers to
`AuthService.hasAtLeast`, so a platform admin passes by hierarchy rather than by being listed
(`core/auth/auth.guard.ts:33-42`). Nav entries carry `adminOnly: true` and are filtered at
`shell.ts:144-148`. ~~The settings hub filters `platformOnly` cards (`settings-hub.ts:71-74`).~~
**Moot, 2026-09-05** -- there is no settings hub (2.8, 12.20).

The old app lists both roles explicitly on each of its ~~route~~ **three remaining routes**
(`app.routing.ts:112, 126, 133` -- `setting`, `setting/lookup`, `setting/subLookup`; the fourth,
`setting/lookpXml`, is gone along with its route, removed 2026-09-07, see 2.8); its `RoleGuard` does
a plain array membership test with no hierarchy (`_helpers/role.guard.ts:21-22`).

**The guard is not enforcement.** Two controls inside these pages are offered to callers the server
will refuse -- see 8.5.

### 8.2 Controller `@PreAuthorize`

| Controller | Class-level | Method-level overrides |
|---|---|---|
| `SettingRestApi` | `hasRole('TENANT_ADMIN')` (`:24`) | `dynamicQueryResponse` → `PLATFORM_ADMIN` (`:43`) |
| `KafkaConnectionProfileRestApi` | `hasRole('TENANT_ADMIN')` (`:20`) | none |
| `KafkaSecretRestApi` | `hasRole('TENANT_ADMIN')` (`:33`) | none |
| `SourceTaskRestApi` | `hasRole('TENANT_ADMIN')` (`:28`) | several, **including** `fetchAllLinkSourceTaskWithSourceTaskTypeId` → `TENANT_USER` (`:108`) |

`@PreAuthorize` is not repeatable: an override **replaces** the class annotation rather than adding
to it. That is what is wanted on `dynamicQueryResponse`, which is raised to `PLATFORM_ADMIN`. It is
also what happens on `fetchAllLinkSourceTaskWithSourceTaskTypeId`, which is *lowered* to
`TENANT_USER` -- so the linked-tasks panel is readable by any signed-in user of the tenant, not only
an admin, even though the route guard sends a `TENANT_USER` to `/unauthorized`. **A route refusal is
not an endpoint refusal**, and this is the endpoint on these screens where the two disagree.

Reading the annotation stack is where this is easy to get wrong: the `@PreAuthorize` sits *above*
the `@RequestMapping`, so the line number a reader reaches for is one past the annotation that
actually decides. An earlier draft of this document made exactly that error on this endpoint. `RoleHierarchyImpl` is configured
`PLATFORM_ADMIN > TENANT_ADMIN > TENANT_USER` (`config/MethodSecurityConfig.java:29`), so
`hasRole('TENANT_ADMIN')` admits a platform admin.

### 8.3 Service rules

This is where the real decisions are made.

**Task types.** `isSourceTaskTypeOwnedByCaller` (`:360-368`) -- a platform admin owns everything;
anyone else needs a non-null `tenant_id` equal to their own, so **a platform-owned task type cannot
be edited or deleted by a tenant admin**, and a caller with no tenant owns nothing.
`isSourceTaskTypeVisibleToCaller` (`:370-375`) is the looser test used by `setKafkaRoute`, and
correctly so: a tenant may route a *shared* type to its own broker.

**Kafka profiles.** `scopedFind` (`:539-553`) is the gate on update, delete, set-default and
test-by-id. `callerOwns` (`:560-566`) decides whether a test result is written to the row and
whether the store bucket and key are returned. `fetchAllProfiles` uses a hand-written query per
scope (`:183-192`); `findVisibleToTenant` returns the tenant's own rows and no others, with the
reasoning recorded on the query (`KafkaConnectionProfileRepository.java:23-38`).

**Kafka routes.** All three refuse a platform admin explicitly, because the override is scoped to a
tenant and a platform admin has none (`:382-384, 397-399, 425-427`).

**Lookups.** `refuseModification` (`:122-144`) is the whole rule for update and delete: platform
admin passes; a platform-only family is refused; a family that is neither owned nor extendable is
refused; a null-tenant row in an extendable family is refused with an explanation; and finally the
row's tenant must equal the caller's. `updateLookupData` additionally runs `isLookupOwnedByCaller`
first (`:486`), which answers "not found" rather than the explanatory refusal -- `deleteLookupData`
does not, and answers the better message (`:586-589`).

**Kafka secrets.** `canUseObject` (`KafkaSecretServiceImpl.java:202-224`) resolves ownership
*through the owner's tenant*, not out of the key, and stops a tenant admin from attaching a peer
administrator's private key. `KafkaSecretPath.parse` re-serialises and compares
(`KafkaSecretPath.java:99`), so `kafka-secrets/+1248/…` and `kafka-secrets/01248/…` do not
authorise as user 1248, and a key holding `..`, `\` or `//` is refused before splitting (`:84-86`).
`refuseUnusableSecret` (`KafkaConnectionProfileServiceImpl.java:461-488`) covers the other bucket:
a non-secret bucket must be a storage connection the caller's own tenant owns.

### 8.4 Hibernate filter

`TenantFilterHelper.enableIfNeeded` turns on `tenantFilter` for a caller with a non-null tenant who
is not a platform admin, and **disables it otherwise** (`security/TenantFilterHelper.java:28-33`).

| Entity | Declares the filter? | Condition |
|---|---|---|
| `SourceTaskType` | yes (`:22-26`) | `(tenant_id = :tenantId or tenant_id is null)` |
| `KafkaConnectionProfile` | yes (`:22-26`) | `(tenant_id = :tenantId or tenant_id is null)` |
| `TenantTaskTypeKafkaRoute` | yes (`:26-29`) | `tenant_id = :tenantId` |
| `LookupData` | **no** | deliberately exempt -- the whole tree is loaded into a process-wide cache rebuilt from inside tenant requests, so a filtered rebuild would serve one tenant's view to everybody (`TenantFilterDeclarationTest.java:34-48`) |

**Neither `SettingServiceImpl` nor `KafkaConnectionProfileServiceImpl` ever calls
`enableIfNeeded`** -- verified by grepping the backend for `TenantFilterHelper`, which returns
thirteen files and neither of these. So for this entire feature the filter layer is **inert**: the
three declarations above never fire on any read path this feature uses, and every isolation decision
falls to the hand-written predicates in 8.3. This matters twice over, because the filter also does
not apply to `findById`, and `findById` is exactly what `updateSourceTaskType`,
`deleteSourceTaskType`, `setKafkaRoute`, `updateLookupData`, `deleteLookupData`,
`fetchSubLookupByParentId` and `scopedFind` all use.

### 8.5 Per role

**PLATFORM_ADMIN** -- sees every task type, every Kafka profile (including every tenant's), every
lookup family including the four engine-state ones, and may create, edit and delete all of them.
Creates task types and profiles with `tenant_id = null`. Cannot set, read or delete a Kafka routing
override: all three endpoints refuse them, and the console correctly hides the control
(`task-types.ts:134`, `task-type-dialog.ts:119`).

**TENANT_ADMIN** -- sees its own task types **and the platform's**
(`SourceTaskTypeRepository.java:42-46`), but may only edit or delete its own. Sees only its own
Kafka profiles. Sees every lookup family except the four platform-only ones; may add children under
~~`BUCKET_LIST`, `PIPELINE_IDS`, `PIPELINE_HOME_PAGES`, `TASK_GROUPS` and `AI_PROVIDER`~~
**`BUCKET_LIST`, `PIPELINE_HOME_PAGES`, `TASK_GROUPS` and `AI_PROVIDER`** (`PIPELINE_IDS` removed
2026-09-07, see 2.9), sees only its own children in the first three and the platform's as well in
`AI_PROVIDER`, and may modify only rows its own tenant owns. May route any *visible* task type --
shared ones included -- to one of its own Kafka profiles.

Two controls are offered to a tenant admin that the server refuses every time:

- **"New lookup"** (`lookup.html:14-16`) creates a top-level row, which `addLookupData` refuses
  because a top-level row has no parent and therefore no tenant-owned family (`:451-456`).
- **Edit / Delete on a parent row** (`lookup.html:174-186`) -- `refuseModification` returns "it is
  platform reference data" for any row whose parent is null (`:129-133`). The child rows are gated
  by `canModify`; the parent rows are not.

**TENANT_USER** -- reaches none of ~~these five routes~~ **these three routes** (`roleGuard`) --
`settings/xml` and `admin/settings` no longer exist to reach, removed 2026-09-05, see 2.8, 12.20 --
and none of the endpoints (class-level `TENANT_ADMIN` on all three controllers). Consumes the
results indirectly: a task points at a task type, a task's pipeline and group come from lookups
(pipeline no longer does, as of 2026-09-07 -- see 2.9), and a job's messages are published through
the resolved Kafka profile.

**A token carrying `TENANT_ADMIN` and no tenant** owns nothing, and the code mostly says so --
`isSourceTaskTypeOwnedByCaller` and `isLookupOwnedByCaller` both return false on a null row tenant,
and `TenantFilterHelper` disables the filter rather than binding `null`. The exception is
`deleteLookupData`, which runs only `refuseModification`; there,
`Objects.equals(row.getTenantId(), TenantContext.getTenantId())` is **true** when both are null, so
a null-tenant tenant admin can delete a platform-owned child of ~~`BUCKET_LIST`, `PIPELINE_IDS`,
`PIPELINE_HOME_PAGES` or `TASK_GROUPS`~~ **`BUCKET_LIST`, `PIPELINE_HOME_PAGES` or `TASK_GROUPS`**
(`PIPELINE_IDS` and its children no longer exist to be a target of this, removed 2026-09-07 -- see
2.9) -- rows every other tenant reads. See 12.5.

### 8.6 Secret handling

- Kafka secrets are write-only across the API: `getProfileDto` returns `saslPasswordConfigured`,
  `sslKeystorePasswordConfigured`, `sslKeyPasswordConfigured`, `sslTruststorePasswordConfigured`
  and never a value (`:709-712`). Store bucket and location are withheld from a non-owner
  (`:716-721`).
- A deleted profile has its four secret columns nulled (`:171-176`).
- A generated store's password travels between the two requests **already encrypted**
  (`KafkaSecretServiceImpl.java:128, 175`) and `applyProfileDto` writes an `…PasswordEnc` value
  through unchanged rather than double-encrypting (`:646-668`).
- Lookup values marked encrypted are AES-encrypted on write and returned as `••••••••`
  (`SettingServiceImpl.java:154, 605-616`). The cache decrypts them for server-side consumers.
- `LOOKUP_ENCRYPTION_KEY` has a literal default in `process/docker-compose.yml`; that is recorded
  under `.ai/discovery/risks.md` as an infrastructure risk and is not this feature's to fix.

---

## 9. Error handling

| Failure | What the user sees | Where |
|---|---|---|
| `appSetting` fails on the task-types screen | The `TableShell` error panel with the server message or "Could not load task types.", and a Try again button | `task-types.ts:212-215` |
| `appSetting` fails on the lookups screen | The same panel, "Could not load lookups." | `lookup.ts:85-88` |
| `fetchAllProfiles` fails | "Kafka profiles could not be loaded." in the error panel | `kafka-connections.ts:125-127` |
| Per-parent child fetch fails | **Nothing** -- the parent renders with zero entries and no expander | `lookup.ts:78` |
| `fetchKafkaRoute` fails | Nothing, deliberately -- "an unrouted type simply has no route" | `task-types.ts:158-159` |
| `fetchAllProfiles` fails on the task-types screen | Nothing; the profile list is empty and the dialog offers "Tenant default" only | `task-types.ts:194-195` |
| A dialog is submitted with an invalid field | "Check the highlighted fields." toast plus per-field messages from `Field` | `task-type-dialog.ts:156-158`, `kafka-dialog.ts:312-315`, `lookup-dialog.ts:104-106` |
| The server refuses a save | The server's own message as an error toast | all three dialogs |
| A save succeeds but the route call fails | "Saved, but the Kafka route could not be applied.", dialog closes, list reloads | `task-type-dialog.ts:204-209` |
| Delete refused (e.g. a Kafka profile still referenced) | The server's message: "This profile is still used by a Source Task Type or tenant routing override -- reassign those first." | `KafkaConnectionProfileServiceImpl.java:166` |
| Connection test fails | An inline card in the dialog, or a toast from the row action; the reason is deliberately generic -- "Authentication rejected", "TLS handshake failed", "Broker unreachable or network blocked (timed out)" -- with the detail only in the server log | `:305-307`, `:352-365` |
| Topic test fails because the topic is absent | "Topic \"X\" does not exist on the connected cluster." -- the one answer that is about the topic rather than the cluster | `:386-388`. **Not reachable from the new console** |
| A certificate upload is not what it claims | The parse failure's own message, before anything is stored | `KafkaSecretServiceImpl.java:90-93` |
| A key and certificate do not match | "That private key does not belong to that certificate. Check you uploaded the pair the broker issued together." | `:164-170` |
| A referenced secret has vanished from the bucket | "That file could not be read from storage. Check it is still there, or upload it again." | `:48-50, 272-288` |
| ~~XML build fails~~ | ~~"The XML could not be built." toast, or the server's "Wrong Input"~~ | ~~`xml-builder.ts:94-99`~~ **removed 2026-09-05, see 2.8, 12.20 -- no screen left to show this** |
| ~~XML input is invalid~~ | ~~A list of specific problems above the Build button, which stays disabled~~ | ~~`xml-builder.html:84-88`~~ **removed 2026-09-05, same note** |
| An uncaught server exception | HTTP 500 with `ProcessUtil.INTERNAL_ERROR_500`; the console shows its own fallback text | every controller's catch block |

Gaps worth naming: a failed child fetch on the lookups screen is indistinguishable from a parent
with no children; and a task type whose Kafka profile list failed to load silently offers only
"Tenant default", which -- combined with 12.1 -- means an edit made in that state clears the
binding.

---

## 10. Dependencies

**Features.** `storage-connections` is the declared dependency and a real one in two directions:
a Kafka profile's TLS material is fetched through the storage layer at client-build time, and
`refuseUnusableSecret` resolves a non-`etl-bucket` reference through
`StorageConnectionRepository.findByAlias` (`KafkaConnectionProfileServiceImpl.java:476-486`). The
old app's Kafka form uploads its stores through `storage.json/uploadObject` directly
(`kafka-connection-profile.component.ts:129, 156`), so the storage connection has to exist first.

Downstream, `source-tasks` cannot function without this feature: the task editor reads task types
from `appSetting` and group/home-page options from `fetchSubLookupByParentId`
(`features/tasks/edit/task-edit.ts:18, 82, 96`). ~~Pipeline is a third option from the same call~~
-- **no longer true, changed 2026-09-07**: `PIPELINE_IDS` is gone from the lookup family this
feature owns (2.9), and the Pipeline picker on that screen now reads a new endpoint this feature's
sibling controller exposes, `GET taskForm.json/listPipelines` (`TaskFormRestApi.java:61-70`,
`TENANT_USER`) -- see `.ai/grooming/source-tasks.md` §12.7 for the full account of that change,
which belongs to that document. ~~and renders its XML preview through `xmlCreateChecker` (`:224`)~~
-- also changed 2026-09-07: that screen no longer has a manual XML preview to render; `save()`
calls `xmlCreateChecker` itself, automatically, whenever a pipeline form is driving the task
(`task-edit.ts:319-391`, same source-tasks reference). `xmlCreateChecker` itself
(`SettingRestApi.java:154-168`) is unaffected either way -- this feature's endpoint did not change,
only who calls it and when. `content-and-ai-tools` reads `AI_PROVIDER` through `appSetting`
(`features/ai/agents/agents.ts:90`). `object-browser` reads `BUCKET_LIST`. ~~`dynamic-forms`'
submission-to-task dialog reads task types and builds XML through the same two endpoints
(`features/forms/submission-to-task-dialog.ts:203, 219`)~~ -- **pre-existing staleness, not part of
the 2026-09-07 work above**: the `dynamic-forms` feature and `features/forms/` do not exist in
`scheduler1/next/src` at all (confirmed by listing `features/` and finding no `forms` entry other
than `features/settings/forms`, the unrelated Pipeline Forms screen -- reachable at
`settings/pipeline-forms` since its own 2026-09-07 rename from `settings/forms`, which now
redirects; see `.ai/grooming/source-tasks.md` §4.1 and §2.6 for that screen's own documents) -- it
was removed 2026-09-05 in the
same `889ae2e` commit that removed the XML builder screen (2.8), which is what its own message names
("Remove Dynamic Forms and Query/Search Engine"). `source-jobs` depends on it transitively.
`tenants-and-users` owns the rule that decides whether a `TENANT_ADMIN` can exist without a tenant,
which 12.5 depends on.

**Services and infrastructure.** A reachable Kafka cluster (topic provisioning runs on every task
type save -- `SettingServiceImpl.java:291-293, 335-337`); object storage for `etl-bucket`;
`LOOKUP_ENCRYPTION_KEY` for encrypted lookup values and every Kafka secret; a Spring cache backend
for `appSetting`.

**Shared frontend.** `TableShell`, `Field`, `FormDialog`, `confirmWith`, `StatTile`, `StatusPill`,
`ViewToggle`, `MineFilter`, `Icon`, `createSort`, `ToastService`, `shared/ui/topic.ts`,
`shared/ui/clipboard.util.ts`, `AuthService`.

---

## 11. Acceptance criteria

Fixtures assumed throughout: tenants **A** and **B**, each with a `TENANT_ADMIN` and a
`TENANT_USER`; a `PLATFORM_ADMIN`; a platform-owned task type `shared-type`
(`tenant_id IS NULL`); a tenant-A task type `a-type` bound at type level to tenant-A profile
`a-prod`; a tenant-B task type `b-type`; tenant-A Kafka profiles `a-prod` (default) and `a-archive`;
a tenant-B profile `b-prod`; a platform profile `platform-prod`; the seeded platform lookup children
`etl-bucket` under `BUCKET_LIST` and `OpenAI` under `AI_PROVIDER`; a tenant-A child `a-bucket` under
`BUCKET_LIST`; a tenant-A encrypted lookup child `a-secret` whose plaintext is `hunter2`.

### Access

1. Tenant A's `TENANT_ADMIN` opens `/settings/task-types`, `/settings/kafka` and `/settings/lookup`
   and each renders. ~~`/settings/xml` and `/admin/settings` and each renders~~ -- **dropped from
   this criterion, 2026-09-05**: neither route exists any more (removed in commit `889ae2e`, before
   and unrelated to this document's 2026-09-07 work; see 2.8, 12.20), so there is nothing left at
   either URL for this criterion to check.
2. Tenant A's `TENANT_USER` navigating to any of ~~those five~~ **those three** lands on
   `/unauthorized`, and the Configuration nav group is not rendered for them. ~~nor the Tools → XML
   Configuration entry~~ -- **moot, 2026-09-05**: there is no such entry any more (2.8, 12.20).
   **Positive control:** the same user reaches `/tasks` and `/jobs`.
3. That `TENANT_USER`, with a valid token, calls `GET /setting.json/appSetting` directly and gets
   HTTP 403. **Positive control:** the same call from tenant A's `TENANT_ADMIN` returns 200.
4. ~~The `PLATFORM_ADMIN` opens `/admin/settings` and sees the Tenants card; tenant A's admin opens
   the same page and does not. **Positive control:** both see the Kafka Connections card.~~
   **Un-checkable as written, since 2026-09-05**: `/admin/settings` (the settings hub) no longer
   exists (2.8, 12.20), so there is no Tenants card and no Kafka Connections card on it to compare.
   The underlying access rule this criterion meant to check -- a platform admin sees tenant
   management, a tenant admin does not -- is `tenants-and-users`' to re-state on whatever screen
   now carries it, not this document's to invent a replacement for.

### Task types -- listing

5. Tenant A's admin opens `/settings/task-types` and the table lists `a-type` **and**
   `shared-type`; `b-type` is absent. **Positive control:** the `PLATFORM_ADMIN` on the same screen
   sees all three.
6. A soft-deleted task type does not appear in the list for anybody.
7. The Tasks column for `a-type` shows the number of non-deleted source tasks pointing at it, and
   clicking it opens the linked-tasks panel listing exactly those tasks; a task whose status is
   `Delete` is not among them.
8. Tenant A's admin opens the linked-tasks panel for `shared-type` and sees only tenant A's tasks.
   **Positive control:** the `PLATFORM_ADMIN` opening the same panel sees tenant A's and tenant B's.

### Task types -- creating and editing

9. Tenant A's admin creates a task type named `Orders v2` with topic `orders-v2` and partition `*`.
   The dialog accepts the topic without marking the field invalid, and the row appears with Topic
   `orders-v2`. *(Fails today -- see 12.6.)*
10. **Positive control for 9:** creating a task type with topic `orders` succeeds today and must
    continue to.
11. Creating a task type with topic `has space` is refused, with the message on the Topic field and
    no HTTP request made.
12. Creating a task type with partition `11` is refused; with partition `10` it succeeds.
13. Tenant A's admin creates a task type and selects Kafka connection `a-archive`. Reopening that
    row's Edit dialog shows `a-archive` selected, and the Kafka column on the list shows
    `a-archive`. *(Fails today on both counts -- see 12.1 and 12.2.)*
14. Tenant A's admin edits `a-type`, changing only its description. Afterwards
    `source_task_type.kafka_connection_profile_id` for `a-type` still points at `a-prod`, and its
    routing override (if any) is unchanged. *(Fails today -- see 12.1.)*
15. **Positive control for 14:** the same admin edits `a-type` and deliberately changes the Kafka
    connection to `a-archive`; afterwards the effective binding is `a-archive` and the list says so.
16. The `PLATFORM_ADMIN` edits `shared-type`'s description. Its
    `kafka_connection_profile_id` is unchanged, and the dialog shows no Kafka connection control at
    all, only the explanatory note. *(The note is correct today; the preservation is not.)*
17. Tenant A's admin creates a task type with the Description field left empty and is either
    stopped in the dialog or told "SourceTaskType description missing." -- not both silently and
    then a toast. **Positive control:** with a description, the create succeeds.
18. Tenant A's admin attempts `PUT /setting.json/updateSourceTaskType` for `b-type` with a valid
    token and is refused "SourceTaskType not found with …". **Positive control:** the same call for
    `a-type` succeeds.
19. Tenant A's admin attempts to edit `shared-type` and is refused. **Positive control:** the
    `PLATFORM_ADMIN` editing `shared-type` succeeds.
20. Tenant A's admin sets a Kafka route on `shared-type` pointing at `a-prod` and it succeeds; the
    same call naming `b-prod` is refused "Kafka connection profile not found."
21. The `PLATFORM_ADMIN` calls `setKafkaRoute` and is refused "Platform Admin publishes unscoped --
    tenant routing overrides don't apply." **Positive control:** tenant A's admin calling it on the
    same task type succeeds.
22. Deleting `a-type` marks it `Delete` and marks every source job built on tasks of that type
    `Delete`. Reading those jobs back through `listSourceJob` afterwards still returns them under a
    recognisable status -- not a row excluded by a case-sensitive comparison. *(Fails today -- see
    12.7.)*
23. The task-type delete confirmation names the number of linked tasks before the button is pressed.

### Task types -- topic reachability

24. With `a-type`'s topic present on the cluster `a-prod` points at, tenant A's admin uses the
    row's Kafka action and is told the topic is reachable and how many partitions it has.
    **Positive control / negative pair:** with the topic absent, the same action says
    `Topic "…" does not exist on the connected cluster.` *(Neither is reachable today -- see 12.4.)*
25. A task type using the tenant default is testable from its row without the operator being told to
    "test that profile directly".

### Kafka connections

26. Tenant A's admin opens `/settings/kafka` and sees `a-prod` and `a-archive`; `b-prod` and
    `platform-prod` are absent. **Positive control:** the `PLATFORM_ADMIN` sees all four.
27. On the `PLATFORM_ADMIN`'s view, each row says whose it is, and a scope control narrows the list
    to platform-wide or tenant-owned rows. *(Absent today -- see 12.10.)*
28. Creating a profile with bootstrap servers `broker1` (no port) is refused
    "bootstrapServers must be a comma-separated list of host:port pairs."; `broker1:9092` succeeds.
29. Creating a `SASL_SSL` profile with no SASL password is blocked in the dialog. **Positive
    control:** with a password it is created, and reopening the dialog shows the password field
    empty with the hint "Already set. Leave blank to keep it."
30. Editing that profile, leaving the password blank and changing the bootstrap servers is refused
    "Enter the SASL password again -- …". **Positive control:** the same edit with the password
    retyped succeeds.
31. Switching a profile from `SASL_SSL` to `PLAINTEXT` and saving leaves
    `sasl_mechanism`, `sasl_username`, `sasl_password`, both store locations and all three store
    passwords null on the row.
32. A profile's Additional properties set to `foo=bar` is marked invalid on the field with "Enter a
    JSON object of properties, not key=value lines" and no request is made. **Positive control:**
    `{"request.timeout.ms":"30000"}` saves.
33. Tenant A's admin uploads a CA certificate, builds a truststore from it and saves the profile;
    afterwards `ssl_truststore_bucket` is `etl-bucket`, `ssl_truststore_location` matches
    `kafka-secrets/{their appUserId}/{uuid}/{date}/truststore-*.p12`, and
    `ssl_truststore_password_enc` is non-null.
34. Tenant A's admin saves a profile naming a truststore key under **tenant B's admin's** user id
    and is refused "That truststore could not be found." **Positive control:** the same save naming
    their own uploaded key succeeds.
35. Tenant A's admin saves a profile naming `kafka-secrets/{tenant A TENANT_USER id}/…` and it
    succeeds; naming `kafka-secrets/{tenant A's other TENANT_ADMIN id}/…` is refused.
36. A profile naming bucket `b-archive` (tenant B's storage connection alias) is refused "No storage
    connection is called 'b-archive'." **Positive control:** naming tenant A's own alias succeeds.
37. Setting `a-archive` as default clears the flag on `a-prod` and leaves `platform-prod`'s flag
    untouched. Clear default takes it off `a-archive` and touches no other tenant's row.
38. An `Inactive` profile cannot be set as default: "This profile is not active and cannot be
    selected as the default."
39. Deleting `a-prod` while `a-type` points at it is refused "This profile is still used by a Source
    Task Type or tenant routing override -- reassign those first." **Positive control:** after
    repointing `a-type` at `a-archive`, deleting `a-prod` succeeds and its four secret columns read
    null.
40. Tenant A's admin calls `testConnection` with `{kafkaConnectionProfileId: <b-prod's id>}` and is
    refused "Profile not found with …". **Positive control:** the same call for `a-prod` runs.
41. A failed connection test shows one of the four generic reasons and never names a host, and the
    row's test pill turns to Failed with the time.
42. No API response anywhere on this screen contains `saslPassword`,
    `sslKeystorePasswordEnc`, `sslKeyPasswordEnc` or `sslTruststorePasswordEnc`. **Positive
    control:** the corresponding `…Configured` booleans are present and true.
43. Tenant A's admin reading `platform-prod` by id through `testConnection` gets "Profile not found";
    the `PLATFORM_ADMIN` doing the same gets a real probe result.

### Lookups

44. Tenant A's admin opens `/settings/lookup` and sees ~~`BUCKET_LIST`, `PIPELINE_IDS`,
    `PIPELINE_HOME_PAGES` and `AI_PROVIDER`~~ **`BUCKET_LIST`, `PIPELINE_HOME_PAGES` and
    `AI_PROVIDER`** (`PIPELINE_IDS` removed 2026-09-07, see 2.9 -- there is no such family left to
    see, seeded or otherwise), and does **not** see `SCHEDULER_LAST_RUN_TIME`,
    `QUEUE_FETCH_LIMIT`, `AUDIT_LOG_SYNC_LAST_RUN_TIME` or `EMAIL_RECEIVER`. **Positive control:**
    the `PLATFORM_ADMIN` sees all ~~eight~~ **seven** (one fewer than before, for the same reason).
45. Tenant A's admin calls `GET /setting.json/fetchSubLookupByParentId?parentLookUpId=<QUEUE_FETCH_LIMIT>`
    directly and is refused "Only a platform admin can view this lookup." **Positive control:** the
    same call for `BUCKET_LIST` returns children.
46. Expanding `BUCKET_LIST` as tenant A's admin shows `a-bucket` and not tenant B's entries; the
    platform's `etl-bucket` is not shown either. **Positive control:** expanding `AI_PROVIDER` does
    show the platform's `OpenAI` alongside any tenant-A provider.
47. On the expanded `AI_PROVIDER`, `OpenAI` shows a "shared" pill and no edit or delete button; a
    tenant-A provider shows both. **Positive control on the same fixture:** both rows are visible.
48. Tenant A's admin adds an entry under `BUCKET_LIST`; the new row carries `tenant_id` = A, appears
    for tenant A, and does not appear for tenant B or in tenant B's Object Browser bucket list.
49. Tenant A's admin edits `a-secret` -- an encrypted entry -- changing only its description and
    saving with the Value field untouched. Afterwards a server-side read of the decrypted value is
    still `hunter2`. *(Fails today -- see 12.3.)*
50. **Positive control for 49:** the same admin edits `a-secret`, types a new value, and afterwards
    the decrypted value is the new one.
51. Opening the edit dialog for an encrypted entry shows the Value field **empty**, with a hint
    saying blank keeps the stored value, and saving is permitted with it empty.
52. Un-ticking "Store encrypted" on `a-secret` without typing a value leaves the row's plaintext as
    `hunter2`, not as the mask.
53. Tenant A's admin presses "New lookup" and either the control is not offered, or the resulting
    save succeeds. It must not be offered and then refused. **Positive control:** the
    `PLATFORM_ADMIN` pressing it creates a top-level family.
54. Tenant A's admin's kebab on the `BUCKET_LIST` parent row offers no Edit or Delete, matching the
    "shared" treatment its children already get. **Positive control:** the `PLATFORM_ADMIN`'s kebab
    on the same row offers both and they work.
55. Tenant A's admin calls `PUT /setting.json/deleteLookupData` with the id of the platform's
    `etl-bucket` and is refused. **Positive control:** the same call for `a-bucket` succeeds.
56. A caller whose token says `TENANT_ADMIN` and carries no tenant is refused that same delete.
    **Positive control:** the `PLATFORM_ADMIN` is allowed it. *(Fails today -- see 12.5.)*
57. Tenant A's admin creates a `BUCKET_LIST` entry whose type string is already used by tenant B and
    it succeeds. *(Fails today -- see 12.9.)* **Positive control:** creating one with a type string
    tenant A already uses is refused with a clear message rather than a 500.
58. Deleting a parent lookup with children names the child count in the confirmation before the
    button is pressed.
59. The task editor's ~~Pipeline,~~ Group and Home page dropdowns are populated for a tenant admin
    who has added entries under ~~all three families~~ **both remaining families**, `TASK_GROUPS`
    included. *(Fails today on `TASK_GROUPS` -- see 12.11.)* **Pipeline dropped from this
    criterion, 2026-09-07**: it is no longer backed by a lookup family a tenant admin adds entries
    to here at all -- it now reads Pipeline Forms (`GET taskForm.json/listPipelines`), a different
    screen this document does not own; see `.ai/grooming/source-tasks.md` §12.7 and its own
    acceptance criteria for that dropdown's coverage.

### XML

~~60. An admin enters a root tag and two children, presses Build, and the output panel shows a
    well-formed document nesting the two under the root.
61. Two rows with the same tag key show "Duplicate tag key: …" and the Build button stays disabled.
62. A row whose parent names a key no other row has shows "Parent tag does not exist: …".
63. A row whose parent is its own key shows "A tag cannot be its own parent: …".
64. When every filled row has a parent, "Every tag has a parent, so there is no root." is shown.
65. Blank rows are ignored: an admin fills one row of the six and Build is enabled.
66. Copy puts the document on the clipboard and Download saves it as
    `master-data-YYYY-MM-DD.xml`; Reset clears both the rows and the output.~~

**Criteria 60-66 are un-checkable, and have been since before this document's last update.** The
screen they test, `settings/xml`, was removed 2026-09-05 (commit `889ae2e`, unrelated to and two
days ahead of the `PIPELINE_IDS` work elsewhere in this pass -- see 2.8, 12.20). Their numbers are
kept, struck through rather than deleted or renumbered, per this document's own discipline of never
silently dropping a claim that used to be checkable. The six client-side rules they describe
(duplicate key, missing parent, self-parent, no root, blank-row handling, at least one keyed tag)
still exist nowhere on the server (7, "Client-only rules"), so if a replacement XML-authoring screen
is ever built, these six are the acceptance criteria to reinstate against it.

### States and chrome

67. With the API unreachable, each of the three list screens shows its error panel with a working
    Try again button, not an empty table.
68. On a tenant with no Kafka profiles, `/settings/kafka` shows "No Kafka profiles yet."; with a
    filter that matches nothing it shows "No profiles match the current filters." and offers Clear.
69. Every one of the five screens renders correctly in light and dark, with no hard-coded colour:
    switching the theme changes text, borders, pills and icons together.
70. At 375 px width no screen scrolls horizontally at the page level; wide tables scroll inside
    their own container.
71. The Kafka dialog is usable at 544 px, including the whole TLS section.

### The endpoint the route guard does not cover

72. A `TENANT_USER` of tenant A, with a valid token, calls
    `GET /sourceTask.json/fetchAllLinkSourceTaskWithSourceTaskTypeId?sourceTaskTypeId=<a type of tenant A>`
    directly and receives **200** with tenant A's linked task names. This is the *current* behaviour
    and the criterion records it deliberately: the method-level `@PreAuthorize` at
    `SourceTaskRestApi.java:108` lowers this one endpoint to `TENANT_USER`, so the `/unauthorized`
    redirect asserted by criterion 2 protects the **screen** and not the **data**.
73. **Positive control for 72:** the same call as tenant A's `TENANT_ADMIN` also returns 200 with the
    same rows, so a failure of 72 is a change in the rule and not a broken fixture.
74. The same call by a `TENANT_USER` of tenant **B**, naming a task type of tenant A, returns no
    rows of tenant A. **Positive control:** tenant B's own task type returns tenant B's rows.

> Criteria 72-74 describe what is true today, not what ought to be. Whether this endpoint should sit
> at `TENANT_USER` is [open question Q-AUTH](../synthesis/platform-configuration.md); until that is
> answered, 72 must keep passing so that any change to it is a decision rather than an accident.

---

## 12. Known issues

### 12.1 Editing a task type silently clears its Kafka binding

`task-type-dialog.ts:161-167` builds the payload from five fields and **omits
`kafkaConnectionProfileId`**. `SettingServiceImpl.updateSourceTaskType` writes the DTO's value
unconditionally:

```
sourceTaskType.get().setKafkaConnectionProfileId(sourceTaskTypeDto.getKafkaConnectionProfileId());
```

(`:326`) -- which is null on every save from the new console. So any edit to a task type, however
trivial, sets `source_task_type.kafka_connection_profile_id` to null.

For a tenant admin the effect is partly masked: `applyRoute` afterwards writes a *routing override*
from the select's value (`:192-211`), so the binding moves from the type to the route. For a
**platform admin** `canRoute()` is false and `applyRoute` returns immediately (`:194`), so the
binding is simply lost -- and a platform-owned task type has no tenant route to fall back to.
`KafkaConnectionResolver` then falls through to the platform default (`:74-81`), which may be a
different cluster entirely.

Severity: **blocker**. It is a silent data loss on the most ordinary action on the screen.

### 12.2 `fetchKafkaRoute`'s response shape and its two readers disagree

`SettingServiceImpl.fetchKafkaRoute` puts a bare id in `data`:

```
.map(route -> new ResponseDto(SUCCESS, "Route fetched.", route.getKafkaConnectionProfileId()))
```

(`:387`). Both callers read a property off it:

- `task-types.ts:155` -- `response.data?.kafkaConnectionProfileId ?? response.data?.profileId`
- `task-type-dialog.ts:147` -- the same expression

Reading a property off a JSON number yields `undefined`, so `profileId` is always falsy and neither
guard fires. Consequences: the **Kafka column on the task-types table always reads "default"**, and
the **Edit dialog never pre-selects the existing route**. Combined with 12.1 the second is worse
than cosmetic -- the dialog opens showing "Tenant default", and saving writes exactly that,
calling `deleteKafkaRoute` (`:199-200`) and removing an override the operator never saw.

Severity: **blocker** in combination with 12.1; **major** on its own.

### 12.3 Editing an encrypted lookup destroys the secret

`fillLookupDateDto` returns `••••••••` for an encrypted row (`SettingServiceImpl.java:609-611`).
`lookup-dialog.ts:95` prefills the Value control from that string with an unconditional
`Validators.required`. `save()` posts the whole raw form (`:109`). `updateLookupData` sees a
non-blank value, so `hasNewValue` is true (`:496`) and it encrypts what it was sent (`:501-504`).

The stored ciphertext is replaced with `encrypt("••••••••")`. The original value is unrecoverable.
`LookupDataCacheService.toLookupDataDto` decrypts into the process-wide cache
(`LookupDataCacheService.java:84-86`), so every server-side consumer of that lookup subsequently
reads the bullet string. Un-ticking "Store encrypted" without typing a value does the same in
plaintext.

The old app avoided this deliberately -- `lookup.component.ts:103` blanks the field and drops the
validator for an encrypted row, and the placeholder explains why
(`lookup.component.html:27`). This is a rewrite regression.

Severity: **blocker**.

### 12.4 The per-row topic test did not migrate, and its replacement answers a different question

The old row action called `kafkaConnectionProfile.json/testTopic` with the topic parsed out of the
row (`setting.component.ts:93-113`). `testTopic` appears nowhere in `scheduler1/next/src`.

Its replacement, `task-types.ts:165-185`, tests the *profile* the type routes to. Because of 12.2
`this.routes()[id]` is always undefined, so the action's first branch always fires and the operator
is told `"<name> uses the tenant default — test that profile directly."` (`:168`). Even once 12.2 is
fixed, testing the profile does not answer whether the topic exists: `testTopicConnection` has a
dedicated branch for `UnknownTopicOrPartitionException` returning
`Topic "X" does not exist on the connected cluster.` (`KafkaConnectionProfileServiceImpl.java:386-388`),
and that answer is now unreachable from either console.

Severity: **major**. Recorded as a migration loss in `.ai/discovery/features.md` §2.3.

### 12.5 A tenant admin carrying no tenant can delete a platform-owned tenant-family lookup

`deleteLookupData` runs only `refuseModification` (`:586-589`); it does not call
`isLookupOwnedByCaller` the way `updateLookupData` does (`:486`). Walk `refuseModification`
(`:122-144`) for a caller with role `TENANT_ADMIN` and `TenantContext.getTenantId() == null`, on the
seeded row `etl-bucket` (`tenant_id` null, parent `BUCKET_LIST`):

- not a platform admin;
- `isPlatformOnly` → family is `BUCKET_LIST` → false;
- `owned` is true, so the "platform reference data" branch is skipped;
- `extendable` is false, so the shared-provider branch is skipped;
- `Objects.equals(null, null)` is **true**, so the "belongs to another workspace" branch is skipped;
- returns null → the delete proceeds.

The row is hard-deleted (`:590`) and disappears for every tenant. The same reasoning covers the
platform's ~~`PIPELINE_IDS`,~~ `PIPELINE_HOME_PAGES` and `TASK_GROUPS` children (`PIPELINE_IDS`
itself no longer exists to be a target of this, removed 2026-09-07, see 2.9).

Reachability: `AppUserServiceImpl.addUser` cannot create such a user -- a non-platform-admin always
gets a tenant (`:165-179`). `updateUser` can: demoting a `PLATFORM_ADMIN` to `TENANT_ADMIN` without
naming a tenant leaves `effectiveTenantId = user.getTenantId()`, which is null for a former platform
admin (`:292-299`). Whether that path should exist at all belongs to `tenants-and-users`; the
missing ownership check here belongs to this feature either way.

Severity: **major**, conditional on the fixture above being reachable.

### 12.6 The task-type topic validator is stricter than the server and misstates why

`task-type-dialog.ts:131-132` applies `Validators.pattern(/^[a-zA-Z-]+$/)` with the hint "Letters
and hyphens only — the server rejects digits, dots and underscores." and the error message "Use
letters and hyphens only, such as scrapping-topic."

The server's pattern is `^topic=([a-zA-Z0-9._-]{1,249})&partitions=\[([0-9]+|\*)\]$`
(`util/KafkaTopicPartitionUtil.java:22-23`), and its test asserts that `orders-v2`,
`etl.jobs.inbound`, `job_events` and `TOPIC9` are all accepted, with a comment recording that the
narrower pattern "refused all three, and a task type carrying one dispatched nothing at all"
(`KafkaTopicPartitionUtilTest.java:55-66`). The shared parser's own spec notes the dialog "once
validated topics against `[a-zA-Z-]*`" (`shared/ui/topic.spec.ts:22-25`) -- it still does.

Consequence: a task type for a real broker topic cannot be created from the new console, and the
operator is told the server is the one refusing it.

Severity: **major**.

### 12.7 Changing a task type's status re-creates the V16 casing bug on every linked job

`updateSourceTaskType` (`:328-331`) and `deleteSourceTaskType` (`:354`) both call
`sourceJobRepository.statusChangeSourceJobLinkWithSourceTaskTypeId`, whose query is:

```
update source_job set job_status = UPPER(?2)
where task_detail_id in (select task_detail_id from source_task where source_task_type_id = ?1)
```

(`model/repository/SourceJobRepository.java:57-58`). `Status` is title-case
(`model/enums/Status.java`), and `@Enumerated(EnumType.STRING)` matches case-sensitively.
`V16__fix_source_job_status_casing.sql` exists precisely to repair rows written this way, and states
that such a row is "silently excluded from every typed JPQL query" and "a hard crash … for any code
path that tries to fully hydrate the row as an entity". The sibling method
`statusChangeSourceJobWithSourceTaskId` (`:64`) has no `UPPER`, so the two paths disagree about the
same column.

Severity: **major**. Also recorded in `.ai/discovery/database.md` §8.3.

### 12.8 The lookups screen offers a tenant admin two controls the server always refuses

`lookup.html:14-16` renders "New lookup" for everyone; `addLookupData` refuses a tenant admin any
row without a tenant-owned or tenant-extendable parent (`:451-456`), and a top-level row has no
parent at all. `lookup.html:174-186` renders Edit and Delete on every parent row;
`refuseModification` returns "Only a platform admin can change this entry -- it is platform
reference data." for any row whose parent is null (`:129-133`). The child rows are already gated by
`canModify` (`lookup.ts:187-193`, `lookup.html:217-232`) -- the same treatment simply was not
applied one level up.

Severity: **minor** (no data is at risk; the operator is misled).

### 12.9 `lookup_data.lookup_type` is globally unique on a tenant-scoped table

`V1__creating_shedlock_schema.sql:16` declares `lookup_type VARCHAR(255) UNIQUE`;
`LookupData.java:53-55` repeats it. The table carries `tenant_id` (`:68`), has a per-tenant
ownership check and a per-tenant listing. Two tenants therefore cannot hold a lookup of the same
type -- the second gets a unique violation, surfacing as a 500 rather than a message. It is also a
weak oracle: a tenant can learn that another tenant already uses a given label. Compare
`uq_tenant_task_type`, which is correctly tenant-qualified
(`TenantTaskTypeKafkaRoute.java:16-17`).

Severity: **major**. Also recorded in `.ai/discovery/database.md` §8.4 and `risks.md` #17.

### 12.10 A platform admin cannot tell whose Kafka profile is whose

`findVisibleToPlatformAdmin` returns every tenant's rows
(`KafkaConnectionProfileRepository.java:20-21`) and the new screen renders them with no owner column
and no scope filter. The old tab had both, gated on `isPlatformAdmin`
(`kafka-connection-profile.component.html:7-13, 60, 76-78`). On an installation with several
tenants the list is unreadable, and `setAsDefault` behaves differently depending on a row property
that is not shown (`KafkaConnectionProfileServiceImpl.java:208-212`).

Severity: **minor** (usability), rising with tenant count.

### 12.11 `TASK_GROUPS` is never seeded

`TASK_GROUPS` is one of the four tenant-owned families (`SettingServiceImpl.java:68`) and is what
the task editor's Group dropdown reads (`features/tasks/edit/task-edit.ts:18`,
`task-edit.html:53`). No changelog inserts it -- grepping the whole of
`db/changelog/changelog-sets` for `TASK_GROUPS` returns nothing. A tenant admin cannot create the
parent themselves (12.8), so on a fresh installation the Group dropdown is empty until a platform
admin creates the family by hand.

Severity: **minor**.

### 12.12 Status chosen on the task-type create dialog is ignored

`task-type-dialog.ts:136` offers Active/Inactive on create and sends it (`:166`).
`SettingServiceImpl.getSourceTaskType` sets `Status.Active` unconditionally (`:626`). A type created
as Inactive appears Active.

Severity: **cosmetic**, but it is a control that lies.

### 12.13 A Kafka route chosen while creating a task type is dropped

`addSourceTaskType` returns a two-argument `ResponseDto` -- status and message only (`:294`), no
`data`. The dialog recovers the new id as
`value.sourceTaskTypeId ?? (response.data as any)?.sourceTaskTypeId` (`:181`), which is undefined on
a create, so `applyRoute` takes its early-return branch (`:194`) and never calls `setKafkaRoute`.
Choosing a Kafka connection on the New task type dialog has no effect; the operator must save, then
reopen and edit.

Severity: **major**.

### 12.14 Description is required on create and not on update

`addSourceTaskType` refuses a missing description (`:271-272`); `updateSourceTaskType` does not
check it (`:300-306`) and then writes it (`:324`) into a `nullable = false` column. The new dialog
requires it on neither (`task-type-dialog.ts:130`), so a create fails with a server toast the field
did not predict, and an edit that blanks the field stores an empty string.

Severity: **minor**.

### 12.15 The lookups screen fires one request per parent on every load

`lookup.ts:74-83` `forkJoin`s a `fetchSubLookupByParentId` for every parent returned by
`appSetting`, on load and on every refresh, purely to populate the Entries column. The comment says
so and calls it "a handful of small requests", which is true today (eight seeded families) and not
a property of the code. A failure in any one of them is swallowed (`:78`), leaving that parent
showing zero entries and no expander -- indistinguishable from a parent that has none.

Severity: **minor**.

### 12.16 The tenant filter is inert across the whole feature

`SourceTaskType`, `KafkaConnectionProfile` and `TenantTaskTypeKafkaRoute` all declare
`@Filter(name = "tenantFilter", …)`, and `TenantFilterDeclarationTest` pins those declarations. But
neither `SettingServiceImpl` nor `KafkaConnectionProfileServiceImpl` calls
`TenantFilterHelper.enableIfNeeded` -- thirteen other services do. So the filter never fires on any
read path this feature uses, and the declarations read as protection that is not applied. Every
isolation decision here rests on a hand-written predicate, which is defensible, but the declarations
should not suggest otherwise. Recorded in `.ai/discovery/risks.md` #13.

Severity: **minor** today; a trap for whoever next assumes the filter is doing something.

### 12.17 `xmlCreateChecker` returns its payload in `message`

`SettingRestApi.java:159-160` returns the built document as the `message` of a success envelope
(was `:177-178` before the unrelated 2026-09-05 removal of `dynamicQueryResponse` shifted this
file's later lines, 2.9). ~~Both consoles know this (`xml-builder.ts:92-93`,
`xml-configuration.component.ts:74`), and so does the task editor.~~ Neither of those two files
exists any more -- `xml-configuration.component.ts` was removed 2026-09-07 and `xml-builder.ts` was
removed 2026-09-05, for unrelated reasons on different dates (2.8). The two real callers today are
the legacy Source Task editor's `ConfigurationMakerService.getXmlData` call
(`task.component.ts:83, 316-327`) and the next app's Task Edit `save()`
(`task-edit.ts:319-391`), and both still read the document out of `message`. Any change to the
server's wording breaks both. Recorded in `.ai/discovery/risks.md` #20.

Severity: **cosmetic**, but it is a contract nobody can see from the endpoint's signature.

### 12.18 Two mutating endpoints are declared PUT

`setting.json/deleteLookupData` is `RequestMethod.PUT` with the id in the body
(`SettingRestApi.java:143-145`, was `:161-163`, same 2.9 shift) and
`kafkaConnectionProfile.json/deleteProfile` is `PUT` with a request parameter
(`KafkaConnectionProfileRestApi.java:51-52`). Both consoles comply, with comments saying so
(`lookup.ts:128-130`, `kafka-connections.ts:206-208`). Nothing is broken; the API is simply not the
shape a reader expects.

Severity: **cosmetic**.

### 12.19 The old app's XML Configuration screen was orphaned, and is now gone -- resolved, 2026-09-07

Recorded here for completeness rather than as an outstanding defect: `setting/lookpXml`
(`_component/setting/xml-configuration/xml-configuration.component.ts` and `.html`) was reachable
from no navbar entry (2.1) and read nothing, wrote nothing of its own -- it only ever posted to
`setting.json/xmlCreateChecker` and displayed the result. As part of the same pass that removed
`PIPELINE_IDS` (2.9), it was deleted outright: the component and template files, the route in
`app.routing.ts`, the `XmlConfigurationComponent` import and declaration in `app.module.ts`, and the
barrel export in `_component/index.ts`. Confirmed by `ls`ing the component's old directory (gone)
and grepping all three of those files for `XmlConfiguration` (no matches). **This did not touch
`ConfigurationMakerService`**, which remains a live dependency of the still-existing Source Task
editor's tag-to-XML button (`task.component.ts:83, 316-327`, 2.8) -- only the standalone screen and
its route are gone.

Severity: **n/a** -- not a defect, a completed removal, kept here so the fact is not silently
dropped from a document that used to describe the screen as live.

### 12.20 The next app's XML builder and settings hub were already gone -- pre-existing staleness this document had not caught up to

This is **not** part of the 2026-09-07 `PIPELINE_IDS` work recorded throughout this document, and
predates it. `features/settings/xml-builder/` (`settings/xml`) and `features/settings/hub/`
(`admin/settings`) were removed **2026-09-05** in commit `889ae2e` ("Remove Dynamic Forms and
Query/Search Engine; UI component refactors and fixes"), for a reason unconnected to lookups or
pipelines. Confirmed by searching `scheduler1/next/src` for `xml` and for `hub`: neither directory
exists, and `features/` has no `xml-builder` or `hub` entry. The same commit also removed
`dynamicQueryResponse` from `SettingRestApi.java` (2.9) and the `dynamic-forms` feature entirely,
including `features/forms/submission-to-task-dialog.ts` (10, Dependencies) -- none of which this
document had recorded before this pass. Every reference to `settings/xml`, `xml-builder.ts`,
`xml-builder.html`, `admin/settings` or `settings-hub.ts` elsewhere in this document (2.1, 2.8, 4.1,
4.3, 4.5, 4.7, 4.9, 7, 8.1, 8.5, 9, 11 criteria 1/2/4/60-66, 13) has been marked in place with a
strikethrough and this note rather than silently deleted, matching this document's own discipline
for a resolved claim.

Severity: **n/a** -- not a defect, a fact this document was simply behind on.

---

## 13. Missing functionality

**Per-row topic reachability (12.4).** The server side exists and is complete. What is missing is a
console control that calls `testTopic` with the row's topic. Roughly: restore the row action to
call `GET /kafkaConnectionProfile.json/testTopic?topicName=<topicOf(row)>`, keep the profile test as
a separate action or fold the two into one that reports both answers. Half a day.

**Owner column and scope filter on the Kafka screen (12.10).** `KafkaConnectionProfileDto` already
carries `tenantId` and the DTO is already returned; the screen needs a column rendered for
`auth.isPlatformAdmin()` and a filter beside the protocol one. The tenant *name* would need a join
or a second call -- `tenantId` alone matches what the old app showed. Half a day for the id, one to
two days if the name is wanted.

**A tenant-qualified uniqueness rule for lookups (12.9).** A migration plus a decision about what
the key should be. See the open question in the synthesis document.

**`TASK_GROUPS` seed (12.11).** One insert in a new changelog set, plus the `setval` the earlier
seeds established as the pattern (`V9__insert_ai_provider_and_bucket_list.sql`). An hour.

~~**XML Configuration on the settings hub.** Nine cards, and this is not one of them
(`settings-hub.ts:50-69`). One line, once somebody decides whether it belongs there or in Tools
only.~~ **Moot, 2026-09-05** -- there is neither a settings hub nor an XML builder screen any more
(both removed in commit `889ae2e`, before and unrelated to this document's 2026-09-07 work; see 2.8,
12.20). Nothing to add a card for, and nothing to decide between Tools and the hub.

**Group filter on the linked-tasks panel.** The old modal had a group dropdown alongside the search
(`setting.component.html:169-176`); the new panel has search only. `groupLabel` is already on every
row (`task-types.ts:19-24`). An hour.

**Tests.** Nothing exercises `SettingServiceImpl`'s twelve service methods, `refuseModification`, or
any of `KafkaConnectionProfileServiceImpl`'s eight. Nothing exercises `task-types.ts`,
`task-type-dialog.ts`, `lookup.ts`, `lookup-dialog.ts`, `kafka-connections.ts` or
`kafka-dialog.ts` (~~`xml-builder.ts`~~ dropped from this list -- the file no longer exists, removed
2026-09-05, see 2.8, 12.20). The three private lookup predicates are covered by reflection in
`TenantOwnedLookupTest`, which is the right instinct pointed at the wrong layer -- the predicates
are correct and the code that calls them is where the defects in section 12 live. A
`SettingGuardTest` in the style of the existing `TenantOwnedLookupTest`, plus a
`lookup-dialog.spec.ts` covering the encrypted-value case and a `task-type-dialog.spec.ts` covering
the payload, would catch 12.1, 12.3, 12.5, 12.6 and 12.13 between them. Three to four days.

**A visible statement of the effective Kafka connection.** Even with 12.1 and 12.2 fixed, the
console shows at most one of the three bindings the resolver will consider. An operator asking
"which cluster will this actually publish to?" has to know that the order is route → type default →
tenant default → platform default (`config/KafkaConnectionResolver.java:49-82`) and check three
screens. A single resolved answer per task type, computed server-side, would be a small endpoint and
a large improvement. Two days.
