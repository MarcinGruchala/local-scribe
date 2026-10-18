.PHONY: setup build check test start dev doctor models

PROFILE ?= fast

setup:
	uv sync --frozen --extra models
	cd frontend && npm ci

build:
	cd frontend && npm run build

test:
	uv run --frozen --no-sync pytest

check: test
	uv run --frozen --no-sync ruff check backend tests
	cd frontend && npm run check

start:
	uv run --frozen --no-sync localscribe

dev:
	uv run --frozen --no-sync localscribe --no-browser

doctor:
	uv run --frozen --no-sync python -m localscribe.models doctor

models:
	uv run --frozen --no-sync python -m localscribe.models download --profile $(PROFILE)
