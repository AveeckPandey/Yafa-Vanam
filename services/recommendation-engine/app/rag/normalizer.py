"""Text normalization and stable identity helpers for ingestion."""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

_CHUNK_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://yafavanam.com/rag-chunks-v1")

_WHITESPACE = re.compile(r"\s+")
_ALIAS_NOISE = re.compile(r"[^a-z0-9 ]+")
_REPLACEMENT_CHAR = "�"


def normalize_text(value: Any) -> str:
    """Collapse whitespace so formatting changes do not alter content hashes."""
    if not isinstance(value, str):
        return ""
    return _WHITESPACE.sub(" ", value.replace(_REPLACEMENT_CHAR, "-")).strip()


def content_hash(*parts: str) -> str:
    joined = "\x1f".join(normalize_text(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def stable_chunk_id(canonical_product_id: str, chunk_type: str, source_version: str, hash_value: str) -> str:
    """Deterministic chunk identity: same inputs never produce a second row."""
    key = f"{canonical_product_id}|{chunk_type}|{source_version}|{hash_value}"
    return str(uuid.uuid5(_CHUNK_NAMESPACE, key))


def stable_document_id(canonical_product_id: str) -> str:
    """Deterministic document identity for upsert-by-product."""
    return str(uuid.uuid5(_CHUNK_NAMESPACE, f"document|{canonical_product_id}"))


def normalize_alias(alias: str) -> str:
    """Aggressive form used for exact-ish alias matching before vector search."""
    lowered = normalize_text(alias).lower()
    return _ALIAS_NOISE.sub(" ", lowered).strip()
