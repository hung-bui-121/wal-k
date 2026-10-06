"""SQLite repository of approval requests (``approval_requests``)."""

from datetime import UTC, datetime
from typing import ClassVar

from walk.permissions.models import ApprovalRequest, ApprovalState, Approver
from walk.persistence import Database, Repository


def _utc_text(value: datetime) -> str:
    """Fixed-width UTC text so that timestamp columns order correctly as strings."""
    return value.astimezone(UTC).isoformat(timespec="microseconds")


class ApprovalRepository(Repository[ApprovalRequest]):
    """``approval_requests``: the `ApprovalRequest` JSON plus state/approver columns."""

    _table: ClassVar[str] = "approval_requests"
    _model = ApprovalRequest

    @property
    def db(self) -> Database:
        """The database the repository reads from; writers open their unit of work on it."""
        return self._db

    def projection(self, obj: ApprovalRequest) -> dict[str, object]:
        """Indexed columns of the ``approval_requests`` table."""
        return {
            "kind": obj.kind,
            "approver": obj.approver,
            "requested_by_role": obj.requested_by_role,
            "run_id": obj.run_id,
            "work_item_id": obj.work_item_id,
            "state": obj.state,
            "requested_at": _utc_text(obj.requested_at),
            "decided_at": None if obj.decided_at is None else _utc_text(obj.decided_at),
        }

    async def pending(self, approver: Approver | None = None) -> list[ApprovalRequest]:
        """PENDING requests, optionally for one approver, oldest first."""
        where = "state = ?"
        params: list[object] = [ApprovalState.PENDING.value]
        if approver is not None:
            where += " AND approver = ?"
            params.append(approver.value)
        return await self.list_where(where, params, order_by="requested_at, id")
