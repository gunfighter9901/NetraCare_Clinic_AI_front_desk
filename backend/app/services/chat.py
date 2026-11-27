"""Patient chat orchestration: validation, safety-first ordering, urgent persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from app.clock import ClinicClock
from app.llm import (
    EMERGENCY_MESSAGE,
    LLMCallFailedError,
    LLMUnavailableError,
    RedFlagResult,
    check_red_flags,
)
from app.models import Patient, UrgentCase, UrgentOrigin
from app.rag import (
    CHAT_SAFETY_FAILURE_MESSAGE,
    CHAT_UNAVAILABLE_MESSAGE,
    Citation,
    RagUnavailableError,
    answer_clinic_question,
    rewrite_question,
)
from app.services.safety import create_urgent_case


class ChatValidationError(ValueError):
    pass


class ChatSafetyError(RuntimeError):
    def __init__(self, message: str = CHAT_SAFETY_FAILURE_MESSAGE):
        super().__init__(message)
        self.message = message


class ChatRagError(RuntimeError):
    def __init__(self, message: str = CHAT_UNAVAILABLE_MESSAGE):
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class ChatSuccess:
    kind: str  # "emergency" or "answer"
    message: str
    sources: list[Citation] = field(default_factory=list)
    urgent_case_id: str | None = None
    urgent_category: str | None = None
    response_type: str = "grounded"


def validate_chat_input(message: str | None, history: list | None) -> tuple[str, list[dict[str, str]]]:
    cleaned = (message or "").strip()
    if not cleaned:
        raise ChatValidationError("Message is required")
    if len(cleaned) > 500:
        raise ChatValidationError("Message must be at most 500 characters")
    items = list(history or [])
    if len(items) > 6:
        raise ChatValidationError("History must contain at most 6 messages")
    normalized: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ChatValidationError("Invalid history entry")
        role = item.get("role")
        content = (item.get("content", "") or "").strip()
        if role not in ("user", "assistant"):
            raise ChatValidationError("Invalid history role")
        if not content:
            raise ChatValidationError("History content must be nonempty")
        limit = 500 if role == "user" else 2000
        if len(content) > limit:
            raise ChatValidationError("History entry is too long")
        normalized.append({"role": role, "content": content})
    return cleaned, normalized


def run_chat(
    db: Session,
    *,
    patient: Patient,
    message: str,
    history: list | None,
    clock: ClinicClock,
    red_flag_checker=None,
    rewrite_fn=None,
    retrieval_fn=None,
    answer_chain=None,
    collection_handle=None,
) -> ChatSuccess:
    """Validate, safety-check, rewrite, retrieve, answer. Raises on failure."""
    cleaned_message, normalized_history = validate_chat_input(message, history)
    checker = red_flag_checker or check_red_flags
    try:
        red_result: RedFlagResult = checker(cleaned_message)
    except (LLMUnavailableError, LLMCallFailedError) as error:
        raise ChatSafetyError() from error
    except Exception as error:
        raise ChatSafetyError() from error
    if red_result.red_flag:
        now: datetime = clock.now()
        urgent: UrgentCase = create_urgent_case(
            db,
            patient_id=patient.id,
            patient_name=patient.name,
            patient_mobile=patient.mobile,
            reason_text=cleaned_message,
            category=red_result.category,
            model_why=red_result.why,
            now=now,
            origin=UrgentOrigin.CHAT,
        )
        return ChatSuccess(
            kind="emergency",
            message=EMERGENCY_MESSAGE,
            sources=[],
            urgent_case_id=urgent.id,
            urgent_category=urgent.category,
            response_type="grounded",
        )
    rewrite = rewrite_fn or rewrite_question
    try:
        standalone = rewrite(history=normalized_history, message=cleaned_message)
    except (LLMUnavailableError, LLMCallFailedError) as error:
        raise ChatRagError() from error
    except Exception as error:
        raise ChatRagError() from error
    try:
        answered = answer_clinic_question(
            question=standalone,
            collection_handle=collection_handle,
            retrieval_fn=retrieval_fn,
            answer_chain=answer_chain,
        )
    except (RagUnavailableError, LLMUnavailableError, LLMCallFailedError) as error:
        raise ChatRagError() from error
    except Exception as error:
        raise ChatRagError() from error
    return ChatSuccess(
        kind="answer",
        message=answered.message,
        sources=list(answered.sources),
        response_type=answered.response_type,
    )
