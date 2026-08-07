import threading
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import insert, select, update

from storage_db import (
    a2a_agents,
    a2a_messages,
    get_engine,
    row_to_dict,
    serialize_record,
    utc_now,
    write_connection,
    read_connection,
)

_SEEDED_ENGINE = None
_SEED_LOCK = threading.Lock()

DEFAULT_AGENTS = [
    {
        "id": "mcp-orchestrator",
        "name": "MCP Orchestrator",
        "description": "Dispatches timeline actions to MCP-enabled tools.",
        "status": "online",
        "endpoint": "local",
        "kind": "agent",
        "tags": ["mcp", "orchestrator"],
    },
    {
        "id": "x-agent",
        "name": "X Agent",
        "description": "Handles @mentions and X actions.",
        "status": "online",
        "endpoint": "x",
        "kind": "agent",
        "tags": ["x", "social"],
    },
    {
        "id": "timeline-ui",
        "name": "Timeline UI",
        "description": "Flokk timeline surface.",
        "status": "online",
        "endpoint": "flokk",
        "kind": "agent",
        "tags": ["ui", "timeline"],
    },
]


def _normalize_kind(value: Any) -> str:
    return value if value in ("agent", "bot") else "agent"


def _serialize_agent(record: Dict[str, Any]) -> Dict[str, Any]:
    value = serialize_record(record)
    value["kind"] = _normalize_kind(value.get("kind"))
    return value


def _serialize_message(record: Dict[str, Any]) -> Dict[str, Any]:
    value = serialize_record(record)
    value["from"] = value.pop("from_agent")
    value["to"] = value.pop("to_agent")
    return value


def _ensure_default_agents() -> None:
    # Seeding is idempotent but takes a write transaction (BEGIN IMMEDIATE on
    # SQLite), so it must not run on every read. Track the engine we seeded
    # against rather than a plain bool: reset_engine_for_tests() builds a new
    # engine, and identity comparison makes the next call re-seed it.
    global _SEEDED_ENGINE

    engine = get_engine()
    if _SEEDED_ENGINE is engine:
        return

    with _SEED_LOCK:
        if _SEEDED_ENGINE is engine:
            return

        with write_connection() as conn:
            existing_ids = {
                row[0]
                for row in conn.execute(select(a2a_agents.c.id).where(a2a_agents.c.id.in_([a["id"] for a in DEFAULT_AGENTS])))
            }

            for agent in DEFAULT_AGENTS:
                if agent["id"] in existing_ids:
                    continue
                conn.execute(
                    insert(a2a_agents).values(
                        **agent,
                        created_at=utc_now(),
                    )
                )

        _SEEDED_ENGINE = engine


def list_agents() -> List[Dict[str, Any]]:
    _ensure_default_agents()
    query = select(a2a_agents).order_by(a2a_agents.c.created_at.asc(), a2a_agents.c.id.asc())
    with read_connection() as conn:
        rows = conn.execute(query).fetchall()
    return [_serialize_agent(row_to_dict(row)) for row in rows]


def get_agent(agent_id: str) -> Optional[Dict[str, Any]]:
    _ensure_default_agents()
    query = select(a2a_agents).where(a2a_agents.c.id == agent_id)
    with read_connection() as conn:
        row = conn.execute(query).fetchone()
    if not row:
        return None
    return _serialize_agent(row_to_dict(row))


def register_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    agent = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "name": payload.get("name", "Agent"),
        "description": payload.get("description", ""),
        "status": payload.get("status", "offline"),
        "endpoint": payload.get("endpoint", ""),
        "kind": _normalize_kind(payload.get("kind")),
        "tags": payload.get("tags", []),
    }

    with write_connection() as conn:
        existing = conn.execute(
            select(a2a_agents).where(a2a_agents.c.id == agent["id"])
        ).fetchone()

        if existing:
            conn.execute(
                update(a2a_agents)
                .where(a2a_agents.c.id == agent["id"])
                .values(**agent)
            )
            row = row_to_dict(existing)
            row.update(agent)
            return _serialize_agent(row)

        created = {**agent, "created_at": utc_now()}
        conn.execute(insert(a2a_agents).values(**created))
        return _serialize_agent(created)


def list_messages(agent_id: str) -> List[Dict[str, Any]]:
    query = (
        select(a2a_messages)
        .where(a2a_messages.c.to_agent == agent_id)
        .order_by(a2a_messages.c.created_at.desc())
    )
    with read_connection() as conn:
        rows = conn.execute(query).fetchall()
    return [_serialize_message(row_to_dict(row)) for row in rows]


def add_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    message = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "from_agent": payload.get("from", "system"),
        "to_agent": payload.get("to", "timeline-ui"),
        "type": payload.get("type", "info"),
        "content": payload.get("content", ""),
        "metadata": payload.get("metadata", {}),
        "created_at": utc_now(),
    }
    with write_connection() as conn:
        conn.execute(insert(a2a_messages).values(**message))
    return _serialize_message(message)
