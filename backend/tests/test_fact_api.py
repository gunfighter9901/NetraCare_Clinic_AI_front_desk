from fastapi.testclient import TestClient

from app.llm import FACT_CAVET, FACT_FALLBACK
from app.main import app
from app.routers.fact import get_fact_fn
from tests.test_auth_api import auth_header, login


def test_fact_requires_patient_role(client: TestClient) -> None:
    assert client.get("/fact-of-the-day").status_code == 401
    staff = login(client, "staff")
    assert client.get("/fact-of-the-day", headers=auth_header(staff)).status_code == 403


def test_fact_returns_caveat_and_fallback_without_key(client: TestClient, monkeypatch) -> None:
    import app.llm as llm_module
    from app.llm import LLMUnavailableError

    monkeypatch.setattr(
        llm_module, "_require_api_key", lambda: (_ for _ in ()).throw(LLMUnavailableError("no key"))
    )
    token = login(client)
    response = client.get("/fact-of-the-day", headers=auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["caveat"] == FACT_CAVET
    assert body["fact"] == FACT_FALLBACK


def test_fact_refresh_and_fallback_with_fake(client: TestClient) -> None:
    token = login(client)

    def fake_fact(previous: str | None = None) -> str:
        if previous:
            return "A different general eye-health fact."
        return "A general eye-health fact."

    def failing(_previous: str | None = None) -> str:
        raise RuntimeError("boom")

    app.dependency_overrides[get_fact_fn] = lambda: fake_fact
    try:
        first = client.get("/fact-of-the-day", headers=auth_header(token)).json()
        second = client.get(
            "/fact-of-the-day", params={"previous": first["fact"]}, headers=auth_header(token)
        ).json()
        assert first["fact"] != second["fact"]
        assert second["caveat"] == FACT_CAVET
    finally:
        app.dependency_overrides.pop(get_fact_fn, None)

    app.dependency_overrides[get_fact_fn] = lambda: failing
    try:
        body = client.get("/fact-of-the-day", headers=auth_header(token)).json()
        assert body["fact"] == FACT_FALLBACK
        assert body["caveat"] == FACT_CAVET
    finally:
        app.dependency_overrides.pop(get_fact_fn, None)
