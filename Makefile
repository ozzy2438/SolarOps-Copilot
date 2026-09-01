.PHONY: help up down logs install test lint typecheck schemas verify

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

up:  ## Bring up the full local stack (postgres+pgvector, redis, espocrm, api, worker)
	docker compose up -d --build

down:  ## Tear the stack down
	docker compose down -v

logs:  ## Follow API logs
	docker compose logs -f api

install:  ## Install the package and dev dependencies into the current environment
	pip install -e ".[dev]"

test:  ## Run the test suite
	pytest -q

lint:  ## Lint
	ruff check voltdesk tests scripts

typecheck:  ## Type-check
	mypy voltdesk

schemas:  ## Regenerate JSON Schema exports from the Pydantic contracts
	python scripts/export_schemas.py

verify: lint typecheck test  ## Everything a phase must pass before reporting done
	python scripts/export_schemas.py --check
	@echo "verify: OK"
