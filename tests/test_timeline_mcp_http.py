"""Real SDK HTTP protocol tests. Only provider JWKS retrieval uses fixture keys."""
import json
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from starlette.testclient import TestClient

import timeline_mcp as tm
import test_timeline_mcp as fixtures

# Reuse the real-signature/database fixtures without shadowing imported names.
settings = fixtures.settings
keys = fixtures.keys
reader = fixtures.reader
authorizer = fixtures.authorizer
make_token = fixtures.make_token


@pytest.fixture
def app(settings, reader, authorizer):
    return tm.create_app(settings, reader=reader, authorizer=authorizer)


@pytest.fixture
def client(app):
    with TestClient(app, base_url="https://mcp.example.test") as client:
        yield client


def rpc(client, token, method, params=None, **headers):
    return client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/json, text/event-stream",
                 "MCP-Protocol-Version": "2025-11-25", **headers},
    )


def call(client, token, name, arguments=None):
    response = rpc(client, token, "tools/call", {"name": name, "arguments": arguments or {}})
    assert response.status_code == 200, response.text
    return response.json()["result"]


def test_resource_metadata_is_public_and_exact(client, settings):
    for path in ["/.well-known/oauth-protected-resource/mcp", "/.well-known/oauth-protected-resource"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.json()["resource"] == settings.resource_url
        assert response.json()["authorization_servers"] == [settings.issuer_url]
        assert response.json()["scopes_supported"] == [tm.READ_SCOPE]
    assert client.get("/health").status_code == 200


def test_unauthenticated_discovery_is_challenged(client):
    response = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert response.status_code == 401
    expected = 'resource_metadata="https://mcp.example.test/.well-known/oauth-protected-resource/mcp"'
    assert expected in response.headers["www-authenticate"]
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("claims,status", [
    ({"scope": ""}, 403), ({"scope": "timeline:write"}, 403),
    ({"exp": 1}, 401), ({"aud": "other-api"}, 401),
    ({"iss": "https://other-issuer.test/"}, 401), ({"nbf": 9999999999}, 401),
    ({"sub": "unmapped"}, 401),
])
def test_http_auth_failures(client, keys, settings, claims, status):
    response = rpc(client, make_token(keys, settings, **claims), "tools/list")
    assert response.status_code == status
    assert "www-authenticate" in response.headers


def test_exact_tools_and_read_only_annotations(client, keys, settings):
    response = rpc(client, make_token(keys, settings), "tools/list")
    assert response.status_code == 200, response.text
    tools = response.json()["result"]["tools"]
    assert {t["name"] for t in tools} == set(tm.TOOL_SCHEMAS)
    for tool in tools:
        assert tool["annotations"]["readOnlyHint"] is True
        assert tool["annotations"]["destructiveHint"] is False
        assert tool["inputSchema"]["additionalProperties"] is False
        assert tool["_meta"]["securitySchemes"] == [{"type": "oauth2", "scopes": [tm.READ_SCOPE]}]


def test_three_tool_workflow_is_read_only(client, keys, settings, reader):
    token = make_token(keys, settings)
    before = reader.get_item("alice", "a1")
    user = call(client, token, "get_current_user")["structuredContent"]
    assert user == {"user_id": "alice", "permissions": [tm.READ_SCOPE], "read_only": True}
    items = call(client, token, "list_timeline_items")["structuredContent"]["items"]
    assert {item["id"] for item in items} == {"a1", "a2"}
    item = call(client, token, "get_timeline_item", {"item_id": "a1"})["structuredContent"]
    assert item["id"] == "a1" and item["approval_url"] == settings.approval_url
    assert "MUST_NOT_LEAK" not in json.dumps(item)
    assert reader.get_item("alice", "a1") == before


def test_each_request_gets_its_own_identity(client, keys, settings):
    alice = make_token(keys, settings)
    bob = make_token(keys, settings, sub="subject-b")
    for token, expected in [(alice, "alice"), (bob, "bob"), (alice, "alice")]:
        assert call(client, token, "get_current_user")["structuredContent"]["user_id"] == expected
    assert call(client, alice, "get_timeline_item", {"item_id": "b1"})["isError"]
    assert call(client, bob, "get_timeline_item", {"item_id": "a1"})["isError"]


@pytest.mark.parametrize("name,args", [
    ("approve", {"item_id": "a1"}), ("createTweet", {"text": "no"}),
    ("list_timeline_items", {"user_id": "bob"}), ("get_current_user", {"user_id": "bob"}),
    ("get_timeline_item", {"item_id": "a1", "action": "Approve"}),
    ("list_timeline_items", {"limit": 100000}), ("list_timeline_items", {"limit": True}),
])
def test_mutations_and_extra_arguments_are_rejected(client, keys, settings, name, args, reader):
    before = reader.get_item("alice", "a1")
    result = call(client, make_token(keys, settings), name, args)
    assert result["isError"] is True
    assert reader.get_item("alice", "a1") == before


def test_untrusted_origin_and_host_fail(client, keys, settings):
    token = make_token(keys, settings)
    for headers in [{"Origin": "https://evil.test"}, {"Host": "evil.test"}]:
        response = rpc(client, token, "tools/list", **headers)
        assert response.status_code in (403, 421), response.text


def test_no_approval_api_is_mounted(client):
    assert client.patch("/v1/timeline/items/a1", json={"action_id": "approve"}).status_code == 404


def test_real_http_socket_initialize_list_and_call(app, keys, settings):
    """Real uvicorn socket; no monkeypatched MCP transport or tool responses."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="on"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert server.started, "MCP server failed to start"
        with httpx.Client(
            base_url=f"http://127.0.0.1:{port}", headers={"Host": "mcp.example.test"}
        ) as remote:
            token = make_token(keys, settings)
            initialized = rpc(remote, token, "initialize", {
                "protocolVersion": "2025-11-25", "capabilities": {},
                "clientInfo": {"name": "myxstack-build-verifier", "version": "1.0"},
            })
            assert initialized.status_code == 200, initialized.text
            assert initialized.json()["result"]["serverInfo"]["name"] == "myxstack-timeline"
            assert rpc(remote, token, "tools/list").status_code == 200
            result = call(remote, token, "get_timeline_item", {"item_id": "a1"})
            assert result["structuredContent"]["id"] == "a1"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
    assert not thread.is_alive()
