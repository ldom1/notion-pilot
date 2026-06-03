.PHONY: up down dev

up:
	docker compose up -d

down:
	docker compose down -v --remove-orphans

dev:
	./launch_webserver.sh
