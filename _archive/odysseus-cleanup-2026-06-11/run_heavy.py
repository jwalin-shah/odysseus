import subprocess
from concurrent.futures import ThreadPoolExecutor

def deduct():
    res = subprocess.run(["python3", "v2/src/sys_quota.py", "deduct", "--db", "test_heavy.db", "--amount", "1"], capture_output=True)
    return res

subprocess.run(["python3", "v2/src/sys_quota.py", "init", "--db", "test_heavy.db", "--limit", "1000"])

with ThreadPoolExecutor(max_workers=50) as ex:
    results = list(ex.map(lambda _: deduct(), range(200)))

failures = [r for r in results if r.returncode != 0]
for f in failures:
    print(f"FAILED: {f.returncode} {f.stderr.decode()}")
