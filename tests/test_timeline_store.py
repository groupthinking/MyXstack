"""Storage-level guarantees: cross-process safety and legacy readability."""

import importlib
import json
import multiprocessing
import os

import pytest


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMELINE_STORE_PATH", str(tmp_path / "timeline.json"))
    import timeline_store

    importlib.reload(timeline_store)
    return timeline_store


def _writer(store_path: str, count: int, tag: str) -> None:
    """Runs in a separate process: reload the module so it binds the shared
    store path, then append cards."""
    os.environ["TIMELINE_STORE_PATH"] = store_path
    import timeline_store

    importlib.reload(timeline_store)
    for i in range(count):
        timeline_store.add_item({"title": f"{tag}-{i}", "body": "x"})


def test_concurrent_processes_do_not_lose_items(tmp_path):
    store_path = str(tmp_path / "timeline.json")
    per_writer = 25
    writers = 4

    ctx = multiprocessing.get_context("spawn")
    procs = [
        ctx.Process(target=_writer, args=(store_path, per_writer, f"w{n}"))
        for n in range(writers)
    ]
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join(timeout=60)
        assert proc.exitcode == 0

    data = json.loads(open(store_path, encoding="utf-8").read())
    assert len(data["items"]) == per_writer * writers
    # Every writer's cards survived, not just the last one to win a race.
    titles = {item["title"] for item in data["items"]}
    assert len(titles) == per_writer * writers


def test_legacy_records_on_disk_are_still_readable(store, tmp_path):
    # Simulate a store written before typed cards existed.
    legacy = {
        "items": [
            {
                "id": "old-1",
                "user_id": "default",
                "title": "Legacy card",
                "body": "BUY 10 $TSLA",
                "status": "unread",
                "posted_by": "tradedesk",
                "actions": ["Approve", "Reject"],
                "metadata": {"agent_id": "tradedesk"},
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": None,
            }
        ]
    }
    (tmp_path / "timeline.json").write_text(json.dumps(legacy), encoding="utf-8")

    item = store.get_item("old-1")
    assert item["blocks"] == [{"type": "text", "label": None, "text": "BUY 10 $TSLA"}]
    assert [a["label"] for a in item["actions"]] == ["Approve", "Reject"]
    assert [a["id"] for a in item["actions"]] == ["approve", "reject"]

    listed = store.list_items("default")
    assert len(listed) == 1
    assert listed[0]["blocks"][0]["text"] == "BUY 10 $TSLA"


def test_updating_blocks_keeps_the_derived_body_in_step(store):
    item = store.add_item({"title": "t", "blocks": [{"type": "text", "text": "before"}]})
    assert item["body"] == "before"

    updated = store.update_item(item["id"], {"blocks": [{"type": "text", "text": "after"}]})
    assert updated["body"] == "after"


def test_metadata_updates_merge_rather_than_replace(store):
    item = store.add_item({"title": "t", "body": "b", "metadata": {"agent_id": "tradedesk"}})
    updated = store.update_item(item["id"], {"metadata": {"processed_action": "Approve"}})
    assert updated["metadata"]["agent_id"] == "tradedesk"
    assert updated["metadata"]["processed_action"] == "Approve"
