"""
Ingestion Routes - Handle PDF upload and processing
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from typing import List
import tempfile
import os

from ..schemas.response import IngestResponse
from ...ingestion.pipeline import IngestionPipeline
from ...observability.metrics import INGESTION_COUNT

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest_pdf(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Ingest a PDF document into the vector store
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Process the PDF
        pipeline = IngestionPipeline()
        result = await pipeline.process(tmp_path, filename=file.filename)
        
        # Cleanup
        os.unlink(tmp_path)
        
        INGESTION_COUNT.labels(status="success").inc()
        
        return IngestResponse(
            filename=file.filename,
            chunks_created=result.chunk_count,
            status="success",
            message=f"Successfully ingested {result.chunk_count} chunks"
        )
        
    except Exception as e:
        INGESTION_COUNT.labels(status="error").inc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/batch")
async def ingest_batch(files: List[UploadFile] = File(...)):
    """
    Batch ingest multiple PDF documents
    """
    results = []
    for file in files:
        try:
            result = await ingest_pdf(file)
            results.append(result)
        except Exception as e:
            results.append(IngestResponse(
                filename=file.filename,
                chunks_created=0,
                status="error",
                message=str(e)
            ))
    
    return {"results": results}
