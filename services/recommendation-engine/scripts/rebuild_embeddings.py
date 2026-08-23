#!/usr/bin/env python
"""Re-embed every stored RAG chunk from its persisted content.

Run this when the embedding provider/model changes (old model -> rebuild ->
new model). All existing vectors are cleared FIRST so a mid-run failure can
never leave two embedding spaces mixed in rag_chunks — search simply returns
nothing until the rebuild completes. The embedding-space metadata row is
refreshed on success so ingestion and startup validation accept the new space.

The vector column dimension must already match the configured provider; a
different dimension requires a new SQL migration plus this rebuild.

Usage (from services/recommendation-engine):
    python scripts/rebuild_embeddings.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.rag.config import RagSettings  # noqa: E402
from app.rag.providers import build_provider  # noqa: E402
from app.rag.repository import RagRepository  # noqa: E402


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        for candidate in (SERVICE_ROOT.parents[1] / ".env", SERVICE_ROOT / ".env"):
            if candidate.exists():
                load_dotenv(candidate, override=False)
    except ImportError:
        pass


def main() -> int:
    _load_dotenv()
    settings = RagSettings.from_env()
    if not settings.vector_database_url:
        print("error: VECTOR_DATABASE_URL is not configured", file=sys.stderr)
        return 2

    provider = build_provider(settings)
    repo = RagRepository(settings.vector_database_url)
    regenerated = 0
    try:
        repo.ensure_schema(provider.dimension)  # re-validates stored dimension
        cleared = repo.clear_all_embeddings()
        print(f"cleared {cleared} old vectors; re-embedding with {provider.model_name} "
              f"(dim {provider.dimension})...")

        rows = repo.all_chunk_content()
        batch_size = 32
        for start in range(0, len(rows), batch_size):
            batch = rows[start : start + batch_size]
            vectors = asyncio.run(provider.embed_documents([content for _, content in batch]))
            repo.store_embeddings({chunk_id: vector for (chunk_id, _), vector in zip(batch, vectors)})
            regenerated += len(vectors)
            print(f"  {regenerated}/{len(rows)}")

        repo.set_embedding_metadata(
            provider=provider.provider_name, model=provider.model_name, dimension=provider.dimension,
        )
    finally:
        repo.close()

    print(json.dumps({
        "chunks_reembedded": regenerated,
        "provider": provider.provider_name,
        "model": provider.model_name,
        "dimension": provider.dimension,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
