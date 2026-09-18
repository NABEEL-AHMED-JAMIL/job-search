# API load review — 2026-09-18

**Question asked.** When the platform admin picks another workspace, or a user clicks deeper
into a screen, does the console fetch what that click needs — or everything up front? Which
screens are slow at the seeded scale (MedAxis: 101 Kafka profiles, 10,201 topics, 10,121
pipelines, 85,817 fields), and what to change.

**Method.** Every read endpoint the console calls (`grep API_BASE` over `scheduler1/next/src/app`),
hit twice through the container at :9098 — once as the platform admin, once as the MedAxis
admin — timing and payload size recorded. Probe script: session scratchpad `perf-probe.py`.

## Before

| Endpoint | Who reads it | Admin | MedAxis |
|---|---|---|---|
| `setting.json/appSetting` | Lookups, Pipelines (topic filter), task editor, Agents | 63 ms · **3.7 MB** · 10,613 topics | 183 ms · 3.6 MB |
| `pipeline.json/list` | Pipelines screen | **1,048 ms · 20 MB** · 10,201 rows with every field | 1,044 ms · 20 MB |
| `pipeline.json/listPipelines` | task editor (to fill a box that shows one topic's) | **1,272 ms · 20 MB** | 1,028 ms · 20 MB |
| `kafkaConnectionProfile.json/fetchAllProfiles` | Kafka rail | 7 ms · 65 KB · 106 | 7 ms · 62 KB |
| `setting.json/topicsForProfile` (new this morning) | Kafka pane, per click | 16 ms · 45 KB · 101 | 13 ms |
| `tenant.json/listTenants`, `appUser.json/listUsers`, `sourceTask.json/listSourceTask`, `report.json/runs`, `dashboard.json/userStatistics`, `notification.json/list`, `storageConnection.json/fetchAllConnections`, `aiAgent.json/fetchAllAgents`, `tenantRequest.json/listRequests` | everything else | all ≤ 25 KB, ≤ 22 ms | same |

Everything but two endpoints is already small. Opening **New task** cost 24 MB (`appSetting` +
`listPipelines`); opening **Pipelines** cost 24 MB (`list` + `appSetting`); opening **Lookups**
cost 3.7 MB for six rows.

## Changed today

| Endpoint | Change | After (admin) |
|---|---|---|
| `pipeline.json/list`, `listPipelines` | Rows via `PipelineRowProjection` (no entity load) with `fieldCount` / `requiredCount`; fields no longer sent | **~200–650 ms · 4.1 MB** |
| `pipeline.json/fields?pipelineKey=` | New. One pipeline's fields, scoped like delete; fetched when a card's field list, edit or copy is opened | ~10 ms · a few KB |
| `setting.json/lookups` | New. Parent lookups alone | 17 ms · **1.5 KB** |
| `setting.json/topics` | New. Six picker columns per visible topic | 143 ms · **2.0 MB** |
| `pipeline.json/listForTopic` | Existing; task editor now calls it when a topic is chosen instead of `listPipelines` | 10 ms · < 1 KB |
| `setting.json/topicsForProfile` | Kafka pane asks per profile click; previous rows stay blurred while the next arrive | 16 ms · 45 KB |

Screen totals: New task 24 MB → 2 MB; Pipelines 24 MB → 6 MB; Lookups 3.7 MB → 1.5 KB + the
per-parent entry calls it already made; Kafka & Topics 3.7 MB → 65 KB + 45 KB per click.

Verified in the browser as the platform admin: Pipelines card "3 fields" → click → one
`fields?pipelineKey=98812` call → list opens; New task → topic picked → one `listForTopic`
call → that topic's pipeline offered. Backend `PipelineServiceImplTenantIsolationTest` 16 green
(two new: a tenant cannot read another's fields; reads its own). Frontend 1,597 green.

## Still open — needs a decision

1. **Pipelines screen still receives and renders all 10k rows** (4 MB, 10,201 DOM cards or
   rows). The fix is server paging with the search/topic/state filters applied server-side
   (`page`, `limit`, `q`, `sourceTaskTypeId`, `status`), the four summary tiles from a count
   query, and the shell's pager. It changes what "10201 of 10201" and the tiles mean and is a
   UX change, so it was not done unasked.
2. **Topic pickers still receive all 10k topics** (`setting.json/topics`, 2 MB) — task editor,
   Pipelines filter, Source Tasks filter, pipeline dialog. Two options: (a) the searchable box
   asks the server as the person types (`topics?q=&limit=50`; `Combobox` gains a remote mode);
   (b) pick the Kafka profile first, then one of its ~100 topics (the drill-down the Kafka
   pane already does). (a) keeps every form as it is; (b) adds a field but matches how topics
   are organised. Recommendation: (a) for the filters, (b) for the task editor.
3. **`appSetting` is cached per tenant (`@Cacheable`)** but the cache is invalidated on every
   topic/lookup write, so after the seed run every first read rebuilt 10k DTOs. With the
   screens moved off it, the remaining reader is the e2e spec; it can move to `topics`.
4. **Kafka rail auto-select fires `topicsForProfile` up to three times** while the selection
   settles (linked → default → first). Stale answers are dropped, so it is waste, not a bug.
5. **Platform admin, other workspace.** The admin's lists already carry every workspace's
   rows; there is no per-workspace fetch. With paging (1) and a workspace filter passed to
   the server, picking a workspace becomes one filtered page rather than a client-side filter
   over everything.

## Follow-up, same day — items 1, 2 and 5 done

- **1 / 5.** `pipeline.json/list` pages and filters on the server (`page, limit, q, topic, status, tenantId, onlyMine`); the screen shows one page with the shared pager, the tiles come from a scope-wide summary query, and a platform admin narrows to one workspace with a box — picking a workspace is one filtered page, not a client-side filter over everything. Admin, page 1 of 50: **69 ms · 20 KB** (was 4.1 MB after part 1, 20 MB before).
- **2.** `setting.json/topics` searches (`q` + `limit`, first 50 by name or Kafka topic: 20 ms · 4 KB), resolves ids, or lists one profile's topics. The Pipelines filter and the pipeline dialog search as the person types (Combobox remote mode); the task editor picks the Kafka connection first (the same ~100 rows as the Kafka rail), then one of its ~100 topics, then the pipeline — option (b), as recommended.
- **3 / 4** remain as noted: `appSetting` is now read by nothing in the console; the Kafka rail's up-to-three auto-select fetches are waste, not a bug.

