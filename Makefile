.PHONY: run test coverage lint docker
run:
	.venv/bin/uvicorn app.main:app --reload
test:
	.venv/bin/pytest
coverage:
	.venv/bin/pytest --cov=app --cov-report=term-missing --cov-fail-under=80
lint:
	.venv/bin/ruff check .
docker:
	docker compose build
