# Deployment (public architecture & principles)

This document describes **how MicroChess is built, released, promoted, and
rolled back**. It is deliberately host-agnostic: this repository is public,
so no server address, filesystem path, service account, unit name, port,
backup location, or certificate path appears here.

Concrete host values are intentionally **not** in this repository. They
live in a private, never-committed operator runbook on the server that
runs MicroChess, and in the private env file consumed by
`ops/deploy.sh` (section 5). Where a value is structurally required to
explain the design, a neutral placeholder is used — `<PROJECT_ROOT>`,
`<PRODUCTION_SERVICE>`, `<BETA_SERVICE>`, `<INTERNAL_PORT>`,
`<SERVER_IP>`, `<BACKUP_ROOT>`, `<APP_USER>`.

Historical context: the project was previously deployed to cPanel shared
hosting. That path is no longer part of the architecture. The old runbook
is kept for the record in `docs/platform/CPANEL_DEPLOYMENT.md` and is
explicitly marked historical — do not follow it.

---

## 1. Architecture

```text
GitHub (main)
   ↓  git push
   <PROJECT_ROOT>/repo/        ← the ONLY Git working tree
   ↓  ops/deploy.sh beta
   <PROJECT_ROOT>/beta/        ← beta environment runtime
   ↓  verify on the beta domain
   ↓  ops/deploy.sh prod <tested-commit>
   <PROJECT_ROOT>/production/  ← production environment runtime
```

A deployment host holds one Git working tree, two runtime directories,
and one private configuration directory side by side, so a single agent
session can read the source of truth, both live runtimes, and the
operator-only configuration without leaving its workspace.

```text
<PROJECT_ROOT>/
  repo/        Git working tree — the source of truth
  beta/        beta environment runtime
  production/  production environment runtime
  private/     private operational configuration — NEVER tracked by Git
```

| Directory | Role | Git? | Editable? |
|---|---|---|---|
| `repo/` | Source of truth. Mirror of GitHub `main`. | **yes** (the only repo) | yes — this is where development happens |
| `beta/` | Runtime deployment. | no | never hand-edit; re-deploy instead |
| `production/` | Runtime deployment. | no | never hand-edit; re-deploy instead |
| `private/` | Operator-only host configuration and the private runbook. | no — it is a sibling of `repo/`, so it is outside the Git working tree and cannot be committed or pushed | yes — by the operator only; never copied into `repo/` |

`private/` being a sibling of `repo/` is what keeps it out of Git: no
`git add`, no commit, and no push can reach it, because it is not inside
a working tree. `.gitignore` additionally carries a `private/` rule as a
defence in depth against a private directory ever being copied inside
`repo/`.

Two public domains, one per environment:

| Environment | Public domain |
|---|---|
| beta | `beta.microchess.ir` |
| production | `microchess.ir`, `www.microchess.ir` |

### Git

```text
main   ← the only permanent branch
```

Development branches may be pushed for review and deleted when merged.
Nothing reaches `main` except through `repo/`. The historical `master`,
`free-premium-verification`, and `p11-sms-kavenegar-status` branches are
gone; the one commit unique to the abandoned P11 SMS line is preserved as
the tag `archive/p11-sms-kavenegar-status`.

---

## 2. Runtime shape

Each environment runs **one** FastAPI application served by a single
process manager (systemd on the current host) as a dedicated non-root
service account, bound to the loopback interface only. Behind it, Nginx
is the only public entry point and does nothing but reverse-proxy.

```text
internet → Nginx (TLS termination) → 127.0.0.1:<INTERNAL_PORT>
                                        → FastAPI/Uvicorn → SQLite
```

Nginx is proxy-only: it defines no `root` or `alias`, so `.env` files,
SQLite databases, virtualenvs, and source files are never reachable over
HTTP. The frontend is served by FastAPI itself from `backend/static/`
with SPA fallback (`backend/app/core/frontend.py`), so a single origin
serves the API and the SPA and no separate static host exists.

After editing a reverse-proxy vhost, validate and reload:

```bash
nginx -t && systemctl reload nginx
```

### Host configuration variables

`ops/deploy.sh` ships in this public repository and therefore contains no
host values. It takes them from a private env file that is never
committed. The variables are:

| Variable | Meaning |
|---|---|
| `MICROCHESS_REPO` | Git working tree |
| `MICROCHESS_BETA` | Beta runtime directory |
| `MICROCHESS_PROD` | Production runtime directory |
| `MICROCHESS_BACKUPS` | Backup root (`0700`) |
| `MICROCHESS_PROD_UNIT` | Production service unit name |
| `MICROCHESS_BETA_UNIT` | Beta service unit name |
| `MICROCHESS_PROD_PORT` | Production loopback port |
| `MICROCHESS_BETA_PORT` | Beta loopback port |
| `MICROCHESS_PROD_DB` | Production SQLite file |
| `MICROCHESS_BETA_DB` | Beta SQLite file |

The env file is looked up at `$MICROCHESS_PRIVATE_ENV`, falling back to
`<PROJECT_ROOT>/private/deploy.env` — the `private/` directory beside
`repo/`, `beta/`, and `production/`. The helper fails closed with a clear
error if a required value is missing; it never guesses. If the file is
absent, `REPO`, the two runtime directories, and the backup root are
derived from the script's own location, so a fresh clone anywhere is
self-consistent.

`private/` holds that env file plus the operator runbook that records the
concrete values this document intentionally replaced with placeholders.
Nothing in it is tracked, pushed, or symlinked into the repository.

---

## 3. Runtime separation

Beta and production share **no** mutable state. Each has its own:

| | Production | Beta |
|---|---|---|
| Database | its own SQLite file beside the code | its own SQLite file beside the code |
| `.env` | production secrets, `ENVIRONMENT=production` | independent secrets, `ENVIRONMENT=beta` |
| Virtualenv | its own | its own |
| Logs | its own service log | its own service log |
| Service unit | `<PRODUCTION_SERVICE>` | `<BETA_SERVICE>` |
| Port | `<INTERNAL_PORT>` | a different `<INTERNAL_PORT>` |
| Domain | `microchess.ir`, `www.` | `beta.microchess.ir` |

Enforcement is meant to be real, not conventional: the two runtime
directories are mode `0750` owned by their own service account
(`<APP_USER>`), so neither process can read the other's `.env` or
database. `DATABASE_URL` is a **relative** path
(`sqlite:///./microchess.db`) resolved against each service's working
directory, which is what keeps the databases apart.

Rules that follow from this:

- **Beta must never use the production database.** Never copy the
  production `*.db` into the beta runtime, and never point beta's
  `DATABASE_URL` at the production file.
- **Production must never use the beta database or beta secrets.**
- **Never run tests against a production database.** Use a disposable
  database.
- `.env` files and databases are runtime state and are gitignored. Only
  `*.example` templates are tracked.
- Telegram verification stays **disabled**
  (`VERIFICATION_TELEGRAM_ENABLED=false`).
- Production messaging-bot credentials stay in production only. A bot has
  exactly one webhook URL, so beta cannot use the production bot without
  leaking a production credential and cross-linking one bot identity
  across two databases. Beta runs with no bot configured until it gets
  its own.

---

## 4. Deployment principles

1. **`repo/` is the source of truth.** Changes are made, reviewed, and
   committed there. `beta/` and `production/` are build outputs.
2. **Never develop in a runtime directory.** Editing `beta/` or
   `production/` by hand is silently lost on the next deploy. A
   production change that is not a commit does not exist.
3. **Beta first.** Push to `main`, deploy beta, exercise the change on the
   beta domain, and only then touch production.
4. **Production takes an explicit commit.** `ops/deploy.sh prod` refuses
   to run without one, so production can never silently pick up an
   unreviewed commit.
5. **Uncommitted work is never deployed.** The helper aborts on a dirty
   working tree and ships the committed tree via `git archive`.
6. **Back up the production database before any production deploy.** The
   helper takes a verified online SQLite backup (`PRAGMA
   integrity_check`) into a `0700` backup root first.
7. **Deployments replace code paths only.** `backend/app`,
   `backend/static`, and `docs` are replaced. `backend/` itself is never
   wiped, so `.env` and the database always survive.
8. **Rollback is a deploy of a previous commit.** Migrations are
   additive, so rolling the code back normally needs no database action.
   If it does, restore the matching database backup from `<BACKUP_ROOT>`.
9. **Nothing is deployed to production automatically.** Promotion is an
   explicit operator action naming a commit that already passed on beta.

### Daily workflow

```bash
cd <PROJECT_ROOT>/repo

# 1. develop, then gate
cd backend && .venv/bin/pytest && cd ..
cd frontend && npm run typecheck && npm test && npm run build && cd ..

# 2. commit and push
git add -A && git commit -m "..." && git push origin main

# 3. deploy to beta
ops/deploy.sh beta                 # deploys origin/main

# 4. verify on the beta domain

# 5. promote the exact commit you tested
ops/deploy.sh prod <commit-sha>

# 6. confirm
ops/deploy.sh status
```

Roll back with the same tool:

```bash
ops/deploy.sh rollback prod <previous-good-commit-sha>
```

`ops/deploy.sh status` prints the live commit for `repo`, beta, and
production side by side; each runtime also records what it is serving in
`<runtime>/DEPLOYED_COMMIT`.

---

## 5. `ops/deploy.sh`

```text
ops/deploy.sh beta  [<commit>]    deploy a commit to beta   (default: origin/main)
ops/deploy.sh prod  <commit>      deploy a VERIFIED commit to production
ops/deploy.sh status              show what each runtime is serving
ops/deploy.sh rollback <env> <commit>
                                   re-deploy a previous known-good commit
```

Safety invariants — each one is load-bearing:

1. A dirty working tree is a hard error, and the payload is exported from
   the commit itself with `git archive`, so what ships is exactly the
   committed tree. Uncommitted work can never be deployed.
2. The commit must already exist on the remote: both runtimes are fed from
   GitHub, never from a local-only commit.
3. Production requires an explicit commit argument. There is no "deploy
   whatever is newest" path for production.
4. Only code paths are replaced. The runtime `.env` and the SQLite
   database are never written, moved, or deleted.
5. A verified online SQLite backup is taken before every production
   deploy and every rollback.
6. The service is restarted only after the new code is in place, and the
   script fails loudly if the health check does not pass.
7. The deployed commit is recorded in `<runtime>/DEPLOYED_COMMIT`, so
   `status` and `rollback` always know what is live.

---

## 6. Frontend build

`frontend/dist/` is committed on purpose: it is the prebuilt production
artifact, so the host never runs Node at runtime. Rebuild it before
committing any frontend change:

```bash
cd frontend
npm ci
VITE_API_BASE_URL= npm run build     # empty => same-origin /api/v1/...
```

A committed regression test fails if a future `frontend/dist/` ever
contains a development API base. The build must be reproducible: a clean
`npm ci && npm run build` must leave `git status` clean.

---

## 7. Backups and restore

Backups live under a private `<BACKUP_ROOT>` on the deployment host,
mode `0700`. Each production backup directory holds the database file
plus a verified integrity result. They are never served by the reverse
proxy and never committed.

To restore: stop the production service, put the backed-up database file
back beside the production code, restore ownership to the production
service account (`<APP_USER>`) and mode `0600`, start the service, then
confirm the health endpoint answers.

---

## 8. Security principles

- Secrets come only from the environment. They are never committed, never
  printed, and never bundled into the frontend. Only `*.example` templates
  are tracked.
- Production refuses to boot with the development JWT secret
  (`Settings.ensure_ready()`, tested).
- The application binds to loopback only; the reverse proxy is the single
  public entry point, and it never serves a filesystem path.
- Runtime directories are `0750` and owned per environment, so a
  compromise of one environment does not yield the other's secrets.
- Backup directories are `0700` and never web-reachable.
- Deploys are code-only and never overwrite runtime state, so a bad
  release cannot destroy data.
- Ports and service names are host configuration, not repository content.
  They are supplied through a private env file so that a public clone
  carries no operational intelligence about the live host.

---

## 9. TLS

TLS terminates on the deployment host, in front of both runtimes. Each
vhost is expected to serve the ACME HTTP-01 challenge path from a
dedicated webroot on plain HTTP, without redirecting it, so renewals keep
working even when everything else is redirected to HTTPS.

When a host cannot yet obtain a certificate, both domains are served over
plain HTTP and that limitation is tracked as a hosting/network matter,
not a repository or proxy one. Certificate storage paths are host
configuration and are not recorded in this repository.

---

## 10. Historical deployment (cPanel)

The retired cPanel/Passenger push deployment is preserved for the record
in `docs/platform/CPANEL_DEPLOYMENT.md`, with `.cpanel.yml`,
`backend/passenger_wsgi.py`, and `backend/lswsgi` kept but unused by the
current architecture. Those files describe a **different, retired hosting
account** and are not part of the current deployment described above.
