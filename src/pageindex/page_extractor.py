"""
Page Extractor — Extract Content from Specific PDF Pages

After tree search identifies relevant page ranges, this module
extracts the actual text content from those specific pages using PyMuPDF.

Replaces chunked retrieval from traditional RAG:
    Retrieve chunks from vector DB  →  Extract exact pages from PDF

Design decisions:
    - Synchronous PyMuPDF operations (CPU-bound, not I/O-bound)
    - 1-indexed page numbers at API boundary, 0-indexed internally for PyMuPDF
    - PDF magic-byte validation for security (don't trust file extensions)
    - File-size guard against abuse (configurable via config.max_pdf_size_mb)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from ..core.config import settings
from ..observability.logging import get_logger

logger = get_logger(__name__)

# PDF magic bytes: every valid PDF starts with this
_PDF_MAGIC_BYTES = b"%PDF"


# ──────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PageContent:
    """
    Extracted content from a single PDF page.

    Attributes:
        page_number: 1-indexed page number (matches human-readable references).
        text: Extracted text content with layout preserved.
        tables: Markdown-formatted tables detected on the page.
        has_images: Whether the page contains embedded images.
        char_count: Character count of extracted text.
    """

    page_number: int
    text: str
    tables: list[str] = field(default_factory=list)
    has_images: bool = False
    char_count: int = 0


@dataclass(frozen=True)
class DocumentMetadataInfo:
    """
    Metadata extracted from a PDF document's structure.

    Attributes:
        title: Document title from PDF metadata (may be empty).
        author: Document author from PDF metadata (may be empty).
        page_count: Total number of pages.
        toc: Table of contents as list of [level, title, page_number].
        file_size_bytes: File size in bytes.
        has_toc: Whether the document has a table of contents.
    """

    title: str
    author: str
    page_count: int
    toc: list[list] = field(default_factory=list)
    file_size_bytes: int = 0
    has_toc: bool = False


@dataclass
class ExtractionResult:
    """
    Result from a page extraction operation.

    Attributes:
        doc_id: Document identifier for tracking.
        pages: List of extracted page contents.
        total_chars: Total character count across all pages.
        total_tokens_estimate: Approximate token count (~4 chars/token).
    """

    doc_id: str
    pages: list[PageContent] = field(default_factory=list)
    total_chars: int = 0
    total_tokens_estimate: int = 0


# ──────────────────────────────────────────────────────────────
# Core extractor
# ──────────────────────────────────────────────────────────────


class PageExtractor:
    """
    Extracts text content from specific pages of PDF documents.

    Uses PyMuPDF (fitz) for high-quality text extraction with support
    for tables and structured content. This class is intentionally
    synchronous: PDF parsing is CPU-bound, not I/O-bound, so async
    wrappers would add overhead without benefit.

    Works in tandem with TreeSearcher:
        TreeSearcher identifies pages  →  PageExtractor gets the content

    Security:
        - Validates PDF magic bytes (rejects non-PDF files)
        - Enforces file-size limit from config
        - Canonicalizes file paths to prevent traversal attacks

    Usage:
        extractor = PageExtractor()
        result = extractor.extract_pages("data/pdfs/report.pdf", [1, 5, 24])
        for page in result.pages:
            print(f"Page {page.page_number}: {page.text[:100]}...")
    """

    def __init__(self) -> None:
        """Initialize PageExtractor with configuration from settings."""
        self._max_file_size: int = settings.max_pdf_size_bytes
        self._max_pages: int = settings.max_pdf_pages
        logger.info(
            "page_extractor.initialized",
            max_file_size_mb=settings.max_pdf_size_mb,
            max_pages=self._max_pages,
        )

    # ─── Public API ─────────────────────────────────────────

    def extract_pages(
        self,
        pdf_path: str | Path,
        page_numbers: list[int],
        doc_id: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract text content from specific pages of a PDF.

        Args:
            pdf_path: Path to the PDF file (absolute or relative to project).
            page_numbers: List of 1-indexed page numbers to extract.
            doc_id: Optional document identifier for tracking.

        Returns:
            ExtractionResult with extracted page contents and statistics.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            ValueError: If page_numbers is empty or contains out-of-range values.
            PermissionError: If the file fails security validation.
        """
        resolved_path = self._validate_pdf_path(pdf_path)

        if not page_numbers:
            raise ValueError("page_numbers must be a non-empty list")

        doc_id = doc_id or resolved_path.stem

        logger.info(
            "page_extractor.extract_pages.start",
            pdf_path=str(resolved_path),
            doc_id=doc_id,
            requested_pages=page_numbers,
        )

        pages: list[PageContent] = []

        with fitz.open(str(resolved_path)) as pdf_doc:
            total_pages = len(pdf_doc)

            # Validate all page numbers before extracting any
            invalid_pages = [
                p for p in page_numbers if p < 1 or p > total_pages
            ]
            if invalid_pages:
                raise ValueError(
                    f"Page numbers out of range (1-{total_pages}): {invalid_pages}"
                )

            # Extract each requested page
            for page_num in sorted(set(page_numbers)):
                page_content = self._extract_single_page(
                    pdf_doc, page_num - 1  # Convert 1-indexed → 0-indexed
                )
                pages.append(page_content)

        total_chars = sum(p.char_count for p in pages)
        # Rough token estimate: ~4 characters per token for English text
        token_estimate = total_chars // 4

        result = ExtractionResult(
            doc_id=doc_id,
            pages=pages,
            total_chars=total_chars,
            total_tokens_estimate=token_estimate,
        )

        logger.info(
            "page_extractor.extract_pages.complete",
            doc_id=doc_id,
            pages_extracted=len(pages),
            total_chars=total_chars,
            token_estimate=token_estimate,
        )

        return result

    def extract_page_range(
        self,
        pdf_path: str | Path,
        start_page: int,
        end_page: int,
        doc_id: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract text from a contiguous range of pages.

        Args:
            pdf_path: Path to the PDF file.
            start_page: Starting page number (1-indexed, inclusive).
            end_page: Ending page number (1-indexed, inclusive).
            doc_id: Optional document identifier.

        Returns:
            ExtractionResult with extracted page contents.

        Raises:
            ValueError: If start_page > end_page or values out of range.
        """
        if start_page > end_page:
            raise ValueError(
                f"start_page ({start_page}) must be <= end_page ({end_page})"
            )

        page_numbers = list(range(start_page, end_page + 1))
        return self.extract_pages(pdf_path, page_numbers, doc_id)

    def get_document_metadata(self, pdf_path: str | Path) -> DocumentMetadataInfo:
        """
        Extract metadata from a PDF document without reading full content.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            DocumentMetadataInfo with title, author, page count, TOC, etc.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            PermissionError: If the file fails security validation.
        """
        resolved_path = self._validate_pdf_path(pdf_path)
        file_size = resolved_path.stat().st_size

        with fitz.open(str(resolved_path)) as pdf_doc:
            metadata = pdf_doc.metadata or {}
            toc = pdf_doc.get_toc()  # [[level, title, page], ...]

            result = DocumentMetadataInfo(
                title=metadata.get("title", "") or "",
                author=metadata.get("author", "") or "",
                page_count=len(pdf_doc),
                toc=toc,
                file_size_bytes=file_size,
                has_toc=len(toc) > 0,
            )

        logger.info(
            "page_extractor.metadata_extracted",
            pdf_path=str(resolved_path),
            page_count=result.page_count,
            has_toc=result.has_toc,
            toc_entries=len(result.toc),
            file_size_bytes=file_size,
        )

        return result

    def get_page_count(self, pdf_path: str | Path) -> int:
        """
        Get the total number of pages in a PDF.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Total page count.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
        """
        resolved_path = self._validate_pdf_path(pdf_path)

        with fitz.open(str(resolved_path)) as pdf_doc:
            return len(pdf_doc)

    # ─── Private helpers ────────────────────────────────────

    def _extract_single_page(
        self, pdf_doc: fitz.Document, page_idx: int
    ) -> PageContent:
        """
        Extract content from a single page.

        Args:
            pdf_doc: Open PyMuPDF document object.
            page_idx: 0-indexed page number (internal PyMuPDF convention).

        Returns:
            PageContent with extracted text, tables, and metadata.
        """
        page: fitz.Page = pdf_doc[page_idx]

        # Extract text with layout preservation
        # "text" mode gives clean plaintext; "blocks" mode preserves structure
        text = page.get_text("text")

        # Detect tables using PyMuPDF's built-in table finder
        tables: list[str] = []
        try:
            found_tables = page.find_tables()
            if found_tables and found_tables.tables:
                for table in found_tables.tables:
                    # Convert table to markdown format for LLM consumption
                    markdown_table = self._table_to_markdown(table)
                    if markdown_table:
                        tables.append(markdown_table)
        except Exception as exc:
            # Table detection can fail on complex layouts — log and continue
            logger.warning(
                "page_extractor.table_detection_failed",
                page_number=page_idx + 1,
                error=str(exc),
            )

        # Check for embedded images
        has_images = len(page.get_images(full=True)) > 0

        return PageContent(
            page_number=page_idx + 1,  # Convert back to 1-indexed
            text=text.strip(),
            tables=tables,
            has_images=has_images,
            char_count=len(text.strip()),
        )

    def _validate_pdf_path(self, pdf_path: str | Path) -> Path:
        """
        Validate and resolve a PDF file path with security checks.

        Security checks performed:
            1. Path canonicalization (prevents directory traversal)
            2. File existence check
            3. PDF magic-byte validation (rejects non-PDF files)
            4. File-size limit enforcement

        Args:
            pdf_path: Raw file path from caller.

        Returns:
            Resolved, validated Path object.

        Raises:
            FileNotFoundError: If the file does not exist.
            PermissionError: If the file fails security validation.
            ValueError: If the file is not a valid PDF or exceeds size limits.
        """
        path = Path(pdf_path).resolve()

        # 1. Existence check
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")

        # 2. File-size guard
        file_size = path.stat().st_size
        if file_size > self._max_file_size:
            raise ValueError(
                f"PDF file exceeds maximum size "
                f"({file_size / (1024 * 1024):.1f}MB > {settings.max_pdf_size_mb}MB): "
                f"{path.name}"
            )

        if file_size == 0:
            raise ValueError(f"PDF file is empty (0 bytes): {path.name}")

        # 3. PDF magic-byte validation — don't trust file extensions
        with open(path, "rb") as f:
            header = f.read(4)
            if header != _PDF_MAGIC_BYTES:
                raise PermissionError(
                    f"File is not a valid PDF (bad magic bytes): {path.name}. "
                    f"Expected %PDF header."
                )

        logger.debug(
            "page_extractor.path_validated",
            path=str(path),
            file_size_mb=round(file_size / (1024 * 1024), 2),
        )

        return path

    @staticmethod
    def _table_to_markdown(table: fitz.table.Table) -> str:
        """
        Convert a PyMuPDF Table object to Markdown format.

        Args:
            table: PyMuPDF table object from page.find_tables().

        Returns:
            Markdown-formatted table string, or empty string if conversion fails.
        """
        try:
            df = table.to_pandas()
            if df.empty:
                return ""

            # Build markdown table manually for zero-dependency approach
            headers = list(df.columns)
            rows = df.values.tolist()

            # Header row
            header_line = "| " + " | ".join(str(h) for h in headers) + " |"
            separator = "| " + " | ".join("---" for _ in headers) + " |"

            # Data rows
            data_lines = []
            for row in rows:
                cells = [str(cell) if cell is not None else "" for cell in row]
                data_lines.append("| " + " | ".join(cells) + " |")

            return "\n".join([header_line, separator] + data_lines)

        except Exception:
            # Graceful fallback: return empty string if table conversion fails
            return ""
