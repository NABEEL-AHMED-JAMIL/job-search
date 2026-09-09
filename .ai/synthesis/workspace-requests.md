# Synthesis -- Workspace Requests

Feature `workspace-requests`, row 17 of [../discovery/features.md](../discovery/features.md), status
**new**. Reads with [../grooming/workspace-requests.md](../grooming/workspace-requests.md); the issue
codes below (K-1 … K-16) are that document's Known issues section.

Paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Summary

This feature is small, well-shaped and almost entirely unguarded. The design is right in the places
that are hardest to get right: a request is stored rather than acted on, because it arrives
unverified; the acknowledgement is one string returned from both branches, so the public form cannot
be used to ask "does this person have an account here?"; the generated password is hashed
immediately, never returned in a response, and masked in the mail log; approval is transactional, so
a failure between the tenant and its first administrator leaves neither. Both screens use the shared
chrome, both themes are token-only, and the queue's card view exists for a stated reason rather than
for decoration.

What it does not have is any enforcement below the controller, and any test at all. For this feature
the service rule and the Hibernate filter are both **empty by design** -- the entity is
platform-owned, there is no per-tenant slice of it to get wrong -- which means three
`@PreAuthorize("hasRole('PLATFORM_ADMIN')")` annotations are the entire authorization story, and
nothing in either test suite would notice if one of them were deleted. The same is true in the other
direction: the `permitAll()` on `submit` is a method-level annotation on a class the codebase's own
convention would give a class-level one, and the day someone follows that convention, sign-up closes
silently. Both of those are one test each, and both tests are missing.

Beyond coverage, five things need changing and one needs deciding. **The only anonymous write in
the application has no rate limit and no length limits** (K-3, K-4), so an unauthenticated caller can
write unbounded rows of unbounded size, and an over-long organisation name reaches the user as an
opaque 500. **The duplicate-account check is case-sensitive against an address the same code
force-lower-cases** (K-2), so approval can mint a second tenant and a second login for a person who
already has an account. **A tenant-code collision is a dead end** (K-5) -- the endpoint accepts the
parameter that would resolve it and the screen never sends it. **Every welcome email links to
`http://localhost:4400`** (K-6), because `app.console.url` is set in no properties file, no compose
file and no `.env`, anywhere in the repository. And the decision: the console tells a stranger the
emailed password "works once", while nothing on the server enforces that (K-8).

Everything else -- the neutral acknowledgement, the mail-failure branch that refuses to report a
clean success, the reject dialog that exists because a plain confirm left `decision_note` null on
every row, the status palette entries added so three outcomes are not three greys -- is already right
and should be left alone.

---

## 2. Gap table

| # | Current | Expected | Gap | Solution | Size | Risk |
|---|---|---|---|---|---|---|
| 1 | Zero tests on either side. The only assertion touching the feature is `auth.guard.spec.ts:139` | The three `@PreAuthorize`s, the `permitAll`, the neutral acknowledgement and the approve transaction each fail a test when removed | The feature's whole authorization is three annotations nothing pins (K-12) | `TenantRequestE2EIT` + `tenant-requests.spec.ts` + `request-workspace.spec.ts` (§3.1) | **M** | Low |
| 2 | `POST submit` is anonymous, unthrottled, uncapped per IP and per address | An anonymous write is bounded | The one open door in the application has no doorstop (K-3) | A per-path rate-limit filter over the Redis already in the stack (§3.2) | **M** | Medium |
| 3 | No `maxlength` client-side, no length check server-side, `VARCHAR(255)` columns | Over-length input is refused with a message naming the limit | An HTTP 500 for something the user could fix (K-4) | Four constants, four `maxlength` attributes, four checks (§3.3) | **S** | Low |
| 4 | `submit`/`approve` look up a lower-cased address; `addUser` stores usernames as typed against a case-sensitive unique index | One person, one account | Approval can create a second tenant and a second login for an existing user (K-2) | Case-insensitive lookup now; the global fold deferred to `tenants-and-users` (§3.4) | **M** | **High** |
| 5 | `approve` accepts `tenantCode`; the screen never sends it | A collision is resolvable where it happens | "Tenant code already in use" with nothing to do about it (K-5) | Replace `confirmWith` with a small dialog carrying the derived code (§3.5) | **S** | Low |
| 6 | `must_change_password` is enforced only by `passwordChangeGuard` in the browser | The emailed credential is spent on first use, or the product stops saying it is | A full-power `TENANT_ADMIN` token that never expires its one-time password (K-8) | Server-side allow-list for a flagged account (§3.6) | **M** | **High** |
| 7 | `app.console.url` is defined nowhere; the fallback is `http://localhost:4400` | The one email carrying a credential links to the real console | The recipient is sent to their own laptop (K-6) | Set the property in three profiles, compose and `.env.example` (§3.7) | **S** | Low |
| 8 | `submit` does check-then-insert against a partial unique index, unwrapped | A double click never produces a 500 | The single path where the uniform acknowledgement is not uniform (K-9) | Catch `DataIntegrityViolationException` and return the acknowledgement (§3.8) | **S** | Low |
| 9 | `listRequests` returns every request ever made, unpaged | The wire cost is bounded | Fine at ten rows, wrong at ten thousand (K-1) | **Deferred** -- see §5 and Q6 | M | Low |
| 10 | Nothing is raised when a request arrives or is decided; Discovery claims otherwise | A platform admin learns of a waiting request without polling a screen | `WR -.-> ACCT` is drawn and not implemented (K-16) | One `NotificationType` member and one `create` call (§3.9) | **S** | Low |
| 11 | Expanded row prints an empty "What they asked for"; `createdTenantId` fetched and never rendered; `RejectDialog.saving` dead; a lost credential is a green toast | The screen says what happened | Four small wrongs on one screen (K-10, K-11) | Four edits in two files (§3.10) | **S** | Low |
| 12 | No FKs on the three pointer columns; `status` a free string; `ix_tenant_request_status` serves no query | The schema matches the rest of the database | V21 predates nothing and was skipped by V12-V14's FK work (K-14) | One changeset (§3.11) | **S** | Low |
| 13 | Two different `normali[sz]eCode` implementations for one concept | "Acme Corp." has one answer | The collision check compares against a value the other rule produced (K-15) | One shared helper plus a test | **S** | Medium |
| 14 | `GENERATED_PASSWORD_LENGTH`, `PASSWORD_ALPHABET` and `random` declared and unread beside the live path | No second copy of a security constant | The drift `TemporaryPassword` was extracted to prevent (K-7) | Delete three fields and two imports | **S** | Low |
| 15 | `request-workspace` has no `canMatch`; the acknowledgement is not announced or focused | The public page follows the file's own pattern and is usable without sight | K-13 and the missing `role="status"` | `canMatch: [anonymousOnly]`, `role="status"`, a focus move | **S** | Low |
| 16 | `.ai/discovery/backend.md:489` says `listRequests` lists pending requests; `features.md:422` draws a notification edge | Discovery matches the code | The feature's own index misdescribes it | Correct both lines | **S** | Low |

---

## 3. Solution detail

### 3.1 Gap 1 -- the tests, first

**Change.** Three new files.

`process/src/test/java/process/e2e/TenantRequestE2EIT.java`, extending `E2ESupport` in the shape of
`TenantLifecycleE2EIT`. `E2ESupport` has no anonymous request builder -- every helper goes through
`asUser` (`E2ESupport.java:119-138`) -- so add one `protected MockHttpServletRequestBuilder
postAnonymous(String url, String body)` beside them. The cases that matter, each with the positive
control the grooming criteria name:

| Case | Asserts |
|---|---|
| Anonymous submit succeeds | 200, `status: SUCCESS`, one row, `contact_email` lower-cased, decision columns null |
| The same address twice | Two response bodies **equal**, still one row |
| An address that already has an account | Same body again, no row created; positive control: a fresh address creates one |
| Body carrying `status`/`decidedBy`/`createdTenantId` | Stored row has the server's values |
| `adminA`, `userA`, `orphan` on each of the three admin endpoints | 403 each; positive control `platform` served each |
| Anonymous `listRequests` | 401; positive control anonymous `submit` 200 |
| Approve | Tenant + `TENANT_ADMIN` + `must_change_password`, the three pointer columns, `created_by` on both rows, and **no password anywhere in the response body** |
| Approve twice | Second refused, nothing created |
| Approve with a colliding code | Refused; then succeeds with an explicit `tenantCode` |
| Reject with and without a note | `decision_note` set / null; a second reject refused |

Note for whoever writes it: `application-e2e.properties:45-46` points mail at `localhost:1025`, which
is not running, so `sendTenantWelcomeEmail` returns `"Error while Sending Mail"` and approve takes
its mail-failure branch. Assert on the created rows and on `status: SUCCESS`, not on the message
string -- or assert the mail-failure message deliberately, which is the more useful test since that
branch is otherwise never exercised.

Frontend: `tenant-requests.spec.ts` and `request-workspace.spec.ts` with `TestBed` and
`HttpTestingController`, in the shape of `features/admin/storage/storage-connections.spec.ts`. The
queue spec covers load, the `status: ERROR` envelope, the HTTP error path, the filters and the
"0 of N" heading, and both decision calls including the parameters actually sent. The form spec
covers the invalid submit (no request issued), the success card carrying the server's sentence, and
the server-refusal path.

**Why first, and why this shape.** Every other change in this document edits a file that nothing
tests. Writing the E2E suite first means the refactors in §3.4 and §3.6 -- the two with real blast
radius -- are made against a net rather than into one.

*Rejected: unit tests over `TenantRequestServiceImpl` with mocked repositories.* They would pass with
every `@PreAuthorize` deleted, because method security is not in the unit path. The thing most worth
pinning here is exactly the thing a mocked unit test cannot see. The E2E harness runs the real
filter chain, which is why `TenantLifecycleE2EIT` is the right template.

*Rejected: waiting until the other gaps are fixed and testing the end state.* The `permitAll` on
`submit` is a whole-feature outage if it regresses, and it can regress today, before any of this
work lands.

### 3.2 Gap 2 -- rate-limit the one anonymous write

**Change.** A `OncePerRequestFilter` registered for `POST /tenantRequest.json/submit` only, placed
before `JwtAuthenticationFilter`, backed by the Redis already in the stack. Two counters: per client
IP and per normalised address, both with a short window. Over the limit, return the **same
acknowledgement envelope** the service returns -- not 429, and not an error.

**Why the same envelope.** The whole point of `TenantRequestServiceImpl.java:81-85` is that this
endpoint tells a caller nothing about what it did. A 429 reintroduces exactly the signal the uniform
acknowledgement removes: it says "this address is interesting". The rate limiter has to inherit the
endpoint's discretion.

*Rejected: a CAPTCHA.* It puts a third-party script and a network dependency on the one page a
stranger's first impression is formed on, and it does nothing about a caller that scripts the API
directly, which is the case that matters.

*Rejected: a generic rate-limiting library across all endpoints.* There is no rate limiting anywhere
in the application today (verified: no `bucket4j`, no `ratelimit`, nothing in `pom.xml`), and
introducing one across 181 endpoints is a platform decision, not this feature's. A narrow filter on
one path, written so its counter store can be lifted out later, is the right size. Say so in its
javadoc, so the next person extending it does not have to guess.

*Rejected: relying on the partial unique index.* It bounds repeats of one address; it does nothing
about a script that varies the local part, which is the actual attack.

### 3.3 Gap 3 -- bound the fields

**Change.** In `TenantRequestServiceImpl`: constants `MAX_NAME = 255`, `MAX_EMAIL = 255`,
`MAX_PURPOSE = 4000`, checked after the blank checks at `:90-99`, each returning a message naming the
limit ("Keep the organisation name under 255 characters."). In `request-workspace.ts:66-88`: a
`maxlength` on each of the four controls matching those numbers, plus `autocomplete="name"` and
`autocomplete="email"`.

**Why both sides rather than one.** Client-only would be a finding in its own right -- the API is
reachable without the form. Server-only would let someone type 400 characters into a box that
accepts them and be refused on submit. The `maxlength` is a courtesy; the service check is the rule.

*Rejected: `@Size` bean validation on the entity.* The controller takes the entity as its body and
the service builds a fresh instance field by field (`:111-118`), so annotation-driven validation
would fire on the wrong object at the wrong time, and a violation would surface as a framework
exception rather than as one of this service's own sentences. The explicit checks match the four
that are already there and read the same way.

*Rejected: capping `purpose` at 255 to match the others.* It is the field the decision rests on, and
`TEXT` was chosen for it deliberately (`V21__tenant_request.sql:14-15`). 4,000 characters is roughly
two pages -- generous for a paragraph, and small enough that a million rows is megabytes rather than
gigabytes.

### 3.4 Gap 4 -- one person, one account

**Change, narrow.** In `TenantRequestServiceImpl`, replace both
`appUserRepository.findByUsernameAndStatusNot(email, Status.Delete)` calls (`:107` and `:157-158`)
with a case-insensitive lookup -- a new
`findByUsernameIgnoreCaseAndStatusNot` on `AppUserRepository`, which Spring Data derives from the
method name with no query to write. That alone closes the path where approval creates a second tenant
and a second login for somebody who already has an account.

**Why not fix it properly here.** The proper fix is one case-folding rule across the whole product: a
migration folding existing `app_user.username` values, a functional unique index (or `citext`) so the
database enforces it, and the same normalisation in `addUser` (`AppUserServiceImpl.java:180-192`) and
in `login` (`AuthServiceImpl.java:52-53`). That is `tenants-and-users` work: it touches the login
path for every existing account, and if two rows already differ only by case the migration has to
decide which one wins -- a question this feature cannot answer.

So: the case-insensitive **check** lands here, because it is two lines and it closes a
duplicate-creation path; the case-insensitive **identity** is handed to feature 16 with this
paragraph as the reason. Record the residual: until the fold happens, `Ivar@X.com` and `ivar@x.com`
remain two valid logins if they already exist, and this change merely stops the workspace-request
path from creating more of them.

*Rejected: lower-casing on the way in at `addUser` only.* It fixes new rows and leaves the existing
ones inconsistent, which is the worst of both -- the check would then be right for accounts created
after the change and wrong for accounts created before it, with nothing on screen to say which is
which.

### 3.5 Gap 5 -- an editable tenant code

**Change.** Replace the `confirmWith` call at `tenant-requests.ts:196-203` with an `ApproveDialog` in
the shape of `RejectDialog` (`reject-dialog.ts`): the same `FormDialog` chrome, a single text field
prefilled with the code the server would derive, normalised live as it is typed, closing with the
string or `null`. Pass the result as the `tenantCode` parameter the endpoint has accepted since it
was written (`TenantRequestRestApi.java:73-74`). The dialog keeps the sentence the confirm has today
about what approval creates and about the one-time password.

The derived default has to be computed client-side, which means the normalisation rule exists in two
languages. That is acceptable only because gap 13 collapses the two **server** copies into one; the
client's copy is a preview of a value the server recomputes and remains authoritative over. Say that
in the dialog's header.

*Rejected: auto-suffixing a colliding code (`acme-2`).* It silently invents an identifier a human
will have to live with, on a screen whose entire job is a human decision. It also hides the more
interesting case -- the collision is often with a **soft-deleted** tenant of the same name, and what
the administrator actually wants then is to reactivate that tenant, not to make a second one.

*Rejected: showing the code as read-only text in the existing confirm.* It tells the administrator
what is about to happen and still leaves them nothing to do when it is wrong.

### 3.6 Gap 6 -- make "works once" true, or stop saying it

**Recommended: enforce it on the server.** In `JwtAuthenticationFilter`, or in a small filter beside
it, refuse any request from a principal whose account carries `must_change_password` unless the path
is `POST /appUser.json/changeOwnPassword`, `GET /appUser.json/me` or `/auth.json/**`. Return the
403 envelope `GlobalExceptionHandler` already produces, with a message naming the reason.

**Why this is worth the cost.** Everywhere else the console's guard is a convenience over a server
rule. Here it is the *only* rule, and the credential it fails to bound was mailed to somebody the
platform has never verified -- the whole premise of the feature is that the contents of a request are
a claim. `features/docs/docs.ts:286-289` tells that person the emailed password stops working; today
it does not, at the API, ever.

The cost is real and has to be acknowledged: the filter needs the flag, and the flag is not on the
token (`AuthResponseDto` carries it, the JWT claims do not). Reading `app_user` per request would
undo the deliberate no-per-request-user-read design that `.ai/discovery/risks.md:60` already flags as
a trade-off. So put `mcp` on the access token as a claim, set at issue in
`AuthServiceImpl.buildAuthResponse`, and accept that clearing the debt requires a token refresh --
which `changeOwnPassword` can trigger, and which the interceptor already has plumbing for
(`core/auth/auth.interceptor.ts:62-64`).

*Rejected: doing nothing and correcting the documentation.* Cheaper, honest, and leaves a mailed
`TENANT_ADMIN` credential valid indefinitely. It also makes the docs worse rather than better: "you
will be asked to change this, but the old one keeps working" is not a sentence anybody wants to
write.

*Rejected: expiring the generated password after N hours.* It needs a new column, a new sweep, and it
converts a lost welcome email from an inconvenience into a dead account. The reset path
(`AppUserServiceImpl.java:338-359`) already covers the case this would be solving.

*Rejected: enforcing at each controller with `@PreAuthorize`.* Twenty-seven controllers, 181 methods,
and the rule would be missing from the next one somebody writes -- the same argument `AuditListener`
makes for itself (`model/pojo/AuditListener.java:10-13`).

**If Q1 is answered the other way**, the alternative is one line of documentation and one line in
the reject dialog's sibling text, and this row drops to **S**.

### 3.7 Gap 7 -- configure `app.console.url`

**Change.** `app.console.url=${APP_CONSOLE_URL}` in `application-dev.properties`,
`application-stage.properties` and `application-prod.properties`; `APP_CONSOLE_URL` in
`docker-compose.yml` and `.env.example`; and change the two `@Value` fallbacks
(`TenantRequestServiceImpl.java:68`, `AppUserServiceImpl.java:71`) from `http://localhost:4400` to a
value that cannot be mistaken for a working console, so a missing configuration is visible in the
first test mail rather than three months later.

*Rejected: deriving the URL from the incoming request's `Host` header.* The request that triggers the
mail is the platform admin's, from wherever they happen to be, and the header is attacker-controlled
on the one endpoint in this feature that anonymous callers can reach. A configured value is the only
safe source.

### 3.8 Gap 8 -- the double-click 500

**Change.** Wrap the `save` at `TenantRequestServiceImpl.java:118` in a try/catch for
`DataIntegrityViolationException` and return the acknowledgement. The row the other request created
is exactly the row this one was going to create, so returning success is not a lie -- it is the same
answer the check at `:106` would have given a moment later.

*Rejected: making `submit` `@Transactional` with a serializable isolation level.* It converts a rare
500 into a rare lock wait on the one endpoint an anonymous caller can hit at will, which is a worse
trade in exactly the scenario gap 2 is about.

### 3.9 Gap 10 -- tell somebody a request arrived

**Change.** Add `TENANT_REQUEST_SUBMITTED` to `NotificationType`
(`model/enums/NotificationType.java:7-8`) and one `notificationCenterService.create(...)` call at the
end of `submit`'s creating branch, addressed to platform administrators, with `linkUrl` of
`/admin/tenant-requests`. `NotificationCenterService.create` already takes exactly the arguments
needed (`model/service/NotificationCenterService.java:12-13`).

One wrinkle to settle in code review: `create` takes a single `recipientUserId`, and the audience
here is "every platform admin". Either loop the platform admins, or pass `null` for tenant and
recipient and let the notification screen treat an unaddressed platform notification as broadcast --
whichever matches what `own-account-and-notifications` decides. Do not invent a third convention here.

*Rejected: emailing platform admins.* The console has a notification centre and a bell; adding a
second channel for one event is how a product ends up with two half-working ones.

*Rejected: notifying on approval and rejection too.* The person who took the decision is the person
who would be told. The applicant is the party who might want to know, and telling them is Q3.

### 3.10 Gap 11 -- the four small ones

All four are single edits:

- `tenant-requests.html:305-309`: wrap the "What they asked for" block in `@if (r.purpose)` with the
  same italic fallback the card uses at `:130-134`.
- `tenant-requests.html`, the card footer and the table's decided cell: when `r.createdTenantId` is
  set, render a `routerLink` to `/admin/tenants` carrying the id.
- `reject-dialog.ts:41`: delete `saving`, and drop `[saving]` from the `FormDialog` binding at `:26`.
  The dialog closes before the POST is issued, so the signal can never be true.
- `tenant-requests.ts:245`: a partly-successful approval must not be a green toast. `ToastService`
  already has the tone -- `warn(message)` at `shared/ui/toast.service.ts:22` -- so nothing new is
  needed on the client. What *is* needed is a way to tell the two successes apart without matching on
  prose: have `approve` return a distinguishable marker (a boolean on the envelope's `data`, or a
  third status value) rather than have the client regex the message. Matching on message text is how
  a copy edit becomes a defect.

### 3.11 Gap 12 -- the schema changeset

One new changeset, `V26.0-tenant-request-constraints`, in the established shape: FKs on `decided_by`
-> `app_user`, `created_tenant_id` -> `tenant`, `created_user_id` -> `app_user`, all `ON DELETE SET
NULL`; a check constraint on `status` for the three values; and `DROP INDEX IF EXISTS
ix_tenant_request_status`. If gap 9 is ever taken up, the index comes back with the query that needs
it -- that is a better reason to have it than the one it has now.

*Rejected: making `status` a JPA enum.* It changes the column's storage and would need a data
migration for a table that already has rows, to buy type safety over three string literals that a
check constraint pins just as well.

---

## 4. Ordering

**First, gap 1 -- the tests.** Everything else edits code with no coverage. In particular the two
tests that pin the `permitAll()` on `submit` and the three `hasRole` annotations should land before
any refactor touches `TenantRequestRestApi`, because those are the regressions with the largest blast
radius and the smallest chance of being noticed.

**Then the two that need no decision:** gap 7 (`app.console.url`) and gap 3 (lengths). Both are
small, both are independent, and gap 3 removes a class of 500 that would otherwise show up as noise
while the rest of the work is being tested.

**Then gap 4 (case-insensitive check) and gap 8 (the duplicate-submit 500).** Both are inside
`TenantRequestServiceImpl` and both are covered by tests written in step one. Gap 4 hands its
residual to `tenants-and-users`; do not wait for that feature.

**Then gap 2 (rate limiting).** It is the largest piece with no external dependency, and it must land
before this endpoint is exposed to anything but a developer's machine. It unblocks nothing, but
nothing about the public form should be considered finished without it.

**Then gap 5 (the approve dialog) with gap 13 (the shared normaliser)**, in that order -- the dialog
previews what the normaliser produces, so consolidating the server's two copies first means the
preview has one thing to mirror.

**Then the small screen fixes:** gaps 11, 15, 14, 16. These are safe to batch.

**Gap 6 is on its own track**, because it is blocked on Q1 and because its blast radius is every
authenticated request in the product, not this feature. It also unblocks nothing here: approval works
either way. If Q1 says enforce, it should be scheduled with `authentication-and-access` rather than
squeezed in beside a screen fix.

**Gap 10 (notifications)** waits on `own-account-and-notifications` settling the broadcast
convention. Gap 9 is deferred outright (§5).

---

## 5. Out of scope

**Server-side paging on `listRequests` (gap 9).** The endpoint returns the full history and the
screen pages it client-side. The shape is wrong and the cost today is nil: this is a table that grows
by the number of organisations that ask for a workspace, which is a human-scale number for a long
time. Changing it means a `Pageable` on the repository, counts returned alongside so the four tiles
stay honest, and switching `createPager` from client to server mode -- work with a real chance of
breaking the tiles, for no present benefit. Recorded with a trigger instead: revisit when
`tenant_request` passes roughly two thousand rows, or as soon as gap 2's rate limiter reports it is
actually stopping anything.

**The global username case fold.** §3.4 explains why the check lands here and the identity does not.
It belongs to `tenants-and-users`, which owns `addUser`, and to `authentication-and-access`, which
owns the login lookup.

**A service interface for `TenantRequestServiceImpl`.** The controller depends on the concrete class,
against the convention every other controller follows. It is a pure rename with no behavioural
content, and doing it in the same pass as the substantive changes above would make every one of those
diffs harder to read. Worth doing the next time the file is opened for another reason.

**Attaching an approved workspace to an existing account.** Today, approving a request whose address
already has an account is refused, and the administrator has to use `admin/tenants` and `admin/users`
by hand. Making approval able to promote an existing account to `TENANT_ADMIN` of a new tenant is a
larger product question about whether one person may administer two workspaces, and nothing in the
current model answers it. Left alone deliberately.

**Anything about `must_change_password` other than gap 6.** The column is shared with two other
features and its other uses -- the seeded platform admin, `addUser`'s generated passwords,
`resetPassword` -- are theirs to groom.

---

## 6. Open questions

**Q1. Is the one-time password enforced on the server, or does the product stop calling it one-time?**
The console pins a flagged session to `/profile`; the API does not care. Options: (a) enforce with a
token claim and a narrow allow-list (§3.6); (b) leave it and correct `docs.ts:286-289` and the approve
dialog's wording. **Recommendation: (a).** This credential is mailed to somebody the platform has
explicitly not verified -- that is the premise of the whole feature -- and it currently grants
unbounded `TENANT_ADMIN` access to an entire tenant for as long as nobody changes it. (b) is a
half-hour of work and makes the product honestly worse. Schedule (a) with
`authentication-and-access`, since the change is in the filter that feature owns.

**Q2. Case folding: check-only now, or the full fold in this pass?** **Recommendation: check-only
now** (§3.4). It is two lines, it closes the path where approval creates a duplicate person, and it
carries no migration risk. The full fold needs a decision about existing rows that differ only by
case, which is `tenants-and-users`' to make. If that feature is being groomed soon, hand it this
paragraph rather than waiting.

**Q3. Is a rejected applicant told?** Today nothing is sent, and `reject-dialog.ts:18` states that as
a design choice. **Recommendation: keep the silence, and record it as a decision rather than leaving
it as an absence.** A rejection email goes to an address nobody has verified, on the strength of a
form anybody can fill in with anybody's address -- so an automatic rejection notice is a message the
platform sends to a stranger about a request they may never have made. The note stays internal, which
is what the dialog already promises the administrator. Add one sentence to `docs.ts`'s request step
saying an unanswered request means no, so the applicant is not left waiting for a message that will
never come.

**Q4. Narrow rate limiter now, or a platform-wide one?** **Recommendation: narrow, on this path,
written to be lifted.** There is no rate limiting anywhere in the application; introducing a general
mechanism is a platform decision with 181 endpoints downstream of it, and this feature should not be
the one that makes it by accident. A single filter with its counter store behind a small interface
gives the platform decision somewhere to land later, and closes today's hole now.

**Q5. What is the cap on `purpose`?** **Recommendation: 4,000 characters**, enforced server-side with
the column left as `TEXT`. Two pages is generous for the paragraph the field asks for, and it bounds
what an anonymous caller can write per row -- which is the point, given gap 2.

**Q6. When does `listRequests` need paging?** **Recommendation: not now** (§5), revisited at roughly
two thousand rows or the first time the rate limiter fires in anger. Note it in the endpoint's javadoc
so the next reader knows the omission was deliberate rather than overlooked.

**Q7. Where does a broadcast notification to "all platform admins" belong?**
`NotificationCenterService.create` takes one `recipientUserId`. Gap 10 needs either a loop over
platform admins or a null-recipient broadcast convention. **Recommendation: defer gap 10 until
`own-account-and-notifications` is groomed and settles this**, and take whichever convention that
document lands on. Inventing a third pattern here to save a week costs more than the week.
