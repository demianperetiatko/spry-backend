.PHONY: help run migrate upgrade downgrade revision

ALEMBIC_CONFIG = -c migrations/alembic.ini

help: ## Show list of available commands
	@echo "Available commands:"
	@echo "  make run        - Start the application"
	@echo "  make migrate    - Apply all migrations"
	@echo "  make upgrade    - Apply new migration"
	@echo "  make downgrade  - Revert the last migration"
	@echo "  make revision   - Create a new migration with a message"

migrate: ## Apply all migrations to the current database state
	source .env && alembic $(ALEMBIC_CONFIG) upgrade head

upgrade: ## Apply new migration
	source .env && alembic $(ALEMBIC_CONFIG) upgrade head

downgrade: ## Revert the last migration
	source .env && alembic $(ALEMBIC_CONFIG) downgrade -1

revision: ## Create a new migration with a message
	@if [ -z "$(msg)" ]; then \
		echo "Error: Please provide a message for the new migration using 'msg' variable, e.g. make revision msg=\"add new table\""; \
		exit 1; \
	fi
	source .env && alembic $(ALEMBIC_CONFIG) revision --autogenerate -m "$(msg)"

run: migrate ## Start the application
	source .env &&  python main.py