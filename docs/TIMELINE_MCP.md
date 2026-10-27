# Authenticated read-only timeline MCP

This is a separate service, not the X OpenAPI MCP server and not the WebMCP browser bridge.
It reads the existing `timeline_items` table. It does not import the approval server,
create tables, change card state, call X, or dispatch work. No OpenAI API key is required.

## Tools and contract

| Tool | Input | Result |
|---|---|---|
| `get_current_user` | `{}` | Server-mapped timeline account and read-only permission |
| `list_timeline_items` | Optional `status`, `limit` (1–50), `offset` (0–10000) | Owned card summaries and bounded pagination |
| `get_timeline_item` | Required `item_id` (1–128 characters) | Owned card text and link to the existing human approval screen |

No tool accepts `user_id`. Unknown tools and extra arguments are rejected.
A nonexistent card and another account's card both return `Item not found`.
Raw `metadata`, `actions`, and `blocks` are not returned. Card body is limited to
20,000 characters with `body_truncated` indicating truncation. User-authored card text
can itself contain sensitive information; this is not a secret-redaction service.
Treat card text as untrusted data, not instructions. The approval link opens the
existing screen; it is not a new item-selection/deep-link feature and does not sign
anyone into that separate operator UI.

## Authentication boundary

This application is an OAuth **resource server**, not an identity provider. An external
authorization server owns authorization-code + PKCE S256, sign-in, consent, client
registration, token issuance/refresh, and provider discovery. Configure that provider
for a dedicated resource audience equal to `TIMELINE_MCP_RESOURCE_URL`, RS256 access
tokens, and `timeline:read`. Configure the actual ChatGPT callback supplied by its
connection setup; do not invent or wildcard redirect URIs.

Every `/mcp` request validates issuer, audience, RSA signature, `exp`, `iat`, optional
`nbf`, and scopes. Missing/invalid tokens receive 401; insufficient scope receives 403.
Discovery is available at `/.well-known/oauth-protected-resource/mcp` and the root
protected-resource metadata URL. There is no shared-bearer or anonymous bypass.

Identity mapping is operator-controlled JSON: provider `sub` -> existing timeline
`user_id`. It is one-to-one and issuer-specific. It never defaults to `default`, and
it never trusts a user/account claim chosen by the caller. This is suitable for an
explicitly provisioned private pilot, not self-service multi-tenant onboarding.

JWT verification is offline after JWKS retrieval (cached up to 300 seconds); it does
not introspect individual-token revocation. Use short-lived access tokens. Removing
an account mapping and restarting this service blocks that account. Provider-side
revocation, key rotation, and actual consent must be checked before release.

## Required configuration

Use `timeline-mcp.env.example`. All six variables are required:

- `TIMELINE_MCP_ISSUER_URL`: exact trusted provider issuer.
- `TIMELINE_MCP_JWKS_URL`: trusted provider signing-key URL.
- `TIMELINE_MCP_RESOURCE_URL`: public HTTPS origin plus `/mcp`.
- `TIMELINE_MCP_APPROVAL_URL`: existing HTTPS approval UI without credentials/query.
- `TIMELINE_MCP_DATABASE_URL`: existing SQLite file or PostgreSQL database.
- `TIMELINE_MCP_USER_MAP`: explicit JSON mapping of approved provider subjects.

Store actual mappings and database credentials in deployment secrets, not source or
browser bundles. The template intentionally contains no usable defaults. No issuer,
production subject mapping, database credentials, or public endpoint is provisioned
by these source files.

## Database access

Use a **dedicated SELECT-only PostgreSQL login** that can read `timeline_items`, not
an owner/superuser. Connections also set `SET TRANSACTION READ ONLY` and a five-second
statement timeout. Legacy `postgres://` URLs are normalized to the psycopg3 driver.
SQLite opens an existing file with `mode=ro` plus `PRAGMA query_only=ON`; missing files
fail rather than creating an empty database. Mount SQLite read-only and ensure the
container UID 10001 can read it and any required SQLite WAL files.

The adapter never performs schema migrations. Maintain schema through the existing
application before starting the reader. Ownership is enforced in both list and
single-card SQL predicates. This does not fix or replace the legacy operator UI's
shared-token authorization; do not expose that UI as a multi-tenant consumer portal.

## Run

```sh
python3 -m venv /tmp/myxstack-timeline-mcp-venv
. /tmp/myxstack-timeline-mcp-venv/bin/activate
python -m pip install -r requirements-timeline-mcp.txt
# Supply the six required variables through your environment/secrets manager.
uvicorn timeline_mcp:create_app --factory --host 0.0.0.0 --port 8090
```

Or build the isolated non-root container:

```sh
docker build -f Dockerfile.timeline-mcp -t myxstack-timeline-mcp .
# Provide a private env file and any read-only SQLite mount; never commit that file.
docker run --rm --env-file /secure/path/timeline-mcp.env -p 8090:8090 myxstack-timeline-mcp
```

Publish behind TLS at the configured resource URL. Preserve the public Host header;
only the configured Host/Origin is accepted. `/health` is a process-health probe, not
proof that the IdP, database, or ChatGPT connection is healthy. Apply edge rate limits
and concurrency limits, especially to token/JWKS requests, before public exposure.
Do not enable production routing until the acceptance checks below pass.

## Verification

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_timeline_mcp*.py -v
python -m pytest -q
python -m flake8 .
```

The dedicated `Read-only Timeline MCP` workflow installs the official SDK, exercises
HTTP discovery/401/403, exact tool listing, account isolation and unknown-tool rejection,
and starts a real uvicorn TCP server for initialize/list/call. The schema test imports
the existing repository table definition; the full CI PostgreSQL job supplies
`TEST_DATABASE_URL` to verify PostgreSQL ownership and write refusal too. Tests sign real RSA JWTs
and use an actual temporary database. Provider key retrieval uses test keys; no test
claims a live third-party OAuth or ChatGPT consent flow. CI exports JUnit, logs, source
hashes and installed dependency versions.

Before connecting privately in ChatGPT, demonstrate the deployed metadata and provider
configuration, complete real sign-in/consent, and call all three tools with a provisioned
account. Prove missing/expired credentials and another account's card remain denied.
A successful code test is not a production connection. No merge/deployment is implicit.

## References

- https://developers.openai.com/plugins/build/auth
- https://developers.openai.com/plugins/deploy/connect-chatgpt
- https://py.sdk.modelcontextprotocol.io/migration/
- https://github.com/modelcontextprotocol/python-sdk/tree/v2.3.0
