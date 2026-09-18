from __future__ import annotations

import re

from .simulator import simulate_scene

_ACTION_RE = re.compile(r"\b(?:show|display|transform|morph|animate|cut|zoom|move|switch|split|highlight|pause|transition|appear|disappear|turns?|walks?|runs?|drives?|burns?|changes?)\b", re.I)
_NEGATIVE_RE = re.compile(r"\b(?:no|not|never|without|avoid|don't|do not|must not)\b", re.I)
_CAMERA_RE = re.compile(r"\b(?:camera|close[- ]?up|medium shot|wide shot|low[- ]angle|high[- ]angle|pan|tilt|zoom|tracking|locked[- ]?off|locked camera|handheld|dolly|crane|orbit|truck|push in|pull out)\b", re.I)
_CAMERA_MOVE_RE = re.compile(r"\b(?:pan(?:s|ning)?|tilt(?:s|ing)?|zoom(?:s|ing)?|track(?:s|ing)?|dolly|crane|orbit|truck|push(?:es)? in|pull(?:s)? out|pedestal|handheld)\b", re.I)
_STATIC_CAMERA_RE = re.compile(r"\b(?:static shot|static camera|locked[- ]?off|locked camera|stationary camera|fixed camera|tripod)\b", re.I)
_ACTION_DETAIL_RE = re.compile(r"\b(?:action|walk|run|drive|turn|transform|morph|burn|move|gesture|raise|look|speak|say)\w*\b", re.I)
_OBJECT_HINT_RE = re.compile(r"\b(?:two|three|four|multiple|both|between|left of|right of|behind|in front of|next to|together|each)\b", re.I)
_GERMAN_HINT_RE = re.compile(r"[A-Za-zÄÖÜäöüß]+", re.U)
_DIALOGUE_RE = re.compile(r"\b(?:says?|asks?|replies?|shouts?|whispers?|answers?)\b", re.I)
_TEXT_MORPH_RE = re.compile(r"\b(?:transform|morph|animate)\b[^\n.;]{0,120}\b(?:into|to)\b", re.I)
_IMAGE_VIDEO_RE = re.compile(r"\b(?:image[- ]to[- ]video|input image|starting frame|start frame|reference image|first frame)\b", re.I)
_MINIMAX_COMMAND_RE = re.compile(r"\[(?:Truck|Pan|Push|Pull|Pedestal|Tilt|Zoom|Shake|Tracking shot|Static shot)", re.I)
_MULTI_SUBJECT_RE = re.compile(r"\b(five|six|seven|eight|nine|ten|\d+)\s+(?:people|persons|characters|subjects|men|women|children|actors)\b", re.I)


def _subject_count_hint(text: str) -> int:
    words = {"five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
    counts: list[int] = []
    for match in _MULTI_SUBJECT_RE.finditer(text):
        raw = match.group(1).lower()
        try:
            counts.append(int(raw))
        except ValueError:
            counts.append(words.get(raw, 0))
    return max(counts, default=0)


def extract_features(text: str, scene: dict) -> dict:
    sim = simulate_scene(scene)
    low = text.lower()
    actions = len(_ACTION_RE.findall(text))
    negatives = len(_NEGATIVE_RE.findall(text))
    has_camera = bool(_CAMERA_RE.search(text))
    camera_moves = len(_CAMERA_MOVE_RE.findall(text))
    has_action = bool(_ACTION_DETAIL_RE.search(text))
    object_complexity = len(_OBJECT_HINT_RE.findall(low))
    screen = scene.get("screen_text", []) or []
    screen_count = len(screen)
    timeline = scene.get("timeline", []) or []
    timeline_count = len(timeline)
    spoken = scene.get("spoken", {}) or {}
    arabic_audio = bool(str(spoken.get("arabic", "")).strip())
    german_screen = any(bool(_GERMAN_HINT_RE.search(str(x))) for x in screen)
    presenter_arabic_only = bool((scene.get("rules") or {}).get("presenter_arabic_only"))
    exact_text_morph = bool(screen_count and (
        _TEXT_MORPH_RE.search(text)
        or any(_TEXT_MORPH_RE.search(str(event.get("action", ""))) for event in timeline if isinstance(event, dict))
    ))
    stripped = text.lstrip()
    dialogue_cues = len(_DIALOGUE_RE.findall(text))
    return {
        "actions": actions,
        "negatives": negatives,
        "has_camera": has_camera,
        "camera_moves": camera_moves,
        "static_camera": bool(_STATIC_CAMERA_RE.search(text)),
        "has_action": has_action,
        "object_complexity": object_complexity,
        "screen_text_count": screen_count,
        "exact_text_present": screen_count > 0,
        "timeline_count": timeline_count,
        "multi_shot": timeline_count >= 2 or bool(re.search(r"\b(?:shot|scene)\s*#?\s*\d+\b", text, re.I)),
        "arabic_audio": arabic_audio,
        "german_screen": german_screen,
        "presenter_arabic_only": presenter_arabic_only,
        "exact_text_morph": exact_text_morph,
        "dialogue_cues": dialogue_cues,
        "multi_speaker_dialogue": dialogue_cues >= 2,
        "json_like": stripped.startswith("{") or stripped.startswith("["),
        "image_to_video_hint": bool(_IMAGE_VIDEO_RE.search(text)),
        "minimax_camera_command": bool(_MINIMAX_COMMAND_RE.search(text)),
        "high_motion_hint": "--motion high" in low or "high motion" in low,
        "subject_count_hint": _subject_count_hint(text),
        "duration": float(scene.get("duration_seconds", 10) or 10),
        "simulation_status": sim.status,
        "speech_utilization": sim.speech_utilization,
        "event_rate_per_10s": sim.event_rate_per_10s,
    }
