"""``skill_projections``: where each skill was projected, per provider and target (ADR-0007)."""

from datetime import datetime

from walk.persistence import Database, UnitOfWork
from walk.skills.models import SkillProjection

_COLUMNS = "skill, provider, target_path, content_sha256, generated_from_sha256, generated_at"


class SkillProjectionRepository:
    """Rows of ``skill_projections`` (primary key: skill, provider, target path)."""

    def __init__(self, db: Database) -> None:
        """Bind the repository to ``db``."""
        self._db = db

    async def upsert(self, uow: UnitOfWork, projections: list[SkillProjection]) -> None:
        """Insert or replace one row per projection in the caller's unit of work."""
        uow.conn.executemany(
            f"INSERT OR REPLACE INTO skill_projections ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)",  # noqa: S608 - constant column list
            [
                (
                    p.skill,
                    p.provider,
                    p.target_path,
                    p.content_sha256,
                    p.generated_from_sha256,
                    p.generated_at.isoformat(),
                )
                for p in projections
            ],
        )

    async def list(self, provider: str | None = None) -> list[SkillProjection]:
        """Every row, or those of ``provider``, ordered by provider, skill and target path."""
        sql = f"SELECT {_COLUMNS} FROM skill_projections"  # noqa: S608 - constant column list
        params: tuple[str, ...] = ()
        if provider is not None:
            sql += " WHERE provider = ?"
            params = (provider,)
        rows = self._db.connect().execute(sql + " ORDER BY provider, skill, target_path", params)
        return [
            SkillProjection(
                skill=row[0],
                provider=row[1],
                target_path=row[2],
                content_sha256=row[3],
                generated_from_sha256=row[4],
                generated_at=datetime.fromisoformat(row[5]),
            )
            for row in rows.fetchall()
        ]
