from pathlib import Path

from fastapi.testclient import TestClient

from app.llm import SUMMARY_FALLBACK, SUMMARY_LABEL
from app.main import app
from app.routers.summary import get_summary_fn
from tests.test_auth_api import auth_header, login

DATA_PACK_2 = Path(__file__).resolve().parents[2] / "Project_Resources" / "data-pack-Iteration_02"


def _load_pack2_for_client(db):
    from app.loader import load_data_pack_2
    load_data_pack_2(db, DATA_PACK_2)


def _book(client: TestClient, token: str, payload: dict) -> str:
    response = client.post("/appointments", json=payload, headers=auth_header(token))
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_summary_requires_doctor_and_ownership(client: TestClient, db) -> None:
    _load_pack2_for_client(db)
    patient_token = login(client)
    appointment_id = _book(client, patient_token, {
        "doctor_id": "D2", "speciality": "Glaucoma", "visit_type": "new",
        "date": "2026-12-02", "start_time": "09:00:00",
        "reason": "Pressure check",
    })
    # Patient refused
    assert client.get(f"/doctor/appointments/{appointment_id}/summary",
                      headers=auth_header(patient_token)).status_code == 403
    # Other doctor refused
    other = login(client, "doctor", doctor_id="D1")
    assert client.get(f"/doctor/appointments/{appointment_id}/summary",
                      headers=auth_header(other)).status_code == 403


def test_summary_fallback_without_key_and_label(client: TestClient, db, monkeypatch) -> None:
    import app.llm as llm_module
    from app.llm import LLMUnavailableError

    monkeypatch.setattr(
        llm_module, "_require_api_key", lambda: (_ for _ in ()).throw(LLMUnavailableError("no key"))
    )
    _load_pack2_for_client(db)
    # P20 has no history
    p20 = login(client, "patient", mobile="9000000020", name="Aditya Bose")
    appointment_id = _book(client, p20, {
        "doctor_id": "D1", "speciality": "General", "visit_type": "new",
        "date": "2026-12-01", "start_time": "09:00:00",
        "reason": "Routine eye test",
    })
    doctor = login(client, "doctor", doctor_id="D1")
    body = client.get(f"/doctor/appointments/{appointment_id}/summary",
                      headers=auth_header(doctor)).json()
    assert body["label"] == SUMMARY_LABEL
    assert body["summary"] == SUMMARY_FALLBACK
    assert body["fallback"] is True


def test_summary_uses_fake_and_enforces_120_words(client: TestClient, db) -> None:
    _load_pack2_for_client(db)
    # P03 has 3 visits: glaucoma latanoprost (D2), cataract (D1), sulfa allergy
    p03 = login(client, "patient", mobile="9000000003", name="Lakshmi Nair")
    appointment_id = _book(client, p03, {
        "doctor_id": "D2", "speciality": "Glaucoma", "visit_type": "follow_up",
        "date": "2026-12-02", "start_time": "09:00:00",
        "reason": "Glaucoma follow-up pressure check",
    })

    captured = {}

    def fake_summary(summary_input: str) -> str:
        captured["input"] = summary_input
        return " ".join(["word"] * 200)

    app.dependency_overrides[get_summary_fn] = lambda: fake_summary
    try:
        doctor = login(client, "doctor", doctor_id="D2")
        body = client.get(f"/doctor/appointments/{appointment_id}/summary",
                          headers=auth_header(doctor)).json()
        assert body["fallback"] is False
        assert body["label"] == SUMMARY_LABEL
        assert len(body["summary"].split()) <= 120
        # Prompt input contains expected recorded data
        assert "Glaucoma follow-up pressure check" in captured["input"]
        assert "latanoprost" in captured["input"].lower()
        assert "Sulfa" in captured["input"] or "sulfa" in captured["input"].lower()
    finally:
        app.dependency_overrides.pop(get_summary_fn, None)


def test_summary_input_contains_asthma_context(client: TestClient, db) -> None:
    _load_pack2_for_client(db)
    p15 = login(client, "patient", mobile="9000000015", name="Sunita Rao")
    appointment_id = _book(client, p15, {
        "doctor_id": "D2", "speciality": "Glaucoma", "visit_type": "follow_up",
        "date": "2026-12-02", "start_time": "09:00:00",
        "reason": "Pressure review",
    })

    captured = {}

    def fake_summary(summary_input: str) -> str:
        captured["input"] = summary_input
        return "Latanoprost started, timolol avoided because of asthma. Recorded by Dr. Iyer."

    app.dependency_overrides[get_summary_fn] = lambda: fake_summary
    try:
        doctor = login(client, "doctor", doctor_id="D2")
        body = client.get(f"/doctor/appointments/{appointment_id}/summary",
                          headers=auth_header(doctor)).json()
        assert "asthma" in captured["input"].lower()
        assert "latanoprost" in captured["input"].lower()
        assert "timolol" in captured["input"].lower()
        assert body["fallback"] is False
    finally:
        app.dependency_overrides.pop(get_summary_fn, None)
