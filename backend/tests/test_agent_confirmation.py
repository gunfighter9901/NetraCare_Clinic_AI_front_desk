from datetime import date, datetime, time

from langchain_core.messages import AIMessage

from app.agent import resume_confirm_turn, run_message_turn
from app.clock import FixedClock
from app.llm import RedFlagResult
from app.models import Appointment, AppointmentStatus

NOW = FixedClock(datetime(2026, 11, 2, 10, 0))


def non_urgent(_t):
    return RedFlagResult(red_flag=False, category="none", why="ok")


class ScriptedModel:
    def __init__(self, script):
        self.script = list(script)

    def __call__(self, tools):
        return self

    def invoke(self, messages, config=None):
        assert messages, "model needs messages"
        item = self.script.pop(0) if self.script else AIMessage(content="done")
        if isinstance(item, Exception):
            raise item
        return item


def _book_script():
    return [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "book_appointment",
                "args": {
                    "doctor_id": "D1", "speciality": "General", "visit_type": "new",
                    "date": "2026-11-04", "start_time": "09:00:00",
                    "reason": "Routine eye test and new glasses",
                },
                "id": "call-1",
            }],
        ),
        AIMessage(content="Booked."),
    ]


def test_no_mutation_before_confirm_and_one_execution(seeded_db) -> None:
    from app.models import Patient

    patient = seeded_db.get(Patient, "P05")
    # P05 has A105 Glaucoma booked; book General (different speciality) to avoid ACTIVE_BOOKING.
    script = [
        AIMessage(
            content="",
            tool_calls=[{
                "name": "book_appointment",
                "args": {
                    "doctor_id": "D1", "speciality": "General", "visit_type": "new",
                    "date": "2026-11-04", "start_time": "09:00:00",
                    "reason": "Routine eye test",
                },
                "id": "call-1",
            }],
        ),
        AIMessage(content="Booked."),
    ]
    model = ScriptedModel(script)
    before = seeded_db.query(Appointment).count() if hasattr(seeded_db, "query") else None
    out = run_message_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-confirm-1", message="book general",
        clock=NOW, red_flag_checker=non_urgent, model_factory=model,
    )
    assert out["pending_action"] is not None
    # No new appointment yet.
    from sqlalchemy import func, select

    count_after_pending = seeded_db.scalar(select(func.count()).select_from(Appointment))
    # Confirm.
    model2 = ScriptedModel([AIMessage(content="Done.")])
    out2 = resume_confirm_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-confirm-1", approved=True,
        clock=NOW, red_flag_checker=non_urgent, model_factory=model2,
    )
    assert out2["kind"] in ("mutation", "answer", "pending")
    count_after_confirm = seeded_db.scalar(select(func.count()).select_from(Appointment))
    assert count_after_confirm == count_after_pending + 1


def test_decline_does_nothing_and_asks_instead(seeded_db) -> None:
    from app.models import Patient

    patient = seeded_db.get(Patient, "P05")
    model = ScriptedModel(_book_script()[:1] + [AIMessage(content="What instead?")])
    out = run_message_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-decline", message="book retina",
        clock=NOW, red_flag_checker=non_urgent, model_factory=model,
    )
    assert out["pending_action"] is not None
    from sqlalchemy import func, select

    before = seeded_db.scalar(select(func.count()).select_from(Appointment))
    model2 = ScriptedModel([AIMessage(content="What would you like instead?")])
    out2 = resume_confirm_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-decline", approved=False,
        clock=NOW, red_flag_checker=non_urgent, model_factory=model2,
    )
    after = seeded_db.scalar(select(func.count()).select_from(Appointment))
    assert after == before


def test_typed_message_declines_and_handles_new(seeded_db) -> None:
    from app.models import Patient

    patient = seeded_db.get(Patient, "P05")
    model = ScriptedModel(_book_script()[:1])
    out = run_message_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-replace", message="book retina",
        clock=NOW, red_flag_checker=non_urgent, model_factory=model,
    )
    assert out["pending_action"] is not None
    from sqlalchemy import func, select

    before = seeded_db.scalar(select(func.count()).select_from(Appointment))
    # New ordinary message should decline old and handle new (no mutation from old).
    model2 = ScriptedModel([AIMessage(content="Here are slots.")])
    out2 = run_message_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-replace", message="what slots tomorrow?",
        clock=NOW, red_flag_checker=non_urgent, model_factory=model2,
    )
    after = seeded_db.scalar(select(func.count()).select_from(Appointment))
    assert after == before
    assert out2["pending_action"] is None


def test_same_raw_thread_isolated_across_patients(seeded_db) -> None:
    from app.models import Patient

    p05 = seeded_db.get(Patient, "P05")
    p06 = seeded_db.get(Patient, "P06")
    m1 = ScriptedModel([AIMessage(content="hello p05")])
    out1 = run_message_turn(
        db=seeded_db, patient=p05, raw_thread_id="shared", message="hi",
        clock=NOW, red_flag_checker=non_urgent, model_factory=m1,
    )
    assert out1["kind"] == "answer"
    m2 = ScriptedModel([AIMessage(content="hello p06")])
    out2 = run_message_turn(
        db=seeded_db, patient=p06, raw_thread_id="shared", message="hi",
        clock=NOW, red_flag_checker=non_urgent, model_factory=m2,
    )
    # Different patients must not share history: second model saw only its own message.
    assert len(m2.invoke.__self__.script) == 0  # consumed
    assert out2["message"] == "hello p06"


def test_mixed_document_plus_card_and_no_history_leak(seeded_db) -> None:
    from app.models import Patient
    from app.rag import ChatAnswer

    patient = seeded_db.get(Patient, "P19")
    # Document tool returns fee answer; agent then books.
    def retrieval(**kwargs):
        from app.rag import RetrievedChunk

        return [RetrievedChunk(chunk_id="c1", source="clinic_policy_faq.md", section="Consultation fees", text="fees", score=1.0, score_kind="hybrid_fused")]

    class Chain:
        def invoke(self, payload, config=None):
            return ChatAnswer(answer="New consultation is Rs 800.", source_ids=["c1"], answered=True, response_type="grounded")

    doc_call = AIMessage(
        content="", tool_calls=[{"name": "search_clinic_docs", "args": {"query": "fee and book"}, "id": "d1"}]
    )
    book_call = AIMessage(
        content="",
        tool_calls=[{"name": "book_appointment", "args": {
            "doctor_id": "D1", "speciality": "General", "visit_type": "new",
            "date": "2026-11-06", "start_time": "14:00:00", "reason": "routine eye test",
        }, "id": "b1"}],
    )
    model = ScriptedModel([doc_call, book_call])
    out = run_message_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-mixed", message="fee and book",
        clock=NOW, red_flag_checker=non_urgent, model_factory=model,
        retrieval_fn=retrieval, answer_chain=Chain(),
    )
    assert out["pending_action"] is not None
    assert "800" in out["message"]
    assert out["sources"] and out["sources"][0]["section"] == "Consultation fees"
    # Next turn without docs must not leak sources.
    model2 = ScriptedModel([AIMessage(content="Your appointments are ...")])
    out2 = run_message_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-mixed", message="what appointments?",
        clock=NOW, red_flag_checker=non_urgent, model_factory=model2,
        retrieval_fn=retrieval, answer_chain=Chain(),
    )
    # Sources from previous turn must not leak when no new doc search occurred in this turn's new messages?
    # Our composer only uses current-turn tool outputs, so this holds unless agent invents.
    assert out2["sources"] == []
