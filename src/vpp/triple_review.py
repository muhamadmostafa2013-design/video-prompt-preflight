from __future__ import annotations

from .prompt_analyzer import analyze_prompt
from .simulator import simulate_scene
from .knowledge import evaluate_knowledge
from .candidates import build_candidates
from .failure_memory import match_failures


def _dedupe(items: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for item in items:
        key = (item.get("rule_id"), item.get("agent"), item.get("message"))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def triple_review(text: str, provider: str = "generic") -> dict:
    scene, base = analyze_prompt(text)
    sim = simulate_scene(scene)

    candidates = build_candidates(scene, provider)
    round1_findings = []
    for f in base.findings:
        round1_findings.append({
            "rule_id": f.rule_id,
            "agent": "Deterministic Verifier",
            "severity": f.severity,
            "message": f.message,
            "recommendation": f.suggestion or "",
            "points": f.points,
            "sources": [],
        })

    evidence = [x.to_dict() for x in evaluate_knowledge(text, scene, provider)]
    memory = match_failures(scene, provider)
    redteam = []
    if sim.status == "tight":
        redteam.append({
            "rule_id": "redteam.timing_pressure",
            "agent": "Adversarial Critic",
            "severity": "warning",
            "message": "The scene fits numerically but has little recovery margin if the generator stretches a beat.",
            "recommendation": "Create at least 0.5–1.0s of timing slack or reduce one independent event.",
            "points": 8,
            "sources": [],
        })
    if len(scene.get("screen_text", []) or []) >= 5 and len(scene.get("timeline", []) or []) >= 5:
        redteam.append({
            "rule_id": "redteam.text_motion_competition",
            "agent": "Adversarial Critic",
            "severity": "warning",
            "message": "Many exact-text changes compete with motion beats in the same short scene.",
            "recommendation": "Keep exact text visually stable for longer or move non-essential text to editing.",
            "points": 8,
            "sources": [],
        })

    all_findings = _dedupe(round1_findings + evidence + memory + redteam)
    errors = [x for x in all_findings if x.get("severity") == "error"]
    warnings = [x for x in all_findings if x.get("severity") == "warning"]
    gate_pass = not errors and sim.status != "overflow"
    heuristic_score = max(0, 100 - sum(int(x.get("points", 0) or 0) for x in all_findings))
    confidence = "high" if gate_pass and len(warnings) <= 1 else "medium" if gate_pass else "low"
    winner = candidates[0]
    if winner.hard_constraint_coverage < 100:
        gate_pass = False
        confidence = "low"
        all_findings.append({
            "rule_id": "gate.candidate_constraint_loss",
            "agent": "Gatekeeper",
            "severity": "error",
            "message": f"Selected candidate preserves only {winner.hard_constraint_coverage}% of hard constraints.",
            "recommendation": "Do not release a candidate that drops exact text, audio, subtitle, music or continuity constraints.",
            "points": 40,
            "sources": [],
        })
        heuristic_score = max(0, heuristic_score - 40)

    return {
        "version": "0.3.0",
        "provider": provider,
        "scene": scene,
        "rounds": [
            {"round": 1, "name": "Correctness + candidate comparison", "findings": round1_findings, "candidates": [c.to_dict() for c in candidates], "winner": winner.name},
            {"round": 2, "name": "Failure prediction + evidence + memory", "findings": evidence + memory + redteam},
            {"round": 3, "name": "Independent gatekeeper", "passed": gate_pass, "heuristic_score": heuristic_score, "confidence_band": confidence},
        ],
        "final_prompt": winner.prompt,
        "passed": gate_pass,
        "heuristic_score": heuristic_score,
        "confidence_band": confidence,
        "simulation": sim.to_dict(),
        "findings": all_findings,
    }
