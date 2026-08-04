.DEFAULT_GOAL := help

.PHONY: help bootstrap format lint typecheck test proof demo benchmark serve build clean

help:
	@echo "GraphABI development commands"
	@echo "  make bootstrap   Install Python 3.12 and locked dependencies"
	@echo "  make lint        Check formatting and lint rules"
	@echo "  make typecheck   Run strict Pyright checks"
	@echo "  make test        Run tests with core coverage threshold"
	@echo "  make proof       Verify public metrics against sources and coverage"
	@echo "  make demo        Run deterministic demo (expected semantic break allowed)"
	@echo "  make benchmark   Generate local benchmark results"
	@echo "  make serve       Serve the latest HTML report at localhost"

bootstrap:
	uv python install 3.12
	uv sync --locked --python 3.12

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .

typecheck:
	uv run pyright

test:
	uv run pytest --cov=graphabi --cov-report=term-missing --cov-fail-under=85

proof:
	uv run python scripts/verify_public_metrics.py

demo:
	uv run graphabi demo --allow-breaking

benchmark:
	uv run python scripts/benchmark.py

serve:
	uv run graphabi report --serve

build:
	uv build

clean:
	uv run python scripts/clean.py
