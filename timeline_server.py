import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from a2a_store import add_message, get_agent, list_agents, list_messages, register_agent
from timeline_store import add_item, delete_item, get_item, list_items, update_item

app = FastAPI(title="xMCP Timeline Service")


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


class TimelineItemCreate(BaseModel):
    user_id: str = "default"
    title: str
    body: str = ""
    status: str = "unread"
    posted_by: str = "agent"
    actions: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimelineItemUpdate(BaseModel):
    status: Optional[str] = None
    action: Optional[str] = None
    posted_by: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    actions: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentCreate(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = ""
    status: Optional[str] = "offline"
    endpoint: Optional[str] = ""
    tags: List[str] = Field(default_factory=list)


class A2AMessageCreate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    from_agent: str = Field(alias="from")
    to: str
    type: str = "info"
    content: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


@app.get("/v1/timeline/users/{user_id}/items")
def get_items(user_id: str, status: Optional[str] = None) -> Dict[str, Any]:
    items = list_items(user_id, status)
    return {"items": items, "count": len(items)}


@app.get("/v1/timeline/items/{item_id}")
def get_item_by_id(item_id: str) -> Dict[str, Any]:
    item = get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/v1/timeline/items")
def create_item(payload: TimelineItemCreate) -> Dict[str, Any]:
    item = add_item(payload.model_dump())
    return item


@app.patch("/v1/timeline/items/{item_id}")
def patch_item(item_id: str, updates: TimelineItemUpdate) -> Dict[str, Any]:
    data = updates.model_dump(exclude_unset=True)
    if updates.action and not updates.status:
        data["status"] = updates.action.lower()
    item = update_item(item_id, data)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if updates.action:
        _dispatch_action(item, updates.action)
    return item


@app.delete("/v1/timeline/items/{item_id}")
def remove_item(item_id: str) -> Dict[str, Any]:
    deleted = delete_item(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"deleted": True, "id": item_id}


@app.get("/v1/a2a/agents")
def get_agents() -> Dict[str, Any]:
    agents = list_agents()
    return {"agents": agents, "count": len(agents)}


@app.get("/v1/a2a/agents/{agent_id}")
def get_agent_by_id(agent_id: str) -> Dict[str, Any]:
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.post("/v1/a2a/agents")
def create_agent(payload: AgentCreate) -> Dict[str, Any]:
    agent = register_agent(payload.model_dump(exclude_unset=True))
    return agent


@app.get("/v1/a2a/agents/{agent_id}/messages")
def get_agent_messages(agent_id: str) -> Dict[str, Any]:
    messages = list_messages(agent_id)
    return {"messages": messages, "count": len(messages)}


@app.post("/v1/a2a/messages")
def create_message(payload: A2AMessageCreate) -> Dict[str, Any]:
    message = add_message(payload.model_dump(by_alias=True))
    return message


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
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
