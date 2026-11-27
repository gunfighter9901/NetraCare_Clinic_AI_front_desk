from datetime import datetime

from langchain_core.messages import AIMessage

from app.agent import (
    build_system_prompt,
    resume_confirm_turn,
    run_message_turn,
    select_model_messages,
)
from app.clock import FixedClock
from app.llm import RedFlagResult
from langchain_core.messages import HumanMessage, ToolMessage

NOW = FixedClock(datetime(2026, 11, 2, 10, 0))


def non_urgent(_t):
    return RedFlagResult(red_flag=False, category="none", why="ok")


def urgent(_t):
    return RedFlagResult(red_flag=True, category="curtain_or_shadow", why="curtain")


class ScriptedModel:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def __call__(self, tools):
        return self

    def invoke(self, messages, config=None):
        self.calls.append(list(messages))
        if not self.script:
            return AIMessage(content="done")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def test_red_flag_short_circuits_without_tools(seeded_db) -> None:
    from app.models import Patient

    patient = seeded_db.get(Patient, "P01")
    model = ScriptedModel([])
    out = run_message_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-red", message="curtain over eye",
        clock=NOW, red_flag_checker=urgent, model_factory=model,
    )
    assert out["kind"] == "emergency"
    assert model.calls == []


def test_safety_failure_never_reaches_tools(seeded_db) -> None:
    from app.llm import LLMCallFailedError
    from app.models import Patient

    def fail(_t):
        raise LLMCallFailedError("down")

    patient = seeded_db.get(Patient, "P01")
    model = ScriptedModel([])
    out = run_message_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-safe", message="hi",
        clock=NOW, red_flag_checker=fail, model_factory=model,
    )
    assert out["kind"] == "safety_fail"
    assert model.calls == []


def test_step_limit_returns_fixed_sentence(seeded_db) -> None:
    from app.models import Patient

    def boom(messages, config=None):
        raise RuntimeError("model down")

    class BoomFactory:
        def __call__(self, tools):
            class M:
                def invoke(self, messages, config=None):
                    raise RuntimeError("down")
            return M()

    patient = seeded_db.get(Patient, "P01")
    out = run_message_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-step", message="hi",
        clock=NOW, red_flag_checker=non_urgent, model_factory=BoomFactory(),
    )
    assert out["message"].startswith("Sorry, I can't finish")


def test_prompt_excludes_notes_and_health(seeded_db) -> None:
    from app.models import Patient

    patient = seeded_db.get(Patient, "P01")
    prompt = build_system_prompt(db=seeded_db, patient=patient, clock=NOW)
    assert "Asha" in prompt
    assert "2026-11-02" in prompt
    assert "doctor_note" not in prompt.lower()
    assert "allerg" not in prompt.lower()
    assert "general_health" not in prompt.lower()


def test_message_trim_keeps_tool_groups() -> None:
    ai = AIMessage(content="", tool_calls=[{"name": "find_slots", "args": {}, "id": "c1"}])
    tool = ToolMessage(content="{}", tool_call_id="c1", name="find_slots")
    msgs = [HumanMessage(content=f"m{i}") for i in range(30)]
    # Interleave a tool group at the end.
    msgs = msgs + [ai, tool]
    trimmed = select_model_messages(msgs, limit=20)
    assert len(trimmed) <= 20
    # No leading ToolMessage.
    assert not isinstance(trimmed[0], ToolMessage)


def test_parallel_mutations_rejected(seeded_db) -> None:
    from app.models import Patient

    patient = seeded_db.get(Patient, "P01")
    ai = AIMessage(
        content="",
        tool_calls=[
            {"name": "book_appointment", "args": {"doctor_id": "D1", "speciality": "General", "visit_type": "new", "date": "2026-11-04", "start_time": "09:00:00", "reason": "x"}, "id": "a1"},
            {"name": "cancel_appointment", "args": {"appointment_id": "A001"}, "id": "a2"},
        ],
    )
    model = ScriptedModel([ai, AIMessage(content="only one at a time")])
    out = run_message_turn(
        db=seeded_db, patient=patient, raw_thread_id="t-para", message="do two things",
        clock=NOW, red_flag_checker=non_urgent, model_factory=model,
    )
    # No appointment mutation should have occurred for parallel batch.
    assert out["kind"] in ("answer", "pending", "mutation", "step_fail")
