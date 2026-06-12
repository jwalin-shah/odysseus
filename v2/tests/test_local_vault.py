import os
import subprocess
import pytest
from pathlib import Path

# The absolute path to the compiled CLI binary or python entrypoint
VAULT_CLI = Path(__file__).parent.parent / "cli" / "local_vault.py"

@pytest.fixture
def clean_env(tmp_path):
    """Ensure a sterile environment with no leaked tokens."""
    env = os.environ.copy()
    env.pop("ODY_CALLER_TOKEN", None)
    # Isolate rate-limit state per test; the lockdown flag is persistent and
    # would otherwise poison every later run via the shared /tmp default.
    env["ODY_VAULT_STATE"] = str(tmp_path / "vault_rate_limit.json")
    return env

class TestVaultPermissions:
    def test_vault_rejects_unauthorized_caller(self, clean_env):
        """
        Catastrophic vulnerability test: If an agent runs `ody-vault get key`,
        it MUST fail unless it has the cryptographic caller token.
        """
        result = subprocess.run(
            ["python3", str(VAULT_CLI), "get", "OPENAI_API_KEY"],
            env=clean_env,
            capture_output=True,
            text=True
        )
        assert result.returncode != 0, "FATAL: Vault allowed access without caller verification!"
        assert "Unauthorized" in result.stderr or "Permission denied" in result.stderr

    def test_vault_accepts_verified_orchestrator(self, clean_env):
        """
        The orchestrator must pass a short-lived caller token to access the vault.
        """
        clean_env["ODY_CALLER_TOKEN"] = "mock_secure_orchestrator_token_123"
        result = subprocess.run(
            ["python3", str(VAULT_CLI), "get", "TEST_KEY"],
            env=clean_env,
            capture_output=True,
            text=True
        )
        # Even if the key doesn't exist, it shouldn't fail auth
        assert "Unauthorized" not in result.stderr
        assert result.returncode == 0

    def test_vault_strictly_rate_limits_requests(self, clean_env):
        """
        If a rogue script loops `ody-vault get` 1000 times, it must trigger
        a rate limit and lock down to prevent brute-force extraction.
        """
        clean_env["ODY_CALLER_TOKEN"] = "mock_secure_orchestrator_token_123"
        
        # Simulate 10 rapid calls
        successes = 0
        for _ in range(10):
            res = subprocess.run(
                ["python3", str(VAULT_CLI), "get", "TEST_KEY"],
                env=clean_env,
                capture_output=True
            )
            if res.returncode == 0:
                successes += 1

        assert successes < 10, "FATAL: Vault did not rate-limit rapid sequential reads. Brute force possible."
