"""Intent classification + category routing (Phase 2 spec section 28)."""
from __future__ import annotations

import pytest

from app.yafa.intents import Intent, categories_for_intent, classify


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("hi", Intent.GREETING_OR_SMALL_TALK),
        ("hello", Intent.GREETING_OR_SMALL_TALK),
        ("hey there!", Intent.GREETING_OR_SMALL_TALK),
        ("thank you", Intent.GREETING_OR_SMALL_TALK),
        ("how are you?", Intent.GREETING_OR_SMALL_TALK),
        ("can you help me?", Intent.ADVISOR_START),
        ("what can you do?", Intent.ADVISOR_START),
        ("I need makeup help", Intent.ADVISOR_START),
        ("What does Soft Ember smell like?", Intent.PRODUCT_INFORMATION),
        ("How do I use Fernwing Volume Mascara?", Intent.PRODUCT_INFORMATION),
        ("What are the product warnings?", Intent.PRODUCT_INFORMATION),
        (
            "what is the expiry date of this product?",
            Intent.PRODUCT_INFORMATION,
        ),
        (
            "Fernwing versus Nightbloom - which lasts longer?",
            Intent.PRODUCT_COMPARISON,
        ),
        ("Recommend a lipstick for me", Intent.LIP_RECOMMENDATION),
        ("I need a blush for a wedding", Intent.CHEEK_RECOMMENDATION),
        ("Which mascara should I get?", Intent.EYE_RECOMMENDATION),
        ("Looking for a good foundation for oily skin", Intent.COMPLEXION_RECOMMENDATION),
        ("Suggest a moisturizer for dehydration", Intent.SKINCARE_RECOMMENDATION),
        ("What fragrance should I wear to an evening wedding?", Intent.FRAGRANCE_RECOMMENDATION),
        ("Build my look for a wedding", Intent.RECOMMEND_FULL_LOOK),
        ("I want a complete look with makeup to match my outfit", Intent.RECOMMEND_FULL_LOOK),
        ("Build me a skincare routine", Intent.ROUTINE_BUILD),
        ("Can I use retinol with vitamin c?", Intent.INGREDIENT_QUESTION),
        ("Does this work together with my moisturizer?", Intent.COMPATIBILITY_QUESTION),
        ("What is my shade?", Intent.SHADE_MATCH_REQUEST),
        ("what shade should I use?", Intent.SHADE_MATCH_REQUEST),
        ("match my makeup to this", Intent.OUTFIT_MATCHING),
        ("match makeup to my outfit", Intent.OUTFIT_MATCHING),
        (
            "I'm wearing navy blue and beige",
            Intent.OUTFIT_MATCHING,
        ),
        ("hello, what does this smell like?", Intent.GREETING_OR_SMALL_TALK),
        ("Are your products cruelty-free?", Intent.BRAND_VALUES_POLICY),
        ("Is everything vegan?", Intent.BRAND_VALUES_POLICY),
        ("Do you donate money to charity?", Intent.BRAND_VALUES_POLICY),
    ],
)
def test_classification(message: str, expected: Intent):
    assert classify(message) == expected


def test_recommend_verb_without_category_is_generic_product():
    assert classify("What would you recommend for me?") == Intent.RECOMMEND_PRODUCT


def test_category_routing_for_full_look():
    categories = categories_for_intent(Intent.RECOMMEND_FULL_LOOK, "")
    assert categories == ["complexion", "eyes", "cheeks", "lips"]


def test_category_routing_for_category_intents():
    assert categories_for_intent(Intent.LIP_RECOMMENDATION, "") == ["lips"]
    assert categories_for_intent(
        Intent.FRAGRANCE_RECOMMENDATION, ""
    ) == ["fragrance"]


def test_generic_recommend_infers_category_from_message():
    assert categories_for_intent(
        Intent.RECOMMEND_PRODUCT, "a nice fragrance please"
    ) == ["fragrance"]
    fallback = categories_for_intent(Intent.RECOMMEND_PRODUCT, "something nice")
    assert fallback == ["lips"]
