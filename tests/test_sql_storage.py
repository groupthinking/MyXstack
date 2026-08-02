import json
import threading
from pathlib import Path

import pytest

import a2a_store
import timeline_store
from scripts.migrate_json_to_sql import migrate
from storage_db import normalize_database_url, reset_engine_for_tests


@pytest.fixture()
def sqlite_db_url(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'xmcp.db'}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    reset_engine_for_tests()
    yield db_url
    reset_engine_for_tests()


def test_timeline_crud_round_trip(sqlite_db_url):
    item = timeline_store.add_item(
        {
            "user_id": "u1",
            "title": "Title",
            "body": "Body",
            "status": "unread",
            "posted_by": "agent",
            "actions": ["Approve", "Reject"],
            "metadata": {"x": 1},
        }
    )

    got = timeline_store.get_item(item["id"])
    assert got is not None
    assert got["title"] == "Title"
    assert got["metadata"] == {"x": 1}

    listed = timeline_store.list_items("u1")
    assert [entry["id"] for entry in listed] == [item["id"]]

    updated = timeline_store.update_item(item["id"], {"status": "approved", "metadata": {"y": 2}})
    assert updated is not None
    assert updated["status"] == "approved"
    assert updated["metadata"] == {"x": 1, "y": 2}

    assert timeline_store.delete_item(item["id"]) is True
    assert timeline_store.get_item(item["id"]) is None


def test_a2a_crud_round_trip(sqlite_db_url):
    agents = a2a_store.list_agents()
    assert any(agent["id"] == "mcp-orchestrator" for agent in agents)

    registered = a2a_store.register_agent(
        {
            "id": "custom-agent",
            "name": "Custom",
            "description": "desc",
            "status": "online",
            "endpoint": "local",
            "kind": "bot",
            "tags": ["custom"],
        }
    )
    assert registered["kind"] == "bot"

    msg = a2a_store.add_message(
        {
            "from": "timeline-ui",
            "to": "custom-agent",
            "type": "timeline_action",
            "content": "approve",
            "metadata": {"timeline_item_id": "item-1"},
        }
    )
    assert msg["to"] == "custom-agent"

    messages = a2a_store.list_messages("custom-agent")
    assert len(messages) == 1
    assert messages[0]["id"] == msg["id"]
    assert messages[0]["from"] == "timeline-ui"


def test_concurrent_timeline_updates_do_not_lose_metadata(sqlite_db_url):
    item = timeline_store.add_item({"user_id": "u1", "title": "Race", "metadata": {}})
    barrier = threading.Barrier(3)

    def writer(key: str) -> None:
        barrier.wait()
        for i in range(40):
            timeline_store.update_item(item["id"], {"metadata": {key: i}})

    t1 = threading.Thread(target=writer, args=("a",))
    t2 = threading.Thread(target=writer, args=("b",))
    t1.start()
    t2.start()
    barrier.wait()
    t1.join()
    t2.join()

    updated = timeline_store.get_item(item["id"])
    assert updated is not None
    metadata = updated["metadata"]
    assert metadata["a"] == 39
    assert metadata["b"] == 39


def test_postgres_url_is_normalized():
    legacy = "postgres" + "://localhost:5432/xmcp"
    normalized = "postgresql" + "://localhost:5432/xmcp"
    assert normalize_database_url(legacy) == normalized


def test_json_to_sql_migration_is_idempotent(tmp_path, monkeypatch):
    timeline_path = tmp_path / "timeline_store.json"
    a2a_path = tmp_path / "a2a_store.json"
    db_url = f"sqlite:///{tmp_path / 'migrated.db'}"

    timeline_payload = {
        "items": [
            {
                "id": "item-1",
                "user_id": "default",
                "title": "Proposal",
                "body": "Body",
                "status": "unread",
                "posted_by": "agent",
                "actions": ["Approve"],
                "metadata": {"k": "v"},
                "created_at": "2025-01-01T00:00:00+00:00",
            }
        ]
    }
    a2a_payload = {
        "agents": [
            {
                "id": "agent-1",
                "name": "Agent",
                "description": "d",
                "status": "online",
                "endpoint": "e",
                "kind": "agent",
                "tags": ["t"],
            }
        ],
        "messages": [
            {
                "id": "msg-1",
                "from": "agent-1",
                "to": "timeline-ui",
                "type": "info",
                "content": "hello",
                "metadata": {"ok": True},
                "created_at": "2025-01-01T00:00:01+00:00",
            }
        ],
    }
    timeline_path.write_text(json.dumps(timeline_payload), encoding="utf-8")
    a2a_path.write_text(json.dumps(a2a_payload), encoding="utf-8")

    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("TIMELINE_STORE_PATH", str(timeline_path))
    monkeypatch.setenv("A2A_STORE_PATH", str(a2a_path))
    reset_engine_for_tests()

    first = migrate()
    second = migrate()

    assert first["timeline_items"][0] == 1
    assert first["a2a_agents"][0] == 1
    assert first["a2a_messages"][0] == 1
    assert second["timeline_items"][0] == 0
    assert second["a2a_agents"][0] == 0
    assert second["a2a_messages"][0] == 0

    migrated_item = timeline_store.get_item("item-1")
    assert migrated_item is not None
    assert migrated_item["metadata"]["k"] == "v"

    migrated_messages = a2a_store.list_messages("timeline-ui")
    assert len(migrated_messages) == 1
    assert migrated_messages[0]["id"] == "msg-1"
