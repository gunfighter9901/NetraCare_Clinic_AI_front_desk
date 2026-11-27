from fastapi.testclient import TestClient


def login(client: TestClient, role: str = "patient", **payload) -> str:
    if role == "patient":
        payload = {"mobile": "9000000001", "name": "Asha Verma", **payload}
    elif role == "doctor":
        payload = {"doctor_id": "D1", **payload}
    else:
        payload = {"name": "Front Desk", **payload}
    response = client.post(f"/auth/{role}", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_public_doctor_options_and_patient_identity_cannot_be_spoofed(client: TestClient) -> None:
    options = client.get("/auth/doctor-options")
    assert options.status_code == 200
    assert len(options.json()) == 5
    token = login(client)
    me = client.get("/auth/me?patient_id=P02&role=staff", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["role"] == "patient"
    assert me.json()["patient_id"] == "P01"
    assert me.json()["display_name"] == "Asha Verma"


def test_missing_and_invalid_sessions_are_refused(client: TestClient) -> None:
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers=auth_header("invalid")).status_code == 401


def test_wrong_role_cannot_access_staff_patients(client: TestClient) -> None:
    patient_token = login(client)
    assert client.get("/staff/patients", headers=auth_header(patient_token)).status_code == 403
    staff_token = login(client, "staff")
    response = client.get("/staff/patients", headers=auth_header(staff_token))
    assert response.status_code == 200
    assert len(response.json()) == 25


def test_all_logins_and_logout(client: TestClient) -> None:
    doctor = client.post("/auth/doctor", json={"doctor_id": "D1"})
    assert doctor.status_code == 200
    assert doctor.json()["display_name"] == "Dr. Anand Rao"
    mismatch = client.post("/auth/patient", json={"mobile": "9000000001", "name": "Wrong"})
    assert mismatch.status_code == 401
    token = login(client)
    assert client.post("/auth/logout", headers=auth_header(token)).status_code == 204
    assert client.get("/auth/me", headers=auth_header(token)).status_code == 401
