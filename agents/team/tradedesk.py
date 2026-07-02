"""@Tradedesk — interactive trading agent.

Usage on X:  @Tradedesk $TSLA buy 100   (or: @Tradedesk buy $TSLA 100)

Flow: parse the command deterministically, optionally enrich with Grok
market context, then log a trade *proposal* to the approval timeline.
Nothing executes until a human approves the card, and execution goes to
the paper broker unless a real adapter is wired in.
"""

import math
import os
import re
from typing import Any, Dict, Optional

from agents.base import (
    KIND_AGENT,
    AgentProfile,
    AgentReply,
    MentionContext,
    TeamMember,
    grok_chat,
)
from agents.broker import PaperBroker

# "$TSLA buy 100" — ticker first
_TICKER_FIRST = re.compile(
    r"\$(?P<ticker>[A-Za-z]{1,10})\s+(?P<side>buy|sell)\b(?:\s+(?P<qty>\d+(?:\.\d+)?))?",
    re.IGNORECASE,
)
# "buy $TSLA 100" — side first ($ required so plain words never match)
_SIDE_FIRST = re.compile(
    r"\b(?P<side>buy|sell)\s+\$(?P<ticker>[A-Za-z]{1,10})\b(?:\s+(?P<qty>\d+(?:\.\d+)?))?",
    re.IGNORECASE,
)

USAGE = "Format: @Tradedesk $TICKER buy|sell [quantity] — e.g. @Tradedesk $TSLA buy 100"


def parse_trade_command(text: str) -> Optional[Dict[str, Any]]:
    match = _TICKER_FIRST.search(text) or _SIDE_FIRST.search(text)
    if not match:
        return None
    return {
        "ticker": match.group("ticker").upper(),
        "side": match.group("side").lower(),
        "quantity": float(match.group("qty")) if match.group("qty") else 1.0,
    }


class TradeDeskAgent(TeamMember):
    def __init__(self, broker: Optional[PaperBroker] = None):
        super().__init__(
            AgentProfile(
                id="tradedesk",
                handle=os.getenv("TRADEDESK_HANDLE", "Tradedesk"),
                name="Trade Desk",
                description="Turns tagged trade commands into approval-gated proposals.",
                kind=KIND_AGENT,
                tags=["trading", "finance"],
            )
        )
        self.broker = broker or PaperBroker()

    def handle_mention(self, mention: MentionContext) -> AgentReply:
        trade = parse_trade_command(mention.text)
        if not trade:
            return AgentReply(text=f"Couldn't parse a trade. {USAGE}")

        summary = f"{trade['side'].upper()} {trade['quantity']:g} ${trade['ticker']}"
        context = ""
        if os.getenv("TRADEDESK_USE_GROK", "1") == "1":
            # Only the parsed, validated ticker/side reach the prompt — the
            # raw mention text never does.
            context = grok_chat(
                f"In under 80 words, give current market context for ${trade['ticker']} "
                f"relevant to a proposed {trade['side']} order. Facts only, no advice."
            )

        body = f"Requested via X mention {mention.mention_id or '?'}:\n\n{mention.text}"
        if context:
            body += f"\n\nMarket context (Grok):\n{context}"

        card = {
            "title": f"Trade proposal: {summary}",
            "body": body,
            "actions": ["Approve", "Reject"],
            "metadata": {
                "agent_id": self.profile.id,
                "action_type": "trade",
                "ticker": trade["ticker"],
                "side": trade["side"],
                "quantity": trade["quantity"],
                "mention_id": mention.mention_id,
                "author_id": mention.author_id,
            },
        }
        reply = (
            f"📋 Trade proposal logged: {summary}. Pending human approval on the "
            f"timeline. (Paper trading — no live orders.)"
        )
        return AgentReply(text=reply, card=card)

    def execute_action(self, item: Dict[str, Any], action: str) -> Optional[str]:
        metadata = item.get("metadata") or {}
        if metadata.get("action_type") != "trade":
            return None
        # Card metadata round-trips through JSON and external stores, so
        # coerce before trusting types.
        ticker = str(metadata.get("ticker", "")).upper()
        if not re.fullmatch(r"[A-Z]{1,10}", ticker):
            return f"⚠️ Invalid ticker '{ticker}' on trade card {item.get('id', '?')}; nothing executed."
        side = str(metadata.get("side", "buy")).lower()
        if side not in ("buy", "sell"):
            return f"⚠️ Invalid side '{side}' on trade card {item.get('id', '?')}; nothing executed."
        try:
            quantity = float(metadata.get("quantity", 1))
        except (TypeError, ValueError):
            return f"⚠️ Invalid quantity on trade card {item.get('id', '?')}; nothing executed."
        if not math.isfinite(quantity) or quantity <= 0:
            return f"⚠️ Invalid quantity {quantity:g} on trade card {item.get('id', '?')}; nothing executed."
        summary = f"{side.upper()} {quantity:g} ${ticker}"
        if action.lower() == "approve":
            # The card id keys the fill, so a replayed/double-clicked
            # approval can never book a second fill for the same proposal.
            key = item.get("id") or (
                f"mention-{metadata['mention_id']}" if metadata.get("mention_id") else None
            )
            fill = self.broker.execute(ticker=ticker, side=side, quantity=quantity, key=key)
            if fill.get("duplicate"):
                return f"↩️ {summary} was already executed (fill {fill['id'][:8]}); duplicate approval ignored."
            return f"✅ Executed {summary} on {fill['venue']} venue (fill {fill['id'][:8]})."
        if action.lower() == "reject":
            return f"🚫 Trade proposal {summary} cancelled. No order placed."
        return None
