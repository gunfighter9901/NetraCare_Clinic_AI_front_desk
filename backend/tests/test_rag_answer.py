import pytest

from app.llm import LLMCallFailedError
from app.rag import (
    CHAT_NON_EYE_MESSAGE,
    CHAT_OUT_OF_SCOPE_MESSAGE,
    CHAT_UNSUPPORTED_MESSAGE,
    ChatAnswer,
    RagUnavailableError,
    RetrievedChunk,
    answer_clinic_question,
)


def chunk(chunk_id="c1", source="clinic_policy_faq.md", section="Timings"):
    return RetrievedChunk(
        chunk_id=chunk_id, source=source, section=section,
        text=f"{section} text", score=1.0, score_kind="hybrid_fused",
    )


class FakeAnswerChain:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def invoke(self, payload, config=None):
        if self.error:
            raise self.error
        return self.result


def test_grounded_answer_builds_ordered_citations() -> None:
    def retrieve(*, collection_handle=None, query="", top_k=4):
        return [chunk("c1", section="Timings"), chunk("c2", section="Booking an appointment")]
    result = ChatAnswer(answer="Open 9 to 6.", source_ids=["c2", "c1"],
                        answered=True, response_type="grounded")
    out = answer_clinic_question(question="When open?", retrieval_fn=retrieve,
                                 answer_chain=FakeAnswerChain(result=result))
    assert out.message == "Open 9 to 6."
    # Citations follow retrieval order, even though the model listed c2 first.
    assert [(c.file, c.section) for c in out.sources] == [
        ("clinic_policy_faq.md", "Timings"),
        ("clinic_policy_faq.md", "Booking an appointment"),
    ]


def test_citation_dedupes_shared_section() -> None:
    def retrieve(*, collection_handle=None, query="", top_k=4):
        return [chunk("c1", section="Timings"), chunk("c2", section="Timings")]
    result = ChatAnswer(answer="Hours.", source_ids=["c1", "c2"],
                        answered=True, response_type="grounded")
    out = answer_clinic_question(question="Hours?", retrieval_fn=retrieve,
                                 answer_chain=FakeAnswerChain(result=result))
    assert len(out.sources) == 1
    assert out.sources[0].section == "Timings"


def test_unsupported_branches() -> None:
    chunks = [chunk("c1")]
    def retrieve(*, collection_handle=None, query="", top_k=4):
        return chunks
    cases = [
        ChatAnswer(answer="x", source_ids=[], answered=True, response_type="grounded"),
        ChatAnswer(answer="x", source_ids=["c1"], answered=False, response_type="grounded"),
        ChatAnswer(answer="x", source_ids=["missing"], answered=True, response_type="grounded"),
        ChatAnswer(answer="  ", source_ids=["c1"], answered=True, response_type="grounded"),
    ]
    for result in cases:
        out = answer_clinic_question(question="q", retrieval_fn=retrieve,
                                     answer_chain=FakeAnswerChain(result=result))
        assert out.message == CHAT_UNSUPPORTED_MESSAGE
        assert out.sources == []
        assert out.fallback is True


def test_capability_replies_have_no_sources() -> None:
    for response_type, message in (
        ("non_eye", CHAT_NON_EYE_MESSAGE),
        ("out_of_scope", CHAT_OUT_OF_SCOPE_MESSAGE),
    ):
        result = ChatAnswer(answer="ignored", source_ids=[], answered=True,
                            response_type=response_type)
        # Booking must not invoke scheduling: retrieval_fn raising proves no
        # retrieval/scheduling call happens before the fixed reply... except
        # retrieval runs before answer, so test booking short-circuit after retrieval.
        def retrieve_ok_inner(*, collection_handle=None, query="", top_k=4):
            return [chunk("c1")]
        out = answer_clinic_question(question="q", retrieval_fn=retrieve_ok_inner,
                                     answer_chain=FakeAnswerChain(result=result))
        assert out.message == message
        assert out.sources == []


def test_booking_response_type_has_no_stale_message() -> None:
    from app.rag import ChatAnswer
    result = ChatAnswer(answer="ignored", source_ids=[], answered=True,
                        response_type="booking")
    def retrieve_ok_inner(*, collection_handle=None, query="", top_k=4):
        return [chunk("c1")]
    out = answer_clinic_question(question="q", retrieval_fn=retrieve_ok_inner,
                                 answer_chain=FakeAnswerChain(result=result))
    assert out.response_type == "booking"
    assert out.sources == []
    assert "cannot book" not in out.message.lower()
    assert "book section" not in out.message.lower()


def test_long_answer_truncated_to_120_words() -> None:
    long_answer = " ".join(f"w{i}" for i in range(200))
    result = ChatAnswer(answer=long_answer, source_ids=["c1"],
                        answered=True, response_type="grounded")
    out = answer_clinic_question(
        question="q",
        retrieval_fn=lambda **kwargs: [chunk("c1")],
        answer_chain=FakeAnswerChain(result=result),
    )
    assert len(out.message.split()) == 120


def test_rag_failures_map_to_unavailable() -> None:
    def failing_retrieval(**kwargs):
        raise RuntimeError("weaviate down")
    with pytest.raises(RagUnavailableError):
        answer_clinic_question(question="q", retrieval_fn=failing_retrieval,
                               answer_chain=FakeAnswerChain(
                                   result=ChatAnswer(answer="x", source_ids=[],
                                                     answered=True, response_type="grounded")))
    with pytest.raises(LLMCallFailedError):
        answer_clinic_question(
            question="q", retrieval_fn=lambda **kwargs: [chunk("c1")],
            answer_chain=FakeAnswerChain(error=LLMCallFailedError("bad")))
