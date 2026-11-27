from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.dependencies import require_patient
from app.llm import FACT_CAVET, FACT_FALLBACK, LLMCallFailedError, LLMUnavailableError, get_fact
from app.models import AuthSession
from app.schemas import FactResponse

router = APIRouter(tags=["fact"])


def get_fact_fn():
    return get_fact


@router.get("/fact-of-the-day", response_model=FactResponse)
def fact_of_the_day(
    previous: str | None = None,
    db: Session = Depends(get_db),
    _session: AuthSession = Depends(require_patient),
    fact_fn=Depends(get_fact_fn),
) -> FactResponse:
    try:
        fact = fact_fn(previous)
    except (LLMUnavailableError, LLMCallFailedError, Exception):
        fact = FACT_FALLBACK
    return FactResponse(fact=fact, caveat=FACT_CAVET)
