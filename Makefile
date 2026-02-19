ALEMBIC_CONFIG = -c alembic.ini
COMPOSE_FILE = docker-compose.yml

.PHONY: help build run run-detached stop clean migrate-upgrade migrate-autogenerate migrate-downgrade lint lint-fix format shell logs

help:  ## Show available commands
	@echo "Spry Backend"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  make %-25s %s\n", $$1, $$2}'
	@echo ""

build:  ## Build Docker images
	docker compose -f $(COMPOSE_FILE) build

run:  ## Run Docker containers
	docker compose -f $(COMPOSE_FILE) up

run-detached:  ## Run Docker containers in detached mode
	docker compose -f $(COMPOSE_FILE) up -d

stop:  ## Stop Docker containers
	docker compose -f $(COMPOSE_FILE) down

clean:  ## Remove containers, volumes, and images
	docker compose -f $(COMPOSE_FILE) down -v --rmi local

logs:  ## Follow Docker container logs
	docker compose -f $(COMPOSE_FILE) logs -f

migrate-upgrade:  ## Upgrade migration to head
	docker compose -f $(COMPOSE_FILE) run --rm web alembic $(ALEMBIC_CONFIG) upgrade head

migrate-autogenerate:  ## Create new migration (msg="description")
	@if [ -z "$(msg)" ]; then \
		echo "Error: Please provide a message for the new migration using 'msg' variable, e.g. make migrate-autogenerate msg=\"add new table\""; \
		exit 1; \
	fi
	docker compose -f $(COMPOSE_FILE) run --rm web alembic $(ALEMBIC_CONFIG) revision --autogenerate -m "$(msg)"

migrate-downgrade:  ## Downgrade migration by one step
	docker compose -f $(COMPOSE_FILE) run --rm web alembic $(ALEMBIC_CONFIG) downgrade -1

lint:  ## Run Ruff linter
	docker run -v $(PWD):/io --rm ghcr.io/astral-sh/ruff:latest check src/ migrations/

format:  ## Run Ruff formatter
	docker run -v $(PWD):/io --rm ghcr.io/astral-sh/ruff:latest format src/ migrations/

lint-fix:  ## Run Ruff linter with auto-fix
	docker run -v $(PWD):/io --rm ghcr.io/astral-sh/ruff:latest check --fix src/ migrations/

shell:  ## Open a shell in the web container
	docker compose -f $(COMPOSE_FILE) run --rm web /bin/bash
