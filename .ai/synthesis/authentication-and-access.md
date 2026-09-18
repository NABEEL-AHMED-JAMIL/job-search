# Synthesis -- Authentication and Access

Companion to [../grooming/authentication-and-access.md](../grooming/authentication-and-access.md).
Paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

The rewrite of this feature is done, and it is the strongest migration in the project: the new console
reads the role from the signed token instead of from a `localStorage` blob anyone can edit, expresses
the role hierarchy once instead of spelling out `PLATFORM_ADMIN || TENANT_ADMIN` in seven templates,
validates the `returnUrl` before following it, forces a one-time password to actually be spent, and
carries 510 lines of tests where the old app carried none. Exactly one behaviour was quietly dropped in
the crossing — the old service re-read `localStorage` on every access, so a sign-out in one tab ended
the session in the others, and the new one caches it in a signal — and one behaviour was gained
without being finished: dark mode exists everywhere except on the sign-in page, which is the one page a
signed-out visitor is most likely to land on cold.

So the work here is not migration work. It is closing the holes the migration inherited from the server,
which nobody has yet had a reason to look at: **a session issued to a tenant-scoped role that carries no
tenant sees every tenant's data**, because login never asks whether the role is entitled to a null tenant
and `TenantFilterHelper` responds to a null tenant by switching the filter off. Alongside that sit an
unauthenticated username oracle, an unthrottled password-guessing endpoint, a forced password change
enforced only in the browser, and a sign-out that ends nothing on the server. Eight items, in the order
below; the first four are the phase, and the rest are a day's work between them.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | Login issues a token to any role with `tenant_id = NULL` (`AuthServiceImpl.java:105-111`), and `TenantFilterHelper` disables the tenant filter whenever the tenant is null (`TenantFilterHelper.java:28-33`) — so a null-tenant `TENANT_USER` reads all 15 filtered entities across every tenant | A caller carrying no tenant owns nothing. Only `PLATFORM_ADMIN` may hold a null tenant | Cross-tenant read exposure, and a direct contradiction of `TenantOwnership`'s own documented rule (`TenantOwnership.java:14-15`) | Refuse the sign-in in `checkAccountAndTenantActive`; make `TenantFilterHelper` bind an impossible tenant instead of disabling; add a `CHECK` constraint and a startup report | **M** | **High** — touches the filter every tenant-scoped read goes through |
| 2 | The account/tenant status check runs **before** the password comparison (`AuthServiceImpl.java:60-66`), so a distinguishable message identifies existing accounts to an anonymous caller | An unauthenticated caller learns nothing about which usernames exist | Username enumeration, plus a timing side channel because BCrypt is skipped for unknown users | Move the status check after the password check; keep the distinct messages, now only for callers who proved the password | **S** | Low |
| 3 | `/auth.json/login` accepts unlimited guesses at full speed; no counter, no filter, no dependency (verified by grep over `src/main/java` and `pom.xml`) | Repeated failures from one source are slowed, then refused | Online password guessing is free | A per-username + per-IP counter in Redis, which is already in the stack, in front of `AuthServiceImpl.login` | **M** | Medium — a wrong threshold locks real users out |
| 4 | `must_change_password` is enforced only by `passwordChangeGuard` in the browser (`auth.guard.ts:59-67`); no server code reads it to refuse anything | A one-time password buys exactly one thing: the ability to replace it | An emailed credential is permanent for anyone who skips the console | A filter after `JwtAuthenticationFilter` refusing everything but `changeOwnPassword` / `me` / `logout` while the debt stands | **M** | Medium — a wrong allow-list bricks the change-password screen itself |
| 5 | `logout()` deletes a `localStorage` key (`auth.service.ts:199-202`); no logout endpoint, no `jti`, no denylist | Signing out — and changing a password — ends every token issued before it | A captured refresh token is good for its full 7 days regardless | `app_user.tokens_valid_from`, stamped on sign-out and on password change, compared against the token's `iat` | **M** | Medium — a clock or backfill mistake signs everyone out |
| 6 | The session is read from `localStorage` once, at construction (`auth.service.ts:39`); the old app re-read it on every access (`scheduler1/src/app/_services/auth.service.ts:69-72`) | A sign-out in one tab ends the session in all of them | **The one regression of the migration** | A `storage` event listener in `AuthService` | **S** | Low |
| 7 | `ThemeService` is instantiated only by `landing`, `docs`, `request-workspace` and `shell`; `login.ts` does not inject it, so `/login` renders light on a cold load whatever the stored theme says | Every page of the app honours the theme, on first paint | Dark-mode users get a light sign-in page beside an always-dark panel, then a flip on sign-in | Inject `ThemeService` in `App`, and add a toggle to the login header | **S** | Low |
| 8 | `login.html` contains no links at all; a refused session lands on `/login` with no explanation (`auth.interceptor.ts:109,125,130`) | The sign-in page says why you are there and offers the ways out the landing page offers | Dead end for deep-linked visitors and for expired sessions | `?reason=expired` rendered as one line, plus the three header links | **S** | Low |

Deliberately **not** in the table, because nothing was lost: the demo credentials the old login page
printed (`scheduler1/src/app/_component/login/login.component.html:30`) and the unused
`RoleGuard.exactUsernames` (`scheduler1/src/app/_helpers/role.guard.ts:18`). Both are correctly absent
from the new app. The full behaviour-by-behaviour comparison is grooming §13.1.

---

## 3. Solution detail

### Row 1 — the null-tenant session

**What changes.**

*`process/src/main/java/process/model/service/impl/AuthServiceImpl.java`* — add one clause to
`checkAccountAndTenantActive` (`:101-112`), before the existing null test:

```java
if (user.getUserRole() != UserRole.PLATFORM_ADMIN && isNull(user.getTenantId())) {
    return "This account is not assigned to an organization. Contact your administrator.";
}
```

The method is already called from both `login` (`:60`) and `refresh` (`:93`), so one clause closes both
doors and an existing session dies at its next renewal rather than at its next 30-minute expiry.

*`process/src/main/java/process/security/TenantFilterHelper.java`* — split the condition at `:28`. A
platform admin still disables the filter; a null tenant on any other role must produce **no rows**, not
all of them.

**A sentinel tenant id alone does not do this, and an earlier draft of this document was wrong to say
it did.** Binding `-1L` closes only the entities whose filter is `tenant_id = :tenantId`. Four
entities carry a second, wider condition — verified, all four read
`condition = "(tenant_id = :tenantId or tenant_id is null)"`:

| Entity | Line | What a tenant-less caller would still read |
|---|---|---|
| `StorageConnection` | `:44` | every platform-owned connection, with its endpoint and bucket |
| `KafkaConnectionProfile` | `:26` | every platform profile, including its store bucket and key locations |
| `SourceTaskType` | `:26` | every platform task type |
| `TaskForm` | `:30` | every platform form |

`-1L` leaves the `or tenant_id is null` disjunct live, so those rows come back regardless — and they
are the platform's own. `TenantOwnership.isOwnedByCaller` returns `false` for every one of them, so
binding a sentinel would leave the two paths disagreeing on exactly the set the change exists to
close. That is the opposite of the stated goal.

The fix therefore has to narrow **both** shapes:

```java
if (TenantContext.isPlatformAdmin()) { ...disable...; return; }   // sees everything, by design
Long tenantId = TenantContext.getTenantId();
boolean tenantless = (tenantId == null);
session.enableFilter(FILTER_NAME)
    .setParameter("tenantId", tenantless ? -1L : tenantId)
    // the shared-catalogue entities read this second parameter; the others ignore it
    .setParameter("sharedVisible", !tenantless);
```

and the four conditions above become
`(tenant_id = :tenantId or (:sharedVisible = true and tenant_id is null))`.

A second named filter would work equally well and avoids touching the four `@FilterDef`s; the
parameter is preferred here only because it keeps one filter name in one helper, which is what makes
the rule greppable. Either way, **the four entities must be named in the change** — the failure mode
is silent, and the javadoc that lists the shared catalogues names only three of them (see below).

`-1L` is safe as the sentinel: the sequences start at 1000 (`Tenant.java:38`).

> `TenantOwnership.java:19-23` lists the shared catalogues as `SourceTaskType`, `TaskForm` and
> `KafkaConnectionProfile` — it omits `StorageConnection`, which carries the same condition. That
> omission is what the earlier draft trusted. Correcting the javadoc is part of this change, not a
> tidy-up after it.

*A new Liquibase set, `V26.0-app-user-tenant-required`* — the check constraint from grooming §6, plus a
`SELECT` in the startup log naming any offending row before the constraint is attempted, because
`TenantSeedService.backfillTenantIds` (`:129-142`) backfills six tables and `app_user` is not one of
them. If the constraint fails, the application must still start: grooming's non-functional rule and
`TenantSeedService.seed`'s own `try/catch` (`:62-77`) both say a migration failure never stops the boot.

*Tests* — a service test alongside `AuthServiceImplMustChangePasswordTest` for the refusal **and** for
the platform admin still signing in (the positive control on the same fixture, grooming criterion 7),
and a filter test asserting a null-tenant `TENANT_USER` sees zero rows where a tenanted one sees its own.

**Why this rather than the alternative.**

The obvious smaller fix is to change only `TenantFilterHelper` and leave login alone: the session becomes
harmless, and no existing account is locked out. **Rejected**, for two reasons. First, `TenantFilterHelper`
is not the only read path — `findById` is never filtered at all, which is exactly the case
`TenantOwnership` was written to cover, and any future service that forgets the ownership check
re-opens the hole. Second, a session that can see nothing is not a working session; it is a support
ticket that looks like a bug. Refusing at the door names the actual problem to the person who has to
fix it, in a sentence they can act on. The filter change stays as well — belt and braces, at the layer
where a mistake is most expensive.

The other rejected option was making `app_user.tenant_id` `NOT NULL` outright and giving the platform
admin a synthetic "platform" tenant row. **Rejected** because it inverts the meaning the whole codebase
is built on — a null `tenant_id` is *platform-owned, not ownerless*, and 15 entities, `TenantOwnership`,
`TenantFilterHelper` and every shared-catalogue filter all read it that way. Changing that reading is a
migration across the entire data model to fix one login check.

### Row 2 — the username oracle

**What changes.** `AuthServiceImpl.login` (`:48-70`) reorders to: exists → password matches → status. On
a password mismatch return `"Invalid username or password."` exactly as now; only after the password is
correct return the inactive-account or suspended-tenant message. The messages themselves stay: they are
genuinely useful to the person who owns the account, and telling *them* their account is suspended is
the point. This also closes the timing channel, because `passwordEncoder.matches` now runs for every
username that exists.

For a username that does **not** exist, the comparison is still skipped entirely (`:56-58`), which leaves
a smaller timing difference. A dummy BCrypt comparison against a constant hash would close it. **Not
proposed**: it costs a ~100 ms hash on every unknown-username request, which is a free denial-of-service
lever, and rate limiting (row 3) is the honest answer to timing enumeration. Recorded so the option is
not rediscovered.

**Why not simply flatten every message to "Invalid username or password."** Because a suspended tenant
is not a wrong password, and telling a whole organisation their credentials are wrong when their
workspace was suspended sends every one of them to support. The ordering fix keeps the useful message
and removes the disclosure; flattening removes both.

### Row 3 — rate limiting

**What changes.** A small `LoginThrottle` component consulted at the top of `AuthServiceImpl.login`,
keyed on the normalised username **and** on the caller's IP, backed by Redis (already in the stack, per
`.ai/project.md`). Counters clear on a successful sign-in. Suggested opening thresholds, to be tuned:
10 failures per username per 15 minutes, 50 per IP per 15 minutes, answering with the same
`"Invalid username or password."` so the throttle itself is not an oracle.

**Why Redis rather than a column on `app_user`.** A counter column means a write on every failed
sign-in, which is a write amplifier an attacker controls, and it cannot see the per-IP dimension at all
— the interesting attack is 10 000 usernames tried once each, which no per-account counter notices.
Redis holds both keys, expires them by itself, and costs nothing when the stack is healthy. **The
rejected option** was doing this at nginx: it is genuinely simpler, but nginx cannot key on the
username, and the deployment already has more than one entry point (`scheduler1/nginx.conf` fronts the
old UI only).

**Why this is Medium risk.** A threshold that is too tight locks out a real user in front of a customer.
The throttle must be configurable, must clear on success, and its refusal must be visible in the log
with the key that tripped it.

### Row 4 — server-side enforcement of the password debt

**What changes.** A `OncePerRequestFilter` registered after `JwtAuthenticationFilter`
(`SecurityConfig.java:56`) which, when `TenantContext.getAppUserId()` is set, reads
`app_user.must_change_password` and — while true — refuses anything outside a small allow-list
(`/appUser.json/changeOwnPassword`, `/appUser.json/me`, `/auth.json/**`) with a 403 carrying the
existing envelope shape.

**Why a per-request database read rather than a claim in the token.** Putting `mustChangePassword` into
`JwtUtil.buildToken` (`:42-54`) is one line and costs nothing per request — but the flag is cleared by
`changeOwnPassword` (`AppUserServiceImpl.java:629`) and the token is not reissued, so the claim stays
stale for up to 30 minutes and the person who just chose a password is still locked out of the console
they were sent to. Working around that means reissuing tokens from the password endpoint, which is a
larger change than the read it was trying to avoid. The read is a primary-key lookup on an indexed
column, on requests made by accounts that are, by construction, brand new.

**Why the allow-list is the risky part.** Get it wrong and the profile screen cannot load the data it
needs to render the change-password form, and the account is bricked. The list above must be verified
against what `features/profile/profile.ts` actually calls on load, and grooming criterion 34 ("sign out
still works") pinned as a test.

### Row 5 — real sign-out

**What changes.** One nullable column, `app_user.tokens_valid_from TIMESTAMP`; a
`POST /auth.json/logout` on `AuthRestApi` that stamps it `now()`; the same stamp inside
`changeOwnPassword` and `resetPassword`; and a comparison in both `JwtAuthenticationFilter` and
`AuthServiceImpl.refresh` rejecting any token whose `iat` predates it. `AuthService.logout()`
(`auth.service.ts:199-202`) calls the endpoint and clears local state regardless of the answer — a
network failure must never leave someone unable to sign out of their own browser.

**Why a timestamp rather than a `jti` denylist.** A denylist revokes the one token it was given, which
means a password change — the case that matters most, because it is what someone does *after* they
suspect a compromise — revokes nothing at all unless every outstanding token for that user is tracked.
The timestamp revokes everything issued before the moment of the decision, in one comparison, with no
new store to operate and nothing to expire. Its cost is granularity: it cannot revoke one device and
leave another signed in. That is a feature nobody has asked for, and the column does not prevent adding
`jti` later if they do.

**Why the filter must read it.** Stamping the column and only checking at refresh leaves a stolen
*access* token working for up to 30 minutes after sign-out. That is defensible, and it is what most
JWT deployments do — but the check is a value already loaded by row 4's filter on the same request, so
the marginal cost is zero once row 4 exists. That is the reason row 5 is ordered after row 4.

### Row 6 — cross-tab sign-out

**What changes.** In `AuthService`'s constructor, listen for `storage` and re-hydrate:

```ts
window.addEventListener('storage', e => {
  if (e.key === STORAGE_KEY) this.currentUser.set(this.readStoredUser());
});
```

Everything downstream is already derived from that signal, so the shell empties, the STOMP socket tears
itself down (`job-events.service.ts:73-81`) and `authGuard` redirects on the next navigation, with no
other change. A test belongs in `auth.service.spec.ts`, whose `useMemoryStorage` helper already stubs
`Storage`.

**Why not poll.** Because the event exists, fires only for *other* documents on the same origin, and
costs nothing when nothing happens.

### Row 7 — the theme on `/login`

**What changes.** Inject `ThemeService` in `App` (`scheduler1/next/src/app/app.ts`) so the class is
applied for every route rather than for the four that happen to inject it, and add the same toggle
button the landing header carries (`landing.ts:74-78`) to `login.html`'s brand row.

**Why in `App` rather than in `Login`.** Adding the injection to `login.ts` fixes the reported page and
leaves `f/:uuid` — the public shared-form renderer, which also injects nothing — with the same bug for
the next person to find. The service is a root singleton with an effect; instantiating it once at the
root is what it was written for.

**The rejected option** was an inline script in `index.html` reading `etl_theme` and setting the class
before Angular boots. That is the standard fix for the flash-of-wrong-theme problem and it is strictly
better on first paint — but it duplicates the storage key and the OS-preference fallback outside
`ThemeService`, in a file that no test covers, and the flash it prevents is a few milliseconds. Worth
revisiting only if the flash is actually observed after the injection lands.

### Row 8 — the sign-in page's dead end

**What changes.** `auth.interceptor.ts` navigates to `/login?reason=expired` on the two paths that
currently call `auth.logout()` after a refused refresh (`:109`, `:130`) — the third, `:125`, is a second
401 on a retry and means the same thing. `login.ts` reads the parameter and `login.html` renders one
line above the form. Separately, the brand row in `login.html:5-11` gains the links the other two public
pages carry: back to `/`, `Setup guide` (`/docs`) and `Request a workspace`.

`Request a workspace` matters most of the three: it is the page built precisely for someone who cannot
sign in, and today it is reachable only from the landing page, which `authGuard` never sends anyone to.

---

## 4. Ordering

**Row 1 first, and on its own.** It is the only item with data exposure behind it, and it touches
`TenantFilterHelper`, which every tenant-scoped read in the product passes through — so it wants the
full test suite to itself before anything else moves. It unblocks nothing; it is simply the thing that
should not wait.

**Then rows 2 and 3 together.** They are one attack told from two ends: row 2 stops the endpoint
answering "does this account exist", row 3 stops it being asked ten thousand times. Shipping row 2 alone
narrows the oracle to a timing difference that row 3 is the answer to, so the pair is the smallest
change that actually closes it.

**Then row 4, then row 5.** Row 4 introduces the post-authentication filter and the per-request read of
`app_user`; row 5's `tokens_valid_from` check is another comparison on the row that filter has already
loaded. Doing row 5 first means writing the filter twice.

**Rows 6, 7 and 8 at any point.** Each is self-contained, none blocks another, and together they are
under a day. Row 6 is the migration regression, so it should not be the one that slips: it is the only
item in this document whose absence is a *loss* rather than an inherited gap.

**Everything here is testable before it ships.** Grooming's acceptance criteria 39, 3-4, 9, 37, 43-44,
45 and (for row 8) 20 are the checks for rows 1-8 respectively, and criteria 39, 5-7, 17-18 and 24-26
are the positive controls that keep a passing refusal from being a broken fixture.

---

## 5. Out of scope

**Password recovery.** Grooming §13.6: there is no "forgot password" anywhere, and the only reset path
is an administrator calling `appUser.json/resetPassword`. For a multi-tenant B2B console where accounts
are provisioned by an admin and the username is a verified work address, admin-mediated reset is a
defensible design rather than an omission. Building self-service recovery means an email-token flow, a
new table and a new public endpoint — a feature, not a fix. Left out deliberately, and recorded in
grooming so the question has a dated answer.

**MFA and a "your active sessions" screen.** Same reasoning, larger. Row 5's `tokens_valid_from` gives
"sign out everywhere", which is the part of session management people actually reach for.

**Anything about the old frontend.** `scheduler1/src` is reference-only for this phase. The stale demo
credentials on its login page (grooming §12.9) are recorded because that app is still deployed, not
because they are in scope to change here.

**The 401 response body.** `SecurityConfig.java:33-34` answers `response.sendError(401)`, which is
Spring's default error body rather than the `{status, message}` envelope every other response uses. The
interceptor handles 401 as an `HttpErrorResponse` before any body is read, so nothing is broken today.
It is an inconsistency worth tidying when that file is next open, not a reason to open it.

**The `ROLE_META` bypass and the four-states-say-suspended message** (grooming §12.10). Both are real,
both are cosmetic, and both should ride along with whichever change next touches those files rather
than justifying a commit.

---

## 6. Open questions

**1. Does refusing a null-tenant sign-in (row 1) lock out anyone real?**
The write paths that could create such a row are closed (`AppUserServiceImpl.java:168-171`, `:300-302`),
so the only candidates are pre-existing or hand-inserted rows — and nobody has counted them.
*Options:* (a) refuse outright; (b) refuse, but ship the startup report one release earlier so the
number is known before the door closes; (c) log and allow for one release, then refuse.
**Recommendation: (b).** The report is part of row 1's migration anyway, and splitting it out one
release costs a day and turns "will this break someone?" into a number. (c) is the option that never
ends, because nothing forces the second release to happen.

**2. Where does the password-debt filter get the flag (row 4)?**
*Options:* (a) a per-request read of `app_user.must_change_password`; (b) a claim in the access token.
**Recommendation: (a),** for the staleness reason in §3 row 4 — (b) leaves someone who has just chosen
their password locked out for up to 30 minutes, which is a worse bug than the one being fixed. If the
read ever shows up in a profile, cache it in Redis keyed on `appUserId` and evict it in
`changeOwnPassword`; do not move it into the token.

**3. What are the rate-limit thresholds, and who is allowed to trip them (row 3)?**
*Options:* (a) per-username only; (b) per-IP only; (c) both, with different limits.
**Recommendation: (c),** at 10 per username and 50 per IP per 15 minutes, both configurable, both
clearing on a successful sign-in. (a) alone misses the spray attack across many usernames; (b) alone
punishes everyone behind one corporate NAT for one person's typo. The numbers are opening positions
and should be revisited after a week of real logs — which means the refusal has to be logged with the
key that tripped it from day one.

**4. Should `changeOwnPassword` and `resetPassword` revoke outstanding tokens (row 5)?**
*Options:* (a) sign-out only; (b) sign-out, own password change and admin reset.
**Recommendation: (b).** Changing a password is what someone does when they think it is known, and a
change that leaves the old sessions running does not do the thing they came to do. An admin reset is
the same argument with a different actor. The cost is one extra stamp in two methods that already
write the row.

**5. Does the username normalisation (grooming §12.2) go in this feature or in `tenants-and-users`?**
Lower-casing at login alone would let `Jane@corp.com` and `jane@corp.com` exist as two rows and both
match the same sign-in, which is worse than the bug. The fix is normalise-on-write plus a one-off
data migration for collisions, and both of those are user-management's.
**Recommendation:** raise it in `tenants-and-users`, cross-referenced from grooming §12.2, and change
`AuthServiceImpl` only once the column is guaranteed normalised. Grooming criterion 8 is written to
fail until then, deliberately, so it stays visible.

---

## Landed since this synthesis (2026-09-17)

Page-level access for tenant users -- `pageKeys` on the login and refresh responses
(`AuthResponseDto`), `pageGuard` beside `authGuard` (`core/auth/auth.guard.ts:53`), the menu
filtered by `canOpen`, and `PageAccessInterceptor` on the server -- is its own feature row and
documents: [../grooming/page-access-profiles.md](../grooming/page-access-profiles.md),
[page-access-profiles.md](page-access-profiles.md). The role hierarchy is unchanged; profiles
narrow a `TENANT_USER` only.
