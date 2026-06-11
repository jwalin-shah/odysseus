import asyncio
import logging
import httpx
import subprocess
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# --- CONFIG MANAGEMENT ---

def load_miners_config() -> List[Dict[str, Any]]:
    """Load miners config from config/miners.json. Returns empty list if file missing."""
    config_path = Path("config/miners.json")
    if not config_path.exists():
        logger.warning("config/miners.json not found")
        return []
    try:
        with open(config_path) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load miners config: {e}")
        return []

def validate_miner_config(miner: Dict[str, Any]) -> bool:
    """Check that a miner config has required fields."""
    required = {"name", "query", "interval_seconds", "source", "enabled"}
    return all(k in miner for k in required)

# --- CLI & GROUNDING HELPERS ---

def run_cli(cmd_list):
    try:
        result = subprocess.run(cmd_list, capture_output=True, text=True, timeout=120)
        return result.stdout.strip() if result.returncode == 0 else f"Error: {result.stderr}"
    except Exception:
        return ""

async def get_githits_code(query: str):
    logger.info(f"GitHits Code Search: {query}")
    initial = run_cli(["/opt/homebrew/bin/githits", "search", query, "--in", "code", "--limit", "3"])
    if "searchRef:" in initial:
        ref = initial.split("searchRef:")[1].split("\n")[0].strip()
        for _ in range(30):
            await asyncio.sleep(5)
            status = run_cli(["/opt/homebrew/bin/githits", "search-status", ref])
            if "Results ready" in status or "---" in status:
                return status
    return run_cli(["/opt/homebrew/bin/githits", "example", query])

def get_recent_transcripts(limit=50):
    """Pulls the latest user/assistant exchanges from the database."""
    db_path = Path("data/app.db")
    if not db_path.exists(): return "Database not found."
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT s.name, m.role, m.content
            FROM chat_messages m
            JOIN sessions s ON m.session_id = s.id
            ORDER BY m.id DESC LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        conn.close()
        return "\n\n".join([f"[{name}] {role.upper()}: {content[:1000]}" for name, role, content in reversed(rows)])
    except Exception as e:
        return f"Database error: {e}"

def get_agent_histories() -> str:
    """Mine transcripts from all local agent CLI roots, recent files only."""
    roots = [
        Path.home() / ".claude-a" / "projects",
        Path.home() / ".claude-b" / "projects",
        Path.home() / ".claude-p" / "projects",
        Path.home() / ".claude" / "projects",
        Path.home() / ".codex" / "sessions",
        Path.home() / ".codex" / "projects",
    ]

    # Collect JSONL files from all roots
    all_files = []
    for root in roots:
        if not root.exists():
            continue
        try:
            jsonl_files = list(root.glob("**/*.jsonl")) + list(root.glob("**/transcript.json"))
            all_files.extend(jsonl_files)
        except Exception as e:
            logger.debug(f"Failed to glob {root}: {e}")

    # Sort by mtime, take N most recent
    try:
        all_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except:
        pass

    recent_files = all_files[:5]  # N=5 most recent

    # Extract exchanges, label with source, truncate
    exchanges = []
    total_chars = 0
    max_total = 15000

    for fpath in recent_files:
        if total_chars >= max_total:
            break

        source_label = f"[{fpath.parent.parent.name}/{str(fpath)[-8:]}]"

        try:
            with open(fpath) as f:
                for line in f:
                    if total_chars >= max_total:
                        break
                    try:
                        event = json.loads(line.strip())
                    except:
                        continue

                    evt_type = event.get("type", "")
                    if evt_type not in ("user", "assistant"):
                        continue

                    # Extract text
                    content = event.get("content", "")
                    if isinstance(content, list):
                        # Array of {type: "text", text: "..."}
                        text_blocks = [block.get("text", "") for block in content if block.get("type") == "text"]
                        content = " ".join(text_blocks)

                    # Truncate message to 800 chars, add label
                    msg = content[:800] if content else ""
                    if msg:
                        labeled = f"{source_label} {evt_type.upper()}: {msg}"
                        exchanges.append(labeled)
                        total_chars += len(labeled)
        except Exception as e:
            logger.debug(f"Failed to parse {fpath}: {e}")

    if not exchanges:
        return "No agent histories found."

    return "\n\n".join(exchanges[:50])

# --- ADAPTIVE INTELLIGENCE ---

async def get_next_research_step(client, base_url, session_id, current_query, last_report):
    planning_prompt = (
        f"We just finished a research pass for: '{current_query}'.\n\n"
        f"LATEST FINDINGS SUMMARY:\n{last_report[:2000]}\n\n"
        "TASK: Based on these findings, what is the single most important NEXT query we should run "
        "to find even more architectural breakthroughs or solve current system bottlenecks?\n"
        "Respond with ONLY the new query string. No chatter."
    )
    try:
        payload = {"message": planning_prompt, "session": session_id, "model": "MiniMax-M3"}
        res = await client.post(f"{base_url}/api/chat", json=payload, headers={"X-Odysseus-Owner": "admin"})
        if res.status_code == 200:
            new_query = res.json().get("text", "").strip()
            if "\n" in new_query: new_query = new_query.split("\n")[0]
            return new_query.strip("\"' ")
    except Exception as e:
        logger.error(f"Planning failed: {e}")
    return current_query

# --- THE MINER LOOPS ---

async def run_adaptive_miner_loop(name: str, initial_query: str, interval: int, source: str = "githits"):
    """Run an adaptive miner loop with hot-reload support.

    Tracks configured_query separately from current_query to preserve evolution:
    - configured_query: what config says (reloaded each cycle)
    - current_query: evolved query from get_next_research_step (only reset if config changed)
    """
    base_url = "http://127.0.0.1:7860"
    current_query = initial_query
    configured_query = initial_query

    while True:
        try:
            # 1. HOT RELOAD: Check if miner is still enabled and config changed
            miners_config = load_miners_config()
            miner_cfg = next((m for m in miners_config if m["name"] == name), None)

            if not miner_cfg:
                logger.info(f"[{name}] Removed from config, sleeping...")
                await asyncio.sleep(10)
                continue

            if not miner_cfg.get("enabled", False):
                logger.debug(f"[{name}] Disabled in config, sleeping...")
                await asyncio.sleep(10)
                continue

            # If configured query changed, adopt it (reset evolution)
            new_configured_query = miner_cfg.get("query", configured_query)
            new_source = miner_cfg.get("source", source)
            new_interval = miner_cfg.get("interval_seconds", interval)

            if new_configured_query != configured_query:
                logger.info(f"[{name}] Config query changed: {configured_query} -> {new_configured_query}")
                current_query = new_configured_query
                configured_query = new_configured_query

            source = new_source
            interval = new_interval

            logger.info(f"[{name}] Starting adaptive pass for: {current_query}")

            # 2. Grounding Phase
            if source == "githits":
                context = await get_githits_code(current_query)
            elif source == "transcripts":
                context = get_recent_transcripts(100)
            elif source == "agent_histories":
                context = get_agent_histories()
            else:
                context = "General research mode."

            async with httpx.AsyncClient(timeout=600.0) as client:
                # 3. Session Setup
                sessions_res = await client.get(f"{base_url}/api/sessions", headers={"X-Odysseus-Owner": "admin"})
                session_id = next((s["id"] for s in sessions_res.json() if s["name"] == name), None)
                if not session_id:
                    create_res = await client.post(f"{base_url}/api/session", headers={"X-Odysseus-Owner": "admin"},
                        data={"name": name, "model": "MiniMax-M3", "endpoint_id": "dd45625c", "skip_validation": "true"})
                    session_id = create_res.json().get("id")

                # 4. Report Synthesis
                mission_type = {
                    "transcripts": "TRANSCRIPT MINING",
                    "agent_histories": "AGENT HISTORY MINING",
                    "githits": "ARCHITECTURE RESEARCH"
                }.get(source, "RESEARCH")

                report_prompt = (
                    f"### {mission_type} MISSION: {current_query}\n"
                    f"GROUNDED CONTEXT:\n{context}\n\n"
                    "TASK:\n"
                    "1. Decompose patterns, errors, or architectural insights from the data.\n"
                    "2. Write specific Pytest files or 'Memory Rules' to auto-fix or capture these insights.\n"
                    "3. Identify the next 'Unknown' we should investigate.\n"
                    "Report for Jwalin's 1-Surface dashboard."
                )

                payload = {"message": report_prompt, "session": session_id, "model": "MiniMax-M3"}
                res = await client.post(f"{base_url}/api/chat", json=payload, headers={"X-Odysseus-Owner": "admin"})

                if res.status_code == 200:
                    last_report = res.json().get("text", "")
                    # 5. Evolution Phase (only if we haven't just reset to config)
                    new_current_query = await get_next_research_step(client, base_url, session_id, current_query, last_report)
                    current_query = new_current_query
                    logger.info(f"[{name}] Report captured. Next: {current_query}")
                else:
                    logger.error(f"[{name}] Synthesis failed: {res.status_code}")

        except Exception as e:
            logger.error(f"[{name}] Loop error: {e}")
            await asyncio.sleep(300)

        await asyncio.sleep(interval)

async def start_all_miners():
    """Spawns the Persistent Adaptive Knowledge Fleet from config/miners.json.

    Reads miners from config, spawns one loop per miner, and supervises new miner
    spawning every ~60s by checking if new miners were added to config.
    """
    await asyncio.sleep(15)

    active_miners = {}  # name -> task
    last_supervisor_check = 0
    supervisor_interval = 60  # Check every 60s for new miners

    while True:
        try:
            current_time = asyncio.get_event_loop().time() if hasattr(asyncio.get_event_loop(), 'time') else 0

            # Supervisor: every ~60s, check for newly added miners
            if (not last_supervisor_check or current_time - last_supervisor_check >= supervisor_interval) and current_time > 0:
                last_supervisor_check = current_time
                miners_config = load_miners_config()
                configured_names = {m["name"] for m in miners_config if m.get("enabled", False)}

                # Spawn new miners that appeared in config
                for miner_cfg in miners_config:
                    name = miner_cfg.get("name")
                    if not name or not miner_cfg.get("enabled", False):
                        continue

                    if name not in active_miners or not active_miners[name].done():
                        if name not in active_miners:
                            logger.info(f"Spawning miner: {name}")
                            task = asyncio.create_task(
                                run_adaptive_miner_loop(
                                    name,
                                    miner_cfg.get("query", ""),
                                    miner_cfg.get("interval_seconds", 3600),
                                    miner_cfg.get("source", "githits")
                                )
                            )
                            active_miners[name] = task
                    # If task exists but is done, log it and let it be re-spawned on next check
                    elif active_miners[name].done():
                        try:
                            active_miners[name].result()  # Check for exception
                        except asyncio.CancelledError:
                            pass
                        except Exception as e:
                            logger.error(f"Miner {name} task ended with error: {e}")
                        logger.info(f"Re-spawning ended miner: {name}")
                        task = asyncio.create_task(
                            run_adaptive_miner_loop(
                                name,
                                miner_cfg.get("query", ""),
                                miner_cfg.get("interval_seconds", 3600),
                                miner_cfg.get("source", "githits")
                            )
                        )
                        active_miners[name] = task

                # Clean up disabled/removed miners from tracking (they'll self-exit via the loop check)
                to_remove = [n for n in active_miners if n not in configured_names]
                for name in to_remove:
                    logger.info(f"Miner {name} removed from config, will exit on next cycle")
                    # Don't remove from active_miners yet; let the miner loop detect it and exit

            await asyncio.sleep(5)  # Lightweight polling

        except Exception as e:
            logger.error(f"Supervisor error: {e}")
            await asyncio.sleep(10)
