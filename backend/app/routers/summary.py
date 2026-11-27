from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.clock import ClinicClock, get_clock
from app.db import get_db
from app.dependencies import require_doctor
from app.llm import (
    SUMMARY_FALLBACK,
    SUMMARY_LABEL,
    LLMCallFailedError,
    LLMUnavailableError,
    build_summary_input,
    get_summary,
)
from app.models import AuthSession
from app.schemas import DoctorSummaryResponse, PatientHistoryItem
from app.services.appointments import list_patient_completed_history

router = APIRouter(prefix="/doctor", tags=["doctor-summary"])


def get_summary_fn():
    return get_summary


def _enforce_120_words(text: str) -> str:
    words = text.split()
    if len(words) <= 120:
        return text
    return " ".join(words[:120])


@router.get("/appointments/{appointment_id}/summary", response_model=DoctorSummaryResponse)
def appointment_summary(
    appointment_id: str,
    db: Session = Depends(get_db),
    session: AuthSession = Depends(require_doctor),
    clock: ClinicClock = Depends(get_clock),
    summary_fn=Depends(get_summary_fn),
) -> DoctorSummaryResponse:
    from app.models import Appointment

    appointment = db.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.doctor_id != (session.doctor_id or ""):
        raise HTTPException(status_code=403, detail="You can only view your own appointments")
    patient = appointment.patient
    yob = patient.year_of_birth if patient else None
    age = clock.now().year - yob if yob else None
    history = list_patient_completed_history(db, appointment.patient_id)
    visits = [
        {
            "date": item.date.isoformat(),
            "doctor": item.doctor.name if item.doctor else item.doctor_id,
            "speciality": item.speciality,
            "reason": item.reason or "",
            "doctor_note": item.doctor_note or "",
        }
        for item in history
    ]
    summary_input = build_summary_input(
        age=age,
        general_health=patient.general_health if patient else None,
        allergies=patient.allergies if patient else None,
        today_reason=appointment.reason or "",
        visits_newest_first=visits,
    )
    try:
        raw = summary_fn(summary_input)
        summary = _enforce_120_words(" ".join(raw.split()))
        fallback = False
    except (LLMUnavailableError, LLMCallFailedError, Exception):
        summary = SUMMARY_FALLBACK
        fallback = True
    return DoctorSummaryResponse(
        appointment_id=appointment.id,
        patient_id=appointment.patient_id,
        summary=summary,
        label=SUMMARY_LABEL,
        fallback=fallback,
    )
