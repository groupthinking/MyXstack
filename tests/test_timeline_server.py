"""Timeline API behaviour: auth, typed cards, and action resolution.

Each test points the store at a throwaway database and rebuilds the schema, so
nothing leaks between tests or into a developer's real `~/.xmcp/xmcp.db`.
"""

import importlib
import os

import pytest
from fastapi.testclient import TestClient

from storage_db import get_engine, metadata, reset_engine_for_tests


@pytest.fixture
def client(tmp_path, monkeypatch):
    url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'xmcp.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.delenv("TIMELINE_API_TOKEN", raising=False)
    monkeypatch.delenv("TIMELINE_CORS_ORIGINS", raising=False)
    reset_engine_for_tests()

    # A shared Postgres persists across tests; start each one from a clean
    # schema so ids and dispatched-action assertions stay independent.
    engine = get_engine()
    metadata.drop_all(engine)
    metadata.create_all(engine)

    import timeline_server

    importlib.reload(timeline_server)
    yield TestClient(timeline_server.app)
    reset_engine_for_tests()


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


def _dispatched_actions(client):
    messages = client.get("/v1/a2a/agents/mcp-orchestrator/messages").json()["messages"]
    return [m["metadata"].get("action") for m in messages if m["type"] == "timeline_action"]


def test_bare_action_label_the_card_never_offered_is_refused(client):
    # The legacy `action` path must be validated too — guarding only
    # `action_id` would leave this wide open while looking closed.
    item = _create(client)
    response = client.patch(
        f"/v1/timeline/items/{item['id']}", json={"action": "Delete Everything"}
    )
    assert response.status_code == 400
    assert _dispatched_actions(client) == []


def test_bare_action_label_on_a_card_with_no_actions_is_refused(client):
    item = _create(client, actions=[])
    response = client.patch(f"/v1/timeline/items/{item['id']}", json={"action": "Approve"})
    assert response.status_code == 400
    assert _dispatched_actions(client) == []


def test_action_label_contradicting_action_id_is_refused(client):
    item = _create(
        client,
        actions=[{"id": "approve", "label": "Approve"}, {"id": "reject", "label": "Reject"}],
    )
    response = client.patch(
        f"/v1/timeline/items/{item['id']}",
        json={"action_id": "approve", "action": "Reject"},
    )
    assert response.status_code == 400
    assert _dispatched_actions(client) == []


def test_matching_action_and_action_id_are_accepted(client):
    item = _create(client, actions=[{"id": "approve", "label": "Approve"}])
    response = client.patch(
        f"/v1/timeline/items/{item['id']}",
        json={"action_id": "approve", "action": "Approve"},
    )
    assert response.status_code == 200
    assert _dispatched_actions(client) == ["Approve"]


def test_duplicate_action_ids_are_rejected_at_creation(client):
    response = client.post(
        "/v1/timeline/items",
        json={
            "title": "x",
            "actions": [
                {"id": "approve", "label": "Approve Purchase"},
                {"id": "approve", "label": "Approve Trade"},
            ],
        },
    )
    assert response.status_code == 422


def test_unsafe_link_url_is_rejected_at_creation(client):
    response = client.post(
        "/v1/timeline/items",
        json={
            "title": "x",
            "blocks": [
                {
                    "type": "links",
                    "links": [{"label": "click", "url": "javascript:alert(1)"}],
                }
            ],
        },
    )
    assert response.status_code == 422


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
