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

Fork-safety (critical under LiteSpeed mod_lsapi):
``ASGIMiddleware`` spawns a dedicated asyncio event-loop *thread* in its
constructor. LiteSpeed/CloudLinux with pre-forked workers
(``LSAPI_CHILDREN``, the default on this host) loads this module in a
master process and then *forks* children to serve requests. A thread
created before ``fork()`` has no runnable copy in the child, so
``a2wsgi``'s ``run_coroutine_threadsafe(...).result()`` would deadlock
forever on the first ``next()`` of the WSGI generator (symptom: requests
reach the WSGI layer — a ``PRE-WSGI`` probe logged — but no response is
ever written; LiteSpeed records ``200 0`` / the client times out). The
middleware is therefore built lazily per ``os.getpid()``: each forked
worker constructs its own loop thread on first request, which works
whether the request lands in the master or any child.

Layout: this file is deployed to the cPanel Python Application Root
(``.../backend``) next to ``app/`` and imported as top-level module
``passenger_wsgi``. The explicit ``sys.path`` additions below cover
running it under LiteSpeed's own interpreter (``/opt/alt/python312``)
where the account virtualenv site-packages are not otherwise on the
path; under Passenger the application root is also on the path.
"""

import os
import sys

# Account virtualenv site-packages (purelib) and any lib64 name for
# binary wheels (e.g. pydantic-core), plus cPanel's Alt-Python packages.
for _p in (
    "/home/microche/virtualenv/microchess/backend/3.12/lib/python3.12/site-packages",
    "/home/microche/virtualenv/microchess/backend/3.12/lib64/python3.12/site-packages",
    "/opt/alt/python312/lib/python3.12/site-packages",
):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)

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

_wsgi = None
_wsgi_pid = None


def get_wsgi() -> ASGIMiddleware:
    """Return a per-process middleware (see fork-safety note above).

    a2wsgi's event-loop thread is bound to the process that constructs
    it. LiteSpeed pre-forks children from a master that imported this
    module; a middleware built at import time would have no live loop
    thread in a forked child and would hang on the first request. Keying
    the cache by ``os.getpid()`` gives every forked worker its own
    functional instance at first request.
    """
    global _wsgi, _wsgi_pid
    pid = os.getpid()
    if _wsgi is None or _wsgi_pid != pid:
        _wsgi = ASGIMiddleware(fastapi_app)
        _wsgi_pid = pid
    return _wsgi


# Passenger looks up exactly this name. It must stay a plain WSGI
# callable: never expose the raw ASGI app here.
def application(environ, start_response):
    return get_wsgi()(environ, start_response)