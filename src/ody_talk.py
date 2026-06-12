#!/usr/bin/env python3
"""ody talk: terminal client for the odysseus app chat agent (M3 + tools).

Same brain as the web UI — dispatch_mission, list_missions, web, documents —
but in the terminal. Session persists across invocations.

Usage:
  ody talk "dispatch a worker to fix X, then check the result"
  ody talk --new "..."     # start a fresh session
"""
import json
import os
import sys
import urllib.parse
import urllib.request

PORT = int(os.environ.get("ODYSSEUS_PORT", os.environ.get("APP_PORT", "7860")))
BASE = f"http://127.0.0.1:{PORT}"
CACHE = os.path.expanduser("~/.cache/ody-talk-session")


def _post(path, data, form=False, timeout=300):
    if form:
        body = urllib.parse.urlencode(data).encode()
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
    else:
        body = json.dumps(data).encode()
        headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(f"{BASE}{path}", data=body, headers=headers)
    return urllib.request.urlopen(req, timeout=timeout)


def get_session(new=False):
    if not new and os.path.exists(CACHE):
        return open(CACHE).read().strip()
    with urllib.request.urlopen(f"{BASE}/api/default-chat", timeout=10) as r:
        ep = json.load(r)
    with _post("/api/session", {"name": "ody-talk", "endpoint_id": ep["endpoint_id"],
               "endpoint_url": ep["endpoint_url"], "model": ep["model"]},
               form=True) as r:
        sid = json.load(r)["id"]
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    open(CACHE, "w").write(sid)
    return sid


def talk(message, sid):
    resp = _post("/api/chat_stream",
                 {"message": message, "session": sid, "mode": "agent"}, form=True)
    answer = []
    for raw in resp:
        line = raw.decode(errors="replace").strip()
        if not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break
        try:
            ev = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if "delta" in ev:  # content chunks are untyped {"delta": "..."}
            answer.append(ev["delta"])
            print(ev["delta"], end="", flush=True)
        elif "tool" in str(ev.get("type", "")):
            print(f"\n[{ev.get('type')}] {ev.get('tool', ev.get('name', ''))}",
                  file=sys.stderr)
    text = "".join(answer)
    if "</think>" in text:  # don't drown the terminal in reasoning
        text = text.split("</think>")[-1].strip()
        print("\n--- answer ---\n" + text)
    print()


def repl(sid):
    try:
        import readline  # noqa: F401  (arrow keys / history)
    except ImportError:
        pass
    print("[ody talk] interactive — /new = fresh session, /quit or Ctrl-D to exit")
    while True:
        try:
            msg = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not msg:
            continue
        if msg in ("/quit", "/exit", "q"):
            return 0
        if msg == "/new":
            sid = get_session(new=True)
            print("[ody talk] new session")
            continue
        try:
            talk(msg, sid)
        except Exception as e:
            print(f"[ody talk] error: {e} (is the app up? try: ody status)",
                  file=sys.stderr)


def main(argv=None):
    args = list(argv if argv is not None else sys.argv[1:])
    new = "--new" in args
    if new:
        args.remove("--new")
    sid = get_session(new=new)
    if not args:
        if sys.stdin.isatty():
            return repl(sid)
        print(__doc__)
        return 1
    talk(" ".join(args), sid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
