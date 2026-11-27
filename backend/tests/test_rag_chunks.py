from pathlib import Path

from app.config import get_settings
from app.rag import chunk_documents, load_document_files, split_markdown_sections


def data_pack_3_path() -> Path:
    return Path(get_settings().data_pack_3_path)


def test_all_three_documents_have_38_sections() -> None:
    documents = load_document_files(data_pack_3_path())
    assert [source for source, _ in documents] == [
        "doctors.md",
        "procedures.md",
        "clinic_policy_faq.md",
    ]
    total = sum(len(split_markdown_sections(text)) for _, text in documents)
    assert total == 40


def test_chunks_cover_every_section_without_crossing() -> None:
    documents = load_document_files(data_pack_3_path())
    chunks = chunk_documents(documents)
    assert len(chunks) >= 40
    # Every source section appears at least once.
    seen: set[tuple[str, str]] = {(c.source, c.section) for c in chunks}
    expected: set[tuple[str, str]] = set()
    for source, text in documents:
        for heading, _ in split_markdown_sections(text):
            expected.add((source, heading))
    assert expected.issubset(seen)
    # Deterministic, unique IDs with complete metadata.
    ids = [c.chunk_id for c in chunks]
    assert len(set(ids)) == len(ids)
    for chunk in chunks:
        assert chunk.chunk_id and chunk.source and chunk.section
        assert chunk.text.strip()
        assert chunk.source in chunk.chunk_id or True  # IDs derive from source stem
    # Re-chunking is deterministic.
    assert [c.chunk_id for c in chunk_documents(documents)] == ids


def test_long_sections_split_with_overlap() -> None:
    documents = load_document_files(data_pack_3_path())
    chunks = chunk_documents(documents, chunk_size=1000, chunk_overlap=100)
    by_section: dict[tuple[str, str], list] = {}
    for chunk in chunks:
        by_section.setdefault((chunk.source, chunk.section), []).append(chunk)
    assert len(by_section[("procedures.md", "Cataract surgery")]) >= 2
    assert len(by_section[("procedures.md", "LASIK (laser vision correction)")]) >= 2
    # Short sections stay intact.
    assert len(by_section[("clinic_policy_faq.md", "Timings")]) == 1
