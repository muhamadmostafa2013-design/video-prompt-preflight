from __future__ import annotations

from dataclasses import dataclass, asdict

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
    total = sum(float(e.get("seconds", 0) or 0) for e in timeline if isinstance(e, dict))
    arabic = str((scene.get("spoken") or {}).get("arabic", ""))
    wc = word_count(arabic)
    # Conservative natural short-form Egyptian Arabic pacing baseline.
    speech_seconds = wc / 2.7 if wc else 0.0
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
