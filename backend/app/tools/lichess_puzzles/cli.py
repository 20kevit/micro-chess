"""Operator CLI for the Lichess puzzle ingestion pipeline.

Run from ``backend/`` (never from production/cPanel unless explicitly
needed — the pipeline is offline tooling, not part of the FastAPI
runtime)::

    python -m app.tools.lichess_puzzles.cli --help
    python -m app.tools.lichess_puzzles.cli download --help
    python -m app.tools.lichess_puzzles.cli download
    python -m app.tools.lichess_puzzles.cli process --help
    python -m app.tools.lichess_puzzles.cli process
    python -m app.tools.lichess_puzzles.cli validate --help
    python -m app.tools.lichess_puzzles.cli validate

Every subcommand is rerunnable: ``download`` skips an existing file
unless ``--force`` is given, and ``process`` regenerates
byte-equivalent outputs (no duplicates accumulate).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(name)s %(levelname)s: %(message)s")


def _add_common_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--data-dir",
        default=None,
        help="Local data root (default: $LICHESS_PUZZLE_DATA_DIR or data/lichess_puzzles).",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=None,
        help="Log progress every N rows (default: $LICHESS_PUZZLE_PROGRESS_EVERY or 200000).",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")


def build_parser() -> argparse.ArgumentParser:
    from app.tools.lichess_puzzles.config import DEFAULT_SOURCE_URL

    parser = argparse.ArgumentParser(
        prog="python -m app.tools.lichess_puzzles.cli",
        description="Offline Lichess puzzle-database ingestion (download / process / validate).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    download = sub.add_parser(
        "download",
        help="Download the official lichess_db_puzzle.csv.zst dump (resumable-safe, atomic).",
        description="Stream the official dump to <data-dir>/lichess_db_puzzle.csv.zst "
        "via a .part file + atomic rename. Rerunnable: skips when present unless --force.",
    )
    download.add_argument(
        "--url", default=None,
        help=f"Override the dump URL (default: $LICHESS_PUZZLE_URL or {DEFAULT_SOURCE_URL}).",
    )
    download.add_argument("--force", action="store_true", help="Re-download even if the file exists.")
    download.add_argument(
        "--timeout", type=int, default=60, help="HTTP timeout in seconds (default: 60)."
    )
    _add_common_options(download)

    process = sub.add_parser(
        "process",
        help="Decompress, validate and normalize the dump to stable JSONL (streaming).",
        description="Stream <input> row by row into processed/puzzles.jsonl + "
        "rejected.jsonl + manifest.json using temp files + atomic rename, "
        "so interrupted runs never corrupt previous valid outputs.",
    )
    process.add_argument(
        "--input",
        default=None,
        help="Input file (.csv.zst or plain .csv; default: <data-dir>/lichess_db_puzzle.csv.zst).",
    )
    process.add_argument(
        "--limit", type=int, default=None,
        help="Process at most N data rows (default: all). Useful for smoke tests.",
    )
    process.add_argument(
        "--force", action="store_true",
        help="Reprocess even when outputs are newer than the input.",
    )
    _add_common_options(process)

    validate = sub.add_parser(
        "validate",
        help="Validate the dump and report counts without writing outputs.",
        description="Stream <input> through the same parser/validator as "
        "`process` and print processed/accepted/rejected/duplicates. "
        "Writes nothing; exits 0 on success.",
    )
    validate.add_argument(
        "--input",
        default=None,
        help="Input file (.csv.zst or plain .csv; default: <data-dir>/lichess_db_puzzle.csv.zst).",
    )
    validate.add_argument(
        "--limit", type=int, default=None, help="Validate at most N data rows (default: all)."
    )
    _add_common_options(validate)
    return parser


def _resolve_config(args) -> "object":
    from app.tools.lichess_puzzles.config import config_from_env

    return config_from_env(
        data_dir=args.data_dir,
        source_url=getattr(args, "url", None),
        progress_every=args.progress_every,
    )


def cmd_download(args) -> int:
    from app.tools.lichess_puzzles import downloader

    config = _resolve_config(args)
    try:
        meta = downloader.download(
            config.source_url, config.raw_path, force=args.force, timeout=args.timeout
        )
    except Exception as exc:
        print(f"error: download failed: {exc}", file=sys.stderr)
        return 1
    if meta["status"] == "already_present":
        print(f"ok: already present: {config.raw_path} ({meta['bytes']} bytes; use --force to re-download)")
    else:
        print(f"ok: downloaded {meta['bytes']} bytes to {config.raw_path}")
        try:
            meta_path = Path(config.raw_meta_path)
            meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        except OSError as exc:
            print(f"warning: could not write download metadata: {exc}", file=sys.stderr)
    return 0


def cmd_process(args) -> int:
    from app.tools.lichess_puzzles.pipeline import run_process

    config = _resolve_config(args)
    try:
        manifest = run_process(
            config,
            input_path=Path(args.input) if args.input else None,
            limit=args.limit,
            force=args.force,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: processing failed: {exc}", file=sys.stderr)
        return 2
    counts = manifest["counts"]
    print(
        f"ok: processed={counts['processed']} accepted={counts['accepted']} "
        f"rejected={counts['rejected']} duplicates={counts['duplicates']}"
    )
    print(f"ok: output={manifest['output_path']}")
    print(f"ok: manifest={config.manifest_path}")
    return 0


def cmd_validate(args) -> int:
    from app.tools.lichess_puzzles.pipeline import run_validate

    config = _resolve_config(args)
    input_path = Path(args.input) if args.input else config.raw_path
    try:
        report = run_validate(input_path, limit=args.limit, progress_every=config.progress_every)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"error: validation failed: {exc}", file=sys.stderr)
        return 2
    counts = report["counts"]
    print(
        f"ok: processed={counts['processed']} accepted={counts['accepted']} "
        f"rejected={counts['rejected']} duplicates={counts['duplicates']}"
    )
    for sample in report["error_samples"]:
        print(f"  line {sample.get('line')}: [{sample.get('code')}] {sample.get('detail')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    if args.command == "download":
        return cmd_download(args)
    if args.command == "process":
        return cmd_process(args)
    if args.command == "validate":
        return cmd_validate(args)
    parser.error(f"unknown command {args.command!r}")
    return 2  # pragma: no cover - argparse guards this


if __name__ == "__main__":
    raise SystemExit(main())
