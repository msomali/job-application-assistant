.PHONY: infra infra-down migrate test lint migration db-reset

infra:
	docker compose up -d

infra-down:
	docker compose down

migrate:
	alembic upgrade head

test:
	cd core && pytest -v --tb=short

lint:
	ruff check core/src/ core/tests/

migration:
	@read -p "Migration message: " msg; \
	alembic revision --autogenerate -m "$$msg"

db-reset:
	docker compose exec postgres psql -U jobapp -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	alembic upgrade head
