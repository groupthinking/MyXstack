# Authenticated read-only timeline MCP implementation plan

Goal: implement the already-approved three-tool private MyXstack integration, separately from PR #174.
Base: groupthinking/MyXstack main 95264e606f546c39deb4830748594fde695b5de9.
Design: independent Python Streamable HTTP MCP resource server using the official MCP SDK. Established external OAuth issuer; RS256/JWKS verification; configured subject-to-existing-timeline-user mapping; SQL reads with ownership predicates and read-only transactions. No model calls, X credentials, dispatch imports, approval routes, migrations, or anonymous fallback.

1. tests/test_timeline_mcp.py: red tests for fail-closed config, real RSA token validation, identity mapping, pagination, ownership and database write denial.
2. timeline_mcp.py: implement validated settings, JWT authorizer, bounded SQL reader, strict three-tool dispatch and SDK HTTP application factory.
3. tests/test_timeline_mcp_http.py: official SDK transport, discovery, authentication failures, forged/expired tokens, cross-user and mutation denial, unchanged records, actual MCP client round trip.
4. requirements-timeline-mcp.txt, Dockerfile.timeline-mcp, timeline-mcp.env.example and docs/TIMELINE_MCP.md: isolated service configuration and accurate deployment/consent boundaries.
5. Persist to a separate branch and PR, execute remote integration/full-project CI if local package downloads remain blocked, fetch logs and compare committed blob hashes.

Completion boundary: implemented and passing code is separate from hosted deployment/provider enrollment/private ChatGPT consent, which require actual configuration and live evidence. No merge or production changes are authorized implicitly by a build.
