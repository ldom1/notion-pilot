.PHONY: up down dev build-frontend install-frontend deploy

DEVBOX_HOST  ?= 100.64.162.103
DEVBOX_PORT  ?= 16152
DEVBOX_USER  ?= lgiron
DEVBOX_PATH  ?= /home/lgiron/Lab/notion-pilot
DEVBOX_SSH_KEY ?= ~/.ssh/notion-pilot-gha
BRANCH       ?= $(shell git rev-parse --abbrev-ref HEAD)

deploy:
	@echo "→ Deploying branch '$(BRANCH)' to devbox $(DEVBOX_HOST)..."
	@git push origin $(BRANCH) 2>/dev/null || true
	ssh -i $(DEVBOX_SSH_KEY) -p $(DEVBOX_PORT) $(DEVBOX_USER)@$(DEVBOX_HOST) \
	  "set -euo pipefail; \
	   cd $(DEVBOX_PATH); \
	   GIT_SSH_COMMAND='ssh -i ~/.ssh/notion-pilot-deploy -o StrictHostKeyChecking=no' git fetch origin; \
	   git checkout $(BRANCH); \
	   git reset --hard origin/$(BRANCH); \
	   docker compose up --build -d; \
	   echo '✓ deployed $(BRANCH)'"

up:
	docker compose up --build -d

down:
	docker compose down -v --remove-orphans

install-frontend:
	cd web/frontend && npm install

build-frontend:
	cd web/frontend && npm run build

dev:
	@echo "Starting FastAPI (:8080) + Vite (:5174)..."
	@echo "  1. Authenticate once at http://localhost:8080"
	@echo "  2. Then use http://localhost:5174 for hot-reload development"
	@trap 'kill %1 %2 2>/dev/null; exit 0' INT; \
	./launch_webserver.sh & \
	cd web/frontend && npm run dev & \
	wait

dev-backend:
	./launch_webserver.sh

dev-frontend:
	cd web/frontend && npm run dev

help:
	@echo "make install-frontend  - Install frontend npm dependencies"
	@echo "make build-frontend    - Build frontend for production (outputs to web/static/)"
	@echo "make dev               - Start FastAPI on :8080 + Vite HMR on :5173"
	@echo "make dev-backend       - FastAPI only (port 8080)"
	@echo "make dev-frontend      - Vite dev server only (port 5173, proxies to :8080)"
	@echo "make up                - Start with Docker Compose"
	@echo "make down              - Stop Docker Compose"
	@echo "make deploy            - Deploy current branch to devbox (BRANCH=name to override)"
