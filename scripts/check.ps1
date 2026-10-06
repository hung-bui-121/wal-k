# Quality gate (docs/00-governance/CONVENTIONS.md section 5). Stops at the first failure.
$ErrorActionPreference = "Stop"
uv run ruff format --check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run mypy src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv run pytest
exit $LASTEXITCODE
