"""The automated-collection CLI: live mode is refused, fixture mode runs end to end."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "collection"))

import collect_auto

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "indigo" / "extract_2026-09-15.json"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 15, 21, 5, 0)

    def __call__(self) -> datetime:
        self.now += timedelta(seconds=2)
        return self.now


@pytest.fixture(autouse=True)
def _clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(collect_auto, "ist_now", Clock())


def test_live_mode_is_refused_before_anything_is_requested_or_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store = tmp_path / "store"
    code = collect_auto.main(
        ["--mode", "live", "--apw", "7", "--store", str(store), "--collection-date", "2026-09-15"]
    )
    assert code == 3
    assert not store.exists()
    err = capsys.readouterr().err
    assert "REFUSED BY THE COMPLIANCE GATE" in err
    assert "AUTOMATION_PROHIBITED" in err


def test_fixture_mode_single_travel_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = collect_auto.main(
        [
            "--mode",
            "fixture",
            "--fixture",
            str(FIXTURE),
            "--collection-date",
            "2026-09-15",
            "--travel-date",
            "2026-09-22",
            "--store",
            str(tmp_path / "store"),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    assert "FIXTURE -- SYNTHETIC PAGES, NOT MARKET DATA, NO REQUEST MADE" in out
    assert "TOTAL 1 searches: expected 5, found 5, accepted 5" in out
    assert '"admissible": 5' in out
    assert "INDEX  not computed" in out


def test_fixture_mode_full_apw_vector(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = collect_auto.main(
        [
            "--mode",
            "fixture",
            "--fixture",
            str(FIXTURE),
            "--collection-date",
            "2026-09-15",
            "--apw",
            "1,3,7,15,30,45,60",
            "--store",
            str(tmp_path / "store"),
        ]
    )
    out = capsys.readouterr().out
    assert code == 0, out
    assert "expected 35, found 34, accepted 32, sold_out 1, excluded 1, missing 1" in out
    assert '"admissible": 32' in out


def test_t21_is_a_configuration_error(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = collect_auto.main(
        [
            "--mode",
            "fixture",
            "--fixture",
            str(FIXTURE),
            "--apw",
            "7,21",
            "--store",
            str(tmp_path / "s"),
        ]
    )
    assert code == 1
    assert "T+21" in capsys.readouterr().err
    assert not (tmp_path / "s").exists()


def test_fixture_mode_requires_a_fixture(tmp_path: Path) -> None:
    assert (
        collect_auto.main(["--mode", "fixture", "--apw", "7", "--store", str(tmp_path / "s")]) == 1
    )
