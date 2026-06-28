.DEFAULT_GOAL := help
.PHONY: help sync run check lint type format test migrate revision downgrade

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-8s\033[0m %s\n", $$1, $$2}'

sync:  ## Install/sync dependencies from uv.lock
	uv sync

run:  ## Start dev server on :8000 with --reload
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

check: lint type  ## Run all static checks (lint + type)

lint:  ## Ruff lint
	uv run ruff check .

type:  ## ty type-check
	uv run ty check

format:  ## Auto-format with ruff
	uv run ruff format .

test:  ## Run the test suite
	uv run pytest

migrate:  ## Apply all pending migrations (alembic upgrade head)
	uv run alembic upgrade head

revision:  ## Generate a new migration (usage: make revision m="describe change")
	uv run alembic revision --autogenerate -m "$(m)"

downgrade:  ## Roll back one migration (alembic downgrade -1)
	uv run alembic downgrade -1
