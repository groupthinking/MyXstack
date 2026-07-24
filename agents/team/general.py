"""General agent — the fallback when no team member is tagged.

Preserves the original listener behavior: send the whole mention to Grok
with MCP tools and reply with whatever it produces, logging a card with
Approve/Reject/Snooze follow-up actions.
"""

from typing import Any, Dict, Optional

from agents.base import (
    KIND_AGENT,
    AgentProfile,
    AgentReply,
    MentionContext,
    TeamMember,
    grok_chat,
    wrap_untrusted,
)


class GeneralAgent(TeamMember):
    def __init__(self):
        """Initialize the fallback X agent with its profile and supported tags."""
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
        """
        Generate a reply and follow-up action card for a mention.
        
        Parameters:
        	mention (MentionContext): The mention content and associated conversation metadata.
        
        Returns:
        	AgentReply: The generated reply and an action card with approval, rejection, and snooze actions.
        """
        reply = grok_chat(
            "You are an autonomous X agent bot. You were mentioned in the post below.\n"
            "Analyze the request/intent. Use available tools to respond helpfully.\n"
            "Always reply directly to the mentioning post. Be concise and actionable.\n\n"
            f"{wrap_untrusted(mention.text)}"
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

    def execute_action(self, item: Dict[str, Any], action: str) -> Optional[str]:
        """Execute an action on one of this agent's timeline cards.
        
        Parameters:
            item (Dict[str, Any]): Timeline item associated with the action.
            action (str): Action selected for the timeline item.
        
        Returns:
            Optional[str]: Workflow status update, or an acknowledgment if no update is produced.
        """
        result = grok_chat(
            f"You are a workflow agent. A user took the action '{action}' on "
            f"timeline item {item.get('id', '?')} titled "
            f"'{item.get('title', '')}'.\n"
            "Use MCP tools to execute any required external steps. "
            "Return a concise status update."
        )
        return result or f"Acknowledged '{action}' (no executor output)."
