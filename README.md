# MyXstack

This repository hosts a lightweight, step-by-step guide and runnable backend for an autonomous X (Twitter) agent system that reasons over thread context via Grok through xMCP.

## Services
- **mcp-server**: X API MCP server (`server.py`)
- **timeline-server**: Timeline + A2A API (`timeline_server.py`)
- **x-listener**: Watches mentions, responds, and pushes timeline cards (`listener.py`)
- **mcp-dispatcher**: Executes timeline actions via MCP (`mcp_dispatcher.py`)

## Local Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
```

Run services in separate terminals:
```bash
python server.py
python timeline_server.py
python listener.py
python mcp_dispatcher.py
```

## Railway Deployment (Monorepo)
Create four Railway services from this repo and set start commands:
- `python server.py`
- `python timeline_server.py`
- `python listener.py`
- `python mcp_dispatcher.py`

Set service env vars from `env.example`, then wire cross-service URLs:
- `MCP_SERVER_URL=https://<mcp-server-domain>/mcp`
- `TIMELINE_API_URL=https://<timeline-server-domain>`

## API Surface
Timeline:
- `GET /v1/timeline/users/{user_id}/items`
- `POST /v1/timeline/items`
- `PATCH /v1/timeline/items/{id}`
- `DELETE /v1/timeline/items/{id}`

A2A:
- `GET /v1/a2a/agents`
- `POST /v1/a2a/agents`
- `GET /v1/a2a/agents/{id}/messages`
- `POST /v1/a2a/messages`

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](/CONTRIBUTING.md) for guidelines on:
- PR title format (conventional commits)
- Code style and conventions
- Testing requirements
- How to submit pull requests

For quick reference on PR titles, see [.github/PR_TITLE_GUIDE.md](/.github/PR_TITLE_GUIDE.md).
