import json
import os
import ssl
import threading
import urllib.request
from typing import Optional

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    _CTX = ssl.create_default_context()

_KEY = os.environ.get("TOKENROUTER_API_KEY", "")
_BASE = "https://api.tokenrouter.com/v1"


def fast_fuse(
    prompt: str,
    model: str = "MiniMax-M3",
    system: Optional[str] = None,
    max_tokens: int = 4000,
) -> str:
    """Single model call — no panel, for latency-sensitive paths (~2s)."""
    msgs = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": prompt})
    req = urllib.request.Request(
        f"{_BASE}/chat/completions",
        data=json.dumps({"model": model, "messages": msgs, "max_tokens": max_tokens}).encode(),
        headers={"Authorization": f"Bearer {_KEY}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60, context=_CTX) as r:
        body = json.load(r)
    out = body["choices"][0]["message"]["content"]
    if "</think>" in out:
        out = out.split("</think>", 1)[1].strip()
    return out


def multi_fast(
    prompts: list[str],
    model: str = "MiniMax-M3",
    system: Optional[str] = None,
    max_tokens: int = 4000,
) -> list[str]:
    """Run multiple prompts in parallel threads, return list of results in same order."""
    results: list[Optional[str]] = [None] * len(prompts)
    errors: list[Optional[Exception]] = [None] * len(prompts)

    def worker(idx: int, prompt: str) -> None:
        try:
            results[idx] = fast_fuse(prompt, model=model, system=system, max_tokens=max_tokens)
        except Exception as e:
            errors[idx] = e
            results[idx] = f"[error: {e}]"

    threads = [threading.Thread(target=worker, args=(i, p)) for i, p in enumerate(prompts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=90)

    return [r or "[timeout]" for r in results]
