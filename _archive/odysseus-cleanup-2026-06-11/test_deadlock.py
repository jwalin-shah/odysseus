import sqlite3
import time
import threading

def init_db():
    conn = sqlite3.connect('test_deadlock.db', timeout=3)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS quota (dim TEXT PRIMARY KEY)")
    
    # Start a deferred transaction
    conn.execute("BEGIN DEFERRED")
    conn.execute("INSERT OR REPLACE INTO quota VALUES ('tokens')")
    # Hold the shared lock
    time.sleep(2)
    # Try to upgrade to exclusive
    try:
        conn.commit()
        print("Init commit successful")
    except Exception as e:
        print("Init error:", e)

def deduct_db():
    time.sleep(1) # Let init_db get the shared lock
    conn = sqlite3.connect('test_deadlock.db', timeout=3)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("UPDATE quota SET dim='cost'")
        conn.commit()
        print("Deduct commit successful")
    except Exception as e:
        print("Deduct error:", e)

t1 = threading.Thread(target=init_db)
t2 = threading.Thread(target=deduct_db)
t1.start(); t2.start()
t1.join(); t2.join()
