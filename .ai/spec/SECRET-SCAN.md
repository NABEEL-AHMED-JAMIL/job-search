# Secret scan — findings and triage

Document 15's security section listed "secret scanning" as MISSING, never run. It has now been
run, over the **git history** of both repositories rather than over the working tree, and this is
what it found.

Scanner: gitleaks 8.30.1, default rule set plus `process/.gitleaks.toml`.
Run it with `.ai/tools/secret-scan.sh`. First run: 2026-09-09.

## Why history and not the working tree

A secret is exposed the moment it is pushed. Deleting the file in a later commit does not
unpublish it — anyone who cloned, forked, or fetched has it, and so does every mirror and CI
cache. **Two of the three `process` findings are files that no longer exist in HEAD**, and a
working-tree scan calls both of them clean.

That is also why the sections below separate *what has to happen* from *what has been done*.
Removing a file is not remediation. **Rotation is the only thing that works.**

## Real findings — process (3)

All three are in published history on `origin`. None can be fixed by editing a file.

| Finding | First committed | In HEAD? | What it is | What has to happen |
|---|---|---|---|---|
| `.env.bak.1787579140` | 2026-08-24 (`2fa0e1d8`) | **yes** | A backup of the service `.env`, holding `SPRING_DATASOURCE_PASSWORD`, `MAIL_PASSWORD` and `WORKER_CALLBACK_TOKEN` | **Rotate all three credentials.** Then untrack the file. `.gitignore` lines 44–47 already name this pattern, but a rule does not untrack a file that is already tracked. |
| `keys/process-key` | 2024-03-12 (`d308afef`) | no | An RSA private key | **Rotate the key pair** and reissue whatever trusts it. Its absence from HEAD is not remediation. |
| `application-dev.properties:58` | 2022-11-30 (`0595865b`) | no (line is a comment now) | `spring.security.oauth2.client.registration.google.clientSecret` | **Rotate the Google OAuth client secret** in the Google Cloud console. |

## Real findings — scheduler1 (5)

| Finding | Committed | In HEAD? | What it is | What has to happen |
|---|---|---|---|---|
| `src/index.html:16` ×5 | 2022-12-17 → 2023-04-06 | no | A Google API key (`gcp-api-key`), added and re-committed across five commits | **Rotate the key**, or restrict it by referrer/API in the Google Cloud console if it is meant to be public. Five separate commits carry it. |

## Allowlisted — read, and confirmed not to be credentials

Each of these was opened and checked. The reasons live in `process/.gitleaks.toml` beside the
entries so that anyone removing one sees why it was added.

| Finding | Why it is not a secret |
|---|---|
| `UserWelcomeTemplateTest.java`, `TenantWelcomeTemplateTest.java` | A `temporary_password` for a person who does not exist (Rosa Delgado at Litware Financial), asserted against in the same file as a string that must appear in the rendered message. |
| `application-e2e.properties` — `jwt.secret.key` | Signs tokens the suite mints for users it creates inside a rolled-back transaction against a local dev database. The profile is never deployed, and the base64 decodes to a sentence saying so. |
| `KafkaCertificateUtil.java` — `X509Certificate` | A Java class name. The rule matched the parameter list of `keyMatchesCertificate(PrivateKey, X509Certificate)`. Allowlisted anchored, so a real key containing that text would still be reported. |
| `KafkaCertificateUtilTest.java` — PEM block | A PEM header whose body is the four characters `AAAA` — a deliberately invalid key, used to prove the parser *refuses* malformed input. Allowlisted on the placeholder body rather than on the file, so a real key pasted into that test would still be reported. |
| `target/` | Build output. The same file scanned twice, and this copy is not in git. |

## What the check does from now on

`.ai/tools/secret-scan.sh` compares each repository against the counts above and **fails when the
number goes up**, naming what it found. It does not compare against zero: a repository with known
unrotated history cannot reach zero, and a threshold that can never be met is a check people turn
off.

When a credential above is rotated, remove its row here and lower the count in the script.
