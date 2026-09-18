# Synthesis -- `page-access-profiles`

Companion to [../grooming/page-access-profiles.md](../grooming/page-access-profiles.md). Written
2026-09-17, the day the feature landed, so the *current → expected → gap* below is the state
before the session and the reasoning that chose the design.

## 1. Current (2026-09-16) → expected

| | Current | Expected |
|---|---|---|
| What a tenant user sees | Every page their role allows; roles are the only lever | The pages their workspace decided they need, and no others |
| Who decides | Nobody -- there is no lever | The tenant admin, with the platform admin able to step in |
| Where it is enforced | Role only, on the server | Page access on the server too: a withheld page's API group answers 403 |

## 2. Options weighed

| Option | Shape | Why it was / was not chosen |
|---|---|---|
| A. Per-user page checkboxes only | One row per person, one checkbox per page | Simplest to build; unmanageable at 30 people × 10 pages, and every new hire starts from zero. Rejected as the primary model |
| **B. Access profiles** (chosen) | Named bundles held by people, one default per workspace | Matches how workspaces actually think ("she is an analyst"); a new person is covered by the default the moment they exist |
| C. Finer than pages (per action) | Gate buttons and endpoints individually | The role hierarchy already does the *how much*; gating *what you can see* at page level is the missing piece, and per-action would double the catalogue overnight |

B was chosen; then A came back as a **layer on top** -- per-person exceptions -- once the People ×
pages grid made it obvious that a tick in a cell should mean something. The exception is stored
separately (`user_page_access`) so a profile never silently absorbs one person's special case.

## 3. Gap → solution

| Gap | Solution | Size |
|---|---|---|
| No catalogue of gateable pages | `PageKey` enum with API prefixes -- one place that both the interceptor and the console read | S |
| No storage | V40 (profiles + pages, `app_user.page_access_profile_id`), V41 (exceptions) | S |
| No enforcement | `PageAccessInterceptor` + 15 s cache; registered in `WebConfig` | M |
| Console shows everything | `pageKeys` on the auth response; `pageGuard` + menu filter + Unauthorized page with Request access | M |
| No management screen | `admin/access-profiles`: cards by section + People × pages grid; platform admin picks a workspace | L |
| Users screen blind to it | Access column / card line / filter / row action; profile picker in the dialog | M |
| Nobody told | Two notification types | S |

## 4. Order (as executed, all 2026-09-17)

`84e6ff0` backend catalogue, schema, interceptor, API → `44a1653` console half → `f77f2c3` /
`96e08cb` platform-admin workspace picker → `10acacc`…`d9277f4` grid, checkboxes, exceptions,
house-style header → `b874133`…`3a694a3` Users screen → `870e32e` / `37526a2` default coverage on
the cards → `e011deb` legend samples that look like the cells.

## 5. Out of scope

- Per-action permissions inside a page.
- Profiles shared across workspaces (each workspace names its own; "Operator" in two workspaces are two rows).

## 6. Open questions

- Rate-limit `requestAccess`? (One click = one notification per admin today.)
- Should a page withheld from *everyone* in a workspace be hidden from the profile editor too? Left visible: the admin may be about to open it.
