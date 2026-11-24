import pytest

from vpp.model_evidence import rank_scene, text_wer


def test_semantic_signals_are_not_approval():
    assert rank_scene(["street", "office"], [.35, .2])["signal"] == "supports_expected"
    assert rank_scene(["street", "office"], [.2, .35])["signal"] == "alternative_ranked_higher"
    result = rank_scene(["street", "office"], [.2, .21])
    assert result["signal"] == "ambiguous"
    assert not result["publication_approved"]


def test_invalid_visual_score():
    with pytest.raises(ValueError):
        rank_scene(["a", "b"], [.5, float("nan")])


def test_wer_against_reference():
    assert text_wer("Eine Frage stellen", "Eine Frage")["wer"] == pytest.approx(1/3)
    assert text_wer("Eine Frage stellen", "")["wer"] == 1
