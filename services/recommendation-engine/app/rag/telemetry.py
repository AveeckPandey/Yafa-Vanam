"""Privacy-preserving RAG decision telemetry for CloudWatch/log drains."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("yafa.rag.telemetry")


@dataclass
class RetrievalTrace:
    request_id: str
    query: str
    tenant_id: str
    started_at: float = field(default_factory=time.monotonic)
    events: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event: str, **details: Any) -> None:
        self.events.append({"event": event, **details})

    def emit(self, *, outcome: str) -> None:
        logger.info(json.dumps({
            "event": "rag_trace", "request_id": self.request_id,
            "query_hash": hashlib.sha256(self.query.encode("utf-8")).hexdigest()[:16],
            "tenant": self.tenant_id, "outcome": outcome,
            "latency_ms": round((time.monotonic() - self.started_at) * 1000),
            "steps": self.events,
        }, separators=(",", ":")))
