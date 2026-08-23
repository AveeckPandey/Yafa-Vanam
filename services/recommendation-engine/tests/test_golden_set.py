"""Golden set: structure and determinism, never absolute scores.

Each case pins ids present/absent, pairwise order, machine-readable codes and
note keys — then runs the engine TWICE asserting byte-identical output so any
nondeterminism (dict ordering, floating drift, hidden randomness) fails here
before it reaches users.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.recommendation.canonical.normalization import to_canonical_profile
from app.recommendation.canonical.schemas import CoordinationHints
from app.recommendation.engines import get_engine

FIXTURE = Path(__file__).parent / "fixtures" / "recommendation_golden.json"


def _cases():
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return document["cases"]


def _run(case: dict):
    engine = get_engine(case["engine"])
    coordination = case.get("coordination")
    return engine(
        to_canonical_profile(case["profile"]),
        limit=case.get("limit", 3),
        coordination=CoordinationHints(**coordination) if coordination else None,
        debug=False,
    )


def _dump(result) -> str:
    return json.dumps({
        "items": [item.model_dump(mode="json") for item in result.items],
        "notes": result.notes,
    }, sort_keys=True)


def _find_index(items, token: str):
    """Locate an item by product_id or shade name (brow rows are shade-level)."""
    for position, item in enumerate(items):
        if item.product_id == token or item.shade_name == token:
            return position
    return None


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case["name"])
def test_golden_case(case: dict):
    first = _run(case)
    second = _run(case)
    assert _dump(first) == _dump(second), f"{case['name']}: engine output must be deterministic"

    items = first.items
    assert items, "every golden case must produce recommendations"

    dumped_ids = [item.product_id for item in items]
    for product_id in case.get("must_include_product_ids") or []:
        assert product_id in dumped_ids
    for product_id in case.get("must_exclude_product_ids") or []:
        assert product_id not in dumped_ids

    for token, maximum in (case.get("max_occurrences") or {}).items():
        assert dumped_ids.count(token) <= maximum

    all_codes = {code for item in items for code in item.reason_codes}
    for code in case.get("reason_codes_present_anywhere") or []:
        assert code in all_codes, f"{case['name']}: expected reason code {code}"
    for prefix in case.get("reason_code_prefixes_anywhere") or []:
        assert any(code.startswith(prefix) for code in all_codes), f"{case['name']}: expected {prefix}*"

    for left, right in case.get("order_constraints") or []:
        left_index, right_index = _find_index(items, left), _find_index(items, right)
        assert left_index is not None, f"{case['name']}: {left!r} not among recommendations"
        assert right_index is not None, f"{case['name']}: {right!r} not among recommendations"
        assert left_index < right_index, f"{case['name']}: {left!r} must rank before {right!r}"

    for key in case.get("notes_keys_present") or []:
        assert key in first.notes, f"{case['name']}: notes must carry {key}"

    for path, expected in (case.get("notes_paths_equal") or {}).items():
        value: object = first.notes
        for part in path.split("."):
            assert isinstance(value, dict) and part in value, f"{case['name']}: missing notes path {path}"
            value = value[part]
        assert value == expected, f"{case['name']}: {path} == {value!r}, expected {expected!r}"
