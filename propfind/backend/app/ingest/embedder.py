"""
embedder.py — Embeds text chunks with sentence-transformers and upserts into ChromaDB.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Sequence

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import CHROMA_PATH, EMBED_MODEL
from app.ingest.chunker import ChunkTuple

logger = logging.getLogger(__name__)

COLLECTION_NAME = "propfind_listings"

_model: SentenceTransformer | None = None
_chroma_client: chromadb.PersistentClient | None = None
_collection = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {EMBED_MODEL}")
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _chunk_id(text: str) -> str:
    """Deterministic ID from chunk text."""
    return hashlib.md5(text.encode()).hexdigest()


def embed_and_upsert(chunks: Sequence[ChunkTuple], batch_size: int = 64) -> int:
    """
    Embed all chunks and upsert into ChromaDB.
    Returns total number of upserted documents.
    """
    model = _get_model()
    collection = _get_collection()

    total = 0
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i : i + batch_size]
        texts = [c[0] for c in batch]
        metadatas = [c[1] for c in batch]
        ids = [_chunk_id(t) for t in texts]

        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        total += len(batch)
        logger.info(f"Upserted batch {i // batch_size + 1}: {len(batch)} docs (total {total})")

    return total


def query_collection(
    query_text: str,
    n_results: int = 10,
    where: dict | None = None,
) -> dict:
    """
    Search ChromaDB for similar chunks.
    Returns ChromaDB result dict with documents, metadatas, distances.
    """
    model = _get_model()
    collection = _get_collection()

    query_embedding = model.encode([query_text]).tolist()

    kwargs: dict = {
        "query_embeddings": query_embedding,
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    results = collection.query(**kwargs)
    return results


def get_collection_count() -> int:
    return _get_collection().count()
