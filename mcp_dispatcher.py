import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import requests
from dotenv import load_dotenv
from xai_sdk import Client
from xai_sdk.chat import user
from xai_sdk.tools import mcp

LAST_SEEN_PATH = Path(os.getenv("XMCP_DISPATCH_LAST_SEEN", "~/.xmcp/dispatch_last_seen.txt")).expanduser()


def load_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def save_last_seen(value: str) -> None:
    LAST_SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_SEEN_PATH.write_text(value, encoding="utf-8")


def load_last_seen() -> Optional[str]:
    if not LAST_SEEN_PATH.exists():
        return None
    return LAST_SEEN_PATH.read_text(encoding="utf-8").strip() or None


def get_messages(agent_id: str) -> list[Dict]:
    timeline_url = os.getenv("TIMELINE_API_URL", "http://127.0.0.1:8080")
    response = requests.get(f"{timeline_url}/v1/a2a/agents/{agent_id}/messages", timeout=10)
    if response.status_code != 200:
        return []
    payload = response.json()
    return payload.get("messages", [])


def send_message(from_agent: str, to: str, content: str, metadata: Dict) -> None:
    timeline_url = os.getenv("TIMELINE_API_URL", "http://127.0.0.1:8080")
    requests.post(
        f"{timeline_url}/v1/a2a/messages",
        json={
            "from": from_agent,
            "to": to,
            "type": "mcp_result",
            "content": content,
            "metadata": metadata,
        },
        timeout=10,
    )


def ensure_agent_registered(agent_id: str) -> None:
    timeline_url = os.getenv("TIMELINE_API_URL", "http://127.0.0.1:8080")
    payload = {
        "id": agent_id,
        "name": "MCP Orchestrator",
        "description": "Dispatches timeline actions to MCP-enabled tools.",
        "status": "online",
        "endpoint": "local",
        "tags": ["mcp", "orchestrator"],
    }
    requests.post(f"{timeline_url}/v1/a2a/agents", json=payload, timeout=10)


def update_timeline_item(item_id: str, metadata: Dict) -> None:
    timeline_url = os.getenv("TIMELINE_API_URL", "http://127.0.0.1:8080")
    requests.patch(
        f"{timeline_url}/v1/timeline/items/{item_id}",
        json={"metadata": metadata},
        timeout=10,
    )


def call_grok(prompt: str) -> str:
    api_key = os.getenv("XAI_API_KEY", "").strip()
    if not api_key:
        return "Missing XAI_API_KEY."
    model = os.getenv("XAI_MODEL", "grok-4-1-fast")
    server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")

    client = Client(api_key=api_key)
    chat = client.chat.create(
        model=model,
        tools=[mcp(server_url=server_url)],
    )
    chat.append(user(prompt))

    response_text = ""
    for _, chunk in chat.stream():
        if chunk.content:
            response_text += chunk.content
    return response_text.strip() or "No response."


def _parse_time(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def main() -> None:
    load_env()
    agent_id = os.getenv("MCP_DISPATCH_AGENT_ID", "mcp-orchestrator")
    last_seen = _parse_time(load_last_seen())
    ensure_agent_registered(agent_id)

    while True:
        messages = get_messages(agent_id)
        for message in messages:
            created_at = _parse_time(message.get("created_at"))
            if last_seen and created_at and created_at <= last_seen:
                continue
            if message.get("type") != "timeline_action":
                continue

            metadata = message.get("metadata", {})
            item_id = metadata.get("timeline_item_id")
            action = metadata.get("action")

            prompt = f"""
You are a workflow agent. A user took the action '{action}' on timeline item {item_id}.
Use MCP tools to execute any required external steps. Return a concise status update.
"""
            result = call_grok(prompt)

            if item_id:
                update_timeline_item(item_id, {"mcp_result": result})

            send_message(
                from_agent=agent_id,
                to=message.get("from", "timeline-ui"),
                content=result,
                metadata={"timeline_item_id": item_id, "action": action},
            )

            last_seen = created_at or datetime.now(timezone.utc)
            save_last_seen(last_seen.isoformat())

        time.sleep(5)


if __name__ == "__main__":
    main()
