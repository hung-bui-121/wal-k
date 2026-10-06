from datetime import UTC, datetime
from enum import StrEnum
from typing import ClassVar

import pytest
from pydantic import Field

from walk.common.errors import ConfigError
from walk.common.models import WalkModel
from walk.persistence import Database, Repository, UnitOfWork


class Color(StrEnum):
    RED = "RED"
    BLUE = "BLUE"


class Widget(WalkModel):
    id: str = Field(description="Key.")
    name: str = Field(description="Display name.")
    rank: int = Field(description="Sort order.")
    color: Color = Field(description="Enum projected as text.")
    active: bool = Field(default=True, description="Bool projected as int.")
    made_at: datetime = Field(description="Datetime projected as ISO text.")
    tags: list[str] = Field(default_factory=list, description="Only in json.")


class WidgetRepository(Repository[Widget]):
    _table: ClassVar[str] = "widgets"
    _model = Widget

    def projection(self, obj: Widget) -> dict[str, object]:
        return {
            "name": obj.name,
            "rank": obj.rank,
            "color": obj.color,
            "active": obj.active,
            "made_at": obj.made_at,
        }


class PlainRepository(Repository[Widget]):
    _table: ClassVar[str] = "plain_widgets"
    _model = Widget


class BadTableRepository(Repository[Widget]):
    _table: ClassVar[str] = "widgets; DROP TABLE widgets"
    _model = Widget


MADE = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def widget_db(db: Database) -> Database:
    db.connect().execute(
        "CREATE TABLE widgets (id TEXT PRIMARY KEY, name TEXT NOT NULL, rank INTEGER NOT NULL, "
        "color TEXT NOT NULL, active INTEGER NOT NULL, made_at TEXT NOT NULL, json TEXT NOT NULL)"
    )
    db.connect().execute("CREATE TABLE plain_widgets (id TEXT PRIMARY KEY, json TEXT NOT NULL)")
    return db


def _widget(id_: str, rank: int, name: str = "w") -> Widget:
    return Widget(id=id_, name=name, rank=rank, color=Color.BLUE, made_at=MADE, tags=["a"])


async def test_insert_and_get_round_trip(widget_db: Database) -> None:
    repo = WidgetRepository(widget_db)
    widget = _widget("W-1", 3)
    async with UnitOfWork(widget_db) as uow:
        assert await repo.insert(widget, uow) == widget
    assert await repo.get("W-1") == widget
    row = widget_db.connect().execute("SELECT * FROM widgets WHERE id = 'W-1'").fetchone()
    assert (row["name"], row["rank"], row["color"], row["active"]) == ("w", 3, "BLUE", 1)
    assert row["made_at"] == MADE.isoformat()


async def test_insert_without_projection_stores_key_and_json(widget_db: Database) -> None:
    repo = PlainRepository(widget_db)
    async with UnitOfWork(widget_db) as uow:
        await repo.insert(_widget("W-1", 1), uow)
    assert await repo.get("W-1") == _widget("W-1", 1)


async def test_upsert_replaces_existing(widget_db: Database) -> None:
    repo = WidgetRepository(widget_db)
    async with UnitOfWork(widget_db) as uow:
        await repo.upsert(_widget("W-1", 1, name="first"), uow)
    async with UnitOfWork(widget_db) as uow:
        await repo.upsert(_widget("W-1", 2, name="second"), uow)
    rows = widget_db.connect().execute("SELECT name, rank FROM widgets").fetchall()
    assert [tuple(row) for row in rows] == [("second", 2)]
    stored = await repo.get("W-1")
    assert stored is not None
    assert stored.name == "second"


async def test_upsert_without_projection_replaces_json(widget_db: Database) -> None:
    repo = PlainRepository(widget_db)
    async with UnitOfWork(widget_db) as uow:
        await repo.upsert(_widget("W-1", 1), uow)
        await repo.upsert(_widget("W-1", 9), uow)
    stored = await repo.get("W-1")
    assert stored is not None
    assert stored.rank == 9


async def test_get_missing_returns_none(widget_db: Database) -> None:
    assert await WidgetRepository(widget_db).get("missing") is None


async def test_list_where_orders_and_limits(widget_db: Database) -> None:
    repo = WidgetRepository(widget_db)
    async with UnitOfWork(widget_db) as uow:
        for id_, rank in (("W-1", 5), ("W-2", 1), ("W-3", 3), ("W-4", 9)):
            await repo.insert(_widget(id_, rank), uow)
    found = await repo.list_where("rank < ?", (9,), order_by="rank DESC", limit=2)
    assert [w.id for w in found] == ["W-1", "W-3"]
    assert len(await repo.list_where()) == 4


async def test_invalid_table_name_is_rejected(widget_db: Database) -> None:
    with pytest.raises(ConfigError):
        BadTableRepository(widget_db)


async def test_invalid_projection_column_is_rejected(widget_db: Database) -> None:
    class BadColumnRepository(WidgetRepository):
        def projection(self, obj: Widget) -> dict[str, object]:
            return {"name; --": obj.name}

    repo = BadColumnRepository(widget_db)
    async with UnitOfWork(widget_db) as uow:
        with pytest.raises(ConfigError):
            await repo.insert(_widget("W-1", 1), uow)
