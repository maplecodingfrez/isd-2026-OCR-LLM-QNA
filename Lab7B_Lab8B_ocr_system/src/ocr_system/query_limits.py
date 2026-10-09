"""Bound materialization and SQLite VM work for already-guarded model queries.

The connection's progress handler belongs to this helper during execution.
A callback cannot preempt a single native function or a database lock wait.
"""
import math
import sqlite3
import time


class QueryBudgetExceeded(RuntimeError):
    """The query exceeded its elapsed-time or VM-instruction budget."""


class QueryRowLimitExceeded(RuntimeError):
    """The query would expose more rows than the caller permits."""


def execute_bounded_rows(conn: sqlite3.Connection, sql: str, *,
                         row_limit: int = 200, timeout_s: float = 2.0,
                         instruction_limit: int = 2_000_000) -> list[dict]:
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 1
           for value in (row_limit, instruction_limit)):
        raise ValueError('Row and instruction limits must be positive integers')
    if (not isinstance(timeout_s, (int, float)) or isinstance(timeout_s, bool)
            or not math.isfinite(timeout_s) or timeout_s <= 0):
        raise ValueError('Query timeout must be positive and finite')
    deadline = time.monotonic() + timeout_s
    interval = min(1000, instruction_limit)
    steps = 0
    exhausted = False
    cursor = None

    def progress():
        nonlocal steps, exhausted
        steps += interval
        exhausted = steps >= instruction_limit or time.monotonic() >= deadline
        return int(exhausted)

    conn.set_progress_handler(progress, interval)
    try:
        cursor = conn.execute(sql)
        rows = cursor.fetchmany(row_limit + 1)
        if len(rows) > row_limit:
            raise QueryRowLimitExceeded('Query returned too many rows')
        return [dict(row) for row in rows]
    except sqlite3.OperationalError as exc:
        if exhausted:
            raise QueryBudgetExceeded('Query execution budget exceeded') from exc
        raise
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            conn.set_progress_handler(None, 0)
