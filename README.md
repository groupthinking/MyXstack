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

There is also an alternative **TypeScript standalone agent** in `src/` that combines listening + MCP server in a single process (see [TypeScript Agent](#typescript-agent) below).

## Prerequisites

- **Python 3.11+** (for the service stack)
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

### Agent-to-Agent (A2A)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/a2a/agents` | List registered agents |
| GET | `/v1/a2a/agents/{id}` | Get agent details |
| POST | `/v1/a2a/agents` | Register new agent |
| GET | `/v1/a2a/agents/{id}/messages` | Get agent's messages |
| POST | `/v1/a2a/messages` | Send agent message |

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
```

See `docs/DEPLOYMENT.md` for full Railway setup details.

## Data Storage

Timeline cards and A2A messages are stored in JSON files at `~/.xmcp/` by default. This is intentional for lightweight local use. For production, override `TIMELINE_STORE_PATH` and `A2A_STORE_PATH` to point to a persistent volume.

## Project Structure

```
├── server.py              # MCP server (X API tools)
├── timeline_server.py     # Timeline + A2A FastAPI server
├── listener.py            # X mention poller + Grok responder
├── mcp_dispatcher.py      # Timeline action executor
├── timeline_store.py      # JSON-file timeline persistence
├── a2a_store.py           # JSON-file A2A persistence
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
