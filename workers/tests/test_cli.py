import json

from ukde_workers.cli import run_cli
from ukde_workers.runtime import run_once, status_payload


def test_status_payload_marks_bootstrap_mode() -> None:
    payload = status_payload()

    assert payload["service"] == "workers"
    assert payload["mode"] in {"bootstrap", "operational"}
    assert payload["telemetry_mode"] == "internal-only"
    assert payload["queue_depth_state"] in {"AVAILABLE", "UNAVAILABLE"}


def test_cli_status_output(capsys) -> None:
    exit_code = run_cli(["status"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert '"service": "workers"' in output


def test_run_once_unavailable_result(monkeypatch) -> None:
    monkeypatch.setattr("ukde_workers.runtime._resolve_job_service", lambda: None)

    result = run_once()

    assert result.action == "unavailable"
    assert result.job_id is None


def test_cli_run_once_json(capsys, monkeypatch) -> None:
    monkeypatch.setattr("ukde_workers.runtime._resolve_job_service", lambda: None)

    exit_code = run_cli(["run-once"])

    assert exit_code == 0
    output = capsys.readouterr().out
    parsed = json.loads(output)
    assert parsed["action"] == "unavailable"
