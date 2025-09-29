ALEMBIC_CONFIG = -c /code/migrations/alembic.ini

.PHONY: help build run migrate upgrade revision

help:  ## Show available commands and their descriptions
	@echo "Makefile for FastAPI project with Alembic and Ruff"
	@echo ""
	@echo "Usage:"
	@echo "  make build                 Build the Docker images"
	@echo "  make run                   Run the Docker containers"
	@echo "  make migration-upgrade     Apply all pending Alembic migrations (upgrade to head)"
	@echo "  make migration-autogenerate msg=\"message\"   Create a new Alembic migration with autogeneration"
	@echo "  make migration-downgrade   Revert the last applied Alembic migration"
	@echo "  make run-ruff              Run Ruff formatter and linter inside Docker"
	@echo ""

build:  ## Build images
	docker compose build

run:  ## Run Docker containers
	docker compose up

migration-upgrade:  ## Upgrade migration
	docker compose run --rm  web alembic $(ALEMBIC_CONFIG) upgrade head

migration-autogenerate:  ## Create new migration
	@if [ -z "$(msg)" ]; then \
		echo "Error: Please provide a message for the new migration using 'msg' variable, e.g. make migration-autogenerate msg=\"add new table\""; \
		exit 1; \
	fi
	docker compose run --rm  web alembic $(ALEMBIC_CONFIG) revision --autogenerate -m "$(msg)"

migration-downgrade:  ## Downgrade migration
	docker compose run --rm  web alembic $(ALEMBIC_CONFIG) downgrade -1

run-ruff:  ## Run linter
	docker run --pull always -v .:/io --rm ghcr.io/astral-sh/ruff:latest format . \
	&& docker run --pull always -v .:/io --rm ghcr.io/astral-sh/ruff:latest check --fix .
