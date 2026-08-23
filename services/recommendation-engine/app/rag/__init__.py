"""Product-knowledge RAG layer (Phase 1).

Retrieval-only: semantic chunks from the canonical catalogue with provenance,
trust filtering, alias resolution and pgvector search. Generation/LLM wiring is
intentionally out of scope until retrieval evaluation passes.
"""

from app.rag.chunker import SemanticChunk, build_chunks, build_document, extract_aliases
from app.rag.config import DimensionMismatchError, RagSettings
from app.rag.models import ChunkType, LiveDataDomain, TrustLevel
from app.rag.repository import RagRepository
from app.rag.schemas import RagSearchRequest, RagSearchResponse
from app.rag.source_policy import can_surface_as_customer_fact

__all__ = [
    "ChunkType",
    "DimensionMismatchError",
    "LiveDataDomain",
    "RagRepository",
    "RagSearchRequest",
    "RagSearchResponse",
    "RagSettings",
    "SemanticChunk",
    "TrustLevel",
    "build_chunks",
    "build_document",
    "can_surface_as_customer_fact",
    "extract_aliases",
]
