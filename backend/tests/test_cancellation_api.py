from fastapi.testclient import TestClient

from tests.test_auth_api import auth_header, login


def patient_books(client: TestClient, token: str, payload: dict) -> str:
    response = client.post("/appointments", json=payload, headers=auth_header(token))
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_cancellation_ownership_late_staff_and_released_capacity(client: TestClient) -> None:
    imran = login(client, "patient", mobile="9000000004", name="Imran Sheikh")
    lakshmi = login(client, "patient", mobile="9000000003", name="Lakshmi Nair")
    priya = login(client, "patient", mobile="9000000005", name="Priya Menon")
    suresh = login(client, "patient", mobile="9000000006", name="Suresh Patil")
    staff = login(client, "staff")

    early_id = patient_books(
        client,
        imran,
        {
            "doctor_id": "D3",
            "speciality": "Retina",
            "visit_type": "new",
            "date": "2026-11-02",
            "start_time": "12:30:00",
            "reason": "Routine eye test and new glasses",
        },
    )
    late_id = patient_books(
        client,
        lakshmi,
        {
            "doctor_id": "D3",
            "speciality": "Retina",
            "visit_type": "new",
            "date": "2026-11-02",
            "start_time": "11:00:00",
            "reason": "Routine eye test and new glasses",
        },
    )
    priya_id = patient_books(
        client,
        priya,
        {
            "doctor_id": "D3",
            "speciality": "General",
            "visit_type": "new",
            "date": "2026-11-02",
            "start_time": "14:00:00",
            "reason": "Routine eye test and new glasses",
        },
    )

    other_patient = client.post(
        f"/appointments/{priya_id}/cancel", headers=auth_header(suresh)
    )
    assert other_patient.status_code == 409
    assert other_patient.json()["reason_code"] == "NOT_YOUR_APPOINTMENT"

    cancelled = client.post(f"/appointments/{early_id}/cancel", headers=auth_header(imran))
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    rebooked = client.post(
        "/appointments",
        json={
            "doctor_id": "D3",
            "speciality": "Retina",
            "visit_type": "new",
            "date": "2026-11-02",
            "start_time": "12:30:00",
            "reason": "Routine eye test and new glasses",
        },
        headers=auth_header(suresh),
    )
    assert rebooked.status_code == 200, rebooked.text
    assert rebooked.json()["patient_id"] == "P06"

    late = client.post(f"/appointments/{late_id}/cancel", headers=auth_header(lakshmi))
    assert late.status_code == 202
    body = late.json()
    assert body["result"] == "to_staff"
    assert body["reason_code"] == "INSIDE_2_HOURS"
    assert body["approval_request"]["status"] == "pending"
    assert body["appointment"]["status"] == "booked"

    staff_cancel = client.post(f"/appointments/{late_id}/cancel", headers=auth_header(staff))
    assert staff_cancel.status_code == 200
    assert staff_cancel.json()["status"] == "cancelled"

    inactive = client.post(f"/appointments/{late_id}/cancel", headers=auth_header(lakshmi))
    assert inactive.status_code == 409
    assert inactive.json()["reason_code"] == "NOT_ACTIVE"


def test_unknown_appointment_returns_404(client: TestClient) -> None:
    token = login(client)
    response = client.post("/appointments/MISSING/cancel", headers=auth_header(token))
    assert response.status_code == 404
