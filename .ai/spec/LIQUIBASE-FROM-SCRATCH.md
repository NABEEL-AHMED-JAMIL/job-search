# The changelog cannot build a database from scratch — diagnosis

Reproduced 2026-09-09 by running the real application image against an empty PostgreSQL database.
This supersedes the one-line note "master changelog can't build a database from scratch (fails at
V12)", which understates it: V12 is the first symptom, not the problem.

## The problem

**Fifteen core tables are created by no changeset in this changelog.**

`ai_agent`, `app_user`, `tenant`, `source_job`, `source_task`, `source_task_payload`,
`storage_connection`, `notification`, `scheduler`, `job_queue`, `job_audit_logs`,
`kafka_connection_profile`, `document_converter_task`, `etl_demo_products`,
`tenant_task_type_kafka_route`.

They exist in every running environment because Hibernate's `ddl-auto=update` created them once,
and they have been carried forward ever since. Liquibase was adopted later, for incremental
changes only. Nothing has ever built this schema from nothing.

## Why it breaks, differently per profile

| Profile | `ddl-auto` | What happens to a fresh database |
|---|---|---|
| dev | `update` | Liquibase runs **before** Hibernate in Spring Boot's startup, so V12 dies with `relation "ai_agent" does not exist` before Hibernate has any chance to create it. |
| stage / prod | `validate` | Worse and silent. Hibernate creates nothing, so even with V12 skipped, fifteen tables never exist. **A fresh production database has never been possible.** |

The master changelog's own header already knew half of this — V4–V7 are excluded because they
`ALTER` "tables/columns Hibernate hasn't created yet at Liquibase-run time". V12 has the same
problem and was not excluded.

## What blocks it, in order

Each was found by clearing the one before it and re-running against an empty database.

| # | Changeset | Blocker |
|---|---|---|
| 1 | V12 | FK on `ai_agent` — table created by nothing |
| 2 | V12 | FK on `database_connection_profile` — **dropped by V27**, gone from the product |
| 3 | V14 | FK on `dynamic_form_submission` — dropped by V26 |
| 4 | V15 | `ALTER … recurrence` — the column's pre-V15 shape, which a baseline of the *current* schema does not have |
| 5 | V18 | index on `lookup_data(tenant_id)` — a column V22 adds |

**Four changesets target tables that no longer exist anywhere**: V12 (6 tables), V14 (5), V17 (9),
V22 (1). All were dropped by V26–V30. They ran on existing databases when those tables were still
there, and their `databasechangelog` rows remain, so they are only a problem for a database being
built now.

## Why this was not fixed here

A baseline was written and tested — it is kept at `liquibase-baseline/hibernate-baseline.sql`,
generated with `pg_dump --schema-only`, idempotent throughout, and verified to be a no-op against
the live database. It cleared blockers 1–3.

Blockers 4 and 5 are the reason it stops there, and they are structural rather than incidental:

- A baseline dumped from the live database is the **final** shape of those tables. Every changeset
  after it that alters one of them expects an **intermediate** shape. V15 alters `scheduler` to a
  state the baseline already has.
- Excluding those changesets is not sufficient either. V22 adds audit columns to baselined tables
  *and* to `lookup_data` and `source_task_type`, which are **not** baselined — excluding it whole
  breaks V18, which indexes a column V22 adds. Several changesets are partly needed.

Making this work is a **squash**: baseline the whole schema, exclude every historical schema
changeset, keep the ones that seed data (V2, V3, V9, V10 all `INSERT`), and re-author the still-live
parts of V12/V14/V17/V22 as one new changeset. That is a coherent piece of work, and it encodes
decisions about what a fresh environment should reproduce that belong to whoever owns this schema.
Half-doing it would leave the changelog altered, still unable to build from scratch, and harder to
reason about than it is now — so the changelog is untouched.

## Reproducing it

```bash
docker exec postgres_db sh -c 'psql -U "$POSTGRES_USER" -d postgres \
  -c "DROP DATABASE IF EXISTS liquibase_scratch;" -c "CREATE DATABASE liquibase_scratch;"'

docker inspect process_app --format '{{range .Config.Env}}{{println .}}{{end}}' \
  | grep -vE "^SPRING_DATASOURCE_URL=|^PATH=|^JAVA_|^LANG=" > /tmp/lbenv.txt

docker run -d --name lb_fresh --network process_default --env-file /tmp/lbenv.txt \
  -e SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/liquibase_scratch \
  process-process_app

docker logs lb_fresh 2>&1 | grep -oE 'ERROR: [^\[]+'
```

The full environment must be passed. With only the datasource variables the application fails on
mail configuration long before Liquibase runs, which looks like a different problem entirely.
