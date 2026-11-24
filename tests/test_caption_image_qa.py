import pytest

from vpp.caption_image_qa import caption_observation, phrase_issues


@pytest.mark.parametrize("phrase", ["einen Termin vereinbaren", "einen Antrag stellen",
                                    "eine Entscheidung treffen", "eine Frage stellen"])
def test_missing_noun_detected(phrase):
    parts = phrase.split()
    observed = " ".join([parts[0], parts[-1]])
    assert phrase_issues(observed, [phrase])
    assert not phrase_issues(phrase, [phrase])


def test_residual_side_text_and_missing_target_block():
    result = caption_observation("einen Termin vereinbaren", "einen vereinbaren",
                                 ["alter Text"], ["einen Termin vereinbaren"])
    assert {i["code"] for i in result["issues"]} == {
        "expected_caption_tokens_missing", "possible_residual_text_outside_panel",
        "possible_incomplete_target_phrase"}
    assert not result["publication_approved"]


def test_clean_source_text_is_review_not_certification():
    assert caption_observation("", "Termin")["decision"] == "needs_review"
    assert caption_observation("", "")["decision"] == "sample_consistent"


def test_reordered_and_duplicate_words():
    assert caption_observation("Ein Verb", "Verb Ein")["issues"][0]["code"] == "caption_token_order_differs"
    assert caption_observation("Ein Verb", "Ein Verb Verb")["issues"][0]["code"] == "unexpected_caption_tokens"
