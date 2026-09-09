# Grooming -- Tenants and Users

Feature 16 in `.ai/discovery/features.md`. Status **migrated**: old `tenants` → new `admin/tenants`,
old `users` → new `admin/users`.

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Purpose

Two screens that answer one question: **who exists here, and what are they allowed to touch?**

A **tenant** is an organisation. It is the box everything else in the product lives inside -- jobs,
tasks, buckets, Kafka profiles, agents, forms all belong to exactly one, and nothing crosses between
them. Someone signs a new customer, and the platform operator makes them a tenant so their work has
somewhere to be. Later that customer stops paying, and the operator suspends the tenant: everybody in
it stops being able to sign in, and not one row of their data is touched. The old screen said this
out loud in a sentence under the toolbar (`scheduler1/src/app/_component/tenants/tenants.component.html:69-73`).

A **user** is a person plus the answer to "how much of this may they change?". Three roles, ranked:
a `TENANT_USER` runs and watches work; a `TENANT_ADMIN` also configures the workspace and staffs it;
a `PLATFORM_ADMIN` operates across every tenant and belongs to none. The screen exists so an
administrator can add the person who joined on Monday, take away the account of the one who left on
Friday, and hand back a password to the one who lost theirs -- without a database client.

The two screens are joined by one link. A tenant card offers **Users**, which opens the user list
already narrowed to that tenant (`tenants.ts:217-219` → `/admin/users?tenantId=`). That is the whole
of the navigation between them, in both apps.

What this feature is **not**: it is not the place a person edits themselves. Own name, own phone, own
picture and own password live on `/profile` and go through a different set of endpoints that derive
the subject from the token rather than from the request body -- feature 18,
`own-account-and-notifications`.

---

## 2. Existing behaviour

### 2.1 Where each app puts it

| | Old app | New app |
|---|---|---|
| Tenant route | `tenants` (`scheduler1/src/app/app.routing.ts:169-175`) | `admin/tenants` (`scheduler1/next/src/app/app.routes.ts:144-149`) |
| Tenant guard | `AuthGuard` + `RoleGuard`, `data.roles = ['PLATFORM_ADMIN']` | `roleGuard` with `data.minRole = 'PLATFORM_ADMIN'`, under the shell's `authGuard` + `passwordChangeGuard` |
| User route | `users` (`app.routing.ts:176-182`) | `admin/users` (`app.routes.ts:138-143`) |
| User guard | `AuthGuard` + `RoleGuard`, `data.roles = ['PLATFORM_ADMIN','TENANT_ADMIN']` | `roleGuard` with `data.minRole = 'TENANT_ADMIN'` |
| Guard semantics | Exact membership of a list (`_helpers/role.guard.ts:21-24`) | Rank comparison, so `TENANT_ADMIN` admits a platform admin too (`core/auth/auth.guard.ts:33-42`, `core/auth/auth.models.ts:10-14`) |
| Components | `TenantsComponent` 206 TS + 179 HTML; `UsersComponent` 251 TS + 235 HTML (`scheduler1/src/app/_component/tenants/`, `.../users/`) | `Tenants` 292 + 234, `TenantDialog` 122; `Users` 448 + 457, `UserDialog` 161 + 97, plus a 100-line spec (`scheduler1/next/src/app/features/admin/tenants/`, `.../users/`) |
| Nav | Administration dropdown, `*ngIf` on the role string (`app.component.html:57-62`) | Administration group, `adminOnly` on Users and `platformOnly` on Tenants (`features/shell/shell.ts:122-136`, filtered at `:140-151`) |
| Second entry point | none | Settings hub cards (`features/settings/hub/settings-hub.ts:51-54`) |
| Service layer | `TenantService`, `AppUserService` (`scheduler1/src/app/_services/`) | No service class -- each component injects `HttpClient` directly |

### 2.2 Tenants -- the list

**Old** (`tenants.component.html`, `tenants.component.ts`). Five KPI tiles across the top: Tenants
(the *filtered* count), Users, Brokers, Buckets, Sources -- where Sources is task types + tasks +
jobs added together (`tenants.component.html:7-43`, sums at `tenants.component.ts:57-89`). A toolbar
with a free-text box, a Status dropdown offering only `Active` and `Suspended`
(`tenants.component.ts:24`), a Clear button disabled when nothing is set, Refresh and Add Tenant
(`:45-68`). Then a paragraph explaining what a tenant is and what suspending does (`:69-73`).

The body is a responsive grid of cards, four to a row at `lg` (`:75-129`). Each card carries the
name, the code in a `<code>`, the creation date, a status pill, and six stat chips -- users, Kafka
profiles, buckets, task types, tasks, jobs (`:93-100`). Beneath them: a **View Users** link to
`/users?tenantId=<id>`, and a three-button group for Edit, Suspend/Reactivate and Delete
(`:102-120`). `Delete` rows are hidden client-side as well as server-side
(`tenants.component.ts:48-51`). When nothing matches, one full-width panel says
`No tenants match your search.` (`:124-128`) -- the same sentence whether a filter is on or the
installation genuinely has no tenants.

Search runs the whole row through `SearchFilterPipe` (`scheduler1/src/app/_helpers/search-filter.ts`),
which is considerably more than a substring match: it tokenises on whitespace, supports quoted
phrases, field paths (`tenantCode:acme`), and negation with a leading `-` (`:40-67`), and matches
against every scalar anywhere in the object (`:83-102`). Typing `suspended` matched on the status
field; typing `-acme` excluded a tenant by name.

**New** (`tenants.html`, `tenants.ts`). Four stat tiles: Tenants (with "N active" underneath), Users,
Jobs (with "N tasks" underneath), and **Unused** -- tenants whose six counts total zero
(`tenants.html:19-28`, computed at `tenants.ts:157-170`). Everything then sits inside `TableShell`
(`shared/ui/data-table.ts`), which supplies the heading, the `(shown of total)` counter, and the
loading / error / empty states the old screen did not have.

The toolbar (`tenants.html:35-67`) is: a table/cards view toggle persisted under key `tenants`, a
status filter offering Active / Suspended / Inactive, a sort select (name, users, jobs, created) with
a direction button, a search box, an **Only mine** toggle, and a Clear button rendered only when
something is set. Cards are the default view (`tenants.ts:54`, with the reason in the comment above
it).

The table view (`tenants.html:73-141`) has thirteen columns: Tenant, Code, all six resource counts,
Created, **Created by**, **Updated by**, State, and a kebab. The kebab offers Users (disabled at zero),
Edit, Suspend/Reactivate and Delete (`:116-136`).

The cards view (`:143-231`) shows three headline metrics rather than six -- users, jobs, tasks -- with
the other three folded into a sentence underneath (`quietSummary`, `tenants.ts:119-133`), and a bar
showing this tenant's share of the largest workspace by headcount (`shareOf`, `:110-116`). The
reasoning for dropping from six tiles to three is written into the source at `tenants.ts:76-86`.

Search matches a plain lowercase substring of `tenantName` + `tenantCode` only (`tenants.ts:142-151`).

### 2.3 Tenants -- create, edit, and the three status actions

**Old.** One Bootstrap modal for both create and edit (`tenants.component.html:131-162`). Create asks
for Tenant Name and Tenant Code, both `Validators.required` (`tenants.component.ts:117-120`). Edit
prefills them and **disables the code** (`:130`), with the note "Code can't be changed once set."
The form is read with `getRawValue()` so the disabled code still travels (`:140`).

Suspend/Reactivate is a single icon button with **no confirmation at all** -- one click writes the new
status (`tenants.component.html:111-114` → `toggleSuspend`, `tenants.component.ts:160-177`). It flips
`Suspended → Active`, and anything else `→ Suspended`.

Delete opens a confirm modal whose body reads "Its users and data are not removed, but the tenant will
no longer be usable", and whose footer holds exactly one button, `Yes, Delete`
(`tenants.component.html:164-179`). There is no Cancel; the only way out is the `×`. It writes
status `Delete` (`tenants.component.ts:188`).

**New.** A CDK dialog (`tenant-dialog.ts`) with three fields: Tenant name, Tenant code, and **Status**
(Active / Suspended / Inactive). While creating, the code is slugged from the name as you type until
you edit the code yourself (`:69-90`). The code is validated against `^[a-z0-9][a-z0-9._-]*$`
(`:65`) and is **editable on edit** -- the old app's lock is gone, replaced by a hint saying
"Changing the code does not move any data, but anything referring to the old code stops matching"
(`:30-32`).

Both status actions are now confirmed through the shared `confirmWith` (`shared/ui/confirm.ts:34-39`),
and both confirmations name what the tenant owns. Suspend says "Users in X will not be able to sign
in" and, when there is anything to keep, lists it (`tenants.ts:221-237`). Delete says how many
resources will become unreachable and suggests suspending instead (`:239-251`). Both offer Cancel.

`toggleSuspend` flips `Active → Suspended` and anything else `→ Active` -- the mirror image of the old
rule, which matters only for a tenant sitting at `Inactive`.

### 2.4 Users -- the list

**Old** (`users.component.html`, `users.component.ts`). No KPI tiles. When `?tenantId` is present a
banner says "Viewing users for X" with a **Show All Tenants** button (`:9-17`); the id is read once in
`ngOnInit` from the route snapshot (`users.component.ts:56-57`). A breadcrumb above it offers
Home / Tenants / Users, with the Tenants crumb shown only while focused (`:1-7`).

The toolbar (`:19-56`) has search, a Tenant dropdown rendered only for a platform admin and populated
from `listTenants` (fetched only for that role, `users.component.ts:58-64`), a Role dropdown listing
the three roles as literals (`users.component.ts:28`), a Status dropdown of Active / Inactive
(`:30`), Clear, Refresh and Add User. Underneath, a one-line explanation of the caller's own scope
that changes with the role (`:57-60`).

One table, seven columns: Full Name, Username, Tenant (platform admin only), Role, Status, Last Login,
Action (`:64-74`). The Tenant cell carries a red `Tenant deleted` pill when `tenantActive === false`,
with a tooltip explaining that the account still reads Active but cannot sign in (`:79-83`, echoed on
the status pill at `:96-98`). Row actions are Edit, an activate/deactivate toggle, and a kebab holding
Reset Password and Delete (`:101-134`). A single empty row says `No users match your search.`
(`:136-140`).

Search is the same `SearchFilterPipe` as the tenants screen, so it reached every field on the row --
role, status, tenant name, last-login timestamp -- and supported field paths and negation.

**New** (`users.html`, `users.ts`). Four stat tiles: Users, Active, Admins, Never signed in
(`users.html:31-40`), all computed over the tenant-focused subset (`users.ts:169-181`). The focus
banner is kept and is now driven by a `queryParamMap` subscription rather than a snapshot
(`users.ts:183-191`), so a change of query string re-narrows without a reload; **Show all tenants**
navigates the parameter away (`:193-195`).

Toolbar (`users.html:47-83`): view toggle (`users` key, table by default), a Role filter whose options
are derived from the roles actually present (`users.ts:107-108`), a Tenant filter rendered only for a
platform admin and only when more than one tenant has users (`users.html:57`, options at
`users.ts:117-124`), a Status filter, search, Only mine, Clear. Every control resets the pager.

The table (`users.html:267-451`) has eight columns: Person (avatar + name + email + phone in one
cell), Role (+ job title beneath), Tenant, Last sign-in, **Workload**, Added (+ "by X" and "edited by
Y"), State, Actions. Four headers are click-to-sort. The Tenant cell shows a `tenant off` pill when
`tenantActive === false` (`:344-348`).

The cards view (`:85-265`) draws a coloured rule keyed to privilege (`roleAccent`, `users.ts:434-436`),
a status ring around the avatar (`statusRing`, `:445-447`), copy buttons for the address and the
number (`copyContact`, `:413-425`), the same workload figures as tiles, and the same four row actions.

Workload comes from `dashboard.json/userStatistics`, fetched once alongside the list and keyed by id
(`users.ts:221-233`). Its failure is swallowed on purpose -- the list is usable without it (`:230-231`).

Below the table, a client-side pager (`shared/ui/pager.ts`, default page size 50).

### 2.5 Users -- the dialog, reset password, status and delete

**Old.** One modal for create and edit (`users.component.html:145-194`). Fields: Full Name
(required), Username (an email, `Validators.email`, **disabled on edit** at
`users.component.ts:142`), Password (create only, required, `minLength(8)`, `:129`), Role, and -- for
a platform admin whose chosen role is not `PLATFORM_ADMIN` -- a Tenant select (`:179-185`). The Role
select offers all three roles and merely **disables** the `PLATFORM_ADMIN` option for a non-platform
admin (`:176`), leaving `TENANT_ADMIN` selectable by a tenant admin -- which the server then refuses.
There is no Status field. On edit the Tenant select is *enabled* (`users.component.ts:144`), so a
platform admin could move somebody between workspaces.

Reset Password is its own modal with a single `type="password"` field, `minLength(8)`, and the hint
"At least 8 characters. The user isn't notified automatically -- share the new password with them
yourself." (`users.component.html:196-218`).

The activate/deactivate toggle writes immediately with no confirmation
(`users.component.ts:174-191`). Delete opens a confirm modal, again with only a `Yes, Delete` button
(`:220-234`), and writes status `Delete`.

**New.** A CDK dialog (`user-dialog.ts`, `user-dialog.html`) with Full name, **Position** (a job title,
with a fifteen-entry datalist), **Phone** (a country picker plus a national number producing E.164,
`shared/ui/phone-input.ts`), Email, Password, Role, Tenant and **Status**.

The differences that matter:

- Password is **optional in both directions** (`user-dialog.ts:97`). Left blank on create, the server
  generates one and emails it (`AppUserServiceImpl:186-187`, mail at `:203-217`). Left blank on edit,
  nothing changes -- the key is deleted from the payload before it is sent (`user-dialog.ts:133`).
- The Role picker offers only what this administrator can actually grant: everything for a platform
  admin, and `TENANT_USER` plus whatever the edited row already carries for a tenant admin
  (`user-dialog.ts:57-63`). This is the console agreeing with the server rather than discovering the
  refusal after the form is filled in.
- Email is **not disabled on edit**.
- Tenant is disabled whenever the edited row already has one (`:103-104`), with a hint saying the
  workspace is fixed once the account exists.

Reset Password reuses the generic `PromptDialog` (`features/objects/dialogs/prompt-dialog.ts`) with a
title naming the person, an eight-character check in the caller before the request goes out
(`users.ts:353-357`), and the hint "They will need this to sign in. It is stored hashed and cannot be
read back."

Activate/deactivate and delete are both confirmed through `confirmWith` (`users.ts:298-322`), with
bodies that say what survives. Both are disabled on your own row (`users.html:248-249, 432-433,
439-440`), and the whole action menu is replaced by a padlock and the sentence "Only a Platform Admin
can manage another Tenant Admin." on any row this administrator cannot act on
(`canManage`, `users.ts:291-296`; rendered at `users.html:411-415` and `:231-235`).

### 2.6 What the server does

**`TenantRestApi`** (`process/src/main/java/process/api/TenantRestApi.java`). Four endpoints, one
class-level `@PreAuthorize("hasRole('PLATFORM_ADMIN')")` at `:20`, and **no method-level override** --
so all four are platform admin, and the not-repeatable rule never bites here.

`TenantServiceImpl` (`process/src/main/java/process/model/service/impl/TenantServiceImpl.java`):

- `listTenants` (`:65-70`) reads every tenant whose status is not `Delete`, newest first, decorates
  each with six counts by issuing six `countBy…` queries per row (`mapToDtoWithStats`, `:72-82`), then
  attaches author names in one further pass (`UserNameResolver.attachToDtos`, `:68`).
- `addTenant` (`:86-104`) requires a name and a code, normalises the code, refuses a duplicate, and
  defaults the status to `Active`.
- `updateTenant` (`:107-132`) requires id, name and code; refuses a code owned by another tenant; and
  applies the status only when one is supplied (`:127-129`). **The code is writable.**
- `changeTenantStatus` (`:135-149`) sets whatever `TenantStatus` it is handed, `Delete` included.
- `normalizeCode` (`:151-153`) is `trim().toLowerCase().replaceAll("[^a-z0-9-]", "-")`.

There is no tenant-scoping rule in this service, and correctly so: a tenant row is platform-owned by
nature, and the controller annotation is the whole of the gate.

**`AppUserRestApi`** (`process/src/main/java/process/api/AppUserRestApi.java`). Class-level
`@PreAuthorize("hasRole('TENANT_ADMIN')")` at `:24`. Five endpoints inherit it -- `listUsers`,
`addUser`, `updateUser`, `changeUserStatus`, `resetPassword`. Five more override it down to
`TENANT_USER` (`:92, :111, :131, :147, :163`) because they are the profile endpoints and derive their
subject from the token. The override is deliberate and is explained in the source at `:86-91`.

`AppUserServiceImpl` (`process/src/main/java/process/model/service/impl/AppUserServiceImpl.java`):

- `listUsers` (`:127-137`). A platform admin gets `findAll()` filtered in memory; anybody else gets
  `findByTenantIdAndStatusNotOrderByAppUserIdDesc(TenantContext.getTenantId(), Delete)`. Note that
  **peer administrators are returned** to a tenant admin -- which is why the console needs `canManage`.
- `addUser` (`:141-218`). Requires username, full name and role. Normalises the phone. Refuses a
  non-platform actor granting `PLATFORM_ADMIN` (`:156-158`) or anything above `TENANT_USER`
  (`:162-164`). Resolves the target tenant: null for a platform admin being created, the named tenant
  when the actor is a platform admin, otherwise **the actor's own tenant, whatever the request said**
  (`:165-176`). Refuses a duplicate username. Generates a password when none is supplied and sets
  `mustChangePassword` accordingly (`:186-199`). **Status is forced to `Active`** (`:198`). Sends a
  welcome email, and when the mail fails says so in a `SUCCESS` response with words the administrator
  has to read (`:203-217`).
- `updateUser` (`:250-315`). `scopedFind` first. Refuses changing your own role (`:275-278`), refuses
  a tenant admin granting `PLATFORM_ADMIN` or `TENANT_ADMIN` unless resubmitting the role already held
  (`:279-289`). Computes the effective tenant, refusing a non-platform role with no tenant (`:301-303`).
  Then writes exactly five fields: role, phone, tenant, full name, position (`:308-312`). **Username
  and status are never written.**
- `changeUserStatus` (`:318-335`). `scopedFind`, then refuses any non-`Active` status on your own row
  (`:328-330`) -- which covers both deactivating and deleting yourself.
- `resetPassword` (`:338-359`). `scopedFind`, an eight-character check via `validateNewPassword`
  (`:368-373`), then a re-hash and `mustChangePassword = true` (`:353-356`). **No mail is sent.**
- `scopedFind` (`:375-398`) is the ownership rule for the four write paths: a `Delete` row is
  unreachable; a platform admin reaches everything; anybody else must share the tenant *and* the
  target must be a `TENANT_USER` or the caller's own row.
- `refusalFor` (`:408-421`) chooses the wording: "Only a Platform Admin can manage another Tenant
  Admin." for a peer in your own tenant, and a flat "User not found." for everything else, so a
  refusal cannot be used to learn who exists elsewhere.

**`dashboard.json/userStatistics`** (`api/DashboardRestApi.java:43-53`) backs the Workload column. The
class requires `TENANT_USER` (`:19`) and this method does **not** override it. `DashboardServiceImpl`
`:68-94` maps thirteen columns; the SQL is `QueryService.userStatistics` (`:273-292`), scoped by
`tenantClause("u")` (`:212-217`), which returns an empty string for a platform admin *and* for any
caller with no tenant in context.

### 2.7 What the rewrite changed -- behaviour by behaviour

The status is `migrated`, and no whole capability vanished. These are the differences, each verified
against both sources.

| # | Behaviour | Old | New | Verdict |
|---|---|---|---|---|
| 1 | Roll-up totals for Kafka profiles, buckets and task types | Three of the five KPI tiles (`tenants.component.html:22-42`) | Not totalled anywhere; per-tenant figures survive in the table view | **Lost** (minor) |
| 2 | All six resource counts visible in the default view | Six chips per card (`tenants.component.html:93-100`) | Cards show three; the table shows six, but cards are the default (`tenants.ts:54`) | **Changed**, recoverable in one click |
| 3 | Explanatory copy about what a tenant is and what suspending does | A paragraph under the toolbar (`tenants.component.html:69-73`) | A shorter page subtitle (`tenants.html:5-7`); the suspend consequence moved into the confirmation | **Changed**, net neutral |
| 4 | Tenant search over the whole row, with field paths and negation | `SearchFilterPipe` (`_helpers/search-filter.ts:40-102`) | Substring over name + code (`tenants.ts:142-151`) | **Lost** |
| 5 | User search over the whole row, with field paths and negation | Same pipe | Substring over email, name, position, phone, tenant name (`users.ts:153-158`) | **Lost** for role, status and date; **gained** for phone and position |
| 6 | Role filter offering all three roles regardless of data | `roleOptions` literal (`users.component.ts:28`) | Derived from rows present (`users.ts:107-108`) | **Changed**, no data hidden |
| 7 | Tenant filter always present for a platform admin | `*ngIf="isPlatformAdmin"` (`users.component.html:25`) | Also requires more than one tenant with users (`users.html:57`) | **Changed**, no data hidden |
| 8 | **Moving a user between tenants** | Tenant select enabled on edit for a platform admin (`users.component.ts:144`, template `users.component.html:179`); `updateUser` honours it (`AppUserServiceImpl:295-296`) | Select disabled whenever the row already has a tenant (`user-dialog.ts:103-104`) | **Lost**, deliberately -- the reason is in the source comment |
| 9 | Username locked on edit | `disabled: true` (`users.component.ts:142`) | Editable, and silently discarded by the server | **Lost** -- and worse than lost, see 12.2 |
| 10 | Reset-password field masked | `type="password"` (`users.component.html:207`) | Plain text input (`prompt-dialog.ts:21-23`) | **Lost**, see 12.3 |
| 11 | Reset-password wording that told the truth | "The user isn't notified automatically" (`users.component.html:208`) | Button title "Send a new one-time password" (`users.html:243`) | **Regressed**, see 12.4 |
| 12 | Tenant code locked on edit | `disabled: true` (`tenants.component.ts:130`) | Editable (`tenant-dialog.ts:64-65`) | **Gained**, with a misleading hint -- see 12.9 |
| 13 | Breadcrumb back to Tenants from a focused user list | `users.component.html:1-7` | None; the focus banner clears the filter but does not navigate (`users.ts:193-195`) | **Lost** (minor) |
| 14 | Distinguishing "nothing matches" from "nothing exists" | One sentence for both (`users.component.html:138`, `tenants.component.html:126`) | `TableShell` picks the wording from `hasFilters()` (`users.html:44`, `tenants.html:32`) | **Gained** |
| 15 | A loading state on the list | Global spinner (`users.component.ts:106`, `tenants.component.ts:97`) | `TableShell` spinner plus a distinct error panel with Try again (`shared/ui/data-table.ts:41-61`) | **Gained** -- a failed load is no longer indistinguishable from an empty result |
| 16 | Confirmation before suspending a tenant or deactivating a user | None (`tenants.component.html:111-114`, `users.component.html:107-110`) | `confirmWith`, naming the consequence (`tenants.ts:221-237`, `users.ts:298-311`) | **Gained** |
| 17 | A Cancel button on the delete confirmations | Absent (`tenants.component.html:174-176`, `users.component.html:230-232`) | Present (`shared/ui/confirm.ts:19-24`) | **Gained** |
| 18 | Offering a tenant admin a role it cannot grant | `TENANT_ADMIN` selectable, refused on submit (`users.component.html:176`) | Not offered (`user-dialog.ts:57-63`), with a spec pinning it | **Gained** |
| 19 | Acting on a row the server will refuse | Every row offered every action | The action menu is replaced by a padlock (`users.ts:291-296`) | **Gained** |
| 20 | Protecting your own account from you | Nothing client-side; server refused (`AppUserServiceImpl:328-330`) | Disabled controls with a title saying why (`users.html:248-249`) | **Gained** |
| 21 | Avatars, phone, position, workload, sort, paging, cards, copy-to-clipboard, Only mine, created/updated by | None | All present | **Gained** |
| 22 | A Status control in the user dialog | None -- status was only ever the row toggle | Present, and does nothing on either path | **Gained in appearance only**, see 12.1 |

### 2.8 Tests that exist

**Frontend.** The old app has no specs at all. The new app has exactly one file for this feature:
`features/admin/users/user-management-scope.spec.ts` -- 7 tests over `Users.canManage` and
`UserDialog.roles`, written explicitly to keep the console in step with `scopedFind` and the role
rules (its header comment says so). **There is no spec for the tenants screen**, none for the filters,
sorting or paging on either screen, and none for either dialog's submit path.

**Backend, unit.**

| File | What it pins |
|---|---|
| `process/src/test/java/process/model/service/impl/AppUserServiceImplRoleScopeTest.java` | 20 tests: a tenant admin cannot create, promote to, edit, deactivate or reset a `TENANT_ADMIN`; may still edit a tenant user and its own row; the cross-tenant refusal says only "User not found."; an administrator's reset is held to the same eight characters and sets `mustChangePassword`; and the avatar read scope |
| `AppUserServiceImplFailClosedTest.java` | The tenant-less caller and the platform-owned row, for `readAvatar` |
| `UserStatisticsQueryTest.java` | `userStatistics` is scoped to the caller's tenant, unscoped for a platform admin, and keeps its `LEFT JOIN`s |
| `model/pojo/TenantFilterDeclarationTest.java` | Every entity carrying `tenant_id` either declares the Hibernate filter or is named here with a reason. `Tenant` and `AppUser` are both named, at `:47-48` |
| `config/MethodSecurityConfigRoleHierarchyTest.java` | The `ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN > ROLE_TENANT_USER` hierarchy |
| `emailer/UserWelcomeTemplateTest.java` | The welcome mail |
| `model/service/impl/AuthServiceImplMustChangePasswordTest.java` | The one-time-password flag at sign-in |

**Backend, end-to-end.** `process/src/test/java/process/e2e/UserManagementE2EIT.java` (659 lines) and
`TenantLifecycleE2EIT.java` (390 lines) drive the real filter chain over MockMvc and cover almost
every refusal this document lists -- cross-tenant reads and writes, peer administrators, a tenant
admin naming another company on a create, a tenant user reaching for a colleague, and all four tenant
endpoints refused to both non-platform roles.

**They do not run in the build.** `process/pom.xml` declares only `spring-boot-maven-plugin` and
`maven-toolchains-plugin`; there is no `maven-failsafe-plugin`, and Surefire's default includes
(`*Test.java`, `Test*.java`, `*Tests.java`, `*TestCase.java`) do not match `*IT.java`. They also need
a live Postgres: `src/test/resources/application-e2e.properties` points at
`jdbc:postgresql://localhost:5433/etl_job` with credentials from the environment.

---

## 3. Expected behaviour

Most of this is what the code already does. The paragraphs below say what *should* be true; where
that differs from today it is called out and cross-referenced to section 12.

**Reading.** A platform admin sees every tenant and every user. A tenant admin sees the users of its
own tenant and no tenants screen at all. A tenant user reaches neither screen and neither endpoint.
That holds today at every layer.

**Creating a tenant.** Name and code, both required; the code unique across the installation, and
normalised the same way whichever path creates it. What the administrator typed and what was stored
should be the same string, or the difference should be shown before saving -- today the dialog permits
dots and underscores that the server silently converts to hyphens (**12.8**).

**Editing a tenant.** Name and status always editable. The code should be editable, because a typo in
a code an administrator has to read on screen is worth being able to fix and nothing in the product
resolves anything by it -- but the hint should not claim a consequence that cannot occur (**12.9**).

**Suspending versus deactivating a tenant.** Both block sign-in for every user in the tenant
(`AuthServiceImpl:105-110` treats any non-`Active` tenant status the same). The dialog should say so
for both; today its hint mentions only suspension, so choosing `Inactive` locks a workspace out with
no warning at all (**12.19**).

**Deleting a tenant.** Should stay a soft delete, and should stay confirmable. It should also tell the
truth about reversibility: today nothing in either console can list or restore a `Delete` tenant, and
the confirmation does not say the step is one-way (section 13).

**Creating a user.** Full name, email and role required; a tenant required for any role but
`PLATFORM_ADMIN`; the password optional, with a generated one emailed when it is left blank. A typed
password must be held to the same eight characters as every other password path -- today it is held to
that only in the browser (**12.5**). The email must be a real address on the server too, not only in
the browser (**12.6**). A Status chosen at creation must be honoured or must not be offered (**12.1**).

**Editing a user.** Full name, position, phone, role, and -- for a platform admin -- status. The email
is the sign-in identity; either the server should accept a change to it, with the uniqueness check
that implies, or the field should be read-only as it was in the old app. What it must not do is accept
the keystrokes and discard them (**12.2**).

**Moving a user between tenants** is supported by `updateUser` and reachable in the old console. The
new console withholds it deliberately. That is a defensible decision, but it should be an explicit one
and it should be recorded somewhere a user can see -- today the only trace is a source comment
(**gap 8 in 2.7**; the decision is taken in the synthesis).

**Resetting a password.** An administrator types a new password, it is stored hashed, the account owes
a change on next sign-in, and the administrator passes it on themselves. The field must be masked
(**12.3**) and the interface must not claim anything was sent (**12.4**). Ideally the account is told
by email that its password was reset -- it is not, today (section 13).

**Deactivating and deleting a user.** Both confirmed, both refused on your own row, both refused
against a peer administrator unless you are a platform admin. All true today. What is not true is that
the effect is immediate: an access token already issued keeps working for up to thirty minutes
(**12.12**).

**Every refusal should read as a rule, not as a fault.** `refusalFor` already does this for the peer
administrator, and `canManage` already stops the console offering what the server will refuse. The
same standard should apply to the two dialogs, where fields that cannot take effect are currently
offered as though they can.

---

## 4. Frontend requirements

### 4.1 Routes and shell

| Route | Component | Guard | Data |
|---|---|---|---|
| `/admin/users` | `features/admin/users/users.ts` `Users` | `authGuard` + `passwordChangeGuard` (shell) + `roleGuard` | `minRole: 'TENANT_ADMIN'` |
| `/admin/tenants` | `features/admin/tenants/tenants.ts` `Tenants` | same + `roleGuard` | `minRole: 'PLATFORM_ADMIN'` |

`roleGuard` must stay on the route that declares `minRole` -- mounted on the shell it reads a key the
shell does not carry and passes for everybody, which is written up in `core/auth/auth.guard.ts:19-32`.
`/admin/users` accepts one query parameter, `tenantId`, and must react to it changing without a
reload.

Nav entries: Administration → Users (`adminOnly`) and Tenants (`platformOnly`), plus the matching
cards on the settings hub. Nothing renders that would 403.

### 4.2 Components

| Component | File | Role |
|---|---|---|
| `Tenants` | `features/admin/tenants/tenants.ts` + `.html` | List, tiles, filters, both views, the three status actions |
| `TenantDialog` | `features/admin/tenants/tenant-dialog.ts` | Create and edit, inline template |
| `Users` | `features/admin/users/users.ts` + `.html` | List, tiles, filters, both views, paging, the four row actions |
| `UserDialog` | `features/admin/users/user-dialog.ts` + `.html` | Create and edit |
| Shared | `shared/ui/` | `TableShell`, `StatusPill`, `StatTile`, `Avatar`, `MineFilter`, `ViewToggle`, `Pagination` + `createPager`, `createSort`, `Field`, `FormDialog`, `PhoneInput`, `confirmWith`, `ToastService`, `copyText` |
| Borrowed | `features/objects/dialogs/prompt-dialog.ts` | The reset-password prompt |

### 4.3 Tenants screen

- **Tiles**: Tenants (+ active count), Users, Jobs (+ task count), Unused. Computed over the whole
  list, not the filtered one.
- **Toolbar**: view toggle (persisted, key `tenants`), status filter (Active / Suspended / Inactive),
  sort select + direction button, search, Only mine, Clear (shown only when something is set, and it
  must reset Only mine as well as the rest).
- **Table**: Tenant, Code (monospace), six counts right-aligned and muted at zero, Created, Created by,
  Updated by, State, kebab. Non-`Active` rows carry reduced opacity.
- **Cards**: name, code chip, "since <date>", status pill, three headline metrics, a share bar for
  headcount, a summary sentence for the quiet three, then Users / Edit / Suspend / Delete.
- **Row actions**: Users (navigates to `/admin/users?tenantId=`), Edit, Suspend/Reactivate, Delete.
  Both status actions confirm first and name what the tenant holds.

### 4.4 Users screen

- **Focus banner** when `tenantId` is present, naming the tenant and offering Show all tenants.
- **Tiles**: Users, Active, Admins, Never signed in -- over the focused subset.
- **Toolbar**: view toggle (key `users`), role filter, tenant filter (platform admin, >1 tenant),
  status filter, search over name / email / position / phone / tenant, Only mine, Clear. Every control
  resets the pager.
- **Table**: Person (avatar, name, email, phone), Role (+ position), Tenant (+ `tenant off` pill),
  Last sign-in, Workload, Added (+ by / edited by), State, actions. Person, Role, Tenant, Last sign-in
  and Added are sortable.
- **Cards**: privilege rule, status ring, You pill, role and tenant pills, copyable contact lines,
  workload tiles, footer facts, the same four actions.
- **Row actions**: Edit, Reset password, Activate/Deactivate, Delete. Self rows: the last two
  disabled with a title saying why. Rows failing `canManage`: a padlock and the rule, no menu.
- **Pager** outside the scroll box, sizes 50 / 100 / 150 / 200.

### 4.5 Dialogs

**Tenant.** `FormDialog` chrome. Tenant name (required), Tenant code (required, pattern, slugged from
the name while creating), Status. Errors rendered by `Field` under the control, not only as a toast.

**User.** `FormDialog` chrome, two-column grid for name / position, full width for phone and email.
Full name (required), Position, Phone (`PhoneInput`, E.164), Email (required, email), Password
(optional, min 8 when typed), Role (only grantable options), Tenant (platform admin, hidden for
`PLATFORM_ADMIN`, locked once set), Status. The dialog must not offer a field the server will
discard -- which today it does twice.

**Reset password.** Must use a masked field. `PromptDialog` as it stands cannot do this; either it
grows a `type` option or this screen gets its own small dialog (decided in the synthesis).

**Confirmations.** `confirmWith` for suspend, reactivate, deactivate, activate and both deletes.
Danger styling on the destructive direction only.

### 4.6 Loading, empty and error

All three come from `TableShell` and must not be re-implemented:

- **Loading** -- a centred spinner with "Loading…", replacing the rows.
- **Error** -- an alert glyph, the server's message where there is one, and a **Try again** button
  wired to the reload. This is the state the old app did not have; a 500 there showed a toast and then
  an empty table.
- **Empty** -- `hasFilters() ? 'No … match the current filters.' : 'No … yet.'`, with an icon.
- The `userStatistics` failure is deliberately silent; the Workload cells fall back to `—`.
- An avatar that 404s falls back to initials (`shared/ui/avatar.ts:75-77`).

### 4.7 Dark and light

Both screens are token-only: `var(--text-secondary)`, `var(--text-muted)`, `var(--border-subtle)`,
`bg-raised`, `bg-sunken`, `bg-subtle`, `var(--series-ok)`, `var(--series-crit)`, `var(--color-ok-500)`.
`StatusPill` owns the mapping from a status string to a tone, so Active is the same green here as
everywhere (`shared/ui/status-pill.ts:54-61`). `ROLE_META` owns the role pill and the card accent
(`core/auth/auth.models.ts:28-47`). No hard-coded hex belongs on either screen. The one place to watch
is `statusRing` (`users.ts:445-447`), which returns a token string and must keep doing so.

### 4.8 Responsive

- Tiles: `grid-cols-2` → `md:grid-cols-4` on both screens.
- Tenant cards: one column → `lg:grid-cols-2` → `2xl:grid-cols-3`. User cards: one → `sm:2` → `lg:3`.
- Both tables scroll inside `TableShell`'s `overflow-x-auto`; the page body must never scroll
  sideways.
- Identity, role and tenant cells are width-capped with `truncate` and a `title`, so a long name
  cannot push the actions column off screen.
- Toolbars wrap (`flex-wrap`); on a narrow viewport the filters stack above the table rather than
  scrolling.

---

## 5. Backend requirements

### 5.1 Endpoints

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/tenant.json/listTenants` | `PLATFORM_ADMIN` | Every tenant whose status is not `Delete`, newest first, each with six resource counts and `createdBy` / `createdByName` / `updatedByName` |
| POST | `/tenant.json/addTenant` | `PLATFORM_ADMIN` | Creates a tenant. Name and code required, code normalised and unique, status defaults to `Active` |
| PUT | `/tenant.json/updateTenant` | `PLATFORM_ADMIN` | Renames, re-codes and optionally re-statuses a tenant. Refuses a code owned by another row |
| PUT | `/tenant.json/changeTenantStatus` | `PLATFORM_ADMIN` | Writes any `TenantStatus`, including `Delete` |
| GET | `/appUser.json/listUsers` | `TENANT_ADMIN` | Every non-`Delete` user for a platform admin; the caller's own tenant otherwise. Peer administrators are included |
| POST | `/appUser.json/addUser` | `TENANT_ADMIN` | Creates a user. Role rules as in 2.6. Status forced `Active`. Generates and emails a password when none is supplied |
| PUT | `/appUser.json/updateUser` | `TENANT_ADMIN` | Writes role, phone, tenant, full name and position on a row `scopedFind` allows |
| PUT | `/appUser.json/changeUserStatus` | `TENANT_ADMIN` | `Active` / `Inactive` / `Delete`, refused on your own row for anything but `Active` |
| PUT | `/appUser.json/resetPassword` | `TENANT_ADMIN` | Re-hashes a password of at least eight characters and sets `mustChangePassword` |
| GET | `/appUser.json/avatar?appUserId=` | `TENANT_USER` (override) | Streams a picture, or 404. Scope decided by `TenantOwnership.isOwnedByCaller` |
| GET | `/dashboard.json/userStatistics` | `TENANT_USER` (inherited) | Per-user job / task / run totals for the caller's tenant. Backs the Workload column |

Every one of these answers with the `ResponseDto` envelope: HTTP 200 carrying
`{status: 'SUCCESS'|'ERROR', message, data}`, and HTTP 500 with `INTERNAL_ERROR_500` on an unhandled
exception. The role column is the *effective* role after `MethodSecurityConfig`'s hierarchy, so
`TENANT_ADMIN` admits `PLATFORM_ADMIN` throughout.

### 5.2 Services

**`TenantService` / `TenantServiceImpl`.** Six repositories for the counts plus `UserNameResolver`.
Requirements: normalise codes identically wherever a tenant is created (this service and
`TenantRequestServiceImpl.approve`, which has its own `normaliseCode` at
`TenantRequestServiceImpl:148`); keep `Delete` out of the listing; keep the counts consistent with
each entity's own soft-delete rule (`countByTenantIdAndStatusNot(…, Delete)` on all six).

**`AppUserService` / `AppUserServiceImpl`.** The authorization surface for this feature. `scopedFind`
is the single ownership rule for the four write paths and must stay that way -- the moment one of them
grows its own copy, the copies start to disagree, which is exactly the history `TenantOwnership`
records. `refusalFor` chooses the wording and must stay unable to confirm the existence of a row
outside the caller's tenant.

**`DashboardService.userStatistics`** builds native SQL through `QueryService`, whose `tenantClause`
is the only isolation. Any change there is a four-layer change.

**Not required and not present**: an email on password reset, an in-app notification on user creation
(a grep of `AppUserServiceImpl` and `TenantServiceImpl` for `Notification` returns nothing), and any
server-side paging or filtering on either list.

---

## 6. Database requirements

### 6.1 `tenant`

| Column | Type | Notes |
|---|---|---|
| `tenant_id` | `BIGINT` PK | `tenant_Seq`, initial value 1000 (`Tenant.java:34-46`) |
| `uuid` | `VARCHAR(36)` unique | Set on create, never surfaced by either console |
| `tenant_name` | not null | No length declared, so the JPA default 255 |
| `tenant_code` | not null, **unique** | The uniqueness the service checks by hand as well |
| `status` | not null, enum string | `Active` / `Inactive` / `Suspended` / `Delete` (`model/enums/TenantStatus.java`) |
| `date_created` | timestamp | |
| `created_by`, `updated_by` | `BIGINT`, nullable | `V22.0-audit-columns/V22__audit_columns.sql:36-37`; stamped by `AuditListener` |

### 6.2 `app_user`

| Column | Type | Notes |
|---|---|---|
| `app_user_id` | `BIGINT` PK | `app_user_Seq`, initial value 1000 |
| `uuid` | `VARCHAR(36)` unique | |
| `tenant_id` | `BIGINT`, **nullable**, indexed, FK to `tenant` | Null means platform-owned -- the seeded platform admin (`TenantSeedService:113-126`) and any other `PLATFORM_ADMIN` |
| `username` | not null, **unique** | An email by convention; the constraint is on the raw string |
| `password` | not null, `@JsonIgnore` | BCrypt |
| `full_name` | not null | |
| `user_role` | not null, enum string | `PLATFORM_ADMIN` / `TENANT_ADMIN` / `TENANT_USER` |
| `status` | not null, enum string | `Active` / `Inactive` / `Delete` (`model/enums/Status.java`) |
| `date_created`, `last_login_at` | timestamps | `last_login_at` written on every successful sign-in (`AuthServiceImpl:67-68`) |
| `avatar_bucket` `VARCHAR(255)`, `avatar_key` `VARCHAR(512)` | | `V18.0-user-avatar/V18__user_avatar.sql:4-5`; key layout `<appUserId>/profile/avatar.<ext>` per `V23.0-avatar-key-layout` |
| `position` | `VARCHAR(120)` | `V20.0-user-position/V20__user_position.sql:6`. **The form does not cap it** |
| `must_change_password` | `BOOLEAN NOT NULL DEFAULT FALSE` | `V21.0-tenant-request/V21__tenant_request.sql:35` |
| `phone_number` | `VARCHAR(20)` | `V24.0-user-phone/V24__user_phone.sql:7`; E.164 fits |
| `created_by`, `updated_by` | `BIGINT`, nullable | `V22__audit_columns.sql:39-40` |

The FK `fk_app_user_tenant` (`V12__add_tenant_user_fk_constraints.sql:35`) has no `ON DELETE`, on
purpose: the application soft-deletes and never issues a real `DELETE FROM tenant`.

### 6.3 The Hibernate filter, and why there isn't one

Neither `Tenant` nor `AppUser` declares `@Filter(name = "tenantFilter")` -- verified by grep against
both POJOs. This is deliberate and it is pinned by a test:
`model/pojo/TenantFilterDeclarationTest.java:47-48` names both in `NOT_SCOPED_BY_TENANT_FILTER`, with
the reasons at `:38-45`. `Tenant`'s `tenant_id` is its own primary key. `AppUser` is read outside the
caller's tenant on two paths that must keep working -- the sign-in lookup, which runs before there is
a tenant at all, and `UserNameResolver`, which turns a `created_by` id into a name for rows a
neighbouring tenant authored.

The consequence for this feature is the whole of section 8.3: **layer four does nothing here, so the
service rule is the only data boundary.** Anything that widens `listUsers` or `scopedFind` widens the
boundary with nothing behind it.

### 6.4 Migrations needed

None for the behaviour described above. Two are needed only if the open questions in the synthesis are
answered a particular way:

- Making `app_user.status` settable from the dialog needs no schema change, only service code.
- Recording a password-reset event, or a "welcome mail sent" flag, would need a new column or table.
  Neither is proposed here.

The one schema smell worth naming: `app_user.position` is `VARCHAR(120)` and nothing above the
database enforces it, so an over-long title reaches Postgres and comes back as a 500 (**12.7**).

---

## 7. Validation

| # | Rule | Client | Server | Verdict |
|---|---|---|---|---|
| 1 | Tenant name required | `Validators.required` (`tenant-dialog.ts:63`) | `TenantServiceImpl:87-88`, `:110-111` | Both |
| 2 | Tenant code required | `Validators.required` (`:65`) | `:89-90`, `:112-113` | Both |
| 3 | Tenant code shape | `^[a-z0-9][a-z0-9._-]*$` (`:65`) | `normalizeCode` rewrites anything outside `[a-z0-9-]` to `-` (`:152`) | **Disagree** -- see 12.8 |
| 4 | Tenant code unique | none | `findByTenantCode` on both create and update (`:93`, `:120-123`) | Server only, correctly |
| 5 | Tenant status is one of four | Select offers three (`tenant-dialog.ts:41-44`); no `Delete` | Enum binding; `changeTenantStatus` accepts all four (`:135-149`) | Both, loosely |
| 6 | User full name required | `Validators.required` (`user-dialog.ts:91`) | `AppUserServiceImpl:144-145`, `:253-254` | Both |
| 7 | Email required | `Validators.required` (`:93`) | `:142-143` | Both |
| 8 | Email is an email | `Validators.email` (`:93`) | **none** -- only non-empty and unique | **Client only** -- 12.6 |
| 9 | Email unique | none | `findByUsernameAndStatusNot` (`:180-182`) | Server only, correctly |
| 10 | Email immutable after creation | Not enforced -- the field is editable | Enforced by omission: `updateUser` never writes it | **Neither states it** -- 12.2 |
| 11 | Password ≥ 8 on **create** | `Validators.minLength(8)` (`user-dialog.ts:97`) | **none** on this path -- `validateNewPassword` is called only from `resetPassword:344` and `changeOwnPassword:611` | **Client only** -- 12.5 |
| 12 | Password ≥ 8 on **reset** | `password.length < 8` in the caller (`users.ts:354`) | `validateNewPassword` (`:368-373`) | Both |
| 13 | Password optional | Yes, by design (`user-dialog.ts:94-97`) | Yes -- generates one (`:186-187`) | Both |
| 14 | Role required | `Validators.required` (`:98`) | `:146-147` on create; optional on update, defaulting to the row's own (`:268`) | Both |
| 15 | Role grantable by this actor | Picker filtered (`:57-63`) | `:156-164` on create, `:279-289` on update | Both, and the spec pins the client half |
| 16 | Cannot change your own role | none | `:275-278` | **Server only** -- acceptable, but the dialog will offer it and then fail |
| 17 | Tenant required for a non-platform role | `save()` guard (`user-dialog.ts:124-128`) | `:169-171` on create, `:301-303` on update | Both |
| 18 | Tenant must exist | none | `:177-179`, `:304-306` | Server only, correctly |
| 19 | Phone is a real number | `libphonenumber` in `PhoneInput` | `PhoneNumberValidator.normalise` (`:151-154`, `:263-266`) | Both, against the same metadata |
| 20 | Position ≤ 120 characters | **none** | **none** -- the column is `VARCHAR(120)` | **Neither** -- 12.7 |
| 21 | Status honoured on create | Select offered | Ignored -- forced `Active` (`:198`) | **Offered and discarded** -- 12.1 |
| 22 | Status honoured on update | Select offered | Ignored -- never written (`:308-312`) | **Offered and discarded** -- 12.1 |
| 23 | Cannot deactivate or delete yourself | Controls disabled (`users.html:248-249`) | `:328-330` | Both |
| 24 | Avatar key is your own | n/a | `isOwnProfileKey` (`:535-543`) | Server only, correctly |

Rows 3, 8, 11, 20, 21 and 22 are the findings. Rows 8 and 11 are the ones that matter: both are
password- or identity-adjacent, and both are enforced by a browser that any caller can decline to use.

---

## 8. Security

### 8.1 Layer one -- the frontend guard

`roleGuard` on each route, reading `data.minRole` and comparing ranks (`core/auth/auth.guard.ts:33-42`,
`core/auth/auth.models.ts:10-14`). `/admin/users` needs `TENANT_ADMIN`, `/admin/tenants` needs
`PLATFORM_ADMIN`. A failure produces a `UrlTree` to `/unauthorized`. The shell adds `authGuard` and
`passwordChangeGuard`, so an account owing a password change cannot reach either screen.

Nav and hub entries are filtered by the same two predicates (`shell.ts:140-151`,
`settings-hub.ts:53`). Within the users screen, `canManage` decides whether a row gets a menu at all
(`users.ts:291-296`) and `UserDialog.roles` decides which roles are offered (`user-dialog.ts:57-63`).

None of this is enforcement. It exists so the console does not propose what the server will refuse.

### 8.2 Layer two -- the controller annotation

| Controller | Class annotation | Method overrides |
|---|---|---|
| `TenantRestApi` | `hasRole('PLATFORM_ADMIN')` (`:20`) | **none** -- all four inherit it |
| `AppUserRestApi` | `hasRole('TENANT_ADMIN')` (`:24`) | Five, all to `hasRole('TENANT_USER')`: `/me` `:92`, `/avatar` `:111`, `/updateOwnProfile` `:131`, `/changeOwnPassword` `:147`, `/updateOwnAvatar` `:163` |
| `DashboardRestApi` | `hasRole('TENANT_USER')` (`:19`) | none on `userStatistics` `:43` |

`@PreAuthorize` is not repeatable, so each of those five method annotations **replaces** the class's
`TENANT_ADMIN` rather than adding to it. That is the intent -- everyone manages their own profile --
and the five endpoints all derive their subject from `TenantContext` rather than the request, so the
override widens who may call without widening what they may touch. The five administrative endpoints
carry no method annotation and so keep `TENANT_ADMIN`.

`MethodSecurityConfig:26-31` installs `ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN > ROLE_TENANT_USER`, so
`hasRole('TENANT_ADMIN')` admits a platform admin. The authority itself is minted by
`JwtAuthenticationFilter:45-46` as `"ROLE_" + userRole` straight off the token claim.

### 8.3 Layer three -- the service rule

This is where the whole boundary lives for this feature.

**Tenants.** No rule at all, and that is right: a tenant row is platform-owned and the controller
annotation already restricts every caller to a platform admin. `findById` is used freely
(`TenantServiceImpl:115`, `:141`) because there is no narrower owner to compare against.

**Users, reading.** `listUsers` (`AppUserServiceImpl:127-137`) branches on
`TenantContext.isPlatformAdmin()`. A platform admin gets everything; anybody else gets
`findByTenantIdAndStatusNotOrderByAppUserIdDesc(TenantContext.getTenantId(), Delete)`. Peer
administrators *are* returned to a tenant admin, which is the reason `canManage` and `refusalFor`
both exist.

**Users, writing.** `scopedFind` (`:375-398`) is the single gate on `updateUser`, `changeUserStatus`
and `resetPassword`. Three conditions, in order: the row must exist and not be `Delete`; a platform
admin passes; everyone else must share the tenant **and** the target must be a `TENANT_USER` or the
caller's own row. `addUser` has its own rules (`:156-176`) because there is no row to find yet.

**Avatars.** `readAvatar` (`:103-124`) asks `TenantOwnership.isOwnedByCaller` at `:117` rather than
comparing ids, and the comment at `:112-116` records why: comparing directly let a tenant-less caller
match a platform admin's tenant-less row, because null equals null.

**Statistics.** `QueryService.tenantClause` (`:212-217`) is the only isolation on `userStatistics`,
and it returns an empty string both for a platform admin *and* for any caller whose tenant is null.

### 8.4 Layer four -- the Hibernate filter

**Absent, deliberately, and tested.** See 6.3. `TenantFilterHelper.enableIfNeeded` turns the filter on
for the session, and Hibernate applies it only to entities that declare it; `Tenant` and `AppUser`
declare nothing, so nothing happens for them. `TenantFilterDeclarationTest:75-90` makes that a
decision somebody has to change on purpose rather than an omission.

The practical rule for anyone working here: **there is no safety net under `findById` on `AppUser`.**
Every write path already routes through `scopedFind`; a new one must too.

### 8.5 Per role

| | `PLATFORM_ADMIN` | `TENANT_ADMIN` | `TENANT_USER` |
|---|---|---|---|
| See `/admin/tenants` | yes | no -- `/unauthorized`, and the nav entry is not rendered | no |
| Any `tenant.json` endpoint | yes | **403** from the filter chain | **403** |
| See `/admin/users` | yes | yes | no -- `/unauthorized` |
| `listUsers` | every non-deleted user in the installation | every non-deleted user of its own tenant, peer admins included | **403** |
| Create a user | any role, any tenant | `TENANT_USER` only, forced into its own tenant whatever the body says (`:173-176`) | **403** |
| Edit a user | anybody, including peers and platform admins | tenant users of its own tenant, plus its own row | **403** |
| Grant a role | any of three | `TENANT_USER`, or resubmit the row's existing role | n/a |
| Change a status | anybody but itself to a non-`Active` value | as above, within `scopedFind` | **403** |
| Reset a password | anybody's | tenant users of its own tenant, and its own | **403** |
| Move a user between tenants | supported by `updateUser:295-296`; **not reachable from the new console** | no -- `effectiveTenantId` falls back to the row's own (`:297-298`) | n/a |
| See somebody's avatar | anybody's | anybody in its own tenant | anybody in its own tenant |
| `userStatistics` | every tenant | own tenant | **own tenant** -- see 12.10 |

A caller with **no tenant claim** and a non-platform role owns nothing, by the rule `TenantOwnership`
states. `readAvatar` holds that line and has a test for it. `listUsers` and `addUser` do not obviously
hold it -- see **12.11**.

### 8.6 What a token still carries after you act

Role and tenant are claims, minted at sign-in and at refresh (`JwtUtil:42-54`) and trusted by
`JwtAuthenticationFilter:38-47` for the life of the token. Access tokens default to thirty minutes
(`JwtUtil:28-29`). `AuthServiceImpl.checkAccountAndTenantActive` (`:101-112`) is consulted on login and
on refresh only. The consequence is in **12.12**.

---

## 9. Error handling

| What fails | What the user sees |
|---|---|
| `listTenants` / `listUsers` returns `ERROR` | `TableShell`'s error panel with the server's message and a **Try again** button (`tenants.ts:189`, `users.ts:205`) |
| Either list request errors at the transport | The same panel, with "Tenants could not be loaded." / "Could not load users." (`tenants.ts:192-195`, `users.ts:207-210`) |
| `userStatistics` fails | Nothing. The Workload column shows `—` and the cards omit the tiles (`users.ts:230-231`) |
| An avatar 404s or 403s | Initials (`avatar.ts:75-77`) |
| A dialog fails client validation | `Field` renders the message under the control, plus a toast "Check the highlighted fields." (`user-dialog.ts:115-118`, `tenant-dialog.ts:94-98`) |
| Tenant missing on a user create | Toast "Choose a tenant for this user." before any request (`user-dialog.ts:124-128`) |
| Reset password under 8 characters | Toast "Use at least 8 characters." before any request (`users.ts:354-357`) |
| The server answers `ERROR` on a save | The server's own message as a toast, and the dialog stays open (`user-dialog.ts:151-153`, `tenant-dialog.ts:112-114`) |
| A duplicate tenant code | `Tenant code "x" is already in use.` |
| A duplicate username | `Username "x" is already in use.` |
| A tenant admin reaching a peer admin | `Only a Platform Admin can manage another Tenant Admin.` -- and the console does not offer the control in the first place |
| A tenant admin reaching another tenant | `User not found.` Nothing distinguishes it from an id that does not exist |
| Creating a user when the mail fails | A **success** toast carrying the server's warning: "created, but the welcome email could not be sent. Reset their password and pass it on another way." (`AppUserServiceImpl:203-217`). The console forwards `response.message` rather than a fixed string precisely so this survives (`user-dialog.ts:146-149`) |
| An unhandled server exception | HTTP 500 with `Some internal error occurred contact with support.` (`ProcessUtil:10`), surfaced as a toast |
| A status change fails | Toast, and the row is left as it was; `busy` clears (`users.ts:335-338`) |

Two gaps in this table. There is no error path for a **stale list**: nothing on either screen tells you
the row you are acting on was changed by somebody else, and the last write wins. And a validation
failure that only the database can catch -- an over-long position -- surfaces as the generic 500 text
rather than as a field error (**12.7**).

---

## 10. Dependencies

**Depends on:**

- **`authentication-and-access`** (feature 1) for everything. The token supplies the role and tenant
  that all four layers read; `auth.interceptor.ts` attaches it; `authGuard` and `passwordChangeGuard`
  wrap the shell. `AuthService.hasAtLeast` is what `roleGuard`, the nav filter and `canManage` all
  consult.
- **`storage-connections`** (feature 9), indirectly and only for pictures. Avatars live in one platform
  bucket named by `StoragePropertyDefaults.AVATAR_BUCKET` (`AppUserServiceImpl:68-69`), read through
  `StorageBrowserService.readForWorkflow`. Without that connection, avatars fall back to initials and
  nothing else on either screen is affected.
- **`dashboard`** (feature 2) for one endpoint, `userStatistics`. Its failure is non-fatal.
- **The mail stack.** `EmailMessagesFactory.sendUserWelcomeEmail` (`emailer/EmailMessagesFactory.java:145`)
  is the only way a generated password reaches its owner. With mail down, `addUser` still succeeds and
  the account is unusable until somebody resets it.

**Depended on by:**

- **`workspace-requests`** (feature 17) writes into both tables: `TenantRequestServiceImpl.approve`
  (`:134-190`) creates the `Tenant` and its first `TENANT_ADMIN` directly, with its own `normaliseCode`.
  Anything this feature changes about how a tenant or a first admin is built has to be mirrored there.
- **`own-account-and-notifications`** (feature 18) edits the same `app_user` row through the five
  `TENANT_USER` endpoints on the same controller.
- **`source-jobs`** through `source_job.assigned_user_id`, which is what `userStatistics` aggregates on.
- **Every tenant-scoped feature**, since `tenant.status` decides whether anybody in the workspace can
  sign in at all.

**Infrastructure:** Postgres (both tables plus the six count queries per tenant row), and an SMTP
server for the welcome mail.

---

## 11. Acceptance criteria

Fixtures assumed throughout: tenants **A** (`tenant_code` `acme`) and **B** (`beta`), each `Active`;
in A a `TENANT_ADMIN` **adminA**, a second `TENANT_ADMIN` **peerA**, and a `TENANT_USER` **userA**; in
B a `TENANT_ADMIN` **adminB** and a `TENANT_USER` **userB**; a `PLATFORM_ADMIN` **root** with
`tenant_id` null; an empty tenant **C** with no users; a tenant **D** at status `Delete`.

### Access

1. **root** opens `/admin/tenants` and the list contains A, B and C. D does not appear.
2. **root** opens `/admin/users` and the list contains adminA, peerA, userA, adminB, userB and root.
3. **adminA** navigates to `/admin/tenants` and lands on `/unauthorized`; the Administration → Tenants
   nav entry and the settings-hub Tenants card are not rendered for them. **Positive control:** the
   Users entry and card *are* rendered, and `/admin/users` opens.
4. **adminA**, with a valid token, calls `GET /tenant.json/listTenants` directly and receives HTTP 403.
   **Positive control:** the same call as **root** returns 200 with A, B and C.
5. **userA** navigates to `/admin/users` and lands on `/unauthorized`; calling
   `GET /appUser.json/listUsers` directly returns HTTP 403. **Positive control:** the same call as
   **adminA** returns 200.
6. **adminA** calls `listUsers` and the payload contains adminA, peerA and userA and **no row whose
   `tenantId` is B's**, and no row for root. **Positive control:** the same call as **root** returns
   all six.
7. A token whose `userRole` claim is `TENANT_ADMIN` and whose `tenantId` claim is **absent** calls
   `listUsers`. The response contains **no rows at all** -- in particular not root. **Positive
   control:** the same token's owner, re-issued with tenant A in the claim, sees A's three users.
   *(Expected to fail today -- see Known issues 12.11.)*
8. That same tenant-less token posts `addUser` with role `TENANT_USER` and no `tenantId`. The request
   is refused and no row is written. **Positive control:** **adminA** posting the same body creates a
   user whose `tenant_id` is A's. *(Expected to fail today -- 12.11.)*

### Tenants -- create and edit

9. **root** creates a tenant named `Ministry of Justice` leaving the code untouched. The code field
   reads `ministry-of-justice` before submit, and the row that appears in the list carries exactly
   that code.
10. **root** types `acme` into the code of a new tenant. The save is refused with
    `Tenant code "acme" is already in use.` and no row is created.
11. **root** types `ACME` into the code of a new tenant. It is refused with the same message -- the
    comparison is case-insensitive because the code is lowercased before the lookup.
12. **root** types `north.west_1` into the code. Either the field is marked invalid before submit, or
    the row that is created carries the code the administrator was shown. It must not silently store
    `north-west-1`. *(Fails today -- 12.8.)*
13. **root** edits tenant A, changes the name to `Acme Holdings`, and saves. The list shows the new
    name, the code is unchanged, and A's users can still sign in.
14. **root** edits tenant A and changes the code to `acme-holdings`. The save succeeds and the hint on
    the field does not claim that anything referring to the old code stops matching, because nothing
    in the product resolves anything by tenant code. *(The hint is wrong today -- 12.9.)*
15. Leaving Tenant name blank marks the field invalid, shows the message under the control rather than
    only as a toast, and makes no HTTP request.

### Tenants -- status

16. **root** clicks Suspend on tenant A. A confirmation appears naming A and stating that its users
    will not be able to sign in; it offers **Cancel**. Cancelling leaves A `Active` and issues no
    request.
17. Confirming that suspension sets A to `Suspended`, and userA's next sign-in attempt is refused with
    `Your organization's access is currently suspended. Contact your administrator.` **Positive
    control:** userB, in tenant B, signs in normally.
18. **root** reactivates A. The status returns to `Active` and userA can sign in again. No job, task or
    connection belonging to A was removed by either step.
19. **root** edits tenant A and sets Status to `Inactive` in the dialog. Before saving, the dialog
    states that this blocks sign-in exactly as suspension does. *(Fails today -- 12.19: the hint
    mentions only suspension, and `AuthServiceImpl:105-110` treats any non-`Active` status alike.)*
20. **root** deletes tenant C. The confirmation says C owns no resources; C disappears from the list;
    `listTenants` no longer returns it and no other tenant is affected.
21. **root** deletes tenant A, which owns users and jobs. The confirmation names the count and suggests
    suspending instead. After confirming, A is gone from the list and adminA's sign-in is refused.
22. After 21, there is a way for **root** to see that A exists at status `Delete`, or the confirmation
    in 21 stated plainly that the step cannot be undone from the console. *(Neither is true today --
    section 13.)*

### Users -- create

23. **adminA** creates a user with a full name and an email, leaving the password blank. The response
    message says the user was created and emailed; the row appears with role `Tenant user`, status
    `Active`, tenant A, and `Never` under Last sign-in. The new account's `must_change_password` is
    true.
24. The Role picker offered to **adminA** contains exactly one option, `Tenant user`. **Positive
    control:** the picker offered to **root** contains all three.
25. **adminA** forces a request with `userRole: TENANT_ADMIN` past the console. It is refused with
    `Only a Platform Admin can create another Tenant Admin.` and no row is written. **Positive
    control:** **root** posting the same body creates the tenant admin.
26. **adminA** forces a request naming tenant B in the body. The user is created **in tenant A**, not
    B -- the actor's own tenant wins (`AppUserServiceImpl:173-176`).
27. **root** creates a user with role `Platform admin`. No Tenant control is shown; the created row has
    `tenant_id` null and the list shows `All tenants` in its Tenant cell.
28. **root** creates a user with role `Tenant user` and no tenant selected. The save is blocked in the
    dialog with `Choose a tenant for this user.` and no request is made. Forcing the request through
    returns `Tenant missing.`
29. Creating a user with an email that already belongs to a non-deleted account is refused with
    `Username "x" is already in use.` -- including when that account is in a *different* tenant.
30. **adminA** creates a user with the password `abc`. The request is refused by the server, not only
    by the browser, and no account is created. *(Fails today -- 12.5: the eight-character rule is
    client-side on this path.)*
31. **adminA** creates a user with the email `not-an-email`. The request is refused by the server, not
    only by the browser. *(Fails today -- 12.6.)*
32. **adminA** creates a user with Status set to `Inactive`. Either the created row is `Inactive`, or
    the dialog does not offer a Status control on create. *(Fails today -- 12.1: the row is created
    `Active`.)*
33. **adminA** creates a user with a 200-character Position. The field is marked invalid before submit
    rather than the request returning a 500. *(Fails today -- 12.7.)*

### Users -- edit

34. **adminA** edits userA's full name and position and saves. The list shows both changes and the row
    now reads `edited by` adminA.
35. **adminA** opens the Edit dialog on peerA. There is no dialog to open: the row shows a padlock and
    the sentence `Only a Platform Admin can manage another Tenant Admin.` Forcing `updateUser` through
    returns that same sentence and the row is unchanged. **Positive control:** **root** edits peerA
    successfully.
36. **adminA** forces `updateUser` for userB's id. The response is `User not found.` -- with no mention
    of tenant B and nothing to distinguish it from an id that does not exist -- and userB's row is
    unchanged. **Positive control:** **adminA** updating userA's id succeeds.
37. **adminA** edits its own row, changes only the full name, and saves. It succeeds, and the role
    picker still shows `Tenant admin` as the selected option.
38. **adminA** edits its own row and changes the role to `Tenant user`. The request is refused with
    `You cannot change your own role.` and the row keeps `TENANT_ADMIN`.
39. **adminA** edits userA and changes the email. Either the change is persisted and a duplicate is
    refused, or the field is read-only. It must not accept the keystrokes and discard them.
    *(Fails today -- 12.2.)*
40. **adminA** edits userA and changes Status to `Inactive`. Either the row becomes `Inactive`, or the
    dialog does not offer a Status control. *(Fails today -- 12.1.)*
41. **root** edits userA. The Tenant control is visible and shows tenant A. Whether it is editable is
    the decision recorded in the synthesis; whichever way it is settled, the dialog must not present an
    enabled control whose change is discarded.
42. **root** demotes a platform admin to `Tenant admin`. The Tenant control becomes visible and
    required; saving without one is refused with `A tenant is required for this role -- assign one
    before removing Platform Admin.` Choosing tenant A and saving moves the row into A.

### Users -- password, status, delete

43. **adminA** resets userA's password. The input is **masked** -- the characters do not appear on
    screen. *(Fails today -- 12.3.)*
44. Nothing in the reset dialog or its trigger claims the password is sent to the user. *(Fails today
    -- the button title says "Send a new one-time password", 12.4.)*
45. After the reset, userA signs in with the new password and is held on `/profile` until they set
    their own -- `must_change_password` is true and `passwordChangeGuard` pins them there.
46. **adminA** resets a password of seven characters. It is refused in the browser *and*, if forced
    through, by the server with `Choose a new password of at least 8 characters.`
47. **adminA** resets peerA's password. Refused with `Only a Platform Admin can manage another Tenant
    Admin.`, and peerA's stored hash is unchanged. **Positive control:** **root** resetting peerA's
    password succeeds.
48. **adminA** deactivates userA. A confirmation appears naming them and saying their work and history
    are kept; after confirming, the row reads `Inactive` and userA's next sign-in is refused with
    `This account is inactive. Contact your administrator.`
49. **adminA** attempts to deactivate itself. Both the menu item and the card button are disabled with
    the title `You cannot deactivate your own account`. Forcing `changeUserStatus` through with
    `Inactive` returns that same refusal.
50. **adminA** deletes userA. After confirming, the row leaves the list, `listUsers` no longer returns
    it, and `updateUser` against its id now answers `User not found.` even to **root**.
51. **adminA** attempts to delete itself. Refused at both layers, exactly as 49.

### Display and states

52. With `listUsers` stubbed to return HTTP 500, `/admin/users` shows the error panel with a **Try
    again** button -- not an empty table. **Positive control:** with it stubbed to return an empty
    list, the same screen shows `No users yet.`
53. With a filter set that matches nothing, the message reads `No users match the current filters.`
    rather than `No users yet.`, and **Clear** returns the full list.
54. **Clear** on either screen resets the search, every dropdown *and* the Only mine toggle, and on
    the users screen it also removes `?tenantId` from the URL and resets the pager to page 1.
55. **root** clicks Users on tenant A's card and arrives at `/admin/users?tenantId=<A>` with the focus
    banner naming A and only A's users listed. Editing the URL to tenant B's id re-narrows the list
    without a reload.
56. On a tenant with zero users, the Users action is disabled with a title explaining why -- and there
    is still some route by which **root** can create that tenant's first user. *(The second half fails
    today -- section 13.)*
57. userA's card and row show a `tenant off` pill when tenant A is `Suspended`, and the account's own
    status pill still reads `Active` -- the two facts are shown separately because they are separate.
58. A user with no picture renders initials, not a broken image, and a users list of fifty rows revokes
    every blob URL it created when the screen is left.
59. Both screens render correctly in dark and light: no hard-coded colour, `Active` the same green as
    on every other screen, and the role pills the three colours `ROLE_META` defines.
60. At 375px wide, neither screen scrolls the page body horizontally; both tables scroll inside their
    own container and the toolbars wrap.

---

## 12. Known issues

### 12.1 The Status control in the user dialog does nothing, on either path

`user-dialog.html:90-95` renders a Status select bound to `form.status`, and `user-dialog.ts:105`
initialises it. `save()` posts the whole form (`:130`).

On create, `AppUserServiceImpl:198` is `user.setStatus(Status.Active)` -- an unconditional literal, so
`Inactive` is discarded. On edit, `updateUser` writes exactly five fields (`:308-312`) and status is
not among them.

An administrator can therefore create a user as `Inactive`, be told "User created", and watch the row
appear as `Active`; or open an active user, set `Inactive`, save, be told "User updated", and see no
change. The old app had no Status field here at all -- status was only ever the row toggle -- so this
control was added by the rewrite and has never worked. The row toggle beside it *does* work, which
makes the dialog's version harder to notice.

### 12.2 The email field is editable when editing a user, and the change is thrown away

`user-dialog.ts:93` declares `username` with no `disabled`, and `user-dialog.html:44-49` renders it as
an ordinary input on both create and edit. `updateUser` never calls `setUsername` (`:308-312`).

The old app disabled it (`users.component.ts:142`) with the template comment structure making the
intent plain. The rewrite dropped the lock without adding the server support, so correcting a typo in
somebody's sign-in address appears to work and does not. There is no error, no toast, and the list
refreshes showing the old address -- which reads as a caching problem rather than as a discarded write.

Note that supporting the change is not free: `username` is unique across the installation
(`AppUser.java:63`) and is the JWT subject (`JwtUtil:45`), so a rename must re-check uniqueness and
invalidate any token issued under the old subject.

### 12.3 The reset-password dialog does not mask what is typed

`users.ts:342-352` opens the generic `PromptDialog`. That component renders
`<input id="value" class="input" …>` with no `type` (`features/objects/dialogs/prompt-dialog.ts:21-23`),
so the new password is typed in plain text, is visible to anyone near the screen, and is offered to
the browser's autofill as an ordinary text field.

The old app used `<input type="password">` for exactly this dialog
(`scheduler1/src/app/_component/users/users.component.html:207`). This is a regression introduced by
reusing a dialog built for folder names.

`PromptDialog` also trims its value before returning it (`:44-45`), so a password with a leading or
trailing space is silently altered between what was typed and what is stored.

### 12.4 "Send a new one-time password" -- nothing is sent

`users.html:243` puts `title="Send a new one-time password"` on the Reset button.
`AppUserServiceImpl.resetPassword` (`:338-359`) hashes the value, sets `mustChangePassword` and
returns; there is no call to `EmailMessagesFactory` anywhere in that method, and a grep of the class
finds mail only on the create path (`:203-217`).

The dialog's own hint is accurate ("They will need this to sign in"), but the tooltip on the control
that opens it is not, and the old app's wording -- "The user isn't notified automatically -- share the
new password with them yourself" (`users.component.html:208`) -- said the true thing plainly. An
administrator who trusts the tooltip resets a password and tells nobody.

### 12.5 A password typed by an administrator at creation is not length-checked on the server

`validateNewPassword` (`AppUserServiceImpl:368-373`) is called from `resetPassword:344` and
`changeOwnPassword:611`. It is **not** called from `addUser`, which takes the supplied password
straight to the encoder (`:186-187`, `:193`).

The eight-character rule therefore exists only as `Validators.minLength(8)` in the browser
(`user-dialog.ts:97`). Any caller that posts `addUser` directly -- or a browser with the validator
patched out -- can create an account with a one-character password, and that account will then be held
to eight characters the first time its owner changes it. The comment above `validateNewPassword` says
the rule was centralised precisely so the two paths could not disagree; the create path was missed.

### 12.6 "Must be an email" is enforced only in the browser

`user-dialog.ts:93` applies `Validators.email`. `addUser` checks only that the username is non-empty
(`:142-143`) and unique (`:180-182`); nothing anywhere checks its shape. Since the username is also the
address the welcome mail is sent to (`:195-197` passes `user.getUsername()` as the recipient), a
malformed one produces an account whose owner is never told it exists.

### 12.7 `position` has no length limit above the database

`user-dialog.ts:92` declares `position` with no validator and `user-dialog.html:18-19` renders it with
no `maxlength`. The column is `VARCHAR(120)` (`V20.0-user-position/V20__user_position.sql:6`).

A longer title reaches Postgres, the insert or update throws, `AppUserRestApi` catches it and returns
HTTP 500 with `Some internal error occurred contact with support.` (`ProcessUtil:10`) -- so a typing
mistake in an optional field reads as a server fault. The same applies to `phone_number VARCHAR(20)`
in principle, though E.164 cannot exceed sixteen characters so it cannot be reached in practice.

### 12.8 The tenant-code pattern the dialog enforces is wider than the one the server keeps

`tenant-dialog.ts:65` validates against `^[a-z0-9][a-z0-9._-]*$` and the field's error message names
"lowercase letters, digits, dots, dashes or underscores" (`:29`).

`TenantServiceImpl.normalizeCode` (`:152`) is
`tenantCode.trim().toLowerCase().replaceAll("[^a-z0-9-]", "-")` -- dots and underscores are replaced
with hyphens. Typing `north.west_1`, which the dialog explicitly says is allowed, stores
`north-west-1`, and the list then shows a code the administrator did not type. The uniqueness check
runs on the normalised value, so two codes that differ only in their separators collide with a message
naming a string that was never entered.

They also disagree about runs: the dialog's own slug generator collapses repeated separators
(`tenant-dialog.ts:86-90`) while `normalizeCode` does not, so `Acme  Corp` suggests `acme-corp` and,
if typed rather than generated, stores `acme--corp`.

### 12.9 The tenant-code hint warns about a consequence that cannot happen

`tenant-dialog.ts:30-32`, shown when editing: "Changing the code does not move any data, but anything
referring to the old code stops matching."

A grep for `tenantCode` / `tenant_code` across `process/src/main/java` returns five call sites, all
inside `TenantServiceImpl` and `TenantRepository.findByTenantCode`, plus
`TenantRequestServiceImpl:148`. Every one of them is the uniqueness lookup at create or update time.
Nothing in the product resolves a job, a bucket, a task, a Kafka route or a storage alias by tenant
code; the new frontend uses it for display and search only (`tenants.html:94`, `:153`,
`tenants.ts:148`).

The hint is a false warning. It is worth fixing rather than ignoring, because it will deter somebody
from correcting a typo in a code that appears on screen.

### 12.10 A plain tenant user can fetch their whole tenant's roster

`/admin/users` is `TENANT_ADMIN` at every layer. But `dashboard.json/userStatistics`, the endpoint that
backs its Workload column, sits on `DashboardRestApi` whose class annotation is
`hasRole('TENANT_USER')` (`:19`), and the method carries no override (`:43-53`).

The rows it returns are not just counts. `DashboardServiceImpl:76-88` maps `app_user_id`, `username`,
`full_name`, `user_role`, `status`, `avatar_bucket` and `avatar_key` alongside the six figures, and the
SQL selects exactly those columns for every non-deleted user in the caller's tenant
(`QueryService:276-291`). Any `TENANT_USER` with a valid token can therefore enumerate every colleague,
their sign-in address and their role.

It is tenant-scoped -- `tenantClause("u")` (`:212-217`) -- and `UserStatisticsQueryTest` pins that
scoping, so the isolation is deliberate and holds. What is not obviously deliberate is the role: the
screen that shows this data is admin-only while the endpoint behind it is not. Recorded as a finding
rather than a hole, because reasonable people will disagree about whether a colleague list is
privileged; but the two should agree, whichever way it is settled.

Note also that `tenantClause` returns an empty string when the caller's tenant is null (`:213`), so a
tenant-less token gets the statistics for **every user in the installation**.

### 12.11 A `TENANT_ADMIN` token with no tenant claim appears to reach the platform-owned rows

`listUsers` (`AppUserServiceImpl:127-132`) sends `TenantContext.getTenantId()` -- which may be null --
straight into the derived query `findByTenantIdAndStatusNotOrderByAppUserIdDesc`. Spring Data JPA
translates a null argument to a `SIMPLE_PROPERTY` part into `IS NULL` rather than `= ?`, so the query
becomes `where tenant_id is null and status <> 'Delete'` -- which is precisely the set of platform
admins, including the seeded one (`TenantSeedService:113-126`).

`addUser` has the matching shape: for a non-platform actor the target tenant is
`TenantContext.getTenantId()` unconditionally (`:173-176`), and the existence check at `:177` is
skipped when that is null -- so the same token would create a tenant-less `TENANT_USER`.

This is the exact failure mode this codebase has already fixed twice elsewhere. `readAvatar` was
changed to ask `TenantOwnership.isOwnedByCaller` for it, with the reason written at `:112-116`
("a caller carrying no tenant of its own matched a platform admin's tenant-less row, because null
equals null"), and `AppUserServiceImplFailClosedTest` and `StorageConnectionTenantlessCallerTest` both
exist for it. `listUsers` and `addUser` were not given the same treatment.

**Not fully verified.** The Spring Data null-to-`IS NULL` translation is asserted from the framework's
documented behaviour for derived queries, not from a run against this application. What I checked:
`AppUserRepository.java:18` (the derived method), `AppUserServiceImpl:127-132` and `:173-176` (no null
guard on either), and `UserManagementE2EIT` (which covers the cross-tenant case at `:169-183` and the
create case at `:185-205`, but has no tenant-less-token case). Confirming it takes one E2E test:
mint a `TENANT_ADMIN` token with a null `tenantId` claim, call `listUsers`, and assert the payload is
empty -- with a positive control on the same token carrying a real tenant. That test belongs in
Execution whichever way it comes out.

### 12.12 Deactivating a user or suspending a tenant does not end a session already open

`AuthServiceImpl.checkAccountAndTenantActive` (`:101-112`) is consulted from `login` (`:60-63`) and
`refresh` (`:93-95`). Nothing consults it per request: `JwtAuthenticationFilter:38-47` parses the
token, reads the claims and builds the authority without touching the database.

Access tokens last thirty minutes by default (`JwtUtil:28-29`). So an administrator who deactivates a
compromised account, or suspends a defaulting tenant, has done nothing to the sessions already
running -- for up to half an hour those users keep working, and their writes keep landing. The
confirmation text says the person "will be signed out" (`users.ts:304`), which is not what happens.

There is no token blacklist and no server-side session store, so this cannot be fixed by a small
change; it is recorded here so that the confirmation wording, at minimum, stops over-promising.

### 12.13 "Only mine" hides every row that predates the audit columns, and its counter never appears

`created_by` was added by `V22.0-audit-columns/V22__audit_columns.sql:36-40` and is nullable on
purpose. `isMine` (`shared/ui/mine-filter.ts:47-49`) is `myId != null && row.createdBy === myId`, so
every row written before that migration fails it. On an installation upgraded rather than freshly
seeded, turning on Only mine can empty both lists even for the person who created everything on them.

Separately, `MineFilter` declares a `hidden` model that renders "(N hidden)" beside the label
(`:30-32`, `:41`), and neither screen binds it (`tenants.html:61`, `users.html:77`). The one affordance
that would explain the empty list is present in the component and unused on both screens that use it.

### 12.14 `listUsers` loads every user in the installation into memory for a platform admin

`AppUserServiceImpl:128-131` is `findAll().stream().filter(u -> u.getStatus() != Status.Delete)`. The
repository has no `findByStatusNot`, so the filter runs in Java over every row ever created, deleted
ones included. There is no paging on either the endpoint or the query.

At current data volumes this is invisible. It is recorded because the fix is a one-line repository
method (`findByStatusNotOrderByAppUserIdDesc`) that mirrors the one already used for the tenant branch,
and because the same call is made every time the users screen refreshes -- which it does after every
create, edit, status change and delete.

`listTenants` has a related shape: `mapToDtoWithStats` (`TenantServiceImpl:72-82`) issues six count
queries **per tenant row**, so listing fifty tenants costs three hundred and one queries plus the name
resolution.

### 12.15 The users list issues one avatar request per rendered row

`users.html:105-106` (cards) and `:311-312` (table) render `<app-avatar [appUserId]>`, and `Avatar`
fires its own authenticated `GET /appUser.json/avatar` per instance (`shared/ui/avatar.ts:57-78`). At
the default page size of 50 that is fifty requests on every render, each of which reaches
`readAvatar`, which does a `findById` and then a storage read.

Most of them 404 -- most people have no picture, which the endpoint treats as a normal outcome
(`AppUserRestApi:116-119`). The component is careful about blob URLs and revokes them on destroy, so
this is a request-count problem rather than a leak.

### 12.16 A focused tenant and the tenant dropdown can contradict each other

`users.ts:140-142` applies `focusedTenantId` (from `?tenantId`) and `tenantFilter` (from the dropdown)
as two independent predicates. Arriving from a tenant card and then choosing a different tenant in the
dropdown produces an empty list with two active filters and no explanation -- the banner says one
tenant, the dropdown says another. The dropdown is still rendered while focused
(`users.html:57-65`), so the state is reachable in two clicks.

### 12.17 The end-to-end suites for this feature are not run by the build

`UserManagementE2EIT.java` (659 lines) and `TenantLifecycleE2EIT.java` (390 lines) between them cover
almost every refusal in section 11 over the real filter chain. `process/pom.xml` declares no
`maven-failsafe-plugin`, and Surefire's default includes do not match `*IT.java`, so neither runs
under `mvn test` or `mvn verify`. They also require a live Postgres on 5433 with credentials from the
environment (`src/test/resources/application-e2e.properties`).

The unit tests that *do* run (`AppUserServiceImplRoleScopeTest`, `AppUserServiceImplFailClosedTest`)
call the service directly and therefore cannot see the controller annotations -- which is exactly the
layer the E2E suites exist to cover, and exactly where a `@PreAuthorize` that a method-level
annotation quietly replaced would go unnoticed.

### 12.18 A tenant with no users offers no route to its first user

`tenants.html:210` and `:118` disable the Users action when `userCount` is zero, with the title "This
tenant has no users yet." That is the one tenant for which an administrator most needs to reach the
users screen. The workaround -- open `/admin/users`, click New user, pick the tenant from the dropdown
-- exists but is not signposted, and the tenant card is where the operator is standing when they
realise they need it.

### 12.19 Setting a tenant `Inactive` from the dialog locks its users out with no warning

The tenant dialog offers three statuses and labels them "Active", "Suspended — sign-in blocked" and
"Inactive — not in use" (`tenant-dialog.ts:41-44`), with a hint that mentions only suspension:
"Suspending a tenant stops its users signing in; its data is kept." (`:39`).

`AuthServiceImpl:105-110` refuses sign-in when the tenant's status is anything other than `Active`, and
returns the same "Your organization's access is currently suspended" message for both. `Inactive` is
therefore a synonym for `Suspended` at the only place either is consulted, while the dialog presents it
as the milder, administrative option. The status filter and the pills carry the same distinction
(`tenants.html:40-42`, `status-pill.ts:58-59` gives both the `warn` tone), so nothing on the screen
corrects the impression.

---

## 13. Missing functionality

**No way to see or restore a deleted tenant or user.** `listTenants` excludes `Delete`
(`TenantServiceImpl:66`), `listUsers` excludes it (`AppUserServiceImpl:130`, `:132`), and `scopedFind`
refuses a `Delete` row outright (`:377-379`) -- so even a platform admin cannot reach one to change its
status back. Deletion is a soft delete in the schema and a hard delete in practice. Closing this needs
either a "show deleted" filter on both lists plus a restore action, or an explicit statement in both
confirmations that the step cannot be undone from the console. The second is a template change; the
first needs a repository method, a service branch and a control on each screen.

**No dependency check before deleting a tenant.** Storage connections refuse deletion while a Kafka
profile binds them, and the new console warns by name (`features/admin/storage/kafka-dependents.ts`).
Deleting a tenant that owns forty jobs succeeds silently; the jobs keep running on a schedule while
their owner has ceased to exist. The confirmation counts the resources (`tenants.ts:239-251`) but
nothing refuses, and nothing stops or reassigns the jobs. This is the largest genuine gap in the
feature.

**No password-reset notification.** `resetPassword` sets `mustChangePassword` and returns; the account
owner learns nothing. `EmailMessagesFactory` already sends a welcome mail with a temporary password
(`:145`), so the template and the plumbing exist; a reset mail is a second factory method and one call.

**No way to resend a welcome.** When `addUser`'s mail fails, the response tells the administrator to
reset the password and pass it on another way (`AppUserServiceImpl:203-217`). There is no "resend
invitation" action, so the only recovery is to overwrite the password.

**No user-visible record of administrative action.** `AuditListener` stamps `updated_by` on every save,
so the list can say who last edited a row -- but a password reset, a deactivation and a name change all
look identical afterwards. There is no event log for this feature. `job_audit_logs` exists for runs;
nothing equivalent exists for accounts.

**No export.** Jobs and tasks both have download-list endpoints (`sourceJob.json/downloadListSourceJob`,
`sourceTask.json/downloadListSourceTask`). Neither the user list nor the tenant list has one, so an
operator asked for "everyone with access, as a spreadsheet" has to read it off the screen.

**No bulk actions on users.** The storage screen grew multi-select and "Test selected"; users has no
select column. Deactivating a departing team of six is six confirmations. The old app had none either,
so this is an absence rather than a loss.

**No server-side paging or filtering on either list.** Both endpoints return everything and both
screens filter, sort and page in the browser (`users.ts:134-166`, `tenants.ts:142-151`). The tenants
screen has no pager at all, so a platform installation with a few hundred tenants renders every card.

**No session revocation**, which is the other half of 12.12. Deactivating an account cannot end its
current session because there is nothing to end it in: tokens are stateless and there is no blacklist.

**No moving a user between workspaces from the console.** `updateUser` supports it
(`AppUserServiceImpl:295-296`) and the old app exposed it (`users.component.ts:144`); the new dialog
locks the control (`user-dialog.ts:103-104`). Restoring it means unlocking the select for a platform
admin and confirming the consequence; leaving it locked means the capability is API-only. Either is
defensible and the choice is taken in the synthesis.

**No spec coverage for the tenants screen or either dialog.** The one frontend spec for this feature
covers `canManage` and the role picker (`user-management-scope.spec.ts`, 7 tests). Nothing covers the
filters, the sort, the pager, `quietSummary`, `shareOf`, or the submit path of either dialog -- which
is where 12.1, 12.2 and 12.8 live.
