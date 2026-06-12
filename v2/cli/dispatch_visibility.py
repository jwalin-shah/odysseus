"""P7: dispatch events must be queryable, not just log-dumped.

Every miner/worker dispatch is appended as one JSON line; the surface
exposes recency and per-workpack queries so 'fire-and-forget' dispatches
stay observable.
"""
import json
import os
import time

EVENTS_FILE = os.environ.get(
    "ODY_DISPATCH_EVENTS", "/tmp/ody_dispatch_events.jsonl"
)


def record_dispatch(workpack_id, role, provider, model, scope):
    event = {
        "ts": time.time(),
        "workpack_id": workpack_id,
        "role": role,
        "provider": provider,
        "model": model,
        "scope": scope,
    }
    with open(EVENTS_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")
    return event


def _load_events():
    if not os.path.exists(EVENTS_FILE):
        return []
    events = []
    with open(EVENTS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except ValueError:
                continue
    return events


class TaskVisibility:
    """Query surface over the dispatch event log."""

    @staticmethod
    def recent_dispatches(limit=50):
        events = _load_events()
        return sorted(events, key=lambda e: e["ts"], reverse=True)[:limit]

    @staticmethod
    def by_workpack(workpack_id):
        return [e for e in _load_events() if e["workpack_id"] == workpack_id]
