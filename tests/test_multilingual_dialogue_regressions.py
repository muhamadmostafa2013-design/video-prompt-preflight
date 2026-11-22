"""Safety regressions for exact Arabic/German educational video dialogue."""
from __future__ import annotations

from vpp.analyzer import analyze_scene
from vpp.candidates import build_candidates
from vpp.parser import parse_prompt
from vpp.simulator import simulate_scene
from vpp.triple_review import triple_review


GERMAN_LONG = (
    "Entschuldigung, ich bin heute zum ersten Mal an dieser Universität "
    "und ich weiß leider überhaupt nicht, wo der große Hörsaal im zweiten "
    "Gebäude liegt, und ich habe nur noch wenige Minuten bis zum Beginn "
    "der Veranstaltung, könnten Sie mir bitte helfen?"
)


def test_exact_german_spoken_text_is_first_class():
    prompt = (
        "Create an 8-second 9:16 clip. Arab student in a university. "
        'Only the student speaks German. Exact German dialogue: "Ich möchte einen Kaffee, bitte." '
        "No subtitles. No music."
    )
    scene = parse_prompt(prompt)
    assert scene["spoken"]["segments"][0]["language"] == "de"
    assert scene["spoken"]["segments"][0]["text"] == "Ich möchte einen Kaffee, bitte."
    result = triple_review(prompt, "gemini_omni")
    assert result["passed"]
    assert "Ich möchte einen Kaffee, bitte." in result["final_prompt"]


def test_long_german_speech_blocks_8_second_video():
    prompt = (
        "Create an 8-second 9:16 clip. Student alone speaks German. "
        f'The student says exactly: "{GERMAN_LONG}" '
        "No subtitles. No music."
    )
    scene = parse_prompt(prompt)
    assert any(item["language"] == "de" for item in scene["spoken"]["segments"])
    sim = simulate_scene(scene)
    assert sim.spoken_words > 30
    assert sim.status == "overflow"
    result = triple_review(prompt, "gemini_omni")
    assert not result["passed"]
    assert "speech.multilingual.overflow" in {f["rule_id"] for f in result["findings"]}


def test_visual_identity_and_reference_are_not_deleted():
    prompt = (
        "Create an 8-second 9:16 cinematic shot of an Egyptian student. "
        "The student wears a green sweater, a black backpack, and stands by "
        'the Berlin university staircase. Exact German dialogue: "Ich bin neu hier." '
        "No subtitles. No music."
    )
    result = triple_review(prompt, "gemini_omni")
    assert result["passed"]
    assert "green sweater" in result["final_prompt"]
    assert "black backpack" in result["final_prompt"]
    assert "Berlin university staircase" in result["final_prompt"]
    assert "Ich bin neu hier." in result["final_prompt"]


def test_arabic_and_german_both_count_as_speech():
    prompt = (
        "Create an 8-second vertical 9:16 video. "
        'Egyptian Arabic narrator says: "أول يوم ليك في الجامعة؟"\n'
        'German student says: "Entschuldigung, wo ist Raum B12?"\n'
        "No background music and no subtitles."
    )
    scene = parse_prompt(prompt)
    languages = {item["language"] for item in scene["spoken"]["segments"]}
    assert languages == {"ar", "de"}
    assert simulate_scene(scene).spoken_words >= 12
    result = triple_review(prompt, "gemini_omni")
    assert all(x in result["final_prompt"] for x in (
        "أول يوم ليك في الجامعة؟", "Entschuldigung, wo ist Raum B12?"
    ))


def test_screen_text_is_not_spoken_dialogue():
    scene = parse_prompt(
        'Create an 8-second 9:16 video. ON SCREEN: "Ich möchte einen Kaffee." '
        "No subtitles or background music."
    )
    assert scene["spoken"]["segments"] == []


def test_source_morph_uses_safe_static_text_cut():
    prompt = (
        "Create a 10 second 9:16 video.\nON SCREEN:\nlaufen\nsich verlaufen\n"
        "TIMELINE:\n0-10s transform laufen into sich verlaufen"
    )
    candidates = build_candidates(parse_prompt(prompt), "veo")
    assert len(candidates) == 3
    assert all("hard cut" in candidate.prompt for candidate in candidates)
    assert "transform laufen into sich verlaufen" not in candidates[0].prompt


def test_invalid_multilingual_segment_blocks():
    scene = {
        "duration_seconds": 8, "spoken": {"segments": [{"text": "Guten Tag"}]}
    }
    result = analyze_scene(scene)
    assert not result.passed
    assert "speech.segments.invalid" in {finding.rule_id for finding in result.findings}


def test_structured_multilingual_speech_compiles_without_loss():
    from vpp.compiler import compile_scene
    scene = {
        "duration_seconds": 8,
        "spoken": {"segments": [
            {"language": "de", "text": "Entschuldigung, wo ist Raum B12?",
             "speaker": "student"},
        ]},
    }
    assert 'Entschuldigung, wo ist Raum B12?' in compile_scene(scene)
