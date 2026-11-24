import pytest
from vpp.song_alignment import audit_words, draft_srt


def word(text, start, end, score=0.9):
    return {"word": text, "start": start, "end": end, "score": score}


def test_valid_word_evidence_never_certifies_human_listening():
    result = audit_words(["Ein Nomen", "ein Verb"], [
        word("Ein", 1, 1.2), word("Nomen", 1.2, 1.8),
        word("ein", 2.1, 2.3), word("Verb", 2.3, 2.9)], 4)
    assert result["decision"] == "review"
    assert not result["human_listening_verified"]
    assert not result["publication_approved"]
    assert "00:00:01,000 --> 00:00:01,800\nEin Nomen\nاسم" in draft_srt(result, ["اسم", "فعل"])
    assert result["cues"][1]["start"] == 2.1


@pytest.mark.parametrize("words", [
    [],
    [word("Ein", 1, 1.2)],
    [word("Ein", 1, 1.2), word("Verb", 1.2, 1.8)],
    [word("Ein", 1, 1.2), word("Nomen", 1.1, 1.8)],
    [word("Ein", 1, 1.2), word("Nomen", 1.2, 5)],
    [word("Ein", 1, 1.2), {"word": "Nomen", "score": 0.9}],
    [word("Ein", 1, 1.2), word("Nomen", 1.2, 1.8, 0.1)],
    [word("Ein", 1, 1.2), word("Nomen", float("nan"), 1.8)],
    [word("Ein", 1, 1.2), {"word": "Nomen", "start": 1.2, "end": 1.8}],
])
def test_invalid_evidence_blocks_and_never_exports(words):
    result = audit_words(["Ein Nomen"], words, 4)
    assert result["decision"] == "blocked"
    assert result["cues"] == []
    with pytest.raises(ValueError):
        draft_srt(result)


def test_repeated_lyric_cannot_be_silently_dropped():
    result = audit_words(["Ein Nomen", "Ein Nomen"], [
        word("Ein", 1, 1.2), word("Nomen", 1.2, 1.8)], 4)
    assert result["decision"] == "blocked"


def test_translation_count_must_match():
    result = audit_words(["Ein"], [word("Ein", 1, 1.2)], 4)
    with pytest.raises(ValueError):
        draft_srt(result, [])
