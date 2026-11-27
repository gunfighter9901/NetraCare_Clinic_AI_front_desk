from datetime import datetime

from app.clock import FixedClock
from app.llm import RedFlagResult
from app.tools import build_tools

NOW = FixedClock(datetime(2026, 11, 2, 10, 0))


def _tools(seeded_db, **overrides):
    kwargs = dict(
        patient_id="P05",
        db=seeded_db,
        clock=NOW,
        red_flag_checker=lambda _t: RedFlagResult(red_flag=False, category="none", why="t"),
        collection_handle=None,
        retrieval_fn=lambda **k: [],
        answer_chain=None,
    )
    kwargs.update(overrides)
    return {t.name: t for t in build_tools(**kwargs)}


def test_all_seven_tools_present_and_no_db_writes_in_source(seeded_db) -> None:
    import pathlib

    tools = _tools(seeded_db)
    assert set(tools) == {
        "search_clinic_docs", "list_doctors", "find_slots", "my_appointments",
        "book_appointment", "cancel_appointment", "reschedule_appointment",
    }
    src = pathlib.Path("app/tools.py").read_text()
    # Tools must not write directly: no direct SQLAlchemy add/commit in tool module.
    assert "db.add" not in src and "db.commit" not in src


def test_read_tools_and_refusal_and_cross_patient(seeded_db) -> None:
    tools = _tools(seeded_db)
    doctors = tools["list_doctors"].invoke({})
    assert doctors["result"] == "ok" and len(doctors["doctors"]) == 5
    mine = tools["my_appointments"].invoke({})
    assert mine["result"] == "ok"
    assert all(a["id"] for a in mine["appointments"])
    # find_slots refusal path (Thursday OFF for Iyer) returns empty, not an exception.
    slots = tools["find_slots"].invoke({
        "doctor_id": "D2", "visit_type": "new",
        "start_date": "2026-11-05", "end_date": "2026-11-05",
    })
    assert slots["result"] == "ok" and slots["slots"] == []
    # Cross-patient: my_appointments for P05 must not include P03's A103.
    ids = {a["id"] for a in mine["appointments"]}
    assert "A103" not in ids


def test_search_docs_tool_exposes_metadata(seeded_db) -> None:
    from app.rag import ChatAnswer, Citation, ClinicAnswer

    def retrieval(**kwargs):
        from app.rag import RetrievedChunk

        return [RetrievedChunk(chunk_id="c1", source="clinic_policy_faq.md", section="Timings", text="t", score=1.0, score_kind="hybrid_fused")]

    class Chain:
        def invoke(self, payload, config=None):
            return ChatAnswer(answer="Open 9 to 6.", source_ids=["c1"], answered=True, response_type="grounded")

    tools = _tools(seeded_db, retrieval_fn=retrieval, answer_chain=Chain())
    out = tools["search_clinic_docs"].invoke({"query": "When open?"})
    assert out["result"] == "ok"
    assert out["sources"] == [{"file": "clinic_policy_faq.md", "section": "Timings"}]
    assert out["answered"] is True
