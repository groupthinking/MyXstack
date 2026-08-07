"""The token policy must hold on every entrypoint, not just `main()`.

`main.py` does `from timeline_server import app` for the Railway timeline
service, so a check that lives only in `timeline_server.main()` never runs
on the deployment that most needs it.
"""

import importlib

import pytest


def _reload_server(monkeypatch, tmp_path):
    monkeypatch.setenv("TIMELINE_STORE_PATH", str(tmp_path / "timeline.json"))
    monkeypatch.setenv("A2A_STORE_PATH", str(tmp_path / "a2a.json"))
    import timeline_server

    return importlib.reload(timeline_server)


def test_deployment_without_a_token_refuses_to_start(monkeypatch, tmp_path):
    monkeypatch.delenv("TIMELINE_API_TOKEN", raising=False)
    monkeypatch.delenv("TIMELINE_ALLOW_INSECURE", raising=False)
    monkeypatch.setenv("RAILWAY_SERVICE_NAME", "timeline-server")

    with pytest.raises(RuntimeError, match="TIMELINE_API_TOKEN"):
        _reload_server(monkeypatch, tmp_path)


def test_deployment_with_a_token_starts(monkeypatch, tmp_path):
    monkeypatch.setenv("RAILWAY_SERVICE_NAME", "timeline-server")
    monkeypatch.setenv("TIMELINE_API_TOKEN", "s3cret")
    assert _reload_server(monkeypatch, tmp_path).app is not None


def test_deployment_can_opt_out_explicitly(monkeypatch, tmp_path):
    monkeypatch.delenv("TIMELINE_API_TOKEN", raising=False)
    monkeypatch.setenv("RAILWAY_SERVICE_NAME", "timeline-server")
    monkeypatch.setenv("TIMELINE_ALLOW_INSECURE", "1")
    assert _reload_server(monkeypatch, tmp_path).app is not None


def test_local_run_without_a_token_only_warns(monkeypatch, tmp_path, capsys):
    for marker in ("RAILWAY_SERVICE_NAME", "RAILWAY_ENVIRONMENT", "KUBERNETES_SERVICE_HOST"):
        monkeypatch.delenv(marker, raising=False)
    monkeypatch.delenv("TIMELINE_API_TOKEN", raising=False)
    monkeypatch.delenv("TIMELINE_ALLOW_INSECURE", raising=False)

    assert _reload_server(monkeypatch, tmp_path).app is not None
    assert "WARNING: TIMELINE_API_TOKEN is not set" in capsys.readouterr().out
