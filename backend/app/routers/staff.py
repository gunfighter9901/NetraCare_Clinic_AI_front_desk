from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clock import ClinicClock, get_clock
from app.db import get_db
from app.dependencies import require_staff
from app.models import AuthSession, Patient
from app.rag import RagUnavailableError, debug_search
from app.routers.appointments import get_red_flag_checker
from app.routers.common import appointment_view, approval_view, safe_booking_response
from app.rules import BookingCandidate
from app.schemas import (
    AppointmentView,
    PatientView,
    SearchDebugChunk,
    SearchDebugResponse,
    StaffAppointmentRequest,
    StaffApprovalRequestView,
)
from app.services.appointments import (
    EntityNotFound,
    InvalidActor,
    get_latest_requests_map,
    list_staff_appointments,
)
from app.services.approvals import approve_request, list_pending_requests, reject_request
from app.services.safety import safe_book_appointment

router = APIRouter(prefix="/staff", tags=["staff"])


def get_rag_collection():
    from fastapi import HTTPException

    from app.config import get_settings
    from app.rag import get_weaviate_client

    settings = get_settings()
    client = get_weaviate_client()
    if client is None:
        raise HTTPException(status_code=503, detail="Weaviate is not configured; run python build_index.py")
    try:
        if not client.collections.exists(settings.rag_collection):
            raise HTTPException(
                status_code=503,
                detail=f"Collection {settings.rag_collection} is missing; run python build_index.py",
            )
        return client.collections.get(settings.rag_collection)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Retrieval failed: {error}") from error


@router.get(
    "/patients",
    response_model=list[PatientView],
    summary="List patients for Staff",
    description="Returns synthetic patients for the Staff booking workflow.",
)
def list_patients(
    db: Session = Depends(get_db), _session: AuthSession = Depends(require_staff)
) -> list[Patient]:
    return list(db.scalars(select(Patient).order_by(Patient.name, Patient.id)).all())


@router.get(
    "/appointments",
    response_model=list[AppointmentView],
    summary="List clinic appointments",
    description="Staff-only appointment list with optional date and doctor filters.",
)
def staff_appointments(
    appointment_date: date | None = None,
    doctor_id: str | None = None,
    db: Session = Depends(get_db),
    _session: AuthSession = Depends(require_staff),
) -> list[AppointmentView]:
    appointments = list_staff_appointments(db, appointment_date, doctor_id)
    latest = get_latest_requests_map(db, [a.id for a in appointments])
    return [appointment_view(a, approval=latest.get(a.id)) for a in appointments]


@router.post(
    "/appointments",
    summary="Book as Staff",
    description="Books for an existing patient or a new walk-in without bypassing clinic rules.",
)
def create_staff_appointment(
    payload: StaffAppointmentRequest,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_staff),
    clock: ClinicClock = Depends(get_clock),
    red_flag_checker=Depends(get_red_flag_checker),
):
    if not payload.patient_id and not (payload.walk_in_name and payload.walk_in_mobile):
        raise HTTPException(status_code=400, detail="Select a patient or provide walk-in details")
    candidate = BookingCandidate(
        patient_id=payload.patient_id or "",
        doctor_id=payload.doctor_id,
        speciality=payload.speciality,
        visit_type=payload.visit_type,
        date=payload.date,
        start_time=payload.start_time,
    )
    try:
        result = safe_book_appointment(
            db,
            candidate,
            role=session.role,
            actor_patient_id=None,
            clock=clock,
            reason=payload.reason,
            walk_in_name=payload.walk_in_name,
            walk_in_mobile=payload.walk_in_mobile,
            red_flag_checker=red_flag_checker,
        )
    except (EntityNotFound, InvalidActor) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return safe_booking_response(result)


@router.get(
    "/approvals",
    response_model=list[StaffApprovalRequestView],
    summary="List pending Staff approvals",
    description="Staff-only queue of pending late cancellations and reschedules.",
)
def list_approvals(
    db: Session = Depends(get_db),
    _session: AuthSession = Depends(require_staff),
) -> list[StaffApprovalRequestView]:
    requests = list_pending_requests(db)
    return [approval_view(item) for item in requests]


@router.post(
    "/approvals/{request_id}/approve",
    summary="Approve a Staff request",
)
def approve_approval(
    request_id: str,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_staff),
    clock: ClinicClock = Depends(get_clock),
):
    staff_name = session.staff_name or "Staff"
    try:
        decision = approve_request(db, request_id, staff_name=staff_name, clock=clock)
    except EntityNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if not decision.allowed:
        if decision.reason_code is None:
            raise HTTPException(status_code=409, detail=decision.message or "Request already decided")
        return JSONResponse(
            status_code=409,
            content={
                "result": "refused",
                "reason_code": decision.reason_code.value,
                "message": decision.message,
            },
        )
    assert decision.request is not None
    return approval_view(decision.request)


@router.post(
    "/approvals/{request_id}/reject",
    summary="Reject a Staff request",
)
def reject_approval(
    request_id: str,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_staff),
    clock: ClinicClock = Depends(get_clock),
):
    staff_name = session.staff_name or "Staff"
    try:
        decision = reject_request(db, request_id, staff_name=staff_name, clock=clock)
    except EntityNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if not decision.allowed:
        raise HTTPException(status_code=409, detail=decision.message or "Request already decided")
    assert decision.request is not None
    return approval_view(decision.request)


@router.get(
    "/search-debug",
    response_model=SearchDebugResponse,
    summary="Inspect retrieval methods",
    description="Staff-only keyword, vector, and hybrid results with labeled scores.",
)
def search_debug(
    q: str,
    _session: AuthSession = Depends(require_staff),
    collection_handle=Depends(get_rag_collection),
):
    query = (q or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query is required")
    try:
        result = debug_search(collection_handle=collection_handle, query=query)
    except RagUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"Retrieval failed: {error}") from error
    def view(chunk):
        return SearchDebugChunk(
            chunk_id=chunk.chunk_id,
            source=chunk.source,
            section=chunk.section,
            text=chunk.text[:500],
            score=chunk.score,
            score_kind=chunk.score_kind,
        )
    return SearchDebugResponse(
        query=query,
        keyword=[view(c) for c in result.keyword],
        vector=[view(c) for c in result.vector],
        hybrid=[view(c) for c in result.hybrid],
    )
