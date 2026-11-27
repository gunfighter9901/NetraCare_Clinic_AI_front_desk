from datetime import date, datetime, time

from app.db import create_session_factory, init_db
from app.migrate_iteration4 import ensure_iteration4_schema
from app.models import (
    Appointment,
    AppointmentStatus,
    ApprovalAction,
    ApprovalStatus,
    Doctor,
    Patient,
    StaffApprovalRequest,
    VisitType,
)


def test_fresh_db_has_approval_table_and_partial_index(engine) -> None:
    init_db(engine)
    ensure_iteration4_schema(engine)
    ensure_iteration4_schema(engine)
    from sqlalchemy import inspect

    names = inspect(engine).get_table_names()
    assert "staff_approval_requests" in names
    indexes = {i["name"] for i in inspect(engine).get_indexes("staff_approval_requests")}
    assert "uq_pending_approval_per_appointment" in indexes


def _seed_minimal(db) -> tuple[str, str]:
    db.add(Doctor(id="DX1", name="Dr. Test"))
    db.add(Patient(id="PX1", name="Test Patient", mobile="9111111111"))
    db.flush()
    appt = Appointment(
        id="AX1",
        patient_id="PX1",
        doctor_id="DX1",
        speciality="General",
        visit_type=VisitType.NEW,
        date=date(2026, 11, 4),
        start_time=time(9, 0),
        end_time=time(9, 20),
        status=AppointmentStatus.BOOKED,
        created_at=datetime(2026, 11, 2, 10, 0),
    )
    db.add(appt)
    db.commit()
    return "PX1", "AX1"


def test_model_defaults_relationships_and_target_snapshot(db) -> None:
    _, appointment_id = _seed_minimal(db)
    req = StaffApprovalRequest(
        id="SR001",
        patient_id="PX1",
        appointment_id=appointment_id,
        action=ApprovalAction.RESCHEDULE,
        status=ApprovalStatus.PENDING,
        target_doctor_id="DX1",
        target_date=date(2026, 11, 5),
        target_start_time=time(10, 0),
        requested_at=datetime(2026, 11, 2, 10, 0),
    )
    db.add(req)
    db.commit()
    fetched = db.get(StaffApprovalRequest, "SR001")
    assert fetched is not None
    assert fetched.status is ApprovalStatus.PENDING
    assert fetched.action is ApprovalAction.RESCHEDULE
    assert fetched.target_date == date(2026, 11, 5)
    assert fetched.target_start_time == time(10, 0)
    assert fetched.patient.name == "Test Patient"
    assert fetched.appointment.id == appointment_id


def test_old_db_preserves_rows_and_gains_schema() -> None:
    from sqlalchemy import create_engine

    from app.migrate_iteration2 import ensure_iteration2_schema
    from app.migrate_iteration3 import ensure_iteration3_schema

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE patients (id TEXT PRIMARY KEY, name TEXT NOT NULL, mobile TEXT NOT NULL UNIQUE, year_of_birth INTEGER)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE doctors (id TEXT PRIMARY KEY, name TEXT NOT NULL)"
        )
        conn.exec_driver_sql(
            "CREATE TABLE appointments (id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, doctor_id TEXT NOT NULL, "
            "speciality TEXT NOT NULL, visit_type TEXT NOT NULL, date DATE NOT NULL, start_time TIME NOT NULL, "
            "end_time TIME NOT NULL, status TEXT NOT NULL, created_at DATETIME NOT NULL, cancelled_at DATETIME, "
            "completed_at DATETIME, reason TEXT, doctor_note TEXT, is_urgent BOOLEAN NOT NULL DEFAULT 0, urgent_case_id TEXT)"
        )
        conn.exec_driver_sql("INSERT INTO patients VALUES ('P01','Asha','9000000001',NULL)")
        conn.exec_driver_sql("INSERT INTO doctors VALUES ('D1','Dr. Rao')")
        conn.exec_driver_sql(
            "INSERT INTO appointments VALUES ('A001','P01','D1','General','new','2026-11-04','09:00:00','09:20:00','booked','2026-11-02 10:00:00',NULL,NULL,NULL,NULL,0,NULL)"
        )
    ensure_iteration2_schema(engine)
    ensure_iteration3_schema(engine)
    first = ensure_iteration4_schema(engine)
    # init_db inside earlier migrations already created the new table.
    assert first["added_tables"] in (0, 1)
    second = ensure_iteration4_schema(engine)
    assert second["added_tables"] == 0
    factory = create_session_factory(engine)
    with factory() as session:
        assert session.get(Appointment, "A001") is not None
        assert session.get(Patient, "P01") is not None
