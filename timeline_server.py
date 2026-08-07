import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from a2a_store import add_message, get_agent, list_agents, list_messages, register_agent
from cards import Block, CardAction, resolve_action
from timeline_store import add_item, delete_item, get_item, list_items, update_item

app = FastAPI(title="xMCP Timeline Service")

UI_DIR = Path(__file__).resolve().parent / "ui"


def _cors_origins() -> List[str]:
    raw = os.getenv("TIMELINE_CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


# The bundled UI is served by this same app, so cross-origin access is only
# needed when a surface is hosted separately. Default to allowing none.
_origins = _cors_origins()
if _origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def require_token(authorization: Optional[str] = Header(None)) -> None:
    """Guard every /v1 route with a shared bearer token.

    Read from the environment per request rather than at import time so
    tests (and a restarted process) see the current value.

    When TIMELINE_API_TOKEN is unset the API stays open, which keeps local
    `make run` working — but this endpoint set includes the approval PATCH
    that authorizes agent actions, so an exposed deployment must set it.
    `main()` warns loudly when it is missing."""
    expected = os.getenv("TIMELINE_API_TOKEN", "").strip()
    if not expected:
        return
    presented = authorization or ""
    if not secrets.compare_digest(presented, f"Bearer {expected}"):
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token")


# /health deliberately stays outside this router: container and load-balancer
# probes must not need a credential.
v1 = APIRouter(prefix="/v1", dependencies=[Depends(require_token)])


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


class TimelineItemCreate(BaseModel):
    user_id: str = "default"
    title: str
    body: str = ""
    # Typed content. `body` is derived from these when it isn't supplied,
    # so older readers keep working either way.
    blocks: List[Block] = Field(default_factory=list)
    status: str = "unread"
    posted_by: str = "agent"
    # Accepts legacy ["Approve", "Reject"] as well as typed actions.
    actions: List[Union[str, CardAction]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimelineItemUpdate(BaseModel):
    status: Optional[str] = None
    # The human-readable action label. Team members match on this, so it
    # stays the value that reaches the dispatcher.
    action: Optional[str] = None
    # The machine id a surface posts; resolved to `action` server-side.
    action_id: Optional[str] = None
    posted_by: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    blocks: Optional[List[Block]] = None
    actions: Optional[List[Union[str, CardAction]]] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentCreate(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = ""
    status: Optional[str] = "offline"
    endpoint: Optional[str] = ""
    # "agent" (interactive, LLM-backed) or "bot" (deterministic executor).
    # Not Optional: an explicit null must be rejected, not persisted.
    kind: Literal["agent", "bot"] = "agent"
    tags: List[str] = Field(default_factory=list)


class A2AMessageCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_agent: str = Field(alias="from")
    to: str
    type: str = "info"
    content: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


@v1.get("/timeline/users/{user_id}/items")
def get_items(user_id: str, status: Optional[str] = None) -> Dict[str, Any]:
    items = list_items(user_id, status)
    return {"items": items, "count": len(items)}


@v1.get("/timeline/items/{item_id}")
def get_item_by_id(item_id: str) -> Dict[str, Any]:
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@v1.post("/timeline/items")
def create_item(payload: TimelineItemCreate) -> Dict[str, Any]:
    item = add_item(payload.model_dump())
    return item


@v1.patch("/timeline/items/{item_id}")
def patch_item(item_id: str, updates: TimelineItemUpdate) -> Dict[str, Any]:
    data = updates.model_dump(exclude_unset=True)
    action = updates.action

    if updates.action_id and not action:
        current = get_item(item_id)
        if not current:
            raise HTTPException(status_code=404, detail="Item not found")
        action = resolve_action(current, updates.action_id)
        # Fail closed: a surface must not be able to trigger an action the
        # card never offered.
        if not action:
            raise HTTPException(
                status_code=400,
                detail=f"Card has no action '{updates.action_id}'",
            )
        data["action"] = action

    if action and not updates.status:
        data["status"] = action.lower()

    item = update_item(item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if action:
        _dispatch_action(item, action)
    return item


@v1.delete("/timeline/items/{item_id}")
def remove_item(item_id: str) -> Dict[str, Any]:
    deleted = delete_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"deleted": True, "id": item_id}


@v1.get("/a2a/agents")
def get_agents() -> Dict[str, Any]:
    agents = list_agents()
    return {"agents": agents, "count": len(agents)}


@v1.get("/a2a/agents/{agent_id}")
def get_agent_by_id(agent_id: str) -> Dict[str, Any]:
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@v1.post("/a2a/agents")
def create_agent(payload: AgentCreate) -> Dict[str, Any]:
    agent = register_agent(payload.model_dump(exclude_unset=True))
    return agent


@v1.get("/a2a/agents/{agent_id}/messages")
def get_agent_messages(agent_id: str) -> Dict[str, Any]:
    messages = list_messages(agent_id)
    return {"messages": messages, "count": len(messages)}


@v1.post("/a2a/messages")
def create_message(payload: A2AMessageCreate) -> Dict[str, Any]:
    message = add_message(payload.model_dump(by_alias=True))
    return message


app.include_router(v1)

# Mounted last so it can never shadow an API route.
if UI_DIR.is_dir():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")


def _dispatch_action(item: Dict[str, Any], action: str) -> None:
    target_agent = os.getenv("TIMELINE_ACTION_AGENT", "mcp-orchestrator")
    add_message(
        {
            "from": "timeline-ui",
            "to": target_agent,
            "type": "timeline_action",
            "content": f"{action} on {item.get('title')}",
            "metadata": {
                "timeline_item_id": item.get("id"),
                "action": action,
                "status": item.get("status"),
            },
        }
    )


def main() -> None:
    host = os.getenv("TIMELINE_HOST", "0.0.0.0")
    port_value = os.getenv("PORT") or os.getenv("TIMELINE_PORT", "8080")
    port = int(port_value)
    if not os.getenv("TIMELINE_API_TOKEN", "").strip():
        print(
            "WARNING: TIMELINE_API_TOKEN is not set — the timeline and A2A API "
            "are unauthenticated. Anyone who can reach this port can approve "
            "agent actions. Set it before exposing this service.",
            flush=True,
        )
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
