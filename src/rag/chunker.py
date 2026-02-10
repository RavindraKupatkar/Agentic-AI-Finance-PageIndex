"""
Semantic Chunker - Intelligent text chunking

Uses semantic boundaries for better chunk quality.
"""

from typing import List
from dataclasses import dataclass

from ..core.config import settings


@dataclass
class Chunk:
    """Represents a text chunk"""
    text: str
    source: str
    index: int
    start_char: int = 0
    end_char: int = 0
    metadata: dict = None


class SemanticChunker:
    """
    Chunk text using semantic boundaries.
    
    Attempts to keep semantically related content together.
    """
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
    
    def chunk_text(
        self,
        text: str,
        source: str = "unknown"
    ) -> List[Chunk]:
        """
        Split text into overlapping chunks.
        
        Tries to break at sentence boundaries when possible.
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        index = 0
        
        while start < len(text):
            # Determine chunk end
            end = start + self.chunk_size
            
            # Try to find a good break point (sentence end)
            if end < len(text):
                # Look for sentence end near chunk boundary
                best_break = self._find_break_point(text, end - 50, end + 50)
                if best_break > start:
                    end = best_break
            else:
                end = len(text)
            
            chunk_text = text[start:end].strip()
            
            if chunk_text:
                chunks.append(Chunk(
                    text=chunk_text,
                    source=source,
                    index=index,
                    start_char=start,
                    end_char=end,
                    metadata={}
                ))
                index += 1
            
            # Move start with overlap
            start = end - self.chunk_overlap
            
            # Prevent infinite loop
            if start >= end:
                start = end
        
        return chunks
    
    def _find_break_point(self, text: str, start: int, end: int) -> int:
        """Find best break point (sentence end) in range"""
        start = max(0, start)
        end = min(len(text), end)
        
        # Look for sentence endings
        best = -1
        for i in range(start, end):
            if text[i] in '.!?\n':
                best = i + 1
        
        return best if best > 0 else end
