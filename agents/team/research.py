"""@Research — interactive research agent.

Usage on X:  @Research what's driving the $NVDA selloff today?

Sends the question to Grok (with MCP tools for live X data), posts a
short reply, and files the full brief on the timeline.
"""

import os

from agents.base import (
    KIND_AGENT,
    AgentProfile,
    AgentReply,
    MentionContext,
    TeamMember,
    grok_chat,
)


class ResearchAgent(TeamMember):
    def __init__(self):
        super().__init__(
            AgentProfile(
                id="research",
                handle=os.getenv("RESEARCH_HANDLE", "Research"),
                name="Research",
                description="Answers questions with Grok + live X context; files full briefs on the timeline.",
                kind=KIND_AGENT,
                tags=["research", "analysis"],
            )
        )

    def handle_mention(self, mention: MentionContext) -> AgentReply:
        brief = grok_chat(
            "You are a research agent on X. Answer the question below concisely "
            "and factually, using available tools for live context.\n\n"
            f"Question (from an X mention):\n{mention.text}"
        )
        if not brief:
            return AgentReply(text="Research agent is offline (no XAI_API_KEY configured).")

        if len(brief) <= 270:
            reply = brief
        else:
            reply = brief[:240].rsplit(" ", 1)[0] + "… Full brief on your timeline."
        card = {
            "title": "Research brief",
            "body": f"Question:\n{mention.text}\n\nBrief:\n{brief}",
            "actions": [],
            "metadata": {
                "agent_id": self.profile.id,
                "action_type": "research",
                "mention_id": mention.mention_id,
            },
        }
        return AgentReply(text=reply, card=card)
