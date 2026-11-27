from fastapi.testclient import TestClient

from tests.test_auth_api import auth_header, login


def _book(client: TestClient, token: str, payload: dict) -> str:
    resp = client.post("/appointments", json=payload, headers=auth_header(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["id"]


def test_reschedule_and_approval_flow(client: TestClient) -> None:
    priya = login(client, "patient", mobile="9000000005", name="Priya Menon")
    lakshmi = login(client, "patient", mobile="9000000003", name="Lakshmi Nair")
    suresh = login(client, "patient", mobile="9000000006", name="Suresh Patil")
    staff = login(client, "staff")

    early_id = _book(
        client,
        priya,
        {
            "doctor_id": "D2",
            "speciality": "Glaucoma",
            "visit_type": "new",
            "date": "2026-11-04",
            "start_time": "10:00:00",
            "reason": "Routine eye test and new glasses",
        },
    )
    late_id = _book(
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

    # Immediate reschedule (early appointment -> Friday).
    resp = client.post(
        f"/appointments/{early_id}/reschedule",
        json={"doctor_id": "D2", "date": "2026-11-06", "start_time": "10:00:00"},
        headers=auth_header(priya),
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "booked"

    # Late reschedule queues to_staff.
    late = client.post(
        f"/appointments/{late_id}/reschedule",
        json={"doctor_id": "D3", "date": "2026-11-04", "start_time": "10:00:00"},
        headers=auth_header(lakshmi),
    )
    assert late.status_code == 202, late.text
    body = late.json()
    assert body["result"] == "to_staff"
    request_id = body["approval_request"]["id"]

    # Cross-patient non-disclosure.
    other = client.post(
        f"/appointments/{late_id}/reschedule",
        json={"doctor_id": "D3", "date": "2026-11-04", "start_time": "10:00:00"},
        headers=auth_header(suresh),
    )
    assert other.status_code == 409
    assert other.json()["reason_code"] == "NOT_YOUR_APPOINTMENT"

    # Staff-only queue.
    forbidden = client.get("/staff/approvals", headers=auth_header(lakshmi))
    assert forbidden.status_code == 403
    queued = client.get("/staff/approvals", headers=auth_header(staff))
    assert queued.status_code == 200
    assert any(r["id"] == request_id for r in queued.json())

    approved = client.post(f"/staff/approvals/{request_id}/approve", headers=auth_header(staff))
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    again = client.post(f"/staff/approvals/{request_id}/approve", headers=auth_header(staff))
    assert again.status_code == 409

    mine = client.get("/appointments", headers=auth_header(lakshmi))
    assert mine.status_code == 200
    assert any(
        a["id"] == late_id and a.get("approval_status") == "approved" for a in mine.json()
    )


def test_reject_and_invalid_target(client: TestClient) -> None:
    priya = login(client, "patient", mobile="9000000005", name="Priya Menon")
    lakshmi = login(client, "patient", mobile="9000000003", name="Lakshmi Nair")
    staff = login(client, "staff")

    early_id = _book(
        client,
        priya,
        {
            "doctor_id": "D2",
            "speciality": "Glaucoma",
            "visit_type": "new",
            "date": "2026-11-04",
            "start_time": "10:00:00",
            "reason": "Routine eye test and new glasses",
        },
    )
    # Invalid reschedule target (Thursday OFF) is refused, not queued.
    bad = client.post(
        f"/appointments/{early_id}/reschedule",
        json={"doctor_id": "D2", "date": "2026-11-05", "start_time": "10:00:00"},
        headers=auth_header(priya),
    )
    assert bad.status_code == 409
    assert bad.json()["reason_code"] == "DOCTOR_OFF"

    late_id = _book(
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
    queued = client.post(f"/appointments/{late_id}/cancel", headers=auth_header(lakshmi))
    assert queued.status_code == 202
    request_id = queued.json()["approval_request"]["id"]
    rejected = client.post(f"/staff/approvals/{request_id}/reject", headers=auth_header(staff))
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
