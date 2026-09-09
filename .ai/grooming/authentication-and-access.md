# Grooming -- Authentication and Access

Feature `authentication-and-access`, row 1 of [../discovery/features.md](../discovery/features.md).
Migration status: **migrated**.

All paths in this document are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Purpose

> "Let me in, keep me in, and don't show me doors I can't open."

This feature is the front door of the console and the thing every other feature stands on. Concretely it
has to do five jobs:

1. **Let the right person in.** A username and a password go to the server; the server decides, and says
   the same unhelpful thing to anyone who gets it wrong.
2. **Keep them in without asking again every half hour.** A short-lived access token does the work; a
   longer-lived refresh token quietly renews it in the background, and the person never sees it happen.
3. **Say who they are.** Name, picture, role and tenant have to be available to every screen so the
   console can address them and shape itself around what they may do.
4. **Not show doors that are locked.** A tenant user should not see an Administration menu that answers
   403 on every click. The menu hiding a control is a courtesy, not the lock — the lock is on the server.
5. **Let go.** Signing out, being deactivated, having the workspace suspended, or handing back a
   one-time password all have to end or interrupt the session in a way the person can understand.

Around that sit three pages that need no account at all: a public front page describing the product, a
setup guide, and the "you don't have access to that" page a role refusal lands on.

---

## 2. Existing behaviour

### 2.1 The server — the same for both frontends

Two endpoints, both anonymous, both on `AuthRestApi`
(`process/src/main/java/process/api/AuthRestApi.java`). The controller carries **no**
`@PreAuthorize` — deliberately, because nobody is signed in yet — and `SecurityConfig` opens the whole
prefix with `.antMatchers("/auth.json/**").permitAll()`
(`process/src/main/java/process/config/SecurityConfig.java:37`).

**`POST /auth.json/login`** (`AuthRestApi.java:30-38` → `AuthServiceImpl.login`,
`process/src/main/java/process/model/service/impl/AuthServiceImpl.java:48-70`) runs four checks in this
order:

| Order | Check | Where | Failure message |
|---|---|---|---|
| 1 | Username and password both present | `AuthServiceImpl.java:49-51` | `Username and password are required.` |
| 2 | A non-deleted account with that exact username exists | `:52-58` (`findByUsernameAndStatusNot(username.trim(), Status.Delete)`) | `Invalid username or password.` |
| 3 | Account is `Active` **and** its tenant is `Active` | `:60-63` → `checkAccountAndTenantActive`, `:101-112` | `This account is inactive. Contact your administrator.` / `Your organization's access is currently suspended. Contact your administrator.` |
| 4 | BCrypt password matches | `:64-66` | `Invalid username or password.` |

On success it stamps `lastLoginAt` and saves the row (`:67-68`), then answers
`{status:"SUCCESS", message:"Login successful.", data: AuthResponseDto}`. `buildAuthResponse`
(`:114-134`) fills the DTO with `accessToken`, `refreshToken`, `username`, `fullName`, `userRole`,
`tenantId`, `appUserId`, `avatarBucket`, `avatarKey` and `mustChangePassword`
(`process/src/main/java/process/model/dto/AuthResponseDto.java:13-32`).

**`POST /auth.json/refresh`** (`AuthRestApi.java:40-48` → `AuthServiceImpl.refresh`, `:72-99`) takes
`{"refreshToken": "..."}`, parses the claims, insists the token's `type` claim is `refresh`
(`:84-86`), re-reads the account, **re-runs the same account-and-tenant status check** (`:93-95`), and
returns an `AuthResponseDto` carrying **only** a new `accessToken` (`:96-98`). It does not rotate the
refresh token and deliberately leaves `mustChangePassword` null, so a partial response merged over a
stored session cannot silently settle a standing debt (`AuthResponseDto.java:23-32`, pinned by
`AuthServiceImplMustChangePasswordTest.refreshStillOnlyMintsAnAccessToken`).

**The token** (`process/src/main/java/process/util/JwtUtil.java:42-54`) is HS256, subject = username,
with claims `appUserId`, `tenantId`, `userRole` and `type`. Access tokens live
`jwt.access-token.expiry-minutes` (default **30**), refresh tokens `jwt.refresh-token.expiry-days`
(default **7**) — `JwtUtil.java:28-32`, wired from `JWT_ACCESS_TOKEN_EXPIRY_MINUTES` /
`JWT_REFRESH_TOKEN_EXPIRY_DAYS` in `process/src/main/resources/application-dev.properties:15-17` (and
the `-stage` / `-prod` twins). The signing key comes from `jwt.secret.key` with **no default**;
`secretKey()` throws `IllegalStateException` rather than signing with an empty key
(`JwtUtil.java:81-87`). `process/docker-compose.yml:154-157` supplies a development fallback and says in
a comment that a real key belongs in any environment with real users.

**Every subsequent request** is authenticated by `JwtAuthenticationFilter`
(`process/src/main/java/process/security/JwtAuthenticationFilter.java:31-59`): it reads
`Authorization: Bearer`, parses the claims, **skips refresh tokens** (`:39`) so one cannot be used as an
access token, fills the four `TenantContext` thread-locals (`:44`) and installs an authentication whose
single authority is `"ROLE_" + userRole` straight from the claim (`:45-47`). A token that will not parse
is logged at debug and the request **continues unauthenticated** (`:50-53`); the 401 comes later from
`.anyRequest().authenticated()` and the entry point at `SecurityConfig.java:33-34`, which calls
`response.sendError(401, "Unauthorized")`. `TenantContext.clear()` runs in a `finally` (`:54-58`).

**The role hierarchy** is installed once, in `MethodSecurityConfig`
(`process/src/main/java/process/config/MethodSecurityConfig.java:26-31`):
`ROLE_PLATFORM_ADMIN > ROLE_TENANT_ADMIN > ROLE_TENANT_USER`. That is what makes every
`@PreAuthorize("hasRole('TENANT_ADMIN')")` in `process/src/main/java/process/api/` admit a platform
admin without naming it.

**The seeded first account** is `admin@platform.local`
(`process/src/main/java/process/model/service/impl/TenantSeedService.java:27`), created only when
`platform.admin.bootstrap-password` is configured (`:41-42`, `:103-127`), created with
`mustChangePassword = true` (`:121`) and with `tenantId = null` (`:115`). With nothing configured, no
account is created at all and the failure is logged rather than defaulted (`:108-113`).

**The WebSocket** uses the same tokens: `StompAuthChannelInterceptor`
(`process/src/main/java/process/security/StompAuthChannelInterceptor.java:34-104`) authenticates the
STOMP `CONNECT` frame from the `Authorization` native header (`:40-58`) and refuses a `SUBSCRIBE` to a
tenant feed the token does not own (`:68-104`).

### 2.2 The old frontend (`scheduler1/src`)

Four files carry the whole feature.

| File | What it does |
|---|---|
| `scheduler1/src/app/_services/auth.service.ts` | `login` posts and stores `response.data` under `etl_auth_user` (`:12`, `:17-31`); `refreshAccessToken` posts the stored refresh token and writes back **only** `accessToken` (`:33-53`); `logout` removes the key and navigates to `/login` (`:55-58`); `currentUser` re-reads `localStorage` **on every access** (`:69-72`) |
| `scheduler1/src/app/_helpers/auth.guard.ts` | `AuthGuard` — presence of an access token; otherwise `/login?returnUrl=<state.url>` (`:16-22`) |
| `scheduler1/src/app/_helpers/role.guard.ts` | `RoleGuard` — reads `route.data.roles` as a **list** and compares `currentUser.userRole` by equality (`:17-27`); also supports an `exactUsernames` list (`:18`, `:23-24`) that **no route uses** |
| `scheduler1/src/app/_helpers/auth.interceptor.ts` | Attaches the bearer token except on the two auth URLs (`:22-27`); on a 401, one shared refresh via `refreshInFlight$` + `shareReplay(1)` (`:48-56`), replays the request, and calls `logout()` if the refresh fails (`:39-42`) |

The stored session shape is `scheduler1/src/app/_models/auth.model.ts:2-10` — seven fields, no avatar,
**no `mustChangePassword`**.

Screens:

- **`''` Welcome** (`scheduler1/src/app/_component/welcome/welcome.component.ts`) — a public marketing
  page: four highlight pills, seven feature cards, three steps, a footer. Redirects a signed-in visitor
  to `/home` from `ngOnInit` (`:83-87`).
- **`login`** (`scheduler1/src/app/_component/login/login.component.ts`) — a two-field reactive form,
  both `Validators.required` (`:31-34`). Redirects to `/home` if already signed in (`:26-29`), honours
  `?returnUrl` with **no validation of its value**, defaulting to `/home` (`:30`, `:54`). On failure it
  sets an inline message and raises a toast (`:48-58`). The template hard-codes a credential hint —
  "Use **admin@platform.local** / **admin@platform.local** to sign in"
  (`scheduler1/src/app/_component/login/login.component.html:30`).
- **`unauthorized`** (`scheduler1/src/app/_component/unauthorized/unauthorized.component.ts`) — an
  empty class over a static template with a "Back to Home" button. Behind `AuthGuard`
  (`scheduler1/src/app/app.routing.ts:184-187`).
- **`**` → `home`** (`app.routing.ts:277-280`).

The signed-in chrome lives in `scheduler1/src/app/app.component.ts`: `showNav` hides the navbar when
signed out or on `/login` (`:49-51`), initials and a role label are derived in the component
(`:57-76`), and `logout()` also disconnects the notification stream and resets its counters
(`:130-137`). Admin nav entries are hidden with `*ngIf` on `authService.currentUser?.userRole`, spelling
out the role pair by hand in seven places (`scheduler1/src/app/app.component.html:29,45,52,57,60,70,73,76`).

Route protection in the old app is 39 hand-written `canActivate` arrays across
`scheduler1/src/app/app.routing.ts:41-281`.

### 2.3 The new frontend (`scheduler1/next/src`)

Four files again, in `scheduler1/next/src/app/core/auth/`.

**`auth.models.ts`** — the three roles as a union (`:1`), a numeric `ROLE_RANK` so "at least this role"
is a comparison rather than a list (`:10-14`), `isUserRole` (`:17-19`), a `ROLE_META` table of label /
hint / pill class / accent per role (`:28-47`), and the stored `AuthUser` shape (`:49-67`) — which
adds `avatarBucket`, `avatarKey` and `mustChangePassword` over the old model.

**`auth.service.ts`** — one signal holding the session, hydrated from `localStorage` **once** at
construction (`:39`), with everything else derived:

- `role` is read **from the JWT, not from the stored blob** (`roleFromToken`, `:20-31`; used at `:43`).
  The comment states why: the blob sits in `localStorage` where devtools can rewrite `userRole` and
  unfold the admin menu. Anything unreadable yields `null`, not a fallback.
- `hasAtLeast` is the single expression of the hierarchy (`:53-56`), and fails closed with no role.
- `mustChangePassword` is read from the blob rather than the token (`:69`), for the reason given at
  `:65-67` — forging it only skips a prompt, and the server stops honouring the old password anyway.
- Six capability computeds named after the API they stand for, not the role (`:87-98`).
- The avatar is fetched as a **blob through `HttpClient`** in an effect (`:139-154`) because an `<img
  src>` cannot carry a bearer token; the effect depends on a value-compared `{bucket, key}` computed
  (`:125-130`) so a token refresh does not re-fetch the picture.
- `login` (`:171-179`), `refresh` (`:186-197`, merging the partial response over the stored user, and
  clearing the session on a non-SUCCESS envelope), `logout` (`:199-202`).

**`auth.guard.ts`** — four guards:

| Guard | Kind | Behaviour | Lines |
|---|---|---|---|
| `authGuard` | `CanActivateFn` | Not signed in → `/login?returnUrl=<state.url>`. Uses `state.url`, not `route.url`, because the shell's own path is empty | `:6-17` |
| `roleGuard` | `CanActivateFn` | Reads `data.minRole`; `!hasAtLeast(min)` → `/unauthorized`. Must sit on the route carrying the data | `:33-42` |
| `passwordChangeGuard` | `CanActivateChildFn` | While `mustChangePassword()`, every shell child except `/profile` redirects to `/profile` | `:59-67` |
| `anonymousOnly` | `CanMatchFn` | Lets `/` and `/login` mean two things without a redirect loop | `:75` |

**`auth.interceptor.ts`** — attaches the bearer token to every request (`:52-55`); rewrites a 200 with
an empty body into the error envelope the ~98 body-reading call sites already handle (`withUsableBody`,
`:28-39`); notices `appUser.json/changeOwnPassword` succeeding and calls `auth.passwordChanged()`
(`:62-64`) so the password gate lets go without waiting for the next sign-in; and runs a **single-flight
refresh queue** on a 401 (`:18-19`, `:67-133`) in which parallel 401s wait on one `Subject`, the queue
can be `error()`ed so a refused refresh fails its waiters instead of stranding them on a spinner
(`:92-103`), and after a successful refresh **only a second 401** signs the session out — any other
status is the endpoint's own problem (`:117-132`).

Routes (`scheduler1/next/src/app/app.routes.ts`):

| Route | Guard | Component | Lines |
|---|---|---|---|
| `login` | `canMatch: [anonymousOnly]` | `features/login/login.ts` | `:6-14` |
| `login` (second entry) | — | `redirectTo: '/dashboard'`, only matched when the first refused | `:15-19` |
| `''` | `canMatch: [anonymousOnly]`, `pathMatch: 'full'` | `features/landing/landing.ts` | `:20-27` |
| `docs` | none — public | `features/docs/docs.ts` | `:34-39` |
| `''` (shell) | `canActivate: [authGuard]`, `canActivateChild: [passwordChangeGuard]` | `features/shell/shell.ts` | `:46-52` |
| `unauthorized` | inside the shell | `features/unauthorized/unauthorized.ts` | `:205-209` |
| `**` | — | `redirectTo: ''` | `:285` |

`features/login/login.ts` is a two-field `nonNullable` reactive form, both required (`:23-26`), with a
`submitting` signal driving the button label and disabled state and an `error` signal for the inline
message (`:20-21`, `:36-55`). The `returnUrl` is followed **only when it is a single-slash in-app path**
(`:43-45`) — the open-redirect guard the old app did not have — falling back to `/`. The template
(`features/login/login.html`) is a two-column layout: the form on the left, a dark panel on the right
carrying the live `ConsolePreview` and three capability captions, `hidden lg:block` so it does not push
the form down on a phone (`login.html:52`).

`features/unauthorized/unauthorized.ts` names the caller's current role in the sentence (`:16`,
`:36-39`) and offers **Go back** via `Location.back()` and **Dashboard**, rather than the old app's
single Home button.

The signed-in chrome is `features/shell/shell.ts`: a single `allNav` table with `adminOnly` /
`platformOnly` flags (`:48-137`) filtered once through `auth.isTenantAdmin()` / `auth.isPlatformAdmin()`
(`:140-151`), replacing the old app's seven hand-written `*ngIf` role pairs. The user menu shows the
avatar or initials, the display name, the role, a link to `/profile` and **Sign out**
(`features/shell/shell.html:75-106`).

Theme is a root service with a `localStorage`-backed signal defaulting to the OS preference
(`scheduler1/next/src/app/core/theme.service.ts:9-20`); a toggle sits in the shell header
(`shell.html:66`), on the landing hero (`landing.ts:76`) and on the docs header (`docs.ts:71`).

### 2.4 Tests that exist today

| Suite | File | Covers |
|---|---|---|
| Backend unit | `process/src/test/java/process/model/service/impl/AuthServiceImplMustChangePasswordTest.java` | 3 tests: the debt is reported at sign-in, absent when not owed, and left untouched by refresh |
| Backend unit | `process/src/test/java/process/config/MethodSecurityConfigRoleHierarchyTest.java` | Instantiates the real config and pins the hierarchy rather than restating the string |
| Frontend | `scheduler1/next/src/app/core/auth/auth.guard.spec.ts` (179 lines) | All four guards, plus five structural assertions over the real route table |
| Frontend | `scheduler1/next/src/app/core/auth/auth.interceptor.spec.ts` (182 lines) | Refresh queue success and failure, queue reuse, the password-debt hook, and not signing out on a non-401 |
| Frontend | `scheduler1/next/src/app/core/auth/auth.service.spec.ts` (149 lines) | Role read from the token, the devtools-escalation case, the hierarchy, the password debt |

**Where there are none, honestly:**

- **No test of any kind touches `/auth.json/login` or `/auth.json/refresh` over HTTP.** Grepping the whole
  of `process/src/test` for `AuthRestApi` or `auth.json` returns nothing; the eight E2E classes in
  `process/src/test/java/process/e2e/` mint their tokens directly with `JwtUtil`
  (`E2ESupport.java:113,120`) rather than signing in. Login's four checks, their ordering and their
  messages are covered only by the mocked service test above.
- **No test for `JwtUtil`**, `JwtAuthenticationFilter`, `StompAuthChannelInterceptor`, or the
  `SecurityConfig` matcher list.
- **No spec for `login.ts`** — including the open-redirect guard at `login.ts:43-45`, which is the one
  piece of security logic in the component.
- No spec for `landing.ts`, `docs.ts`, `unauthorized.ts` or `shell.ts`.
- **The old frontend has zero test files.** `find scheduler1/src -name "*.spec.ts"` returns 0.

---

## 3. Expected behaviour

Most of this feature already behaves as it should. The list below states the target; the lines marked
**differs** are where today's code does not meet it, and each is carried into §12 with evidence.

1. Anyone may reach `/`, `/login` and `/docs` with no account. Everything else requires a session.
2. Sign-in takes a username and a password, and answers with the same message for an unknown user and a
   wrong password. — **differs:** a *known but inactive* account, or one whose tenant is not Active, gets
   a distinguishable message **before** the password is checked, which is a username oracle (§12.1).
3. A username is an email address and should be matched the way an email address is used. — **differs:**
   the lookup is exact and case-sensitive (§12.2).
4. Repeated failed sign-ins from one source are slowed or blocked. — **differs:** there is no throttling,
   lockout or delay anywhere (§12.3).
5. A session survives a page reload, renews itself silently while the refresh token is valid, and ends
   the moment the refresh is refused.
6. Role and tenant are read from the signed token, never from anything the browser can edit. Already
   true on both the server (`JwtAuthenticationFilter.java:41`) and the new client
   (`auth.service.ts:20-31,43`); the old client reads the blob (`role.guard.ts:19`).
7. **A caller carrying no tenant owns nothing.** A non-platform-admin session must not be issued for an
   account with a null `tenant_id`, and if one exists it must see no tenant-scoped rows. — **differs:**
   login issues the token, and `TenantFilterHelper` responds to a null tenant by *disabling* the filter
   (§12.4). This is the most serious item in this document.
8. An account owing a one-time password change cannot do anything but change it. — **differs:** enforced
   only in the browser; the server accepts every call from such a token (§12.5).
9. Signing out ends the session everywhere it is held. — **differs:** the refresh token stays valid for
   its full seven days, and a sign-out in one tab is invisible to another (§12.6, §12.7).
10. Every page of this feature renders correctly in both themes at every supported width. — **differs:**
    `/login` never applies the dark class on a cold load (§12.8).
11. A role refusal explains itself and offers a way back. Already true (`unauthorized.ts:14-27`).
12. A refused session says why it ended. — **differs:** the session simply vanishes to `/login` with no
    message (§13.4).

---

## 4. Frontend requirements

### 4.1 Routes

| Path | Access | Component | Notes |
|---|---|---|---|
| `''` | `anonymousOnly`, `pathMatch: 'full'` | `features/landing/landing.ts` | Public front page. Signed in, the same path falls through to the shell and redirects to `/dashboard` |
| `login` | `anonymousOnly` | `features/login/login.ts` | Sign-in form |
| `login` | — | redirect | `/dashboard` when already signed in |
| `docs` | public | `features/docs/docs.ts` | Setup guide |
| `unauthorized` | shell child (`authGuard`) | `features/unauthorized/unauthorized.ts` | Where `roleGuard` sends a refusal |
| `**` | — | redirect to `''` | Resolves to the landing page or the dashboard depending on the session |

### 4.2 The sign-in form

- Two controls, `username` and `password`, both `Validators.required`, `nonNullable`
  (`login.ts:23-26`).
- `autocomplete="username"` and `autocomplete="current-password"` so password managers work
  (`login.html:22,31`).
- Submit is disabled and the label becomes "Signing in…" while a request is in flight
  (`login.html:43-45`).
- Per-field messages appear only once a control is `touched` (`login.html:23-25,32-34`); a blocked
  submit calls `markAllAsTouched()` so they all appear at once (`login.ts:31-32`).
- The server's message is shown verbatim in a bordered block above the button (`login.html:37-41`).
- `?returnUrl` is followed only when it starts with exactly one `/` (`login.ts:43-45`).

**Required additions** (see §12.8 and §13.5): the login page must apply the stored theme on a cold load,
and must carry the same header links the landing and docs pages have — back to `/`, `Request a
workspace`, `Setup guide` — because `authGuard` drops deep-linked visitors here with no other exit.

### 4.3 States

| State | Today | Requirement |
|---|---|---|
| Loading | Button disabled + "Signing in…" (`login.html:43-45`) | Keep |
| Empty | n/a for a two-field form | — |
| Error (credentials) | Inline block, server message (`login.html:37-41`) | Keep |
| Error (network) | `Could not reach the server.` (`login.ts:53`) | Keep |
| Error (session ended) | **nothing** — the app navigates to `/login` silently | Add a one-line reason on the sign-in page (§13.4) |
| Refusal by role | `/unauthorized`, naming the current role, Go back + Dashboard (`unauthorized.ts:10-30`) | Keep |
| Password debt | Pinned to `/profile` by `passwordChangeGuard` | Keep; the profile screen owns the prompt |

### 4.4 Theme and responsiveness

- Theme is `html.dark`, toggled by `ThemeService` and driven entirely by tokens redefined at
  `scheduler1/next/src/styles.css:93-138` (light) and `:140-172` (dark).
- The landing hero is deliberately a single dark surface in both themes and states so
  (`landing.ts:24-33`); the login page's right-hand panel is likewise always `bg-ink-900`
  (`login.html:52`). Both are intentional and should stay.
- The login layout is `grid lg:grid-cols-2` with the right panel `hidden lg:block`, so below `lg` the
  form is the whole page (`login.html:1,52`).
- The landing capability grid steps `1 → sm:2 → lg:3` with the dividing rules recalculated per breakpoint
  (`landing.ts:40-48`); the step sequence's connecting rule appears only at `lg` (`landing.ts:51-56`) and
  is suppressed under `prefers-reduced-motion` along with the entry animation (`landing.ts:60`).
- The shell collapses its nav behind a menu button below `xl` (`shell.html:110-113`) and hides the
  display name below `sm` (`shell.html:85`).

### 4.5 Dialogs and tables

This feature has neither. The only overlay it owns is the shell's user menu
(`shell.html:87-106`), closed by an outside click or Escape (`shell.ts:157-171`).

---

## 5. Backend requirements

### 5.1 Endpoints

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/auth.json/login` | **anonymous** (`SecurityConfig.java:37`) | Validates the credential, checks account and tenant status, stamps `last_login_at`, returns access + refresh tokens and the profile fields the console needs, including `mustChangePassword` |
| POST | `/auth.json/refresh` | **anonymous** (same matcher) | Validates a refresh token, re-checks account and tenant status, returns a new access token only |

Also part of this feature's surface, though owned by other controllers:

| Method | Path | Role | Why it is here |
|---|---|---|---|
| PUT | `/appUser.json/changeOwnPassword` | `TENANT_USER` | The only call that settles a password debt; the interceptor watches for it (`auth.interceptor.ts:42,62-64`) and the server clears the flag (`AppUserServiceImpl.java:629`) |
| STOMP | `CONNECT` / `SUBSCRIBE` on `/ws` | token-bearing | Authenticated by the same tokens (`StompAuthChannelInterceptor.java:34-104`) |

### 5.2 Services

- **`AuthServiceImpl`** (`process/src/main/java/process/model/service/impl/AuthServiceImpl.java`, 136
  lines) — the only implementation of `AuthService`. `login` (`:48-70`), `refresh` (`:72-99`),
  `checkAccountAndTenantActive` (`:101-112`), `buildAuthResponse` (`:114-134`).
- **`JwtUtil`** (`process/src/main/java/process/util/JwtUtil.java`) — mints and parses; the only place
  the claim names live (`:18-23`).
- **`JwtAuthenticationFilter`** — turns a bearer token into a `TenantContext` and an authentication.
- **`TenantSeedService.ensurePlatformAdmin`** (`:103-127`) — the bootstrap account.
- **`GlobalExceptionHandler`** (`process/src/main/java/process/config/GlobalExceptionHandler.java:24-30`)
  — turns an `AccessDeniedException` into a 403 carrying
  `{"status":"ERROR","message":"You don't have permission to perform this action."}`.

### 5.3 Configuration

| Property | Default | Source |
|---|---|---|
| `jwt.secret.key` | **none** — throws if unset | `application-dev/stage/prod.properties:15`, `JwtUtil.java:82-84` |
| `jwt.access-token.expiry-minutes` | 30 | `...:16`, `JwtUtil.java:28-29` |
| `jwt.refresh-token.expiry-days` | 7 | `...:17`, `JwtUtil.java:31-32` |
| `platform.admin.bootstrap-password` | **none** — no admin is seeded | `TenantSeedService.java:41-42` |

---

## 6. Database requirements

Two tables. Neither needs a schema change for this feature as specified; the migration listed at the end
is the one §12.4 would want.

### `app_user` (`process/src/main/java/process/model/pojo/AppUser.java`)

| Column | Type / mapping | Role in this feature |
|---|---|---|
| `app_user_id` | `Long`, sequence `app_user_Seq` from 1000 (`:39-51`) | The `appUserId` claim |
| `uuid` | `varchar(36)` unique (`:53-54`) | Not used at sign-in |
| `tenant_id` | `Long`, **nullable** (`:56-57`), FK added by `V12` | The `tenantId` claim. Null means platform-owned |
| `username` | `varchar` **not null, globally unique** (`:63-64`) | The login identity and the token subject |
| `password` | `varchar` not null, `@JsonIgnore` (`:66-68`) | BCrypt hash — never leaves the server |
| `full_name` | not null (`:70-71`) | `fullName` in the response |
| `user_role` | enum string, not null (`:73-75`) | The `userRole` claim |
| `status` | enum `Inactive/Active/Delete`, not null (`:77-79`) | Check 3 at sign-in |
| `last_login_at` | timestamp (`:84-85`) | Written on every successful login (`AuthServiceImpl.java:67`) |
| `must_change_password` | boolean not null default false (`:104-105`) | Added by `V21` |
| `avatar_bucket` / `avatar_key` | varchar (`:107-111`) | Carried in the sign-in response so the header can draw the picture immediately |

Added by `process/src/main/resources/db/changelog/changelog-sets/V21.0-tenant-request/V21__tenant_request.sql:35`:
`ALTER TABLE app_user ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;`

### `tenant` (`process/src/main/java/process/model/pojo/Tenant.java`)

Read at sign-in and at refresh for one reason only: `status` must be `Active`
(`AuthServiceImpl.java:107`). `TenantStatus` has four values — `Active, Inactive, Suspended, Delete`
(`process/src/main/java/process/model/enums/TenantStatus.java`).

### Migration this feature would need

Closing §12.4 at the data layer means `app_user.tenant_id` must be `NOT NULL` for every row whose
`user_role <> 'PLATFORM_ADMIN'`. Postgres expresses that as a check constraint, not a column
constraint — a platform admin legitimately has none:

```sql
ALTER TABLE app_user ADD CONSTRAINT ck_app_user_tenant_required
  CHECK (user_role = 'PLATFORM_ADMIN' OR tenant_id IS NOT NULL);
```

It must be preceded by a report of the offending rows, because `TenantSeedService.backfillTenantIds`
(`:129-142`) backfills six tables and **`app_user` is not one of them**.

---

## 7. Validation

| Rule | Client | Server | Verdict |
|---|---|---|---|
| Username required | `Validators.required` (`login.ts:24`) | `isNull` check (`AuthServiceImpl.java:49`) | Both |
| Password required | `Validators.required` (`login.ts:25`) | `isNull` check (`AuthServiceImpl.java:49`) | Both |
| Username trimmed | no | `.trim()` (`AuthServiceImpl.java:53`) | Server |
| Account exists and is not deleted | no | `findByUsernameAndStatusNot(..., Status.Delete)` (`:52-53`) | Server |
| Account is `Active` | no | `checkAccountAndTenantActive` (`:102-104`) | Server |
| Tenant is `Active` | no | `checkAccountAndTenantActive` (`:105-110`) | Server |
| Password matches the BCrypt hash | no | `passwordEncoder.matches` (`:64`) | Server |
| Refresh token parses and is signed by us | no | `jwtUtil.parseClaims` (`:79`) | Server |
| Refresh token is a refresh token, not an access token | no | `isRefreshToken` (`:84-86`) | Server |
| Access token is **not** a refresh token | `roleFromToken` does not check `type` (`auth.service.ts:20-31`) | `JwtAuthenticationFilter.java:39` | Server — fails safe: a swapped token yields a role in the browser but 401s on every call |
| `returnUrl` is an in-app path | `startsWith('/') && !startsWith('//')` (`login.ts:44-45`) | n/a | **Client only, and correctly so** — the value never leaves the browser |
| Route minimum role | `roleGuard` (`auth.guard.ts:33-42`) | `@PreAuthorize` on each controller | Both |
| Password debt blocks the session | `passwordChangeGuard` (`auth.guard.ts:59-67`) | **nothing** | **Client only — a finding, §12.5** |
| New password ≥ 8 characters | profile screen | `validateNewPassword` (`AppUserServiceImpl.java:368-370`) | Both — owned by `own-account-and-notifications` |

Two client-only rows appear above. `returnUrl` is legitimately client-only: it is a browser navigation
target the server never sees. The password debt is not — §12.5.

---

## 8. Security

### 8.1 The four layers, for this feature

| Layer | What it does here | Verdict |
|---|---|---|
| **Frontend guard** | `authGuard` on the shell; `roleGuard` per route from `data.minRole`; `passwordChangeGuard` as `canActivateChild`; `anonymousOnly` on `/` and `/login` (`auth.guard.ts`, `app.routes.ts:6-52`) | Correct, and pinned by `auth.guard.spec.ts:105-178`, which walks the real route table and fails if a route declares a `minRole` without running the guard |
| **Controller `@PreAuthorize`** | `AuthRestApi` carries **none**, by design; the two endpoints are `permitAll` (`SecurityConfig.java:37`) | Correct. Note the repeatability rule elsewhere: a method-level `@PreAuthorize` **replaces** the class-level one, so every override in `process/src/main/java/process/api/` has to be read on its own |
| **Service rule** | `AuthServiceImpl.checkAccountAndTenantActive` (`:101-112`), run at both login (`:60`) and refresh (`:93`) | Correct as far as it goes; **it never asks whether a non-platform-admin role is entitled to a null tenant** — §12.4 |
| **Hibernate filter** | `AppUser` and `Tenant` declare **no** `@Filter` — grep for `tenantFilter` across `process/src/main/java/process/model/pojo/` returns 15 files and neither of these is among them | Correct here, and deliberate: the login lookup runs before any tenant exists. Remember that a `@Filter` never applies to `findById` — which is exactly how the tenant is read at `AuthServiceImpl.java:106` — and silently no-ops on an entity that never declared one |

### 8.2 What each role may do in this feature

| Actor | May |
|---|---|
| **Anonymous** | Reach `/`, `/login`, `/docs`; POST `/auth.json/login`; POST `/auth.json/refresh` with a token they already hold. Nothing else — `.anyRequest().authenticated()` (`SecurityConfig.java:55`) |
| **TENANT_USER** | Hold a session; read their own name, role, tenant and picture from it; reach every ungated shell route; be refused at `/unauthorized` for any route naming a higher `minRole`. Subscribe only to `/topic/jobs.{ownTenantId}` (`StompAuthChannelInterceptor.java:94-99`) |
| **TENANT_ADMIN** | Everything above, plus every route whose `minRole` is `TENANT_ADMIN` — eleven of them in `app.routes.ts`. Still refused `admin/tenants`, `admin/tenant-requests` and `tools/search` |
| **PLATFORM_ADMIN** | Everything, across every tenant. Carries `tenant_id = null` by design (`AppUserServiceImpl.java:166-167`, `TenantSeedService.java:115`), which is what makes `TenantFilterHelper` disable the filter for it (`TenantFilterHelper.java:28-33`) and `TenantOwnership.isOwnedByCaller` return true unconditionally (`TenantOwnership.java:36-38`). It is the **only** role for which a null tenant is correct. It may subscribe to `/topic/jobs.all` (`StompAuthChannelInterceptor.java:86-89`) |

### 8.3 Properties worth stating plainly

- **Role and tenant come from the token, not from a per-request database read.** An access token issued
  before a user was deactivated, moved between tenants, or demoted keeps working until it expires —
  default 30 minutes. Status is re-checked only at `/auth.json/login` and `/auth.json/refresh`
  (`AuthServiceImpl.java:60,93`). Deactivating a user therefore takes effect within 30 minutes, not
  immediately.
- **There is no revocation.** No `jti`, no denylist, no `logout` endpoint. See §12.6.
- **No secret leaves the server.** `AppUser.password` is `@JsonIgnore` (`AppUser.java:66-68`) and the
  hash is never mapped into `AuthResponseDto`.
- **The signing key has no default.** `JwtUtil.secretKey()` throws rather than signing with an empty key
  (`:82-84`), which fails the whole application loudly rather than issuing forgeable tokens quietly.
- **The seeded admin cannot be guessed.** With `platform.admin.bootstrap-password` unset, no account is
  created at all (`TenantSeedService.java:108-113`) — the comment at `:94-102` records that it used to
  be the compiled-in string `admin`.

---

## 9. Error handling

| What fails | HTTP | Body | What the user sees |
|---|---|---|---|
| Blank username or password | 200 | `{status:"ERROR", message:"Username and password are required."}` | Blocked client-side first, so effectively unreachable |
| Unknown username | 200 | `... "Invalid username or password."` | That message in the inline block |
| Wrong password | 200 | same | Identical message — correct |
| Account `Inactive` | 200 | `... "This account is inactive. Contact your administrator."` | That message. **Shown before the password is checked** — §12.1 |
| Tenant not `Active` | 200 | `... "Your organization's access is currently suspended. Contact your administrator."` | That message. Says "suspended" for `Inactive` and `Delete` too, and for a missing tenant row (`AuthServiceImpl.java:107-109`) |
| Unhandled exception in login/refresh | 500 | `{status:"ERROR", message:"Some internal error occurred contact with support."}` (`AuthRestApi.java:36,46`) | `Could not reach the server.` is *not* shown — `login.ts:53` reads `err.error.message`, which is present, so the real message appears |
| Network down / CORS | 0 | none | `Could not reach the server.` (`login.ts:53`) |
| Expired access token on any call | 401 | Spring's default error body, **not** the `{status,message}` envelope (`SecurityConfig.java:33-34`) | Nothing — the interceptor refreshes and replays; the user sees no interruption |
| Expired refresh token | 200 | `... "Refresh token is invalid or expired -- please log in again."` | The session is cleared and the browser lands on `/login` **with no explanation** — §13.4 |
| Role refusal on a route | n/a | n/a | `/unauthorized`, naming the current role, with Go back and Dashboard |
| Role refusal on a call | 403 | `{status:"ERROR", message:"You don't have permission to perform this action."}` (`GlobalExceptionHandler.java:24-30`) | Whatever the calling screen does with it — **a 403 is not routed to `/unauthorized`** in either app |
| 200 with an empty body | 200 | rewritten to `{status:"ERROR", message:"The server returned an empty response."}` (`auth.interceptor.ts:28-39`) | That message, instead of a `Cannot read properties of null` crash |
| Retried request fails for its own reason after a successful refresh | any | as returned | Surfaced as-is; the session is **kept** unless it is a second 401 (`auth.interceptor.ts:117-132`) |

---

## 10. Dependencies

**This feature depends on nothing.** It is the root of the graph
(`../discovery/features.md` §5.1).

**Everything depends on it.** Every other feature draws its bearer token from
`core/auth/auth.interceptor.ts` and its role from `core/auth/auth.service.ts`; every shell route sits
behind `authGuard`; fifteen of the eighteen features gate at least one control on a capability computed
from `hasAtLeast`.

Coupling worth naming:

- **`own-account-and-notifications`** owns `/profile` and `changeOwnPassword`, which is the only way to
  settle the debt `passwordChangeGuard` enforces. The two are a single loop and must be tested together.
- **`tenants-and-users`** owns `app_user` and `tenant` writes. The check constraint in §6 and the
  null-tenant rows in §12.4 are its data to fix; this feature's job is to stop minting a session over
  them.
- **`source-jobs`** consumes the token over STOMP through `core/socket/job-events.service.ts:69-80`,
  whose connection follows `{destination, token}` — so a token refresh reconnects the socket and a
  sign-out tears it down.
- Infrastructure: `JWT_SECRET_KEY` and `PLATFORM_ADMIN_BOOTSTRAP_PASSWORD` must reach the container;
  the dev fallback key is in `process/docker-compose.yml:157`.

---

## 11. Acceptance criteria

Fixtures assumed throughout: tenant **A** (`Active`) with `admin_a` (`TENANT_ADMIN`) and `user_a`
(`TENANT_USER`); tenant **B** (`Active`) with `user_b`; a `PLATFORM_ADMIN` `padmin` with
`tenant_id = null`; all four `Active` and owing no password change unless a criterion says otherwise.

### Signing in

1. **A visitor posts `user_a`'s correct username and password to `/auth.json/login`.** The response is
   HTTP 200 with `status: "SUCCESS"` and a `data` object carrying a non-empty `accessToken` and
   `refreshToken`, `userRole: "TENANT_USER"`, `tenantId` = A, and `appUserId` = `user_a`'s id.
2. **The same visitor posts `user_a`'s username with a wrong password.** The response is
   `status: "ERROR"`, `message: "Invalid username or password."`, and carries **no** `data`.
3. **The same visitor posts a username no `app_user` row has.** The response is byte-for-byte the same as
   criterion 2 — same status, same message, no `data`, no field naming the username.
4. **Positive control for 2 and 3 on the same fixture:** criterion 1 still succeeds for `user_a`
   immediately afterwards, proving the refusals came from the credential and not from a broken fixture.
5. **`user_a` is set to `Status.Inactive` and posts their correct password.** The response is
   `status: "ERROR"` and the account-inactive message. **`user_b`, untouched, signs in successfully on
   the same run.**
6. **Tenant A is set to `Suspended`; `user_a` posts their correct password.** The response is
   `status: "ERROR"` with the organisation message. **`user_b`, in tenant B, signs in successfully on
   the same run.**
7. **`padmin` (no tenant) signs in.** Success — a null `tenant_id` must not be mistaken for a suspended
   tenant. This is the positive control for criterion 6's tenant lookup.
8. **`user_a` signs in with the username in a different case (`USER_A`).** *Target behaviour:* success,
   same session as criterion 1. *Today:* refused with "Invalid username or password." — §12.2. This
   criterion is expected to fail until that is fixed and is the check that proves it was.
9. **Any client posts 20 wrong passwords for `user_a` within one minute.** *Target behaviour:* at least
   the last of them is refused without a password comparison being attempted, and `user_a` can still
   sign in correctly after the window. *Today:* all 20 are processed identically — §12.3.
10. **A successful sign-in advances `app_user.last_login_at`.** Read the column before and after
    criterion 1; the second value is greater. It is unchanged for the refusals in 2, 3, 5 and 6.

### The token

11. **Decode the access token from criterion 1.** Its claims include `userRole`, `tenantId`, `appUserId`,
    `type: "access"`, and its `exp` is `iat` + `jwt.access-token.expiry-minutes`.
12. **Call any authenticated endpoint with the *refresh* token from criterion 1 in the `Authorization`
    header.** The response is 401. **The same call with the access token succeeds** — the paired positive
    control, and the reason `JwtAuthenticationFilter.java:39` exists.
13. **Call any authenticated endpoint with a token signed by a different key.** 401. **The same call with
    a correctly signed token succeeds.**
14. **Start the application with `jwt.secret.key` empty and attempt a sign-in.** The request fails and the
    log names the missing key; no token is issued. It must not fall back to any built-in key.

### Refresh

15. **Post the refresh token from criterion 1 to `/auth.json/refresh`.** `status: "SUCCESS"`, `data`
    carries an `accessToken` and **no** `refreshToken` and **no** `mustChangePassword`.
16. **Post an *access* token to `/auth.json/refresh`.** `status: "ERROR"`, `"Not a refresh token."`
    **Posting the real refresh token immediately after still succeeds.**
17. **Deactivate `user_a`, then post their still-valid refresh token.** `status: "ERROR"`,
    `"Account no longer active -- please log in again."` **`user_b`'s refresh, run in the same test,
    succeeds.**
18. **Suspend tenant A, then post `user_a`'s refresh token.** Same refusal. **`user_b`'s refresh
    succeeds.**
19. **Six calls hit an expired access token at once in the browser.** The network log shows exactly
    **one** POST to `/auth.json/refresh`, and all six original requests complete successfully with the new
    token. (`auth.interceptor.spec.ts:62-78` asserts this at unit level; this is the browser check.)
20. **The same six calls, with the refresh token also expired.** All six subscribers receive an error —
    none is left pending — and the browser ends on `/login`. (`auth.interceptor.spec.ts:40-60`.)
21. **A refreshed request then returns 500.** The 500 is surfaced to the caller and the session is
    **not** ended; the user stays on the page. (`auth.interceptor.spec.ts:130-157`.)

### Guards and roles

22. **Signed out, open `/jobs` directly.** The browser lands on `/login?returnUrl=%2Fjobs`; after signing
    in it lands on `/jobs`, not on `/dashboard`.
23. **Signed out, open `/login?returnUrl=https://example.com`.** After signing in the browser is on `/`
    (which resolves to `/dashboard`), never on `example.com`. **With `returnUrl=/queue` the same flow
    lands on `/queue`** — the positive control proving the guard did not simply ignore the parameter.
24. **Signed in as `user_a`, open `/admin/users`.** The browser lands on `/unauthorized` and the page
    names the role as "tenant user". **`admin_a` opening `/admin/users` sees the users screen.**
25. **Signed in as `admin_a`, open `/admin/tenants`.** `/unauthorized`. **`padmin` opening
    `/admin/tenants` sees the tenants screen.**
26. **Signed in as `padmin`, open `/admin/users`** — a route whose minimum is `TENANT_ADMIN`. It opens.
    A higher role must satisfy a lower minimum (`auth.guard.spec.ts:45-49`).
27. **With devtools, rewrite `userRole` to `PLATFORM_ADMIN` inside `localStorage.etl_auth_user` while
    signed in as `user_a`, and reload.** The Administration and Configuration menus stay hidden, `/admin/tenants`
    still lands on `/unauthorized`, and `AuthService.role()` still reports `TENANT_USER`.
28. **Corrupt the access token in `localStorage` to an unparseable string and reload.** Every guarded
    route resolves to `/unauthorized` rather than opening — `hasAtLeast` fails closed with no readable
    role (`auth.guard.spec.ts:56-58`).
29. **Signed in, open `/login`.** The browser is redirected to `/dashboard` and the sign-in form is never
    rendered. **Signed out, `/login` renders the form.**
30. **Signed in, open `/`.** The dashboard. **Signed out, `/` renders the landing page.**
31. **Open `/no-such-page`.** Signed out → the landing page; signed in → the dashboard.
32. **Every route in `app.routes.ts` that declares `data.minRole` also lists `roleGuard` in its own
    `canActivate`.** Asserted structurally over the real table (`auth.guard.spec.ts:117-123`); it must
    keep passing after any route is added.

### The password debt

33. **`padmin` is seeded and signs in for the first time.** The sign-in response carries
    `mustChangePassword: true`, and the browser is on `/profile`.
34. **That session tries to open `/dashboard`, `/jobs` and `/admin/users`.** Each redirects to `/profile`.
    **Sign out from the same session still works** — it is a control in the shell, not a child route.
35. **That session changes its password successfully.** Without a reload, `/dashboard` now opens — the
    interceptor cleared the flag on the response (`auth.interceptor.ts:62-64`).
36. **That session reloads the page after the change.** It is still free — the cleared flag was persisted,
    not merely held in a signal (`auth.service.spec.ts:142-148`).
37. **The same session calls `/sourceJob.json/listSourceJob` with its token *before* changing the
    password, bypassing the browser.** *Target behaviour:* refused. *Today:* it succeeds — §12.5. This
    criterion is expected to fail until the server-side gate exists.

### Tenancy

38. **`user_a` signs in and lists source jobs.** Only tenant A's jobs come back. **`user_b` doing the same
    sees only tenant B's** — neither list contains the other's rows.
39. **An `app_user` row exists with `user_role = 'TENANT_USER'` and `tenant_id = NULL`.** *Target
    behaviour:* either sign-in is refused, or the session sees **zero** rows on every tenant-filtered
    entity. *Today:* sign-in succeeds and the session sees **every tenant's** rows — §12.4. **Positive
    control on the same fixture: `user_a`, with a tenant, still sees only tenant A's rows.**
40. **`user_a` subscribes over STOMP to `/topic/jobs.<tenantB>`.** The frame is dropped and no events
    arrive. **Subscribing to `/topic/jobs.<tenantA>` delivers events on the same connection.**
41. **`user_a` subscribes to `/topic/jobs.all`.** Refused. **`padmin` subscribing to `/topic/jobs.all`
    receives events.**

### Sign-out and session lifetime

42. **Signed in, choose Sign out.** `localStorage.etl_auth_user` is gone, the browser is on `/login`, the
    STOMP connection is closed, and pressing Back does not restore a working console.
43. **After signing out, replay the old refresh token against `/auth.json/refresh`.** *Target behaviour:*
    refused. *Today:* it mints a working access token for the remainder of seven days — §12.6.
44. **Sign out in tab 1 while tab 2 is open on `/jobs`.** *Target behaviour:* tab 2 also ends its session.
    *Today:* tab 2 continues working until its access token expires — §12.7.

### Presentation

45. **Set the theme to dark in the shell, sign out, and load `/login` fresh (a full browser reload, not
    an in-app navigation).** *Target behaviour:* the page renders dark. *Today:* it renders light —
    §12.8. **Control on the same run: `/` and `/docs` both render dark.**
46. **Load `/login` at 375 px wide.** The form is the full width, nothing scrolls horizontally, and the
    right-hand preview panel is not rendered.
47. **Load `/` at 375 px, 768 px and 1440 px.** The capability grid is 1, 2 and 3 columns respectively,
    and the page never scrolls horizontally at any of the three.
48. **With `prefers-reduced-motion: reduce`, load `/`.** No entry animation runs and no connecting rule
    animates (`landing.ts:60`).
49. **Signed in as each of the three roles in turn, open the shell.** The nav shows Administration and
    Configuration for `admin_a` and `padmin` and neither for `user_a`; Tenants and Workspace Requests
    appear only for `padmin`; Source Tasks, AI Agents and Query Engine appear for all three
    (`shell.ts:140-151`).
50. **Signed in, open the user menu.** It shows the avatar or two-letter initials, the display name and
    the role. It closes on an outside click and on Escape.

### The tenant-less caller

These exist because the sentinel-only version of the tenancy fix passes a test written against
`source_job` and fails silently on the four shared catalogues. A criterion that names only one
entity cannot tell the two fixes apart, so each of the four is asserted by name.

51. **A token carrying `TENANT_USER` and no tenant claim calls `GET /sourceJob.json/listSourceJob`.**
    Zero rows. **Positive control:** the same call carrying tenant A's claim returns tenant A's jobs.
52. **The same tenant-less token calls `GET /storageConnection.json/fetchAllConnections`.** Zero rows
    — in particular **not** `etl-avatar` or `etl-bucket`, whose `tenant_id` is null.
    **Positive control:** a `PLATFORM_ADMIN` receives both platform rows from the same call.
53. **The same tenant-less token reads the other three shared catalogues** — Kafka connection
    profiles, source task types and task forms. Each returns zero rows, and no platform-owned row
    appears in any of them. **Positive control:** tenant A's `TENANT_ADMIN` sees its own rows in all
    three; a `PLATFORM_ADMIN` sees the platform's.
54. **No store location leaks with them.** For every response above, no `sslKeystoreLocation`,
    `sslTruststoreLocation` or bucket name belonging to a profile the caller does not own appears in
    the body.

> 52 and 53 are the criteria that distinguish a working fix from the sentinel-only one. A change that
> satisfies 51 alone has closed the narrow filters and left the four wide ones open, which is the
> more serious of the two halves.

---

## 12. Known issues

### 12.1 Login discloses whether an account exists, before the password is checked — **major**

`AuthServiceImpl.login` runs the status check at `:60-63` and the password comparison at `:64-66` — in
that order. So for a username that exists but is `Inactive`, or whose tenant is not `Active`, an
attacker supplying **any** password gets `"This account is inactive. Contact your administrator."` or
`"Your organization's access is currently suspended. Contact your administrator."`, while an unknown
username gets `"Invalid username or password."`. The two are trivially distinguishable, so the endpoint
answers "does this account exist?" to an unauthenticated caller.

The same ordering makes the response measurably faster for an unknown username, because
`passwordEncoder.matches` — a deliberately slow BCrypt comparison — is never reached (`:56-58` returns
before `:64`).

### 12.2 Sign-in is case-sensitive on an email-shaped username — **major**

`findByUsernameAndStatusNot(loginRequestDto.getUsername().trim(), Status.Delete)`
(`AuthServiceImpl.java:52-53`) is an exact match, and the stored value is only trimmed on creation
(`AppUserServiceImpl.java:192`) — never lowercased. Usernames are email addresses throughout the product
(the users dialog treats the field as one, and `notifyNewUser` mails the credential to it,
`AppUserServiceImpl.java:226-237`). A user whose account is `Jane.Doe@corp.com` and who types
`jane.doe@corp.com` — which every mail client and password manager will offer them — is told their
password is wrong. Neither frontend normalises the field either
(`login.ts:35`, `scheduler1/src/app/_component/login/login.component.ts:47`).

### 12.3 No throttling, lockout or delay on `/auth.json/login` — **major**

Grepping `process/src/main/java` and `process/pom.xml` for `bucket4j`, `RateLimit`, `failedAttempt`,
`lockout` and `loginAttempt` returns nothing. `AppUser` has no failed-attempt counter
(`AppUser.java:26-111`), and `SecurityConfig` installs no filter in front of the permitted matcher
(`SecurityConfig.java:36-56`). The endpoint accepts unlimited guesses at full speed from a single
source, and combined with §12.1 an attacker can first enumerate valid usernames and then grind them.

### 12.4 A session with no tenant is issued to any role, and then sees every tenant — **blocker**

Two facts that are individually defensible combine into cross-tenant exposure.

**Fact one.** `checkAccountAndTenantActive` skips the tenant check entirely when `tenantId` is null:

```java
if (!isNull(user.getTenantId())) {          // AuthServiceImpl.java:105
    Optional<Tenant> tenantOpt = ...
}
return null;                                 // :111
```

It never asks whether the *role* is entitled to a null tenant. `buildAuthResponse` then mints a token
carrying `tenantId: null` for whatever role the row holds (`:114-134`, via `JwtUtil.java:47-48`).

**Fact two.** `TenantFilterHelper.enableIfNeeded` treats a null tenant as "no filtering needed",
regardless of role:

```java
if (tenantId == null || TenantContext.isPlatformAdmin()) {   // TenantFilterHelper.java:28
    ... session.disableFilter(FILTER_NAME);                  // :30
    return;
}
```

So a `TENANT_USER` or `TENANT_ADMIN` whose `app_user.tenant_id` is NULL signs in successfully and every
list query over the fifteen `tenantFilter` entities runs **unfiltered** — that caller reads every
tenant's source jobs, tasks, task types, storage connections, Kafka profiles, AI agents, dynamic forms,
query definitions, query executions and PDF highlighter tasks.

The codebase already knows this is the wrong reading. `TenantOwnership` says so in its own header —
"a context with no tenant owns nothing, so it is refused outright" — and `isOwnedByCaller` implements
it (`process/src/main/java/process/security/TenantOwnership.java:14-15, 35-41`). The list path and the
by-id path therefore **disagree**: such a caller can read every tenant's rows in a list and is refused
when it tries to act on one by id.

**Reachability, stated honestly.** The two write paths are closed today: `AppUserServiceImpl.addUser`
refuses a non-platform-admin role with no tenant when the actor is a platform admin
(`:168-171`, `"Tenant missing."`), and `updateUser` refuses to leave one without a tenant
(`:300-302`). What is *not* closed:

- `app_user.tenant_id` is nullable in the mapping (`AppUser.java:56-57`), the `V12` FK adds no NOT NULL
  (`process/src/main/resources/db/changelog/changelog-sets/V12.0-tenant-user-fk-constraints/V12__add_tenant_user_fk_constraints.sql:35`
  is the only `app_user` statement in the file, and the file contains no `NOT NULL` at all), and
  `TenantSeedService.backfillTenantIds` backfills six tables — `app_user` is **not** among them
  (`TenantSeedService.java:129-142`). Any pre-existing or hand-inserted row survives untouched.
- If such a row exists and is a `TENANT_ADMIN`, `addUser` propagates it: with the actor's own tenant
  null, `targetTenantId = TenantContext.getTenantId()` is null (`AppUserServiceImpl.java:173-175`) and
  the `!isNull(targetTenantId)` guard at `:177` is skipped.

So this is not reachable by clicking through today's UI, and it is a defence-in-depth failure at the
layer whose job is to decide whether a session should exist at all.

### 12.5 The forced password change is enforced only in the browser — **major**

`passwordChangeGuard` (`auth.guard.ts:59-67`) pins a session owing a change to `/profile`. Nothing on
the server does. Grepping `process/src/main/java` for `mustChangePassword` returns only the places that
**set** it (`TenantSeedService.java:121`, `TenantRequestServiceImpl.java:180`,
`AppUserServiceImpl.java:199,356`), **clear** it (`AppUserServiceImpl.java:629`) and **report** it
(`AuthServiceImpl.java:132`, `AppUserServiceImpl.java:571`) — no `@PreAuthorize`, no filter and no
service check refuses a call because of it.

An account created with a generated password therefore holds a fully-powered session from the moment it
signs in. Anyone who reads the emailed credential — it is sent in the body of a mail
(`AppUserServiceImpl.java:226-237`) — can use the API directly and never change it. The whole point of
`must_change_password`, stated at `AppUser.java:100-103`, is that the emailed credential is *one-time*;
today it is one-time only for people who use the console.

### 12.6 Signing out does not end the session; there is no revocation at all — **major**

`AuthService.logout()` removes a `localStorage` key and navigates (`auth.service.ts:199-202`); the old
app does the same (`scheduler1/src/app/_services/auth.service.ts:55-58`). There is no `/auth.json/logout`
endpoint — `AuthRestApi` has exactly two methods — and `JwtUtil.buildToken` mints no `jti`
(`JwtUtil.java:42-54`), so there is nothing to revoke against and no denylist to revoke into. A refresh
token captured from a shared machine, a proxy log or a browser backup keeps minting access tokens for
its full seven days, whether or not its owner signed out, and whether or not they changed their password
— `changeOwnPassword` does not touch token validity (`AppUserServiceImpl.java:627-631`).

### 12.7 A sign-out in one tab is invisible to another — **minor, and a regression from the old app**

The new service hydrates the session **once**, at construction:
`private readonly currentUser = signal<AuthUser | null>(this.readStoredUser());`
(`auth.service.ts:39`). Nothing listens for the `storage` event. The old service read
`localStorage.getItem` on **every** access to `currentUser` (`scheduler1/src/app/_services/auth.service.ts:69-72`),
so `AuthGuard`'s next check in a second tab saw the cleared key and redirected. In the new app the second
tab keeps its in-memory token and carries on until that token expires — up to 30 minutes after the user
believed they had signed out.

### 12.8 `/login` never applies the dark theme on a cold load — **minor**

`html.dark` is set by an effect inside `ThemeService`
(`scheduler1/next/src/app/core/theme.service.ts:14-20`), which is `providedIn: 'root'` and therefore
instantiated lazily. Grepping `scheduler1/next/src` for `ThemeService` returns exactly four injectors:
`landing.ts:206`, `docs.ts:266`, `request-workspace.ts:120` and `shell.ts:34`. **`features/login/login.ts`
is not among them**, and neither `App` (`scheduler1/next/src/app/app.ts`) nor `appConfig`
(`app.config.ts:7-14`) touches it. There is also no theme-bootstrapping script in
`scheduler1/next/src/index.html`.

Consequence: any load whose *first* rendered route is `/login` — a bookmark, a typed URL, a browser
refresh on the sign-in page, or a deep link that `authGuard` bounces before the shell ever constructs —
renders the light palette regardless of the stored `etl_theme` value or the OS preference. Signing in
then flips the whole console to dark. The right-hand panel is `bg-ink-900` unconditionally
(`login.html:52`), so the mismatch is visible as a light form beside a dark panel.

The login page also has **no theme toggle at all**, while `/` (`landing.ts:76`), `/docs`
(`docs.ts:71`) and the shell (`shell.html:66`) all have one — so a visitor who arrives there cannot
correct it either.

### 12.9 The old app's login page advertises a credential that no longer works — **minor, old app only**

`scheduler1/src/app/_component/login/login.component.html:30` reads
"Use **admin@platform.local** / **admin@platform.local** to sign in (change the password after)". The
password has not been that since `TenantSeedService` started taking it from
`platform.admin.bootstrap-password` with no default (`TenantSeedService.java:41-42, 103-113`) — the
comment at `:94-102` records the change. The hint is now both wrong and an invitation to guess. The new
app dropped it, correctly. Recorded because the old app is still deployed, not because it is in scope to
change.

### 12.10 Small things, worth fixing when the file is open

- **The bearer token is attached to `/auth.json/` calls too.** `auth.interceptor.ts:55` calls
  `next(withToken(auth.accessToken))` unconditionally; `isAuthCall` is only consulted in the error path
  (`:68`). Refresh therefore carries the expired access token, which `JwtAuthenticationFilter` parses,
  rejects and logs at debug on every renewal (`JwtAuthenticationFilter.java:50-53`). Harmless — the
  matcher is `permitAll` — but noisy. The old app excluded them (`auth.interceptor.ts:22-27`).
- **`ROLE_META` is bypassed by two of this feature's own screens.** `auth.models.ts:28-47` exists so a
  role has one label; `shell.html:93` renders `auth.role()?.replace('_',' ') | lowercase` and
  `unauthorized.ts:38` does `role.toLowerCase().replace(/_/g,' ')`. The users list uses `ROLE_META`, so
  the same role reads "Tenant admin" on one screen and "tenant admin" on another.
- **The tenant refusal message says "suspended" for four different states.**
  `AuthServiceImpl.java:107-109` returns the same sentence for `Inactive`, `Suspended`, `Delete` and a
  missing tenant row.
- **`RoleGuard.exactUsernames` in the old app is dead.** `scheduler1/src/app/_helpers/role.guard.ts:18,23-24`
  reads `route.data.exactUsernames`; grepping `scheduler1/src` finds that identifier only in the guard
  itself. Not migrated, and correctly so.
- **`AuthServiceImpl.login` saves the user row on every sign-in** (`:67-68`) to stamp `lastLoginAt`.
  `AppUser` carries `@EntityListeners(AuditListener.class)` (`AppUser.java:24`), and at that moment
  `TenantContext` is empty because the matcher is `permitAll`. `AuditListener.onUpdate` returns early
  when the actor is null (`AuditListener.java:46-49`), so `updated_by` is correctly left alone. Verified,
  not a defect — recorded because it looks like one.

---

## 13. Missing functionality

### 13.1 Nothing was lost in the migration

Every old-app capability in this feature has a successor, and most were improved on. The comparison,
behaviour by behaviour:

| Old app | New app | Verdict |
|---|---|---|
| Welcome page, 7 feature cards + 3 steps (`welcome.component.ts:27-76`) | Landing, 9 capabilities + 4 steps + 3 facts, theme toggle, links to docs and workspace request (`landing.ts:212-257`) | Superset |
| Login form, two required fields | Same, plus a submitting state and an open-redirect guard | Superset |
| Demo credentials printed on the login page (`login.component.html:30`) | Dropped | Deliberate improvement — §12.9 |
| Toast **and** inline message on a failed sign-in (`login.component.ts:51`) | Inline message only (`login.html:37-41`) | Deliberate — one message per failure |
| `returnUrl` followed unvalidated (`login.component.ts:30,54`) | Validated as an in-app path (`login.ts:43-45`) | Improvement |
| Unauthorized page, static text + Home (`unauthorized.component.html`) | Names the current role, Go back + Dashboard (`unauthorized.ts:10-30`) | Improvement |
| `RoleGuard` comparing role strings against a list (`role.guard.ts:17-27`) | `roleGuard` comparing a rank against one minimum (`auth.guard.ts:33-42`) | Improvement — the hierarchy is expressed once |
| `RoleGuard.exactUsernames` (`role.guard.ts:18`) | Absent | Dead in the old app; correctly dropped |
| Role read from `localStorage` (`role.guard.ts:19`, `app.component.html:29,45,…`) | Read from the JWT (`auth.service.ts:20-31`) | Improvement — closes a devtools escalation |
| Nav gated by seven hand-written role pairs (`app.component.html`) | One `allNav` table filtered once (`shell.ts:48-151`) | Improvement |
| Shared refresh via `shareReplay(1)` (`auth.interceptor.ts:48-56`) | Single-flight queue that can fail its waiters (`auth.interceptor.ts:79-133`) | Improvement — a refused refresh no longer strands parallel requests |
| `logout()` also tears down the notification stream (`app.component.ts:130-137`) | The socket follows `{destination, token}` and tears itself down (`job-events.service.ts:73-81`) | Equivalent, and does not need remembering |
| `**` → `home` (`app.routing.ts:277-280`) | `**` → `''` (`app.routes.ts:285`) | Equivalent; the new one is friendlier when signed out |
| — | `mustChangePassword` + `passwordChangeGuard` | Addition |
| — | `anonymousOnly`, so `/` and `/login` mean two things | Addition |
| — | Avatar in the session, fetched as a blob (`auth.service.ts:139-154`) | Addition |
| — | Dark mode | Addition (but see §12.8) |
| — | `/docs` | Addition |
| — | Three spec files, 510 lines | Addition — the old app has none |
| Session re-read from `localStorage` on every access (`auth.service.ts:69-72`) | Read once into a signal (`auth.service.ts:39`) | **The one regression** — §12.7 |

### 13.2 Server-side enforcement of the password debt

Absent — §12.5. **What it would take:** a small `HandlerInterceptor` or a `OncePerRequestFilter` after
`JwtAuthenticationFilter` that reads `TenantContext.getAppUserId()`, and refuses every request other
than `changeOwnPassword`, `me` and `logout` with a 403 while the account owes a change. The flag has to
come from somewhere: putting it in the token is one line in `JwtUtil.buildToken` but makes it stale for
30 minutes after the change, so a per-request read of `app_user.must_change_password` — one indexed
primary-key lookup — is the honest option. Small, and it needs a decision (see synthesis, open question 2).

### 13.3 Token revocation and a real sign-out

Absent — §12.6. **What it would take:** a `jti` claim on the refresh token, a `POST /auth.json/logout`
that records it, and a check in `AuthServiceImpl.refresh`. The store can be Redis, which is already in
the stack. Alternatively a `token_valid_from` timestamp per user, compared against the token's `iat`,
which revokes everything at once on sign-out and on password change and needs no new store — one
nullable column on `app_user`. The second is smaller and covers the password-change case the first does
not.

### 13.4 A reason when the session ends

When a refresh is refused, `auth.logout()` navigates to `/login` and the person is looking at an empty
sign-in form with no idea why (`auth.interceptor.ts:109,125,130`). **What it would take:** navigate to
`/login?reason=expired` (or a small signal on `AuthService`) and render one line above the form —
"Your session ended. Please sign in again." Trivial, and it is the difference between a bug report and a
shrug.

### 13.5 A way off the sign-in page

`login.html` contains no links at all — not to `/`, not to `/docs`, not to `/request-workspace` — while
the landing page and the docs page both link to each other and to sign-in (`landing.ts:72,101,104`;
`docs.ts:63,74,258-259`). Someone whom `authGuard` dropped on `/login` from a deep link has no way back
to the public site short of editing the URL, and no route to `Request a workspace` — the page that
exists precisely for people who cannot sign in.

### 13.6 Password recovery

There is no "forgot password" anywhere in either frontend or on the server. The only reset path is
`appUser.json/resetPassword`, which is `TENANT_ADMIN` (`tenants-and-users`) — so a user who forgets
their password must ask an administrator. That may well be the right call for a B2B console; it is
recorded here because it is absent rather than decided.

### 13.7 Multi-factor authentication and session listing

Neither exists, and neither is claimed anywhere. Recorded so that a later "why is there no MFA?" has an
answer with a date on it.

### 13.8 Tests

Named in §2.4. The gaps that matter most: **no test exercises `/auth.json/login` or
`/auth.json/refresh` over HTTP at all**, and there is no spec for `login.ts` — so the open-redirect
guard at `login.ts:43-45`, which is this feature's only piece of client-side security logic, is
unpinned. An E2E class alongside the eight in `process/src/test/java/process/e2e/` would cover
criteria 1-10 and 15-18 directly; `E2ESupport` already builds real users and mints real tokens
(`E2ESupport.java:96,113`), so the fixture work is done.
