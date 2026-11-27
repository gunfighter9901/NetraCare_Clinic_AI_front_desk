from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import display_name, get_current_session
from app.models import AuthSession, Doctor
from app.schemas import (
    ActorResponse,
    AuthResponse,
    DoctorLoginRequest,
    DoctorOption,
    PatientLoginRequest,
    StaffLoginRequest,
)
from app.services.auth import (
    AuthenticationError,
    login_doctor,
    login_patient,
    login_staff,
    logout,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def auth_response(session: AuthSession) -> AuthResponse:
    return AuthResponse(
        token=session.token,
        role=session.role,
        patient_id=session.patient_id,
        doctor_id=session.doctor_id,
        display_name=display_name(session),
    )


@router.get(
    "/doctor-options",
    response_model=list[DoctorOption],
    summary="List doctors for login",
    description="Public doctor IDs and names used by the Doctor login picker.",
)
def doctor_options(db: Session = Depends(get_db)) -> list[Doctor]:
    return list(db.scalars(select(Doctor).order_by(Doctor.id)).all())


@router.post(
    "/patient",
    response_model=AuthResponse,
    summary="Log in as a Patient",
    description="Logs in with mobile and name; a new mobile creates a synthetic patient.",
)
def patient_login(payload: PatientLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        return auth_response(login_patient(db, payload.mobile, payload.name))
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error


@router.post(
    "/doctor",
    response_model=AuthResponse,
    summary="Log in as a Doctor",
    description="Logs in by selecting one of the listed doctor IDs.",
)
def doctor_login(payload: DoctorLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        return auth_response(login_doctor(db, payload.doctor_id))
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error


@router.post(
    "/staff",
    response_model=AuthResponse,
    summary="Log in as Staff",
    description="Logs in with a nonempty Staff display name.",
)
def staff_login(payload: StaffLoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    try:
        return auth_response(login_staff(db, payload.name))
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error


@router.get(
    "/me",
    response_model=ActorResponse,
    summary="Show the authenticated actor",
    description="Returns the role and identity derived from the bearer session.",
)
def me(session: AuthSession = Depends(get_current_session)) -> ActorResponse:
    return ActorResponse(
        role=session.role,
        patient_id=session.patient_id,
        doctor_id=session.doctor_id,
        display_name=display_name(session),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out",
    description="Invalidates the bearer session.",
)
def end_session(
    session: AuthSession = Depends(get_current_session), db: Session = Depends(get_db)
) -> Response:
    logout(db, session.token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
