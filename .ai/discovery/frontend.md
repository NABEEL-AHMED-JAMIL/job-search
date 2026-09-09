# Discovery -- New Frontend (scheduler1/next)

Everything below was read out of `scheduler1/next/src` on 2026-09-01. Paths are relative to
`/Users/nabeel.amd93/Desktop/Old-School`. Where a claim could not be verified from the code it
says so.

---

## 1. Stack and conventions actually in use

### 1.1 Versions and build

From `scheduler1/next/package.json`:

| Thing | Version | Note |
| --- | --- | --- |
| `@angular/core`, `common`, `forms`, `router`, `compiler` | `^22.1.0` | |
| `@angular/build` / `@angular/cli` | `^22.1.5` | `@angular/build:application` builder |
| `@angular/cdk` | `^22.1.3` | Dialog, Menu, `cdkFocusInitial` |
| `tailwindcss` + `@tailwindcss/postcss` | `^4.3.3` | Tailwind 4, via `.postcssrc.json` |
| `typescript` | `~6.0.2` | |
| `vitest` | `^4.0.8` | run through `@angular/build:unit-test` |
| `@stomp/stompjs` + `sockjs-client` | `^7.3.0` / `^1.6.1` | the websocket |
| `pdfjs-dist` | `^6.2.108` | dynamically imported by the PDF viewer |
| `libphonenumber-js` | `^1.13.12` | phone input |
| `echarts`, `ngx-echarts`, `marked`, `file-saver` | declared | **never imported anywhere in `src`** -- see Risks |

`scheduler1/next/tsconfig.json` runs `strict: true`, `noImplicitOverride`,
`noPropertyAccessFromIndexSignature`, `noImplicitReturns`, `noFallthroughCasesInSwitch`, and
`strictTemplates` + `strictInjectionParameters` + `strictInputAccessModifiers` on the Angular
compiler.

`scheduler1/next/angular.json` defines exactly three targets (`build`, `serve`, `test`), one
global stylesheet (`src/styles.css`), assets from `public/`, and a production budget of 500 kB
warning / 1 MB error on the initial bundle. There is no `test` options block, so vitest runs on
the builder defaults -- no coverage thresholds, no reporters configured.

### 1.2 Bootstrap

`scheduler1/next/src/main.ts` is eleven lines. Line 4 shims `globalThis.global` before anything
else, with a comment saying sockjs-client reaches for Node's `global` and took bootstrap down
without it. Then `bootstrapApplication(App, appConfig)`.

`scheduler1/next/src/app/app.config.ts:9-12` is the whole provider set:

- `provideBrowserGlobalErrorListeners()`
- `provideZonelessChangeDetection()` -- **the app is zoneless**
- `provideRouter(routes, withComponentInputBinding())`
- `provideHttpClient(withInterceptors([authInterceptor]))`

`zone.js` is still a devDependency but nothing in `src` imports it.

`scheduler1/next/src/app/app.ts` is a three-element template: `<app-route-progress />`,
`<router-outlet />`, `<app-toast-host />`.

### 1.3 Component conventions

- **87 components** (`@Component`), **1 directive** (`StickToBottom`), **8 injectables**.
- All standalone. There is no `NgModule` and no `standalone: true` anywhere -- Angular 22
  defaults to standalone, and `imports: [...]` arrays are used on every component.
- `CommonModule` is never imported. Pipes are imported individually
  (`DatePipe`, `LowerCasePipe`, `DecimalPipe`, `NgTemplateOutlet`).
- 38 components use `templateUrl`, 49 use an inline `template:` string. The split is by size --
  list screens and long forms get their own `.html`, dialogs and small primitives stay inline.
- Control flow is entirely the new block syntax: **512 `@if`**, **228 `@for`**, **165 `@else`**,
  8 `@switch`, 3 `@empty`. There is not one `*ngIf` or `*ngFor` in the tree. No `@defer` is used.
- No `changeDetection: OnPush` is declared anywhere -- under zoneless it is not needed, because
  change detection is driven by signal reads.

### 1.4 State

State is held in signals on the component, with no store library.

| API | Occurrences in `src/app` (specs excluded) |
| --- | --- |
| `signal(` | 293 |
| `computed(` | 271 |
| `input(` / `input.required` | 46 / 26 |
| `effect(` | 19 |
| `viewChild` | 9 |
| `toSignal` | 5 |
| `output(` | 3 |
| `model(` | 3 |
| `linkedSignal` / `resource(` | 0 |

The house pattern on a list screen is: a `signal` per raw field
(`rows`, `loading`, `error`, `search`, filters), one `computed` called `filtered` that applies
the filters, and a second `computed` called `paged` that slices `filtered` through a pager
helper. `scheduler1/next/src/app/features/tasks/tasks.ts:71-90` is the smallest complete example;
`scheduler1/next/src/app/features/jobs/jobs.ts` is the largest.

Cross-component state lives in four root services: `AuthService`, `ThemeService`,
`JobEventsService`, `ToastService` (plus `DictationService`, `StorageService`,
`KafkaSecretService`, `DashboardService`, which are feature-scoped but `providedIn: 'root'`).

`model()` is used exactly where two-way binding is genuinely wanted:
`MineFilter.only`/`.hidden`, `ViewToggle.value`, `PhoneInput.value`.

### 1.5 HTTP (`src/app/core/api`)

The whole HTTP layer is one 15-line file, `scheduler1/next/src/app/core/api/api.config.ts`:

```ts
export const API_BASE = `${window.location.protocol}//${window.location.hostname}:9098/api/v1`;
```

The base URL is computed at **runtime** from `window.location`, deliberately, so one bundle
works on localhost, staging and an on-premise install. The port `9098` is hard-coded.

Every endpoint answers with the same envelope:

```ts
interface ApiResponse<T> { status: 'SUCCESS' | 'ERROR'; message: string; data?: T; }
```

`status`, not the HTTP status, is the success signal. `API_SUCCESS = 'SUCCESS'` is compared at
roughly a hundred call sites.

There is **no generated client and no per-feature HTTP service by default**. Components inject
`HttpClient` directly and build the URL from `API_BASE`. The four exceptions that do wrap HTTP
are `DashboardService` (`features/dashboard/dashboard.service.ts`), `StorageService`
(`features/objects/storage.service.ts`), `KafkaSecretService`
(`features/settings/kafka/kafka-secret.service.ts`) and `AuthService`.

Endpoints in use, grouped by controller (counted from `API_BASE}/…` string literals):

`sourceJob.json`, `sourceTask.json`, `setting.json`, `dashboard.json`, `appUser.json`,
`tenant.json`, `tenantRequest.json`, `notification.json`, `storage.json`,
`storageConnection.json`, `kafkaConnectionProfile.json`, `kafkaSecret.json`, `message.json`,
`aiAgent.json`, `ollama.json`, `fileChat.json`, `fileShare.json`, `dynamicForm.json`,
`taskForm.json`, `queryEngine.json`, `report.json`, `documentConverter.json`,
`audioTranscript.json`, `textCleaner.json`, `auth.json`, plus `/ws`.

### 1.6 Auth (`src/app/core/auth`)

Four files: `auth.models.ts`, `auth.service.ts`, `auth.guard.ts`, `auth.interceptor.ts`.

**Roles** (`auth.models.ts:1-19`) are `PLATFORM_ADMIN | TENANT_ADMIN | TENANT_USER`, ranked
`2 / 1 / 0` in `ROLE_RANK` so "at least this role" is a numeric comparison rather than a list.
`ROLE_META` (`auth.models.ts:28-47`) carries the label, hint, pill class and accent colour for
each role in one table, and is re-used by the users list and the user dialog's role picker.

**The session** lives in one signal in `AuthService`
(`scheduler1/next/src/app/core/auth/auth.service.ts:39`), hydrated from `localStorage`
(`etl_auth_user`) and written back on every change. Derived state is all `computed`:
`isLoggedIn`, `role`, `isPlatformAdmin`, `isTenantAdmin`, `mustChangePassword`, `displayName`,
`initials`, `avatarUrl`.

The role is **read from the JWT, not from the stored blob**
(`auth.service.ts:20-31`, `roleFromToken`): the payload segment is base64url-decoded and its
`userRole` claim checked against `ROLE_RANK`; anything unreadable means no role at all. The
comment states the reason -- the localStorage blob's own `userRole` could be rewritten in
devtools to open the admin menu.

Capability computeds (`auth.service.ts:87-98`) name the API they stand for rather than a role:
`canManageTasks`, `canManageQueries`, `canManageAgents`, `canManageForms`, `canManageUsers`,
`canManageTenants`. Templates gate write controls on these.

The avatar is fetched as a blob through `HttpClient` in an `effect`
(`auth.service.ts:139-154`) rather than pointed at by an `<img src>`, because an `<img>` cannot
carry the bearer token. The effect depends on a value-compared `computed`
(`auth.service.ts:125-130`) of just `{bucket, key}`, so a token refresh does not re-fetch.

**Guards** (`auth.guard.ts`):

| Guard | Kind | Behaviour |
| --- | --- | --- |
| `authGuard` | `CanActivateFn` | Not signed in -> `/login?returnUrl=<state.url>` |
| `roleGuard` | `CanActivateFn` | Reads `route.data.minRole`; `!auth.hasAtLeast(min)` -> `/unauthorized`. Must sit on the route carrying the data, not a parent. |
| `passwordChangeGuard` | `CanActivateChildFn` | While `mustChangePassword()`, every child route except `/profile` redirects to `/profile` |
| `anonymousOnly` | `CanMatchFn` | Lets `/` and `/login` mean two different things without a redirect loop |

**Interceptor** (`auth.interceptor.ts`) does three things:

1. Attaches `Authorization: Bearer <accessToken>` to every request.
2. `withUsableBody` (lines 28-39): a 200 with an empty/non-JSON body is rewritten to
   `{status:'ERROR', message:'The server returned an empty response.'}` so the ~98 call sites
   that read `response.status` off the body do not crash on `null`. A 204 is left alone.
3. A **single-flight refresh queue** (lines 18-19, 72-133). One module-level `refreshInFlight`
   flag plus a `Subject<string|null>`; parallel 401s queue on the subject and replay with the
   new token. The subject is replaced after each cycle and can be `error()`ed, so a failed
   refresh fails the queue instead of leaving components on a spinner forever. After a
   successful refresh, only a *second* 401 on the retry logs out -- any other status is
   surfaced as-is.
4. It also watches for `/appUser.json/changeOwnPassword` succeeding and calls
   `auth.passwordChanged()` (lines 62-64), because the guard would otherwise hold the session
   on `/profile` until the next sign-in.

### 1.7 Websocket (`src/app/core/socket`)

One file, `scheduler1/next/src/app/core/socket/job-events.service.ts` -- a root singleton STOMP
client over SockJS at `${API_BASE}/ws` (line 23).

- Destination is chosen by role (lines 47-58): `/topic/jobs.all` for a platform admin,
  `/topic/jobs.${tenantId}` otherwise. The role comes from `AuthService` (i.e. the token), not
  the stored blob.
- The connection follows a value-compared `computed` of `{destination, token}` (lines 69-71),
  inside an `effect` -- so it connects on sign-in, reconnects on token refresh, tears down on
  sign-out, and is *not* torn down by an unrelated write to the stored user (rename, new
  avatar, password-debt cleared).
- `reconnectDelay: 5000`, heartbeats 10 s both ways, STOMP frame logging suppressed.
- Exposes `events: Observable<JobEvent>` and `connected: Signal<boolean>`.
- `JobEvent` types seen in code: `job.status`, `job.log`, `job.deleted`, `job.toggled`, and
  `job.updated` is handled in `jobs.ts` though not listed in the union.

**Only one screen consumes it**: `features/jobs/jobs.ts`. It patches rows in place
(`applyEvent`), and re-reads the whole list after a *gap* in the connection (constructor
effect, `jobs.ts:236-256`) because a dropped socket loses events with no replay.

### 1.8 Tailwind 4 and the design tokens

`scheduler1/next/src/styles.css` is 1219 lines and is the entire design system. There is no
`tailwind.config.js`; configuration is the CSS-first `@theme` block.

- **`@theme` (lines 14-88)** declares the palette: `ink-50…950` (blue-biased neutrals, plus a
  bespoke `ink-450`), `brand-50…900` (indigo, `#4f46e5` at 500), and semantic `ok`/`warn`/`crit`
  families. It also *declares* the semantic roles (`--color-page`, `--color-raised`,
  `--color-subtle`, `--color-primary`, `--color-accent`, …) so they become real Tailwind
  utilities (`bg-raised`, `border-subtle`, `text-muted`, `text-accent`).
- **`:root` (lines 93-138)** and **`html.dark` (lines 140-172)** give those roles their values
  per theme. Light also sets `color-scheme: light` and swaps the OS-drawn select chevron and
  date glyph for inline SVG data URIs.
- Contrast is documented per token with measured ratios (e.g. `--text-secondary` is `ink-600` at
  7.35:1 on white; `--accent-text` becomes `brand-300` at 7.45:1 in dark, where `brand-600`
  measured 2.16:1).
- **Chart series tokens** are separate and per-theme: `--chart-0…5` (line 1070 light, 1103 dark)
  for categorical data, and `--series-*` (line 1089 light, 1097 dark) for the eight run statuses,
  held to a 3:1 non-text contrast floor.
- **Component primitives are CSS classes, not components**, stated at lines 203-210: `.btn` +
  `.btn-primary/-default/-ghost/-danger/-intent-*`, `.card`, `.input`, `.label`, `.field`,
  `.pill` + tone variants, `.table-modern`, `.tabs`, `.seg`, `.dropzone`, `.progress`, `.mono`,
  `.spinner`, `.md-*` (markdown), `.log-*`, `.guide-*`, `.stat-*`. Anything with behaviour
  (overlays, toasts) is a real component on the CDK.
- Button weight is a documented decision, not taste (lines 232-247), including the finding that
  an audit found 59.7% of 186 buttons were ghost.

---

## 2. Every route

From `scheduler1/next/src/app/app.routes.ts`. Six top-level routes, one shell with **38 children**
(37 screens plus an empty redirect), and a `**` catch-all. Role column is what `roleGuard` reads
from `data.minRole`; the hierarchy means `TENANT_ADMIN` also admits `PLATFORM_ADMIN`.

### 2.1 Public (outside the shell)

| Path | Component | Role required | What the screen does |
| --- | --- | --- | --- |
| `login` | `features/login/login.ts` `Login` | none, `canMatch: anonymousOnly` | Username/password reactive form; on success follows `returnUrl` only if it starts with a single `/` (open-redirect guard, `login.ts:41-47`) |
| `login` (2nd entry) | -- | -- | Redirect to `/dashboard`; only matched when `anonymousOnly` refused the first, i.e. already signed in |
| `` (pathMatch full) | `features/landing/landing.ts` `Landing` | none, `anonymousOnly` | Public marketing front door with a hero, a live `ConsolePreview` mock, capability grid and step sequence |
| `request-workspace` | `features/tenant-request/request-workspace.ts` `RequestWorkspace` | none (public) | Reactive form posting `tenantRequest.json/submit`; acknowledgement is deliberately identical whether or not the email is known |
| `docs` | `features/docs/docs.ts` `Docs` | none (public) | Setup guide: 9 steps (`request`, `tenant`, `storage`, `task-type`, `task`, `job`, `watch`, `report`, `optional`) plus a `reference` section, with a scroll-spy table of contents and a per-step theme-aware screenshot slot (wired, currently unused -- see Risks) |
| `f/:uuid` | `features/forms/form-fill.ts` `FormFill` | none (public) | Renders a shared dynamic form by uuid via `dynamicForm.json/fetchFormByUuid` |
| `**` | -- | -- | Redirect to `` |

### 2.2 Inside the shell (`features/shell/shell.ts`, `canActivate: authGuard`, `canActivateChild: passwordChangeGuard`)

| Path | Component | Role required | What the screen does |
| --- | --- | --- | --- |
| `` (pathMatch full) | -- | signed in | Redirect to `dashboard` |
| `dashboard` | `features/dashboard/dashboard.ts` `Dashboard` | signed in | Date-range KPI tiles, two donuts, a daily bar chart, an hour x weekday heatmap, and a click-through per-hour job breakdown table with a summed footer; every count links into run history |
| `jobs` | `features/jobs/jobs.ts` `Jobs` | signed in | The main list. Live counts from the socket, stalled-run banner, filters, "Only mine", bulk select/run/delete, expandable row panel with recent-run bars and task payload, row menu (run/skip/clone/notifications/toggle/delete), embedded assistant panel |
| `jobs/new` | `features/jobs/edit/job-edit.ts` `JobEdit` | signed in | Reactive form: name, task, execution type, priority 1-9, status, three email switches, and a nested scheduler group with a plain-language schedule summary |
| `jobs/:jobId/edit` | `JobEdit` | signed in | Same form, prefilled from `fetchSourceJobDetailWithSourceJobId` |
| `jobs/:jobId/assistant` | `features/jobs/assistant/job-assistant.ts` `JobAssistant` | signed in | Rule-based Q&A over one job's own record and runs (no model call), with preset questions, dictation, and CSV/XLSX run export |
| `jobs/:jobId/runs/:jobQueueId/logs` | `features/jobs/logs/job-logs.ts` `JobLogs` | signed in | One run's audit log in three views (timeline / table / console), 5 s auto-refresh while the run is not terminal, gap analysis showing where the run sat waiting |
| `queue` | `features/queue/queue.ts` `Queue` | signed in | Q-messages over a date range with status chips, insight charts (status mix, duration buckets, per-job, per-day, flag splits), and force-to-`Failed`/`Interrupt` for stuck runs |
| `jobs/history` | `features/jobs/history/job-history.ts` `JobHistory` | signed in | Same screen without a job -- the dashboard TOTAL row drills into an hour across every job |
| `jobs/:jobId/history` | `JobHistory` | signed in | One job's runs, with an outcome donut, duration trend, flag split, expandable status messages, and drill-down narrowing by `targetDate`/`targetHr`/`jobStatus` query params |
| `tasks` | `features/tasks/tasks.ts` `Tasks` | signed in (list is `TENANT_USER` on the server) | Source task list, table/cards, expandable panel showing the jobs linked to a task; write controls gated in-template on `auth.canManageTasks()` |
| `tasks/new` | `features/tasks/edit/task-edit.ts` `TaskEdit` | **TENANT_ADMIN** | Task editor: name/type/status/pipeline/group/home page, a tag-row FormArray, a server-rendered XML preview (`setting.json/xmlCreateChecker`), and an optional pipeline-driven form that authors the tag rows |
| `tasks/:taskDetailId/edit` | `TaskEdit` | **TENANT_ADMIN** | Same, prefilled |
| `tasks/bulk` | `features/bulk/bulk-transfer.ts` `BulkTransfer` (`data.kind='task'`) | **TENANT_ADMIN** | Download template, export all, drag-and-drop upload with progress |
| `jobs/bulk` | `BulkTransfer` (`data.kind='job'`) | signed in | Same three operations against the sourceJob endpoints |
| `objects` | `features/objects/objects.ts` `Objects` | **TENANT_USER** | Object browser: bucket picker, breadcrumbs, search + date filters, upload, new folder, rename, delete, multi-select download/email, preview dialog, and a per-file AI chat panel |
| `reports` | `features/reports/reports.ts` `Reports` | signed in | Client-side pivot over run rows: pick row dimension, column dimension and one of 12 measures; 10 chart kinds; cell drill-down drawer; server-side export |
| `tools/query` | `features/tools/query-engine/query-engine.ts` `QueryEngine` | signed in (open on purpose) | Three tabs -- Queries, Connections, Runs. Reads and execute are `TENANT_USER`; create/edit/delete gated in-template on `auth.canManageQueries()` |
| `tools/search` | `features/tools/search-engine/search-engine.ts` `SearchEngine` | **PLATFORM_ADMIN** | Ad-hoc read-only SQL with a client-side write-keyword guard, result grid, filter, pager, copy |
| `tools/converter` | `features/tools/converter/converter.ts` `Converter` | signed in | Upload a document, pick an output format, convert; plus a task list of previous conversions with preview/download/delete |
| `tools/transcript` | `features/tools/transcript/transcript.ts` `Transcript` | signed in | Speech-to-text from an upload or a bucket object, optional timestamps, segmented output |
| `tools/cleaner` | `features/tools/cleaner/cleaner.ts` `Cleaner` | signed in | Paste text, `textCleaner.json/clean`, copy the result |
| `ai/agents` | `features/ai/agents/agents.ts` `Agents` | signed in (open on purpose) | AI agent list (provider, model, target file types, JSON mode, status); add/edit/delete gated on `auth.canManageAgents()` |
| `ai/models` | `features/ai/models/models.ts` `Models` | **TENANT_ADMIN** | Installed Ollama models plus a curated 16-entry catalogue to pull from |
| `settings/task-types` | `features/settings/task-types/task-types.ts` `TaskTypes` | **TENANT_ADMIN** | Source task types, their Kafka topic/partition and profile, and which tasks use each |
| `settings/forms` | `features/settings/forms/task-forms.ts` `TaskForms` | **TENANT_ADMIN** | Per-pipeline form definitions that drive the task editor |
| `settings/dynamic-forms` | `features/forms/dynamic-forms.ts` `DynamicForms` | **TENANT_ADMIN** | Shareable form builder with a live preview, share link, submissions list, and "use a submission as task configuration" |
| `settings/lookup` | `features/settings/lookup/lookup.ts` `Lookup` | **TENANT_ADMIN** | Parent/child lookup key-value data; children fetched per parent |
| `settings/kafka` | `features/settings/kafka/kafka-connections.ts` `KafkaConnections` | **TENANT_ADMIN** | Kafka profiles: bootstrap servers, security protocol, SASL, TLS material, default flag, test connection |
| `settings/xml` | `features/settings/xml-builder/xml-builder.ts` `XmlBuilder` | **TENANT_ADMIN** | Six blank tag rows -> validated -> `setting.json/xmlCreateChecker` -> copyable XML |
| `admin/storage` | `features/admin/storage/storage-connections.ts` `StorageConnections` | **TENANT_ADMIN** | S3/Azure/MinIO/FTP/FTPS connections, bucket discovery, test, clone, bulk test, Kafka-dependency warnings |
| `admin/users` | `features/admin/users/users.ts` `Users` | **TENANT_ADMIN** | User list with avatars, per-user workload stats, role/status/tenant filters, sort, pager, add/edit, status change, password reset |
| `admin/tenants` | `features/admin/tenants/tenants.ts` `Tenants` | **PLATFORM_ADMIN** | Tenants with resource counts (users, jobs, tasks, task types, buckets, Kafka), cards by default, add/edit/status/delete |
| `admin/tenant-requests` | `features/tenant-request/tenant-requests.ts` `TenantRequests` | **PLATFORM_ADMIN** | Inbound workspace requests; approve creates the tenant + first admin, reject collects an optional note |
| `admin/settings` | `features/settings/hub/settings-hub.ts` `SettingsHub` | **TENANT_ADMIN** | A 9-card index of every configuration area, filtered by role |
| `notifications` | `features/notifications/notifications.ts` `Notifications` | signed in | Notification list, unread filter, type filter, mark read / mark all read, click-through with legacy route rewriting |
| `profile` | `features/profile/profile.ts` `Profile` | signed in | Own details (name, phone, position), avatar upload/remove, password change, recent activity with an outcome donut. The only page reachable while `mustChangePassword` is set |
| `unauthorized` | `features/unauthorized/unauthorized.ts` `Unauthorized` | signed in | States the current role, offers Back and Dashboard |

Routing details worth noting:

- Every child is `loadComponent` -- the whole console is lazily chunked per screen.
- `withComponentInputBinding()` means route params, query params **and route `data`** bind to
  signal inputs: `BulkTransfer.kind` comes from `data.kind`; `JobHistory` reads `jobStatus`,
  `targetDate`, `targetHr` straight from query params.
- `jobs/history` and `jobs/bulk` are literal two-segment paths and there is no `jobs/:jobId`
  route, so nothing shadows them.

---

## 3. Feature directories

Twenty directories under `scheduler1/next/src/app/features`.

| Directory | Files | Routes it serves |
| --- | --- | --- |
| `admin/` | `storage/` (`storage-connections.ts/.html`, `connection-dialog.ts/.html`, `clone-dialog.ts`, `kafka-dependents.ts`, 4 specs), `users/` (`users.ts/.html`, `user-dialog.ts/.html`, 1 spec), `tenants/` (`tenants.ts/.html`, `tenant-dialog.ts`) | `/admin/storage`, `/admin/users`, `/admin/tenants` |
| `ai/` | `agents/` (`agents.ts/.html`, `agent-dialog.ts/.html`), `models/` (`models.ts/.html`) | `/ai/agents`, `/ai/models` |
| `bulk/` | `bulk-transfer.ts/.html` | `/jobs/bulk`, `/tasks/bulk` (one component, two `data.kind` values) |
| `dashboard/` | `dashboard.ts/.html`, `dashboard.service.ts` | `/dashboard` |
| `docs/` | `docs.ts` (474 lines, inline template + content data) | `/docs` |
| `forms/` | `dynamic-forms.ts/.html`, `dynamic-form.model.ts`, `dynamic-form-dialog.ts`, `form-renderer.ts`, `form-fill.ts`, `submission-to-task-dialog.ts` | `/settings/dynamic-forms`, `/f/:uuid` |
| `jobs/` | `jobs.ts/.html`, `job-actions.ts`, `stalled.ts`, `notify-summary.ts`, `notify-dialog.ts`; `edit/`, `history/`, `logs/`, `assistant/` (`job-assistant.ts/.html`, `.intents.ts`, `.answers.ts`); 6 specs | `/jobs`, `/jobs/new`, `/jobs/:id/edit`, `/jobs/:id/assistant`, `/jobs/:id/runs/:qid/logs`, `/jobs/history`, `/jobs/:id/history` |
| `landing/` | `landing.ts`, `console-preview.ts` | `/` (public); `ConsolePreview` is also used by `/login` |
| `login/` | `login.ts/.html` | `/login` |
| `notifications/` | `notifications.ts/.html`, `notification-links.ts` (+ spec) | `/notifications`; `notification-links.ts` is shared with the header bell |
| `objects/` | `objects.ts/.html`, `storage.service.ts`; `chat/` (`file-chat.ts/.html`, `chat-export.ts`, 2 specs); `dialogs/` (`prompt-dialog.ts`, `share-dialog.ts`); `preview/` (`preview-dialog.ts/.html`, `pdf-viewer.ts`, `audio-player.ts`) | `/objects`. `StorageService` and `PreviewDialog` are also used by `/tools/converter`, `/tools/transcript` and `/profile` |
| `profile/` | `profile.ts/.html` | `/profile` |
| `queue/` | `queue.ts/.html` | `/queue` |
| `reports/` | `reports.ts/.html`, `pivot.ts` (+ spec), `report-chart.ts` | `/reports` |
| `settings/` | `hub/settings-hub.ts`; `task-types/`; `forms/` (`task-forms.ts/.html`, `task-form-dialog.ts`); `kafka/` (`kafka-connections.ts/.html`, `kafka-dialog.ts`, `kafka-profile-form.ts`, `kafka-tls-section.ts` (978 lines), `kafka-secret.service.ts`, 2 specs); `lookup/`; `xml-builder/` | `/admin/settings`, `/settings/task-types`, `/settings/forms`, `/settings/kafka`, `/settings/lookup`, `/settings/xml` |
| `shell/` | `shell.ts/.html`, `notification-bell.ts` | The authenticated layout for every route in §2.2 |
| `tasks/` | `tasks.ts/.html`; `edit/task-edit.ts/.html` | `/tasks`, `/tasks/new`, `/tasks/:id/edit` |
| `tenant-request/` | `tenant-requests.ts/.html`, `request-workspace.ts`, `reject-dialog.ts` | `/admin/tenant-requests`, `/request-workspace` |
| `tools/` | `converter/`, `cleaner/`, `transcript/` (+ spec), `search-engine/`, `query-engine/` (`query-engine.ts/.html`, `types.ts`, `query-dialog.ts`, `db-connection-dialog.ts`, `query-schedule-dialog.ts`) | `/tools/converter`, `/tools/cleaner`, `/tools/transcript`, `/tools/search`, `/tools/query` |
| `unauthorized/` | `unauthorized.ts` | `/unauthorized` |

### The shell's navigation

`features/shell/shell.ts:48-137` holds the nav as data, grouped by task rather than by backend:
`Dashboard`, `Pipelines` (Source Jobs, Source Tasks, Queue, Reports), `Object Browser`,
`Tools` (Query Engine, Search Engine, Document Converter, XML Configuration, Audio Transcript,
Content Cleaner), `AI` (AI Agents, Models), `Configuration` (7 entries), `Administration`
(Users, Tenants, Workspace Requests). Each child carries a one-line `hint` shown in the dropdown.
`nav()` filters by `adminOnly` / `platformOnly` so nothing renders that would 403, and drops a
group that ends up empty. Dropdowns close on any outside click (`@HostListener('document:click')`)
and on Escape. There is a separate mobile nav below `xl`.

---

## 4. Shared UI inventory

### 4.1 `src/app/shared/ui` -- 15 components, 1 directive, 2 services, 5 helper modules

| File | Selector / export | What it is for |
| --- | --- | --- |
| `icon.ts` | `<app-icon>` | The whole icon set -- 76 stroke glyphs on a 24x24 grid at stroke-width 1.9, sized in `em` so an icon tracks its button's type size. Logs a dev-mode error for an unknown name (an unknown name used to render an empty `<svg>`) |
| `field.ts` | `<app-field>` | Label + projected control + hint/error in one place. Mirrors the reactive control's `events` stream into a signal (lines 55-57) so the message actually recomputes; errors stay hidden until the field is touched or the form submitted; the wrapper carries the invalid border so every control type gets it |
| `data-table.ts` | `<app-table-shell>` | The chrome for every list screen: titled card, `[toolbar]` slot, optional `[subbar]` slot, and the three states -- loading spinner, error with a Try again button, empty with an icon and an `[empty-action]` slot. Rows scroll in their own box (`scrollRows`, default true) so toolbar and pager stay put. Also renders "(shown of total)" |
| `form-dialog.ts` | `<app-form-dialog>` | The shell for create/edit dialogs: header, scrolling body, footer with Cancel + a Save that shows a spinner and "Saving…". `size="wide"` (58 rem) vs default (34 rem); `max-h-[85vh]`; `[footer-start]` slot for Test/Validate/Preview buttons |
| `confirm.ts` | `<app-confirm>` + `confirmWith()` | Yes/no dialog. `confirmWith(dialog, options)` returns a promise so callers write `if (!await confirmWith(...)) return;`. `danger: true` gives the only `.btn-danger` in the app |
| `status-pill.ts` | `<app-status>` | One table (lines 33-61) decides what every status looks like: 8 run states, 5 request/decision states, 6 entity states. Statuses in a family are separated by weight (`solid`) and by their own glyph, so red/green is not the only cue. `quiet` renders a dot + text instead of a chip for the unremarkable tones, but never for a run's own status |
| `stat-tile.ts` | `<app-stat-tile>` | The KPI tile above a table: label, value, optional foot line, optional tinted glyph (`tone`) |
| `pagination.ts` | `<app-pagination>` | Prev/Next, "Page x of y", "a-b of n", per-page select. Hides itself entirely when the total fits the smallest page size |
| `pager.ts` | `createPager<T>()` | The paging *logic* as a helper, not a component, so the table keeps its own markup. `slice()` clamps the page against the row count so a filter that shrinks the list cannot strand you on a blank page. `PAGE_SIZES = [50,100,150,200]` |
| `sort.ts` | `createSort<T>()` | Column sorting helper: `toggle`, `iconFor`, `indicator`, `apply`. Nulls always sort last; numbers compare numerically, strings via `localeCompare` with `numeric: true` |
| `view-toggle.ts` | `<app-view-toggle>` | Table-or-cards segmented control. `key` persists the choice per screen under `etl.view.<key>` in `localStorage`, wrapped in try/catch |
| `mine-filter.ts` | `<app-mine-filter>` + `isMine()` | "Only mine" toggle, matched on `createdBy` id rather than display name. Deliberately **not** persisted |
| `avatar.ts` | `<app-avatar>` | Someone's picture or their initials. Two ways in -- `appUserId` (server resolves the key) or `bucket`+`key`. Always via `HttpClient` so the token is attached; revokes its blob URL on destroy so a user list does not leak one per row |
| `phone-input.ts` | `<app-phone-input>` | Country select + national number producing one E.164 string, validated by libphonenumber (the same metadata the server uses). Countries sorted by name |
| `markdown.ts` | `<app-markdown>` | Parses the subset a model actually produces (fenced code, inline code, bold, italic, links, headings, lists, rules) into blocks and renders them through Angular templates -- **never** `innerHTML`, so model output cannot inject markup. Code blocks get a Copy button |
| `toast-host.ts` / `toast.service.ts` | `<app-toast-host>` / `ToastService` | Replaces ngx-toastr (which pins Angular 21). `success/error/warn/info`; errors live 7 s, everything else 4 s; host is `role="status" aria-live="polite"` |
| `route-progress.ts` | `<app-route-progress>` | Top-of-page bar driven by the router lifecycle; trickles asymptotically toward 90%, snaps to 100% on `NavigationEnd`/`Cancel`/`Error`, with a 400 ms minimum on-screen time |
| `stick-to-bottom.ts` | `[appStickToBottom]` directive | Keeps a log pinned to its newest line, and stops the moment the reader scrolls up. Walks up the DOM to find the element that actually scrolls (often the table shell, not the host) |
| `dictation.service.ts` | `DictationService` | Web Speech wrapper shared by the file chat and the job assistant. One owner at a time; speech is appended to what is typed; `supported` hides the button where the API is absent |
| `clipboard.util.ts` | `copyText()` | Async Clipboard API with a hidden-textarea fallback; returns whether the copy actually happened |
| `format-size.ts` | `formatSize()` | Byte counts. `0` prints "0 B"; only a missing value gets an em dash |
| `topic.ts` | `parseTopicPartition()` / `formatTopicPartition()` | `topic=name&partitions=[0]` in and out. Reading is looser than writing, so a legacy value still renders |

`src/app/shared/testing/memory-storage.ts` -- `useMemoryStorage()`, a complete in-memory
`Storage` stubbed per test. Used by `auth.service.spec.ts` only.

### 4.2 `src/app/shared/charts` -- 5 components + 1 helper

| File | Selector | What it draws |
| --- | --- | --- |
| `bar-chart.ts` | `<app-bar-chart>` | Vertical bars, linear scale with a 3 px floor so a tiny value stays visible. Labels are *dropped* rather than shrunk past 24 bars (values) / 16 bars (names), and a repeated name is drawn only on the first of its run. Bars can be clickable and emit `barClicked` |
| `donut.ts` | `<app-donut>` | 104 px ring with a single-line legend beside it, compact centre total (`1.2k`, `3.4M`), optional `colorFor` so statuses keep their colour. Each slice carries an SVG `<title>`; the whole SVG has `role="img"` and an aria-label listing every value |
| `heatmap.ts` | `<app-heatmap>` | 7 days x 24 hours as a CSS grid. Intensity is square-rooted so quiet hours stay distinguishable from empty ones. Cells are real buttons (hover/focus/click), with an `sr-only` tooltip, a reserved legend row that does not jump, and a "Busiest hour" readout |
| `ranked-bar.ts` | `<app-ranked-bar>` | Horizontal bars, longest first, one 22 px row each. Rolls the tail into "Other (n)". Bars scale against the largest row, not the total |
| `split-bar.ts` | `<app-split-bar>` | One bar per row split between two opposed outcomes (ran/skipped, sent/not), with a shared baseline and a two-item legend |
| `status-color.ts` | `statusColor(name, index)` | The single status -> colour mapping, returning `--series-*` tokens (theme-aware) and falling back to `--chart-N` for anything with no status meaning. Used by charts on the dashboard, jobs, queue, history, reports, profile and the assistant |

`features/reports/report-chart.ts` is a **second, separate** chart component (404 lines): one
hand-built SVG renderer covering ten kinds (grouped, stacked, 100% stacked, donut, pie, line,
area, ranked, heat, radar) over the report pivot. It does not use `shared/charts`.

---

## 5. Forms, tables, modals -- the patterns

### 5.1 Forms

Two styles, chosen per case:

- **Reactive (`ReactiveFormsModule`) -- 17 files.** Every real create/edit form:
  `login`, `job-edit`, `task-edit`, `request-workspace`, and the dialogs for connection, tenant,
  user, agent, task-type, task-form, dynamic-form, lookup, kafka, kafka-tls-section,
  db-connection, query, query-schedule.
- **Template-driven (`FormsModule` alone) -- 5 files.** `clone-dialog`, `form-renderer`,
  `submission-to-task-dialog`, `reject-dialog`, `phone-input`. These are short or dynamic
  (`form-renderer` builds inputs from a field definition at runtime).

The standard reactive-form shape:

```
readonly form: FormGroup = this.fb.group({ ... Validators ... });
readonly saving = signal(false);
readonly submitted = signal(false);

save(): void {
  this.submitted.set(true);
  if (this.form.invalid) { this.form.markAllAsTouched(); this.toast.error('Check the highlighted fields.'); return; }
  ...
}
```

Every field is wrapped in `<app-field>` with `[control]`, `[submitted]`, `[required]`, an
optional `hint`, and optional `[errorMessages]` overrides keyed by validator name. Layout uses
`.form-stack` (20 px between fields), `.form-grid` (container-query columns), `.form-section`
(24 px + rule), `.form-actions`.

Notable form logic:

- `job-edit.ts:28-32` -- a cross-field `endAfterStart` validator on the scheduler group; the
  message `'The end date is before the start date'` is one of `Field`'s built-in messages.
- `job-edit.ts` `summary()` -- restates the schedule in plain language before saving.
- `task-edit.ts` -- a `FormArray` of tag rows plus a `formData` `FormGroup` built at runtime from
  whichever task form the chosen pipeline has; `syncFormToTags()` writes the answers back into
  the tag rows, so downstream code knows nothing about forms.
- `kafka-profile-form.ts` -- validation rules extracted from the dialog so they can be tested:
  `protocolNeedsSasl`, `protocolNeedsSsl`, `additionalPropertiesJson` (runs the same Gson-shaped
  parse the server does, before the request leaves), `profilePayload`, `combinationSummary`.
- `connection-dialog.ts:15-22` -- `azureCredentialPresent`, a pair-validator because Azure takes
  either a connection string or account name + key.
- Secrets are never returned by the API. Dialogs use `*Configured` booleans and treat an empty
  field as "keep the stored one"; `CLEAR_FLAGS` in `kafka-profile-form.ts` exist so a credential
  can actually be removed.

### 5.2 Tables

**19 screens** import `TableShell`. The pattern is:

```html
<app-table-shell heading="…" [loading]="loading()" [error]="error()"
                 [isEmpty]="!filtered().length" [shown]="filtered().length" [total]="rows().length"
                 [emptyMessage]="hasFilters() ? 'No … match the current filters.' : 'No … yet.'"
                 emptyIcon="…" (retry)="load()">
  <ng-container toolbar> …filters, search, Only mine, Clear… </ng-container>
  <table class="table-modern"> … </table>
  <app-pagination pager … />
</app-table-shell>
```

Consistent details:

- `.table-modern` is 12 px body / 11 px uppercase headers, chosen deliberately for dense
  operational tables (`styles.css:779-784`).
- `.col-pin-right` (`styles.css:832-839`) sticks the actions column so it stays reachable when
  the table scrolls sideways -- with its own hover background, because a sticky cell floats.
- Row actions are a CDK menu (`CdkMenuTrigger`/`CdkMenu`/`CdkMenuItem`), used on 11 screens.
  `styles.css` forces `.cdk-menu { width: max-content }` because the overlay otherwise sized
  menus 500-718 px wide.
- Expandable detail rows (jobs, tasks, lookups, tenant requests) fetch their extra data on open
  and cache it -- jobs caches payloads **by task id**, not job id, because many jobs share a task.
- Sorting where present uses `createSort` on a `.th-sort` header; paging uses `createPager` +
  `<app-pagination>`; layout switching uses `<app-view-toggle>` (10 screens).
- Bulk selection is a `signal<Set<id>>` with `allOnPageSelected` / `someOnPageSelected`
  computeds, and select-all covers **the page in view**, not the whole filtered list.

### 5.3 Modals and dialogs

All overlays are `@angular/cdk/dialog` (`Dialog`, `DialogRef`, `DIALOG_DATA`). There are **35
`dialog.open(...)` call sites** across 13 screens plus the shared `confirmWith` helper. Three
families:

1. **`confirmWith(dialog, {...})`** -- the promise-wrapped yes/no. Used before every destructive
   or irreversible action (delete job/task/agent/connection/tenant/lookup/form/model, deactivate,
   suspend, force a run to Failed, bulk run, bulk delete, reset password). The body always names
   the consequence, e.g. jobs: *"Slots that pass while it is off are recorded as Missed rather
   than replayed."*
2. **`<app-form-dialog>` dialogs** -- 16 files. Create/edit forms with a consistent header,
   scrolling body and footer, plus `[footer-start]` for Test connection / Validate / Preview.
3. **Bespoke dialogs** -- `PromptDialog` (single text input, used for new folder / rename /
   reset-password reason), `ShareDialog` (email a ZIP of selected objects), `PreviewDialog`
   (full object preview with `PdfViewer`, `AudioPlayer`, image/video/text/JSON/markdown modes).

Dialogs close with a typed result (`boolean`, `string`, `ShareResult`, `string|null`) and the
caller reloads on truthy. `RejectDialog` closes with the note text rather than a boolean,
explicitly so the caller cannot forget to read it.

---

## 6. Cross-cutting behaviour -- what is actually implemented

### 6.1 Validation -- implemented, and centralised

`Field` (`shared/ui/field.ts:65-85`) is the single place a validation message is produced. It
covers `required`, `email`, `min`, `max`, `minlength`, `pattern`, the custom `endBeforeStart`,
and falls back to `'Check this value'`. Per-error overrides come in through `[errorMessages]`.
Errors are withheld until the control is touched or the form submitted. The red border is on the
wrapper (`.field-invalid`), not opted into per control -- the comment records that the previous
opt-in had been added to 2 of 11 controls on the job form.

Client-side guards that exist *in addition* to server validation, and say so:

- `search-engine.ts` blocks write keywords before the request goes out.
- `xml-builder.ts` `problems()` checks duplicate keys, invalid XML names, orphan parents,
  self-parenting, and "no root".
- `kafka-profile-form.ts` `additionalPropertiesJson` parses the JSON the way Gson would.
- `phone-input.ts` validates against libphonenumber rather than a length rule.
- `tasks.ts` refuses to delete a task that has linked jobs, with a message pointing at the fix.
- `dynamic-form.model.ts` `validateForm` and `FIELD_TYPES` mirror the server's allowed set.

### 6.2 Loading states -- implemented

- Route level: `RouteProgress` bar on every navigation.
- Table level: `TableShell` renders a `.spinner` ring + "Loading…" (`data-table.ts:42-46`).
- Button level: `<app-icon name="refresh" class="spin">` on Refresh, Test, Validate, Preview,
  and `saving()` on every `FormDialog` footer ("Saving…", both buttons disabled).
- Row level: `busyJob` / `busyTask` / `testing` / `running` signals hold the id currently in
  flight.
- Quiet refresh: `JobLogs.load(quiet)` keeps the list on screen during the 5 s auto-refresh
  instead of blanking it.
- `.spinner` and `.spin` both honour `prefers-reduced-motion` (`styles.css:858, 867`).

### 6.3 Empty states -- implemented, and filter-aware

`TableShell` renders an icon + message + optional action slot. Nearly every screen distinguishes
"nothing here" from "nothing matches", e.g. jobs:
`search() || statusFilter() || executionFilter() ? 'No jobs match the current filters.' : 'No jobs yet.'`
Charts have their own empty copy (`'Nothing to show in this range.'`, `'No data in this range.'`,
`'No activity in this range.'`, `'Nothing to show yet.'`). The notification bell says
"You are all caught up."

### 6.4 Error states -- implemented, with one consistent shape

- `TableShell` error state: crit alert icon, the message, and a **Try again** button wired to
  `(retry)`.
- Everything else surfaces through `ToastService`. The idiom is
  `err?.error?.message || '<plain sentence>'` -- a human fallback rather than a stack.
- The interceptor turns an empty 200 body into an error envelope so the ~98 `response.status`
  reads cannot crash.
- Some errors are deliberately swallowed with a comment saying why: the notification bell
  (`'A failing bell must not put an error in front of whatever the user is doing.'`), the
  dashboard's unread tile, the user-stats enrichment, the job-history context panel, the
  assistant's run list, and `kafkaProfilesUsing` (advisory only).
- `Profile.activityFailed` exists specifically so a failed request is not rendered as "you have
  no jobs".
- `JobLogs` refuses a URL whose ids are not numeric and explains what to do instead, rather than
  passing `"undefined"` to the server.

### 6.5 Dark / light mode -- implemented

`scheduler1/next/src/app/core/theme.service.ts` is 25 lines:

- Reads `localStorage['etl_theme']`; with nothing stored it falls back to
  `matchMedia('(prefers-color-scheme: dark)')`.
- An `effect` toggles `document.documentElement.classList` `dark` and writes the choice back.
- `toggle()` flips it. The toggle button lives in the shell header, the landing page header and
  the request-workspace header, so it is reachable signed-out as well.

Theming is token-based: `:root` and `html.dark` redefine ~20 role variables and every component
reads those, plus `color-scheme` so OS-drawn widgets (select list, date picker, scrollbars)
follow. Places where a token alone was not enough are handled explicitly and commented: pill
backgrounds are `color-mix`ed in dark, `.pill-solid-*` fills are lightened, semantic text
utilities are remapped to the `-400` steps, `.input::-webkit-calendar-picker-indicator` is
inverted, and both chart palettes have a dark variant. `Landing` and `ConsolePreview` fix their
own palettes because they sit on a hero that is dark in both themes.

### 6.6 Responsive behaviour -- implemented, mostly at three breakpoints

- Breakpoint prefixes in use: `sm:` 51, `lg:` 27, `xl:` 19, `md:` 15, `2xl:` 1.
- The shell switches from a horizontal nav to a hamburger sheet at `xl`
  (`shell.html:11`, `:110`, `:117`).
- Content is capped at `max-w-[1600px]` with `px-4 sm:px-6 lg:px-8`.
- `.form-grid` uses **container queries**, not viewport queries (`styles.css:1139-1146`):
  1 column, 2 at 30 rem, 3 at 62 rem, measured against the form -- explicitly so the same grid
  works inside a 544 px dialog and across a 1244 px page. The Kafka TLS layout does the same at
  52 rem (`styles.css:355`).
- `FormRenderer` re-implements the same idea for author-declared field widths: `--span-sm/md/lg`
  custom properties collapse 4-across to 2 to 1.
- Wide content scrolls in its own box rather than the page: `TableShell`'s `.scroll-table`,
  `overflow-x-auto` on tables, `max-h-80 overflow-y-auto` in the bell.
- Dialogs are `max-w-[calc(100vw-2rem)]` and `max-h-[85vh]`.
- Explicit fixes are commented, e.g. the dashboard date row wraps because two date fields plus
  buttons need 454 px and overflowed on a phone (`dashboard.html:9-11`).

### 6.7 Accessibility -- partially implemented

What is there (counts across all templates):

| Signal | Count |
| --- | --- |
| `aria-label` | 94 |
| `role="alert"` | 14 |
| `sr-only` | 9 |
| `aria-hidden` | 6 |
| `role="status"` | 5 |
| `aria-expanded` | 5 |
| `role="group"` | 3 |
| `aria-pressed` | 3 |
| `role="img"` | 2 |
| `role="tablist"` / `role="tab"` / `aria-selected` | 1 each |
| `role="progressbar"`, `role="note"`, `aria-live`, `aria-invalid` | 1 each |

- A global `:focus-visible` ring is defined once (`styles.css:196-200`), and `.input` gets its own
  focus shadow because a border-colour change alone was not enough to navigate by.
- `Icon` is `aria-hidden` unless given a `label`, in which case it becomes `role="img"`.
- `Field` renders `<span class="sr-only">(required)</span>` beside the visual asterisk and the
  error paragraph is `role="alert"`.
- `.sr-only` is hand-written (`styles.css:811-822`) with a comment saying it is for action columns
  whose header is otherwise announced as a blank column.
- `StatusPill` and the notification severity glyphs pair colour with shape, deliberately.
- The toast host is `role="status" aria-live="polite"`.
- Heatmap cells and chart bars are real `<button>`s with `sr-only` text and `<title>` elements.
- `prefers-reduced-motion` is honoured in four places (`.spin`, `.spinner`, `.pulse`, `.typing`,
  `.route-progress`, `.rise`).

Gaps observed:

- Only one `aria-live` region in the whole app (the toast host). Table content that changes after
  a filter or a socket event is not announced.
- The nav dropdowns are `<button>` + a plain `<div>` -- no `role="menu"`/`menuitem`, no arrow-key
  navigation, and only some carry `aria-expanded`. The CDK menu *is* used for row actions, which
  does provide keyboard semantics; the header nav does not use it (the comment at `shell.ts:159`
  says the overlay is reserved for menus that need positioning).
- `features/tools/query-engine/query-engine.html:38` is the only `role="tablist"` in the app.
  `ViewToggle` does carry `role="group"` + `aria-pressed`, but the other segmented controls do
  not: `features/jobs/logs/job-logs.html:133` (Timeline/Table/Console),
  `features/tools/converter/converter.html:10` and `features/tools/transcript/transcript.html:123`
  are bare `.seg` divs of buttons.
- Expandable table rows use `aria-expanded` in only 5 places across the app.
- No skip-to-content link, no `<main>` landmark labelling beyond the single `<main>` in
  `shell.html:154`, and no automated a11y checking in the test suite.

---

## 7. Test coverage

`npx ng test --watch=false` on 2026-09-01: **31 test files, 445 tests, all passing**, in ~3 s.

Runner is vitest 4 through `@angular/build:unit-test`, with `tsconfig.spec.json` pulling in
`vitest/globals`. 11 of the 31 files use `TestBed`; the rest are plain unit tests over exported
functions. There is **no e2e framework, no lint config, and no coverage threshold** in the repo.

### 7.1 What has tests

| Spec file | Tests | Subject |
| --- | --- | --- |
| `src/app/app.routes.spec.ts` | 2 | `/objects` minRole, `/tools/query` deliberately ungated |
| `core/auth/auth.guard.spec.ts` | 18 | all four guards |
| `core/auth/auth.interceptor.spec.ts` | 6 | token attach, refresh queue, empty-body rewrite |
| `core/auth/auth.service.spec.ts` | 9 | role-from-token, hierarchy, persistence (uses `useMemoryStorage`) |
| `features/admin/storage/clone-dialog.spec.ts` | 4 | alias pattern, payload |
| `features/admin/storage/connection-dialog.spec.ts` | 5 | provider-conditional validation |
| `features/admin/storage/kafka-dependents.spec.ts` | 9 | dependency lookup + sentence |
| `features/admin/storage/storage-connections.spec.ts` | 5 | list screen behaviour |
| `features/admin/users/user-management-scope.spec.ts` | 7 | which roles a tenant admin may grant |
| `features/jobs/job-actions.spec.ts` | 2 | the four action verb/method/path pairs |
| `features/jobs/stalled.spec.ts` | 11 | in-flight / stalled / age wording |
| `features/jobs/notify-summary.spec.ts` | 9 | chips, count, sentence |
| `features/jobs/assistant/job-assistant.intents.spec.ts` | 21 | intent classification + scope refusal |
| `features/jobs/assistant/chatbot-suite.spec.ts` | 37 | end-to-end answer composition |
| `features/jobs/assistant/csv-injection.spec.ts` | (parameterised) | CSV formula injection in `runsToCsv` |
| `features/notifications/notification-links.spec.ts` | 4 | legacy route rewriting |
| `features/objects/chat/chat-export.spec.ts` | 18 | fenced-file grammar |
| `features/objects/chat/csv-injection.spec.ts` | (parameterised) | CSV formula injection in `parseDownloadableFiles` |
| `features/reports/pivot.spec.ts` | 20 | dimensions, 12 measures, percentile, formatting |
| `features/settings/kafka/kafka-profile-form.spec.ts` | 36 | protocol rules, JSON properties, payload, clear flags |
| `features/settings/kafka/kafka-tls-section.spec.ts` | 30 | upload slots, store fields, removal semantics |
| `features/tools/transcript/transcript.spec.ts` | 7 | timestamp segmentation |
| `shared/charts/bar-chart.spec.ts` | 6 | scaling, label dropping |
| `shared/charts/status-color.spec.ts` | 5 | status -> token mapping |
| `shared/ui/format-size.spec.ts` | (parameterised) | byte formatting |
| `shared/ui/markdown.spec.ts` | 14 | the markdown parser |
| `shared/ui/pager.spec.ts` | 8 | clamping, sizing, reset |
| `shared/ui/sort.spec.ts` | 6 | null-last, numeric compare |
| `shared/ui/status-pill.spec.ts` | 10 | tone, quiet, unknown |
| `shared/ui/topic.spec.ts` | 8 | parse/format round trip |
| `shared/ui/view-toggle.spec.ts` | 11 | persistence, storage failure |

### 7.2 Features with **no** `.spec.ts` at all

Feature directories (or sub-features) with zero test files:

| Untested | Files |
| --- | --- |
| `features/dashboard` | `dashboard.ts` (282 lines), `dashboard.html`, `dashboard.service.ts` |
| `features/queue` | `queue.ts` (263 lines), `queue.html` |
| `features/tasks` | `tasks.ts` (279), `tasks.html`, `edit/task-edit.ts` (440), `edit/task-edit.html` |
| `features/jobs` (screens) | `jobs.ts` (789), `jobs.html` (455), `edit/job-edit.ts`, `history/job-history.ts` (333), `logs/job-logs.ts` (285) -- only the four helper modules and the assistant are covered |
| `features/reports` (screens) | `reports.ts` (280), `report-chart.ts` (404) -- only `pivot.ts` is covered |
| `features/forms` | `dynamic-forms.ts`, `dynamic-form.model.ts`, `dynamic-form-dialog.ts` (380), `form-renderer.ts`, `form-fill.ts`, `submission-to-task-dialog.ts` (279) |
| `features/settings/forms` | `task-forms.ts`, `task-form-dialog.ts` (385) |
| `features/settings/task-types` | `task-types.ts`, `task-type-dialog.ts` |
| `features/settings/lookup` | `lookup.ts`, `lookup-dialog.ts` |
| `features/settings/xml-builder` | `xml-builder.ts` |
| `features/settings/hub` | `settings-hub.ts` |
| `features/settings/kafka` (screen) | `kafka-connections.ts`, `kafka-dialog.ts` (339), `kafka-secret.service.ts` -- only the two rule modules are covered |
| `features/admin/tenants` | `tenants.ts` (292), `tenant-dialog.ts` |
| `features/ai` | `agents/agents.ts`, `agents/agent-dialog.ts`, `models/models.ts` |
| `features/objects` (screen) | `objects.ts` (487), `storage.service.ts`, `chat/file-chat.ts` (413), `preview/preview-dialog.ts`, `preview/pdf-viewer.ts`, `preview/audio-player.ts`, `dialogs/prompt-dialog.ts`, `dialogs/share-dialog.ts` |
| `features/tools` (rest) | `converter/converter.ts` (320), `cleaner/cleaner.ts`, `search-engine/search-engine.ts`, `query-engine/*` (5 files) |
| `features/tenant-request` | `tenant-requests.ts` (277), `request-workspace.ts`, `reject-dialog.ts` |
| `features/profile` | `profile.ts` (444), `profile.html` |
| `features/notifications` (screen) | `notifications.ts` -- only `notification-links.ts` is covered |
| `features/login` | `login.ts` -- including the `returnUrl` open-redirect guard |
| `features/landing` | `landing.ts`, `console-preview.ts` |
| `features/docs` | `docs.ts` (474) |
| `features/bulk` | `bulk-transfer.ts` |
| `features/shell` | `shell.ts` (including the role-filtered `nav()` computed), `notification-bell.ts` |
| `features/unauthorized` | `unauthorized.ts` |

Untested shared code:

- `shared/ui`: `avatar.ts`, `clipboard.util.ts`, `confirm.ts`, `data-table.ts`,
  `dictation.service.ts`, `field.ts`, `form-dialog.ts`, `icon.ts`, `mine-filter.ts`,
  `pagination.ts`, `phone-input.ts`, `route-progress.ts`, `stat-tile.ts`, `stick-to-bottom.ts`,
  `toast-host.ts`, `toast.service.ts`.
- `shared/charts`: `donut.ts`, `heatmap.ts`, `ranked-bar.ts`, `split-bar.ts`.
- `core`: `theme.service.ts`, `socket/job-events.service.ts`, `api/api.config.ts`,
  `auth/auth.models.ts`.
- Root: `app.ts`, `app.config.ts`.

The shape of the coverage is clear and consistent: **pure logic that was extracted from a
component is tested; the component itself is not.** `job-actions.ts`, `stalled.ts`,
`notify-summary.ts`, `pivot.ts`, `kafka-profile-form.ts`, `chat-export.ts`,
`notification-links.ts` and `topic.ts` all exist as separate modules partly so they could be
tested -- several say so in their own header comments.

---

## Risks and things that look wrong

1. **`API_BASE` hard-codes port 9098 with no build-time or runtime override**
   (`scheduler1/next/src/app/core/api/api.config.ts:6`). There is no `environments/` directory
   and no `fileReplacements` in `angular.json`. Any deployment that terminates the API on 443
   behind the same host, or on any other port, needs a source change and a rebuild.

2. **Four declared dependencies are never imported**: `echarts`, `ngx-echarts`, `marked`,
   `file-saver` (and `@types/file-saver`). Every chart is hand-built SVG/CSS and the markdown
   parser is hand-written in `shared/ui/markdown.ts`. They do not reach the bundle, but they
   sit in `package.json` implying a charting/markdown stack that does not exist.

3. **The public form-fill page cannot submit.** `features/forms/form-fill.ts:9-19` states that
   `fetchFormByUuid` is `permitAll` but `submitForm` still requires `TENANT_USER`, so an
   anonymous visitor following a share link can read the form and not answer it. The page warns
   up front rather than failing on the button, but the feature is half-delivered until the
   server changes.

4. **`transcript.spec.ts` re-implements the component's parser instead of importing it**
   (lines 3-11: *"Mirrors the component's parser"*). Seven tests pass against a copy; the real
   `Transcript.segments` computed can drift without a failure. The parser is not exported.

5. **The websocket has exactly one consumer.** `JobEventsService` is a root singleton connected
   for the whole session, but only `features/jobs/jobs.ts` subscribes. The Queue, Job History
   and Dashboard screens all show run state and all poll or require a manual refresh. `JobLogs`
   runs its own 5 s `setTimeout` loop and the notification bell its own 60 s `setInterval`.

6. **The `JobEvent` type union and the one handler disagree.**
   `core/socket/job-events.service.ts:9` names `job.status | job.log | job.deleted | job.toggled`
   (widened by `| string`), but `jobs.ts:285-307` handles `job.status`, `job.deleted`,
   `job.toggled` and `job.updated` -- so `job.log` is declared and never consumed anywhere, and
   `job.updated` is consumed while not being named. The `| string` escape hatch means the
   compiler cannot flag either.

7. **143 uses of `any` in non-spec code**, concentrated in the screens that read the richest
   payloads: `task-edit.ts` (11), `tenants.ts` (7), `file-chat.ts` (6), `pdf-viewer.ts` (5),
   `jobs.ts` (5). `DashboardService.breakdownDetail` returns `ApiResponse<any[]>`. With
   `strictTemplates` on everywhere else, these are the places where a server-side field rename
   would fail silently at runtime rather than at build time.

8. **Two endpoints return their payload in `message` rather than `data`** and each caller has to
   know: `setting.json/xmlCreateChecker` is read as `(response as any).message ?? response.data`
   in `task-edit.ts`, and `addSourceJob`'s new id is recovered by regexing
   `/jobId (\d+)/` out of `created.message` in `jobs.ts`. Both are brittle against any change to
   the server's wording.

9. **`mustChangePassword` is read from the localStorage blob, not the token**
   (`core/auth/auth.service.ts:69`). The code argues this is acceptable -- editing it only skips
   a prompt, and the server still refuses the old password once replaced -- but it is a
   client-trusted flag guarding a client-side redirect, and worth knowing.

10. **Header navigation is not keyboard-accessible as a menu.** The dropdowns in `shell.html` are
    a button plus a `div` of links with no `role="menu"`, no roving focus and no arrow keys, and
    close only on outside click or Escape. Row action menus use the CDK and are fine; the primary
    nav is the one that is not.

11. **No lint, no e2e, no coverage gate.** There is no ESLint config, no Playwright/Cypress, and
    `angular.json`'s `test` target has no options block. `README.md` still carries the stock
    Angular CLI text, including an `ng e2e` section for a framework that is not installed.

12. **Duplicated chart implementations.** `features/reports/report-chart.ts` (404 lines, ten
    chart kinds) shares nothing with `shared/charts` beyond the colour tokens. A change to how a
    chart reads has to be made in both places; the reports chart has no tests.

13. **A hand-maintained model catalogue will go stale.** `features/ai/models/models.ts:37-53`
    lists 16 Ollama models with approximate sizes, and says outright that Ollama publishes no
    catalogue endpoint this backend proxies. Nothing will tell anyone when it is wrong.

14. **The object browser formats the same byte count two different ways, on one screen.**
    `features/objects/objects.ts:151` binds the shared helper (`humanSize = formatSize`) and
    `:478` declares a second, divergent `formatBytes`. Both are live: the size chart uses
    `humanSizeFn` -> `formatSize` (`objects.html:163`), while the header total and the Size
    column use `formatBytes` (`objects.html:125`, `:218`). They round differently -- `formatSize`
    always prints one decimal (`15.0 KB`), `formatBytes` drops it at or above 10 (`15 KB`), uses
    one decimal rather than two for GB, and adds a TB step `formatSize` does not have. This is
    exactly the drift `shared/ui/format-size.ts`'s own header comment says the extraction was
    meant to end.

15. **The docs screenshot feature is fully wired and entirely unused.** `features/docs/docs.ts`
    declares `shot`/`shotCaption` on `Step` (lines 18-20), renders them (lines 153-165) and
    resolves `/docs/<name>-<theme>.png` (line 444), but **not one of the nine steps sets `shot`**
    and `scheduler1/next/public/docs` is an empty directory. The guide currently ships as text
    only; anyone adding a step with a `shot` will get a broken image until the two PNGs are
    placed there.
