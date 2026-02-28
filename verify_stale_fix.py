"""Trigger the API to auto-clean stale entries, then verify."""
import requests

print("=== Calling /api/v1/pageindex/documents to trigger auto-cleanup ===")
try:
    r = requests.get("http://localhost:8000/api/v1/pageindex/documents", timeout=10)
    print(f"Status: {r.status_code}")
    docs = r.json()
    print(f"Documents returned: {len(docs)}")
    for d in docs:
        print(f"  - {d['doc_id']}: {d['filename']}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== Re-checking SQLite after cleanup ===")
import sqlite3
from pathlib import Path

conn = sqlite3.connect("data/pageindex_metadata.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT doc_id, filename, tree_path FROM documents").fetchall()
print(f"Documents remaining in SQLite: {len(rows)}")
stale = 0
for r in rows:
    d = dict(r)
    exists = Path(d["tree_path"]).exists()
    status = "OK" if exists else "STALE"
    if not exists:
        stale += 1
    print(f"  [{status}] {d['doc_id']}")
conn.close()

if stale == 0:
    print("\n SUCCESS: All stale entries have been auto-cleaned!")
else:
    print(f"\n WARNING: {stale} stale entries still remain.")
