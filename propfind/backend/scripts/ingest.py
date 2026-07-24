"""
ingest.py — One-shot ingestion script.
Run from propfind/backend/:  python scripts/ingest.py
"""
import sys
import logging
from pathlib import Path

# Allow imports from backend/app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("ingest")


def main():
    from app.ingest.loader import load_all
    from app.ingest.chunker import build_all_chunks
    from app.ingest.embedder import embed_and_upsert, get_collection_count

    logger.info("=== Step 1: Loading CSVs into SQLite ===")
    counts = load_all()
    for table, n in counts.items():
        logger.info(f"  {table}: {n} rows inserted")

    logger.info("=== Step 2: Building NL chunks ===")
    chunks = build_all_chunks()
    logger.info(f"  Total chunks: {len(chunks)}")

    logger.info("=== Step 3: Embedding & upserting into ChromaDB ===")
    total = embed_and_upsert(chunks)
    logger.info(f"  Upserted {total} docs. ChromaDB total: {get_collection_count()}")

    logger.info("=== Ingestion complete ===")


if __name__ == "__main__":
    main()
