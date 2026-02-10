"""
Ingestion Pipeline - Document processing orchestration

Coordinates PDF extraction, chunking, embedding, and storage.
"""

from dataclasses import dataclass
from typing import Optional

from .pdf_processor import PDFProcessor
from ..rag.chunker import SemanticChunker
from ..rag.embeddings import EmbeddingService
from ..vectorstore.qdrant_store import QdrantStore
from ..observability.logging import get_logger

logger = get_logger(__name__)


@dataclass
class IngestionResult:
    """Result from document ingestion"""
    filename: str
    page_count: int
    chunk_count: int
    success: bool
    error: Optional[str] = None


class IngestionPipeline:
    """
    Pipeline for ingesting documents into the RAG system.
    
    Steps:
    1. Extract text from PDF
    2. Chunk text semantically
    3. Generate embeddings
    4. Store in vector database
    """
    
    def __init__(self, collection_name: str = None):
        self.pdf_processor = PDFProcessor()
        self.chunker = SemanticChunker()
        self.embedding_service = EmbeddingService()
        self.vector_store = QdrantStore(collection_name=collection_name)
        self.logger = logger
    
    async def process(
        self,
        file_path: str,
        filename: str = None
    ) -> IngestionResult:
        """
        Process a PDF file and ingest into vector store.
        
        Args:
            file_path: Path to PDF file
            filename: Original filename for metadata
            
        Returns:
            IngestionResult with statistics
        """
        filename = filename or file_path.split("/")[-1]
        
        try:
            self.logger.info("ingestion_started", filename=filename)
            
            # Step 1: Extract text from PDF
            pages = self.pdf_processor.extract_text(file_path)
            full_text = "\n\n".join(pages)
            
            self.logger.info(
                "text_extracted",
                filename=filename,
                page_count=len(pages),
                char_count=len(full_text)
            )
            
            # Step 2: Chunk the text
            chunks = self.chunker.chunk_text(full_text, source=filename)
            
            self.logger.info(
                "text_chunked",
                filename=filename,
                chunk_count=len(chunks)
            )
            
            # Step 3: Generate embeddings
            texts = [chunk.text for chunk in chunks]
            embeddings = self.embedding_service.embed_texts(texts)
            
            # Step 4: Prepare documents for storage
            documents = [
                {
                    "content": chunk.text,
                    "source": chunk.source,
                    "chunk_index": chunk.index,
                    "metadata": {
                        "start_char": chunk.start_char,
                        "end_char": chunk.end_char
                    }
                }
                for chunk in chunks
            ]
            
            # Step 5: Store in vector database
            doc_ids = self.vector_store.add_documents(documents, embeddings)
            
            self.logger.info(
                "ingestion_completed",
                filename=filename,
                chunk_count=len(chunks),
                doc_ids=len(doc_ids)
            )
            
            return IngestionResult(
                filename=filename,
                page_count=len(pages),
                chunk_count=len(chunks),
                success=True
            )
            
        except Exception as e:
            self.logger.error(
                "ingestion_failed",
                filename=filename,
                error=str(e)
            )
            
            return IngestionResult(
                filename=filename,
                page_count=0,
                chunk_count=0,
                success=False,
                error=str(e)
            )
    
    def process_sync(
        self,
        file_path: str,
        filename: str = None
    ) -> IngestionResult:
        """Synchronous version of process"""
        import asyncio
        return asyncio.run(self.process(file_path, filename))
