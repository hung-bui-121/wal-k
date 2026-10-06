"""Composition root: the only place that wires concrete implementations together.

`build_kernel` (E01-S30) will live here; until then this module opens the project database
and wires the services the CLI commands use.
"""

from pathlib import Path

from walk.budgets import (
    BudgetRepository,
    CostRepository,
    DefaultBudgetManager,
    DefaultCostManager,
)
from walk.common.clock import Clock, SystemClock
from walk.hooks import DefaultHookManager, HookExecutionRepository
from walk.persistence import Database, IdSequenceStore
from walk.telemetry import DefaultLedgerManager, LedgerRepository
from walk.workflow import (
    TABLES_DIR,
    DefaultWorkflowManager,
    ProjectRepository,
    WorkflowRepository,
)

_AI_DIR = ".ai"
_DB_FILE = "kernel.db"


def open_database(repo: Path, *, read_only: bool = False) -> Database:
    """Open the project database ``<repo>/.ai/kernel.db``.

    Args:
        repo: Game repository root.
        read_only: Open without write access; the database must already exist.

    Returns:
        A connected `Database`. A writable database (and ``.ai/``) is created when missing.

    Raises:
        ConfigError: If a read-only database does not exist or cannot be opened.
    """
    db = Database(repo / _AI_DIR / _DB_FILE, read_only=read_only)
    db.connect()
    return db


def open_workflow(db: Database, *, clock: Clock | None = None) -> DefaultWorkflowManager:
    """Wire a `DefaultWorkflowManager` (with ledger and hook manager) on ``db``.

    Args:
        db: An open project database.
        clock: Time source; the system clock when ``None`` (tests inject a fake).

    Raises:
        ConfigError: If a packaged transition table is invalid.
    """
    time = clock or SystemClock()
    ids = IdSequenceStore(db)
    ledger = DefaultLedgerManager(db, LedgerRepository(db), ids, time)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, time)
    return DefaultWorkflowManager(
        db,
        WorkflowRepository(db),
        ProjectRepository(db),
        ids,
        ledger,
        hooks,
        time,
        TABLES_DIR,
    )


def open_costs(db: Database, *, clock: Clock | None = None) -> DefaultCostManager:
    """Wire a `DefaultCostManager` (with its budget manager, ledger and hooks) on ``db``.

    Args:
        db: An open project database.
        clock: Time source; the system clock when ``None`` (tests inject a fake).
    """
    time = clock or SystemClock()
    ledger = DefaultLedgerManager(db, LedgerRepository(db), IdSequenceStore(db), time)
    hooks = DefaultHookManager(HookExecutionRepository(db), ledger, time)
    budgets = DefaultBudgetManager(db, BudgetRepository(db), ledger, hooks, time)
    return DefaultCostManager(db, CostRepository(db), ledger, budgets, WorkflowRepository(db))
