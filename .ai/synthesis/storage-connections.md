# Synthesis -- Storage Connections

Companion to `.ai/grooming/storage-connections.md`. Paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

Storage Connections migrated well and then grew. The new screen at `admin/storage` does everything
the old `setting/storageConnection` did and adds server-side cloning, bulk testing, an alias
pattern rule, provider-conditional validators, real loading/error/empty states, Kafka-dependency
warnings, authorship columns and a cards view. What the rewrite dropped is small in code and
sharp in effect: the Azure endpoint field is gone, the Credentials pill forgot that an Azure
connection can be credentialled by a connection string, the FTPS port/implicit-TLS pairing that the
old app got right in both directions is now wrong in the default case, and the provider is printed
as a raw enum. Alongside those sit four defects that are not migration losses at all but were
introduced with the new features or have been there since the table was written: the Clone dialog's
bucket discovery posts a payload the endpoint cannot serve and has never once succeeded; the Status
control on the create dialog is inert because the server forces `Active`; a soft-deleted connection
holds its globally-unique alias forever, so a mistaken delete is unrecoverable through the UI; and
the delete and retire confirmations describe a consequence when the server is going to refuse
outright. The work is therefore one small schema change (a partial unique index on `alias`), about
a dozen focused frontend edits, three narrow service changes, and the tests that five of the eight
service methods have never had. None of it is architectural. The order that matters is: fix the
alias burn before anyone tests deletion, and fix the confirmation wording in the same pass as the
guards it lies about.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | Clone dialog posts `{storageConnectionId}` to `discoverBuckets`; the endpoint refuses a DTO with no provider before it loads the saved row (`StorageConnectionServiceImpl.java:475-477`) | "List buckets on this server" lists the source's buckets | The feature has never worked; its spec stubs a SUCCESS envelope and never exercises the payload | Make `discoverBuckets` resolve the saved row **first** and inherit provider/endpoint/region/accessKey from it when the DTO omits them | S | Low |
| 2 | Soft delete leaves the row and the globally-unique alias in place; `addConnection`/`cloneConnection` reject it and `uq_storage_connection_alias` would too | A deleted alias becomes available again | A mis-delete permanently orphans every job pointing at that alias | Partial unique index `WHERE status <> 'Delete'`, drop the JPA `@UniqueConstraint`, and exclude deleted rows from the two alias checks | M | Medium — schema change on a live constraint |
| 3 | Status select rendered on create; `addConnection` forces `Status.Active` (`:172`) | The connection is created with the chosen status | An operator's choice is silently discarded | Honour `dto.getStatus()` on create, defaulting to `Active` when absent | S | Low |
| 4 | Delete and Inactive confirmations phrase the Kafka dependency as a consequence, then the server refuses (`:285-290`, `:314-317`) | The UI says the change will be refused, before the button | The operator is invited to do something impossible and learns from a toast | Reword both, and disable the confirm button when dependants are named | S | Low |
| 5 | No Azure endpoint field (`connection-dialog.html:61-77`); the old form had one and `StorageClientFactory.java:224-228` uses it | Azure endpoint is settable and editable | Sovereign-cloud and private-endpoint containers cannot be configured | Render the existing `endpoint` control for Azure with the old placeholder | S | Low |
| 6 | Credentials pill checks `secretKeyConfigured \|\| passwordConfigured` only (`storage-connections.ts:44-45`) | Also `azureConnectionStringConfigured`, as the old table did | An Azure connection with a working connection string reads "Not stored" | Add the field to the row interface and both pill expressions | S | Low |
| 7 | FTPS defaults to port 990 with `implicitTls` false; toggling the checkbox does not move the port (`connection-dialog.ts:110,121`) | 21 explicit / 990 implicit, kept in step, never overwriting a typed port | A default FTPS connection attempts explicit AUTH TLS on the implicit port | Port default from the flag, plus a `valueChanges` on `implicitTls` mirroring the old `onImplicitTlsChange` | S | Low |
| 8 | `testConnection` saves the row to record its result, firing `AuditListener` and stamping `updated_by` (`:387-390`) | Testing does not change who last updated the connection | The new "Updated by" column reports the tester as the editor, and a bulk test rewrites twenty rows | Write the three test-result columns with a repository `@Modifying` update that bypasses the listener | M | Medium — touches the audit path |
| 9 | Provider printed as the raw enum in the table and filter (`storage-connections.html:77,198`) | "AWS S3", "Azure Blob", "MinIO" | Cosmetic, but the old app was better | Export the label map from `connection-dialog.ts` and use it on the list | S | Low |
| 10 | `clearFilters()` ignores `onlyMine`, and the Clear button is not rendered when it is the only active filter | Clear clears everything it is offered for | The "totals cover all N" caveat can appear with no way to dismiss it | Reset `onlyMine` in `clearFilters()` and render on `isFiltered()` | S | Low |
| 11 | Empty state has no call to action (`storage-connections.html:52-53`) | Offers "New connection" from inside the empty panel | An operator with nothing configured has to find the header button | Project a button into `TableShell`'s `[empty-action]` slot | S | Low |
| 12 | Row id column dropped in the rewrite; every server message names a connection by it | The id is recoverable from the screen | "not found with 1042" cannot be matched to a row | Restore as a narrow leading column, or as a `title` on the name | S | Low |
| 13 | No test for `addConnection`, `cloneConnection`, `testConnection`, `discoverBuckets`, or the `fetchAllConnections` post-filter; the reserved-alias guard is exercised by nothing | Each guard has a refusal and a positive control | The sharpest rule in the service — claiming `etl-avatar` — is untested | One `StorageConnectionGuardTest` in the style of the existing three | M | Low |
| 14 | Nothing consults jobs, tasks, schedules or converter tasks before a delete, though the confirmation claims they will break | Dependants named before the delete | The one thing the message promises to know, it does not | A dependants endpoint over the four alias-holding tables | L | Medium |
| 15 | `is_default` is not-null on the table, in the DTO, written by `applyDto`, and read or set by nothing | Either a real default, or gone | Dead weight that reads as an unbuilt feature | Decide (see Open questions) | S | Low |
| 16 | `discoverBuckets` is the only service method without `@Transactional` yet calls `enableIfNeeded` + `findById` | Consistent with its seven siblings | Works by accident of `findById` being unfiltered | Add `@Transactional(readOnly = true)` | S | Low |

---

## 3. Solution detail

### 3.1 Clone discovery (gap 1)

The endpoint's ordering is the whole bug. `discoverBuckets` opens with

```java
if (isNull(dto) || isNull(dto.getProvider())) {
    return new ResponseDto(ERROR, "Select a provider first.");
}
```

(`StorageConnectionServiceImpl.java:475-477`) and only reaches the saved-row lookup at `:486-489`.
Swap the two: load the row when `storageConnectionId` is present, use it to fill provider,
endpoint, region and access key wherever the DTO leaves them blank, and only then insist that a
provider has been resolved from *somewhere*. The DTO keeps precedence for every field it does
supply, which is what the connection dialog relies on -- it sends a half-filled form and expects
those values used, not the stored ones.

The alternative was to fix it entirely in the browser: have `CloneDialog` copy the source's
provider, endpoint, region and access key into the payload from the row it already holds. Rejected
for two reasons. The source's `accessKey` is on the row but its **secret** is not, by design
(`toDto` withholds every `*_enc` column, `:591-621`), so the browser can never assemble a probe
that authenticates -- the server-side secret inheritance at `:497-499` is not optional. And the
endpoint already advertises `storageConnectionId` as a supported input for exactly this reason;
leaving it half-supported means the next caller hits the same wall.

Files: `process/src/main/java/process/model/service/impl/StorageConnectionServiceImpl.java`
(`discoverBuckets`, `:473-540`). No frontend change needed. The clone spec grows a case that posts
the real payload shape against a stub asserting a provider-less body is accepted.

### 3.2 Alias reuse after delete (gap 2)

Three things currently conspire: `deleteConnection` sets `Status.Delete` and keeps the row
(`:318`); `findByAlias` matches any status, so the two alias checks (`:166-168`, `:208`) refuse it;
and `uq_storage_connection_alias` (`StorageConnection.java:31-33`) is unconditional, so removing
the checks alone would move the failure into a flush-time constraint violation with an unreadable
message.

The fix is the shape the project has already used once: a **partial** unique index, exactly as
`ux_task_form_pipeline_tenant` is written at `V19__task_form_builder.sql:45-47` —
`... ON task_form (pipeline_id, COALESCE(tenant_id, -1)) WHERE form_status <> 'Delete'`, where the
`WHERE` clause is what lets a soft-deleted form give its slot back. Same problem, same answer. So:

- a changeset creating `CREATE UNIQUE INDEX ux_storage_connection_alias_live ON storage_connection (alias) WHERE status <> 'Delete'`
  and dropping `uq_storage_connection_alias`;
- remove the `@UniqueConstraint` from `StorageConnection.java:31-33` in the same change, or
  `ddl-auto=update` will put the unconditional index straight back in dev;
- narrow the two service checks to `findByAliasAndStatusNot(alias, Status.Delete)` — the repository
  already has `findByAliasAndStatus`, so this is one derived-query method
  (`StorageConnectionRepository.java:18-20`).

The rejected alternative was a hard delete. It is simpler and it would also free the alias, but it
throws away the audit trail and, more importantly, changes what `StorageBrowserServiceImpl`
observes: `isPlatformBucket` deliberately reads a connection at **any** status, because "a retired
or soft-deleted row still names a real bucket" and matching only Active rows would let the platform
guard fall through to the legacy `BUCKET_LIST` path (`StorageBrowserServiceImpl.java:450-463`). A
hard delete removes the row that guard is reading. Soft delete plus a partial index keeps that
intact.

Deployment order matters: the index must be created before the service change ships, or a brief
window exists where the service permits an alias the database still refuses.

### 3.3 Status on create (gap 3)

`addConnection` calls `applyDto` and then overwrites the status (`:171-172`). Replace the
unconditional `Status.Active` with `isNull(dto.getStatus()) ? Status.Active : dto.getStatus()`,
and guard against a client posting `Status.Delete` — creating a row already soft-deleted would
consume an alias for a connection that never existed.

The alternative was to hide the control on create, which is what the old app did
(`storage-connection.component.html:191-199`) and is a one-line template change with no server
risk. Rejected because staging a connection Inactive before its bucket exists is a real workflow
and the new dialog already promises it; and because the current state — a control that appears to
work and does not — is the worst of the three options, so leaving the server alone only makes sense
if the control also goes, and removing a capability the UI already offers is a regression in a
feature we are otherwise adding to.

### 3.4 Confirmations that tell the truth (gap 4)

Two call sites, one message. `storage-connections.ts:178-185` already fetches the dependants before
opening the confirm dialog, and `connection-dialog.ts:76-82` already fetches them when Inactive is
chosen — the data is in hand at both points. What is wrong is only the sentence and the button.

- Delete: when `kafkaProfilesUsing` returns names, the body becomes "This connection cannot be
  deleted while Kafka profiles a, b load a keystore or truststore from it. Point them at another
  connection first." and the confirm button is not offered — the dialog degrades to an
  acknowledgement. `ConfirmOptions` (`shared/ui/confirm.ts:4-9`) needs one optional field for that;
  it is a shared component, so the change has to be additive and default to today's behaviour.
- Inactive: `dependentWarning()` drops "so their next publish will fail" and gains "so this change
  will be refused." The dialog's save button can stay enabled — the server's refusal is the
  authority and the operator may still want to change something else on the form — but the warning
  must not read as a forecast.

Rejected alternative: make the server warn instead of refuse, so the messages become true. The
refusal is deliberate and argued in place (`StorageConnectionServiceImpl.java:110-119`): a warning
only ever reaches the caller who skipped the dialog — a script — where it is a line in a response
body nothing reads, while a live producer loses its truststore. Weakening the server to match a UI
string is the wrong direction.

### 3.5 The three form regressions (gaps 5, 6, 7)

All three are single-file edits and should ship together, because they are the same class of thing:
the rewrite reimplemented the provider-conditional form from the screen rather than from the old
component, and lost the details that only show up per provider.

- **Azure endpoint** — `connection-dialog.html`: render the existing `endpoint` control inside the
  `@if (isAzure())` block with the old app's placeholder, "https://account.blob.core.windows.net
  (defaults from account name)". The form control already exists (`connection-dialog.ts:96`) and is
  already sent, so this is markup only.
- **Credentials pill** — `storage-connections.ts`: add `azureConnectionStringConfigured?: boolean`
  to the row interface (`:21-46`) and extend both expressions in `storage-connections.html:141,203`.
  The condition is already written correctly one file away, in `hasStoredSecret()`
  (`connection-dialog.ts:85-87`), so lift it into a small helper rather than writing it a third
  time.
- **FTPS port** — `connection-dialog.ts`: change `:121-122` to derive the default from
  `implicitTls`, matching `storage-connection.component.ts:216-221`, and add a `valueChanges`
  subscription on `implicitTls` that moves the port between 21 and 990 **only when it currently
  holds 21, 990 or nothing** — the old app's exact condition
  (`storage-connection.component.ts:224-229`), which is what stops it clobbering a port the
  operator typed.

The rejected option for the FTPS case was to normalise the port on the server instead: default it
from `implicitTls` in `applyDto` when absent. That would fix the saved value but not the form,
which would still display 990 next to an unticked box — and the operator would be looking at a
combination that reads as wrong even after it had been silently corrected. The rule belongs where
the two fields are visible together.

### 3.6 "Updated by" and the test button (gap 8)

The cleanest fix is to stop the test result going through the entity listener at all: a
`@Modifying @Query` on `StorageConnectionRepository` writing `connection_status`, `last_tested_at`
and `last_test_message` by id, called from `testConnection` in place of `save` (`:390`). A JPQL
bulk update does not fire `@PreUpdate`, which is precisely the property wanted, and the three
columns are exactly the ones that describe a test rather than an edit.

Two alternatives were considered and rejected. Suppressing the stamp inside `AuditListener` with a
thread-local "this is not an edit" flag would work but puts feature-specific knowledge into a
listener that ten other entities share (`@EntityListeners(AuditListener.class)` appears on eleven
classes under `process/model/pojo/`) — a trap for whoever writes the next service. Adding
separate `last_tested_by` columns and leaving `updated_by` alone is more honest data but is a
migration plus a UI change to answer a question nobody has asked; the requirement is only that
testing stops *lying* about the editor.

Risk is real but contained: bulk updates bypass the persistence context, so `testConnection` must
not go on to use the entity after writing, and the response DTO must be built from the in-memory
object with the three values set by hand. The existing tests in
`StorageConnectionKafkaDependencyTest` do not touch `testConnection`, so nothing pins the current
behaviour — which is also why gap 13 should land alongside this one.

### 3.7 Cosmetics and chrome (gaps 9–12)

Grouped because they are one afternoon and no risk. Export the `PROVIDERS` label map from
`connection-dialog.ts:32-38` (it is already a module-level const) and use it for the table cell and
the filter options. Reset `onlyMine` in `clearFilters()` and change the button's `@if` to
`isFiltered()`. Project a "New connection" button into `TableShell`'s existing `[empty-action]`
slot (`shared/ui/data-table.ts:60`). Restore the id as a narrow first column after the checkbox —
the old table led with it (`storage-connection.component.html:75`) and every server message names
it.

### 3.8 Tests (gap 13)

One new file, `process/src/test/java/process/model/service/impl/StorageConnectionGuardTest.java`,
built the way the three existing ones are: Mockito mocks for the six constructor dependencies,
`TenantContext.set(...)` in `@BeforeEach`, `TenantContext.clear()` in `@AfterEach`, and every
refusal paired with a positive control on the same fixture — the pattern
`StorageConnectionTenantlessCallerTest.aPlatformAdminStillManagesTheSameRow` establishes and
explains at `:152-155`.

Minimum contents: a tenant admin refused the alias `etl-bucket` and a platform admin allowed it
(the reserved-alias guard is currently exercised by nothing — `PlatformBucketNamedGuardTest`
targets `StorageBrowserServiceImpl`, not this service); `addConnection` honouring a supplied status
once 3.3 lands; the alias check ignoring soft-deleted rows once 3.2 lands; `cloneConnection`
refused when the source belongs to another tenant and allowed for the owner; `fetchAllConnections`
dropping a platform row for a tenant admin and keeping it for a platform admin — the one that pins
the compensation for the permissive Hibernate filter.

Note `avatarBucket` is `@Value`-injected and therefore null in a unit test; `isReservedAlias`
already null-guards it (`:139-142`), so the `etl-bucket` half works unconfigured and the
`etl-avatar` half needs the field set reflectively.

### 3.9 Alias dependants (gap 14)

The delete confirmation asserts that "jobs and tasks pointing at this alias will stop resolving"
without having looked at a single one. Making that true means a read across every table that stores
an alias as a string: `source_job` / `source_task` (bucket, input and output folders),
`query_schedule` (output destination), `document_converter_task` (storage keys), and the Kafka
profiles already covered. That is a new service method and a new endpoint, tenant-scoped like
everything else here, plus a UI that can show more than a sentence when the list is long.

Deliberately sized L and sequenced last. It is the largest genuine gap in the feature and the only
one that is a new capability rather than a repair, and it should not delay the repairs. Until it
lands, the delete confirmation should say what it actually knows — the Kafka profiles — and stop
asserting about jobs and tasks it has not checked.

---

## 4. Ordering

**First, and blocking:** gap 2 (alias reuse). It is the only schema change, it has a deployment
ordering constraint of its own (index before service), and every acceptance criterion about
deletion is unreliable until it lands — a tester who deletes a fixture connection today cannot
recreate it. Do this before anyone exercises the delete path.

**Second, together:** gaps 1, 3, 4 — the three "this control does not do what it says" defects.
They are independent of each other and of gap 2, they are all small, and each one is currently
costing an operator a wasted attempt. Gap 4 should ship in the same change as the wording it
corrects, not separately, or the release notes will describe a fix nobody can see.

**Third, together:** gaps 5, 6, 7 — the migration losses in the provider-conditional form. One
file each, no dependencies, and they are the answer to "what did the rewrite quietly drop", which
is the question this document exists to answer. Ship them as one change so the regression is closed
in one place.

**Fourth:** gap 13 (tests), then gap 8 ("Updated by"). Tests first, deliberately: gap 8 changes how
a row is written and nothing currently pins `testConnection`'s behaviour, so the test that would
catch a mistake has to exist before the mistake can be made. Gap 8 in turn unblocks trusting the
Created by / Updated by columns at all, which is what makes gap 12 (the id column) and the
authorship display worth having.

**Fifth:** gaps 9, 10, 11, 12, 16 — cosmetics and the missing `@Transactional`. No dependencies,
no risk, and they are the right work for whatever time is left in the slice.

**Last, and separately scoped:** gap 14 (alias dependants) and gap 15 (`is_default`). Both need a
decision before they need code. Neither blocks anything above.

Downstream: `object-browser` cannot be verified end to end until at least one connection can be
created, tested and deleted cleanly, so gaps 1–4 gate that feature's QA as well as this one.
`platform-configuration`'s Kafka screen shares `kafkaProfilesUsing` through
`kafka-dependents.ts`, so any change to the dependency sentence has to be checked on both screens.

---

## 5. Out of scope

**Rewriting the alias as a foreign key.** Every consumer stores the alias as a plain string with no
referential integrity — `job_queue.bucket`, a Kafka profile's `sslTruststoreBucket`, a converter
task's storage key. Making it a real relationship would be the correct model and would make gap 14
free, but it means migrating every one of those columns and every code path that resolves a bucket
by name, across six features. Not this slice.

**Changing the Hibernate filter on `StorageConnection`.** The permissive
`(tenant_id = :tenantId or tenant_id is null)` condition (`StorageConnection.java:44`) is wrong for
a listing and right for the avatar and Kafka alias lookups, and the service compensates
(`:328-335`). Tightening it would break `etl-avatar` and `etl-bucket` resolution; splitting it into
two named filters is a change to a mechanism fourteen other entities share. Recorded as Known issue
12.11, left alone here.

**Hardening the class-level `@PreAuthorize`.** `StorageConnectionRestApi` has exactly one,
class-level, with no method-level annotation to replace it — which is the correct state given
`@PreAuthorize` is not repeatable. There is nothing to fix; it is called out only so a future
change knows not to add one per method.

**`fetchConnectionById`.** Dead in both clients and already listed as undecided backend surface in
`.ai/discovery/features.md:76`. It belongs to a cross-feature decision about five dead endpoints,
not to this document.

**The `MineFilter` `hidden` count.** Rendered by the shared component, bound by none of its eleven
call sites, so the "(N hidden)" badge is permanently zero everywhere. Cross-cutting, and fixing it
here would fix it for one screen out of eleven.

**Test-on-save, copy-alias, bulk delete, restore-a-deleted-connection.** All listed under Missing
functionality in the grooming document. Each is a genuine improvement and none is a defect; they
belong in a later slice once the repairs above have landed.

**Anything about the old app.** `scheduler1` keeps working as it does. This document treats it only
as the specification of record for what the new screen is supposed to do.

---

## 6. Open questions

**6.1 Should `is_default` become a feature or be deleted?**
Options: (a) build it — two endpoints and a row action, mirroring `KafkaConnectionProfile`'s
`setAsDefault` / `clearDefault`, so a job with no bucket named falls back to the default
connection; (b) drop the column, the DTO field and the `applyDto` branch. **Recommendation: (b),
drop it.** Nothing in six years of consumers has asked for a fallback bucket; every alias-holding
column in the product is explicitly set, and a silent fallback in storage is how a job writes to
the wrong bucket without anyone noticing. Dropping is a nullable-column removal and three small
deletions. If a default is genuinely wanted later, it is easier to add with a clear requirement
than to keep guessing at one.

**6.2 Should a create be allowed to specify `Inactive`, or should the control disappear on create?**
Options: (a) server honours `dto.getStatus()`; (b) template hides the select unless editing, as the
old app did. **Recommendation: (a).** Staging a connection before its bucket exists is a real use
and the dialog already advertises it; (b) removes a capability the UI currently claims to have. The
cost of (a) is one line plus a guard against `Status.Delete` arriving from a client.

**6.3 Partial unique index, or hard delete, for the alias problem?**
Options: (a) partial unique index `WHERE status <> 'Delete'`, keeping the soft delete; (b) hard
delete the row. **Recommendation: (a).** `StorageBrowserServiceImpl.isPlatformBucket` deliberately
reads connections at any status, including deleted ones, because "a retired or soft-deleted row
still names a real bucket" (`StorageBrowserServiceImpl.java:450-463`) — a hard delete removes the
row that guard depends on. The project has also already solved exactly this problem this way, at
`V19__task_form_builder.sql:45-47`, so (a) is the house pattern.

**6.4 How should "Updated by" stop being rewritten by a test?**
Options: (a) a `@Modifying` repository update for the three test-result columns, bypassing the
listener; (b) a thread-local suppression flag inside `AuditListener`; (c) new `last_tested_by`
columns, leaving `updated_by` alone. **Recommendation: (a).** It is local to this service, needs no
migration, and expresses the actual intent — recording a test result is not an edit. (b) puts
feature knowledge into a listener ten other entities share; (c) is a migration and a UI change to
answer a question nobody has asked.

**6.5 How much should the delete confirmation claim before gap 14 exists?**
Options: (a) leave the sentence as it is, asserting jobs and tasks will break; (b) narrow it to
what is actually checked — the Kafka profiles — and say nothing about jobs and tasks;
(c) hold the wording until the dependants endpoint exists. **Recommendation: (b).** The current
sentence is an assertion made without a lookup, which is the same category of problem as the
warning-versus-refusal mismatch in gap 4; narrowing it costs nothing and is honest. (c) couples a
one-line fix to an L-sized piece of work.

**6.6 Does the alias-dependants lookup (gap 14) belong in this feature's slice at all?**
Options: (a) here, as the natural completion of the delete guard; (b) as its own piece of work
scoped across `source-jobs`, `source-tasks` and `query-and-search-engines`, since it reads their
tables. **Recommendation: (b).** The endpoint has to know the shape of four other features' data
and will need their owners' input on what counts as a dependency; scoping it here would either
produce a shallow version or stall the sixteen small repairs behind it. It should be raised as its
own item with this document as the reason.
