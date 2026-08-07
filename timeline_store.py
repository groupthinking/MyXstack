import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, insert, select, update

from cards import SCHEMA_VERSION, derive_body, normalize_actions, normalize_card
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
    return [normalize_card(serialize_record(row_to_dict(row))) for row in rows]


def get_item(item_id: str) -> Optional[Dict[str, Any]]:
    query = select(timeline_items).where(timeline_items.c.id == item_id)
    with read_connection() as conn:
        row = conn.execute(query).fetchone()
    if not row:
        return None
    return normalize_card(serialize_record(row_to_dict(row)))


def add_item(payload: Dict[str, Any]) -> Dict[str, Any]:
    blocks = payload.get("blocks") or []
    # `body` stays authoritative for every older reader, so derive it from
    # blocks when the caller didn't supply one itself.
    body = payload.get("body") or ""
    if blocks and not body:
        body = derive_body(blocks)

    item = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "user_id": payload.get("user_id", "default"),
        "title": payload.get("title", "Untitled"),
        "body": body,
        "blocks": blocks,
        "schema_version": payload.get("schema_version") or SCHEMA_VERSION,
        # Always present, so a surface can read it uniformly instead of having
        # to treat "missing" and "unclaimed" as the same thing. A new card has
        # dispatched nothing; only claim_action sets this.
        "dispatched_action": "",
        "status": payload.get("status", "unread"),
        "posted_by": payload.get("posted_by", "agent"),
        "actions": normalize_actions(payload.get("actions")),
        "metadata": payload.get("metadata", {}),
        "created_at": utc_now(),
        "updated_at": None,
    }

    with write_connection() as conn:
        conn.execute(insert(timeline_items).values(**item))
    return normalize_card(serialize_record(item))


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
            changed["actions"] = normalize_actions(updates["actions"])

        if "blocks" in updates and isinstance(updates["blocks"], list):
            changed["blocks"] = updates["blocks"]
            # Keep the derived text form in step with the blocks unless the
            # caller overrode `body` in the same update.
            if updates.get("body") is None:
                changed["body"] = derive_body(updates["blocks"])

        changed["updated_at"] = utc_now()
        conn.execute(
            update(timeline_items)
            .where(timeline_items.c.id == item_id)
            .values(**changed)
        )
        current.update(changed)

        return normalize_card(serialize_record(current))


def delete_item(item_id: str) -> bool:
    with write_connection() as conn:
        result = conn.execute(delete(timeline_items).where(timeline_items.c.id == item_id))
        return result.rowcount > 0


def claim_action(item_id: str, action: str) -> bool:
    """Claim this card's one dispatch, atomically. True only for the winner.

    Approval is single-shot: a card carries an action to a member exactly
    once, or a human double-clicking -- or two surfaces, or a retried
    request -- executes the same trade more than once. Validating that the
    card *offers* an action does not give that, because every concurrent
    caller passes the same validation.

    The guarantee comes from the database rather than from a check in the
    handler: a single UPDATE ... WHERE dispatched_action = '' can only
    succeed for one caller, whatever the interleaving, and it holds across
    processes -- which matters because several timeline-server replicas may
    serve the same card.
    """
    with write_connection() as conn:
        result = conn.execute(
            update(timeline_items)
            .where(timeline_items.c.id == item_id)
            .where(timeline_items.c.dispatched_action == "")
            .values(dispatched_action=action, updated_at=utc_now())
        )
        return result.rowcount == 1


def release_action_claim(item_id: str) -> None:
    """Undo a claim whose dispatch never happened.

    Dispatch can fail after the claim is taken (the A2A write throws). Left
    alone, that card would be permanently unapprovable -- terminal without
    anything having run. Releasing keeps a failed approval retryable, which
    is the same rule the dispatcher already follows for failed execution.
    """
    with write_connection() as conn:
        conn.execute(
            update(timeline_items)
            .where(timeline_items.c.id == item_id)
            .values(dispatched_action="")
        )
