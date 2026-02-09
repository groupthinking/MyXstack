# MyXstack

This repository hosts a lightweight, step-by-step guide for setting up an autonomous X (Twitter) agent system that acts on thread context and reasoning, through Grok via the xMCP server. 

## Phase 1: Gather prerequisites & accounts (1–2 hours)

### X developer account & app
1. Go to <https://developer.x.com> and sign in with the account you want the bot to run on.
2. Create a new app/project (free tier is fine to start).
3. Set app permissions to **Read + Write + Direct Messages** so the agent can post replies.
4. Generate and record the OAuth 1.0a credentials:
   - API Key
   - API Secret
   - Access Token (user context)
   - Access Token Secret

### Dedicated bot account (recommended)
1. Create a new X account for the bot (for example, `@MyXMCPBot`).
2. Link the bot account to your developer app via the OAuth flow.
3. Note the bot user ID (you can fetch this via the API later).

### xAI / Grok API key
1. Visit <https://console.x.ai>, open the API keys section, and create a key that starts with `xai-`.
2. Store the key securely.

### Local tooling
- Install Python 3.9+ (3.10–3.13 recommended).
- Ensure `git` is installed for cloning.

## Phase 2: Clone & set up the xMCP server (local first)

1. Clone your fork of the xMCP server:
   ```bash
   git clone https://github.com/groupthinking/xMCP.git
   cd xMCP
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create your `.env`:
   ```bash
   cp env.example .env
   ```
5. Fill in the `.env` values you need:
   ```text
   # OAuth user token for posting replies
   X_OAUTH_ACCESS_TOKEN=your_access_token_here
   X_OAUTH_ACCESS_TOKEN_SECRET=your_access_token_secret_here

   # Optional read-only bearer token
   # X_BEARER_TOKEN=your_bearer_token_here

   # Grok / xAI
   XAI_API_KEY=your_xai_key_here
   XAI_MODEL=grok-4-1-fast

   # Optional tuning
   MCP_HOST=127.0.0.1
   MCP_PORT=8000
   X_API_DEBUG=1
   ```
6. If you need to generate OAuth user tokens, add `CLIENT_ID` and `CLIENT_SECRET` to `.env`, update the redirect URI in `generate_authtoken.py`, and run:
   ```bash
   python generate_authtoken.py
   ```

## Phase 3: Test the core xMCP server + Grok connection

1. Start the MCP server:
   ```bash
   python server.py
   ```
   You should see `Server running on http://127.0.0.1:8000`.
2. In another terminal, test Grok integration:
   ```bash
   python test_grok_mcp.py
   ```
3. Try prompts like:
   - `Search recent posts about MCP`
   - `Get my user info`
   - `Post a test reply saying 'Hello from MCP' to tweet ID 1234567890`

If these work, the core pipe (Grok → xMCP → X API) is live.

## Phase 4: Add the trigger layer (tag/mention → action)

A simple polling listener is provided in `listener.py` at the repo root. It uses Tweepy to poll for mentions and posts a placeholder reply. The listener requires OAuth user credentials (plus a bearer token for reads). Install Tweepy, export your environment variables, and run it while the xMCP server is up:

```bash
pip install tweepy
export X_API_KEY=your_api_key
export X_API_SECRET=your_api_secret
export X_OAUTH_ACCESS_TOKEN=your_access_token
export X_OAUTH_ACCESS_TOKEN_SECRET=your_access_token_secret
export X_BEARER_TOKEN=your_bearer_token
export POLL_INTERVAL_SECONDS=60
python listener.py
```

Then tag your bot from another account to see it respond. Replace the placeholder Grok call with your real xMCP/Grok invocation when ready.

## Phase 5: Iterate toward full autonomy

- Wire the listener to call Grok through the xMCP server.
- Add Docker/Docker Compose if you want a containerized workflow.
- Persist state (SQLite) to avoid reprocessing old mentions.
- Extend with proxies, CrewAI/AutoGen, or other agent frameworks.
- Deploy to Railway/Render/VPS for 24/7 operation.

## Current status
Start with Phases 1–4 today. If you hit a snag, share the exact output/error and we can debug together.
