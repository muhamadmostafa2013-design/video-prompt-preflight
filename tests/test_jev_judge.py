from vpp.jev_judge import derive_gate


def test_jev_gate_releases_high_confidence_safe_prompt():
    result = derive_gate(
        hard_constraints_probability=0.98,
        provider_fit_probability=0.94,
        human_review_probability=0.08,
        risk_score=0.6,
        dominant_risk="none",
        score_confidence=0.93,
        choice_confidence=0.96,
    )
    assert result.decision == "release"


def test_jev_gate_routes_uncertain_prompt_to_review():
    result = derive_gate(
        hard_constraints_probability=0.84,
        provider_fit_probability=0.82,
        human_review_probability=0.42,
        risk_score=1.5,
        dominant_risk="exact_text",
    )
    assert result.decision == "review"


def test_jev_gate_blocks_high_risk_prompt():
    result = derive_gate(
        hard_constraints_probability=0.96,
        provider_fit_probability=0.91,
        human_review_probability=0.74,
        risk_score=3.6,
        dominant_risk="conflicting_instructions",
    )
    assert result.decision == "block"
