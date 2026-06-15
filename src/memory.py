import json
import time
from pathlib import Path
from typing import Optional

MEMORY_DIR = Path.home() / ".odysseus" / "memory"
HOT_LIMIT = 20


class OdysseusMemory:
    def __init__(self, memory_dir: Path = MEMORY_DIR):
        self._dir = memory_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._hot_turns: list[dict] = []
        self._hot_snapshots: dict[str, list] = {}

    def record_turn(self, role: str, content: str, intent: dict = None) -> None:
        entry = {"role": role, "content": content, "ts": time.time()}
        if intent:
            entry["intent"] = intent
        self._hot_turns.append(entry)
        if len(self._hot_turns) > HOT_LIMIT:
            self._hot_turns.pop(0)
        self._append("turns", entry)

    def record_inbox_snapshot(self, platform: str, data: list) -> None:
        self._hot_snapshots[platform] = data
        self._append(f"inbox_{platform}", {"ts": time.time(), "data": data})

    def get_recent_turns(self, n: int = 10) -> list[dict]:
        return self._hot_turns[-n:]

    def get_last_snapshot(self, platform: str) -> Optional[list]:
        return self._hot_snapshots.get(platform)

    def search_history(self, query: str) -> list[dict]:
        results = []
        q = query.lower()
        path = self._dir / "turns.jsonl"
        if not path.exists():
            return []
        for line in path.read_text().splitlines():
            try:
                entry = json.loads(line)
                if q in entry.get("content", "").lower():
                    results.append(entry)
            except json.JSONDecodeError:
                pass
        return results[-20:]

    def to_context(self, n: int = 5) -> str:
        lines = []
        for turn in self._hot_turns[-n:]:
            lines.append(f"{turn['role'].upper()}: {turn['content'][:200]}")
        return "\n".join(lines)

    def _append(self, name: str, data: dict) -> None:
        path = self._dir / f"{name}.jsonl"
        with open(path, "a") as f:
            f.write(json.dumps(data) + "\n")
