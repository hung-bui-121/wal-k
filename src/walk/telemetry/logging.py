"""JSON-lines diagnostics log (ADR-0009 D-16); never the source of truth (ADR-0001)."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

_LOG_RELATIVE_PATH = Path(".walk") / "logs" / "kernel.jsonl"
_STANDARD_ATTRS = frozenset(logging.LogRecord("", logging.INFO, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
}
_FIELDS_ATTR = "walk_fields"  # structured fields attached by DefaultTelemetryManager.log


class JsonLineHandler(logging.FileHandler):
    """Appends one JSON object per record: ``ts, level, msg``, ``logger``, then the fields.

    Fields come from ``extra={...}`` (CONVENTIONS §2) or from `DefaultTelemetryManager.log`.
    A field never replaces ``ts``, ``level``, ``msg`` or ``logger``. Values that JSON cannot
    encode are written as their ``repr``, so formatting never raises.
    """

    def __init__(self, path: Path) -> None:
        """Log to ``path`` (appending); the parent directory is created, the file on first use."""
        path.parent.mkdir(parents=True, exist_ok=True)
        super().__init__(path, mode="a", encoding="utf-8", delay=True)

    def format(self, record: logging.LogRecord) -> str:
        """Return the record as a single JSON line (without the newline)."""
        entry: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "msg": record.getMessage(),
        }
        if record.name:
            entry["logger"] = record.name
        fields = {k: v for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS}
        fields.update(fields.pop(_FIELDS_ATTR, None) or {})
        for key, value in fields.items():
            entry.setdefault(key, value)
        return _dumps(entry)


def _dumps(entry: dict[str, object]) -> str:
    try:
        return json.dumps(entry, default=repr, ensure_ascii=False)
    except (TypeError, ValueError):
        # Circular structures and non-string keys cannot be encoded even with default=repr.
        safe = {key: _encodable_or_repr(value) for key, value in entry.items()}
        return json.dumps(safe, default=repr, ensure_ascii=False)


def _encodable_or_repr(value: object) -> object:
    try:
        json.dumps(value, default=repr)
    except (TypeError, ValueError):
        return repr(value)
    return value


def configure_logging(repo_root: Path, *, level: str = "INFO") -> None:
    """Send the ``walk`` logger hierarchy to ``<repo_root>/.walk/logs/kernel.jsonl``.

    Idempotent: an earlier `JsonLineHandler` on the ``walk`` logger is closed and replaced.

    Args:
        repo_root: Game repository root.
        level: Minimum level name for the ``walk`` logger, e.g. ``"INFO"``.
    """
    logger = logging.getLogger("walk")
    for handler in list(logger.handlers):
        if isinstance(handler, JsonLineHandler):
            logger.removeHandler(handler)
            handler.close()
    logger.addHandler(JsonLineHandler(repo_root / _LOG_RELATIVE_PATH))
    logger.setLevel(level.upper())
