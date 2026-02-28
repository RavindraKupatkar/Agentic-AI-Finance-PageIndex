import asyncio
import httpx
import time

BASE_URL = "http://localhost:8000/api/v1"

async def stress_query(client, i):
    payload = {
        "question": f"Test concurrent query number {i}",
        "thread_id": "stress_thread_1",
        "user_id": "stress_user"
    }
    start = time.time()
    try:
        res = await client.post(f"{BASE_URL}/pageindex/query", json=payload, timeout=60.0)
        latency = time.time() - start
        return res.status_code, latency
    except Exception as e:
        return str(e), time.time() - start

async def test_concurrent_queries(concurrency=5):
    print(f"\n--- Stress Testing: {concurrency} Concurrent Queries ---")
    async with httpx.AsyncClient() as client:
        tasks = [stress_query(client, i) for i in range(concurrency)]
        results = await asyncio.gather(*tasks)
        
        successes = sum(1 for status, latency in results if status == 200)
        failures = concurrency - successes
        avg_latency = sum(latency for status, latency in results) / concurrency
        
        print(f"Total Requests: {concurrency}")
        print(f"Successes: {successes}")
        print(f"Failures: {failures}")
        print(f"Average Latency: {avg_latency:.2f}s")
        for i, (status, latency) in enumerate(results):
            print(f"  Request {i}: Status {status}, Latency {latency:.2f}s")

async def test_penetration():
    print("\n--- Basic Penetration & Edge Cases ---")
    async with httpx.AsyncClient() as client:
        # SQL Injection attempt in thread_id
        payload_sql = {
            "question": "What is the revenue?",
            "thread_id": "'; DROP TABLE conversations; --",
            "user_id": "hacker"
        }
        res = await client.post(f"{BASE_URL}/pageindex/query", json=payload_sql, timeout=30.0)
        print(f"SQLi payload status (expected 200 or 422, robustly handled DB): {res.status_code}")

        # Massive payload attempt
        payload_large = {
            "question": "A" * 10000,
            "thread_id": "large_thread",
            "user_id": "user"
        }
        res = await client.post(f"{BASE_URL}/pageindex/query", json=payload_large, timeout=30.0)
        print(f"Large payload status (expected handled error or block): {res.status_code}")

async def main():
    await test_concurrent_queries(concurrency=3) # Small concurrency first to not overload API limits
    await test_penetration()
    print("\nStress & Pen Testing complete.")

if __name__ == "__main__":
    asyncio.run(main())
