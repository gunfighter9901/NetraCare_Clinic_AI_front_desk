"""Additive migration for Iteration 4.

Creates staff_approval_requests table with a filtered unique index allowing
only one pending request per appointment. Safe to run repeatedly; fresh
databases get the same schema via create_all.
"""

from __future__ import annotations

from sqlalchemy import Engine

from app.db import init_db


def ensure_iteration4_schema(engine: Engine) -> dict[str, int]:
    added = 0
    with engine.begin() as connection:
        tables = {row[0] for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        if "staff_approval_requests" not in tables:
            added += 1
    # Create missing tables/indices on old DBs; no-op on fresh DBs.
    init_db(engine)
    # Ensure partial unique index exists on old DBs that already have the table
    # but were created before the index (e.g. partial manual creation).
    with engine.begin() as connection:
        try:
            indexes = {row[0] for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()}
            if "uq_pending_approval_per_appointment" not in indexes:
                connection.exec_driver_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "uq_pending_approval_per_appointment ON "
                    "staff_approval_requests (appointment_id) WHERE status = 'pending'"
                )
        except Exception:
            pass
    return {"added_tables": added}


if __name__ == "__main__":
    from app.db import engine as default_engine

    print(ensure_iteration4_schema(default_engine))
