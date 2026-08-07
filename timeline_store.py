import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, insert, select, update

from storage_db import (
    merge_json,
    row_to_dict,
    serialize_record,
    timeline_items,
    utc_now,
    write_connection,
    read_connection,
)


def list_items(user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    query = select(timeline_items).where(timeline_items.c.user_id == user_id)
    if status:
        query = query.where(timeline_items.c.status == status)
    query = query.order_by(timeline_items.c.created_at.desc())

    with read_connection() as conn:
        rows = conn.execute(query).fetchall()
    return [serialize_record(row_to_dict(row)) for row in rows]


def get_item(item_id: str) -> Optional[Dict[str, Any]]:
    query = select(timeline_items).where(timeline_items.c.id == item_id)
    with read_connection() as conn:
        row = conn.execute(query).fetchone()
    if not row:
        return None
    return serialize_record(row_to_dict(row))


def add_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    item = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "user_id": payload.get("user_id", "default"),
        "title": payload.get("title", "Untitled"),
        "body": payload.get("body", ""),
        "status": payload.get("status", "unread"),
        "posted_by": payload.get("posted_by", "agent"),
        "actions": payload.get("actions", []),
        "metadata": payload.get("metadata", {}),
        "created_at": utc_now(),
        "updated_at": None,
    }

    with write_connection() as conn:
        conn.execute(insert(timeline_items).values(**item))
    return serialize_record(item)


def update_item(item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with write_connection() as conn:
        # with_for_update() locks the row for the life of the transaction, so the
        # read-merge-write below stays atomic. Without it, Postgres runs this at
        # READ COMMITTED and two callers merging different metadata keys can read
        # the same base dict and clobber each other -- the approval/action path
        # this store backs must not lose updates. SQLite has no row locks and
        # SQLAlchemy renders nothing there; write_connection()'s BEGIN IMMEDIATE
        # already serializes SQLite writers.
        row = conn.execute(
            select(timeline_items).where(timeline_items.c.id == item_id).with_for_update()
        ).fetchone()
        if not row:
            return None

        current = row_to_dict(row)
        changed: Dict[str, Any] = {}

        for key in ["status", "posted_by", "title", "body"]:
            if key in updates and updates[key] is not None:
                changed[key] = updates[key]

        if "metadata" in updates and isinstance(updates["metadata"], dict):
            changed["metadata"] = merge_json(current.get("metadata"), updates["metadata"])

        if "actions" in updates and isinstance(updates["actions"], list):
            changed["actions"] = updates["actions"]

        changed["updated_at"] = utc_now()
        conn.execute(
            update(timeline_items)
            .where(timeline_items.c.id == item_id)
            .values(**changed)
        )
        current.update(changed)

        return serialize_record(current)


def delete_item(item_id: str) -> bool:
    with write_connection() as conn:
        result = conn.execute(delete(timeline_items).where(timeline_items.c.id == item_id))
        return result.rowcount > 0
