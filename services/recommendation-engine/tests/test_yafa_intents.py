"""RAG-only intent classification rejects ranking requests explicitly."""
import pytest

from app.yafa.intents import Intent, classify


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("hi", Intent.GREETING_OR_SMALL_TALK),
        ("What does Soft Ember smell like?", Intent.PRODUCT_INFORMATION),
        ("Is everything vegan?", Intent.PRODUCT_INFORMATION),
        ("Fernwing versus Nightbloom", Intent.PRODUCT_COMPARISON),
        ("Recommend a lipstick for me", Intent.RECOMMENDATION_UNAVAILABLE),
        ("Build my look for a wedding", Intent.RECOMMENDATION_UNAVAILABLE),
        ("What can you do?", Intent.GENERAL),
    ],
)
def test_classification(message: str, expected: Intent):
    assert classify(message) is expected
