"""@TickerBot — API bot (kind="bot").

Usage on X:  @TickerBot $TSLA

Pure function executor: parses cashtags and returns a canned, deterministic
response with search links. No LLM, no autonomy — this is the reference
implementation of the "bot" classification.
"""

import os
import re

from agents.base import KIND_BOT, AgentProfile, AgentReply, MentionContext, TeamMember

_CASHTAG = re.compile(r"\$(?P<ticker>[A-Za-z]{1,10})\b")


class TickerBot(TeamMember):
    def __init__(self):
        super().__init__(
            AgentProfile(
                id="tickerbot",
                handle=os.getenv("TICKERBOT_HANDLE", "TickerBot"),
                name="Ticker Bot",
                description="Deterministic cashtag lookup: input ticker, output search links.",
                kind=KIND_BOT,
                tags=["tickers", "utility"],
            )
        )

    def handle_mention(self, mention: MentionContext) -> AgentReply:
        """
        Format a response for cashtags found in a mention.
        
        Parameters:
            mention (MentionContext): The mention whose text is searched for cashtags.
        
        Returns:
            AgentReply: A usage instruction when no cashtags are found; otherwise, newline-delimited live-search links for the unique tickers.
        """
        tickers = sorted({m.group("ticker").upper() for m in _CASHTAG.finditer(mention.text)})
        if not tickers:
            return AgentReply(text="Usage: @TickerBot $TICKER — e.g. @TickerBot $TSLA")
        lines = [
            f"${ticker}: live chatter → x.com/search?q=%24{ticker}&f=live" for ticker in tickers
        ]
        return AgentReply(text="\n".join(lines))
