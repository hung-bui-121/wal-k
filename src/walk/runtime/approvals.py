"""`EventApprovalWaiter`: wakes a run paused for approval as soon as it is decided (E02-S11).

The permission manager calls `resolve` after it committed a decision or an expiry
(``DefaultPermissionManager.on_decided``). Decisions made by another process (``walk approve``
in-process while the daemon runs) never reach that callback, so the waiter also re-reads the
request every ``poll_interval_s``. It holds no database connection while it waits.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Final

from walk.common.clock import Clock
from walk.common.errors import ConfigError, GuardRejected
from walk.common.ids import ApprovalRequestId
from walk.permissions.models import ApprovalState
from walk.permissions.protocols import PermissionManager
from walk.permissions.repository import ApprovalRepository

_KERNEL: Final = "kernel"
_TIMEOUT_NOTE: Final = "timeout"


class EventApprovalWaiter:
    """`ApprovalWaiter` over in-process events, with a database poll as the fallback."""

    def __init__(
        self,
        approvals: ApprovalRepository,
        clock: Clock,
        *,
        permissions: PermissionManager,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        poll_interval_s: float = 1.0,
    ) -> None:
        """Wire the waiter.

        Args:
            approvals: Read side of the approval requests (the state after every wake-up).
            clock: Measures the timeout.
            permissions: Expires a timed-out request (it owns ``APPROVAL_DECIDED``).
            sleep: The poll interval's sleep; tests inject one that advances a fake clock.
            poll_interval_s: Seconds between database polls while no event arrives.
        """
        self._approvals = approvals
        self._clock = clock
        self._permissions = permissions
        self._sleep = sleep
        self._poll_interval_s = poll_interval_s
        self._events: dict[ApprovalRequestId, asyncio.Event] = {}

    def register(self, approval_id: ApprovalRequestId) -> None:
        """Prepare the event of ``approval_id`` (a decision before `wait` is not missed)."""
        self._events.setdefault(approval_id, asyncio.Event())

    def resolve(self, approval_id: ApprovalRequestId, state: ApprovalState) -> None:
        """Wake the waiter of ``approval_id`` once it is no longer PENDING; else a no-op."""
        if state is ApprovalState.PENDING:
            return
        event = self._events.get(approval_id)
        if event is not None:
            event.set()

    async def wait(self, approval_id: ApprovalRequestId, timeout_s: int) -> ApprovalState:
        """Return APPROVED/DENIED/EXPIRED; timeout → EXPIRED (and the request is expired).

        Raises:
            ConfigError: The approval request does not exist.
        """
        self.register(approval_id)
        event = self._events[approval_id]
        started = self._clock.now()
        try:
            while True:
                state = await self._state(approval_id)
                if state is not ApprovalState.PENDING:
                    return state
                if (self._clock.now() - started).total_seconds() >= timeout_s:
                    return await self._expire(approval_id)
                await self._nap(event)
        finally:
            self._events.pop(approval_id, None)

    async def _nap(self, event: asyncio.Event) -> None:
        """Until ``event`` is set or one poll interval passed."""
        woken = asyncio.ensure_future(event.wait())
        polled = asyncio.ensure_future(self._sleep(self._poll_interval_s))
        try:
            await asyncio.wait({woken, polled}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (woken, polled):
                if not task.done():
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
        event.clear()

    async def _state(self, approval_id: ApprovalRequestId) -> ApprovalState:
        approval = await self._approvals.get(approval_id)
        if approval is None:
            msg = f"unknown approval request {approval_id}"
            raise ConfigError(msg, detail={"approval_id": approval_id})
        return approval.state

    async def _expire(self, approval_id: ApprovalRequestId) -> ApprovalState:
        try:
            await self._permissions.decide_approval(
                approval_id, approve=False, by=_KERNEL, note=_TIMEOUT_NOTE, expired=True
            )
        except GuardRejected:
            return await self._state(approval_id)  # decided just before the expiry: it stands
        return ApprovalState.EXPIRED
