# Contributor guide

This repository is currently limited to Stage 1 (foundation and API contracts).
Do not add live GitHub calls, real credentials, persistence workflows, or completed
issue/comment/webhook behavior until a later stage explicitly requests it.

## Exact commands

Run from the repository root with Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/ruff check .
.venv/bin/pytest
```

Start the development server with:

```bash
.venv/bin/uvicorn app.main:app --reload
```

Never commit `.env`, credentials, database files, logs, or virtual environments.
Keep `openapi.yaml` synchronized with route and shared-model changes.
