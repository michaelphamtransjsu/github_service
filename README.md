# GitHub Issues Gateway

A FastAPI gateway for one GitHub repository, with signed and idempotent webhook intake. Automated
tests use mocked HTTP responses; no live repository or real secret is required.

## Setup

Python 3.12 is required. Create `.env` locally (it is ignored) from `.env.example`, then run:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
make lint test coverage
make run
```

Set `GITHUB_TOKEN`, `GITHUB_OWNER`, and `GITHUB_REPO` only when you intentionally want live API
access. Set a strong `GITHUB_WEBHOOK_SECRET` before accepting webhooks. The default SQLite file is
local; Docker Compose stores it in a named volume. Do not expose `/events` publicly without adding
authentication.

## Examples

```bash
curl http://localhost:8000/issues?state=open
curl -X POST http://localhost:8000/issues -H 'Content-Type: application/json' \
  -d '{"title":"Documentation gap","labels":["docs"]}'
curl -X PATCH http://localhost:8000/issues/12 -H 'Content-Type: application/json' \
  -d '{"state":"closed"}'
curl -X POST http://localhost:8000/issues/12/comments -H 'Content-Type: application/json' \
  -d '{"body":"Fixed in the next release"}'
curl http://localhost:8000/events
```

GitHub must send `X-GitHub-Event`, `X-GitHub-Delivery`, and `X-Hub-Signature-256` headers to
`POST /webhook`. Generate the signature over the exact raw request bytes; never paste secrets into
shell history in a real environment. Supported events are `ping`, `issues`, and `issue_comment`.

## Operations

`make docker` builds the image; `docker compose up --build` runs it. The checked-in
[`openapi.yaml`](openapi.yaml) is the canonical OpenAPI 3.1 contract. See [`DESIGN.md`](DESIGN.md)
for tradeoffs. Live GitHub and real webhook delivery tests are intentionally manual and must only
be performed by an authorized user with their own credentials.
