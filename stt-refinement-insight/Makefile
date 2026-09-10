.PHONY: check test

check:
	uv lock --check
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest

test:
	uv run pytest
