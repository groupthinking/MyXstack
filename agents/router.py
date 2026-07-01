"""Route an inbound mention to a team member by @handle."""

import re
from typing import List, Optional

from agents.base import TeamMember


def find_target(text: str, team: List[TeamMember]) -> Optional[TeamMember]:
    """Return the first team member whose @handle appears in the text.

    Matching is case-insensitive and word-bounded, so @Tradedesk matches
    "@tradedesk $TSLA buy" but not "@TradedeskFanClub". Members with an
    empty handle (the fallback agent) are never matched here.
    """
    lowered = text.lower()
    for member in team:
        handle = member.profile.handle.lower()
        if not handle:
            continue
        if re.search(r"@" + re.escape(handle) + r"\b", lowered):
            return member
    return None
