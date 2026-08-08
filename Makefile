.DEFAULT_GOAL := help
.PHONY: help up down logs ps build test lint fmt migrate seed backup restore verify-restore deploy-local rollback-local

help: ## List available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

up: ## Start the full local stack
	@echo "TODO(phase 2)"

down: ## Stop the stack and remove containers
	@echo "TODO(phase 2)"

logs: ## Tail stack logs
	@echo "TODO(phase 2)"

ps: ## Show container status
	@echo "TODO(phase 2)"

build: ## Build images
	@echo "TODO(phase 2)"

test: ## Run the test suite
	@echo "TODO(phase 3)"

lint: ## Run ruff check
	@echo "TODO(phase 3)"

fmt: ## Run ruff format
	@echo "TODO(phase 3)"

migrate: ## Run alembic upgrade head
	@echo "TODO(phase 1)"

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
