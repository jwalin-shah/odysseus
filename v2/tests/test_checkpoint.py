"""Test suite for sys-checkpoint: The Context Compressor.

This CLI takes a raw text file or piped stdin (like a massive scraped DOM or a giant git diff),
prompts a cheap local model (like Pioneer/Haiku) to compress it, and outputs a dense markdown summary.
It prevents us from blowing out our quotas on expensive models.
"""
import os
import subprocess
import pytest
from pathlib import Path

# The V2 CLI shim we will create
CHECKPOINT_CLI = Path(__file__).parent.parent.parent / ".venv" / "bin" / "sys-checkpoint"

def test_checkpoint_help_exists():
    """The CLI should be executable and have a --help flag."""
    if not CHECKPOINT_CLI.exists():
        pytest.skip("sys-checkpoint shim not created yet")
    
    result = subprocess.run([str(CHECKPOINT_CLI), "--help"], capture_output=True, text=True)
    assert result.returncode == 0
    assert "Compress raw text into dense markdown" in result.stdout

def test_checkpoint_respects_token_budget():
    """If given a strict output token budget, the compressor must truncate or strictly prompt the LLM."""
    if not CHECKPOINT_CLI.exists():
        pytest.skip("sys-checkpoint shim not created yet")
        
    raw_input = "User says: " + ("blah " * 1000)
    
    # We ask it to compress it to max 50 tokens
    result = subprocess.run(
        [str(CHECKPOINT_CLI), "--max-tokens", "50", "--model", "dummy-mock"], 
        input=raw_input,
        capture_output=True, 
        text=True
    )
    
    assert result.returncode == 0
    # Assuming rough token estimation (1 token ~ 4 chars)
    assert len(result.stdout) < 250, "Output blew past the token budget!"

def test_checkpoint_handles_empty_input():
    """Empty input should return an empty string or a standard empty checkpoint marker, not crash."""
    if not CHECKPOINT_CLI.exists():
        pytest.skip("sys-checkpoint shim not created yet")
        
    result = subprocess.run([str(CHECKPOINT_CLI)], input="", capture_output=True, text=True)
    assert result.returncode == 0
    assert "No content to compress" in result.stdout or result.stdout.strip() == ""
