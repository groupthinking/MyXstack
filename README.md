# MyXstack

An autonomous X (Twitter) agent system that monitors mentions, reasons over thread context via Grok, and executes actions through MCP-enabled tools.

## Architecture

Four services working together:

| Service | File | Port | Role |
|---------|------|------|------|
| **MCP Server** | `server.py` | 8000 | Wraps X API as MCP tools via OpenAPI spec |
| **Timeline Server** | `timeline_server.py` | 8080 | Timeline cards + Agent-to-Agent messaging API |
| **Listener** | `listener.py` | — | Polls X mentions → Grok reasoning → auto-reply + timeline card |
| **Dispatcher** | `mcp_dispatcher.py` | — | Watches timeline actions → executes via Grok + MCP tools |

**Flow**: Mention arrives → Listener sends to Grok (with MCP tools) → Grok crafts reply → posted to X + timeline card created → user approves/rejects via timeline → Dispatcher executes follow-up actions.

### Agent Team

Mentions are routed to a **team of @handle-addressable members** (see [docs/AGENTS.md](docs/AGENTS.md)):

```text
@MyXstack @Tradedesk $TSLA buy 100     → approval-gated trade proposal (paper broker)
@MyXstack @Research why is $NVDA down? → Grok research brief on the timeline
@MyXstack @Shopping shoes under $150   → product picks, purchase approval-gated
@MyXstack @TickerBot $BTC              → deterministic cashtag lookup (API bot)
@MyXstack stand up a 48-hour probe     → Hermes owns the goal and briefs it
```

Members are classified as **orchestrator** (`kind: orchestrator` — Hermes; owns untagged goals, routes vertical jobs, never does the specialist's job), **interactive agents** (`kind: agent` — conversational, LLM-backed, can delegate over A2A) or **API bots** (`kind: bot` — deterministic input → function → output). Untagged mentions go to **Hermes**, not a generic Grok dump. Tagged specialists still win when present.

There is also an alternative **TypeScript standalone agent** in `src/` that combines listening + MCP server in a single process (see [TypeScript Agent](#typescript-agent) below).

## Prerequisites

- **Python 3.12** (for the service stack — matches the Dockerfile and CI)
- **X API credentials** — [developer.x.com/portal](https://developer.x.com/portal) (Basic tier minimum)
- **xAI API key** — [console.x.ai](https://console.x.ai/) (for Grok)
- **Node.js 20+** (only if using the TypeScript agent)

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/groupthinking/MyXstack.git
cd MyXstack
cp env.example .env
```

Edit `.env` and fill in your credentials. At minimum you need:

```
X_BEARER_TOKEN=your_bearer_token
X_API_KEY=your_api_key
X_API_SECRET=your_api_secret
X_ACCESS_TOKEN=your_access_token
X_ACCESS_SECRET=your_access_secret
XAI_API_KEY=your_xai_key
```

### 2a. Run with Make (recommended)

```bash
make setup   # creates venv, installs deps, copies env
make run     # starts all 4 services in background
make stop    # shuts everything down
```

### 2b. Run with Docker

```bash
docker compose up -d --build
```

### 2c. Run manually

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# In separate terminals:
python server.py
python timeline_server.py
python listener.py
python mcp_dispatcher.py
```

### 3. Verify

```bash
# Timeline health check
curl http://localhost:8080/health

# List timeline items
curl http://localhost:8080/v1/timeline/users/default/items

# List registered agents
curl http://localhost:8080/v1/a2a/agents
```

## API Reference

### Timeline

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/timeline/users/{user_id}/items` | List timeline cards |
| GET | `/v1/timeline/items/{id}` | Get single item |
| POST | `/v1/timeline/items` | Create timeline card |
| PATCH | `/v1/timeline/items/{id}` | Update / take action on card |
| DELETE | `/v1/timeline/items/{id}` | Delete card |

Take an action with either `{"action_id": "approve"}` (what the UI sends) or
`{"action": "Approve"}` (the label). Both dispatch identically — the server
resolves an id to its label before handing off, because team members match on
labels. An `action_id` the card doesn't offer is rejected with a 400.

### Agent-to-Agent (A2A)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/a2a/agents` | List registered agents |
| GET | `/v1/a2a/agents/{id}` | Get agent details |
| POST | `/v1/a2a/agents` | Register new agent |
| GET | `/v1/a2a/agents/{id}/messages` | Get agent's messages |
| POST | `/v1/a2a/messages` | Send agent message |

## Approval UI

The timeline server serves a dependency-free approval surface at
**http://localhost:8080/ui**. It lists cards, renders their typed content, and
sends approvals back to the API. Enter the API token (if one is set) in the
header.

Cards whose action has already been executed render disabled, mirroring the
dispatcher's rule that a processed card is terminal.

> **Token storage.** The UI keeps the token in `localStorage` so a reload
> doesn't lose it. That is a deliberate convenience for an operator console on
> a trusted machine, not a hardened default: any same-origin script, and anyone
> with access to the browser profile, can read it. Treat the token as a
> credential that lives on that machine, rotate it when a browser profile is
> shared or retired, and prefer a dedicated browser profile for the console.

### Authentication

The timeline and A2A API — including the PATCH that authorizes agent actions —
is **unauthenticated when `TIMELINE_API_TOKEN` is empty**, which keeps local
development frictionless.

**On a deployment, an empty token is fatal rather than merely noisy.** When a
deployment marker is present (`RAILWAY_SERVICE_NAME`, `RAILWAY_ENVIRONMENT`,
`KUBERNETES_SERVICE_HOST`) and no token is set, the app refuses to start. This
runs at import time, so it applies to every entrypoint including
`uvicorn main:app` — the Railway path, which never calls
`timeline_server.main()`. Set `TIMELINE_ALLOW_INSECURE=1` to override
deliberately. Without a deployment marker, an empty token only warns.

**That detection is a heuristic with a known gap.** Only Railway and
Kubernetes are recognised. A VPS, Fly, Render, or `docker compose` on a public
host sets none of those markers, so an empty token there warns rather than
refusing — and the approval API is reachable anonymously. Set
`TIMELINE_API_TOKEN` yourself on any host not in that list. Closing the gap
means inverting the default (always fatal, opt out explicitly for local),
which is a deliberate open question rather than an oversight.

```bash
export TIMELINE_API_TOKEN="$(openssl rand -hex 32)"   # export: make run needs it in the child env
```

All four services must read the same value. Under `docker compose` that happens
via the shared `env_file`, but **separate Railway services do not inherit each
other's environment** — set `TIMELINE_API_TOKEN` on the timeline-server,
listener, and dispatcher services individually, or the workers will get 401s.

`/health` never requires the token, so container and load-balancer probes keep
working. Set `TIMELINE_CORS_ORIGINS` only if you host a surface on another
origin.

## Card Content

A card carries typed `blocks` so a surface can render structure instead of one
blob of text. Four block types cover what members produce:

| Block | Use |
|-------|-----|
| `text` | A prose section (`label` becomes its heading) |
| `facts` | Key/value pairs — the parameters of a proposed action |
| `table` | Tabular results |
| `links` | Sources or destinations (http/https only — other schemes are rejected) |

Actions are typed too — `{id, label, style}` plus an optional `confirm` prompt —
where `label` is both what the human reads and what a member's `execute_action`
matches on. Action ids must be unique within a card; duplicates are rejected
with a 422.

Members build cards with helpers from `agents/base.py` rather than raw dicts:

```python
from agents.base import build_card, facts_block, text_block, approve_reject

card = build_card(
    title="Trade proposal: BUY 10 $TSLA",
    blocks=[
        facts_block({"Ticker": "$TSLA", "Side": "BUY"}, label="Order"),
        text_block(mention.text, label="Requested via X"),
    ],
    actions=approve_reject("Approve", "Reject"),
    metadata={"agent_id": "tradedesk", "action_type": "trade"},
)
```

**Backward compatibility.** `body` is still populated — derived from `blocks`
when not supplied — so anything reading it keeps working. Cards written before
typed blocks are upgraded in memory on read, so no card-level rewrite is needed.
(That is separate from `scripts/migrate_json_to_sql.py`, which is a one-time
move of the old JSON stores into SQL.)

## OpenAPI Filtering

The MCP server loads all X API operations from `openapi.json`. Filter what's exposed:

```bash
# Only expose tweet-related tools
X_API_TOOL_TAGS=tweets

# Allow specific operations
X_API_TOOL_ALLOWLIST=createTweet,findTweetById

# Block specific operations
X_API_TOOL_DENYLIST=listBatchComplianceJobs
```

Streaming and webhook endpoints are excluded automatically.

## TypeScript Agent

An alternative standalone agent that combines mention monitoring and MCP server in a single Node.js process. Includes a simulation mode for testing without real API credentials.

```bash
npm install
npm run build
npm start
```

Set `X_USERNAME` in `.env`. If `X_BEARER_TOKEN` or `XAI_API_KEY` are missing, the agent runs in simulation mode with mock data.

## Deployment (Railway)

Create four Railway services from this repo with these start commands:

| Service | Command | Env Overrides |
|---------|---------|---------------|
| mcp-server | `python server.py` | — |
| timeline-server | `python timeline_server.py` | — |
| listener | `python listener.py` | `MCP_SERVER_URL`, `TIMELINE_API_URL` |
| dispatcher | `python mcp_dispatcher.py` | `MCP_SERVER_URL`, `TIMELINE_API_URL` |

Wire the cross-service URLs after deployment:

```
MCP_SERVER_URL=https://<mcp-server>.up.railway.app/mcp
TIMELINE_API_URL=https://<timeline-server>.up.railway.app
# All four services must share one database:
DATABASE_URL=postgres://<user>:<pass>@<host>:<port>/<db>
```

See `docs/DEPLOYMENT.md` for full Railway setup details.

## Data Storage

Timeline cards and A2A messages are stored in SQL and selected by `DATABASE_URL`:

- `DATABASE_URL` unset (or `sqlite://...`) → SQLite (`~/.xmcp/xmcp.db` by default)
- `postgres://...` or `postgresql://...` → Postgres (Railway-ready; `postgres://` is normalized automatically)

Tables are created automatically on startup. For local concurrency safety, SQLite enables WAL mode and a busy timeout. To migrate legacy JSON stores (`TIMELINE_STORE_PATH`, `A2A_STORE_PATH`), run:

```bash
python scripts/migrate_json_to_sql.py
```

## Project Structure

```
├── server.py              # MCP server (X API tools)
├── timeline_server.py     # Timeline + A2A FastAPI server
├── listener.py            # X mention poller + Grok responder
├── mcp_dispatcher.py      # Timeline action executor
├── cards.py               # Typed card schema (blocks, actions, legacy upgrade)
├── timeline_store.py      # SQL-backed timeline persistence
├── a2a_store.py           # SQL-backed A2A persistence
├── storage_db.py          # Shared SQLAlchemy engine/schema
├── store_lock.py          # Cross-process file locking for the paper-trade ledger
├── scripts/migrate_json_to_sql.py
├── ui/                    # Approval surface served at /ui (no build step)
├── openapi.json           # X API OpenAPI spec (used by MCP server)
├── src/                   # TypeScript standalone agent (alternative)
├── docs/                  # Architecture, deployment, usage guides
├── docker-compose.yml     # Multi-service Docker orchestration
├── Dockerfile
├── Makefile
├── env.example
├── requirements.txt
├── package.json
└── tsconfig.json
```

## License

MIT
