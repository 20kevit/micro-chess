"""Operations CLI (Phase 12): first-admin bootstrap.

Run from ``backend/``::

    python -m app.cli create-admin <username>
    python -m app.cli create-admin <username> --confirm-production

There is no HTTP or frontend bootstrap path by design: role assignment
otherwise requires an existing ADMIN, so the very first administrator
is promoted locally by an operator with shell access.

Safety rules (enforced in ``promote_to_admin``, covered by tests):

* the user must already exist (looked up by canonical username);
  accounts are never created implicitly and passwords are never handled
* only the ADMIN role can be granted; arbitrary role assignment is
  not exposed
* idempotent: an account that already holds ADMIN reports success
  without changing anything
* in production (``ENVIRONMENT=production``) an explicit
  ``--confirm-production`` flag is required; without it the command
  refuses to run
"""

import argparse
import sys

from sqlalchemy.orm import Session


def promote_to_admin(
    db: Session, username: str, *, allow_production: bool = False, environment: str = "development"
) -> str:
    """Grant ADMIN to an existing account. Returns ``"created"`` or
    ``"already_admin"``. Raises ``ValueError("user_not_found")`` when no
    such account exists and
    ``RuntimeError("production_confirmation_required")`` when running
    against production without explicit confirmation.
    """
    from app.modules.admin import service as admin_service
    from app.modules.auth.service import normalize_username
    from app.modules.users.models import User

    if environment.strip().lower() == "production" and not allow_production:
        raise RuntimeError("production_confirmation_required")
    name = normalize_username(username)
    target = db.query(User).filter(User.username == name).first()
    if target is None:
        raise ValueError("user_not_found")
    already = any(row.role == "ADMIN" for row in (target.roles or []))
    roles, _ = admin_service.assign_role(db, actor_id=target.id, target_id=target.id, role="ADMIN")
    if "ADMIN" not in roles:  # pragma: no cover - assign_role guarantees this
        raise RuntimeError("bootstrap_failed")
    # ``assign_role`` is idempotent, so promoting an existing ADMIN is a
    # success no-op that changes nothing.
    return "already_admin" if already else "created"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="MicroChess operations CLI.")
    sub = parser.add_subparsers(dest="command", required=True)
    create_admin = sub.add_parser("create-admin", help="Grant ADMIN to an existing account.")
    create_admin.add_argument("username", help="Existing account username (canonical form).")
    create_admin.add_argument(
        "--confirm-production",
        action="store_true",
        help="Required when ENVIRONMENT=production.",
    )
    args = parser.parse_args(argv)

    from app.core.config import settings
    from app.db.session import SessionLocal, init_db

    init_db()
    db = SessionLocal()
    try:
        if args.command == "create-admin":
            try:
                outcome = promote_to_admin(
                    db,
                    args.username,
                    allow_production=args.confirm_production,
                    environment=settings.environment,
                )
            except ValueError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            except RuntimeError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 2
            if outcome == "already_admin":
                print(f"ok: '{args.username.strip().lower()}' is already an ADMIN (no change).")
            else:
                print(f"ok: '{args.username.strip().lower()}' is now an ADMIN.")
            return 0
    finally:
        db.close()
    return 0  # pragma: no cover - argparse guarantees a command


if __name__ == "__main__":
    raise SystemExit(main())
