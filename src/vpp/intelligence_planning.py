"""Bounded local planning, education checks and deterministic prompt mutation tests."""
from __future__ import annotations

import random
from collections import Counter

from .german_music_qa import LEVELS, review_song
from .prompt_analyzer import analyze_prompt
from .song_alignment import _tokens


def cost_plan(scenes, budget_cents):
    """Estimate only, no provider request; never drop a required fix silently."""
    if type(budget_cents) is not int or budget_cents < 0:
        raise ValueError("Budget must be nonnegative integer cents.")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 300:
        raise ValueError("Provide 1..300 scenes.")
    rows = []
    seen = set()
    for scene in scenes:
        sid, status, price = scene["id"], scene["status"], scene["regenerate_cents"]
        if not isinstance(sid, str) or not sid.strip() or sid in seen:
            raise ValueError("Unique scene IDs required.")
        seen.add(sid)
        if type(price) is not int or price < 0:
            raise ValueError("Explicit integer-cent regeneration estimates required.")
        if status not in {"ok", "subtitle_only", "visual_failed", "unknown"}:
            raise ValueError("Unknown scene status.")
        action = {"ok": "keep", "subtitle_only": "local_caption_repair",
                  "visual_failed": "propose_regeneration", "unknown": "human_review"}[status]
        rows.append({"id": sid, "action": action,
                     "estimated_provider_cents": price if status == "visual_failed" else 0})
    needed = sum(r["estimated_provider_cents"] for r in rows)
    full = sum(s["regenerate_cents"] for s in scenes)
    unknown = any(s["status"] == "unknown" for s in scenes)
    return {"decision": "blocked_budget" if needed > budget_cents else
            "review_unknown" if unknown else "plan_only",
            "actions": rows, "budget_cents": budget_cents, "estimated_provider_cents": needed,
            "full_regeneration_cents": full, "potential_avoided_cents": full-needed,
            "paid_calls": 0, "publication_approved": False,
            "limitations": "User-supplied estimates exclude local compute, taxes and retry charges. No guaranteed savings."}


def model_route(candidates, task, memory_mb):
    """Choose among explicitly validated local candidates only; no network fallback."""
    if type(memory_mb) is not int or memory_mb < 0:
        raise ValueError("Memory budget must be nonnegative integer MiB.")
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 100:
        raise ValueError("Invalid model candidates.")
    eligible = []
    rejected = []
    seen = set()
    for c in candidates:
        model = c["id"]
        if not isinstance(model, str) or not model.strip() or model in seen:
            raise ValueError("Unique model IDs required.")
        seen.add(model)
        size, loss = c["required_memory_mb"], c["benchmark_loss"]
        if (type(size) is not int or size < 0 or type(loss) not in (int, float)
                or not 0 <= loss <= 10):
            raise ValueError("Invalid resource or benchmark measurement.")
        reasons = []
        if c.get("task") != task:
            reasons.append("different_task")
        if c.get("local") is not True or c.get("weights_verified") is not True:
            reasons.append("local_weights_unverified")
        if c.get("benchmark_comparable") is not True:
            reasons.append("benchmark_unverified")
        if size > memory_mb:
            reasons.append("memory_limit")
        if reasons:
            rejected.append({"id": model, "reasons": reasons})
        else:
            eligible.append(c)
    chosen = min(eligible, key=lambda c: (c["benchmark_loss"], c["required_memory_mb"], c["id"])) if eligible else None
    return {"decision": "proposal" if chosen else "blocked_no_local_model",
            "chosen": chosen["id"] if chosen else None, "rejected": rejected,
            "remote_fallback": False, "publication_approved": False,
            "limitations": "Readiness and comparable benchmark labels are supplied, not independently verified by this planner."}


def education_review(spec):
    """Reuse existing German song QA; add explicit curriculum requirements, not invented CEFR grading."""
    report = review_song(spec)
    curriculum = spec.get("curriculum", {})
    if not isinstance(curriculum, dict):
        raise TypeError("Curriculum must be an object.")
    issues = []
    level = spec.get("cefr", "").lower()
    if level not in LEVELS:
        issues.append("missing_or_invalid_cefr")
    objective = curriculum.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        issues.append("missing_learning_objective")
    allowed = curriculum.get("approved_vocabulary", [])
    if not isinstance(allowed, list) or any(not isinstance(x, str) or not _tokens(x) for x in allowed):
        raise ValueError("Approved vocabulary must contain words or phrases.")
    if allowed:
        known = {w for item in allowed for w in _tokens(item)}
        unknown = sorted(set(_tokens(spec["lyrics"])) - known)
    else:
        unknown = []
        issues.append("no_curated_vocabulary")
    return {"decision": "review" if report["passed"] else "blocked",
            "existing_music_qa": report, "curriculum_issues": issues,
            "out_of_vocabulary_review": unknown,
            "publication_approved": False,
            "limitations": "Teacher-supplied vocabulary only; no full CEFR classification, grammar or semantic translation certification."}


def mutate_prompts(seed=20261124, trials=600):
    """Known-answer prompt mutations: duration, music and subtitle conflicts plus clean controls."""
    if type(trials) is not int or not 1 <= trials <= 3000:
        raise ValueError("Trials must be 1..3000.")
    rng = random.Random(seed)
    counts = Counter()
    failures = []
    options = ("duration", "music", "subtitle", "clean")
    for i in range(trials):
        variant = options[i % len(options)]
        counts[variant] += 1
        seconds = rng.choice([6, 8, 10, 12, 15])
        text = (f"Create a {seconds} second vertical video. Vertical 9:16.\n"
                "No background music. No automatic subtitles.\n")
        expected = None
        if variant == "duration":
            text = text.replace(" vertical video.", f" vertical video, but make the scene {seconds+2} seconds long.")
            expected = "prompt.duration.conflict"
        elif variant == "music":
            text += rng.choice(["Add subtle background music.", "Use background music.", "Play music."])
            expected = "prompt.music.conflict"
        elif variant == "subtitle":
            text += rng.choice(["Generate subtitles.", "Show automatic subtitles.", "Add subtitles."])
            expected = "prompt.subtitle.conflict"
        if rng.choice([False, True]):
            text = text.upper()
        if rng.choice([False, True]):
            text = text.replace(" ", "  ")
        _, report = analyze_prompt(text)
        error_ids = {f.rule_id for f in report.findings if f.severity == "error"}
        if (expected and (expected not in error_ids or report.passed)) or (not expected and error_ids):
            failures.append({"trial": i, "variant": variant, "expected": expected,
                             "actual_errors": sorted(error_ids), "prompt": text})
    return {"seed": seed, "trials": trials, "counts": dict(counts),
            "failed_trials": len(failures), "failures": failures[:100],
            "decision": "fail" if failures else "pass_simulation",
            "limitations": "Known-answer mutations of supported prompt patterns, not arbitrary adversarial coverage."}
