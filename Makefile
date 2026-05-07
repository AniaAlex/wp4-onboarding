.PHONY: run
run: ## Build image and start container
	@docker-compose build
	@docker-compose up -d
	@echo "Django running at http://localhost:$$(grep '^WEB_PORT' .env 2>/dev/null | cut -d= -f2 | tr -d '[:space:]' || echo 8000)/"

.PHONY: stop
stop: ## Stop containers (data preserved)
	@docker-compose down

.PHONY: logs
logs: ## Tail Django logs
	@docker-compose logs -f django

.PHONY: sh
sh: ## Shell into the Django container
	@docker-compose exec django bash

.PHONY: shell
shell: ## Django interactive shell
	@docker-compose exec django python manage.py shell

.PHONY: migrations
migrations: ## Generate migrations from model changes
	@docker-compose exec django python manage.py makemigrations

.PHONY: migrate
migrate: ## Apply pending migrations
	@docker-compose exec django python manage.py migrate

.PHONY: createsuperuser
createsuperuser: ## Create Django admin (interactive)
	@docker-compose exec django python manage.py createsuperuser

.PHONY: seed
seed: ## Seed demo operator + 7 schemes
	@docker-compose exec django python manage.py seed_demo

.PHONY: test
test: ## Run pytest
	@docker-compose exec django python manage.py test

.PHONY: clean
clean: ## Stop AND wipe SQLite volume
	@docker-compose down -v
	@echo "Database volume removed."

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
