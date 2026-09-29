# MXS research warehouse — local foundation

This is an isolated, single-operator development CLI, not the complete hub or a
hosted multi-tenant service. It does not start the existing listener, fetch URLs,
publish posts, provision cloud resources, or modify the timeline database.
Python standard library only.

## Run

```sh
python -m warehouse --db /tmp/mxs-research.db init
python -m warehouse --db /tmp/mxs-research.db import warehouse/resources.json
python -m warehouse --db /tmp/mxs-research.db status
python -m warehouse --db /tmp/mxs-research.db evaluate VERSION_ID
# Explicit live evaluation; configure TYPESAFE_API_KEY securely first:
python -m warehouse --db /tmp/mxs-research.db evaluate VERSION_ID --live
python -m unittest discover -s tests/warehouse -v
```

Use a dedicated database path. Do not use the existing timeline database. Imports
are JSON arrays of platform, source, external_id, url, title, and text strings.
The included resources record the user's supplied links and their stated role;
they are not scraped documents or evidence of product features. Platform accounts
and Radar remain unconfigured. No secrets belong in import records.

Exact replays preserve item/version identity. Changed payloads create immutable
versions. An invalid record rejects the entire batch. URL queries and path case
are retained; fragments are removed. Each Jev attempt stores its request and
state hash before calling the provider. Missing credentials produce a pending
record; malformed responses, low confidence, and provider errors require review.
Accepted means category classification accepted, not publication approval.
Re-evaluation is explicit and creates another decision record, potentially another
billable request. There is no automatic retry or background execution.

## Template provenance

Decision routing is a Python adaptation of the confidence validation and bounded
provider-call pattern pulled from the user-approved Vercel template:
https://github.com/vercel-labs/jev-ai-sdk-form-router

Pinned source commit: `27ea469d15b5b26b922d9faacfdcffc13bf024bb`, `lib/router.ts`.
MIT notice retained in TEMPLATE-LICENSE. Unlike that template, this module sends
uncertainty to review rather than a generative fallback. Direct HTTP integration
follows https://docs.typesafe.ai/api (read 2026-09-28); Choice answers contain their
own confidence, unlike the AI SDK metadata shape. Raw judgments are persisted.
No live Jev calls were required for the offline tests; fixture responses are labeled.
The threshold is a starting policy requiring later calibration on real examples.

## Scope and next integration

Implemented: four SQLite tables, transactional manual import, immutable source
versions, recorded Jev classification attempts, CLI, tests. Local DB access uses
OS permissions; there is no network service or application authentication.

Not implemented: PostgreSQL adapter/migrations, Payload UI, object storage,
tracked-account polling, cursor-based scheduled ingestion, content extraction,
full product/brief/review schemas, multi-tenant authorization, agent execution,
and cloud hosting. Payload remains the proposed later editorial interface.
This deliberately small first slice replaces no existing repo services.

Before production: define retention and deletion behavior, enforce access control,
add migration management, test PostgreSQL if selected, and integrate real feeds.
Do not run `make run` to collect research: it starts the existing auto-reply listener.

## Offline verification

```sh
python -m unittest discover -s tests/warehouse -v
python -m flake8 warehouse tests/warehouse
```

The fixture suite checks replay/revision identity, transaction rollback, source
isolation, missing credentials (no provider call), provider errors without secret
logging, retained provider responses, confidence boundaries, and invalid answers.
