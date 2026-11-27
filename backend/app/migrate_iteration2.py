"""Additive migration for Iteration 2.

Adds patient profile columns, appointment reason/note/urgent columns, and the
urgent_cases table to existing SQLite databases without losing appointments.
Safe to run repeatedly; fresh databases get the same schema via create_all.
"""

from __future__ import annotations

from sqlalchemy import Engine, text

from app.db import init_db


def _existing_columns(connection, table: str) -> set[str]:
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def ensure_iteration2_schema(engine: Engine) -> dict[str, int]:
    added = 0
    with engine.begin() as connection:
        tables = {row[0] for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "patients" in tables:
            existing = _existing_columns(connection, "patients")
            if "general_health" not in existing:
                connection.exec_driver_sql("ALTER TABLE patients ADD COLUMN general_health TEXT")
                added += 1
            if "allergies" not in existing:
                connection.exec_driver_sql("ALTER TABLE patients ADD COLUMN allergies TEXT")
                added += 1
        if "appointments" in tables:
            existing = _existing_columns(connection, "appointments")
            if "reason" not in existing:
                connection.exec_driver_sql("ALTER TABLE appointments ADD COLUMN reason TEXT")
                added += 1
            if "doctor_note" not in existing:
                connection.exec_driver_sql("ALTER TABLE appointments ADD COLUMN doctor_note TEXT")
                added += 1
            if "is_urgent" not in existing:
                connection.exec_driver_sql(
                    "ALTER TABLE appointments ADD COLUMN is_urgent BOOLEAN DEFAULT 0"
                )
                added += 1
            if "urgent_case_id" not in existing:
                connection.exec_driver_sql("ALTER TABLE appointments ADD COLUMN urgent_case_id TEXT")
                added += 1
    # Create missing tables (urgent_cases on old DBs, everything on fresh DBs).
    init_db(engine)
    # Backfill NULL is_urgent flags on old rows.
    with engine.begin() as connection:
        try:
            connection.execute(text("UPDATE appointments SET is_urgent=0 WHERE is_urgent IS NULL"))
        except Exception:
            pass
    return {"added_columns": added}


if __name__ == "__main__":
    from app.db import engine as default_engine

    print(ensure_iteration2_schema(default_engine))
