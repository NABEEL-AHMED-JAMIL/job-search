# Push-readiness audit

Date: 2026-09-02
Scope: `/Users/nabeel.amd93/Desktop/Old-School` (root), `process`, `scheduler1`. Findings in
`job-search` and `service-3` are included where they were reached from the root-repo question or
from the secrets sweep.

**Verdict: NO-GO.**

Five independent blockers. Two are live credential exposures already on `origin`, one is a *new*
credential file staged and one `git commit` away from being a third, one would push branches that do
not compile, and one would push into the wrong GitHub repository entirely.

No secret value is reproduced anywhere in this report — only file paths and variable names.

---

## 1. Secrets

### 1.1 BLOCKER — `service-3/.env` is STAGED for commit (new; not previously known)

`/Users/nabeel.amd93/Desktop/Old-School/service-3/.env`, branch `ETL-2023-DEV`, status `A` (added to
index). This is not yet pushed. It is one `git commit && git push` from becoming a third permanent
leak.

Variables present:

- `MONGO_INITDB_ROOT_USERNAME`
- `MONGO_INITDB_ROOT_PASSWORD`
- `SPRING_DATA_MONGODB_URI` — a Mongo URI, which carries the credentials inline
- `MONGO_DB_NAME`, `SPRING_DATA_MONGODB_DATABASE`, `SPRING_PROFILES_ACTIVE`, `SERVER_PORT`,
  `APP_NAME`, `APP_VERSION`

`service-3/.gitignore` has no `.env` rule — `git check-ignore -v .env` exits 1. Nothing would have
stopped this.

### 1.2 BLOCKER — `process/.env.bak.1787579140` is TRACKED and already pushed

Confirmed tracked (`git ls-files --error-unmatch` succeeds) on `new-screen-2026`, which is level with
`origin/new-screen-2026` (`rev-list --left-right --count` = `0 0`). **The values below are already on
GitHub and must be treated as compromised regardless of what happens next.**

Variables present:

- `SPRING_DATASOURCE_PASSWORD`
- `MAIL_PASSWORD`
- `WORKER_CALLBACK_TOKEN`
- `SPRING_DATASOURCE_URL`, `SPRING_DATASOURCE_USERNAME`, `SPRING_KAFKA_BOOTSTRAP_SERVERS`,
  `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `EFS_FILE_DIRE`

Second-order problem worth naming: **the file is not ignored either.** `process/.gitignore` has
`.env` and `.env.local`; a gitignore `.env` line matches only a file named exactly `.env`, so
`.env.bak.1787579140` matches nothing. Verified: `git check-ignore -v .env.bak.1787579140` exits 1.
So `git rm --cached` alone leaves it sitting untracked and un-ignored, ready for the next `git add .`
to put it straight back. The ignore rule has to be widened in the same step.

### 1.3 BLOCKER — `job-search/env` is TRACKED

`/Users/nabeel.amd93/Desktop/Old-School/job-search/env`, still in the index (`git ls-files env`
returns it). Variables present:

- `MONGO_ROOT_PASSWORD`, `MONGO_APP_PASSWORD`, `ME_BASICAUTH_PASSWORD`
- `MONGO_ROOT_USER`, `MONGO_APP_USER`, `MONGO_DATABASE`, `ME_BASICAUTH_USER`

The working-tree change to `job-search/.gitignore` adds an `env` line and its own comment already
says the right thing — it stops the *next* one, it does not untrack this one. Correct as far as it
goes; the `git rm --cached` and the rotation still have to happen.

### 1.4 Clear — cross-contamination check

I extracted every value from `process/.env`, `process/.env.bak.1787579140`, `job-search/env`,
`service-3/.env` and `process/kafka-it/.env` and searched for each across `.ai/`, root `README.md`,
`process/src` and `scheduler1/next/src`.

**No password and no token value from any of those files appears in any of those trees.** The only
matches are non-secret: the DB username, the JDBC URL, the Kafka bootstrap address and the EFS path,
which show up in `.ai/discovery/infrastructure.md`, `.ai/discovery/application-inventory.md`,
`.ai/old-scope/TRIAGE.md` and a few other discovery docs.

One line to eyeball: `.ai/discovery/infrastructure.md:458` quotes a `worker.callback.token=` value,
28 characters. I compared it byte-for-byte against the live `WORKER_CALLBACK_TOKEN` in both
`process/.env` and `process/.env.bak.1787579140` — **it does not match**, so it is a placeholder, not
the live token. Worth a human glance before `.ai/` goes anywhere, but not a blocker.

### 1.5 Clear — `process/.env.example`

Every key has an empty value (zero lines match `^KEY=.+`). Safe to keep tracked; the `!.env.example`
negation in `process/.gitignore` is correct.

### 1.6 Minor — `process/.idea/` is tracked despite being gitignored

11 files tracked under `process/.idea/` (`aws.xml`, `dbnavigator.xml`, `compiler.xml`, `misc.xml`,
`vcs.xml`, …). `process/.gitignore` contains `.idea/`, so these predate the rule and the rule cannot
retroactively remove them.

Exposure is small but real: `process/.idea/dbnavigator.xml:111` stores a database **username** in a
`<user value="…"/>` element. No password — DB Navigator keeps those in `dataSources.local.xml`, which
*is* correctly ignored (it shows under `git status --ignored`). `aws.xml` contains no access keys.

Not a blocker. Should be untracked in a separate housekeeping commit, not mixed into this push.

---

## 2. `process/kafka-it/` after the move — PASS

Verified with `git check-ignore -v`, both exit 0:

```
kafka-it/.gitignore:3:secrets/	kafka-it/secrets/
kafka-it/.gitignore:4:.env	kafka-it/.env
```

Both are correctly ignored at the new location. Supporting checks:

- The move is staged as five `R100` renames out of `docker/kafka-it/`, and
  `docker/kafka-it/.gitignore -> kafka-it/.gitignore` is one of them. The ignore rule travels with
  the directory, so it still holds after the commit lands — not just in the working tree.
- `git ls-files kafka-it/` returns exactly five files: `.gitignore`,
  `docker-compose.kafka-it.yml`, `generate-certs.sh`, `start.sh`, `stop.sh`. Nothing under
  `secrets/`, no `.env`.
- `git ls-files docker/` is empty and `docker/` no longer exists on disk — no orphaned copy of the
  old secrets path left behind in the index.

The generated cert material in `kafka-it/secrets/` (17 entries) and `kafka-it/.env` both show under
`git status --ignored` as `!!`, which is what we want.

One gap: `kafka-it/README.md` is untracked and needs adding — see §5.

---

## 3. The ROOT repo — a naive `git add .` is wrong, and so is a naive `git push`

State: one commit (`5e8dbe7 first commit`), one tracked file (`README.md`, currently modified,
+39/-1), no `.gitignore`.

### 3.1 BLOCKER — root `origin` points at the `job-search` repository

```
$ git -C /Users/nabeel.amd93/Desktop/Old-School remote -v
origin	https://github.com/NABEEL-AHMED-JAMIL/job-search.git
```

That is the **same remote as the nested `job-search/` repo**, and the two histories are unrelated
(root HEAD `5e8dbe7`, job-search HEAD `ba41df91`). Branch `main` has no upstream configured and
`git branch -a` shows no remote-tracking refs at all, so this root repo has never fetched or pushed.

Concretely: `git push origin main` from the root is rejected as non-fast-forward. If anyone reaches
for `--force` to get past that, or pushes to a new branch name, the workspace scaffolding — and
whatever `git add .` swept in — lands in the real `job-search` GitHub repository. A forced push would
replace `job-search`'s `main` with a single-README tree.

The root remote is simply wrong. It should be removed or repointed before anything else is done
there.

### 3.2 The nested-repo problem

`process/`, `scheduler1/`, `job-search/`, `service-3/` and `my-user-redux-frontend/` each contain
their own `.git` — confirmed by `git rev-parse --show-toplevel` inside each. They are nested repos,
not submodules: there is no `.gitmodules` at root.

On git 2.50.1, `git add .` at the root does not add their contents as files. It prints the "adding
embedded git repository" warning and records each one as a **gitlink** — a bare commit SHA with no
`.gitmodules` entry to say where to fetch it from. The result is a repo whose tree references five
commits nobody can resolve; a fresh clone gets five empty directories. It would also add `.DS_Store`
and all 2.4 MB of `.ai/`.

### 3.3 What the root `.gitignore` should contain

Create `/Users/nabeel.amd93/Desktop/Old-School/.gitignore`:

```
# Nested project repositories -- each has its own .git and its own remote.
# Never add these here: `git add .` records them as gitlinks with no .gitmodules,
# producing a tree that references commits nobody can fetch.
/process/
/scheduler1/
/job-search/
/service-3/
/my-user-redux-frontend/

# OS
.DS_Store
```

### 3.4 Where `.ai/` belongs

`.ai/` is cross-repo material — its `discovery/`, `synthesis/` and `grooming/` trees describe
`process`, `scheduler1` and `job-search` together. So it does **not** belong inside any one of those
repos; putting it in `process/` or `scheduler1/` would duplicate it and immediately drift.

The root is the right *place* for it, but the root repo is not currently a safe *home*: its `origin`
is the `job-search` GitHub repo (§3.1). Recommended, in order of preference:

1. Point the root repo at a new, private workspace repository of its own, then track `.ai/` there.
   This is the only option that both keeps `.ai/` versioned and keeps it out of a project repo.
2. If no such repo will be created: add `/.ai/` to the root `.gitignore` and leave it as local-only
   working material. Do not commit it to the current root remote.

Either way, `.ai/` must not be pushed to `github.com/NABEEL-AHMED-JAMIL/job-search`. It contains the
JDBC URL, the DB username and the Kafka bootstrap address (§1.4) alongside a full internal
architecture write-up.

`.DS_Store` at the root and `.ai/.DS_Store` are covered by the `.gitignore` above.

---

## 4. Should be gitignored and is not

| Repo | Item | Status |
|---|---|---|
| `process` | `.env.bak.1787579140` — the `.env` rule does not match this name | **Blocker**, §1.2 |
| `service-3` | no `.env` rule at all | **Blocker**, §1.1 |
| `process` | `.idea/` tracked from before the rule existed | Minor, §1.6 |
| root | no `.gitignore` at all; `.DS_Store` untracked | §3.3 |
| `scheduler1` | root `.gitignore` has no `.DS_Store` (only `next/.gitignore` does) | Minor — no stray `.DS_Store` on disk right now |

No build output, coverage output or log file is tracked in either `process` or `scheduler1`.
`target/`, `logs/`, `node_modules/`, `dist/`, `.angular/` all show correctly as `!!` under
`git status --ignored`.

One thing I checked and want to record as *clear*, because this class of bug already bit this repo:
`scheduler1/.gitignore` still carries unanchored `dist`, `coverage`, `typings` and `node_modules`
patterns, which match a directory of that name at **any** depth. That is exactly the failure the
`/logs/` comment in that file describes — a bare `logs` had silently excluded
`next/src/app/features/jobs/logs`, a whole feature. I searched `next/src` for directories named
`dist`, `coverage`, `typings` or `pids` and found none, so there is no live trap today, and
`next/src/app/features/jobs/logs/{job-logs.ts,job-logs.html}` is tracked and safe. Anchoring those
four patterns is worth doing, but it is housekeeping, not a blocker.

---

## 5. BLOCKER — untracked files that tracked, modified code already depends on

This is the one that costs a broken build on `origin`. In each case the *importer* is tracked and
modified and will go into the commit; the *implementation* is untracked and will not, unless it is
added explicitly. `git commit -a` does **not** pick up untracked files.

### `process`

| Untracked file | Imported by (tracked + modified) |
|---|---|
| `src/main/java/process/config/StoragePropertyDefaults.java` | `StorageConnectionBootstrap.java:68`, `StorageBrowserServiceImpl.java:16,68`, `AppUserServiceImpl.java:27,68`, `StorageConnectionServiceImpl.java:7,55` |

Four `@Value(StoragePropertyDefaults.AVATAR_BUCKET)` references in `src/main`. Without this one file
the branch does not compile — `mvn compile` fails, not just the tests.

Also untracked and needed:

- `run-kafka-matrix.sh` — referenced by the modified `README.md:98,100` and by the staged
  `kafka-it/start.sh:42`. Without it the README documents a script that is not in the repo.
- `kafka-it/README.md` — the moved directory's documentation; 16 KB, referenced by nothing in code
  but clearly part of the move.
- Eight new test files: `config/AvatarBucketPropertyTest.java` (which is the only *test* referencing
  `StoragePropertyDefaults`), `config/KafkaConnectionResolverProfileOwnershipTest.java`,
  `config/KafkaTemplateProviderSecretCacheTest.java`,
  `model/service/impl/KafkaProtocolCredentialLifetimeTest.java`,
  `model/service/impl/KafkaSecretUnreadableObjectTest.java`,
  `model/service/impl/OwnAvatarFolderGuardTest.java`,
  `model/service/impl/StorageConnectionTenantlessCallerTest.java`,
  `util/KafkaCertificateStoreAliasTest.java`.

### `scheduler1`

| Untracked file | Imported by (tracked + modified) |
|---|---|
| `features/admin/storage/kafka-dependents.ts` | `connection-dialog.ts:10`, `storage-connections.ts:19` |
| `features/notifications/notification-links.ts` | `shell/notification-bell.ts:6`, `notifications/notifications.ts:9` |
| `features/settings/kafka/kafka-profile-form.ts` | `kafka-dialog.ts:16` |
| `features/settings/kafka/kafka-tls-section.ts` | `kafka-dialog.ts:12` (and its template uses `<app-kafka-tls-section>` at `:124`) |
| `features/settings/kafka/kafka-secret.service.ts` | `kafka-profile-form.ts:2`, `kafka-tls-section.ts:17` |
| `features/tenant-request/tenant-requests.html` | `tenant-requests.ts:44` — `templateUrl: './tenant-requests.html'` |
| `shared/testing/memory-storage.ts` | `core/auth/auth.service.spec.ts:7` |

`tenant-requests.html` deserves a callout: `git ls-files next/src/app/features/tenant-request/`
returns only `reject-dialog.ts`, `request-workspace.ts` and `tenant-requests.ts`. The template has
**never** been tracked, and `tenant-requests.ts` now points at it with `templateUrl`. Push without it
and `ng build` fails on a missing resource for a component that is on the router.

Plus nine untracked spec files that pair with the above: `app.routes.spec.ts`,
`core/auth/auth.interceptor.spec.ts`, `core/auth/auth.service.spec.ts`,
`admin/storage/clone-dialog.spec.ts`, `admin/storage/connection-dialog.spec.ts`,
`admin/storage/kafka-dependents.spec.ts`, `admin/storage/storage-connections.spec.ts`,
`admin/users/user-management-scope.spec.ts`, `notifications/notification-links.spec.ts`,
`settings/kafka/kafka-profile-form.spec.ts`, `settings/kafka/kafka-tls-section.spec.ts`.

### `job-search` (same class, noted in passing)

| Untracked file | Imported by (tracked + modified) |
|---|---|
| `etl/tpd/offset_tracker.py` | `etl/tpd/tpd_scrapping_listener.py:14`, `etl/tpd/tpd_test_listener.py:11` |

Both listeners do `from etl.tpd.offset_tracker import OffsetTracker` and then use it throughout.
Without the module they raise `ModuleNotFoundError` on import — the workers do not start.

Also untracked there: `.env.example` (which the `!.env.example` negation in `job-search/.gitignore`
is written to allow, so it is clearly meant to be committed), and `tests/test_credential_env.py` and
`tests/test_offset_tracker.py`. Nothing under `tests/` is tracked at all today.

---

## Remediation — run in this order

Everything below is deliberately explicit. Do not substitute `git add .` at any step.

### Step 1 — Stop the new leak before anything else

```
cd /Users/nabeel.amd93/Desktop/Old-School/service-3
git rm --cached .env
printf '\n# Local environment -- holds the Mongo root password and the Mongo URI.\n.env\n.env.*\n!.env.example\n' >> .gitignore
git check-ignore -v .env          # must now print a .gitignore line and exit 0
```

Then create a `service-3/.env.example` with the nine keys and empty values, and add that instead.

### Step 2 — Rotate the credentials that are already public

Nothing in git fixes this; the values are on GitHub. Rotate before or in parallel with the rest:

- The Postgres password behind `SPRING_DATASOURCE_PASSWORD` (`process/.env.bak.1787579140`)
- The mail account password behind `MAIL_PASSWORD` (same file)
- `WORKER_CALLBACK_TOKEN` (same file)
- The Mongo passwords behind `MONGO_ROOT_PASSWORD`, `MONGO_APP_PASSWORD` and the mongo-express
  password behind `ME_BASICAUTH_PASSWORD` (`job-search/env`)

Rotate `service-3/.env`'s Mongo root password too if that database was ever shared or reachable.

### Step 3 — Untrack the two leaked files and close the ignore gaps

```
cd /Users/nabeel.amd93/Desktop/Old-School/process
git rm --cached .env.bak.1787579140
# Widen the rule: plain `.env` never matched this name.
printf '.env.bak*\n.env.*\n!.env.example\n' >> .gitignore
git check-ignore -v .env.bak.1787579140    # must exit 0 now

cd /Users/nabeel.amd93/Desktop/Old-School/job-search
git rm --cached env                        # .gitignore already has the `env` line
git check-ignore -v env                    # must exit 0 now
```

Purging these from history (`git filter-repo`, force-push, and every collaborator re-cloning) is a
separate decision. **Rotation in step 2 is not optional either way** — assume anything that was
pushed has been scraped.

### Step 4 — Fix the root repo

```
cd /Users/nabeel.amd93/Desktop/Old-School
git remote remove origin        # it points at the job-search repo -- see 3.1
```

Write the `.gitignore` from §3.3, then:

```
git add .gitignore README.md
git status                      # confirm: ONLY these two. No nested dirs, no .DS_Store, no .ai/
```

Decide `.ai/` per §3.4 before committing. If it is not going to a new private repo, add `/.ai/` to
that `.gitignore` now. Do not add a remote back until that decision is made.

### Step 5 — Add the missing implementation files

`process`:

```
cd /Users/nabeel.amd93/Desktop/Old-School/process
git add src/main/java/process/config/StoragePropertyDefaults.java
git add run-kafka-matrix.sh kafka-it/README.md
git add src/test/java/process/config/AvatarBucketPropertyTest.java \
        src/test/java/process/config/KafkaConnectionResolverProfileOwnershipTest.java \
        src/test/java/process/config/KafkaTemplateProviderSecretCacheTest.java \
        src/test/java/process/model/service/impl/KafkaProtocolCredentialLifetimeTest.java \
        src/test/java/process/model/service/impl/KafkaSecretUnreadableObjectTest.java \
        src/test/java/process/model/service/impl/OwnAvatarFolderGuardTest.java \
        src/test/java/process/model/service/impl/StorageConnectionTenantlessCallerTest.java \
        src/test/java/process/util/KafkaCertificateStoreAliasTest.java
```

`scheduler1`:

```
cd /Users/nabeel.amd93/Desktop/Old-School/scheduler1
git add next/src/app/features/admin/storage/kafka-dependents.ts \
        next/src/app/features/notifications/notification-links.ts \
        next/src/app/features/settings/kafka/kafka-profile-form.ts \
        next/src/app/features/settings/kafka/kafka-tls-section.ts \
        next/src/app/features/settings/kafka/kafka-secret.service.ts \
        next/src/app/features/tenant-request/tenant-requests.html \
        next/src/app/shared/testing/memory-storage.ts
git add next/src/app/app.routes.spec.ts \
        next/src/app/core/auth/auth.interceptor.spec.ts \
        next/src/app/core/auth/auth.service.spec.ts \
        next/src/app/features/admin/storage/clone-dialog.spec.ts \
        next/src/app/features/admin/storage/connection-dialog.spec.ts \
        next/src/app/features/admin/storage/kafka-dependents.spec.ts \
        next/src/app/features/admin/storage/storage-connections.spec.ts \
        next/src/app/features/admin/users/user-management-scope.spec.ts \
        next/src/app/features/notifications/notification-links.spec.ts \
        next/src/app/features/settings/kafka/kafka-profile-form.spec.ts \
        next/src/app/features/settings/kafka/kafka-tls-section.spec.ts
```

`job-search`:

```
cd /Users/nabeel.amd93/Desktop/Old-School/job-search
git add etl/tpd/offset_tracker.py .env.example \
        tests/test_credential_env.py tests/test_offset_tracker.py
```

### Step 6 — Prove the trees are complete before committing

Build from the index, not from the working tree, so an untracked file cannot mask a missing one:

```
cd /Users/nabeel.amd93/Desktop/Old-School/process   && mvn -q compile
cd /Users/nabeel.amd93/Desktop/Old-School/scheduler1/next && npx ng build
cd /Users/nabeel.amd93/Desktop/Old-School/job-search && python -m unittest discover tests
```

The strict check for §5, worth doing at least for `scheduler1` where the missing template is easiest
to overlook: `git stash -u` the untracked files, build, watch it fail, restore. Or clone the staged
tree to a scratch directory and build there.

Then, in each repo, `git status --porcelain` should show no `??` entry that any tracked file
references.

### Step 7 — Housekeeping, in its own commit, after the above lands

- `cd process && git rm -r --cached .idea` (`.gitignore` already covers it)
- Anchor `dist`, `coverage`, `typings`, `node_modules` in `scheduler1/.gitignore` as `/dist`,
  `/coverage`, `/typings`, `/node_modules` — same fix the `/logs/` line already documents
- Add `.DS_Store` to `scheduler1/.gitignore`

---

## Re-check before pushing

- [ ] `git -C service-3 diff --cached --name-only | grep -c '\.env$'` → `0`
- [ ] `git -C process check-ignore -v .env.bak.1787579140` → exits 0
- [ ] `git -C job-search check-ignore -v env` → exits 0
- [ ] `git -C process check-ignore -v kafka-it/secrets/ kafka-it/.env` → exits 0 (already passing)
- [ ] `git -C /Users/nabeel.amd93/Desktop/Old-School remote -v` → no `job-search.git`
- [ ] `mvn compile`, `ng build` and the python tests all pass from the staged tree
- [ ] Rotated: `SPRING_DATASOURCE_PASSWORD`, `MAIL_PASSWORD`, `WORKER_CALLBACK_TOKEN`,
      `MONGO_ROOT_PASSWORD`, `MONGO_APP_PASSWORD`, `ME_BASICAUTH_PASSWORD`
