# Old scope

Superseded documents, kept rather than deleted.

A document that was wrong is still a record of what somebody believed at the time, and occasionally of how the system used to be operated — which is worth having when a half-migrated corner of it turns out still to work the old way. Nothing here is current. Nothing here should be followed.

[TRIAGE.md](TRIAGE.md) is the assessment that put these files here: every claim in each document checked against the code, with the verdict and the evidence.

## What is here

| File | Was at | Verdict | Why it moved |
|---|---|---|---|
| [root-README.md](root-README.md) | `README.md` | wrong | Its entire content was `# job-search` — one of five unrelated sibling checkouts, and not what this directory is |
| [scheduler1-README.md](scheduler1-README.md) | `scheduler1/README.md` | boilerplate | Fourteen bytes. Said nothing about a repository that holds **two** frontends |
| [scheduler1-DEPLOYMENT.md](scheduler1-DEPLOYMENT.md) | `scheduler1/DEPLOYMENT.md` | partly stale | Mechanics correct, but the verify URL sent readers to a 404, and it documented only the superseded app without saying so |
| [scheduler1-next-README.md](scheduler1-next-README.md) | `scheduler1/next/README.md` | boilerplate | The stock Angular CLI scaffold, unmodified |
| [process-README.md](process-README.md) | `process/README.md` | partly stale | Overview and architecture sound; endpoints, bootstrap SQL, actuator dump and tech stack no longer true |
| [dynamic-forms-grooming.md](dynamic-forms-grooming.md) | `grooming/dynamic-forms.md` | overridden | Not wrong — the feature it plans was removed whole on 2026-09-03 at the product owner's call, so the plan has nothing left to apply to |
| [dynamic-forms-synthesis.md](dynamic-forms-synthesis.md) | `synthesis/dynamic-forms.md` | overridden | Same feature, same date. Had a live gap table of fixes in flight; all moot once the feature was deleted |

The originals were **copied**, not moved — each path still had a document at time of archiving. The first five were rewritten in place; the two dynamic-forms documents have no replacement, because [`../discovery/features.md`](../discovery/features.md) §2 (row 13) now records the removal directly and there is no feature left to groom or synthesize a plan for.

## Worth reading even though it is stale

Two passages in [process-README.md](process-README.md) are the only surviving record of how the service used to be brought up, and are deliberately not carried into the new README:

**The bootstrap SQL** (lines 89–98). Before Liquibase, `lookup_data` and `source_task_type` were seeded by hand. The statements no longer match the tables — `lookup_data` has since gained `created_by`, `updated_by`, `is_encrypted` and `tenant_id`, and `source_task_type` gained `tenant_id`, `task_type_status` and `kafka_connection_profile_id` — so running them today fails. The schema is now managed entirely by `process/src/main/resources/db/changelog/` (V1.0 → V25.0), and `ModelApplication` seeds `SCHEDULER_LAST_RUN_TIME` itself on startup without overwriting an existing value.

**The actuator index** (lines 123–205). A pasted HAL response advertising sixteen endpoints including `env`, `configprops`, `heapdump`, `threaddump` and `shutdown`. Only four still resolve: `application.properties` now sets `management.endpoints.web.exposure.include=health,info,metrics,prometheus` and disables `shutdown`, with a comment recording that the others leak secrets. Useful as a record of a hole that was closed.

## Also unverified

Five further documents exist in `process/` that were never part of this triage and have had no verification pass. They are listed so that a decision about the five files above is not mistaken for a decision about the repository's documentation as a whole:

- `process/ext-detail/md/DATABASE_CONNECTION_GUIDE.md`
- `process/ext-detail/md/REFACTORING_SUMMARY.md`
- `process/ext-detail/md/SQL_UPDATE_GUIDE.md`
- `process/ext-detail/md/QUICK_REFERENCE.md`
- `process/docs/design/kafka-dynamic-configuration.md`

None is linked from `process/README.md`. Treat them as unknown until somebody checks them.
