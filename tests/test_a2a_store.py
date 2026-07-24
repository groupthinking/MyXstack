import a2a_store


def _isolate_store(monkeypatch, tmp_path):
    monkeypatch.setattr(a2a_store, "A2A_STORE_PATH", tmp_path / "a2a_store.json")


def test_register_agent_defaults_kind_to_agent_when_missing(monkeypatch, tmp_path):
    _isolate_store(monkeypatch, tmp_path)
    agent = a2a_store.register_agent({"id": "no-kind", "name": "No Kind"})
    assert agent["kind"] == "agent"


def test_register_agent_defaults_kind_to_agent_when_invalid(monkeypatch, tmp_path):
    _isolate_store(monkeypatch, tmp_path)
    agent = a2a_store.register_agent({"id": "bad-kind", "name": "Bad Kind", "kind": "robot"})
    assert agent["kind"] == "agent"


def test_register_agent_defaults_kind_to_agent_when_null(monkeypatch, tmp_path):
    _isolate_store(monkeypatch, tmp_path)
    agent = a2a_store.register_agent({"id": "null-kind", "name": "Null Kind", "kind": None})
    assert agent["kind"] == "agent"


def test_register_agent_accepts_bot_kind(monkeypatch, tmp_path):
    _isolate_store(monkeypatch, tmp_path)
    agent = a2a_store.register_agent({"id": "tickerbot", "name": "Ticker Bot", "kind": "bot"})
    assert agent["kind"] == "bot"


def test_register_agent_new_agent_is_appended_once(monkeypatch, tmp_path):
    _isolate_store(monkeypatch, tmp_path)
    a2a_store.register_agent({"id": "one-off", "name": "One Off"})
    agents = a2a_store.list_agents()
    matches = [a for a in agents if a.get("id") == "one-off"]
    assert len(matches) == 1


def test_register_agent_reregistration_updates_mutable_fields(monkeypatch, tmp_path):
    _isolate_store(monkeypatch, tmp_path)
    first = a2a_store.register_agent(
        {
            "id": "custom-member",
            "name": "Custom",
            "description": "old",
            "status": "offline",
            "endpoint": "old-endpoint",
            "tags": ["old"],
        }
    )
    assert first["kind"] == "agent"

    second = a2a_store.register_agent(
        {
            "id": "custom-member",
            "name": "Custom Renamed",
            "description": "new",
            "status": "online",
            "endpoint": "x:@custom",
            "kind": "bot",
            "tags": ["x", "social"],
        }
    )

    assert second["name"] == "Custom Renamed"
    assert second["description"] == "new"
    assert second["status"] == "online"
    assert second["endpoint"] == "x:@custom"
    assert second["kind"] == "bot"
    assert second["tags"] == ["x", "social"]
    # Identity fields are preserved across re-registration.
    assert second["id"] == "custom-member"
    assert second["created_at"] == first["created_at"]

    # No duplicate entry was created.
    agents = a2a_store.list_agents()
    assert len([a for a in agents if a.get("id") == "custom-member"]) == 1


def test_register_agent_reregistration_backfills_seeded_agent_without_kind(monkeypatch, tmp_path):
    """The seeded default x-agent record predates the "kind" field entirely
    (see DEFAULT_AGENTS); re-registering it must normalize kind in place."""
    _isolate_store(monkeypatch, tmp_path)
    seeded = a2a_store.get_agent("x-agent")
    assert "kind" not in seeded

    updated = a2a_store.register_agent({"id": "x-agent", "name": "X Agent", "kind": "agent"})

    assert updated["kind"] == "agent"
    assert updated["id"] == "x-agent"
    agents = a2a_store.list_agents()
    assert len([a for a in agents if a.get("id") == "x-agent"]) == 1


def test_register_agent_reregistration_normalizes_invalid_kind(monkeypatch, tmp_path):
    _isolate_store(monkeypatch, tmp_path)
    a2a_store.register_agent({"id": "flaky", "name": "Flaky", "kind": "bot"})
    updated = a2a_store.register_agent({"id": "flaky", "name": "Flaky", "kind": "not-a-kind"})
    assert updated["kind"] == "agent"


def test_register_agent_reregistration_returns_the_stored_object(monkeypatch, tmp_path):
    _isolate_store(monkeypatch, tmp_path)
    a2a_store.register_agent({"id": "dup", "name": "Dup"})
    updated = a2a_store.register_agent({"id": "dup", "name": "Dup 2"})
    stored = a2a_store.get_agent("dup")
    assert stored["name"] == "Dup 2"
    assert updated == stored