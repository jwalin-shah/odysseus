"""Test suite for the V2 LLM Router pipeline.

This pipeline wires together sys_router.py to dynamically route requests based on
the live quota constraints before falling back to free compute.
"""
import os
import json
import pytest
import subprocess
from pathlib import Path

ROUTER_CLI = Path(__file__).parent.parent.parent / ".venv" / "bin" / "sys-router"

def test_router_waterfall_claude_a(tmp_path, monkeypatch):
    """Router should pick claude-a if it is available and has premium quota."""
    if not ROUTER_CLI.exists():
        pytest.skip("sys-router shim not created yet")
        
    db_path = tmp_path / "quota-live.json"
    monkeypatch.setenv("SYS_QUOTA_STATE", str(db_path))
    
    # Mock quota-live.json with claude-a available
    data = {
        "providers": {
            "ca": {
                "quotas": {
                    "session_pct_remaining": 50,
                    "weekly_pct_remaining": 50
                }
            }
        }
    }
    with open(db_path, "w") as f:
        json.dump(data, f)
    
    # Try to route a message automatically
    result = subprocess.run(
        [str(ROUTER_CLI), "--model", "auto"], 
        input="Write my resume",
        capture_output=True, 
        text=True
    )
    
    assert result.returncode == 0
    assert "Routed to claude-a successfully" in result.stdout

def test_router_waterfall_fallback_codex(tmp_path, monkeypatch):
    """Router should fallback to codex if premium accounts are exhausted."""
    if not ROUTER_CLI.exists():
        pytest.skip("sys-router shim not created yet")
        
    db_path = tmp_path / "quota-live.json"
    monkeypatch.setenv("SYS_QUOTA_STATE", str(db_path))
    
    # Mock quota-live.json with premium accounts exhausted
    data = {
        "providers": {
            "ca": {
                "quotas": {
                    "session_pct_remaining": 5, # exhausted (< 10)
                    "weekly_pct_remaining": 50
                }
            },
            "cb": {
                "quotas": {
                    "session_pct_remaining": 5, # exhausted (< 10)
                    "weekly_pct_remaining": 50
                }
            }
        }
    }
    with open(db_path, "w") as f:
        json.dump(data, f)
    
    # Try to route a message automatically
    result = subprocess.run(
        [str(ROUTER_CLI), "--model", "auto"], 
        input="Test Prompt",
        capture_output=True, 
        text=True
    )
    
    assert result.returncode == 0
    assert "Routed to codex successfully" in result.stdout

def test_router_respects_explicit_model(tmp_path, monkeypatch):
    """Router should respect an explicit model override."""
    if not ROUTER_CLI.exists():
        pytest.skip("sys-router shim not created yet")
        
    # Call the router with a mock model that just echoes "Mock MiniMax Response"
    result = subprocess.run(
        [str(ROUTER_CLI), "--model", "dummy-mock"], 
        input="Test Prompt",
        capture_output=True, 
        text=True
    )
    
    assert result.returncode == 0
    assert "Mock MiniMax Response" in result.stdout

from v2.src.sys_router import pick_premium_tier

def test_pick_premium_tier_ca():
    providers = {
        "ca": {
            "quotas": {
                "session_pct_remaining": 50,
                "weekly_pct_remaining": 50
            }
        }
    }
    assert pick_premium_tier(providers) == "claude-a"

def test_pick_premium_tier_falls_through_to_codex():
    providers = {
        "ca": {
            "quotas": {
                "session_pct_remaining": 5,
                "weekly_pct_remaining": 50
            }
        },
        "cb": {
            "quotas": {
                "session_pct_remaining": 5,
                "weekly_pct_remaining": 50
            }
        }
    }
    assert pick_premium_tier(providers) is None
