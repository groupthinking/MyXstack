import json
import os
import threading
from pathlib import Path
from typing import List

import pytest

import a2a_store
import timeline_store
from scripts.migrate_json_to_sql import migrate
from storage_db import get_engine, metadata, normalize_database_url, reset_engine_for_tests


@pytest.fixture()
def db_url(tmp_path, monkeypatch):
    """Backend under test.

    Defaults to a throwaway SQLite file. Set TEST_DATABASE_URL to run the same
    suite against Postgres -- worth doing, because SQLite's BEGIN IMMEDIATE
    serializes writers and therefore masks concurrency bugs that only appear
    under Postgres' READ COMMITTED.
    """
    url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'xmcp.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    reset_engine_for_tests()

    # A shared Postgres persists across tests; start each one from a clean schema.
    engine = get_engine()
    metadata.drop_all(engine)
    metadata.create_all(engine)

    yield url
    reset_engine_for_tests()


def test_timeline_crud_round_trip(db_url):
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


def test_a2a_crud_round_trip(db_url):
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


def test_concurrent_timeline_updates_do_not_lose_metadata(db_url):
    item = timeline_store.add_item({"user_id": "u1", "title": "Race", "metadata": {}})
    # Each writer contributes one distinct key through a single update_item()
    # call, so the merge that must stay atomic happens inside the store. Two
    # writers looping over {key: i} instead converges on the same final value
    # whether or not updates are lost, which hides the race.
    writers = 40
    barrier = threading.Barrier(writers)
    errors: List[Exception] = []

    def writer(index: int) -> None:
        try:
            barrier.wait()
            timeline_store.update_item(item["id"], {"metadata": {f"k{index}": index}})
        except Exception as exc:  # pragma: no cover - surfaced by the assert below
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, errors[:3]
    updated = timeline_store.get_item(item["id"])
    assert updated is not None
    metadata = updated["metadata"]
    missing = [f"k{i}" for i in range(writers) if f"k{i}" not in metadata]
    assert not missing, f"lost {len(missing)} concurrent updates: {missing[:5]}"


def test_postgres_url_is_normalized():
    legacy = "postgres" + "://localhost:5432/xmcp"
    modern = "postgresql" + "://localhost:5432/xmcp"
    # Both must name the psycopg (v3) driver explicitly. requirements.txt ships
    # psycopg 3, but SQLAlchemy resolves a bare postgresql:// to psycopg2 and
    # dies with ModuleNotFoundError on first connect.
    expected = "postgresql+psycopg" + "://localhost:5432/xmcp"
    assert normalize_database_url(legacy) == expected
    assert normalize_database_url(modern) == expected

    # An explicitly chosen driver is left alone.
    pinned = "postgresql+psycopg2" + "://localhost:5432/xmcp"
    assert normalize_database_url(pinned) == pinned


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
