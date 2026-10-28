"""Use the repository's real schema, including PostgreSQL in the existing CI job."""
import os
import uuid
from dataclasses import replace

import pytest
from sqlalchemy import create_engine, delete, insert, text
from sqlalchemy.exc import DBAPIError

import test_timeline_mcp as fixtures
from storage_db import normalize_database_url, timeline_items, utc_now
from timeline_mcp import ItemNotFound, TimelineReader

settings = fixtures.settings


def test_existing_schema_ownership_and_database_write_protection(settings):
    # Only the explicit TEST_DATABASE_URL is used, never deployment DATABASE_URL.
    raw_url = os.getenv("TEST_DATABASE_URL") or settings.database_url
    writer = create_engine(normalize_database_url(raw_url))
    suffix = uuid.uuid4().hex
    own_id, foreign_id = f"own-{suffix}", f"other-{suffix}"
    own_user, foreign_user = f"user-{suffix}", f"foreign-{suffix}"
    ids = [own_id, foreign_id]
    instance = None
    try:
        timeline_items.create(writer, checkfirst=True)
        with writer.begin() as conn:
            for item_id, owner in [(own_id, own_user), (foreign_id, foreign_user)]:
                conn.execute(insert(timeline_items).values(
                    id=item_id, user_id=owner, title="Schema integration card",
                    body="Only account-owned data", status="unread", posted_by="test",
                    actions=[{"id": "approve", "label": "Approve"}],
                    metadata={"api_token": "MUST_NOT_LEAK"}, blocks=[],
                    schema_version="test", dispatched_action="", created_at=utc_now(),
                ))
        instance = TimelineReader(replace(settings, database_url=raw_url))
        assert [item["id"] for item in instance.list_items(own_user)["items"]] == [own_id]
        own = instance.get_item(own_user, own_id)
        assert own["body"] == "Only account-owned data"
        assert own["action_dispatched"] is False
        assert not {"metadata", "actions", "blocks"} & own.keys()
        with pytest.raises(ItemNotFound):
            instance.get_item(own_user, foreign_id)
        with instance.engine.connect() as conn:
            with pytest.raises(DBAPIError):
                conn.execute(text("DELETE FROM timeline_items WHERE id=:id"), {"id": own_id})
        assert instance.get_item(own_user, own_id) == own
    finally:
        if instance is not None:
            instance.close()
        with writer.begin() as conn:
            conn.execute(delete(timeline_items).where(timeline_items.c.id.in_(ids)))
        writer.dispose()
