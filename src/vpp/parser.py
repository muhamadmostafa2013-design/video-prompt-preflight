from __future__ import annotations

import re
from dataclasses import dataclass, field

from .text import contains_arabic


_DURATION_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:[-–—]\s*)?(?:seconds?|secs?|sec|ثانية|ثواني)\b", re.I)
_ASPECT_RE = re.compile(r"\b(9\s*:\s*16|16\s*:\s*9|1\s*:\s*1|4\s*:\s*5)\b")
_RANGE_RE = re.compile(r"(?P<start>\d+(?:\.\d+)?)\s*[-–—]\s*(?P<end>\d+(?:\.\d+)?)\s*s\b", re.I)
_QUOTED_RE = re.compile(r'["“”](.*?)["“”]')

_MARKERS = {
    "on screen", "on-screen", "screen text", "display", "show", "text appears",
    "final screen", "title", "on screen title", "visual text"
}

_STOP_PREFIXES = (
    "create ", "use ", "do ", "don't ", "do not ", "keep ", "avoid ", "make ",
    "presenter ", "camera ", "visual ", "animation ", "spoken ", "important",
    "highlight ", "end ", "start ", "same ", "no ", "never ", "only ", "then ",
    "pause ", "show ", "display ", "transform ", "vertical ", "duration", "format"
)


def _clean_line(line: str) -> str:
    line = line.strip()
    line = re.sub(r"^(?:[-*•]\s+)", "", line)
    line = re.sub(r"\s+", " ", line)
    return line.strip()


def _looks_like_exact_text(line: str) -> bool:
    if not line or len(line) > 80:
        return False
    lower = line.lower()
    if lower.startswith(_STOP_PREFIXES):
        return False
    if line.endswith(":"):
        return False
    # Exact screen text is usually short and not a full instruction sentence.
    words = line.split()
    if len(words) > 8:
        return False
    if any(ch in line for ch in "{}[]"):
        return False
    return bool(re.search(r"[A-Za-zÄÖÜäöüß]", line) or contains_arabic(line))


def _extract_arabic_spoken(text: str) -> str:
    candidates: list[str] = []
    for q in _QUOTED_RE.findall(text):
        if contains_arabic(q):
            candidates.append(q.strip())
    if candidates:
        return max(candidates, key=len)

    lines = text.splitlines()
    capture = False
    buf: list[str] = []
    for raw in lines:
        line = _clean_line(raw)
        low = line.lower()
        if any(key in low for key in ("spoken arabic", "arabic dialogue", "الكلام", "النص المنطوق")):
            capture = True
            after = line.split(":", 1)[1].strip() if ":" in line else ""
            if after and contains_arabic(after):
                buf.append(after.strip('"“”'))
            continue
        if capture:
            if not line:
                if buf:
                    break
                continue
            if contains_arabic(line):
                buf.append(line.strip('"“”'))
            elif buf:
                break
    return " ".join(buf).strip()


def _extract_screen_text(text: str) -> list[str]:
    lines = text.splitlines()
    out: list[str] = []
    capture = False
    capture_budget = 8

    for raw in lines:
        line = _clean_line(raw)
        low = line.lower()
        if not line:
            if capture:
                capture_budget -= 1
                if capture_budget <= 0:
                    capture = False
            continue

        marker_hit = any(m in low for m in _MARKERS)
        if capture and line.endswith(":") and not marker_hit:
            capture = False
            continue
        if marker_hit and (line.endswith(":") or low in _MARKERS or low.startswith(tuple(_MARKERS))):
            capture = True
            capture_budget = 8
            # Handle inline exact text: On screen: ver-
            if ":" in line:
                inline = line.split(":", 1)[1].strip().strip('"“”')
                if _looks_like_exact_text(inline):
                    out.append(inline)
            continue

        if capture:
            capture_budget -= 1
            candidate = line.strip('"“”')
            # Ignore arrows-only lines but preserve text containing arrows.
            if _looks_like_exact_text(candidate):
                out.append(candidate)
            if capture_budget <= 0 or low.startswith(_STOP_PREFIXES):
                capture = False

    # Quoted non-Arabic strings explicitly following screen/display language.
    for m in re.finditer(r"(?:on[- ]screen|display|show|text)\s*(?:text)?\s*[:=]?\s*[\"“]([^\"”]+)[\"”]", text, re.I):
        value = m.group(1).strip()
        if value and not contains_arabic(value):
            out.append(value)

    # Stable de-duplication.
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in out:
        item = item.rstrip(".")
        if item not in seen:
            seen.add(item)
            cleaned.append(item)
    return cleaned


def _extract_timeline(text: str, duration: float) -> list[dict]:
    events: list[dict] = []
    lines = text.splitlines()
    for raw in lines:
        line = _clean_line(raw)
        m = _RANGE_RE.search(line)
        if not m:
            continue
        start = float(m.group("start"))
        end = float(m.group("end"))
        if end <= start:
            continue
        action = line[m.end():].lstrip(": -–—").strip()
        if not action:
            action = "unspecified action"
        events.append({"seconds": round(end - start, 3), "action": action})
    return events


def parse_prompt(text: str) -> dict:
    """Heuristically convert a free-form video prompt into a Scene Spec.

    This parser is deterministic. It intentionally favors conservative extraction over
    inventing missing semantic content.
    """
    durations = [float(x) for x in _DURATION_RE.findall(text)]
    duration = durations[0] if durations else 10.0
    aspect_match = _ASPECT_RE.search(text)
    aspect = aspect_match.group(1).replace(" ", "") if aspect_match else "9:16"

    lower = text.lower()
    no_arabic = bool(re.search(r"(?:no|do not|don't|without)\s+(?:any\s+)?arabic\s+(?:text|writing|subtitles?)", lower))
    no_subtitles = bool(re.search(r"(?:no|do not|don't|without)\s+(?:automatic\s+)?subtitles?", lower))
    no_music = bool(re.search(r"(?:no|without|do not use|don't use)\s+(?:background\s+)?music", lower))
    presenter_arabic_only = bool(re.search(r"presenter[^.\n]{0,80}(?:arabic only|speaks?[^.\n]{0,30}arabic)", lower))
    german_forbidden = bool(re.search(r"presenter[^.\n]{0,100}(?:must not|do not|don't)[^.\n]{0,50}pronounce[^.\n]{0,40}german", lower))
    if german_forbidden:
        presenter_arabic_only = True
    same_presenter = "same presenter" in lower or "same male presenter" in lower

    spoken_arabic = _extract_arabic_spoken(text)
    screen_text = _extract_screen_text(text)
    timeline = _extract_timeline(text, duration)

    style = []
    for phrase in (
        "premium educational short", "dark modern studio", "warm cinematic lighting",
        "cinematic", "modern educational", "vertical educational video", "same Egyptian male presenter"
    ):
        if phrase.lower() in lower and phrase not in style:
            style.append(phrase)

    scene = {
        "name": "Imported free-form prompt",
        "aspect_ratio": aspect,
        "duration_seconds": duration,
        "style": style,
        "spoken": {"arabic": spoken_arabic, "german_by_presenter": []},
        "screen_text": screen_text,
        "text_whitelist": list(screen_text),
        "timeline": timeline,
        "rules": {
            "no_arabic_on_screen": no_arabic,
            "no_auto_subtitles": no_subtitles,
            "no_background_music": no_music,
            "presenter_arabic_only": presenter_arabic_only,
            "same_presenter": same_presenter,
            "max_screen_text_items": 6,
            "max_events_per_10s": 5,
            "max_spoken_words_per_second": 2.7,
        },
        "forbidden": [],
        "source_prompt": text,
        "parse_meta": {
            "duration_mentions": durations,
            "parser": "deterministic-v0.2",
        },
    }
    return scene
