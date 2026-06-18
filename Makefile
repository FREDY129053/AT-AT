DC_FILE := project/scripts/docker-compose.yaml

.PHONY: up down restart logs ps

up:
	docker compose -f $(DC_FILE) up -d

down:
	docker compose -f $(DC_FILE) down

restart:
	docker compose -f $(DC_FILE) restart

logs:
	docker compose -f $(DC_FILE) logs -f

ps:
	docker compose -f $(DC_FILE) ps