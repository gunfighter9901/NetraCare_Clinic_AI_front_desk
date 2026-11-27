"""Build the Iteration 3 Weaviate collection from the supplied documents.

Usage from backend/:
    python build_index.py
    python build_index.py --collection NetraCareChunksTest
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from app.config import get_settings
from app.rag import chunk_documents, get_weaviate_client, load_document_files, rebuild_collection


def main() -> int:
    parser = argparse.ArgumentParser(description="Build NetraCare Weaviate RAG collection")
    parser.add_argument("--collection", default=None)
    args = parser.parse_args()
    settings = get_settings()
    collection = args.collection or settings.rag_collection
    documents = load_document_files(settings.data_pack_3_path)
    chunks = chunk_documents(
        documents,
        chunk_size=settings.rag_chunk_size,
        chunk_overlap=settings.rag_chunk_overlap,
    )
    client = get_weaviate_client()
    if client is None:
        print("WEAVIATE_URL or WEAVIATE_API_KEY is not configured")
        return 2
    try:
        count = rebuild_collection(
            client=client,
            collection=collection,
            embedding_model=settings.rag_embedding_model,
            chunks=chunks,
        )
    finally:
        try:
            client.close()
        except Exception:
            pass
        try:
            from app.rag import get_weaviate_client as _cached_client

            _cached_client.cache_clear()
        except Exception:
            pass
    sources = sorted({c.source for c in chunks})
    print(f"collection={collection} chunks={count} sources={','.join(sources)}")
    for chunk in chunks[:5]:
        print(f"  {chunk.chunk_id} | {chunk.source} > {chunk.section}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
