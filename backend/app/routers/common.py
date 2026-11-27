from fastapi.responses import JSONResponse

from app.llm import EMERGENCY_MESSAGE
from app.models import Appointment
from app.schemas import AppointmentView


def appointment_view(appointment: Appointment, approval=None) -> AppointmentView:
    return AppointmentView(
        id=appointment.id,
        patient_id=appointment.patient_id,
        patient_name=appointment.patient.name,
        doctor_id=appointment.doctor_id,
        doctor_name=appointment.doctor.name,
        speciality=appointment.speciality,
        visit_type=appointment.visit_type,
        date=appointment.date,
        start_time=appointment.start_time,
        end_time=appointment.end_time,
        status=appointment.status,
        created_at=appointment.created_at,
        cancelled_at=appointment.cancelled_at,
        completed_at=appointment.completed_at,
        reason=appointment.reason,
        is_urgent=bool(appointment.is_urgent),
        urgent_case_id=appointment.urgent_case_id,
        approval_request_id=approval.id if approval is not None else None,
        approval_action=approval.action if approval is not None else None,
        approval_status=approval.status if approval is not None else None,
    )


def approval_view(request) -> dict:
    from app.schemas import StaffApprovalRequestView

    target_doctor_name = request.target_doctor.name if getattr(request, "target_doctor", None) else None
    patient_name = request.patient.name if getattr(request, "patient", None) else None
    return StaffApprovalRequestView(
        id=request.id,
        patient_id=request.patient_id,
        patient_name=patient_name,
        appointment_id=request.appointment_id,
        action=request.action,
        status=request.status,
        target_doctor_id=request.target_doctor_id,
        target_doctor_name=target_doctor_name,
        target_date=request.target_date,
        target_start_time=request.target_start_time,
        replacement_appointment_id=request.replacement_appointment_id,
        requested_at=request.requested_at,
        decided_at=request.decided_at,
        decided_by=request.decided_by,
    )


def to_staff_response(appointment, request) -> JSONResponse:
    view = appointment_view(appointment, approval=request).model_dump(mode="json")
    approval = approval_view(request).model_dump(mode="json")
    return JSONResponse(
        status_code=202,
        content={
            "result": "to_staff",
            "reason_code": "INSIDE_2_HOURS",
            "message": "Sent to Staff for approval. The appointment remains booked.",
            "appointment": view,
            "approval_request": approval,
        },
    )


def refusal_response(result) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "result": "refused",
            "reason_code": result.reason_code.value if result.reason_code else None,
            "message": result.message,
        },
    )


def safe_booking_response(result) -> JSONResponse | dict:
    if result.check_failed:
        return JSONResponse(
            status_code=503,
            content={
                "result": "refused",
                "reason_code": "RED_FLAG_CHECK_FAILED",
                "message": result.message,
            },
        )
    if not result.allowed and result.reason_code is None and not result.red_flag:
        # Invalid reason (no rule code)
        return JSONResponse(
            status_code=400,
            content={"result": "refused", "reason_code": "INVALID_REASON", "message": result.message},
        )
    if result.allowed:
        view = appointment_view(result.appointment).model_dump(mode="json")
        if result.red_flag:
            view["emergency"] = EMERGENCY_MESSAGE
            view["urgent_case_id"] = result.urgent_case.id if result.urgent_case else None
        return view
    # Refused by clinic rules (with or without red flag)
    body: dict = {
        "result": "refused",
        "reason_code": result.reason_code.value if result.reason_code else None,
        "message": result.message,
    }
    if result.red_flag:
        body["emergency"] = EMERGENCY_MESSAGE
        body["urgent_case_id"] = result.urgent_case.id if result.urgent_case else None
        if result.urgent_case:
            body["urgent_category"] = result.urgent_case.category
    return JSONResponse(status_code=409, content=body)
