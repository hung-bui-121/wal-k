"""Workflow errors."""

from walk.common.errors import PermanentError


class WorkItemNotFound(PermanentError):
    """No work item has the requested id; ``detail["work_item_id"]`` names it."""


class UnknownTransition(PermanentError):
    """No table row exists for the item's state and the event (``detail``: kind, state, event)."""
