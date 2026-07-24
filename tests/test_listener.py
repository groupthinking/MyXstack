from types import SimpleNamespace

import pytest
import requests

import listener
from agents.base import AgentReply, MentionContext


class _StubMember:
    def __init__(self, agent_id="stub-agent", kind="agent"):
        self.profile = SimpleNamespace(id=agent_id, kind=kind)

    def handle_mention(self, ctx):
        raise NotImplementedError("override in test")


def _mention(**overrides):
    defaults = dict(id=1, text="@MyXstack hello", author_id=2, conversation_id=3)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_push_timeline_card_posts_expected_payload(monkeypatch):
    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            calls["raise_for_status_called"] = True

    def fake_post(url, json, timeout):
        calls["url"] = url
        calls["json"] = json
        return FakeResponse()

    monkeypatch.setattr(listener.requests, "post", fake_post)
    monkeypatch.setenv("TIMELINE_API_URL", "http://timeline.test")
    monkeypatch.setenv("TIMELINE_USER_ID", "user-1")

    listener.push_timeline_card(
        {"title": "T", "body": "B", "actions": ["Approve"], "metadata": {"k": "v"}},
        posted_by="tradedesk",
    )

    assert calls["url"] == "http://timeline.test/v1/timeline/items"
    assert calls["json"] == {
        "user_id": "user-1",
        "title": "T",
        "body": "B",
        "posted_by": "tradedesk",
        "actions": ["Approve"],
        "metadata": {"k": "v"},
    }
    assert calls["raise_for_status_called"] is True


def test_push_timeline_card_defaults_missing_fields(monkeypatch):
    calls = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        calls["json"] = json
        return FakeResponse()

    monkeypatch.setattr(listener.requests, "post", fake_post)

    listener.push_timeline_card({}, posted_by="x-agent")

    assert calls["json"]["title"] == "Untitled"
    assert calls["json"]["body"] == ""
    assert calls["json"]["actions"] == []
    assert calls["json"]["metadata"] == {}


def test_push_timeline_card_raises_on_http_error(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            raise requests.HTTPError("500")

    monkeypatch.setattr(listener.requests, "post", lambda url, json, timeout: FakeResponse())

    with pytest.raises(requests.HTTPError):
        listener.push_timeline_card({"title": "t"}, posted_by="x-agent")


def test_process_mention_success_pushes_card_then_replies(monkeypatch):
    member = _StubMember("tradedesk")
    monkeypatch.setattr(listener, "route_mention", lambda ctx: member)
    monkeypatch.setattr(
        member, "handle_mention", lambda ctx: AgentReply(text="ok", card={"title": "card"})
    )

    pushed = []
    monkeypatch.setattr(
        listener, "push_timeline_card", lambda card, posted_by: pushed.append((card, posted_by))
    )

    tweets = []

    class FakeClient:
        def create_tweet(self, text, in_reply_to_tweet_id):
            tweets.append((text, in_reply_to_tweet_id))

    result = listener.process_mention(FakeClient(), _mention())

    assert result is True
    assert pushed == [({"title": "card"}, "tradedesk")]
    assert tweets == [("ok", 1)]


def test_process_mention_without_card_skips_card_push(monkeypatch):
    member = _StubMember("research")
    monkeypatch.setattr(listener, "route_mention", lambda ctx: member)
    monkeypatch.setattr(member, "handle_mention", lambda ctx: AgentReply(text="reply only"))

    pushed = []
    monkeypatch.setattr(
        listener, "push_timeline_card", lambda card, posted_by: pushed.append((card, posted_by))
    )

    class FakeClient:
        def create_tweet(self, text, in_reply_to_tweet_id):
            pass

    result = listener.process_mention(FakeClient(), _mention())
    assert result is True
    assert pushed == []


def test_process_mention_truncates_reply_to_280_chars(monkeypatch):
    member = _StubMember("research")
    monkeypatch.setattr(listener, "route_mention", lambda ctx: member)
    long_text = "x" * 400
    monkeypatch.setattr(member, "handle_mention", lambda ctx: AgentReply(text=long_text))

    tweets = []

    class FakeClient:
        def create_tweet(self, text, in_reply_to_tweet_id):
            tweets.append(text)

    listener.process_mention(FakeClient(), _mention())
    assert len(tweets[0]) == 280


def test_process_mention_handle_mention_exception_dead_letters_card(monkeypatch):
    member = _StubMember("tradedesk")
    monkeypatch.setattr(listener, "route_mention", lambda ctx: member)

    def raise_error(ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr(member, "handle_mention", raise_error)

    pushed = []
    monkeypatch.setattr(
        listener, "push_timeline_card", lambda card, posted_by: pushed.append((card, posted_by))
    )

    class FakeClient:
        def create_tweet(self, text, in_reply_to_tweet_id):
            raise AssertionError("should not be called")

    result = listener.process_mention(FakeClient(), _mention(id=99))

    assert result is True
    assert len(pushed) == 1
    card, posted_by = pushed[0]
    assert posted_by == "tradedesk"
    assert "boom" in card["body"]
    assert card["metadata"]["error"] == "boom"
    assert card["metadata"]["mention_id"] == 99


def test_process_mention_returns_false_when_dead_letter_card_also_fails(monkeypatch):
    member = _StubMember("tradedesk")
    monkeypatch.setattr(listener, "route_mention", lambda ctx: member)

    def raise_error(ctx):
        raise RuntimeError("boom")

    monkeypatch.setattr(member, "handle_mention", raise_error)

    def failing_push(card, posted_by):
        raise requests.HTTPError("still down")

    monkeypatch.setattr(listener, "push_timeline_card", failing_push)

    class FakeClient:
        def create_tweet(self, text, in_reply_to_tweet_id):
            raise AssertionError("should not be called")

    result = listener.process_mention(FakeClient(), _mention())
    assert result is False


def test_process_mention_returns_false_when_card_push_fails(monkeypatch):
    member = _StubMember("tradedesk")
    monkeypatch.setattr(listener, "route_mention", lambda ctx: member)
    monkeypatch.setattr(
        member, "handle_mention", lambda ctx: AgentReply(text="ok", card={"title": "card"})
    )

    def failing_push(card, posted_by):
        raise requests.HTTPError("down")

    monkeypatch.setattr(listener, "push_timeline_card", failing_push)

    class FakeClient:
        def create_tweet(self, text, in_reply_to_tweet_id):
            raise AssertionError("should not be called when the card failed to push")

    result = listener.process_mention(FakeClient(), _mention())
    assert result is False


def test_process_mention_create_tweet_failure_with_no_prior_card_holds_watermark(monkeypatch):
    member = _StubMember("research")
    monkeypatch.setattr(listener, "route_mention", lambda ctx: member)
    monkeypatch.setattr(member, "handle_mention", lambda ctx: AgentReply(text="reply only"))

    def failing_push(card, posted_by):
        raise requests.HTTPError("down")

    monkeypatch.setattr(listener, "push_timeline_card", failing_push)

    class FakeClient:
        def create_tweet(self, text, in_reply_to_tweet_id):
            raise RuntimeError("x api down")

    result = listener.process_mention(FakeClient(), _mention())
    assert result is False


def test_process_mention_create_tweet_failure_with_prior_card_does_not_hold_watermark(monkeypatch):
    member = _StubMember("tradedesk")
    monkeypatch.setattr(listener, "route_mention", lambda ctx: member)
    monkeypatch.setattr(
        member, "handle_mention", lambda ctx: AgentReply(text="ok", card={"title": "card"})
    )

    push_calls = []

    def push_side_effect(card, posted_by):
        push_calls.append(card)
        if len(push_calls) > 1:
            raise requests.HTTPError("recovery push also fails")

    monkeypatch.setattr(listener, "push_timeline_card", push_side_effect)

    class FakeClient:
        def create_tweet(self, text, in_reply_to_tweet_id):
            raise RuntimeError("x api down")

    result = listener.process_mention(FakeClient(), _mention())
    # The proposal card already landed before the reply failed, so the
    # mention must not be retried even though the recovery card also failed.
    assert result is True