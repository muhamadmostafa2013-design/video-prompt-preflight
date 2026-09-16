from __future__ import annotations

from .compiler import compile_scene
from .fixer import auto_fix_scene
from .prompt_analyzer import analyze_prompt
from .analyzer import analyze_scene


_AMBIGUOUS_CONFLICTS = {
    "prompt.duration.conflict",
    "prompt.music.conflict",
    "prompt.subtitle.conflict",
    "prompt.audio.conflict",
}


def optimize_prompt(text: str) -> dict:
    """Deterministically parse, preflight, safely fix and compile a free-form prompt.

    The optimizer never claims ambiguous semantic choices are certain. It can produce a
    constrained candidate while marking decisions that should be reviewed by a human.
    """
    scene, before = analyze_prompt(text)
    fixed = auto_fix_scene(scene)
    fixed["text_whitelist"] = list(fixed.get("screen_text", []) or [])
    optimized = compile_scene(fixed)
    after = analyze_scene(fixed)

    conflict_ids = [f.rule_id for f in before.findings if f.rule_id in _AMBIGUOUS_CONFLICTS]
    decisions: list[str] = []
    if "prompt.duration.conflict" in conflict_ids:
        decisions.append(f"Kept the first explicit duration mention: {fixed.get('duration_seconds')}s.")
    if "prompt.music.conflict" in conflict_ids:
        decisions.append("Applied the stricter audio constraint: no background music.")
    if "prompt.subtitle.conflict" in conflict_ids:
        decisions.append("Applied the stricter text constraint: no automatic subtitles.")
    if "prompt.audio.conflict" in conflict_ids:
        decisions.append("Applied the stricter presenter constraint: presenter does not pronounce German.")

    return {
        "scene": fixed,
        "before": before.to_dict(),
        "after": after.to_dict(),
        "optimized_prompt": optimized,
        "requires_review": bool(conflict_ids),
        "decisions": decisions,
    }
