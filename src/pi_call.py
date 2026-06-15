import subprocess
import asyncio
import json
import ssl
import urllib.request
import os
from typing import Optional

BUDGET_MODELS = [
    "tokenrouter/MiniMax-M3",
    "tokenrouter/deepseek/deepseek-v4-pro",
]
FRONTIER_MODELS = [
    "anthropic/claude-sonnet-4-6",
    "anthropic/claude-opus-4-8",
]

_TOKENROUTER_BASE = "https://api.tokenrouter.com/v1"


def _provider_model(model: str) -> tuple[str, str]:
    """Split 'provider/model-name' into (provider, model)."""
    parts = model.split("/", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "tokenrouter", model


def _pi_available() -> bool:
    try:
        subprocess.run(["pi", "--version"], capture_output=True, timeout=5)
        return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _direct_tokenrouter(prompt: str, model: str, system: Optional[str], timeout: int) -> str:
    key = os.environ.get("TOKENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("TOKENROUTER_API_KEY not set")
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    ctx = ssl.create_default_context()
    try:
        import certifi
        ctx = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        pass
    payload = json.dumps({"model": model, "messages": msgs, "max_tokens": 8000}).encode()
    req = urllib.request.Request(
        f"{_TOKENROUTER_BASE}/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        body = json.load(r)
    out = body["choices"][0]["message"]["content"]
    if "</think>" in out:
        out = out.split("</think>", 1)[1].strip()
    return out


def pi_call(
    prompt: str,
    model: str = "tokenrouter/MiniMax-M3",
    system: Optional[str] = None,
    timeout: int = 120,
) -> str:
    provider, model_name = _provider_model(model)
    if _pi_available():
        cmd = ["pi", "--provider", provider, "--model", model_name, "--print", prompt]
        if system:
            cmd += ["--system", system]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"pi timed out after {timeout}s")

    # Fallback: direct API for tokenrouter models
    if provider == "tokenrouter":
        return _direct_tokenrouter(prompt, model_name, system, timeout)

    raise RuntimeError(f"pi not available and no direct fallback for provider={provider}")


async def pi_async(
    prompt: str,
    model: str = "tokenrouter/MiniMax-M3",
    system: Optional[str] = None,
    timeout: int = 120,
) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: pi_call(prompt, model, system, timeout))
