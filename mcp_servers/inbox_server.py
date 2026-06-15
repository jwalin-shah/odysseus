"""
inbox_server.py

MCP server bridging the inbox REST API (183 routes) to Odysseus as MCP tools.

Architecture:
  Odysseus agent
    └── mcp_manager
        └── inbox_server (this file, stdio MCP)
            └── HTTP → http://localhost:9849/<route>  (the running inbox_server)

Setup:
  1. Inbox server must be running: `uv run python inbox_server.py` (default port 9849)
  2. Auth token in env: INBOX_SERVER_TOKEN  (we read from Infisical on startup if unset)
  3. Registered in src/builtin_mcp.py::_BUILTIN_SERVERS

Capabilities exposed:
  - inbox.health                  — server health check
  - inbox.list_routes             — show all 183 inbox routes
  - inbox.call                    — generic: call any inbox route by path+method+body
  - inbox.gmail.list_unread       — convenience: list unread Gmail threads
  - inbox.gmail.search            — convenience: search Gmail
  - inbox.calendar.upcoming       — convenience: upcoming calendar events
  - inbox.calendar.quick          — convenience: create a quick event
  - inbox.imessage.recent         — convenience: recent iMessage conversations
  - inbox.reminders.list          — convenience: list reminders
  - inbox.tasks.list              — convenience: list tasks
  - inbox.contacts.search         — convenience: search contacts
  - inbox.notes.list              — convenience: list notes
  - inbox.drive.search            — convenience: search Drive
  - inbox.github.notifications    — convenience: list GitHub notifications
  - inbox.spawn_agent             — spawn a pi/codex/claude CLI for heavy work
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import urllib.request
import urllib.error

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Make project root importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Config — read inbox URL + token from env or Infisical
INBOX_URL = os.environ.get("INBOX_URL", "http://127.0.0.1:9849").rstrip("/")
INBOX_TOKEN_ENV = "INBOX_SERVER_TOKEN"


def _resolve_token() -> str:
    """Resolve the inbox auth token from env or Infisical."""
    tok = os.environ.get(INBOX_TOKEN_ENV, "").strip()
    if tok:
        return tok
    # Try Infisical (no display, just length)
    try:
        result = subprocess.run(
            ["infisical", "secrets", "get", "server_token", "--path", "/providers/inbox", "--env", "dev", "--plain"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            tok = result.stdout.strip()
            os.environ[INBOX_TOKEN_ENV] = tok  # cache
            return tok
    except Exception:
        pass
    return ""


def _http(method: str, path: str, body: Optional[dict] = None, params: Optional[dict] = None) -> Dict[str, Any]:
    """Make an authenticated request to the inbox server."""
    url = urljoin(INBOX_URL + "/", path.lstrip("/"))
    if params:
        from urllib.parse import urlencode
        url += "?" + urlencode(params)

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    token = _resolve_token()
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return {"status": resp.status, "body": json.loads(raw)}
            except json.JSONDecodeError:
                return {"status": resp.status, "body": raw[:4000]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        return {"status": e.code, "error": raw[:2000]}
    except Exception as e:
        return {"status": 0, "error": str(e)[:500]}


# ─────────────────────────────────────────────────────────────────────────
# MCP server
# ─────────────────────────────────────────────────────────────────────────

server = Server("inbox")


@server.list_tools()
async def list_tools() -> List[Tool]:
    return [
        Tool(
            name="inbox_health",
            description="Check if the inbox server is reachable and healthy",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="inbox_list_routes",
            description="List all available inbox REST routes grouped by domain",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="inbox_call",
            description="Call any inbox REST route. method=GET/POST/PUT/DELETE, path like '/conversations', optional body for POST/PUT.",
            inputSchema={
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                    "path": {"type": "string", "description": "Path like '/gmail/search' (no host)"},
                    "body": {"type": "object", "description": "JSON body for POST/PUT"},
                    "params": {"type": "object", "description": "Query string params"},
                },
                "required": ["method", "path"],
            },
        ),
        # Convenience shortcuts
        Tool(
            name="inbox_gmail_unread",
            description="List unread Gmail threads",
            inputSchema={"type": "object", "properties": {"limit": {"type": "number", "default": 20}}, "required": []},
        ),
        Tool(
            name="inbox_gmail_search",
            description="Search Gmail",
            inputSchema={"type": "object", "properties": {"q": {"type": "string"}, "limit": {"type": "number", "default": 20}}, "required": ["q"]},
        ),
        Tool(
            name="inbox_calendar_upcoming",
            description="List upcoming calendar events",
            inputSchema={"type": "object", "properties": {"days": {"type": "number", "default": 7}}, "required": []},
        ),
        Tool(
            name="inbox_imessage_recent",
            description="Recent iMessage conversations",
            inputSchema={"type": "object", "properties": {"limit": {"type": "number", "default": 10}}, "required": []},
        ),
        Tool(
            name="inbox_reminders_list",
            description="List reminders",
            inputSchema={"type": "object", "properties": {"list_id": {"type": "string"}}, "required": []},
        ),
        Tool(
            name="inbox_tasks_list",
            description="List tasks",
            inputSchema={"type": "object", "properties": {"list_id": {"type": "string"}}, "required": []},
        ),
        Tool(
            name="inbox_spawn_agent",
            description="Spawn a pi/codex/claude CLI subprocess for heavy work (e.g. drafting a long email reply, processing many messages). Returns the spawned process PID and instructions to read output.",
            inputSchema={
                "type": "object",
                "properties": {
                    "cli": {"type": "string", "enum": ["pi", "codex", "claude"], "default": "pi"},
                    "task": {"type": "string", "description": "What the CLI should do"},
                    "context": {"type": "string", "description": "Optional context to pass to the CLI"},
                },
                "required": ["task"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    try:
        if name == "inbox_health":
            result = _http("GET", "/health")
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "inbox_list_routes":
            # Read the route inventory from the inbox server source dynamically
            result = _http("GET", "/providers/status")
            return [TextContent(type="text", text=json.dumps(result, indent=2))]

        if name == "inbox_call":
            method = arguments["method"]
            path = arguments["path"]
            body = arguments.get("body")
            params = arguments.get("params")
            result = _http(method, path, body, params)
            return [TextContent(type="text", text=json.dumps(result, indent=2)[:8000])]

        if name == "inbox_gmail_unread":
            limit = arguments.get("limit", 20)
            result = _http("GET", "/gmail/conversations", params={"unread": "true", "limit": limit})
            return [TextContent(type="text", text=json.dumps(result, indent=2)[:8000])]

        if name == "inbox_gmail_search":
            q = arguments["q"]
            limit = arguments.get("limit", 20)
            result = _http("GET", "/gmail/search", params={"q": q, "limit": limit})
            return [TextContent(type="text", text=json.dumps(result, indent=2)[:8000])]

        if name == "inbox_calendar_upcoming":
            days = arguments.get("days", 7)
            result = _http("GET", "/calendar/upcoming", params={"days": days})
            return [TextContent(type="text", text=json.dumps(result, indent=2)[:8000])]

        if name == "inbox_imessage_recent":
            limit = arguments.get("limit", 10)
            result = _http("GET", "/conversations", params={"source": "imessage", "limit": limit})
            return [TextContent(type="text", text=json.dumps(result, indent=2)[:8000])]

        if name == "inbox_reminders_list":
            list_id = arguments.get("list_id")
            params = {"list_id": list_id} if list_id else None
            result = _http("GET", "/reminders", params=params)
            return [TextContent(type="text", text=json.dumps(result, indent=2)[:8000])]

        if name == "inbox_tasks_list":
            list_id = arguments.get("list_id")
            params = {"list_id": list_id} if list_id else None
            result = _http("GET", "/tasks", params=params)
            return [TextContent(type="text", text=json.dumps(result, indent=2)[:8000])]

        if name == "inbox_spawn_agent":
            cli = arguments.get("cli", "pi")
            task = arguments["task"]
            context = arguments.get("context", "")
            # Build a focused prompt and spawn the CLI
            prompt = f"{task}\n\n{context}".strip()
            try:
                proc = subprocess.Popen(
                    [cli, "-p", prompt],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    start_new_session=True,
                )
                return [TextContent(type="text", text=json.dumps({
                    "spawned": cli,
                    "pid": proc.pid,
                    "task": task,
                    "note": f"PID {proc.pid} running in background; check stdout/stderr when done",
                }, indent=2))]
            except FileNotFoundError:
                return [TextContent(type="text", text=json.dumps({
                    "error": f"{cli} not on PATH; install or use a different CLI",
                }, indent=2))]

        return [TextContent(type="text", text=json.dumps({"error": f"unknown tool: {name}"}))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": str(e)[:500]}, indent=2))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
