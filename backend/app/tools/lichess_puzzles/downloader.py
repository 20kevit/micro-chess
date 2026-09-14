"""Streaming downloader for the official Lichess puzzle dump.

Failure-safe by construction: bytes stream to ``<dest>.part`` and the
file is atomically renamed to ``<dest>`` only after the transfer
completes. An interrupted or partial download therefore never corrupts
a previously downloaded valid file — the old file stays untouched and
the stale ``.part`` is removed on error. Re-running without ``--force``
is a cheap no-op when the destination already exists.

Only the standard library is used (no new dependency for HTTP).
"""

from __future__ import annotations

import logging
import os
import time
import urllib.request
from pathlib import Path

logger = logging.getLogger("microchess.lichess_puzzles.download")

CHUNK_SIZE = 1024 * 1024  # 1 MiB: streaming, never whole-file in RAM


def download(url: str, dest: Path, *, force: bool = False, timeout: int = 60) -> dict:
    """Download ``url`` to ``dest`` atomically. Returns a metadata dict.

    Metadata always carries ``status``: ``"downloaded"`` or
    ``"already_present"`` (plus byte counts and duration). Raises on
    network/HTTP errors without touching an existing ``dest``.
    """
    dest = Path(dest)
    if dest.is_file() and not force:
        return {
            "status": "already_present",
            "url": url,
            "path": str(dest),
            "bytes": dest.stat().st_size,
        }
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    started = time.monotonic()
    downloaded = 0
    expected: int | None = None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "MicroChess-lichess-ingest/1.0"})
        with urllib.request.urlopen(request, timeout=timeout) as response, open(part, "wb") as out:
            length = response.headers.get("Content-Length")
            if length is not None:
                try:
                    expected = int(length)
                except ValueError:
                    expected = None
            while True:
                chunk = response.read(CHUNK_SIZE)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if downloaded % (50 * CHUNK_SIZE) < CHUNK_SIZE:
                    logger.info("downloaded %.1f MiB ...", downloaded / (1024 * 1024))
        os.replace(part, dest)
    except Exception:
        try:
            if part.exists():
                part.unlink()
        except OSError:
            pass
        raise
    elapsed = time.monotonic() - started
    if expected is not None and downloaded != expected:
        raise IOError(f"incomplete download: got {downloaded} bytes, expected {expected}")
    logger.info("downloaded %s (%d bytes in %.1fs)", dest, downloaded, elapsed)
    return {
        "status": "downloaded",
        "url": url,
        "path": str(dest),
        "bytes": downloaded,
        "expected_bytes": expected,
        "duration_s": round(elapsed, 2),
    }
