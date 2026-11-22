"""AI Prompt Director: deterministic, local-only final pre-generation gates.

A pass indicates that specified constraints were checked; it NEVER certifies
unrestricted German grammar, native pronunciation, audio or video accuracy.
"""
from __future__ import annotations

import re
from typing import Any

from .german_music_qa import KNOWN_ARTICLES

_LEVELS = {"pre-a1", "a1", "a2", "b1", "b2", "c1", "c2"}
_ARTICLES = re.compile(r"(?<!\w)(der|die|das)\s+([a-zäöüß]+)\b", re.IGNORECASE)
_CONFLICT = re.compile(
    r"\b(?:add|include|generate|display|show)\s+(?:automatic\s+)?(?:subtitles?|captions?)\b",
    re.IGNORECASE,
)
_RECAST = re.compile(r"\b(?:different|new|replace|switch)\s+(?:actors?|cast|presenters?)\b",
                     re.IGNORECASE)


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


def _is_text(value: Any, limit: int = 500) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= limit


def _phrases(value: Any) -> bool:
    return (isinstance(value, list) and 1 <= len(value) <= 20 and
            all(_is_text(item, 160) for item in value))


def _age_valid(value: Any) -> bool:
    return (isinstance(value, list) and len(value) == 2 and
            all(type(x) is int and 3 <= x <= 100 for x in value) and
            value[0] <= value[1])


def review_job(
    job: dict[str, Any], prompts: list[str],
    vpp_results: list[dict[str, Any]] | None = None,
    music_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Review a normalized production job; never send data to an AI provider."""
    findings: list[dict[str, Any]] = []

    def add(stage: str, rule: str, severity: str, message: str, suggestion: str) -> None:
        findings.append({"stage": stage, "rule_id": rule, "severity": severity,
                         "message": message, "suggestion": suggestion})

    if job.get("type") not in {"video", "song"}:
        raise ValueError("Director accepts normalized video or song jobs only.")

    objective = job.get("learning_objective")
    if not _is_text(objective, 280) or len(objective.strip().split()) < 4:
        add("education", "director.objective.missing", "error",
            "A specific, assessable learning objective is required.",
            "Set learning_objective to a specific observable outcome.")
    cefr = job.get("cefr_level")
    if not isinstance(cefr, str) or cefr.casefold() not in _LEVELS:
        add("education", "director.cefr.missing", "error",
            "A valid CEFR level is required.", "Set cefr_level (e.g. A1).")
    ages = job.get("learner_age")
    if not _age_valid(ages):
        add("education", "director.age.missing", "error",
            "Specify a valid learner_age range.", "Example: learner_age: [16, 25].")
    targets = job.get("target_phrases")
    if not _phrases(targets):
        add("education", "director.targets.missing", "error",
            "Provide 1–20 clear German target phrases.",
            "Set target_phrases to a list of exact words or sentences.")
        targets = []

    if job["type"] == "video":
        scenes = job["scenes"]
        if len(prompts) != len(scenes):
            add("compatibility", "director.prompts.count", "error",
                "Prompt count does not match the number of scenes.",
                "Build exactly one prompt for each scene.")
        if len(scenes) > 1:
            cast = job.get("cast")
            if not _phrases(cast):
                add("continuity", "director.cast.missing", "error",
                    "Multi-scene videos need a fixed character list.",
                    "Provide cast: [Student A, Student B].")
                cast = []
            anchor = job.get("continuity_anchor")
            if not _is_text(anchor, 500) or len(anchor.strip()) < 20:
                add("continuity", "director.continuity.missing", "error",
                    "Multi-scene continuity needs a stable visual reference.",
                    "Describe identity, hair, clothes and consistent visual traits.")
        else:
            cast = job.get("cast", [])
            if cast and not _phrases(cast):
                add("continuity", "director.cast.invalid", "error",
                    "Cast must be a short list of names.", "Use a list of 1–20 names.")
                cast = []

        all_dialogue = []
        for index, scene in enumerate(scenes):
            duration = scene["duration_seconds"]
            scene_prompt = scene["prompt"]
            lines = scene.get("expected_dialogue")
            silent = scene.get("silent", False)
            if type(silent) is not bool:
                add("language", "director.silent.invalid", "error",
                    f"Scene {index + 1}: silent must be true or false.",
                    "Use a boolean silent value.")
                silent = False
            if silent and lines:
                add("language", "director.audio.conflict", "error",
                    f"Scene {index + 1}: silence conflicts with declared dialogue.",
                    "Remove dialogue or set silent: false.")
            if not silent and (not isinstance(lines, list) or not lines):
                add("language", "director.dialogue.unspecified", "error",
                    f"Scene {index + 1}: exact spoken dialogue is not declared.",
                    "Provide expected_dialogue with a speaker and exact German text, or silent: true.")
                continue
            if not isinstance(lines, list):
                lines = []
            if len(lines) > 12:
                add("language", "director.dialogue.limit", "error",
                    f"Scene {index + 1}: more than 12 dialogue turns.",
                    "Split the scene to preserve pronunciation and pacing.")
                continue
            words = 0
            for turn in lines:
                if not isinstance(turn, dict):
                    add("language", "director.dialogue.invalid", "error",
                        "Each dialogue turn must have speaker and text.",
                        "Provide a mapping with speaker and text.")
                    continue
                speaker, phrase = turn.get("speaker"), turn.get("text")
                if not _is_text(speaker, 100) or not _is_text(phrase, 400):
                    add("language", "director.dialogue.invalid", "error",
                        "Each dialogue turn needs a short speaker and nonempty text.",
                        "Declare speaker and exact text.")
                    continue
                if cast and _normalized(speaker) not in {_normalized(n) for n in cast}:
                    add("continuity", "director.speaker.not_in_cast", "error",
                        f"Scene {index + 1}: speaker is not in the fixed cast.",
                        "Add the speaker to cast or use an existing cast name.")
                if _normalized(phrase) not in _normalized(scene_prompt):
                    add("language", "director.dialogue.not_in_prompt", "error",
                        f"Scene {index + 1}: declared spoken text differs from the scene prompt.",
                        "Keep the exact approved dialogue in both fields.")
                all_dialogue.append(phrase)
                words += len(phrase.split())
                for article, noun in _ARTICLES.findall(phrase):
                    expected = KNOWN_ARTICLES.get(noun.casefold())
                    if expected and article.casefold() != expected:
                        add("language", "director.article.check", "error",
                            f"Scene {index + 1}: check '{article} {noun}' (expected {expected}).",
                            "Correct the noun/article pair in both dialogue and scene prompt.")
            if words > duration * 3.2:
                add("pacing", "director.speech.overflow", "error",
                    f"Scene {index + 1}: {words} dialogue words in {duration}s are too dense.",
                    "Increase scene length or shorten dialogue.")
            elif words > duration * 2.4:
                add("pacing", "director.speech.tight", "warning",
                    f"Scene {index + 1}: dialogue may be rushed for learners.",
                    "Reduce spoken words or add a pause for comprehension.")
            if _CONFLICT.search(scene_prompt):
                add("compatibility", "director.captions.conflict", "error",
                    f"Scene {index + 1}: requests generated captions despite the postproduction policy.",
                    "Keep subtitles in the editing stage, not in the generator.")
            if _RECAST.search(scene_prompt) and len(scenes) > 1:
                add("continuity", "director.recast", "warning",
                    f"Scene {index + 1}: possible cast change conflicts with continuity.",
                    "Keep character identity consistent or intentionally split the series.")

        transcript = _normalized(" ".join(all_dialogue))
        for target in targets:
            if _normalized(target) not in transcript:
                add("education", "director.target.not_spoken", "error",
                    f"Required target phrase absent from the exact dialogue: {target}",
                    "Include the phrase in expected_dialogue, or remove the target.")
        for idx, result in enumerate(vpp_results or []):
            if not result.get("passed", False):
                add("vpp", "director.vpp.blocked", "error",
                    f"Existing VPP Triple Verify blocked scene {idx + 1}.",
                    "Resolve the underlying VPP findings before generation.")
        if len(vpp_results or []) != len(scenes):
            add("vpp", "director.vpp.missing", "error",
                "Not all scenes have a VPP Triple Verify report.",
                "Run VPP for every scene.")

    else:
        song = job.get("song_spec", {})
        qa = music_report or {}
        if not qa.get("passed", False):
            add("music", "director.music.blocked", "error",
                "German Educational Music QA did not pass.",
                "Fix all blocking Music QA findings.")
        elif qa.get("decision") == "review":
            add("music", "director.music.review", "warning",
                "Music QA produced advisory findings.",
                "Review Music QA issues before allowing generation.")
        if cefr and isinstance(cefr, str) and cefr.casefold() != str(song.get("cefr", "")).casefold():
            add("education", "director.cefr.mismatch", "error",
                "Song spec CEFR differs from production CEFR.",
                "Align cefr_level with the song spec.")
        if _age_valid(ages) and ages != song.get("age_range"):
            add("education", "director.age.mismatch", "error",
                "Learner ages differ from the song age range.",
                "Align learner_age with song_spec.age_range.")
        lyrics = _normalized(song.get("lyrics", "") if isinstance(song.get("lyrics"), str) else "")
        for target in targets:
            if _normalized(target) not in lyrics:
                add("education", "director.target.not_sung", "error",
                    f"Required target phrase missing from exact lyrics: {target}",
                    "Include it in the approved lyrics.")

    stages = ["education", "language", "pacing", "continuity",
              "compatibility", "vpp", "music"]
    stage_reports = []
    for stage in stages:
        items = [item for item in findings if item["stage"] == stage]
        state = ("blocked" if any(f["severity"] == "error" for f in items)
                 else "needs_revision" if items else "passed")
        stage_reports.append({"stage": stage, "status": state, "findings": items})
    blocked = any(item["severity"] == "error" for item in findings)
    warnings = any(item["severity"] == "warning" for item in findings)
    decision = "blocked" if blocked else "needs_revision" if warnings else "ready_for_generation"
    return {
        "module": "AI Prompt Director",
        "decision": decision, "ready_for_generation": decision == "ready_for_generation",
        "provider": "Gemini Omni" if job["type"] == "video" else "Gemini Lyria",
        "stages": stage_reports, "findings": findings,
        "reviewed_prompt_count": len(prompts),
        "manual_post_generation_checks": [
            "Listen for correct German pronunciation and compare every spoken word with the approved script.",
            "Check visible text, real speaker identity, gestures, scene continuity and timing.",
            "Confirm age/CEFR suitability with a German teacher before publication.",
            "Review music/visual originality, rights and generated-media safety.",
        ],
        "limitation": (
            "Local rules do not certify full German grammar, teaching accuracy, "
            "model compliance, actual audio or final video quality."
        ),
    }
