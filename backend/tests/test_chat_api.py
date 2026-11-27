from datetime import datetime

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.agent import STEP_LIMIT_MESSAGE
from app.clock import FixedClock, get_clock
from app.db import get_db
from app.llm import EMERGENCY_MESSAGE, RedFlagResult
from app.loader import load_data_pack
from app.main import app
from app.rag import CHAT_SAFETY_FAILURE_MESSAGE, ChatAnswer
from app.routers.appointments import get_red_flag_checker
from app.routers.chat import get_model_factory


class ScriptedModel:
    def __init__(self, script):
        self.script = list(script)

    def __call__(self, tools):
        return self

    def invoke(self, messages, config=None):
        if not self.script:
            return AIMessage(content="done")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def build_client(db, red_checker=None, model_script=None):
    from pathlib import Path

    load_data_pack(db, Path(__file__).resolve().parents[2] / "Project_Resources" / "data-pack-Iteration_01")

    def override_db():
        yield db

    checker = red_checker or (lambda _t: RedFlagResult(red_flag=False, category="none", why="t"))
    script = list(model_script or [AIMessage(content="Hello from agent")])
    factory = ScriptedModel(script)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_clock] = lambda: FixedClock(datetime(2026, 11, 2, 10, 0))
    app.dependency_overrides[get_red_flag_checker] = lambda: checker
    app.dependency_overrides[get_model_factory] = lambda: factory
    return TestClient(app)


def teardown():
    app.dependency_overrides.clear()


def login(client: TestClient, role="patient"):
    if role == "patient":
        resp = client.post("/auth/patient", json={"mobile": "9000000001", "name": "Asha Verma"})
    elif role == "staff":
        resp = client.post("/auth/staff", json={"name": "Front Desk"})
    else:
        resp = client.post("/auth/doctor", json={"doctor_id": "D1"})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def test_patient_chat_answer_and_modes(db) -> None:
    client = build_client(db, model_script=[AIMessage(content="Clinic is open 9-6.")])
    try:
        token = login(client, "patient")
        headers = {"Authorization": f"Bearer {token}"}
        # Message mode.
        resp = client.post("/chat", json={"thread_id": "t1", "message": "When open?"}, headers=headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == "Clinic is open 9-6."
        # Invalid modes.
        assert client.post("/chat", json={"thread_id": "t1", "message": "hi", "confirm": True}, headers=headers).status_code == 400
        assert client.post("/chat", json={"thread_id": "t1"}, headers=headers).status_code in (400, 422)
        assert client.post("/chat", json={"thread_id": "t1", "confirm": True}, headers=headers).status_code == 409
        assert client.post("/chat", json={"thread_id": "", "message": "hi"}, headers=headers).status_code in (400, 422)
    finally:
        teardown()


def test_roles_and_spoofed_identity_refused(db) -> None:
    client = build_client(db)
    try:
        for role in ("staff", "doctor"):
            token = login(client, role)
            resp = client.post("/chat", json={"thread_id": "t1", "message": "hi"}, headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code == 403, (role, resp.text)
        resp = client.post("/chat", json={"thread_id": "t1", "message": "hi"})
        assert resp.status_code == 401
    finally:
        teardown()


def test_emergency_and_safety_failures(db) -> None:
    def red_checker(_t):
        return RedFlagResult(red_flag=True, category="curtain_or_shadow", why="curtain")

    client = build_client(db, red_checker=red_checker)
    try:
        token = login(client, "patient")
        resp = client.post("/chat", json={"thread_id": "t1", "message": "curtain over eye"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["kind"] == "emergency"
        assert resp.json()["message"] == EMERGENCY_MESSAGE
        assert resp.json()["sources"] == []
    finally:
        teardown()

    def fail_checker(_t):
        from app.llm import LLMCallFailedError

        raise LLMCallFailedError("down")

    client = build_client(db, red_checker=fail_checker)
    try:
        token = login(client, "patient")
        resp = client.post("/chat", json={"thread_id": "t1", "message": "hi"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 503, resp.text
        assert resp.json()["detail"] == CHAT_SAFETY_FAILURE_MESSAGE
    finally:
        teardown()


def test_step_limit_returns_fixed_sentence(db) -> None:
    def boom(messages, config=None):
        raise RuntimeError("down")

    class BoomFactory:
        def __call__(self, tools):
            class M:
                def invoke(self, messages, config=None):
                    raise RuntimeError("down")
            return M()

    from app.routers.chat import get_model_factory as _gmf

    # Build with boom factory directly.
    from pathlib import Path

    load_data_pack(db, Path(__file__).resolve().parents[2] / "Project_Resources" / "data-pack-Iteration_01")

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_clock] = lambda: FixedClock(datetime(2026, 11, 2, 10, 0))
    app.dependency_overrides[get_red_flag_checker] = lambda: (lambda _t: RedFlagResult(red_flag=False, category="none", why="t"))
    app.dependency_overrides[_gmf] = lambda: BoomFactory()
    client = TestClient(app)
    try:
        token = login(client, "patient")
        resp = client.post("/chat", json={"thread_id": "t1", "message": "hi"}, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["message"] == STEP_LIMIT_MESSAGE
    finally:
        teardown()
