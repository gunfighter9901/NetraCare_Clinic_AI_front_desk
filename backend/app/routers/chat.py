from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agent import resume_confirm_turn, run_message_turn, validate_thread_id
from app.clock import ClinicClock, get_clock
from app.db import get_db
from app.dependencies import require_patient
from app.models import AuthSession
from app.rag import CHAT_SAFETY_FAILURE_MESSAGE, CHAT_UNAVAILABLE_MESSAGE
from app.routers.appointments import get_red_flag_checker
from app.schemas import ChatPendingAction, ChatRequest, ChatResponse, ChatSource


def get_model_factory():
    return None

router = APIRouter(tags=["chat"])


def _to_sources(items: list[dict]) -> list[ChatSource]:
    out: list[ChatSource] = []
    for item in items or []:
        try:
            out.append(ChatSource(file=item.get("file", ""), section=item.get("section", "")))
        except Exception:
            continue
    return out


def _to_pending(payload: dict | None) -> ChatPendingAction | None:
    if not payload:
        return None
    try:
        return ChatPendingAction(
            action=payload.get("action", "book"),
            summary=payload.get("summary", "Please confirm?"),
            appointment_id=payload.get("appointment_id"),
            doctor_id=payload.get("doctor_id"),
            doctor_name=payload.get("doctor_name"),
            date=payload.get("date"),
            start_time=payload.get("start_time"),
            speciality=payload.get("speciality"),
            visit_type=payload.get("visit_type"),
        )
    except Exception:
        return None


@router.post("/chat", response_model=ChatResponse)
def patient_chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_patient),
    clock: ClinicClock = Depends(get_clock),
    red_flag_checker=Depends(get_red_flag_checker),
    model_factory=Depends(get_model_factory),
):
    if session.patient_id is None or session.patient is None:
        raise HTTPException(status_code=403, detail="Role not allowed")
    try:
        raw_thread = validate_thread_id(payload.thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    has_message = payload.message is not None
    has_confirm = payload.confirm is not None
    if has_message == has_confirm:
        raise HTTPException(status_code=400, detail="Provide exactly one of message or confirm")
    if has_message:
        text = (payload.message or "").strip()
        if not text or len(text) > 500:
            raise HTTPException(status_code=400, detail="Message must be 1-500 characters")
        try:
            out = run_message_turn(
                db=db,
                patient=session.patient,
                raw_thread_id=raw_thread,
                message=text,
                clock=clock,
                red_flag_checker=red_flag_checker,
                model_factory=model_factory,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        kind = out.get("kind")
        if kind == "safety_fail":
            raise HTTPException(status_code=503, detail=CHAT_SAFETY_FAILURE_MESSAGE)
        if kind == "rag_fail":
            raise HTTPException(status_code=503, detail=CHAT_UNAVAILABLE_MESSAGE)
        if kind == "emergency":
            return ChatResponse(
                kind="emergency",
                message=out.get("message", ""),
                sources=[],
                urgent_case_id=out.get("urgent_case_id"),
                urgent_category=out.get("urgent_category"),
                response_type="grounded",
                pending_action=None,
            )
        if kind == "step_fail":
            return ChatResponse(
                kind="answer",
                message=out.get("message", ""),
                sources=[],
                response_type="grounded",
                pending_action=None,
            )
        if kind == "pending":
            return ChatResponse(
                kind="answer",
                message=out.get("message", ""),
                sources=_to_sources(out.get("sources", [])),
                response_type="grounded",
                pending_action=_to_pending(out.get("pending_action")),
            )
        # Final answer / mutation without pending (e.g. availability explained).
        mutation = out.get("mutation") if isinstance(out, dict) else None
        approval_id = None
        if isinstance(mutation, dict) and mutation.get("result") == "to_staff":
            approval_id = mutation.get("approval_request_id")
        return ChatResponse(
            kind="answer",
            message=out.get("message", ""),
            sources=_to_sources(out.get("sources", [])),
            response_type="grounded",
            pending_action=None,
            approval_request_id=approval_id,
        )
    # Confirm path.
    assert payload.confirm is not None
    try:
        out = resume_confirm_turn(
            db=db,
            patient=session.patient,
            raw_thread_id=raw_thread,
            approved=bool(payload.confirm),
            clock=clock,
            red_flag_checker=red_flag_checker,
            model_factory=model_factory,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    kind = out.get("kind")
    if kind == "no_pending":
        raise HTTPException(status_code=409, detail="No pending action to confirm")
    if kind == "safety_fail":
        raise HTTPException(status_code=503, detail=CHAT_SAFETY_FAILURE_MESSAGE)
    if kind == "rag_fail":
        raise HTTPException(status_code=503, detail=CHAT_UNAVAILABLE_MESSAGE)
    if kind == "emergency":
        return ChatResponse(
            kind="emergency",
            message=out.get("message", ""),
            sources=[],
            urgent_case_id=out.get("urgent_case_id"),
            urgent_category=out.get("urgent_category"),
            response_type="grounded",
        )
    if kind == "step_fail":
        return ChatResponse(
            kind="answer", message=out.get("message", ""), sources=[], response_type="grounded"
        )
    if kind == "pending":
        return ChatResponse(
            kind="answer",
            message=out.get("message", ""),
            sources=_to_sources(out.get("sources", [])),
            response_type="grounded",
            pending_action=_to_pending(out.get("pending_action")),
        )
    mutation = out.get("mutation") if isinstance(out, dict) else None
    approval_id = None
    message = out.get("message", "")
    sources = _to_sources(out.get("sources", []))
    if isinstance(mutation, dict):
        res = mutation.get("result")
        if res == "to_staff":
            approval_id = mutation.get("approval_request_id")
            message = message or "Sent to Staff for approval. The appointment remains booked."
        elif res == "booked":
            message = message or f"Booked appointment {mutation.get('appointment_id')}."
        elif res == "cancelled":
            message = message or "Appointment cancelled."
        elif res == "rescheduled":
            message = message or f"Rescheduled to {mutation.get('date')} {mutation.get('start_time')}."
        elif res == "refused":
            message = message or mutation.get("message", "Request refused.")
        elif res == "declined":
            message = message or "Okay, nothing changed. What would you like instead?"
    return ChatResponse(
        kind="answer",
        message=message,
        sources=sources,
        response_type="grounded",
        pending_action=None,
        approval_request_id=approval_id,
    )
