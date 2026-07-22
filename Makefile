.PHONY: up down dev dev-stop build-frontend check-frontend install-frontend deploy

BRANCH         ?= $(shell git rev-parse --abbrev-ref HEAD)
INFISICAL_ENV  ?= dev
# All envs (dev, staging, prod): secrets at project root /
INFISICAL_PATH ?= /
INFISICAL      ?= infisical run --env $(INFISICAL_ENV) --path $(INFISICAL_PATH) --

deploy:
	BRANCH=$(BRANCH) ./deploy.sh

up:
	docker compose up --build -d

down:
	docker compose down -v --remove-orphans

install-frontend:
	cd web/frontend && npm install

build-frontend:
	cd web/frontend && npm run build

# Type-checks vite.config.ts too, which `tsc --noEmit` on the solution config does not.
check-frontend:
	cd web/frontend && npx tsc -b --force

dev:
	@echo "Starting FastAPI (:8080) + Vite (:5173) [Infisical env: $(INFISICAL_ENV)]..."
	@echo "  1. Open http://localhost:5173 and sign in with Notion"
	@echo "  2. If Infisical session expired: infisical login"
	@trap 'kill %1 %2 2>/dev/null; exit 0' INT; \
	(PORT=8080 INFISICAL_ENV=$(INFISICAL_ENV) $(INFISICAL) ./launch_webserver.sh) & \
	cd web/frontend && npm run dev & \
	wait

dev-stop:
	@pkill -f 'uvicorn web.server:app_factory.*--port 8080' 2>/dev/null || true
	@pkill -f 'web/frontend/node_modules/.bin/vite' 2>/dev/null || true
	@echo "Stopped dev servers on :8080 / :5173 (if any were running)"

dev-backend:
	PORT=8080 INFISICAL_ENV=$(INFISICAL_ENV) $(INFISICAL) ./launch_webserver.sh

dev-frontend:
	cd web/frontend && npm run dev

help:
	@echo "make install-frontend  - Install frontend npm dependencies"
	@echo "make build-frontend    - Build frontend for production (outputs to web/static/)"
	@echo "make check-frontend    - Type-check the frontend (incl. vite.config.ts)"
	@echo "make dev               - Start FastAPI on :8080 + Vite HMR on :5173 (Infisical env: dev)"
	@echo "make dev-stop          - Kill orphaned uvicorn/vite dev processes"
	@echo "make dev-backend       - FastAPI only (port 8080, Infisical env: dev)"
	@echo "make dev-frontend      - Vite dev server only (port 5173, proxies to :8080)"
	@echo "  INFISICAL_ENV=staging make dev   - other env (path / by default)"
	@echo "make up                - Start with Docker Compose"
	@echo "make down              - Stop Docker Compose"
	@echo "make deploy            - Push + deploy current branch to devbox via deploy.sh (BRANCH=name)"
