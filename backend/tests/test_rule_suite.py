from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Appointment, AppointmentStatus, StaffApprovalRequest
from tests.rule_suite import SELECTED_IDS, expected_reason_code, run_rule_case, selected_cases


def appointment_state(db: Session) -> list[tuple[str, str]]:
    appointments = db.scalars(select(Appointment).order_by(Appointment.id)).all()
    return sorted([(item.id, item.status.value) for item in appointments])


def expected_state_after(
    before: list[tuple[str, str]], case: dict[str, str], result
) -> list[tuple[str, str]]:
    if case["action"] == "book" and getattr(result, "allowed", False):
        combined = before + [(result.appointment.id, AppointmentStatus.BOOKED.value)]
        return sorted(combined)
    if case["action"] == "reschedule" and getattr(result, "allowed", False):
        # Original cancelled, replacement added.
        updated = [
            (
                appointment_id,
                AppointmentStatus.CANCELLED.value
                if appointment_id == case["appointment_id"]
                else status,
            )
            for appointment_id, status in before
        ]
        assert result.appointment is not None
        combined = updated + [(result.appointment.id, AppointmentStatus.BOOKED.value)]
        return sorted(combined)
    if case["action"] == "cancel" and getattr(result, "allowed", False):
        return sorted(
            [
                (appointment_id, AppointmentStatus.CANCELLED.value if appointment_id == case["appointment_id"] else status)
                for appointment_id, status in before
            ]
        )
    return sorted(before)


def test_exactly_thirty_eight_cases_are_selected_including_rescheduling() -> None:
    cases = selected_cases()
    assert [case["test_id"] for case in cases] == list(SELECTED_IDS)
    assert len({case["test_id"] for case in cases}) == 38
    assert any(case["action"] == "reschedule" for case in cases)


def test_selected_rule_cases(seeded_db: Session, rule_case: dict[str, str]) -> None:
    case = rule_case
    before = appointment_state(seeded_db)
    result = run_rule_case(seeded_db, case)
    expected = (case["expected"] or "").strip()
    if expected == "allowed":
        assert getattr(result, "allowed", False) is True
        assert getattr(result, "to_staff", False) is False
        assert result.appointment is not None
        assert appointment_state(seeded_db) == expected_state_after(before, case, result)
        assert expected_reason_code(case) is None
    elif expected == "to_staff":
        assert getattr(result, "allowed", False) is False
        assert getattr(result, "to_staff", False) is True
        assert result.reason_code == expected_reason_code(case)
        assert result.message
        assert result.approval_request is not None
        # Original preserved; approval queued.
        assert appointment_state(seeded_db) == before
        pending = seeded_db.scalar(
            select(StaffApprovalRequest).where(
                StaffApprovalRequest.appointment_id == case["appointment_id"],
                StaffApprovalRequest.status == "pending",
            )
        )
        # SQLAlchemy enum comparison uses string value in SQLite partial index.
        assert pending is not None
    else:
        assert getattr(result, "allowed", False) is False
        assert getattr(result, "to_staff", False) is False
        assert getattr(result, "appointment", None) is None
        assert result.reason_code == expected_reason_code(case)
        assert result.message
        assert appointment_state(seeded_db) == before


def pytest_generate_tests(metafunc) -> None:
    if "rule_case" in metafunc.fixturenames and metafunc.function.__name__ == "test_selected_rule_cases":
        cases = selected_cases()
        metafunc.parametrize("rule_case", cases, ids=[case["test_id"] for case in cases])
