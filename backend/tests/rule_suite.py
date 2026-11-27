import csv
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.clock import FixedClock
from app.models import Role, VisitType
from app.rules import BookingCandidate, ReasonCode
from app.services.appointments import (
    BookingResult,
    CancellationResult,
    RescheduleResult,
    book_appointment,
    cancel_appointment,
    reschedule_appointment,
)

CLINIC_NOW = datetime(2026, 11, 2, 10, 0)
FIXED_CLOCK = FixedClock(CLINIC_NOW)
RULE_TESTS_PATH = (
    Path(__file__).resolve().parents[2]
    / "Project_Resources"
    / "data-pack-Iteration_01"
    / "stretch"
    / "rule_tests.csv"
)
SELECTED_IDS = tuple(f"T{number:02d}" for number in range(1, 39))


def load_rule_cases() -> list[dict[str, str]]:
    with RULE_TESTS_PATH.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def role_for(case: dict[str, str]) -> Role:
    return Role.PATIENT if case["role"] == "patient" else Role.STAFF


def actor_patient_id(case: dict[str, str]) -> str | None:
    return case["acting_patient_id"] if case["role"] == "patient" else None


def run_booking_case(db: Session, case: dict[str, str]) -> BookingResult:
    candidate = BookingCandidate(
        patient_id=case["acting_patient_id"] or case.get("patient_id", ""),
        doctor_id=case["doctor_id"],
        speciality=case["speciality"],
        visit_type=VisitType(case["visit_type"]),
        date=date.fromisoformat(case["date"]),
        start_time=time.fromisoformat(case["start_time"]),
    )
    return book_appointment(
        db,
        candidate,
        role=role_for(case),
        actor_patient_id=actor_patient_id(case),
        clock=FIXED_CLOCK,
        reason="Routine eye test and new glasses",
        is_urgent=False,
    )


def run_cancellation_case(db: Session, case: dict[str, str]) -> CancellationResult:
    return cancel_appointment(
        db,
        case["appointment_id"],
        role=role_for(case),
        actor_patient_id=actor_patient_id(case),
        clock=FIXED_CLOCK,
    )


def run_reschedule_case(db: Session, case: dict[str, str]) -> RescheduleResult:
    return reschedule_appointment(
        db,
        case["appointment_id"],
        role=role_for(case),
        actor_patient_id=actor_patient_id(case),
        clock=FIXED_CLOCK,
        target_doctor_id=case["doctor_id"],
        target_date=date.fromisoformat(case["date"]),
        target_start_time=time.fromisoformat(case["start_time"]),
    )


def run_rule_case(db: Session, case: dict[str, str]) -> Any:
    if case["action"] == "book":
        return run_booking_case(db, case)
    if case["action"] == "cancel":
        return run_cancellation_case(db, case)
    if case["action"] == "reschedule":
        return run_reschedule_case(db, case)
    raise ValueError(f"Unsupported action: {case['action']}")


def expected_reason_code(case: dict[str, str]) -> ReasonCode | None:
    value = case["reason_code"].strip()
    return ReasonCode[value] if value else None


def selected_cases() -> list[dict[str, str]]:
    cases = {case["test_id"]: case for case in load_rule_cases() if case["test_id"] in SELECTED_IDS}
    return [cases[test_id] for test_id in SELECTED_IDS]
