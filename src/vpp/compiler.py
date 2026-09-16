from __future__ import annotations


def compile_scene(scene: dict) -> str:
    """Compile a structured scene into a compact, generator-friendly prompt."""
    lines: list[str] = []
    title = scene.get("name", "Scene")
    duration = scene.get("duration_seconds", 10)
    aspect = scene.get("aspect_ratio", "9:16")
    style = scene.get("style", []) or []
    screen_text = scene.get("screen_text", []) or []
    timeline = scene.get("timeline", []) or []
    spoken = scene.get("spoken", {}) or {}
    rules = scene.get("rules", {}) or {}
    forbidden = scene.get("forbidden", []) or []

    lines.append(f"SCENE: {title}")
    lines.append(f"FORMAT: vertical {aspect}; exact duration {duration}s")
    if style:
        lines.append("STYLE: " + "; ".join(map(str, style)))

    arabic = spoken.get("arabic")
    if arabic:
        lines.append(f'ARABIC AUDIO ONLY: "{arabic}"')
    if rules.get("presenter_arabic_only"):
        lines.append("PRESENTER AUDIO: Egyptian Arabic only; do not pronounce German.")

    if screen_text:
        lines.append("EXACT SCREEN TEXT ONLY: " + " | ".join(map(str, screen_text)))
    if scene.get("text_whitelist"):
        lines.append("TEXT WHITELIST IS STRICT; render no other words or subtitles.")

    if timeline:
        parts = []
        cursor = 0.0
        for event in timeline:
            seconds = float(event.get("seconds", 0))
            start, end = cursor, cursor + seconds
            parts.append(f"{start:g}-{end:g}s {event.get('action', '').strip()}")
            cursor = end
        lines.append("TIMELINE: " + "; ".join(parts))

    constraints = []
    if rules.get("no_arabic_on_screen"):
        constraints.append("no Arabic text on screen")
    if rules.get("no_auto_subtitles"):
        constraints.append("no automatic subtitles")
    if rules.get("no_background_music"):
        constraints.append("no background music")
    if rules.get("same_presenter"):
        constraints.append("same presenter identity, wardrobe, studio and lighting")
    if forbidden:
        constraints.append("never add: " + ", ".join(map(str, forbidden)))
    if constraints:
        lines.append("STRICT: " + "; ".join(constraints) + ".")

    return "\n".join(lines).strip() + "\n"
