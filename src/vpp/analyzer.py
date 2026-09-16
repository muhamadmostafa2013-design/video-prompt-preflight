from __future__ import annotations

from .models import Finding, Report
from .text import contains_arabic, word_count


def _add(report: Report, rule_id: str, severity: str, message: str, suggestion: str | None, points: int) -> None:
    report.findings.append(Finding(rule_id, severity, message, suggestion, points))


def analyze_scene(scene: dict) -> Report:
    """Analyze a structured scene specification without calling any LLM."""
    report = Report()

    duration = scene.get("duration_seconds")
    if not isinstance(duration, (int, float)) or duration <= 0:
        _add(report, "duration.missing", "error", "A positive duration_seconds value is required.", "Set duration_seconds, e.g. 10.", 30)
    elif duration > 12:
        _add(report, "duration.long", "warning", f"Scene duration is {duration}s.", "For short-form generation, consider splitting the scene.", 8)

    screen_text = scene.get("screen_text", []) or []
    if not isinstance(screen_text, list):
        _add(report, "screen_text.type", "error", "screen_text must be a list of exact strings.", "Convert screen_text to a YAML/JSON list.", 25)
        screen_text = []

    rules = scene.get("rules", {}) or {}
    if rules.get("no_arabic_on_screen", False):
        bad = [x for x in screen_text if contains_arabic(str(x))]
        if bad:
            _add(report, "screen_text.arabic", "error", f"Arabic screen text found: {bad}", "Remove Arabic from screen_text and add it later in editing.", 35)

    max_items = int(rules.get("max_screen_text_items", 6))
    if len(screen_text) > max_items:
        _add(report, "screen_text.crowded", "warning", f"{len(screen_text)} screen-text items requested; limit is {max_items}.", "Reduce simultaneous text or split the scene.", 12)

    whitelist = set(scene.get("text_whitelist", []) or [])
    if whitelist:
        extras = [x for x in screen_text if x not in whitelist]
        if extras:
            _add(report, "screen_text.whitelist", "error", f"Screen text outside whitelist: {extras}", "Use only exact whitelisted strings.", 35)

    events = scene.get("timeline", []) or []
    if duration and isinstance(events, list):
        max_events = int(rules.get("max_events_per_10s", 5)) * max(1, round(float(duration) / 10))
        if len(events) > max_events:
            _add(report, "timeline.overloaded", "warning", f"{len(events)} timeline events may overload a {duration}s scene.", "Reduce actions/transitions or split into another scene.", 15)

        total = 0.0
        for event in events:
            try:
                total += float(event.get("seconds", 0))
            except (TypeError, ValueError, AttributeError):
                _add(report, "timeline.invalid", "error", "Each timeline event needs a numeric seconds value.", "Add seconds to every event.", 25)
                break
        if total and duration and total > float(duration) + 0.05:
            _add(report, "timeline.overflow", "error", f"Timeline totals {total:.1f}s but scene is {duration}s.", "Shorten or remove timeline events.", 35)

    spoken = scene.get("spoken", {}) or {}
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
    prompt_notes = " ".join(str(x) for x in scene.get("notes", []) or [])
    for phrase in forbidden:
        if phrase and phrase.lower() in prompt_notes.lower():
            _add(report, "forbidden.conflict", "error", f"Forbidden instruction appears in notes: {phrase}", "Remove the conflicting instruction.", 30)

    if not report.findings:
        _add(report, "preflight.clean", "info", "No deterministic preflight risks detected.", None, 0)

    return report
