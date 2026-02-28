"""
Tests for PageIndex Tree Searcher

Tests search data structures and async tree search logic:
- SearchStep creation and serialization
- SearchResult defaults and serialization
- TreeSearcher static helpers (_collect_pages, _calculate_confidence)
- Full async search with mocked LLM
- Empty tree error handling
- Max depth limiting
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.pageindex.tree_searcher import (
    SearchStep,
    SearchResult,
    TreeSearcher,
)
from src.pageindex.tree_generator import TreeNode, DocumentTree


# ──────────────────────────────────────────────────────────────
# SearchStep tests
# ──────────────────────────────────────────────────────────────


class TestSearchStep:
    """Tests for SearchStep dataclass."""

    def test_search_step_creation(self) -> None:
        """Test SearchStep with all fields."""
        step = SearchStep(
            level=0,
            node_id="sec_1",
            node_title="Financial Statements",
            reasoning="Likely contains revenue data",
            selected=True,
            page_range="p.10-30",
        )
        assert step.level == 0
        assert step.node_id == "sec_1"
        assert step.selected is True
        assert step.page_range == "p.10-30"

    def test_search_step_default_page_range(self) -> None:
        """Test SearchStep default page_range."""
        step = SearchStep(
            level=1,
            node_id="n1",
            node_title="Section",
            reasoning="Not relevant",
            selected=False,
        )
        assert step.page_range == ""

    def test_search_step_to_dict(self) -> None:
        """Test SearchStep serialization."""
        step = SearchStep(
            level=2,
            node_id="deep_1",
            node_title="Balance Sheet",
            reasoning="Contains asset breakdown",
            selected=True,
            page_range="p.15-20",
        )
        d = step.to_dict()

        assert d["level"] == 2
        assert d["node_id"] == "deep_1"
        assert d["node_title"] == "Balance Sheet"
        assert d["reasoning"] == "Contains asset breakdown"
        assert d["selected"] is True
        assert d["page_range"] == "p.15-20"


# ──────────────────────────────────────────────────────────────
# SearchResult tests
# ──────────────────────────────────────────────────────────────


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_search_result_defaults(self) -> None:
        """Test SearchResult default values."""
        result = SearchResult()
        assert result.relevant_pages == []
        assert result.relevant_nodes == []
        assert result.reasoning_trace == []
        assert result.confidence == 0.0
        assert result.total_tokens_used == 0

    def test_search_result_with_data(self) -> None:
        """Test SearchResult populated with search data."""
        node = TreeNode(
            title="Revenue",
            node_id="rev",
            start_page=5,
            end_page=10,
        )
        step = SearchStep(
            level=0,
            node_id="rev",
            node_title="Revenue",
            reasoning="Matches revenue query",
            selected=True,
            page_range="p.5-10",
        )
        result = SearchResult(
            relevant_pages=[5, 6, 7, 8, 9, 10],
            relevant_nodes=[node],
            reasoning_trace=[step],
            confidence=0.85,
            total_tokens_used=450,
        )
        assert len(result.relevant_pages) == 6
        assert result.confidence == 0.85

    def test_search_result_to_dict(self) -> None:
        """Test SearchResult serialization."""
        node = TreeNode(
            title="Costs",
            node_id="cost_1",
            start_page=20,
            end_page=25,
        )
        step = SearchStep(
            level=0,
            node_id="cost_1",
            node_title="Costs",
            reasoning="Cost analysis section",
            selected=True,
            page_range="p.20-25",
        )
        result = SearchResult(
            relevant_pages=[20, 21, 22, 23, 24, 25],
            relevant_nodes=[node],
            reasoning_trace=[step],
            confidence=0.72,
            total_tokens_used=300,
        )
        d = result.to_dict()

        assert d["relevant_pages"] == [20, 21, 22, 23, 24, 25]
        assert len(d["relevant_nodes"]) == 1
        assert d["relevant_nodes"][0]["node_id"] == "cost_1"
        assert len(d["reasoning_trace"]) == 1
        assert d["confidence"] == 0.72
        assert d["total_tokens_used"] == 300


# ──────────────────────────────────────────────────────────────
# TreeSearcher static helpers
# ──────────────────────────────────────────────────────────────


class TestTreeSearcherHelpers:
    """Tests for TreeSearcher static/class methods."""

    def test_collect_pages_single_node(self) -> None:
        """Test page collection from a single node."""
        node = TreeNode(
            title="Section",
            node_id="s1",
            start_page=5,
            end_page=8,
        )
        pages = TreeSearcher._collect_pages([node])
        assert pages == [5, 6, 7, 8]

    def test_collect_pages_multiple_nodes(self) -> None:
        """Test page collection from multiple nodes."""
        nodes = [
            TreeNode(title="A", node_id="a", start_page=1, end_page=3),
            TreeNode(title="B", node_id="b", start_page=10, end_page=12),
        ]
        pages = TreeSearcher._collect_pages(nodes)
        assert pages == [1, 2, 3, 10, 11, 12]

    def test_collect_pages_empty(self) -> None:
        """Test page collection with no nodes."""
        assert TreeSearcher._collect_pages([]) == []

    def test_calculate_confidence_empty(self) -> None:
        """Test confidence calculation with no trace/nodes."""
        assert TreeSearcher._calculate_confidence([], []) == 0.0

    def test_calculate_confidence_with_data(self) -> None:
        """Test confidence calculation produces reasonable score."""
        trace = [
            SearchStep(
                level=0,
                node_id="a",
                node_title="A",
                reasoning="relevant",
                selected=True,
            ),
            SearchStep(
                level=0,
                node_id="b",
                node_title="B",
                reasoning="not relevant",
                selected=False,
            ),
        ]
        nodes = [
            TreeNode(title="A", node_id="a", start_page=1, end_page=5),
        ]
        confidence = TreeSearcher._calculate_confidence(trace, nodes)
        assert 0.0 < confidence <= 1.0


# ──────────────────────────────────────────────────────────────
# TreeSearcher async search tests
# ──────────────────────────────────────────────────────────────


class TestTreeSearcherSearch:
    """Tests for TreeSearcher.search() with mocked LLM."""

    def _make_tree(self) -> DocumentTree:
        """Create a test DocumentTree."""
        return DocumentTree(
            doc_id="test-doc",
            filename="test.pdf",
            title="Test Document",
            description="A test document for unit testing",
            total_pages=30,
            root_nodes=[
                TreeNode(
                    title="Introduction",
                    node_id="intro",
                    start_page=1,
                    end_page=5,
                    summary="Introduction and executive summary",
                    level=0,
                ),
                TreeNode(
                    title="Financial Statements",
                    node_id="fin",
                    start_page=6,
                    end_page=20,
                    summary="Income statement, balance sheet, cash flow",
                    level=0,
                    children=[
                        TreeNode(
                            title="Income Statement",
                            node_id="fin_inc",
                            start_page=6,
                            end_page=12,
                            summary="Revenue, costs, and net income",
                            level=1,
                        ),
                        TreeNode(
                            title="Balance Sheet",
                            node_id="fin_bal",
                            start_page=13,
                            end_page=20,
                            summary="Assets, liabilities, equity",
                            level=1,
                        ),
                    ],
                ),
                TreeNode(
                    title="Appendix",
                    node_id="app",
                    start_page=21,
                    end_page=30,
                    summary="Notes and supplementary data",
                    level=0,
                ),
            ],
        )

    def _make_searcher(self) -> tuple[TreeSearcher, AsyncMock]:
        """Create a TreeSearcher with mocked LLM."""
        mock_llm = AsyncMock()
        with patch("src.pageindex.tree_searcher.settings") as mock_settings:
            mock_settings.tree_search_model = "llama-3.1-8b-instant"
            mock_settings.tree_search_breadth = 3
            mock_settings.max_tree_depth = 5
            searcher = TreeSearcher(llm=mock_llm)
        return searcher, mock_llm

    @pytest.mark.asyncio
    async def test_search_empty_tree_raises(self) -> None:
        """Test that searching an empty tree raises ValueError."""
        searcher, _ = self._make_searcher()
        empty_tree = DocumentTree(
            doc_id="empty",
            filename="empty.pdf",
            title="Empty",
            description="",
            total_pages=0,
            root_nodes=[],
        )
        with pytest.raises(ValueError, match="no root nodes"):
            await searcher.search("What is revenue?", empty_tree)

    @pytest.mark.asyncio
    async def test_search_selects_relevant_nodes(self) -> None:
        """Test that search identifies and returns relevant nodes."""
        searcher, mock_llm = self._make_searcher()
        tree = self._make_tree()

        # LLM response for root level evaluation: select Financial Statements
        root_response = json.dumps([
            {"node_id": "intro", "selected": False, "reasoning": "Intro not relevant for debt question", "confidence": 0.1},
            {"node_id": "fin", "selected": True, "reasoning": "Financial statements contain debt info", "confidence": 0.9},
            {"node_id": "app", "selected": False, "reasoning": "Appendix unlikely for main debt data", "confidence": 0.2},
        ])

        # LLM response for child level: select Balance Sheet
        child_response = json.dumps([
            {"node_id": "fin_inc", "selected": False, "reasoning": "Income statement less relevant for debt", "confidence": 0.3},
            {"node_id": "fin_bal", "selected": True, "reasoning": "Balance sheet contains debt/liabilities", "confidence": 0.95},
        ])

        mock_llm.agenerate = AsyncMock(side_effect=[root_response, child_response])

        result = await searcher.search("What is the total debt?", tree)

        assert len(result.relevant_pages) > 0
        assert len(result.relevant_nodes) > 0
        assert result.confidence > 0
        # Balance sheet pages (13-20) should be in relevant pages
        assert 13 in result.relevant_pages
        assert 20 in result.relevant_pages

    @pytest.mark.asyncio
    async def test_search_respects_max_depth(self) -> None:
        """Test that search stops at max_depth."""
        searcher, mock_llm = self._make_searcher()
        tree = self._make_tree()

        # Single level response — select Financial Statements node
        root_response = json.dumps([
            {"node_id": "intro", "selected": False, "reasoning": "Not relevant", "confidence": 0.1},
            {"node_id": "fin", "selected": True, "reasoning": "Relevant", "confidence": 0.9},
            {"node_id": "app", "selected": False, "reasoning": "Not relevant", "confidence": 0.1},
        ])

        mock_llm.agenerate = AsyncMock(return_value=root_response)

        # Limit to depth 1 — should not drill into children
        result = await searcher.search("What is revenue?", tree, max_depth=1)

        # With depth=1, it should evaluate root level only
        # Financial Statements has children, but at depth limit those children
        # become relevant nodes directly
        assert len(result.relevant_pages) > 0
        # Only 1 LLM call (root level evaluation)
        assert mock_llm.agenerate.call_count == 1

    @pytest.mark.asyncio
    async def test_search_reasoning_trace(self) -> None:
        """Test that search records a full reasoning trace."""
        searcher, mock_llm = self._make_searcher()
        tree = self._make_tree()

        # Select all root nodes as leaf (they don't have children except fin)
        root_response = json.dumps([
            {"node_id": "intro", "selected": True, "reasoning": "Might be relevant", "confidence": 0.6},
            {"node_id": "fin", "selected": False, "reasoning": "Not needed", "confidence": 0.2},
            {"node_id": "app", "selected": False, "reasoning": "Not needed", "confidence": 0.1},
        ])

        mock_llm.agenerate = AsyncMock(return_value=root_response)

        result = await searcher.search("Give me the executive summary", tree)

        # Should have reasoning trace entries
        assert len(result.reasoning_trace) >= 3  # One per root node
        # Check trace structure
        for step in result.reasoning_trace:
            assert hasattr(step, "level")
            assert hasattr(step, "node_id")
            assert hasattr(step, "reasoning")
            assert hasattr(step, "selected")

    @pytest.mark.asyncio
    async def test_search_llm_parse_failure_fallback(self) -> None:
        """Test that search handles LLM parse failures gracefully."""
        searcher, mock_llm = self._make_searcher()
        tree = self._make_tree()

        # Return garbage — parser should fallback to selecting by position
        mock_llm.agenerate = AsyncMock(return_value="This is not valid JSON at all!")

        result = await searcher.search("What is revenue?", tree)

        # Should still return a result (fallback selects nodes by position)
        assert isinstance(result, SearchResult)
        assert len(result.reasoning_trace) > 0
