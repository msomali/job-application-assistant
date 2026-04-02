.DEFAULT_GOAL := help
.PHONY: help install dev setup test lint format typecheck check bot agent discover verify clean ci

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install package in editable mode
	pip install -e .

dev:  ## Install package with dev dependencies + playwright + pre-commit
	pip install -e ".[dev]"
	playwright install chromium
	pre-commit install

ci:  ## Install for CI (no playwright, no pre-commit)
	pip install -e ".[dev]"

setup:  ## First-time interactive setup
	@bash scripts/setup.sh

test:  ## Run test suite
	pytest -v --tb=short

lint:  ## Run ruff linter
	ruff check src/ tests/

format:  ## Auto-format code with ruff
	ruff format src/ tests/
	ruff check --fix src/ tests/

typecheck:  ## Run mypy type checker
	mypy src/

check: lint typecheck test  ## Run all checks (lint + typecheck + test)

bot:  ## Start the Telegram bot
	python -m src.agent.telegram_bot

agent:  ## Start the autonomous agent
	python -m src.agent.agent

discover:  ## Run job discovery pipeline
	job discover --analyze-all

verify:  ## Verify setup is complete
	@python3 scripts/verify.py

clean:  ## Remove build artifacts and caches
	rm -rf build/ dist/ *.egg-info .ruff_cache/ .mypy_cache/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
