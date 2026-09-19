from agents.base import AgentReply, MentionContext
from agents.registry import build_team, route_mention
from agents.team.hermes import HermesAgent, pick_owner


def test_pick_owner_trade():
    assert pick_owner("@MyXstack $TSLA buy 100") == "tradedesk"
    assert pick_owner("buy $NVDA 5") == "tradedesk"


def test_pick_owner_shopping():
    assert pick_owner("@MyXstack find trail running shoes under $150") == "shopping"


def test_pick_owner_research_question():
    assert pick_owner("@MyXstack why is $NVDA down?") == "research"


def test_pick_owner_bare_cashtag():
    assert pick_owner("@MyXstack $BTC") == "tickerbot"


def test_pick_owner_goal_stays_with_hermes():
    assert pick_owner("@MyXstack stand up a 48-hour LinkedIn probe") is None
    assert pick_owner("@MyXstack open a pod for Northwater") is None


def test_untagged_mention_routes_to_hermes():
    member = route_mention(MentionContext(text="@MyXstack what's the weather?"))
    assert member.profile.id == "hermes"
    assert member.profile.fallback is True
    assert member.profile.kind == "orchestrator"


def test_tagged_hermes_routes_to_hermes():
    member = route_mention(MentionContext(text="@MyXstack @Hermes own this goal"))
    assert member.profile.id == "hermes"


def test_tagged_specialist_still_wins():
    member = route_mention(MentionContext(text="@MyXstack @Research why is $NVDA down?"))
    assert member.profile.id == "research"


def test_exactly_one_fallback():
    fallbacks = [m.profile.id for m in build_team() if m.profile.fallback]
    assert fallbacks == ["hermes"]


def test_hermes_brief_is_not_a_generic_dump(monkeypatch):
    captured = {}

    def fake_grok(prompt: str) -> str:
        captured["prompt"] = prompt
        return "Goal: probe\nUnits:\n1. Harper — landscape — done: cited brief"

    monkeypatch.setattr("agents.team.hermes.grok_chat", fake_grok)
    reply = HermesAgent().handle_mention(
        MentionContext(text="@MyXstack stand up a 48-hour LinkedIn probe", mention_id=9)
    )
    assert isinstance(reply, AgentReply)
    assert "Hermes has the goal" in reply.text
    assert reply.card is not None
    assert reply.card["metadata"]["agent_id"] == "hermes"
    assert reply.card["actions"] == []
    assert "autonomous X agent bot" not in captured["prompt"]
    assert "never do the specialist" in captured["prompt"].lower()


def test_hermes_handoff_preserves_specialist_owner(monkeypatch):
    monkeypatch.setattr("agents.team.hermes.send_a2a_message", lambda *a, **k: True)
    monkeypatch.setenv("TRADEDESK_USE_GROK", "0")
    # Rebuild after env so the TradeDesk constructed inside get_team is stale;
    # call handle_mention on a fresh Hermes against the live team.
    reply = HermesAgent().handle_mention(
        MentionContext(text="@MyXstack $TSLA buy 100", mention_id=3)
    )
    assert reply.card is not None
    assert reply.card["metadata"]["agent_id"] == "tradedesk"
    assert reply.card["metadata"]["routed_by"] == "hermes"
    assert reply.text.startswith("Hermes → @")
