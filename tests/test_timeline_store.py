"""Card-level guarantees of the timeline store, against the SQL backend.

Storage mechanics (engine setup, concurrency, URL normalization) live in
tests/test_sql_storage.py. What matters here is that typed card content
survives a round trip and that a record written before typed cards existed is
still readable.
"""

import os
from datetime import datetime, timezone

import pytest

import timeline_store
from storage_db import get_engine, metadata, reset_engine_for_tests, timeline_items


@pytest.fixture()
def store(tmp_path, monkeypatch):
    url = os.getenv("TEST_DATABASE_URL") or f"sqlite:///{tmp_path / 'xmcp.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    reset_engine_for_tests()

    engine = get_engine()
    metadata.drop_all(engine)
    metadata.create_all(engine)

    yield timeline_store
    reset_engine_for_tests()


def test_typed_blocks_survive_a_round_trip(store):
    blocks = [{"type": "facts", "label": "Order", "facts": [{"key": "Side", "value": "BUY"}]}]
    item = store.add_item({"title": "Trade proposal", "blocks": blocks})

    fetched = store.get_item(item["id"])
    assert fetched["blocks"] == blocks
    # The text form is derived so a reader that predates blocks still works.
    assert "Side: BUY" in fetched["body"]


def test_legacy_records_are_upgraded_on_read(store):
    # A row as the JSON->SQL migration would leave it: a body, string actions,
    # and no blocks at all.
    with get_engine().begin() as conn:
        conn.execute(
            timeline_items.insert().values(
                id="old-1",
                user_id="default",
                title="Legacy card",
                body="BUY 10 $TSLA",
                blocks=[],
                schema_version="",
                status="unread",
                posted_by="tradedesk",
                actions=["Approve", "Reject"],
                metadata={"agent_id": "tradedesk"},
                created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                updated_at=None,
            )
        )

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


def test_an_explicit_body_wins_over_the_derived_one(store):
    item = store.add_item(
        {"title": "t", "body": "explicit", "blocks": [{"type": "text", "text": "derived"}]}
    )
    assert item["body"] == "explicit"

    updated = store.update_item(
        item["id"], {"body": "still explicit", "blocks": [{"type": "text", "text": "new"}]}
    )
    assert updated["body"] == "still explicit"


def test_string_actions_are_normalized_on_write(store):
    item = store.add_item({"title": "t", "body": "b", "actions": ["Approve Purchase"]})
    assert item["actions"] == [
        {"id": "approve-purchase", "label": "Approve Purchase", "style": "neutral", "confirm": None}
    ]


def test_metadata_updates_merge_rather_than_replace(store):
    item = store.add_item({"title": "t", "body": "b", "metadata": {"agent_id": "tradedesk"}})
    updated = store.update_item(item["id"], {"metadata": {"processed_action": "Approve"}})
    assert updated["metadata"]["agent_id"] == "tradedesk"
    assert updated["metadata"]["processed_action"] == "Approve"
