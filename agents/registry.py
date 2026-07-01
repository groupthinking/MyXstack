"""Team roster, @handle routing, and A2A registration."""

import os
import threading
import time
from typing import List, Optional

import requests

from agents.base import MentionContext, TeamMember
from agents.router import find_target


def build_team() -> List[TeamMember]:
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
    if not agent_id:
        return None
    for member in get_team():
        if member.profile.id == agent_id:
            return member
    return None


def register_team() -> None:
    """Register every team member in the timeline server's A2A registry."""
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
                requests.post(f"{timeline_url}/v1/a2a/agents", json=payload, timeout=10)
                break
            except requests.RequestException as exc:
                if attempt == 2:
                    print(f"Could not register agent {profile.id}: {exc}", flush=True)
                else:
                    time.sleep(2**attempt)
