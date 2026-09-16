import copy
import yaml
from pathlib import Path

from vpp.analyzer import analyze_scene
from vpp.compiler import compile_scene
from vpp.fixer import auto_fix_scene
from vpp.parser import parse_prompt
from vpp.prompt_analyzer import analyze_prompt
from vpp.simulator import simulate_scene
from vpp.optimizer import optimize_prompt
from vpp.knowledge import evaluate_knowledge
from vpp.triple_review import triple_review
from vpp.candidates import build_candidates
from vpp.failure_memory import match_failures

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return yaml.safe_load((ROOT / "examples" / name).read_text(encoding="utf-8"))


def test_verified_ver_scene_passes():
    report = analyze_scene(load("ver_scene_1.yml"))
    assert report.passed
    assert report.risk_score == 0


def test_bad_scene_catches_known_failures():
    report = analyze_scene(load("bad_scene.yml"))
    ids = {f.rule_id for f in report.findings}
    assert not report.passed
    assert "screen_text.arabic" in ids
    assert "screen_text.whitelist" in ids
    assert "timeline.overflow" in ids
    assert "audio.german_presenter" in ids


def test_safe_auto_fix_removes_text_and_audio_risks():
    fixed = auto_fix_scene(load("bad_scene.yml"))
    assert "يتوه وهو ماشي" not in fixed["screen_text"]
    assert fixed["spoken"]["german_by_presenter"] == []


def test_compiler_emits_compact_constraints():
    prompt = compile_scene(load("ver_scene_1.yml"))
    assert "EXACT SCREEN TEXT ONLY" in prompt
    assert "TEXT WHITELIST IS STRICT" in prompt
    assert "TEXT SAFETY" in prompt
    assert "no Arabic text on screen" in prompt


def test_freeform_parser_extracts_ver_scene():
    text = (ROOT / "examples" / "ver_scene_1_prompt.txt").read_text(encoding="utf-8")
    scene = parse_prompt(text)
    assert scene["duration_seconds"] == 10
    assert scene["aspect_ratio"] == "9:16"
    assert scene["rules"]["no_arabic_on_screen"] is True
    assert scene["rules"]["presenter_arabic_only"] is True
    assert "ver-" in scene["screen_text"]
    assert "sich verlaufen" in scene["screen_text"]
    assert len(scene["timeline"]) == 5


def test_raw_prompt_conflicts_are_detected():
    text = (ROOT / "examples" / "conflicting_prompt.txt").read_text(encoding="utf-8")
    _, report = analyze_prompt(text)
    ids = {f.rule_id for f in report.findings}
    assert "prompt.duration.conflict" in ids
    assert "prompt.music.conflict" in ids
    assert "prompt.subtitle.conflict" in ids
    assert "prompt.audio.conflict" in ids


def test_simulator_marks_verified_scene_comfortable():
    sim = simulate_scene(load("ver_scene_1.yml"))
    assert sim.status == "comfortable"
    assert sim.timeline_seconds == 10


def test_optimizer_compiles_freeform_prompt():
    text = (ROOT / "examples" / "ver_scene_1_prompt.txt").read_text(encoding="utf-8")
    result = optimize_prompt(text)
    assert "EXACT SCREEN TEXT ONLY" in result["optimized_prompt"]
    assert "TEXT SAFETY" in result["optimized_prompt"]
    assert "no Arabic text on screen" in result["optimized_prompt"]
    assert result["after"]["risk_score"] <= result["before"]["risk_score"]


def test_optimizer_marks_ambiguous_conflicts_for_review():
    text = (ROOT / "examples" / "conflicting_prompt.txt").read_text(encoding="utf-8")
    result = optimize_prompt(text)
    assert result["requires_review"] is True
    assert result["decisions"]
    assert "no background music" in result["optimized_prompt"]
    assert "no automatic subtitles" in result["optimized_prompt"]


def test_triple_review_ver_scene_passes_for_veo():
    text = (ROOT / "examples" / "ver_scene_1_prompt.txt").read_text(encoding="utf-8")
    result = triple_review(text, provider="veo")
    assert result["passed"] is True
    assert len(result["rounds"]) == 3
    assert result["final_prompt"]
    assert result["rounds"][0]["candidates"]


def test_runway_knowledge_flags_negative_overload():
    text = "Create a 10 second video. No music. No subtitles. Never zoom. Avoid cuts. Do not move the camera. The subject walks slowly."
    scene = parse_prompt(text)
    findings = evaluate_knowledge(text, scene, provider="runway")
    ids = {f.rule_id for f in findings}
    assert "runway.positive_phrasing" in ids


def test_candidates_are_ranked_and_preserve_content():
    scene = load("ver_scene_1.yml")
    candidates = build_candidates(scene, provider="veo")
    assert len(candidates) == 3
    assert candidates[0].score >= candidates[-1].score
    assert any("sich verlaufen" in c.prompt for c in candidates)


def test_triple_review_conflict_prompt_fails_gate():
    text = (ROOT / "examples" / "conflicting_prompt.txt").read_text(encoding="utf-8")
    result = triple_review(text, provider="veo")
    assert result["passed"] is False
    assert result["confidence_band"] == "low"


def test_failure_memory_matches_real_regressions():
    scene = load("ver_scene_1.yml")
    matches = match_failures(scene, provider="veo")
    ids = {m["rule_id"] for m in matches}
    assert "memory.failure-0001" in ids
    assert "memory.failure-0002" in ids
    assert "memory.failure-0003" not in ids


def test_exact_text_morph_is_flagged():
    scene = copy.deepcopy(load("ver_scene_1.yml"))
    scene["timeline"][2]["action"] = "transform laufen into sich verlaufen; highlight only ver-"
    report = analyze_scene(scene)
    ids = {f.rule_id for f in report.findings}
    assert "screen_text.morph_risk" in ids
    assert "screen_text.state_coverage" in ids


def test_compiler_rewrites_exact_text_morph_to_static_cut():
    scene = copy.deepcopy(load("ver_scene_1.yml"))
    scene["timeline"][2]["action"] = "transform laufen into sich verlaufen; highlight only ver-"
    prompt = compile_scene(scene)
    assert "transform laufen into sich verlaufen" not in prompt.lower()
    assert "show laufen as static text" in prompt.lower()
    assert "hard cut" in prompt.lower()
    assert "do not morph" in prompt.lower()


def test_veo_knowledge_matches_exact_text_morph_regression():
    text = """Create a 10 second 9:16 video.
ON SCREEN:
laufen
sich verlaufen
TIMELINE:
0-5s show laufen
5-10s transform laufen into sich verlaufen
"""
    scene = parse_prompt(text)
    findings = evaluate_knowledge(text, scene, provider="veo")
    ids = {f.rule_id for f in findings}
    assert "veo.exact_text_morph" in ids


def test_failure_memory_matches_exact_text_morph_case():
    scene = copy.deepcopy(load("ver_scene_1.yml"))
    scene["timeline"][2]["action"] = "morph laufen into sich verlaufen"
    matches = match_failures(scene, provider="veo")
    ids = {m["rule_id"] for m in matches}
    assert "memory.failure-0003" in ids
