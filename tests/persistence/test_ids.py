import re

import pytest

from walk.common.errors import ConfigError
from walk.common.ids import ULID_PATTERN
from walk.persistence import SEQUENCE_WIDTHS, Database, IdSequenceStore, UnitOfWork


async def test_next_sequence_allocates_contiguous_ids(db: Database) -> None:
    store = IdSequenceStore(db)
    async with UnitOfWork(db) as uow:
        ids = store.bind(uow)
        allocated = [ids.next_sequence("FEAT") for _ in range(3)]
    assert allocated == ["FEAT-0001", "FEAT-0002", "FEAT-0003"]
    async with UnitOfWork(db) as uow:
        assert store.bind(uow).next_sequence("FEAT") == "FEAT-0004"
        assert store.bind(uow).next_sequence("BUG") == "BUG-0001"


async def test_next_sequence_requires_bound_uow(db: Database) -> None:
    store = IdSequenceStore(db)
    with pytest.raises(ConfigError):
        store.next_sequence("FEAT")
    async with UnitOfWork(db) as uow:
        bound = store.bind(uow)
    with pytest.raises(ConfigError):
        bound.next_sequence("FEAT")


async def test_next_sequence_rejects_unknown_prefix(db: Database) -> None:
    async with UnitOfWork(db) as uow:
        with pytest.raises(ConfigError):
            IdSequenceStore(db).bind(uow).next_sequence("NOPE")


async def test_sequences_never_repeat_committed_ids(db: Database) -> None:
    store = IdSequenceStore(db)
    async with UnitOfWork(db) as uow:
        committed = store.bind(uow).next_sequence("STORY")
    rolled_back: list[str] = []

    async def aborted() -> None:
        async with UnitOfWork(db) as uow:
            rolled_back.append(store.bind(uow).next_sequence("STORY"))
            msg = "abort"
            raise RuntimeError(msg)

    with pytest.raises(RuntimeError):
        await aborted()
    async with UnitOfWork(db) as uow:
        after = store.bind(uow).next_sequence("STORY")
    assert committed == "STORY-0001"
    assert rolled_back == ["STORY-0002"]  # gap given back by the rollback
    assert after != committed
    assert after == "STORY-0002"


async def test_sequence_width_follows_table(db: Database) -> None:
    async with UnitOfWork(db) as uow:
        ids = IdSequenceStore(db).bind(uow)
        assert ids.next_sequence("EVD") == "EVD-000001"
        assert ids.next_sequence("PHASE") == "PHASE-01"
        assert ids.next_sequence("OBS-K") == "OBS-K-0001"
    assert SEQUENCE_WIDTHS["EVD"] == 6
    assert SEQUENCE_WIDTHS["EPIC"] == 3


def test_new_ulid_is_ulid(db: Database) -> None:
    assert re.fullmatch(ULID_PATTERN, IdSequenceStore(db).new_ulid())
