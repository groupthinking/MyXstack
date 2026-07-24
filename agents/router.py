"""Route an inbound mention to a team member by @handle."""

import re
from typing import List, Optional

from agents.base import TeamMember


def find_target(text: str, team: List[TeamMember]) -> Optional[TeamMember]:
    """
    Selects the team member whose handle is mentioned first in the text.
    
    Matching is case-insensitive and requires a word boundary after the handle.
    Members with empty handles are not eligible for selection.
    
    Returns:
        The team member associated with the earliest matching handle, or `None`
        if no handle is mentioned.
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
