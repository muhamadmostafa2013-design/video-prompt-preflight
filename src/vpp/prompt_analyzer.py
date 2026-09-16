from __future__ import annotations

import re

from .models import Finding, Report
from .parser import parse_prompt
from .analyzer import analyze_scene


def _add(report: Report, rule_id: str, severity: str, message: str, suggestion: str | None, points: int) -> None:
    report.findings.append(Finding(rule_id, severity, message, suggestion, points))


def analyze_prompt(text: str) -> tuple[dict, Report]:
    """Analyze raw free-form prompt plus its conservatively parsed Scene Spec."""
    scene = parse_prompt(text)
    report = analyze_scene(scene)
    # Remove the clean marker before adding raw prompt findings.
    report.findings = [f for f in report.findings if f.rule_id != "preflight.clean"]
    low = text.lower()

    durations = scene.get("parse_meta", {}).get("duration_mentions", [])
    unique_durations = sorted(set(round(float(x), 3) for x in durations))
    if len(unique_durations) > 1:
        _add(report, "prompt.duration.conflict", "error", f"Conflicting duration mentions found: {unique_durations}.", "Use one exact scene duration.", 35)

    # Music contradictions.
    no_music = bool(re.search(r"(?:no|without|do not use|don't use)\s+(?:background\s+)?music", low))
    wants_music = bool(re.search(r"(?:add|use|with|include)\s+(?:soft\s+|subtle\s+)?(?:background\s+)?music", low))
    if no_music and wants_music:
        _add(report, "prompt.music.conflict", "error", "Prompt both forbids and requests music.", "Choose one audio policy.", 30)

    # Subtitle contradictions.
    no_sub = bool(re.search(r"(?:no|without|do not|don't)\s+(?:automatic\s+)?subtitles?", low))
    wants_sub = bool(re.search(r"(?:add|show|include|generate)\s+(?:automatic\s+)?subtitles?", low))
    if no_sub and wants_sub:
        _add(report, "prompt.subtitle.conflict", "error", "Prompt both forbids and requests subtitles.", "Keep subtitles entirely in post-production or entirely in generation.", 30)

    # German presenter contradiction.
    forbid_german_presenter = bool(re.search(r"presenter[^.\n]{0,120}(?:must not|do not|don't)[^.\n]{0,50}(?:pronounce|speak)[^.\n]{0,40}german", low))
    presenter_sentences = re.split(r"[.\n]+", low)
    asks_presenter_german = False
    for sentence in presenter_sentences:
        if "presenter" not in sentence:
            continue
        if re.search(r"(?:must not|do not|don't|never)[^;]{0,60}(?:pronounce|speak|say)", sentence):
            continue
        if re.search(r"(?:should\s+|must\s+|will\s+|then\s+)?(?:say|says|pronounce|pronounces|speak|speaks)[^;]{0,60}(?:german|laufen|verfahren|verlaufen|hören|verschlafen)", sentence):
            asks_presenter_german = True
            break
    if forbid_german_presenter and asks_presenter_german:
        _add(report, "prompt.audio.conflict", "error", "Presenter is told both not to pronounce German and to say/pronounce German.", "Reserve German for post-production or a separate verified voice.", 40)

    # Complexity estimate from imperative/action verbs.
    action_hits = re.findall(r"\b(?:show|display|transform|animate|cut|zoom|move|switch|split|highlight|pause|transition|appear|disappear)\b", low)
    duration = float(scene.get("duration_seconds", 10) or 10)
    max_actions = max(5, round(duration / 10 * 7))
    if len(action_hits) > max_actions:
        _add(report, "prompt.action_density", "warning", f"Detected about {len(action_hits)} visual/action instructions for {duration:g}s.", "Reduce visual actions or split the scene.", 15)

    # Prompt verbosity proxy: long prompts often increase instruction collisions.
    tokens_est = max(1, round(len(text) / 4))
    if tokens_est > 700:
        _add(report, "prompt.verbose", "warning", f"Prompt is roughly {tokens_est} tokens before generation.", "Compile to a constrained Scene Spec prompt to reduce collisions and token use.", 8)

    # Screen text precision: if user says exact/only but parser found none, require review.
    if re.search(r"(?:exact|only)\s+(?:screen\s+)?text", low) and not scene.get("screen_text"):
        _add(report, "prompt.screen_text.unparsed", "warning", "Prompt appears to constrain exact screen text, but no exact items were safely extracted.", "Move screen text into a clear ON SCREEN: block or Scene Spec whitelist.", 12)

    if not report.findings:
        _add(report, "preflight.clean", "info", "No deterministic preflight risks detected.", None, 0)
    return scene, report
