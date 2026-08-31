#!/usr/bin/env python
"""Evaluate grounded answer consistency against the existing RAG fixture.

This complements retrieval evaluation by exercising the complete chat path,
repeating each factual question, and failing on unstable answers, missing
grounding, wrong products/chunk types, or excessive p95 latency.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.yafa.orchestrator import handle_chat  # noqa: E402
from app.yafa.schemas import PageContext, YafaChatRequest  # noqa: E402

DEFAULT_FIXTURE = SERVICE_ROOT / "tests" / "fixtures" / "rag_eval.json"


async def run(fixture: Path, repeats: int, max_p95_ms: float) -> int:
    cases = json.loads(fixture.read_text(encoding="utf-8"))["cases"]
    failures: list[str] = []
    latencies: list[float] = []
    evaluated = 0
    for case in cases:
        if case.get("is_live_data_check") or case.get("expect_requires_live_data"):
            continue
        answers = []
        for repeat in range(repeats):
            started = time.monotonic()
            response = await handle_chat(YafaChatRequest(
                conversation_id=f"eval-{case['id']}-{repeat}",
                message=case["question"],
                page_context=PageContext(**case["page_context"]) if case.get("page_context") else None,
            ))
            latencies.append((time.monotonic() - started) * 1000)
            answers.append(response.message)
            products = {chunk.product_id for chunk in response.grounding}
            types = {chunk.chunk_type for chunk in response.grounding}
            expected_product = case.get("expected_product")
            if expected_product and expected_product not in products:
                failures.append(f"{case['id']}: missing grounded product {expected_product}")
            for chunk_type in case.get("expected_chunk_types") or []:
                if chunk_type not in types:
                    failures.append(f"{case['id']}: missing grounded chunk type {chunk_type}")
        if len(set(answers)) != 1:
            failures.append(f"{case['id']}: answer changed across {repeats} identical runs")
        evaluated += 1

    ordered = sorted(latencies)
    p95 = ordered[min(len(ordered) - 1, max(0, int(len(ordered) * 0.95) - 1))] if ordered else 0.0
    if p95 > max_p95_ms:
        failures.append(f"p95 latency {p95:.1f}ms exceeded {max_p95_ms:.1f}ms")
    print(json.dumps({
        "cases": evaluated, "repeats": repeats, "p95_ms": round(p95, 1),
        "mean_ms": round(statistics.fmean(latencies), 1) if latencies else 0,
        "failures": failures,
    }, indent=2))
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-p95-ms", type=float, default=2500)
    args = parser.parse_args()
    return asyncio.run(run(args.fixture, max(2, args.repeats), args.max_p95_ms))


if __name__ == "__main__":
    raise SystemExit(main())
