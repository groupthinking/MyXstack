import os
import secrets
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from a2a_store import add_message, get_agent, list_agents, list_messages, register_agent
from cards import Block, CardAction, DuplicateActionIdError, normalize_actions, resolve_action
from timeline_store import (
    add_item,
    claim_action,
    delete_item,
    get_item,
    list_items,
    release_action_claim,
    update_item,
)

app = FastAPI(title="xMCP Timeline Service")

UI_DIR = Path(__file__).resolve().parent / "ui"


def _cors_origins() -> List[str]:
    raw = os.getenv("TIMELINE_CORS_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


# The bundled UI is served by this same app, so cross-origin access is only
# needed when a surface is hosted separately. Default to allowing none.
_origins = _cors_origins()
if _origins:
    # No allow_credentials: this API authenticates with a bearer header, not
    # cookies, so enabling credentialed CORS would widen exposure for nothing.
    # Methods and headers are enumerated rather than wildcarded.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )


# Environment variables that indicate this process is a deployment rather
# than someone's laptop. On a deployment an empty token is fatal, not a
# warning — this API includes the PATCH that authorizes agent actions.
_DEPLOY_MARKERS = ("RAILWAY_SERVICE_NAME", "RAILWAY_ENVIRONMENT", "KUBERNETES_SERVICE_HOST")


def _is_deployment() -> bool:
    return any(os.getenv(marker, "").strip() for marker in _DEPLOY_MARKERS)


def enforce_token_policy() -> None:
    """Refuse to serve approval routes anonymously on a deployment.

    Called at import time so it applies to *every* entrypoint — including
    `uvicorn main:app`, which imports `timeline_server.app` directly and
    never runs `main()`. Putting this check only in `main()` would leave
    the Railway path (main.py: `from timeline_server import app`) silently
    unauthenticated, which is the one deployment that most needs it.

    Local development stays frictionless: with no deployment marker set,
    an empty token only warns. `TIMELINE_ALLOW_INSECURE=1` is the explicit
    escape hatch for deliberately running a deployment open."""
    if os.getenv("TIMELINE_API_TOKEN", "").strip():
        return

    if _is_deployment() and os.getenv("TIMELINE_ALLOW_INSECURE", "").strip() != "1":
        raise RuntimeError(
            "TIMELINE_API_TOKEN is not set but this looks like a deployment "
            f"({', '.join(m for m in _DEPLOY_MARKERS if os.getenv(m, '').strip())}). "
            "The /v1 approval endpoints authorize agent actions and would be "
            "reachable anonymously. Set TIMELINE_API_TOKEN, or set "
            "TIMELINE_ALLOW_INSECURE=1 to override deliberately."
        )

    print(
        "WARNING: TIMELINE_API_TOKEN is not set — the timeline and A2A API "
        "are unauthenticated. Anyone who can reach this port can approve "
        "agent actions. Set it before exposing this service.",
        flush=True,
    )


def require_token(authorization: Optional[str] = Header(None)) -> None:
    """Guard every /v1 route with a shared bearer token.

    Read from the environment per request rather than at import time so
    tests (and a restarted process) see the current value.

    When TIMELINE_API_TOKEN is unset the API stays open for local use;
    `enforce_token_policy()` makes that state fatal on a deployment."""
    expected = os.getenv("TIMELINE_API_TOKEN", "").strip()
    if not expected:
        return
    presented = authorization or ""
    if not secrets.compare_digest(presented, f"Bearer {expected}"):
        raise HTTPException(status_code=401, detail="Missing or invalid bearer token")


enforce_token_policy()


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
    data = payload.model_dump()
    # Reject duplicate action ids before the card is stored: once persisted,
    # resolve_action would silently pick the first match and the later button
    # would be unreachable.
    try:
        normalize_actions(data.get("actions"), strict=True)
    except DuplicateActionIdError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return add_item(data)


@v1.patch("/timeline/items/{item_id}")
def patch_item(item_id: str, updates: TimelineItemUpdate) -> Dict[str, Any]:
    data = updates.model_dump(exclude_unset=True)
    action = updates.action

    # Every dispatched action must be one the card actually offers — on BOTH
    # paths. Validating only `action_id` would leave the legacy `action` label
    # path able to dispatch anything, which is worse than no guard at all
    # because the tests would make the endpoint look closed.
    if updates.action_id or action:
        current = get_item(item_id)
        if not current:
            raise HTTPException(status_code=404, detail="Item not found")

        if updates.action_id:
            resolved = resolve_action(current, updates.action_id)
            if not resolved:
                raise HTTPException(
                    status_code=400,
                    detail=f"Card has no action '{updates.action_id}'",
                )
            # A caller may send both; they must agree, or we cannot know
            # which one the human actually chose.
            if action and action != resolved:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"action '{action}' does not match action_id "
                        f"'{updates.action_id}' (which resolves to '{resolved}')"
                    ),
                )
            action = resolved
        else:
            offered = {a.get("label") for a in current.get("actions") or []}
            if action not in offered:
                raise HTTPException(
                    status_code=400,
                    detail=f"Card does not offer action '{action}'",
                )

        data["action"] = action

        # Claim before anything is written or dispatched. Validating that the
        # card offers the action does not make approval single-shot -- every
        # concurrent caller passes that same check -- so without this a
        # double-click, two surfaces, or a retried request each dispatch the
        # action again, and the member executes the trade once per request.
        if not claim_action(item_id, action):
            current = get_item(item_id) or {}
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Card already dispatched "
                    f"'{current.get('dispatched_action') or 'an action'}'"
                ),
            )

    if action and not updates.status:
        data["status"] = action.lower()

    item = update_item(item_id, data)
    if not item:
        if action:
            release_action_claim(item_id)
        raise HTTPException(status_code=404, detail="Item not found")
    if action:
        try:
            _dispatch_action(item, action)
        except Exception:
            # The claim exists to stop a second dispatch, not to make a card
            # that never dispatched permanently unapprovable.
            release_action_claim(item_id)
            raise
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
    # The token policy is enforced at import time (see enforce_token_policy),
    # so it has already run for every entrypoint by the time we get here.
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
