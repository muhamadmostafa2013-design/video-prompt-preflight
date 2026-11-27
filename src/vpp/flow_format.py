"""Opt-in documented format checks for Google Flow's Veo 3.1 Lite UI."""

from .models import Finding

FLOW_VEO_LITE_TEXT = "flow-veo-3.1-lite-text-to-video"


def flow_veo_lite_text_findings(scene: dict) -> list[Finding]:
    """Check explicit duration and ratio only; this is not a live capability check."""
    if not isinstance(scene, dict):
        return []

    parse_meta = scene.get("parse_meta")
    if not isinstance(parse_meta, dict):
        parse_meta = {}
    findings = []
    duration = scene.get("duration_seconds")
    if (
        parse_meta.get("duration_explicit") is False
        or isinstance(duration, bool)
        or not isinstance(duration, (int, float))
        or duration not in (4, 6, 8)
    ):
        findings.append(Finding(
            "target.flow_veo_lite.duration", "error",
            "Google Flow Veo 3.1 Lite text-to-video requires an explicit 4s, 6s or 8s duration.",
            "Set one of those durations and adjust the timeline to match.", 30,
        ))
    aspect = scene.get("aspect_ratio")
    if parse_meta.get("aspect_explicit") is False or aspect not in ("9:16", "16:9"):
        findings.append(Finding(
            "target.flow_veo_lite.aspect_ratio", "error",
            "Google Flow Veo 3.1 Lite text-to-video requires explicit 9:16 or 16:9.",
            'Set aspect_ratio to "9:16" (portrait) or "16:9" (landscape).', 30,
        ))
    return findings
