"""Streaming process/validate pipeline for the Lichess puzzle dump.

Design notes:

* Streaming only: the ``.csv.zst`` input is decompressed incrementally
  (``zstandard`` stream reader) and parsed one CSV row at a time — the
  multi-million-row file is never loaded into RAM. Only the output
  file handles and a run-local ``PuzzleId`` seen-set are held in
  memory.
* Failure-safe: normalized output, rejected rows, and the manifest are
  written to ``*.tmp`` files and atomically renamed (``os.replace``)
  only after the whole input is consumed. An interrupted run leaves
  the previous valid outputs untouched.
* Idempotent: re-running over the same input regenerates byte-equivalent
  outputs (duplicate ``PuzzleId`` rows are skipped deterministically,
  keeping the first occurrence), so no duplicates can accumulate.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, TextIO

import zstandard as zstd

from app.tools.lichess_puzzles.config import (
    NORMALIZED_FORMAT_VERSION,
    TOOL_VERSION,
    LichessPuzzleConfig,
)
from app.tools.lichess_puzzles.parser import EXPECTED_COLUMNS, is_header_row, parse_row

logger = logging.getLogger("microchess.lichess_puzzles.pipeline")

MAX_ERROR_SAMPLES = 20


@dataclass
class PipelineStats:
    processed: int = 0
    accepted: int = 0
    rejected: int = 0
    duplicates: int = 0
    error_samples: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        data = asdict(self)
        return data


def open_csv_text_stream(path: Path) -> tuple[TextIO, IO]:
    """Open ``path`` (``.zst`` or plain CSV) as a text stream.

    Returns ``(text_stream, owned_binary)``; the caller must close the
    text stream (which closes the underlying binary stream). Streaming:
    at most one decompression window is buffered, never the whole file.
    """
    raw = open(path, "rb")
    if str(path).endswith(".zst"):
        decompressor = zstd.ZstdDecompressor()
        binary = decompressor.stream_reader(raw, read_across_frames=True)
        text = io.TextIOWrapper(binary, encoding="utf-8", errors="strict", newline="")
    else:
        binary = raw
        text = io.TextIOWrapper(raw, encoding="utf-8", errors="strict", newline="")
    return text, binary


def _record_error(stats: PipelineStats, line_no: int, error: dict) -> None:
    stats.rejected += 1
    if len(stats.error_samples) < MAX_ERROR_SAMPLES:
        stats.error_samples.append({"line": line_no, **error})


def process_stream(
    text_stream: TextIO,
    out_fh,
    rejected_fh,
    *,
    limit: int | None = None,
    progress_every: int = 200_000,
) -> PipelineStats:
    """Consume one CSV text stream, writing normalized/rejected JSONL.

    Pure streaming core shared by ``process`` and ``validate`` (pass
    ``None`` file handles to count only). Returns run statistics.
    """
    stats = PipelineStats()
    seen: set[str] = set()
    reader = csv.reader(text_stream)
    line_no = 0
    for cells in reader:
        line_no += 1
        if limit is not None and stats.processed >= limit:
            break
        if line_no == 1 and is_header_row(cells):
            continue
        if not cells or all(not (c or "").strip() for c in cells):
            _record_error(stats, line_no, {"code": "empty_row", "detail": "row has no content"})
            if rejected_fh is not None:
                rejected_fh.write(json.dumps({"line": line_no, "code": "empty_row"}) + "\n")
            continue
        stats.processed += 1
        normalized, error = parse_row(cells)
        if error is not None:
            _record_error(stats, line_no, error)
            if rejected_fh is not None:
                rejected_fh.write(json.dumps({"line": line_no, **error}) + "\n")
            continue
        assert normalized is not None
        puzzle_id = normalized["puzzle_id"]
        if puzzle_id in seen:
            stats.duplicates += 1
            if rejected_fh is not None:
                rejected_fh.write(
                    json.dumps({"line": line_no, "code": "duplicate_puzzle_id",
                                "detail": f"duplicate PuzzleId: {puzzle_id!r}"}) + "\n"
                )
            continue
        seen.add(puzzle_id)
        stats.accepted += 1
        if out_fh is not None:
            out_fh.write(json.dumps({"format_version": NORMALIZED_FORMAT_VERSION, **normalized}) + "\n")
        if stats.processed % progress_every == 0:
            logger.info(
                "processed=%d accepted=%d rejected=%d duplicates=%d",
                stats.processed, stats.accepted, stats.rejected, stats.duplicates,
            )
    return stats


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def process_file(
    input_path: Path,
    output_path: Path,
    rejected_path: Path,
    *,
    limit: int | None = None,
    progress_every: int = 200_000,
) -> PipelineStats:
    """Stream ``input_path`` into ``output_path``/``rejected_path`` atomically.

    Outputs are written to ``*.tmp`` siblings and renamed only on full
    success, so an interrupted run never corrupts previous valid data.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = output_path.with_name(output_path.name + ".tmp")
    tmp_rejected = rejected_path.with_name(rejected_path.name + ".tmp")
    started = time.monotonic()
    try:
        text_stream, _binary = open_csv_text_stream(input_path)
        try:
            with open(tmp_out, "w", encoding="utf-8") as out_fh, open(
                tmp_rejected, "w", encoding="utf-8"
            ) as rejected_fh:
                stats = process_stream(
                    text_stream, out_fh, rejected_fh,
                    limit=limit, progress_every=progress_every,
                )
        finally:
            text_stream.close()
    except Exception:
        for tmp in (tmp_out, tmp_rejected):
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
        raise
    os.replace(tmp_out, output_path)
    os.replace(tmp_rejected, rejected_path)
    elapsed = time.monotonic() - started
    logger.info(
        "done in %.1fs: processed=%d accepted=%d rejected=%d duplicates=%d",
        elapsed, stats.processed, stats.accepted, stats.rejected, stats.duplicates,
    )
    return stats


def run_process(
    config: LichessPuzzleConfig,
    *,
    input_path: Path | None = None,
    limit: int | None = None,
    force: bool = False,
) -> dict:
    """Run the full process step for ``config``. Returns the manifest dict.

    Skips work (returning the existing manifest) when outputs are newer
    than the input unless ``force`` is set — reruns are cheap no-ops.
    """
    source = Path(input_path) if input_path is not None else config.raw_path
    if not source.is_file():
        raise FileNotFoundError(f"input not found: {source}")
    if (
        not force
        and config.manifest_path.is_file()
        and config.output_path.is_file()
        and config.output_path.stat().st_mtime >= source.stat().st_mtime
    ):
        return json.loads(config.manifest_path.read_text(encoding="utf-8"))

    started_at = _utcnow_iso()
    stats = process_file(
        source, config.output_path, config.rejected_path,
        limit=limit, progress_every=config.progress_every,
    )
    manifest = {
        "tool": "lichess_puzzles",
        "tool_version": TOOL_VERSION,
        "format_version": NORMALIZED_FORMAT_VERSION,
        "source_url": config.source_url,
        "source_page": "https://database.lichess.org/",
        "input_path": str(source),
        "input_bytes": source.stat().st_size,
        "output_path": str(config.output_path),
        "rejected_path": str(config.rejected_path),
        "started_at": started_at,
        "finished_at": _utcnow_iso(),
        "row_limit": limit,
        "counts": {
            "processed": stats.processed,
            "accepted": stats.accepted,
            "rejected": stats.rejected,
            "duplicates": stats.duplicates,
        },
        "error_samples": stats.error_samples,
    }
    tmp_manifest = config.manifest_path.with_name(config.manifest_path.name + ".tmp")
    tmp_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp_manifest, config.manifest_path)
    return manifest


def run_validate(
    input_path: Path,
    *,
    limit: int | None = None,
    progress_every: int = 200_000,
) -> dict:
    """Validate ``input_path`` without writing outputs. Returns counts."""
    path = Path(input_path)
    if not path.is_file():
        raise FileNotFoundError(f"input not found: {path}")
    text_stream, _binary = open_csv_text_stream(path)
    try:
        stats = process_stream(text_stream, None, None, limit=limit, progress_every=progress_every)
    finally:
        text_stream.close()
    return {
        "input_path": str(path),
        "input_bytes": path.stat().st_size,
        "expected_columns": EXPECTED_COLUMNS,
        "counts": {
            "processed": stats.processed,
            "accepted": stats.accepted,
            "rejected": stats.rejected,
            "duplicates": stats.duplicates,
        },
        "error_samples": stats.error_samples,
    }
