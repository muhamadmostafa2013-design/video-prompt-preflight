from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAILURES_DIR = ROOT / "failures"


def load_failure_memory() -> list[dict]:
    out = []
    if not FAILURES_DIR.exists():
        return out
    for path in sorted(FAILURES_DIR.glob("*.json")):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue
    return out


def match_failures(scene: dict, provider: str = "generic") -> list[dict]:
    rules = scene.get("rules", {}) or {}
    screen = scene.get("screen_text", []) or []
    spoken = scene.get("spoken", {}) or {}
    matches = []
    for item in load_failure_memory():
        p = item.get("provider", "generic")
        if p not in {"generic", provider}:
            continue
        category = item.get("category")
        triggered = False
        if category == "multilingual_audio":
            triggered = bool(spoken.get("arabic")) and bool(screen)
        elif category == "exact_text":
            triggered = bool(screen)
        if not triggered:
            continue
        matches.append({
            "rule_id": f"memory.{item.get('id', category)}",
            "agent": "Failure Memory",
            "severity": "info",
            "message": f"Related prior failure: {item.get('title', category)}",
            "recommendation": item.get("expected", "Review this failure pattern before generation."),
            "points": 0,
            "sources": [],
        })
    return matches
