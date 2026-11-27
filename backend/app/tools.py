"""Iteration 4 service-backed tools. Patient identity comes from trusted config, never LLM args."""

from __future__ import annotations

import datetime as dt
from datetime import date, datetime
from typing import Any

from langchain_core.tools import tool


def _get_ctx(config: dict | None) -> dict:
    if not config:
        return {}
    cfg = config.get("configurable", {}) if isinstance(config, dict) else {}
    return cfg if isinstance(cfg, dict) else {}


def build_tools(
    *,
    patient_id: str,
    db,
    clock,
    red_flag_checker=None,
    collection_handle=None,
    retrieval_fn=None,
    answer_chain=None,
):
    """Build the seven tools closing over request-scoped dependencies."""
    from app.clock import ClinicClock
    from app.models import Role, VisitType
    from app.rag import (
        CHAT_UNAVAILABLE_MESSAGE,
        RagUnavailableError,
        answer_clinic_question,
    )
    from app.rules import BookingCandidate
    from app.services import appointments as appt_svc
    from app.services.safety import safe_book_appointment
    from app.services.scheduling import opd_days_for_doctor, search_availability
    from langgraph.types import interrupt

    # --- read tools ---

    @tool
    def search_clinic_docs(query: str) -> dict:
        """Search clinic documents for policy, procedure, fee, or speciality guidance. Returns answer, sources, and whether documents answered."""
        q = (query or "").strip()
        if not q:
            return {"result": "refused", "message": "Query is required"}
        handle = collection_handle
        if handle is None and retrieval_fn is None:
            # Lazy Weaviate lookup so pure booking turns do not require retrieval.
            try:
                from app.config import get_settings
                from app.rag import get_weaviate_client

                settings = get_settings()
                client = get_weaviate_client()
                if client is not None and client.collections.exists(settings.rag_collection):
                    handle = client.collections.get(settings.rag_collection)
            except Exception:
                handle = None
        try:
            answered = answer_clinic_question(
                question=q,
                collection_handle=handle,
                retrieval_fn=retrieval_fn,
                answer_chain=answer_chain,
            )
        except RagUnavailableError as exc:
            return {"result": "error", "reason_code": "RAG_UNAVAILABLE", "message": str(exc) or CHAT_UNAVAILABLE_MESSAGE}
        except Exception as exc:
            return {"result": "error", "reason_code": "RAG_FAILED", "message": CHAT_UNAVAILABLE_MESSAGE}
        sources = [{"file": c.file, "section": c.section} for c in (answered.sources or [])]
        return {
            "result": "ok",
            "message": answered.message,
            "sources": sources,
            "answered": not getattr(answered, "fallback", False) and bool(answered.message),
            "response_type": getattr(answered, "response_type", "grounded"),
        }

    @tool
    def list_doctors() -> dict:
        """List doctors with IDs, specialities, and OPD days."""
        try:
            doctors = appt_svc.list_doctors_with_opd(db) if hasattr(appt_svc, "list_doctors_with_opd") else None
        except Exception:
            doctors = None
        if doctors is None:
            # Fallback inline (avoids import cycle in tests).
            from sqlalchemy import select

            from app.models import Doctor

            rows = list(db.scalars(select(Doctor).order_by(Doctor.id)).all())
            doctors = [
                {
                    "id": d.id,
                    "name": d.name,
                    "specialities": sorted([s.speciality for s in d.specialities]),
                    "opd_days": opd_days_for_doctor(db, d.id),
                }
                for d in rows
            ]
        return {"result": "ok", "doctors": doctors}

    @tool
    def find_slots(
        speciality: str | None = None,
        doctor_id: str | None = None,
        visit_type: str = "new",
        start_date: str | None = None,
        end_date: str | None = None,
        session: str | None = None,
    ) -> dict:
        """Find free start times for a speciality or doctor over a date range and optional AM/PM session. At most 10, earliest first."""
        try:
            vt = VisitType(visit_type) if visit_type in ("new", "follow_up") else VisitType.NEW
        except Exception:
            vt = VisitType.NEW
        try:
            sd = dt.date.fromisoformat(start_date) if start_date else None
            ed = dt.date.fromisoformat(end_date) if end_date else None
        except Exception:
            return {"result": "refused", "reason_code": "INVALID_DATE", "message": "Dates must be YYYY-MM-DD"}
        try:
            agg = search_availability(
                db,
                visit_type=vt,
                clock=clock,
                doctor_id=doctor_id,
                speciality=speciality,
                start_date=sd,
                end_date=ed,
                session=session,
                limit=10,
            )
        except LookupError as exc:
            return {"result": "refused", "reason_code": "DOCTOR_NOT_FOUND", "message": str(exc)}
        except Exception as exc:
            return {"result": "error", "message": f"Slot search failed: {exc}"}
        slots = [
            {
                "doctor_id": s.doctor_id,
                "doctor_name": s.doctor_name,
                "date": s.date.isoformat(),
                "start_time": s.start_time.strftime("%H:%M:%S"),
                "speciality": s.speciality,
                "visit_type": s.visit_type.value,
            }
            for s in agg.slots
        ]
        return {
            "result": "ok",
            "slots": slots,
            "message": agg.message,
            "searched_doctors": agg.searched_doctors,
            "searched_days": agg.searched_days,
        }

    @tool
    def my_appointments() -> dict:
        """List the authenticated patient's upcoming appointments with IDs and Staff request status."""
        try:
            items = appt_svc.list_upcoming_patient_items(db, patient_id, clock)
        except Exception as exc:
            return {"result": "error", "message": f"Could not list appointments: {exc}"}
        return {"result": "ok", "appointments": items}

    # --- mutation tools with interrupt-before-service ---

    def _interrupt_summary(payload: dict) -> Any:
        # Pre-interrupt work is read-only: payload already contains summary.
        return interrupt(payload)

    @tool
    def book_appointment(
        doctor_id: str,
        speciality: str,
        visit_type: str,
        date: str,
        start_time: str,
        reason: str,
    ) -> dict:
        """Book an appointment for the authenticated patient. Pauses for patient confirmation before changing anything."""
        from datetime import time as dtime

        try:
            vt = VisitType(visit_type)
            d = dt.date.fromisoformat(date)
            st = dt.time.fromisoformat(start_time)
        except Exception:
            return {"result": "refused", "reason_code": "INVALID_INPUT", "message": "Invalid doctor, date, or time"}
        # Read-only summary before interrupt.
        try:
            from app.models import Doctor as DoctorModel

            doc = db.get(DoctorModel, doctor_id)
            doc_name = doc.name if doc else doctor_id
        except Exception:
            doc_name = doctor_id
        summary = f"Book {doc_name}, {speciality} {'follow-up' if vt.value=='follow_up' else 'new'} ({10 if vt.value=='follow_up' else 20} min), {d.isoformat()} {st.strftime('%H:%M')}?"
        resume = _interrupt_summary(
            {"action": "book", "summary": summary, "args": {
                "doctor_id": doctor_id, "speciality": speciality, "visit_type": vt.value,
                "date": d.isoformat(), "start_time": st.strftime("%H:%M:%S"), "reason": reason,
            }}
        )
        approved = resume is True or (isinstance(resume, dict) and resume.get("approved") is True)
        decline_only = isinstance(resume, dict) and resume.get("decline_only") is True
        if decline_only:
            return {"result": "declined_superseded", "message": "Superseded by new message"}
        if not approved:
            return {"result": "declined", "message": "Declined by patient"}
        candidate = BookingCandidate(
            patient_id=patient_id,
            doctor_id=doctor_id,
            speciality=speciality,
            visit_type=vt,
            date=d,
            start_time=st,
        )
        try:
            result = safe_book_appointment(
                db,
                candidate,
                role=Role.PATIENT,
                actor_patient_id=patient_id,
                clock=clock,
                reason=reason,
                red_flag_checker=red_flag_checker,
            )
        except Exception as exc:
            return {"result": "error", "message": f"Booking failed: {exc}"}
        if getattr(result, "check_failed", False):
            return {"result": "error", "reason_code": "RED_FLAG_CHECK_FAILED", "message": result.message}
        if not result.allowed:
            return {"result": "refused", "reason_code": result.reason_code.value if result.reason_code else None, "message": result.message}
        assert result.appointment is not None
        return {
            "result": "booked",
            "appointment_id": result.appointment.id,
            "date": result.appointment.date.isoformat(),
            "start_time": result.appointment.start_time.strftime("%H:%M:%S"),
        }

    @tool
    def cancel_appointment(appointment_id: str) -> dict:
        """Cancel one of the authenticated patient's appointments by ID. Pauses for confirmation."""
        # Read-only: fetch display name without mutating.
        try:
            appt = db.get(__import__("app.models", fromlist=["Appointment"]).Appointment, appointment_id)
            label = f"{appt.date.isoformat()} {appt.start_time.strftime('%H:%M')}" if appt else appointment_id
        except Exception:
            label = appointment_id
        summary = f"Cancel appointment {appointment_id} ({label})?"
        resume = _interrupt_summary({"action": "cancel", "summary": summary, "args": {"appointment_id": appointment_id}})
        approved = resume is True or (isinstance(resume, dict) and resume.get("approved") is True)
        decline_only = isinstance(resume, dict) and resume.get("decline_only") is True
        if decline_only:
            return {"result": "declined_superseded", "message": "Superseded by new message"}
        if not approved:
            return {"result": "declined", "message": "Declined by patient"}
        try:
            result = appt_svc.cancel_appointment(
                db, appointment_id, role=Role.PATIENT, actor_patient_id=patient_id, clock=clock
            )
        except Exception as exc:
            if exc.__class__.__name__ == "EntityNotFound":
                return {"result": "refused", "reason_code": "NOT_FOUND", "message": "Appointment not found"}
            return {"result": "error", "message": f"Cancel failed: {exc}"}
        if getattr(result, "to_staff", False):
            return {
                "result": "to_staff",
                "reason_code": "INSIDE_2_HOURS",
                "message": result.message,
                "approval_request_id": result.approval_request.id if result.approval_request else None,
            }
        if not result.allowed:
            code = result.reason_code.value if result.reason_code else None
            # Do not leak other-patient details: service already returns generic.
            return {"result": "refused", "reason_code": code, "message": result.message}
        return {"result": "cancelled", "appointment_id": appointment_id}

    @tool
    def reschedule_appointment(appointment_id: str, doctor_id: str, date: str, start_time: str) -> dict:
        """Reschedule one appointment to a new doctor/date/start. Pauses for confirmation; one card only."""
        from datetime import time as dtime

        try:
            d = dt.date.fromisoformat(date)
            st = dt.time.fromisoformat(start_time)
        except Exception:
            return {"result": "refused", "reason_code": "INVALID_INPUT", "message": "Invalid date or time"}
        summary = f"Reschedule {appointment_id} to {d.isoformat()} {st.strftime('%H:%M')} with {doctor_id}?"
        resume = _interrupt_summary(
            {"action": "reschedule", "summary": summary, "args": {
                "appointment_id": appointment_id, "doctor_id": doctor_id,
                "date": d.isoformat(), "start_time": st.strftime("%H:%M:%S"),
            }}
        )
        approved = resume is True or (isinstance(resume, dict) and resume.get("approved") is True)
        decline_only = isinstance(resume, dict) and resume.get("decline_only") is True
        if decline_only:
            return {"result": "declined_superseded", "message": "Superseded by new message"}
        if not approved:
            return {"result": "declined", "message": "Declined by patient"}
        try:
            result = appt_svc.reschedule_appointment(
                db,
                appointment_id,
                role=Role.PATIENT,
                actor_patient_id=patient_id,
                clock=clock,
                target_doctor_id=doctor_id,
                target_date=d,
                target_start_time=st,
            )
        except Exception as exc:
            if exc.__class__.__name__ == "EntityNotFound":
                return {"result": "refused", "reason_code": "NOT_FOUND", "message": "Appointment not found"}
            return {"result": "error", "message": f"Reschedule failed: {exc}"}
        if getattr(result, "to_staff", False):
            return {
                "result": "to_staff",
                "reason_code": "INSIDE_2_HOURS",
                "message": result.message,
                "approval_request_id": result.approval_request.id if result.approval_request else None,
            }
        if not result.allowed:
            code = result.reason_code.value if result.reason_code else None
            return {"result": "refused", "reason_code": code, "message": result.message}
        assert result.appointment is not None
        return {
            "result": "rescheduled",
            "appointment_id": result.appointment.id,
            "date": result.appointment.date.isoformat(),
            "start_time": result.appointment.start_time.strftime("%H:%M:%S"),
        }

    return [
        search_clinic_docs,
        list_doctors,
        find_slots,
        my_appointments,
        book_appointment,
        cancel_appointment,
        reschedule_appointment,
    ]
