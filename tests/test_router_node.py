"""
Tests for Router Node — src/agents/nodes/router_node.py

Tests the pure-logic helper functions (no LLM calls needed):
    - _compute_complexity_heuristics: Scoring queries by lexical signals
    - _parse_classification: Parsing LLM output to query types
    - _score_to_type: Converting numeric scores to categorical types
"""

from __future__ import annotations

import pytest
from src.agents.nodes.router_node import (
    _compute_complexity_heuristics,
    _parse_classification,
    _score_to_type,
)


# ──────────────────────────────────────────────────────────────
# Heuristic Complexity Scoring
# ──────────────────────────────────────────────────────────────


class TestComputeComplexityHeuristics:
    """Tests for the rule-based complexity scoring function."""

    def test_short_simple_question(self):
        """A simple factual question should have low complexity."""
        score = _compute_complexity_heuristics("What is the revenue?")
        assert score < 0.5

    def test_long_question_increases_score(self):
        """Questions longer than 200 chars should get a +0.2 bump."""
        short = _compute_complexity_heuristics("What is the revenue?")
        long_q = "Explain in detail the " + "financial performance " * 15 + " of the company."
        long_score = _compute_complexity_heuristics(long_q)
        assert long_score > short

    def test_medium_length_question(self):
        """Questions between 100-200 chars should get a +0.1 bump."""
        q = "x" * 150  # 150 chars
        score = _compute_complexity_heuristics(q)
        assert score >= 0.3  # base 0.2 + 0.1

    @pytest.mark.parametrize("keyword", [
        "compare", "contrast", "versus", "difference between", "all attached files",
    ])
    def test_multi_part_keywords_trigger_high_score(self, keyword):
        """Multi-part keywords should push score well above 0.5."""
        q = f"Can you {keyword} Q1 and Q2 results?"
        score = _compute_complexity_heuristics(q)
        assert score >= 0.8, f"Expected high score for keyword '{keyword}', got {score}"

    @pytest.mark.parametrize("conjunction", ["and also", "additionally", "furthermore"])
    def test_conjunctions_add_moderate_bump(self, conjunction):
        """Conjunctions should add +0.15 to the score."""
        base = _compute_complexity_heuristics("What is the profit?")
        with_conj = _compute_complexity_heuristics(f"What is the profit {conjunction} the loss?")
        assert with_conj > base

    @pytest.mark.parametrize("phrase", [
        "analyze", "explain why", "how does", "what caused", "impact of",
    ])
    def test_analysis_phrases_boost_score(self, phrase):
        """Analysis phrases should increase complexity."""
        q = f"{phrase} the market decline?"
        score = _compute_complexity_heuristics(q)
        assert score >= 0.4  # base 0.2 + 0.2

    @pytest.mark.parametrize("word", [
        "calculate", "compute", "total", "sum", "average", "percentage",
    ])
    def test_calculation_words_boost_score(self, word):
        """Calculation keywords should increase complexity."""
        q = f"Please {word} the annual return."
        score = _compute_complexity_heuristics(q)
        assert score >= 0.34  # base 0.2 + 0.15 = 0.35 (allow float rounding)

    def test_score_capped_at_one(self):
        """Score should never exceed 1.0 even with multiple triggers."""
        q = "Compare and contrast and additionally analyze the difference between Q1 and Q2 calculate the total."
        score = _compute_complexity_heuristics(q)
        assert score <= 1.0

    def test_empty_string(self):
        """Empty question should get baseline score."""
        score = _compute_complexity_heuristics("")
        assert score == 0.2  # baseline


# ──────────────────────────────────────────────────────────────
# LLM Classification Parsing
# ──────────────────────────────────────────────────────────────


class TestParseClassification:
    """Tests for parsing raw LLM response into query types."""

    @pytest.mark.parametrize("response,expected", [
        ("SIMPLE", "simple"),
        ("simple", "simple"),
        ("  SIMPLE  ", "simple"),
        ("STANDARD", "standard"),
        ("COMPLEX", "complex"),
        ("MULTI_HOP", "multi_hop"),
        ("MULTI-HOP", "multi_hop"),
        ("multi_hop", "multi_hop"),
        ("I think this is COMPLEX.", "complex"),
        ("definitely SIMPLE query", "simple"),
        ("unknown_response", "standard"),  # fallback
        ("", "standard"),  # empty → fallback
    ])
    def test_parse_classification(self, response, expected):
        """Should correctly parse various LLM classification responses."""
        assert _parse_classification(response) == expected


# ──────────────────────────────────────────────────────────────
# Score-to-Type Conversion
# ──────────────────────────────────────────────────────────────


class TestScoreToType:
    """Tests for converting numeric scores to query type strings."""

    @pytest.mark.parametrize("score,expected", [
        (0.0, "simple"),
        (0.1, "simple"),
        (0.29, "simple"),
        (0.3, "standard"),
        (0.5, "standard"),
        (0.59, "standard"),
        (0.6, "complex"),
        (0.7, "complex"),
        (0.79, "complex"),
        (0.8, "multi_hop"),
        (0.9, "multi_hop"),
        (1.0, "multi_hop"),
    ])
    def test_score_to_type_boundaries(self, score, expected):
        """Should map scores to correct types at boundaries."""
        assert _score_to_type(score) == expected
