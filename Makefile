.PHONY: help up down destroy logs install materialise-generated golden-set test lint typecheck schemas verify

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-12s %s\n", $$1, $$2}'

up:  ## Bring up the full local stack (postgres+pgvector, redis, espocrm, api, worker)
	docker compose up -d --build

down:  ## Stop the stack. Volumes and their data are KEPT.
	docker compose down

destroy:  ## Stop the stack AND DELETE its volumes (pgdata, espodata). Irreversible.
	@echo "This deletes the voltdesk postgres and espocrm volumes and everything in them."
	@echo "Only VoltDesk's own volumes - nothing else on this machine is touched."
	@printf "Type 'destroy' to confirm: " && read ans && [ "$$ans" = "destroy" ]
	docker compose down -v

logs:  ## Follow API logs
	docker compose logs -f api

install:  ## Install the package and dev dependencies into the current environment
	pip install -e ".[dev]"

materialise-generated:  ## Materialise deterministic synthetic inputs used by the golden set
	python scripts/materialise_generated.py

golden-set: materialise-generated  ## Rebuild the golden records after materialising inputs
	python scripts/build_golden_set.py

test: materialise-generated  ## Run the test suite
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
