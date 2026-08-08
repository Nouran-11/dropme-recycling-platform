.DEFAULT_GOAL := help
.PHONY: help up down logs ps build require-env test lint fmt migrate seed backup restore verify-restore deploy-local rollback-local

COMPOSE ?= docker compose

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

require-env: ## Fail fast if .env is missing (never auto-created — it holds secrets)
	@test -f .env || { echo "ERROR: .env is missing. Copy .env.example to .env and set POSTGRES_PASSWORD and API_KEY."; exit 1; }

up: require-env ## Build and start the full local stack, blocking until healthy
	$(COMPOSE) up -d --build --wait

down: ## Stop the stack and remove containers
	$(COMPOSE) down --remove-orphans

logs: ## Tail stack logs
	$(COMPOSE) logs -f

ps: ## Show container status
	$(COMPOSE) ps

build: require-env ## Build images
	$(COMPOSE) build

test: ## Run the test suite (needs Postgres+Redis on localhost)
	cd app && uv run pytest -q

lint: ## Run ruff check
	cd app && uv run ruff check .

fmt: ## Format with ruff
	cd app && uv run ruff format .

migrate: require-env ## Run alembic upgrade head as a one-shot
	$(COMPOSE) run --rm migrate

seed: ## Seed ~200 sample events into the running stack
	$(COMPOSE) exec -T postgres sh -c 'psql -v ON_ERROR_STOP=1 -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"' < ops/seed.sql

backup: ## Create a verified database backup (stack must be up)
	$(COMPOSE) exec -T backup bash /ops/backup.sh

restore: ## Restore the newest backup into the scratch database
	$(COMPOSE) exec -T backup bash /ops/restore.sh

verify-restore: ## Compare source vs restored scratch database (PASS/FAIL)
	$(COMPOSE) exec -T backup bash /ops/verify_restore.sh

deploy-local: ## Deploy to local k3d cluster
	@echo "TODO(phase 7)"

rollback-local: ## Roll back the local deployment
	@echo "TODO(phase 7)"
