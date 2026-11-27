from datetime import date, time
from pathlib import Path

from sqlalchemy import func, select

from app.clock import FixedClock
from app.loader import load_data_pack, load_data_pack_2
from app.models import Appointment, AppointmentStatus, Patient, VisitType
from app.rules import BookingCandidate, evaluate_booking
from app.services.appointments import _load_booking_context

DATA_PACK_2 = Path(__file__).resolve().parents[2] / "Project_Resources" / "data-pack-Iteration_02"


def test_pack2_loads_27_completed_and_25_profiles(db, data_pack_path) -> None:
    load_data_pack(db, data_pack_path)
    result = load_data_pack_2(db, DATA_PACK_2)
    assert result == {"profiles": 25, "past_visits": 27}
    assert db.scalar(select(func.count()).select_from(Appointment)) == 27
    assert db.scalar(select(func.count()).select_from(Appointment).where(Appointment.status == AppointmentStatus.BOOKED)) == 0
    assert sum(1 for p in db.scalars(select(Patient)).all() if p.general_health) == 25
    asha_visits = sorted(
        db.scalars(select(Appointment).where(Appointment.patient_id == "P01")).all(),
        key=lambda a: a.date,
    )
    assert [a.id for a in asha_visits] == ["V001", "V002", "V003"]
    assert all(a.status is AppointmentStatus.COMPLETED for a in asha_visits)
    assert all(a.reason and a.doctor_note for a in asha_visits)


def test_pack2_reload_is_idempotent(db, data_pack_path) -> None:
    load_data_pack(db, data_pack_path)
    load_data_pack_2(db, DATA_PACK_2)
    load_data_pack(db, data_pack_path)
    load_data_pack_2(db, DATA_PACK_2)
    assert db.scalar(select(func.count()).select_from(Appointment)) == 27


def test_p01_retina_follow_up_eligible_after_pack2(db, data_pack_path) -> None:
    from datetime import datetime

    load_data_pack(db, data_pack_path)
    load_data_pack_2(db, DATA_PACK_2)
    candidate = BookingCandidate(
        patient_id="P01",
        doctor_id="D3",
        speciality="Retina",
        visit_type=VisitType.FOLLOW_UP,
        date=date(2026, 11, 4),
        start_time=time(11, 30),
    )
    doctor, schedule, holiday, doctor_appts, patient_appts = _load_booking_context(db, candidate)
    decision = evaluate_booking(
        candidate, doctor, schedule, holiday, doctor_appts, patient_appts, datetime(2026, 11, 2, 10, 0)
    )
    assert decision.allowed


def test_pack1_only_behavior_unchanged(db, data_pack_path) -> None:
    load_data_pack(db, data_pack_path)
    assert db.scalar(select(func.count()).select_from(Appointment)) == 0
