from __future__ import annotations

from copy import deepcopy
from .text import contains_arabic


def auto_fix_scene(scene: dict) -> dict:
    """Apply safe deterministic fixes only. Never invent semantic content."""
    fixed = deepcopy(scene)
    rules = fixed.setdefault("rules", {})

    if rules.get("no_arabic_on_screen"):
        fixed["screen_text"] = [x for x in fixed.get("screen_text", []) if not contains_arabic(str(x))]

    whitelist = set(fixed.get("text_whitelist", []) or [])
    if whitelist:
        fixed["screen_text"] = [x for x in fixed.get("screen_text", []) if x in whitelist]

    if rules.get("presenter_arabic_only"):
        spoken = fixed.setdefault("spoken", {})
        spoken["german_by_presenter"] = []

    max_items = int(rules.get("max_screen_text_items", 6))
    if len(fixed.get("screen_text", [])) > max_items:
        fixed["screen_text"] = fixed["screen_text"][:max_items]

    return fixed
