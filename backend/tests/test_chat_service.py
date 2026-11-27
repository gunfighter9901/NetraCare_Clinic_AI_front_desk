from datetime import datetime

import pytest
from sqlalchemy import select

from app.clock import FixedClock
from app.llm import EMERGENCY_MESSAGE, LLMCallFailedError, RedFlagResult
from app.models import Appointment, Patient, UrgentCase, UrgentOrigin
from app.rag import (
    CHAT_SAFETY_FAILURE_MESSAGE,
    CHAT_UNAVAILABLE_MESSAGE,
    ChatAnswer,
    Citation,
    ClinicAnswer,
    RagUnavailableError,
)
from app.services.chat import (
    ChatRagError,
    ChatSafetyError,
    ChatValidationError,
    run_chat,
)

NOW = FixedClock(datetime(2026, 11, 2, 10, 0))


def patient(db, patient_id="P01") -> Patient:
    row = db.get(Patient, patient_id)
    assert row is not None
    return row


def non_urgent(_text):
    return RedFlagResult(red_flag=False, category="none", why="routine")


def red(_text):
    return RedFlagResult(red_flag=True, category="curtain_or_shadow", why="curtain")


def test_red_flag_short_circuits_later_steps(seeded_db) -> None:
    calls: list[str] = []

    def rewrite_fn(*, history, message):
        calls.append("rewrite")
        return message

    def retrieval_fn(*, collection_handle=None, query="", top_k=4):
        calls.append("retrieval")
        return []

    before = seeded_db.scalar(select(__import__("sqlalchemy").func.count()).select_from(Appointment))
    result = run_chat(
        seeded_db, patient=patient(seeded_db), message="A curtain came down over my left eye an hour ago",
        history=[], clock=NOW, red_flag_checker=red,
        rewrite_fn=rewrite_fn, retrieval_fn=retrieval_fn,
    )
    assert result.kind == "emergency"
    assert result.message == EMERGENCY_MESSAGE
    assert result.urgent_category == "curtain_or_shadow"
    assert calls == []
    urgents = seeded_db.scalars(select(UrgentCase)).all()
    assert len(urgents) == 1
    assert urgents[0].origin == UrgentOrigin.CHAT
    assert urgents[0].reason_text == "A curtain came down over my left eye an hour ago"
    assert urgents[0].patient_id == "P01"
    after = seeded_db.scalar(select(__import__("sqlalchemy").func.count()).select_from(Appointment))
    assert after == before


def test_failures_stop_before_side_effects(seeded_db) -> None:
    calls: list[str] = []

    def fail_checker(_text):
        calls.append("checker")
        raise LLMCallFailedError("down")

    def rewrite_fn(*, history, message):
        calls.append("rewrite")
        return message

    with pytest.raises(ChatSafetyError) as exc:
        run_chat(seeded_db, patient=patient(seeded_db), message="Hello",
                 history=[], clock=NOW, red_flag_checker=fail_checker,
                 rewrite_fn=rewrite_fn)
    assert str(exc.value) == CHAT_SAFETY_FAILURE_MESSAGE
    assert calls == ["checker"]
    assert seeded_db.scalars(select(UrgentCase)).all() == []

    def bad_rewrite(*, history, message):
        raise LLMCallFailedError("rewrite down")

    with pytest.raises(ChatRagError) as exc:
        run_chat(seeded_db, patient=patient(seeded_db), message="Hello",
                 history=[], clock=NOW, red_flag_checker=non_urgent,
                 rewrite_fn=bad_rewrite)
    assert str(exc.value) == CHAT_UNAVAILABLE_MESSAGE

    def good_rewrite(*, history, message):
        return message

    def bad_retrieval(**kwargs):
        raise RagUnavailableError("down")

    class FakeChain:
        def invoke(self, payload, config=None):
            return ChatAnswer(answer="x", source_ids=[], answered=True,
                              response_type="grounded")

    with pytest.raises(ChatRagError):
        run_chat(seeded_db, patient=patient(seeded_db), message="Hello",
                 history=[], clock=NOW, red_flag_checker=non_urgent,
                 rewrite_fn=good_rewrite, retrieval_fn=bad_retrieval,
                 answer_chain=FakeChain())


def test_normal_continuation(seeded_db) -> None:
    order: list[str] = []

    def checker(text):
        order.append("check")
        return non_urgent(text)

    def rewrite_fn(*, history, message):
        order.append("rewrite")
        return "standalone?"

    def retrieval_fn(*, collection_handle=None, query="", top_k=4):
        order.append("retrieval")
        assert query == "standalone?"
        from app.rag import RetrievedChunk

        return [RetrievedChunk(chunk_id="c1", source="clinic_policy_faq.md",
                               section="Timings", text="t", score=1.0,
                               score_kind="hybrid_fused")]

    class FakeChain:
        def invoke(self, payload, config=None):
            order.append("answer")
            return ChatAnswer(answer="Open 9 to 6.", source_ids=["c1"],
                              answered=True, response_type="grounded")

    result = run_chat(seeded_db, patient=patient(seeded_db), message="When open?",
                      history=[], clock=NOW, red_flag_checker=checker,
                      rewrite_fn=rewrite_fn, retrieval_fn=retrieval_fn,
                      answer_chain=FakeChain())
    assert order == ["check", "rewrite", "retrieval", "answer"]
    assert result.kind == "answer"
    assert result.message == "Open 9 to 6."
    assert [(c.file, c.section) for c in result.sources] == [("clinic_policy_faq.md", "Timings")]


def test_validation_bounds(seeded_db) -> None:
    from app.services.chat import validate_chat_input

    with pytest.raises(ChatValidationError):
        validate_chat_input("   ", [])
    with pytest.raises(ChatValidationError):
        validate_chat_input("x" * 501, [])
    with pytest.raises(ChatValidationError):
        validate_chat_input("hi", [{"role": "user", "content": "x"}] * 7)
    with pytest.raises(ChatValidationError):
        validate_chat_input("hi", [{"role": "system", "content": "x"}])
    # 500 chars allowed for chat text and urgent persistence.
    long_message = "y" * 500
    result = run_chat(seeded_db, patient=patient(seeded_db), message=long_message,
                      history=[], clock=NOW, red_flag_checker=red)
    assert result.kind == "emergency"
    stored = seeded_db.scalars(select(UrgentCase)).all()[0]
    assert stored.reason_text == long_message
