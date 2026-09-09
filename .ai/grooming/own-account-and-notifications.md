# Grooming -- Own Account and Notifications

Feature `own-account-and-notifications`, migration status **migrated**. All paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Purpose

This is the only part of the console that is about the person using it rather than about the work.
It answers two questions.

**"What happened to my work while I was not looking?"** A job the user owns finished, or failed, or
somebody handed them a new one, or a bulk upload they started finished writing rows. The
notification centre is where those events wait. It is not a log -- a log is a record of what the
system did, and this is a short list of the things that happened *to you*, each one with a link
back to the screen it is about, and a read/unread state so the same thing is not read twice.

**"Is this me, and is this what other people see?"** The profile screen is where somebody corrects
their own display name, sets their job title and phone number, puts a face beside their name, and
changes their own password. It deliberately does not let them change their role, their tenant or
their account status -- those are an administrator's decisions about them, not their own -- and it
carries one small activity card so that opening it answers "how are my jobs doing" without a
detour to the dashboard.

There is one hard rule underneath both halves: *everything on these screens is derived from the
token, never from the request*. No endpoint here takes a user id. There is nothing to point at
somebody else.

---

## 2. Existing behaviour

The notification centre exists in both applications. The profile screen exists **only in the new
one** -- the old app has no `profile` route (`scheduler1/src/app/app.routing.ts` lists 40 paths and
none of them is `profile`), and none of `appUser.json/me`, `/updateOwnProfile`,
`/changeOwnPassword`, `/updateOwnAvatar` or `sourceJob.json/myActivity` is called anywhere under
`scheduler1/src/app`. Avatars, phone numbers, job titles and the password-change debt are all
additions of the rewrite.

### 2.1 Routes, guards and entry points

| | Old (`scheduler1/src/app`) | New (`scheduler1/next/src/app`) |
|---|---|---|
| Notification route | `notifications` → `NotificationCenterComponent`, `AuthGuard` only (`app.routing.ts:193-197`) | `notifications` → `Notifications` (`app.routes.ts:155-158`), under the shell's `authGuard` + `passwordChangeGuard` (`app.routes.ts:49-52`) |
| Profile route | none | `profile` → `Profile` (`app.routes.ts:151-153`), same two shell guards |
| Role requirement | none beyond signed-in | none; neither child declares `minRole`, so no `roleGuard` runs |
| Header entry | bell dropdown in the navbar (`app.component.html:85-124`) + user card (`:125-142`) | `<app-notification-bell />` (`features/shell/shell.html:65`) + user menu with "Your profile" (`shell.html:96-99`) |
| Nav entry | none for either | none for either -- `features/shell/shell.ts` builds `nav()` with no `/notifications` or `/profile` item |
| Theme | light only; the old app has no dark mode | theme-aware via `core/theme.service.ts` (class `html.dark`, OS default, persisted to `etl_theme`) |

`passwordChangeGuard` (`core/auth/auth.guard.ts:59-67`) is new and matters here: while
`auth.mustChangePassword()` is true, every child of the shell except one whose URL starts with
`/profile` is redirected to `/profile`. That makes the profile screen the only page a freshly
created account can open, and the password card on it the only way out.

### 2.2 The notification centre -- old app

`_component/notification-center/notification-center.component.ts` (93 lines) and its template.

- Two tabs, **All** and **Unread**, as `unreadOnly` (`:15`, `:33-40`). Switching resets to page 1
  and re-fetches.
- **Server-side paging**, 20 per page (`:16-18`), with a numbered pager plus prev/next rendered
  only when there is more than one page (`.html:49-53`). `totalRecord` comes from
  `response.paging.totalRecord` (`:50`).
- A **Refresh** button (`.html:13-15`) and a **Mark all read** button that is *disabled* while the
  shared unread count is zero (`.html:16-18`).
- Clicking anywhere on a row calls `NotificationService.open()` (`.html:29`), which marks it read
  on the server, decrements the shared count locally, and then navigates to the raw stored
  `linkUrl` (`_services/notification.service.ts:121-130`).
- Loading is the **global spinner** (`spinnerService.show()/hide()`, `:43, 47, 55`); a failure is an
  **error toast** via `AlertService` (`:52, 56`). There is no inline error state and no retry
  control -- a failed load leaves the previous list on screen with a toast over it.
- Empty state distinguishes the two tabs: `'No unread notifications.'` vs `"You're all caught up."`
  (`.html:24`).
- Severity glyph comes from `NotificationService.iconClass` (`_services/notification.service.ts:132-139`),
  mapped to Bootstrap glyphicons by `glyphClass` (`:83-91`). Note the fourth case: a notification of
  type `TASK_ASSIGNED` whose severity is not SUCCESS/ERROR/WARNING gets `'task'` → a **person**
  glyph, not the generic info glyph.
- Timestamp is `date:'MMM d, y, h:mm a'` (`.html:41`) -- absolute, **with the year**.

### 2.3 The header bell -- old app

`app.component.ts` + `app.component.html:85-124`.

- One shared `NotificationService` holds `unreadCountSubject` and `recentSubject` as
  `BehaviorSubject`s (`_services/notification.service.ts:15-16`), exposed as `unreadCount$` and
  `recent$` (`:37-43`). The navbar and the notification page both read the same two streams, so
  they cannot disagree.
- The count is **authoritative**: `refreshUnreadCount()` calls `notification.json/unreadCount`
  (`:58-66`). The badge caps its *display* at `99+` (`app.component.html:88`) but the number behind
  it is the server's.
- The recent list is the newest 12 (`MAX_RECENT`, `:20, 68-76`), refetched every time the dropdown
  opens -- wired through raw jQuery on `show.bs.dropdown` (`app.component.ts:82-86`).
- **Live push.** `WebSocketAPI` subscribes `/user/queue/notifications`
  (`_services/websocketapi.service.ts:33`); `handleLivePush` (`notification.service.ts:169-183`)
  parses `{notification, unreadCount}` and pushes both into the shared subjects, so a new
  notification appears in the bell and moves the badge with no polling at all. The server sends
  exactly that payload (`process/.../NotificationCenterServiceImpl.java:83-96`).
- `timeAgo` gives relative times in the dropdown -- `Just now`, `12m ago`, `3h ago`, `Yesterday`,
  `4d ago`, then `Mar 7` (`notification.service.ts:141-167`).
- Logging out disconnects the socket and zeroes both subjects (`app.component.ts:132-138`,
  `notification.service.ts:52-56`).

The user card in the same navbar shows initials (no picture -- `nav-avatar-initials`), full name,
a role label, the username, and a **live `America/Chicago` clock ticking every second**
(`app.component.ts:25-27, 78-80, 127-130`; `app.component.html:131-138`).

### 2.4 The notification centre -- new app

Split across two components that share only the link-rewriting module.

`features/notifications/notifications.ts` + `.html`:

- **One request, no paging**: `notification.json/list` with `page=1&limit=100` (`:59-60`). No
  pager anywhere. Rows 101 and older cannot be reached from this screen.
- `unreadOnly` is **not sent to the server**. It is a checkbox filtering the loaded array
  (`:36, 42-49`; `.html:34-38`).
- A **type filter** the old app did not have, whose options are derived from the loaded rows
  (`:39-40`; `.html:25-33`), plus a **Clear** button when either filter is active (`:52, 76-79`).
- A per-row **Mark as read** tick that does not navigate (`.html:73-79`), and an **Open** button
  rendered only when the row has a resolvable target (`.html:81-87`). The row itself is not
  clickable.
- **Mark all read (n)** in the page head, shown only when `unreadCount()` is non-zero -- and that
  count is computed from the loaded rows (`:51`; `.html:11-15`), plus a success toast (`:106`).
- Loading, error-with-retry and two empty states come from `shared/ui/data-table.ts` `TableShell`
  (`.html:19-23`; `data-table.ts:41-61`): `'Nothing matches those filters.'` vs
  `'No notifications yet.'`, bell icon, and a `shown of total` counter in the card heading.
- Severity is carried by **shape as well as colour** (`:117-124` `glyphOf`, `:126-133` `intentOf`,
  `:135-142` `toneOf`), and an unread row gets a coloured left rule plus a tinted surface derived
  from the theme (`src/styles.css:1011-1021`) so it works in both themes.
- A `New` pill on unread rows and a type pill that is suppressed when it would merely repeat the
  title (`:144-157`; `.html:56-59`).
- Timestamp is `date: 'd MMM, HH:mm'` (`.html:70`) -- **no year**.

`features/shell/notification-bell.ts` (one file, inline template):

- Polls `notification.json/list?page=1&limit=20` every **60 seconds** (`:110, 122-133`) and again
  whenever the dropdown is opened (`:117-120`).
- The badge is `items().filter(n => !n.read).length` (`:102`) -- i.e. the unread count **within the
  newest 20 rows**. It never calls `unreadCount`.
- Shows the newest 8 (`:103`), with `ago()` relative times (`:176-186`).
- Errors are deliberately swallowed on every call (`:131, 142, 152`) with the comment *"A failing
  bell must not put an error in front of whatever the user is doing."*
- **No live push.** The new app has exactly one STOMP consumer, `core/socket/job-events.service.ts`,
  and it subscribes `/topic/jobs.all` or `/topic/jobs.{tenantId}` (`:51-58, 97-104`). Nothing
  subscribes `/user/queue/notifications`.

`features/notifications/notification-links.ts` is shared by both, and is the only tested piece of
this feature. It rewrites stored Angular-8 routes -- `/jobList`→`/jobs`, `/taskList`→`/tasks`,
`/objectBrowser`→`/objects`, `/users`→`/admin/users`, `/tenants`→`/admin/tenants` (`:10-16`) --
matches on the path alone and discards the query string (`:28`), passes an unmapped absolute path
through, and returns `null` for anything blank or non-absolute (`:29`). Four tests cover it
(`notification-links.spec.ts`).

### 2.5 What the rewrite dropped, behaviour by behaviour

| Behaviour | Old | New | Verdict |
|---|---|---|---|
| Server-side paging, 20/page + numbered pager | `notification-center.component.ts:16-18, 42-66`; `.html:49-53` | one `limit=100` call, no pager (`notifications.ts:59-60`) | **lost** |
| `unreadOnly` sent to the server | `_services/notification.service.ts:80-82` | filtered client-side (`notifications.ts:44-45`) | **lost** |
| Authoritative unread badge | `unreadCount$` fed by `notification.json/unreadCount` (`notification.service.ts:58-66`) | derived from 20 loaded rows (`notification-bell.ts:102`) | **lost** |
| One shared count across bell/page/dashboard | one `BehaviorSubject` (`notification.service.ts:15-16`) | three independent readers | **lost** |
| Live WebSocket push of new notifications | `/user/queue/notifications` (`websocketapi.service.ts:33`, `notification.service.ts:169-183`) | 60 s poll (`notification-bell.ts:110`) | **lost** |
| `TASK_ASSIGNED` person glyph | `notification.service.ts:137` | severity only (`notifications.ts:117-124`, `notification-bell.ts:158-165`) | **lost** |
| Year in the list timestamp | `.html:41` `'MMM d, y, h:mm a'` | `.html:70` `'d MMM, HH:mm'` | **lost** |
| Whole row clickable | `.html:29` | two explicit buttons (`.html:73-87`) | changed, defensible |
| Mark-all-read *disabled* at zero | `.html:16` | button hidden at zero (`.html:11`) | changed, equivalent |
| Chicago clock in the user menu | `app.component.ts:127-130` | absent (`shell.html:88-94`) | **lost** |
| Username shown in the user menu | `app.component.html:136` | absent; only on `/profile` | **lost** |
| Refresh button | `.html:13-15` | `.html:8-10` | kept |
| Type filter, per-row mark-read, `New` pill, retry state, dark mode, legacy-route rewriting | -- | new | **gained** |

### 2.6 The profile screen -- new app only

`features/profile/profile.ts` (444 lines) + `profile.html` (341 lines). Three columns of content
in a two-column grid (`lg:grid-cols-[20rem_minmax(0,1fr)]`, `.html:22`).

**Identity card** (`.html:25-94`): the picture or `auth.initials()` in a 7rem circle, an uploading
overlay, the full name, the email with a copy button that flips to a tick for 1.5 s
(`ts:430-443`; `.html:50-57`), Replace/Add-picture and Remove controls, and a two-cell definition
list showing "Member for *n* days" (`ts:185-190`) and the role.

**Donut** (`.html:96-102`): how the caller's jobs last ran, from `myActivity.outcomes`, coloured
through the shared `statusColor` (`ts:179-181`).

**Password-debt banner** (`.html:106-118`): rendered when `me.mustChangePassword`, explaining that
the account was opened with a one-time password.

**Details card** (`.html:122-201`): display name, position, and the shared `app-phone-input`
(the same component the admin users screen uses). Save/Cancel appear only when something actually
changed -- `detailsChanged()` covers all three fields and blocks on a blank name (`ts:136-142`).
Below the fields, a read-only definition list: email, role, tenant (`tenantName`, else `#id`, else
`All tenants`), status pill, joined date, last sign-in (`Never` when null).

**Password card** (`.html:203-240`): current + new password, a client rule of `>= 8` characters
(`ts:262-264`), an inline `role="alert"` error, and a button disabled until both are satisfied.
Both fields are cleared on every outcome, success or failure (`ts:281-282, 293-294`).

**Activity card** (`.html:242-337`): four stat tiles -- Jobs (linking to `/jobs`, with "n active"),
Runs in the window, Failed in the window (the only tile that colours itself, and only when
non-zero), and Unread notifications (linking to `/notifications`) -- then the recent runs list with
job name, status pill, start time, a humanised duration (`ts:199-208`), a "so far" suffix while a
run is still going (`ts:211-213`), and the failure message on failed runs only.

That card has three distinct empty states, in a deliberate order (`.html:321-336`): *the request
failed*, *you have n jobs but none has run*, and *no jobs are assigned to you*. `activityFailed`
exists precisely so the first is not rendered as the third (`ts:82-89`).

**Avatar upload flow** (`ts:345-409`):
1. Client checks the MIME type against `['image/png','image/jpeg','image/webp','image/gif']` and
   the size against 2 MB (`ts:59-60, 351-358`).
2. The destination bucket is whatever the server nominated in `avatarUploadBucket` (`ts:162`).
3. The key is `${appUserId}/profile/avatar.${ext}`, where `ext` is taken from the uploaded
   filename (`ts:365-367`), and the file is renamed to `avatar.<ext>` before upload so a
   replacement overwrites (`ts:370`).
4. `storage.json/uploadObject` (multipart `bucket`/`prefix`/`file`) via
   `features/objects/storage.service.ts:101-107`.
5. On success, `appUser.json/updateOwnAvatar` records the pointer (`ts:391-409`), and
   `syncHeader()` patches the stored user so the header updates without a reload (`ts:412-418`).

Reading the picture back is *not* through `appUser.json/avatar`: `AuthService` fetches
`storage.json/previewObject` with the stored bucket/key and exposes a blob URL
(`core/auth/auth.service.ts:106-152`), which both the header (`shell.html:79`) and the profile card
(`profile.html:28`) bind to. The shared `shared/ui/avatar.ts` component -- which handles both
routes and is used on the admin users screen -- is not used by either.

### 2.7 Backend -- notifications

`api/NotificationRestApi.java`: class-level `@PreAuthorize("hasRole('TENANT_USER')")` (`:19`),
four methods, none of which overrides it. Every method wraps the service in try/catch and returns
the generic 500 envelope on an exception (`:37-40, 47-50, 57-60, 67-70`).

`model/service/impl/NotificationCenterServiceImpl.java`:

- `create(...)` (`:58-101`) is `@Transactional(REQUIRES_NEW)`, returns silently when there is no
  recipient (`:62-65`), writes the row, **increments a Redis counter** `notif:unread:{userId}`
  (`:79`), then looks the recipient up and pushes `{notification, unreadCount}` to
  `/user/queue/notifications` (`:81-97`). The whole body is wrapped in a catch that only logs
  (`:98-100`) -- a notification failure never fails the job that raised it.
- `list(...)` (`:103-115`) reads `TenantContext.getAppUserId()`, builds a `Pageable` sorted
  `dateCreated desc` through `PagingUtil.ApplyPaging` (one-based page, `PagingUtil.java:29-32`,
  default limit 10), and calls one of two repository methods depending on `unreadOnly`. It returns
  a bare array in `data` **and** a `PagingDto` in `paging`.
- `unreadCount()` (`:117-129`) reads the Redis key; on a miss it counts in the database and writes
  the key back. No TTL is set.
- `markRead(...)` (`:131-146`) runs `NotificationRepository.markRead`, whose `WHERE` includes
  `n.recipientUserId = ?3` (`NotificationRepository.java:27`) -- so another user's id simply
  updates nothing -- and decrements Redis only when a row actually changed, clamping at zero.
- `markAllRead()` (`:148-155`) updates every unread row for the caller and sets Redis to `"0"`.

There are **five** places that raise a notification, and they cover four of the ten declared types:

| Where | Type | Severity | linkUrl |
|---|---|---|---|
| `engine/BulkAction.java:247-249` | `JOB_COMPLETED` | SUCCESS | `/jobList` |
| `engine/BulkAction.java:251-253` | `JOB_FAILED` | ERROR | `/jobList` |
| `SourceJobServiceImpl.java:98-101` | `TASK_ASSIGNED` | INFO | `/jobList` |
| `SourceJobBulkServiceImpl.java:250-252` | `BATCH_DONE` | INFO | `/jobList` |
| `SourceTaskServiceImpl.java:630-632` | `BATCH_DONE` | INFO | `/taskList` |

`TASK_ASSIGNED` is suppressed when the assignee is unchanged or is the person doing the assigning
(`SourceJobServiceImpl.java:93-97`).

### 2.8 Backend -- own account

`api/AppUserRestApi.java` is class-level `@PreAuthorize("hasRole('TENANT_ADMIN')")` (`:24`). Five
methods override that down to `TENANT_USER`: `/me` (`:92`), `/avatar` (`:111`),
`/updateOwnProfile` (`:131`), `/changeOwnPassword` (`:147`), `/updateOwnAvatar` (`:163`).
**The override replaces the class annotation, it does not add to it** -- which is the point of the
comment at `:86-91`. Everything else on this controller stays admin-only.

`model/service/impl/AppUserServiceImpl.java`:

- `currentUser()` (`:444-454`) reads `TenantContext.getAppUserId()`, refuses when it is null or the
  row is soft-deleted, and returns the full `AppUserDto`.
- `updateOwnProfile(...)` (`:463-490`) requires a non-blank full name, normalises the phone number
  through `PhoneNumberValidator` **before** writing anything, and sets exactly three fields:
  `fullName`, `position` (blank → null via `trimToNull`, `:590-592`), `phoneNumber`. Role, status,
  tenant and username are untouched by construction.
- `updateOwnAvatar(...)` (`:502-524`) checks the key against `isOwnProfileKey` (`:539-546`) --
  `<appUserId>/profile/<plain filename>`, no sub-folders, no `.` or `..` -- and **ignores the
  bucket the client sent**, always storing the configured avatar bucket (`:516-518`). A blank key
  clears both columns.
- `changeOwnPassword(...)` (`:603-631`) requires the current password, requires the new one to be
  at least 8 characters via the shared `validateNewPassword` (`:369-374`), refuses a new password
  equal to the current one, verifies the current one with `passwordEncoder.matches`, and on success
  writes the new hash and sets `mustChangePassword = false`. The failure message is deliberately
  vague (`:622`).
- `readAvatar(appUserId)` (`:103-124`) resolves the key from that person's row, refuses via
  `TenantOwnership.isOwnedByCaller(user.getTenantId())` (`:78`), and streams through
  `readForWorkflow` -- the trusted resolver -- because the object browser would correctly refuse a
  platform bucket.
- `mapToDtoWithoutTenantName` (`:562-586`) is what `/me` returns. It includes `avatarUploadBucket`,
  set unconditionally to the configured avatar bucket (`:578-579`).

### 2.9 Backend -- `sourceJob.json/myActivity`

`api/SourceJobRestApi.java:94-107`, on a controller that is class-level `TENANT_USER` (`:29`).
Takes `limit` (default 8) and `windowDays` (default 7) and **clamps** rather than validates --
1..50 and 1..90 (`:100-101`).

`SourceJobServiceImpl.fetchMyActivity` (`:639-681`) is `@Transactional(readOnly = true)` and issues
four queries, all keyed on `TenantContext.getAppUserId()`:

| Query | Returns |
|---|---|
| `SourceJobRepository.countAssignedTo` (`:85-87`) | jobs assigned, and how many are `Active` |
| `JobQueueRepository.countRecentRunsForAssignee` (`:76-80`) | runs started in the window, and failures among them |
| `JobQueueRepository.findRecentRunsForAssignee` (`:69-73`) | the newest `limit` runs, `start_time desc nulls last` |
| `SourceJobRepository.outcomesForAssignee` (`:98-101`) | `job_running_status` grouped, nulls as `'Not run'` |

It needs no tenant filter: a job is either assigned to the caller's id or it is not. When there is
no signed-in user it returns an empty shape with `SUCCESS` rather than an error (`:644-647`), and
`jobStatusMessage` is copied only onto failed runs (`:670-673`).

### 2.10 Tests

| Covered | Where |
|---|---|
| Legacy route rewriting (4 tests) | `scheduler1/next/src/app/features/notifications/notification-links.spec.ts` |
| `updateOwnAvatar` -- claiming another key, traversal, own key | `process/src/test/java/process/model/service/impl/AppUserServiceImplRoleScopeTest.java:323-367` |
| `readAvatar` -- same tenant, other tenant, platform admin, absent picture | same file, `:369-423` |
| Password debt cleared by the interceptor | `scheduler1/next/src/app/core/auth/auth.interceptor.spec.ts:104-124` |

| **Not covered** | |
|---|---|
| `NotificationCenterServiceImpl` | no test file exists anywhere under `process/src/test` |
| `currentUser`, `updateOwnProfile`, `changeOwnPassword` | no test |
| `fetchMyActivity` and its four queries | no test |
| `Notifications`, `NotificationBell`, `Profile` components | no spec files |
| `passwordChangeGuard` | `auth.guard.spec.ts` exists; no case names it |

---

## 3. Expected behaviour

Where this differs from today it is marked **[differs]**.

**Notifications.**

1. The bell badge shows the number of unread notifications the *server* holds, not the number
   visible in whatever page the bell happens to have loaded. **[differs]**
2. There is one unread number in the application. The bell, the dashboard tile and the profile
   tile show the same figure at the same moment, and marking something read anywhere moves all
   three. **[differs]**
3. A new notification reaches an open console without a 60-second wait, because the server already
   pushes it. **[differs]**
4. The notification list is paged against the server, and every notification a user has is
   reachable -- not only the newest 100. **[differs]**
5. "Unread only" is a question asked of the server, so it means "all my unread notifications", not
   "the unread ones among the newest 100". **[differs]**
6. A notification opens the screen it refers to, in this application's route vocabulary,
   whether it was written by the old app or by the server this morning.
7. Severity is legible without colour, and an assignment is visibly a different *kind* of thing
   from a job outcome. **[differs]** -- the type pill partly restores this; the person glyph did
   not survive.
8. A timestamp is unambiguous. **[differs]** -- the year is currently dropped.
9. A failing notification list says so and offers to try again; a failing bell stays quiet.

**Own account.**

10. `/me` is the single source of truth for the profile screen, and it is re-read after every write
    rather than the client patching what it thinks changed.
11. A person may change their display name, job title, phone number, picture and password, and
    nothing else. Role, tenant, status and username are read-only on this screen and unwritable by
    these endpoints.
12. A blank phone number or job title is a legitimate edit that clears the field; a blank name is
    not.
13. A phone number is stored in E.164 and validated against the same metadata on both sides.
14. Changing a password requires the current one, and clears the password debt so the guard
    releases the session immediately.
15. A picture is the person's own: it can only be written under `<appUserId>/profile/`, only read
    back through a path that authorises it, and only ever recorded in the server's own bucket.
16. Removing a picture removes the object, not just the pointer. **[differs]**
17. The size and type rules that the browser applies are also applied by the server. **[differs]**
18. The activity card never states something about the account when what actually happened was a
    failed request.

---

## 4. Frontend requirements

### 4.1 Routes

| Route | Component | Guards | Notes |
|---|---|---|---|
| `/notifications` | `features/notifications/notifications.ts` | `authGuard`, `passwordChangeGuard` (inherited from the shell) | no `minRole` |
| `/profile` | `features/profile/profile.ts` | same; **exempt** from the password gate | the only page reachable while `mustChangePassword` |

Both should also be reachable from the navigation, not only from the header menus.
`shell.ts` `nav()` currently lists neither.

### 4.2 Components

| Component | Responsibility |
|---|---|
| `Notifications` | the list, its filters, mark-read/mark-all-read, click-through |
| `NotificationBell` (`features/shell/notification-bell.ts`) | badge, newest-8 dropdown, mark-all-read, "View all" |
| `notification-links.ts` | the one route-rewriting table, imported by both above |
| `Profile` | identity card, details form, password form, activity card |
| `PhoneInput` (`shared/ui/phone-input.ts`) | country + national number → one E.164 string; shared with the admin users screen |
| `TableShell` (`shared/ui/data-table.ts`) | loading / error+retry / empty chrome for the notification list |
| `Donut`, `statusColor` (`shared/charts/`) | the outcome ring and its colours |
| `StatusPill` (`shared/ui/status-pill.ts`) | run status and account status |
| `Avatar` (`shared/ui/avatar.ts`) | **should** be what the header and the profile card render; today they hand-roll it |
| `StorageService` (`features/objects/storage.service.ts`) | the multipart upload |
| A shared notification store | **does not exist**; see §13 |

### 4.3 Forms

| Form | Fields | Submit rule |
|---|---|---|
| Details | display name (text, required), position (text, optional), phone (`app-phone-input`, optional) | Save/Cancel appear only when `detailsChanged()`; Save blocked on a blank name and on an invalid phone, with `phoneSubmitted` flipping the phone error on first attempt (`profile.ts:308-317`) |
| Password | current password, new password | disabled until current is non-empty and new is ≥ 8 characters; both cleared on every outcome |
| Picture | file input, `accept="image/png,image/jpeg,image/webp,image/gif"` | disabled while uploading or when no target bucket |

### 4.4 Tables and lists

The notification list is a `<ul>` inside `TableShell`, not a table -- correctly, since a
notification is a paragraph rather than a row of columns. It needs, and today lacks, a pager slot;
`TableShell` already reserves one (`data-table.ts:69`, `<ng-content select="[pager]">`) and
`shared/ui/pager.ts` `createPager` exists and is used by other screens.

The recent-runs list on the profile is a plain `<ul>` with a link to `/jobs/:jobId/history`
per row.

### 4.5 Dialogs

There are none in this feature, in either app, and none is needed -- with one exception worth
stating: **removing a picture is destructive and unconfirmed** (`profile.html:67-72` fires
`removePicture()` straight from the button). A confirm step, or an undo window, belongs here once
removal also deletes the object.

### 4.6 States

| State | Notifications | Profile |
|---|---|---|
| Loading | `TableShell` spinner + "Loading…" | full-card "Loading your profile…" (`profile.html:12`); the activity card has its own "Loading…" (`:286`) |
| Error | `TableShell` crit icon, message, **Try again** wired to `load()` | full-card alert + **Try again** (`:14-20`); activity failure degrades to one sentence inside its card |
| Empty | filter-aware: `'Nothing matches those filters.'` / `'No notifications yet.'` | three-way in the activity card (failed / no runs yet / no jobs assigned) |
| Bell empty | "You are all caught up." | -- |
| Busy | Refresh icon spins while loading | Save shows "Saving…", password shows "Changing…", avatar shows a dark overlay with a spinner |

### 4.7 Dark and light mode

The new app is theme-aware; the old one is not. The two theme-sensitive pieces of this feature are
both handled deliberately:

- `.notification-row.is-unread` derives its tint from the row's own severity tone via
  `color-mix(in oklab, var(--tone) 7%, transparent)` (`styles.css:1011-1021`). The comment there
  records why: a fixed `bg-brand-50` rendered white-on-dark.
- `.bell-badge` is `bg-crit-500` with white text in both themes (`styles.css:1023-1027`).

Everything else on both screens uses the `--surface-*`, `--text-*`, `--border-*` and `--series-*`
tokens, so nothing needs a per-theme override.

### 4.8 Responsive behaviour

- Profile: single column below `lg`, `20rem` + fluid above (`profile.html:22`). The details grid is
  a container query (`.form-grid` inside `.form-section`, `profile.html:122, 128`), so it folds on
  the *card's* width rather than the viewport's. The read-only definition list is
  `sm:grid-cols-2`. Stat tiles are `grid-cols-2 lg:grid-cols-4` (`:253`).
- Notifications: rows are flex with a `flex-wrap` title line; the meta column is `shrink-0`. The
  toolbar wraps.
- Bell: a `w-80` panel anchored `right-0`, which fits a 375 px viewport. The bell itself lives in
  the always-visible right-hand group of the header, so it survives the `xl:hidden` nav collapse.
- The email line on the profile card is `break-all` on the text only, with the copy button held
  `shrink-0` so it is never split off (`profile.html:46-57`).

---

## 5. Backend requirements

`@PreAuthorize` values below are what the code actually carries. Remember two things when reading
them: the role hierarchy is `PLATFORM_ADMIN > TENANT_ADMIN > TENANT_USER`
(`config/MethodSecurityConfig.java:27-31`), so `hasRole('TENANT_USER')` admits all three; and a
method-level annotation **replaces** the class-level one.

| Method | Path | Role | What it does |
|---|---|---|---|
| GET | `/notification.json/list?unreadOnly&page&limit` | `TENANT_USER` (class) | The caller's own notifications, newest first, paged. `page` is one-based; `limit` defaults to 10 and is uncapped. Returns an array in `data` and a `PagingDto` in `paging`. |
| GET | `/notification.json/unreadCount` | `TENANT_USER` (class) | Unread count for the caller, from Redis `notif:unread:{appUserId}` with a database fallback that writes the key back. |
| POST | `/notification.json/markRead/{notificationId}` | `TENANT_USER` (class) | Marks one row read **only if it belongs to the caller**; decrements Redis when a row changed. Always answers SUCCESS. |
| POST | `/notification.json/markAllRead` | `TENANT_USER` (class) | Marks every unread row for the caller read; sets Redis to 0. |
| GET | `/appUser.json/me` | `TENANT_USER` (**method override**, class is `TENANT_ADMIN`) | The caller's own `AppUserDto`, including `avatarUploadBucket` and `mustChangePassword`. |
| PUT | `/appUser.json/updateOwnProfile` | `TENANT_USER` (override) | Writes `fullName`, `position`, `phoneNumber` on the caller's own row. Returns the updated DTO. |
| PUT | `/appUser.json/changeOwnPassword` | `TENANT_USER` (override) | Body is a plain `Map` of `currentPassword`/`newPassword`. Verifies the current one, writes the new hash, clears `mustChangePassword`. |
| PUT | `/appUser.json/updateOwnAvatar` | `TENANT_USER` (override) | Records `avatarKey` after checking it is under `<appUserId>/profile/`; the bucket is the server's, not the caller's. A blank key clears both columns. |
| GET | `/appUser.json/avatar?appUserId` | `TENANT_USER` (override) | Streams somebody's picture, resolving the key from their row. 404 when there is none. Not used by the profile screen today. |
| GET | `/sourceJob.json/myActivity?limit&windowDays` | `TENANT_USER` (class) | Counts, recent runs and outcome breakdown for jobs assigned to the caller. Both parameters clamped. |
| POST | `/storage.json/uploadObject` (multipart) | `TENANT_USER` (class) | Used here to put the picture at `<appUserId>/profile/avatar.<ext>`. |
| GET | `/storage.json/previewObject?bucket&key` | `TENANT_USER` (class) | Used here to read the caller's own picture back. |

### Services

| Service | Role in this feature |
|---|---|
| `NotificationCenterServiceImpl` | the whole notification centre, plus `create(...)` used by four other features |
| `AppUserServiceImpl` | `currentUser`, `updateOwnProfile`, `changeOwnPassword`, `updateOwnAvatar`, `readAvatar` |
| `SourceJobServiceImpl.fetchMyActivity` | the profile activity card |
| `StorageBrowserServiceImpl` | `resolveServiceForCaller` + `isOwnProfileObject` -- the one exception that lets a tenant user touch a platform bucket |
| `PhoneNumberValidator` | server-side E.164 normalisation, shared with `addUser`/`updateUser` |
| `RedisTemplate<String,String>` | the unread counter (`RedisConfig.java:25-35`) |
| `SimpMessagingTemplate` | the live push the new frontend does not consume |
| `StorageConnectionBootstrap` | creates the platform `etl-avatar` connection at startup, when `MINIO_ENDPOINT` is set |

---

## 6. Database requirements

### `notification`

| Column | Type | Notes |
|---|---|---|
| `notification_id` | identity PK | `GenerationType.IDENTITY` -- the only identity column in the schema (`Notification.java:30-33`) |
| `tenant_id` | bigint, nullable | Written by `create` (`NotificationCenterServiceImpl.java:68`); **never read**. No FK. |
| `recipient_user_id` | bigint, **not null** | The only scoping key. No FK to `app_user`. |
| `type` | varchar, enum string, not null | 10 declared values; 4 in use |
| `severity` | varchar, enum string, not null | `INFO`/`SUCCESS`/`WARNING`/`ERROR` |
| `title` | varchar, not null | |
| `message` | varchar(2000) | |
| `link_url` | varchar | Angular-8 paths, still being written |
| `is_read` | boolean, not null | |
| `read_at` | timestamp | Set by both mark-read queries |
| `date_created` | timestamp, not null | Sort key |

Indexes: `idx_notification_recipient` and `idx_notification_recipient_read` declared on the entity
(`Notification.java:19-22`), plus `idx_notification_tenant_id` and a second
`idx_notification_recipient (recipient_user_id, date_created DESC)` created by
`V18__foreign_key_indexes.sql:24-25`.

### `app_user` -- the columns this feature owns

| Column | Migration |
|---|---|
| `avatar_bucket` varchar(255), `avatar_key` varchar(512) | `V18__user_avatar.sql`; the key layout comment corrected by `V23__avatar_key_layout.sql` |
| `position` varchar(120) | `V20__user_position.sql` |
| `phone_number` varchar(20) | `V24__user_phone.sql` |
| `must_change_password` boolean not null | `AppUser.java:104-105`; no dedicated changeset found |
| `last_login_at` timestamp | `AppUser.java:84-85`; read-only here |

### `source_job` / `job_queue`

Read-only for this feature. `myActivity` depends on `source_job.assigned_user_id`,
`source_job.job_status`, `source_job.job_running_status`, and `job_queue.start_time`, `.end_time`,
`.job_status`, `.job_status_message`.

### Migrations needed

1. **A changeset that creates `notification`.** Nothing creates it. `V17` comments it and `V18`
   indexes it, so on a database that has never been through a `ddl-auto=update` boot both of those
   fail. Dev is `update` (`application-dev.properties:87`); stage and prod are `validate`
   (`application-stage.properties:90`, `application-prod.properties:92`).
2. **FKs on `notification.recipient_user_id` → `app_user` and `notification.tenant_id` → `tenant`,**
   or a decision to drop `tenant_id` and `idx_notification_tenant_id` entirely.
3. **A retention decision.** There is no delete path of any kind. The table only grows.
4. *(Only if server paging with a total is restored.)* No new index is needed --
   `(recipient_user_id, date_created DESC)` already serves it.

---

## 7. Validation

| Rule | Client | Server | Where |
|---|---|---|---|
| Display name required, non-blank | yes -- `detailsChanged()` returns false on a blank name (`profile.ts:138`) | yes -- `"Full name is required."` (`AppUserServiceImpl.java:471-473`) | **both** |
| Display name trimmed | trimmed before sending (`profile.ts:322`) | trimmed before storing (`:483`) | both |
| Position optional, blank clears | sends `null` for blank (`profile.ts:323`) | `trimToNull` (`:485`, `:590-592`) | both |
| Phone valid or empty | yes -- libphonenumber in `PhoneInput`, error surfaced only after first Save (`phone-input.ts:73`, `profile.ts:313-317`) | yes -- `PhoneNumberValidator.normalise`, rejects before any write (`:479-482`) | **both**, same metadata |
| Phone stored E.164 | the component emits E.164 | `UTIL.format(..., E164)` (`PhoneNumberValidator.java:49`) | both |
| Current password required | button disabled while empty (`profile.ts:263`) | `"Enter your current password."` (`:611-613`) | both |
| New password ≥ 8 characters | `newPassword().length >= 8` (`profile.ts:263`) | `validateNewPassword` (`:369-374`), shared with `resetPassword` | both |
| New password must differ from current | **no** | yes (`:618-620`) | **server only** |
| Current password must match | n/a | `passwordEncoder.matches` (`:626-629`) | server only |
| Avatar MIME type in {png,jpeg,webp,gif} | yes (`profile.ts:59, 351-354`) | **no** | **client only -- finding** |
| Avatar ≤ 2 MB | yes (`profile.ts:60, 355-358`) | **no** -- multipart limit is 500 MB (`application.properties:40-41`) | **client only -- finding** |
| Avatar key is the caller's own | key built client-side from `appUserId` | yes -- `isOwnProfileKey` (`:539-546`) **and** `isOwnProfileObject` in the storage guard (`StorageBrowserServiceImpl.java:496-511`) | server, twice |
| Avatar key has no traversal | no | yes -- `isSafeKey` refuses `..`, `.`, `\`, leading `/` (`StorageBrowserServiceImpl.java:405-418`) | server only |
| Avatar bucket | the client sends one | **ignored**; the server always uses its own (`AppUserServiceImpl.java:516-518`) | server only |
| Avatar filename produces a previewable extension | **no** -- extension taken from the uploaded name (`profile.ts:365`) | refused at read time (`ContentTypeUtil.java:74-76`) | neither, effectively -- see K11 |
| `myActivity` limit / windowDays | not sent | clamped 1..50 / 1..90 (`SourceJobRestApi.java:100-101`) | server only |
| `notification.json/list` limit | fixed at 100 / 20 in code | **uncapped** (`PagingUtil.java:45-47` only floors it) | neither |
| `notificationId` present | n/a | `"notificationId missing."` (`:134-136`) | server only |

**Client-only findings:** the avatar type and size rules. Both are trivially bypassed by posting to
`storage.json/uploadObject` directly, and the destination -- `<appUserId>/profile/` in a platform
bucket -- is one the storage guard explicitly permits.

---

## 8. Security

### Layer 1 -- the frontend guard

`authGuard` on the shell requires a session (`auth.guard.ts:6-17`). `passwordChangeGuard` holds a
session that owes a password change on `/profile` (`:59-67`). Neither `/notifications` nor
`/profile` declares `minRole`, so `roleGuard` never runs for them -- correctly, since every signed-in
role may use both. `mustChangePassword` is read from the stored blob rather than the token
(`auth.service.ts:69`), which is stated and defensible: editing it in devtools only skips a prompt
to replace a password its owner already knows, and the server is what stops honouring the old one.

**The frontend hides nothing here that the server would otherwise allow.** There is no control on
either screen that is gated by role.

### Layer 2 -- controller `@PreAuthorize`

| Controller | Class | Overrides |
|---|---|---|
| `NotificationRestApi` | `hasRole('TENANT_USER')` (`:19`) | none |
| `AppUserRestApi` | `hasRole('TENANT_ADMIN')` (`:24`) | `/me`, `/avatar`, `/updateOwnProfile`, `/changeOwnPassword`, `/updateOwnAvatar` → `hasRole('TENANT_USER')` |
| `SourceJobRestApi` | `hasRole('TENANT_USER')` (`:29`) | none on `/myActivity` |
| `StorageBrowserRestApi` | `hasRole('TENANT_USER')` (`:36`) | none on `uploadObject`/`previewObject` |

The five overrides on `AppUserRestApi` are the interesting ones, and they are correct in the way
that matters: because the annotation *replaces* rather than adds, `/me` is `TENANT_USER` and
`/listUsers` beside it stays `TENANT_ADMIN`. Widening the role here does not widen what the method
touches, because each of the five derives its subject from the token.

### Layer 3 -- the service rule

| Endpoint | Rule |
|---|---|
| `list`, `unreadCount`, `markAllRead` | keyed on `TenantContext.getAppUserId()` -- no request parameter names a user |
| `markRead` | the id is a path variable, but the UPDATE carries `and n.recipientUserId = ?3` (`NotificationRepository.java:27`), so another user's id updates zero rows |
| `/me`, `updateOwnProfile`, `changeOwnPassword`, `updateOwnAvatar` | `TenantContext.getAppUserId()`; each refuses when it is null or the row is soft-deleted |
| `updateOwnAvatar` | additionally `isOwnProfileKey` -- prefix `<appUserId>/profile/`, plain filename only |
| `readAvatar` | `TenantOwnership.isOwnedByCaller(row.tenantId)` -- a platform admin sees anyone; a tenant caller sees only its own tenant; **a caller with no tenant that is not a platform admin sees nobody**, which is the case a direct null-equals-null comparison used to let through (`AppUserServiceImpl.java:73-79`) |
| `uploadObject` / `previewObject` on `etl-avatar` | `resolveServiceForCaller` refuses a platform bucket unless the caller is a platform admin **or** `isOwnProfileObject(bucket, key)` -- avatar bucket only, key not ending in `/`, `isSafeKey`, and `key.startsWith(callerId + "/profile/")`. The trailing separator is what stops user `1248` matching `12480/profile/` (`StorageBrowserServiceImpl.java:484-511`) |
| `fetchMyActivity` | every query filters `assigned_user_id = callerId` |

### Layer 4 -- the Hibernate filter

**`Notification` declares no `@Filter` at all** (`.ai/discovery/database.md:335`). Its `tenant_id`
column exists, is written and is indexed, and the filter mechanism never acts on it. That is not a
hole, because the recipient id is a strictly narrower key than the tenant -- but it means the whole
isolation of this table rests on `TenantContext.getAppUserId()` being non-null and correct.
`AppUser` likewise has no filter and is scoped by hand. `JobQueue` has no filter and inherits its
scope from `source_job`, which `myActivity` narrows by `assigned_user_id` anyway.

Note the general trap this feature does not fall into but sits next to: a `@Filter` does not apply
to `findById`, and every own-account read here *is* a `findById`. It is safe only because the id
comes from the token.

### Per role

| | `TENANT_USER` | `TENANT_ADMIN` | `PLATFORM_ADMIN` |
|---|---|---|---|
| Read/mark own notifications | yes | yes | yes |
| Read anyone else's notifications | no -- no endpoint takes a recipient | no | no |
| Read/edit own profile, password, picture | yes | yes | yes |
| Change own role/tenant/status | no -- those fields are not written by `updateOwnProfile` | no | no |
| See another user's picture | only within its own tenant, via `appUser.json/avatar` | within its own tenant | anyone |
| Browse `etl-avatar` in the object browser | no -- filtered out of `listBuckets` and refused by `resolveServiceForCaller` | no | yes |
| Write into `etl-avatar` | only `<own appUserId>/profile/<file>` | same | anywhere |
| Own activity card | own jobs only | own jobs only | own jobs only |

A tenant admin has no privileged view of anybody's notifications, and a platform admin has none
either. That is right, and worth stating because it is the reason there is no admin surface here.

---

## 9. Error handling

| Failure | What the user sees | Where |
|---|---|---|
| `notification.json/list` returns ERROR | inline `TableShell` error with the server message and **Try again** | `notifications.ts:63`; `.html:19-23` |
| `notification.json/list` throws | same panel, `'Could not load notifications.'` fallback | `notifications.ts:69-72` |
| `markRead` fails | toast `'Could not mark that as read.'`; the row stays unread | `notifications.ts:98` |
| `markAllRead` fails | toast `'Could not mark them as read.'` | `notifications.ts:108` |
| Any bell request fails | **nothing** -- deliberately swallowed | `notification-bell.ts:131, 142, 152` |
| `appUser.json/me` fails | the whole page is replaced by an alert card with **Try again** | `profile.html:13-20` |
| `myActivity` fails | the rest of the page is unaffected; the card says *"Your activity could not be read just now."* | `profile.ts:89, 225`; `.html:321-327` |
| `notification.json/unreadCount` fails on the profile | the Unread tile shows 0, silently | `profile.ts:229` |
| `updateOwnProfile` returns ERROR | toast with the server's message (`"Full name is required."`, or the phone message) | `profile.ts:335` |
| Invalid phone caught client-side | toast `'Check the phone number before saving.'` and the field error appears | `profile.ts:313-317` |
| `changeOwnPassword` returns ERROR | **inline** `role="alert"` under the fields, not a toast; both boxes cleared | `profile.ts:287`; `.html:226-231` |
| Wrong current password | `"That is not your current password."` -- deliberately vague about which half was wrong | `AppUserServiceImpl.java:622` |
| Avatar wrong type | toast `'Pick a PNG, JPEG, WebP or GIF.'` | `profile.ts:352` |
| Avatar over 2 MB | toast `'That picture is over 2 MB — pick a smaller one.'` | `profile.ts:356` |
| No target bucket | the picture button is disabled and a warning sits under it -- **which cannot currently render**, see K12 | `profile.html:75-79` |
| Upload refused by the storage guard | toast carrying the server text, e.g. `"Unknown bucket: etl-avatar."` | `profile.ts:375, 382` |
| `updateOwnAvatar` refuses the key | toast `"That is not your own picture."` | `AppUserServiceImpl.java:512` |
| Picture object unreadable | falls back to initials, no message | `auth.service.ts:151` |
| Any endpoint throws server-side | the generic 500 envelope; the controller logs it. `changeOwnPassword` logs **without the request body**, because it holds two passwords | `AppUserRestApi.java:156-157` |
| Redis unavailable | `unreadCount` throws → 500 → bell silent, dashboard and profile tiles show 0 | `NotificationCenterServiceImpl.java:120` |
| Notification creation fails | nothing user-visible; logged and swallowed so the job is unaffected | `NotificationCenterServiceImpl.java:98-100` |

---

## 10. Dependencies

**Features.** `authentication-and-access` supplies the token, `TenantContext`, the role hierarchy,
the interceptor that clears the password debt, and `mustChangePassword` itself.
`storage-connections` supplies the `etl-avatar` connection without which no picture can be written
or read. Discovery records this feature as *downstream of everything and depended on by nothing*
(`.ai/discovery/features.md:471-473`) -- `source-jobs`, `source-tasks`, `bulk-transfer` and the
scheduler engine all raise notifications; nothing reads them back.

**One edge runs the other way, and it is not optional.**
`features/notifications/notification-links.ts` is imported by both `notifications.ts` and
`shell/notification-bell.ts`, and every feature whose route changed in the rewrite has to be
represented in its map -- because rows already in the database carry the old paths, and the server
is *still writing them* (see K15). An unmapped path sends a click to the wildcard redirect.

**Infrastructure.**

| Dependency | Used for | Failure mode |
|---|---|---|
| Redis | `notif:unread:{appUserId}` | `unreadCount` 500s; see also K9 |
| A MinIO/S3/Azure bucket aliased `etl-avatar` | every picture | uploads and reads fail with `"Unknown bucket"` |
| `MINIO_ENDPOINT` at first boot | lets `StorageConnectionBootstrap` create that connection (`:149-155`) | a logged warning and no connection |
| STOMP/SockJS at `/api/v1/ws` | the live push the old app consumed | the new app does not use it, so nothing breaks -- and nothing arrives |
| Postgres | `count(*) filter (where …)` in three of the four `myActivity` queries | these are Postgres-specific and will not run on another engine |

---

## 11. Acceptance criteria

Each is checkable by someone who did not write it. Refusals are paired with a positive control on
the same fixture.

**Fixtures.** Tenant A holds `userA1` (TENANT_USER, id 7), `userA2` (TENANT_USER, id 9) and
`adminA` (TENANT_ADMIN). Tenant B holds `userB1` (TENANT_USER). `platformAdmin` carries no tenant.
`userA1` has 130 notifications, of which 25 are unread and 20 of those 25 are older than the newest
100 by date. `userA1` has 3 jobs assigned, 2 Active, with runs in the last 7 days including at
least one FAILED.

### Notifications -- list and filters

1. `userA1` opens `/notifications` and sees a list of their own notifications, newest first, and no
   notification whose recipient is `userA2` or `userB1`.
2. `userA1` reaches every one of their 130 notifications from `/notifications` -- by paging, by
   scrolling, or by any control the page offers. *(Fails today: only the newest 100 load.)*
3. `userA1` ticks **Unread only** and sees 25 rows, not 5. *(Fails today: the filter runs over the
   loaded 100.)*
4. **Positive control for 3:** with **Unread only** off, `userA1` sees read and unread rows
   together, and the unread ones are visibly distinguished (left rule, tinted background, `New`
   pill).
5. `userA1` selects a type in the kind filter and sees only rows of that type; the option list
   offers every type present in their notifications, not only those on the current page.
6. `userA1` clears the filters and the full list returns without a page reload.

### Notifications -- read state and counts

7. `userA1` clicks the tick on an unread row; the row loses its unread styling, and after a full
   page reload it is still read.
8. **Positive control for 7:** a row `userA1` did not tick remains unread after the same reload.
9. `userA2` issues `POST /notification.json/markRead/{id}` for a notification belonging to
   `userA1`. The call answers SUCCESS, and that notification is **still unread** when `userA1`
   reloads `/notifications`.
10. **Positive control for 9:** `userA2` marks one of their *own* notifications read by the same
    call, and it is read on their next reload.
11. `userA1` presses **Mark all read**; every row on the page loses its unread styling and the
    header badge goes to zero **without waiting for the 60-second poll**.
12. With 25 unread notifications, the header badge reads `25`. *(Fails today: it reads at most the
    number unread among the newest 20.)*
13. The badge, the dashboard **Unread** tile and the profile **Unread** tile show the same number
    at the same moment.
14. A notification raised for `userA1` while their console is open (assign them a job as `adminA`)
    appears in the bell and increments the badge without a manual refresh and within a few seconds.
15. A notification row created by the old app with `linkUrl = "/jobList?jobId=42"` opens `/jobs` in
    the new app.
16. **Positive control for 15:** a row with `linkUrl = "/queue"` opens `/queue`, and a row with a
    blank `linkUrl` shows no **Open** control at all.
17. A row whose `linkUrl` is `https://example.com/jobs` shows no **Open** control and navigates
    nowhere.
18. A notification timestamp identifies its year without the reader having to guess.
    *(Fails today.)*
19. With the notification list endpoint returning 500, `/notifications` shows the error panel and a
    **Try again** button, and pressing it re-issues the request. The header bell shows no error and
    the rest of the console is usable.

### Own account -- reading

20. `userA1` opens `/profile` and sees their own name, email, role, tenant, status, joined date and
    last sign-in, and no field belonging to any other user.
21. `GET /appUser.json/me` accepts no parameter that could name another user; adding
    `?appUserId=9` to it returns `userA1`'s own record.
22. `userA1` (TENANT_USER) receives a successful response from `/appUser.json/me`.
    **Positive/negative pair:** the same `userA1` receives 403 from `/appUser.json/listUsers` on the
    same controller.

### Own account -- editing

23. `userA1` changes their display name and saves; the name updates in the header without a reload,
    and survives a reload.
24. `userA1` clears the phone field and saves; the number is removed, and `/me` returns
    `phoneNumber: null`.
25. `userA1` enters `03001234567` (no country code) and presses Save; the save is refused with a
    message naming the expected format, and the previously stored number is unchanged.
26. **Positive control for 25:** `userA1` enters `+923001234567`, saves successfully, and `/me`
    returns exactly `+923001234567`.
27. `userA1` saves a blank display name: the Save control is unavailable, and posting the blank name
    directly to `/appUser.json/updateOwnProfile` is refused with `"Full name is required."`
28. `userA1` posts `{"fullName":"x","userRole":"PLATFORM_ADMIN","tenantId":null,"status":"Active"}`
    to `/appUser.json/updateOwnProfile`. The call succeeds, the name changes, and the role, tenant
    and status are **unchanged** in `/me` and in the users table.

### Own account -- password

29. `userA1` submits the wrong current password; the change is refused inline, both boxes are
    cleared, and the old password still signs them in.
30. **Positive control for 29:** with the correct current password and a new one of at least 8
    characters, the change succeeds, the old password no longer signs them in, and the new one does.
31. A new password of 7 characters is refused by the button *and* by the server when posted
    directly.
32. A new password identical to the current one is refused by the server.
33. A user created by `adminA` with `mustChangePassword` set signs in, is redirected to `/profile`
    from any other URL they try, sees the banner, changes their password, and is then able to open
    `/jobs` without signing out and back in.
34. **Positive control for 33:** `userA2`, who does not owe a change, opens `/jobs` directly and is
    not redirected.

### Own account -- picture

35. `userA1` uploads a 200 KB PNG; the picture appears in the profile card and in the header
    immediately, and is still there after a reload and after signing out and in again.
36. `userA1` uploads a file named `IMG_1234` with no extension; the picture renders.
    *(Fails today -- see K11.)*
37. `userA1` posts to `/appUser.json/updateOwnAvatar` with `avatarKey: "9/profile/avatar.png"`; the
    call is refused with `"That is not your own picture."` and `userA1`'s stored key is unchanged.
38. **Positive control for 37:** the same call with `avatarKey: "7/profile/avatar.png"` succeeds.
39. `userA1` posts `avatarKey: "7/profile/../../9/profile/avatar.png"`; it is refused.
40. A user whose id is `1248` cannot read, write, rename or delete anything under `12480/profile/`
    in the avatar bucket.
41. **Positive control for 40:** user `1248` can write and read `1248/profile/avatar.png`.
42. `userA1` requests `GET /storage.json/listObjects?bucket=etl-avatar`; it is refused with
    `"Unknown bucket: etl-avatar."`, and `etl-avatar` does not appear in `storage.json/buckets`
    for them.
43. **Positive control for 42:** `platformAdmin` can list `etl-avatar`.
44. `userB1` requests `GET /appUser.json/avatar?appUserId=7`; the response is 404 and no bytes are
    returned. **Positive control:** `adminA` requesting the same id receives the picture.
45. `userA1` uploads a 40 MB PNG by posting to `storage.json/uploadObject` directly; the server
    refuses it. *(Fails today -- client-only rule.)*
46. `userA1` removes their picture; the header falls back to initials, and the object no longer
    exists in the avatar bucket. *(The second half fails today.)*

### Own account -- activity

47. `userA1` opens `/profile` and the Jobs tile reads 3 with "2 active"; the Runs and Failed tiles
    are consistent with the runs listed below them and with the stated window.
48. A running job of `userA1`'s shows a duration ending in "so far" and no end time.
49. A failed run shows its failure message; a completed run shows none.
50. With `sourceJob.json/myActivity` returning 500, the activity card says the activity could not be
    read, **not** "No jobs are assigned to you yet", and the rest of the profile still renders.
51. **Positive control for 50:** a user with genuinely no jobs sees "No jobs are assigned to you
    yet."
52. `GET /sourceJob.json/myActivity?limit=100000&windowDays=-4` returns at most 50 runs and a
    window of at least 1 day, without an error.
53. `userB1`'s activity card counts none of `userA1`'s jobs, even when a job name matches.

### Presentation

54. Every screen in this feature is legible in both light and dark mode: an unread notification row
    is distinguishable from a read one in both, and no text or badge loses contrast.
55. At a 375 px viewport width neither `/profile` nor `/notifications` scrolls horizontally, and the
    bell dropdown stays fully on screen.
56. Severity is distinguishable in a greyscale screenshot -- each severity has its own glyph shape,
    not only its own colour.
57. An assignment notification is distinguishable from a job-outcome notification at a glance.

---

## 12. Known issues

Each of these exists today. None is fixed here.

**K1 -- The bell badge is not the unread count.**
`notification-bell.ts:102` computes it as the unread rows within `list?page=1&limit=20` (`:124`).
The server has an authoritative count at `notification.json/unreadCount`
(`NotificationRestApi.java:43-51`), which the bell never calls. Twenty-one unread notifications
produce a badge of at most 20; twenty-one unread ones all older than the newest 20 produce a badge
of 0.

**K2 -- Three unread counters, three sources.**
The bell derives its own (`notification-bell.ts:102`), the dashboard calls `unreadCount` once on
init (`features/dashboard/dashboard.ts:154`), and the profile calls it once on init
(`features/profile/profile.ts:227-230`). They can and do disagree. The old app had one
`BehaviorSubject` read by every consumer (`_services/notification.service.ts:15-16, 37-43`).

**K3 -- Marking read on the page does not move the bell.**
`notifications.ts:92-110` updates only its own signal. The bell finds out on its next 60-second
poll (`notification-bell.ts:110`). The old app called `markAllReadLocally()` on the shared service
(`notification-center.component.ts:72`), which both consumers were subscribed to.

**K4 -- Server paging was dropped.**
Old: 20 per page with a numbered pager and `totalRecord` from the envelope
(`notification-center.component.ts:16-18, 42-66`; `.html:49-53`). New: one `page=1&limit=100`
request and no pager (`notifications.ts:59-60`). The 101st-newest notification is unreachable from
the UI.

**K5 -- `unreadOnly` is no longer asked of the server.**
The endpoint supports it (`NotificationRestApi.java:32`; `NotificationCenterServiceImpl.java:107-109`)
and the old client sent it (`_services/notification.service.ts:80-82`). The new page filters the
loaded array (`notifications.ts:44-45`). Combined with K4, "Unread only" can show an empty list to a
user who has unread notifications and a lit badge.

**K6 -- The kind filter enumerates only what happens to be loaded.**
`notifications.ts:39-40` derives the options from `items()`. The available filters therefore change
with the contents of the first 100 rows.

**K7 -- The `TASK_ASSIGNED` glyph was lost.**
`_services/notification.service.ts:137` returned `'task'` -- a person glyph -- for a
`TASK_ASSIGNED` notification of INFO severity. Both new implementations switch on severity alone
(`notifications.ts:117-124`; `notification-bell.ts:158-165`), so an assignment now looks exactly
like every other informational message. The type pill (`notifications.html:56-59`) partly
compensates on the page; the bell has no compensation at all.

**K8 -- `paging` is returned and cannot be read.**
`ResponseDto` carries a `paging` field (`ResponseDto.java:17`) that
`NotificationCenterServiceImpl.java:113-114` fills with page size, current page and total. The new
app's `ApiResponse` interface declares only `status`, `message` and `data`
(`core/api/api.config.ts:9-13`), so the total record count is discarded before any component sees
it.

**K9 -- The Redis unread counter can be silently wrong after a Redis restart.**
`create()` calls `increment` on `notif:unread:{userId}` (`NotificationCenterServiceImpl.java:79`);
on a missing key Redis creates it at 1. `unreadCount()` falls back to the database **only when the
key is absent** (`:120-127`). The keys carry no TTL -- they are written through a raw
`RedisTemplate` (`RedisConfig.java:25-35`), not through the `CacheManager` whose TTLs are
configured beside it. So after a flush or a restart, the first new notification for a user sets the
count to 1 and every earlier unread one stops being counted, until `markAllRead` resets it to 0.

**K10 -- Two authorisation paths for the same picture, and the shared component is used for
neither.**
`AuthService.avatarSync` reads the caller's own picture through `storage.json/previewObject`
(`core/auth/auth.service.ts:145-152`), which is authorised by the platform-bucket guard's
own-profile exception. `shared/ui/avatar.ts:66-71` reads other people's through
`appUser.json/avatar`, authorised by `readAvatar` + `TenantOwnership`. The `Avatar` component
handles both routes, and neither the header (`shell.html:79`) nor the profile card
(`profile.html:28`) uses it -- both hand-roll an `<img>`/initials pair against `auth.avatarUrl()`.

**K11 -- A picture whose filename has no extension is stored but can never be displayed.**
`profile.ts:365` derives the extension as
`file.name.slice(file.name.lastIndexOf('.') + 1).toLowerCase() || 'png'`. For a name with no dot,
`lastIndexOf` is `-1`, so the expression returns the **whole filename** -- `IMG_1234` yields the key
`7/profile/avatar.img_1234`. The upload succeeds and `updateOwnAvatar` stores the pointer, but
`previewObject` refuses any key whose extension is not previewable
(`StorageBrowserServiceImpl.java:169-171`; `ContentTypeUtil.java:74-76`), so the picture silently
never renders and the user is left looking at their initials with no error anywhere.

**K12 -- The "no storage connection" warning cannot render.**
`profile.html:75-79` is gated on `!targetBucket()`, and `targetBucket()` reads `avatarUploadBucket`
(`profile.ts:162`), which `AppUserServiceImpl.java:578-579` sets unconditionally to the configured
bucket name -- a value `StoragePropertyDefaults.AVATAR_BUCKET` guarantees is non-blank even when
the property is empty. The condition is therefore always false. The real failure -- no
`storage_connection` aliased `etl-avatar`, which `StorageConnectionBootstrap:149-155` warns about
at startup -- reaches the user only as an `"Unknown bucket: etl-avatar."` toast after they have
chosen a file.

**K13 -- The avatar size and type rules are client-only.**
`profile.ts:59-60, 351-358`. The server applies neither: `uploadObject` has no size or type check
beyond the 500 MB multipart limit (`application.properties:40-41`), and `isOwnProfileKey`
(`AppUserServiceImpl.java:539-546`) accepts any plain filename in the folder. Anyone signed in can
put arbitrary files of arbitrary size under their own `<appUserId>/profile/` prefix in the platform
avatar bucket.

**K14 -- Removing or replacing a picture orphans the object.**
`removePicture()` calls `saveAvatar('', '')`, which clears the two columns and nothing else
(`profile.ts:387-409`). No `deleteObject` call exists anywhere in this feature. Changing format --
png to jpg -- strands the previous file too, which the code acknowledges at `profile.ts:100-103`.

**K15 -- The server still writes Angular-8 link URLs.**
All five `create` call sites pass `/jobList` or `/taskList`: `engine/BulkAction.java:249, 253`;
`SourceJobServiceImpl.java:101`; `SourceJobBulkServiceImpl.java:252`;
`SourceTaskServiceImpl.java:632`. Rows written by the server today need the rewrite map exactly as
much as rows written three years ago, so `notification-links.ts` cannot ever be retired, and any
route the map forgets sends a click to the wildcard redirect.

**K16 -- Six of the ten notification types are never raised.**
`NotificationType` declares ten (`model/enums/NotificationType.java:6-8`). Only `JOB_COMPLETED`,
`JOB_FAILED`, `TASK_ASSIGNED` and `BATCH_DONE` have a `create` call anywhere in
`process/src/main/java`. `JOB_SKIPPED`, `KAFKA_TEST_FAILED`, `USER_ADDED`, `FILE_SHARE_SENT`,
`FILE_SHARE_FAILED` and `FILE_SHARED_WITH_YOU` appear nowhere but the enum -- and the old app's
model listed all ten as though they existed
(`scheduler1/src/app/_models/notification.model.ts:1-2`). Notably, a *skipped* job raises nothing
even though `BulkAction.notifyJobOutcome` returns early for any status that is not Completed or
Failed (`BulkAction.java:241-244`).

**K17 -- `notification.tenant_id` is written, indexed and never read.**
`NotificationCenterServiceImpl.java:68` sets it; every repository query keys on
`recipient_user_id` alone (`NotificationRepository.java:19-33`); `V18__foreign_key_indexes.sql:24`
indexes it. The entity declares no `@Filter` (`.ai/discovery/database.md:335`), so the tenant filter
never acts on it either. Also recorded as risk 30 in `.ai/discovery/risks.md:105`.

**K18 -- No changeset creates the `notification` table.**
`V17__table_descriptions.sql:45-46` comments it and `V18__foreign_key_indexes.sql:24-25` indexes it,
but no `CREATE TABLE` for it exists under `db/changelog/changelog-sets`. The table exists only
because `ddl-auto=update` creates it in dev (`application-dev.properties:87`). Stage and prod run
`validate` (`application-stage.properties:90`, `application-prod.properties:92`), so a stage or
prod database that has never been through a dev boot has nothing for V17 and V18 to act on.

**K19 -- No foreign keys on `notification`.**
Neither `recipient_user_id` → `app_user` nor `tenant_id` → `tenant` has a constraint; the V12--V14
FK sweep did not include this table (`.ai/discovery/database.md:618-619`).

**K20 -- The list timestamp lost its year.**
Old: `date:'MMM d, y, h:mm a'` (`notification-center.component.html:41`). New:
`date: 'd MMM, HH:mm'` (`notifications.html:70`). Given K4 is fixed and older notifications become
reachable, two rows a year apart will read identically.

**K21 -- The Chicago clock and the email line were dropped from the user menu.**
`app.component.ts:25-27, 78-80, 127-130` and `app.component.html:131-138` rendered a live
`America/Chicago` clock, the role label and the username in the navbar user card. The new user menu
(`shell.html:88-94`) shows the name and the role only. The email moved to `/profile`; the clock has
no successor anywhere, and the scheduler's whole domain is timetables.

**K22 -- No test covers the notification centre.**
There is no `NotificationCenterServiceImpl` test under `process/src/test`, and no `notifications`,
`notification-bell` or `profile` spec under `scheduler1/next/src`. The only covered piece is the
route rewriting (4 tests). `updateOwnProfile`, `changeOwnPassword` and `fetchMyActivity` are
likewise untested; only `updateOwnAvatar` and `readAvatar` have coverage
(`AppUserServiceImplRoleScopeTest.java:323-423`).

**K23 -- The list sort is applied twice.**
`NotificationCenterServiceImpl.java:106` builds a `Pageable` sorted `dateCreated desc` and passes it
to repository methods whose names already end `OrderByDateCreatedDesc`
(`NotificationRepository.java:19, 21`). Both orderings agree, so today the result is correct;
changing one without the other would not be caught by anything.

**K24 -- `changeOwnPassword` is the only own-account write with no `@Transactional`.**
`currentUser` (`:442-443`), `updateOwnProfile` (`:461-462`) and `updateOwnAvatar` (`:500-501`) all
carry it; `changeOwnPassword` (`:602-603`) does not. The single `save()` is transactional in its own
right, so today's behaviour is correct -- but a second write added to that method would not be
atomic with the first.

**K25 -- `notification.json/list` has no server-side ceiling on `limit`.**
`PagingUtil.java:45-47` only replaces a null or sub-1 value with the default of 10. Nothing stops
`?limit=1000000`.

---

## 13. Missing functionality

Absent from both applications unless stated, with what it would take.

| Missing | What it would take |
|---|---|
| **Deleting or archiving a notification.** No repository delete, no endpoint, no UI, and no retention job. The table only grows, forever, for every user. | A `DELETE /notification.json/{id}` scoped by recipient, a bulk clear-read, and a scheduled purge of read rows older than N days. Small; the index it needs already exists. |
| **Marking something unread.** Reading is one-way. | Reuse `markRead`'s shape with a boolean; the Redis counter would need an increment on the same terms. |
| **Notification preferences.** No control over which types a person receives, or in-app versus email. `source_job`'s three email flags are a separate mechanism and do not feed this table. | A per-user preference row and a check inside `NotificationCenterServiceImpl.create`. Medium; a design decision first. |
| **Live push in the new app.** The server already sends `{notification, unreadCount}` to `/user/queue/notifications` (`NotificationCenterServiceImpl.java:83-96`); the old client consumed it; the new app's only STOMP consumer subscribes `/topic/jobs.*` (`core/socket/job-events.service.ts:51-58, 97-104`). | A second subscription on the existing client and a shared notification store. Small, and it removes the 60-second poll. |
| **A navigation entry for either screen.** Neither `/notifications` nor `/profile` is in `shell.ts`'s `nav()`; the bell's own comment records that the page was previously unreachable except by typing the URL (`notification-bell.ts:18-23`). | Two entries. Trivial. |
| **A "since you last looked" divider, or grouping by day.** 130 undifferentiated rows is a list, not a summary. | Presentational; needs `read_at` or a stored last-seen timestamp. |
| **Any account-security surface beyond the password.** No session list, no "sign out of all devices", no 2FA, no e-mail change, no record of when the password last changed. | Each is its own piece of work; a `password_changed_at` column and a sessions view are the cheap two. |
| **Avatar cropping, resizing or server-side re-encoding.** The stored object is whatever was uploaded. | A crop step client-side, or a server-side thumbnail on upload. Would also close K13. |
| **A tenant-scoped or platform-wide announcement.** Every notification has exactly one recipient (`recipient_user_id` is `NOT NULL`). There is no way to tell a whole workspace anything. | A nullable recipient with a tenant fan-out, or a separate announcement table. Medium, and it changes the read-state model. |
| **Any use of `notification.tenant_id`.** Written, indexed, unread. | Either read it (a platform admin's cross-tenant view) or drop the column and its index. |
| **Server-side avatar limits.** See K13. | A type and size check in `updateOwnAvatar`'s upload path, or a dedicated avatar upload endpoint that does not go through the general object browser at all. |
