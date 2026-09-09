# Discovery -- Old Frontend (scheduler1/src)

Inventory of the legacy Angular 8 / Webpack frontend at `scheduler1/src`, produced by reading the
source. Its sibling `scheduler1/next` is the Angular 22 rewrite; it is referenced only in
section 7, to say whether an old capability appears to have a successor there.

All paths are relative to `/Users/nabeel.amd93/Desktop/Old-School`.

---

## 1. What the app is, and how it is built

### 1.1 What it is

A multi-tenant ETL / job-scheduling console. The browser tab is titled "ETL"
(`scheduler1/src/index.html:7`) and the navbar brand is "ETL" (`scheduler1/src/app/app.component.html:5`).
The landing page describes it as "Multi-tenant ETL orchestration, built around Kafka and AI"
(`scheduler1/src/app/_component/welcome/welcome.component.html:16`).

The surface breaks into seven areas, which match the navbar groups in
`scheduler1/src/app/app.component.html:9-82`:

| Nav group | Screens |
|---|---|
| Source | Source Job, Source Task (+ their editors, batch upload, history, logs) |
| Object Browser | Bucket file browser with preview, AI chat, email share |
| Productivity Tools | Search Engine, Query Engine, PDF Highlighter, Dynamic Forms, Document Converter, Audio Transcript Extractor |
| AI Suite | AI Agents, Ollama Models, Content Cleaner |
| Administration | Users, Tenants |
| Settings | Source TaskType (+ Kafka Connection tab), Lookup, Storage Connections, Q-Message |
| (navbar right) | Notification bell + Notification Center, user menu with Chicago-time clock, logout |

Three roles exist, declared in `scheduler1/src/app/_models/auth.model.ts:7`:
`PLATFORM_ADMIN`, `TENANT_ADMIN`, `TENANT_USER`.

### 1.2 Framework and dependencies

From `scheduler1/package.json`:

| Concern | Value |
|---|---|
| Angular | `^8.0.0` (`@angular/core`, `common`, `forms`, `router`, `animations`, `platform-browser`) |
| TypeScript | `^3.1.3`, `target: ES5` (`scheduler1/tsconfig.json`) |
| RxJS | `^6.3.3` |
| Bundler | Webpack `^4.32.2` + `ts-loader` + `angular2-template-loader` (JIT, not Ivy/AOT) |
| Charts | `echarts@^4.9.0` + `ngx-echarts@^5.2.2` |
| Toasts | `ngx-toastr@^11.3.3` (also `ng2-toastr@^4.1.2` is declared but never imported) |
| Realtime | `sockjs-client@^1.3.0` + `stompjs@^2.3.3` |
| PDF | `pdfjs-dist@^2.16.105` (worker copied to `assets/pdf.worker.min.js`) |
| Markdown | `marked@^4.3.0` (used only in the Object Browser chat) |
| File save | `file-saver@^2.0.5` |

Note `@angular/cli@^14.1.1` is in `devDependencies` but the app is **not** CLI-built -- there is
no `angular.json`. It is a hand-rolled Webpack build.

### 1.3 Build

`scheduler1/package.json` scripts:

- `npm run build` -> `webpack --mode production`
- `npm start` -> `cross-env NODE_OPTIONS=--openssl-legacy-provider webpack-dev-server --mode development --open --open-page scheduler/`

`scheduler1/webpack.config.js`:

- Entry `./src/main.ts`, output to `dist/` with `[name].[contenthash].js`, `publicPath: '/scheduler/'`.
- Alias `@` -> `src/app/` (mirrored by `paths` in `scheduler1/tsconfig.json`).
- Loaders: `ts-loader` + `angular2-template-loader` for `.ts`, `html-loader` for `.html`,
  `style-loader/css-loader/less-loader` for `.less`, `style-loader/css-loader` for `.css`.
- `CopyWebpackPlugin` copies `src/assets` to `dist/assets`.
- `HtmlWebpackPlugin` from `src/index.html`.
- **Runtime config is baked in by `DefinePlugin`** (`scheduler1/webpack.config.js:52-59`):

  ```js
  config = {
      sessionId: '0hw0dz34',
      transactionId: '40ef-dd1d-bd9f-1d7f',
      apiUrl: (window.location.protocol + '//' + window.location.hostname + ':9098/api/v1'),
      webSocketUrl: (window.location.protocol + '//' + window.location.hostname + ':9098/api/v1/ws')
  }
  ```

  `config` is a global declared in `scheduler1/src/typings.d.ts:2` and read by every service.
  The API host is hardcoded to **port 9098** at the same hostname as the page. There is no
  environment file and no per-deploy override.

Two Node patch scripts run around the build (`scheduler1/Dockerfile:26,33`):
`scheduler1/patch.js` (pre-build, fixes a `sockjs-client` unicode regex) and
`scheduler1/patch_dist.js` (post-build, rewrites literal-Unicode character classes in the
emitted bundles to escape sequences, to avoid "Range out of order in character class").
Both are invoked with `|| true`, so a failure is silent.

### 1.4 How it is served

`scheduler1/Dockerfile` is a two-stage build:

1. **Builder** -- `node:14-bullseye-slim`, installs `python3 make g++`, runs
   `npm install --legacy-peer-deps` plus an explicit `copy-webpack-plugin@5`, deletes any
   host `dist`, runs `patch.js`, `webpack --mode production`, then `patch_dist.js`.
2. **Production** -- `nginx:1.27-alpine`, copies `dist/` to
   `/usr/share/nginx/html/scheduler`, copies `nginx.conf` to
   `/etc/nginx/conf.d/default.conf`, exposes 80, `HEALTHCHECK` hits `/health`.

`scheduler1/nginx.conf` serves the SPA under `/scheduler/` with `try_files ... /scheduler/index.html`,
gzips text assets, sets `expires 1y; Cache-Control: public, immutable` on static assets and
`no-store` on `.html`, and adds `/health` and `/scheduler/health` plaintext endpoints.
`location = /scheduler` 301-redirects to `/scheduler/`.

`scheduler1/docker-compose.yml` builds the `production` target as image `scheduler1-app`,
container `scheduler1-app`, maps `80:80`, `restart: unless-stopped`, and healthchecks with
`wget -qO- http://127.0.0.1/health` (a comment explains 127.0.0.1 is used because nginx only
binds IPv4). `scheduler1/DEPLOYMENT.md` documents `docker-compose build --no-cache` then
`docker-compose up -d`, and says the app opens at `http://localhost/`.

`scheduler1/src/index.html` sets `<base href="/scheduler/">` and pulls four things from public
CDNs at runtime: Google Fonts (IBM Plex Sans/Mono), Bootstrap 3.4.1 CSS+JS, jQuery 3.4.1, and
DataTables 1.10.2 CSS+JS. It also contains ~55 lines of inline jQuery that "portals" open
Bootstrap dropdown menus to `position: fixed` so row-level `...` menus inside a scrolling table
are not clipped (`scheduler1/src/index.html:18-72`).

### 1.5 Application shell

- `scheduler1/src/main.ts` -- imports polyfills (`core-js/features/reflect`, `zone.js/dist/zone`
  via `scheduler1/src/polyfills.ts`) and bootstraps `AppModule`.
- `scheduler1/src/app/app.module.ts` -- a **single, eager NgModule**: 41 components + 1 pipe
  declared, no lazy loading, no feature modules. Imports `BrowserModule`,
  `NgxEchartsModule.forRoot({ echarts: () => import('echarts') })`, `FormsModule`,
  `ReactiveFormsModule`, `HttpClientModule`, `BrowserAnimationsModule`, `AppRoutingModule`,
  and `ToastrModule.forRoot({...})` (top-right, 1500ms, close button, progress bar,
  `preventDuplicates: true`). The only provider is the `AuthInterceptor`.
- `scheduler1/src/app/app.component.ts` / `.html` -- navbar, notification bell dropdown, user
  menu, `<router-outlet>`, and a global `<spinner>`. It also imports the global stylesheet
  (`import './_content/app.less'`, line 8) and registers an echarts theme named `default`
  (lines 12-16). `showNav` hides the navbar on `/login` and when logged out (line 49-51);
  `isFlushRoute` removes page padding at `/` (the landing page). A `setInterval` updates a
  `America/Chicago` clock every second (line 80).

### 1.6 Styling

There is no component-scoped CSS. Everything is one 5,381-line LESS file,
`scheduler1/src/app/_content/app.less`, imported once from `app.component.ts`. It starts by
importing `~ngx-toastr/toastr.css`. Layout comes from the CDN Bootstrap 3 grid plus custom
classes (`card-panel`, `toolbar`, `pill`, `entity-card`, `kpi-tile`, `empty-state`,
`table-modern`, ...). Icons are Bootstrap 3 `glyphicon`s throughout.

Two files in `_content/` are **not wired into the build at all**:
`scheduler1/src/app/_content/icon.html` (a 51-line standalone SVG-icon demo page) and
`scheduler1/src/app/_content/svg-icons-animate.css` (referenced only by that demo page).
`scheduler1/src/app/_content/slide-in-out.animation.ts` exports a `slideInOutAnimation`
trigger that no component imports.

---

## 2. Routes

All routes are declared flat in `scheduler1/src/app/app.routing.ts` via `RouterModule.forRoot`.
There is no lazy loading and there are no child routes (two list templates contain a nested
`<router-outlet>` -- `source-job.component.html:327` and `source-task.component.html` -- but no
route is configured to fill them).

Guards (`scheduler1/src/app/_helpers/`):

- `AuthGuard` (`auth.guard.ts`) -- redirects to `/login?returnUrl=<url>` when
  `AuthService.isLoggedIn()` is false, i.e. when there is no access token in `localStorage`.
- `RoleGuard` (`role.guard.ts`) -- reads `route.data.roles` (and, unused, `route.data.exactUsernames`)
  and redirects to `/unauthorized` on mismatch.

| # | Path | Component | What the screen does | Guard / role |
|---|---|---|---|---|
| 1 | `''` (exact) | `WelcomeComponent` | Public marketing landing page: hero, 7 feature cards, 3 "how it works" steps, footer. Redirects signed-in users to `/home` in `ngOnInit`. | none |
| 2 | `login` | `LoginComponent` | Username/password sign-in. Redirects to `/home` if already signed in; honours `returnUrl`. | none |
| 3 | `home` | `HomeComponent` | Dashboard: date-range filter, 6 KPI tiles, 4 echarts panels (job-status donut, running pie, weekly bar, hourly-by-weekday heatmap), and a drill-down "Job Breakdown" table with an inline mini stacked bar. Auto-refreshes every 60s. | `AuthGuard` |
| 4 | `taskList` | `SourceTaskComponent` | Source Task list. Table/card toggle (persisted in `localStorage`), search, status filter, client-side paging (50/100/150/200), expandable rows showing linked jobs, clone, delete, per-row JSON download. | `AuthGuard` |
| 5 | `taskList/taskBatchAction` | `SourceBatchActionComponent` | Bulk xlsx upload/download/template for tasks. `data: { router: '/taskList', action: 'sourceTask' }`. | `AuthGuard` |
| 6 | `addTask` | `TaskComponent` | Create Source Task: name, task type, pipeline/home-page/group lookups, tenant picker (Platform Admin only), a `FormArray` of XML tag rows, generated `taskPayload`. | `AuthGuard` |
| 7 | `editTask/:taskDetailId` | `TaskComponent` | Same form in update mode. | `AuthGuard` |
| 8 | `jobList` | `SourceJobComponent` | Source Job list. Table/card toggle, search, status filter, paging, multi-select with bulk run/delete, run / skip-next / clone / activate-deactivate / history per row, expandable row with linked-task panel and a run-duration bar chart. Live-updates over STOMP. | `AuthGuard` |
| 9 | `jobList/jobBatchAction` | `SourceBatchActionComponent` | Bulk xlsx upload/download/template for jobs. `data: { router: '/jobList', action: 'sourceJob' }`. | `AuthGuard` |
| 10 | `jobList/jobHistory` | `JobHistoryActionComponent` | Run history for a job (or an hour across all jobs), driven by `?jobId&jobStatus&targetDate&targetHr`. Run-duration chart, status pie, boolean-fields chart, per-row drill into logs. | `AuthGuard` |
| 11 | `jobList/jobLogs` | `JobLogComponent` | Audit log for one run (`?jobId&jobQueueId&from`). Three view modes (timeline / table / console), a Queue->Start->Running->Completed pipeline strip, log-gap bar chart, 5s auto-refresh while the run is not terminal, stick-to-bottom. | `AuthGuard` |
| 12 | `addJob` | `JobComponent` | Create Source Job: name, execution (Auto/Manual), priority, task picker, and -- for Auto -- a scheduler sub-form (start/end date, start time, frequency, interval, days-of-week, day-of-month) with a live plain-English schedule preview. | `AuthGuard` |
| 13 | `editJob/:jobId` | `JobComponent` | Same form in update mode (execution type is disabled). | `AuthGuard` |
| 14 | `setting` | `SettingComponent` | Two tabs: **Source TaskType** (list, add/edit modal, test-Kafka-topic per row, linked-task browser modal, JSON download, delete) and **Kafka Connection** (embeds `KafkaConnectionProfileComponent`). | `AuthGuard` + `RoleGuard` `['PLATFORM_ADMIN','TENANT_ADMIN']` |
| 15 | `setting/storageConnection` | `StorageConnectionComponent` | Storage connections (S3 / Azure / MinIO / FTP / FTPS): list with provider filter, add/edit modal with per-provider fields, bucket discovery, test-connection, delete. | `AuthGuard` + `RoleGuard` `['PLATFORM_ADMIN','TENANT_ADMIN']` |
| 16 | `setting/lookup` | `SettingLookupComponent` | Lookup master list; opens the shared `LookupComponent` modal for add/edit; links into sub-lookups. | `AuthGuard` + `RoleGuard` `['PLATFORM_ADMIN','TENANT_ADMIN']` |
| 17 | `setting/subLookup` | `SubLookupComponent` | Child lookups of `?lookupId`, with add/edit/delete. | `AuthGuard` + `RoleGuard` `['PLATFORM_ADMIN','TENANT_ADMIN']` |
| 18 | `setting/queueMessage` | `QueueMessageComponent` | "Q-Message": filter the job queue by id / date range / status / job id; result table with duration; four echarts summaries including a custom Gantt-style start->end comparison; per-row fail / interrupt. | `AuthGuard` **only** |
| 19 | `setting/lookpXml` | `XmlConfigurationComponent` | Standalone XML builder: a `FormArray` of tag rows -> server-generated XML -> download as `.xml`. Not linked from the navbar. | `AuthGuard` + `RoleGuard` `['PLATFORM_ADMIN','TENANT_ADMIN']` |
| 20 | `setting/searchEngine` | `SearchEngineComponent` | "Q-Result": free-text SQL `SELECT` box, dynamic result table with client-side search. | `AuthGuard` + `RoleGuard` `['PLATFORM_ADMIN']` |
| 21 | `setting/queryEngine` | `QueryEngineComponent` | Query Engine, three tabs (Connections / Queries / Executions): DB connection profiles with test, saved queries with validate + preview, run-to-bucket, recurring schedules, execution history. | `AuthGuard` **only** |
| 22 | `tenants` | `TenantsComponent` | Tenant admin: list with per-tenant counts, add/edit modal, suspend/resume, soft delete. | `AuthGuard` + `RoleGuard` `['PLATFORM_ADMIN']` |
| 23 | `users` | `UsersComponent` | User admin: list with tenant/role/status filters, add/edit modal, activate/deactivate, reset-password modal, soft delete. Honours `?tenantId` to focus one tenant. | `AuthGuard` + `RoleGuard` `['PLATFORM_ADMIN','TENANT_ADMIN']` |
| 24 | `unauthorized` | `UnauthorizedComponent` | Static "you don't have access" panel with a Back-to-Home button. | `AuthGuard` |
| 25 | `objectBrowser` | `ObjectBrowserComponent` | Bucket file browser. See section 3.4 -- the largest screen in the app. Deep-linkable via `?bucket&prefix`. | `AuthGuard` |
| 26 | `notifications` | `NotificationCenterComponent` | All / Unread tabs, paged list, mark-all-read, click-through to `linkUrl`. | `AuthGuard` |
| 27 | `pdfHighlighter` | `PdfHighlighterComponent` | PDF Highlighter task list with status filters, edit / view / delete, copy stored file path. | `AuthGuard` |
| 28 | `pdfHighlighter/new` | `PdfHighlighterDetailComponent` | New highlighter task. | `AuthGuard` |
| 29 | `pdfHighlighter/:pdfHighlighterTaskId` | `PdfHighlighterDetailComponent` | Canvas PDF editor: render pages with pdf.js, drag rectangles to define fields, derive a text selector from the page text layer, reorder fields, zoom/page nav, copy/download the mapping JSON. `?mode=view` makes it read-only. | `AuthGuard` |
| 30 | `dynamicForm` | `DynamicFormListComponent` | Dynamic form list; add / edit / fill / submissions / copy API share link / delete. | `AuthGuard` |
| 31 | `dynamicForm/new` | `CUDynamicFormComponent` | Create a form (name + description), then redirects to edit. | `AuthGuard` |
| 32 | `dynamicForm/edit/:dynamicFormId` | `CUDynamicFormComponent` | Form builder: field list with move up/down, add/edit field modal covering 17 field types, options editor, width/validation attributes, delete-field modal. | `AuthGuard` |
| 33 | `dynamicForm/fill/:dynamicFormId` | `FillDynamicFormComponent` | Renders the form dynamically and submits a payload (grouped by `section` fields). | `AuthGuard` |
| 34 | `dynamicForm/fill/:dynamicFormId/edit/:submissionId` | `FillDynamicFormComponent` | Same renderer pre-filled from an existing submission; saves via `updateSubmission`. | `AuthGuard` |
| 35 | `dynamicForm/submissions/:dynamicFormId` | `DynamicFormSubmissionsComponent` | Submissions list for one form, with a two-field preview, copy API link, edit, view, delete. | `AuthGuard` |
| 36 | `dynamicForm/submissions/:dynamicFormId/:submissionId` | `ViewDynamicFormSubmissionComponent` | One submission rendered field-by-field, with a sibling-submission switcher, share URL + share token copy, edit, delete. | `AuthGuard` |
| 37 | `aiAgent` | `AiAgentComponent` | AI agent registry: table/card views, provider+status filters, add/edit/clone modal (provider, endpoint, API key, model, instructions, JSON mode, target file types), copy tool URL, delete. Mutations gated in-template to admins. | `AuthGuard` |
| 38 | `ollamaModels` | `OllamaModelsComponent` | Local Ollama models: list with size/family, pull from a 14-entry popular catalog or a typed tag, delete. | `AuthGuard` + `RoleGuard` `['PLATFORM_ADMIN','TENANT_ADMIN']` |
| 39 | `contentCleaner` | `ContentCleanerComponent` | Paste text or browse a bucket file (pdf/csv/txt/json/xlsx/xml), extract (pdf.js in-browser for PDFs), clean server-side, show raw vs cleaned and chars saved. | `AuthGuard` |
| 40 | `documentConverter` | `DocumentConverterComponent` | Convert a document between formats: upload or browse-bucket, format-family reference table, optional save-to-bucket with folder browser, inline preview of input and output, past-conversions table with preview + delete. | `AuthGuard` |
| 41 | `audioTranscriptExtractor` | `AudioTranscriptExtractorComponent` | Transcribe `.mp3`/`.m4a` from upload or bucket, optional timestamps (highlighted in the output), reopen an already-saved `.txt`, save the transcript back to a bucket folder. | `AuthGuard` |
| 42 | `**` | -- | `redirectTo: 'home'`. | -- |

### Route observations

- `setting/queueMessage` (#18) and `setting/queryEngine` (#21) sit under a `/setting/` prefix
  whose sibling routes are admin-gated, but carry only `AuthGuard`. That is deliberate in the
  navbar (both appear for every role) but makes the URL prefix a poor guide to who may enter.
- `setting/lookpXml` (#19) -- note the typo in the path -- has no navbar entry
  (`app.component.html` has no link to it). It is reachable only by typing the URL.
- The navbar hides admin entries with `*ngIf` on `authService.currentUser?.userRole`
  (`app.component.html:29, 45, 52, 57, 60, 70, 73, 76`); the `RoleGuard` is the real gate.
- `RoleGuard` reads `route.data.exactUsernames` (`role.guard.ts:18`) but **no route sets it**.

---

## 3. Components under `_component`

41 components are declared in `app.module.ts`: 39 live under
`scheduler1/src/app/_component/`, plus `AppComponent` and `SpinnerComponent`. Barrel:
`scheduler1/src/app/_component/index.ts`.

Four of the 39 have **no route** and exist only as children:
`LookupComponent`, `SourceTaskTypeComponent`, `KafkaConnectionProfileComponent`,
`LinkedTaskPanelComponent`.

### 3.1 Shell / entry

| Component | Files | Notes |
|---|---|---|
| `AppComponent` | `app/app.component.ts`, `.html` | Navbar, notification bell (badge, recent list, mark-all-read), user card with initials avatar + Chicago clock, logout, `<router-outlet>`, `<spinner>`. Uses raw jQuery for the bell's `show.bs.dropdown` hook (`app.component.ts:83`). |
| `WelcomeComponent` | `_component/welcome/` | Public landing page. Feature/step cards are hardcoded arrays in the `.ts` (`welcome.component.ts:27-76`). |
| `LoginComponent` | `_component/login/` | Reactive form, `username` + `password` required. The template hardcodes demo credentials in a hint (`login.component.html:30`). |
| `UnauthorizedComponent` | `_component/unauthorized/` | Template only; the class is empty. |
| `SpinnerComponent` | `_modal/spinner.component.ts` | Inline-template + inline-styles global overlay spinner, toggled by adding/removing `is-visible` on the `<spinner>` element. |

### 3.2 Source Job / Source Task

| Component | Files | Notes |
|---|---|---|
| `SourceJobComponent` | `_component/source-job/source-job.component.*` | 650 lines. Table + card views, `SearchFilterPipe` + status filter + client paging, bulk select with run/delete, per-row run / skip / clone / toggle-status / history / delete, expandable row with `<linked-task-panel>` and a per-run duration bar chart (click a bar -> job logs). Opens a STOMP connection in the constructor and patches rows from `/user/queue/reply` pushes (`source-job.component.ts:78-97`). Clone is implemented client-side: fetch, reshape, re-`addSourceJob` (`:285-340`). |
| `JobComponent` | `_component/source-job/job/job.component.*` | Add/Edit job. Nested `FormGroup` for `taskDetail`, dynamically added/removed `scheduler` group when execution flips Auto/Manual (`:322-332`). `scheduleSummary` getter renders a plain-English preview (`:361-395`). |
| `SourceTaskComponent` | `_component/source-task/source-task.component.*` | Table + card views, filters, paging, expandable rows that lazily fetch linked jobs, clone, delete, per-row JSON download via `CommomService.createFile`. |
| `TaskComponent` | `_component/source-task/task/task.component.*` | Add/Edit task. Loads three sub-lookup sets (`PIPELINE_IDS`, `PIPELINE_HOME_PAGES`, `TASK_GROUPS`) from `appSetting` + `fetchSubLookupByParentId`. `FormArray` of 10 blank tag rows on create; a `noWhitespaceValidator` and a `trimTagField`/`trimAllTagFields` pass guard against invisible whitespace in bucket names (`:38-43, 122-154`). Highlights "storage tag keys" (`bucket`, `bucket_name`, `input_folder`, `output_folder`). Platform Admin gets a required tenant picker. |
| `SourceBatchActionComponent` | `_component/batch-action/` | Shared by the job and task bulk routes; branches on `route.data.action`. Drag-and-drop dropzone, hidden file input, download-list and download-template buttons, per-row error table. Platform Admin uploading tasks must pick a tenant first (`:67-69, 113-116`). |
| `JobHistoryActionComponent` | `_component/job-history-action/` | Run history, driven entirely by query params. Recomputes four echarts options whenever the search text or status filter changes (setters at `:34-55`). |
| `JobLogComponent` | `_component/job-logs/` | Timeline / table / console views, pipeline strip (`pipelineStages` getter, `:285-308`), log-gap chart with data-zoom memory, 5s auto-refresh while non-terminal, `BACK_TARGETS` map so "Back" returns to whichever screen linked here (`:18-27`). |
| `LinkedTaskPanelComponent` | `_component/linked-task-panel/` | Presentational. `@Input() taskDetail`. Shows task link, type, topic/partitions, pipeline, home page, a "View in Bucket" deep link into `/objectBrowser?bucket=&prefix=`, and the task payload with a copy button. |

### 3.3 Settings

| Component | Files | Notes |
|---|---|---|
| `SettingComponent` | `_component/setting/setting.component.*` | Bootstrap tabs. Source TaskType table with a per-row **Test Kafka Connection** button (`:93-113`), a "Link Source Task" modal with search + group filter (`:120-166`), JSON download, delete. Second tab hosts `<kafka-connection-profile>`. |
| `SourceTaskTypeComponent` | `_component/setting/source-task-type/` | Add/Edit/View modal for a task type. Splits and rebuilds the `topic=<x>&partitions=[<y>]` string (`:186-206`). Partition options are `*` plus `0..10`. |
| `KafkaConnectionProfileComponent` | `_component/setting/kafka-connection-profile/` | 447 lines, no route. CRUD for Kafka profiles: bootstrap servers, security protocol (`PLAINTEXT`/`SASL_*`/`SSL`), SASL mechanism + credentials, keystore/truststore selection with upload into a bucket under `kafka-secrets/`, additional properties, test-connection both in-modal and per row, set/clear default, tenant-vs-platform scope filter, inline help toggles. |
| `SettingLookupComponent` | `_component/setting/setting-lookup.component.*` | Lookup master list; delegates add/edit to `<look-up>`. |
| `LookupComponent` | `_component/setting/lookup/` | Add/Edit lookup modal. When a lookup is `encrypted`, the value field is blanked and its `required` validator dropped (`:99-107`). |
| `SubLookupComponent` | `_component/setting/sub-lookup/` | Children of `?lookupId`, with inline delete and the same `<look-up>` modal. |
| `XmlConfigurationComponent` | `_component/setting/xml-configuration/` | 6 blank tag rows -> `xmlCreateChecker` -> XML string -> `saveAs` download. |
| `QueueMessageComponent` | `_component/setting/queue-message/` | 398 lines. Filter form + result table + four charts, including an echarts **custom series** Gantt of start->end per run with data-zoom (`:234-292`) whose bars link into job logs. |
| `QueryEngineComponent` | `_component/setting/query-engine/` | 565 lines, six modals, three tabs. Connections (add/edit/test/delete), Queries (add/edit, validate, preview into a result grid, delete, run-to-bucket modal, schedule modal), Executions (history with status filter). |
| `StorageConnectionComponent` | `_component/setting/storage-connection/` | Provider-aware form (S3 / Azure / MinIO / FTP / FTPS), default ports for FTP/FTPS with implicit-TLS handling (`:216-229`), bucket discovery, test-connection, and a deliberate "blank secret means keep the stored one" rule on save (`:236-242`). |
| `SearchEngineComponent` | `_component/search-engine/` | SQL textarea -> `dynamicQueryResponse` -> dynamic `column`/`data` table with client-side search and long-cell wrapping. |

### 3.4 Object Browser

`_component/object-browser/object-browser.component.ts` is **1,904 lines** with a 694-line
template -- by far the largest component. It contains, in one class:

- **Browsing**: bucket picker, breadcrumb path, infinite scroll via `continuationToken`
  (`onTableScroll`, `:635`), name + modified-date-range filters, select-all / bulk selection,
  deep-link entry from `?bucket&prefix` (`:267-284`).
- **Folder Insights**: four echarts tiles (files-vs-folders, sub-folder sizes, file types,
  upload age) built from a capped stats pass. FTP/FTPS are treated as slow providers and the
  insights panel starts collapsed there (`:349-358`, with a comment measuring 14s on a real mirror).
- **Per-entry actions**: view, download, email, rename folder, copy path, copy ETag, delete.
- **Preview modal**: json / csv / txt / xml / md / pdf / mp3 / m4a / mp4 / image, with a
  gzip-aware "effective extension" (`:1407`), markdown rendering via `marked`, and an
  **inline text editor** that saves the edited file back to the bucket (`:1537-1609`).
- **Bulk**: staggered multi-download (`BULK_DOWNLOAD_STAGGER_MS`), bulk delete, bulk email-as-ZIP.
- **AI file chat**: a floating, minimisable chat widget bound to one file -- agent picker,
  suggested prompts, Web Speech dictation (`webkitSpeechRecognition`, `:815-850`), stop button,
  slow-response hint, copy message, and an elaborate protocol for extracting downloadable files
  out of fenced code blocks in the model's reply (`CHAT_FENCE_PATTERN_SOURCE`, `:1087-1210`),
  including converting csv/json/md into `xlsx`/`docx`/`pdf` through `fileChat.json/exportFile`,
  plus a preview modal for the generated file.

Eight modals live in its template: `objectPreviewModal`, `newFolderModal`, `renameFolderModal`,
`emailShareModal`, `deleteConfirmModal`, `leaveChatConfirmModal`, `closeChatConfirmModal`,
`chatFilePreviewModal`.

### 3.5 Productivity tools

| Component | Files | Notes |
|---|---|---|
| `PdfHighlighterComponent` | `_component/pdf-highlighter/` | List with highlighter-status (Draft/Ready) and status filters, copy stored file path (`pdf-highlighter/<id>/<name>`), delete modal. |
| `PdfHighlighterDetailComponent` | `_component/pdf-highlighter/pdf-highlighter-detail/` | 602 lines. Loads a PDF with pdf.js into a `<canvas>`, overlays a drag-to-draw rectangle layer, converts each rectangle into a `PdfHighlighterField` (page, x, y, w, h) **and** derives a text selector from the page text layer -- `path`, `text`, and 30-char `prefix`/`suffix` context (`buildSelector`, `:415`), with a `useXpathFirst` flag. Zoom 0.5-3.0, page nav, field reorder, per-field selector copy, mapping JSON copy + download, drag-and-drop file load, read-only mode. |
| `DynamicFormListComponent` | `_component/dynamic-form/dynamic-form-list/` | List + status filter + delete modal + "copy API link" (`fetchFormByUuid`). |
| `CUDynamicFormComponent` | `_component/dynamic-form/cu-dynamic-form/` | Form builder. 17 field types (`_models/dynamic-form.model.ts:22-40`) including `section` headers; per-field placeholder, default, mandatory, regex pattern, min/max length, 1-12 grid width; options editor for select/multi-select/radio/checkbox; duplicate-`fieldName` check (`:235-241`); reorder by swapping `fieldOrder` and issuing two `updateField` calls (`:324-352`). |
| `FillDynamicFormComponent` | `_component/dynamic-form/fill-dynamic-form/` | Builds a `FormGroup` at runtime from the field definitions, wires validators per field, keeps checkbox groups in `Set`s outside the form, nests answers under the preceding `section` key when building the payload (`:205-223`). Handles both create and edit. |
| `DynamicFormSubmissionsComponent` | `_component/dynamic-form/dynamic-form-submissions/` | Submissions table with a two-value preview line, copy API link, edit, view, delete. |
| `ViewDynamicFormSubmissionComponent` | `_component/dynamic-form/view-dynamic-form-submission/` | One submission rendered against its form's fields, sibling-submission switcher, share URL + raw share token copy, edit, delete. |
| `DocumentConverterComponent` | `_component/document-converter/` | 738 lines. Upload-or-browse source, supported-format reference table, output-format picker scoped to the input's family, optional save-to-bucket with a folder browser, side-by-side input/output preview (pdf / image / text / html), download, and a past-conversions table with preview and delete. |
| `AudioTranscriptExtractorComponent` | `_component/audio-transcript-extractor/` | Upload-or-browse `.mp3`/`.m4a`, optional timestamps, timestamp highlighting via a sanitized HTML pass (`:262-270`), reopen an existing `.txt` transcript from a bucket, save the transcript into a (possibly new) bucket folder with a suggested folder name (`:299-305`). |
| `ContentCleanerComponent` | `_component/content-cleaner/` | Paste-or-browse, in-browser PDF text extraction via `extractPdfText`, server-side clean, raw vs cleaned panes, chars-saved counter, copy. |

### 3.6 AI

| Component | Files | Notes |
|---|---|---|
| `AiAgentComponent` | `_component/ai-agent/` | Agent registry. Providers come from the `AI_PROVIDER` lookup tree (`ai-agent.component.ts:105-137`). Add / edit / clone in one modal; target file types are checkboxes joined into a CSV (`:263`); built-in providers (OpenAI/Anthropic/Ollama) get default endpoints and Ollama needs no key (`:216-229`); a blank key on edit means "keep the stored one" (`:265-267`); copy-tool-URL builds `aiAgent.json/fetchToolByUuid?uuid=` (`:309`). |
| `OllamaModelsComponent` | `_component/ollama-models/` | Model list with total disk and family count, colour-coded families, pull from `OLLAMA_POPULAR_MODELS` (14 entries in `_models/ollama.model.ts:18-35`) or a typed tag, delete modal. |

### 3.7 Administration and notifications

| Component | Files | Notes |
|---|---|---|
| `TenantsComponent` | `_component/tenants/` | Tenant cards with per-tenant counts (users, kafka profiles, buckets, task types, tasks, jobs) and roll-up totals; add/edit modal (`tenantCode` disabled on edit); suspend/resume; delete = `changeTenantStatus` to `'Delete'`. |
| `UsersComponent` | `_component/users/` | User table with tenant/role/status filters and a `?tenantId` focus banner; add/edit modal (username is an email, disabled on edit; password min length 8); activate/deactivate; reset-password modal; delete = `changeUserStatus` to `'Delete'`. |
| `NotificationCenterComponent` | `_component/notification-center/` | All/Unread tabs, server paging (20/page), mark-all-read, row click marks read and navigates to `linkUrl`. |
| `HomeComponent` | `_component/home/` | Dashboard, described in section 2 row 3. Clicking a heatmap cell loads the per-job breakdown; clicking a count in that table routes to `jobList/jobHistory` with `jobId`, `jobStatus`, `targetDate`, `targetHr` (`:625-639`). |

### 3.8 Helpers, models, pipes

`scheduler1/src/app/_helpers/` (barrel `index.ts`):

| File | Purpose |
|---|---|
| `auth.guard.ts` | `AuthGuard` -- token presence check. |
| `role.guard.ts` | `RoleGuard` -- `data.roles` (and unused `data.exactUsernames`). |
| `auth.interceptor.ts` | Attaches `Authorization: Bearer`, skips the two auth endpoints, and on a 401 does a **single shared refresh** (`refreshInFlight$` + `shareReplay(1)`, `:48-56`) then replays the request; logs out if the refresh fails. |
| `spinner.service.ts` | `show()`/`hide()` by toggling `is-visible` on the `<spinner>` DOM element. |
| `search-filter.ts` | `SearchFilterPipe` -- a tokenising client-side filter supporting `field.path:term`, quoted phrases, and `-negation` (`:40-55`). Used in 13 templates. |
| `job-status-chart.helper.ts` | Shared chart palette + builders: `JOB_STATUS_COLOR`, `JOB_STATUS_ORDER`, `CATEGORY_PALETTE`, `categoricalColumnStats`, `toPieOptions`, `toRankedBarOptions`, `jobIdRankedBarOptions`, `booleanFieldsChartOptions`, `rowDuration`, `formatDateTime`, `compactAxisNumber`. |
| `pdf-text-extractor.ts` | `extractPdfText(ArrayBuffer)` via pdf.js legacy build. |
| `pretty-print.ts` | `prettyPrint()` -- **exported but never imported anywhere**. |

`scheduler1/src/app/global-config.ts` (240 lines) holds shared constants and pure helpers:
`PRIORITY`, `Execution`, `UserType` (unused), `FREQUENCY` + `FREQUENCY_LABEL` + `FREQUENCY_DETAIL`,
`DAYS_OF_WEEK`, `DAY_OF_MONTH_OPTIONS`, `formatScheduleSummary()`, `parseTopicPartition()`, and a
literal 1,440-entry `TIMES` array of every `HH:mm` in a day (`:96-241`).

`scheduler1/src/app/_models/` (barrel `index.ts`): `response.ts` (`ApiResponse`, `ApiCode` enum),
`object.ts` (core domain interfaces: `SourceTaskType`, `SourceTask`, `SourceJobDetail`,
`Scheduler`, `QMessage`, `LookupData`, `Paging`, `QueryCriteria`, `Action` enum, `STATUS_LIST`,
plus PDF-highlighter and storage-browser shapes), and one file per feature
(`auth`, `app-user`, `tenant`, `notification`, `dynamic-form`, `query-engine`, `ai-agent`,
`ollama`, `kafka-connection-profile`, `storage-connection`, `audio-transcript`,
`document-converter`). Several model files carry logic, not just types -- e.g.
`dynamic-form.model.ts:99-163` (`optionLabelFor`, `sectionKeyFor`, `payloadValueFor`,
`submissionFieldDisplayValue`, `submissionShareUrl`, `formShareUrl`) and
`ai-agent.model.ts:29-50` (`targetFileTypesList`, `fileExtension`, `agentsForFile`).

`HttpRequestInfo` and `FileInfo` (`_models/object.ts:6-15`) are declared and never used.

---

## 4. Services and the endpoints they call

All 26 services live in `scheduler1/src/app/_services/` (barrel `index.ts`) and are
`providedIn: 'root'`. Every HTTP URL is built from the global `config.apiUrl`, i.e.
`<protocol>//<hostname>:9098/api/v1`. Every JSON response is typed `ApiResponse`
(`status` / `message` / `data` / `paging`) and callers compare `status` to `ApiCode.SUCCESS`.

### 4.1 Auth, users, tenants

| Service | Method | Verb | Endpoint |
|---|---|---|---|
| `auth.service.ts` | `login` | POST | `/auth.json/login` |
| | `refreshAccessToken` | POST | `/auth.json/refresh` |
| | `logout` / `isLoggedIn` / `currentUser` | -- | reads/writes `localStorage['etl_auth_user']` |
| `app-user.service.ts` | `listUsers` | GET | `/appUser.json/listUsers` |
| | `addUser` | POST | `/appUser.json/addUser` |
| | `updateUser` | PUT | `/appUser.json/updateUser` |
| | `changeUserStatus` | PUT | `/appUser.json/changeUserStatus` |
| | `resetPassword` | PUT | `/appUser.json/resetPassword` |
| `tenant.service.ts` | `listTenants` | GET | `/tenant.json/listTenants` |
| | `addTenant` | POST | `/tenant.json/addTenant` |
| | `updateTenant` | PUT | `/tenant.json/updateTenant` |
| | `changeTenantStatus` | PUT | `/tenant.json/changeTenantStatus` |

### 4.2 Settings, lookups, queue messages

| Service | Method | Verb | Endpoint |
|---|---|---|---|
| `setting.service.ts` | `appSetting` | GET | `/setting.json/appSetting` |
| | `addSourceTaskType` | POST | `/setting.json/addSourceTaskType` |
| | `updateSourceTaskType` | PUT | `/setting.json/updateSourceTaskType` |
| | `deleteSourceTaskType` | DELETE | `/setting.json/deleteSourceTaskType?sourceTaskTypeId=` |
| | `addLookupData` | POST | `/setting.json/addLookupData` |
| | `updateLookupData` | PUT | `/setting.json/updateLookupData` |
| | `deleteLookupData` | **PUT** | `/setting.json/deleteLookupData` |
| | `fetchSubLookupByParentId` | GET | `/setting.json/fetchSubLookupByParentId?parentLookUpId=` |
| | `fetchLogs` | POST | `/message.json/fetchLogs` |
| | `failJobLogs` | DELETE | `/message.json/failJobLogs?jobQId=` |
| | `interruptJobLogs` | DELETE | `/message.json/interruptJobLogs?jobQId=` |
| | `dynamicQueryResponse` | POST | `/setting.json/dynamicQueryResponse` |
| `configuration.service.ts` | `getXmlData` | POST | `/setting.json/xmlCreateChecker` |

### 4.3 Dashboard

| Service | Method | Verb | Endpoint |
|---|---|---|---|
| `hom.service.ts` (`HomeService`) | `jobStatusStatistics` | GET | `/dashboard.json/jobStatusStatistics` |
| | `jobRunningStatistics` | GET | `/dashboard.json/jobRunningStatistics` |
| | `weeklyRunningJobStatistics` | GET | `/dashboard.json/weeklyRunningJobStatistics` |
| | `weeklyHrsRunningJobStatistics` | GET | `/dashboard.json/weeklyHrsRunningJobStatistics` |
| | `weeklyHrRunningStatisticsDimension` | GET | `/dashboard.json/weeklyHrRunningStatisticsDimension` |
| | `weeklyHrRunningStatisticsDimensionDetail` | GET | `/dashboard.json/weeklyHrRunningStatisticsDimensionDetail` |

### 4.4 Source jobs and tasks

| Service | Method | Verb | Endpoint |
|---|---|---|---|
| `source.job.service.ts` | `fetchSourceJobDetailWithSourceJobId` | GET | `/sourceJob.json/fetchSourceJobDetailWithSourceJobId?jobId=` |
| | `listSourceJob` | GET | `/sourceJob.json/listSourceJob` |
| | `addSourceJob` | POST | `/sourceJob.json/addSourceJob` |
| | `updateSourceJob` | PUT | `/sourceJob.json/updateSourceJob` |
| | `deleteSourceJob` | PUT | `/sourceJob.json/deleteSourceJob` |
| | `toggleSourceJobStatus` | PUT | `/sourceJob.json/toggleSourceJobStatus` |
| | `runSourceJob` | POST | `/sourceJob.json/runSourceJob` |
| | `skipNextSourceJob` | POST | `/sourceJob.json/skipNextSourceJob` |
| | `findSourceJobAuditLog` | GET | `/sourceJob.json/findSourceJobAuditLog?jobQueueId=&jobId=` |
| | `fetchSourceJobQueueListWithJobId` | GET | `/sourceJob.json/fetchSourceJobQueueListWithJobId?jobId=` |
| | `downloadSourceJobTemplateFile` | GET (blob) | `/sourceJob.json/downloadSourceJobTemplateFile` |
| | `downloadListSourceJob` | GET (blob) | `/sourceJob.json/downloadListSourceJob` |
| | `uploadSourceJob` | POST (multipart) | `/sourceJob.json/uploadSourceJob` |
| `source.task.service.ts` | `addSourceTask` | POST | `/sourceTask.json/addSourceTask` |
| | `updateSourceTask` | PUT | `/sourceTask.json/updateSourceTask` |
| | `deleteSourceTask` | PUT | `/sourceTask.json/deleteSourceTask` |
| | `listSourceTask` | POST | `/sourceTask.json/listSourceTask` + `startDate/endDate/page/limit/columnName/order` params |
| | `downloadListSourceTask` | GET (blob) | `/sourceTask.json/downloadListSourceTask` |
| | `downloadSourceTaskTemplate` | GET (blob) | `/sourceTask.json/downloadSourceTaskTemplate` |
| | `uploadSourceTask` | POST (multipart) | `/sourceTask.json/uploadSourceTask` (+ optional `tenantId` part) |
| | `fetchSourceTaskWithSourceTaskId` | GET | `/sourceTask.json/fetchSourceTaskWithSourceTaskId?sourceTaskId=` |
| | `fetchAllLinkJobsWithSourceTaskId` | POST | `/sourceTask.json/fetchAllLinkJobsWithSourceTaskId?sourceTaskId=&page=1&limit=500` |
| | `fetchAllLinkSourceTaskWithSourceTaskTypeId` | GET | `/sourceTask.json/fetchAllLinkSourceTaskWithSourceTaskTypeId?sourceTaskTypeId=` |

`listSourceTask` caches the last `searchText` on the service instance (`source.task.service.ts:12, 29-31`)
and re-sends it as the body when a later call omits one -- shared mutable state across screens.

### 4.5 Storage

| Service | Method | Verb | Endpoint |
|---|---|---|---|
| `storage.service.ts` | `buckets` | GET | `/storage.json/buckets` |
| | `listObjects` | GET | `/storage.json/listObjects?bucket=&prefix=&maxKeys=&continuationToken=` |
| | `objectMetadata` | GET | `/storage.json/objectMetadata?bucket=&key=` |
| | `previewObjectUrl` / `previewObjectText` / `previewObjectArrayBuffer` | GET | `/storage.json/previewObject?bucket=&key=` |
| | `downloadObjectUrl` | GET | `/storage.json/downloadObject?bucket=&key=` |
| | `uploadObject` | POST (multipart) | `/storage.json/uploadObject?bucket=&prefix=` |
| | `createFolder` | POST | `/storage.json/createFolder?bucket=&prefix=&folderName=` |
| | `deleteObject` | DELETE | `/storage.json/deleteObject?bucket=&key=` |
| | `deleteObjects` | POST | `/storage.json/deleteObjects` |
| | `deleteFolder` | DELETE | `/storage.json/deleteFolder?bucket=&key=` |
| | `renameFolder` | POST | `/storage.json/renameFolder?bucket=&key=&newFolderName=` |
| `storage-connection.service.ts` | `addConnection` | POST | `/storageConnection.json/addConnection` |
| | `updateConnection` | PUT | `/storageConnection.json/updateConnection` |
| | `deleteConnection` | DELETE | `/storageConnection.json/deleteConnection?storageConnectionId=` |
| | `fetchAllConnections` | GET | `/storageConnection.json/fetchAllConnections` |
| | `fetchConnectionById` | GET | `/storageConnection.json/fetchConnectionById?storageConnectionId=` |
| | `discoverBuckets` | POST | `/storageConnection.json/discoverBuckets` |
| | `testConnection` | POST | `/storageConnection.json/testConnection?storageConnectionId=` |
| `file-share.service.ts` | `sendFile` | POST | `/fileShare.json/send` |

### 4.6 Kafka

| Service | Method | Verb | Endpoint |
|---|---|---|---|
| `kafka-connection-profile.service.ts` | `addProfile` | POST | `/kafkaConnectionProfile.json/addProfile` |
| | `updateProfile` | PUT | `/kafkaConnectionProfile.json/updateProfile` |
| | `deleteProfile` | **PUT** | `/kafkaConnectionProfile.json/deleteProfile?kafkaConnectionProfileId=` |
| | `fetchAllProfiles` | GET | `/kafkaConnectionProfile.json/fetchAllProfiles` |
| | `setAsDefault` | POST | `/kafkaConnectionProfile.json/setAsDefault?kafkaConnectionProfileId=` |
| | `clearDefault` | POST | `/kafkaConnectionProfile.json/clearDefault` |
| | `testConnection` | POST | `/kafkaConnectionProfile.json/testConnection` |
| | `testTopic` | GET | `/kafkaConnectionProfile.json/testTopic?topicName=` |
| | `fetchKafkaRoute` | GET | `/setting.json/fetchKafkaRoute?sourceTaskTypeId=` |
| | `setKafkaRoute` | PUT | `/setting.json/setKafkaRoute?sourceTaskTypeId=&kafkaConnectionProfileId=` |
| | `deleteKafkaRoute` | DELETE | `/setting.json/deleteKafkaRoute?sourceTaskTypeId=` |

The three `*KafkaRoute` methods and `fetchKafkaRoute` are declared here but are **not called from
any component** -- routing a task type to a profile is done through the `kafkaConnectionProfileId`
field on the task-type form instead.

### 4.7 PDF Highlighter

| Service | Method | Verb | Endpoint |
|---|---|---|---|
| `pdf-highlighter.service.ts` | `fetchAllPdfHighlighterTask` | GET | `/pdfHighlighter.json/fetchAllPdfHighlighterTask` |
| | `fetchPdfHighlighterTaskById` | GET | `/pdfHighlighter.json/fetchPdfHighlighterTaskById?pdfHighlighterTaskId=` |
| | `addPdfHighlighterTask` | POST | `/pdfHighlighter.json/addPdfHighlighterTask` |
| | `updatePdfHighlighterTask` | PUT | `/pdfHighlighter.json/updatePdfHighlighterTask` |
| | `deletePdfHighlighterTask` | DELETE | `/pdfHighlighter.json/deletePdfHighlighterTask?pdfHighlighterTaskId=` |
| | `fetchPdfHighlighterFields` | GET | `/pdfHighlighter.json/fetchPdfHighlighterFields?pdfHighlighterTaskId=` |
| | `syncPdfHighlighterFields` | POST | `/pdfHighlighter.json/syncPdfHighlighterFields` |
| | `uploadPdfHighlighterFile` | POST (multipart) | `/pdfHighlighter.json/uploadPdfHighlighterFile?pdfHighlighterTaskId=` |
| | `downloadPdfHighlighterFile` | GET (blob) | `/pdfHighlighter.json/downloadPdfHighlighterFile?pdfHighlighterTaskId=` |

### 4.8 Dynamic Forms

| Service | Method | Verb | Endpoint |
|---|---|---|---|
| `dynamic-form.service.ts` | `addForm` | POST | `/dynamicForm.json/addForm` |
| | `updateForm` | PUT | `/dynamicForm.json/updateForm` |
| | `deleteForm` | DELETE | `/dynamicForm.json/deleteForm?dynamicFormId=` |
| | `fetchAllForms` | GET | `/dynamicForm.json/fetchAllForms` |
| | `fetchFormByFormId` | GET | `/dynamicForm.json/fetchFormByFormId?dynamicFormId=` |
| | `addField` | POST | `/dynamicForm.json/addField?dynamicFormId=` |
| | `updateField` | PUT | `/dynamicForm.json/updateField` |
| | `deleteField` | DELETE | `/dynamicForm.json/deleteField?dynamicFormFieldId=` |
| | `submitForm` | POST | `/dynamicForm.json/submitForm` |
| | `updateSubmission` | PUT | `/dynamicForm.json/updateSubmission` |
| | `deleteSubmission` | DELETE | `/dynamicForm.json/deleteSubmission?dynamicFormSubmissionId=` |
| | `fetchSubmissionsByFormId` | GET | `/dynamicForm.json/fetchSubmissionsByFormId?dynamicFormId=` |
| | `fetchSubmissionBySubmissionId` | GET | `/dynamicForm.json/fetchSubmissionBySubmissionId?dynamicFormSubmissionId=` |
| `_models/dynamic-form.model.ts:155` | `submissionShareUrl` | (URL only) | `/dynamicForm.json/fetchSubmissionByUuid?uuid=` |
| `_models/dynamic-form.model.ts:161` | `formShareUrl` | (URL only) | `/dynamicForm.json/fetchFormByUuid?uuid=` |

### 4.9 Query Engine

`query-engine.service.ts` -- 20 endpoints, all under `/queryEngine.json/`:

- Connections: `connections/add` (POST), `connections/update` (PUT), `connections/delete` (DELETE),
  `connections/fetchAll` (GET), `connections/testConnection` (POST).
- Queries: `queries/add` (POST), `queries/update` (PUT), `queries/delete` (DELETE),
  `queries/fetchAll` (GET), `queries/fetchById` (GET), `queries/validate` (POST),
  `queries/preview` (POST).
- Executions: `executions/execute` (POST), `executions/fetchAll` (GET),
  `executions/fetchByQueryId` (GET).
- Schedules: `schedules/add` (POST), `schedules/update` (PUT), `schedules/delete` (DELETE),
  `schedules/fetchAll` (GET).

`fetchExecutionsByQueryId` is not called from any component.

### 4.10 AI and content tools

| Service | Method | Verb | Endpoint |
|---|---|---|---|
| `ai-agent.service.ts` | `addAgent` | POST | `/aiAgent.json/addAgent` |
| | `updateAgent` | PUT | `/aiAgent.json/updateAgent` |
| | `deleteAgent` | DELETE | `/aiAgent.json/deleteAgent?aiAgentId=` |
| | `fetchAllAgents` | GET | `/aiAgent.json/fetchAllAgents` |
| | `fetchAgentByAgentId` | GET | `/aiAgent.json/fetchAgentByAgentId?aiAgentId=` -- **never called** |
| | `processAdHoc` | POST | `/aiAgent.json/processAdHoc` -- **never called** |
| `_component/ai-agent/ai-agent.component.ts:309` | `copyToolUrl` | (URL only) | `/aiAgent.json/fetchToolByUuid?uuid=` |
| `ollama.service.ts` | `listModels` | GET | `/ollama.json/listModels` |
| | `pullModel` | POST | `/ollama.json/pullModel?name=` |
| | `deleteModel` | DELETE | `/ollama.json/deleteModel?name=` |
| `text-cleaner.service.ts` | `clean` | POST | `/textCleaner.json/clean` |
| `audio-transcript.service.ts` | `extractFromUpload` | POST (multipart) | `/audioTranscript.json/extractFromUpload` |
| | `extractFromBucket` | POST | `/audioTranscript.json/extractFromBucket` |
| `document-converter.service.ts` | `supportedFormats` | GET | `/documentConverter.json/supportedFormats` |
| | `fetchAllTasks` | GET | `/documentConverter.json/fetchAllTasks` |
| | `fetchTaskById` | GET | `/documentConverter.json/fetchTaskById?documentConverterTaskId=` -- **never called** |
| | `convert` | POST (multipart) | `/documentConverter.json/convert` |
| | `deleteTask` | DELETE | `/documentConverter.json/deleteTask?documentConverterTaskId=` |
| `file-chat.service.ts` | `prepareContext` | POST | `/fileChat.json/prepareContext` |
| | `sendMessage` | POST | `/fileChat.json/sendMessage` |
| | `exportFile` | POST | `/fileChat.json/exportFile` |

### 4.11 Notifications and realtime

| Service | Method | Verb | Endpoint |
|---|---|---|---|
| `notification.service.ts` | `list` | GET | `/notification.json/list?unreadOnly&page&limit` |
| | `unreadCount` | GET | `/notification.json/unreadCount` |
| | `markRead` | POST | `/notification.json/markRead/{notificationId}` |
| | `markAllRead` | POST | `/notification.json/markAllRead` |
| `websocketapi.service.ts` | `connect` | SockJS + STOMP | `config.webSocketUrl`, `Authorization: Bearer` connect header; subscribes `/user/queue/reply` and `/user/queue/notifications`; reconnects after 5s on error. |
| `websocketshare.service.ts` | -- | -- | Two `BehaviorSubject`s bridging the socket to components (`getNewValue()` for job updates, `getNewNotification()` for notifications). |

`NotificationService` also holds the app-wide unread-count and recent-list state as
`BehaviorSubject`s, applies live pushes (`handleLivePush`, `:169-183`), and renders relative
timestamps (`timeAgo`, `:141-167`).

### 4.12 Non-HTTP services

| Service | Purpose |
|---|---|
| `alert.service.ts` | Wraps `ngx-toastr`. `formatMessage` unwraps `Error`, arrays, and `{message}` / `{error.message}` / `{response.message}` shapes before falling back to `JSON.stringify` (`:11-47`). |
| `common.service.ts` | `createFile(payload)` -- saves any object as `Raad-Master-Data <uuid>.json` via `file-saver`. Used for the per-row JSON export on Source Task and Source TaskType. |
| `spinner.service.ts` (in `_helpers`) | Global overlay toggle. |

---

## 5. Forms, tables, modals and dialogs

### 5.1 Reactive forms

Every real form is a `ReactiveForms` `FormGroup`. `ngModel` is used separately for toolbar
search/filter inputs (which are not part of any form).

| Screen | Form(s) | Notable structure |
|---|---|---|
| Login | `loginForm` | `username`, `password`, both required. |
| Add/Edit Job | `sourceJobForm` | Nested `taskDetail` group; `scheduler` group added/removed at runtime on execution change (`job.component.ts:322-332`). |
| Add/Edit Task | `sourceTaskForm` | `FormArray` `tagsInfo` (10 blank rows on create), custom `noWhitespaceValidator`, conditional `tenantId` required for Platform Admin. |
| Source TaskType | `sourceTaskTaypeForm` | `topicName` + `partitions` are recombined into `queueTopicPartition` before submit. |
| Lookup | `lookupDataForm` | `lookupValue`'s `required` is dropped when the record is encrypted. |
| XML Configuration | `xmlForm` | `FormArray` `tagsInfo`, 6 blank rows. |
| Q-Message | `qMessageSearcForm` | Filter-only form (`jobQId`, `fromDate`, `toDate`, `jobStatuses`, `jobId`). |
| Search Engine | `tableQueryForm` | Single required `query` textarea. |
| Query Engine | `connectionForm`, `queryForm`, `runForm`, `scheduleForm` | Four independent forms in one component. |
| Storage Connection | `connectionForm` | 18 controls; only `connectionName`, `alias`, `provider` are `required` -- the rest are conditionally shown per provider. |
| Kafka Profile | `profileForm` | 15 controls; `profileName`, `bootstrapServers`, `securityProtocol` required. |
| AI Agent | `agentForm` | `agentName`, `provider`, `model`, `instructions` required; file types live in a `Set` outside the form. |
| Dynamic Form builder | `dynamicFormForm`, `fieldForm` | `fieldWidth` uses `Validators.min(1)`/`max(12)`. |
| Fill Dynamic Form | `fillForm` | Built entirely at runtime; validators derived from each field's `mandatory` / `pattern` / `minLength` / `maxLength` / email type (`fill-dynamic-form.component.ts:132-150`). |
| Users | `userForm`, `resetPasswordForm` | `username` uses `Validators.email`; passwords `Validators.minLength(8)`. |
| Tenants | `tenantForm` | `tenantName`, `tenantCode` required; `tenantCode` disabled on edit. |

Screens with **no** `FormGroup` at all, driven by plain `ngModel` and component fields:
PDF Highlighter detail, Object Browser, Document Converter, Audio Transcript Extractor,
Content Cleaner, Ollama Models, Batch Action.

### 5.2 Tables

Tables are hand-rolled `<table class="table table-modern">`. Despite DataTables being loaded in
`index.html`, **no component initialises it** -- there is no `DataTable(` call anywhere in `src`.
Sorting, filtering and paging are all implemented in component code.

| Screen | Table(s) |
|---|---|
| Home | Job Breakdown drill-down (12 columns incl. an inline stacked bar) |
| Source Job | Job list (10 columns) + expandable detail row |
| Source Task | Task list + linked-jobs sub-table in the expanded row |
| Batch Action | Upload error table (Row / Error) |
| Job History | Run list |
| Job Logs | Log table (one of three view modes) |
| Q-Message | Queue table with computed duration |
| Search Engine | Fully dynamic table from `jsonPayload.column` / `.data` |
| Query Engine | Connections, Queries, Executions, and a preview-result grid (4 tables) |
| Setting | Source TaskType table + linked-task table inside a modal |
| Lookup / Sub-Lookup | Lookup tables |
| Storage Connection | Connections table |
| Kafka Profile | Profiles table |
| Object Browser | Object table + chat-file preview table |
| PDF Highlighter | Task list |
| Dynamic Forms | Form list, submissions list |
| Document Converter | Supported-formats reference + past-conversions table |
| Ollama Models | Model list |
| Users | User list |
| AI Agent | Agent list (table mode) |
| Audio Transcript / Content Cleaner | Bucket-browser tables |

Client-side paging (50/100/150/200 per page, `list-pagination` footer) exists only on
**Source Job** and **Source Task**. Notification Center pages server-side (20/page).
Object Browser uses infinite scroll with a continuation token. Everything else renders the full
result set.

Table/card view toggles, persisted in `localStorage`, exist on **Source Job**
(`sourceJobViewMode`), **Source Task** (`sourceTaskViewMode`), and **AI Agent** (in-memory only).

### 5.3 Modals and dialogs

All modals are Bootstrap 3 markup driven by `data-toggle="modal"` / `data-target="#id"`, closed
imperatively by clicking a `@ViewChild` reference to the modal's close button
(e.g. `this.closebutton.nativeElement.click()`). There is no Angular dialog service.

| Screen | Modal ids |
|---|---|
| Object Browser | `objectPreviewModal`, `newFolderModal`, `renameFolderModal`, `emailShareModal`, `deleteConfirmModal`, `leaveChatConfirmModal`, `closeChatConfirmModal`, `chatFilePreviewModal` (8) |
| Query Engine | `connectionModal`, `deleteConnectionModal`, `queryModal`, `deleteQueryModal`, `runModal`, `scheduleModal` (6) |
| Users | `userModal`, `resetPasswordModal`, `deleteUserModal` (3) |
| AI Agent | `agentModal`, `deleteAgentModal` |
| Dynamic Form builder | `fieldModal`, `deleteFieldModal` |
| Kafka Profile | `profileModal`, `deleteProfileModal` |
| Storage Connection | `storageConnectionModal`, `deleteStorageConnectionModal` |
| Tenants | `tenantModal`, `deleteTenantModal` |
| Setting | `sourceTaskType` (hosts `<source-task-type>`), `deleteSetting`, `linkSourceTaskModal` |
| Source Job | `deleteSourceJob` |
| Source Task | delete-confirm + a `sourceTaskTaype` view modal |
| Dynamic Form list / submissions / view submission | one delete-confirm each |
| PDF Highlighter list | delete-confirm |
| Ollama Models | `deleteModelModal` |
| Document Converter | `deleteTaskModal` |
| Lookup / Source TaskType | the component *is* a modal body, hosted by its parent |

Screens with **no** modal at all: Home, Login, Welcome, Unauthorized, Notification Center,
Job History, Job Logs, Q-Message, Search Engine, Batch Action, Content Cleaner,
Audio Transcript Extractor, PDF Highlighter detail, Fill Dynamic Form, Sub-Lookup,
XML Configuration, Add/Edit Job, Add/Edit Task.

The global `<spinner>` overlay (`app.component.html:150`) is the app's only non-Bootstrap dialog.

---

## 6. Validation, loading, empty and error states

### 6.1 Validation

**Field-level validation exists and is consistent on the reactive forms**, using the same
`submitted && control.errors` pattern:

- Bootstrap 3 style (`has-error` + `.text-danger`): Login, Add/Edit Job, Add/Edit Task,
  Users, Tenants, Kafka Profile, Storage Connection, Query Engine, AI Agent,
  Dynamic Form builder, Fill Dynamic Form.
  Example: `source-job/job/job.component.html:23-25` -- 17 such blocks in that one template.
- Bootstrap 4 style (`is-invalid` + `.invalid-feedback`) in `setting/source-task-type/` and
  `setting/lookup/` -- **these classes are not defined by the Bootstrap 3 stylesheet the app
  loads**, so those messages render unstyled rather than red-boxed.

Submission is blocked by an `if (form.invalid) return;` guard in each component's submit method.
Several screens add hand-written cross-field checks *after* the form guard and surface them as
toasts rather than inline errors:

- `ai-agent.component.ts:248-259` -- endpoint required for non-built-in providers, at least one
  target file type, API key required on create.
- `cu-dynamic-form.component.ts:231-241` -- at least one option for option-based fields,
  duplicate `fieldName` rejection.
- `fill-dynamic-form.component.ts:231-237` -- mandatory checkbox groups (which live outside the
  `FormGroup`) are validated separately.
- `home.component.ts:120-130` -- both dates required, start <= end.
- `audio-transcript-extractor.component.ts:390-401` -- bucket and folder name required before save.

Screens driven by `ngModel` alone have **no field-level validation**: Object Browser,
Document Converter, Audio Transcript Extractor, Content Cleaner, Ollama Models, PDF Highlighter
detail, Batch Action. They rely on `[disabled]` bindings plus post-hoc toasts. For example
`pdf-highlighter-detail.component.ts:173-177` checks the task name only inside `saveTask()`.

### 6.2 Loading states

Three mechanisms coexist:

1. **Global blocking spinner** -- `SpinnerService.show()/hide()` around most HTTP calls. This is
   the dominant pattern (used in ~25 components). It blocks the whole page and gives no
   per-region feedback.
2. **Per-region flags** -- `loadingObjects`, `loadingBuckets`, `directoryStats.loading`,
   `expandedJobQueuesLoading`, `linkedSourceTasksLoading`, `chatPreparing`, `converting`,
   `extracting`, `cleaning`, `pulling`, `testingRowId` / `testingTopicRowId`, `saving`,
   `discoveringBuckets`, `uploading`, `refreshing`. These render inline text or a
   `glyphicon-refresh spin` icon and are the better-behaved parts of the app.
3. **Auto-refresh timers** -- Home dashboard every 60s (`home.component.ts:105`, `silent = true`
   so the spinner does not flash); Job Logs every 5s while the run is non-terminal
   (`job-logs.component.ts:16, 147-156`).

Consistency is uneven: `storage-connection.component.ts:165-175` (`fetchAllConnections`) and
`ollama-models.component.ts:60-75` (`fetchModels`) never call the global spinner, while
`setting.component.ts:63-79` does. Several `SpinnerService.show()` calls immediately followed by
`hide()` guard nothing at all (e.g. `source-task-type.component.ts:88-99`,
`source-task.component.ts` `downloadSourceTask`).

### 6.3 Empty states

Genuine empty states exist on the list-heavy screens and are reasonably well written:

- Source Job / Source Task -- a full `.empty-state` block with icon, title and text
  (`source-job.component.html:297-305`), plus a card-mode variant.
- Home -- `No jobs match "<term>"` in the breakdown table (`home.component.html:210-215`).
- Search Engine -- `No rows match "<term>"`.
- Object Browser -- distinguishes `This folder is empty.` from `No files match your search.`
  (`object-browser.component.html:229-233`), plus an empty-charts tile and an
  "no buckets configured yet" hint that links to `/setting/storageConnection`.
- Notification Center -- `You're all caught up.` / `No unread notifications.`
- Batch Action -- `Upload a file to see results here.`
- Setting's link-task modal -- `No tasks are built on this type yet.`
- PDF Highlighter list, Dynamic Form list, Sub-Lookup, Setting Lookup, Q-Message, Job History,
  Job Logs, Storage Connection -- all have at least one empty-row message.

Screens with **no empty state**: Users, Tenants, AI Agent (table body just renders nothing),
Ollama Models, Document Converter's past-conversions table, Dynamic Form submissions,
View Dynamic Form Submission.

### 6.4 Error states

Error handling is uniform in shape and almost entirely **toast-based**:

```ts
.subscribe((response) => {
    if (response.status === ApiCode.SUCCESS) { ... return; }
    this.alertService.showError(response.message, this.ERROR);
}, (error) => {
    this.alertService.showError(error, this.ERROR);
});
```

This pattern is repeated in essentially every component. Consequences:

- **A failed load leaves the screen looking empty rather than broken.** A 500 on
  `listSourceJob` shows a 1.5-second toast and then the "No jobs found" empty state. There is no
  retry affordance and no persistent error banner anywhere in the app.
- Toasts default to `timeOut: 1500` with `preventDuplicates: true` (`app.module.ts:69-80`), so a
  burst of per-item errors (bulk run, bulk delete) can collapse into a single short toast.
- `AlertService.formatMessage` (`alert.service.ts:11-47`) is what saves this: it unwraps
  `HttpErrorResponse`-shaped objects so the toast usually shows the backend message rather than
  `[object Object]`.

The exceptions -- screens that render errors **in place** rather than as toasts -- are:

| Screen | Field | Location |
|---|---|---|
| Login | `error` string under the form | `login.component.ts:14`, `login.component.html:22` |
| Batch Action | `lastUploadOk` / `lastUploadMessage` + per-row `errors` table | `batch-action.component.ts:30, 36-37` |
| Content Cleaner | `extractError` | `content-cleaner.component.ts:41` |
| Audio Transcript | `extractError`, `saveTranscriptError` | `audio-transcript-extractor.component.ts:45, 56` |
| PDF Highlighter detail | `errorMessage`, `setupError` | `pdf-highlighter-detail.component.ts:65, 73` |
| Object Browser | `previewError`, `chatPrepareError` | `object-browser.component.ts:181, 787` |
| Storage Connection | `discoverBucketsError` | `storage-connection.component.ts:83` |
| Kafka Profile | `modalTestResult` | `kafka-connection-profile.component.ts:49` |
| Query Engine | `connectionTestResult`, `validationResult` | `query-engine.component.ts:41, 50` |

`audio-transcript-extractor.component.ts:245-256` carries a comment explaining that the backend
returns real failures as HTTP errors with a `ResponseDto` body, so the useful message lives at
`error.error.message`, not `error.message` -- a detail most other screens do not handle explicitly
(they lean on `AlertService.formatMessage` instead).

---

## 7. Features with no obvious successor in the new app

Checked against `scheduler1/next` by reading `next/src/app/app.routes.ts`,
`next/src/app/features/shell/shell.ts` (the nav tree), and by searching the whole of
`next/src` for the relevant identifiers and endpoint strings.

### 7.1 PDF Highlighter -- the entire feature is gone

**Highest-value gap.** Searching `next/src` for `pdfhighlight` or `highlighter`
(case-insensitive) returns **zero files**. Nothing in `app.routes.ts` or `shell.ts` mentions it.

What disappears with it:

| Old asset | Location |
|---|---|
| 3 routes (`pdfHighlighter`, `/new`, `/:pdfHighlighterTaskId`) | `app.routing.ts:198-212` |
| 2 components, 943 lines of TS + 349 lines of HTML | `_component/pdf-highlighter/**` |
| 1 service, 9 endpoints | `_services/pdf-highlighter.service.ts` |
| 4 model interfaces + `HIGHLIGHTER_STATUS_LIST` | `_models/object.ts:136-182` |
| The pdf.js canvas + overlay editor | `pdf-highlighter-detail.component.ts` |
| Text-selector derivation from the PDF text layer (`path`, `text`, 30-char `prefix`/`suffix`, `useXpathFirst`) | `pdf-highlighter-detail.component.ts:371-440` |
| Mapping JSON copy/download, per-field selector copy, field reorder, zoom/page nav, read-only mode | `pdf-highlighter-detail.component.ts:528-601` |

The new app still depends on `pdfjs-dist` (`next/package.json`), but only for object preview --
there is no field-mapping editor.

Note also: this feature was the subject of the two most recent commits on the current branch
(`86c2269 PDF Highlighter`, `4c07a7a pdf highlighter xpath added`), i.e. it is **recent work in
the old app that the rewrite has not picked up**.

### 7.2 Dynamic Forms -- submission editing and the per-submission page

The new app has dynamic forms (`next/src/app/features/forms/`, routes `settings/dynamic-forms`
and the public `f/:uuid`), and it can list, view (in an inline panel) and delete submissions.
Three old capabilities have no counterpart:

| Old capability | Old location | Evidence of absence |
|---|---|---|
| **Editing an existing submission** | route `dynamicForm/fill/:dynamicFormId/edit/:submissionId` (`app.routing.ts:233-237`), `fill-dynamic-form.component.ts:73-98, 241-247` | `updateSubmission` appears **nowhere** in `next/src`. The new `form-fill.ts` only calls `submitForm`. |
| **A dedicated per-submission page** with a sibling switcher | route `dynamicForm/submissions/:dynamicFormId/:submissionId`, `view-dynamic-form-submission.component.ts` | `fetchSubmissionBySubmissionId` appears nowhere in `next/src`; the new UI shows a submission from data already in the list (`next/.../dynamic-forms.ts:73` `viewing` signal). |
| **Share URL / share token for one submission** | `_models/dynamic-form.model.ts:153-157`, `view-dynamic-form-submission.component.ts:141-169` | `fetchSubmissionByUuid` appears nowhere in `next/src`. (Form-level sharing survived and improved -- the new `f/:uuid` route is a real public form page.) |

### 7.3 "Test Kafka Connection" per Source TaskType row

`kafkaConnectionProfile.json/testTopic` is called from `setting.component.ts:93-113` behind a
per-row lightning-bolt button (`setting.component.html:177-182`), which resolves the row's topic
name out of `queueTopicPartition` and pings it.

`testTopic` appears **nowhere** in `next/src`. The new `settings/kafka` screen keeps
profile-level `testConnection`, but the per-task-type topic check is gone.

### 7.4 AI agent "Copy tool URL"

`ai-agent.component.ts:304-327` builds `${config.apiUrl}/aiAgent.json/fetchToolByUuid?uuid=<toolUuid>`
and copies it, so an agent can be called as an external tool.

Neither `toolUuid` nor `fetchToolByUuid` appears anywhere in `next/src`. The new agents screen
has no equivalent affordance.

### 7.5 Per-row JSON export on Source Task

`source-task.component.ts` `downloadSourceTask` calls `CommomService.createFile(sourceTask)` to
save a task as JSON.

The new app **does** carry this forward for Source **TaskType**
(`next/.../settings/task-types/task-types.ts:111-118`, whose comment says "as the legacy screen's
download did") but there is no `download`/export method in `next/.../tasks/tasks.ts`. The
Source **Task** JSON export has no successor.

### 7.6 Table / card view toggle, persisted per user

Source Job, Source Task and AI Agent each offer a table-vs-card switch, with the choice stored in
`localStorage` under `sourceJobViewMode` / `sourceTaskViewMode`
(`source-job.component.ts:56, 101-116`; `source-task.component.ts:48`).

`viewMode` appears **nowhere** in `next/src`. The new list screens render one layout.

### 7.7 `tabActive` gating on run history

`SourceJobDetail.tabActive` (`_models/object.ts:81`) disables the History action for jobs that
have never run (`source-job.component.ts:235-237`, `source-job.component.html:129`).

`tabActive` appears nowhere in `next/src`; the new jobs screen does not consume that flag.

### 7.8 Smaller items worth checking during migration

These are old service methods that are **already dead in the old app** and therefore may simply
not need porting -- but they represent backend surface the new frontend also does not touch, so
they are worth a decision rather than an accident:

| Endpoint | Declared at | Called by old UI? | In new app? |
|---|---|---|---|
| `aiAgent.json/processAdHoc` | `ai-agent.service.ts:35` | no | no |
| `aiAgent.json/fetchAgentByAgentId` | `ai-agent.service.ts:31` | no | no |
| `storageConnection.json/fetchConnectionById` | `storage-connection.service.ts:32` | no | no |
| `queryEngine.json/executions/fetchByQueryId` | `query-engine.service.ts:77` | no | no |
| `documentConverter.json/fetchTaskById` | `document-converter.service.ts:22` | no | no |
| `setting.json/fetchKafkaRoute` / `setKafkaRoute` / `deleteKafkaRoute` | `kafka-connection-profile.service.ts:48-59` | no | `fetchKafkaRoute`, `setKafkaRoute`, `deleteKafkaRoute` **do** appear in `next/src` -- so the new app uses routes the old UI never called |

Confirmed as **having** successors (checked, not assumed): dashboard (all six statistics
endpoints, in `next/.../dashboard/dashboard.service.ts`), job run/skip/delete/toggle
(`next/.../jobs/job-actions.ts`), full storage browser API
(`next/.../objects/storage.service.ts`), query engine including `fetchAll` variants
(`next/.../tools/query-engine/query-engine.ts:103-106`), bulk xlsx upload/download for jobs and
tasks (`next/.../bulk/bulk-transfer.ts`), Q-Message (`next/.../queue/`), search engine, XML
builder (with download), lookups and sub-lookups, storage connections, Kafka profiles, tenants,
users, notifications, Ollama models, AI agents, content cleaner, document converter, audio
transcript, object-browser file chat and email share, and the `?bucket&prefix` deep link from a
job row into the object browser (`next/.../objects/objects.ts:173-179`,
`next/.../jobs/jobs.html:317-323`).

---

## Appendix: things that look broken, dead or risky in the old frontend

1. **Hardcoded API host.** `webpack.config.js:52-59` bakes `apiUrl` to
   `<page-protocol>//<page-hostname>:9098/api/v1`. There is no environment file. Deploying the
   frontend anywhere the API is not on port 9098 of the same host requires a rebuild.
2. **`config.sessionId` and `config.transactionId` are dead.** Defined in `webpack.config.js`,
   referenced by nothing in `src`.
3. **Four runtime CDN dependencies** (`src/index.html:10-17`): Google Fonts, Bootstrap 3.4.1,
   jQuery 3.4.1, DataTables 1.10.2. The container has no local copies, so an air-gapped or
   offline deploy renders unstyled and the dropdown-portal script throws.
4. **DataTables is loaded and never used.** No `DataTable(` call exists in `src`. It is ~90 KB of
   CSS+JS downloaded on every page load for nothing.
5. **jQuery is a load-bearing dependency of Angular code.** `app.component.ts:10` declares
   `var $: any` and `:83` binds a Bootstrap dropdown event to trigger a data load; the modal
   close-by-clicking-a-`@ViewChild`-button pattern in ~15 components depends on Bootstrap's jQuery
   plugin being present.
6. **`localStorage` holds the access *and* refresh token** in plaintext under `etl_auth_user`
   (`auth.service.ts:12, 24`), readable by any script on the origin.
7. **Demo credentials are printed on the login page** (`login.component.html:30`:
   `admin@platform.local` / `admin@platform.local`).
8. **`RoleGuard` supports `exactUsernames` that no route uses** (`role.guard.ts:18, 23-24`) -- a
   half-built authorization mechanism.
9. **`setting/lookpXml` is misspelled and unreachable from the UI** (`app.routing.ts:151`); no
   navbar entry links to it.
10. **`setting/queueMessage` and `setting/queryEngine` carry only `AuthGuard`** while every other
    `/setting/*` route is admin-gated. Intentional or not, the prefix is misleading.
11. **Bootstrap 4 validation classes on a Bootstrap 3 stylesheet.**
    `setting/source-task-type/` and `setting/lookup/` use `is-invalid` / `invalid-feedback`,
    which the loaded Bootstrap 3.4.1 does not define -- those validation messages render unstyled.
12. **Failed loads are indistinguishable from empty results.** The universal toast-only error
    path (section 6.4) with a 1.5s timeout means a user who looks away sees an empty table and no
    indication anything went wrong. There is no retry control anywhere.
13. **Bulk operations fan out one request per item from the browser.**
    `source-job.component.ts:370-465` fires N parallel `runSourceJob` / `deleteSourceJob` calls and
    counts completions manually; there is no server-side bulk endpoint and no cancellation.
14. **Clone is a client-side read-then-write.** `cloneSourceJob` (`source-job.component.ts:285-340`)
    and `cloneSourceTask` (`source-task.component.ts`) fetch, reshape and re-POST. Any field the
    reshaping forgets is silently dropped from the clone.
15. **`SourceTaskService` keeps mutable cross-screen state.** `searchText` is stored on the
    singleton (`source.task.service.ts:12, 29-31`) and re-sent when a later caller omits one, so a
    search typed on one screen can silently filter another.
16. **Two `deleteX` methods use `PUT`**: `setting.json/deleteLookupData` and
    `kafkaConnectionProfile.json/deleteProfile`. Harmless but inconsistent with the DELETE verbs
    used elsewhere, and easy to mis-port.
17. **`patch.js` / `patch_dist.js` run with `|| true`** (`Dockerfile:26, 33`). If either fails the
    build proceeds and the bundle ships with the regex bug they exist to fix.
18. **No lazy loading.** One eager `NgModule` with 41 components pulls the entire app -- including
    pdf.js, echarts and marked -- into the initial load.
19. **Unused files carried in the source tree**: `_content/icon.html` and
    `_content/svg-icons-animate.css` (an SVG demo page wired to nothing),
    `_content/slide-in-out.animation.ts` (imported by no component),
    `_helpers/pretty-print.ts` (`prettyPrint` imported by nothing),
    `_models/object.ts` `HttpRequestInfo` / `FileInfo`, `global-config.ts` `UserType`.
    `ng2-toastr` is in `package.json` but never imported.
20. **`global-config.ts` contains a literal 1,440-element `TIMES` array** (`:96-241`) instead of
    generating it -- 145 lines of the file are a hardcoded list of every minute in a day.
21. **`object-browser.component.ts` is 1,904 lines in a single class** covering browsing, charts,
    preview, in-place editing, bulk actions, email share and an AI chat client with its own
    fenced-file extraction protocol. It is the highest-risk file to port.
22. **Duplicate export in a barrel.** `_services/index.ts` exports `./alert.service` twice
    (lines 1 and 3).
