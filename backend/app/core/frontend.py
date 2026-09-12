"""Serve the prebuilt frontend (Vite ``dist/``) with SPA fallback.

Production architecture (see docs/platform/CPANEL_DEPLOYMENT.md): the
frontend is built locally (``npm ci && npm run build``), committed as
``frontend/dist/``, and deployed by ``.cpanel.yml`` to
``backend/static/`` next to this package. No Node runs in production.

Routing contract (order matters — this mounts LAST, after every API
router, ``/health``, and FastAPI's own ``/docs``/``/openapi.json``):

* ``/api/*``             → never served here; unknown API paths keep the
  JSON 404 envelope from ``app.core.errors``.
* existing static file  → served directly (``/assets/*``, fonts, SVGs).
* ``/`` and any other   → ``index.html`` (React Router owns the route).
  (non-API) path

No production paths live in this code: the directory resolves relative
to this package (``backend/static`` in production; absent locally, where
the Vite dev server owns the frontend instead). When the directory (or
its ``index.html``) is absent, nothing mounts and API behavior is
byte-identical to a backend-only deployment.
"""

import mimetypes
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

# Deterministic media types across platforms/Python versions: the stdlib
# mapping varies (notably for fonts), and browsers key script/font
# handling off the Content-Type.
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("font/woff", ".woff")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("text/javascript", ".js")

INDEX = "index.html"


def static_dir_for_package() -> Path:
    """Resolve ``backend/static`` relative to this package. No hard-coded
    deployment roots: the same resolution works locally and in production."""
    return Path(__file__).resolve().parent.parent / "static"


def _safe_file(static_dir: Path, request_path: str) -> Path | None:
    """Return the static file for ``request_path`` or None. Never escapes
    ``static_dir`` (percent-decoded ``..`` segments resolve back inside and
    then fail the file check, or are rejected outright)."""
    root = static_dir.resolve()
    candidate = (root / request_path.lstrip("/")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Mount ``/`` + SPA fallback serving ``static_dir``. MUST be called
    after all API routes are registered so they always take precedence."""
    root = static_dir.resolve()
    index = root / INDEX
    if not index.is_file():
        raise FileNotFoundError(f"frontend bundle missing: {index}")

    def _respond(request_path: str) -> FileResponse:
        if request_path.startswith("api/"):
            # Unknown API path: keep the JSON 404 contract, never index.html.
            raise HTTPException(status_code=404, detail="not_found")
        found = _safe_file(root, request_path)
        return FileResponse(found if found is not None else index)

    @app.get("/", include_in_schema=False)
    def _spa_root() -> FileResponse:
        return FileResponse(index)

    @app.get("/{full_path:path}", include_in_schema=False)
    def _spa_fallback(full_path: str) -> FileResponse:
        return _respond(full_path)


def mount_spa_if_present(app: FastAPI) -> bool:
    """Mount the prebuilt frontend when deployed, else do nothing.
    Returns True when mounted (production) so callers/tests can assert."""
    static_dir = static_dir_for_package()
    if not (static_dir / INDEX).is_file():
        return False
    mount_spa(app, static_dir)
    return True
