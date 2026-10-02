"""Command-line options of the lab console (python -m ui / python -m ui.replay_server)."""

import pytest

from ui.__main__ import parse_args


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("CRITICAL_RAT_RUNS_DIR", raising=False)


def test_defaults_bind_to_this_machine_only():
    args = parse_args([])
    assert (args.host, args.port, args.runs_dir) == ("127.0.0.1", 8000, "runs")


def test_environment_variables_are_used_when_flags_are_absent(monkeypatch):
    monkeypatch.setenv("PORT", "8123")
    monkeypatch.setenv("CRITICAL_RAT_RUNS_DIR", "/tmp/my-runs")
    args = parse_args([])
    assert (args.port, args.runs_dir) == (8123, "/tmp/my-runs")


def test_flags_win_over_environment_variables(monkeypatch):
    monkeypatch.setenv("PORT", "8123")
    monkeypatch.setenv("CRITICAL_RAT_RUNS_DIR", "/tmp/my-runs")
    args = parse_args(["--port", "9000", "--runs-dir", "elsewhere"])
    assert (args.port, args.runs_dir) == (9000, "elsewhere")


def test_a_malformed_port_variable_is_a_clear_error(monkeypatch, capsys):
    monkeypatch.setenv("PORT", "eighty")
    with pytest.raises(SystemExit):
        parse_args([])
    assert "PORT environment variable" in capsys.readouterr().err
