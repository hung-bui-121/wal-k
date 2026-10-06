"""Context service protocol (INTERFACES §1.7)."""

from typing import Protocol

from walk.common.enums import Effort
from walk.context.models import ContextBundle, ContextRequest


class ContextManager(Protocol):
    """§6.8, §40-§43. Hosted by walk.context."""

    async def build(self, request: ContextRequest) -> ContextBundle:
        """INTERFACES §5.4 algorithm.

        Fires ON_CONTEXT_STALE for any POSSIBLY_STALE/INVALID item included.
        """
        ...

    def token_budget_for(
        self, effort: Effort, context_window_tokens: int, max_output_tokens: int
    ) -> int:
        """LOW 20%, MEDIUM 35%, HIGH 50%, VERY_HIGH 60% of the window minus max_output_tokens.

        ADR-0012 D-3. Caller passes the numbers from ModelDescriptor (context stays below
        model_router).
        """
        ...
