#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple

from sqlalchemy import insert, select, update

from cards import normalize_actions
from storage_db import a2a_agents, a2a_messages, timeline_items, write_connection


def _parse_timestamp(value: Any, *, field: str = "created_at") -> datetime:
    """Parse a stored timestamp, or fail.

    Substituting now() for an unparsable value silently reorders the timeline
    and, because the UPDATE path used to write created_at back, moved the
    record forward again on every re-run. A migration that cannot read its
    own input should say so."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"unparsable {field} {value!r}") from exc
    return datetime.now(timezone.utc)


def _read_json(path: Path) -> Dict[str, Any]:
    """Read a JSON store, or fail loudly.

    A corrupt file must not read as "nothing to migrate". This is a one-shot
    move of the only copy of the data: swallowing a decode error here reports
    `inserted=0` under a "Migration complete" banner and exits 0, and the
    operator deletes the JSON store on the strength of that. A truncated or
    partially flushed file is exactly how a JSON store dies."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _upsert_timeline_items(items: Iterable[Dict[str, Any]]) -> Tuple[int, int]:
    inserted = 0
    updated = 0
    with write_connection() as conn:
        for item in items:
            item_id = item.get("id")
            if not item_id:
                continue
            payload = {
                "id": item_id,
                "user_id": item.get("user_id", "default"),
                "title": item.get("title", "Untitled"),
                "body": item.get("body", ""),
                # A JSON store predating typed cards has neither field. Carry
                # across whatever is there and leave the rest empty -- reads
                # upgrade a legacy record from `body` on the way out.
                "blocks": item.get("blocks") or [],
                "schema_version": item.get("schema_version") or "",
                "status": item.get("status", "unread"),
                "posted_by": item.get("posted_by", "agent"),
                "actions": normalize_actions(item.get("actions")),
                "metadata": item.get("metadata", {}),
                "created_at": _parse_timestamp(item.get("created_at")),
                "updated_at": _parse_timestamp(item.get("updated_at")) if item.get("updated_at") else None,
            }
            exists = conn.execute(
                select(timeline_items.c.id).where(timeline_items.c.id == item_id)
            ).fetchone()
            if exists:
                # created_at belongs to the original record; a re-run must not
                # move it.
                conn.execute(
                    update(timeline_items)
                    .where(timeline_items.c.id == item_id)
                    .values(**{k: v for k, v in payload.items() if k != "created_at"})
                )
                updated += 1
            else:
                conn.execute(insert(timeline_items).values(**payload))
                inserted += 1
    return inserted, updated


def _upsert_agents(agents: Iterable[Dict[str, Any]]) -> Tuple[int, int]:
    inserted = 0
    updated = 0
    with write_connection() as conn:
        for agent in agents:
            agent_id = agent.get("id")
            if not agent_id:
                continue
            payload = {
                "id": agent_id,
                "name": agent.get("name", "Agent"),
                "description": agent.get("description", ""),
                "status": agent.get("status", "offline"),
                "endpoint": agent.get("endpoint", ""),
                "kind": agent.get("kind") if agent.get("kind") in ("agent", "bot") else "agent",
                "tags": agent.get("tags", []),
                "created_at": _parse_timestamp(agent.get("created_at")),
            }
            exists = conn.execute(select(a2a_agents.c.id).where(a2a_agents.c.id == agent_id)).fetchone()
            if exists:
                conn.execute(update(a2a_agents).where(a2a_agents.c.id == agent_id).values(**payload))
                updated += 1
            else:
                conn.execute(insert(a2a_agents).values(**payload))
                inserted += 1
    return inserted, updated


def _upsert_messages(messages: Iterable[Dict[str, Any]]) -> Tuple[int, int]:
    inserted = 0
    updated = 0
    with write_connection() as conn:
        for message in messages:
            message_id = message.get("id")
            if not message_id:
                continue
            payload = {
                "id": message_id,
                "from_agent": message.get("from", "system"),
                "to_agent": message.get("to", "timeline-ui"),
                "type": message.get("type", "info"),
                "content": message.get("content", ""),
                "metadata": message.get("metadata", {}),
                "created_at": _parse_timestamp(message.get("created_at")),
            }
            exists = conn.execute(
                select(a2a_messages.c.id).where(a2a_messages.c.id == message_id)
            ).fetchone()
            if exists:
                conn.execute(update(a2a_messages).where(a2a_messages.c.id == message_id).values(**payload))
                updated += 1
            else:
                conn.execute(insert(a2a_messages).values(**payload))
                inserted += 1
    return inserted, updated


def migrate() -> Dict[str, Tuple[int, int]]:
    timeline_path = Path(
        os.getenv("TIMELINE_STORE_PATH", "~/.xmcp/timeline_store.json")
    ).expanduser()
    a2a_path = Path(os.getenv("A2A_STORE_PATH", "~/.xmcp/a2a_store.json")).expanduser()

    timeline_data = _read_json(timeline_path)
    a2a_data = _read_json(a2a_path)

    timeline_result = _upsert_timeline_items(timeline_data.get("items", []))
    agents_result = _upsert_agents(a2a_data.get("agents", []))
    messages_result = _upsert_messages(a2a_data.get("messages", []))

    return {
        "timeline_items": timeline_result,
        "a2a_agents": agents_result,
        "a2a_messages": messages_result,
    }


def main() -> None:
    result = migrate()
    print("Migration complete:")
    for table, (inserted, updated) in result.items():
        print(f"- {table}: inserted={inserted}, updated={updated}")


if __name__ == "__main__":
    main()
