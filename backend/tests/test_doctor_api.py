from fastapi.testclient import TestClient

from tests.test_auth_api import auth_header, login


def patient_books_cataract(client: TestClient, token: str, start: str = "09:00:00") -> str:
    response = client.post(
        "/appointments",
        json={
            "doctor_id": "D1",
            "speciality": "Cataract",
            "visit_type": "new",
            "date": "2026-12-01",
            "start_time": start,
            "reason": "Routine eye test and new glasses",
        },
        headers=auth_header(token),
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_doctor_schedule_completion_and_same_doctor_follow_up(client: TestClient) -> None:
    patient = login(client)
    appointment_id = patient_books_cataract(client, patient)
    other_doctor = login(client, "doctor", doctor_id="D2")
    doctor = login(client, "doctor", doctor_id="D1")

    schedule = client.get(
        "/doctor/appointments",
        params={"appointment_date": "2026-12-01"},
        headers=auth_header(doctor),
    )
    assert schedule.status_code == 200
    assert [item["id"] for item in schedule.json()] == [appointment_id]
    assert schedule.json()[0]["patient_name"] == "Asha Verma"

    forbidden = client.post(
        f"/appointments/{appointment_id}/complete",
        json={"doctor_note": "Cataract review, listed for surgery."},
        headers=auth_header(other_doctor),
    )
    assert forbidden.status_code == 403
    assert "own appointments" in forbidden.json()["detail"]

    completed = client.post(
        f"/appointments/{appointment_id}/complete",
        json={"doctor_note": "Nuclear sclerosis grade 2 OS. Discussed surgery."},
        headers=auth_header(doctor),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["completed_at"] is not None

    follow_up = client.post(
        "/appointments",
        json={
            "doctor_id": "D1",
            "speciality": "Cataract",
            "visit_type": "follow_up",
            "date": "2026-12-01",
            "start_time": "09:20:00",
            "reason": "Routine eye test and new glasses",
        },
        headers=auth_header(patient),
    )
    assert follow_up.status_code == 200, follow_up.text
    assert follow_up.json()["end_time"] == "09:30:00"

    inactive = client.post(
        f"/appointments/{appointment_id}/complete",
        json={"doctor_note": "Another note."},
        headers=auth_header(doctor),
    )
    assert inactive.status_code == 409
    assert "Only a booked appointment" in inactive.json()["detail"]


def test_follow_up_with_different_doctor_is_refused(client: TestClient) -> None:
    patient = login(client)
    appointment_id = patient_books_cataract(client, patient)
    doctor = login(client, "doctor", doctor_id="D1")
    completed = client.post(
        f"/appointments/{appointment_id}/complete",
        json={"doctor_note": "Cataract review completed."},
        headers=auth_header(doctor),
    )
    assert completed.status_code == 200

    response = client.post(
        "/appointments",
        json={
            "doctor_id": "D2",
            "speciality": "Cataract",
            "visit_type": "follow_up",
            "date": "2026-12-02",
            "start_time": "09:00:00",
            "reason": "Routine eye test and new glasses",
        },
        headers=auth_header(patient),
    )
    assert response.status_code == 409
    assert response.json()["reason_code"] == "FOLLOW_UP_DIFFERENT_DOCTOR"
    assert "Dr. Anand Rao" in response.json()["message"]
