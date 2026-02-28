import asyncio
import httpx
import time
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"
ERROR_LOG_FILE = "complex_query_errors.md"

FILES_TO_INGEST = [
    "data/Ferrari N.V. Interim Report - September 30, 2025.pdf",
    "data/pwc-global-annual-review-2025.pdf",
    "data/TSX_TCS_2024.pdf"
]

QUERIES = [
    "Summarise all attached files",
    "Compare the revenues of these companies",
    "Compare sales of these companies"
]

markdown_log = []

def log(msg):
    print(msg)
    markdown_log.append(msg)

async def main():
    async with httpx.AsyncClient(timeout=300.0) as client:
        log("# Complex Query Error Log")
        log(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        log("")

        # 1. Ingest Files
        log("## 1. Ingestion Phase")
        for file_path in FILES_TO_INGEST:
            p = Path(file_path)
            if not p.exists():
                log(f"- **Error**: File not found: `{file_path}`")
                continue
            
            log(f"- Ingesting `{p.name}`...")
            with open(p, "rb") as f:
                start = time.time()
                try:
                    resp = await client.post(
                        f"{BASE_URL}/pageindex/ingest",
                        files={"file": (p.name, f, "application/pdf")}
                    )
                    latency = time.time() - start
                    if resp.status_code == 200:
                        log(f"  - ✅ Success ({latency:.1f}s). Doc ID: `{resp.json().get('doc_id')}`")
                    else:
                        log(f"  - ❌ Failed ({latency:.1f}s). Status: {resp.status_code}. Response: `{resp.text}`")
                except Exception as e:
                    log(f"  - ❌ Error ({time.time() - start:.1f}s): `{str(e)}`")

        log("\n## 2. Query Phase")
        for i, query in enumerate(QUERIES, 1):
            log(f"### Query {i}: {query}")
            log("```json")
            payload = {
                "question": query,
                "thread_id": "complex_test",
                "user_id": "test_runner"
            }
            start = time.time()
            try:
                resp = await client.post(f"{BASE_URL}/pageindex/query", json=payload)
                latency = time.time() - start
                
                if resp.status_code == 200:
                    data = resp.json()
                    log(f"// Success ({latency:.1f}s)")
                    log(f"Answer snippet: {str(data.get('answer', ''))[:200]}...")
                    log(f"Query Type: {data.get('query_type')}")
                    log(f"Confidence: {data.get('confidence')}")
                    sources = data.get('sources', [])
                    log(f"Sources cited: {len(sources)}")
                else:
                    log(f"// Failed ({latency:.1f}s)")
                    log(f"Status: {resp.status_code}")
                    log(f"Response: {resp.text}")
            except Exception as e:
                log(f"// Error ({time.time() - start:.1f}s)")
                log(f"Exception: {str(e)}")
            log("```\n")

    with open(ERROR_LOG_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(markdown_log))
    print(f"\n📝 Log written to {ERROR_LOG_FILE}")

if __name__ == "__main__":
    asyncio.run(main())
