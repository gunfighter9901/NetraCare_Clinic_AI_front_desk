from datetime import date

from fastapi.testclient import TestClient

from tests.test_auth_api import auth_header, login


def test_doctors_and_slots_are_protected_and_structured(client: TestClient) -> None:
    assert client.get("/doctors").status_code == 401
    token = login(client)
    doctors = client.get("/doctors", headers=auth_header(token))
    assert doctors.status_code == 200
    assert [doctor["id"] for doctor in doctors.json()] == ["D1", "D2", "D3", "D4", "D5"]
    assert doctors.json()[0]["specialities"] == ["Cataract", "General"]

    slots = client.get(
        "/slots",
        params={"doctor_id": "D1", "appointment_date": "2026-12-01", "visit_type": "new"},
        headers=auth_header(token),
    )
    assert slots.status_code == 200
    assert "09:00:00" in slots.json()["slots"]
    assert slots.json()["message"].startswith("Free slots")


def test_patient_books_and_sees_only_own_appointments(client: TestClient) -> None:
    asha = login(client)
    booking = client.post(
        "/appointments",
        json={
            "doctor_id": "D1",
            "speciality": "General",
            "visit_type": "new",
            "date": "2026-12-01",
            "start_time": "09:00:00",
            "reason": "Routine eye test and new glasses",
        },
        headers=auth_header(asha),
    )
    assert booking.status_code == 200, booking.text
    appointment = booking.json()
    assert appointment["id"] == "A001"
    assert appointment["patient_id"] == "P01"
    assert appointment["doctor_name"] == "Dr. Anand Rao"
    assert appointment["end_time"] == "09:20:00"

    rohan = login(client, "patient", mobile="9000000002", name="Rohan Gupta")
    rohan_appointments = client.get("/appointments", headers=auth_header(rohan))
    assert rohan_appointments.status_code == 200
    assert rohan_appointments.json() == []

    asha_appointments = client.get("/appointments", headers=auth_header(asha))
    assert [item["id"] for item in asha_appointments.json()] == ["A001"]


def test_staff_books_existing_patient_and_walk_in(client: TestClient) -> None:
    asha = login(client)
    patient_booking = client.post(
        "/appointments",
        json={
            "doctor_id": "D1",
            "speciality": "General",
            "visit_type": "new",
            "date": "2026-12-01",
            "start_time": "09:00:00",
            "reason": "Routine eye test and new glasses",
        },
        headers=auth_header(asha),
    )
    assert patient_booking.status_code == 200

    staff = login(client, "staff")
    existing = client.post(
        "/staff/appointments",
        json={
            "patient_id": "P02",
            "doctor_id": "D1",
            "speciality": "General",
            "visit_type": "new",
            "date": "2026-12-01",
            "start_time": "09:20:00",
            "reason": "Routine eye test and new glasses",
        },
        headers=auth_header(staff),
    )
    assert existing.status_code == 200, existing.text
    assert existing.json()["patient_id"] == "P02"

    walk_in = client.post(
        "/staff/appointments",
        json={
            "walk_in_name": "Walk In",
            "walk_in_mobile": "9999999999",
            "doctor_id": "D1",
            "speciality": "General",
            "visit_type": "new",
            "date": "2026-12-01",
            "start_time": "09:40:00",
            "reason": "Routine eye test and new glasses",
        },
        headers=auth_header(staff),
    )
    assert walk_in.status_code == 200, walk_in.text
    assert walk_in.json()["patient_id"] == "P26"
    assert walk_in.json()["patient_name"] == "Walk In"

    daily = client.get(
        "/staff/appointments",
        params={"appointment_date": "2026-12-01"},
        headers=auth_header(staff),
    )
    assert daily.status_code == 200
    assert [item["start_time"] for item in daily.json()] == ["09:00:00", "09:20:00", "09:40:00"]


def test_staff_invalid_booking_returns_structured_refusal(client: TestClient) -> None:
    staff = login(client, "staff")
    response = client.post(
        "/staff/appointments",
        json={
            "patient_id": "P03",
            "doctor_id": "D4",
            "speciality": "Glaucoma",
            "visit_type": "new",
            "date": "2026-12-01",
            "start_time": "10:00:00",
            "reason": "Routine eye test and new glasses",
        },
        headers=auth_header(staff),
    )
    assert response.status_code == 409
    assert response.json() == {
        "result": "refused",
        "reason_code": "SPECIALITY_MISMATCH",
        "message": "Dr. Fatima Khan does not cover Glaucoma",
    }
