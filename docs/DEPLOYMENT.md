# Deployment (canonical operations reference)

This is the single operator reference for how MicroChess is built,
deployed, and rolled back. It describes the **current** infrastructure.

Historical context: the project was previously deployed to cPanel shared
hosting. That path is no longer part of the architecture. The old runbook
is kept for the record in `docs/platform/CPANEL_DEPLOYMENT.md` and is
explicitly marked historical — do not follow it.

---

## 1. Architecture

```text
GitHub (main)
   ↓  git push
/opt/projects/micro-chess/repo/        ← the ONLY Git working tree
   ↓  ops/deploy.sh beta
/opt/projects/micro-chess/beta/        ← beta.microchess.ir runtime
   ↓  verify, approve
   ↓  ops/deploy.sh prod <tested-commit>
/opt/projects/micro-chess/production/  ← microchess.ir runtime
```

Everything below `/opt/projects/micro-chess/` is one OpenCode workspace.
`repo/`, `beta/`, and `production/` all sit inside it, so an agent started
in `/opt/projects/micro-chess` can read all three without leaving its
workspace boundary.

| Directory  | Role | Git? | Editable? |
|------------|------|------|-----------|
| `repo/`    | Source of truth. Mirror of GitHub `main`. | **yes** (the only repo) | yes — this is where development happens |
| `beta/`    | Runtime deployment. | no | never hand-edit; re-deploy instead |
| `production/` | Runtime deployment. | no | never hand-edit; re-deploy instead |

### Git

```text
main   ← the only permanent branch
```

Development branches may be pushed for review and deleted when merged.
Nothing is merged into `main` except via `repo/`. The historical
`master`, `free-premium-verification`, and `p11-sms-kavenegar-status`
branches are gone; the one commit unique to the abandoned P11 SMS line
is preserved as the tag `archive/p11-sms-kavenegar-status`.

---

## 2. Paths

| Purpose | Path |
|---|---|
| Workspace / OpenCode root | `/opt/projects/micro-chess` |
| Git working tree | `/opt/projects/micro-chess/repo` |
| Beta runtime | `/opt/projects/micro-chess/beta` |
| Production runtime | `/opt/projects/micro-chess/production` |
| Deployment helper | `/opt/projects/micro-chess/repo/ops/deploy.sh` |
| Backups | `/opt/backups/` (mode `0700`) |
| ACME webroot | `/var/www/letsencrypt` |

Inside a runtime, `backend/` holds `app/` (code), `static/` (the
prebuilt frontend bundle), `.venv/`, `.env`, and the SQLite database.

---

## 3. Services

| Unit | Runs as | Working directory | Port |
|---|---|---|---|
| `microchess.service` | `microchess` | `/opt/projects/micro-chess/production/backend` | `127.0.0.1:8000` |
| `microchess-beta.service` | `microchessbeta` | `/opt/projects/micro-chess/beta/backend` | `127.0.0.1:8001` |

Both are `Restart=always`, enabled at boot, and run as dedicated
non-root system users. Neither listens on a public interface: Nginx is
the only public entry point.

Useful commands:

```bash
systemctl status microchess microchess-beta
systemctl restart microchess-beta
journalctl -u microchess -f
journalctl -u microchess-beta -f
```

---

## 4. Domains

| Domain | Backend | Served by |
|---|---|---|
| `microchess.ir`, `www.microchess.ir` | `127.0.0.1:8000` (production) | `/etc/nginx/sites-available/microchess` |
| `beta.microchess.ir` | `127.0.0.1:8001` (beta) | `/etc/nginx/sites-available/microchess-beta` |

Nginx is proxy-only: it defines no `root` or `alias`, so `.env`, SQLite
databases, virtualenvs, and source files are never reachable over HTTP.
The frontend is served by FastAPI itself from `backend/static/` with SPA
fallback (`backend/app/core/frontend.py`).

Edit a vhost, then always:

```bash
nginx -t && systemctl reload nginx
```

---

## 5. Runtime separation

Beta and production share **no** mutable state. Each has its own:

| | Production | Beta |
|---|---|---|
| Database | `production/backend/microchess.db` | `beta/backend/microchess-beta.db` |
| `.env` | production secrets, `ENVIRONMENT=production` | independent secrets, `ENVIRONMENT=beta` |
| Virtualenv | `production/backend/.venv` | `beta/backend/.venv` |
| Logs | `journalctl -u microchess` | `journalctl -u microchess-beta` |
| Service | `microchess.service` | `microchess-beta.service` |
| Port | `127.0.0.1:8000` | `127.0.0.1:8001` |
| Domain | `microchess.ir`, `www.` | `beta.microchess.ir` |

Enforcement is real, not conventional: the two runtime directories are
mode `0750` owned by their own service user, so neither process can
read the other's `.env` or database. `DATABASE_URL` is a **relative**
path (`sqlite:///./microchess.db`) resolved against each unit's
`WorkingDirectory`, which is what keeps the databases apart.

Rules that follow from this:

- **Beta must never use the production database.** Never copy
  `microchess.db` into `beta/`, and never point beta's `DATABASE_URL` at
  the production file.
- **Production must never use the beta database or beta secrets.**
- `.env` files and databases are runtime state and are gitignored. Only
  `*.example` templates are tracked.
- Telegram verification stays **disabled** (`VERIFICATION_TELEGRAM_ENABLED=false`).
- The production Bale bot credentials stay in production only. A Bale bot
  has exactly one webhook URL, so beta cannot use the production bot
  without leaking a production credential and cross-linking one bot
  identity across two databases. Beta runs with no bot configured until
  it gets its own.

---

## 6. Deployment principles

1. **`repo/` is the source of truth.** Changes are made, reviewed, and
   committed there. `beta/` and `production/` are build outputs.
2. **Never develop in a runtime directory.** Editing `beta/` or
   `production/` by hand is silently lost on the next deploy. A
   production change that is not a commit does not exist.
3. **Beta first.** Push to `main`, deploy beta, exercise the change on
   `beta.microchess.ir`, and only then touch production.
4. **Production takes an explicit commit.** `ops/deploy.sh prod` refuses
   to run without one, so production can never silently pick up an
   unreviewed commit.
5. **Uncommitted work is never deployed.** The helper aborts on a dirty
   working tree and ships the committed tree via `git archive`.
6. **Back up the production database before any production deploy.** The
   helper takes a verified online SQLite backup (`PRAGMA
   integrity_check`) into `/opt/backups/` first.
7. **Deployments replace code paths only.** `backend/app`,
   `backend/static`, and `docs` are replaced. `backend/` itself is never
   wiped, so `.env` and the database always survive.
8. **Rollback is a deploy of a previous commit.** Migrations are
   additive, so rolling the code back normally needs no database action.
   If it does, restore the matching database backup from `/opt/backups/`.

### Daily workflow

```bash
cd /opt/projects/micro-chess/repo

# 1. develop, then gate
cd backend && .venv/bin/pytest && cd ..
cd frontend && npm run typecheck && npm test && npm run build && cd ..

# 2. commit and push
git add -A && git commit -m "..." && git push origin main

# 3. deploy to beta
ops/deploy.sh beta                 # deploys origin/main

# 4. verify on https://beta.microchess.ir

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

## 7. Frontend build

`frontend/dist/` is committed on purpose: it is the prebuilt production
artifact, so the host never runs Node at runtime. Rebuild it before
committing any frontend change:

```bash
cd frontend
npm ci
VITE_API_BASE_URL= npm run build     # empty => same-origin /api/v1/...
```

A committed regression test fails if a future `frontend/dist/` ever
contains `localhost` or `127.0.0.1`. The build must be reproducible: a
clean `npm ci && npm run build` must leave `git status` clean.

---

## 8. Backups and restore

```bash
ls -1 /opt/backups/                 # microchess-prod-<UTC timestamp>/
```

Each production backup directory holds `microchess.db` plus a verified
integrity result. To restore, stop `microchess.service`, copy the file
to `production/backend/microchess.db`, fix ownership
(`microchess:root`, mode `0600`), and start the service.

Backups are `0700` and are never served by Nginx or committed to Git.

---

## 9. TLS

TLS terminates on this host in front of both runtimes. The ACME
HTTP-01 webroot is `/var/www/letsencrypt`, and each vhost serves
`/.well-known/acme-challenge/` from disk on port 80 so renewals keep
working even if HTTP is redirected to HTTPS.

**Current state:** no certificate is installed. Certificate issuance
from this host currently fails at the TCP connect stage — Let's Encrypt
resolves this host correctly but its validators time out reaching port
80, so the challenge never arrives at Nginx. Issuing a certificate needs
inbound port 80/443 to be reachable from the validation networks, which
is a hosting/network matter rather than a repository or Nginx one. Until
that is resolved both domains are served over plain HTTP. Keep the
webroot in place: it is what a later `certbot certonly --webroot` run
needs, and renewals depend on it.
