"""
Tests for PageIndex Page Extractor

Tests page-level content extraction:
- PageContent dataclass creation and immutability
- ExtractionResult defaults and population
- File-not-found and empty page list error handling
- Successful page extraction with mocked PyMuPDF
- Page range extraction
- Page count retrieval
- Invalid/reversed page range handling
"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from dataclasses import FrozenInstanceError

from src.pageindex.page_extractor import (
    PageExtractor,
    PageContent,
    ExtractionResult,
    DocumentMetadataInfo,
)


# ──────────────────────────────────────────────────────────────
# PageContent dataclass tests
# ──────────────────────────────────────────────────────────────


class TestPageContent:
    """Tests for PageContent dataclass."""

    def test_page_content_creation(self) -> None:
        """Test PageContent initialization with all fields."""
        pc = PageContent(
            page_number=5,
            text="Revenue for Q3 was $2.1 billion.",
            tables=["| Metric | Value |\n| --- | --- |\n| Revenue | 2.1B |"],
            has_images=True,
            char_count=33,
        )
        assert pc.page_number == 5
        assert "Revenue" in pc.text
        assert len(pc.tables) == 1
        assert pc.has_images is True
        assert pc.char_count == 33

    def test_page_content_defaults(self) -> None:
        """Test PageContent default values."""
        pc = PageContent(page_number=1, text="hello")
        assert pc.tables == []
        assert pc.has_images is False
        assert pc.char_count == 0

    def test_page_content_is_frozen(self) -> None:
        """Test that PageContent is immutable (frozen dataclass)."""
        pc = PageContent(page_number=1, text="test")
        with pytest.raises(FrozenInstanceError):
            pc.page_number = 2  # type: ignore


# ──────────────────────────────────────────────────────────────
# ExtractionResult tests
# ──────────────────────────────────────────────────────────────


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_extraction_result_defaults(self) -> None:
        """Test ExtractionResult default values."""
        result = ExtractionResult(doc_id="test-doc")
        assert result.doc_id == "test-doc"
        assert result.pages == []
        assert result.total_chars == 0
        assert result.total_tokens_estimate == 0

    def test_extraction_result_with_pages(self) -> None:
        """Test ExtractionResult populated with pages."""
        pages = [
            PageContent(page_number=1, text="Page 1 text", char_count=11),
            PageContent(page_number=2, text="Page 2 text", char_count=11),
        ]
        result = ExtractionResult(
            doc_id="doc-1",
            pages=pages,
            total_chars=22,
            total_tokens_estimate=5,
        )
        assert len(result.pages) == 2
        assert result.total_chars == 22


# ──────────────────────────────────────────────────────────────
# PageExtractor tests
# ──────────────────────────────────────────────────────────────


class TestPageExtractor:
    """Tests for PageExtractor class."""

    @pytest.fixture
    def extractor(self) -> PageExtractor:
        """Create a PageExtractor with mocked settings."""
        with patch("src.pageindex.page_extractor.settings") as mock_settings:
            mock_settings.max_pdf_size_bytes = 100 * 1024 * 1024
            mock_settings.max_pdf_size_mb = 100
            mock_settings.max_pdf_pages = 1000
            return PageExtractor()

    def test_extract_pages_file_not_found(self, extractor: PageExtractor) -> None:
        """Test that extract_pages raises FileNotFoundError for missing PDF."""
        with pytest.raises(FileNotFoundError, match="PDF file not found"):
            extractor.extract_pages("/nonexistent/path/to/doc.pdf", [1])

    def test_extract_pages_empty_page_list(self, extractor: PageExtractor) -> None:
        """Test that extract_pages raises ValueError for empty page list."""
        with patch.object(extractor, "_validate_pdf_path", return_value=Path("/fake/doc.pdf")):
            with pytest.raises(ValueError, match="page_numbers must be a non-empty list"):
                extractor.extract_pages("/fake/doc.pdf", [])

    @patch("src.pageindex.page_extractor.fitz")
    def test_extract_pages_success(
        self, mock_fitz: MagicMock, extractor: PageExtractor
    ) -> None:
        """Test successful page extraction with mocked PyMuPDF."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Sample financial text on page 1."
        mock_page.find_tables.return_value = MagicMock(tables=[])
        mock_page.get_images.return_value = []

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=10)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_fitz.open.return_value = mock_doc

        with patch.object(extractor, "_validate_pdf_path", return_value=Path("/fake/doc.pdf")):
            result = extractor.extract_pages("/fake/doc.pdf", [1, 3])

        assert result.doc_id == "doc"
        assert len(result.pages) == 2
        assert result.pages[0].text == "Sample financial text on page 1."
        assert result.total_chars > 0

    @patch("src.pageindex.page_extractor.fitz")
    def test_extract_page_range(
        self, mock_fitz: MagicMock, extractor: PageExtractor
    ) -> None:
        """Test page range extraction generates correct page numbers."""
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Text"
        mock_page.find_tables.return_value = MagicMock(tables=[])
        mock_page.get_images.return_value = []

        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=20)
        mock_doc.__getitem__ = MagicMock(return_value=mock_page)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_fitz.open.return_value = mock_doc

        with patch.object(extractor, "_validate_pdf_path", return_value=Path("/fake/doc.pdf")):
            result = extractor.extract_page_range("/fake/doc.pdf", 5, 8)

        assert len(result.pages) == 4
        page_nums = [p.page_number for p in result.pages]
        assert page_nums == [5, 6, 7, 8]

    @patch("src.pageindex.page_extractor.fitz")
    def test_get_pdf_page_count(
        self, mock_fitz: MagicMock, extractor: PageExtractor
    ) -> None:
        """Test getting total page count."""
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=42)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_fitz.open.return_value = mock_doc

        with patch.object(extractor, "_validate_pdf_path", return_value=Path("/fake/doc.pdf")):
            count = extractor.get_page_count("/fake/doc.pdf")

        assert count == 42

    @patch("src.pageindex.page_extractor.fitz")
    def test_extract_pages_invalid_range(
        self, mock_fitz: MagicMock, extractor: PageExtractor
    ) -> None:
        """Test error handling for out-of-range page numbers."""
        mock_doc = MagicMock()
        mock_doc.__len__ = MagicMock(return_value=5)
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock_fitz.open.return_value = mock_doc

        with patch.object(extractor, "_validate_pdf_path", return_value=Path("/fake/doc.pdf")):
            with pytest.raises(ValueError, match="Page numbers out of range"):
                extractor.extract_pages("/fake/doc.pdf", [1, 10])

    def test_extract_page_range_reversed(self, extractor: PageExtractor) -> None:
        """Test that start_page > end_page raises ValueError."""
        with pytest.raises(ValueError, match="start_page.*must be <= end_page"):
            extractor.extract_page_range("/any.pdf", 10, 5)
