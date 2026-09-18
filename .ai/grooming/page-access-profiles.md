# Grooming -- `page-access-profiles`

**Row 20 of [../discovery/features.md](../discovery/features.md). Status `new`: the old app has no
per-page access at all.** Groomed after the fact on 2026-09-17: the feature was designed and
built in one session (see [../synthesis/page-access-profiles.md](../synthesis/page-access-profiles.md)
for the options weighed), and this document records what it has to do so the next change to it
starts from the requirement rather than from the code.

Paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

## 1. Purpose

Roles say how much a person may do (`PLATFORM_ADMIN` > `TENANT_ADMIN` > `TENANT_USER`). They say
nothing about **which pages** a tenant user should see. A workspace with an operator who only runs
jobs and an analyst who only reads reports had one choice: show everyone everything. An access
profile is a named bundle of pages -- "Operator", "Analyst" -- that a tenant user holds, with a
per-person exception when one person needs one page more or less than their profile.

## 2. Current behaviour (as built)

| Layer | Where | What |
|---|---|---|
| Catalogue | `process/src/main/java/process/model/enums/PageKey.java` | Ten gated pages -- `jobs`, `tasks`, `queue`, `reports`, `objects`, `analytics`, `analytics-dashboards`, `tools-converter`, `tools-transcript`, `ai-agents` -- each with the API prefixes it owns. Dashboard, Profile and Notifications are never gated; Configuration and Administration stay admin-only by role |
| Schema | `process/src/main/resources/db/changelog/yaml/V40.0-page-access-profiles.yaml`, `V41.0-user-page-access.yaml` | `page_access_profile` (tenant-scoped, `is_default`), `page_access_profile_page` (one row per page), `app_user.page_access_profile_id`, `user_page_access` (per-person exceptions: user, page, open/withheld) |
| Resolution | `PageAccessServiceImpl.resolve` (`process/src/main/java/process/model/service/impl/PageAccessServiceImpl.java`) | Admins → every page. Tenant user → own profile, else the workspace default, else every page; then the person's exceptions applied on top |
| Enforcement | `process/src/main/java/process/security/PageAccessInterceptor.java:53`, cached by `PageAccessCache` (15 s TTL) | A tenant user calling an API group behind a withheld page gets **403**, whatever the browser shows |
| API | `PageAccessRestApi` at `/pageAccess.json/*` | catalogue, mine, list/add/update/delete/setDefault profiles, people, assignProfile, setPageAccess, clearPageAccess, requestAccess |
| Sign-in | `AuthResponseDto.pageKeys`, `pageAccessProfileName` | The resolved page list travels with the login and refresh responses |
| Console | `scheduler1/next/src/app/core/auth/auth.guard.ts:53` (`pageGuard`), `auth.service.ts:106` (`canOpen`), `app.routes.ts` (`data.pageKey` on 20 routes), `features/shell/shell.ts` (menu filtering), `features/unauthorized/` ("Request access") | A withheld page leaves the menu; a direct link lands on Unauthorized with a Request-access button that notifies every admin of the workspace |
| Management | `features/admin/access-profiles/` at `admin/access-profiles` -- cards grouped by section, and a **People × pages grid** (`access-people-grid.ts`) with a checkbox per person per page; per-person ticks become exceptions, marked amber, with "reset to profile". A platform admin picks the workspace first (`?tenantId=`), deep-linkable with `?view=people&q=` | |
| Users screen | `features/admin/users/` -- Access column, card line, "Filter by access profile", "Page access" row action; the dialog assigns a profile | |
| Notifications | `NotificationType.PAGE_ACCESS_REQUESTED`, `PAGE_ACCESS_CHANGED` | Profile change notifies everyone on it; a request notifies the workspace's admins |

## 3. Requirements

1. A tenant admin manages the profiles of their own workspace; a platform admin manages any workspace's, after naming it.
2. The first profile a workspace creates becomes its default. Exactly one default per workspace; a workspace with no profile keeps showing every page (nothing changes for workspaces that never opt in).
3. A profile that people still hold cannot be deleted.
4. Enforcement is server-side: the guard and the menu are courtesy, the interceptor is the rule.
5. Per-person exceptions are visible as exceptions -- never mistakable for the profile -- and reversible in one click.
6. Changing a profile's pages notifies the people on it; asking for a page notifies the admins.

## 4. Validation and security

- Profile name unique within the workspace; page keys validated against `PageKey`.
- A tenant admin cannot address another workspace's profile or person (tenant filter on every repository read; `TenantOwnership`).
- The interceptor reads the cached resolution, so a change takes at most 15 s to bite on the API; the console re-reads `pageKeys` on refresh.
- `requestAccess` has **no throttle** -- flagged, not fixed (see synthesis §6).

## 5. Acceptance criteria (verified 2026-09-17)

- Playwright `scheduler1/next/e2e/access-profiles.spec.ts`; vitest specs under `features/admin/access-profiles/` (21) and `features/admin/users/` (14).
- Scripted browser flows over three roles (87 screens) and the Users/profiles flows: zero console errors.
- Documented for users at `/docs` (step "Decide which pages each person opens") and for engineers in `process/ext-detail/md/PAGE_ACCESS_PROFILES.md`.

## 6. Known issues / open

- `requestAccess` can be spammed (no rate limit).
- The default profile's "people covered" count includes everyone without a profile of their own -- by design, but it surprised one reader; the card now says so.
