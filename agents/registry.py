"""Team roster, @handle routing, and A2A registration."""

import os
import threading
import time
from typing import List, Optional

import requests

from agents.base import MentionContext, TeamMember
from agents.router import find_target


def build_team() -> List[TeamMember]:
    """Construct the roster of available team agents.
    
    Returns:
        List[TeamMember]: Team members ordered with the general agent last as the fallback.
    """
    from agents.team.general import GeneralAgent
    from agents.team.research import ResearchAgent
    from agents.team.shopping import ShoppingAgent
    from agents.team.tickerbot import TickerBot
    from agents.team.tradedesk import TradeDeskAgent

    # GeneralAgent must stay last: it is the fallback when no handle matches.
    return [TradeDeskAgent(), ShoppingAgent(), ResearchAgent(), TickerBot(), GeneralAgent()]


_TEAM: Optional[List[TeamMember]] = None
_TEAM_LOCK = threading.Lock()


def get_team() -> List[TeamMember]:
    """
    Return the cached team roster, constructing it on first access.
    
    Returns:
    	List[TeamMember]: The team roster.
    """
    global _TEAM
    if _TEAM is None:
        with _TEAM_LOCK:
            if _TEAM is None:
                _TEAM = build_team()
    return _TEAM


def route_mention(mention: MentionContext) -> TeamMember:
    """Route to the earliest-tagged member; fall back to the member with an
    empty handle (the general agent), regardless of roster order."""
    team = get_team()
    target = find_target(mention.text, team)
    if target:
        return target
    return next(m for m in team if not m.profile.handle)


def find_member(agent_id: Optional[str]) -> Optional[TeamMember]:
    """
    Find a team member by agent ID.
    
    Parameters:
    	agent_id (Optional[str]): The ID of the agent to locate.
    
    Returns:
    	Optional[TeamMember]: The matching team member, or `None` if no member has the specified ID.
    """
    if not agent_id:
        return None
    for member in get_team():
        if member.profile.id == agent_id:
            return member
    return None


def register_team() -> None:
    """
    Register all team members with the timeline server's A2A registry.
    
    The registry URL is read from the `TIMELINE_API_URL` environment variable, defaulting to the local timeline server. Each member is retried up to three times when registration requests fail.
    """
    timeline_url = os.getenv("TIMELINE_API_URL", "http://127.0.0.1:8080")
    for member in get_team():
        profile = member.profile
        payload = {
            "id": profile.id,
            "name": profile.name,
            "description": profile.description,
            "status": "online",
            "endpoint": f"x:@{profile.handle}" if profile.handle else "x",
            "kind": profile.kind,
            "tags": profile.tags,
        }
        # The timeline server may still be booting (compose/k8s startup
        # order is not guaranteed), so retry with backoff before giving up.
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{timeline_url}/v1/a2a/agents", json=payload, timeout=10
                )
                # 4xx/5xx (e.g. server still booting) must retry too.
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == 2:
                    print(f"Could not register agent {profile.id}: {exc}", flush=True)
                else:
                    time.sleep(2**attempt)
