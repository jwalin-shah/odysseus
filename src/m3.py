#!/usr/bin/env python3
"""m3: direct MiniMax-M3 client over TokenRouter's OpenAI-compatible API.

No agent harness, no opencode — raw chat completions for the analyze/research
lane. M3 never writes code (see .credit-lab/mining/FINDINGS.md); use it for
diagnosis, summaries, triage, and bulk corpus work on the free tier.

Usage:
  m3 "why might a SQLite BEGIN IMMEDIATE deadlock under WAL?"
  echo "long report text" | m3 "summarize this in 5 bullets"
  m3 --model deepseek/deepseek-v4-pro "..."
"""
import argparse
import json
import os
import ssl
import sys
import urllib.request

try:
    import certifi
    SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CTX = ssl.create_default_context()

OPENCODE_JSON = os.path.expanduser("~/.config/opencode/opencode.json")
BASE_URL = "https://api.tokenrouter.com/v1"
DEFAULT_MODEL = "MiniMax-M3"


def api_key():
    key = os.environ.get("TOKENROUTER_API_KEY")
    if key:
        return key
    cfg = json.load(open(OPENCODE_JSON))
    return cfg["provider"]["tokenrouter"]["options"]["apiKey"]


def complete(prompt, model=DEFAULT_MODEL, system=None, max_tokens=65536, timeout=300):
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": prompt})
    req = urllib.request.Request(
        f"{BASE_URL}/chat/completions",
        data=json.dumps({"model": model, "messages": messages,
                         "max_tokens": max_tokens}).encode(),
        headers={"Authorization": f"Bearer {api_key()}",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        body = json.load(r)
    return body["choices"][0]["message"]["content"]


def main(argv=None):
    p = argparse.ArgumentParser(prog="m3", description=__doc__.splitlines()[0])
    p.add_argument("prompt", help="the question/instruction; stdin is appended as context")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--system", default="You are a precise technical analyst. "
                   "You never produce code patches; you diagnose, summarize, and explain.")
    p.add_argument("--max-tokens", type=int, default=65536)
    args = p.parse_args(argv)

    prompt = args.prompt
    if not sys.stdin.isatty():
        stdin = sys.stdin.read().strip()
        if stdin:
            prompt = f"<context>\n{stdin[:120000]}\n</context>\n\n{prompt}"
    print(complete(prompt, model=args.model, system=args.system,
                   max_tokens=args.max_tokens))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
