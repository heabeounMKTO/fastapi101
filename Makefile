test:
	uv run pytest

dev-db:
	docker compose up -d db

dev: dev-db
	uv run alembic upgrade head
	uv run main.py

up:
	docker compose up --build -d

down:
	docker compose down

# usage: make migration m="add something"
migration:
	uv run alembic revision --autogenerate -m "$(m)"
