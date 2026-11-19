# MyXstack: Sites, WebMCP, ChatGPT plugins and the OpenAI API

**Scope:** One optional, read-only WebMCP bridge is implemented for the existing timeline UI. This change does NOT deploy or publish a ChatGPT Site, connect a ChatGPT plugin, call the OpenAI API, or authorize commerce/trades.

## Layers and responsibilities

| Layer | Responsibility | Verified implementation boundary |
| --- | --- | --- |
| Site / frontend | Human-facing UI; can be hosted independently or built as a ChatGPT Site | This repo already serves the timeline UI at /ui. ChatGPT Sites is an optional distinct product, not automatically a deployment of this repo. |
| WebMCP | Expose page-context actions to compatible browser agents | The /ui page conditionally registers three read/navigation tools using document.modelContext. No write tools are registered. |
| ChatGPT plugin | Package server MCP tools, reusable skills and optional MCP Apps UI for ChatGPT/Codex | This repo includes an existing MCP server for X API operations. Plugin packaging, safe allowlisting, authentication, installation, review and publication are not yet verified. |
| OpenAI API | Optional model inference for server-owned features | Not needed for ChatGPT to reason with a plugin; not implemented here. The repo's existing Grok/xAI logic remains separate. API keys must be kept on the server. |
| Shared application API | Centralize domain logic, validation, authorization, idempotency | Existing timeline /v1 APIs remain the only place that dispatches card actions. WebMCP calls existing frontend logic for refresh. |
| Storage / integrations | Persistent data and external effects | Existing SQL timeline storage and X API service. Shopify, Stripe, subscriptions and fulfillment require separate adapters and explicit authorization. |
| Identity / observability | Per-user access, audit, permissions, rate limits, tracing | Some existing bearer-token and atomic action protections exist. Production hardening remains necessary. |

## Browser WebMCP interface

- myxstack_list_visible_cards(): Returns ids, titles, statuses, poster and available action labels for cards already rendered on the selected timeline. No new account fetch; does not read hidden card bodies or credentials.
- myxstack_focus_card(card_id): Focuses and scrolls to a visible card by id. It never presses a button.
- myxstack_refresh_timeline(): Uses the existing UI refresh method and its existing authorization to reload the selected timeline.

The browser agents' ability to discover tools depends on compatible browsers and agent implementations. The page uses feature detection; normal UI remains functional when WebMCP is absent.

**Safety:** Action labels are information, not consent. Timeline approvals can cause consequential side effects, including trading and purchasing tasks. No browser tool can approve or reject a card. Do not expose write tools until there are explicit per-action user permissions, authenticated identities, robust idempotency, audit logs, and browser-agent security review.

## Production gates, none claimed complete by this change

1. Run JavaScript test: node --test tests/test_webmcp.cjs.
2. Run repo CI: make ci. The WebMCP test should be included in the repeatable CI gate.
3. Manually verify Chrome/Edge or ChatGPT Desktop browser-agent discovery in a WebMCP-compatible release; experimental feature and origin-trial conditions vary.
4. Reconcile existing timeline bearer-token/localStorage security. The deployment token fail-closed heuristic recognizes Railway/Kubernetes only; other public hosts need manual verification.
5. Review backend MCP server tool allowlists and authorization before connecting to a private ChatGPT plugin. Never expose raw write-capable X API tools to untrusted plugin users on one shared service token.
6. Use MCP Inspector to test the actual deployed HTTPS /mcp endpoint, then connect a private plugin only with approved auth and permissions; publish only after review.
7. Add an OpenAI API backend adapter only for explicitly identified model-powered business workflows, with server-side key storage, usage budgets, rate limits and cost tracking.
8. Verify audit logs, tenant isolation, no unintended side effects, production smoke tests and rollbacks before releasing.

## Official references

- https://github.com/webmachinelearning/webmcp
- https://github.com/webmachinelearning/webmcp/blob/main/implementation-status.md
- https://developers.openai.com/plugins
- https://developers.openai.com/plugins/build/mcp-server
- https://developers.openai.com/plugins/build/app-quickstart
- https://help.openai.com/en/articles/20001339-creating-and-using-chatgpt-sites
- https://platform.openai.com/docs/overview
