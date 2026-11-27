"""Staff approval queue for late Patient cancellations and reschedules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import ClinicClock
from app.models import (
    Appointment,
    AppointmentStatus,
    ApprovalAction,
    ApprovalStatus,
    Role,
    StaffApprovalRequest,
)
from app.rules import ReasonCode, RuleDecision
from app.services.appointments import (
    EntityNotFound,
    InvalidActor,
    _apply_cancel_no_commit,
    _build_replacement_no_commit,
    _evaluate_reschedule_target,
)


@dataclass(frozen=True)
class ApprovalDecision:
    allowed: bool
    appointment: Appointment | None = None
    replacement: Appointment | None = None
    request: StaffApprovalRequest | None = None
    reason_code: ReasonCode | None = None
    message: str | None = None


def _pending_or_raise(db: Session, request_id: str) -> StaffApprovalRequest:
    request = db.get(StaffApprovalRequest, request_id)
    if request is None:
        raise EntityNotFound("Approval request not found")
    return request


def list_pending_requests(db: Session) -> list[StaffApprovalRequest]:
    return list(
        db.scalars(
            select(StaffApprovalRequest)
            .where(StaffApprovalRequest.status == ApprovalStatus.PENDING)
            .order_by(StaffApprovalRequest.requested_at, StaffApprovalRequest.id)
        ).all()
    )


def list_all_requests(db: Session, *, include_decided: bool = True) -> list[StaffApprovalRequest]:
    query = select(StaffApprovalRequest).order_by(
        StaffApprovalRequest.requested_at.desc(), StaffApprovalRequest.id.desc()
    )
    if not include_decided:
        query = query.where(StaffApprovalRequest.status == ApprovalStatus.PENDING)
    return list(db.scalars(query).all())


def approve_request(
    db: Session, request_id: str, *, staff_name: str, clock: ClinicClock
) -> ApprovalDecision:
    request = _pending_or_raise(db, request_id)
    if request.status is not ApprovalStatus.PENDING:
        return ApprovalDecision(
            allowed=False,
            request=request,
            reason_code=None,
            message="Request has already been decided",
        )
    original = db.get(Appointment, request.appointment_id)
    if original is None:
        db.rollback()
        return ApprovalDecision(
            allowed=False,
            request=request,
            reason_code=ReasonCode.NOT_ACTIVE,
            message="Only a booked appointment can be cancelled",
        )
    try:
        if original.status is not AppointmentStatus.BOOKED:
            db.rollback()
            return ApprovalDecision(
                allowed=False,
                request=request,
                reason_code=ReasonCode.NOT_ACTIVE,
                message="Only a booked appointment can be cancelled",
            )
        if request.action == ApprovalAction.CANCEL:
            _apply_cancel_no_commit(original, clock)
            request.status = ApprovalStatus.APPROVED
            request.decided_at = clock.now()
            request.decided_by = staff_name
            db.commit()
            db.refresh(original)
            db.refresh(request)
            return ApprovalDecision(allowed=True, appointment=original, request=request)
        if request.action == ApprovalAction.RESCHEDULE:
            if not request.target_doctor_id or not request.target_date or not request.target_start_time:
                db.rollback()
                return ApprovalDecision(
                    allowed=False,
                    request=request,
                    reason_code=None,
                    message="Reschedule request is missing its target",
                )
            decision = _evaluate_reschedule_target(
                db,
                original,
                request.target_doctor_id,
                request.target_date,
                request.target_start_time,
                clock.now(),
            )
            if not decision.allowed:
                db.rollback()
                return ApprovalDecision(
                    allowed=False,
                    request=request,
                    reason_code=decision.reason_code,
                    message=decision.message,
                )
            _apply_cancel_no_commit(original, clock)
            replacement = _build_replacement_no_commit(
                db,
                original,
                request.target_doctor_id,
                request.target_date,
                request.target_start_time,
                clock,
            )
            request.status = ApprovalStatus.APPROVED
            request.decided_at = clock.now()
            request.decided_by = staff_name
            request.replacement_appointment_id = replacement.id
            db.commit()
            db.refresh(original)
            db.refresh(replacement)
            db.refresh(request)
            return ApprovalDecision(
                allowed=True, appointment=original, replacement=replacement, request=request
            )
        db.rollback()
        return ApprovalDecision(
            allowed=False, request=request, reason_code=None, message="Unknown approval action"
        )
    except Exception:
        db.rollback()
        raise


def reject_request(
    db: Session, request_id: str, *, staff_name: str, clock: ClinicClock
) -> ApprovalDecision:
    request = _pending_or_raise(db, request_id)
    if request.status is not ApprovalStatus.PENDING:
        return ApprovalDecision(
            allowed=False,
            request=request,
            reason_code=None,
            message="Request has already been decided",
        )
    try:
        request.status = ApprovalStatus.REJECTED
        request.decided_at = clock.now()
        request.decided_by = staff_name
        db.commit()
        db.refresh(request)
        original = db.get(Appointment, request.appointment_id)
        return ApprovalDecision(allowed=True, appointment=original, request=request)
    except Exception:
        db.rollback()
        raise
