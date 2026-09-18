from vpp.jev_judge import candidate_utility, derive_gate, rank_candidate_scores


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


def test_candidate_utility_penalizes_lost_hard_constraints():
    complete = candidate_utility(
        hard_constraints_probability=0.88,
        provider_fit_probability=0.84,
        ambiguity_probability=0.18,
        risk_score=1.1,
        deterministic_score=81,
        hard_constraint_coverage=100,
    )
    prettier_but_incomplete = candidate_utility(
        hard_constraints_probability=0.96,
        provider_fit_probability=0.94,
        ambiguity_probability=0.05,
        risk_score=0.4,
        deterministic_score=97,
        hard_constraint_coverage=80,
    )
    assert complete > prettier_but_incomplete


def test_rank_candidates_prefers_safe_complete_candidate():
    ranked = rank_candidate_scores([
        {
            "key": "c0",
            "name": "A",
            "hard_constraints_probability": 0.93,
            "provider_fit_probability": 0.88,
            "ambiguity_probability": 0.12,
            "risk_score": 0.9,
            "deterministic_score": 85,
            "hard_constraint_coverage": 100,
        },
        {
            "key": "c1",
            "name": "B",
            "hard_constraints_probability": 0.98,
            "provider_fit_probability": 0.96,
            "ambiguity_probability": 0.05,
            "risk_score": 0.5,
            "deterministic_score": 98,
            "hard_constraint_coverage": 75,
        },
        {
            "key": "c2",
            "name": "C",
            "hard_constraints_probability": 0.76,
            "provider_fit_probability": 0.82,
            "ambiguity_probability": 0.35,
            "risk_score": 1.8,
            "deterministic_score": 82,
            "hard_constraint_coverage": 100,
        },
    ])
    assert ranked[0].key == "c0"
    assert ranked[-1].key == "c1"
