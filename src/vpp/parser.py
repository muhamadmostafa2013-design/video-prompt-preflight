from __future__ import annotations

import re

from .text import contains_arabic


_DURATION_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)\s*(?:[-–—]\s*)?(?:seconds?|secs?|sec|ثانية|ثواني)\b", re.I)
_ASPECT_RE = re.compile(r"\b(9\s*:\s*16|16\s*:\s*9|1\s*:\s*1|4\s*:\s*5)\b")
_RANGE_RE = re.compile(r"(?P<start>\d+(?:\.\d+)?)\s*[-–—]\s*(?P<end>\d+(?:\.\d+)?)\s*(?:s\b|seconds?\b|secs?\b)", re.I)
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

        # Only a recognized section heading can begin capture. An ordinary
        # imperative such as "show dramatic sunset" is NOT a text block.
        header = low.split(":", 1)[0].strip()
        marker_hit = header in _MARKERS and (":" in line or low in _MARKERS)
        if capture and line.endswith(":") and not marker_hit:
            capture = False
            continue
        if marker_hit:
            capture = True
            capture_budget = 8
            if ":" in line:
                inline = line.split(":", 1)[1].strip().strip('"“”')
                if _looks_like_exact_text(inline):
                    out.append(inline)
            continue

        if capture:
            capture_budget -= 1
            candidate = line.strip('"“”')
            if _looks_like_exact_text(candidate) and not re.search(
                r"\b(?:lighting|cinematic|camera|background|studio|vertical|portrait|audio|music|subtitles)\b",
                candidate, re.I
            ):
                out.append(candidate)
            if capture_budget <= 0 or low.startswith(_STOP_PREFIXES):
                capture = False

    for m in re.finditer(r"(?:on[- ]screen|display|show|text)\s*(?:text)?\s*[:=]?\s*[\"“]([^\"”]+)[\"”]", text, re.I):
        value = m.group(1).strip()
        if value and not contains_arabic(value):
            out.append(value)

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
    for raw in text.splitlines():
        line = _clean_line(raw)
        m = _RANGE_RE.search(line)
        if not m:
            continue
        start = float(m.group("start"))
        end = float(m.group("end"))
        if end <= start:
            continue
        action = line[m.end():].lstrip(": -–—").strip() or "unspecified action"
        events.append({"start": start, "end": end, "seconds": round(end - start, 3), "action": action})
    return events


def parse_prompt(text: str) -> dict:
    """Heuristically convert a free-form video prompt into a conservative Scene Spec."""
    # Global scene durations must not be confused with individual hold/action times.
    durations = []
    for match in _DURATION_RE.finditer(text):
        # Examine only the local clause: a total-duration phrase earlier in
        # the same line must not turn a later "hold 2 seconds" into a conflict.
        beginning = max(text.rfind("\n", 0, match.start()),
                        text.rfind(".", 0, match.start()),
                        text.rfind(";", 0, match.start()),
                        text.rfind(",", 0, match.start())) + 1
        line_prefix = text[beginning:match.start()].lower()
        end_offsets = [i for sep in ("\n", ".", ";", ",")
                       if (i := text.find(sep, match.end())) >= 0]
        line_suffix = text[match.end():min(end_offsets) if end_offsets else len(text)].lower()
        if re.search(r"\b(?:hold|wait|pause|delay|after|before)\s+(?:for\s+)?$", line_prefix):
            continue
        if re.search(r"\d+\s*[-–—]\s*$", line_prefix):
            continue
        if (re.search(r"\b(?:create|make|generate|video|scene|clip|duration|length|total|entire|whole)\b", line_prefix)
                or re.match(r"\s*(?:long\b|total\b|video\b|clip\b|scene\b)", line_suffix)
                or not line_prefix.strip()):
            durations.append(float(match.group(1)))
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
    same_presenter = bool(re.search(r"same(?:\s+\w+){0,2}\s+presenter", lower))

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

    return {
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
        "parse_meta": {"duration_mentions": durations, "duration_explicit": bool(durations),
                       "aspect_explicit": bool(aspect_match), "parser": "deterministic-v0.5.2"},
    }
