from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from walk.common.enums import Effort
from walk.common.roles import AgentRole
from walk.context import (
    ContextBundle,
    ContextBundleRef,
    ContextItem,
    ContextItemKind,
    ContextRequest,
)
from walk.memory import FreshnessAssessment, FreshnessStatus

AT = datetime(2026, 1, 1, tzinfo=UTC)


def _item(item_id: str, kind: ContextItemKind, *, stale: bool = False) -> ContextItem:
    return ContextItem(
        id=item_id,
        kind=kind,
        title=item_id,
        content="text",
        tokens_estimate=2,
        score=1.0,
        freshness=FreshnessAssessment(
            status=FreshnessStatus.POSSIBLY_STALE,
            reason="relevant files changed",
            assessed_against="3f9c2e1",
            assessed_at=AT,
        )
        if stale
        else None,
        requires_verification=stale,
        mandatory=True,
    )


def test_context_models_and_ref() -> None:
    assert [kind.value for kind in ContextItemKind] == [
        "WORK_ITEM",
        "FEATURE_CONTEXT",
        "BUG_CONTEXT",
        "PROJECT_CONTEXT",
        "DECISION",
        "APPROVED_ARTIFACT",
        "HANDOVER",
        "WORKFLOW_STATE",
        "CODE_GRAPH",
        "SOURCE_FILE",
        "EVIDENCE",
        "SKILL",
    ]
    request = ContextRequest(
        work_item_id="STORY-0001", role=AgentRole.SENIOR_DEV, effort=Effort.MEDIUM, token_budget=900
    )
    bundle = ContextBundle(
        request=request,
        items=[
            _item("WORK_ITEM:STORY-0001", ContextItemKind.WORK_ITEM),
            _item("FEATURE_CONTEXT:FEAT-0001", ContextItemKind.FEATURE_CONTEXT, stale=True),
        ],
        total_tokens_estimate=4,
        excluded_count=0,
        built_at=AT,
        head_commit="3f9c2e1",
    )

    ref = bundle.ref()

    assert ref == ContextBundleRef(
        item_ids=["WORK_ITEM:STORY-0001", "FEATURE_CONTEXT:FEAT-0001"],
        total_tokens_estimate=4,
        stale_item_ids=["FEATURE_CONTEXT:FEAT-0001"],
    )
    assert ContextBundle.model_validate_json(bundle.model_dump_json()) == bundle
    assert request.include_source is True
    assert request.code_graph_depth == 2


def test_context_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        ContextBundleRef(item_ids=[], total_tokens_estimate=0, extra=1)  # type: ignore[call-arg]  # extra field on purpose
