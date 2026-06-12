import pytest
import subprocess
import tempfile
import os

QUOTA_EXHAUSTED_EXIT = 75  # EX_TEMPFAIL; 429 not representable in 8-bit POSIX exit status

def _concurrent_deduct(db):
    res = subprocess.run(["sys-quota", "deduct", "--amount", "15", "--db", db])
    return res.returncode

# ============================================================================
# V2 ARCHITECTURAL SPEC: `sys-quota` (Quota & Limits CLI)
# ============================================================================
# Analysis of Open-Source Quota Management (OpenCode, SwarmAI, agentmemory):
# 1. Atomic Concurrency: Multiple background agents operate concurrently. Quota 
#    checks/deductions must be atomic to prevent race conditions exceeding budgets.
# 2. Strict Boundary Enforcement: A hard limit MUST trigger a specific exit code 
#    (e.g., 429) before external network boundaries are crossed.
# 3. Dry-Run / Pre-Check: Agents need a fast path to verify quota state without
#    deducting or locking resources.
# 4. Multi-Dimensional Tracking: Quotas apply at multiple levels (Token Count,
#    Cost Budget, Daily API Call Count) and must decay/reset correctly.
# ============================================================================

def run_sys_quota(*args):
    """Helper to run the sys-quota CLI in tests."""
    return subprocess.run(
        ["sys-quota", *args],
        capture_output=True,
        text=True
    )

class TestOdyQuotaArchitecture:
    """
    Adversarial Pytest Specifications for the `sys-quota` CLI.
    These tests enforce safe concurrent budget tracking and strict exit codes.
    """

    def test_strict_exit_code_on_exhaustion(self, tmp_path):
        """
        MUST return a distinct exit code (e.g. 429) when a quota is exhausted,
        never a generic error or success.
        """
        db_path = tmp_path / "quota.db"
        # Setup: Limit is 100
        run_sys_quota("init", "--db", str(db_path), "--limit", "100")
        
        # Deduct 100
        res1 = run_sys_quota("deduct", "--amount", "100", "--db", str(db_path))
        assert res1.returncode == 0
        
        # Deduct 1 more -> Must fail with 429
        res2 = run_sys_quota("deduct", "--amount", "1", "--db", str(db_path))
        assert res2.returncode == QUOTA_EXHAUSTED_EXIT
        assert "QUOTA_EXHAUSTED" in res2.stderr

    def test_atomic_concurrency_protection(self, tmp_path):
        """
        MUST use atomic file locks or WAL-mode SQLite to handle highly parallel 
        deductions from multiple subagents without double-spending.
        """
        db_path = tmp_path / "quota.db"
        run_sys_quota("init", "--db", str(db_path), "--limit", "100")
        
        # Simulate 10 parallel processes trying to deduct 15 tokens at the same time
        # (10 * 15 = 150 > 100). Only a subset should succeed, total deducted exactly 90.
        import multiprocessing

        with multiprocessing.Pool(10) as p:
            results = p.map(_concurrent_deduct, [str(db_path)] * 10)
            
        successes = [r for r in results if r == 0]
        failures = [r for r in results if r == QUOTA_EXHAUSTED_EXIT]

        # Exactly 6 should succeed (6 * 15 = 90), the remaining 4 must get 429
        assert len(successes) == 6
        assert len(failures) == 4
        
        # Verify remaining balance is exactly 10
        check = run_sys_quota("check", "--db", str(db_path))
        assert "REMAINING: 10" in check.stdout

    def test_stateless_dry_run_checks(self, tmp_path):
        """
        MUST allow querying the quota (`--dry-run` or `check`) without locking
        or deducting. This must be extremely fast.
        """
        db_path = tmp_path / "quota.db"
        run_sys_quota("init", "--db", str(db_path), "--limit", "100")
        
        # Check quota
        res = run_sys_quota("check", "--db", str(db_path))
        assert res.returncode == 0
        assert "REMAINING: 100" in res.stdout
        
        # Check again to ensure no deduction
        res2 = run_sys_quota("check", "--db", str(db_path))
        assert "REMAINING: 100" in res2.stdout

    def test_dimensional_routing(self, tmp_path):
        """
        MUST allow specifying WHICH quota dimension is being evaluated 
        (e.g., token_count vs cost_usd vs api_calls).
        """
        db_path = tmp_path / "quota.db"
        run_sys_quota("init", "--db", str(db_path), "--tokens", "5000", "--cost", "2.0")
        
        # Deduct cost
        res_cost = run_sys_quota("deduct", "--type", "cost", "--amount", "1.5", "--db", str(db_path))
        assert res_cost.returncode == 0
        
        # Deduct tokens
        res_tokens = run_sys_quota("deduct", "--type", "tokens", "--amount", "4000", "--db", str(db_path))
        assert res_tokens.returncode == 0
        
        # Exceed cost
        res_fail = run_sys_quota("deduct", "--type", "cost", "--amount", "1.0", "--db", str(db_path))
        assert res_fail.returncode == QUOTA_EXHAUSTED_EXIT

    def test_rolling_decay_reset(self, tmp_path):
        """
        MUST cleanly reset quotas on bounded rolling windows (e.g. daily reset)
        without needing a persistent daemon. Time-based diffs on access.
        """
        db_path = tmp_path / "quota.db"
        
        # Init with a past timestamp to simulate yesterday
        run_sys_quota("init", "--db", str(db_path), "--limit", "100", "--window", "24h")
        run_sys_quota("deduct", "--amount", "100", "--db", str(db_path))
        
        # Fast forward time internally via CLI env injection
        res = subprocess.run(
            ["sys-quota", "deduct", "--amount", "10", "--db", str(db_path)],
            env={**os.environ, "ODY_MOCK_TIME_OFFSET_HOURS": "25"},
            capture_output=True,
            text=True
        )
        # Should succeed because the window reset automatically on access
        assert res.returncode == 0

    def test_concurrent_mixed_workload(self, tmp_path):
        """
        MUST handle concurrent init, check, and deduct without locking errors.
        """
        db_path = tmp_path / "quota.db"
        run_sys_quota("init", "--db", str(db_path), "--limit", "10000")
        
        import threading
        
        errors = []
        def do_deduct():
            res = run_sys_quota("deduct", "--db", str(db_path), "--amount", "1")
            if res.returncode not in (0, QUOTA_EXHAUSTED_EXIT):
                errors.append(f"deduct failed: {res.returncode} {res.stderr}")
                
        def do_check():
            res = run_sys_quota("check", "--db", str(db_path))
            if res.returncode != 0:
                errors.append(f"check failed: {res.returncode} {res.stderr}")

        def do_init():
            res = run_sys_quota("init", "--db", str(db_path), "--limit", "10000")
            if res.returncode != 0:
                errors.append(f"init failed: {res.returncode} {res.stderr}")

        threads = []
        for _ in range(20):
            threads.append(threading.Thread(target=do_deduct))
            threads.append(threading.Thread(target=do_check))
            threads.append(threading.Thread(target=do_init))
            
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert not errors
