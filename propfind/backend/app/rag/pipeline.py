"""
pipeline.py — Orchestrates the full RAG pipeline (retrieve → generate).
"""
from __future__ import annotations

import logging
from typing import Generator

from app.rag.retriever import retrieve
from app.rag.generator import generate_answer, stream_answer

logger = logging.getLogger(__name__)


def rag_query(
    query: str,
    n_results: int = 8,
    filters: dict | None = None,
    chat_history: list[dict] | None = None,
) -> dict:
    """
    Non-streaming RAG.
    Returns {"answer": str, "sources": list[dict], "source_count": int}
    """
    chunks = retrieve(query, n_results=n_results, filters=filters, chat_history=chat_history)
    answer = generate_answer(query, chunks, chat_history=chat_history)
    return {
        "answer": answer,
        "sources": chunks,
        "source_count": len(chunks),
    }


def rag_stream(
    query: str,
    n_results: int = 8,
    filters: dict | None = None,
    chat_history: list[dict] | None = None,
) -> tuple[Generator[str, None, None], list[dict]]:
    """
    Streaming RAG.
    Returns (token_generator, source_chunks).
    The caller should first yield sources metadata, then stream tokens.
    """
    chunks = retrieve(query, n_results=n_results, filters=filters, chat_history=chat_history)
    token_gen = stream_answer(query, chunks, chat_history=chat_history)
    return token_gen, chunks
