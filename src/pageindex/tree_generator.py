"""
Tree Generator — Hierarchical Tree Index from PDF Documents

Transforms lengthy PDF documents into a semantic tree structure (like an
intelligent Table of Contents) optimized for LLM reasoning-based retrieval.

This is the INGESTION component of the PageIndex pipeline:
    PDF → Parse Structure → Generate Hierarchical Tree → Store Tree JSON

Uses Groq's OpenAI-compatible API with configurable model.

Design decisions:
    - Async throughout (agenerate for LLM calls)
    - Accepts GroqClient and TelemetryService via dependency injection
    - Page text extraction is synchronous (CPU-bound PyMuPDF), wrapped in
      asyncio.to_thread for non-blocking execution
    - Tree generation uses structured JSON prompts for reliable parsing
    - Node summaries generated in parallel batches for speed
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import fitz  # PyMuPDF

from ..core.config import settings
from ..observability.logging import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from ..llm.groq_client import GroqClient
    from ..observability.telemetry import TelemetryService


# ──────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────


@dataclass
class TreeNode:
    """
    A single node in the PageIndex tree structure.

    Each node represents a section/subsection of the document
    with metadata for traceability.

    Attributes:
        title: Section/subsection title.
        node_id: Unique identifier for the node.
        start_page: Starting page number (1-indexed).
        end_page: Ending page number (1-indexed).
        summary: LLM-generated summary of the section content.
        children: Child nodes (sub-sections).
        level: Depth level in the tree (0 = root).
    """

    title: str
    node_id: str
    start_page: int
    end_page: int
    summary: str = ""
    children: list[TreeNode] = field(default_factory=list)
    level: int = 0

    def to_dict(self) -> dict:
        """
        Convert tree node to dictionary for JSON serialization.

        Returns:
            Dictionary representation including recursively serialized children.
        """
        return {
            "title": self.title,
            "node_id": self.node_id,
            "start_page": self.start_page,
            "end_page": self.end_page,
            "summary": self.summary,
            "level": self.level,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict) -> TreeNode:
        """
        Create a TreeNode from a dictionary.

        Args:
            data: Dictionary with tree node fields.

        Returns:
            Reconstructed TreeNode with all children.

        Raises:
            KeyError: If required fields are missing.
        """
        children = [
            cls.from_dict(child_data)
            for child_data in data.get("children", [])
        ]
        return cls(
            title=data["title"],
            node_id=data["node_id"],
            start_page=data["start_page"],
            end_page=data["end_page"],
            summary=data.get("summary", ""),
            level=data.get("level", 0),
            children=children,
        )


@dataclass
class DocumentTree:
    """
    Complete tree index for a single document.

    Attributes:
        doc_id: Unique document identifier.
        filename: Original PDF filename.
        title: Document title.
        description: LLM-generated document description.
        total_pages: Total number of pages in the PDF.
        root_nodes: Top-level tree nodes.
        metadata: Additional document metadata.
    """

    doc_id: str
    filename: str
    title: str
    description: str
    total_pages: int
    root_nodes: list[TreeNode] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """
        Convert document tree to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the full document tree.
        """
        return {
            "doc_id": self.doc_id,
            "filename": self.filename,
            "title": self.title,
            "description": self.description,
            "total_pages": self.total_pages,
            "root_nodes": [node.to_dict() for node in self.root_nodes],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> DocumentTree:
        """
        Create a DocumentTree from a dictionary.

        Args:
            data: Dictionary with document tree fields.

        Returns:
            Reconstructed DocumentTree with full node hierarchy.

        Raises:
            KeyError: If required fields are missing.
        """
        root_nodes = [
            TreeNode.from_dict(node_data)
            for node_data in data.get("root_nodes", [])
        ]
        return cls(
            doc_id=data["doc_id"],
            filename=data["filename"],
            title=data["title"],
            description=data.get("description", ""),
            total_pages=data["total_pages"],
            root_nodes=root_nodes,
            metadata=data.get("metadata", {}),
        )


# ──────────────────────────────────────────────────────────────
# Prompts
# ──────────────────────────────────────────────────────────────

_TREE_GENERATION_PROMPT = """You are analyzing a PDF document to generate a hierarchical tree index.
The document has {total_pages} pages. Below is a sample of the document content.

{content_sample}

{toc_section}

Generate a hierarchical tree index as JSON. The tree should:
1. Have sections and subsections that capture the document's logical structure
2. Each node must specify accurate start_page and end_page (1-indexed)
3. Page ranges must not overlap between sibling nodes
4. Page ranges must cover all {total_pages} pages collectively
5. Leaf nodes should cover no more than {max_pages_per_node} pages each
6. Include a brief summary for each node (1-2 sentences)

Output ONLY a valid JSON object in this exact format:
{{
    "title": "Document title",
    "description": "Brief description of the entire document",
    "sections": [
        {{
            "title": "Section name",
            "start_page": 1,
            "end_page": 10,
            "summary": "What this section covers",
            "subsections": [
                {{
                    "title": "Subsection name",
                    "start_page": 1,
                    "end_page": 5,
                    "summary": "What this subsection covers",
                    "subsections": []
                }}
            ]
        }}
    ]
}}"""

_SUMMARY_PROMPT = """Summarize the following document section in 1-2 concise sentences.
Focus on the key topics, data points, or arguments presented.

Section: {title} (Pages {start_page}-{end_page})

Content:
{content}

Summary:"""


# ──────────────────────────────────────────────────────────────
# Core Generator
# ──────────────────────────────────────────────────────────────


class TreeGenerator:
    """
    Generates hierarchical tree indexes from PDF documents.

    Uses the PageIndex approach:
    1. Extract text and structure from PDF (via PyMuPDF)
    2. Detect/use existing Table of Contents if available
    3. Use LLM to generate section summaries and hierarchy
    4. Build the tree index with page-level references

    Configuration:
        - model: LLM model for tree generation (from settings.tree_gen_model)
        - max_pages_per_node: Maximum pages per leaf node (from settings)

    Args:
        llm: GroqClient for LLM calls. Injected via InjectedState.
        telemetry: TelemetryService for logging. Injected via InjectedState.
        query_id: Telemetry query ID for tracking this operation.
    """

    def __init__(
        self,
        llm: GroqClient,
        telemetry: Optional[TelemetryService] = None,
        query_id: Optional[str] = None,
    ) -> None:
        """
        Initialize TreeGenerator with injected dependencies.

        Args:
            llm: GroqClient for LLM generation.
            telemetry: TelemetryService for observability.
            query_id: Current operation's telemetry tracking ID.
        """
        self._llm = llm
        self._telemetry = telemetry
        self._query_id = query_id
        self._model: str = settings.tree_gen_model
        self._max_pages_per_node: int = settings.max_pages_per_node
        self._max_tree_depth: int = settings.max_tree_depth

        logger.info(
            "tree_generator.initialized",
            model=self._model,
            max_pages_per_node=self._max_pages_per_node,
            max_tree_depth=self._max_tree_depth,
        )

    async def generate_tree(self, pdf_path: str) -> DocumentTree:
        """
        Generate a hierarchical tree index from a PDF document.

        Full async pipeline:
            1. Extract page texts from PDF (in thread pool)
            2. Detect existing Table of Contents
            3. Build tree structure with LLM
            4. Generate node summaries
            5. Return complete DocumentTree

        Args:
            pdf_path: Absolute path to the PDF file.

        Returns:
            DocumentTree with hierarchical structure and page references.

        Raises:
            FileNotFoundError: If the PDF file does not exist.
            ValueError: If the PDF is empty or unreadable.
            RuntimeError: If LLM fails to generate a valid tree.
        """
        import time

        start_time = time.time()
        resolved_path = Path(pdf_path).resolve()

        if not resolved_path.exists():
            raise FileNotFoundError(f"PDF file not found: {resolved_path}")

        # Generate stable doc_id from filename
        doc_id = self._generate_doc_id(resolved_path.name)
        filename = resolved_path.name

        logger.info(
            "tree_generator.generate_tree.start",
            pdf_path=str(resolved_path),
            doc_id=doc_id,
        )

        try:
            # Step 1: Extract text from PDF (CPU-bound → thread pool)
            pdf_structure = await asyncio.to_thread(
                self._extract_pdf_structure_sync, str(resolved_path)
            )

            page_texts: list[str] = pdf_structure["page_texts"]
            total_pages: int = pdf_structure["total_pages"]
            pdf_title: str = pdf_structure.get("title", "")
            total_chars = sum(len(t) for t in page_texts)
            pages_with_text = sum(1 for t in page_texts if t.strip())

            logger.info(
                "tree_generator.pdf_extracted",
                doc_id=doc_id,
                total_pages=total_pages,
                total_chars=total_chars,
                pages_with_text=pages_with_text,
            )

            # ── Zero-text guard: detect image-only or corrupted PDFs ──
            if total_chars == 0:
                logger.warning(
                    "tree_generator.zero_text_extraction",
                    doc_id=doc_id,
                    total_pages=total_pages,
                    reason="No text extracted from any page. PDF may be image-only or have corrupted streams.",
                )
            elif pages_with_text < total_pages * 0.1:
                logger.warning(
                    "tree_generator.low_text_extraction",
                    doc_id=doc_id,
                    total_pages=total_pages,
                    pages_with_text=pages_with_text,
                    reason="Very few pages produced text. PDF may be mostly images.",
                )

            # Step 2: Detect existing TOC
            toc = pdf_structure.get("toc", [])

            # Step 3: Build tree with LLM
            tree_data = await self._build_tree_with_llm(
                page_texts=page_texts,
                total_pages=total_pages,
                toc=toc if toc else None,
            )

            # Step 4: Parse LLM response into TreeNode objects
            root_nodes = self._parse_tree_response(tree_data, total_pages)

            # Step 5: Generate detailed summaries for nodes
            await self._generate_node_summaries(root_nodes, page_texts)

            # Build final DocumentTree
            doc_title = tree_data.get("title", pdf_title) or filename
            description = tree_data.get("description", "")

            tree = DocumentTree(
                doc_id=doc_id,
                filename=filename,
                title=doc_title,
                description=description,
                total_pages=total_pages,
                root_nodes=root_nodes,
                metadata={
                    "has_toc": len(toc) > 0,
                    "toc_entries": len(toc),
                    "generation_model": self._model,
                    "text_extraction_chars": total_chars,
                    "pages_with_text": pages_with_text,
                    "is_image_only": total_chars == 0,
                },
            )

            elapsed_ms = (time.time() - start_time) * 1000

            logger.info(
                "tree_generator.generate_tree.complete",
                doc_id=doc_id,
                total_pages=total_pages,
                node_count=self._count_nodes(root_nodes),
                tree_depth=self._calculate_depth(root_nodes),
                elapsed_ms=round(elapsed_ms, 1),
            )

            return tree

        except Exception as exc:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(
                "tree_generator.generate_tree.failed",
                doc_id=doc_id,
                error=str(exc),
                elapsed_ms=round(elapsed_ms, 1),
            )

            if self._telemetry:
                await self._telemetry.log_error(
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    query_id=self._query_id,
                    node_name="tree_generator",
                    exception=exc,
                    recovery_action="abort",
                )

            raise

    # ─── PDF Extraction (synchronous, run in thread) ───

    def _extract_pdf_structure_sync(self, pdf_path: str) -> dict:
        """
        Extract raw text and structural elements from a PDF.

        This is intentionally synchronous — PyMuPDF is CPU-bound.
        Called via asyncio.to_thread() from the async pipeline.

        Now also extracts tables and appends them as markdown to each
        page's text, so the LLM sees table data when building the tree.

        MuPDF stderr warnings (e.g., zlib decompression errors for
        image-heavy PDFs) are suppressed to reduce log noise.

        Args:
            pdf_path: Absolute path to the PDF file.

        Returns:
            Dict with page_texts, total_pages, title, toc.
        """
        import sys
        import os

        page_texts: list[str] = []
        toc: list[list] = []
        title: str = ""

        # Suppress MuPDF's noisy stderr output (zlib errors for image-heavy PDFs)
        # These are non-fatal warnings from MuPDF's C library that clutter logs
        old_stderr = sys.stderr
        try:
            devnull = open(os.devnull, "w")
            sys.stderr = devnull
        except Exception:
            devnull = None

        try:
            with fitz.open(pdf_path) as pdf_doc:
                total_pages = len(pdf_doc)

                # Extract metadata
                metadata = pdf_doc.metadata or {}
                title = metadata.get("title", "") or ""

                # Extract TOC (bookmarks)
                toc = pdf_doc.get_toc()

                # Extract text + tables per page
                for page_idx in range(total_pages):
                    page = pdf_doc[page_idx]
                    text = page.get_text("text").strip()

                    # Extract tables and append as markdown
                    try:
                        found_tables = page.find_tables()
                        if found_tables and found_tables.tables:
                            table_markdowns = []
                            for table in found_tables.tables:
                                md = self._table_to_markdown_safe(table)
                                if md:
                                    table_markdowns.append(md)
                            if table_markdowns:
                                tables_section = (
                                    "\n\n[TABLES ON THIS PAGE]\n"
                                    + "\n\n".join(table_markdowns)
                                )
                                text = text + tables_section
                    except Exception:
                        # Table extraction failure is non-fatal
                        pass

                    page_texts.append(text)
        finally:
            # Restore stderr
            sys.stderr = old_stderr
            if devnull is not None:
                try:
                    devnull.close()
                except Exception:
                    pass

        return {
            "page_texts": page_texts,
            "total_pages": total_pages,
            "title": title,
            "toc": toc,
        }

    @staticmethod
    def _table_to_markdown_safe(table) -> str:
        """Convert a PyMuPDF table to markdown, safely handling errors."""
        try:
            df = table.to_pandas()
            if df.empty:
                return ""
            headers = list(df.columns)
            rows = df.values.tolist()
            header_line = "| " + " | ".join(str(h) for h in headers) + " |"
            separator = "| " + " | ".join("---" for _ in headers) + " |"
            data_lines = []
            for row in rows:
                cells = [str(cell) if cell is not None else "" for cell in row]
                data_lines.append("| " + " | ".join(cells) + " |")
            return "\n".join([header_line, separator] + data_lines)
        except Exception:
            return ""

    # ─── LLM Tree Building ─────────────────────────────

    async def _build_tree_with_llm(
        self,
        page_texts: list[str],
        total_pages: int,
        toc: Optional[list[list]] = None,
    ) -> dict:
        """
        Use LLM reasoning to build hierarchical tree from document content.

        Sends a structured prompt with:
        - Sample content from key pages (first, middle, last)
        - Existing TOC if available
        - Instructions for JSON tree output

        Args:
            page_texts: List of text content per page.
            total_pages: Total number of pages.
            toc: Existing TOC entries if detected, None otherwise.

        Returns:
            Parsed dict with title, description, and sections.

        Raises:
            RuntimeError: If LLM returns invalid JSON.
        """
        import time

        # Build content sample — first pages, middle pages, last pages
        content_sample = self._build_content_sample(page_texts, total_pages)

        # Build TOC section
        toc_section = ""
        if toc:
            toc_lines = []
            for entry in toc[:30]:  # Limit TOC entries
                level, toc_title, page_num = entry[0], entry[1], entry[2]
                indent = "  " * (level - 1)
                toc_lines.append(f"{indent}- {toc_title} (p.{page_num})")
            toc_section = (
                "The document has an existing Table of Contents:\n"
                + "\n".join(toc_lines)
                + "\n\nUse this TOC as the basis for your tree structure."
            )
        else:
            toc_section = (
                "No Table of Contents was found. Analyze the content "
                "to identify logical sections."
            )

        prompt = _TREE_GENERATION_PROMPT.format(
            total_pages=total_pages,
            content_sample=content_sample,
            toc_section=toc_section,
            max_pages_per_node=self._max_pages_per_node,
        )

        start_time = time.time()

        response = await self._llm.agenerate(
            prompt=prompt,
            model=self._model,
            max_tokens=4096,
            temperature=0.1,
            response_format={"type": "json_object"},
            system_prompt=(
                "You are a document analysis expert. Generate precise, "
                "well-structured hierarchical tree indexes from documents. "
                "Output ONLY valid JSON, no markdown fences."
            ),
        )

        latency_ms = (time.time() - start_time) * 1000

        # Log LLM call
        if self._telemetry:
            await self._telemetry.log_llm_call(
                query_id=self._query_id,
                node_name="tree_generator",
                model=self._model,
                latency_ms=round(latency_ms, 1),
                temperature=0.1,
            )

        # Parse JSON response
        tree_data = self._parse_llm_json(response)

        logger.info(
            "tree_generator.llm_tree_built",
            sections=len(tree_data.get("sections", [])),
            latency_ms=round(latency_ms, 1),
        )

        return tree_data

    async def _generate_node_summaries(
        self,
        nodes: list[TreeNode],
        page_texts: list[str],
    ) -> None:
        """
        Generate concise summaries for each node using LLM.

        Processes nodes in batches for efficiency. Only generates
        summaries for nodes that don't already have one.

        Args:
            nodes: List of tree nodes to summarize.
            page_texts: Full page texts for context.
        """
        import time

        nodes_to_summarize: list[TreeNode] = []
        self._collect_nodes_for_summary(nodes, nodes_to_summarize)

        if not nodes_to_summarize:
            return

        logger.info(
            "tree_generator.generating_summaries",
            node_count=len(nodes_to_summarize),
        )

        # Process in batches of 5 to avoid rate limits
        batch_size = 5
        for i in range(0, len(nodes_to_summarize), batch_size):
            batch = nodes_to_summarize[i: i + batch_size]

            tasks = []
            for node in batch:
                # Get page content for this node
                start_idx = max(0, node.start_page - 1)
                end_idx = min(len(page_texts), node.end_page)
                content = "\n".join(page_texts[start_idx:end_idx])

                # Truncate to avoid token limits
                content = content[:2000]

                tasks.append(
                    self._generate_single_summary(node, content)
                )

            await asyncio.gather(*tasks, return_exceptions=True)

    async def _generate_single_summary(
        self,
        node: TreeNode,
        content: str,
    ) -> None:
        """
        Generate a summary for a single node.

        Args:
            node: TreeNode to summarize.
            content: Text content from the node's page range.
        """
        import time

        try:
            prompt = _SUMMARY_PROMPT.format(
                title=node.title,
                start_page=node.start_page,
                end_page=node.end_page,
                content=content,
            )

            start_time = time.time()

            summary = await self._llm.agenerate(
                prompt=prompt,
                model=settings.fast_llm_model,
                max_tokens=150,
                temperature=0.1,
            )

            latency_ms = (time.time() - start_time) * 1000

            node.summary = summary.strip()

            if self._telemetry:
                await self._telemetry.log_llm_call(
                    query_id=self._query_id,
                    node_name="tree_generator_summary",
                    model=settings.fast_llm_model,
                    latency_ms=round(latency_ms, 1),
                    temperature=0.1,
                )

        except Exception as exc:
            logger.warning(
                "tree_generator.summary_failed",
                node_id=node.node_id,
                error=str(exc),
            )
            # Keep existing summary or leave empty — non-fatal error

    # ─── Private helpers ───────────────────────────────

    def _build_content_sample(
        self,
        page_texts: list[str],
        total_pages: int,
    ) -> str:
        """
        Build a representative content sample for the LLM.

        Selects pages from the beginning, middle, and end of the document
        to give the LLM enough context to identify the document's structure.

        Args:
            page_texts: All page texts.
            total_pages: Total page count.

        Returns:
            Formatted content sample string.
        """
        sample_pages: list[int] = []

        # First 3 pages (usually TOC, intro)
        for i in range(min(3, total_pages)):
            sample_pages.append(i)

        # Middle pages
        if total_pages > 10:
            mid = total_pages // 2
            for i in range(max(0, mid - 1), min(total_pages, mid + 2)):
                if i not in sample_pages:
                    sample_pages.append(i)

        # Last 2 pages
        for i in range(max(0, total_pages - 2), total_pages):
            if i not in sample_pages:
                sample_pages.append(i)

        parts: list[str] = []
        for idx in sorted(sample_pages):
            text = page_texts[idx][:800]  # Truncate each page
            parts.append(f"--- Page {idx + 1} ---\n{text}")

        return "\n\n".join(parts)

    def _parse_llm_json(self, response: str) -> dict:
        """
        Parse LLM response as JSON, handling common formatting issues.

        Args:
            response: Raw LLM response string.

        Returns:
            Parsed dictionary.

        Raises:
            RuntimeError: If response cannot be parsed as valid JSON.
        """
        cleaned = response.strip()

        # Remove markdown code fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last lines (```json and ```)
            lines = [
                line for line in lines
                if not line.strip().startswith("```")
            ]
            cleaned = "\n".join(lines)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to find JSON object in response
            start_idx = cleaned.find("{")
            end_idx = cleaned.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                try:
                    return json.loads(cleaned[start_idx:end_idx])
                except json.JSONDecodeError:
                    pass

            raise RuntimeError(
                f"Failed to parse LLM response as JSON. "
                f"Response preview: {cleaned[:200]}..."
            )

    def _parse_tree_response(
        self,
        tree_data: dict,
        total_pages: int,
    ) -> list[TreeNode]:
        """
        Convert the raw LLM JSON response into TreeNode objects.

        Args:
            tree_data: Parsed JSON dict from LLM.
            total_pages: Total pages for validation.

        Returns:
            List of root-level TreeNode objects.
        """
        sections = tree_data.get("sections", [])
        root_nodes: list[TreeNode] = []

        for idx, section in enumerate(sections):
            node = self._section_to_node(section, level=0, parent_idx=idx)
            root_nodes.append(node)

        # Validate page coverage
        self._validate_page_coverage(root_nodes, total_pages)

        return root_nodes

    def _section_to_node(
        self,
        section: dict,
        level: int,
        parent_idx: int,
    ) -> TreeNode:
        """
        Recursively convert a section dict to a TreeNode.

        Args:
            section: Section dict from LLM response.
            level: Current depth level.
            parent_idx: Index of this node among its siblings.

        Returns:
            TreeNode with children.
        """
        node_id = f"L{level}_N{parent_idx}_{section.get('title', 'unknown')[:20]}"
        node_id = node_id.replace(" ", "_").replace("/", "_")

        children: list[TreeNode] = []
        subsections = section.get("subsections", [])
        for child_idx, sub in enumerate(subsections):
            child_node = self._section_to_node(sub, level + 1, child_idx)
            children.append(child_node)

        return TreeNode(
            title=section.get("title", f"Section {parent_idx + 1}"),
            node_id=node_id,
            start_page=section.get("start_page", 1),
            end_page=section.get("end_page", 1),
            summary=section.get("summary", ""),
            children=children,
            level=level,
        )

    def _validate_page_coverage(
        self,
        nodes: list[TreeNode],
        total_pages: int,
    ) -> None:
        """
        Validate that tree nodes cover all pages reasonably.

        Logs warnings for gaps or overlaps but doesn't fail — the LLM
        may not produce perfect page ranges every time.

        Args:
            nodes: Root-level tree nodes.
            total_pages: Total pages in the document.
        """
        if not nodes:
            logger.warning("tree_generator.validation.no_nodes")
            return

        covered_pages: set[int] = set()
        for node in nodes:
            self._collect_covered_pages(node, covered_pages)

        expected = set(range(1, total_pages + 1))
        missing = expected - covered_pages
        extra = covered_pages - expected

        if missing:
            logger.warning(
                "tree_generator.validation.missing_pages",
                count=len(missing),
                sample=sorted(list(missing))[:10],
            )

        if extra:
            logger.warning(
                "tree_generator.validation.extra_pages",
                count=len(extra),
                sample=sorted(list(extra))[:10],
            )

    def _collect_covered_pages(
        self, node: TreeNode, pages: set[int]
    ) -> None:
        """Recursively collect all pages covered by a node and its children."""
        if node.children:
            for child in node.children:
                self._collect_covered_pages(child, pages)
        else:
            # Leaf node — add its page range
            for p in range(node.start_page, node.end_page + 1):
                pages.add(p)

    def _collect_nodes_for_summary(
        self,
        nodes: list[TreeNode],
        result: list[TreeNode],
    ) -> None:
        """Recursively collect nodes that need summaries."""
        for node in nodes:
            if not node.summary or len(node.summary.strip()) < 10:
                result.append(node)
            for child in node.children:
                self._collect_nodes_for_summary([child], result)

    @staticmethod
    def _generate_doc_id(filename: str) -> str:
        """
        Generate a stable document ID from filename.

        Args:
            filename: Original PDF filename.

        Returns:
            Short hash-based document ID.
        """
        h = hashlib.sha256(filename.encode()).hexdigest()[:12]
        name = Path(filename).stem[:20].replace(" ", "_")
        return f"{name}_{h}"

    @staticmethod
    def _count_nodes(nodes: list[TreeNode]) -> int:
        """Count total nodes in a tree recursively."""
        count = 0
        for node in nodes:
            count += 1
            if node.children:
                count += TreeGenerator._count_nodes(node.children)
        return count

    @staticmethod
    def _calculate_depth(
        nodes: list[TreeNode], current: int = 1
    ) -> int:
        """Calculate maximum depth of a tree."""
        if not nodes:
            return 0
        max_depth = current
        for node in nodes:
            if node.children:
                child_depth = TreeGenerator._calculate_depth(
                    node.children, current + 1
                )
                max_depth = max(max_depth, child_depth)
        return max_depth
