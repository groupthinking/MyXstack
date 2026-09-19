# Agent Team

MyXstack runs a **team of @handle-addressable members** on top of the A2A
(agent-to-agent) layer. Tag a member in any mention and the listener routes the request to it.
Untagged mentions go to **Hermes**.

```text
@MyXstack @Tradedesk $TSLA buy 100
@MyXstack @Research what's driving the $NVDA selloff?
@MyXstack @Shopping find trail running shoes under $150
@MyXstack @TickerBot $BTC
@MyXstack stand up a 48-hour probe
@MyXstack @Hermes own this goal
```

## Classification: interactive agents vs API bots

Every member is classified by `kind` in its profile (and in the A2A
registry at `GET /v1/a2a/agents`):

| Kind | What it is | Traits |
|------|------------|--------|
| `orchestrator` | Captain. Owns the goal. | Routes work, reads the roster, never does the specialist's job. Untagged mentions land here. |
| `agent` (interactive agent) | Conversational, LLM-backed member | Reasons with Grok + MCP tools, can converse, run sub-steps, delegate to other members over A2A, and propose actions gated on human approval |
| `bot` (API bot) | Deterministic function executor | Input → function → output. No LLM, no autonomy, instant and predictable |

## Built-in roster

| Handle | ID | Kind | What it does |
|--------|----|------|--------------|
| `@Hermes` | `hermes` | orchestrator | Owns untagged goals. Hands a vertical job to the matching specialist. Otherwise files a captain brief (units, owners, stop). Never answers as a generic Grok dump. |
| `@Tradedesk` | `tradedesk` | agent | Parses `$TICKER buy/sell [qty]`, logs a **trade proposal** to the approval timeline. On Approve, executes via the **paper broker** (simulated fills in `~/.xmcp/paper_trades.json`). No live orders — a real broker is a pluggable adapter with the same `execute()` interface. |
| `@Shopping` | `shopping` | agent | Researches product picks with Grok; purchases are approval-gated intents (no payment executor is wired in by default). |
| `@Research` | `research` | agent | Answers questions using Grok + MCP tools for live X context; posts a short reply and files the full brief on the timeline. |
| `@TickerBot` | `tickerbot` | bot | Deterministic cashtag lookup — returns live-search links for each `$TICKER`. Reference implementation of the `bot` kind. |
| *(legacy)* | `x-agent` | agent | Owner of pre-Hermes cards only. New untagged mentions do not land here. |

Handles are configurable via `HERMES_HANDLE`, `TRADEDESK_HANDLE`, `RESEARCH_HANDLE`,
`SHOPPING_HANDLE`, `TICKERBOT_HANDLE` in `.env`.

## How a request flows

```text
X mention "@Tradedesk $TSLA buy 100"
   │
   ▼
listener.py ── router matches @handle ──► TradeDeskAgent.handle_mention()
   │                                          │ replies on X: "proposal logged"
   │                                          ▼
   │                                    timeline card [Approve] [Reject]
   │                                          │ human clicks Approve
   ▼                                          ▼
mcp_dispatcher.py ── card owner lookup ──► TradeDeskAgent.execute_action()
                                              │
                                              ▼
                                        PaperBroker.execute() → fill recorded
```

Members can also message each other directly on the A2A bus
(`POST /v1/a2a/messages`) via `agents.base.send_a2a_message()` — an
interactive agent can drive its own sub-agents and bots this way.

## Adding a team member

1. Create `agents/team/mymember.py` subclassing `TeamMember`:
   - set an `AgentProfile` with a unique `id`, a `handle`, and a `kind`
   - implement `handle_mention()` → `AgentReply(text, card=None)`
   - implement `execute_action()` if your cards have Approve/Reject actions
2. Add it to `build_team()` in `agents/registry.py`. Untagged mentions always
   go to the member with `fallback=True` (Hermes). Do not add a second fallback.
3. Done — routing, X replies, timeline cards, and dispatcher callbacks are
   handled by the framework.

## Writing a card

A card is how a member asks a human to look at something and, when it carries
actions, to authorize something. Build one with the helpers in
`agents/base.py` — never hand-roll the dict, or your content won't render on
the approval surface at `/ui`.

```python
from agents.base import (
    approve_reject, build_card, facts_block, links_block, table_block, text_block,
)

card = build_card(
    title="Shopping picks",
    blocks=[
        text_block(mention.text, label="Request"),
        table_block(["Item", "Price"], [["Speedgoat 6", "$145"]], label="Picks"),
        links_block([{"label": "Source", "url": "https://…"}], label="Sources"),
    ],
    actions=approve_reject("Approve Purchase", "Reject"),
    metadata={"agent_id": self.profile.id, "action_type": "purchase"},
)
```

Block types are `text`, `facts`, `table`, and `links`. The set is deliberately
small — every surface must be able to render every type, so adding one is a
real cost rather than a free extension.

Two rules matter when your card has actions:

- **`metadata["agent_id"]` is required.** The dispatcher routes an approval
  back to the member that proposed it via this field. Without it the card
  falls through to the generic Grok executor.
- **Action labels are the contract.** `execute_action()` receives the *label*,
  not the id, so `approve_reject("Approve Purchase", …)` must be matched by
  code that checks for `"Approve Purchase"`. Changing a label is a
  behavioural change.

Cards with no actions (a research brief, an error report) are informational —
pass no `actions` and the surface renders them without buttons.

## Safety defaults

- **Trades are paper-only.** `PaperBroker` writes simulated fills to a local
  ledger; nothing touches a real exchange.
- **Purchases are intents.** Approving a shopping card records the intent;
  no payment adapter ships with the repo.
- **Actions are approval-gated.** Cards with side effects require a human
  action on the timeline before the dispatcher executes anything.
- **Approvals are authenticated** when `TIMELINE_API_TOKEN` is set. It is empty
  by default for local use. On a deployment (detected via `RAILWAY_SERVICE_NAME`
  and friends) an empty token makes the app refuse to start rather than serve
  approvals anonymously; the check runs at import time so it covers every
  entrypoint, including `uvicorn main:app`. `TIMELINE_ALLOW_INSECURE=1`
  overrides it deliberately.
- **A surface can only trigger actions the card offers.** Both an unknown
  `action_id` and a bare `action` label the card doesn't carry are rejected
  with a 400, and nothing is dispatched. Sending an `action` that contradicts
  the supplied `action_id` is also a 400.
- **Card links are http(s) only.** `links_block` drops other schemes and the
  API rejects them, because card content derives from model output over
  untrusted mentions and lands in the approval UI's DOM.

## X API Exhibit

X has opened an early-access interest form for **X API Exhibit**, its
program for agent experiences on X — relevant if each team member should
eventually run under its own real X handle:
<https://devcommunity.x.com/t/introducing-the-x-api-exhibit-early-access-interest-form-now-open/268432>

Until then, all members share the listener's X account: users tag the bot
account plus the member handle (e.g. `@MyXstack @Tradedesk …`), and the
router picks the member from the text.
