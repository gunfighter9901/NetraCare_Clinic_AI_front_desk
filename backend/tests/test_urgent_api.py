from fastapi.testclient import TestClient

from app.llm import RedFlagResult
from app.main import app
from app.routers.appointments import get_red_flag_checker
from tests.test_auth_api import auth_header, login


def use_checker(fake):
    app.dependency_overrides[get_red_flag_checker] = lambda: fake


def clear_checker():
    app.dependency_overrides.pop(get_red_flag_checker, None)


def non_urgent(_text: str) -> RedFlagResult:
    return RedFlagResult(red_flag=False, category="none", why="routine")


def red(_text: str) -> RedFlagResult:
    return RedFlagResult(red_flag=True, category="sudden_vision_loss", why="sudden")


def test_staff_urgent_visibility_and_acknowledgement(client: TestClient) -> None:
    staff = login(client, "staff")
    use_checker(red)
    try:
        booking = client.post(
            "/appointments",
            json={
                "doctor_id": "D1", "speciality": "Cataract", "visit_type": "new",
                "date": "2026-12-01", "start_time": "09:00:00",
                "reason": "I suddenly can't see from my left eye",
            },
            headers=auth_header(login(client)),
        )
        assert booking.status_code == 200, booking.text
        assert "emergency" in booking.json()
        assert booking.json()["is_urgent"] is True
        assert booking.json()["urgent_case_id"]
        urgents = client.get("/urgent-cases", headers=auth_header(staff))
        assert urgents.status_code == 200
        assert len(urgents.json()) == 1
        urgent_id = urgents.json()[0]["id"]
        seen = client.post(f"/urgent-cases/{urgent_id}/seen", headers=auth_header(staff))
        assert seen.status_code == 200
        assert client.get("/urgent-cases", headers=auth_header(staff)).json() == []
    finally:
        clear_checker()


def test_red_flag_with_rule_refusal_returns_emergency_and_urgent(client: TestClient) -> None:
    staff = login(client, "staff")
    patient = login(client)
    use_checker(red)
    try:
        booking = client.post(
            "/appointments",
            json={
                "doctor_id": "D1", "speciality": "Cataract", "visit_type": "new",
                "date": "2026-11-05", "start_time": "10:00:00",
                "reason": "I suddenly can't see",
            },
            headers=auth_header(patient),
        )
        assert booking.status_code == 409, booking.text
        body = booking.json()
        assert "emergency" in body and "urgent attention" in body["emergency"]
        assert body["reason_code"] == "SURGERY_SESSION"
        urgents = client.get("/urgent-cases", headers=auth_header(staff))
        assert len(urgents.json()) == 1
    finally:
        clear_checker()


def test_urgent_endpoints_require_staff(client: TestClient) -> None:
    patient = login(client)
    assert client.get("/urgent-cases", headers=auth_header(patient)).status_code == 403
    use_checker(non_urgent)
    try:
        booking = client.post(
            "/appointments",
            json={
                "doctor_id": "D1", "speciality": "General", "visit_type": "new",
                "date": "2026-12-01", "start_time": "09:00:00",
                "reason": "Routine eye test",
            },
            headers=auth_header(patient),
        )
        assert booking.status_code == 200, booking.text
        assert "emergency" not in booking.json()
    finally:
        clear_checker()


def test_check_failure_returns_503_without_appointment(client: TestClient) -> None:
    from app.llm import LLMCallFailedError

    def failing(_text: str):
        raise LLMCallFailedError("timeout")

    patient = login(client)
    use_checker(failing)
    try:
        booking = client.post(
            "/appointments",
            json={
                "doctor_id": "D1", "speciality": "General", "visit_type": "new",
                "date": "2026-12-01", "start_time": "09:00:00",
                "reason": "Routine eye test",
            },
            headers=auth_header(patient),
        )
        assert booking.status_code == 503
        assert "couldn't check" in booking.json()["message"]
        assert client.get("/appointments", headers=auth_header(patient)).json() == []
    finally:
        clear_checker()
