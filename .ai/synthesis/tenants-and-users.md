# Synthesis -- Tenants and Users

Feature 16. Inputs read: `.ai/discovery/features.md`, `frontend.md`, `frontend-old.md`, `backend.md`,
`database.md`; `.ai/grooming/tenants-and-users.md`; the real code in `scheduler1/src/app/_component/{tenants,users}/`,
`scheduler1/next/src/app/features/admin/{tenants,users}/`, `process/src/main/java/process/api/{TenantRestApi,AppUserRestApi,DashboardRestApi}.java`
and `process/src/main/java/process/model/service/impl/{TenantServiceImpl,AppUserServiceImpl}.java`;
the tests in `process/src/test/java/process/` and `scheduler1/next/src/app/features/admin/users/user-management-scope.spec.ts`.
There are no QA findings for this feature yet -- `.ai/qa/` holds only its README.

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

The rewrite of this feature went well. The authorization rules are the strongest in the product --
`scopedFind` is a single ownership gate for all four write paths, `refusalFor` gets the wording right,
`canManage` and the filtered role picker make the console agree with the server, and there are two
end-to-end suites covering nearly every refusal. Nothing was dropped that anybody will miss badly. The
work that remains is of a different kind: **the two dialogs offer controls the server discards, and one
regression made a password visible on screen.**

Four things have to be fixed because they are wrong rather than merely absent. The Status select in the
user dialog does nothing on either create or edit. The email field is editable on edit and the change
is thrown away. The reset-password prompt renders an unmasked text input, where the old app used
`type="password"`. And the button that opens it claims to send the password to the user, which nothing
does. After those, one server-side check is missing -- `addUser` never length-checks a typed password --
and one probable authorization hole wants confirming: a `TENANT_ADMIN` token carrying no tenant claim
appears to receive the platform admins from `listUsers`, which is the same fall-open this codebase has
already fixed twice elsewhere.

Everything else is smaller: a code pattern the client and server disagree about, a hint that warns
about a consequence that cannot happen, an `Inactive` tenant status that blocks sign-in without saying
so, a handful of narrowed filters, and one genuinely dropped capability -- a platform admin can no
longer move a user between tenants from the console, though the API still supports it. The two E2E
suites that would catch a regression in any of this do not run in the build, and wiring them in is the
single highest-value item in the list.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | The user dialog's Status select is posted and discarded -- `addUser` forces `Active` (`AppUserServiceImpl:198`), `updateUser` never writes it (`:308-312`) | A control that is offered takes effect, or is not offered | Two silent no-ops presented as working controls | Drop Status from the create form; honour it on update, inside `scopedFind` and behind the same self-protection `changeUserStatus` has | S | Touches a write path guarded by `scopedFind`; needs the self-deactivation refusal duplicated or shared, or an admin can lock themselves out through the dialog |
| 2 | Email is editable on edit and never written (`user-dialog.ts:93`, `AppUserServiceImpl:308-312`) | Either the change lands, or the field is read-only | A discarded write that looks like a caching bug | Make the field read-only on edit, as the old app did | S | None -- removes a capability nobody has today |
| 3 | The reset-password prompt is a plain text input (`prompt-dialog.ts:21-23`); the old app masked it | The password is masked while typed | A credential rendered in cleartext on a shared screen | Give `PromptDialog` an optional `type`, pass `'password'` from `users.ts` | S | `PromptDialog` is shared with the object browser; adding an optional input with a default of `text` cannot change those call sites |
| 4 | "Send a new one-time password" on the Reset button (`users.html:243`); nothing is sent (`AppUserServiceImpl:338-359`) | The interface says what happens | An administrator resets a password and tells nobody | Reword to the old app's sentence; separately consider actually sending one (row 22) | S | None |
| 5 | `addUser` accepts any typed password; `validateNewPassword` is not called on that path (`:186-187` vs `:344`, `:611`) | One length rule wherever a password is set | Client-only validation on a credential | Call `validateNewPassword` in `addUser` before encoding | S | A fixture or script that creates users with short passwords starts failing -- which is the point |
| 6 | "Must be an email" is `Validators.email` only (`user-dialog.ts:93`); the server checks non-empty and unique | Server-side shape check | A malformed username produces an account whose welcome mail goes nowhere | Add a shape check in `addUser` beside the uniqueness check | S | Rejects existing malformed usernames only on re-creation, never on read |
| 7 | `position` has no length limit in the form; the column is `VARCHAR(120)` (`V20__user_position.sql:6`) | A too-long title is a field error, not a 500 | Generic 500 for a typing mistake | `Validators.maxLength(120)` plus `maxlength` on the input; a server-side trim-or-refuse in `addUser`/`updateUser` | S | None |
| 8 | The dialog allows `.` and `_` in a tenant code (`tenant-dialog.ts:65`); `normalizeCode` rewrites them to `-` (`TenantServiceImpl:152`) | What was typed is what is stored, or the field says no first | A code appears in the list that nobody typed | Narrow the client pattern to `^[a-z0-9]+(-[a-z0-9]+)*$` and make `normalizeCode` collapse runs so the two agree | S | Changes what `addTenant` accepts; existing rows are untouched, and the uniqueness check runs on the same normalised value it does today |
| 9 | The code hint warns "anything referring to the old code stops matching" (`tenant-dialog.ts:30-32`); nothing refers to it | The hint describes reality | A false warning that deters a legitimate correction | Reword: the code is a label, changing it affects nothing but the label | S | None |
| 10 | `Inactive` is offered as the milder tenant status (`tenant-dialog.ts:41-44`) while `AuthServiceImpl:105-110` blocks sign-in for it exactly as for `Suspended` | The dialog says what a status does | A workspace locked out by an option labelled "not in use" | Remove `Inactive` from the dialog's options and keep it in the enum for existing rows; extend the hint to name both | S | Any tenant already at `Inactive` still lists and filters; only the *setting* of it moves out of reach |
| 11 | `listUsers` passes a possibly-null tenant into a derived query (`AppUserServiceImpl:127-132`); `addUser` uses the same null unconditionally (`:173-176`) | A caller with no tenant owns nothing | Probable: a tenant-less `TENANT_ADMIN` token receives the platform admins and can create tenant-less users | Add the explicit guard `TenantOwnership` already states, and an E2E case for the tenant-less token | S | **Authorization.** Four layers: the guard and the annotation are unaffected; the service rule changes; there is no Hibernate filter on `AppUser` to fall back on (`TenantFilterDeclarationTest:47-48`) |
| 12 | `dashboard.json/userStatistics` is `TENANT_USER` (`DashboardRestApi:19,43`) and returns username, full name, role and status for every user in the tenant | The endpoint matches the only screen that calls it, which is `TENANT_ADMIN` | Any tenant user can enumerate their colleagues | Add `@PreAuthorize("hasRole('TENANT_ADMIN')")` on the method; it has exactly one caller (`users.ts:222`) | S | **Authorization.** A method-level annotation *replaces* the class-level one, which is the intent here; verify no other screen breaks -- a grep of both frontends returns one hit |
| 13 | The deactivate confirmation says the person "will be signed out" (`users.ts:304`); their token stays valid for up to 30 minutes (`JwtUtil:28-29`) | The interface does not over-promise | A false assurance during an incident | Reword the confirmation to say sign-in is blocked and an open session ends within the token's life | S | None. Real revocation is out of scope -- see section 5 |
| 14 | Search matches a fixed substring set; the old app's pipe reached every field with field paths and negation (`_helpers/search-filter.ts:40-102`) | Searching for a role or a status finds the rows | Two useful matches lost on the users screen, one on tenants | Add `userRole` and `status` to the users match set; add `status` to the tenants one | S | Widening a match set can only add rows to a filtered view |
| 15 | A platform admin cannot move a user between tenants; the old app could (`users.component.ts:144`), and `updateUser` still supports it (`:295-296`) | An explicit decision, either way | A capability lost by a source comment rather than by a decision | **Keep it dropped.** Record it here and leave the field's hint as the user-facing statement | -- | None. Reversing later is unlocking one control |
| 16 | Roll-up totals for buckets, Kafka profiles and task types are gone from the tenants tiles (`tenants.component.html:22-42` → `tenants.html:19-28`) | An explicit decision | Three estate-wide totals lost | **Keep them dropped.** The per-tenant figures survive in the table view, and the tiles were replaced by two that carry more (`active`, `unused`) | -- | None |
| 17 | No link back to Tenants from a tenant-focused user list (old: `users.component.html:1-7`) | A way back | One extra click through the nav | Make the focus banner's tenant name a link to `/admin/tenants` | S | None |
| 18 | The Users action is disabled on a tenant with no users (`tenants.html:210`, `:118`) -- the tenant that most needs it | A route to the first user | An operator dead-ends on the tenant card | Keep it enabled and let the empty state do the work; the users screen already offers **New user** | S | None -- the destination handles an empty list correctly |
| 19 | "Only mine" hides every row created before `V22` (`isMine`, `mine-filter.ts:47-49`); the "(N hidden)" counter is never bound (`tenants.html:61`, `users.html:77`) | An empty result is explained | A filter that silently empties the list on an upgraded installation | Bind `hidden` on both screens | S | None. The underlying null `created_by` is correct and stays |
| 20 | `focusedTenantId` and `tenantFilter` apply as independent predicates (`users.ts:140-142`) | They cannot contradict each other | An empty list with two filters and no explanation | Hide the tenant dropdown while a focus is active | S | None |
| 21 | `UserManagementE2EIT` and `TenantLifecycleE2EIT` are not run: no failsafe plugin in `process/pom.xml`, and Surefire's defaults exclude `*IT.java` | The suites that cover the refusals run | Roughly a thousand lines of authorization coverage that never executes | Bind `maven-failsafe-plugin` to a profile that needs the database, and run that profile where one exists | M | The suites need Postgres on 5433 with credentials from the environment (`application-e2e.properties`); binding them to the default build would break it everywhere else |
| 22 | Deleting a tenant with live jobs succeeds silently; there is no way to see or restore a deleted tenant or user | Deletion is either refused while dependents exist, or plainly one-way | The largest genuine gap: orphaned scheduled work behind an unreachable tenant | Refuse `changeTenantStatus(Delete)` while the tenant owns an `Active` source job, naming the count -- the storage-connection precedent; and state in both delete confirmations that the step cannot be undone from the console | M | **Changes a write path a platform admin relies on.** A tenant that genuinely has to go now needs its jobs deactivated first, which is the intent |
| 23 | `listUsers` is `findAll()` filtered in Java (`:128-131`); `listTenants` issues six count queries per row (`TenantServiceImpl:72-82`) | Bounded work per request | Invisible today, quadratic in tenants | Add `findByStatusNotOrderByAppUserIdDesc` to mirror the tenant branch; leave the counts alone for now | S | None -- the repository method is the same shape as the one beside it |
| 24 | One avatar request per rendered row (`users.html:105-106`, `:311-312`; `avatar.ts:57-78`) | A page of fifty does not cost fifty requests | Fifty mostly-404 round trips per render | **Defer.** `Avatar` is shared and correct; a batch endpoint is a bigger change than this feature warrants | -- | Deferring risks nothing; the requests are cached for 300s by the endpoint (`AppUserRestApi:123`) |

---

## 3. Solution detail

### Row 1 -- the Status control

**What changes.** `user-dialog.html:90-95` becomes conditional on `!isEdit()` being false -- that is,
the Status field renders only when editing. `AppUserServiceImpl.updateUser` gains, after the tenant
resolution and before the writes at `:308-312`:

```
if (!isNull(appUserDto.getStatus()) && appUserDto.getStatus() != user.getStatus()) {
    if (user.getAppUserId().equals(TenantContext.getAppUserId()) && appUserDto.getStatus() != Status.Active) {
        return new ResponseDto(ERROR, "You cannot deactivate your own account.");
    }
    user.setStatus(appUserDto.getStatus());
}
```

The self-protection is the same sentence `changeUserStatus:328-330` already returns, and it has to be
repeated here rather than assumed: without it the dialog becomes a second, unguarded route to the
thing the row toggle carefully refuses.

**Why this shape rather than the alternatives.** Two other options were considered.

*Remove the control from both create and edit.* This is smaller and it is what the old app did --
status was only ever the row toggle. It was rejected because the toggle is a two-state flip and the
dialog is where an administrator is already standing when they are correcting a row; making them close
the dialog to change one more field is worse than the small amount of service code above.

*Honour it on create too.* Rejected. A user created `Inactive` still gets a welcome email with a
working password and a link to a sign-in that will refuse them (`AppUserServiceImpl:203-217` runs
unconditionally). Honouring the field on create means either suppressing that mail or sending a
misleading one, and neither is a decision this row should be making. Create makes an active account;
deactivating it is a second, deliberate step.

### Row 2 -- the email field

**What changes.** `user-dialog.html:44-49` gains `[readonly]="isEdit()"` and the hint changes to say
the address is the sign-in identity and is fixed. Nothing on the server changes.

**Why not make it editable.** The obvious fix -- have `updateUser` write the username -- is the wrong
one, and it is worth writing down why so it is not proposed again. `username` is `unique` at the column
level (`AppUser.java:63`), so a rename needs the same `findByUsernameAndStatusNot` check `addUser`
already does. It is also the JWT subject (`JwtUtil:45`), which means every token already issued to that
person names an address that no longer exists -- `refresh` looks the user up by
`claims.getSubject()` (`AuthServiceImpl:87`), so their session dies at the next refresh with
"Account no longer active", which is both wrong and alarming. And it is the address the welcome mail
went to, so support conversations stop matching. Making it editable is a real piece of work with a
session-invalidation story attached; making it read-only is one attribute and restores the old app's
behaviour exactly. If somebody genuinely needs to change an address, deleting and recreating the
account is the honest path today.

### Row 3 -- the masked password field

**What changes.** `features/objects/dialogs/prompt-dialog.ts` gains `type?: 'text' | 'password'` on
`PromptOptions` and binds `[type]="data.type || 'text'"` on the input. `users.ts:342-352` passes
`type: 'password'`. The `autocomplete="new-password"` attribute goes on at the same time.

**Why not a dedicated dialog.** Writing a `ResetPasswordDialog` for this one screen was the first
instinct, and it was rejected: `PromptDialog` is already the right shape -- one labelled field, a hint,
a confirm label -- and the only thing wrong with it is a missing attribute. A second dialog would
duplicate the layout and give the two a chance to drift. The optional input defaults to `text`, so the
object browser's three call sites are untouched.

While in there: `PromptDialog.submit` trims (`:44-45`), which silently alters a password with a
leading or trailing space. Trimming is right for a folder name and wrong for a credential, so the trim
should apply to the *guard* (`if (!trimmed) return`) and the untrimmed value should be what closes the
dialog.

### Row 5 -- the missing length check on `addUser`

**What changes.** One call, in `addUser` between the phone normalisation and the role rules:

```
if (!isNull(appUserDto.getPassword()) && !appUserDto.getPassword().trim().isEmpty()) {
    ResponseDto weakPassword = validateNewPassword(appUserDto.getPassword());
    if (weakPassword != null) { return weakPassword; }
}
```

The guard is necessary: a blank password is the *good* path here, and `validateNewPassword` refuses
null.

**Why not a broader password policy.** The temptation is to take the opportunity and add complexity
rules -- upper, digit, symbol. Rejected: `validateNewPassword`'s own comment
(`AppUserServiceImpl:361-367`) records that it exists so that the path a person chooses for themselves
and the path an administrator imposes are held to the *same* rule. Adding a rule here and not in
`changeOwnPassword` recreates exactly the asymmetry it was written to remove, and adding it to both is
a product decision about every existing account, not a bug fix.

### Row 11 -- the tenant-less caller

**What changes.** `listUsers` and `addUser` stop trusting a null tenant.

```
// listUsers
if (!TenantContext.isPlatformAdmin() && isNull(TenantContext.getTenantId())) {
    return new ResponseDto(SUCCESS, "Users fetched successfully.", Collections.emptyList());
}
```

```
// addUser, in the else branch at :173-176
targetTenantId = TenantContext.getTenantId();
if (isNull(targetTenantId)) {
    return new ResponseDto(ERROR, "No tenant in context.");
}
```

Plus the E2E case the grooming document specifies: a `TENANT_ADMIN` token with a null `tenantId` claim
gets an empty list, with a positive control on the same token carrying a real tenant.

**Why a hand-written guard rather than routing through `TenantOwnership`.** `TenantOwnership`
(`process/src/main/java/process/security/TenantOwnership.java`) answers "may this caller act on a row
owned by X" -- it takes an owner id, and `listUsers` has no row yet. Calling it per row after the query
would work but would still have issued the query, and the query is the problem: it returns the platform
admins. The guard has to come before it. The rule being applied is `TenantOwnership`'s, stated at
`:14-16` ("a context with no tenant owns nothing"), and the comment on the guard should say so and
point at it, so the two do not drift.

**Why not add a Hibernate filter to `AppUser` instead.** That is the shape that would make this class
of bug impossible, and it is firmly rejected. `TenantFilterDeclarationTest:38-45` names the two paths
that read `AppUser` outside the caller's tenant and must keep working: the sign-in lookup, which runs
before there is a tenant at all, and `UserNameResolver`, which turns a `created_by` id into a display
name for rows a neighbouring tenant authored. Declaring the filter breaks both, and the test exists to
stop somebody doing it in good faith.

**Verify before fixing.** The grooming document marks the Spring Data null-to-`IS NULL` translation as
the unverified link. Execution should run the E2E case first and record what it returns; the guard is
worth adding whichever way it comes out -- it costs two lines and states a rule this codebase already
holds everywhere else -- but the severity of the finding depends on the answer.

### Row 12 -- `userStatistics`

**What changes.** One annotation on `DashboardRestApi.userStatistics`:

```
@PreAuthorize("hasRole('TENANT_ADMIN')")
```

**Why that is safe here.** `@PreAuthorize` is not repeatable, so this *replaces* the class's
`hasRole('TENANT_USER')` rather than adding to it -- which is exactly the intent, and is the same
mechanism `AppUserRestApi` already uses in the other direction at `:92`, `:111`, `:131`, `:147`,
`:163`. A grep of both frontends for `userStatistics` returns exactly one call site,
`features/admin/users/users.ts:222`, on a screen already gated at `TENANT_ADMIN`. Nothing else breaks.

**Why not narrow the payload instead.** Dropping `username`, `full_name`, `user_role`, `status`,
`avatar_bucket` and `avatar_key` from the SQL (`QueryService:276-291`) would leave the endpoint
harmless at `TENANT_USER` and would still serve the users screen, which reads only the id and the six
counts (`users.ts:27-36`). It was rejected because it leaves the endpoint's *name* and *shape*
promising per-user statistics to a role that has no business asking for them, and because a future
caller would add the columns back. The role is the honest fix; the columns can stay.

Note the second half of the finding: `tenantClause` (`QueryService:212-217`) returns an empty string
when the caller's tenant is null, so a tenant-less token gets every user in the installation. That is
the same defect as row 11 in a different service, and the same guard applies -- but it belongs to the
`dashboard` feature's own grooming, not this one. Flagged here, fixed there.

### Row 22 -- deleting a tenant

**What changes.** `TenantServiceImpl.changeTenantStatus` gains a dependency check when the incoming
status is `Delete`:

```
if (tenantDto.getStatus() == TenantStatus.Delete) {
    long activeJobs = this.sourceJobRepository.countByTenantIdAndJobStatus(tenantId, Status.Active);
    if (activeJobs > 0) {
        return new ResponseDto(ERROR, String.format(
            "%s still has %d active job(s). Suspend the tenant, or deactivate its jobs, first.",
            tenant.getTenantName(), activeJobs));
    }
}
```

`countByTenantIdAndJobStatus` needs adding beside the existing `countByTenantIdAndJobStatusNot`. On the
frontend, both delete confirmations (`tenants.ts:239-251`, `users.ts:313-322`) gain a sentence saying
the step cannot be undone from the console -- because it cannot: `listTenants:66` and
`listUsers:130,132` exclude `Delete`, and `scopedFind:377-379` refuses a `Delete` row outright, so
there is no path back even for a platform admin.

**Why refuse rather than cascade.** The alternative -- delete the tenant and deactivate its jobs in the
same transaction -- was rejected on the same reasoning the storage-connection delete uses. A cascade
makes one click destroy work in six other tables, and the operator finds out what happened afterwards.
A refusal that names the count makes the operator do the deactivation deliberately, on the screen where
it belongs, and leaves the tenant recoverable until they do.

**Why active jobs and not all six resource counts.** Jobs are the only one of the six that *acts*: a
scheduled job belonging to a deleted tenant keeps dispatching. Tasks, task types, buckets and Kafka
profiles are inert configuration and blocking on them would make deletion practically impossible.

**Why not build the restore path now.** A "show deleted" filter plus a restore action on both screens
is a genuinely useful feature and roughly a day of work across two services and two screens. It is
deferred in favour of the honest confirmation, because the confirmation is a template change that stops
somebody deleting a tenant *believing* it is reversible, and that is where the harm is.

### Row 21 -- running the E2E suites

**What changes.** A `maven-failsafe-plugin` binding inside a profile:

```xml
<profile>
  <id>e2e</id>
  <build><plugins><plugin>
    <artifactId>maven-failsafe-plugin</artifactId>
    <executions><execution><goals>
      <goal>integration-test</goal><goal>verify</goal>
    </goals></execution></executions>
  </plugin></plugins></build>
</profile>
```

**Why a profile rather than the default build.** `E2ESupport` boots the whole application against a
real Postgres on 5433 with credentials from the environment
(`src/test/resources/application-e2e.properties`). Binding failsafe unconditionally makes `mvn verify`
fail on every machine without that database, which is the fastest way to get the suites disabled again.
A profile keeps `mvn test` working everywhere and gives CI -- which has a database -- one flag to pass.

**Why this is worth doing before the behavioural fixes.** Rows 1, 11 and 12 all change authorization or
a write path, and the suites are what would notice if one of them moved a boundary. Running them first
means the fixes land against a working net rather than beside a dormant one.

### Rows 4, 9, 10, 13 -- the four wording fixes

These are grouped because they are the same class of change and each is a few words.

- **Row 4:** `users.html:243` becomes the old app's honest sentence -- the user is not notified, share
  the password yourself.
- **Row 9:** `tenant-dialog.ts:30-32` stops warning about references that do not exist. The code is a
  label; it is shown on this screen and matched on in search, and nothing else reads it. Verified by
  grep: five call sites in `process/src/main/java`, all uniqueness lookups.
- **Row 10:** `Inactive` leaves the dialog's option list (`tenant-dialog.ts:41-44`) and the hint names
  the real consequence. It stays in `TenantStatus`, stays in the status filter and stays rendered on
  any row that already has it, because existing data must keep listing.
- **Row 13:** the deactivate confirmation (`users.ts:302-305`) stops saying "will be signed out". Say
  that sign-in is blocked immediately and an open session ends when its token expires.

**Why wording changes are in the plan at all**, rather than being left as cosmetic: each of these four
causes a person to make a wrong decision. An administrator who believes a password was sent does not
send it. One who believes a code change breaks references does not fix a typo. One who picks "not in
use" locks a workspace out. One who believes a deactivation signed somebody out stops looking during an
incident.

---

## 4. Ordering

**First, and independently: row 21.** Bind failsafe to a profile and get `UserManagementE2EIT` and
`TenantLifecycleE2EIT` running somewhere. Nothing else in this plan changes; everything else lands more
safely afterwards.

**Then the authorization pair, 11 and 12**, in that order. Row 11 needs its E2E case written before its
guard, so that the finding is confirmed rather than assumed. Row 12 is one annotation and should be
verified by the same suite: a `TENANT_USER` calling `userStatistics` must move from 200 to 403, and a
`TENANT_ADMIN` must stay at 200.

**Then the four discarded-or-unsafe controls: 1, 2, 3, 5.** Rows 2, 3 and 5 are independent of each
other and of everything else. Row 1 touches `updateUser`, so it should land after row 11's guard rather
than at the same time -- two changes to one method in one pass is how a self-protection check gets lost.

**Then the remaining server-side validation, 6 and 7**, and the tenant-code agreement, 8. Row 8 changes
what `addTenant` accepts, so it wants the tenant E2E suite running -- which row 21 provides.

**Then rows 22 and 10 together.** Both are about what a tenant status means, both touch
`TenantServiceImpl` and the tenant dialog, and doing them in one pass keeps the dialog's copy and the
service's refusals consistent.

**Then the console polish, in any order: 4, 13, 14, 17, 18, 19, 20, 23.** None blocks another; all are
single-file changes.

**Unblocked by all of it:** the deferred work in section 5. None of it depends on anything above.

---

## 5. Out of scope

**Session revocation.** Row 13 rewords the confirmation; it does not make deactivation immediate.
Doing that means a token blacklist or a per-request account check, which is a change to
`JwtAuthenticationFilter` affecting every endpoint in the product and adding a database read to each
one. It is an `authentication-and-access` decision, not this feature's, and it wants its own grooming.

**Restoring a deleted tenant or user.** Deferred in favour of an honest confirmation (row 22). The
restore path needs a "show deleted" filter, two repository methods, a service branch that
`scopedFind` currently refuses outright, and a restore control on both screens -- and it needs a
decision about whether restoring a user whose email has since been reused is even possible. Worth
doing; not worth doing inside a bug-fix pass.

**A password-reset notification.** `EmailMessagesFactory` already sends a welcome mail with a
temporary password (`:145`), so the plumbing exists and a reset mail is one factory method and one
call. It is left out because row 4 makes the interface honest about the current behaviour, and adding
the mail afterwards is a clean, separately testable change rather than something bundled into a
wording fix.

**Batching avatar requests** (row 24). `Avatar` is shared with the profile screen, the shell and the
job assistant; a batch endpoint would change all of them. The endpoint already sets
`Cache-Control: private, max-age=300` (`AppUserRestApi:123`), so a page revisited inside five minutes
costs nothing.

**Restoring the old `SearchFilterPipe`.** Row 14 adds two fields to a substring match rather than
porting the old pipe's field paths, negation and quoted phrases (`_helpers/search-filter.ts:40-102`).
The pipe is genuinely more capable, and it was rejected because it is a shared concern across nineteen
list screens in the new app, not a property of this one. If it comes back it should come back once, in
`shared/ui/`, for every screen -- and that is a decision for whoever owns the shared list chrome.

**Server-side paging on either list.** Both endpoints return everything. At the current data volumes
this costs nothing visible, and adding it means changing the response envelope, which every list
screen in the product shares. Row 23 takes the one-line repository fix and leaves the shape alone.

**The six-count-per-tenant query pattern** (`TenantServiceImpl:72-82`). A single grouped query would
replace three hundred round trips at fifty tenants. Left alone because it is invisible at the current
scale and the rewrite would touch six repositories.

**Anything on `/profile`.** Own name, phone, picture and password are feature 18. They share the
controller and the entity and nothing else.

---

## 6. Open questions

**Q1. Should a user's email be changeable at all?**

*Options.* (a) Read-only on edit, as the old app had it and as row 2 proposes. (b) Editable, with the
uniqueness check and a session-invalidation story. (c) Editable but only by a platform admin.

*Recommendation: (a).* The full cost of (b) is in section 3 -- unique constraint, JWT subject, refresh
lookup, welcome-mail trail -- and it is a real piece of work with a security-adjacent edge (a rename
silently invalidates every token that names the old subject). (c) has the same cost and a narrower
audience. Read-only restores a behaviour that existed and worked, and it can be revisited when somebody
actually asks for it. Delete-and-recreate is the honest workaround until then.

**Q2. Should the user dialog's Status control be honoured, or removed?**

*Options.* (a) Remove from create, honour on update -- row 1. (b) Remove from both, leaving the row
toggle as the only route. (c) Honour on both.

*Recommendation: (a).* (c) is out because a user created `Inactive` still receives a welcome mail with
a working password and a sign-in that refuses them, and untangling that is a bigger decision than this.
(b) is defensible and is what the old app did, but the dialog is where an administrator already is when
they are correcting a row, and the extra service code is small and well-guarded. (a) is the one that
leaves no control on screen that does nothing.

**Q3. Should a platform admin be able to move a user between tenants from the console?**

*Options.* (a) Leave it locked, as today. (b) Unlock the select for a platform admin, behind a
confirmation naming what gets re-parented. (c) Remove the server support too, so the API and the
console agree.

*Recommendation: (a), recorded as a decision rather than an accident.* The field's hint already tells
the user the workspace is fixed once the account exists (`user-dialog.html:74-76`), so the console is
internally honest. (c) is wrong because `TenantRequestServiceImpl` and any future admin tooling may
legitimately need the capability. (b) is the right answer the first time somebody asks for it -- the
change is unlocking one control and adding a confirmation -- but there is no evidence anybody has, and
a control that re-parents everything a person is attached to is not one to add speculatively. **This is
the one place the rewrite lost a capability the old app had; it should be signed off by whoever owns
the product, not left as a source comment.**

**Q4. Is a colleague list privileged information?**

*Options.* (a) Raise `userStatistics` to `TENANT_ADMIN` -- row 12. (b) Leave the role and strip the
identifying columns from the SQL. (c) Leave it as it is: a tenant is one organisation, and its members
knowing each other's names is not a disclosure.

*Recommendation: (a).* It is one annotation, it has exactly one caller, and that caller is already
admin-only, so the change costs nothing. (c) may well be right in principle -- but if it is, then
`/admin/users` is over-gated, and the two should be settled together rather than left disagreeing. (b)
leaves an endpoint whose name promises per-user statistics open to a role that has no business asking.

**Q5. Should deleting a tenant with active jobs be refused, or warned about?**

*Options.* (a) Refuse while any `Active` source job belongs to it -- row 22. (b) Warn in the
confirmation, which is roughly what happens now (the count is already named). (c) Cascade: delete the
tenant and deactivate its jobs together.

*Recommendation: (a).* (c) makes one click destroy work in six tables and is rejected on the same
grounds the storage-connection delete already rejects it. (b) is where we are, and it is not enough: a
scheduled job belonging to a deleted tenant keeps dispatching, and nothing in either console will ever
show it again. (a) matches an established precedent in this codebase, is a single count query, and
leaves the operator with an obvious next step.

**Q6. Do `Suspended` and `Inactive` mean different things for a tenant?**

*Options.* (a) No -- remove `Inactive` from the dialog and treat the two as one state in the interface,
keeping the enum value for existing rows (row 10). (b) Yes -- make them differ, e.g. `Inactive` blocks
new work but lets people sign in and read. (c) Leave both offered and fix only the hint.

*Recommendation: (a).* `AuthServiceImpl:105-110` is the only place either value is consulted and it
treats them identically, so today (b) is aspirational and (c) leaves a trap labelled "not in use". (b)
is a real product idea -- a read-only workspace is a useful thing -- but it means a second check on
every write path in the product, and it should be designed rather than inferred from an unused enum
value.

**Q7. Where should the E2E profile run?**

*Options.* (a) A CI job with a Postgres service container, on every pull request. (b) A nightly job.
(c) Documented for developers to run locally, unwired.

*Recommendation: (a) if there is a CI system with a database available, (b) if the database is the
obstacle.* (c) is where we are and it is why a thousand lines of authorization coverage has never run.
These suites are the only tests in the repository that see the controller annotations at all -- the
unit tests call services directly -- so they are precisely the ones that catch a `@PreAuthorize`
silently replaced by a method-level annotation, which is the failure this codebase is most exposed to.
Whatever the answer, it needs deciding by someone who knows what the build infrastructure actually is;
the plan can only go as far as the profile.
