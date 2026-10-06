"""Runtime errors (E01-S25)."""

from walk.common.errors import PermanentError


class RunNotFound(PermanentError):
    """No `agent_runs` row has the requested run id."""


class CheckpointNotFound(PermanentError):
    """No checkpoint matches the request (raised by the resume/recovery paths, E01-S28)."""
