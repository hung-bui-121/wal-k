"""Workflow errors."""

from walk.common.errors import PermanentError


class WorkItemNotFound(PermanentError):
    """No work item has the requested id; ``detail["work_item_id"]`` names it."""
