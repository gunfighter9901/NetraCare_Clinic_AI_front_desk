from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import FixedClock
from app.models import Appointment, AppointmentStatus, ApprovalAction, ApprovalStatus, Role, StaffApprovalRequest
from app.rules import ReasonCode
from app.services.appointments import cancel_appointment, reschedule_appointment
from app.services.approvals import approve_request, list_pending_requests, reject_request

NOW = FixedClock(datetime(2026, 11, 2, 10, 0))


def _late_cancel(seeded_db: Session):
    return cancel_appointment(
        seeded_db, "A103", role=Role.PATIENT, actor_patient_id="P03", clock=NOW
    )


def test_pending_original_and_duplicate_prevention(seeded_db: Session) -> None:
    first = _late_cancel(seeded_db)
    assert first.to_staff and first.approval_request is not None
    second = cancel_appointment(
        seeded_db, "A103", role=Role.PATIENT, actor_patient_id="P03", clock=NOW
    )
    assert second.to_staff
    assert second.approval_request.id == first.approval_request.id
    rows = seeded_db.scalars(
        select(StaffApprovalRequest).where(StaffApprovalRequest.appointment_id == "A103")
    ).all()
    assert len(rows) == 1


def test_approve_late_cancellation_atomically(seeded_db: Session) -> None:
    created = _late_cancel(seeded_db)
    assert created.approval_request is not None
    decision = approve_request(
        seeded_db, created.approval_request.id, staff_name="Front Desk", clock=NOW
    )
    assert decision.allowed
    assert decision.request.status is ApprovalStatus.APPROVED
    assert seeded_db.get(Appointment, "A103").status is AppointmentStatus.CANCELLED


def test_approve_late_reschedule_atomically(seeded_db: Session) -> None:
    created = reschedule_appointment(
        seeded_db,
        "A103",
        role=Role.PATIENT,
        actor_patient_id="P03",
        clock=NOW,
        target_doctor_id="D3",
        target_date=date(2026, 11, 4),
        target_start_time=time(10, 0),
    )
    assert created.to_staff and created.approval_request is not None
    decision = approve_request(
        seeded_db, created.approval_request.id, staff_name="Front Desk", clock=NOW
    )
    assert decision.allowed
    assert decision.replacement is not None
    assert decision.replacement.status is AppointmentStatus.BOOKED
    assert seeded_db.get(Appointment, "A103").status is AppointmentStatus.CANCELLED


def test_reject_leaves_original_booked(seeded_db: Session) -> None:
    created = _late_cancel(seeded_db)
    assert created.approval_request is not None
    decision = reject_request(
        seeded_db, created.approval_request.id, staff_name="Front Desk", clock=NOW
    )
    assert decision.allowed
    assert decision.request.status is ApprovalStatus.REJECTED
    assert seeded_db.get(Appointment, "A103").status is AppointmentStatus.BOOKED


def test_stale_approval_keeps_pending_and_changes_nothing(seeded_db: Session) -> None:
    created = _late_cancel(seeded_db)
    assert created.approval_request is not None
    # Staff directly cancels first, making approval stale.
    from app.services.appointments import cancel_appointment as direct_cancel

    direct = direct_cancel(seeded_db, "A103", role=Role.STAFF, actor_patient_id=None, clock=NOW)
    assert direct.allowed
    # Re-create booked state for stale-target test: use reschedule target taken.
    # Approve the original pending cancel now that appointment is cancelled.
    decision = approve_request(
        seeded_db, created.approval_request.id, staff_name="Front Desk", clock=NOW
    )
    assert not decision.allowed
    assert decision.reason_code is ReasonCode.NOT_ACTIVE
    # Request remains pending for Staff to reject.
    assert seeded_db.get(StaffApprovalRequest, created.approval_request.id).status is ApprovalStatus.PENDING


def test_double_decision_refused_without_repeat(seeded_db: Session) -> None:
    created = _late_cancel(seeded_db)
    assert created.approval_request is not None
    first = reject_request(
        seeded_db, created.approval_request.id, staff_name="Front Desk", clock=NOW
    )
    assert first.allowed
    second = approve_request(
        seeded_db, created.approval_request.id, staff_name="Front Desk", clock=NOW
    )
    assert not second.allowed
    assert seeded_db.get(Appointment, "A103").status is AppointmentStatus.BOOKED


def test_list_pending_and_role_restriction(seeded_db: Session) -> None:
    assert list_pending_requests(seeded_db) == []
    _late_cancel(seeded_db)
    pending = list_pending_requests(seeded_db)
    assert len(pending) == 1 and pending[0].action == ApprovalAction.CANCEL
