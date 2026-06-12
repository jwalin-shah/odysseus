import subprocess
import threading

def init_db():
    subprocess.run(["python3", "v2/src/sys_quota.py", "init", "--db", "test_init.db", "--limit", "1000"])

threads = [threading.Thread(target=init_db) for _ in range(50)]
for t in threads: t.start()
for t in threads: t.join()
print("Done init test")
