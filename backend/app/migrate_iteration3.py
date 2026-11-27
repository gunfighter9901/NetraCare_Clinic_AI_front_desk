"""Additive migration for Iteration 3.

Adds urgent_cases.origin (booking/chat) with booking backfill. Safe to run
repeatedly; fresh databases get the same schema via create_all. SQLite does
not enforce VARCHAR lengths, so the 300 -> 500 reason_text change needs no
table rebuild; fresh schemas declare String(500).
"""

from __future__ import annotations

from sqlalchemy import Engine, text

from app.db import init_db


def _existing_columns(connection, table: str) -> set[str]:
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def ensure_iteration3_schema(engine: Engine) -> dict[str, int]:
    added = 0
    with engine.begin() as connection:
        tables = {row[0] for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "urgent_cases" in tables:
            existing = _existing_columns(connection, "urgent_cases")
            if "origin" not in existing:
                connection.exec_driver_sql(
                    "ALTER TABLE urgent_cases ADD COLUMN origin TEXT DEFAULT 'booking'"
                )
                added += 1
    # Create missing tables on old DBs; no-op on fresh DBs.
    init_db(engine)
    # Backfill NULL/empty origins to booking.
    with engine.begin() as connection:
        try:
            connection.execute(text(
                "UPDATE urgent_cases SET origin='booking' "
                "WHERE origin IS NULL OR origin=''"
            ))
        except Exception:
            pass
    return {"added_columns": added}


if __name__ == "__main__":
    from app.db import engine as default_engine

    print(ensure_iteration3_schema(default_engine))
