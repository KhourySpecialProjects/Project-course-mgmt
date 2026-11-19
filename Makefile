# Shortcuts for common tasks. Run `make help` to list them.
#
# Every target is just a docker compose command, shown next to it, so you can
# also copy the command and run it directly (handy on Windows without `make`).

.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help
help: ## Show this list
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# --- Running the stack -------------------------------------------------------

.env:
	cp .env.example .env
	@echo "Created .env from .env.example. Review it, then run 'make up' again."

.PHONY: up
up: .env ## Build and start everything (web, api, db) in the background
	$(COMPOSE) up --build -d
	@echo ""
	@echo "  Web app:   http://localhost:3000"
	@echo "  API docs:  http://localhost:8000/api/docs"
	@echo ""

.PHONY: down
down: ## Stop everything (your data is kept)
	$(COMPOSE) down

.PHONY: logs
logs: ## Follow the logs of all containers (Ctrl+C to stop)
	$(COMPOSE) logs -f

.PHONY: ps
ps: ## Show which containers are running
	$(COMPOSE) ps

# --- Quality checks ----------------------------------------------------------

.PHONY: test
test: ## Run the API tests
	$(COMPOSE) exec api pytest

.PHONY: lint
lint: ## Lint + type-check both api and web
	$(COMPOSE) exec api ruff check .
	$(COMPOSE) exec api ruff format --check .
	$(COMPOSE) exec api mypy app tests
	$(COMPOSE) exec web npm run lint
	$(COMPOSE) exec web npm run typecheck
	$(COMPOSE) exec web npm run format:check

.PHONY: format
format: ## Auto-format all code
	$(COMPOSE) exec api ruff check --fix .
	$(COMPOSE) exec api ruff format .
	$(COMPOSE) exec web npm run format

.PHONY: check
check: lint test ## Everything CI runs: lint, type-check, and tests

# --- Database ----------------------------------------------------------------

.PHONY: migrate
migrate: ## Apply pending database migrations
	$(COMPOSE) exec api alembic upgrade head

.PHONY: migration
migration: ## Create a migration from model changes: make migration m="add courses table"
	@test -n "$(m)" || (echo 'Usage: make migration m="describe the change"' && exit 1)
	$(COMPOSE) exec api alembic revision --autogenerate -m "$(m)"

.PHONY: psql
psql: ## Open a SQL prompt on the development database
	$(COMPOSE) exec db sh -c 'psql -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"'

.PHONY: reset-db
reset-db: ## DANGER: delete ALL local data and start with an empty database
	@printf "This deletes all local database data. Type 'yes' to continue: " && read ans && [ "$$ans" = "yes" ]
	$(COMPOSE) down -v
	$(COMPOSE) up --build -d

# --- Users -------------------------------------------------------------------

.PHONY: reset-password
reset-password: ## Set a new password for a user: make reset-password email=admin@example.com
	@test -n "$(email)" || (echo 'Usage: make reset-password email=someone@example.com' && exit 1)
	$(COMPOSE) exec api python -m app.cli reset-password "$(email)"
