"""Integration tests for the Lichess puzzle ingestion pipeline.

Minimal end-to-end coverage with tiny local fixtures (never the real
multi-GB dump, never the network — downloads use ``file://`` URLs):

* process a plain CSV and a ``.csv.zst`` fixture -> identical outputs
* reruns are idempotent (byte-equivalent outputs, no duplicate growth)
* malformed rows are reported, never fatal
* interrupted/failed runs leave previous valid outputs untouched
* validate counts without writing anything
* download is atomic and skips existing files unless forced
"""

import csv
import io
import json
from pathlib import Path

import pytest
import zstandard as zstd

from app.tools.lichess_puzzles import cli as lichess_cli
from app.tools.lichess_puzzles import downloader
from app.tools.lichess_puzzles.config import config_from_env
from app.tools.lichess_puzzles.pipeline import run_process, run_validate

# Official sample rows from https://database.lichess.org/ (puzzle section).
SAMPLE_MATE_IN_2 = (
    "00sHx,q3k1nr/1pp1nQpp/3p4/1P2p3/4P3/B1PP1b2/B5PP/5K2 b k - 0 17,"
    "e8d7 a2e6 d7d8 f7f8,1760,80,83,72,"
    "mate mateIn2 middlegame short,https://lichess.org/yyznGmXs/black#34,"
    "Italian_Game Italian_Game_Classical_Variation,"
)
SAMPLE_LONG = (
    "00sJ9,r3r1k1/p4ppp/2p2n2/1p6/3P1qb1/2NQR3/PPB2PP1/R1B3K1 w - - 5 18,"
    "e3g3 e8e1 g1h2 e1c1 a1c1 f4h6 h2g1 h6c1,2671,105,87,325,"
    "advantage attraction fork middlegame sacrifice veryLong,https://lichess.org/gyFeQsOE#35,"
    "French_Defense French_Defense_Exchange_Variation,1607774862751"
)
SAMPLE_NO_OPENING = (
    "00sO1,1k1r4/pp3pp1/2p1p3/4b3/P3n1P1/8/KPP2PN1/3rBR1R b - - 2 31,"
    "b8c7 e1a5 b7b6 f1d1,998,85,94,293,"
    "advantage discoveredAttack master middlegame short,https://lichess.org/vsfFkG0s/black#62,,"
)

BAD_FEN_ROW = (
    "badFen1,not-a-fen,e8d7 a2e6,1500,80,50,10,"
    "mate short,https://lichess.org/aaaa#1,,"
)
BAD_MOVES_ROW = (
    "badMoves1,q3k1nr/1pp1nQpp/3p4/1P2p3/4P3/B1PP1b2/B5PP/5K2 b k - 0 17,"
    "e8d7 a2a8,1500,80,50,10,mate short,https://lichess.org/bbbb#2,,"
)
SHORT_ROW = "short1,only-two-columns\n"


@pytest.fixture()
def csv_text() -> str:
    return "\n".join(
        [
            SAMPLE_MATE_IN_2,
            SAMPLE_LONG,
            SAMPLE_NO_OPENING,
            BAD_FEN_ROW,
            BAD_MOVES_ROW,
            SHORT_ROW.strip(),
            SAMPLE_MATE_IN_2,  # exact duplicate PuzzleId -> duplicate_skipped
        ]
    ) + "\n"


@pytest.fixture()
def plain_csv(tmp_path: Path, csv_text: str) -> Path:
    path = tmp_path / "sample.csv"
    path.write_text(csv_text, encoding="utf-8")
    return path


@pytest.fixture()
def zst_csv(tmp_path: Path, csv_text: str) -> Path:
    path = tmp_path / "sample.csv.zst"
    compressed = zstd.ZstdCompressor().compress(csv_text.encode("utf-8"))
    path.write_bytes(compressed)
    return path


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    root.mkdir()
    return root


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_process_plain_csv_counts_and_outputs(data_dir: Path, plain_csv: Path):
    config = config_from_env(data_dir=data_dir, progress_every=2)
    manifest = run_process(config, input_path=plain_csv)
    assert manifest["counts"] == {
        "processed": 7, "accepted": 3, "rejected": 3, "duplicates": 1,
    }
    rows = _read_jsonl(config.output_path)
    assert [row["puzzle_id"] for row in rows] == ["00sHx", "00sJ9", "00sO1"]
    assert all(row["format_version"] == 1 for row in rows)
    rejected = _read_jsonl(config.rejected_path)
    codes = sorted(entry["code"] for entry in rejected)
    assert codes == ["bad_column_count", "bad_fen", "bad_moves", "duplicate_puzzle_id"]
    assert manifest["output_path"] == str(config.output_path)
    assert manifest["error_samples"], "manifest keeps samples for operators"


def test_process_zst_matches_plain_csv(data_dir: Path, plain_csv: Path, zst_csv: Path, tmp_path: Path):
    plain_out = tmp_path / "plain"
    zst_out = tmp_path / "zst"
    manifest_plain = run_process(config_from_env(data_dir=plain_out), input_path=plain_csv)
    manifest_zst = run_process(config_from_env(data_dir=zst_out), input_path=zst_csv)
    assert manifest_plain["counts"] == manifest_zst["counts"]
    assert (plain_out / "processed" / "puzzles.jsonl").read_bytes() == (
        zst_out / "processed" / "puzzles.jsonl"
    ).read_bytes()


def test_rerun_is_idempotent(data_dir: Path, plain_csv: Path):
    config = config_from_env(data_dir=data_dir)
    first = run_process(config, input_path=plain_csv)
    before = config.output_path.read_bytes()
    second = run_process(config, input_path=plain_csv)
    assert config.output_path.read_bytes() == before
    assert second["counts"] == first["counts"]
    assert len(_read_jsonl(config.output_path)) == 3


def test_failed_run_keeps_previous_valid_outputs(data_dir: Path, plain_csv: Path, tmp_path: Path):
    config = config_from_env(data_dir=data_dir)
    run_process(config, input_path=plain_csv)
    good_output = config.output_path.read_bytes()
    good_manifest = config.manifest_path.read_bytes()
    corrupt = tmp_path / "corrupt.csv.zst"
    corrupt.write_bytes(b"this is not zstd data {{{")
    with pytest.raises(Exception):
        run_process(config, input_path=corrupt, force=True)
    assert config.output_path.read_bytes() == good_output
    assert config.manifest_path.read_bytes() == good_manifest
    leftovers = list(config.processed_dir.glob("*.tmp"))
    assert leftovers == [], "temp files are cleaned up on failure"


def test_missing_input_raises_clean_error(data_dir: Path, tmp_path: Path):
    config = config_from_env(data_dir=data_dir)
    with pytest.raises(FileNotFoundError):
        run_process(config, input_path=tmp_path / "absent.csv.zst")


def test_validate_counts_without_writing(data_dir: Path, plain_csv: Path):
    report = run_validate(plain_csv)
    assert report["counts"] == {
        "processed": 7, "accepted": 3, "rejected": 3, "duplicates": 1,
    }
    assert not (data_dir / "processed").exists(), "validate must not write outputs"


def test_validate_supports_limit(plain_csv: Path):
    report = run_validate(plain_csv, limit=2)
    assert report["counts"]["processed"] == 2
    assert report["counts"]["accepted"] == 2


def test_download_from_file_url_is_atomic_and_rerunnable(tmp_path: Path):
    src = tmp_path / "origin.csv.zst"
    src.write_bytes(b"fake-zstd-payload")
    dest = tmp_path / "dl" / "lichess_db_puzzle.csv.zst"
    first = downloader.download(src.as_uri(), dest)
    assert first["status"] == "downloaded"
    assert dest.read_bytes() == b"fake-zstd-payload"
    assert not dest.with_name(dest.name + ".part").exists()
    second = downloader.download(src.as_uri(), dest)
    assert second["status"] == "already_present"
    third = downloader.download(src.as_uri(), dest, force=True)
    assert third["status"] == "downloaded"


def test_failed_download_leaves_existing_file_untouched(tmp_path: Path):
    dest = tmp_path / "lichess_db_puzzle.csv.zst"
    dest.write_bytes(b"previous-valid-data")
    with pytest.raises(Exception):
        downloader.download("file:///nonexistent-origin-xyz/data.zst", dest, force=True)
    assert dest.read_bytes() == b"previous-valid-data"
    assert not dest.with_name(dest.name + ".part").exists()


def test_cli_process_and_validate_end_to_end(
    data_dir: Path, plain_csv: Path, capsys: pytest.CaptureFixture
):
    assert lichess_cli.main(["process", "--input", str(plain_csv), "--data-dir", str(data_dir)]) == 0
    out = capsys.readouterr().out
    assert "processed=7 accepted=3 rejected=3 duplicates=1" in out
    assert lichess_cli.main(["validate", "--input", str(plain_csv), "--data-dir", str(data_dir)]) == 0


def test_cli_missing_input_exits_nonzero(data_dir: Path, tmp_path: Path):
    assert lichess_cli.main(["process", "--input", str(tmp_path / "nope.csv"),
                              "--data-dir", str(data_dir)]) == 1


def test_runtime_does_not_import_pipeline():
    """Guard: the FastAPI runtime stays independent of offline ingestion."""
    source = (Path(__file__).resolve().parent.parent / "app" / "main.py").read_text(encoding="utf-8")
    assert "lichess" not in source.lower()
    assert "app.tools" not in source
