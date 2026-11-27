from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.clock import ClinicClock, get_clock
from app.db import get_db
from app.dependencies import require_staff
from app.models import AuthSession
from app.schemas import UrgentCaseView
from app.services.safety import list_urgent_cases, mark_urgent_seen

router = APIRouter(prefix="/urgent-cases", tags=["urgent-cases"])


@router.get("", response_model=list[UrgentCaseView])
def get_urgent_cases(
    db: Session = Depends(get_db),
    _session: AuthSession = Depends(require_staff),
) -> list[UrgentCaseView]:
    cases = list_urgent_cases(db)
    return [UrgentCaseView.model_validate(case, from_attributes=True) for case in cases]


@router.post("/{urgent_id}/seen", response_model=UrgentCaseView)
def mark_seen(
    urgent_id: str,
    db: Session = Depends(get_db),
    _session: AuthSession = Depends(require_staff),
    clock: ClinicClock = Depends(get_clock),
) -> UrgentCaseView:
    urgent = mark_urgent_seen(db, urgent_id, now=clock.now())
    if urgent is None:
        raise HTTPException(status_code=404, detail="Urgent case not found")
    return UrgentCaseView.model_validate(urgent, from_attributes=True)
