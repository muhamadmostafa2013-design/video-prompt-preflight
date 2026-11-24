import json

import pytest

import vpp.project_quality as project


def fixture(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    spec = {}
    for key in ("audio", "video", "lyrics", "srt", "alignment_run", "clip_model", "scene_manifest"):
        (root / key).write_text("[]", encoding="utf-8")
        spec[key] = key
    manifest = root / "manifest.json"
    return root, manifest, spec


def test_project_rejects_path_escape(tmp_path):
    _, manifest, spec = fixture(tmp_path)
    (tmp_path / "outside").write_text("secret")
    spec["audio"] = "../outside"
    manifest.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="escapes"):
        project.run_project(manifest, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_project_missing_track_blocks_render(tmp_path, monkeypatch):
    _, manifest, spec = fixture(tmp_path)
    spec["render"] = True
    spec["clean_source"] = True
    manifest.write_text(json.dumps(spec))
    monkeypatch.setattr(project, "visual_scan", lambda *a: {"decision": "review"})
    monkeypatch.setattr(project, "semantic_scan", lambda *a: {"decision": "review",
        "samples": [{"signal": "supports_expected"}]})
    out = tmp_path / "out"
    result = project.run_project(manifest, out)
    assert result["decision"] == "blocked"
    assert result["stages"]["render"]["status"] == "blocked"
    assert not result["publication_approved"]
    assert (out / "dashboard.html").is_file()


def test_project_success_still_review_only(tmp_path, monkeypatch):
    root, manifest, spec = fixture(tmp_path)
    (root / "track.json").write_text(json.dumps({"words": []}))
    spec["independent_tracks"] = ["track.json"]
    spec["render"] = True
    spec["clean_source"] = True
    manifest.write_text(json.dumps(spec))
    monkeypatch.setattr(project, "visual_scan", lambda *a: {"decision": "review"})
    monkeypatch.setattr(project, "semantic_scan", lambda *a: {"decision": "review",
        "samples": [{"signal": "supports_expected"}]})
    def repair(*args):
        target = args[5]
        target.mkdir()
        (target / "REVIEW_ONLY.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nEin Nomen\n", encoding="utf-8")
        return {"decision": "review", "duration_seconds": 2}
    (root / "scene_manifest").write_text(json.dumps([{"id": "a", "start": 0, "end": 2, "required_phrases": ["Ein Nomen"]}]))
    monkeypatch.setattr(project, "guarded_repair", repair)
    monkeypatch.setattr(project, "render_draft", lambda *a, **k: {"decision": "review"})
    result = project.run_project(manifest, tmp_path / "out")
    assert result["decision"] == "review"
    assert result["stages"]["render"]["status"] == "completed"
    assert not result["publication_approved"]
    assert result["remote_calls"] == 0


def test_runtime_failure_visible_and_blocks(tmp_path, monkeypatch):
    _, manifest, spec = fixture(tmp_path)
    manifest.write_text(json.dumps(spec))
    def fail(*args):
        raise RuntimeError("unavailable weights")
    monkeypatch.setattr(project, "visual_scan", fail)
    monkeypatch.setattr(project, "semantic_scan", fail)
    result = project.run_project(manifest, tmp_path / "out")
    assert result["stages"]["video_decode"]["status"] == "failed"
    assert result["decision"] == "blocked"


def test_semantic_disagreement_blocks_render(tmp_path, monkeypatch):
    _, manifest, spec = fixture(tmp_path)
    spec["render"] = True
    manifest.write_text(json.dumps(spec))
    monkeypatch.setattr(project, "visual_scan", lambda *a: {"decision": "review"})
    monkeypatch.setattr(project, "semantic_scan", lambda *a: {
        "samples": [{"signal": "alternative_ranked_higher"}]})
    result = project.run_project(manifest, tmp_path / "out")
    assert result["stages"]["semantic_gate"]["status"] == "blocked"
    assert result["stages"]["render"]["status"] == "blocked"
