from __future__ import annotations

from dataclasses import asdict, dataclass

from .text import word_count


@dataclass
class Simulation:
    duration_seconds: float
    timeline_seconds: float
    idle_seconds: float
    event_count: int
    screen_text_items: int
    spoken_words: int
    estimated_speech_seconds: float
    speech_utilization: float
    event_rate_per_10s: float
    status: str

    def to_dict(self):
        return asdict(self)


def simulate_scene(scene: dict) -> Simulation:
    duration = float(scene.get("duration_seconds", 10) or 10)
    timeline = scene.get("timeline", []) or []
    total = 0.0
    for event in timeline:
        if not isinstance(event, dict):
            continue
        if "start" in event:
            start = float(event["start"])
            total = max(total, float(event.get("end", start + float(event.get("seconds", 0)))))
        else:
            total += float(event.get("seconds", 0) or 0)
    spoken = scene.get("spoken") or {}
    if not isinstance(spoken, dict):
        spoken = {}
    segments = spoken.get("segments") or []
    if not isinstance(segments, list):
        segments = []
    valid_segments = [item for item in segments if isinstance(item, dict)
                      and isinstance(item.get("text"), str) and item["text"].strip()]
    # Exact dialogue is tracked per language, not just the Arabic narrator.
    # Rates are screening heuristics, not a guarantee of natural TTS speed.
    speeds = {"ar": 2.7, "de": 2.4, "en": 2.6, "und": 2.4}
    wc = 0
    speech_seconds = 0.0
    seen: set[str] = set()
    for item in valid_segments:
        line = item["text"].strip()
        if line in seen:
            continue
        seen.add(line)
        count = word_count(line)
        wc += count
        speech_seconds += count / speeds.get(str(item.get("language")), 2.4)
    arabic = str(spoken.get("arabic", "") or "")
    if arabic and arabic not in seen:
        count = word_count(arabic)
        wc += count
        speech_seconds += count / 2.7
    utilization = speech_seconds / duration if duration else 1.0
    event_count = len(timeline)
    event_rate = event_count / duration * 10 if duration else float("inf")

    status = "comfortable"
    if total > duration + 0.05 or utilization > 1.0:
        status = "overflow"
    elif utilization > 0.86 or event_rate > 6:
        status = "tight"

    return Simulation(
        duration_seconds=duration,
        timeline_seconds=round(total, 3),
        idle_seconds=round(max(0.0, duration - total), 3),
        event_count=event_count,
        screen_text_items=len(scene.get("screen_text", []) or []),
        spoken_words=wc,
        estimated_speech_seconds=round(speech_seconds, 2),
        speech_utilization=round(utilization, 3),
        event_rate_per_10s=round(event_rate, 2),
        status=status,
    )
