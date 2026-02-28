"""
Tests for PageIndex Tree Generator

Tests tree data structures and serialization:
- TreeNode creation, to_dict, from_dict, nested children
- DocumentTree creation, to_dict, from_dict
- Round-trip serialization (dict → object → dict)
- Missing/optional field handling in from_dict
- TreeGenerator initialisation
"""

import pytest
from src.pageindex.tree_generator import TreeNode, DocumentTree


# ──────────────────────────────────────────────────────────────
# TreeNode tests
# ──────────────────────────────────────────────────────────────


class TestTreeNode:
    """Tests for TreeNode dataclass and serialization."""

    def test_tree_node_creation(self) -> None:
        """Test TreeNode with all fields."""
        node = TreeNode(
            title="Financial Statements",
            node_id="sec_1",
            start_page=10,
            end_page=30,
            summary="Covers income, balance sheet, and cash flow.",
            level=1,
        )
        assert node.title == "Financial Statements"
        assert node.node_id == "sec_1"
        assert node.start_page == 10
        assert node.end_page == 30
        assert node.level == 1
        assert node.children == []

    def test_tree_node_defaults(self) -> None:
        """Test TreeNode default values for optional fields."""
        node = TreeNode(
            title="Intro",
            node_id="n0",
            start_page=1,
            end_page=2,
        )
        assert node.summary == ""
        assert node.children == []
        assert node.level == 0

    def test_tree_node_to_dict(self) -> None:
        """Test serialization of TreeNode to dictionary."""
        child = TreeNode(
            title="Balance Sheet",
            node_id="sec_1_1",
            start_page=15,
            end_page=20,
            summary="Balance sheet section",
            level=2,
        )
        parent = TreeNode(
            title="Financial Statements",
            node_id="sec_1",
            start_page=10,
            end_page=30,
            summary="All financial statements",
            level=1,
            children=[child],
        )
        d = parent.to_dict()

        assert d["title"] == "Financial Statements"
        assert d["node_id"] == "sec_1"
        assert d["start_page"] == 10
        assert d["end_page"] == 30
        assert d["summary"] == "All financial statements"
        assert d["level"] == 1
        assert len(d["children"]) == 1
        assert d["children"][0]["title"] == "Balance Sheet"
        assert d["children"][0]["level"] == 2

    def test_tree_node_from_dict(self) -> None:
        """Test deserialization of TreeNode from dictionary."""
        data = {
            "title": "Revenue Analysis",
            "node_id": "rev_1",
            "start_page": 5,
            "end_page": 12,
            "summary": "Detailed revenue breakdown",
            "level": 1,
            "children": [
                {
                    "title": "Product Revenue",
                    "node_id": "rev_1_1",
                    "start_page": 5,
                    "end_page": 8,
                    "summary": "Revenue by product line",
                    "level": 2,
                    "children": [],
                }
            ],
        }
        node = TreeNode.from_dict(data)

        assert node.title == "Revenue Analysis"
        assert node.node_id == "rev_1"
        assert len(node.children) == 1
        assert node.children[0].title == "Product Revenue"
        assert node.children[0].level == 2

    def test_tree_node_from_dict_optional_fields(self) -> None:
        """Test from_dict with missing optional fields."""
        data = {
            "title": "Minimal",
            "node_id": "min_1",
            "start_page": 1,
            "end_page": 3,
        }
        node = TreeNode.from_dict(data)

        assert node.summary == ""
        assert node.level == 0
        assert node.children == []

    def test_tree_node_roundtrip(self) -> None:
        """Test dict → object → dict round-trip preserves data."""
        original = TreeNode(
            title="Section A",
            node_id="a1",
            start_page=1,
            end_page=10,
            summary="Section A content",
            level=0,
            children=[
                TreeNode(
                    title="Subsection A.1",
                    node_id="a1_1",
                    start_page=1,
                    end_page=5,
                    summary="Subsection A.1 detail",
                    level=1,
                ),
                TreeNode(
                    title="Subsection A.2",
                    node_id="a1_2",
                    start_page=6,
                    end_page=10,
                    summary="Subsection A.2 detail",
                    level=1,
                ),
            ],
        )
        roundtripped = TreeNode.from_dict(original.to_dict())
        assert roundtripped.to_dict() == original.to_dict()

    def test_tree_node_from_dict_missing_required_fields(self) -> None:
        """Test that from_dict raises KeyError for missing required fields."""
        data = {"title": "Incomplete"}  # Missing node_id, start_page, end_page
        with pytest.raises(KeyError):
            TreeNode.from_dict(data)


# ──────────────────────────────────────────────────────────────
# DocumentTree tests
# ──────────────────────────────────────────────────────────────


class TestDocumentTree:
    """Tests for DocumentTree dataclass and serialization."""

    def test_document_tree_creation(self) -> None:
        """Test DocumentTree with all fields."""
        root = TreeNode(
            title="Executive Summary",
            node_id="root_1",
            start_page=1,
            end_page=5,
            summary="Overview of the annual report",
            level=0,
        )
        tree = DocumentTree(
            doc_id="ferrari-2024",
            filename="Ferrari_Annual_Report_2024.pdf",
            title="Ferrari N.V. Annual Report 2024",
            description="Full annual report for FY2024",
            total_pages=120,
            root_nodes=[root],
            metadata={"year": 2024, "company": "Ferrari N.V."},
        )
        assert tree.doc_id == "ferrari-2024"
        assert tree.total_pages == 120
        assert len(tree.root_nodes) == 1
        assert tree.metadata["company"] == "Ferrari N.V."

    def test_document_tree_defaults(self) -> None:
        """Test DocumentTree default values."""
        tree = DocumentTree(
            doc_id="test",
            filename="test.pdf",
            title="Test",
            description="",
            total_pages=1,
        )
        assert tree.root_nodes == []
        assert tree.metadata == {}

    def test_document_tree_to_dict(self) -> None:
        """Test DocumentTree serialization."""
        tree = DocumentTree(
            doc_id="doc-abc",
            filename="report.pdf",
            title="Quarterly Report",
            description="Q3 financial results",
            total_pages=50,
            root_nodes=[
                TreeNode(
                    title="Financials",
                    node_id="sec_fin",
                    start_page=1,
                    end_page=25,
                    level=0,
                ),
                TreeNode(
                    title="Appendix",
                    node_id="sec_app",
                    start_page=26,
                    end_page=50,
                    level=0,
                ),
            ],
            metadata={"quarter": "Q3"},
        )
        d = tree.to_dict()

        assert d["doc_id"] == "doc-abc"
        assert d["total_pages"] == 50
        assert len(d["root_nodes"]) == 2
        assert d["root_nodes"][0]["title"] == "Financials"
        assert d["metadata"]["quarter"] == "Q3"

    def test_document_tree_from_dict(self) -> None:
        """Test DocumentTree deserialization."""
        data = {
            "doc_id": "pwc-report",
            "filename": "pwc-global.pdf",
            "title": "PwC Global Annual Review",
            "description": "Annual review of PwC operations",
            "total_pages": 80,
            "root_nodes": [
                {
                    "title": "Overview",
                    "node_id": "ov_1",
                    "start_page": 1,
                    "end_page": 15,
                    "summary": "Company overview",
                    "level": 0,
                    "children": [],
                }
            ],
            "metadata": {"year": 2024},
        }
        tree = DocumentTree.from_dict(data)

        assert tree.doc_id == "pwc-report"
        assert tree.title == "PwC Global Annual Review"
        assert len(tree.root_nodes) == 1
        assert tree.root_nodes[0].title == "Overview"
        assert tree.metadata["year"] == 2024

    def test_document_tree_roundtrip(self) -> None:
        """Test dict → DocumentTree → dict round-trip."""
        tree = DocumentTree(
            doc_id="rt-test",
            filename="roundtrip.pdf",
            title="Round Trip Test",
            description="Testing round-trip serialization",
            total_pages=10,
            root_nodes=[
                TreeNode(
                    title="Chapter 1",
                    node_id="ch1",
                    start_page=1,
                    end_page=5,
                    summary="First chapter",
                    level=0,
                    children=[
                        TreeNode(
                            title="Section 1.1",
                            node_id="ch1_s1",
                            start_page=1,
                            end_page=3,
                            summary="First section of chapter 1",
                            level=1,
                        ),
                    ],
                ),
            ],
            metadata={"tag": "test"},
        )
        roundtripped = DocumentTree.from_dict(tree.to_dict())
        assert roundtripped.to_dict() == tree.to_dict()

    def test_document_tree_from_dict_missing_optional(self) -> None:
        """Test from_dict with missing optional fields."""
        data = {
            "doc_id": "min-doc",
            "filename": "minimal.pdf",
            "title": "Minimal",
            "total_pages": 5,
        }
        tree = DocumentTree.from_dict(data)
        assert tree.description == ""
        assert tree.root_nodes == []
        assert tree.metadata == {}
