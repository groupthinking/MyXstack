import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

A2A_STORE_PATH = Path(os.getenv("A2A_STORE_PATH", "~/.xmcp/a2a_store.json")).expanduser()
A2A_STORE_LOCK = threading.Lock()

DEFAULT_AGENTS = [
    {
        "id": "mcp-orchestrator",
        "name": "MCP Orchestrator",
        "description": "Dispatches timeline actions to MCP-enabled tools.",
        "status": "online",
        "endpoint": "local",
        "tags": ["mcp", "orchestrator"],
    },
    {
        "id": "x-agent",
        "name": "X Agent",
        "description": "Handles @mentions and X actions.",
        "status": "online",
        "endpoint": "x",
        "tags": ["x", "social"],
    },
    {
        "id": "timeline-ui",
        "name": "Timeline UI",
        "description": "Flokk timeline surface.",
        "status": "online",
        "endpoint": "flokk",
        "tags": ["ui", "timeline"],
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_store() -> None:
    if A2A_STORE_PATH.exists():
        return
    A2A_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"agents": DEFAULT_AGENTS, "messages": []}
    A2A_STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_store() -> Dict[str, Any]:
    _ensure_store()
    raw = A2A_STORE_PATH.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"agents": DEFAULT_AGENTS, "messages": []}
    if "agents" not in data or not isinstance(data["agents"], list):
        data["agents"] = DEFAULT_AGENTS
    if "messages" not in data or not isinstance(data["messages"], list):
        data["messages"] = []
    return data


def _write_store(data: Dict[str, Any]) -> None:
    A2A_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    A2A_STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_agents() -> List[Dict[str, Any]]:
    with A2A_STORE_LOCK:
        return _read_store()["agents"]


def get_agent(agent_id: str) -> Optional[Dict[str, Any]]:
    with A2A_STORE_LOCK:
        for agent in _read_store()["agents"]:
            if agent.get("id") == agent_id:
                return agent
    return None


def register_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    agent = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "name": payload.get("name", "Agent"),
        "description": payload.get("description", ""),
        "status": payload.get("status", "offline"),
        "endpoint": payload.get("endpoint", ""),
        "tags": payload.get("tags", []),
        "created_at": _utc_now(),
    }
    with A2A_STORE_LOCK:
        data = _read_store()
        if any(existing.get("id") == agent["id"] for existing in data["agents"]):
            return agent
        data["agents"].append(agent)
        _write_store(data)
    return agent


def list_messages(agent_id: str) -> List[Dict[str, Any]]:
    with A2A_STORE_LOCK:
        data = _read_store()
        return [msg for msg in data["messages"] if msg.get("to") == agent_id]


def add_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    message = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "from": payload.get("from", "system"),
        "to": payload.get("to", "timeline-ui"),
        "type": payload.get("type", "info"),
        "content": payload.get("content", ""),
        "metadata": payload.get("metadata", {}),
        "created_at": _utc_now(),
    }
    with A2A_STORE_LOCK:
        data = _read_store()
        data["messages"].insert(0, message)
        _write_store(data)
    return message
