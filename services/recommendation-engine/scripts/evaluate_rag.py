#!/usr/bin/env python
"""Run the RAG evaluation fixture against a live vector database.

Checks per case: expected product retrieved, expected chunk types present,
claim-safety (no unverified/mock content surfaced to customers) and live-data
deferral. Exits non-zero on any failure so it can gate deploys.

Usage (from services/recommendation-engine):
    python scripts/evaluate_rag.py [--fixture tests/fixtures/rag_eval.json] [--json]
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

from app.rag.config import RagSettings  # noqa: E402
from app.rag.models import TrustLevel  # noqa: E402
from app.rag.retriever import build_retriever  # noqa: E402
from app.rag.schemas import PageContext, RagSearchRequest  # noqa: E402

DEFAULT_FIXTURE = SERVICE_ROOT / "tests" / "fixtures" / "rag_eval.json"

# Trust levels that must never appear in customer-facing factual answers.
_FORBIDDEN_CUSTOMER_TRUST = {
    TrustLevel.MOCK_DEVELOPMENT.value,
    TrustLevel.LEGACY_CONCEPT.value,
}


async def _run_case(retriever, case: dict, repeats: int) -> dict:
    request = RagSearchRequest(
        query=case["question"],
        top_k=case.get("top_k", 5),
        allowed_for_customer=True,
        page_context=PageContext(**case["page_context"]) if case.get("page_context") else None,
    )
    responses = []
    latencies = []
    for _ in range(repeats):
        started = time.monotonic()
        responses.append(await retriever.search(request))
        latencies.append((time.monotonic() - started) * 1000)
    response = responses[0]
    failures: list[str] = []
    retrieved_products = {result.product_id for result in response.results}
    retrieved_types = {result.chunk_type for result in response.results}
    result_signatures = [
        [(result.chunk_id, result.similarity) for result in item.results]
        for item in responses
    ]
    if any(signature != result_signatures[0] for signature in result_signatures[1:]):
        failures.append("retrieval changed across identical repeated queries")
    if response.conflicts:
        failures.append(f"unresolved source conflicts: {', '.join(response.conflicts)}")

    if not case.get("is_live_data_check"):
        if case.get("expected_product") and case["expected_product"] not in retrieved_products:
            failures.append(f"expected product {case['expected_product']} not retrieved")
        for expected_type in case.get("expected_chunk_types") or []:
            if expected_type not in retrieved_types:
                failures.append(f"expected chunk type '{expected_type}' not retrieved")
        if not response.results and not case.get("allow_empty"):
            failures.append("no results retrieved")

    for domain in case.get("expect_requires_live_data") or []:
        if domain not in {requirement.domain.value for requirement in response.requires_live_data}:
            failures.append(f"expected requires_live_data domain '{domain}'")

    # Claim safety: customer mode may never surface concept/mock-trust chunks.
    for result in response.results:
        if result.trust_level in _FORBIDDEN_CUSTOMER_TRUST:
            failures.append(
                f"claim-safety: {result.trust_level} chunk surfaced ({result.chunk_type})"
            )
        if case.get("expect_results_suppressed") and response.results:
            failures.append("expected results suppressed but knowledge chunks were returned")

    return {
        "id": case.get("id") or case["question"][:60],
        "question": case["question"],
        "passed": not failures,
        "failures": failures,
        "top_result": (
            f"{response.results[0].product_id}/{response.results[0].chunk_type}"
            f"@{response.results[0].similarity}"
            if response.results
            else None
        ),
        "resolution": response.resolution,
        "mean_latency_ms": round(statistics.fmean(latencies), 1),
        "max_latency_ms": round(max(latencies), 1),
    }


async def _main_async(fixture_path: Path, as_json: bool, repeats: int, max_p95_ms: float) -> int:
    cases = json.loads(fixture_path.read_text(encoding="utf-8"))["cases"]
    retriever = build_retriever(RagSettings.from_env())
    reports = []
    for case in cases:
        report = await _run_case(retriever, case, repeats)
        reports.append(report)
        marker = "PASS" if report["passed"] else "FAIL"
        print(f"[{marker}] {report['id']}: {report['question']}")
        if not report["passed"]:
            for failure in report["failures"]:
                print(f"       - {failure}")

    passed = sum(1 for report in reports if report["passed"])
    latency_values = sorted(report["max_latency_ms"] for report in reports)
    p95 = latency_values[min(len(latency_values) - 1, max(0, int(len(latency_values) * 0.95) - 1))]
    if p95 > max_p95_ms:
        print(f"[FAIL] p95 latency {p95:.1f}ms exceeds {max_p95_ms:.1f}ms")
        passed = max(0, passed - 1)
    print(f"\n{passed}/{len(reports)} cases passed")
    if as_json:
        print(json.dumps({"passed": passed, "total": len(reports), "cases": reports}, indent=2))
    return 0 if passed == len(reports) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--json", action="store_true", help="append a machine-readable summary")
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--max-p95-ms", type=float, default=1500)
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv

        for candidate in (SERVICE_ROOT.parents[1] / ".env", SERVICE_ROOT / ".env"):
            if candidate.exists():
                load_dotenv(candidate, override=False)
    except ImportError:
        pass

    return asyncio.run(_main_async(args.fixture, args.json, max(2, args.repeats), args.max_p95_ms))


if __name__ == "__main__":
    raise SystemExit(main())
