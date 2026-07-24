import agents.team.shopping as shopping
from agents.base import MentionContext
from agents.team.shopping import ShoppingAgent


def test_handle_mention_offline_when_no_api_key(monkeypatch):
    monkeypatch.setattr(shopping, "grok_chat", lambda prompt: "")
    agent = ShoppingAgent()
    reply = agent.handle_mention(MentionContext(text="find shoes under $150"))
    assert "offline" in reply.text.lower()
    assert reply.card is None


def test_handle_mention_builds_card_with_purchase_actions(monkeypatch):
    monkeypatch.setattr(shopping, "grok_chat", lambda prompt: "1. Shoe A - $120")
    agent = ShoppingAgent()
    reply = agent.handle_mention(
        MentionContext(text="find trail shoes under $150", mention_id=1, author_id=2)
    )
    assert reply.card["title"] == "Shopping picks"
    assert reply.card["actions"] == ["Approve Purchase", "Reject"]
    metadata = reply.card["metadata"]
    assert metadata["agent_id"] == "shopping"
    assert metadata["action_type"] == "purchase"
    assert metadata["mention_id"] == 1
    assert metadata["author_id"] == 2


def test_handle_mention_extracts_budget_into_prompt(monkeypatch):
    captured = {}

    def fake_grok_chat(prompt):
        captured["prompt"] = prompt
        return "picks"

    monkeypatch.setattr(shopping, "grok_chat", fake_grok_chat)
    agent = ShoppingAgent()
    agent.handle_mention(MentionContext(text="find trail shoes under $150.50"))
    assert "with a budget of $150.50" in captured["prompt"]


def test_handle_mention_no_budget_phrase_omits_budget_from_prompt(monkeypatch):
    captured = {}

    def fake_grok_chat(prompt):
        captured["prompt"] = prompt
        return "picks"

    monkeypatch.setattr(shopping, "grok_chat", fake_grok_chat)
    agent = ShoppingAgent()
    agent.handle_mention(MentionContext(text="find me trail shoes"))
    assert "with a budget of" not in captured["prompt"]


def test_handle_mention_reply_is_truncated_for_x(monkeypatch):
    long_picks = "pick " * 100
    monkeypatch.setattr(shopping, "grok_chat", lambda prompt: long_picks)
    agent = ShoppingAgent()
    reply = agent.handle_mention(MentionContext(text="find shoes"))
    assert reply.text.endswith("… Full list on your timeline.")
    assert len(reply.text) <= 270


def test_execute_action_approve_records_intent_without_payment():
    agent = ShoppingAgent()
    item = {"metadata": {"action_type": "purchase"}}
    result = agent.execute_action(item, "Approve Purchase")
    assert "Purchase intent recorded" in result
    assert "no payment adapter" in result.lower() or "no payment" in result.lower()


def test_execute_action_approve_is_case_insensitive():
    agent = ShoppingAgent()
    item = {"metadata": {"action_type": "purchase"}}
    result = agent.execute_action(item, "approve")
    assert "Purchase intent recorded" in result


def test_execute_action_reject_closes_request():
    agent = ShoppingAgent()
    item = {"metadata": {"action_type": "purchase"}}
    result = agent.execute_action(item, "Reject")
    assert "closed" in result.lower()
    assert "nothing was purchased" in result.lower()


def test_execute_action_ignores_non_purchase_cards():
    agent = ShoppingAgent()
    item = {"metadata": {"action_type": "trade"}}
    assert agent.execute_action(item, "Approve") is None


def test_execute_action_missing_metadata_is_ignored():
    agent = ShoppingAgent()
    assert agent.execute_action({}, "Approve") is None


def test_execute_action_unknown_action_returns_none():
    agent = ShoppingAgent()
    item = {"metadata": {"action_type": "purchase"}}
    assert agent.execute_action(item, "Snooze") is None