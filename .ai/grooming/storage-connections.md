# Grooming -- Storage Connections

Feature 9 in `.ai/discovery/features.md`. Status **migrated**: old `setting/storageConnection` →
new `admin/storage`.

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Purpose

An operator has a bucket somewhere -- an S3 bucket, an Azure container, a MinIO bucket on the
cluster next door, or a directory on an FTP server -- and wants the console to be able to read from
and write to it. This screen is where they say so once: pick the provider, paste the credentials,
name it.

The name is the point. Everything else in the product refers to storage by a short string called
the **alias** -- a job's bucket, a converted document's output, a query's CSV destination, the
folder a Kafka profile loads its truststore from. None of those places ask for an endpoint or a
key; they ask for an alias, and this screen is what makes an alias mean something. Add
`prod-archive` here and `prod-archive` becomes a selectable source in Object Browser, a valid
bucket on a job, and a place a transcript can be written. Delete it and every one of those stops
resolving.

Two other things the screen exists for, both operational rather than administrative:

- **"Is it actually reachable?"** Credentials rot, endpoints move, firewalls change. The Test
  button opens a real connection and records the answer on the row, so the screen doubles as a
  health board for the estate's storage.
- **"I need another one exactly like that one, pointing at a different bucket."** Cloning copies
  the credentials server-side, because the secret is deliberately never sent back to the browser
  and so cannot be re-assembled there.

Credentials are write-only across the API. You can set a secret and you can replace it; you can
never read one back. The screen tells you only whether one is stored.

---

## 2. Existing behaviour

### 2.1 Where each app puts it

| | Old app | New app |
|---|---|---|
| Route | `setting/storageConnection` (`scheduler1/src/app/app.routing.ts:123-128`) | `admin/storage` (`scheduler1/next/src/app/app.routes.ts:124-130`) |
| Guard | `AuthGuard` + `RoleGuard`, `data.roles = ['PLATFORM_ADMIN','TENANT_ADMIN']` | `roleGuard` with `data.minRole = 'TENANT_ADMIN'`, under the shell's `authGuard` + `passwordChangeGuard` (`scheduler1/next/src/app/app.routes.ts:128-129`) |
| Component | `StorageConnectionComponent`, 321 TS + 387 HTML (`scheduler1/src/app/_component/setting/storage-connection/`) | `StorageConnections` + `ConnectionDialog` + `CloneDialog` + `kafka-dependents.ts`, 1542 lines incl. 4 specs (`scheduler1/next/src/app/features/admin/storage/`) |
| Nav | Settings dropdown, shown only to the two admin roles (`scheduler1/src/app/app.component.html:76-78`) | Configuration group, `adminOnly` (`scheduler1/next/src/app/features/shell/shell.ts:114-115`); also a card on the settings hub (`.../settings/hub/settings-hub.ts:55-56`) and the Object Browser empty state links to it (`.../objects/objects.html:64-66`) |
| Service layer | `StorageConnectionService`, 7 methods (`scheduler1/src/app/_services/storage-connection.service.ts`) | No service class -- each component injects `HttpClient` directly |

### 2.2 The list screen

**Old.** Three KPI tiles -- Connections (the *filtered* count), Active, Tested OK
(`storage-connection.component.html:7-29`). A toolbar with a free-text search over name / alias /
bucket / host, a provider dropdown populated from the static `STORAGE_PROVIDERS` constant, a Clear
button that is always rendered and disabled when no filter is set, Refresh, and Add Connection
(`:31-54`). One table with nine columns: `# No` (the row id), Name (+ description underneath),
Alias, Provider, Target, Credentials, Last Test, Status, Action (`:74-84`). Per-row: Edit, Test,
and a kebab whose only item is Delete (`:118-144`).

**New.** Four stat tiles -- In service, Tested OK, Failing, Untested -- computed over the whole
estate rather than the filtered view, with a line underneath saying so while a filter is on
(`storage-connections.html:29-47`, `storage-connections.ts:110-120`). Toolbar: a table/cards view
toggle persisted under `etl.view.storage`, the provider dropdown (derived from the data that is
actually present, `storage-connections.ts:72-73`), search, an "Only mine" toggle, and a Clear
button rendered only when search or provider is set (`storage-connections.html:71-89`). The table
has eleven columns: a select-all checkbox, Name, Alias, Provider, Target, Credentials, Last test
(with the timestamp underneath), Created by, Updated by, State, actions
(`storage-connections.html:161-178`). Ticking rows opens a second toolbar row offering **Test
selected** (`:59-70`). Per-row kebab: Edit, Test connection, Clone…, Delete
(`:233-242`). A cards view renders the same data as a grid of provider-glyphed cards
(`:91-156`).

Both compute `Target` the same way -- host:port + base directory for FTP/FTPS, otherwise bucket
name falling back to alias (`storage-connection.component.ts:157-163`,
`storage-connections.ts:214-220`).

Loading, error and empty are handled very differently. The old screen has no loading state at all
for the list -- `fetchAllConnections` never touches `SpinnerService`
(`storage-connection.component.ts:165-175`; noted in `.ai/discovery/frontend-old.md:747`) -- and a
failed load produces a toast plus an empty table, indistinguishable from having no connections. The
new screen routes all three through `TableShell`
(`scheduler1/next/src/app/shared/ui/data-table.ts`): a spinner, an error panel with a Try again
button, and an empty panel whose message distinguishes "No connections match the filters." from
"No connections configured yet." (`storage-connections.html:49-55`).

### 2.3 The add/edit form

Both apps drive one form off the selected provider.

| Field | Old | New |
|---|---|---|
| Connection name | required (`storage-connection.component.ts:194`) | required (`connection-dialog.ts:91`) |
| Alias | required only (`:195`) | required **and** matched against `/^[a-zA-Z0-9._-]+$/` (`connection-dialog.ts:30,92`) |
| Provider | select of 5, with a per-provider hint line (`:196`, `_models/storage-connection.model.ts:3-9`) | same 5, same idea, different hint text (`connection-dialog.ts:32-38`) |
| Status | shown **only when editing** (`storage-connection.component.html:191-199`) | shown always, create included (`connection-dialog.html:147-153`) |
| Bucket / Container | free text, optional, with a Discover button for the three object stores (`:213-239`) | same, plus a client-side `required` for every object store (`connection-dialog.ts:145`) |
| Region | S3 only | S3 only |
| Endpoint | one field for **all three** object stores, with a per-provider placeholder (`:255-261`) | S3 and MinIO only -- **no Azure endpoint field** (`connection-dialog.html:61-77`) |
| Access key / Secret key | S3 + MinIO, both optional | S3 + MinIO; access key required for S3 always, secret key required for S3 on create (`connection-dialog.ts:156-157`) |
| Azure connection string / account name / account key | all three (`:283-297`) | all three, with a cross-field validator requiring the string *or* the account name on create (`connection-dialog.ts:17-22,158-162`) |
| FTP host / port / username / password / base directory / passive / implicit TLS | all present, none required client-side | host and username required; password required on create only (`connection-dialog.ts:147-150`) |
| FTP port defaulting | on provider change: `990` only if FTPS **and** implicit TLS is already ticked, else `21`; ticking implicit TLS moves the port between 21 and 990 (`storage-connection.component.ts:216-229`) | on provider change: FTPS → `990`, FTP → `21`; ticking implicit TLS does nothing to the port (`connection-dialog.ts:120-122`) |

Both apps implement the same "blank secret means keep the stored one" rule by deleting empty
`secretKey` / `azureConnectionString` / `password` from the payload before sending
(`storage-connection.component.ts:236-242`, `connection-dialog.ts:212-216`), which matches the
server (`StorageConnectionServiceImpl.java:575-584`).

**Bucket discovery** is the same shape in both: POST the form as it stands to
`discoverBuckets`, and if buckets come back swap the text input for a select with a "type instead"
escape (`storage-connection.component.ts:91-118`, `connection-dialog.ts:183-202`). Both report the
failure inline under the field rather than as a toast.

**Only in the new app:** when Status is switched to Inactive on an existing connection, the dialog
lazily fetches every Kafka profile and names the ones bound to this alias underneath the field
(`connection-dialog.ts:76-82,176-181`, `kafka-dependents.ts:24-44`).

### 2.4 Test, clone, delete

**Test.** Identical in both: POST `testConnection?storageConnectionId=`, toast the result, reload
the list (`storage-connection.component.ts:267-284`, `storage-connections.ts:156-173`). The server
builds an *uncached* client and, for an object store, lists one object at the bucket root; for
FTP it calls the FTP service's own `testConnection`. It then writes `connectionStatus`,
`lastTestedAt` and `lastTestMessage` back onto the row and returns SUCCESS or ERROR accordingly
(`StorageConnectionServiceImpl.java:356-394`).

**Bulk test** exists only in the new app (`storage-connections.ts:325-353`): it runs the ticked
ids sequentially, shows "Testing n of m…", reports both the passed and the failed count, then
clears the selection and reloads. Ids for rows that have since disappeared are pruned on every load
(`:278-284`).

**Clone** exists only in the new app. `CloneDialog` asks for a name, an alias and a bucket, and
POSTs them with `?sourceId=` (`clone-dialog.ts:143-147`). The server copies everything else from
the source -- provider, endpoint, region, host, port, TLS flags, and the *encrypted* secret columns
moved across without being decrypted -- stamps the copy with the **caller's** tenant, forces
`Active` / `UNTESTED`, and returns "Cloned to "x". Test it before relying on it."
(`StorageConnectionServiceImpl.java:192-249`).

**Delete.** Old: a Bootstrap modal saying the alias will stop resolving and no files are removed
(`storage-connection.component.html:368-387`). New: `confirmWith` with the same sentence plus, when
applicable, the Kafka-dependency note naming the profiles (`storage-connections.ts:175-201`). Both
then call `deleteConnection?storageConnectionId=`. The server soft-deletes -- `status = Delete` --
after refusing outright if any visible Kafka profile binds to the alias
(`StorageConnectionServiceImpl.java:302-322`).

### 2.5 What the server does with a connection once it exists

- **Object Browser.** `StorageBrowserServiceImpl.collectBuckets` lists every non-deleted connection,
  keeps only `Status.Active`, and narrows to the caller's own unless the caller is a platform admin
  or a trusted workflow thread (`StorageBrowserServiceImpl.java:105-112`). Legacy `BUCKET_LIST`
  lookup entries are still honoured, but a storage connection with the same alias wins (`:117-133`).
- **Resolving one bucket.** `resolveService` looks up `findByAliasAndStatus(bucket, Active)`,
  re-checks the tenant, and wraps the client in a `BucketRewritingStorageService` when the alias
  differs from the real bucket name (`StorageBrowserServiceImpl.java:530-548`).
- **Kafka.** A profile stores a storage alias as a plain string in `sslTruststoreBucket` /
  `sslKeystoreBucket` with no foreign key. `KafkaConnectionProfileServiceImpl.refuseUnusableSecret`
  resolves it by `findByAlias` and refuses a bucket the caller does not own
  (`KafkaConnectionProfileServiceImpl.java:476-487`).
- **Platform bootstrap.** `StorageConnectionBootstrap` creates the two platform-owned MinIO
  connections `etl-avatar` and `etl-bucket` from `MINIO_*` env vars on first start, with
  `tenantId = null`, and migrates old `BUCKET_LIST` lookup children into connection rows
  (`StorageConnectionBootstrap.java:144-208`).

### 2.6 Tests that exist

| Where | Count | What it covers |
|---|---|---|
| `process/src/test/.../StorageConnectionKafkaDependencyTest.java` | 7 | delete/rename/retire refused while a profile binds the alias; every dependant named; an endpoint-only edit still saves and never even looks the dependants up |
| `process/src/test/.../StorageConnectionTenantlessCallerTest.java` | 5 | a `TENANT_ADMIN` token carrying no tenant cannot repoint, retire, read by id or list a platform connection -- with a platform-admin positive control on the same fixture |
| `process/src/test/.../StorageConnectionAliasDisclosureTest.java` | 3 | the alias-collision message never names the colliding row |
| `scheduler1/next/.../storage-connections.spec.ts` | 5 | tile arithmetic; bulk test covers ticked-but-filtered-out rows; selection pruned on reload |
| `scheduler1/next/.../connection-dialog.spec.ts` | 5 | S3 key requirements on create vs edit; rules dropped on provider change |
| `scheduler1/next/.../clone-dialog.spec.ts` | 4 | alias pattern enforced; empty-but-successful discovery reported as info, not an error |
| `scheduler1/next/.../kafka-dependents.spec.ts` | 9 | exact-match alias lookup, de-duplication, failure returns `[]`, sentence wording |

**No tests at all for:** `addConnection` (including the reserved-alias guard and the status
handling), `updateConnection`'s alias-uniqueness branch, `testConnection`, `discoverBuckets`,
`cloneConnection`, or `fetchAllConnections`'s post-filter. **The old app has no tests whatsoever** --
there is no spec file anywhere under `scheduler1/src`.

---

## 3. Expected behaviour

Everything in section 2 that is not called out below is expected to stay as it is. What follows is
the delta.

**A connection is created with the status the operator chose.** The new dialog offers a Status
select on create; the server ignores it (`StorageConnectionServiceImpl.java:172` sets
`Status.Active` unconditionally, and `applyDto` never touches status). Either the server honours
`dto.getStatus()` on create, or the control is hidden on create as it was in the old app. Honouring
it is the better answer: creating a connection Inactive is how an operator stages one before its
bucket exists.

**A deleted connection's alias becomes available again.** Today the soft delete leaves the row in
the table and `findByAlias` matches any status, so `addConnection` refuses the alias forever
(`:166-168`) -- and the unique index `uq_storage_connection_alias` would refuse it even without the
check (`StorageConnection.java:31-33`). An operator who deletes `prod-archive` by mistake cannot
recreate it under the same name, and every job pointing at that alias is unrecoverable through the
UI.

**"Credentials: Stored" is true for an Azure connection credentialled by a connection string
alone.** The new list checks only `secretKeyConfigured || passwordConfigured`
(`storage-connections.ts:44-45`, `storage-connections.html:141,203`). The old app checked all three
including `azureConnectionStringConfigured` (`storage-connection.component.html:98-99`), and the DTO
carries it (`StorageConnectionDto.java:43`).

**An Azure endpoint can be set and changed from the form.** `StorageClientFactory` uses it and only
falls back to `https://<account>.blob.core.windows.net` when it is blank
(`StorageClientFactory.java:224-228`) -- which is what a sovereign cloud or a private endpoint
needs. The old form had the field; the new one does not render it for Azure
(`connection-dialog.html:61-77`). The stored value survives an edit because the control still
exists in the form group (`connection-dialog.ts:96`) and is sent by `getRawValue()`, so this is
"cannot set", not "wipes on save".

**A new FTPS connection defaults to explicit TLS on port 21, and ticking Implicit TLS moves it to
990.** The new dialog defaults FTPS to 990 while leaving `implicitTls` false
(`connection-dialog.ts:110,121`), which asks the client to attempt explicit AUTH TLS against the
implicit port -- `FtpObjectStorageServiceImpl.java:69,74-76` builds the client from `implicitTls`
and uses the stored port as-is. The old app got this right in both directions
(`storage-connection.component.ts:216-229`).

**The Clone dialog's "List buckets on this server" lists the source's buckets.** It currently
cannot: it posts `{ storageConnectionId }` with no provider (`clone-dialog.ts:100-101`) and
`discoverBuckets` refuses a DTO with no provider before it ever loads the saved row
(`StorageConnectionServiceImpl.java:475-477`). See Known issues.

**A refusal is announced before the click, not after it.** Both the delete confirmation
(`storage-connections.ts:179-185`) and the Inactive warning in the edit dialog
(`connection-dialog.ts:76-82`) phrase the Kafka dependency as a consequence -- "their next publish
will fail" -- while the server refuses the operation outright
(`StorageConnectionServiceImpl.java:285-290,314-317`). The wording should say the change will be
refused, and the confirm button should not be offered as though it will work.

**Running a test does not change who last updated the connection.** `testConnection` saves the row
to record the result (`:390`), which fires `AuditListener.onUpdate` and stamps `updated_by`
(`AuditListener.java:41-51`). The new list surfaces that as the "Updated by" column, so testing a
connection rewrites its apparent editor.

**The Provider column reads as a label.** The old table ran the value through `providerLabel()`
("AWS S3", "Azure Blob", "MinIO"); the new one prints the raw enum
(`storage-connections.html:198`).

---

## 4. Frontend requirements

### 4.1 Route and shell

| Item | Value |
|---|---|
| Path | `admin/storage`, lazy `loadComponent` |
| Guards | `authGuard` + `passwordChangeGuard` (inherited from the shell), `roleGuard` with `data.minRole: 'TENANT_ADMIN'` |
| Nav | Configuration group, `adminOnly: true`, icon `cloud`, hint "S3, Azure, MinIO, FTP" |
| Other entry points | Settings hub card; Object Browser's "No storage is connected yet" empty state |

`roleGuard` reads a single minimum role and resolves the rest through the hierarchy in
`AuthService` (`core/auth/auth.guard.ts:33-42`), so `PLATFORM_ADMIN` is admitted without being
listed. `auth.guard.spec.ts:133-144` pins `admin/storage` at `TENANT_ADMIN`.

### 4.2 Components

| Component | File | Responsibility |
|---|---|---|
| `StorageConnections` | `features/admin/storage/storage-connections.ts` + `.html` | List, filters, tiles, selection, bulk test, per-row test/delete, dialog launch |
| `ConnectionDialog` | `.../connection-dialog.ts` + `.html` | Create and edit, provider-conditional fields and validators, bucket discovery, Inactive dependency warning |
| `CloneDialog` | `.../clone-dialog.ts` (inline template) | Name / alias / bucket for a server-side copy |
| `kafka-dependents.ts` | `.../kafka-dependents.ts` | `kafkaProfilesUsing()` + `kafkaDependencyNote()`, shared by the list and the dialog |

Shared chrome consumed: `TableShell`, `StatTile`, `StatusPill`, `MineFilter`, `ViewToggle`, `Icon`,
`Field`, `FormDialog`, `confirmWith`, `ToastService`.

### 4.3 Table

Columns, in order: select checkbox · Name (+ description) · Alias (mono, accent) · Provider ·
Target · Credentials · Last test (+ timestamp) · Created by · Updated by · State · kebab.

Provider must render the human label rather than the enum. The row id (`storageConnectionId`) is
worth restoring as a narrow leading column or at least a `title` on the name, because every server
message identifies a connection by it ("Storage connection saved with 1042.", "Storage connection
not found with 1042.").

The kebab carries Edit · Test connection · Clone… · Delete, with Delete separated and styled
`menu-item-danger`. The row dims (`opacity-55`) and its kebab disables while that row is being
tested.

### 4.4 Cards view

Provider glyph, name, alias (leading, mono), status pill, kebab; description clamped to two lines;
a Target / Provider definition list; and a footer of test pill + credentials pill + last-tested
timestamp. Persisted per screen under `etl.view.storage` by `ViewToggle`. The cards view currently
omits Created by / Updated by, which is acceptable -- it is the scan view, not the audit view.

### 4.5 Filters and tiles

- Search over connection name, alias, bucket name and host, case-insensitive substring.
- Provider select, options derived from the connections actually present.
- "Only mine", matched on `createdBy` against `auth.user()?.appUserId`, not persisted.
- Clear must reset **every** filter it is offered for. Today it resets search and provider only, and
  is not even rendered when "Only mine" is the sole active filter
  (`storage-connections.html:86-88`, `storage-connections.ts:246-249`) -- while `isFiltered()`
  counts it (`:96-97`).
- Four tiles: In service (foot: "of N configured"), Tested OK, Failing, Untested. Counted over the
  whole estate, with the caveat line rendered whenever `isFiltered()`.

### 4.6 Dialogs

`ConnectionDialog` is `size="wide"` on a two-column `form-grid`. Field visibility by provider:

| Provider | Fields shown beyond name / alias / description / status |
|---|---|
| MINIO | Bucket (+ Discover), Endpoint (required), Access key, Secret key |
| S3 | Bucket (+ Discover), Region, Endpoint, Access key, Secret key |
| AZURE | Container (+ Discover), Connection string, Account name, Account key — **plus an Endpoint field, to be added** |
| FTP | Host, Port, Username, Password, Base directory, Passive mode |
| FTPS | the same, plus Implicit TLS |

Secret fields carry `type="password"` and `autocomplete="new-password"`, and on edit their hint
reads "Leave blank to keep the stored …" whenever `hasStoredSecret()`.

`CloneDialog` asks for name, alias and bucket only, with a standing note that credentials are
copied server-side and the copy starts untested.

### 4.7 Loading, empty and error

Supplied by `TableShell`: a centred spinner while loading; an alert glyph, the message and a
**Try again** button on error; an icon plus a message on empty, differentiated between "No
connections match the filters." and "No connections configured yet."
(`storage-connections.html:49-55`). The empty state should also offer a **New connection** button
through the shell's `[empty-action]` slot -- it currently does not, so an operator arriving with
nothing configured has to find the button in the page header.

Inline, non-toast errors: `discoverError()` under the bucket field
(`connection-dialog.html:56-58`); `dependentWarning()` under Status (`:155-160`). Everything else
is a toast.

### 4.8 Dark and light

Theming is token-based: `:root` and `html.dark` blocks in `scheduler1/next/src/styles.css:93-170`,
toggled by `ThemeService` adding `.dark` to `<html>` and remembered under `etl_theme`
(`core/theme.service.ts`). Nothing on this screen hardcodes a colour -- pills use
`pill-ok` / `pill-crit` / `pill-neutral`, text uses `var(--text-muted)` /
`var(--text-secondary)`, and the accent alias uses `text-accent`, which is redefined per theme.
Both themes must be checked for: the test pills, the "Not stored" neutral pill, the four stat
tiles' tones (`info`/`ok`/`crit`/`warn`) and the bulk sub-bar's `bg-sunken`.

### 4.9 Responsive

Stat tiles: `grid-cols-2` on small, `md:grid-cols-4` above. Cards: 1 / `sm:2` / `xl:3`.
The table scrolls inside its own `overflow-x-auto` box supplied by `TableShell`
(`shared/ui/data-table.ts:66`), so the toolbar and the bulk bar stay put -- which matters here,
since eleven columns will not fit a laptop width. The dialog is `max-w-[calc(100vw-2rem)]` and its
`form-grid` collapses to one column below `sm`.

---

## 5. Backend requirements

### 5.1 Endpoints

`process/src/main/java/process/api/StorageConnectionRestApi.java`, class-level
`@PreAuthorize("hasRole('TENANT_ADMIN')")` at line 24. No method carries its own `@PreAuthorize`,
so the class-level annotation is in force for all eight.

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/storageConnection.json/fetchAllConnections` | TENANT_ADMIN | Every non-deleted connection the caller owns, newest id first, with `createdBy` / `createdByName` / `updatedByName` attached and secrets replaced by `*Configured` booleans |
| GET | `/storageConnection.json/fetchConnectionById?storageConnectionId=` | TENANT_ADMIN | One connection, ownership-checked. **Called by neither frontend** (`.ai/discovery/frontend-old.md:913`) |
| POST | `/storageConnection.json/addConnection` | TENANT_ADMIN | Validates, refuses a taken or reserved alias, stamps the caller's tenant, forces `Active` + `UNTESTED` |
| PUT | `/storageConnection.json/updateConnection` | TENANT_ADMIN | Alias uniqueness first (before the tenant filter), then ownership, then the Kafka guard on rename/retire, then apply + evict the cached client |
| POST | `/storageConnection.json/cloneConnection?sourceId=` | TENANT_ADMIN | Copies the source including its encrypted secrets, under the caller's tenant, `Active` + `UNTESTED` |
| DELETE | `/storageConnection.json/deleteConnection?storageConnectionId=` | TENANT_ADMIN | Refuses while a visible Kafka profile binds the alias; otherwise soft-deletes (`status = Delete`) and evicts |
| POST | `/storageConnection.json/testConnection?storageConnectionId=` | TENANT_ADMIN | Builds an uncached client, lists one object at the bucket root (or runs the FTP probe), records `connectionStatus` / `lastTestedAt` / `lastTestMessage` |
| POST | `/storageConnection.json/discoverBuckets` | TENANT_ADMIN | Enumerates buckets for the supplied credentials, falling back to the saved row's encrypted secrets when an id is supplied |

Every method returns HTTP 200 with a `ResponseDto` whose `status` is `SUCCESS` or `ERROR`; only an
unhandled exception produces a 500 (`StorageConnectionRestApi.java:39-42` and siblings). Clients
therefore have to branch on the envelope, not on the HTTP status -- which both frontends do.

### 5.2 Services

| Class | Role |
|---|---|
| `StorageConnectionServiceImpl` (623 lines) | All eight operations, validation, the reserved-alias guard, the Kafka-dependency guard, DTO mapping that withholds secrets |
| `StorageClientFactory` | Builds and caches a provider client per connection; `buildUncached` for tests; `listAvailableBuckets`; `ambientCredentialsAllowed(tenantId)` = `storage.allow-instance-role` **and** a null tenant (`:161-163`) |
| `EncryptionUtil` | Encrypts `secret_key_enc`, `azure_connection_string_enc`, `password_enc`; decrypted only inside `StorageClientFactory` (`:165-176`) |
| `TenantFilterHelper` / `TenantOwnership` | The Hibernate filter and the explicit ownership rule respectively |
| `UserNameResolver.attachToDtos` | Fills `createdBy` / `createdByName` / `updatedByName` on the list in one extra query (`UserNameResolver.java:86-113`) |
| `StorageConnectionBootstrap` | Startup-only: creates `etl-avatar` and `etl-bucket`, migrates `BUCKET_LIST` lookups |

`discoverBuckets` is the only method on the service without `@Transactional`
(`StorageConnectionServiceImpl.java:473-474`, against `:159 :193 :252 :303 :325 :343 :357`) yet it
still calls `tenantFilterHelper.enableIfNeeded` and `findById` (`:487-489`). It works because
`findById` is unfiltered and `isOwnedByCaller` is what actually decides, but the inconsistency is
worth closing.

---

## 6. Database requirements

### 6.1 `storage_connection`

Mapped by `process/src/main/java/process/model/pojo/StorageConnection.java`.

| Column | Type / notes |
|---|---|
| `storage_connection_id` | PK, sequence `storage_connection_Seq`, initial value 1000 |
| `tenant_id` | nullable; **null means platform-owned**, not ownerless. Indexed (`idx_storage_connection_tenant_id`) |
| `connection_name` | not null |
| `alias` | not null, **globally unique** (`uq_storage_connection_alias`) -- not scoped by tenant |
| `provider` | not null, enum string: `MINIO` / `S3` / `AZURE` / `FTP` / `FTPS` |
| `description` | nullable |
| `bucket_name`, `endpoint`, `region`, `access_key` | plaintext by design |
| `secret_key_enc` | 1000, `EncryptionUtil` ciphertext |
| `azure_account_name` | plaintext |
| `azure_connection_string_enc` | 2000, ciphertext |
| `host`, `port`, `username`, `base_directory` | FTP/FTPS, plaintext |
| `password_enc` | 1000, ciphertext |
| `passive_mode` | default `true` |
| `implicit_tls` | default `false` |
| `is_default` | not null, default `false`. **Written by nothing and read by nothing** -- no UI in either app, and the only writer is the conditional in `applyDto` (`StorageConnectionServiceImpl.java:569-571`) that no client populates |
| `status` | not null, enum `Active` / `Inactive` / `Delete` |
| `connection_status` | free string, in practice `UNTESTED` / `SUCCESS` / `FAILED` |
| `last_tested_at`, `last_test_message` (TEXT), `date_created` | bookkeeping |
| `created_by`, `updated_by` | BIGINT, added by `V22__audit_columns.sql:27-28`, stamped by `AuditListener` |

The table itself is created by Hibernate `ddl-auto=update` in dev
(`application-dev.properties:87`), not by a changeset; stage and prod are `validate`. Liquibase
touches it only twice: a table comment (`V17__table_descriptions.sql:33`) and the two audit
columns.

### 6.2 Hibernate filter

`@Filter(name = "tenantFilter", condition = "(tenant_id = :tenantId or tenant_id is null)")`
(`StorageConnection.java:44`) -- the **shared-catalogue** condition, the same one
`SourceTaskType`, `TaskForm` and `KafkaConnectionProfile` carry. It deliberately publishes
platform-owned rows so that `etl-avatar` and `etl-bucket` resolve by alias for the avatar and
Kafka workflows. It is therefore the wrong rule for a listing, and `fetchAllConnections`
post-filters with `isOwnedByCaller` to compensate (`:333-335`).

### 6.3 Migrations needed

Two, both driven by section 3:

1. **Alias reuse after delete.** Either the unique constraint becomes partial --
   `CREATE UNIQUE INDEX ... ON storage_connection (alias) WHERE status <> 'Delete'`, the shape
   `ux_task_form_pipeline_tenant` already uses (`V19__task_form_builder.sql:45-47`) -- or delete
   stops being soft. A partial index cannot be expressed as a JPA `@UniqueConstraint`, so it has to
   be a changeset, and `StorageConnection.java:31-33` must drop its `@UniqueConstraint` in the same
   change or `ddl-auto` will recreate the unconditional one in dev.
2. **Nothing else.** Honouring status on create, the Azure endpoint, the Credentials pill, the FTPS
   port and the clone discovery are all code, not schema.

---

## 7. Validation

| Rule | Client | Server | Where |
|---|---|---|---|
| Connection name present | yes (both apps) | yes | `connection-dialog.ts:91`; `StorageConnectionServiceImpl.java:412-414` |
| Alias present | yes (both apps) | yes | `connection-dialog.ts:92`; `:415-417` |
| Alias matches `[A-Za-z0-9._-]+` | **new app only** | yes | `connection-dialog.ts:30,92` and `clone-dialog.ts:138-141`; `:418-421`. The old app never checked it |
| Alias not already taken (platform-wide) | no | yes | `:166-168` (add), `:264-269` (update), `:208-211` (clone). The message never names the colliding row |
| Alias is not a reserved platform bucket (`etl-bucket`, `etl-avatar`) unless platform admin | **no** | yes | `:139-142`, `:422-424`, `:208-209`. Purely server-side, and a `TENANT_ADMIN` who tries gets the same non-committal "That alias isn't available." |
| Provider present | implicit (select, defaulted) | yes | `:425-427` |
| Bucket / container required for every object store | yes | yes | `connection-dialog.ts:145`; `:441-446`. **The old app did not require it** |
| MinIO endpoint required | yes | yes | `connection-dialog.ts:146`; `:447-449` |
| S3 access key required | yes, always | yes, unless `ambientCredentialsAllowed` | `connection-dialog.ts:156`; `:454-458`. The client asks unconditionally because it cannot tell whether the deployment opted in -- a deliberate over-ask, documented at `connection-dialog.ts:151-155` |
| S3 secret key required on create | yes | yes | `connection-dialog.ts:157`; `:460-462` |
| Azure needs a connection string **or** an account name, on create | yes (cross-field) | yes | `connection-dialog.ts:17-22,158-162`; `:464-469` |
| FTP/FTPS host required | yes | yes | `connection-dialog.ts:147`; `:430-432` |
| FTP/FTPS username required | yes | yes | `connection-dialog.ts:148`; `:433-435` |
| FTP/FTPS password required on create | yes | yes | `connection-dialog.ts:150`; `:436-438` |
| Blank secret on update = keep the stored one | yes (payload key deleted) | yes (conditional write) | `connection-dialog.ts:212-216`; `:575-584` |
| Clone: name and alias present and trimmed | yes | partially -- alias required, name defaults to "<source> (copy)" | `clone-dialog.ts:131-141`; `:203-205,219-220` |
| Rename / retire refused while a Kafka profile binds the alias | **warning only** | refused | `connection-dialog.ts:76-82`; `:282-290` |
| Delete refused while a Kafka profile binds the alias | **warning only** | refused | `storage-connections.ts:178-185`; `:314-317` |
| `sourceId` present on clone | implicit | yes | `:195-197` |
| `storageConnectionId` present on update / delete / test | implicit | yes | `:254-256`, `:305-307`, `:359-361` |

**Client-only rules: none.** Every rule the browser enforces has a server counterpart. The two
gaps run the other way -- **server-only** rules the browser does not mirror: the reserved-alias
guard, and the fact that the Kafka dependency is a refusal rather than a warning. The reserved
alias is defensible (the message must not confirm which names are special); the Kafka one is not,
because the browser already has the list and chooses to phrase it as a consequence.

---

## 8. Security

Four layers, checked one at a time.

### 8.1 Frontend guard

`roleGuard` on `admin/storage` with `minRole: 'TENANT_ADMIN'`, under the shell's `authGuard`.
`AuthService.hasAtLeast` implements `PLATFORM_ADMIN > TENANT_ADMIN > TENANT_USER`, so a platform
admin passes without being named. A `TENANT_USER` is redirected to `/unauthorized`. The nav entry
and the settings-hub card are additionally hidden by `adminOnly`. Old app: `RoleGuard` with an
explicit `['PLATFORM_ADMIN','TENANT_ADMIN']` list. Both are cosmetic -- neither decides anything.

### 8.2 Controller `@PreAuthorize`

One class-level `@PreAuthorize("hasRole('TENANT_ADMIN')")`
(`StorageConnectionRestApi.java:24`), and **no method-level annotation anywhere in the file** --
which matters, because `@PreAuthorize` is not repeatable and a method-level one would silently
replace it. `MethodSecurityConfig.java:27-30` installs
`ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN > ROLE_TENANT_USER`, so `PLATFORM_ADMIN` satisfies it and
`TENANT_USER` does not. This is the layer that actually keeps a tenant user out.

### 8.3 Service rules

Three distinct guards, all in `StorageConnectionServiceImpl`:

- **Ownership.** `isOwnedByCaller` delegates to `TenantOwnership.isOwnedByCaller`
  (`:154-156`, `TenantOwnership.java:35-41`): a platform admin owns everything; everyone else must
  carry a tenant id and match exactly. A caller with **no** tenant owns nothing -- which is the
  case that matters, because a bare `Objects.equals` would have made a tenant-less
  `TENANT_ADMIN` the owner of every platform row, including `etl-avatar` and `etl-bucket`. Applied
  on update (`:272`), delete (`:310`), fetch-by-id (`:350`), test (`:364`), clone (`:199`) and
  discovery-by-id (`:490`), and as a post-filter on the list (`:335`).
- **Reserved aliases.** A non-platform-admin may not claim `etl-bucket` or `etl-avatar`
  (`:139-142`, enforced at `:422-424` on add/update and `:208-209` on clone). Without it a tenant
  admin could mint a connection whose alias every trusted workflow resolves by name, and every
  profile picture and Kafka certificate would land in storage whose credentials that tenant holds.
- **Kafka dependency.** Rename, retire and delete are refused while any profile *visible to the
  caller* binds the alias (`:95-108`, `:285-290`, `:314-317`). Visibility deliberately mirrors
  `fetchAllProfiles`, on the reasoning that a reference the caller cannot see is one that could
  never have resolved.

### 8.4 Hibernate filter

`StorageConnection` declares `tenantFilter` with the **permissive** condition
`(tenant_id = :tenantId or tenant_id is null)` (`StorageConnection.java:44`). Consequences:

- It does **not** apply to `findById`, which is exactly how `updateConnection`, `deleteConnection`,
  `testConnection`, `fetchConnectionById`, `cloneConnection` and `discoverBuckets` reach a row --
  so in every one of those the ownership check is the only thing standing between a tenant admin
  and another tenant's connection.
- On the list query it admits platform rows, so `fetchAllConnections` has to strip them again
  (`:333-335`). The comment at `:328-332` records that before that post-filter, every tenant was
  shown the platform's two connections.
- `TenantFilterHelper.enableIfNeeded` disables the filter entirely for a platform admin **and for
  any caller with a null tenant** (`TenantFilterHelper.java:28-33`) -- another reason the ownership
  check, not the filter, is load-bearing.

### 8.5 Per role

| Role | May |
|---|---|
| `PLATFORM_ADMIN` | Everything, on every tenant's connections and on the platform-owned ones. Is the only role that may claim `etl-bucket` / `etl-avatar` as an alias, and the only one whose new connections and clones are platform-level (`TenantContext.getTenantId()` is null for them). Sees every bucket in Object Browser (`StorageBrowserServiceImpl.java:93`) |
| `TENANT_ADMIN` | Full CRUD, test, clone and discovery **on their own tenant's rows only**. Cannot see, edit, clone or delete a platform-owned row -- clone included, since `cloneConnection` checks `isOwnedByCaller(source)` at `:199`. Cannot claim a reserved alias. Cannot rename, retire or delete a connection one of their Kafka profiles binds to |
| `TENANT_USER` | Nothing on this controller -- 403 from the class-level `@PreAuthorize`. Still browses the resulting buckets through `StorageBrowserRestApi`, which is where the controller's own javadoc says the split belongs (`StorageConnectionRestApi.java:15-18`) |
| A token with a tenant-admin role and **no** tenant claim | Nothing. Owns no row, sees an empty list, and is refused by id -- covered by five tests in `StorageConnectionTenantlessCallerTest.java`, with a platform-admin positive control on the same fixture |

### 8.6 Secret handling

Secrets are write-only across the API. `toDto` (`:591-621`) copies every field except the three
`*_enc` columns and sets `secretKeyConfigured` / `azureConnectionStringConfigured` /
`passwordConfigured` from whether ciphertext is present (`:617-619`). Ciphertext is decrypted only
inside `StorageClientFactory.decrypt` (`:165-176`), and `cloneConnection` moves the ciphertext
across without decrypting it (`:235-238`). The alias-collision message is deliberately
non-committal so that a tenant admin cannot enumerate other tenants' aliases one guess at a time
(`:46-52`, pinned by `StorageConnectionAliasDisclosureTest`).

---

## 9. Error handling

| Failure | What the user sees |
|---|---|
| List load fails (network or 5xx) | New: the `TableShell` error panel with the message and a **Try again** button. Old: a toast and an empty table, indistinguishable from having no connections |
| List returns an `ERROR` envelope | Same error panel (new) / toast (old) |
| Save fails validation on the client | Toast "Check the highlighted fields.", every control marked touched so `Field` renders its message underneath (`connection-dialog.ts:206-210`) |
| Save refused by the server | Toast with the server's own sentence; the dialog stays open with the values intact (`connection-dialog.ts:229-231`) |
| Alias taken or reserved | Toast "That alias isn't available. Choose another." — never naming the colliding connection |
| Rename or retire refused by the Kafka guard | Toast: "This connection can't be renamed: Kafka profile prod-events loads a keystore or truststore from this alias. Point it at another connection first." The dialog stays open |
| Delete refused by the Kafka guard | Toast with the same sentence, after the confirm dialog has already been accepted. The confirm dialog phrased it as a warning, so the refusal reads as a contradiction — see Known issues |
| Test fails | Toast with the root cause -- `rootCause()` unwraps to the innermost exception and falls back to the class name (`:396-403`). The row's pill turns Failed and the full message becomes the pill's `title` |
| Bulk test partly fails | Toast "7 reached their bucket, 2 did not — see Last test." Both numbers always, deliberately (`storage-connections.ts:349-352`) |
| Discovery fails with a permissions error | Inline under the field: "These credentials can't list buckets (s3:ListAllMyBuckets is missing). Type the bucket name instead -- reading a specific bucket may still work." (`:532-537`) |
| Discovery succeeds with nothing to list | The dialog shows the server's "These credentials work, but no buckets were returned." inline; the clone dialog shows it as an **info** toast, not an error (`clone-dialog.ts:109-113`) |
| Discovery from the clone dialog | Always an error toast, "Select a provider first." — see Known issues |
| A stored secret cannot be decrypted | "A stored credential for this connection could not be decrypted -- re-enter it and save again." (`StorageClientFactory.java:173-174`), surfaced through the test or the browse path |
| Kafka dependency lookup fails or is refused | Silently treated as "no dependants" (`kafka-dependents.ts:34-36`). Advisory by design: someone who cannot read the profiles must still be able to save, and the server decides anyway |
| Unhandled server exception | HTTP 500 with the generic `ProcessUtil.ERROR_MESSAGE`; the client falls back to its own sentence ("Could not load connections.", "Delete failed.", "The connection could not be saved.") |

---

## 10. Dependencies

**Upstream (this feature needs them):**

- `authentication-and-access` -- the bearer token, the role, and the tenant claim that
  `TenantContext` is filled from. Nothing here works without it.
- A configured `EncryptionUtil` key. Losing it costs every stored credential.
- `StorageConnectionBootstrap` and the `MINIO_*` environment variables, for the two platform
  connections. Absent them the bootstrap logs a warning and creates nothing
  (`StorageConnectionBootstrap.java:149-155`).

**Downstream (they need this one) --- and this is the wider half:**

| Consumer | How it depends |
|---|---|
| `object-browser` | A connection is what makes a bucket exist. `collectBuckets` builds the picker from Active connections (`StorageBrowserServiceImpl.java:105-112`); `resolveService` resolves every read and write by alias (`:530-548`) |
| `platform-configuration` (Kafka) | A profile loads its truststore/keystore from a storage alias, stored as plain text with no foreign key. This is why rename / retire / delete are refused (`KafkaConnectionProfileServiceImpl.java:476-487`) |
| `content-and-ai-tools` | Document converter and audio transcript read their input from a bucket, and the converter can write its output back |
| `query-and-search-engines` | Executions stream their CSV results into a bucket |
| `reports` | One of the export destinations is a bucket write |
| `own-account-and-notifications` | Avatars live in the single platform bucket `etl-avatar` under `<appUserId>/profile/` |
| `source-jobs` / `job-runs-and-queue` | `job_queue.bucket` is an alias |

The `is_default` flag is a dependency on nothing: no writer, no reader, no UI.

---

## 11. Acceptance criteria

Fixtures assumed throughout: tenant **A** and tenant **B**, each with a `TENANT_ADMIN` and a
`TENANT_USER`; a `PLATFORM_ADMIN`; a platform-owned connection `platform-archive`
(`tenant_id IS NULL`); a tenant-A connection `a-archive`; a tenant-B connection `b-archive`; a
tenant-A Kafka profile `prod-events` whose `sslTruststoreBucket` is `a-archive`.

### Access

1. Tenant A's `TENANT_ADMIN` opens `/admin/storage` and the table lists `a-archive` and no other
   tenant's connection; `b-archive` and `platform-archive` are absent.
2. **Positive control for 1:** the `PLATFORM_ADMIN` opens the same screen and sees `a-archive`,
   `b-archive` and `platform-archive`.
3. Tenant A's `TENANT_USER` navigates to `/admin/storage` and lands on `/unauthorized`; the
   Configuration → Storage Connections nav entry and the settings-hub card are not rendered for
   them.
4. That same `TENANT_USER`, with a valid token, calls `GET /storageConnection.json/fetchAllConnections`
   directly and receives HTTP 403. **Positive control:** the same call from tenant A's
   `TENANT_ADMIN` returns 200 with `a-archive`.
5. A token whose role is `TENANT_ADMIN` but which carries no tenant claim gets an empty list from
   `fetchAllConnections`, an error from `fetchConnectionById(platform-archive)`, and is refused an
   update and a delete of it. **Positive control:** the `PLATFORM_ADMIN` gets `platform-archive`
   back from both reads and can update it.

### Creating

6. Tenant A's admin creates a MinIO connection with name, alias `a-staging`, endpoint and bucket.
   The row appears in the list, `State` = Active, `Last test` = Untested, and `a-staging` becomes
   selectable in Object Browser.
7. Typing `a staging/1` into Alias marks the field invalid in both the new-connection dialog and
   the clone dialog, and no HTTP request is made.
8. Creating a connection with alias `b-archive` is refused with "That alias isn't available.
   Choose another.", and the message contains neither the word "exists" nor any reference to
   tenant B.
9. Tenant A's admin creating a connection with alias `etl-bucket` (or `etl-avatar`) is refused with
   the same non-committal message. **Positive control:** the `PLATFORM_ADMIN` creating a connection
   with that alias, on an installation where no row holds it, succeeds.
10. Choosing provider S3 and leaving Access key blank marks that field required in the dialog and
    blocks submission; forcing the request through anyway returns "an access key is required for an
    S3 connection."
11. Choosing Azure and supplying neither a connection string nor an account name is refused, with
    the message rendered under the Connection string field rather than only as a toast.
12. Choosing MinIO and leaving Endpoint blank is refused; choosing FTP and leaving Host, Username
    or Password blank is refused, each with the field marked.
13. Creating a connection with Status set to **Inactive** produces a row whose `State` reads
    Inactive, and that alias does not appear in Object Browser's bucket picker. *(Fails today --
    see Known issues 12.1.)*

### Editing

14. Editing `a-archive`'s description with the Secret key box left blank saves successfully, the
    Credentials pill still reads "Stored", and a subsequent Test still passes -- i.e. the stored
    secret was not overwritten with an empty string.
15. Editing an Azure connection that has a custom endpoint and saving without touching it leaves
    the endpoint unchanged in the database; and the form offers an Endpoint field through which
    that value can be changed. *(The second half fails today -- Known issues 12.3.)*
16. Renaming `a-archive`'s alias is refused with a message naming `prod-events`, and the alias in
    the database is unchanged. **Positive control:** renaming a tenant-A connection that no profile
    binds to succeeds.
17. Switching `a-archive` to Inactive is refused, naming `prod-events`. **Positive control:**
    switching an unbound tenant-A connection to Inactive succeeds, and that alias then disappears
    from Object Browser's bucket picker.
18. Changing only `a-archive`'s endpoint succeeds despite `prod-events` binding it, and the cached
    storage client is evicted so the next browse uses the new endpoint.
19. Before the confirm button is offered, both the delete confirmation and the Inactive path state
    that the change will be **refused** while `prod-events` binds the alias, rather than describing
    a consequence. *(Fails today -- Known issues 12.5.)*
20. Tenant B's admin issuing `updateConnection` for `a-archive`'s id gets "Storage connection not
    found with <id>." and nothing on the row changes. **Positive control:** tenant A's admin
    updating the same row succeeds.

### Testing

21. Testing a connection whose bucket is reachable produces a success toast, turns the Last test
    pill to OK, and writes a `lastTestedAt` that is rendered under the pill.
22. Testing a connection whose credentials are wrong produces an error toast, turns the pill to
    Failed, and the pill's tooltip carries the root-cause message rather than a wrapper exception's
    class name.
23. Ticking three rows, then typing a search term that leaves only one on screen, then pressing
    Test selected runs **three** tests, reports both a passed and a failed count if any failed, and
    clears the selection afterwards.
24. Deleting a row that was ticked and reloading leaves the bulk bar counting only the rows that
    still exist.
25. Running a test on `a-archive` does not change the `Updated by` column. *(Fails today -- Known
    issues 12.6.)*

### Discovery

26. In the new-connection dialog, with valid MinIO credentials and an endpoint, pressing Discover
    replaces the Bucket text input with a select listing the buckets, and a "Type instead" button
    returns to free text.
27. With credentials that can read one bucket but cannot list, Discover shows, inline under the
    field, the sentence naming `s3:ListAllMyBuckets`, and the field remains typable.
28. In the Clone dialog, "List buckets on this server" lists the **source connection's** buckets
    without the operator re-entering any credential. *(Fails today -- Known issues 12.2.)*

### Cloning

29. Tenant A's admin clones `a-archive` into name "A archive (copy)" and alias `a-archive-copy`
    with a different bucket. The copy appears Active and Untested, and passes its own Test without
    any secret having been typed.
30. Cloning into an alias already held by any connection, deleted ones included, is refused with
    "That alias isn't available."
31. Tenant A's admin attempting to clone `platform-archive` is refused with "Storage connection not
    found with <id>." **Positive control:** the `PLATFORM_ADMIN` clones it successfully and the
    copy's `tenant_id` is null.

### Deleting

32. Deleting `a-archive` is refused, naming `prod-events`, and the row's status in the database is
    still `Active`.
33. Deleting a tenant-A connection that nothing binds removes it from the list and from Object
    Browser's bucket picker, and no object is removed from the storage itself.
34. After 33, creating a new connection reusing that same alias succeeds. *(Fails today -- Known
    issues 12.4.)*

### Display

35. An Azure connection credentialled by a connection string only shows Credentials = "Stored".
    *(Fails today -- Known issues 12.7.)*
36. The Provider column and the provider filter read "AWS S3" / "Azure Blob" / "MinIO" / "FTP" /
    "FTPS", not the raw enum. *(Fails today -- Known issues 12.9.)*
37. Selecting FTPS on a new connection sets Port to 21 with Implicit TLS unticked; ticking Implicit
    TLS moves Port to 990, and unticking it moves it back to 21. A port the operator typed by hand
    is never overwritten. *(Fails today -- Known issues 12.8.)*

### States

38. With the API returning a 500, the list shows the error panel with a Try again button, and
    pressing it re-issues the request; with the API returning an empty list the screen shows "No
    connections configured yet." and offers a New connection action from within the empty panel;
    with a search term matching nothing it shows "No connections match the filters."
39. Turning "Only mine" on when it is the only active filter renders a Clear control, and pressing
    it turns "Only mine" back off. *(Fails today -- Known issues 12.10.)*
40. The screen renders correctly in both themes: the four stat tiles, the OK / Failed / Untested
    pills, the Stored / Not stored pills and the bulk sub-bar are all legible in light and dark,
    and switching theme does not require a reload.
41. Switching to Cards and navigating away and back keeps Cards selected; the same choice on
    another list screen is unaffected.

---

## 12. Known issues

Each of these exists in the code today. None is fixed here.

### 12.1 The Status control on the create dialog does nothing

`connection-dialog.html:147-153` renders the Status select unconditionally, create included, and
`connection-dialog.ts:111` seeds it into the payload. `addConnection` sets
`connection.setStatus(Status.Active)` at `StorageConnectionServiceImpl.java:172`, after `applyDto`,
and `applyDto` never touches status (`:542-585`). Choosing Inactive on create silently produces an
Active connection. The old app avoided this by rendering the control only when editing
(`storage-connection.component.html:191-199`).

### 12.2 The Clone dialog's bucket discovery can never succeed

`clone-dialog.ts:99-101` posts `{ storageConnectionId }` and nothing else.
`discoverBuckets` refuses a DTO with no provider on its first line --
`if (isNull(dto) || isNull(dto.getProvider())) return new ResponseDto(ERROR, "Select a provider
first.")` (`StorageConnectionServiceImpl.java:475-477`) -- **before** it looks the saved row up at
`:486-489`. So every press of "List buckets on this server" produces the toast "Select a provider
first." on a dialog that offers no provider control.

It is worse than a missing field. Even with a provider supplied, the probe takes `endpoint`,
`region` and `accessKey` from the DTO alone (`:504-507`) and inherits only the tenant, the Azure
account name and the three ciphertext columns from the saved row (`:494-499`) -- so a MinIO source
would fail on a missing endpoint and an S3 source on a missing access key. The endpoint accepts a
saved id but does not actually support being called with only one.

`clone-dialog.spec.ts:81-87` passes because its stub returns `{status:'SUCCESS', data: []}`,
exercising the empty-listing branch and never the payload the server actually receives.

### 12.3 There is no Azure endpoint field

`connection-dialog.html:61-77` renders Endpoint for S3 and MinIO only. The old form rendered it for
all three object stores (`storage-connection.component.html:255-261`), and the server uses it:
`blobServiceClient` prefers `connection.getEndpoint()` and only falls back to
`https://<account>.blob.core.windows.net` when it is blank (`StorageClientFactory.java:224-228`).
An Azure Government, Azure China or private-endpoint container cannot be configured from the new
UI. The stored value survives an edit -- the control exists in the form group at
`connection-dialog.ts:96` and `getRawValue()` sends it -- so nothing is wiped; it simply cannot be
set or changed.

### 12.4 A deleted connection's alias is burned permanently

`deleteConnection` soft-deletes by setting `Status.Delete` (`:318`) and leaves the row in place.
`addConnection` rejects the alias if `findByAlias` returns **anything**, deleted rows included
(`:166-168`); `cloneConnection` does the same (`:208`); and `uq_storage_connection_alias`
(`StorageConnection.java:31-33`) is unconditional, so even removing the check would produce a
constraint violation at flush. Delete `prod-archive` and no connection can ever be called
`prod-archive` again -- while every job, task and export still pointing at that alias remains
unfixable through the UI.

### 12.5 The delete and retire confirmations describe a consequence the server will not let happen

`storage-connections.ts:179-185` builds the confirm body as "…will be removed. Jobs and tasks
pointing at "x" will stop resolving." plus, when applicable, "Kafka profiles a, b load a keystore
or truststore from this alias." -- and then offers a red Delete button. The server refuses outright
(`:314-317`). The Inactive warning in the dialog is worse: `connection-dialog.ts:79-81` appends
"An Inactive connection is not resolved, so their next publish will fail", which asserts the save
will go through, when `:285-290` refuses it. In both cases the operator is invited to make a change
that cannot be made, and finds out from a toast afterwards.

### 12.6 Testing a connection rewrites its "Updated by"

`testConnection` records its result by calling `save` on the managed entity (`:387-390`), which
fires `AuditListener.onUpdate` and stamps `updated_by` with the tester
(`AuditListener.java:41-51`). The new list surfaces `updatedByName` as a column
(`storage-connections.html:224-226`), so pressing Test -- or Test selected across twenty rows --
silently makes the tester look like the last editor of every one of them. The old app never showed
the column, so the behaviour existed but was invisible.

### 12.7 An Azure connection credentialled only by a connection string reads "Not stored"

The new list's row interface omits `azureConnectionStringConfigured`
(`storage-connections.ts:44-45`) and both the table cell and the card check only
`secretKeyConfigured || passwordConfigured` (`storage-connections.html:203`, `:141`). The DTO
carries the third flag (`StorageConnectionDto.java:43`, set at
`StorageConnectionServiceImpl.java:618`) and the old table used all three
(`storage-connection.component.html:98-99`). The edit dialog gets it right --
`hasStoredSecret()` checks all three (`connection-dialog.ts:85-87`) -- so the list and the dialog
disagree about the same connection.

### 12.8 A new FTPS connection defaults to explicit TLS on the implicit port

`connection-dialog.ts:121` sets Port to 990 when FTPS is selected, while `implicitTls` is
initialised to `false` (`:110`) and the Implicit TLS checkbox has no change handler
(`connection-dialog.html:104-108`). `FtpObjectStorageServiceImpl.java:69` builds the client from
`implicitTls` and `:74-76` uses the stored port verbatim, so the default combination attempts
explicit AUTH TLS against port 990. The old app produced 21/990 correctly from the flag on provider
change and kept them in step when the flag was toggled
(`storage-connection.component.ts:216-229`).

### 12.9 The provider is displayed as a raw enum

`storage-connections.html:198` prints `{{ c.provider }}` and `:77` fills the filter with the same
raw values. The old table ran it through `providerLabel()`
(`storage-connection.component.ts:147-150`) against the labels in
`_models/storage-connection.model.ts:3-9`. The new dialog has the labels
(`connection-dialog.ts:32-38`) but the list does not import them.

### 12.10 Clear does not clear "Only mine"

`clearFilters()` resets search and provider only (`storage-connections.ts:246-249`), and the button
is rendered only when one of those two is set (`storage-connections.html:86-88`) -- yet
`isFiltered()` counts `onlyMine()` (`:96-97`), so the "these totals cover all N" caveat appears
with no control to dismiss it. Related and cosmetic: `MineFilter` exposes a `hidden` count that
renders "(N hidden)" on the button, and **no screen in the app binds it** -- all eleven call sites
pass `[(only)]` alone -- so that count is permanently zero. That one is cross-cutting, not this
feature's.

### 12.11 The Hibernate filter is the wrong shape for this entity, and the service compensates

`StorageConnection.java:44` uses the shared-catalogue condition
`(tenant_id = :tenantId or tenant_id is null)`, which publishes platform-owned rows to every
tenant. That is deliberate -- the avatar and Kafka workflows resolve `etl-avatar` and `etl-bucket`
by alias -- but it means the filter alone leaks the platform's connections into every tenant's
listing, and `fetchAllConnections` has to post-filter with `isOwnedByCaller` to prevent it
(`:328-335`, whose comment records that this is exactly what used to happen). Any future read path
on this repository that forgets the post-filter reintroduces the leak silently. Also flagged at
`.ai/discovery/backend.md:1129-1131` and `.ai/discovery/database.md:430-431`.

### 12.12 `is_default` is dead

`StorageConnection.java:147-148` declares a not-null `is_default` column, `applyDto` writes it if
present (`:569-571`), `toDto` returns it (`:610`), and **nothing** in either frontend sets or reads
it. Compare `KafkaConnectionProfile`, which has `setAsDefault` / `clearDefault` endpoints and a UI.
Either it is a half-built feature or a copied field.

### 12.13 `fetchConnectionById` is dead in both clients

Declared in the old service (`scheduler1/src/app/_services/storage-connection.service.ts:31-34`),
called by no old screen, and absent from `scheduler1/next/src` entirely. Already listed as
undecided backend surface in `.ai/discovery/features.md:76` and `frontend-old.md:913`.

### 12.14 The list load costs an avoidable second query

`fetchAllConnections` maps the rows it already holds into DTOs and then calls
`userNameResolver.attachToDtos(dtos, repository, ...)` (`:337-338`), which re-fetches those same
entities by id (`UserNameResolver.java:99-101`) purely to read `createdBy` / `updatedBy` off them.
`attachNames(entities)` on the list already in hand would do. Minor, and only worth mentioning
because it is a one-line change.

---

## 13. Missing functionality

Absent from both apps, or absent from the new one, and worth an explicit decision.

**A default connection.** `is_default` exists on the table and in the DTO and has no way to be set.
Kafka profiles have exactly this concept with endpoints and a UI behind it. If a default storage
connection would be useful -- as the fallback bucket for a job with none named -- it needs two
endpoints and a row action; if not, the column should go. Small either way.

**Anything that reads the estate.** There is no way to answer "what is pointing at this alias?"
before deleting it, beyond the Kafka profiles the dialog already names. A job's bucket, a task's
input folder, a query schedule's output and a converter task's storage key are all aliases, and
none of them is consulted. The delete confirmation says "Jobs and tasks pointing at x will stop
resolving" without ever having looked. Doing this properly means a dependants endpoint over
`source_job`, `source_task`, `query_schedule` and `document_converter_task` -- medium, and the
biggest genuine gap in the feature.

**Restore a soft-deleted connection.** Rows sit in the table with `status = Delete` forever,
holding their alias, with nothing that can see or revive them. Either a restore path or a hard
delete would resolve both this and Known issue 12.4.

**A per-row "copy alias".** The alias is the string that has to be typed into a job, a task, a
Kafka profile and a query schedule, and it is rendered as unselectable-looking mono text in a table
cell. A copy button is trivial and would be used constantly.

**Bulk anything except test.** The new app added multi-select and then attached one action to it.
Bulk delete and bulk retire are the obvious companions -- both would have to honour the Kafka
guard per row and report per-row outcomes, which is exactly what `testSelected` already does.

**Test on save.** Both apps let an operator save a connection and walk away without ever finding
out whether it works; the row sits at Untested until someone presses the button. A "test before
saving" affordance in the dialog would use `testConnection`'s existing uncached path.

**Any old-app test coverage.** `scheduler1/src` has no spec files at all. This is not specific to
storage connections, but it means the old behaviour this document cites as the baseline is
established only by reading the code.

**Server-side tests for five of the eight operations.** `addConnection`, `cloneConnection`,
`testConnection`, `discoverBuckets` and `fetchAllConnections`'s post-filter have no test. The
reserved-alias guard -- arguably the sharpest security rule in the service, since claiming
`etl-avatar` would redirect every user's profile picture -- is exercised by nothing.
`PlatformBucketNamedGuardTest` tests `StorageBrowserServiceImpl`, not this service.
