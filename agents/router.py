"""Route an inbound mention to a team member by @handle."""

import re
from typing import List, Optional

from agents.base import TeamMember


def find_target(text: str, team: List[TeamMember]) -> Optional[TeamMember]:
    """Return the team member whose @handle appears earliest in the text.

    Matching is case-insensitive and word-bounded, so @Tradedesk matches
    "@tradedesk $TSLA buy" but not "@TradedeskFanClub". When several
    members are tagged, the one tagged first wins (user intent, not roster
    order). Members with an empty handle (the fallback agent) are never
    matched here.
    """
    lowered = text.lower()
    best_member: Optional[TeamMember] = None
    best_pos: Optional[int] = None
    for member in team:
        handle = member.profile.handle.lower()
        if not handle:
            continue
        match = re.search(r"@" + re.escape(handle) + r"\b", lowered)
        if match and (best_pos is None or match.start() < best_pos):
            best_member, best_pos = member, match.start()
    return best_member
