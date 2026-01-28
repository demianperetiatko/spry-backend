ALEMBIC_CONFIG = -c alembic.ini
COMPOSE_FILE = docker-compose.yml

.PHONY: help build run stop clean migrate-upgrade migrate-autogenerate migrate-downgrade lint format test

help:  ## Show available commands and their descriptions
	@echo "Makefile for Spry Backend v2 (FastAPI + SQLAlchemy 2.0)"
	@echo ""
	@echo "Usage:"
	@echo "  make build                 Build the Docker images"
	@echo "  make run                   Run the Docker containers"
	@echo "  make stop                  Stop the Docker containers"
	@echo "  make clean                 Remove containers and volumes"
	@echo "  make migrate-upgrade       Apply all pending Alembic migrations"
	@echo "  make migrate-autogenerate msg=\"message\"   Create a new Alembic migration"
	@echo "  make migrate-downgrade     Revert the last applied migration"
	@echo "  make lint                  Run Ruff linter"
	@echo "  make format                 Run Ruff formatter"
	@echo "  make shell                  Run shell"
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

migrate-upgrade:  ## Upgrade migration to head
	docker compose -f $(COMPOSE_FILE) run --rm web alembic $(ALEMBIC_CONFIG) upgrade head

migrate-autogenerate:  ## Create new migration with autogenerate
	@if [ -z "$(msg)" ]; then \
		echo "Error: Please provide a message for the new migration using 'msg' variable, e.g. make migrate-autogenerate msg=\"add new table\""; \
		exit 1; \
	fi
	docker compose -f $(COMPOSE_FILE) run --rm web alembic $(ALEMBIC_CONFIG) revision --autogenerate -m "$(msg)"

migrate-downgrade:  ## Downgrade migration by one step
	docker compose -f $(COMPOSE_FILE) run --rm web alembic $(ALEMBIC_CONFIG) downgrade -1

lint:  ## Run Ruff linter
	docker run --pull always -v $(PWD):/io --rm ghcr.io/astral-sh/ruff:latest check src/ migrations/

format:  ## Run Ruff formatter
	docker run --pull always -v $(PWD):/io --rm ghcr.io/astral-sh/ruff:latest format src/ migrations/

lint-fix:  ## Run Ruff linter with auto-fix
	docker run --pull always -v $(PWD):/io --rm ghcr.io/astral-sh/ruff:latest check --fix src/ migrations/

shell:  ## Open a shell in the web container
	docker compose -f $(COMPOSE_FILE) run --rm web /bin/bash

