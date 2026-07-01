# Agent Team

MyXstack runs a **team of @handle-addressable members** on top of the A2A
(agent-to-agent) layer. Tag a member in any mention and the listener routes
the request to it:

```
@MyXstack @Tradedesk $TSLA buy 100
@MyXstack @Research what's driving the $NVDA selloff?
@MyXstack @Shopping find trail running shoes under $150
@MyXstack @TickerBot $BTC
```

## Classification: interactive agents vs API bots

Every member is classified by `kind` in its profile (and in the A2A
registry at `GET /v1/a2a/agents`):

| Kind | What it is | Traits |
|------|------------|--------|
| `agent` (interactive agent) | Conversational, LLM-backed member | Reasons with Grok + MCP tools, can converse, run sub-steps, delegate to other members over A2A, and propose actions gated on human approval |
| `bot` (API bot) | Deterministic function executor | Input → function → output. No LLM, no autonomy, instant and predictable |

## Built-in roster

| Handle | ID | Kind | What it does |
|--------|----|------|--------------|
| `@Tradedesk` | `tradedesk` | agent | Parses `$TICKER buy/sell [qty]`, logs a **trade proposal** to the approval timeline. On Approve, executes via the **paper broker** (simulated fills in `~/.xmcp/paper_trades.json`). No live orders — a real broker is a pluggable adapter with the same `execute()` interface. |
| `@Shopping` | `shopping` | agent | Researches product picks with Grok; purchases are approval-gated intents (no payment executor is wired in by default). |
| `@Research` | `research` | agent | Answers questions using Grok + MCP tools for live X context; posts a short reply and files the full brief on the timeline. |
| `@TickerBot` | `tickerbot` | bot | Deterministic cashtag lookup — returns live-search links for each `$TICKER`. Reference implementation of the `bot` kind. |
| *(fallback)* | `x-agent` | agent | Original generic behavior when no member is tagged. |

Handles are configurable via `TRADEDESK_HANDLE`, `RESEARCH_HANDLE`,
`SHOPPING_HANDLE`, `TICKERBOT_HANDLE` in `.env`.

## How a request flows

```
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
2. Add it to `build_team()` in `agents/registry.py` (before the fallback
   `GeneralAgent`).
3. Done — routing, X replies, timeline cards, and dispatcher callbacks are
   handled by the framework.

## Safety defaults

- **Trades are paper-only.** `PaperBroker` writes simulated fills to a local
  ledger; nothing touches a real exchange.
- **Purchases are intents.** Approving a shopping card records the intent;
  no payment adapter ships with the repo.
- **Actions are approval-gated.** Cards with side effects require a human
  action on the timeline before the dispatcher executes anything.

## X API Exhibit

X has opened an early-access interest form for **X API Exhibit**, its
program for agent experiences on X — relevant if each team member should
eventually run under its own real X handle:
<https://devcommunity.x.com/t/introducing-the-x-api-exhibit-early-access-interest-form-now-open/268432>

Until then, all members share the listener's X account: users tag the bot
account plus the member handle (e.g. `@MyXstack @Tradedesk …`), and the
router picks the member from the text.
