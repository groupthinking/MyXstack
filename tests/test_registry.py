import requests

import agents.registry as registry


def test_register_team_posts_each_member_with_expected_payload(monkeypatch):
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(registry.requests, "post", fake_post)
    monkeypatch.setenv("TIMELINE_API_URL", "http://timeline.test")

    registry.register_team()

    team = registry.get_team()
    assert len(calls) == len(team)
    for call, member in zip(calls, team):
        assert call["url"] == "http://timeline.test/v1/a2a/agents"
        payload = call["json"]
        assert payload["id"] == member.profile.id
        assert payload["name"] == member.profile.name
        assert payload["status"] == "online"
        assert payload["kind"] == member.profile.kind
        assert payload["tags"] == member.profile.tags
        if member.profile.handle:
            assert payload["endpoint"] == f"x:@{member.profile.handle}"
        else:
            assert payload["endpoint"] == "x"


def test_register_team_retries_on_failure_then_succeeds(monkeypatch):
    attempts = {"count": 0}

    class FakeResponse:
        def raise_for_status(self):
            return None

    def fake_post(url, json, timeout):
        attempts["count"] += 1
        if attempts["count"] < 2:
            raise requests.ConnectionError("still booting")
        return FakeResponse()

    sleeps = []
    single_member = [registry.get_team()[0]]
    monkeypatch.setattr(registry.requests, "post", fake_post)
    monkeypatch.setattr(registry.time, "sleep", lambda seconds: sleeps.append(seconds))
    monkeypatch.setattr(registry, "get_team", lambda: single_member)

    registry.register_team()

    assert attempts["count"] == 2
    assert sleeps == [1]  # 2**0 backoff before the second attempt


def test_register_team_gives_up_after_three_failed_attempts(monkeypatch, capsys):
    def fake_post(url, json, timeout):
        raise requests.ConnectionError("down")

    monkeypatch.setattr(registry.requests, "post", fake_post)
    monkeypatch.setattr(registry.time, "sleep", lambda seconds: None)
    single_member = [registry.get_team()[0]]
    monkeypatch.setattr(registry, "get_team", lambda: single_member)

    registry.register_team()  # must not raise

    captured = capsys.readouterr()
    assert f"Could not register agent {single_member[0].profile.id}" in captured.out


def test_register_team_retries_on_http_error_status(monkeypatch):
    class FailResponse:
        def raise_for_status(self):
            raise requests.HTTPError("503")

    class OkResponse:
        def raise_for_status(self):
            return None

    responses = [FailResponse(), OkResponse()]

    def fake_post(url, json, timeout):
        return responses.pop(0)

    single_member = [registry.get_team()[0]]
    monkeypatch.setattr(registry.requests, "post", fake_post)
    monkeypatch.setattr(registry.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(registry, "get_team", lambda: single_member)

    registry.register_team()  # should retry past the HTTP error and succeed

    assert responses == []


def test_get_team_returns_cached_singleton():
    first = registry.get_team()
    second = registry.get_team()
    assert first is second