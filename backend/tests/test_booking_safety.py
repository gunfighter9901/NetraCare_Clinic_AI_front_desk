from datetime import date, time

from sqlalchemy import func, select

from app.clock import FixedClock
from app.llm import LLMCallFailedError, RedFlagResult
from app.models import Appointment, Patient, Role, UrgentCase, VisitType
from app.rules import BookingCandidate
from app.services.safety import safe_book_appointment

NOW = FixedClock(__import__("datetime").datetime(2026, 11, 2, 10, 0))


def candidate(**overrides):
    base = dict(
        patient_id="P17",
        doctor_id="D1",
        speciality="Cataract",
        visit_type=VisitType.NEW,
        date=date(2026, 11, 4),
        start_time=time(9, 0),
    )
    base.update(overrides)
    return BookingCandidate(**base)


def non_urgent_checker(_text: str) -> RedFlagResult:
    return RedFlagResult(red_flag=False, category="none", why="routine")


def red_checker(_text: str) -> RedFlagResult:
    return RedFlagResult(red_flag=True, category="sudden_vision_loss", why="sudden loss")


def failing_checker(_text: str) -> RedFlagResult:
    raise LLMCallFailedError("timeout")


def count_appointments(db) -> int:
    return db.scalar(select(func.count()).select_from(Appointment)) or 0


def test_reason_required_and_length(seeded_db) -> None:
    for bad in [None, "", "   ", "x" * 301]:
        result = safe_book_appointment(
            seeded_db, candidate(), role=Role.PATIENT, actor_patient_id="P17", clock=NOW,
            reason=bad, red_flag_checker=non_urgent_checker,
        )
        assert not result.allowed and not result.check_failed
    assert count_appointments(seeded_db) == 46


def test_check_failure_creates_nothing_nor_walk_in_patient(seeded_db) -> None:
    result = safe_book_appointment(
        seeded_db, candidate(), role=Role.PATIENT, actor_patient_id="P17", clock=NOW,
        reason="Routine check", red_flag_checker=failing_checker,
    )
    assert not result.allowed and result.check_failed
    assert "couldn't check" in (result.message or "")
    assert count_appointments(seeded_db) == 46

    walk_in = safe_book_appointment(
        seeded_db, candidate(patient_id=""), role=Role.STAFF, actor_patient_id=None, clock=NOW,
        reason="Routine check", walk_in_name="No One", walk_in_mobile="7777777777",
        red_flag_checker=failing_checker,
    )
    assert not walk_in.allowed and walk_in.check_failed
    assert seeded_db.scalar(select(Patient).where(Patient.mobile == "7777777777")) is None


def test_non_urgent_success_persists_reason(seeded_db) -> None:
    result = safe_book_appointment(
        seeded_db, candidate(), role=Role.PATIENT, actor_patient_id="P17", clock=NOW,
        reason="Routine eye test", red_flag_checker=non_urgent_checker,
    )
    assert result.allowed and not result.red_flag
    assert result.appointment.reason == "Routine eye test"
    assert result.appointment.is_urgent is False


def test_red_flag_success_creates_urgent_and_tags(seeded_db) -> None:
    result = safe_book_appointment(
        seeded_db, candidate(), role=Role.PATIENT, actor_patient_id="P17", clock=NOW,
        reason="I suddenly can't see from my left eye", red_flag_checker=red_checker,
    )
    assert result.allowed and result.red_flag
    assert result.emergency and "urgent attention" in result.emergency
    assert result.urgent_case is not None
    assert result.appointment.is_urgent is True
    assert result.appointment.urgent_case_id == result.urgent_case.id


def test_red_flag_refused_by_rule_retains_urgent(seeded_db) -> None:
    result = safe_book_appointment(
        seeded_db,
        candidate(doctor_id="D1", date=date(2026, 11, 5), start_time=time(10, 0)),
        role=Role.PATIENT, actor_patient_id="P17", clock=NOW,
        reason="I suddenly can't see", red_flag_checker=red_checker,
    )
    assert not result.allowed and result.red_flag
    assert result.emergency
    assert result.reason_code is not None
    assert result.urgent_case is not None
    urgents = seeded_db.scalars(select(UrgentCase)).all()
    assert len(urgents) == 1


def test_red_walk_in_refused_retains_snapshot_without_patient(seeded_db) -> None:
    result = safe_book_appointment(
        seeded_db,
        candidate(patient_id="", doctor_id="D4", speciality="Glaucoma"),
        role=Role.STAFF, actor_patient_id=None, clock=NOW,
        reason="Got hit in eye", walk_in_name="Hurt Walkin", walk_in_mobile="6666666666",
        red_flag_checker=red_checker,
    )
    assert not result.allowed and result.red_flag
    assert result.urgent_case is not None
    assert result.urgent_case.patient_id is None
    assert result.urgent_case.patient_mobile == "6666666666"
    assert seeded_db.scalar(select(Patient).where(Patient.mobile == "6666666666")) is None
