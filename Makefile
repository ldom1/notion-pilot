.PHONY: up down dev build-frontend install-frontend deploy

BRANCH       ?= $(shell git rev-parse --abbrev-ref HEAD)

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

dev:
	@echo "Starting FastAPI (:8080) + Vite (:5174)..."
	@echo "  1. Authenticate once at http://localhost:8080"
	@echo "  2. Then use http://localhost:5174 for hot-reload development"
	@trap 'kill %1 %2 2>/dev/null; exit 0' INT; \
	infisical run -- ./launch_webserver.sh & \
	cd web/frontend && npm run dev & \
	wait

dev-backend:
	infisical run -- ./launch_webserver.sh

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
	@echo "make deploy            - Push + deploy current branch to devbox via deploy.sh (BRANCH=name)"
