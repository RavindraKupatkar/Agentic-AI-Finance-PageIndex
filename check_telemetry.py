import sqlite3, os

db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "telemetry.db")
print("PATH:", db)
print("EXISTS:", os.path.exists(db))
print("SIZE:", os.path.getsize(db), "bytes")
print()

c = sqlite3.connect(db)
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print("ALL TABLES:")
for t in tables:
    n = c.execute(f"SELECT COUNT(*) FROM [{t[0]}]").fetchone()[0]
    print(f"  -> {t[0]}: {n} rows")
c.close()
