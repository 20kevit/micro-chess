# Security Policy

## Scope

The security model (authentication, authorization, privacy, abuse
protection, audit) is documented in `docs/platform/SECURITY.md`.
Deployment-specific rules (secrets handling, runtime separation,
production guards, the deploy-path safety invariants) are in
`docs/DEPLOYMENT.md`.

Hard rules, verified in code and tests:

- Secrets come only from the environment — never committed, never
  bundled into the frontend.
- Production refuses to boot with the development JWT secret
  (`Settings.ensure_ready()`, tested).
- `.env` files, databases, and credentials are never committed and
  never overwritten by a deploy: only code paths (`backend/app`,
  `backend/static`, `docs`) are replaced, and the `backend/` directory
  holding `.env` and the database is never wiped.
- On the deployment host, beta and production each run as their own
  non-root service account over their own `.env`, database, virtualenv,
  loopback port, and domain. Neither can read the other's files.
- Backups are written to a private backup root with restrictive
  permissions and are never served by the reverse proxy (Nginx) or
  committed.
- Host-specific values (paths, service accounts, unit names, ports,
  backup locations, certificate paths) are **not** in this public
  repository. They are supplied at deploy time from a private,
  never-committed env file, and `ops/deploy.sh` fails closed if one is
  missing rather than guessing.

## Reporting a vulnerability

No public contact is designated yet. Until the maintainer adds one
here, report security issues privately to the repository owner
instead of opening a public issue, and do not include secrets,
credentials, or production data in any report.
