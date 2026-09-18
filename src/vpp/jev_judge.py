from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class JevGateDecision:
    decision: str
    hard_constraints_probability: float
    provider_fit_probability: float
    human_review_probability: float
    risk_score: float
    dominant_risk: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class JevCandidateScore:
    key: str
    name: str
    hard_constraints_probability: float
    provider_fit_probability: float
    ambiguity_probability: float
    risk_score: float
    deterministic_score: float
    hard_constraint_coverage: int
    utility: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def derive_gate(
    *,
    hard_constraints_probability: float,
    provider_fit_probability: float,
    human_review_probability: float,
    risk_score: float,
    dominant_risk: str,
    score_confidence: float = 1.0,
    choice_confidence: float = 1.0,
) -> JevGateDecision:
    hard = max(0.0, min(1.0, float(hard_constraints_probability)))
    fit = max(0.0, min(1.0, float(provider_fit_probability)))
    review = max(0.0, min(1.0, float(human_review_probability)))
    risk = max(0.0, min(4.0, float(risk_score)))

    certainty = [
        abs(hard - 0.5) * 2,
        abs(fit - 0.5) * 2,
        abs(review - 0.5) * 2,
        max(0.0, min(1.0, float(score_confidence))),
        max(0.0, min(1.0, float(choice_confidence))),
    ]
    confidence = round(sum(certainty) / len(certainty), 4)

    if hard < 0.65 or fit < 0.55 or risk >= 3.25:
        decision = "block"
    elif hard < 0.90 or fit < 0.80 or review > 0.35 or risk >= 1.75:
        decision = "review"
    else:
        decision = "release"

    return JevGateDecision(
        decision=decision,
        hard_constraints_probability=round(hard, 4),
        provider_fit_probability=round(fit, 4),
        human_review_probability=round(review, 4),
        risk_score=round(risk, 4),
        dominant_risk=dominant_risk,
        confidence=confidence,
    )


def candidate_utility(
    *,
    hard_constraints_probability: float,
    provider_fit_probability: float,
    ambiguity_probability: float,
    risk_score: float,
    deterministic_score: float,
    hard_constraint_coverage: int,
) -> float:
    """Combine Jev probabilities with VPP's deterministic score.

    Hard constraints are a gate, not merely another preference. A candidate
    with deterministic coverage below 100% is heavily penalized.
    """
    hard = max(0.0, min(1.0, float(hard_constraints_probability)))
    fit = max(0.0, min(1.0, float(provider_fit_probability)))
    ambiguity = max(0.0, min(1.0, float(ambiguity_probability)))
    risk = max(0.0, min(4.0, float(risk_score))) / 4.0
    det = max(0.0, min(100.0, float(deterministic_score))) / 100.0
    coverage = max(0, min(100, int(hard_constraint_coverage)))

    utility = (
        hard * 0.42
        + fit * 0.28
        + (1.0 - ambiguity) * 0.10
        + (1.0 - risk) * 0.15
        + det * 0.05
    )

    if coverage < 100:
        utility -= 0.50 + (100 - coverage) / 200.0
    if hard < 0.65:
        utility -= 0.35
    return round(utility, 6)


def rank_candidate_scores(rows: list[dict[str, Any]]) -> list[JevCandidateScore]:
    ranked: list[JevCandidateScore] = []
    for row in rows:
        ranked.append(JevCandidateScore(
            key=str(row["key"]),
            name=str(row["name"]),
            hard_constraints_probability=float(row["hard_constraints_probability"]),
            provider_fit_probability=float(row["provider_fit_probability"]),
            ambiguity_probability=float(row["ambiguity_probability"]),
            risk_score=float(row["risk_score"]),
            deterministic_score=float(row.get("deterministic_score", 0)),
            hard_constraint_coverage=int(row.get("hard_constraint_coverage", 0)),
            utility=candidate_utility(
                hard_constraints_probability=float(row["hard_constraints_probability"]),
                provider_fit_probability=float(row["provider_fit_probability"]),
                ambiguity_probability=float(row["ambiguity_probability"]),
                risk_score=float(row["risk_score"]),
                deterministic_score=float(row.get("deterministic_score", 0)),
                hard_constraint_coverage=int(row.get("hard_constraint_coverage", 0)),
            ),
        ))
    return sorted(ranked, key=lambda x: x.utility, reverse=True)


def _compact_findings(review_result: dict) -> list[dict[str, Any]]:
    findings = []
    for item in review_result.get("findings", []):
        findings.append({
            "rule_id": item.get("rule_id"),
            "severity": item.get("severity"),
            "message": item.get("message"),
            "recommendation": item.get("recommendation"),
            "evidence_tier": item.get("evidence_tier"),
        })
    return findings


def _compact_state(review_result: dict, original_prompt: str) -> dict[str, Any]:
    return {
        "task": "Decide whether this AI-video prompt should be released, reviewed, or blocked before generation.",
        "provider": review_result.get("provider", "generic"),
        "original_prompt": original_prompt,
        "selected_prompt": review_result.get("final_prompt", ""),
        "scene": review_result.get("scene", {}),
        "simulation": review_result.get("simulation", {}),
        "deterministic_gate": {
            "passed": review_result.get("passed"),
            "score": review_result.get("heuristic_score"),
            "confidence": review_result.get("confidence_band"),
        },
        "findings": _compact_findings(review_result),
    }


def _client_and_types(client: Any | None):
    try:
        from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
    except ImportError as exc:
        raise RuntimeError(
            "Jev support is optional. Install it with: pip install 'video-prompt-preflight[jev]'"
        ) from exc

    owns_client = client is None
    if owns_client:
        client = TypeSafeClient()
    return client, owns_client, Choice, Noul, Score


def jev_rank_candidates(
    review_result: dict,
    *,
    original_prompt: str,
    model: str | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Ask Jev to judge A/B/C in parallel, then rank them deterministically."""
    client, owns_client, Choice, Noul, Score = _client_and_types(client)
    candidates = list((review_result.get("rounds") or [{}])[0].get("candidates") or [])
    if not candidates:
        raise RuntimeError("No candidates were found in the triple-review result.")

    state_candidates = []
    questions: dict[str, Any] = {}
    labels: dict[str, str] = {}

    for idx, candidate in enumerate(candidates):
        key = f"c{idx}"
        labels[key] = str(candidate.get("name", key))
        state_candidates.append({
            "key": key,
            "name": candidate.get("name"),
            "prompt": candidate.get("prompt"),
            "deterministic_score": candidate.get("score"),
            "hard_constraint_coverage": candidate.get("hard_constraint_coverage"),
            "token_estimate": candidate.get("token_estimate"),
        })
        questions[f"{key}_constraints"] = Noul(
            instructions=(
                f"Candidate {key} preserves every explicit hard constraint and required "
                "piece of content from the original prompt."
            )
        )
        questions[f"{key}_provider_fit"] = Noul(
            instructions=(
                f"Candidate {key} is well suited to the named video provider and is "
                "unlikely to create avoidable semantic confusion."
            )
        )
        questions[f"{key}_ambiguity"] = Noul(
            instructions=(
                f"Candidate {key} still contains meaningful ambiguity that could cause "
                "a preventable generation failure."
            )
        )
        questions[f"{key}_risk"] = Score(
            instructions=f"Score the remaining preventable generation risk in candidate {key}.",
            criteria=[
                "minimal preventable risk",
                "low preventable risk",
                "moderate preventable risk",
                "high preventable risk",
                "critical preventable risk",
            ],
        )

    questions["best_candidate"] = Choice(
        instructions=(
            "Choose the strongest candidate overall. Prioritize complete hard-constraint "
            "preservation first, provider fit second, then lower ambiguity and failure risk."
        ),
        criteria={key: name for key, name in labels.items()},
    )

    state = {
        "task": "Compare multiple candidate prompts for one AI-video generation request.",
        "provider": review_result.get("provider", "generic"),
        "original_prompt": original_prompt,
        "scene": review_result.get("scene", {}),
        "findings": _compact_findings(review_result),
        "candidates": state_candidates,
    }

    try:
        kwargs: dict[str, Any] = {"state": state, "questions": questions}
        if model:
            kwargs["model"] = model
        response = client.system_one(**kwargs)

        rows: list[dict[str, Any]] = []
        for idx, candidate in enumerate(candidates):
            key = f"c{idx}"
            rows.append({
                "key": key,
                "name": candidate.get("name", key),
                "hard_constraints_probability": response.nouls[f"{key}_constraints"].noul,
                "provider_fit_probability": response.nouls[f"{key}_provider_fit"].noul,
                "ambiguity_probability": response.nouls[f"{key}_ambiguity"].noul,
                "risk_score": response.scores[f"{key}_risk"].score,
                "deterministic_score": candidate.get("score", 0),
                "hard_constraint_coverage": candidate.get("hard_constraint_coverage", 0),
            })

        ranked = rank_candidate_scores(rows)
        best_answer = response.choices["best_candidate"]
        winner = ranked[0]
        winner_candidate = next(c for c, s in zip(candidates, [f"c{i}" for i in range(len(candidates))]) if s == winner.key)

        return {
            "engine": "jev",
            "model": response.model,
            "winner": winner.to_dict(),
            "winner_prompt": winner_candidate.get("prompt", ""),
            "ranking": [x.to_dict() for x in ranked],
            "jev_advisory_choice": {
                "key": best_answer.choice,
                "name": labels.get(best_answer.choice, best_answer.choice),
                "confidence": best_answer.confidence,
                "probabilities": dict(best_answer.probabilities),
            },
            "usage": {
                "input_tokens": getattr(response.usage, "input_tokens", None),
                "output_tokens": getattr(response.usage, "output_tokens", None),
            },
        }
    finally:
        if owns_client and hasattr(client, "close"):
            client.close()


def jev_gate(
    review_result: dict,
    *,
    original_prompt: str,
    model: str | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Run an optional Jev semantic gate after VPP's deterministic triple review."""
    client, owns_client, Choice, Noul, Score = _client_and_types(client)
    state = _compact_state(review_result, original_prompt)

    questions = {
        "hard_constraints_preserved": Noul(
            instructions=(
                "The selected prompt preserves all explicit hard constraints "
                "and required content from the original prompt."
            )
        ),
        "provider_fit": Noul(
            instructions=(
                "The selected prompt is likely to be interpreted by the named "
                "video provider without avoidable semantic ambiguity."
            )
        ),
        "needs_human_review": Noul(
            instructions=(
                "A human should review this prompt before spending a generation "
                "because meaningful ambiguity or failure risk remains."
            )
        ),
        "preventable_risk": Score(
            instructions=(
                "Score the remaining preventable generation risk in the selected "
                "prompt, considering the supplied findings and provider."
            ),
            criteria=[
                "minimal preventable risk",
                "low preventable risk",
                "moderate preventable risk",
                "high preventable risk",
                "critical preventable risk",
            ],
        ),
        "dominant_risk": Choice(
            instructions="Which single risk category is most important in the selected prompt?",
            criteria={
                "none": "No meaningful preventable risk is evident.",
                "timing": "Too much speech, motion, or too many events for the duration.",
                "conflicting_instructions": "The prompt contains instructions that compete or contradict.",
                "exact_text": "Required on-screen text or typography may be unreliable.",
                "audio": "Dialogue, language ownership, sound, or lip-sync is risky.",
                "camera_motion": "Camera instructions are ambiguous or overloaded.",
                "continuity": "Identity, wardrobe, object, or scene continuity is at risk.",
                "compositional_complexity": "Too many objects, relations, or actions must bind correctly.",
                "provider_specific": "The prompt conflicts with a known provider-specific behavior.",
                "other": "Another risk dominates.",
            },
        ),
    }

    try:
        kwargs: dict[str, Any] = {"state": state, "questions": questions}
        if model:
            kwargs["model"] = model
        response = client.system_one(**kwargs)

        hard = response.nouls["hard_constraints_preserved"].noul
        fit = response.nouls["provider_fit"].noul
        review = response.nouls["needs_human_review"].noul
        risk_answer = response.scores["preventable_risk"]
        dominant_answer = response.choices["dominant_risk"]

        decision = derive_gate(
            hard_constraints_probability=hard,
            provider_fit_probability=fit,
            human_review_probability=review,
            risk_score=risk_answer.score,
            dominant_risk=dominant_answer.choice,
            score_confidence=risk_answer.confidence,
            choice_confidence=dominant_answer.confidence,
        )

        return {
            "engine": "jev",
            "model": response.model,
            "decision": decision.to_dict(),
            "probabilities": {
                "dominant_risk": dict(dominant_answer.probabilities),
                "risk_levels": {str(k): v for k, v in risk_answer.probabilities.items()},
            },
            "usage": {
                "input_tokens": getattr(response.usage, "input_tokens", None),
                "output_tokens": getattr(response.usage, "output_tokens", None),
            },
        }
    finally:
        if owns_client and hasattr(client, "close"):
            client.close()


def jev_review(
    review_result: dict,
    *,
    original_prompt: str,
    model: str | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Rank candidates with Jev, then gate the deterministic winner.

    When a caller passes one client, both requests reuse it. The candidate
    ranking remains deterministic once Jev has returned its probabilities.
    """
    client, owns_client, _, _, _ = _client_and_types(client)
    try:
        ranking = jev_rank_candidates(
            review_result,
            original_prompt=original_prompt,
            model=model,
            client=client,
        )
        selected = dict(review_result)
        selected["final_prompt"] = ranking["winner_prompt"]

        gate = jev_gate(
            selected,
            original_prompt=original_prompt,
            model=model,
            client=client,
        )
        return {
            "candidate_judge": ranking,
            "semantic_gate": gate,
            "final_prompt": ranking["winner_prompt"],
            "decision": gate["decision"]["decision"],
        }
    finally:
        if owns_client and hasattr(client, "close"):
            client.close()
