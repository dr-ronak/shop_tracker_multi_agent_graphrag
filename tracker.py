"""Snapshot store so shops can be tracked over time (rating / review / status changes)."""
import json
import time
from pathlib import Path

FILE = Path("data/tracking.json")


def _load() -> dict:
    return json.loads(FILE.read_text("utf-8")) if FILE.exists() else {}


def save_snapshot(key: str, shops: list[dict]):
    FILE.parent.mkdir(exist_ok=True)
    db = _load()
    db.setdefault(key, []).append({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "shops": [{k: s.get(k) for k in ("place_id", "title", "rating", "reviews", "open_state")} for s in shops],
    })
    FILE.write_text(json.dumps(db, indent=2), "utf-8")


def history(key: str) -> list[dict]:
    return _load().get(key, [])


def diff_last_two(key: str) -> list[dict]:
    h = history(key)
    if len(h) < 2:
        return []
    old = {s["place_id"]: s for s in h[-2]["shops"]}
    changes = []
    for s in h[-1]["shops"]:
        o = old.get(s["place_id"])
        if not o:
            changes.append({"shop": s["title"], "change": "NEW in results"})
            continue
        for f in ("rating", "reviews", "open_state"):
            if o.get(f) != s.get(f):
                changes.append({"shop": s["title"], "change": f"{f}: {o.get(f)} -> {s.get(f)}"})
    gone = set(old) - {s["place_id"] for s in h[-1]["shops"]}
    changes += [{"shop": old[g]["title"], "change": "DROPPED from results"} for g in gone]
    return changes