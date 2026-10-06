import pytest
from pydantic import ValidationError

from walk.common import Actor, AgentRole, FrozenModel, WalkModel, utcnow


class _Sample(WalkModel):
    name: str


class _Frozen(FrozenModel):
    name: str


def test_walk_model_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        _Sample.model_validate({"name": "a", "unexpected": 1})


def test_walk_model_validates_assignment() -> None:
    sample = _Sample(name="a")
    with pytest.raises(ValidationError):
        sample.name = 3  # type: ignore[assignment]  # deliberate wrong type


def test_frozen_model_is_immutable() -> None:
    frozen = _Frozen(name="a")
    with pytest.raises(ValidationError):
        frozen.name = "b"  # type: ignore[misc]  # deliberate mutation of a frozen model


def test_actor_serialises_by_value() -> None:
    dumped = Actor(role=AgentRole.QC).model_dump()
    assert dumped == {"role": "QC", "model_id": None, "run_id": None}
    assert Actor(role=AgentRole.QC).model_dump_json() == (
        '{"role":"QC","model_id":null,"run_id":null}'
    )


def test_utcnow_is_timezone_aware() -> None:
    assert utcnow().tzinfo is not None
