"""cPanel Passenger (WSGI) entry point for the MicroChess FastAPI application.

Passenger requires a synchronous WSGI callable named ``application`` in
this file, but the application (``app.main:app``) is FastAPI, i.e. ASGI.
``a2wsgi.asgi.ASGIMiddleware`` (pure Python, maintained, Python 3.12
compatible) bridges ASGI to WSGI with no extra server stack.

Lifespan note: the middleware never sends ASGI lifespan events, so the
FastAPI ``lifespan`` in ``app/main.py`` does NOT run under Passenger.
The required startup initialization (logging, production config guard,
idempotent schema setup) therefore runs once here at process startup,
mirroring that lifespan. ``init_db()`` (``ensure_schema``) is idempotent:
safe on fresh and existing databases, never destructive, never deletes
data, and running it again under uvicorn (which DOES run the lifespan)
is a harmless no-op.

Layout: this file is deployed to the cPanel Python Application Root
(``.../backend``) next to ``app/`` and imported as top-level module
``passenger_wsgi``. The ``sys.path`` bootstrap below only covers running
it as a plain script (local smoke tests); under Passenger the
application root is already on the path.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a2wsgi.asgi import ASGIMiddleware  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.db.session import init_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


def run_startup() -> None:
    """Run once at process startup. Mirrors the FastAPI lifespan in main.py."""
    configure_logging(settings.log_level)
    # Fail fast (process does not boot) on unsafe production config,
    # e.g. the development JWT secret with ENVIRONMENT=production.
    settings.ensure_ready()
    init_db()


run_startup()

# Passenger looks up exactly this name. It must stay a plain WSGI callable:
# never expose the raw ASGI app here.
application = ASGIMiddleware(fastapi_app)
