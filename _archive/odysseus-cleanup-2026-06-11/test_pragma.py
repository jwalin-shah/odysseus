import sqlite3
import threading
import time

def worker():
    conn = sqlite3.connect('test_pragma.db', timeout=30)
    for _ in range(100):
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("SELECT * FROM sqlite_master")
        except Exception as e:
            print("ERROR", e)

threads = [threading.Thread(target=worker) for _ in range(50)]
for t in threads: t.start()
for t in threads: t.join()
print("Done")
