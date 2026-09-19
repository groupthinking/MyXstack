"""@Hermes — orchestrator. Owns the goal. Never does the specialist's job.

Untagged mentions land here. Tagged specialists still win when present.

Usage on X:
  @MyXstack why is $NVDA down?          → Hermes owns it, hands to @Research
  @MyXstack $TSLA buy 100               → Hermes owns it, hands to @Tradedesk
  @MyXstack stand up a 48-hour probe    → Hermes briefs the goal
  @MyXstack @Hermes …                   → same member, tagged explicitly
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, Optional

from agents.base import (
    KIND_ORCHESTRATOR,
    AgentProfile,
    AgentReply,
    MentionContext,
    TeamMember,
    build_card,
    facts_block,
    grok_chat,
    send_a2a_message,
    text_block,
    truncate_for_reply,
    wrap_untrusted,
)
from agents.team.tradedesk import parse_trade_command

_SHOPPING = re.compile(
    r"\b(find(?:\s+me)?|shop(?:ping)?|buy me|purchase|under\s+\$)\b",
    re.IGNORECASE,
)
_QUESTION = re.compile(
    r"\b(why|what(?:'s|s)?|how|who|when|where|explain|brief|research)\b",
    re.IGNORECASE,
)
_CASHTAG = re.compile(r"\$[A-Za-z]{1,10}\b")

ORCHESTRATOR_PROMPT = (
    "You are Hermes, orchestrator of MyXstack. You own the goal. "
    "You never do the specialist's job, invent citations, or answer the "
    "question yourself.\n"
    "Specialists: @Research (live briefs), @Tradedesk (paper-trade proposals), "
    "@Shopping (product picks, approval-gated), @TickerBot (cashtag lookup).\n"
    "Decompose the inbound goal into 3-7 operational units. Each unit names "
    "an owner, the work, and a definition of done. Side-effects wait on a "
    "timeline card. Closed loops only.\n"
    "Return plain text in this shape:\n"
    "Goal: …\n"
    "Units:\n"
    "1. owner — work — done: …\n"
    "Side-effect: none | named gate\n"
    "Stop: …\n\n"
)


def pick_owner(text: str) -> Optional[str]:
    """Return a specialist id when the mention is already a vertical job.

    None means Hermes keeps the goal and briefs it. Deterministic — no LLM.
    Order is the contract: a parsed trade beats a shopping phrase, a
    question beats a bare cashtag.
    """
    if parse_trade_command(text):
        return "tradedesk"
    if _SHOPPING.search(text):
        return "shopping"
    if _QUESTION.search(text):
        return "research"
    if _CASHTAG.search(text):
        return "tickerbot"
    return None


class HermesAgent(TeamMember):
    def __init__(self):
        super().__init__(
            AgentProfile(
                id="hermes",
                handle=os.getenv("HERMES_HANDLE", "Hermes"),
                name="Hermes",
                description=(
                    "Owns untagged goals. Routes vertical jobs to specialists. "
                    "Never answers as a generic Grok dump."
                ),
                kind=KIND_ORCHESTRATOR,
                tags=["command", "orchestrator"],
                fallback=True,
            )
        )

    def handle_mention(self, mention: MentionContext) -> AgentReply:
        owner_id = pick_owner(mention.text)
        if owner_id:
            handed = self._handoff(mention, owner_id)
            if handed:
                return handed
        return self._brief(mention)

    def execute_action(self, item: Dict[str, Any], action: str) -> Optional[str]:
        metadata = item.get("metadata") or {}
        if metadata.get("agent_id") != self.profile.id:
            return None
        return (
            f"Hermes briefs are informational. Action '{action}' did not "
            "execute a side-effect."
        )

    def _handoff(self, mention: MentionContext, owner_id: str) -> Optional[AgentReply]:
        from agents.registry import find_member

        owner = find_member(owner_id)
        if owner is None or owner.profile.id == self.profile.id:
            return None
        send_a2a_message(
            from_agent=self.profile.id,
            to=owner.profile.id,
            message_type="handoff",
            content=mention.text,
            metadata={
                "mention_id": mention.mention_id,
                "reason": "untagged vertical job",
            },
        )
        reply = owner.handle_mention(mention)
        if reply.card:
            meta = dict(reply.card.get("metadata") or {})
            meta["routed_by"] = self.profile.id
            reply.card["metadata"] = meta
        handle = owner.profile.handle or owner.profile.id
        prefix = f"Hermes → @{handle}. "
        reply.text = truncate_for_reply(prefix + reply.text)
        return reply

    def _brief(self, mention: MentionContext) -> AgentReply:
        plan = grok_chat(
            ORCHESTRATOR_PROMPT + wrap_untrusted(mention.text)
        )
        if not plan:
            plan = (
                "Grok is offline. Goal is owned by Hermes. No specialist "
                "assigned. No side-effect proposed."
            )
        card = build_card(
            title="Hermes brief",
            blocks=[
                facts_block(
                    {
                        "Owner": "Hermes",
                        "Route": "captain",
                        "Side-effect": "none",
                    },
                    label="Intake",
                ),
                text_block(mention.text, label="Goal"),
                text_block(plan, label="Units"),
            ],
            metadata={
                "agent_id": self.profile.id,
                "action_type": "brief",
                "mention_id": mention.mention_id,
                "author_id": mention.author_id,
                "conversation_id": mention.conversation_id,
            },
        )
        reply = truncate_for_reply(
            "Hermes has the goal. Units on your timeline.",
            suffix="… Full brief on your timeline.",
        )
        return AgentReply(text=reply, card=card)
