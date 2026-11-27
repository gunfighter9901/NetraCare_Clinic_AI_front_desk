import pytest
from langchain_core.runnables import RunnableLambda

from app import llm
from app.llm import LLMCallFailedError, LLMUnavailableError, RedFlagResult, red_flag_parser, red_flag_prompt


def _fake_model(output: str):
    return RunnableLambda(lambda _: output)


def test_prompt_covers_all_five_categories() -> None:
    text = red_flag_prompt.format(reason="test", format_instructions="").lower()
    for category in [
        "sudden_vision_loss",
        "curtain_or_shadow",
        "floaters_or_flashes",
        "chemical_or_injury",
        "severe_pain_headache_haloes",
    ]:
        assert category in text
    assert "no sudden loss" in text
    assert "gradual" in text or "slowly" in text
    assert "unsure" in text or "when unsure" in text


def test_parser_round_trips_structured_output() -> None:
    red = red_flag_parser.invoke(
        '{"red_flag": true, "category": "curtain_or_shadow", "why": "curtain over vision"}'
    )
    assert isinstance(red, RedFlagResult)
    assert red.red_flag is True
    assert red.category == "curtain_or_shadow"
    non_red = red_flag_parser.invoke('{"red_flag": false, "category": "none", "why": "routine check"}')
    assert non_red.red_flag is False
    assert non_red.category == "none"
    with pytest.raises(Exception):
        red_flag_parser.invoke("not structured at all")


def test_check_red_flags_empty_reason_fails_closed() -> None:
    with pytest.raises(LLMCallFailedError):
        llm.check_red_flags("   ")


def test_check_red_flags_missing_key_raises_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(llm, "_require_api_key", lambda: (_ for _ in ()).throw(LLMUnavailableError("no key")))
    # _make_model will raise unavailable before building chain
    with pytest.raises(LLMUnavailableError):
        llm.check_red_flags("Routine eye test")


def test_check_red_flags_classifies_and_normalizes_category(monkeypatch) -> None:
    monkeypatch.setattr(
        llm, "_make_model", lambda temperature=0: _fake_model('{"red_flag": true, "category": "sudden_vision_loss", "why": "sudden loss"}')
    )
    result = llm.check_red_flags("I suddenly can't see from my left eye")
    assert result.red_flag is True
    assert result.category == "sudden_vision_loss"

    monkeypatch.setattr(
        llm, "_make_model", lambda temperature=0: _fake_model('{"red_flag": false, "category": "sudden_vision_loss", "why": "routine"}')
    )
    result = llm.check_red_flags("Routine eye test and new glasses")
    assert result.red_flag is False
    assert result.category == "none"


def test_check_red_flags_negated_and_gradual_not_flagged(monkeypatch) -> None:
    monkeypatch.setattr(
        llm, "_make_model", lambda temperature=0: _fake_model('{"red_flag": false, "category": "none", "why": "negated"}')
    )
    assert llm.check_red_flags("No sudden loss of vision but I want a check-up").red_flag is False
    assert llm.check_red_flags("Gradual loss of vision over two years").red_flag is False


def test_check_red_flags_unparsable_fails_closed(monkeypatch) -> None:
    monkeypatch.setattr(llm, "_make_model", lambda temperature=0: _fake_model("gibberish"))
    with pytest.raises(LLMCallFailedError):
        llm.check_red_flags("Seeing flashes")
