# Lichess Puzzle Database Ingestion

Standalone offline pipeline that fetches the official Lichess puzzle
dump and normalizes it into a stable format for future MicroChess use.
It is **not** part of the application runtime: the FastAPI app never
imports it, no lifespan hook runs it, and the normal API works without
it. It never runs on production/cPanel unless an operator invokes it
explicitly over SSH.

## Source

* Data page: `https://database.lichess.org/` (CC0 license)
* Dump file: `lichess_db_puzzle.csv.zst` (~6.1M puzzles at last check)
* Official columns (the dump carries **no header row**; one is tolerated):

```text
PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags,DailyDate
```

Lichess move semantics: `FEN` is the position *before* the opponent's
move. Applying `Moves[0]` gives the position shown to the player, and
`Moves[1:]` is the solution.

## Layout

```text
backend/app/tools/lichess_puzzles/
  config.py      env-driven configuration (URL, data dir, progress interval)
  parser.py      pure per-row parse/validate/normalize (no I/O, no DB)
  downloader.py  atomic streaming HTTP download (stdlib only)
  pipeline.py    streaming process/validate orchestration + manifest
  cli.py         operator CLI: download / process / validate
```

Follows the existing operator-tooling pattern (`python -m app.cli
create-admin`, `python -m app.modules.<exercise>.seed`): run from
`backend/` with `python -m ...`, rerunnable, `--help` on every command.

## Usage

Run from `backend/`:

```bash
python -m app.tools.lichess_puzzles.cli --help
python -m app.tools.lichess_puzzles.cli download --help
python -m app.tools.lichess_puzzles.cli process --help
python -m app.tools.lichess_puzzles.cli validate --help
```

Typical flow:

```bash
python -m app.tools.lichess_puzzles.cli download
python -m app.tools.lichess_puzzles.cli process
python -m app.tools.lichess_puzzles.cli validate --limit 10000   # quick check
```

Data root defaults to `data/lichess_puzzles` (relative to the working
directory, gitignored):

```text
data/lichess_puzzles/
  lichess_db_puzzle.csv.zst            # raw official dump (never committed)
  lichess_db_puzzle.csv.zst.meta.json  # download metadata
  processed/
    puzzles.jsonl                      # normalized accepted records
    rejected.jsonl                     # rejected rows with reasons
    manifest.json                      # source/version/date + counts
```

## Configuration

| Variable | Default | Notes |
|---|---|---|
| `LICHESS_PUZZLE_URL` | `https://database.lichess.org/lichess_db_puzzle.csv.zst` | Official dump URL. |
| `LICHESS_PUZZLE_DATA_DIR` | `data/lichess_puzzles` | Local data root (raw + processed). |
| `LICHESS_PUZZLE_PROGRESS_EVERY` | `200000` | Progress log interval (rows). |

Explicit CLI flags (`--url`, `--data-dir`, `--input`,
`--progress-every`, `--limit`, `--force`) always override the
environment. No pipeline variable is required for the normal FastAPI
runtime.

## Validation rules

* `FEN` must parse with python-chess (reuses the standard-chess rule:
  no exercise-specific logic in the pipeline).
* Every UCI token in `Moves` must parse and be legal in sequence from
  the FEN (full line replayed on a `chess.Board`).
* `PuzzleId` must be non-empty with no whitespace, and unique within
  the run (later duplicates are skipped, first occurrence wins).
* Numerics: `Rating` 100–3000 (matches the content rating bounds),
  `RatingDeviation` 0–500, `Popularity` −100–100, `NbPlays` ≥ 0.
* `Themes` split on whitespace into a list (at least one required);
  `OpeningTags` split the same way (may be empty).
* `GameUrl` must start with `https://lichess.org/`;
  `DailyDate` is an optional millisecond Unix timestamp.
* Malformed rows are recorded in `rejected.jsonl` with
  `{line, code, detail}` and never abort the run.

## Output format (stable, versioned)

`processed/puzzles.jsonl`: one JSON object per line with
`"format_version": 1`:

```jsonc
{
  "format_version": 1,
  "puzzle_id": "00sHx",
  "fen_initial": "q3k1nr/... b k - 0 17",
  "fen_presented": "q5nr/... w - - 1 18",
  "opponent_move_uci": "e8d7",
  "solution_uci": ["a2e6", "d7d8", "f7f8"],
  "rating": 1760,
  "rating_deviation": 80,
  "popularity": 83,
  "nb_plays": 72,
  "themes": ["mate", "mateIn2", "middlegame", "short"],
  "game_url": "https://lichess.org/yyznGmXs/black#34",
  "opening_tags": ["Italian_Game", "Italian_Game_Classical_Variation"],
  "daily_date_ms": null,
  "source": "lichess",
  "source_reference": "00sHx"
}
```

`manifest.json` records tool version, format version, source URL/input
size, start/finish timestamps, `processed/accepted/rejected/duplicates`
counts, and the first error samples.

## Schema reuse (no new tables)

No new database model was created. The existing `puzzles` table
already carries everything a future import needs:

* `fen` ← `fen_presented`
* `answer_json` ← `{"solution_uci": [...], "puzzle_id": ..., "rating": ...}`
* `source` = `"imported"` (already a canonical `PUZZLE_SOURCES` value),
  `source_reference` ← Lichess `PuzzleId`
* `initial_rating` / `target_rating` ← Lichess `Rating`
* `content_hash` dedup already guards against re-imports

A future import step therefore maps JSONL lines onto `Puzzle` rows
through the existing Phase 07 content lifecycle — this pipeline only
prepares the data.

## Safety properties

* Streaming: decompression (`zstandard` stream reader) and CSV parsing
  are row-at-a-time; the full dump is never in RAM.
* Atomic writes: download streams to `.part`, processing writes to
  `.tmp` files; `os.replace` publishes results only on success.
  Interrupted runs leave previous valid data untouched.
* Idempotent: reruns regenerate equivalent outputs (no accumulation);
  `download` skips existing files and `process` skips up-to-date
  outputs unless `--force` is given.
* The raw dump and all derived large files live under the gitignored
  data directory and are never committed.

## Tests

```bash
cd backend
python -m pytest tests/test_lichess_puzzle_parser.py tests/test_lichess_puzzle_pipeline.py -q
```

Parser unit tests use the official sample rows from the source page;
pipeline integration tests use tiny local CSV/`.zst` fixtures
(including a `file://`-URL download test) — no network, no real dump.
