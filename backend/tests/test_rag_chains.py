import pytest

from app.llm import LLMCallFailedError, LLMUnavailableError
from app.rag import (
    RetrievedChunk,
    answer_with_chunks,
    chat_answer_parser,
    rewrite_question,
)


def chunk(chunk_id="procedures-cataract-surgery-0"):
    return RetrievedChunk(
        chunk_id=chunk_id, source="procedures.md", section="Cataract surgery",
        text="Cataract surgery text", score=0.9, score_kind="hybrid_fused",
    )


class FakeRewriteChain:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.seen = None

    def invoke(self, payload, config=None):
        self.seen = payload
        if self.error:
            raise self.error
        return self.result


class FakeAnswerChain:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.seen = None

    def invoke(self, payload, config=None):
        self.seen = payload
        if self.error:
            raise self.error
        return self.result


def test_rewrite_uses_history_and_preserves_complete_questions() -> None:
    chain = FakeRewriteChain(result="What should I avoid after cataract surgery?")
    out = rewrite_question(
        history=[{"role": "user", "content": "Tell me about cataract surgery"}],
        message="What should I avoid after it?",
        chain=chain,
    )
    assert out == "What should I avoid after cataract surgery?"
    assert "cataract" in chain.seen["history"].lower()
    assert "avoid" in chain.seen["message"].lower()

    complete = FakeRewriteChain(result="What time does the clinic open on Saturday?")
    out = rewrite_question(
        history=[], message="What time does the clinic open on Saturday?", chain=complete
    )
    assert out == "What time does the clinic open on Saturday?"


def test_rewrite_failure_raises() -> None:
    with pytest.raises(LLMCallFailedError):
        rewrite_question(history=[], message="hi",
                         chain=FakeRewriteChain(error=ValueError("bad")))
    with pytest.raises(LLMUnavailableError):
        rewrite_question(history=[], message="hi",
                         chain=FakeRewriteChain(error=LLMUnavailableError("no key")))


def test_answer_chain_validates_response_types_and_structure() -> None:
    from app.rag import ChatAnswer

    for response_type in ("grounded", "booking", "non_eye", "out_of_scope"):
        result = ChatAnswer(answer="ok", source_ids=[], answered=True,
                            response_type=response_type)
        chain = FakeAnswerChain(result=result)
        out = answer_with_chunks(question="q", chunks=[chunk()], chain=chain)
        assert out.response_type == response_type
    with pytest.raises(Exception):
        ChatAnswer(answer="ok", source_ids=[], answered=True,
                   response_type="invalid-type")
    with pytest.raises(Exception):
        chat_answer_parser.parse("just free text without structure")


def test_answer_malformed_fails_closed() -> None:
    with pytest.raises(LLMCallFailedError):
        answer_with_chunks(question="q", chunks=[chunk()],
                           chain=FakeAnswerChain(error=ValueError("bad parse")))
