from fastapi.testclient import TestClient

from tests.test_auth_api import auth_header, login
from tests.test_doctor_api import patient_books_cataract


def test_completion_requires_non_empty_note(client: TestClient) -> None:
    patient = login(client)
    appointment_id = patient_books_cataract(client, patient)
    doctor = login(client, "doctor", doctor_id="D1")
    for bad in ["", "   "]:
        response = client.post(
            f"/appointments/{appointment_id}/complete",
            json={"doctor_note": bad},
            headers=auth_header(doctor),
        )
        assert response.status_code in (400, 422), response.text
    # Still booked
    schedule = client.get(
        "/doctor/appointments",
        params={"appointment_date": "2026-12-01"},
        headers=auth_header(doctor),
    )
    assert schedule.json()[0]["status"] == "booked"


def test_saved_note_appears_in_history(client: TestClient) -> None:
    patient = login(client)
    appointment_id = patient_books_cataract(client, patient)
    doctor = login(client, "doctor", doctor_id="D1")
    note = "Early cortical cataract, review 1 year."
    completed = client.post(
        f"/appointments/{appointment_id}/complete",
        json={"doctor_note": note},
        headers=auth_header(doctor),
    )
    assert completed.status_code == 200
    history = client.get("/doctor/patients/P01/history", headers=auth_header(doctor))
    assert history.status_code == 200
    assert any(item["id"] == appointment_id and item["doctor_note"] == note for item in history.json())


def test_patient_cannot_access_history(client: TestClient) -> None:
    token = login(client)
    assert client.get("/doctor/patients/P01/history", headers=auth_header(token)).status_code == 403
