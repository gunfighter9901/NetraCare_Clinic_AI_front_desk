from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_any_role
from app.models import AuthSession, Doctor
from app.schemas import DoctorView
from app.services.scheduling import opd_days_for_doctor

router = APIRouter(prefix="/doctors", tags=["clinic"])


@router.get(
    "",
    response_model=list[DoctorView],
    summary="List doctors and specialities",
    description="Protected doctor directory with IDs, names, and covered specialities.",
)
def list_doctors(
    db: Session = Depends(get_db), _session: AuthSession = Depends(require_any_role)
) -> list[DoctorView]:
    doctors = db.scalars(select(Doctor).order_by(Doctor.id)).all()
    return [
        DoctorView(
            id=doctor.id,
            name=doctor.name,
            specialities=sorted([item.speciality for item in doctor.specialities]),
            opd_days=opd_days_for_doctor(db, doctor.id),
        )
        for doctor in doctors
    ]
