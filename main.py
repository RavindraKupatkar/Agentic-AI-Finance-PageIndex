"""
Finance Agentic RAG - Main Entry Point

CLI interface for running queries, ingestion, and server.
"""

import argparse
import asyncio
from pathlib import Path


def run_server():
    """Run the FastAPI server"""
    import uvicorn
    from src.core.config import settings
    
    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )


async def run_query(question: str, thread_id: str = "cli"):
    """Run a single query"""
    from src.agents.orchestrator import AgentOrchestrator
    
    print(f"\n📝 Question: {question}\n")
    print("🔍 Processing...\n")
    
    orchestrator = AgentOrchestrator()
    result = orchestrator.query(question, thread_id=thread_id)
    
    print("=" * 60)
    print(f"📌 Answer:\n{result.answer}")
    print("-" * 60)
    print(f"📚 Sources: {', '.join(result.sources) if result.sources else 'None'}")
    print(f"🎯 Confidence: {result.confidence:.2%}")
    print(f"⏱️  Latency: {result.latency_ms:.0f}ms")
    print("=" * 60)


async def run_ingest(file_path: str):
    """Ingest a PDF document"""
    from src.ingestion.pipeline import IngestionPipeline
    
    path = Path(file_path)
    if not path.exists():
        print(f"❌ File not found: {file_path}")
        return
    
    print(f"📄 Ingesting: {path.name}")
    
    pipeline = IngestionPipeline()
    result = await pipeline.process(str(path), filename=path.name)
    
    if result.success:
        print(f"✅ Successfully ingested {result.chunk_count} chunks")
    else:
        print(f"❌ Ingestion failed: {result.error}")


def main():
    parser = argparse.ArgumentParser(description="Finance Agentic RAG")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Server command
    server_parser = subparsers.add_parser("server", help="Run the API server")
    
    # Query command
    query_parser = subparsers.add_parser("query", help="Run a query")
    query_parser.add_argument("question", type=str, help="Question to ask")
    query_parser.add_argument("--thread", type=str, default="cli", help="Thread ID")
    
    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest a document")
    ingest_parser.add_argument("file", type=str, help="Path to PDF file")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check system status")
    
    args = parser.parse_args()
    
    if args.command == "server":
        run_server()
    elif args.command == "query":
        asyncio.run(run_query(args.question, args.thread))
    elif args.command == "ingest":
        asyncio.run(run_ingest(args.file))
    elif args.command == "status":
        from src.vectorstore.qdrant_store import QdrantStore
        store = QdrantStore()
        print(f"📊 Documents in store: {store.get_count()}")
        print(f"✅ Vector store: {'healthy' if store.health_check() else 'unhealthy'}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
