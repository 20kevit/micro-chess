# Security Policy

## Scope

The security model (authentication, authorization, privacy, abuse
protection, audit) is documented in `docs/platform/SECURITY.md`.
Deployment-specific rules (secrets handling, production guards,
`.cpanel.yml` safety invariants) are in
`docs/platform/CPANEL_DEPLOYMENT.md` (sections 5 and 14).

Hard rules, verified in code and tests:

- Secrets come only from the environment — never committed, never
  bundled into the frontend.
- Production refuses to boot with the development JWT secret
  (`Settings.ensure_ready()`, tested).
- `.env` files, databases, and credentials are never copied by
  `.cpanel.yml` and live outside the replaced code paths.

## Reporting a vulnerability

No public contact is designated yet. Until the maintainer adds one
here, report security issues privately to the repository owner
instead of opening a public issue, and do not include secrets,
credentials, or production data in any report.
