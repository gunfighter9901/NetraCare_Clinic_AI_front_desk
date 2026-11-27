from datetime import datetime

from app.migrate_iteration3 import ensure_iteration3_schema
from app.models import UrgentCase, UrgentOrigin
from app.services.safety import create_urgent_case


def test_default_origin_is_booking(seeded_db) -> None:
    urgent = create_urgent_case(
        seeded_db,
        patient_id="P01",
        patient_name="Asha Verma",
        patient_mobile="9000000001",
        reason_text="Routine eye test",
        category="none",
        model_why="test",
        now=datetime(2026, 11, 2, 10, 0),
    )
    assert urgent.origin == UrgentOrigin.BOOKING
    assert urgent.origin.value == "booking"


def test_chat_origin_retains_full_text(seeded_db) -> None:
    long_text = "x" * 500
    urgent = create_urgent_case(
        seeded_db,
        patient_id="P01",
        patient_name="Asha Verma",
        patient_mobile="9000000001",
        reason_text=long_text,
        category="curtain_or_shadow",
        model_why="chat test",
        now=datetime(2026, 11, 2, 10, 0),
        origin=UrgentOrigin.CHAT,
    )
    assert urgent.origin == UrgentOrigin.CHAT
    fetched = seeded_db.get(UrgentCase, urgent.id)
    assert fetched is not None and fetched.reason_text == long_text


def test_migration_backfills_existing_booking_origin() -> None:
    from sqlalchemy import create_engine

    from app.db import create_session_factory

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE urgent_cases ("
            "id TEXT PRIMARY KEY, patient_id TEXT, patient_name TEXT, "
            "patient_mobile TEXT, reason_text TEXT NOT NULL, category TEXT NOT NULL, "
            "model_why TEXT, created_at DATETIME NOT NULL, seen BOOLEAN NOT NULL, "
            "seen_at DATETIME)"
        )
        conn.exec_driver_sql(
            "INSERT INTO urgent_cases (id, reason_text, category, created_at, seen) "
            "VALUES ('U001', 'Old booking urgent', 'sudden_vision_loss', "
            "'2026-11-02 10:00:00', 0)"
        )
    result = ensure_iteration3_schema(engine)
    assert result["added_columns"] == 1
    # Re-run for idempotence.
    ensure_iteration3_schema(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        fetched = session.get(UrgentCase, "U001")
        assert fetched is not None
        assert fetched.origin == UrgentOrigin.BOOKING
        assert fetched.reason_text == "Old booking urgent"
