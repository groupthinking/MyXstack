"""Security and data tests use real RSA signatures and a temporary SQLite DB."""
import json
import time
from dataclasses import replace
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

import timeline_mcp as tm


@pytest.fixture
def settings(tmp_path):
    return tm.Settings(
        issuer_url="https://issuer.example.test/",
        jwks_url="https://issuer.example.test/.well-known/jwks.json",
        resource_url="https://mcp.example.test/mcp",
        approval_url="https://timeline.example.test/ui/",
        database_url=f"sqlite:///{tmp_path / 'timeline.db'}",
        user_map={"subject-a": "alice", "subject-b": "bob"},
    )


@pytest.fixture
def keys():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(keys, settings, **overrides):
    now = int(time.time())
    claims = dict(iss=settings.issuer_url, aud=settings.resource_url,
                  sub="subject-a", exp=now + 300, iat=now - 1,
                  scope=tm.READ_SCOPE, client_id="test-client")
    claims.update(overrides)
    return jwt.encode(claims, keys, algorithm="RS256", headers={"kid": "test-key"})


@pytest.fixture
def authorizer(settings, keys):
    # Only JWKS retrieval is substituted. JWT signature/claims are really checked.
    client = SimpleNamespace(get_signing_key_from_jwt=lambda _: SimpleNamespace(key=keys.public_key()))
    return tm.JWTAuthorizer(settings, jwks_client=client)


@pytest.fixture
def reader(settings):
    engine = create_engine(settings.database_url)
    with engine.begin() as conn:
        conn.execute(text("""CREATE TABLE timeline_items (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
            body TEXT NOT NULL, status TEXT NOT NULL, posted_by TEXT NOT NULL,
            created_at DATETIME NOT NULL, updated_at DATETIME,
            dispatched_action TEXT NOT NULL DEFAULT '',
            actions JSON, metadata JSON, blocks JSON)"""))
        for ident, owner, status in [("a1", "alice", "unread"),
                                     ("a2", "alice", "read"), ("b1", "bob", "unread")]:
            conn.execute(
                text("""INSERT INTO timeline_items
                    (id,user_id,title,body,status,posted_by,created_at,actions,metadata,blocks)
                    VALUES (:id,:owner,:title,:body,:status,'agent',:created,:actions,:metadata,'[]')"""),
                dict(id=ident, owner=owner, title=f"Card {ident}", body=f"Body {ident}",
                     status=status, created="2026-01-01 00:00:00",
                     actions='[{"id":"approve","label":"Approve"}]',
                     metadata='{"api_token":"MUST_NOT_LEAK"}'),
            )
    engine.dispose()
    instance = tm.TimelineReader(settings)
    yield instance
    instance.close()


def test_empty_environment_fails_closed(monkeypatch):
    for key in list(__import__('os').environ):
        if key.startswith("TIMELINE_MCP_"):
            monkeypatch.delenv(key)
    with pytest.raises(ValueError):
        tm.Settings.from_env()


@pytest.mark.parametrize("field,value", [
    ("issuer_url", "http://issuer.test/"),
    ("jwks_url", "http://issuer.test/jwks"),
    ("resource_url", "https://mcp.test/wrong"),
    ("resource_url", "https://user:password@mcp.test/mcp"),
    ("approval_url", "https://timeline.test/ui/?token=secret"),
    ("issuer_url", "https://issuer.test/#fragment"),
    ("user_map", {}), ("user_map", {"subject-a": ""}),
    ("user_map", {"subject-a": "alice", "subject-b": "alice"}),
    ("database_url", ""),
])
def test_invalid_configuration_is_rejected(settings, field, value):
    with pytest.raises(ValueError):
        replace(settings, **{field: value})


def test_signed_token_resolves_server_owned_identity(authorizer, keys, settings):
    identity = authorizer.verify(make_token(keys, settings, user_id="bob"))
    assert identity.user_id == "alice"
    assert identity.subject == "subject-a"
    assert identity.scopes == (tm.READ_SCOPE,)


@pytest.mark.parametrize("override", [
    {"iss": "https://evil.test/"}, {"aud": "some-other-api"},
    {"exp": 1}, {"nbf": 9999999999}, {"iat": 9999999999},
    {"sub": "unmapped"}, {"sub": ""}, {"sub": 5},
    {"scope": []}, {"exp": None}, {"exp": True},
])
def test_invalid_tokens_are_rejected(authorizer, keys, settings, override):
    assert authorizer.verify(make_token(keys, settings, **override)) is None


@pytest.mark.parametrize("claim", ["sub", "exp", "iat", "iss", "aud"])
def test_required_claims_are_rejected_when_absent(authorizer, keys, settings, claim):
    payload = jwt.decode(make_token(keys, settings), options={"verify_signature": False})
    payload.pop(claim)
    token = jwt.encode(payload, keys, algorithm="RS256", headers={"kid": "test-key"})
    assert authorizer.verify(token) is None


def test_forged_signature_is_rejected(authorizer, settings):
    foreign = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert authorizer.verify(make_token(foreign, settings)) is None


@pytest.mark.parametrize("token", ["invalid", "", "x" * 17000])
def test_malformed_token_is_rejected(authorizer, token):
    assert authorizer.verify(token) is None


def test_unsigned_token_is_rejected(authorizer, settings):
    token = jwt.encode({"sub": "subject-a", "aud": settings.resource_url}, key="", algorithm="none")
    assert authorizer.verify(token) is None


def test_jwks_failure_fails_closed(settings, keys):
    calls = []

    def unavailable(token):
        calls.append(token)
        raise jwt.PyJWKClientConnectionError("offline")

    auth = tm.JWTAuthorizer(settings, jwks_client=SimpleNamespace(get_signing_key_from_jwt=unavailable))
    signed = make_token(keys, settings)
    assert auth.verify(signed) is None
    assert calls == [signed]


def test_list_is_scoped_and_bounded(reader):
    page = reader.list_items("alice", limit=1)
    assert [item["id"] for item in page["items"]] == ["a2"]
    assert page["next_offset"] == 1
    second = reader.list_items("alice", limit=1, offset=1)
    assert [item["id"] for item in second["items"]] == ["a1"]
    assert second["next_offset"] is None
    assert reader.list_items("alice", status="unread")["items"][0]["id"] == "a1"


def test_other_user_and_missing_item_are_indistinguishable(reader):
    for ident in ["b1", "missing", "' OR 1=1 --"]:
        with pytest.raises(tm.ItemNotFound, match="Item not found"):
            reader.get_item("alice", ident)


def test_only_allowed_fields_are_returned(reader):
    item = reader.get_item("alice", "a1")
    assert item["body"] == "Body a1"
    assert item["approval_url"] == "https://timeline.example.test/ui/"
    assert not {"actions", "metadata", "user_id", "blocks"} & item.keys()
    assert "MUST_NOT_LEAK" not in json.dumps(item)


def test_database_connection_refuses_writes(reader):
    with reader.engine.connect() as conn:
        with pytest.raises(DBAPIError):
            conn.execute(text("DELETE FROM timeline_items"))
    assert len(reader.list_items("alice")["items"]) == 2


@pytest.mark.parametrize("arguments", [
    {"limit": 0}, {"limit": 51}, {"offset": -1}, {"offset": 10001},
    {"limit": True}, {"status": "x" * 65},
])
def test_reader_rejects_unbounded_inputs(reader, arguments):
    with pytest.raises(ValueError):
        reader.list_items("alice", **arguments)


def test_tool_allowlist_is_exact():
    assert set(tm.TOOL_SCHEMAS) == {"get_current_user", "list_timeline_items", "get_timeline_item"}
    for schema in tm.TOOL_SCHEMAS.values():
        assert schema["additionalProperties"] is False
        assert "user_id" not in schema["properties"]


def test_real_jwks_selection_and_unknown_key_fail_closed(settings, keys, monkeypatch):
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(keys.public_key()))
    jwk.update(kid="test-key", use="sig", alg="RS256")
    client = jwt.PyJWKClient(settings.jwks_url)
    monkeypatch.setattr(client, "fetch_data", lambda: {"keys": [jwk]})
    auth = tm.JWTAuthorizer(settings, jwks_client=client)
    signed = make_token(keys, settings)
    assert auth.verify(signed).user_id == "alice"
    payload = jwt.decode(signed, options={"verify_signature": False})
    unknown = jwt.encode(payload, keys, algorithm="RS256", headers={"kid": "unknown"})
    assert auth.verify(unknown) is None


def test_missing_database_does_not_create_a_file(settings):
    path = __import__("pathlib").Path(settings.database_url.removeprefix("sqlite:///"))
    assert not path.exists()
    with pytest.raises(FileNotFoundError):
        tm.TimelineReader(settings)
    assert not path.exists()


def test_identity_map_cannot_be_modified(settings):
    with pytest.raises(TypeError):
        settings.user_map["subject-c"] = "alice"
