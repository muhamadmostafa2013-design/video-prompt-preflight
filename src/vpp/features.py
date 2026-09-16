from __future__ import annotations

import re

from .simulator import simulate_scene

_ACTION_RE = re.compile(r"\b(?:show|display|transform|morph|animate|cut|zoom|move|switch|split|highlight|pause|transition|appear|disappear|turns?|walks?|runs?|drives?|burns?|changes?)\b", re.I)
_NEGATIVE_RE = re.compile(r"\b(?:no|not|never|without|avoid|don't|do not|must not)\b", re.I)
_CAMERA_RE = re.compile(r"\b(?:camera|close[- ]?up|medium shot|wide shot|low[- ]angle|high[- ]angle|pan|tilt|zoom|tracking|locked camera|handheld)\b", re.I)
_ACTION_DETAIL_RE = re.compile(r"\b(?:action|walk|run|drive|turn|transform|morph|burn|move|gesture|raise|look|speak|say)\w*\b", re.I)
_OBJECT_HINT_RE = re.compile(r"\b(?:two|three|four|multiple|both|between|left of|right of|behind|in front of|next to|together|each)\b", re.I)
_GERMAN_HINT_RE = re.compile(r"[A-Za-zÄÖÜäöüß]+", re.U)
_TEXT_MORPH_RE = re.compile(r"\b(?:transform|morph|animate)\b[^\n.;]{0,120}\b(?:into|to)\b", re.I)


def extract_features(text: str, scene: dict) -> dict:
    sim = simulate_scene(scene)
    low = text.lower()
    actions = len(_ACTION_RE.findall(text))
    negatives = len(_NEGATIVE_RE.findall(text))
    has_camera = bool(_CAMERA_RE.search(text))
    has_action = bool(_ACTION_DETAIL_RE.search(text))
    object_complexity = len(_OBJECT_HINT_RE.findall(low))
    screen_count = len(scene.get("screen_text", []) or [])
    timeline = scene.get("timeline", []) or []
    timeline_count = len(timeline)
    spoken = scene.get("spoken", {}) or {}
    arabic_audio = bool(str(spoken.get("arabic", "")).strip())
    german_screen = any(bool(_GERMAN_HINT_RE.search(str(x))) for x in scene.get("screen_text", []) or [])
    presenter_arabic_only = bool((scene.get("rules") or {}).get("presenter_arabic_only"))
    exact_text_morph = bool(screen_count and (
        _TEXT_MORPH_RE.search(text)
        or any(_TEXT_MORPH_RE.search(str(event.get("action", ""))) for event in timeline if isinstance(event, dict))
    ))
    return {
        "actions": actions,
        "negatives": negatives,
        "has_camera": has_camera,
        "has_action": has_action,
        "object_complexity": object_complexity,
        "screen_text_count": screen_count,
        "timeline_count": timeline_count,
        "arabic_audio": arabic_audio,
        "german_screen": german_screen,
        "presenter_arabic_only": presenter_arabic_only,
        "exact_text_morph": exact_text_morph,
        "duration": float(scene.get("duration_seconds", 10) or 10),
        "simulation_status": sim.status,
        "speech_utilization": sim.speech_utilization,
        "event_rate_per_10s": sim.event_rate_per_10s,
    }
