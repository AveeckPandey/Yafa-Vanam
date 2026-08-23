"""Live-commerce intent detection (spec §8/§27)."""

from __future__ import annotations

import pytest

from app.rag.filters import detect_live_data_domains, is_pure_live_data_query
from app.rag.models import LiveDataDomain


class TestDomainDetection:
    @pytest.mark.parametrize(
        ("query", "domain"),
        [
            ("Is this in stock?", LiveDataDomain.INVENTORY),
            ("When will Fernwing be back in stock?", LiveDataDomain.INVENTORY),
            ("What's the price of Soft Ember?", LiveDataDomain.PRICE),
            ("How much does it cost?", LiveDataDomain.PRICE),
            ("Any discount on this?", LiveDataDomain.DISCOUNTS),
            ("Are there reviews for Fernwing?", LiveDataDomain.REVIEWS),
            ("What rating does it have?", LiveDataDomain.RATINGS),
            ("Where is my order?", LiveDataDomain.ORDER_STATUS),
            ("How long is shipping?", LiveDataDomain.SHIPPING),
        ],
    )
    def test_detects_domain(self, query, domain):
        assert domain in detect_live_data_domains(query)

    @pytest.mark.parametrize(
        "query",
        [
            "What does Fernwing Volume Mascara do?",
            "Where does this fit in my routine?",
            "What is the scent profile?",
            "Which ingredients are verified?",
        ],
    )
    def test_knowledge_questions_trigger_nothing(self, query):
        assert detect_live_data_domains(query) == []


class TestPureVsMixed:
    @pytest.mark.parametrize(
        "query",
        [
            "Is this in stock?",                      # spec §27 exact case
            "Do you have Fernwing in stock?",
            "How much does it cost?",
            "Are there any reviews?",
            "Is this available in India?",
            "When will my order arrive?",
        ],
    )
    def test_pure_live_questions(self, query):
        assert is_pure_live_data_query(query)

    @pytest.mark.parametrize(
        "query",
        [
            "What does Soft Ember smell like?",
            "What does this cost and what does it smell like?",  # mixed
            "Tell me about Fernwing Volume Mascara.",
        ],
    )
    def test_mixed_or_knowledge_questions(self, query):
        assert not is_pure_live_data_query(query)
