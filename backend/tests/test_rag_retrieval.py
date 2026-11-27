from types import SimpleNamespace

from app.rag import bm25_search, hybrid_search, vector_search


def make_obj(chunk_id, source, section, text, score):
    return SimpleNamespace(
        properties={"chunk_id": chunk_id, "source": source, "section": section, "text": text},
        metadata=SimpleNamespace(score=score),
    )


class FakeQuery:
    def __init__(self, mapping):
        self.mapping = mapping
        self.calls: list[tuple[str, dict]] = []

    def _lookup(self, kind, query):
        self.calls.append((kind, dict(query=query)))
        return SimpleNamespace(objects=list(self.mapping.get((kind, query), [])))

    def hybrid(self, query, alpha=0.5, limit=4, return_metadata=None):
        assert alpha == 0.5
        assert limit == 4
        return self._lookup("hybrid", query)

    def bm25(self, query, limit=4, return_metadata=None):
        assert limit == 4
        return self._lookup("bm25", query)

    def near_text(self, query, limit=4, return_metadata=None):
        assert limit == 4
        return self._lookup("vector", query)


class FakeHandle:
    def __init__(self, mapping):
        self.query = FakeQuery(mapping)


def mapping_fixture():
    hb = make_obj("procedures-diabetic-eye-check-0", "procedures.md",
                  "Diabetic eye check", "HbA1c text", 1.0)
    menon = make_obj("doctors-dr-vikram-menon-0", "doctors.md",
                     "Dr. Vikram Menon", "Menon text", 1.0)
    squint = make_obj("procedures-squint-surgery-0", "procedures.md",
                      "Squint surgery", "Squint text", 0.9)
    return {
        ("bm25", "Menon?"): [menon],
        ("bm25", "Should I bring my HbA1c report?"): [hb],
        ("hybrid", "Should I bring my HbA1c report?"): [hb, menon],
        ("hybrid", "operation to straighten his eye"): [squint],
        ("vector", "operation to straighten his eye"): [squint],
        ("vector", "Menon?"): [menon],
    }


def test_bm25_matches_exact_terms_despite_punctuation() -> None:
    handle = FakeHandle(mapping_fixture())
    menon = bm25_search(collection_handle=handle, query="Menon?")
    assert menon and menon[0].section == "Dr. Vikram Menon"
    assert menon[0].score_kind == "bm25"
    hba1c = bm25_search(
        collection_handle=handle, query="Should I bring my HbA1c report?"
    )
    assert hba1c[0].section == "Diabetic eye check"


def test_hybrid_equal_weight_dedupes_to_four() -> None:
    dup = make_obj("procedures-diabetic-eye-check-0", "procedures.md",
                   "Diabetic eye check", "dup", 0.8)
    other = make_obj("doctors-dr-vikram-menon-0", "doctors.md",
                     "Dr. Vikram Menon", "other", 0.5)
    handle = FakeHandle({("hybrid", "q"): [dup, dup, other]})
    results = hybrid_search(collection_handle=handle, query="q")
    assert [r.chunk_id for r in results] == [
        "procedures-diabetic-eye-check-0", "doctors-dr-vikram-menon-0"
    ]
    assert all(r.score_kind == "hybrid_fused" for r in results)
    assert len(results) <= 4


def test_semantic_paraphrase_reaches_squint() -> None:
    handle = FakeHandle(mapping_fixture())
    vector = vector_search(
        collection_handle=handle, query="operation to straighten his eye"
    )
    hybrid = hybrid_search(
        collection_handle=handle, query="operation to straighten his eye"
    )
    assert vector[0].section == "Squint surgery"
    assert hybrid[0].section == "Squint surgery"
