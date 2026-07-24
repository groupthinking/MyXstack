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
    truncate_for_reply,
    wrap_untrusted,
)


class ResearchAgent(TeamMember):
    def __init__(self):
        """Initialize the research agent with its profile and identifying metadata."""
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
        """
        Respond to a mention with a concise research brief and a full-brief timeline card.
        
        Parameters:
            mention (MentionContext): The mention containing the research question and its identifier.
        
        Returns:
            AgentReply: A truncated research response with a full brief card, or an offline status message when no brief is available.
        """
        brief = grok_chat(
            "You are a research agent on X. Answer the question below concisely "
            "and factually, using available tools for live context.\n\n"
            f"{wrap_untrusted(mention.text)}"
        )
        if not brief:
            return AgentReply(text="Research agent is offline (no XAI_API_KEY configured).")

        reply = truncate_for_reply(brief, suffix="… Full brief on your timeline.")
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
