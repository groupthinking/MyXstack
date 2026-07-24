"""@Shopping — interactive shopping agent.

Usage on X:  @Shopping find me trail running shoes under $150

Grok researches options and replies with picks; any purchase intent is
logged as an approval card. There is no built-in payment executor —
approving records the intent until a commerce adapter is wired in.
"""

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
    truncate_for_reply,
    wrap_untrusted,
)

_BUDGET = re.compile(r"under\s+\$(?P<budget>\d+(?:\.\d+)?)", re.IGNORECASE)


class ShoppingAgent(TeamMember):
    def __init__(self):
        """Initialize the shopping agent with its profile and commerce-related tags."""
        super().__init__(
            AgentProfile(
                id="shopping",
                handle=os.getenv("SHOPPING_HANDLE", "Shopping"),
                name="Shopping",
                description="Finds products; purchases are approval-gated intents.",
                kind=KIND_AGENT,
                tags=["shopping", "commerce"],
            )
        )

    def handle_mention(self, mention: MentionContext) -> AgentReply:
        """
        Generate shopping recommendations for a mention and attach an approval-gated purchase card.
        
        Parameters:
            mention (MentionContext): Mention containing the user's shopping request.
        
        Returns:
            AgentReply: A reply with product recommendations and a purchase action card, or an offline message when recommendations are unavailable.
        """
        budget_match = _BUDGET.search(mention.text)
        budget = f" with a budget of ${budget_match.group('budget')}" if budget_match else ""
        picks = grok_chat(
            "You are a shopping assistant. From the request below, suggest up to 3 "
            f"specific products{budget}, one line each with an approximate price. "
            "Facts only.\n\n"
            f"{wrap_untrusted(mention.text)}"
        )
        if not picks:
            return AgentReply(text="Shopping agent is offline (no XAI_API_KEY configured).")

        card = {
            "title": "Shopping picks",
            "body": f"Request:\n{mention.text}\n\nPicks:\n{picks}",
            "actions": ["Approve Purchase", "Reject"],
            "metadata": {
                "agent_id": self.profile.id,
                "action_type": "purchase",
                "mention_id": mention.mention_id,
                "author_id": mention.author_id,
            },
        }
        reply = truncate_for_reply(picks, suffix="… Full list on your timeline.")
        return AgentReply(text=reply, card=card)

    def execute_action(self, item: Dict[str, Any], action: str) -> Optional[str]:
        """
        Process an approval or rejection action for a purchase intent card.
        
        Parameters:
            item (Dict[str, Any]): Card data containing purchase intent metadata.
            action (str): Action selected for the card.
        
        Returns:
            Optional[str]: A status message for a recognized purchase action, or `None` when the card or action is unsupported.
        """
        metadata = item.get("metadata") or {}
        if metadata.get("action_type") != "purchase":
            return None
        if action.lower().startswith("approve"):
            return (
                "🛒 Purchase intent recorded. No payment adapter is configured, "
                "so nothing was bought — connect a commerce executor to complete orders."
            )
        if action.lower() == "reject":
            return "🚫 Shopping request closed. Nothing was purchased."
        return None
