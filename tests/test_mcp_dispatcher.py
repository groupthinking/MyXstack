from types import SimpleNamespace

import pytest
import requests

import mcp_dispatcher


class _StopLoop(Exception):
    """Sentinel used to break out of main()'s while-True loop in tests."""


class _StubMember:
    def __init__(self, agent_id, result=None, raise_exc=None):
        self.profile = SimpleNamespace(id=agent_id)
        self._result = result
        self._raise_exc = raise_exc
        self.calls = []

    def execute_action(self, item, action):
        self.calls.append((item, action))
        if self._raise_exc:
            raise self._raise_exc
        return self._result


def _prepare_common_mocks(monkeypatch, message, updates, sent):
    monkeypatch.setattr(mcp_dispatcher, "ensure_agent_registered", lambda agent_id: None)
    monkeypatch.setattr(mcp_dispatcher, "load_last_seen", lambda: None)
    monkeypatch.setattr(mcp_dispatcher, "save_last_seen", lambda value: None)
    monkeypatch.setattr(mcp_dispatcher, "get_messages", lambda agent_id: [message])
    monkeypatch.setattr(
        mcp_dispatcher, "update_timeline_item", lambda item_id, u: updates.append((item_id, u))
    )
    monkeypatch.setattr(
        mcp_dispatcher,
        "send_message",
        lambda from_agent, to, content, metadata: sent.append(
            {"from_agent": from_agent, "to": to, "content": content, "metadata": metadata}
        ),
    )

    def fake_sleep(seconds):
        raise _StopLoop()

    monkeypatch.setattr(mcp_dispatcher.time, "sleep", fake_sleep)


# ── get_timeline_item ─────────────────────────────────────────────


def test_get_timeline_item_returns_json_on_200(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {"id": "abc", "metadata": {"agent_id": "tradedesk"}}

    monkeypatch.setattr(mcp_dispatcher.requests, "get", lambda url, timeout: FakeResponse())
    item = mcp_dispatcher.get_timeline_item("abc")
    assert item == {"id": "abc", "metadata": {"agent_id": "tradedesk"}}


def test_get_timeline_item_returns_none_on_non_200(monkeypatch):
    class FakeResponse:
        status_code = 404

        def json(self):
            raise AssertionError("should not be called")

    monkeypatch.setattr(mcp_dispatcher.requests, "get", lambda url, timeout: FakeResponse())
    assert mcp_dispatcher.get_timeline_item("missing") is None


def test_get_timeline_item_returns_none_on_request_exception(monkeypatch):
    def fake_get(url, timeout):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(mcp_dispatcher.requests, "get", fake_get)
    assert mcp_dispatcher.get_timeline_item("abc") is None


def test_get_timeline_item_returns_none_on_invalid_json(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            raise ValueError("bad json")

    monkeypatch.setattr(mcp_dispatcher.requests, "get", lambda url, timeout: FakeResponse())
    assert mcp_dispatcher.get_timeline_item("abc") is None


# ── main() dispatch logic ─────────────────────────────────────────


def test_main_executes_action_via_owning_member(monkeypatch):
    message = {
        "from": "timeline-ui",
        "created_at": "2024-01-01T00:00:00+00:00",
        "type": "timeline_action",
        "metadata": {"timeline_item_id": "item-1", "action": "Approve"},
    }
    item = {"id": "item-1", "metadata": {"agent_id": "tradedesk"}}
    updates, sent = [], []
    _prepare_common_mocks(monkeypatch, message, updates, sent)
    monkeypatch.setattr(mcp_dispatcher, "get_timeline_item", lambda item_id: item)

    stub = _StubMember("tradedesk", result="executed trade")
    monkeypatch.setattr(mcp_dispatcher, "find_member", lambda agent_id: stub)

    with pytest.raises(_StopLoop):
        mcp_dispatcher.main()

    assert stub.calls == [(item, "Approve")]
    assert updates == [("item-1", {"mcp_result": "executed trade", "processed_action": "Approve"})]
    assert sent[0]["content"] == "executed trade"


def test_main_fails_closed_when_owner_returns_none(monkeypatch):
    message = {
        "from": "timeline-ui",
        "created_at": "2024-01-01T00:00:00+00:00",
        "type": "timeline_action",
        "metadata": {"timeline_item_id": "item-2", "action": "Approve"},
    }
    item = {"id": "item-2", "metadata": {"agent_id": "tickerbot"}}
    updates, sent = [], []
    _prepare_common_mocks(monkeypatch, message, updates, sent)
    monkeypatch.setattr(mcp_dispatcher, "get_timeline_item", lambda item_id: item)

    stub = _StubMember("tickerbot", result=None)
    monkeypatch.setattr(mcp_dispatcher, "find_member", lambda agent_id: stub)
    monkeypatch.setattr(
        mcp_dispatcher, "call_grok", lambda prompt: pytest.fail("must not use generic fallback")
    )

    with pytest.raises(_StopLoop):
        mcp_dispatcher.main()

    result = updates[0][1]["mcp_result"]
    assert "not handled by agent tickerbot" in result
    assert "nothing executed" in result
    # The owner was found (no exception), so execution_failed stays False
    # and the action is still marked processed even though nothing ran -
    # this prevents an unhandled action from being retried forever.
    assert updates[0][1]["processed_action"] == "Approve"


def test_main_fails_closed_when_owner_raises(monkeypatch):
    message = {
        "from": "timeline-ui",
        "created_at": "2024-01-01T00:00:00+00:00",
        "type": "timeline_action",
        "metadata": {"timeline_item_id": "item-3", "action": "Approve"},
    }
    item = {"id": "item-3", "metadata": {"agent_id": "tradedesk"}}
    updates, sent = [], []
    _prepare_common_mocks(monkeypatch, message, updates, sent)
    monkeypatch.setattr(mcp_dispatcher, "get_timeline_item", lambda item_id: item)

    stub = _StubMember("tradedesk", raise_exc=RuntimeError("broker offline"))
    monkeypatch.setattr(mcp_dispatcher, "find_member", lambda agent_id: stub)

    with pytest.raises(_StopLoop):
        mcp_dispatcher.main()

    result = updates[0][1]["mcp_result"]
    assert "broker offline" in result
    assert "processed_action" not in updates[0][1]


def test_main_fails_closed_when_item_cannot_be_loaded(monkeypatch):
    message = {
        "from": "timeline-ui",
        "created_at": "2024-01-01T00:00:00+00:00",
        "type": "timeline_action",
        "metadata": {"timeline_item_id": "missing-item", "action": "Approve"},
    }
    updates, sent = [], []
    _prepare_common_mocks(monkeypatch, message, updates, sent)
    monkeypatch.setattr(mcp_dispatcher, "get_timeline_item", lambda item_id: None)
    monkeypatch.setattr(
        mcp_dispatcher, "find_member", lambda agent_id: pytest.fail("ownership must not be resolved")
    )

    with pytest.raises(_StopLoop):
        mcp_dispatcher.main()

    item_id, update = updates[0]
    assert item_id == "missing-item"
    assert "Could not load timeline item missing-item" in update["mcp_result"]
    assert "processed_action" not in update


def test_main_falls_back_to_generic_grok_when_no_owner(monkeypatch):
    message = {
        "from": "timeline-ui",
        "created_at": "2024-01-01T00:00:00+00:00",
        "type": "timeline_action",
        "metadata": {"timeline_item_id": "item-4", "action": "Snooze"},
    }
    item = {"id": "item-4", "metadata": {}}  # no agent_id -> unowned card
    updates, sent = [], []
    _prepare_common_mocks(monkeypatch, message, updates, sent)
    monkeypatch.setattr(mcp_dispatcher, "get_timeline_item", lambda item_id: item)
    monkeypatch.setattr(mcp_dispatcher, "find_member", lambda agent_id: None)
    monkeypatch.setattr(mcp_dispatcher, "call_grok", lambda prompt: "generic status update")

    with pytest.raises(_StopLoop):
        mcp_dispatcher.main()

    assert updates == [
        ("item-4", {"mcp_result": "generic status update", "processed_action": "Snooze"})
    ]


def test_main_does_not_mark_processed_when_xai_key_missing(monkeypatch):
    message = {
        "from": "timeline-ui",
        "created_at": "2024-01-01T00:00:00+00:00",
        "type": "timeline_action",
        "metadata": {"timeline_item_id": "item-5", "action": "Approve"},
    }
    item = {"id": "item-5", "metadata": {}}
    updates, sent = [], []
    _prepare_common_mocks(monkeypatch, message, updates, sent)
    monkeypatch.setattr(mcp_dispatcher, "get_timeline_item", lambda item_id: item)
    monkeypatch.setattr(mcp_dispatcher, "call_grok", lambda prompt: "Missing XAI_API_KEY.")

    with pytest.raises(_StopLoop):
        mcp_dispatcher.main()

    item_id, update = updates[0]
    assert update["mcp_result"] == "Missing XAI_API_KEY."
    assert "processed_action" not in update


def test_main_skips_already_processed_action_without_reexecuting(monkeypatch):
    message = {
        "from": "timeline-ui",
        "created_at": "2024-01-01T00:00:00+00:00",
        "type": "timeline_action",
        "metadata": {"timeline_item_id": "item-6", "action": "Reject"},
    }
    item = {
        "id": "item-6",
        "metadata": {"agent_id": "tradedesk", "processed_action": "Approve"},
    }
    updates, sent = [], []
    _prepare_common_mocks(monkeypatch, message, updates, sent)
    monkeypatch.setattr(mcp_dispatcher, "get_timeline_item", lambda item_id: item)
    monkeypatch.setattr(
        mcp_dispatcher, "find_member", lambda agent_id: pytest.fail("must not execute a replay")
    )

    with pytest.raises(_StopLoop):
        mcp_dispatcher.main()

    # Skipped entirely: no timeline update and no A2A message sent.
    assert updates == []
    assert sent == []


def test_main_ignores_messages_older_than_last_seen(monkeypatch):
    message = {
        "from": "timeline-ui",
        "created_at": "2024-01-01T00:00:00+00:00",
        "type": "timeline_action",
        "metadata": {"timeline_item_id": "item-7", "action": "Approve"},
    }
    updates, sent = [], []
    _prepare_common_mocks(monkeypatch, message, updates, sent)
    monkeypatch.setattr(
        mcp_dispatcher, "load_last_seen", lambda: "2024-06-01T00:00:00+00:00"
    )
    monkeypatch.setattr(
        mcp_dispatcher, "get_timeline_item", lambda item_id: pytest.fail("stale message processed")
    )

    with pytest.raises(_StopLoop):
        mcp_dispatcher.main()

    assert updates == []
    assert sent == []


def test_main_ignores_non_timeline_action_messages(monkeypatch):
    message = {
        "from": "timeline-ui",
        "created_at": "2024-01-01T00:00:00+00:00",
        "type": "mcp_result",
        "metadata": {"timeline_item_id": "item-8", "action": "Approve"},
    }
    updates, sent = [], []
    _prepare_common_mocks(monkeypatch, message, updates, sent)
    monkeypatch.setattr(
        mcp_dispatcher, "get_timeline_item", lambda item_id: pytest.fail("should not be fetched")
    )

    with pytest.raises(_StopLoop):
        mcp_dispatcher.main()

    assert updates == []
    assert sent == []