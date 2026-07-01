"""General agent — the fallback when no team member is tagged.

Preserves the original listener behavior: send the whole mention to Grok
with MCP tools and reply with whatever it produces, logging a card with
Approve/Reject/Snooze follow-up actions.
"""

from agents.base import (
    KIND_AGENT,
    AgentProfile,
    AgentReply,
    MentionContext,
    TeamMember,
    grok_chat,
)


class GeneralAgent(TeamMember):
    def __init__(self):
        super().__init__(
            AgentProfile(
                id="x-agent",
                handle="",  # fallback member; never matched by @handle
                name="X Agent",
                description="Handles @mentions and X actions.",
                kind=KIND_AGENT,
                tags=["x", "social"],
            )
        )

    def handle_mention(self, mention: MentionContext) -> AgentReply:
        reply = grok_chat(
            "You are an autonomous X agent bot. You were mentioned in this thread:\n\n"
            f"{mention.text}\n\n"
            "Analyze the request/intent. Use available tools to respond helpfully.\n"
            "Always reply directly to the mentioning post. Be concise and actionable."
        )
        if not reply:
            reply = "Thinking..."
        card = {
            "title": f"New mention {mention.mention_id or ''}".strip(),
            "body": mention.text,
            "actions": ["Approve", "Reject", "Snooze"],
            "metadata": {
                "agent_id": self.profile.id,
                "mention_id": mention.mention_id,
                "author_id": mention.author_id,
                "conversation_id": mention.conversation_id,
                "reply_preview": reply[:280],
            },
        }
        return AgentReply(text=reply, card=card)
