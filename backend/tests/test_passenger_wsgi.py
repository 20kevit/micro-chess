"""cPanel Passenger adapter tests (Phase 13, deployment readiness).

These tests exercise the REAL adapter (``backend/passenger_wsgi.py``):
nothing about the WSGI bridge itself is mocked. Product behavior is
untouched — the adapter only transports the existing FastAPI app.
"""

import io
import json
import re
import tomllib
from pathlib import Path

import pytest
from a2wsgi.asgi import ASGIMiddleware

import passenger_wsgi
from app.core.config import Settings
from app.main import app as fastapi_app

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _wsgi_get(path: str):
    """Perform a real synchronous WSGI round-trip through ``application``."""
    environ = {
        "REQUEST_METHOD": "GET",
        "SCRIPT_NAME": "",
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "micro.20kevit.ir",
        "SERVER_PORT": "443",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "https",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.errors": io.BytesIO(),
        "wsgi.multithread": True,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
        "CONTENT_LENGTH": "0",
    }
    captured: dict = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(passenger_wsgi.application(environ, start_response))
    return captured, body


def test_application_exists_and_is_wsgi_bridge():
    assert callable(passenger_wsgi.application)
    # Per-process lazy construction: `application` is a callable that
    # resolves the a2wsgi bridge on first request in the current process
    # (fork-safe under LiteSpeed mod_lsapi). The bridge wraps the
    # existing FastAPI app — no duplicated app.
    middleware = passenger_wsgi.get_wsgi()
    assert isinstance(middleware, ASGIMiddleware)
    assert middleware.app is fastapi_app
    # Same-process caching: repeated resolution is a no-op.
    assert passenger_wsgi.get_wsgi() is middleware
    # The public callable stays a plain WSGI entry point.
    assert not isinstance(passenger_wsgi.application, ASGIMiddleware)


def test_health_reachable_through_adapter():
    captured, body = _wsgi_get("/health")
    assert captured["status"].startswith("200")
    assert json.loads(body.decode()) == {"status": "ok"}


def test_api_routes_reachable_through_adapter():
    captured, body = _wsgi_get("/api/v1/exercises")
    assert captured["status"].startswith("200")
    payload = json.loads(body.decode())
    assert isinstance(payload, list)
    assert payload, "exercise catalog must stay reachable through the adapter"


def test_auth_boundary_intact_through_adapter():
    # Anonymous request to a protected endpoint must still fail closed.
    captured, _body = _wsgi_get("/api/v1/users/me")
    assert captured["status"].startswith("401")


def test_unknown_route_stays_404_through_adapter():
    captured, _body = _wsgi_get("/api/v1/no-such-route")
    assert captured["status"].startswith("404")


def test_startup_is_idempotent_and_safe_to_rerun():
    # Mirrors Passenger process startup; safe on an initialized database
    # (uvicorn lifespan re-runs the same init in development).
    passenger_wsgi.run_startup()
    passenger_wsgi.run_startup()


def test_production_config_fails_safe():
    unsafe = Settings(environment="production", jwt_secret="change-me-in-production")
    with pytest.raises(RuntimeError):
        unsafe.ensure_ready()
    safe = Settings(environment="production", jwt_secret="operator-configured-secret")
    safe.ensure_ready()


def _requirement_names(path: Path) -> set[str]:
    names = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.add(re.split(r"[<>=!;\s\[]", line, maxsplit=1)[0].strip().lower())
    return names


def test_requirements_mirror_pyproject():
    # requirements.txt is a generated mirror for cPanel (see its header),
    # not an independent list: both files must name the same packages.
    pyproject = tomllib.loads((BACKEND_DIR / "pyproject.toml").read_text())
    pyproject_names = {
        re.split(r"[<>=!;\s\[]", dep, maxsplit=1)[0].strip().lower()
        for dep in pyproject["project"]["dependencies"]
    }
    requirements_names = _requirement_names(BACKEND_DIR / "requirements.txt")
    assert requirements_names == pyproject_names
    assert "a2wsgi" in requirements_names


def test_cpanel_yml_deploys_adapter_safely():
    # Plain-text assertions keep this test dependency-free (no YAML lib
    # needed): the file's structure is validated separately by deployment.
    script = (BACKEND_DIR.parent / ".cpanel.yml").read_text()
    assert "export DEPLOYPATH=/home/microche/microchess" in script
    assert "/home/example/" not in script
    assert "passenger_wsgi.py" in script
    assert "requirements.txt" in script
    assert "restart.txt" in script
    # Prebuilt-frontend architecture: the committed bundle deploys to
    # backend/static (served by FastAPI); nothing is built on the server.
    assert "frontend/dist" in script
    assert "backend/static" in script
    assert any(
        "pip" in ln and "install" in ln and "requirements.txt" in ln
        for ln in script.splitlines()
        if ln.strip().startswith("- ")
    ), "venv pip install must run on every deploy (idempotent)"
    # Safety invariants: no deployment *command* touches the repo clone
    # (the path is only mentioned in header comments), secrets, data,
    # virtualenvs, node tooling, or server-side builds.
    commands = [ln for ln in script.splitlines() if ln.strip().startswith("- ")]
    assert commands, "expected deployment tasks"
    assert not any("repositories/micro-chess" in ln for ln in commands)
    assert any(".env.example" in ln for ln in commands), "env template must deploy"
    for ln in commands:
        assert not re.search(r"\.env(?!\.example)", ln), ln
        # Never wipe the backend dir itself: a `.env`/database beside the
        # code must survive. Only explicit subpaths may be replaced
        # (`mkdir -p` of the dir itself is safe and exempt).
        if "rm " in ln:
            assert '"$DEPLOYPATH/backend"' not in ln, ln
        for forbidden in (
            ".db",
            "frontend/src",
            "node_modules",
            "npm ci",
            "npm install",
            "npm run build",
            "node server",
        ):
            assert forbidden not in ln, ln
