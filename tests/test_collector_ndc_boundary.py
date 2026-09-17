"""IndiGo NDC groundwork: sandbox gate, credentials, and the index-input boundary.

No IndiGo NDC request, parser or fixture exists yet -- the official request model
could not be read (developer portal HTTP 502). These tests cover what does not
depend on it, and the invariant that matters most:

    A SANDBOX observation must never become PRIMARY index input.

Register entries marked HYPOTHETICAL exist only in this file.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import ClassVar

import pytest
import yaml

from apix.ingestion.collectors import runner as runner_module
from apix.ingestion.collectors.contract import (
    CollectionConfig,
    ConfigError,
    SearchParams,
    validate_travel_date_apw,
)
from apix.ingestion.collectors.gate import (
    CollectionMode,
    GateRefused,
    evaluate_live_gate,
    evaluate_sandbox_gate,
    find_source,
)
from apix.ingestion.collectors.index_boundary import (
    IndexBoundaryError,
    assert_not_index_input,
    index_input_observations,
    is_index_input_run,
)
from apix.ingestion.collectors.indigo.fixture import FixtureIndigoAdapter
from apix.ingestion.collectors.indigo.ndc import (
    REDACTED,
    REQUIRED_ENV,
    CredentialError,
    NdcCredentials,
    credentials_present,
)
from apix.ingestion.collectors.runner import run_collection
from apix.ingestion.store import CollectionStore, open_store
from apix.schemas.enums import SourceType
from tests.fixtures.indigo_synthetic import COLLECTION_DATE, day_payload
from tests.test_collector_runner import Clock, ScriptedAdapter, Sleeps

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "indigo" / "extract_2026-09-15.json"
REGISTRY = ROOT / "source_registry" / "registry.yaml"
sys.path.insert(0, str(ROOT / "tools" / "collection"))

SECRET_SUB = "SUB-7f3c-DO-NOT-PRINT"
SECRET_AUTH = "AUTH-91ab-DO-NOT-PRINT"
ENV = {
    "INDIGO_NDC_BASE_URL": "https://uat.example.invalid/ndc",
    "INDIGO_NDC_SUBSCRIPTION_KEY": SECRET_SUB,
    "INDIGO_NDC_AUTHORIZATION_KEY": SECRET_AUTH,
}

#: HYPOTHETICAL register entry shaped like the indigo_ndc record proposed in PR #27.
NDC_ENTRY: dict[str, object] = {
    "source_id": "indigo_ndc",
    "automation_gate": "AUTOMATION_ALLOWED_WITH_PERMISSION",
    "robots_status": "NOT_APPLICABLE",
    "data_admissibility": "NOT_ASSESSED",
    "tos_status": "NOT_VERIFIED",
}


class SandboxDouble(ScriptedAdapter):
    """Test double in SANDBOX mode with credentials 'issued'. No network."""

    registry_id: ClassVar[str] = "indigo"

    def __init__(self, script: dict[int, list[object]], clock: Clock, keys: bool = True) -> None:
        super().__init__(script, CollectionMode.SANDBOX, clock)
        self.keys = keys

    def credentials_present(self) -> bool:
        return self.keys


@pytest.fixture
def store(tmp_path: Path) -> Iterator[CollectionStore]:
    s = open_store(tmp_path / "store")
    yield s
    s.close()


# ── credentials ──────────────────────────────────────────────────────────────


def test_missing_credentials_name_the_variables_and_nothing_else() -> None:
    with pytest.raises(CredentialError) as exc:
        NdcCredentials.from_env({})
    for name in REQUIRED_ENV:
        assert name in str(exc.value)
    assert not credentials_present({})


def test_credentials_never_appear_in_repr_str_or_errors() -> None:
    creds = NdcCredentials.from_env(ENV)
    for rendering in (repr(creds), str(creds), f"{creds}"):
        assert SECRET_SUB not in rendering and SECRET_AUTH not in rendering
        assert REDACTED in rendering
    assert (
        creds.redact(f"Ocp token {SECRET_SUB} / {SECRET_AUTH}")
        == f"Ocp token {REDACTED} / {REDACTED}"
    )


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"INDIGO_NDC_BASE_URL": "http://uat.example.invalid"}, "https://"),
        ({"INDIGO_NDC_SUBSCRIPTION_KEY": "has space"}, "whitespace"),
    ],
)
def test_malformed_credentials_are_refused_without_echoing_them(
    override: dict[str, str], fragment: str
) -> None:
    with pytest.raises(CredentialError, match=fragment) as exc:
        NdcCredentials.from_env({**ENV, **override})
    assert "has space" not in str(exc.value)


# ── sandbox gate ─────────────────────────────────────────────────────────────


def test_sandbox_gate_clears_an_official_api_channel_with_issued_keys() -> None:
    assert evaluate_sandbox_gate(NDC_ENTRY, credentials_present=True).allowed


def test_sandbox_gate_refuses_without_keys() -> None:
    decision = evaluate_sandbox_gate(NDC_ENTRY, credentials_present=False)
    assert not decision.allowed
    assert any(f.startswith("credentials=ABSENT") for f in decision.failures)


def test_sandbox_gate_can_never_reach_a_website() -> None:
    website = dict(find_source(yaml.safe_load(REGISTRY.read_text(encoding="utf-8")), "indigo"))
    decision = evaluate_sandbox_gate(website, credentials_present=True)
    assert not decision.allowed
    assert any(f.startswith("robots_status=") for f in decision.failures)


@pytest.mark.parametrize("gate", ["AUTOMATION_UNKNOWN", "AUTOMATION_PROHIBITED", "MANUAL_ONLY"])
def test_sandbox_gate_refuses_channels_the_register_does_not_rate_as_published(gate: str) -> None:
    assert not evaluate_sandbox_gate(
        {**NDC_ENTRY, "automation_gate": gate}, credentials_present=True
    ).allowed


def test_with_permission_never_clears_the_live_gate() -> None:
    decision = evaluate_live_gate(NDC_ENTRY)
    assert not decision.allowed
    assert decision.failures[0].startswith("automation_gate=AUTOMATION_ALLOWED_WITH_PERMISSION")


# ── APW consistency ──────────────────────────────────────────────────────────


def test_travel_date_and_apw_must_agree_and_are_never_rewritten() -> None:
    validate_travel_date_apw(date(2026, 9, 15), date(2026, 9, 22), 7)
    with pytest.raises(ConfigError, match=r"T\+8 .* not the requested T\+7"):
        validate_travel_date_apw(date(2026, 9, 15), date(2026, 9, 23), 7)
    with pytest.raises(ConfigError, match=r"T\+21 is not a production bucket"):
        validate_travel_date_apw(date(2026, 9, 15), date(2026, 10, 6), 21)


# ── the index-input boundary ─────────────────────────────────────────────────


def test_no_automated_mode_maps_to_the_primary_frame() -> None:
    for mode in CollectionMode:
        assert not runner_module.FRAME_SUFFIX[mode].endswith("@primary")


def test_a_sandbox_run_is_labelled_and_is_never_index_input(
    store: CollectionStore, tmp_path: Path
) -> None:
    clock = Clock()
    adapter = SandboxDouble({7: [day_payload(7)]}, clock)
    config = CollectionConfig.for_apw("indigo", COLLECTION_DATE, [7])
    report = run_collection(
        config,
        adapter,
        store,
        export_root=tmp_path / "runs",
        registry_entry=NDC_ENTRY,
        clock=clock,
        sleep=Sleeps(),
    )
    (run,) = store.runs()
    assert run.frame_id.endswith("@sandbox")
    assert run.collector_identity == "sandbox:SandboxDouble"
    assert not is_index_input_run(run)
    stored = store.observations()
    assert len(stored) == 5
    assert {o.source_type for o in stored} == {SourceType.AUTHORIZED_FEED}
    assert index_input_observations(store) == []
    assert report.loaded


def test_a_sandbox_run_without_keys_requests_nothing_and_writes_nothing(
    store: CollectionStore, tmp_path: Path
) -> None:
    clock = Clock()
    adapter = SandboxDouble({7: [day_payload(7)]}, clock, keys=False)
    config = CollectionConfig.for_apw("indigo", COLLECTION_DATE, [7])
    with pytest.raises(GateRefused, match="credentials=ABSENT"):
        run_collection(
            config,
            adapter,
            store,
            export_root=tmp_path / "runs",
            registry_entry=NDC_ENTRY,
            clock=clock,
        )
    assert adapter.calls == []
    assert store.runs() == []
    assert not (tmp_path / "runs").exists()


def test_a_forged_primary_label_is_refused_before_anything_is_written(
    store: CollectionStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(runner_module.FRAME_SUFFIX, CollectionMode.FIXTURE, "@primary")
    clock = Clock()
    config = CollectionConfig.for_apw("indigo", COLLECTION_DATE, [7])
    with pytest.raises(IndexBoundaryError, match="reserved for the manual Day-1 contract"):
        run_collection(
            config,
            FixtureIndigoAdapter(FIXTURE, clock=clock),
            store,
            export_root=tmp_path / "runs",
            clock=clock,
        )
    assert store.runs() == []
    assert not (tmp_path / "runs").exists()


def test_only_manual_primary_observations_are_index_input(
    store: CollectionStore, tmp_path: Path
) -> None:
    from tests.test_manual_loader import attempt_row, fare_row, run_load

    run_load(tmp_path, [attempt_row()], [fare_row()])
    manual_store = open_store(tmp_path / "store")
    try:
        clock = Clock()
        config = CollectionConfig.for_apw("indigo", COLLECTION_DATE, [7])
        run_collection(
            config,
            FixtureIndigoAdapter(FIXTURE, clock=clock),
            manual_store,
            export_root=tmp_path / "runs",
            clock=clock,
        )
        runs = {r.frame_id.rsplit("@", 1)[1]: r for r in manual_store.runs()}
        assert set(runs) == {"primary", "fixture"}
        assert is_index_input_run(runs["primary"]) and not is_index_input_run(runs["fixture"])
        admitted = index_input_observations(manual_store)
        assert len(admitted) == 1 and admitted[0].flight_number == "2045"
        assert len(manual_store.observations()) == 6
    finally:
        manual_store.close()


def test_assert_not_index_input_accepts_every_automated_label() -> None:
    from apix.schemas.collection import CollectionRun

    base = CollectionRun(
        run_id="r",
        collection_date=COLLECTION_DATE,
        started_ts=datetime(2026, 9, 15, 21, 0),
        collection_window_start=datetime(2026, 9, 15, 21, 0),
        collection_window_end=datetime(2026, 9, 15, 22, 0),
        source_precedence_version="v",
        basket_version="b",
        parser_version="p",
        collector_version="0.1.0",
        collector_identity="sandbox:X",
        protocol_version="automated-collection-trial-1",
        methodology_version="2.1",
        frame_id="DEL-BOM/6E/AIRLINE_DIRECT/T7@sandbox",
    )
    for suffix in ("@sandbox", "@fixture", "@automated-trial"):
        assert_not_index_input(replace(base, frame_id=f"DEL-BOM/6E/AIRLINE_DIRECT/T7{suffix}"))
    with pytest.raises(IndexBoundaryError):
        assert_not_index_input(replace(base, frame_id="DEL-BOM/6E/AIRLINE_DIRECT/T7@primary"))
    assert not is_index_input_run(replace(base, frame_id="X@primary"))  # automated version


# ── CLI ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    import collect_auto

    monkeypatch.setattr(collect_auto, "ist_now", Clock())
    for name in REQUIRED_ENV:
        monkeypatch.delenv(name, raising=False)
    return collect_auto


def _registry_with_ndc(tmp_path: Path) -> Path:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    data["sources"] = [*data["sources"], NDC_ENTRY]
    path = tmp_path / "registry.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


NDC_ARGS = [
    "--source",
    "indigo-ndc",
    "--collection-date",
    "2026-09-15",
    "--travel-date",
    "2026-09-22",
    "--apw",
    "7",
]


def test_cli_ndc_fixture_is_blocked_pending_official_schema(
    cli, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:  # type: ignore[no-untyped-def]
    code = cli.main([*NDC_ARGS, "--mode", "fixture", "--store", str(tmp_path / "s")])
    out = capsys.readouterr()
    assert code == 5
    assert "SOURCE: INDIGO NDC" in out.out and "MODE: FIXTURE" in out.out
    assert "UNCONFIRMED" in out.err
    assert not (tmp_path / "s").exists()


def test_cli_ndc_sandbox_is_refused_against_the_real_register(
    cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:  # type: ignore[no-untyped-def]
    """Refused against the REAL register, whatever that register currently says.

    This previously asserted the refusal reason was ``'indigo_ndc' is not in the
    source registry`` -- true only while the channel was absent from the file.
    The source audit added ``indigo_ndc`` (AUTOMATION_ALLOWED_WITH_PERMISSION),
    so the gate chain now advances one barrier and refuses on ABSENT CREDENTIALS
    instead. Both are refusals; pinning the exact reason made this test depend on
    which pull request had landed.

    What must hold in every register state is the OUTCOME: exit 3, nothing
    requested, nothing written. Credentials are cleared first so a developer
    holding real UAT keys gets the same result as CI.
    """
    for var in REQUIRED_ENV:
        monkeypatch.delenv(var, raising=False)
    store = tmp_path / "s"
    code = cli.main([*NDC_ARGS, "--mode", "sandbox", "--store", str(store)])
    err = capsys.readouterr().err

    assert code == 3, "sandbox against the real register must be refused"
    assert "REFUSED BY THE COMPLIANCE GATE" in err
    assert not store.exists(), "a refused run must write nothing"
    # The reason must be one of the two legitimate barriers, never a clearance.
    assert "credentials=ABSENT" in err or "is not in" in err


def test_cli_ndc_sandbox_without_keys_names_the_variables(
    cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(cli, "REGISTRY", _registry_with_ndc(tmp_path))
    monkeypatch.setattr(cli, "REPO", tmp_path)
    code = cli.main([*NDC_ARGS, "--mode", "sandbox", "--store", str(tmp_path / "s")])
    err = capsys.readouterr().err
    assert code == 3
    assert "credentials=ABSENT" in err
    assert "INDIGO_NDC_SUBSCRIPTION_KEY" in err


def test_cli_ndc_sandbox_with_keys_stops_before_any_request_and_never_prints_them(
    cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(cli, "REGISTRY", _registry_with_ndc(tmp_path))
    monkeypatch.setattr(cli, "REPO", tmp_path)
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    code = cli.main([*NDC_ARGS, "--mode", "sandbox", "--store", str(tmp_path / "s")])
    out = capsys.readouterr()
    assert code == 5
    assert "MODE: SANDBOX" in out.out and "BLOCKED" in out.err
    for secret in (SECRET_SUB, SECRET_AUTH):
        assert secret not in out.out and secret not in out.err
    assert not (tmp_path / "s").exists()


def test_cli_ndc_live_is_refused_for_a_with_permission_channel(
    cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(cli, "REGISTRY", _registry_with_ndc(tmp_path))
    monkeypatch.setattr(cli, "REPO", tmp_path)
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    assert cli.main([*NDC_ARGS, "--mode", "live", "--store", str(tmp_path / "s")]) == 3
    assert "AUTOMATION_ALLOWED_WITH_PERMISSION" in capsys.readouterr().err


def test_cli_website_source_has_no_sandbox(cli, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    assert (
        cli.main(
            [
                "--mode",
                "sandbox",
                "--apw",
                "7",
                "--collection-date",
                "2026-09-15",
                "--store",
                str(tmp_path / "s"),
            ]
        )
        == 1
    )


def test_cli_refuses_a_travel_date_that_does_not_match_the_apw(
    cli, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(
        [
            "--mode",
            "fixture",
            "--fixture",
            str(FIXTURE),
            "--collection-date",
            "2026-09-15",
            "--travel-date",
            "2026-09-23",
            "--apw",
            "7",
            "--store",
            str(tmp_path / "s"),
        ]
    )
    assert code == 1
    assert "not the requested T+7" in capsys.readouterr().err


def test_cli_accepts_a_matching_travel_date_and_apw(cli, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    code = cli.main(
        [
            "--mode",
            "fixture",
            "--fixture",
            str(FIXTURE),
            "--collection-date",
            "2026-09-15",
            "--travel-date",
            "2026-09-22",
            "--apw",
            "7",
            "--store",
            str(tmp_path / "s"),
        ]
    )
    assert code == 0


def test_search_params_record_is_unchanged_for_sandbox_runs() -> None:
    params = SearchParams(
        "indigo-direct",
        CollectionConfig.for_apw("indigo", COLLECTION_DATE, [7]).contract,
        COLLECTION_DATE,
        COLLECTION_DATE + timedelta(days=7),
    )
    assert params.as_record()["apw_bucket"] == 7
