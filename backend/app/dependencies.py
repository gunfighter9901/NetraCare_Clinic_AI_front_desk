from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuthSession, Role
from app.services.auth import resolve_session

bearer = HTTPBearer(auto_error=False)


def get_current_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> AuthSession:
    token = credentials.credentials if credentials else None
    session = resolve_session(db, token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return session


def require_roles(*roles: Role) -> Callable:
    def role_dependency(session: AuthSession = Depends(get_current_session)) -> AuthSession:
        if session.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Role not allowed")
        return session

    return role_dependency


require_patient = require_roles(Role.PATIENT)
require_staff = require_roles(Role.STAFF)
require_doctor = require_roles(Role.DOCTOR)
require_patient_or_staff = require_roles(Role.PATIENT, Role.STAFF)
require_any_role = require_roles(Role.PATIENT, Role.STAFF, Role.DOCTOR)


def display_name(session: AuthSession) -> str:
    if session.role is Role.PATIENT and session.patient:
        return session.patient.name
    if session.role is Role.DOCTOR and session.doctor:
        return session.doctor.name
    return session.staff_name or "Staff"
