import shutil
import subprocess

import pytest

from vpp.caption_image_qa import (
    caption_observation,
    phrase_issues,
    scan_caption_images,
    simulate_caption_faults,
)


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


@pytest.mark.parametrize("seed", [11, 97, 20261124])
def test_seeded_caption_faults(seed):
    result = simulate_caption_faults(seed, 1200)
    assert result["failed_trials"] == 0
    assert sum(result["counts"].values()) == 1200


def test_real_encoded_caption_ocr(tmp_path):
    if not all(shutil.which(b) for b in ("ffmpeg", "ffprobe", "tesseract")):
        pytest.skip("FFmpeg and Tesseract needed.")
    font = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    from pathlib import Path
    if not Path(font).is_file():
        pytest.skip("Fixture font unavailable.")
    video = tmp_path / "caption.mp4"
    srt = tmp_path / "expected.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\neinen Termin vereinbaren\n", encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
        "color=black:s=720x480:r=10:d=2", "-vf",
        (f"drawtext=fontfile={font}:text=einen vereinbaren:fontsize=34:fontcolor=white:x=180:y=365,"
         f"drawtext=fontfile={font}:text=ALT:fontsize=26:fontcolor=white:x=18:y=365"),
        "-c:v", "mpeg4", str(video)], check=True, capture_output=True, timeout=30)
    result = scan_caption_images(video, srt, targets=["einen Termin vereinbaren"],
        panel=(.18, .72, .98, .9), inspection=(0., .72, 1., .9),
        language="eng", samples_per_cue=1)
    codes = {issue["code"] for row in result["rows"] for issue in row["issues"]}
    assert "expected_caption_tokens_missing" in codes
    assert "possible_residual_text_outside_panel" in codes
    assert "possible_incomplete_target_phrase" in codes
    assert result["decision"] == "needs_review"


@pytest.mark.parametrize("expected,observed", [("einen Termin vereinbaren", "einen termin vereinbaren"),
                                             ("Ich höre Musik", "ich höre Musik")])
def test_german_caption_capitalization_is_not_ignored(expected, observed):
    result = caption_observation(expected, observed)
    assert result["decision"] == "needs_review"
    assert result["issues"] == [{"code": "caption_capitalization_differs"}]
    assert not result["publication_approved"]


def test_unicode_canonical_equivalence_not_a_capitalization_error():
    assert caption_observation("Ich höre Musik", "Ich ho\u0308re Musik")["decision"] == "sample_consistent"



def test_caption_sampling_long_gaps_and_cues():
    from vpp.caption_image_qa import caption_sample_points

    cues = [{"start_ms": 10000, "end_ms": 30000, "lines": ["Ein Nomen", "اسم"]}]
    points = caption_sample_points(cues, 40, bilingual=True)
    assert len(points) == 20
    assert points[0] == (1.0, "")
    assert points[-1] == (39.0, "")
    assert sum(text == "Ein Nomen اسم" for _, text in points) == 10
    assert max(b[0]-a[0] for a, b in zip(points, points[1:])) <= 2


def test_clean_source_sampling_does_not_depend_on_old_caption_timing():
    from vpp.caption_image_qa import caption_sample_points

    points = caption_sample_points([], 61)
    assert len(points) == 31
    assert all(text == "" for _, text in points)
    assert points[-1][0] > 60
