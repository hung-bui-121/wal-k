from tests.context.conftest import (
    ManagerFactory,
    story_under_feature,
    write_feature_doc,
    write_project_doc,
)
from tests.fakes.fake_clock import FakeClock
from walk.common.enums import Effort
from walk.common.roles import AgentRole
from walk.context import ContextRequest
from walk.memory import DefaultMemoryManager
from walk.workflow import DefaultWorkflowManager


async def test_bundle_is_byte_identical(
    make_manager: ManagerFactory,
    workflow: DefaultWorkflowManager,
    memory: DefaultMemoryManager,
    fake_clock: FakeClock,
) -> None:
    story_id = await story_under_feature(workflow)
    await write_feature_doc(memory, fake_clock)
    await write_project_doc(memory, fake_clock)
    request = ContextRequest(
        work_item_id=story_id, role=AgentRole.LEAD_DEV, effort=Effort.HIGH, token_budget=80_000
    )

    first = await make_manager().build(request)
    fake_clock.advance(3600)
    second = await make_manager().build(request)

    assert first.built_at != second.built_at
    assert first.model_dump_json(exclude={"built_at"}) == second.model_dump_json(
        exclude={"built_at"}
    )
