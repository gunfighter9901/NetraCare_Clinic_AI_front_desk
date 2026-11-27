from datetime import datetime

from fastapi.testclient import TestClient

from app.clock import FixedClock, get_clock
from app.db import get_db
from app.loader import load_data_pack
from app.main import app
from app.rag import RetrievedChunk
from app.routers.appointments import get_red_flag_checker
from app.routers.staff import get_rag_collection


def make_chunk(chunk_id, source, section, score, kind):
    return RetrievedChunk(
        chunk_id=chunk_id, source=source, section=section,
        text=f"{section} text", score=score, score_kind=kind,
    )


class FakeQuery:
    def __init__(self, chunks):
        self.chunks = chunks

    def _resp(self, kind):
        from types import SimpleNamespace

        objs = []
        for c in self.chunks[kind]:
            objs.append(SimpleNamespace(
                properties={"chunk_id": c.chunk_id, "source": c.source,
                            "section": c.section, "text": c.text},
                metadata=SimpleNamespace(score=c.score),
            ))
        return SimpleNamespace(objects=objs)

    def hybrid(self, query, alpha=0.5, limit=4, return_metadata=None):
        assert alpha == 0.5
        return self._resp("hybrid")

    def bm25(self, query, limit=4, return_metadata=None):
        return self._resp("keyword")

    def near_text(self, query, limit=4, return_metadata=None):
        return self._resp("vector")


class FakeHandle:
    def __init__(self, chunks):
        self.query = FakeQuery(chunks)


def build_client(db, chunks=None, rag_error=None):
    from app.llm import RedFlagResult

    load_data_pack(db, __import__("pathlib").Path(__file__).resolve().parents[2]
                   / "Project_Resources" / "data-pack-Iteration_01")

    def override_db():
        yield db

    def stub_checker(_text):
        return RedFlagResult(red_flag=False, category="none", why="test")

    async def noop():
        return None

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_clock] = lambda: FixedClock(datetime(2026, 11, 2, 10, 0))
    app.dependency_overrides[get_red_flag_checker] = lambda: stub_checker
    if rag_error is not None:
        def fail_collection():
            raise rag_error
        app.dependency_overrides[get_rag_collection] = fail_collection
    elif chunks is not None:
        app.dependency_overrides[get_rag_collection] = lambda: FakeHandle(chunks)
    return TestClient(app)


def teardown():
    app.dependency_overrides.clear()


def login(client: TestClient, role: str, identifier: str = "") -> str:
    if role == "staff":
        resp = client.post("/auth/staff", json={"name": "Front Desk"})
    elif role == "patient":
        resp = client.post("/auth/patient", json={"mobile": "9000000001", "name": "Asha Verma"})
    else:
        resp = client.post("/auth/doctor", json={"doctor_id": "D1"})
    assert resp.status_code == 200, resp.text
    return resp.json()["token"]


def test_staff_debug_returns_labeled_scores(db) -> None:
    from app.rag import hybrid_search

    chunks = {
        "keyword": [make_chunk("procedures-diabetic-eye-check-0", "procedures.md",
                               "Diabetic eye check", 3.2, "bm25")],
        "vector": [make_chunk("procedures-squint-surgery-0", "procedures.md",
                              "Squint surgery", 0.12, "vector_similarity")],
        "hybrid": [make_chunk("procedures-diabetic-eye-check-0", "procedures.md",
                              "Diabetic eye check", 0.98, "hybrid_fused")],
    }
    client = build_client(db, chunks=chunks)
    try:
        token = login(client, "staff")
        resp = client.get("/staff/search-debug", params={"q": "HbA1c"},
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["query"] == "HbA1c"
        assert body["keyword"][0]["score_kind"] == "bm25"
        assert body["vector"][0]["score_kind"] == "vector_similarity"
        assert body["hybrid"][0]["score_kind"] == "hybrid_fused"
        for group in ("keyword", "vector", "hybrid"):
            assert len(body[group]) <= 4
            for item in body[group]:
                assert item["chunk_id"] and item["source"] and item["section"]
        # Debug hybrid ranking agrees with the chat retrieval path.
        debug_ids = [c["chunk_id"] for c in body["hybrid"]]
        direct = hybrid_search(collection_handle=FakeHandle(chunks), query="HbA1c")
        assert debug_ids == [c.chunk_id for c in direct]
    finally:
        teardown()


def test_non_staff_refused(db) -> None:
    chunks = {"keyword": [], "vector": [], "hybrid": []}
    for role in ("patient", "doctor"):
        client = build_client(db, chunks=chunks)
        try:
            token = login(client, role)
            resp = client.get("/staff/search-debug", params={"q": "HbA1c"},
                              headers={"Authorization": f"Bearer {token}"})
            assert resp.status_code in (401, 403), (role, resp.text)
        finally:
            teardown()
    client = build_client(db, chunks=chunks)
    try:
        resp = client.get("/staff/search-debug", params={"q": "HbA1c"})
        assert resp.status_code == 401, resp.text
    finally:
        teardown()


def test_retrieval_failure_is_503_without_partial_results(db) -> None:
    from fastapi import HTTPException

    client = build_client(db, rag_error=HTTPException(status_code=503, detail="missing collection"))
    try:
        token = login(client, "staff")
        resp = client.get("/staff/search-debug", params={"q": "HbA1c"},
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 503, resp.text
    finally:
        teardown()
