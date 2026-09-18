from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FAILURES_DIR = ROOT / "failures"
_MORPH_RE = re.compile(r"\b(?:transform|morph|animate)\b[^\n.;]{0,120}\b(?:into|to)\b", re.I)


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
    screen = scene.get("screen_text", []) or []
    spoken = scene.get("spoken", {}) or {}
    timeline = scene.get("timeline", []) or []
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
        elif category == "exact_text_morph":
            triggered = bool(screen) and any(
                _MORPH_RE.search(str(event.get("action", "")))
                for event in timeline if isinstance(event, dict)
            )
        if not triggered:
            continue
        matches.append({
            "rule_id": f"memory.{item.get('id', category)}",
            "agent": "Failure Memory",
            "severity": item.get("severity", "info"),
            "message": f"Related prior failure: {item.get('title', category)}",
            "recommendation": item.get("expected", "Review this failure pattern before generation."),
            "points": int(item.get("points", 0) or 0),
            "sources": [],
        })
    return matches
