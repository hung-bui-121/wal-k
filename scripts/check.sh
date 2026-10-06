#!/bin/sh
# Quality gate (docs/00-governance/CONVENTIONS.md §5). Stops at the first failure.
set -e
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
