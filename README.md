# GitHub Issues Gateway

Stage 1 establishes the contract and runtime foundation for a FastAPI gateway that
will manage GitHub issues, comments, and signed webhook deliveries. GitHub calls,
webhook processing, and persistence workflows are deliberately **not implemented**
yet; non-health endpoints return a typed `501 Not Implemented` response.

The canonical HTTP contract is [`openapi.yaml`](openapi.yaml). See
[`AGENTS.md`](AGENTS.md) for reproducible setup, lint, and test commands.

## Configuration

Copy `.env.example` to `.env` and replace every placeholder. Never commit `.env`.
Configuration is read from these fixed names:

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | Runtime environment (`development`, `test`, or `production`) |
| `LOG_LEVEL` | Python logging level |
| `DATABASE_URL` | SQLite URL |
| `GITHUB_TOKEN` | GitHub token reserved for a later stage |
| `GITHUB_OWNER` | Repository owner |
| `GITHUB_REPO` | Repository name |
| `GITHUB_WEBHOOK_SECRET` | Secret reserved for signature verification |

Run locally with `uvicorn app.main:app --reload` and inspect `/docs` or `/healthz`.
