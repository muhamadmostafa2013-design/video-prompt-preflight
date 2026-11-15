from __future__ import annotations

import math
import re

from .models import Finding, Report
from .text import contains_arabic, word_count

_MORPH_RE = re.compile(r"\b(?:transform|morph|animate)\b[^\n.;]{0,120}\b(?:into|to)\b", re.IGNORECASE)
_STABLE_TEXT_RE = re.compile(r"\b(?:show|display|hold|static|keep|present|visible)\b", re.IGNORECASE)


def _add(report: Report, rule_id: str, severity: str, message: str, suggestion: str | None, points: int) -> None:
    report.findings.append(Finding(rule_id, severity, message, suggestion, points))


def analyze_scene(scene: dict) -> Report:
    """Analyze a structured scene specification without calling any LLM."""
    report = Report()
    if not isinstance(scene, dict):
        _add(report, "scene.type", "error", "Scene Spec must be an object.", "Supply a YAML or JSON object.", 40)
        return report

    rules = scene.get("rules", {})
    if rules is None:
        rules = {}
    if not isinstance(rules, dict):
        _add(report, "rules.type", "error", "rules must be a mapping.", "Use a YAML/JSON object for rules.", 35)
        rules = {}
    else:
        rules = dict(rules)  # Analysis must not mutate the original Scene Spec.

    duration = scene.get("duration_seconds")
    try:
        if (isinstance(duration, bool) or not isinstance(duration, (int, float))
                or not math.isfinite(duration) or duration <= 0 or duration > 86400):
            duration = None
    except (OverflowError, TypeError, ValueError):
        duration = None
    if duration is None:
        _add(report, "duration.missing", "error", "A positive duration_seconds value is required.", "Set duration_seconds, e.g. 10.", 30)
    elif duration > 12:
        _add(report, "duration.long", "warning", f"Scene duration is {duration}s.", "For short-form generation, consider splitting the scene.", 8)

    screen_text = scene.get("screen_text", [])
    if screen_text is None:
        screen_text = []
    if not isinstance(screen_text, list) or any(not isinstance(x, str) for x in screen_text):
        _add(report, "screen_text.type", "error", "screen_text must be a list of exact strings.", "Convert screen_text to a YAML/JSON list.", 25)
        screen_text = []

    limits = {"max_screen_text_items": (int, 6), "max_events_per_10s": (int, 5),
              "max_spoken_words_per_second": (float, 2.7)}
    for key, (cast, default) in limits.items():
        try:
            value = cast(rules.get(key, default))
            if isinstance(rules.get(key), bool) or not math.isfinite(value) or value <= 0:
                raise ValueError("invalid rule bound")
        except (ValueError, TypeError, OverflowError):
            _add(report, "rules.invalid", "error", f"Invalid rule setting: {key}.",
                 "Use finite positive numeric limits.", 30)
            rules[key] = default
    if rules.get("no_arabic_on_screen", False):
        bad = [x for x in screen_text if contains_arabic(str(x))]
        if bad:
            _add(report, "screen_text.arabic", "error", f"Arabic screen text found: {bad}", "Remove Arabic from screen_text and add it later in editing.", 35)

    max_items = int(rules.get("max_screen_text_items", 6))
    if len(screen_text) > max_items:
        _add(report, "screen_text.crowded", "warning", f"{len(screen_text)} screen-text items requested; limit is {max_items}.", "Reduce simultaneous text or split the scene.", 12)

    raw_whitelist = scene.get("text_whitelist", [])
    if raw_whitelist is None:
        raw_whitelist = []
    if not isinstance(raw_whitelist, list) or any(not isinstance(x, str) for x in raw_whitelist):
        _add(report, "screen_text.whitelist_type", "error", "text_whitelist must be a list of strings.",
             "Provide only exact text strings.", 35)
        raw_whitelist = []
    whitelist = set(raw_whitelist)
    if whitelist:
        extras = [x for x in screen_text if x not in whitelist]
        if extras:
            _add(report, "screen_text.whitelist", "error", f"Screen text outside whitelist: {extras}", "Use only exact whitelisted strings.", 35)

    events = scene.get("timeline", [])
    if events is None:
        events = []
    if not isinstance(events, list):
        _add(report, "timeline.type", "error", "timeline must be a list of events.",
             "Provide a list of time intervals.", 35)
        events = []
    if duration and isinstance(events, list):
        max_events = int(rules.get("max_events_per_10s", 5)) * max(1, round(float(duration) / 10))
        if len(events) > max_events:
            _add(report, "timeline.overloaded", "warning", f"{len(events)} timeline events may overload a {duration}s scene.", "Reduce actions/transitions or split into another scene.", 15)

        total = 0.0
        previous_end = 0.0
        for event in events:
            try:
                if not isinstance(event, dict):
                    raise ValueError("timeline event must be an object")
                seconds = float(event.get("seconds", 0))
                if "start" in event:
                    start = float(event["start"])
                    end = float(event.get("end", start + seconds))
                    if not all(math.isfinite(x) for x in (start, end, seconds)):
                        raise ValueError("non-finite event interval")
                    if start < 0 or end <= start or seconds <= 0 or abs((end - start) - seconds) > .05:
                        raise ValueError("invalid interval")
                    if start < previous_end - .05:
                        _add(report, "timeline.overlap", "error",
                             f"Timeline overlaps: {start:g}s begins before prior end {previous_end:g}s.",
                             "Use nonoverlapping chronological intervals, or split parallel actions explicitly.", 35)
                    total = max(total, end)
                    previous_end = max(previous_end, end)
                else:
                    if not math.isfinite(seconds) or seconds <= 0:
                        raise ValueError("invalid event length")
                    total += seconds
                    previous_end = total
            except (TypeError, ValueError, AttributeError):
                _add(report, "timeline.invalid", "error", "Each timeline event needs a valid numeric interval.", "Fix each timeline interval.", 25)
                break
        if total and duration and total > float(duration) + 0.05:
            _add(report, "timeline.overflow", "error", f"Timeline totals {total:.1f}s but scene is {duration}s.", "Shorten or remove timeline events.", 35)

        actions = [str(event.get("action", "")) for event in events if isinstance(event, dict)]
        morph_actions = [action for action in actions if _MORPH_RE.search(action)]
        if screen_text and morph_actions:
            _add(
                report,
                "screen_text.morph_risk",
                "warning",
                "Exact on-screen text is being morphed or animated between states; generative video can corrupt letters during the transition.",
                "Use separate static text states with clean hard cuts, or add exact educational text in post-production.",
                22,
            )

        if screen_text:
            missing_stable = []
            for item in screen_text:
                needle = str(item).lower()
                stable = any(needle in action.lower() and _STABLE_TEXT_RE.search(action) for action in actions)
                if not stable:
                    missing_stable.append(str(item))
            if missing_stable:
                _add(
                    report,
                    "screen_text.state_coverage",
                    "warning",
                    "Exact text states are not explicitly held as stable text: " + " | ".join(missing_stable),
                    "Give every required string an explicit show/hold/static state; do not rely on a morph transition to imply the source or target text.",
                    18,
                )

    spoken = scene.get("spoken", {}) or {}
    if not isinstance(spoken, dict):
        _add(report, "spoken.type", "error", "spoken must be an object.",
             "Supply dialogue as structured fields.", 30)
        spoken = {}
    arabic = str(spoken.get("arabic", ""))
    max_wps = float(rules.get("max_spoken_words_per_second", 2.7))
    if duration and arabic:
        wc = word_count(arabic)
        capacity = float(duration) * max_wps
        if wc > capacity:
            _add(report, "speech.too_dense", "warning", f"Arabic dialogue has {wc} words; target capacity is about {int(capacity)} words.", "Shorten dialogue or increase scene duration.", 12)

    if rules.get("presenter_arabic_only", False):
        german_audio = spoken.get("german_by_presenter", []) or []
        if german_audio:
            _add(report, "audio.german_presenter", "error", "German speech is assigned to the Arabic presenter.", "Use pauses and add verified German audio in post-production.", 40)

    forbidden = scene.get("forbidden", []) or []
    if not isinstance(forbidden, list):
        _add(report, "forbidden.type", "error", "forbidden must be a list.", "Provide list of strings.", 25)
        forbidden = []
    raw_notes = scene.get("notes", []) or []
    if isinstance(raw_notes, str):
        raw_notes = [raw_notes]
    prompt_notes = " ".join(str(x) for x in raw_notes) if isinstance(raw_notes, list) else ""
    for phrase in forbidden:
        phrase = str(phrase)
        if phrase and phrase.lower() in prompt_notes.lower():
            _add(report, "forbidden.conflict", "error", f"Forbidden instruction appears in notes: {phrase}", "Remove the conflicting instruction.", 30)

    if not report.findings:
        _add(report, "preflight.clean", "info", "No deterministic preflight risks detected.", None, 0)

    return report
