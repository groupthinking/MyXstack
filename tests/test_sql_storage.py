import json
import multiprocessing
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


def test_a_database_predating_the_card_columns_is_upgraded_in_place(tmp_path, monkeypatch):
    """`metadata.create_all` leaves an existing table alone, so a database
    created before `blocks`/`schema_version` existed would keep its old column
    set and fail every read. Adding them on connect is what keeps a database
    written by the previous revision usable.

    This runs against whichever backend the suite is pointed at. That matters:
    the ADD COLUMN is rendered per dialect, so the Postgres form (JSONB, and a
    NOT NULL default applied to existing rows) is only actually exercised when
    TEST_DATABASE_URL is set.
    """
    from datetime import datetime, timezone

    from sqlalchemy import Column, MetaData, Table, create_engine, inspect

    from storage_db import get_engine, reset_engine_for_tests, timeline_items

    url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'old.db'}"

    # The table exactly as the previous revision defined it: every current
    # column except the two this change adds. Copying the real Column objects
    # keeps the DDL dialect-correct instead of stringly-typed.
    legacy_meta = MetaData()
    Table(
        timeline_items.name,
        legacy_meta,
        *[
            Column(c.name, c.type, primary_key=c.primary_key, nullable=c.nullable)
            for c in timeline_items.columns
            if c.name not in ("blocks", "schema_version")
        ],
    )

    bootstrap = create_engine(normalize_database_url(url), future=True)
    legacy_meta.drop_all(bootstrap)
    legacy_meta.create_all(bootstrap)
    with bootstrap.begin() as conn:
        conn.execute(
            legacy_meta.tables[timeline_items.name].insert().values(
                id="legacy-1",
                user_id="default",
                title="Old card",
                body="BUY 10 $TSLA",
                status="unread",
                posted_by="tradedesk",
                actions=["Approve"],
                metadata={},
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=None,
            )
        )
    bootstrap.dispose()

    monkeypatch.setenv("DATABASE_URL", url)
    reset_engine_for_tests()

    columns = {c["name"] for c in inspect(get_engine()).get_columns(timeline_items.name)}
    assert {"blocks", "schema_version"} <= columns

    # The row written before the columns existed still reads, and upgrades to
    # typed content rather than erroring on the newly added NOT NULL columns.
    item = timeline_store.get_item("legacy-1")
    assert item is not None
    assert item["blocks"] == [{"type": "text", "label": None, "text": "BUY 10 $TSLA"}]
    assert [a["id"] for a in item["actions"]] == ["approve"]

    reset_engine_for_tests()


def _make_legacy_table(url):
    """The timeline_items table as the revision before blocks/schema_version
    defined it."""
    from sqlalchemy import Column, MetaData, Table, create_engine

    from storage_db import normalize_database_url, timeline_items

    engine = create_engine(normalize_database_url(url), future=True)
    legacy = MetaData()
    Table(
        timeline_items.name,
        legacy,
        *[
            Column(c.name, c.type, primary_key=c.primary_key, nullable=c.nullable)
            for c in timeline_items.columns
            if c.name not in ("blocks", "schema_version")
        ],
    )
    legacy.drop_all(engine)
    legacy.create_all(engine)
    engine.dispose()
    return engine


def test_concurrent_startups_do_not_collide_on_the_column_upgrade(tmp_path, monkeypatch):
    """All four services boot at once against one database.

    The reflection in _add_missing_columns is not a lock, so several callers
    can decide a column is missing before any of them adds it. Whoever loses
    that race must not crash -- the column being there is the goal, and it does
    not matter who created it.
    """
    from sqlalchemy import create_engine, inspect

    from storage_db import _add_missing_columns, normalize_database_url, timeline_items

    url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'race.db'}"
    _make_legacy_table(url)

    # A separate engine per worker, so each reflects the schema independently
    # -- a shared engine would not reproduce the race.
    workers = 4
    engines = [create_engine(normalize_database_url(url), future=True) for _ in range(workers)]
    barrier = threading.Barrier(workers)
    errors: List[BaseException] = []

    def boot(engine):
        try:
            barrier.wait(timeout=30)
            _add_missing_columns(engine)
        except BaseException as exc:  # noqa: BLE001 - re-raised via `errors`
            errors.append(exc)

    threads = [threading.Thread(target=boot, args=(e,)) for e in engines]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)

    assert errors == [], f"a concurrent startup failed: {errors[0]!r}"

    columns = {c["name"] for c in inspect(engines[0]).get_columns(timeline_items.name)}
    assert {"blocks", "schema_version"} <= columns
    for engine in engines:
        engine.dispose()


def test_a_real_migration_failure_is_not_swallowed():
    """The duplicate-column tolerance must not hide a genuinely broken ALTER."""
    from sqlalchemy.exc import DBAPIError

    from storage_db import _is_duplicate_column

    duplicate = DBAPIError("stmt", {}, Exception('column "blocks" already exists'))
    sqlite_duplicate = DBAPIError("stmt", {}, Exception("duplicate column name: blocks"))
    unrelated = DBAPIError("stmt", {}, Exception("permission denied for table timeline_items"))

    assert _is_duplicate_column(duplicate) is True
    assert _is_duplicate_column(sqlite_duplicate) is True
    assert _is_duplicate_column(unrelated) is False


def _boot_one_service(url, queue):
    """A whole service starting: fresh interpreter, its own engine, its own
    module state. Must run in a separate *process* -- threads share
    `_ENGINE_LOCK`, `_SEED_LOCK` and the cached engine, which serializes
    exactly the steps whose cross-process race this is testing.
    """
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ["DATABASE_URL"] = url
    try:
        import a2a_store
        import storage_db

        storage_db.reset_engine_for_tests()
        storage_db.get_engine()          # create_all
        a2a_store.list_agents()          # seeds DEFAULT_AGENTS
        queue.put(None)
    except BaseException as exc:  # noqa: BLE001 - reported via the queue
        queue.put(f"{type(exc).__name__}: {str(exc)[:200]}")


def test_a_first_deploy_boots_every_service_against_an_empty_database(tmp_path, monkeypatch):
    """The first deploy: empty database, all four services starting at once.

    Two reflect-then-write races meet here. `create_all` checks which tables
    exist before creating them, and the DEFAULT_AGENTS seed checks which agents
    exist before inserting them -- neither check is a lock, and on Postgres
    (READ COMMITTED) both can be stale by the time the write lands. SQLite
    hides this because its writers serialize, so it only bites on the
    production backend.
    """
    from storage_db import get_engine, reset_engine_for_tests

    url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'fresh.db'}"
    monkeypatch.setenv("DATABASE_URL", url)

    # Start from genuinely nothing, the way a newly provisioned database is.
    reset_engine_for_tests()
    metadata.drop_all(get_engine())
    reset_engine_for_tests()

    workers = 4
    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    procs = [ctx.Process(target=_boot_one_service, args=(url, queue)) for _ in range(workers)]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=120)

    failures = [msg for msg in (queue.get(timeout=30) for _ in range(workers)) if msg]
    assert failures == [], f"{len(failures)}/{workers} services failed to boot: {failures[0]}"

    reset_engine_for_tests()
    ids = [agent["id"] for agent in a2a_store.list_agents()]
    assert len(ids) == len(set(ids)), f"an agent was seeded twice: {ids}"
    reset_engine_for_tests()
