#!/usr/bin/env python
"""Ingest the canonical product catalogue into the pgvector RAG store.

Usage (from services/recommendation-engine):
    python scripts/ingest_products.py                       # skip unchanged chunks
    python scripts/ingest_products.py --product-id yv-frag-010   # single-product trial
    python scripts/ingest_products.py --force-embed         # re-embed everything

Free-tier embedding endpoints rate-limit: a failed run stops safely after the
products committed so far — re-run the same command to resume without
duplicates.

Reads VECTOR_DATABASE_URL / EMBEDDING_* / OPENROUTER_* from the environment
(.env is loaded from the repo root when python-dotenv is available).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.rag.config import RagSettings  # noqa: E402
from app.rag.providers import build_provider  # noqa: E402
from app.rag.ingestion import ingest_catalogue  # noqa: E402
from app.rag.repository import RagRepository  # noqa: E402


def _load_dotenv() -> None:
    """Best-effort .env load so local runs do not need exported variables."""
    try:
        from dotenv import load_dotenv

        for candidate in (SERVICE_ROOT.parents[1] / ".env", SERVICE_ROOT / ".env"):
            if candidate.exists():
                load_dotenv(candidate, override=False)
    except ImportError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-embed", action="store_true", help="recompute embeddings even for unchanged chunks")
    parser.add_argument(
        "--product-id",
        action="append",
        dest="product_ids",
        metavar="ID",
        help="ingest only this canonical product id (repeatable); e.g. yv-frag-010 (Soft Ember)",
    )
    parser.add_argument("--quiet", action="store_true", help="only print the final stats JSON")
    args = parser.parse_args()

    _load_dotenv()
    settings = RagSettings.from_env()
    if not settings.vector_database_url:
        print("error: VECTOR_DATABASE_URL is not configured", file=sys.stderr)
        return 2

    provider = build_provider(settings)  # validates configured vs model dimension
    repo = RagRepository(settings.vector_database_url)
    lock_acquired = False
    try:
        repo.acquire_ingestion_lock()
        lock_acquired = True
        def log(message: str) -> None:
            if not args.quiet:
                print(message)

        stats = asyncio.run(
            ingest_catalogue(
                repo, provider, settings,
                force_embed=args.force_embed, product_ids=args.product_ids, log=log,
            )
        )
    except Exception as error:  # surface a clean failure for CI/Railway jobs
        print(f"ingestion failed: {error}", file=sys.stderr)
        return 1
    finally:
        if lock_acquired:
            repo.release_ingestion_lock()
        repo.close()

    print(json.dumps(stats.as_dict(), indent=2))
    return 1 if stats.stopped_reason else 0


if __name__ == "__main__":
    raise SystemExit(main())
