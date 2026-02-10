"""
PDF Processor - Extract text from PDF documents

Uses PyMuPDF (fitz) for fast, accurate extraction.
"""

from typing import List
import fitz  # PyMuPDF


class PDFProcessor:
    """
    Extract text from PDF documents.
    
    Uses PyMuPDF for faster extraction than pypdf.
    """
    
    def extract_text(self, file_path: str) -> List[str]:
        """
        Extract text from each page of a PDF.
        
        Args:
            file_path: Path to PDF file
            
        Returns:
            List of text strings, one per page
        """
        pages = []
        
        with fitz.open(file_path) as doc:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                
                if text.strip():
                    pages.append(text)
        
        return pages
    
    def extract_with_metadata(self, file_path: str) -> List[dict]:
        """
        Extract text with page metadata.
        
        Returns:
            List of dicts with 'text', 'page', 'metadata'
        """
        results = []
        
        with fitz.open(file_path) as doc:
            metadata = doc.metadata
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                
                if text.strip():
                    results.append({
                        "text": text,
                        "page": page_num + 1,
                        "metadata": {
                            "title": metadata.get("title", ""),
                            "author": metadata.get("author", ""),
                            "total_pages": len(doc)
                        }
                    })
        
        return results
    
    def get_page_count(self, file_path: str) -> int:
        """Get number of pages in PDF"""
        with fitz.open(file_path) as doc:
            return len(doc)
