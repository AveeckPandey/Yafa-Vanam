#!/usr/bin/env python
"""Build a new embedding space without touching the active production store.

Point SHADOW_VECTOR_DATABASE_URL at a fresh PostgreSQL/pgvector database and
configure EMBEDDING_PROVIDER/MODEL/DIMENSION for the candidate model. The
active VECTOR_DATABASE_URL is never opened for writes. After evaluation,
promote by deploying a new service revision whose VECTOR_DATABASE_URL points
to the shadow database; traffic switching and rollback stay atomic at the
load balancer/ECS deployment layer.
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import replace
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.rag.config import RagSettings  # noqa: E402
from app.rag.ingestion import ingest_catalogue  # noqa: E402
from app.rag.providers import build_provider  # noqa: E402
from app.rag.repository import RagRepository  # noqa: E402


def main() -> int:
    settings = RagSettings.from_env()
    shadow_url = (os.getenv("SHADOW_VECTOR_DATABASE_URL") or "").strip()
    if not shadow_url:
        raise SystemExit("SHADOW_VECTOR_DATABASE_URL is required")
    if shadow_url == settings.vector_database_url:
        raise SystemExit("shadow database must not be the active VECTOR_DATABASE_URL")

    shadow_settings = replace(settings, vector_database_url=shadow_url, cache_namespace="shadow-build")
    provider = build_provider(shadow_settings)
    repo = RagRepository(shadow_url)
    try:
        stats = asyncio.run(ingest_catalogue(repo, provider, shadow_settings, force_embed=True, log=print))
        if stats.stopped_reason:
            raise SystemExit(f"shadow build incomplete: {stats.stopped_reason}")
        metadata = repo.get_embedding_metadata()
        expected = {
            "embedding_provider": provider.provider_name,
            "embedding_model": provider.model_name,
            "embedding_dimension": provider.dimension,
        }
        if metadata != expected:
            raise SystemExit("shadow embedding metadata verification failed")
    finally:
        repo.close()
    print("shadow embedding space is complete; run evaluation before promotion")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
