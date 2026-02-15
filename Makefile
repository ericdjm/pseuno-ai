COMPOSE_DEV = docker compose -f docker-compose.dev.yml
COMPOSE_PROD = docker compose -f docker-compose.prod.yml

.PHONY: dev dev-up dev-down dev-build dev-logs dev-ps backend-shell frontend-shell db-shell redis-cli
.PHONY: prod prod-up prod-down prod-build prod-logs

dev:
	$(COMPOSE_DEV) up --build

dev-up:
	$(COMPOSE_DEV) up -d

dev-down:
	$(COMPOSE_DEV) down

dev-build:
	$(COMPOSE_DEV) build

dev-logs:
	$(COMPOSE_DEV) logs -f --tail=100

dev-ps:
	$(COMPOSE_DEV) ps

backend-shell:
	$(COMPOSE_DEV) exec backend sh

frontend-shell:
	$(COMPOSE_DEV) exec frontend sh

db-shell:
	$(COMPOSE_DEV) exec postgres psql -U pseuno -d pseuno

redis-cli:
	$(COMPOSE_DEV) exec redis redis-cli

prod:
	$(COMPOSE_PROD) up --build

prod-up:
	$(COMPOSE_PROD) up -d

prod-down:
	$(COMPOSE_PROD) down

prod-build:
	$(COMPOSE_PROD) build

prod-logs:
	$(COMPOSE_PROD) logs -f --tail=100
