"""Standalone Lichess puzzle-database ingestion pipeline.

Offline tooling (see ``app.tools``): downloads the official
``lichess_db_puzzle.csv.zst`` dump, validates every record with
streaming I/O (the multi-million-row file is never loaded into RAM),
and writes a stable normalized JSONL output plus a manifest for a
future database import.

Run from ``backend/``::

    python -m app.tools.lichess_puzzles.cli --help
    python -m app.tools.lichess_puzzles.cli download --help
    python -m app.tools.lichess_puzzles.cli process --help
    python -m app.tools.lichess_puzzles.cli validate --help

The pipeline never touches the application database and never runs as
part of the FastAPI lifespan. Full documentation lives in
``docs/LICHESS_PUZZLES.md``.
"""
