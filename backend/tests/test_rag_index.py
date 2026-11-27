from app.rag import (
    chunk_documents,
    ensure_collection,
    load_document_files,
    rebuild_collection,
)
from app.config import get_settings


class FakeBatch:
    def __init__(self, parent):
        self.parent = parent

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def add_object(self, properties):
        self.parent.inserted.append(properties)


class FakeCollection:
    def __init__(self, parent, name):
        self.parent = parent
        self.name = name
        self.batch = self

    def dynamic(self):
        return FakeBatch(self.parent)


class FakeCollections:
    def __init__(self):
        self.created: list[tuple[str, str]] = []
        self.inserted: list[dict] = []
        self._exists: set[str] = set()

    def exists(self, name: str) -> bool:
        return name in self._exists

    def get(self, name: str):
        return FakeCollection(self, name)

    def create(self, name: str, **kwargs):
        vector_cfg = kwargs.get("vector_config")
        self.created.append((name, str(vector_cfg)))
        self._exists.add(name)

    def delete(self, name: str):
        self._exists.discard(name)


class FakeClient:
    def __init__(self):
        self.collections = FakeCollections()


def test_build_ingests_all_chunks_with_metadata() -> None:
    documents = load_document_files(get_settings().data_pack_3_path)
    chunks = chunk_documents(documents)
    client = FakeClient()
    count = rebuild_collection(
        client=client,
        collection="NetraCareChunks",
        embedding_model="Snowflake/snowflake-arctic-embed-m-v1.5",
        chunks=chunks,
    )
    assert count == len(chunks) >= 40
    assert len(client.collections.inserted) == len(chunks)
    first = client.collections.inserted[0]
    assert set(first) == {"text", "source", "section", "chunk_id"}
    ids = [obj["chunk_id"] for obj in client.collections.inserted]
    assert len(set(ids)) == len(ids)


def test_rebuild_is_explicit_and_idempotent() -> None:
    documents = load_document_files(get_settings().data_pack_3_path)
    chunks = chunk_documents(documents)
    client = FakeClient()
    rebuild_collection(
        client=client, collection="C", embedding_model="m", chunks=chunks[:3]
    )
    assert len(client.collections.created) == 1
    # Second rebuild deletes then recreates exactly once more.
    rebuild_collection(
        client=client, collection="C", embedding_model="m", chunks=chunks[:3]
    )
    assert len(client.collections.created) == 2


def test_ensure_collection_reuses_existing() -> None:
    client = FakeClient()
    client.collections._exists.add("NetraCareChunks")
    ensure_collection(client, collection="NetraCareChunks", embedding_model="m")
    assert client.collections.created == []
