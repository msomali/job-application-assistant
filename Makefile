.PHONY: infra infra-down migrate test test-api test-all lint migration db-reset api-dev worker-dev web-dev web-build web-test web-install

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

api-dev:
	cd api && uvicorn src.app:app --reload --port 8000

worker-dev:
	cd api && celery -A src.workers.celery_app worker --loglevel=info --concurrency=2

test-api:
	cd api && pytest -v --tb=short

test-all:
	cd core && pytest -v --tb=short
	cd api && pytest -v --tb=short

db-reset:
	docker compose exec postgres psql -U jobapp -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	alembic upgrade head

web-dev:
	cd web && npm run dev

web-build:
	cd web && npm run build

web-test:
	cd web && npx vitest run

web-install:
	cd web && npm install
