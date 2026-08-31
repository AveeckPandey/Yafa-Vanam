"""Immediately withdraw an approved document from customer retrieval."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.rag.config import RagSettings  # noqa: E402
from app.rag.repository import RagRepository  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("canonical_product_id")
    parser.add_argument("--tenant", default="public")
    args = parser.parse_args()
    settings = RagSettings.from_env()
    if not settings.vector_database_url:
        raise SystemExit("VECTOR_DATABASE_URL is required")
    repo = RagRepository(settings.vector_database_url)
    try:
        if not repo.revoke_document(args.canonical_product_id, tenant_id=args.tenant):
            raise SystemExit("no active document matched")
    finally:
        repo.close()
    print("document revoked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
