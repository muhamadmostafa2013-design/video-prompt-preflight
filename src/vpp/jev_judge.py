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


def _compact_state(review_result: dict, original_prompt: str) -> dict[str, Any]:
    findings = []
    for item in review_result.get("findings", []):
        findings.append({
            "rule_id": item.get("rule_id"),
            "severity": item.get("severity"),
            "message": item.get("message"),
            "recommendation": item.get("recommendation"),
            "evidence_tier": item.get("evidence_tier"),
        })

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
        "findings": findings,
    }


def jev_gate(
    review_result: dict,
    *,
    original_prompt: str,
    model: str | None = None,
    client: Any | None = None,
) -> dict[str, Any]:
    """Run an optional Jev semantic gate after VPP's deterministic triple review.

    Jev is intentionally used only for typed judgments. It never generates or
    rewrites the final prompt. If no client is supplied, TYPESAFE_API_KEY is
    read by the official TypeSafe SDK.
    """
    try:
        from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
    except ImportError as exc:
        raise RuntimeError(
            "Jev support is optional. Install it with: pip install 'video-prompt-preflight[jev]'"
        ) from exc

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

    owns_client = client is None
    if owns_client:
        client = TypeSafeClient()

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
