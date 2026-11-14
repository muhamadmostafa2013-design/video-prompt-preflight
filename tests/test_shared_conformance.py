"""Cross-engine golden behavior corpus; same cases checked in Node browser engine."""
import json
from pathlib import Path

import pytest

from vpp.prompt_analyzer import analyze_prompt


CASES = json.loads((Path(__file__).parent / "conformance_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["name"])
def test_python_conformance(case):
    scene, report = analyze_prompt(case["prompt"])
    finding_ids = {f.rule_id for f in report.findings}
    if "duration" in case:
        assert scene["duration_seconds"] == case["duration"]
    if "screen" in case:
        assert scene["screen_text"] == case["screen"]
    if "no_music" in case:
        assert scene["rules"]["no_background_music"] == case["no_music"]
    if "no_subtitles" in case:
        assert scene["rules"]["no_auto_subtitles"] == case["no_subtitles"]
    if "timeline_starts" in case:
        assert [event["start"] for event in scene["timeline"]] == case["timeline_starts"]
        assert [event["end"] for event in scene["timeline"]] == case["timeline_ends"]
    for field in ("expect_finding", "expect_finding_secondary"):
        if field in case:
            assert case[field] in finding_ids
    if case.get("check_no_duration_conflict"):
        assert "prompt.duration.conflict" not in finding_ids
    if case.get("check_no_music_conflict"):
        assert "prompt.music.conflict" not in finding_ids
    if case.get("check_no_subtitle_conflict"):
        assert "prompt.subtitle.conflict" not in finding_ids
