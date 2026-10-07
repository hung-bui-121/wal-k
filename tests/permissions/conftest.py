"""Fixtures of the permission tests: the runtime fixtures, for approvals inside real runs."""

from tests.runtime import conftest as runtime_fixtures

# The runtime fixtures, shared with this folder (E02-S11 approval lifecycle tests).
checkpoint_fired = runtime_fixtures.checkpoint_fired
git = runtime_fixtures.git
hooks = runtime_fixtures.hooks
idempotency = runtime_fixtures.idempotency
ledger = runtime_fixtures.ledger
make_executor_env = runtime_fixtures.make_executor_env
memory = runtime_fixtures.memory
runs = runtime_fixtures.runs
story = runtime_fixtures.story
