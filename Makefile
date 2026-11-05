.PHONY: help deploy deploy-systemd test clean logs status

SHELL := /bin/bash

help:
	@echo "km_lexicon Operational Targets:"
	@echo "  make deploy         - Run clean slate deployment (Docker only, keeps systemd halted)"
	@echo "  make deploy-systemd - Run deployment and re-enable systemd user services at the end"
	@echo "  make test           - Run pytest test suite inside the app container"
	@echo "  make clean          - Purge all containers, volumes, and temporary logs"
	@echo "  make logs           - Stream live docker compose container logs"
	@echo "  make status         - Check port bindings, systemd units, and container status"

deploy:
	@chmod +x ./reset_and_deploy.sh
	./reset_and_deploy.sh

deploy-systemd:
	@chmod +x ./reset_and_deploy.sh
	./reset_and_deploy.sh --with-systemd

test:
	docker compose exec -T app pytest tests/ -v

clean:
	docker compose down --remove-orphans --volumes
	docker image prune -f

logs:
	docker compose logs -f --tail=100

status:
	@echo "=== PORT 8000 STATUS ==="
	@sudo lsof -i :8000 || echo "Port 8000 is free"
	@echo "=== SYSTEMD SERVICES ==="
	@systemctl --user list-units --type=service | grep -iE 'km_lexicon|uvicorn' || true
	@echo "=== DOCKER CONTAINERS ==="
	@docker compose ps
