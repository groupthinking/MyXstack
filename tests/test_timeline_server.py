"""Timeline API behaviour: auth, typed cards, and action resolution.

Each test points the stores at a fresh tmp_path and reloads the modules so
that module-level store paths pick the new location up.
"""

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMELINE_STORE_PATH", str(tmp_path / "timeline.json"))
    monkeypatch.setenv("A2A_STORE_PATH", str(tmp_path / "a2a.json"))
    monkeypatch.delenv("TIMELINE_API_TOKEN", raising=False)
    monkeypatch.delenv("TIMELINE_CORS_ORIGINS", raising=False)

    import a2a_store
    import timeline_server
    import timeline_store

    importlib.reload(a2a_store)
    importlib.reload(timeline_store)
    importlib.reload(timeline_server)
    return TestClient(timeline_server.app)


def _create(client, **overrides):
    payload = {"title": "Card", "body": "hello", "actions": ["Approve", "Reject"]}
    payload.update(overrides)
    response = client.post("/v1/timeline/items", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# --- typed cards -----------------------------------------------------------


def test_legacy_card_round_trips_and_gains_typed_actions(client):
    item = _create(client)
    assert item["body"] == "hello"
    assert [a["id"] for a in item["actions"]] == ["approve", "reject"]
    assert item["blocks"][0]["text"] == "hello"


def test_typed_card_derives_body_from_blocks(client):
    item = _create(
        client,
        body="",
        blocks=[
            {"type": "facts", "label": "Order", "facts": [{"key": "Side", "value": "BUY"}]},
            {"type": "text", "label": "Note", "text": "pending"},
        ],
        actions=[{"id": "approve", "label": "Approve", "style": "primary"}],
    )
    # `body` stays populated for every reader that predates blocks.
    assert "Order:\nSide: BUY" in item["body"]
    assert "Note:\npending" in item["body"]
    assert item["actions"][0]["style"] == "primary"


def test_explicit_body_is_not_overwritten_by_blocks(client):
    item = _create(
        client,
        body="explicit",
        blocks=[{"type": "text", "text": "derived"}],
    )
    assert item["body"] == "explicit"


def test_unknown_block_type_is_rejected(client):
    response = client.post(
        "/v1/timeline/items",
        json={"title": "x", "blocks": [{"type": "hologram", "text": "hi"}]},
    )
    assert response.status_code == 422


# --- action resolution -----------------------------------------------------


def test_action_id_resolves_to_the_label_and_dispatches(client):
    item = _create(
        client,
        actions=[{"id": "approve", "label": "Approve Purchase"}],
    )
    response = client.patch(f"/v1/timeline/items/{item['id']}", json={"action_id": "approve"})
    assert response.status_code == 200
    assert response.json()["status"] == "approve purchase"

    # The dispatcher must receive the label, not the id — members match on it.
    messages = client.get("/v1/a2a/agents/mcp-orchestrator/messages").json()["messages"]
    action_messages = [m for m in messages if m["type"] == "timeline_action"]
    assert action_messages[0]["metadata"]["action"] == "Approve Purchase"


def test_legacy_action_label_still_works(client):
    item = _create(client)
    response = client.patch(f"/v1/timeline/items/{item['id']}", json={"action": "Approve"})
    assert response.status_code == 200
    assert response.json()["status"] == "approve"

    messages = client.get("/v1/a2a/agents/mcp-orchestrator/messages").json()["messages"]
    assert messages[0]["metadata"]["action"] == "Approve"


def test_action_id_the_card_never_offered_is_refused(client):
    item = _create(client, actions=[])
    response = client.patch(f"/v1/timeline/items/{item['id']}", json={"action_id": "approve"})
    assert response.status_code == 400

    # Nothing may be dispatched for a refused action.
    messages = client.get("/v1/a2a/agents/mcp-orchestrator/messages").json()["messages"]
    assert [m for m in messages if m["type"] == "timeline_action"] == []


def test_action_id_on_a_missing_card_is_404(client):
    response = client.patch("/v1/timeline/items/nope", json={"action_id": "approve"})
    assert response.status_code == 404


# --- auth ------------------------------------------------------------------


def test_api_is_open_when_no_token_is_configured(client):
    assert client.get("/v1/timeline/users/default/items").status_code == 200


def test_token_is_required_when_configured(client, monkeypatch):
    monkeypatch.setenv("TIMELINE_API_TOKEN", "s3cret")

    assert client.get("/v1/timeline/users/default/items").status_code == 401
    assert client.post("/v1/timeline/items", json={"title": "x"}).status_code == 401
    assert client.patch("/v1/timeline/items/any", json={"action": "Approve"}).status_code == 401
    assert client.get("/v1/a2a/agents").status_code == 401

    ok = client.get(
        "/v1/timeline/users/default/items",
        headers={"Authorization": "Bearer s3cret"},
    )
    assert ok.status_code == 200


def test_wrong_token_is_rejected(client, monkeypatch):
    monkeypatch.setenv("TIMELINE_API_TOKEN", "s3cret")
    response = client.get(
        "/v1/timeline/users/default/items",
        headers={"Authorization": "Bearer wrong"},
    )
    assert response.status_code == 401


def test_health_never_requires_a_token(client, monkeypatch):
    monkeypatch.setenv("TIMELINE_API_TOKEN", "s3cret")
    assert client.get("/health").status_code == 200
