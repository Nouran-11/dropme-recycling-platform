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

test: ## Run the test suite
	@echo "TODO(phase 3)"

lint: ## Run ruff check
	@echo "TODO(phase 3)"

fmt: ## Run ruff format
	@echo "TODO(phase 3)"

migrate: require-env ## Run alembic upgrade head as a one-shot
	$(COMPOSE) run --rm migrate

seed: ## Seed sample events
	@echo "TODO(phase 6)"

backup: ## Create a verified database backup
	@echo "TODO(phase 6)"

restore: ## Restore into the scratch database
	@echo "TODO(phase 6)"

verify-restore: ## Compare source vs restored database
	@echo "TODO(phase 6)"

deploy-local: ## Deploy to local k3d cluster
	@echo "TODO(phase 7)"

rollback-local: ## Roll back the local deployment
	@echo "TODO(phase 7)"
