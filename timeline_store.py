import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cards import SCHEMA_VERSION, derive_body, normalize_actions, normalize_card
from store_lock import file_lock

STORE_PATH = Path(os.getenv("TIMELINE_STORE_PATH", "~/.xmcp/timeline_store.json")).expanduser()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_store() -> None:
    if STORE_PATH.exists():
        return
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps({"items": []}, indent=2), encoding="utf-8")


def _read_store() -> Dict[str, Any]:
    _ensure_store()
    raw = STORE_PATH.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"items": []}
    if "items" not in data or not isinstance(data["items"], list):
        data["items"] = []
    return data


def _write_store(data: Dict[str, Any]) -> None:
    """Atomic replace so a mid-write crash can't truncate the timeline."""
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE_PATH.with_suffix(STORE_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, STORE_PATH)


def list_items(user_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    with file_lock(STORE_PATH):
        data = _read_store()
        items = [item for item in data["items"] if item.get("user_id") == user_id]
        if status:
            items = [item for item in items if item.get("status") == status]
        return [normalize_card(item) for item in items]


def get_item(item_id: str) -> Optional[Dict[str, Any]]:
    with file_lock(STORE_PATH):
        data = _read_store()
        for item in data["items"]:
            if item.get("id") == item_id:
                return normalize_card(item)
    return None


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
        "status": payload.get("status", "unread"),
        "posted_by": payload.get("posted_by", "agent"),
        "actions": normalize_actions(payload.get("actions")),
        "metadata": payload.get("metadata", {}),
        "created_at": _utc_now(),
        "updated_at": None,
    }

    with file_lock(STORE_PATH):
        data = _read_store()
        data["items"].insert(0, item)
        _write_store(data)
    return normalize_card(item)


def update_item(item_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with file_lock(STORE_PATH):
        data = _read_store()
        for item in data["items"]:
            if item.get("id") != item_id:
                continue
            for key in ["status", "posted_by", "title", "body"]:
                if key in updates and updates[key] is not None:
                    item[key] = updates[key]
            if "metadata" in updates and isinstance(updates["metadata"], dict):
                item["metadata"] = {**item.get("metadata", {}), **updates["metadata"]}
            if "actions" in updates and isinstance(updates["actions"], list):
                item["actions"] = normalize_actions(updates["actions"])
            if "blocks" in updates and isinstance(updates["blocks"], list):
                item["blocks"] = updates["blocks"]
                # Keep the derived text form in step with the blocks unless
                # the caller overrode `body` in the same update.
                if "body" not in updates or updates["body"] is None:
                    item["body"] = derive_body(updates["blocks"])
            item["updated_at"] = _utc_now()
            _write_store(data)
            return normalize_card(item)
    return None


def delete_item(item_id: str) -> bool:
    with file_lock(STORE_PATH):
        data = _read_store()
        original = len(data["items"])
        data["items"] = [item for item in data["items"] if item.get("id") != item_id]
        if len(data["items"]) == original:
            return False
        _write_store(data)
        return True
