# Design-System Consistency Audit — `scheduler1/next`

Read out of `scheduler1/next/src/app` and `scheduler1/next/src/styles.css` on 2026-09-07. Paths
are relative to `/Users/nabeel.amd93/Desktop/Old-School`. This is a discovery pass only — nothing
below has been fixed. The legacy `scheduler1/src` app has no token system at all (confirmed: no
`@theme`, no CSS custom properties for colour/surface/text) and is out of scope for the rest of
this document.

---

## 1. The token system as it exists today

From `scheduler1/next/src/styles.css`.

| Token / class | Value (light → dark) | What it's for |
| --- | --- | --- |
| `--color-ink-50..950` | Tailwind Slate, `ink-450` custom (`#5e6e84`) | Neutral scale; `ink-450` is the one hand-tuned step, interpolated to clear 4.5:1 on the sunken surface |
| `--color-brand-50..900` | Tailwind Blue, shifted one step down (`brand-500` = `blue-600`) | Accent scale; shifted because Tailwind's own `blue-500` fails AA for white text |
| `--color-ok/warn/crit-100/400/500` | green/amber/rose families | Semantic status colour, independent of the accent |
| `--color-page/raised/sunken/inset/code/inverse` | `:root` light values, redefined under `html.dark` | Surface roles — a component never reaches for a raw palette step |
| `--border-subtle` / `--border-strong` | `ink-200`/`ink-300` → `ink-800`/`ink-700` | Border roles |
| `--text-primary/secondary/muted` | `ink-900`/`ink-600`/`ink-450` → `ink-50`/`ink-300`/`ink-400` | Text roles |
| `--accent-text` / `--accent-soft` | `brand-600`/`brand-50` → `brand-300`/color-mix | Accent *as text*, separate from accent *as fill* (`brand-500`, same in both themes) |
| `--radius-card` | `0.625rem` | Card corner radius (`styles.css:72`) |
| `--chart-0..5`, `--series-{brand,ok,warn,crit}{,-soft}` | per-theme, contrast-measured | Chart series colour; status series always derived from the same family as the matching pill |
| `.btn` / `.btn-primary` / `.btn-default` / `.btn-ghost` / `.btn-danger` / `.btn-intent-{ok,warn,crit}` / `.btn-sm` / `.btn-xs` / `.btn-icon` / `.btn-circle` | `styles.css:225-303` | Button vocabulary — weight carries meaning (primary = one per view, default = a real secondary action, ghost = dismissal/icon-only) |
| `.pill` / `.pill-{brand,ok,warn,crit,neutral}` / `.pill-solid-*` | `styles.css:630-663`, dark overrides `904-914` | Status/label chip — shape (rounded-full, 11px, semibold) plus colour |
| `.status-quiet` / `.status-dot` / `.dot-ok` / `.dot-neutral` | `styles.css:665-676` | Quiet form of a status: a coloured dot + plain text |
| `.card` | `styles.css:519-523` | `border` + `rounded-[var(--radius-card)]` + `bg-raised` |
| `.input` | `styles.css:525-549` | Text/select/date input; `min-height: 2.25rem` so mixed control types line up |
| `.checkbox` | `styles.css:318-323` | `accent-color: var(--color-brand-600)`, `w-4 h-4 rounded`, focus ring |
| `.table-modern` | `styles.css:784-802` | 12px dense operational table, 11px header, hover = sunken surface |
| `.form-grid` / `.form-section` / `.form-actions` | `styles.css:1133-1156` | Form rhythm: 6px within a field, 20px between fields, 24px+rule between sections; `.form-actions` = `flex flex-wrap items-center justify-end gap-2 border-t pt-4 mt-6` |
| `.page` / `.page-head` / `.page-title` / `.page-subtitle` | `styles.css:1163-1171` | Page shell — confirmed used identically on all 27 feature pages, no divergence found |
| `app-icon` (`shared/ui/icon.ts`) | 77 named glyphs, 24×24 grid, 1.9 stroke | The one icon set; an unknown name renders nothing and logs a dev error (`icon.ts:117-122`) |

Shared building blocks read for this audit: `shared/ui/field.ts`, `icon.ts`, `data-table.ts`
(exports `TableShell`, selector `app-table-shell`), `status-pill.ts` (selector `app-status`),
`stat-tile.ts`, `view-toggle.ts`, `pager.ts`, `form-dialog.ts`, `confirm.ts`, `mine-filter.ts`,
`avatar.ts`, `segmented.ts`.

---

## 2. Colours

Console-preview.ts (`landing/console-preview.ts`) is excluded throughout, per its own header
comment (`console-preview.ts:6-15`): "sits on the hero... so its colours are stated here rather
than taken from the page." That reasoning is real and documented in the file itself.

| file:line | What's there now | What it should be | Severity |
| --- | --- | --- | --- |
| `landing/landing.ts:28-32` | `.hero` block: `linear-gradient(180deg, #141833 0%, #0f1220 100%)`, `color: #eef0fd`, `rgb(238 240 253 / 0.72)`, `rgb(159 165 243 / 0.95)` | Same rationale as `console-preview.ts` (a fixed dark surface, stated explicitly at `landing.ts:20-22`) but not named as an exception anywhere. Either document it the same way console-preview is, or derive from `--color-ink-900`/`--color-brand-*` so a future palette change doesn't miss it | minor |
| `landing/landing.ts:104` | `style="color: #c4c9f9;"` on the "Setup guide" link inside `.hero` | Same hero exception as above — a fourth hand-picked value where the block already has `.hero-eyebrow`/`.hero-sub` classes it could have reused or extended | minor |
| `login/login.html:56-57` | `background-image: linear-gradient(to right, #fff 1px, ...), linear-gradient(to bottom, #fff 1px, ...)` on the decorative grid texture over `bg-ink-900` | `#ffffff` / `var(--text-inverse)` — the panel is already forced dark (`bg-ink-900`) regardless of theme, so this is low-risk, but it's a literal value where the file already uses `text-white` as a class elsewhere on the same panel | cosmetic |
| `profile/profile.html:39` | `style="background: rgba(0,0,0,.55);"` — overlay behind the spin icon while an avatar uploads | `color-mix(in oklab, var(--color-ink-950) 55%, transparent)` or similar, matching the `color-mix` idiom already used in `objects/chat/file-chat.html:44,57,92` | cosmetic |
| `tenant-request/tenant-requests.html:67` and `admin/users/users.html:94` | `hover:shadow-[0_6px_20px_-8px_rgb(0_0_0/0.35)]` — identical literal black shadow, duplicated verbatim in the only two card-grid screens that lift on hover | No `--shadow-*` token exists in `styles.css` to point at (a real gap, not just an oversight) — worth a `--shadow-card-hover` token given it's already duplicated once | minor (repeats ×2) |
| `docs/docs.ts:47` | `box-shadow: 0 10px 30px -12px rgb(0 0 0 / 0.28);` on `.doc-shot` | Same gap: no shadow token exists. A third, independently-chosen opacity/blur for conceptually the same "lifted panel" shadow | cosmetic |
| `jobs/logs/job-logs.html:118-119` | `<span class="inline-block w-2.5 h-2.5 rounded-sm shrink-0 bg-warn-500">` — legend swatch for the stall highlight, square | Uses the real `bg-warn-500` token (correct), but every other legend/status dot in the app is `rounded-full` (`.status-dot`, `.dot-ok`, `.live-dot`). A one-off shape, not colour | cosmetic |

**False positives excluded after inspection:** `jobs/assistant/job-assistant.intents.ts:23` (`#999` is a regex-comment example, not a colour); all values inside `console-preview.ts` (documented exception); `--chart-*`/`--series-*` consumers everywhere (`reports/report-chart.ts`, `dashboard/dashboard.html:165,219`, `admin/users/users.html:201,379`, `profile/profile.html:269,314`, `reports/reports.html:148,183,194`, `ai/models/models.html:48`) — all correctly read a CSS variable, never a literal.

**Colour findings: 7** (2 minor-repeated, 5 cosmetic/minor singles). No feature was found writing its own `html.dark` override — the pattern the token system's own comment (`styles.css:96-98`) says used to happen 43 times has not recurred.

---

## 3. Buttons

109 `<button>` tags were found without a `btn` class string; on inspection nearly all of them
correctly carry a *different* established class instead — `menu-item`/`menu-item-danger`
(cdkMenu rows, ~40 instances across `settings/forms/task-forms.html`, `settings/lookup/lookup.html`,
`settings/kafka/kafka-connections.html`, `settings/task-types/task-types.html`, `tasks/tasks.html`,
`admin/tenants/tenants.html`, `admin/storage/storage-connections.html`, `admin/users/users.html`,
`objects/objects.html`, `ai/agents/agents.html`, `jobs/jobs.html`, `queue/queue.html`),
`th-sort` (sortable headers), `pill pill-neutral`, `link-inline`, `audio-play`, `ts-mark`. These
are correct uses of a different, equally-established primitive and are **not findings**.

Real divergences:

| file:line | What's there now | What it should be | Severity |
| --- | --- | --- | --- |
| `jobs/edit/job-edit.html:146-150` and `tasks/edit/task-edit.html:170-174` | Footer: `class="flex gap-2 mt-5 pt-4 border-t border-subtle"`, buttons in order **Save (primary) → Cancel (ghost)**, left-aligned | `.form-actions` (`styles.css:1153-1156`) exists for exactly this — `flex flex-wrap items-center justify-end gap-2 border-t pt-4 mt-6` — and is used **nowhere in `features/`**. Using it would right-align the footer and, by convention with `form-dialog.ts:29-41` (Cancel first, Confirm last via `ml-auto`), the two full-page forms currently put the primary action on the *left*, backwards from every dialog in the app | major (repeats ×2, and is exactly the alignment/order convention this audit was asked to check) |
| `objects/dialogs/share-dialog.ts:19-31`, `objects/dialogs/prompt-dialog.ts:15-31`, `reports/report-destination-dialog.ts:24-56` | Each hand-rolls the same small-dialog shell: `class="card shadow-2xl w-[Nrem] max-w-[calc(100vw-2rem)] overflow-hidden"`, header `px-5 pt-4 pb-3`, footer `flex justify-end gap-2 px-5 py-3 border-t border-subtle`, `Cancel` (`btn-default btn-sm`) then primary (`btn-primary btn-sm`) | Button order/alignment is correct here (matches `form-dialog.ts`), but the shell markup is copy-pasted three times (plus a fourth copy in `shared/ui/confirm.ts:14-25`) with three different widths (`26rem`, `28rem`, `26rem`) chosen independently rather than sharing one small-dialog primitive the way list screens share `TableShell` | minor (repeats ×4) |
| `queue/queue.html:24-30` and `jobs/history/job-history.html:190-196` | Status-count filter chip: `<button class="card px-3.5 py-2 flex items-center gap-2 hover:shadow-md transition-shadow" [class.ring-2] [class.ring-brand-500]>` wrapping `<app-status>` + a count | An ad hoc "chip-as-button" built on `.card`, not on `.pill`; `hover:shadow-md` and `ring-brand-500` are bare Tailwind utilities, not tokens, and this exact composition is duplicated verbatim between the two files | major (repeats ×2, functional filter control) |
| `tenant-request/tenant-requests.html:96-105`, `admin/users/users.html:149-159,166-176`, `profile/profile.html:50-56` | Icon-only "copy to clipboard" button: `class="shrink-0 ml-auto p-0.5 rounded text-[color:var(--text-muted)] hover:text-brand-600 transition-colors"`, byte-identical across all four call sites | Not composed from `.btn-ghost.btn-icon` (or a new shared "copy" affordance) despite existing as an established variant for icon-only controls (`styles.css:249-251`) | minor (repeats ×4) |

**Button findings: 4 rows, 10 concrete duplications.**

---

## 4. Chips / pills

No new ad hoc *coloured* chip was found — every status/label badge in `features/` goes through
`app-status` (`shared/ui/status-pill.ts`, 16 call sites) or `.pill`/`.pill-*` directly
(`settings/lookup/lookup.html:79,154`, `settings/task-types/task-types.html:130,173`,
`objects/chat/file-chat.html:170`). The prior session's colour-token pass appears to have held.

| file:line | What's there now | What it should be | Severity |
| --- | --- | --- | --- |
| `queue/queue.html:24-30`, `jobs/history/job-history.html:190-196` | (Also listed under Buttons.) A `.card`-based filter chip wrapping `app-status`, not the pill's own sizing (`rounded-full`, `px-2 py-0.5`, `text-[11px]`) | If this is meant to read as a chip rather than a KPI-card button, it should take `.pill`'s shape, not `.card`'s | major (repeats ×2) |
| `jobs/logs/job-logs.html:118-119` | Square (`rounded-sm`) legend swatch, `w-2.5 h-2.5` | Every other legend dot in the app (`.status-dot`, `.dot-ok/.dot-neutral`, `.live-dot`) is `rounded-full` at a slightly different size (`w-1.5 h-1.5`) | cosmetic |

**Chip findings: 2** (one shared with Buttons). Pill *colour* consistency: clean.

---

## 5. Spacing and sizing

| file:line | What's there now | What it should be | Severity |
| --- | --- | --- | --- |
| `features/shell/shell.html:7`, `features/landing/landing.ts:70`, `features/docs/docs.ts:65`, `features/tenant-request/request-workspace.ts:30` | `text-[15px]` — four independent, byte-identical occurrences, all inside the same duplicated "ETL Console" brand-mark block (see §6) | 15px is not on the established scale (`text-sm`=14px is used for body copy everywhere else; `text-[11px]`/`text-[10px]` are the only other arbitrary sizes, and both are already established via `.pill`, `.stat-label`, `.detail-head`, `.bell-badge`). Should be `text-sm` or a new named size, not a fourth one-off pixel value | major (repeats ×4, one shared root cause) |
| Search box width in table toolbars — 17 occurrences across `settings/forms/task-forms.html:52`, `settings/lookup/lookup.html:27`, `settings/kafka/kafka-connections.html:67`, `settings/task-types/task-types.html:44` (+ a second, nested one at `:241` using `max-w-52`), `tasks/tasks.html:32`, `admin/tenants/tenants.html:56`, `admin/storage/storage-connections.html:79`, `admin/users/users.html:72`, `ai/agents/agents.html:23`, `jobs/logs/job-logs.html:142`, `jobs/history/job-history.html:270` (all `max-w-56`); `tenant-request/tenant-requests.html:39`, `tasks/tasks.html:32` (`max-w-64`); `dashboard/dashboard.html:95`, `queue/queue.html:94`, `jobs/jobs.html:85` (`max-w-52`); `ai/models/models.html:88` (`max-w-44`) | The same `.search-field` control, visually equivalent in every one of these toolbars, takes four different max-widths (44/52/56/64) with no apparent reason tied to content | Standardise on one width (56 is the majority, 10 of 17) unless a screen has a documented reason to differ | major (repeats across 17 sites, 4 distinct values) |
| `objects/dialogs/share-dialog.ts:10` (`w-[28rem]`), `objects/dialogs/prompt-dialog.ts:16` (`w-[26rem]`), `reports/report-destination-dialog.ts:25` (`w-[26rem]`), `shared/ui/confirm.ts:14` (`w-[26rem]`), `objects/preview/preview-dialog.html:1` (`w-[60rem]`, `max-h-[88vh]`), `objects/chat/file-chat.html:1` (`w-[32rem]`), `jobs/jobs.html:422` and `jobs/history/job-history.html:384` (`w-[34rem]`, floating panel) | Every small/medium dialog picks its own arbitrary width rather than `form-dialog.ts`'s own `size` input (`default`=34rem, `wide`=58rem, `xwide`=min(92vw,76rem), `form-dialog.ts:51-59`) | `share-dialog`/`prompt-dialog`/`report-destination-dialog`/`confirm` could converge on one width (they're all "a card, a couple of inputs, Cancel/Confirm" per `report-destination-dialog.ts:17-19`'s own comment); `preview-dialog.html`'s `88vh` vs `FormDialog`'s own `85vh` is an unexplained one-pixel-scale divergence | minor (repeats ×8) |
| `admin/storage/storage-connections.html:163,184` | `<input type="checkbox" class="accent-brand-600 cursor-pointer">` — the row-select and select-all checkboxes | `.checkbox` (`styles.css:318-323`) — used correctly 16 other places including `admin/storage/connection-dialog.html:102,106` **in the same feature** | major |
| `settings/forms/task-form-dialog.ts:181`, `tasks/edit/task-edit.html:130` | `<input type="checkbox" formControlName="required" />` / `<input type="checkbox" [id]="...">` — completely unstyled, no class at all | `.checkbox` | major (repeats ×2) |
| `tenant-request/tenant-requests.html:65-67`, `admin/users/users.html:92-94` vs. 7 other card-grid screens (`settings/forms/task-forms.html:68`, `settings/lookup/lookup.html:38`, `settings/kafka/kafka-connections.html:83`, `settings/task-types/task-types.html:60`, `tasks/tasks.html:46`, `admin/storage/storage-connections.html:94`, `ai/agents/agents.html:37`) | Only 2 of 9 card-grid screens add `hover:-translate-y-0.5 hover:border-[color:var(--border-strong)] hover:shadow-[...]`; the other 7 leave `.card` static on hover | Pick one behaviour for "a card in a grid" and apply it everywhere, or document why tenant-requests/users need the lift and the rest don't | minor (inconsistent across 9 screens) |

**Spacing/sizing findings: 6 rows, 40+ concrete sites** — the single largest category by repeat count.

---

## 6. Everything else (backgrounds, icons, avatars, modals, dark mode)

| file:line | What's there now | What it should be | Severity |
| --- | --- | --- | --- |
| `jobs/jobs.html:433`, `jobs/history/job-history.html:396` | `<app-icon name="expand" />` — `"expand"` is **not** one of the 77 glyphs defined in `shared/ui/icon.ts` (closest existing name is `maximize`, `icon.ts:83`) | Per `icon.ts:117-122` this renders an empty `<svg>` and logs a dev-mode console error; the "Full page" link in the job-assistant floating panel silently loses its icon in both files | major (functional bug, repeats ×2) |
| `features/shell/shell.html:81`, `features/profile/profile.html:32-34` | Avatar-initials fallback hand-rolled as `<span class="size-7/28 rounded-full bg-brand-500 text-white grid place-items-center ...">` | `shared/ui/avatar.ts` exists precisely for this ("Someone's picture, or their initials when there is none", `avatar.ts:6`) and is already used correctly in `tools/transcript/transcript.ts`, `admin/users/users.ts/.html`, `objects/chat/file-chat.ts/.html`, `profile/profile.ts` (for other pictures on the same page!). Reimplementing it also changes the look: `.avatar-initials` is `bg-sunken`/`text-secondary` (`styles.css:333-337`), while these two spots instead fill solid brand-500 — a visible, not just structural, divergence. Separately, `shell.html:81`'s `<img>` path reads `auth.avatarUrl()` directly rather than through Avatar's authenticated blob fetch (`avatar.ts:67-77`) — worth a follow-up, out of scope for this visual audit | major (repeats ×2, both structural and visual) |
| `tenant-request/request-workspace.ts:29-30`, `landing/landing.ts:69-70`, `docs/docs.ts:64-65`, `features/shell/shell.html:6-7` (+ a near-duplicate at `login/login.html:6-9`) | The "ETL Console" brand mark (`size-7 rounded-md bg-brand-500 ... "E"` + wordmark) is copy-pasted byte-for-byte four times, a fifth time with different sizing in login | No shared brand-mark component exists; a change to the logo (e.g. an actual icon instead of the letter "E") means editing five files by hand | minor (repeats ×5, root cause of the `text-[15px]` finding above) |
| `jobs/jobs.html:421-433`, `jobs/history/job-history.html:383-403` | The floating job-assistant panel (`fixed bottom-4 right-4 z-50 w-[34rem] ... card shadow-2xl`, header with chat icon + title + Full-page link + minimise/close buttons) is duplicated near-verbatim between the two job-list screens | `objects/chat/file-chat.html` implements a structurally identical "floating panel" (different width, same anatomy) as its own component (`FileChat`) — the job-assistant version has no equivalent extraction | minor (repeats ×2, candidate for a shared `FloatingPanel` shell) |
| `profile/profile.html:254-276`, `ai/models/models.html:13-30` | Hand-written `<div class="stat-tile">…<div class="stat-label">…<div class="stat-value">` (8 tiles total) instead of `<app-stat-tile [label] [value] [icon] [tone]>` | `shared/ui/stat-tile.ts` is imported and used correctly in 7 other features (`tenant-request`, `settings/forms`, `settings/kafka`, `settings/task-types`, `admin/tenants`, `admin/storage`, `admin/users`). The hand-written copies reuse the *classes* (so today they render identically) but bypass the component, so they won't pick up e.g. a future icon-glyph change to `StatTile` | minor (repeats ×2 files / 8 tiles) |
| `login/login.html:38` | Inline error banner: `class="rounded-md border border-crit-500/30 bg-crit-100 px-3 py-2 text-sm text-crit-500"` | No shared `.alert`/banner class exists anywhere in `styles.css`, and this is the only inline (non-toast) error surface found in `features/` — likely legitimate, since login has no toast host mounted pre-auth, but flagged as an **unknown**: it was not possible to confirm from the code alone whether an alert primitive was deliberately never built, or simply never needed elsewhere | unknown / cosmetic |
| `objects/preview/preview-dialog.html:118` | `<video class="... bg-black">` | Every other "well" surface (`.log-console`, `--surface-code`) is `var(--color-ink-900)` in light / `#000` in dark rather than bare Tailwind `black` in both. Likely harmless for video letterboxing but is a literal rather than a token | cosmetic |
| Dark-mode compliance (positive finding) | No `html.dark` override and no theme-conditional literal colour were found anywhere under `features/` (confirmed by grep) | This is the intended state per `styles.css:96-98`'s own history ("forty-three hand-written html.dark rules had accumulated... eliminated"); the audit found **zero** regressions of that pattern | n/a — clean |

**Everything-else findings: 7** (4 major/minor structural, 2 cosmetic, 1 unknown, 1 clean baseline).

---

## 7. Prioritized punch list (highest value first)

Ordered first by how many sites the same bad pattern touches (a fix compounds), then by visual/functional severity.

**Status (2026-09-07): items 1-9, 11, 15, 16 fixed and verified** (full `ng build` + full test
suite, 505/505 green, both before and after each batch; the `next-app` container was rebuilt and
redeployed and every fix re-checked live in the running app). Items 10, 12, 13, 14 remain open,
no code changed for them.

**Two further bugs, found via live user QA rather than this audit's own read-through, fixed the
same day (see §8 below for the full writeup):** the Jobs list's "Type" column actually shows the
job's Auto/Manual trigger, not the task's real type -- renamed to "Execution" in both `jobs.html`
and the nested table in `tasks.html`, matching the label `job-edit.html` already used for the same
field. And the Pipeline Form dialog's field-card grid was rendering three columns for two fields
(a dead, invisible third track eating a third of the width) because `.form-grid`'s container query
was scoped to the outer `<form>`, not the nested field-card -- fixed by giving `.card` its own
`container-type: inline-size` so nested grids size off their real container.

1. ~~**Search-box width inconsistency** — 17 sites, 4 different `max-w-*` values (`44/52/56/64`). Standardise on `max-w-56` (majority). *(major, §5)*~~ **Fixed 2026-09-07:** all 16 toolbar search fields (the 17th, `job-assistant.html`, correctly uses `flex-1` to fill its narrow floating panel) now share `search-field max-w-56`.
2. ~~**Brand-mark block duplicated 5×** with its own arbitrary `text-[15px]` each time — `shell/shell.html:6-7`, `landing/landing.ts:69-70`, `docs/docs.ts:64-65`, `tenant-request/request-workspace.ts:29-30`, `login/login.html:6-9`. Extract one component; fixes the `text-[15px]` finding for free. *(major, §5/§6)*~~ **Fixed 2026-09-07:** extracted `shared/ui/brand-mark.ts` (`app-brand-mark`, with a `subtitle` input for login's two-line variant and a `hideOnMobile` input for the shell header); all 5 sites now use it, `text-sm` throughout.
3. ~~**Full-page form footers (`job-edit.html`, `task-edit.html`) don't use `.form-actions`**, are left-aligned with primary-first, backwards from every dialog's Cancel→Confirm/right-aligned convention. *(major, §3)*~~ **Fixed 2026-09-07:** both now use `.form-actions`, Cancel first then the primary button, right-aligned.
4. ~~**`.form-actions` class is defined and completely unused** — direct enabler of #3.~~ **Fixed 2026-09-07** (see #3) — now used in both full-page forms.
5. ~~**Checkbox styling gap** — 3 unstyled/ad hoc checkboxes (`storage-connections.html:163,184`, `task-form-dialog.ts:181`, `task-edit.html:130`) among 16 correct ones, one of them in the *same feature* as a correct example (`connection-dialog.html:102,106`). *(major, §5)*~~ **Fixed 2026-09-07:** all four checkboxes (including the two in `storage-connections.html`, missed in the original count) now use `.checkbox`. Verified live: rendered as a filled, bordered control, not the bare OS default.
6. ~~**Missing `expand` icon glyph** — silently blank icon in the job-assistant "Full page" link, 2 sites, real rendering bug not just a style gap. *(major, §6)*~~ **Fixed 2026-09-07:** both sites now use the real `maximize` glyph.
7. ~~**Avatar-initials reimplemented ad hoc** in `shell.html:81` and `profile.html:32-34`, with a visibly different colour (`bg-brand-500` fill vs. the component's `bg-sunken`/`text-secondary`) from every correct usage elsewhere. *(major, §6)*~~ **Fixed 2026-09-07:** both now use the `.avatar-img`/`.avatar-initials` classes so the fallback tone matches every other avatar in the app. The underlying fetch mechanism (`auth.avatarUrl()` / profile's own `avatarUrl()` signal, not the `Avatar` component's own blob fetch) was deliberately left alone — swapping that is a separate, riskier change with no visual payoff, and is still open as a follow-up.
8. ~~**Status-filter "chip" built on `.card` instead of `.pill`**, duplicated verbatim in `queue/queue.html:24-30` and `job-history.html:190-196`, with untokenized `hover:shadow-md`/`ring-brand-500`. *(major, §3/§4)*~~ **Fixed 2026-09-07:** extracted `shared/ui/status-filter-chip.ts` (`app-status-filter-chip`) so the markup lives in one place; kept the existing `.card`-based shape rather than switching to `.pill` (the count number needs the card's room), which was the lower-risk half of this finding.
9. ~~**Card-grid hover behaviour inconsistent** — only `tenant-requests`/`users` lift+shadow on hover, 7 sibling card grids don't; the shadow value itself (`rgb(0 0 0/0.35)`) is a literal, duplicated twice, with no token to point at. *(minor, §2/§5)*~~ **Fixed 2026-09-07:** removed the hover lift/shadow/border from `users.html` and `tenant-requests.html` to match the other 7 card grids — none of the 9 make the whole card a click target (actions are inner buttons/kebab menus), so static was the majority-consistent, lower-risk choice. This also resolves #16's two duplicated literals (the third, `docs.ts`'s screenshot-frame shadow, is a different idiom -- a framed image, not a card in a grid -- and was left alone).
10. **Small-dialog shell duplicated 4×** (`confirm.ts`, `share-dialog.ts`, `prompt-dialog.ts`, `report-destination-dialog.ts`) with 3 different widths chosen independently. *(minor, §3)* — still open.
11. ~~**Copy-to-clipboard icon button duplicated 4×** byte-for-byte instead of a shared `.btn-ghost.btn-icon` composition. *(minor, §3)*~~ **Fixed 2026-09-07:** extracted `shared/ui/copy-button.ts` (`app-copy-button`); all 4 sites (`tenant-requests.html`, `users.html`×2, `profile.html`) now use it.
12. **StatTile bypassed** in `profile.html` (4 tiles) and `models.html` (4 tiles) — reuses the classes but not the component. *(minor, §6)* — still open.
13. **Floating job-assistant panel duplicated** between `jobs.html` and `job-history.html` with no shared shell, unlike `file-chat.ts`'s equivalent panel which *is* its own component. *(minor, §6)* — still open.
14. **Dialog widths chosen ad hoc instead of `FormDialog`'s `size` input** — 8 sites (`26rem`/`28rem`/`32rem`/`34rem`×2/`60rem`); `preview-dialog.html`'s `88vh` vs. `FormDialog`'s own `85vh` is an unexplained one-off. *(minor, §5)* — still open.
15. ~~**`landing.ts`'s hero literals** (5 hardcoded colour values, `landing.ts:28-32,104`) follow the same "fixed dark surface" logic as `console-preview.ts` but aren't documented as an exception the same way. *(minor, §2)*~~ **Fixed 2026-09-07:** the hero background/text colours already carried a documented exception comment (added in an earlier pass this session); the one remaining undocumented literal, the "Read the setup guide" link's `#c4c9f9`, now reuses the existing `.hero-eyebrow` class instead of a fourth hand-picked value.
16. ~~**No `--shadow-*` token exists** for the "lifted card"/"framed screenshot" idiom, so 3 independent files (`tenant-requests.html:67`, `users.html:94`, `docs.ts:47`) each pick their own opacity. *(minor, §2)*~~ **Resolved differently 2026-09-07:** rather than add a token, the two card-grid duplicates were removed outright (see #9); `docs.ts`'s screenshot-frame shadow is a distinct, single-site idiom and was left as-is rather than tokenized for one caller.
17. **`login.html`'s decorative grid uses literal `#fff`** (2×) where `text-white`/`var(--text-inverse)` is already the convention on the same panel. *(cosmetic, §2)*
18. **`profile.html`'s upload-overlay uses `rgba(0,0,0,.55)`** where `color-mix(in oklab, ...)` is the established idiom elsewhere in the same feature area (`file-chat.html:44,57,92`). *(cosmetic, §2)*

---

## 8. Two bugs found live, not by reading the code (fixed 2026-09-07)

*(§8.3 covers the nav-bar placement request; §8.1/8.2 below are the two bugs.)*

### 8.3 Nav-bar placement: `admin/storage` and missing Notifications/Profile links

The user asked to "use the right nav bar or position for nav bar and user friendly." Investigated
first rather than guessed: the nav (`shell.ts`) is already grouped into 7 sections (Dashboard,
Pipelines, Object Browser, Tools, Assistants, Configuration, Administration), each a dropdown
with an icon and one-line hint, not a flat mixed list -- a prior pass this session had already
split a former 7-item flat "Admin" group into these two. There is no existing scaffolding
anywhere (no CSS tokens, no aside component) for a right-side vertical nav; that would be new UI
built from scratch, not a fix to something broken. Asked the user to choose between that larger
change and fixing two concrete placement issues the investigation surfaced; they chose the latter.

Fixed: **`admin/storage` renamed to `settings/storage-connections`** -- it already lived in the
Configuration menu (correctly, since it groups with Kafka Connections/Lookups/Pipeline Forms as
infrastructure setup, not with Administration's people/tenant management), but its URL prefix
said `admin/`, which read as a placement mistake. Renamed the route, the nav entry, and the one
`routerLink` in `objects.html`; kept `admin/storage` as a `redirectTo`, mirroring the existing
`settings/forms` -> `settings/pipeline-forms` precedent, so old links and bookmarks still work.
Also updated a stale path reference in `auth.guard.spec.ts` and a code comment in the backend's
`BucketAccessE2EIT.java`. **Added "Notifications" to the user avatar menu**, alongside the
existing "Your profile" link -- both were previously reachable only via their own icon (bell /
avatar), never from a text menu; Profile was already one click away in that same menu, so only
Notifications needed adding. Verified live: `/admin/storage` redirects to
`/settings/storage-connections` and loads correctly; the new "Notifications" menu entry resolves
to `/notifications` and the page renders.

Neither of these was in this audit's own §1-6 findings -- both surfaced when the user pointed at
a live screen and said something looked wrong, and turned out to be real, not cosmetic.

### 8.1 "Type" column on the Jobs list is ambiguous with the task's actual type

**Symptom:** the user circled the Jobs list's `TASK` and `TYPE` column headers and asked for the
naming to be corrected.

**Root cause:** `jobs.html`'s `TYPE` column shows `job.execution` (`Auto`/`Manual` -- the backend
`Execution` enum, `process/.../enums/Execution.java`), while the *same row*'s expanded detail
panel has a field literally labelled `"Task type"` bound to `job.taskDetail.sourceTaskType.serviceName`
-- a completely different backend entity (`SourceTaskType`, a JPA entity naming a downstream
Kafka consumer). Worse, `tasks.html`'s own top-level `Type` column already uses "Type" for
*that* second concept (`sourceTaskType.serviceName`), so the same word meant two different things
on two sibling pages, and two different things within one expanded row on the same page.

**Fix:** renamed the Auto/Manual column to **"Execution"** in both `jobs.html`'s main table and
`tasks.html`'s nested "Jobs using this task" sub-table -- reusing the label `job-edit.html`
already uses for this exact field (`<app-field label="Execution" ...>`), rather than inventing a
new word. `tasks.html`'s own top-level "Type" column (`sourceTaskType.serviceName`) was correct
as-is and untouched.

### 8.2 Pipeline Form dialog: a field row rendered with a dead third column

**Symptom:** the user circled the "New pipeline" dialog with one field and said the width didn't
look good -- the XML Tag/Label and Type/Nested Under rows each left visible dead space to the
right instead of filling the card.

**Root cause:** `.form-grid` (`styles.css:1139-1146`) is a `@container`-query grid: 1 column below
a 30rem-wide container, 2 columns 30rem-62rem, 3 columns above 62rem. Container queries resolve
against the *nearest ancestor with `container-type` set* -- and only `<form>` and `.form-section`
had it (`styles.css:1119`). A field-card's own `.form-grid` is nested inside a plain `.card`,
which set no containment of its own, so it inherited the outer `<form>`'s width instead of its
own -- and in an `xwide` (76rem) dialog with only one field (spanning both grid columns per an
earlier fix this session), that form width comfortably cleared 62rem, tripping the 3-column
layout for a grid with only 2 children. The 2 real fields rendered at 1/3 width each; the phantom
third column sat empty.

**Fix:** added `container-type: inline-size` to `.card` itself (`styles.css:519-528`), so any
`.form-grid` (or other `@container` consumer) nested inside a card sizes against the card's own
real width, however wide its ancestors are. Verified live: the same field-card now measures its
own ~920px width, correctly falls in the 30rem-62rem range, and both fields render at ~450px
with no dead column. Checked for regressions before applying: `.card` is never combined with a
nested (non-portaled) `position: fixed`/`absolute` element that depends on escaping the card's
bounds to anchor elsewhere -- the app's floating panels (`toast-host.ts`, the job-assistant panel,
the reports drawer) all carry `fixed` and `card` on the *same* element, which containment does
not affect; CDK menus/dialogs portal to `document.body` and never sit inside a card in the DOM.

### 8.4 `app-segmented`'s host swallowed every vertical margin (fixed 2026-09-07)

**Symptom:** the user circled the Document Converter's `BUCKET` label and said "margin issue" --
the Bucket/File labels sat flush against the Upload-a-file/From-a-bucket tabs above them.

**Root cause:** measured live, `.form-grid`'s top and the tab row's bottom were both exactly
212px -- a literal 0px gap. The parent is `<div class="card p-4 space-y-4">`, and Tailwind v4
compiles `space-y-4` to `:where(.space-y-4 > :not(:last-child)) { margin-block-end: ... }` --
i.e. bottom margin on every child *except the last*, so the margin belongs to `<app-segmented>`,
the first child. But an Angular component host is an unknown element and defaults to
`display: inline`, and **vertical margins on an inline box have no layout effect** -- the margin
was computed and silently dropped.

This is the same failure `styles.css:203-207` already documents and fixes for
`app-field`/`app-form-dialog`/`app-table-shell`/`app-stat-tile`; `app-segmented` had simply never
been added to that list. **Fix:** added it. `.seg` inside it is `inline-flex` and still
shrink-wraps, so blockifying the host changes the spacing and nothing else. Components meant to
sit inline in running text (`app-icon`, `app-status`, `app-copy-button`) deliberately stay out of
that rule. Both screens using the control were affected -- Document Converter and Audio
Transcript Extractor -- and both are fixed by the one change. Verified live: host now `block`,
`margin-block-end` resolves to 16px, gap 0px -> 16px.

### 8.5 The bucket folder picker dumped hundreds of buttons (fixed 2026-09-07)

**Symptom:** picking the `etl-avatar` bucket in Document Converter's "From a bucket" mode
rendered ~200 folder buttons (one per user id) as a single wrapping row, pushing Supported
formats and Recent conversions off the bottom of the screen. The user circled the whole block.

**Fix:** two changes, both matching conventions the app already had for exactly this problem.
A `.folder-picker` scroll box (`max-height: 13rem; overflow-y: auto`) added next to the existing
`.scroll-table` rule, whose own comment describes the same failure for tables ("a bucket of 200
files pushed every bit of context off the top of the screen"). And a "Filter folders"
`.search-field` box that appears only once a level holds more than 12 folders, with a
"N of M folders" count under the list; the filter resets when navigating to another level but
survives "load more", since that is the same level still being read. Verified live: 200 folders
scroll inside their own box, typing `2401` narrows to 1 of 200, and the rest of the page is
visible again without scrolling.

---

*End of audit.*
