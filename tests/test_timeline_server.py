import pytest

pytest.importorskip("fastapi")

import a2a_store
from fastapi.testclient import TestClient
from timeline_server import app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(a2a_store, "A2A_STORE_PATH", tmp_path / "a2a_store.json")
    return TestClient(app)


def test_create_agent_defaults_kind_to_agent(client):
    response = client.post("/v1/a2a/agents", json={"id": "no-kind", "name": "No Kind"})
    assert response.status_code == 200
    assert response.json()["kind"] == "agent"


def test_create_agent_accepts_bot_kind(client):
    response = client.post(
        "/v1/a2a/agents", json={"id": "tickerbot", "name": "Ticker Bot", "kind": "bot"}
    )
    assert response.status_code == 200
    assert response.json()["kind"] == "bot"


def test_create_agent_rejects_invalid_kind(client):
    response = client.post(
        "/v1/a2a/agents", json={"id": "bad", "name": "Bad", "kind": "robot"}
    )
    assert response.status_code == 422


def test_create_agent_rejects_null_kind(client):
    response = client.post("/v1/a2a/agents", json={"id": "bad", "name": "Bad", "kind": None})
    assert response.status_code == 422


def test_create_agent_persists_kind_in_registry(client):
    client.post("/v1/a2a/agents", json={"id": "tradedesk", "name": "Trade Desk", "kind": "agent"})
    response = client.get("/v1/a2a/agents/tradedesk")
    assert response.status_code == 200
    assert response.json()["kind"] == "agent"