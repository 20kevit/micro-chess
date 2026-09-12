"""Prebuilt-frontend serving tests (deployment architecture).

Covers the routing contract from ``app.core.frontend`` against a fixture
bundle AND against the real committed ``frontend/dist/`` artifact:

* ``/api/*``  → never ``index.html`` (JSON 404 preserved)
* API routes  → take precedence over the fallback
* static file → served with a deterministic Content-Type
* ``/`` + frontend routes → ``index.html`` (SPA refresh works)
* traversal   → can never escape the bundle directory
* committed ``dist/`` → production-safe (same-origin, no dev URLs)
"""

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.errors import register_error_handlers
from app.core.frontend import mount_spa, mount_spa_if_present, static_dir_for_package

BACKEND_DIR = Path(__file__).resolve().parent.parent
COMMITTED_DIST = BACKEND_DIR.parent / "frontend" / "dist"

INDEX_HTML = "<!doctype html><html><body><div>microchess</div></body></html>"


@pytest.fixture()
def bundle(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (root / "assets" / "app.abc123.js").write_text("console.log('app')", encoding="utf-8")
    (root / "assets" / "font.abc123.woff2").write_bytes(b"fakefont")
    # Decoy OUTSIDE the bundle: no request path may ever reach it.
    (tmp_path / "secret.txt").write_text("outside", encoding="utf-8")
    return root


def _spa_client(bundle: Path) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    @app.get("/api/v1/ping")
    def _ping() -> dict[str, str]:
        return {"status": "ok"}

    mount_spa(app, bundle)
    return TestClient(app)


def test_root_serves_index(bundle: Path):
    res = _spa_client(bundle).get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "microchess" in res.text


@pytest.mark.parametrize("route", ["/login", "/exercises", "/exercises/pin", "/admin/users"])
def test_spa_refresh_serves_index(bundle: Path, route: str):
    res = _spa_client(bundle).get(route)
    assert res.status_code == 200
    assert "microchess" in res.text


def test_static_asset_served(bundle: Path):
    res = _spa_client(bundle).get("/assets/app.abc123.js")
    assert res.status_code == 200
    assert res.text == "console.log('app')"


def test_font_content_type_is_deterministic(bundle: Path):
    res = _spa_client(bundle).get("/assets/font.abc123.woff2")
    assert res.status_code == 200
    assert res.headers["content-type"] == "font/woff2"


def test_api_route_takes_precedence(bundle: Path):
    res = _spa_client(bundle).get("/api/v1/ping")
    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_unknown_api_path_is_json_404_not_index(bundle: Path):
    res = _spa_client(bundle).get("/api/v1/no-such-route")
    assert res.status_code == 404
    assert "application/json" in res.headers["content-type"]
    assert "microchess" not in res.text


def test_traversal_cannot_escape_bundle(bundle: Path):
    client = _spa_client(bundle)
    for evil in ("/assets/../../secret.txt", "/..%2Fsecret.txt", "/%2e%2e/secret.txt"):
        res = client.get(evil)
        assert "outside" not in res.text


def test_mount_requires_index(tmp_path: Path):
    app = FastAPI()
    with pytest.raises(FileNotFoundError):
        mount_spa(app, tmp_path)


def test_no_mount_without_bundle():
    # Local development (no backend/static): API-only behavior unchanged.
    assert not (static_dir_for_package() / "index.html").is_file()
    assert mount_spa_if_present(FastAPI()) is False


def test_committed_dist_is_deployed_and_production_safe():
    # The committed artifact is what cPanel deploys: it must exist, serve
    # through the real wiring, and contain no development API URL.
    index = COMMITTED_DIST / "index.html"
    assert index.is_file(), "frontend/dist must be committed for git-push deployment"
    html = index.read_text(encoding="utf-8")
    assert "localhost" not in html and "127.0.0.1" not in html
    assert "/src/main" not in html, "dist must not reference Vite dev sources"

    app = FastAPI()
    register_error_handlers(app)
    mount_spa(app, COMMITTED_DIST)
    client = TestClient(app)

    root = client.get("/")
    assert root.status_code == 200
    assert "text/html" in root.headers["content-type"]
    assert "میکروچس" in root.text
    assert client.get("/login").status_code == 200
    assert "میکروچس" in client.get("/login").text

    asset_refs = re.findall(r'/(?:assets|chess-pieces)/[^"\'()]+', html)
    assert asset_refs, "index.html must reference hashed static assets"
    for ref in sorted(set(asset_refs)):
        res = client.get(ref)
        assert res.status_code == 200, ref

    for js in sorted((COMMITTED_DIST / "assets").glob("*.js")):
        body = js.read_text(encoding="utf-8")
        assert "localhost" not in body and "127.0.0.1" not in body, js.name
