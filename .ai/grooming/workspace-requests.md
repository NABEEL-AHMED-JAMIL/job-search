# Grooming -- Workspace Requests

Feature `workspace-requests`, row 17 of [../discovery/features.md](../discovery/features.md).
Status **new**: the old application has no counterpart, so this document is about whether what
shipped is **complete and correct**, not about parity. Where it is hard on missing states, missing
authorization and missing tests, that is the point.

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. Purpose

Somebody outside the platform wants a workspace. They have no account -- that is what they are
asking for -- so there is nowhere for them to sign in and ask. This feature is the front door:

> *Tell us who you are and what you need it for. A platform administrator reviews every request; if
> yours is granted, we will email you how to sign in.*
> -- `scheduler1/next/src/app/features/tenant-request/request-workspace.ts:57-60`

And, from the other side of the door, the setup guide's own summary:

> *If you do not have a workspace yet, request one. A platform administrator reviews every request;
> nothing is created until somebody agrees to it.*
> -- `scheduler1/next/src/app/features/docs/docs.ts:276-277`

Two things follow from "nothing is created until somebody agrees to it", and both are design rather
than accident.

**A request is a claim, not a fact.** It arrives from an unauthenticated form, so every word in it
is unverified. The server therefore stores a row and does nothing else -- no tenant, no account, no
mail. `TenantRequest`'s own header says so
(`process/src/main/java/process/model/pojo/TenantRequest.java:12-19`), and so does the migration
that created the table (`process/src/main/resources/db/changelog/changelog-sets/V21.0-tenant-request/V21__tenant_request.sql:1-6`).

**The form must not answer "does this person have an account here?"** A sign-up form that says "you
already have one" is a free account-enumeration oracle for anybody who asks. The acknowledgement is
identical whether the address is new, already has an open request, or already belongs to a user
(`process/src/main/java/process/model/service/impl/TenantRequestServiceImpl.java:81-85, 101-109`).

The platform administrator's side is a queue at `/admin/tenant-requests`: read what was written,
approve -- which creates the tenant, its first `TENANT_ADMIN` and that account's one-time password
-- or reject with a note that stays inside the platform.

---

## 2. Existing behaviour

### 2.1 The old application has none of this

Verified, not inferred:

| Check | Result |
|---|---|
| `grep -ril tenantRequest scheduler1/src` | zero files |
| `grep -rli "signup\|register\|request-workspace" scheduler1/src/app` | one file, `app.component.ts:12`, which is `echarts.registerTheme` |
| Routes in `scheduler1/src/app/app.routing.ts` | 42, none of them a public request or an admin queue |

There is no old-app half of this feature. Everything below is `scheduler1/next` plus the backend.

### 2.2 The public form -- `/request-workspace`

`scheduler1/next/src/app/features/tenant-request/request-workspace.ts`, 161 lines, one standalone
component with its template inline. Routed at `app.routes.ts:28-33`, outside the shell, with **no
guard at all** -- not `authGuard`, and not the `anonymousOnly` that `login` (`:12`) and the landing
page (`:25`) carry.

It draws its own page chrome because it sits outside the shell: a header with the product mark, a
theme toggle and a "Sign in" button (`:26-41`), and a footer linking back to the front page and to
the setup guide (`:110-115`).

**The form** (`:130-135`) is four reactive controls:

| Control | Validators | Rendered as |
|---|---|---|
| `organisationName` | `required` | text input, hint "The name your workspace will carry." (`:63-68`) |
| `contactName` | `required` | text input (`:71-74`) |
| `contactEmail` | `required`, `email` | `type="email"`, hint "Where the sign-in details will be sent, and your username.", custom message override for `email` (`:76-81`) |
| `purpose` | none | 4-row textarea (`:84-88`) |

All four go through the shared `Field` wrapper (`shared/ui/field.ts`), which owns the label, the
required marker, the hint and the error line, and withholds a message until the control is touched
or the form has been submitted (`field.ts:65-85`).

**Submit** (`:137-160`): sets `submitted`, clears `error`; if the form is invalid it marks
everything touched and sets `error` to "Check the highlighted fields." and returns; otherwise it
POSTs `form.getRawValue()` to `${API_BASE}/tenantRequest.json/submit`. On a non-`SUCCESS` envelope
it puts the server's own message into the same red line under the form (`:150`). On success it
stores the server's message and flips `done`, which replaces the whole form with an acknowledgement
card (`:44-54`) carrying a tick, the heading "Thank you -- your request has been recorded", the
server's sentence, and a link back to the front page.

The one entry point into it is the landing page's hero
(`features/landing/landing.ts:101` -- `Request a workspace`, beside Sign in), plus the docs step
that describes it (`features/docs/docs.ts:274-295`).

### 2.3 `POST /tenantRequest.json/submit` -- the only anonymous write in the feature

Controller: `process/src/main/java/process/api/TenantRequestRestApi.java:49-58`. The class carries
**no class-level `@PreAuthorize`**, deliberately, and its javadoc explains why (`:41-48`): adding
the class-level annotation the rest of the codebase uses would replace the method-level one and
silently close sign-up. `SecurityConfig.java:47` says the same thing in the URL layer, and says it
for `POST` only.

The service (`TenantRequestServiceImpl.java:86-120`) does, in order:

1. Null body -> `ERROR "Nothing to submit."`
2. Blank organisation -> `ERROR "Tell us the name of your organisation."`
3. Blank contact name -> `ERROR "Tell us your name."`
4. Email trimmed and **lower-cased** (`:96`), then matched against
   `^[^@\s]+@[^@\s.]+\.[^@\s]+$` (`:51`); failure -> `ERROR "That does not look like an email
   address."`
5. If `findOpenByEmail` finds a Pending row for that address, **or** `findByUsernameAndStatusNot`
   finds a non-deleted account, return `SUCCESS` with the acknowledgement and create nothing
   (`:106-109`).
6. Otherwise build a **fresh** `TenantRequest` copying exactly four fields -- organisation, contact
   name, lower-cased email, purpose -- force `status = "Pending"`, stamp `dateCreated`, save
   (`:111-118`).

Step 6 is worth naming: the endpoint takes the whole `TenantRequest` entity as its body
(`TenantRequestRestApi.java:51`), and a caller can therefore post `status`, `decidedBy`,
`createdTenantId`, `createdUserId` or `tenantRequestId`. None of them is read. Mass assignment is
closed by construction rather than by a DTO.

The acknowledgement is one string literal defined once (`:101-102`) and returned from both the
"nothing created" branch and the "row created" branch, which is what makes the two indistinguishable
to a caller.

### 2.4 The queue -- `/admin/tenant-requests`

`features/tenant-request/tenant-requests.ts` (277 lines) + `tenant-requests.html` (350 lines).
Routed at `app.routes.ts:198-204` with `data: { minRole: 'PLATFORM_ADMIN' }` and
`canActivate: [roleGuard]`. Linked from the shell's Administration group with `platformOnly: true`
(`features/shell/shell.ts:133-134`), whose comment records that a tenant admin shown this link "was
walked straight into the unauthorized page".

**Load** (`tenant-requests.ts:178-193`): a single `GET listRequests` on init, into `requests`,
`loading` and `error` signals. Refresh button in the page head (`tenant-requests.html:10-12`).

**Four stat tiles** (`tenant-requests.html:15-25`) from a computed summary
(`tenant-requests.ts:166-174`): Waiting / Approved / Rejected / Total.

**Chrome** is the shared `TableShell` (`shared/ui/data-table.ts`), which supplies the loading
spinner, the error card with a "Try again" button, and the empty card, all from
`data-table.ts:42-67`. The empty message is filter-aware
(`tenant-requests.html:32-34`): "No request matches those filters." when a filter is on, otherwise
"No requests yet. The form at /request-workspace feeds this list."

**Toolbar** (`:36-57`): a table/cards `ViewToggle` keyed `tenant-requests` (persisted per screen in
`localStorage` under `etl.view.`, `shared/ui/view-toggle.ts:6,46-60`), a free-text search, a status
`<select>` whose Pending option is labelled **Waiting**, and a Clear button that appears only when a
filter is set.

**Filtering and sorting** (`tenant-requests.ts:80-93`): the search runs over organisation, contact
name, email **and purpose** -- the comment at `:86-87` explains that purpose is included because it
is what the decision rests on. Sorting uses the shared `createSort` with `dateCreated`/`desc` as the
default (`:77`), and the Status column sorts by a hand-written urgency order
(`STATUS_ORDER`, `:277`) so one click brings Pending to the top rather than Approved. Paging is the
shared `createPager` (`:78`, `:98-101`), 50 rows a page.

**Cards is the default view** (`:69`), unlike every other admin screen, with the reason stated at
`:62-68`: a request is read before it is compared, and a table cell can only show the first two
lines of the paragraph the decision rests on.

*Card* (`tenant-requests.html:60-177`): a status-coloured top rule (`statusAccent`,
`tenant-requests.ts:142-150` -- amber for Pending, green for Approved, and deliberately **not** red
for Rejected), organisation heading, status chip, contact name, a `mailto:` address with an
always-visible copy button (`:97-108`, with the reasoning at `:94-96` that a hover-only control is
unreachable by keyboard and invisible on touch), an "Asked for" panel that clamps to four lines with
a "Read all" toggle for long text (`isLong`, `tenant-requests.ts:137-139`), a "Reason given" block
for rejected rows, a footer with received and decided dates, and the two decision buttons on Pending
rows only.

*Table* (`:179-343`): sortable Organisation, Contact, Received and Status columns; an "Asked for"
column deliberately left unsortable (`:183-185`); a chevron column that expands a full-width detail
row (`:301-340`) carrying the whole purpose, contact, email, decided timestamp and reason; and a
right-pinned Actions column.

**Copy feedback** (`tenant-requests.ts:152-164`): the copied address's tick clears after 1.5 s, and
only if nothing else has been copied since.

### 2.5 Approve

Client (`tenant-requests.ts:195-207`): a `confirmWith` dialog titled "Create a workspace for
`{organisation}`?" whose body states that this creates the tenant, makes the contact address its
first administrator, and that they are emailed a password that works once. On confirm it POSTs
`approve` with **only** `tenantRequestId` -- the optional `tenantCode` parameter the endpoint
accepts is never sent.

Server (`TenantRequestServiceImpl.java:133-209`, `@Transactional`):

| Step | Line | Behaviour |
|---|---|---|
| Missing id | :135-137 | `ERROR "Request id missing."` |
| Unknown id | :138-141 | `ERROR "Request not found with %d."` |
| Already decided | :143-146 | `ERROR "This request was already approved/rejected."` |
| Derive the code | :148 | `tenantCode` if given, else the organisation name, through `normaliseCode` (`:233-237`): lower case, runs of non-alphanumerics collapsed to one hyphen, ends stripped |
| Empty code | :149-151 | `ERROR "Give the tenant a code."` |
| Code taken | :152-154 | `ERROR "Tenant code \"%s\" is already in use."` |
| Address taken | :157-161 | Re-checked here rather than trusting submission -- an account may have appeared in between. `ERROR "There is already an account for %s."` |
| Create the tenant | :163-169 | New uuid, `tenantName` = organisation name, code, `TenantStatus.Active` |
| Create the admin | :171-182 | New uuid, the new `tenantId`, username = the request's email, full name = contact name, `UserRole.TENANT_ADMIN`, `Status.Active`, bcrypt of `TemporaryPassword.generate()`, **`mustChangePassword = true`** |
| Close the request | :184-189 | `Approved`, `decidedAt`, `decidedBy = TenantContext.getAppUserId()`, `createdTenantId`, `createdUserId` |
| Mail | :191-193 | `sendTenantWelcomeEmail(email, name, tenantName, username, temporaryPassword, consoleUrl + "/login")` |
| Mail failed | :195-205 | Still `SUCCESS`, with a different message: the tenant exists, the credential did not arrive, reset it by hand |
| Done | :206-208 | `SUCCESS "Tenant \"%s\" created. %s has been emailed how to sign in."` |

Both created rows pick up `created_by` = the approving platform admin, through
`AuditListener.onCreate` (`model/pojo/AuditListener.java:23-39`), whose comment at `:33-38` names
this exact case.

**The password never leaves the server in a readable form except in the mail.** It is generated at
`:171`, bcrypt-hashed at `:179`, passed once to the mailer at `:193`, and appears in no
`ResponseDto` on any branch. `EmailMessagesFactory.sendTenantWelcomeEmail` (`:115-136`) refuses to
log the exception message on failure because a mail failure can echo the body (`:131-133`), and
`safeToLog` (`:216-228`) masks any body key containing "password" before the success line at `:194`.
The template is `resources/templates/tenant_welcome.vm`, tables-and-inline-styles for Outlook, with
sign-in URL, username and one-time password.

### 2.6 Reject

Client: a purpose-built dialog rather than a yes/no confirm
(`features/tenant-request/reject-dialog.ts`). Its header records why (`:7-19`): a plain confirm was
used before, which is how `decision_note` came to be a column, an endpoint parameter and a display
that nothing ever filled. The dialog closes with the trimmed string, or `null` when cancelled
(`:44-48`), so the caller cannot forget to read it (`tenant-requests.ts:214-218`). The reason is
optional by design, and the dialog says the note is visible only to platform administrators and that
no mail is sent.

Server (`TenantRequestServiceImpl.java:211-230`): same id and already-decided guards, then
`Rejected`, `decidedAt`, `decidedBy`, `decisionNote` (blank -> null). No mail, no notification.

Both decisions share one client method (`decide`, `tenant-requests.ts:237-256`): mark the row busy,
POST, clear busy, toast **the server's own message** -- because approve can partly succeed and only
the server knows which happened (`:232-235`) -- and reload on success.

### 2.7 What happens to the person who was approved

The emailed password is a debt, not a password. `AuthServiceImpl.buildAuthResponse` puts
`mustChangePassword` on the login response (`:132`), `passwordChangeGuard` pins any session carrying
it to `/profile` (`core/auth/auth.guard.ts:59-67`), and `changeOwnPassword` clears the flag
(`AppUserServiceImpl.java:627-629`) with the interceptor noticing the success envelope and telling
`AuthService` (`core/auth/auth.interceptor.ts:62-64`). Sign-in itself is not blocked. The recovery
path when the mail never arrives is `appUser.json/resetPassword`, which sets the flag again
(`AppUserServiceImpl.java:352-357`).

### 2.8 What is stored

`tenant_request`, created by `V21.0-tenant-request` (`V21__tenant_request.sql`), mapped by
`TenantRequest.java`. Eleven columns, one sequence starting at 1000, two indexes. No `tenant_id` --
this is a platform-owned table, and correctly so. Section 6 has the full column list.

### 2.9 Tests

**There are none.** Stated plainly because it is the single largest finding in this document.

| Suite | Search | Result |
|---|---|---|
| Frontend | 31 `*.spec.ts` under `scheduler1/next/src`; any importing `TenantRequests`, `RequestWorkspace` or `RejectDialog` | **zero** |
| Backend unit | `grep -rl "TenantRequest\|tenantRequest" process/src/test` | **zero** |
| Backend E2E | `process/src/test/java/process/e2e/` -- eight classes, including `TenantLifecycleE2EIT` and `UserManagementE2EIT` | **no** `TenantRequest*E2EIT` |

The only assertion in the repository that touches the feature is
`core/auth/auth.guard.spec.ts:139`, which pins `admin/tenant-requests` to `PLATFORM_ADMIN` in the
route table. Nothing tests the endpoints, the service, the neutral acknowledgement, the approve
transaction, the already-decided guards, or either screen.

---

## 3. Expected behaviour

Most of section 2 *is* the expected behaviour: the neutral acknowledgement, the
store-then-decide shape, the password that is never returned, the two-guard approve, the note on
rejection. Those are right and should not be touched. What follows is where today and expected part
company.

**A request is a claim, so its size must be bounded before it is stored.** Today the only checks are
blankness and email shape; `organisation_name`, `contact_name` and `contact_email` are
`VARCHAR(255)` and `purpose` is unbounded `TEXT`. A 300-character organisation name is accepted by
the browser, accepted by the service, and rejected by Postgres -- reaching the user as a generic
HTTP 500. **Expected:** explicit maximum lengths, stated on the client and enforced on the server,
with a message naming the limit.

**An open door needs a doorstop.** `POST submit` is the only anonymous write in the application and
has no rate limit, no per-address cap and no CAPTCHA. **Expected:** a per-IP and per-address rate
limit, so an anonymous caller cannot write rows without bound.

**A collision must be resolvable where it happens.** The endpoint already accepts `tenantCode`; the
screen never sends it, so when the derived code is taken the administrator is told "already in use"
and given nothing to do about it. **Expected:** the approve dialog shows the code that will be used,
lets it be edited, and re-checks.

**The duplicate-account check must match the way usernames are actually stored.** The request email
is force-lower-cased; `appUser.json/addUser` stores usernames exactly as typed
(`AppUserServiceImpl.java:180-192`) and `app_user.username` is a case-sensitive unique index
(`AppUser.java:63`). **Expected:** one case-folding rule across both paths, so approval cannot mint
a second account for a person who already has one.

**"A password that works once" must be true at the API, not only in the browser.** The console's
guard is a good user experience; it is not enforcement. **Expected:** a server-side rule that an
account carrying `must_change_password` may reach `changeOwnPassword`, `me` and `logout` and nothing
else -- or, if that is judged too large, the docs and the dialog stop claiming the password stops
working.

**The link in the one email that carries a credential must point at the real console.**
`app.console.url` is defined in no properties file, no compose file and no `.env`, so every welcome
mail links to the `@Value` default `http://localhost:4400/login`. **Expected:** the property is set
per environment, and the fallback is a value that is obviously wrong rather than plausibly wrong.

**A decision should be traceable to the thing it created.** `created_tenant_id` is stored, read into
the client's row type, and rendered nowhere. **Expected:** an approved row links to the tenant.

**The list should not grow without bound on the wire.** `listRequests` returns every request ever
made, ordered by id, unpaged; the screen pages client-side. **Expected:** server-side paging with a
status filter, keeping the client's tiles honest by returning counts alongside.

**And the feature should be covered by tests that fail when its rules are removed** -- which today
is nothing at all.

---

## 4. Frontend requirements

### 4.1 Routes

| Path | Component | Guard | Notes |
|---|---|---|---|
| `request-workspace` | `RequestWorkspace` | none today | Outside the shell. Should gain `canMatch: [anonymousOnly]` to match `login` and `''` |
| `admin/tenant-requests` | `TenantRequests` | `authGuard` (shell), `passwordChangeGuard` (shell), `roleGuard` with `minRole: 'PLATFORM_ADMIN'` | `app.routes.ts:198-204` |

### 4.2 Components

| File | What it owns |
|---|---|
| `features/tenant-request/request-workspace.ts` | The public page: header, theme toggle, form, acknowledgement card, footer |
| `features/tenant-request/tenant-requests.ts` | The queue: load, filter, sort, page, expand, copy, approve, reject |
| `features/tenant-request/tenant-requests.html` | Its two views and the detail row |
| `features/tenant-request/reject-dialog.ts` | The reason dialog |

Shared pieces the screens must keep using rather than reimplementing: `Field`, `TableShell`,
`StatTile`, `StatusPill`, `ViewToggle`, `Pagination`, `createSort`, `createPager`, `confirmWith`,
`FormDialog`, `ToastService`, `copyText`.

### 4.3 The public form

- Four controls as in 2.2, three required, with `maxlength` on all four matching the server's
  limits, and `autocomplete` on name (`name`) and email (`email`).
- Errors withheld until touched or submitted; a summary line under the form for a server-side
  refusal (`request-workspace.ts:90-95`).
- Submit disabled and labelled "Sending…" with a spinning glyph while in flight (`:98-101`).
- On success the form is replaced by the acknowledgement card carrying **the server's own sentence**,
  not a client-side copy of it -- this is what keeps the neutral wording in one place.
- **Required and missing today:** focus must move to the acknowledgement, and it must be announced
  (`role="status"` or `aria-live="polite"`). Today the submit button vanishes with focus on it and a
  screen reader is told nothing.

### 4.4 The queue

- Header with title, one-line description and a Refresh button disabled while loading.
- Four stat tiles: Waiting, Approved, Rejected, Total.
- `TableShell` supplying loading / error+retry / empty, with `shown` and `total` so a filtered-out
  list reads "0 of 12" rather than looking empty.
- Toolbar: view toggle (persisted), search across organisation, contact, email and purpose, status
  select using the console's word **Waiting** for the stored value `Pending`, Clear.
- Cards by default; both views must offer the same two decisions on Pending rows -- a card view that
  can only look while the table can act is a worse version of the same screen
  (`tenant-requests.html:159-161`).
- Expandable full text in both views, with `aria-expanded` on the control.
- Approve: confirm dialog naming the organisation and the address, stating what will be created.
  **Must gain** an editable tenant code.
- Reject: its own dialog with an optional reason.
- Per-row busy state while a decision is in flight; the outcome shown as a toast carrying the
  server's message; the list reloaded on success.
- An approved row **must** link to the tenant it created.

### 4.5 States

| State | Public form | Queue |
|---|---|---|
| Loading | Button "Sending…", disabled | `TableShell` spinner, "Loading…" |
| Error | Red line under the form with the server's message, or "Your request could not be sent. Please try again." | `TableShell` error card with the server's message and "Try again" |
| Empty | n/a | "No requests yet. The form at /request-workspace feeds this list." / "No request matches those filters." |
| Success | Acknowledgement card replacing the form | Toast with the server's message, list reloaded |
| Partial success | n/a | Approve returns `SUCCESS` with the "welcome email could not be sent" message -- shown verbatim as a success toast. It should be shown as a **warning**, because a credential was lost |

### 4.6 Dark and light

Both screens are token-only: `bg-page`, `border-subtle`, `--text-secondary`, `--text-muted`,
`--surface-sunken`, `--border-strong`, `--color-warn-600`, `--color-ok-500`. Themes are class-based
(`html.dark`, `styles.css:138-150`), driven by `ThemeService`
(`core/theme.service.ts`), and the public page carries its own toggle because it sits outside the
shell (`request-workspace.ts:33-37`). The three request statuses were added to the shared status
palette specifically so they would not all render as the same neutral grey
(`shared/ui/status-pill.ts:39-52`), each with its own glyph so the difference survives for a reader
who cannot separate the hues.

The one hard-coded colour in the feature is the top rule of a card, and it reads tokens rather than
hex (`tenant-requests.ts:142-150`).

### 4.7 Responsive

- Public page: `max-w-3xl` column, `form-grid` collapsing name and email to one column on small
  screens.
- Queue: tiles `grid-cols-2 md:grid-cols-4`; cards `sm:grid-cols-2 xl:grid-cols-3`; the table scrolls
  inside `TableShell`'s own `overflow-x-auto` box (`data-table.ts:66`) so the page body never scrolls
  sideways; the Contact column is capped at `max-w-48` and the Asked-for cell at `max-w-64`, with the
  reason recorded in the template at `tenant-requests.html:243-247` -- one long address widened the
  column to 270px and pushed Approve off the edge.

---

## 5. Backend requirements

### 5.1 Endpoints

`process/src/main/java/process/api/TenantRequestRestApi.java`. **No class-level `@PreAuthorize`** --
see `:41-48`; adding one would replace the method-level `permitAll()` and close sign-up.

| Method | Path | Role | What it does |
|---|---|---|---|
| POST | `/tenantRequest.json/submit` | **anonymous**, `@PreAuthorize("permitAll()")` (:49) and `SecurityConfig.java:47` | Validates and stores a request. Returns the same acknowledgement whether or not anything was created |
| GET | `/tenantRequest.json/listRequests` | `PLATFORM_ADMIN` (:60) | Returns **every** request, newest id first. Not "pending only" -- `.ai/discovery/backend.md:489` is wrong on this point |
| POST | `/tenantRequest.json/approve` | `PLATFORM_ADMIN` (:71) | `tenantRequestId` required, `tenantCode` optional. Creates the tenant, its first `TENANT_ADMIN` and that account's one-time password; mails it |
| POST | `/tenantRequest.json/reject` | `PLATFORM_ADMIN` (:84) | `tenantRequestId` required, `note` optional |

Every method wraps its body in try/catch and returns `500 { status: ERROR, message: "Some internal
error occurred contact with support." }` on an exception (`:97-101`).

### 5.2 Services

| Class | Responsibility |
|---|---|
| `TenantRequestServiceImpl` (242 lines) | All four operations. **Has no interface** -- the controller depends on the concrete class (`TenantRequestRestApi.java:16,35`), unlike most of the codebase |
| `TenantRequestRepository` | `findAllByOrderByTenantRequestIdDesc()`; `findOpenByEmail` -- a native query matching `lower(contact_email)` with `status = 'Pending' limit 1` (`:23-25`) |
| `TenantRepository.findByTenantCode` | The code-collision check. Does **not** exclude `TenantStatus.Delete`, so a soft-deleted tenant still holds its code |
| `AppUserRepository.findByUsernameAndStatusNot` | The duplicate-account check, run at submission and again at approval |
| `TemporaryPassword.generate()` | The shared 16-character generator, alphabet without `I l 1 O 0` (`util/TemporaryPassword.java:17-35`) |
| `EmailMessagesFactory.sendTenantWelcomeEmail` | The one message in the product that carries a credential (`:108-136`) |
| `AuditListener` | Stamps `created_by` on the tenant and the account (`model/pojo/AuditListener.java:23-39`) |

Requirements on the service that must not regress:

1. Nothing in a submitted body is trusted; the stored row is built field by field.
2. The acknowledgement string exists once and is returned from both branches.
3. The generated password is never logged, never returned, and never shown to the approver.
4. Approve is `@Transactional`, so a failure between the tenant and the account leaves neither.
5. A mail failure does not roll the transaction back and does not report a clean success.
6. `decided_by` comes from `TenantContext.getAppUserId()`, never from the request body.

---

## 6. Database requirements

### 6.1 `tenant_request`

Created by `V21__tenant_request.sql`, changeset `21.0-tenant-request`
(`db/changelog/yaml/V21.0-tenant-request.yaml`), included in the master changelog. Rollback drops the
column, the table and the sequence.

| Column | Type | Null | Entity field | Note |
|---|---|---|---|---|
| `tenant_request_id` | `BIGINT` PK | no | `tenantRequestId` | `tenant_request_seq`, starts at 1000, `allocationSize = 1` |
| `organisation_name` | `VARCHAR(255)` | no | `organisationName` | Becomes `tenant.tenant_name` on approval |
| `contact_name` | `VARCHAR(255)` | no | `contactName` | Becomes `app_user.full_name` |
| `contact_email` | `VARCHAR(255)` | no | `contactEmail` | Stored lower-cased; becomes `app_user.username` |
| `purpose` | `TEXT` | yes | `purpose` | Free text, unbounded |
| `status` | `VARCHAR(24)` | no, default `'Pending'` | `status` | Plain string, not an enum: `Pending` / `Approved` / `Rejected` |
| `date_created` | `TIMESTAMP` | no, default `now()` | `dateCreated` | |
| `decided_at` | `TIMESTAMP` | yes | `decidedAt` | |
| `decided_by` | `BIGINT` | yes | `decidedBy` | The platform admin's `app_user_id`. **No FK** |
| `decision_note` | `TEXT` | yes | `decisionNote` | Rejection reason; never shown outside the platform |
| `created_tenant_id` | `BIGINT` | yes | `createdTenantId` | **No FK** |
| `created_user_id` | `BIGINT` | yes | `createdUserId` | **No FK** |

No `tenant_id`, and no `created_by`/`updated_by` -- the table was not in V22's audit-column list.
Both omissions are right: this is a platform-owned register with its own decision trail.

### 6.2 Indexes

| Index | Definition | Used by |
|---|---|---|
| `ux_tenant_request_open_email` | `UNIQUE ON (lower(contact_email)) WHERE status = 'Pending'` (`:27-29`) | Exactly matches `findOpenByEmail`, and is the last line of defence against a double submit |
| `ix_tenant_request_status` | `ON (status)` (`:31`) | **Nothing.** `listRequests` is an unfiltered `findAll…OrderBy…Desc`; status filtering happens in the browser |

The partial unique index cannot be expressed in JPA, so a schema built from the entity mappings
alone silently lacks it -- already recorded as `.ai/discovery/risks.md:81`.

### 6.3 Migration needed

| Change | Why |
|---|---|
| Length constraints, or a documented decision to leave `purpose` unbounded | Section 3; today over-length input becomes a 500 |
| FKs on `decided_by`, `created_tenant_id`, `created_user_id` | Every other table got them in V12-V14; `tenant_request` was created in V21 and no later changeset touches it (verified across `db/changelog`) |
| Drop `ix_tenant_request_status`, or start using it | An index supporting no query, the same shape as `.ai/discovery/risks.md:105` |
| A `status` check constraint, or an enum | The column is a free string with a default; nothing in the database stops `'Approvedd'` |

The `app_user.must_change_password` column added by the same changeset (`:35`) is shared with
`tenants-and-users` and `authentication-and-access`; it belongs to those documents, not this one.

---

## 7. Validation

Client column = `request-workspace.ts` / `tenant-requests.ts`. Server = `TenantRequestServiceImpl`.
DB = the schema.

| Rule | Client | Server | DB | Notes |
|---|---|---|---|---|
| Organisation required | yes (`:131`) | yes (`:90-92`) | `NOT NULL` | |
| Contact name required | yes (`:132`) | yes (`:93-95`) | `NOT NULL` | |
| Email required | yes (`:133`) | yes (`:97`) | `NOT NULL` | |
| Email shape | `Validators.email` | `^[^@\s]+@[^@\s.]+\.[^@\s]+$` (`:51`) | -- | **The two disagree in both directions.** Verified by running both patterns: `a@b` and `user@localhost` pass the client and are refused by the server; `a@-b.com` and `x@y..z` are blocked by the client and would be accepted by the server |
| Email lower-cased | no | yes (`:96`) | -- | The client sends what was typed |
| Email trimmed | no | yes (`safe`, `:240`) | -- | |
| Purpose optional | yes | yes (`blankToNull`, `:241`) | nullable | |
| Maximum lengths | **none** | **none** | `VARCHAR(255)` x3 | Client-only would be a finding; *neither* is worse. See K-4 |
| One open request per address | -- | check-then-insert (`:106`) | partial unique index | The index is the real rule; the check is the friendly one. Racy -- K-9 |
| No second request for an existing account | -- | yes (`:107`) | -- | Case-sensitive against a lower-cased address -- K-2 |
| Body cannot set status / decision / created ids | -- | by construction (`:111-118`) | -- | Correct |
| Approve: id present, found, still Pending | -- | yes (`:135-146`) | -- | |
| Approve: tenant code non-empty after normalisation | -- | yes (`:149-151`) | -- | |
| Approve: tenant code unique | -- | yes (`:152-154`) | `tenant.tenant_code UNIQUE` | Does not exclude deleted tenants |
| Approve: no existing account for the address | -- | yes (`:157-161`) | `app_user.username UNIQUE` | Case-sensitive -- K-2 |
| Reject: id present, found, still Pending | -- | yes (`:212-223`) | -- | |
| Reject note optional, blank -> null | trimmed (`reject-dialog.ts:47`) | `blankToNull` (`:227`) | nullable | |
| Reject note maximum length | **none** | **none** | `TEXT` | |
| Decision actor | -- | `TenantContext` (`:186`, `:226`) | -- | Never from the body |

**Client-only rules: none.** Everything the browser checks, the server checks too. The finding here
is the reverse -- rules that are on *neither* side (lengths) and rules where the two are not the
same rule (email shape, case folding).

---

## 8. Security

Three roles, hierarchical, with `PLATFORM_ADMIN > TENANT_ADMIN > TENANT_USER` declared once in
`config/MethodSecurityConfig.java:29` and mirrored in the frontend's `roleGuard`
(`core/auth/auth.guard.ts:33-42`), which names a single minimum and lets the hierarchy do the rest.

### 8.1 Who may do what

| Actor | submit | listRequests | approve | reject |
|---|---|---|---|---|
| Anonymous | **yes** -- the point of the feature | 401 | 401 | 401 |
| `TENANT_USER` | yes (pointless but permitted) | 403 | 403 | 403 |
| `TENANT_ADMIN` | yes | 403 | 403 | 403 |
| `PLATFORM_ADMIN` | yes | yes | yes | yes |
| A caller with no tenant and no `PLATFORM_ADMIN` role | as `TENANT_USER` | 403 | 403 | 403 |

A signed-in caller reaching `submit` is harmless: the service ignores the caller entirely and the
duplicate check will find their own account, so the call creates nothing and returns the same
sentence as everyone else.

### 8.2 The four layers, one by one

**Layer 1 -- the frontend guard.** `admin/tenant-requests` carries `minRole: 'PLATFORM_ADMIN'` and
`canActivate: [roleGuard]` (`app.routes.ts:198-204`). The nav entry is `platformOnly` and filtered
out for anyone else (`features/shell/shell.ts:133-134` and the computed at `:140-150`). Pinned by
`core/auth/auth.guard.spec.ts:139` and by the route-table test at `:117-123`, which fails any route
that declares a minimum without running the guard. `request-workspace` carries no guard, which is
correct for a public page and slightly wrong in one direction only -- a signed-in user can open it
(K-13). **This layer hides controls; it enforces nothing.**

**Layer 2 -- the controller annotation.** Three `@PreAuthorize("hasRole('PLATFORM_ADMIN')")` and one
`@PreAuthorize("permitAll()")`, all at method level, on a class with no class-level annotation. This
is the case the ground rules warn about, handled correctly and deliberately: `@PreAuthorize` is not
repeatable, so a class-level `hasRole` would *replace* the method's `permitAll()` and close the
public form. The javadoc at `TenantRequestRestApi.java:41-48` records exactly that. A refusal here
is turned into `403 { status: ERROR, message: "You don't have permission to perform this action." }`
by `config/GlobalExceptionHandler.java:24-30`.

**Layer 2b -- the URL layer.** `SecurityConfig.java:47` permits `POST /tenantRequest.json/submit`
and nothing else under that prefix; `anyRequest().authenticated()` (`:55`) covers the other three,
and the entry point returns a bare 401 (`:33-34`). The method restriction matters: a `GET` to
`/submit` is not permitted by the URL layer.

**Layer 3 -- the service rule.** `TenantRequestServiceImpl` performs **no** role or ownership check
of its own. It reads `TenantContext.getAppUserId()` to stamp the decision (`:186`, `:226`) and
otherwise trusts that the controller annotation held. For this feature that is defensible -- the
entity is platform-owned, there is no per-tenant slice of it to get wrong, and there is nothing an
ownership check could compare against -- but it must be said out loud, because it means **the
`@PreAuthorize` is the only thing standing between a tenant admin and the approve endpoint.** Delete
one annotation and nothing downstream notices. Nothing tests that today.

**Layer 4 -- the Hibernate filter.** `TenantRequest` declares no `@FilterDef`/`@Filter`
(verified: it is not among the 15 entities in `model/pojo/` that do), so the tenant filter is a
genuine no-op here -- and `TenantFilterHelper.enableIfNeeded` is never called on this path in any
case. `.ai/discovery/database.md:336` records the same. This is correct for a platform-owned table,
and it is the reason layer 3 has nothing to do: **for this feature, layers 3 and 4 are both empty by
design, and the whole rule lives in layer 2.**

### 8.3 Secrets

- The generated password exists in readable form in exactly two places: the local variable at
  `TenantRequestServiceImpl.java:171` and the mail body. It is bcrypt-hashed before it touches the
  database (`:179`), never returned in a `ResponseDto`, and masked in the mail log by
  `EmailMessagesFactory.safeToLog` (`:216-228`).
- `sendTenantWelcomeEmail` catches without logging the exception message (`:130-134`) because a mail
  failure can echo the body, and this body holds the credential.
- `listRequests` serialises the raw `TenantRequest` entity, so `decidedBy`, `createdTenantId` and
  `createdUserId` all reach the client. Only a platform admin can call it, so this is not a leak --
  but it is a raw entity on the wire with no DTO, which is how a future column becomes a leak.

### 8.4 The enumeration property, and its one hole

The uniform acknowledgement holds on every path the service returns from. It does **not** hold when
the insert throws: a duplicate open request created concurrently produces a 500 rather than the
acknowledgement (K-9). The window is small; the property is either total or it is not one.

### 8.5 The one-time password is one-time only in the browser

`must_change_password` is written by approval (`:180`), reported at login
(`AuthServiceImpl.java:132`) and enforced by `passwordChangeGuard` in the client
(`core/auth/auth.guard.ts:59-67`). Grepping the backend for `mustChangePassword` finds it written,
read into two DTOs and cleared -- and consulted by no filter, no interceptor and no `@PreAuthorize`.
A caller who takes the emailed password to `POST /auth.json/login` receives a full `TENANT_ADMIN`
token and may drive every endpoint indefinitely. The setup guide tells the recipient the emailed
password "stops working at that moment" (`features/docs/docs.ts:286-289`). At the API it does not.

---

## 9. Error handling

| What fails | Server | What the user sees |
|---|---|---|
| Empty required field on the public form | not reached | Red message under the field, plus "Check the highlighted fields." under the form (`request-workspace.ts:142`) |
| Malformed email the client catches | not reached | "That does not look like an email address." on the field (`:79`) |
| Malformed email only the server catches (`a@b`) | `ERROR` + message | The server's sentence in the red line **under the form**, not on the field (`:150`). Wrong place |
| Address already known | `SUCCESS` + acknowledgement | The acknowledgement card. Deliberate |
| Over-length field | exception -> 500 | "Some internal error occurred contact with support." for something the user could have fixed. K-4 |
| Concurrent duplicate submit | exception -> 500 | Same. K-9 |
| Network failure on submit | -- | "Your request could not be sent. Please try again." (`:156-158`) |
| Queue load refused (403) | `ERROR` + "You don't have permission to perform this action." | `TableShell` error card with that message and "Try again" |
| Queue load 401 | bare 401 from the entry point | The interceptor attempts one refresh; on failure the session is ended and the user is sent to `/login` (`core/auth/auth.interceptor.ts:105-132`) |
| Queue load 500 | `ERROR` envelope | Error card with the server's message, retry available |
| Approve on an already-decided request | `ERROR "This request was already approved."` | Error toast; list not reloaded, so the stale row stays until Refresh |
| Approve with a taken tenant code | `ERROR "Tenant code \"x\" is already in use."` | Error toast, and **no way forward** -- the screen cannot send a different code. K-5 |
| Approve where the address already has an account | `ERROR "There is already an account for x."` | Error toast |
| Approve succeeds, mail fails | `SUCCESS` + "Tenant created, but the welcome email could not be sent. Reset the password for x and pass it on another way." | A **green** success toast. The words are right; the colour says the opposite |
| Approve throws mid-transaction | 500 | Error toast with the generic message; the transaction rolls back, so no half-made tenant |
| Reject cancelled | not called | Nothing |
| Missing `tenantRequestId` parameter | `MissingServletRequestParameterException` -> `handleExceptionInternal` -> 400 with the exception message | Error toast carrying a framework message |

---

## 10. Dependencies

| Depends on | Why |
|---|---|
| `authentication-and-access` | The bearer token and the role every guard reads; `passwordChangeGuard` is what makes the emailed password a one-time credential in practice; the landing page and the login screen are the only routes that link here |
| `tenants-and-users` (feature 16) | Approval creates a `Tenant` and an `AppUser`, reuses `TenantRepository.findByTenantCode` and `AppUserRepository.findByUsernameAndStatusNot`, and shares `TemporaryPassword` with `addUser`. The recovery path for a lost welcome mail is that feature's `resetPassword` |
| SMTP | `EmailMessagesFactory` + `JavaMailSender` + `templates/tenant_welcome.vm`. Without it the feature still works and says so, but the credential is lost |
| `app.console.url` | The sign-in link in the welcome mail. Configured nowhere; falls back to `http://localhost:4400` |
| Liquibase changeset `21.0-tenant-request` | The table, the sequence and the partial unique index. `ddl-auto=update` would create the table but not that index |
| Shared UI | `Field`, `TableShell`, `StatTile`, `StatusPill`, `ViewToggle`, `Pagination`, `createSort`, `createPager`, `confirmWith`, `FormDialog`, `ToastService`, `copyText`, `ThemeService` |

Nothing depends on this feature. The dotted edge `WR -.-> ACCT` in Discovery's graph
(`.ai/discovery/features.md:422`) is **not implemented** -- see K-16.

---

## 11. Acceptance criteria

Fixtures used throughout:

- `platform` -- `PLATFORM_ADMIN`, `tenant_id` null.
- `adminA` -- `TENANT_ADMIN` of tenant **A** (`tenant_code = acme`).
- `userA` -- `TENANT_USER` of tenant A.
- `orphan` -- `TENANT_USER` with `tenant_id` null.
- `R-PEND` -- Pending, organisation "Northwind Logistics", contact `ivar@northwind.example`, a
  600-character purpose.
- `R-NOPURPOSE` -- Pending, `purpose` null.
- `R-DUPCODE` -- Pending, organisation "Acme", whose derived code `acme` is already tenant A's.
- `R-APPR` -- Approved. `R-REJ` -- Rejected, with a note.

Five requests in all: three Pending, one Approved, one Rejected.

### The public form

1. An anonymous visitor opens `/request-workspace` without signing in and sees four controls;
   Organisation, Your name and Your email carry a required marker, "What do you need it for?" does
   not.
2. Pressing **Send request** on an empty form produces three field-level messages and the line
   "Check the highlighted fields."; `tenant_request` gains no row.
3. An anonymous visitor submits Organisation "Northwind Logistics", name "Ivar Halvorsen", email
   `Ivar@Northwind.Example`, purpose "Nightly rail feeds". The form is replaced by the
   acknowledgement card; exactly one `tenant_request` row exists with `status = 'Pending'`,
   `contact_email = 'ivar@northwind.example'` (lower-cased), `date_created` set, and `decided_at`,
   `decided_by`, `decision_note`, `created_tenant_id` and `created_user_id` all null.
4. Submitting the same address again returns an acknowledgement **byte-identical** to the one in
   criterion 3, and the table still holds exactly one row for that address.
5. Submitting the address of an existing active account returns the same byte-identical
   acknowledgement and creates no row. Positive control on the same fixture: a fresh address returns
   the same sentence **and** does create a row.
6. `a@b` passes the browser's validator and is refused by the server with "That does not look like
   an email address."; the message appears **on the email field**, not only under the form.
   *(Placement fails today.)* Positive control: `ivar@northwind.example` is accepted.
7. A raw `POST /tenantRequest.json/submit` whose body carries valid names plus
   `{"status":"Approved","decidedBy":1,"createdTenantId":9,"tenantRequestId":7}` stores a row whose
   `status` is `Pending` and whose `decided_by`, `created_tenant_id` and `tenant_request_id` are the
   server's own values.
8. A 300-character organisation name is refused with a message naming the limit and an HTTP 4xx.
   *(Fails today -- K-4: it reaches Postgres and returns 500.)* Positive control: a 200-character
   name is accepted.
9. Two `submit` calls for the same new address issued concurrently both return the acknowledgement
   and neither returns 500. *(Fails today -- K-9.)*
10. Anonymous `GET /tenantRequest.json/listRequests` returns 401. Positive control: anonymous
    `POST /tenantRequest.json/submit` with a valid body returns 200 and `status: SUCCESS`.
11. On success, keyboard focus moves to the acknowledgement card and the sentence is announced to a
    screen reader. *(Absent today.)*
12. The public page renders in both themes with no colour defined outside a token, and at 360 px the
    page body does not scroll horizontally.

### The queue -- who may see it

13. `platform` opens `/admin/tenant-requests` and sees all five fixture requests; the tiles read
    Waiting 3, Approved 1, Rejected 1, Total 5.
14. `adminA` sees no "Workspace Requests" entry under Administration. Positive control: `adminA`
    does see "Users" in the same menu.
15. `adminA` types `/admin/tenant-requests` and lands on `/unauthorized`. Positive control: `adminA`
    opens `/admin/users` successfully.
16. `userA` types `/admin/tenant-requests` and lands on `/unauthorized`. Positive control: `userA`
    opens `/dashboard` successfully.
17. `adminA`'s token on `GET listRequests` returns 403 with `status: ERROR` and the message "You
    don't have permission to perform this action.", and **no** `data` array. Positive control:
    `platform`'s token on the same call returns 200 with an array.
18. `userA`'s token on `POST approve?tenantRequestId=<R-PEND>` returns 403; `R-PEND` is still
    Pending, no tenant named "Northwind Logistics" exists and no account exists for
    `ivar@northwind.example`. Positive control: `platform` on the same id succeeds and both rows
    appear.
19. `orphan`'s token is refused on all three of `listRequests`, `approve` and `reject`. Positive
    control: `platform`'s token is served on all three.
20. Removing `@PreAuthorize` from any one of `listRequests`, `approve` or `reject` makes a test fail.
    *(No such test exists today -- K-12.)*

### The queue -- behaviour

21. With the endpoint slow, the card shows a spinner and "Loading…" and no rows.
22. With the endpoint returning `status: ERROR`, the card shows that message and a "Try again"
    button; pressing it re-issues the call and the list appears when the server recovers.
23. With no requests at all, the card reads "No requests yet. The form at /request-workspace feeds
    this list."
24. Selecting **Waiting** in the status filter leaves only Pending rows and the heading reads
    "Requests (3 of 5)"; **Clear** restores all five.
25. Typing a word that appears only inside one request's purpose narrows the list to that request.
26. Clicking the Status header once puts Waiting rows above Approved and Rejected.
27. The screen opens in **cards**; switching to Table and reloading the page returns to Table
    (`localStorage` key `etl.view.tenant-requests`).
28. Approve and Reject appear on Pending rows in **both** views and on no Approved or Rejected row in
    either.
29. Expanding `R-NOPURPOSE` in the table shows no empty "What they asked for" block. *(Fails today --
    K-10.)* Positive control: expanding `R-PEND` shows its full 600-character purpose.
30. Clicking the copy control on a card puts the address on the clipboard and shows a tick that
    clears within about two seconds.
31. In dark mode the Waiting, Approved and Rejected chips differ in both colour and glyph.
32. At 360 px the table scrolls inside its own box while the page body does not, and the cards fall
    to a single column.

### Approve

33. `platform` presses Approve on `R-PEND`; the dialog names "Northwind Logistics" and
    `ivar@northwind.example` and states that a one-time password will be emailed. Cancelling posts
    nothing and leaves the row Pending.
34. Confirming produces a toast carrying the server's message; after the reload `R-PEND` shows as
    Approved with a decided date; a `tenant` row exists with `tenant_name = 'Northwind Logistics'`,
    `tenant_code = 'northwind-logistics'`, `status = Active`; an `app_user` row exists with
    `username = 'ivar@northwind.example'`, `user_role = TENANT_ADMIN`, `status = Active`,
    `must_change_password = true` and `tenant_id` = the new tenant.
35. The approve response body contains no password field, and no log line emitted during the call
    contains the generated password in clear text.
36. `tenant_request.created_tenant_id` and `created_user_id` point at the two rows created,
    `decided_by` is `platform`'s `app_user_id`, and `tenant.created_by` and `app_user.created_by` are
    also `platform`'s id.
37. The approved row on screen offers a link to the tenant it created. *(Absent today -- K-11.)*
38. The new administrator signs in with the emailed password, is held on `/profile` whatever URL is
    typed, changes the password, and is then free to open `/dashboard`. Positive control: signing in
    again with the **new** password lands on the dashboard directly.
39. Approving `R-APPR` returns "This request was already approved." and creates nothing. Positive
    control: approving `R-PEND` on the same fixture succeeds.
40. Approving `R-DUPCODE` offers an editable tenant code, defaulted to `acme`, and succeeds when
    `acme-2` is supplied. *(Fails today -- K-5: the call is refused and the screen has no field.)*
41. With an account already stored as `Ivar@Northwind.Example` (mixed case, created through
    `admin/users`), approving `R-PEND` is refused with "There is already an account for …" and
    creates neither a tenant nor a second account. *(Fails today -- K-2.)* Positive control: with the
    stored account lower-cased, the same approval is refused, proving the check itself works.
42. With SMTP unreachable, approve still returns `status: SUCCESS`, its message names the account and
    says the welcome email could not be sent, the tenant and account both exist, and the toast is
    rendered as a **warning** rather than a plain success. *(Warning styling absent today.)*
43. `platform` resets the new administrator's password through `admin/users`; the account's
    `must_change_password` returns to true and the person can sign in with the new value.

### Reject

44. `platform` presses Reject on `R-PEND`; a dialog appears with an optional Reason. Cancelling posts
    nothing and leaves the row Pending.
45. Rejecting with "Not a real organisation." stores that text in `decision_note`, shows it on the
    row and in the expanded detail, and creates no tenant or account.
46. Rejecting with the reason left blank stores `decision_note` as null and the row shows no "Reason
    given" block.
47. Rejecting `R-REJ` returns "This request was already rejected." Positive control: rejecting
    `R-PEND` on the same fixture succeeds.
48. After `R-PEND` is rejected, the same address may submit again and the new request appears as a
    Waiting row -- the partial unique index covers Pending rows only.

### Coverage

49. A backend test exists that submits the same address twice as an anonymous caller and asserts the
    two response bodies are equal. *(Absent today.)*
50. A backend test exists that approves a request and asserts the tenant, the account, the flags and
    the three pointer columns; and one that asserts a second approve is refused. *(Absent today.)*
51. A frontend spec exists for `TenantRequests` covering load, the error path, the filters, and both
    decision calls with `HttpTestingController`; and one for `RequestWorkspace` covering the invalid
    submit, the success card and the server-refusal path. *(Absent today.)*

---

## 12. Known issues

### K-1 -- `listRequests` returns the entire history, unpaged, and Discovery says otherwise

`TenantRequestServiceImpl.java:122-125` calls `findAllByOrderByTenantRequestIdDesc()` -- every row
ever written, with no status filter, no limit and no paging. The screen pages client-side
(`tenant-requests.ts:78,98`) and computes its four tiles from the full array (`:166-174`), so the
tiles are honest only because the whole table is on the wire. `.ai/discovery/backend.md:489`
describes the endpoint as "Lists pending requests", which is wrong and would mislead anyone sizing
the work. Not urgent at ten requests; the shape does not survive ten thousand.

### K-2 -- The duplicate-account check is case-sensitive against a force-lower-cased address

`submit` lower-cases the address (`:96`) and both the submission check (`:107`) and the approval
re-check (`:157-158`) look it up with `findByUsernameAndStatusNot(email, Status.Delete)`. But
`appUser.json/addUser` stores the username exactly as typed --
`user.setUsername(appUserDto.getUsername().trim())` (`AppUserServiceImpl.java:192`), with the
duplicate check at `:180` equally case-sensitive -- and `app_user.username` is a plain
`unique = true` column (`AppUser.java:63`), which in Postgres is a case-sensitive unique index.

So an account created as `Ivar@Northwind.Example` is invisible to both checks. The consequence at
approval is not a cosmetic one: a **second** `app_user` row and a **second** tenant are created for a
person who already has an account, and `Ivar@Northwind.Example` and `ivar@northwind.example` then
coexist as two distinct logins. Login itself is case-sensitive too
(`AuthServiceImpl.java:52-53`), so the two accounts are genuinely separate.

The same asymmetry has a smaller second effect: a request submitted for an address whose account is
stored in mixed case will be recorded rather than silently absorbed. The response is identical
either way, so the enumeration property is unharmed.

### K-3 -- The only anonymous write in the application has no rate limit

`POST /tenantRequest.json/submit` is `permitAll` (`TenantRequestRestApi.java:49`,
`SecurityConfig.java:47`) and writes a row. Searching the whole of `process/src/main` and `pom.xml`
for `ratelimit`, `rate-limit`, `bucket4j` or `throttl` returns **nothing**, and there is no CAPTCHA,
no per-IP cap and no per-address cap beyond "one *open* request per address". A script varying the
local part writes one row per call for as long as it is left running. Combined with K-4 -- `purpose`
is unbounded `TEXT` -- each of those rows can be arbitrarily large.

### K-4 -- No maximum length on any field, client or server

`request-workspace.ts:66-88` sets no `maxlength` on any of the four controls, and
`TenantRequestServiceImpl.java:90-99` checks blankness and email shape only. Three of the columns are
`VARCHAR(255)` (`V21__tenant_request.sql:11-13`). A 300-character organisation name therefore passes
both layers and fails in Postgres; the exception is caught by the controller's catch-all
(`TenantRequestRestApi.java:54-57`) and returned as HTTP 500 "Some internal error occurred contact
with support." -- an opaque 500 where the code already knows the reason, which is exactly what the
project's own observability rule calls a defect. `purpose` is `TEXT`, so it takes whatever is sent.

### K-5 -- A tenant-code collision is a dead end in the UI

`approve` accepts an optional `tenantCode` (`TenantRequestRestApi.java:73-74`) precisely so a
collision can be resolved. `tenant-requests.ts:204-206` sends only `tenantRequestId`, so the code is
always derived from the organisation name. When `normaliseCode(organisationName)` collides -- with a
live tenant, or with a **soft-deleted** one, since `TenantRepository.findByTenantCode` does not
exclude `TenantStatus.Delete` and `Delete` is a status rather than a row removal
(`TenantStatus.java`, `TenantServiceImpl.java:141-148`) -- the administrator gets "Tenant code
\"acme\" is already in use." and the screen offers nothing to do about it. The only way through is
to create the tenant and the user by hand on two other screens and then reject the request, which
loses the trail the `created_tenant_id` column exists to keep.

### K-6 -- Every welcome email links to `http://localhost:4400`

`@Value("${app.console.url:http://localhost:4400}")` at `TenantRequestServiceImpl.java:68` (and the
same at `AppUserServiceImpl.java:71`). Searching the whole `process` tree, excluding `target`, for
`console.url` or `CONSOLE_URL` returns **only those two lines** -- the property is set in no
`.properties` file, no `docker-compose.yml` and no `.env.example`. So the sign-in link in the one
message that carries a credential is always the fallback. The new frontend's own default port is
4200 (`.ai/project.md`), so even on a developer's machine the link is usually wrong; in any deployed
environment it points at the recipient's own laptop.

### K-7 -- Dead password machinery beside the live path

`TenantRequestServiceImpl` declares `GENERATED_PASSWORD_LENGTH = 16` (`:52-53`), `PASSWORD_ALPHABET`
(`:54-59`) and `private final SecureRandom random` (`:66`). None of the three is read anywhere in the
class; the password comes from `TemporaryPassword.generate()` (`:171`). The duplicated constants
carry the same comment as the real ones (`TemporaryPassword.java:19-23`), which is the drift that
class's own header says it was extracted to prevent (`:8-11`). Harmless today, misleading to the
next reader, and the sort of thing that gets "fixed" by editing the copy nobody uses.

### K-8 -- The one-time password is enforced only by the browser

Detailed in §8.5. `must_change_password` is written at `TenantRequestServiceImpl.java:180`, surfaced
at `AuthServiceImpl.java:132`, and acted on only by `passwordChangeGuard`
(`core/auth/auth.guard.ts:59-67`). No server-side check consults it -- grepping the backend for
`mustChangePassword` finds writes, DTO plumbing and the clear at `AppUserServiceImpl.java:629`, and
nothing else. The credential mailed to a stranger is a full-power `TENANT_ADMIN` login that stays
valid until somebody chooses to change it. `features/docs/docs.ts:286-289` tells the recipient
otherwise.

### K-9 -- Concurrent duplicate submits produce a 500, breaking the uniform acknowledgement

`submit` is not `@Transactional` and does a check-then-insert (`:106-118`) against a partial unique
index (`V21__tenant_request.sql:27-29`). Two requests for the same new address that interleave
between the check and the save give the loser a `DataIntegrityViolationException`, caught at
`TenantRequestRestApi.java:54-57` and returned as HTTP 500. It is the one path where the response is
not the deliberately uniform acknowledgement, and it is reachable by a double click.

### K-10 -- An expanded row prints an empty "What they asked for"

`tenant-requests.html:305-309` renders the heading and `{{ r.purpose }}` with no guard. The card view
guards the same value (`:118-134`, with an italic "Nothing was written here" fallback) and so does
the collapsed table cell (`:253-266`). Expanding `R-NOPURPOSE` in the table therefore shows a
heading over blank space.

### K-11 -- Loose ends on the queue screen

Three small ones, grouped because each is a line or two:

- `createdTenantId` is declared on the row interface (`tenant-requests.ts:30`) and rendered nowhere
  (verified: zero matches in `tenant-requests.html`). The pointer that makes a decision traceable is
  fetched and dropped.
- `RejectDialog.saving` is declared (`reject-dialog.ts:41`) and never set true (`:44-48`), so the
  dialog's confirm button has no pending state. In practice the dialog closes before the POST is
  issued (`tenant-requests.ts:214-223`), so the signal cannot ever be true -- it is dead.
- A partly-successful approval -- tenant created, mail lost -- is a `SUCCESS` envelope
  (`TenantRequestServiceImpl.java:201-205`) and is toasted with `toast.success`
  (`tenant-requests.ts:245`). The words say a credential was lost; the colour says everything is
  fine. `ToastService` already carries the right tone (`shared/ui/toast.service.ts:22`, `warn`); what
  is missing is any way for the client to tell the two successes apart other than by reading the
  message.

### K-12 -- Zero tests, on both sides

Per §2.9. No spec imports any of the three components; `process/src/test` contains no reference to
`TenantRequest`. What that leaves uncovered, concretely: the neutral acknowledgement (a security
property), the `permitAll` on `submit` surviving a future class-level annotation (a whole-feature
outage if it regresses), the three `@PreAuthorize` annotations that are the *only* authorization this
feature has (§8.2), the approve transaction, both already-decided guards, the code-collision path,
the mail-failure path, the reject note, and every state of both screens.

The two most valuable of these are cheap. `TenantLifecycleE2EIT` and `UserManagementE2EIT` already
provide the fixture helpers (`E2ESupport.newPlatformAdmin`, `newUser`, `newTenant`, `getAs`,
`postAs`); the only thing missing is an anonymous request builder, since `E2ESupport` exposes no
un-authenticated helper.

### K-13 -- The public form has no `anonymousOnly` guard

`app.routes.ts:28-33` carries no `canMatch`, unlike `login` (`:12`) and the landing page (`:25`). A
signed-in user who types `/request-workspace` gets the signed-out page, complete with a "Sign in"
button, outside the shell. Cosmetic, and the submit would be a harmless no-op, but it is the one
route in the file that does not follow the pattern the file establishes.

### K-14 -- Schema loose ends

- No foreign keys on `decided_by`, `created_tenant_id` or `created_user_id`
  (`V21__tenant_request.sql:20-23`), while V12-V14 added FK constraints across the rest of the
  schema. Verified that no changeset after V21 touches `tenant_request`.
- `ix_tenant_request_status` (`:31`) supports no query the application issues: the only read is an
  unfiltered `findAll…OrderBy…Desc` and status filtering is client-side. An index maintained for
  nothing, the same shape as `.ai/discovery/risks.md:105`.
- `status` is a free `VARCHAR(24)` with a default and no check constraint, compared against the
  string literal `"Pending"` in three places (`TenantRequestServiceImpl.java:116,143,220`) and
  against `'Pending'` in the partial index and the native query. Five copies of one magic string,
  none of them an enum.

### K-15 -- Two different normalisations of "tenant code"

`TenantRequestServiceImpl.normaliseCode` (`:233-237`) lower-cases, collapses each run of
non-alphanumerics into a single hyphen and strips leading and trailing hyphens.
`TenantServiceImpl.normalizeCode` (`:151-153`) lower-cases and replaces each offending character
with its own hyphen, collapsing nothing and stripping nothing. "Acme Corp." becomes `acme-corp`
through approval and `acme-corp-` through the tenants screen. Since the collision check
(`TenantRequestServiceImpl.java:152`) compares against whatever the other path stored, the two rules
disagreeing is precisely how a collision goes undetected in one direction and is falsely reported in
the other.

### K-16 -- Nothing tells anyone a request has arrived, or has been decided

`TenantRequestServiceImpl` never touches `NotificationCenterService` (verified: zero occurrences of
"otification" in the file), and `NotificationType` has no member for a workspace request
(`model/enums/NotificationType.java:7-8`). A platform administrator learns of a waiting request only
by opening `/admin/tenant-requests` and looking. Discovery's dependency graph draws
`WR -.-> ACCT` (`.ai/discovery/features.md:422`) and §5.3 asserts that "tenant approvals … raise
notifications"; neither is true. The rejected applicant is likewise told nothing, which *is*
deliberate (`reject-dialog.ts:18`) but is a product decision worth re-confirming rather than
inheriting.

---

## 13. Missing functionality

| Missing | What it would take |
|---|---|
| **Any test at all** (K-12) | A `TenantRequestE2EIT` in the shape of `TenantLifecycleE2EIT`: the neutral acknowledgement by byte comparison, the three role refusals each with a positive control, approve's created rows and pointer columns, both already-decided guards, the code collision, and the reject note. Plus `tenant-requests.spec.ts` and `request-workspace.spec.ts` with `HttpTestingController`, in the shape of `features/admin/storage/storage-connections.spec.ts`. An anonymous request helper has to be added to `E2ESupport` |
| **Length limits** (K-4) | Constants in `TenantRequestServiceImpl`, four `maxlength` attributes in `request-workspace.ts`, and a decision on `purpose` (recommend 4,000 characters, enforced server-side, `TEXT` left as it is) |
| **Rate limiting on `submit`** (K-3) | A servlet filter or a Spring interceptor on that one path, per IP and per address, backed by the Redis already in the stack. Nothing generic exists to reuse -- this would be the first |
| **An editable tenant code at approval** (K-5) | Replace `confirmWith` with a small dialog in the shape of `RejectDialog`: prefilled with the derived code, live-normalised, closing with the string, and passed as the `tenantCode` parameter the endpoint already accepts |
| **Server-side enforcement of `must_change_password`** (K-8) | Either a check in `JwtAuthenticationFilter` allowing only `changeOwnPassword`, `me` and `logout` for a flagged account, or a claim on the token consulted by a small `@PreAuthorize` helper. Needs a decision -- see the synthesis |
| **A configured `app.console.url`** (K-6) | The property in `application-dev/stage/prod.properties`, an `APP_CONSOLE_URL` in `docker-compose.yml` and `.env.example`, and a fallback that fails loudly rather than pointing at `localhost:4400` |
| **Server-side paging and filtering on `listRequests`** (K-1) | `Pageable` plus a status parameter on the repository method, counts returned alongside so the tiles stay honest, and the screen's `createPager` switched to server mode |
| **A link from an approved request to its tenant** (K-11) | One `routerLink` in `tenant-requests.html` using the `createdTenantId` already on the row |
| **Notification on arrival and on decision** (K-16) | A `TENANT_REQUEST_SUBMITTED` member on `NotificationType`, a `notificationCenterService.create(...)` call in `submit` addressed to platform admins, and a decision about whether a rejected applicant is emailed |
| **Case-folded usernames** (K-2) | One rule applied in both `TenantRequestServiceImpl` and `AppUserServiceImpl.addUser`, plus a migration to fold existing rows and a case-insensitive unique index on `app_user.username`. Cross-feature -- it belongs with `tenants-and-users` |
| **Foreign keys and a status constraint** (K-14) | A new changeset adding three FKs and a check constraint, and either dropping `ix_tenant_request_status` or giving it a query to serve |
| **Accessible acknowledgement** | `role="status"` on the card at `request-workspace.ts:45` and a programmatic focus move on `done()` |
| **A shared code normaliser** (K-15) | One static helper used by both services, and a test that pins "Acme Corp." to a single answer |
| **A service interface for `TenantRequestServiceImpl`** | Every comparable service has one; this controller depends on the implementation class directly. Cosmetic, and worth doing only alongside another change to the file |
| **A correction to Discovery** | `.ai/discovery/backend.md:489` says `listRequests` lists pending requests; it lists all of them. `.ai/discovery/features.md:422` and §5.3 claim a notification edge that does not exist |
