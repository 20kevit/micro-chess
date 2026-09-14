"""Configuration for the Lichess puzzle ingestion pipeline.

All values are env-driven with safe defaults; explicit CLI flags always
win over the environment. Nothing here is hard-coded to a developer
machine: large-file paths resolve under a single configurable data
directory (default ``data/lichess_puzzles`` relative to the current
working directory — run the CLI from ``backend/``).

Environment variables:

* ``LICHESS_PUZZLE_URL`` — official dump URL.
* ``LICHESS_PUZZLE_DATA_DIR`` — local data root (raw + processed).
* ``LICHESS_PUZZLE_PROGRESS_EVERY`` — progress log interval (rows).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SOURCE_URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"
SOURCE_PAGE_URL = "https://database.lichess.org/"

RAW_FILENAME = "lichess_db_puzzle.csv.zst"
RAW_META_FILENAME = "lichess_db_puzzle.csv.zst.meta.json"
PROCESSED_DIRNAME = "processed"
OUTPUT_FILENAME = "puzzles.jsonl"
REJECTED_FILENAME = "rejected.jsonl"
MANIFEST_FILENAME = "manifest.json"

NORMALIZED_FORMAT_VERSION = 1
TOOL_VERSION = "1.0.0"

DEFAULT_PROGRESS_EVERY = 200_000

ENV_URL = "LICHESS_PUZZLE_URL"
ENV_DATA_DIR = "LICHESS_PUZZLE_DATA_DIR"
ENV_PROGRESS_EVERY = "LICHESS_PUZZLE_PROGRESS_EVERY"


@dataclass(frozen=True)
class LichessPuzzleConfig:
    """Resolved pipeline configuration (env + CLI overrides applied)."""

    data_dir: Path
    source_url: str
    progress_every: int

    @property
    def raw_path(self) -> Path:
        return self.data_dir / RAW_FILENAME

    @property
    def raw_meta_path(self) -> Path:
        return self.data_dir / RAW_META_FILENAME

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / PROCESSED_DIRNAME

    @property
    def output_path(self) -> Path:
        return self.processed_dir / OUTPUT_FILENAME

    @property
    def rejected_path(self) -> Path:
        return self.processed_dir / REJECTED_FILENAME

    @property
    def manifest_path(self) -> Path:
        return self.processed_dir / MANIFEST_FILENAME


def config_from_env(
    *,
    data_dir: str | os.PathLike[str] | None = None,
    source_url: str | None = None,
    progress_every: int | None = None,
) -> LichessPuzzleConfig:
    """Build a config: explicit args > environment > built-in defaults."""
    raw_dir = (
        str(data_dir)
        if data_dir is not None
        else os.environ.get(ENV_DATA_DIR, "data/lichess_puzzles")
    )
    raw_url = source_url or os.environ.get(ENV_URL, DEFAULT_SOURCE_URL)
    if progress_every is None:
        try:
            progress_every = int(os.environ.get(ENV_PROGRESS_EVERY, str(DEFAULT_PROGRESS_EVERY)))
        except ValueError:
            progress_every = DEFAULT_PROGRESS_EVERY
    if progress_every < 1:
        progress_every = DEFAULT_PROGRESS_EVERY
    return LichessPuzzleConfig(
        data_dir=Path(raw_dir).expanduser(),
        source_url=raw_url.strip(),
        progress_every=progress_every,
    )
