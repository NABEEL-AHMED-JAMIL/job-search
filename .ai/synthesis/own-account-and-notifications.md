# Synthesis -- Own Account and Notifications

Companion to `.ai/grooming/own-account-and-notifications.md`. Paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

This row is recorded as *migrated*, and on the profile half that is an understatement -- the profile
screen, avatars, phone numbers, job titles and the password-change gate are all new, and none of it
existed in the old app. The notification half is where the accounting has to be done, and the
pattern there is the one this project keeps finding: **what was a control survived the rewrite,
what was ambient did not.** The new page gained a type filter, a per-row mark-read, a `New` pill,
real empty and error states and dark mode. It lost server paging, a server-side unread filter, an
authoritative unread badge, the single shared count that kept the bell and the page honest with
each other, the live WebSocket push that made a notification arrive rather than be polled for, the
person glyph that made an assignment look different from a job outcome, and the year in the
timestamp. Four of those six losses share one cause: **the old app had a `NotificationService`
holding the state, and the new app has two components that each hold their own.** Fix that one
thing and K1, K2, K3 and the polling all fall out together.

Underneath, the backend is in better shape than the client. Every endpoint takes its subject from
the token, `markRead` carries the recipient in its `WHERE` clause so a stolen id updates nothing,
the avatar key is checked in two independent places, and the platform-bucket exception is narrow
enough to have a comment explaining why `1248` does not match `12480/`. The real server-side work
is small and specific: the unread counter can go silently wrong after a Redis restart, the avatar
size and type rules exist only in the browser, no changeset creates the `notification` table, and
there is no way to delete a notification at all -- a table that only ever grows, per user, forever.
Finally, the server is still writing Angular-8 link URLs into new rows, which means the rewrite map
that everyone treats as a migration shim is in fact permanent load-bearing code.

The work is restoration plus a small correctness pass, not a rebuild. One shared store, one paging
control, one Redis fix, one server-side upload rule, one migration, one retention decision.

---

## 2. The gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | Bell badge = unread rows within `list?limit=20` (`notification-bell.ts:102, 124`); dashboard and profile each call `unreadCount` once (`dashboard.ts:154`, `profile.ts:227`) | One unread number, from the server, shared by every consumer | Shared state dropped; old app had one `BehaviorSubject` (`_services/notification.service.ts:15-16`) | A `core/notifications/notification-store.ts` root service owning `unread`, `recent` and the mutations; bell, page, dashboard and profile all read it | M | Low |
| 2 | Marking read on `/notifications` leaves the bell stale for up to 60 s (`notifications.ts:92-110` vs `notification-bell.ts:110`) | Any mark-read moves every counter at once | Same root cause as 1 | Falls out of 1 -- the mutations live in the store | S | Low |
| 3 | Server pushes `{notification, unreadCount}` to `/user/queue/notifications` (`NotificationCenterServiceImpl.java:83-96`); nothing subscribes. Bell polls every 60 s | A notification arrives; it is not waited for | Live push dropped; the new app's one STOMP consumer subscribes `/topic/jobs.*` (`job-events.service.ts:51-58, 97-104`) | Add a user-queue subscription to the existing `Client` and feed the store; keep a slow poll as a fallback | M | Medium |
| 4 | One `page=1&limit=100` request, no pager (`notifications.ts:59-60`); old paged 20/page server-side with a numbered pager (`notification-center.component.ts:16-18`; `.html:49-53`) | Every notification is reachable | Server paging dropped; `paging` in the envelope is not even typed client-side (`api.config.ts:9-13`) | Add `paging` to `ApiResponse`; drive `page`/`limit` from the component; render the existing `[pager]` slot `TableShell` already reserves (`data-table.ts:69`) | M | Low |
| 5 | `unreadOnly` filtered client-side over the loaded 100 (`notifications.ts:44-45`); the endpoint supports it (`NotificationRestApi.java:32`) | "Unread only" means all my unread ones | Server filter dropped | Send `unreadOnly` and reload; reset to page 1 on change | S | Low |
| 6 | Kind-filter options derived from loaded rows (`notifications.ts:39-40`) | The filter offers every type the user has | Derived from a page, not from the data | Populate from `NotificationType` (a fixed enum of 10), or add a distinct-types call. Prefer the enum | S | Low |
| 7 | `TASK_ASSIGNED` renders the generic info glyph in both new views (`notifications.ts:117-124`, `notification-bell.ts:158-165`); old returned a person glyph (`_services/notification.service.ts:137`) | An assignment looks different from a job outcome | Type dropped from the glyph decision | One shared `glyphOf(severity, type)` in the store module, used by both views | S | Low |
| 8 | `date: 'd MMM, HH:mm'` (`notifications.html:70`); old carried the year (`notification-center.component.html:41`) | A timestamp is unambiguous | Year dropped -- harmless at 100 rows, wrong once gap 4 lands | Relative time under a day, `d MMM HH:mm` inside the year, `d MMM y` beyond it | S | Low |
| 9 | `create` increments a Redis key that may not exist (`NotificationCenterServiceImpl.java:79`); `unreadCount` trusts any present key (`:120-127`); no TTL (`RedisConfig.java:25-35`) | The count is right, or it is recomputed | After a Redis flush the first new notification sets the count to 1 and hides the rest | Give the key a TTL and re-derive on a miss; recompute rather than increment when the key is absent | S | Medium |
| 10 | Avatar type and size checked only in the browser (`profile.ts:59-60, 351-358`); multipart limit is 500 MB (`application.properties:40-41`) | The server enforces what the browser claims | Client-only validation on a write into a platform bucket | Check content type and size in `StorageBrowserServiceImpl` when the own-profile exception is the reason the write is allowed | S | Medium |
| 11 | Extension taken from the uploaded filename (`profile.ts:365`); a name with no dot yields `avatar.img_1234`, which `previewObject` then refuses (`ContentTypeUtil.java:74-76`) | Any accepted image renders | The `\|\| 'png'` fallback never fires, because `slice(-1 + 1)` returns the whole name | Derive the extension from the validated MIME type, not the filename | S | Low |
| 12 | "No storage connection is available" is gated on `!targetBucket()` (`profile.html:75-79`), and `avatarUploadBucket` is never blank (`AppUserServiceImpl.java:578-579`) | The screen says so before a file is chosen | Dead UI; the real failure arrives as a toast after the upload | Have `/me` report whether an *Active* connection for the bucket exists, and gate on that | S | Low |
| 13 | `removePicture()` clears the pointer only (`profile.ts:387-409`); a format change strands the old file (`profile.ts:100-103`) | Removing removes | No delete call anywhere in the feature | Delete the object server-side inside `updateOwnAvatar` when clearing or replacing, using the key already on the row | M | Medium |
| 14 | No changeset creates `notification`; `V17:45-46` comments it and `V18:24-25` indexes it | A fresh stage/prod database builds | The table exists only via `ddl-auto=update` in dev (`application-dev.properties:87`) | A `CREATE TABLE IF NOT EXISTS` changeset ordered before V17, plus FKs on `recipient_user_id` and `tenant_id` | S | Medium |
| 15 | No delete, no archive, no retention; `notification` only grows | Old read notifications age out | Never built, in either app | `DELETE /notification.json/{id}` scoped by recipient, a "clear read" bulk action, and a scheduled purge of read rows past a configured age | M | Medium |
| 16 | `tenant_id` written, indexed, never read (`NotificationCenterServiceImpl.java:68`; `NotificationRepository.java:19-33`) | No column carries a claim nothing checks | Also risk 30 in `.ai/discovery/risks.md:105` | Decide: give it an FK and a platform-admin cross-tenant read, or drop the column and `idx_notification_tenant_id` | S | Low |
| 17 | Six of ten `NotificationType` values are never raised (`NotificationType.java:6-8`); a *skipped* job raises nothing (`BulkAction.java:241-244`) | The enum describes what happens | Four types in use; six aspirational | Raise `JOB_SKIPPED`; delete the five with no plausible producer, or record why they are kept | S | Low |
| 18 | Server writes `/jobList` and `/taskList` into new rows (`BulkAction.java:249, 253`; `SourceJobServiceImpl.java:101`; `SourceJobBulkServiceImpl.java:252`; `SourceTaskServiceImpl.java:632`) | New rows carry routes this app has | The rewrite map is permanent rather than transitional | Move the link vocabulary server-side to the current routes; keep `notification-links.ts` for the historical rows | S | Medium |
| 19 | Own picture read via `storage.json/previewObject` (`auth.service.ts:145-152`); everyone else's via `appUser.json/avatar` (`shared/ui/avatar.ts:66-71`); `Avatar` used by neither the header nor the profile card | One way in, one component | Two authorisation paths for the same picture, and a shared component nobody adopted | Point `AuthService` at `appUser.json/avatar?appUserId=<self>` and render `app-avatar` in both places | S | Low |
| 20 | Neither `/notifications` nor `/profile` is in `shell.ts`'s `nav()` | Both are navigable | The bell's own comment records the page was once unreachable except by URL (`notification-bell.ts:18-23`) | Two nav entries | S | Low |
| 21 | Chicago clock and username dropped from the user menu (`app.component.ts:127-130`; `app.component.html:131-138` → `shell.html:88-94`) | An operator can see the scheduler's reference time | Ambient information dropped | Decide whether the clock belongs -- see open question 3 | S | Low |
| 22 | No test for the notification centre on either side; `updateOwnProfile`, `changeOwnPassword` and `fetchMyActivity` untested | The rules that hold this feature together are asserted | Only `notification-links.spec.ts` (4 tests), `updateOwnAvatar` and `readAvatar` are covered | `NotificationCenterServiceImplTest` (recipient scoping, Redis behaviour), `AppUserOwnProfileTest`, `MyActivityTest`, and specs for the store, the page and the profile forms | M | Low |
| 23 | `limit` uncapped on `notification.json/list` (`PagingUtil.java:45-47`) | A list endpoint has a ceiling | Nothing stops `?limit=1000000` | Clamp in `NotificationCenterServiceImpl.list` | S | Low |
| 24 | Sort applied twice (`NotificationCenterServiceImpl.java:106` + `OrderByDateCreatedDesc`) | One ordering, in one place | Belt and braces that can drift | Use `findByRecipientUserId(...)` without the method-name ordering and let the `Pageable` decide | S | Low |
| 25 | `changeOwnPassword` has no `@Transactional`, unlike its three siblings (`AppUserServiceImpl.java:602-603`) | Consistent transaction boundaries | Correct today by accident of having one write | Add the annotation | S | Low |

---

## 3. Solution detail

Only the rows where the approach was a genuine choice are argued. The rest are substitutions whose
alternative is "leave it".

### Gaps 1, 2, 3, 5 -- one store, and what it replaces

**What changes.** A new root-provided `core/notifications/notification-store.ts` owning:

- `unread: Signal<number>` -- fed by `notification.json/unreadCount`, and by the `unreadCount`
  field the server already sends on every live push.
- `recent: Signal<Note[]>` -- the newest ~12, for the bell.
- `refreshUnread()`, `loadRecent()`, `markRead(id)`, `markAllRead()` -- each performing the request
  *and* the local update, so a caller cannot do one without the other.

`features/shell/notification-bell.ts` loses its `items`/`unread`/`recent` signals, its
`setInterval`, and its three HTTP calls, and becomes a view over the store.
`features/notifications/notifications.ts` keeps its own paged list (that is page state, not app
state) but routes every mutation through the store. `features/dashboard/dashboard.ts:154` and
`features/profile/profile.ts:227-230` drop their one-shot `unreadCount` calls and read
`store.unread()`.

For gap 3, `core/socket/job-events.service.ts` gains a second `client.subscribe`, on
`/user/queue/notifications`, using the same connect headers it already sends; the frame body is the
JSON `NotificationCenterServiceImpl.java:93-96` builds, and the store consumes it.

**Why this rather than the alternatives.**

*Rejected: give the bell its own `unreadCount` call and leave the three consumers independent.*
This is the one-line fix for gap 1 and it is tempting. It was rejected because it does not touch
gaps 2 or 3, and it makes the disagreement worse rather than better: four independent readers of
one number, each refreshing on its own schedule, is not "one number shown four times", it is four
numbers that happen to agree most of the time. The old app got this right with one
`BehaviorSubject` and the rewrite lost it; restoring the shape is the fix, not patching one reader.

*Rejected: keep polling and drop the WebSocket idea entirely.* Polling is honest and it works. But
the server already does the push -- the code is written, tested by the old client, and running in
production right now, sending to a queue nobody listens on. The marginal cost is one `subscribe`
call on a `Client` that is already connected for the whole session. Declining that in favour of a
60-second timer is paying for the same thing twice. The poll stays as a fallback at a longer
interval, because a socket that silently drops must not leave the badge frozen.

*Rejected: move the whole notification list into the store too.* Page number, filters and the
current slice belong to the screen looking at them, not to the application. Two consumers with
different needs (8 rows for the bell, a paged list for the page) sharing one collection is how the
old `MAX_RECENT` constant ended up deciding what the page could show. The store owns the *count*
and the *recent* list; the page owns its own query.

**Risk.** Gap 3 is the only Medium here. Two subscriptions on one STOMP client means a frame parse
failure on one destination must not tear down the other -- `job-events.service.ts:98-103` already
swallows a bad frame per-subscription, and the new one must do the same. It also means the
reconnect effect (`:73-80`) now restores two subscriptions, so both must be re-created in
`onConnect`, not once at construction.

### Gap 4 -- paging, and why the client-side pager is not the answer

**What changes.** `ApiResponse` in `core/api/api.config.ts` gains an optional
`paging?: { pageSize: number; currentPage: number; totalRecord: number }`, matching what
`PagingUtil.convertEntityToPagingDTO` already returns. `notifications.ts` holds `page` and `limit`
signals, passes them to the request, reads `totalRecord` back, and renders a pager into
`TableShell`'s existing `[pager]` slot.

*Rejected: keep the single request and wrap the rows in `createPager` (`shared/ui/pager.ts`).* This
is what several other screens in the new app do, and it would be consistent with them. It was
rejected because it does not solve the problem: paging 100 rows in the browser still leaves rows
101 and older unreachable, and it makes gap 5 *worse* -- "unread only" over a client-side pager
reads as though it searched everything. The endpoint pages server-side already; there is nothing to
build on the server, only a client that stopped asking.

*Note the ordering dependency.* Gap 5 is nearly free once gap 4 lands, because both are the same
change to the same request. Doing 5 alone -- sending `unreadOnly` against a fixed `limit=100` --
would fix the filter and leave the pager missing, which is a strange half-state. Do them together.

### Gap 9 -- the Redis counter

**What changes.** In `NotificationCenterServiceImpl`:

- `create` stops calling `increment` blind. It checks for the key; on a miss it counts in the
  database (the row it just wrote is included) and `set`s that, on a hit it increments.
- Every `set` carries a TTL -- a day is generous -- so a counter that has drifted for any reason
  self-heals rather than being wrong until the next `markAllRead`.

*Rejected: drop Redis and count in the database every time.* The query is
`countByRecipientUserIdAndReadFalse` against `idx_notification_recipient_read`, which is cheap, and
it is unconditionally correct. It was rejected because gap 3 makes the count part of every push
payload, and the push happens inside `create`, which already runs `REQUIRES_NEW` on the job
completion path -- adding a count query to every job outcome is a cost paid by the scheduler rather
than by the person looking at a badge. Redis is the right shape; it just needs to fail towards
recomputation instead of towards a stale 1.

*Rejected: expire the key on every write.* Simpler, but it turns the cache into a no-op under load,
which is the case it exists for.

**Risk Medium** because the fix is only correct if the count-on-miss happens inside the same
transaction as the insert, or after the flush -- `saveAndFlush` at `:77` already forces the write,
so counting after that line is right and counting before it is off by one.

### Gaps 10, 11, 13 -- the avatar path

These three are one piece of work, because they all live at the seam between
`profile.ts`'s upload and the storage guard's own-profile exception.

**What changes.**

- `StorageBrowserServiceImpl.uploadMultipart` learns that when the write was permitted *only* by
  `isOwnProfileObject` (rather than by the caller being a platform admin), the object must be an
  image and must be under a configurable ceiling. That is the honest place for the rule: it is the
  one path by which a non-admin writes into a platform bucket, and it is where the exception is
  granted.
- `profile.ts` derives the extension from the MIME type it has already validated -- a four-entry
  map -- rather than from `file.name`.
- `updateOwnAvatar` deletes the object the row currently points at when the key is being cleared,
  and when the new key differs from the old one.

*Rejected: a dedicated `POST /appUser.json/uploadOwnAvatar` that takes the multipart directly and
never touches the object browser.* This is architecturally cleaner -- it would remove the only
reason a tenant user can address a platform bucket at all, and with it the whole `isOwnProfileObject`
exception, `12480/` comment included. It was rejected for **now** because that exception is also
what makes `previewObject` work for the caller's own picture, and removing it means moving the read
path too (gap 19) and re-testing every case in
`AppUserServiceImplRoleScopeTest.java:323-423` plus whatever covers the storage guard. It is the
right end state and it is recorded in open question 2 rather than being done quietly here.

*On gap 13's risk.* Deleting an object during a profile save is the first destructive act this
feature performs. If the delete fails the pointer must still be cleared -- a user who pressed Remove
must not be told it failed and left with their picture -- so the delete is best-effort and logged,
and the pointer write is what the response reports. That asymmetry needs to be deliberate, which is
why this is Medium rather than Small.

### Gap 14 -- the missing `CREATE TABLE`

**What changes.** A changeset creating `notification` with the columns
`Notification.java:30-65` declares, ordered **before** `V17` (which comments the table) and `V18`
(which indexes it), guarded `IF NOT EXISTS` in the style V8 and V11 already use for exactly this
reason. FKs on `recipient_user_id` → `app_user` and `tenant_id` → `tenant` go in the same
changeset, which also settles gap 19's first half.

*Rejected: add it as a new high-numbered changeset at the end.* It would create the table on a
fresh database, but only after V17 and V18 had already failed against it. Liquibase runs in file
order, so the fix has to sit ahead of the two changesets that assume the table.

*Rejected: leave it and rely on `ddl-auto`.* Stage and prod are `validate`
(`application-stage.properties:90`, `application-prod.properties:92`). The current estates work
because their databases passed through a dev boot at some point in their history. That is not a
property anyone should be relying on, and it is invisible until the day somebody provisions a clean
environment.

### Gap 15 -- retention

**What changes.** Three pieces: a scoped delete endpoint, a "clear read" bulk action on the page,
and a scheduled purge with a configurable age.

*Rejected: soft-delete, matching every other table in this schema.* `source_job`, `source_task`,
`app_user` and the rest all soft-delete via a status column, and consistency is a real argument.
It was rejected because a notification has no history worth keeping -- it is a copy of an event
that is recorded properly elsewhere (`job_queue`, `job_audit_logs`), and a soft-deleted
notification is a row that costs storage and index space forever to preserve information nobody
will ever ask for. Hard delete, with the recipient in the `WHERE` clause exactly as `markRead`
already does it.

*Rejected: purge on read count rather than on age.* "Keep the newest 500 per user" is bounded,
which is attractive, but it means a user who reads nothing for a month silently loses the oldest
unread rows. Age with a floor -- never purge an unread row -- is easier to explain and easier to
defend.

### Gap 18 -- the link vocabulary

**What changes.** The five `create` call sites pass the current routes (`/jobs`, `/tasks`).
`notification-links.ts` and its four tests stay exactly as they are, because rows already in the
database still carry the old paths and the old app is still running against the same database.

*Rejected: a backfill `UPDATE notification SET link_url = ...`.* It would let the rewrite map be
deleted, which is the tidy end state. It was rejected because **the old app is still live against
this database** (`notification-links.ts:1-9` says so explicitly), and rewriting `/jobList` to
`/jobs` in the table would break every click in the old client. The map is the price of running two
frontends, and it stays until one of them is switched off.

*Why change the server at all, then?* Because the map only helps routes it knows about. Every new
route the server starts referencing is a route somebody has to remember to add in two places -- the
server and the map. Writing current routes going forward shrinks that surface to the historical
rows only, which is a fixed set that can be enumerated once.

### Gap 19 -- one avatar path

**What changes.** `AuthService.avatarSync` (`auth.service.ts:139-152`) calls
`appUser.json/avatar?appUserId=<own id>` instead of `storage.json/previewObject`. The header
(`shell.html:76-83`) and the profile card (`profile.html:27-36`) render `<app-avatar>` with an
`appUserId`, which already handles the blob URL, the revoke-on-destroy and the initials fallback
(`shared/ui/avatar.ts`).

*Rejected: leave `previewObject` and just adopt `<app-avatar>` with bucket/key.* It would remove
the duplicated markup but keep two authorisation paths for the same picture, which is the part that
actually costs something: `readAvatar` refuses via `TenantOwnership` and `previewObject` refuses via
`isOwnProfileObject`, and a change to either is a change to how somebody's face is protected. One
path, checked in one place.

*Consequence worth noting.* `readAvatar` resolves the key from the row rather than from the request
(`AppUserServiceImpl.java:81-84`), so after this change a stale `avatarKey` in the stored
`AuthUser` blob can no longer produce a wrong picture -- the server is the only thing that decides
which object is read.

---

## 4. Ordering

**First, because everything else reads more clearly afterwards:**

1. **Gap 1** -- the notification store. It is the prerequisite for 2 (free once it lands), 3 (needs
   somewhere to put a pushed notification) and part of 4 (the page's mutations route through it).
2. **Gap 14** -- the `CREATE TABLE` changeset. Independent of everything, and it unblocks anyone
   trying to stand up a clean environment to test the rest of this.

**Then the list itself, as one change:**

3. **Gaps 4 + 5 + 6 + 8** -- server paging, the server-side unread filter, the fixed type list, and
   the timestamp format. These are all edits to `notifications.ts` and its template plus the one
   `ApiResponse` field, and doing them separately means touching the same request three times.
   Gap 8 in particular only *matters* once gap 4 lands.

**Then the two server correctness items, in either order:**

4. **Gap 9** -- the Redis counter. Do it after gap 1, so there is a single client-side consumer to
   verify against.
5. **Gaps 10 + 11 + 13** -- the avatar path as one piece. Gap 11 is a one-line client fix but it is
   pointless in isolation, since a file that fails it produces exactly the symptom gap 13's cleanup
   would otherwise be tidying up.

**Then, and only then, the push:**

6. **Gap 3** -- the WebSocket subscription. Last of the behavioural work, because it is the only
   item that can fail intermittently and the only one whose failure looks like "nothing happened".
   Debugging it against a store that is otherwise proven is a much shorter afternoon.

**Alongside, at any point:** gaps 7, 12, 19, 20, 21, 23, 24, 25 are independent small edits.
**Gap 22** (tests) is written with each item rather than after all of them --
`NotificationCenterServiceImplTest` belongs to gap 9, the store spec to gap 1, the paging spec to
gap 4.

**Deferred until a decision:** gaps 15, 16, 17 and 18 all need an answer from §6 first.

**What this unblocks elsewhere.** Nothing downstream depends on this feature -- Discovery records it
as depended on by nothing (`.ai/discovery/features.md:471`). But gap 18 has a standing obligation
in the other direction: **every feature whose route changed in the rewrite must be represented in
`notification-links.ts`**. `pdf-highlighter` is the live case -- it is not migrated, so a stored
`/pdfHighlighter` link currently maps to nothing, and whatever that feature's own synthesis decides
(migrate or drop) determines whether the map needs an entry or the notifications need purging.

---

## 5. Out of scope

**Rebuilding the old app's notification screen.** The old `NotificationCenterComponent` is not
coming back and nothing here should be read as a proposal to restore its markup. What is being
restored is four *behaviours* it had; the new screen's chrome, filters, states and theming are
better and stay.

**Notification preferences.** Choosing which types you receive, or in-app versus email, is a real
gap (§13 of grooming) and a real design decision. It touches `NotificationCenterServiceImpl.create`,
a new preference table, and the relationship with `source_job`'s three existing email flags -- which
are a separate mechanism that does not feed this table at all. It is not a migration gap; nothing
was lost. Out of scope until somebody asks for it.

**Tenant-wide or platform-wide announcements.** `recipient_user_id` is `NOT NULL`
(`Notification.java:38-39`), so there is no way to address a workspace. Adding one changes the
read-state model -- one row per recipient, or one row with a per-user read table -- and is a feature,
not a repair.

**Account security beyond the password.** No session list, no "sign out everywhere", no 2FA, no
`password_changed_at`. Each belongs to `authentication-and-access` rather than to the profile
screen, and each is its own piece of work.

**Avatar cropping and server-side re-encoding.** Gap 10 puts a type and size ceiling on the upload;
it does not resize, crop or re-encode. A 2 MB PNG rendered into a 28-pixel circle is wasteful and
nobody has complained.

**The four other things `notification.json` could grow.** Mark-as-unread, grouping by day, a
"since you last looked" divider, and a search box. All reasonable, none of them lost in the
rewrite.

**Everything about how notifications are *raised*.** The five `create` call sites belong to
`source-jobs`, `source-tasks` and `bulk-transfer`. Gap 17 and gap 18 touch their arguments, and
that is the whole extent of it -- when a notification should be raised is those features' question.

---

## 6. Open questions

**Q1. What does `notification.tenant_id` mean -- and does it stay?**
It is written on every row, indexed, has no FK, and is read by nothing
(`NotificationCenterServiceImpl.java:68`; `NotificationRepository.java:19-33`; risk 30 in
`.ai/discovery/risks.md:105`). Options: (a) drop the column and `idx_notification_tenant_id`;
(b) keep it and give it an FK, purely as provenance; (c) keep it and build something that reads it,
such as a platform-admin view of a tenant's notification volume.
**Recommendation: (b).** Dropping it is the tidiest answer and the one the "no column carries a
claim nothing checks" principle argues for -- but it is a one-way door on a column that is already
populated with correct data across the whole estate, and re-deriving it later would mean joining
every notification back to its recipient's *current* tenant, which is not the same thing as the
tenant at the time. Add the FK in gap 14's changeset, keep the column, and drop
`idx_notification_tenant_id` -- an index supporting no query is pure cost, and it can be re-created
in an afternoon if (c) ever happens.

**Q2. Does the avatar upload keep going through the object browser?**
Today a tenant user writes into a platform bucket, and the only thing making that safe is
`isOwnProfileObject` (`StorageBrowserServiceImpl.java:484-511`) -- a carefully-argued exception with
a comment about `12480/` and a trailing-separator check, i.e. exactly the kind of rule that is
correct and fragile. The alternative is a dedicated `appUser.json/uploadOwnAvatar` that takes the
multipart, builds the key itself, and writes through `uploadForWorkflow` -- after which the
exception could be deleted entirely, and gap 19 would follow for free.
**Recommendation: do gap 10 now, and schedule the dedicated endpoint.** The exception is currently
load-bearing for both the write *and* the read, so removing it is a two-sided change that wants its
own slot rather than being smuggled into an avatar fix. But it is the right end state: this feature
is the sole reason a non-admin can name a platform bucket at all, and a feature should not be the
reason a security exception exists.

**Q3. Does the Chicago clock come back, and where?**
The old navbar showed a live `America/Chicago` clock ticking every second
(`app.component.ts:127-130`). The new app shows no time anywhere. In a product whose entire subject
is timetables, that is not obviously decoration -- but "Chicago" is hardcoded and undocumented, and
`.ai/synthesis/dashboard.md` gap 13 records that the same zone question is unresolved on the
dashboard, where the new app derives dates in UTC and the old one in Chicago.
**Recommendation: do not restore it here, and do not restore it as "Chicago".** Answer the zone
question once, in the dashboard's synthesis, and whatever that decides -- a configured platform
zone, or the browser's -- surface it in the shell header for every screen rather than in the user
menu for whoever opens it. Restoring a hardcoded Chicago clock now would make it harder to change
later, because it would then be in two places instead of none.

**Q4. What is the retention period for a read notification?**
Gap 15 needs a number. Options: 30, 90, or 365 days, with unread rows never purged.
**Recommendation: 90 days, configurable, unread never purged.** Ninety days outlives any
quarter-end investigation, and the row is a copy of an event recorded properly in `job_queue` and
`job_audit_logs`, so nothing is actually lost. Making it a property rather than a constant means an
operator with a compliance reason to keep more can, without a release.

**Q5. Should the five unproducible notification types be deleted from the enum?**
`KAFKA_TEST_FAILED`, `USER_ADDED`, `FILE_SHARE_SENT`, `FILE_SHARE_FAILED` and
`FILE_SHARED_WITH_YOU` have no `create` call anywhere (`NotificationType.java:6-8`), and the old
app's model listed all of them as though they worked
(`scheduler1/src/app/_models/notification.model.ts:1-2`). `JOB_SKIPPED` is the sixth and is
different -- a skipped job is a real event the engine already observes
(`BulkAction.java:241-244` returns early for it).
**Recommendation: raise `JOB_SKIPPED`, keep the other five, and document them.** Deleting an
`@Enumerated(EnumType.STRING)` value is only safe if no row in any environment holds it, which
nobody has checked -- and `FILE_SHARED_WITH_YOU` in particular names a feature that exists
(`fileShare.json/send` is live in `object-browser`) and simply never learned to notify. Add a
one-line comment beside each saying "declared, not yet raised", which costs nothing and stops the
next reader assuming they are broken.

**Q6. Does the notification list get a nav entry, or stay bell-only?**
Neither `/notifications` nor `/profile` appears in `shell.ts`'s `nav()`.
**Recommendation: `/profile` stays in the user menu where people look for it; `/notifications` gets
a nav entry.** The bell is a peek, not a destination, and "View all notifications" is currently the
only route to a full-page list -- which means a user who has dismissed the dropdown has to open it
again to get back. A nav entry costs one line and removes the dependency on a transient popover.
