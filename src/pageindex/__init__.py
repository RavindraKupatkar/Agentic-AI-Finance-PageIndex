"""
PageIndex Module - Vectorless, Reasoning-based RAG

Core module implementing VectifyAI's PageIndex approach:
- Tree index generation from PDF documents
- LLM-based tree search for reasoning-driven retrieval
- Page-level content extraction with full traceability

Uses Groq's OpenAI-compatible API (gpt-oss-120b) for tree operations.

Note: TreeGenerator and PageExtractor require PyMuPDF (fitz).
      Imports are lazy to avoid import errors when fitz is not installed.
"""

from .tree_store import TreeStore

# Lazy imports for modules that require PyMuPDF
__all__ = [
    "TreeGenerator",
    "TreeStore",
    "TreeSearcher",
    "PageExtractor",
]


def __getattr__(name: str):
    """Lazy import for heavy modules that require PyMuPDF."""
    if name == "TreeGenerator":
        from .tree_generator import TreeGenerator
        return TreeGenerator
    elif name == "TreeSearcher":
        from .tree_searcher import TreeSearcher
        return TreeSearcher
    elif name == "PageExtractor":
        from .page_extractor import PageExtractor
        return PageExtractor
    raise AttributeError(f"module 'src.pageindex' has no attribute {name}")
