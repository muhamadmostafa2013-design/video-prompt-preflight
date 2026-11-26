"""Explicit local project runner; bounded stages and review-only output."""
from __future__ import annotations

import json
from pathlib import Path

from .acoustic_models import LocalGermanCTC, phoneme_evidence
from .acoustic_review import review_evidence
from .caption_image_qa import scan_caption_images
from .consensus import audiovisual_review
from .extended_quality import bilingual_review, pronunciation_review
from .intelligence_planning import cost_plan, education_review
from .intelligence_workflow import guarded_repair, write_dashboard
from .model_evidence import asr_evidence, semantic_scan
from .quality_engine import render_draft, visual_scan
from .quality_evidence import _read_json
from .subtitle_sync import parse_srt
from .triple_review import triple_review


def _local_path(root, name):
    if not isinstance(name, str) or not name.strip() or Path(name).is_absolute():
        raise ValueError("Use explicit project-relative input paths.")
    path = (root / name).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError("Project path escapes its directory.")
    return path


def run_project(manifest, output):
    spec_path = Path(manifest).resolve(strict=True)
    root = spec_path.parent
    spec = _read_json(spec_path, 1_000_000)
    if not isinstance(spec, dict):
        raise TypeError("Project manifest must be an object.")
    # Resolve every requested input before running any model.
    paths = {key: _local_path(root, spec[key]) for key in
             ("audio", "video", "lyrics", "srt", "alignment_run")}
    for key in ("ctc_model", "whisper_model", "clip_model", "phoneme_model", "phoneme_audio",
                "scene_manifest", "song_spec", "cost_spec", "prompt",
                "phoneme_reference", "bilingual_reference"):
        if key in spec:
            paths[key] = _local_path(root, spec[key])
    for key in ("render", "clean_source", "burn", "caption_image_qa", "strict_educational_qa",
                "acoustic_drift_review"):
        if key in spec and type(spec[key]) is not bool:
            raise ValueError(f"{key} must be a JSON boolean.")
    drift_requested = spec.get("acoustic_drift_review") is True
    drift_tolerance = spec.get("acoustic_drift_tolerance_ms", 150)
    if type(drift_tolerance) is not int or not 0 <= drift_tolerance <= 5000:
        raise ValueError("acoustic_drift_tolerance_ms must be an integer in 0..5000.")
    strict = spec.get("strict_educational_qa") is True
    if strict:
        required = {"scene_manifest", "clip_model", "song_spec", "phoneme_model",
                    "phoneme_audio", "phoneme_reference", "bilingual_reference"}
        missing = sorted(required - paths.keys())
        if missing:
            raise ValueError("Strict educational QA missing inputs: " + ", ".join(missing))
        if spec.get("caption_image_qa") is not True or spec.get("caption_language") != "deu+eng+ara":
            raise ValueError("Strict educational QA requires German and Arabic caption OCR.")
    if "phoneme_reference" in paths and not {"phoneme_audio", "phoneme_model"} <= paths.keys():
        raise ValueError("Phone reference requires both local audio segment and model.")
    if not isinstance(spec.get("independent_tracks", []), list):
        raise TypeError("independent_tracks must be a list.")
    track_paths = [_local_path(root, p) for p in spec.get("independent_tracks", [])]
    if len(track_paths) + int("whisper_model" in paths) + int("ctc_model" in paths) > 4:
        raise ValueError("At most four supplementary tracks.")
    destination = Path(output).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    result = {"decision": "review", "stages": {}, "strict_educational_qa": strict,
              "publication_approved": False,
              "human_listening_verified": False, "remote_calls": 0}

    def stage(name, fn):
        try:
            value = fn()
            if not isinstance(value, dict):
                raise TypeError("Stage evidence must be an object.")
            json.dumps(value, ensure_ascii=False, allow_nan=False)
        except Exception as exc:  # noqa: BLE001 -- optional model/runtime failure must be visible
            result["stages"][name] = {"status": "failed", "error_type": type(exc).__name__}
            result["decision"] = "blocked"
            return None
        result["stages"][name] = {"status": "completed", "evidence": value}
        return value

    def skip(name, reason, *, blocked=False):
        result["stages"][name] = {"status": "blocked" if blocked else "not_requested",
                                  "reason": reason}
        if blocked:
            result["decision"] = "blocked"

    if "prompt" in paths:
        preflight = stage("preflight", lambda: triple_review(paths["prompt"].read_text(encoding="utf-8"),
                                                           provider=spec.get("provider", "generic")))
        if preflight is not None and not preflight["passed"]:
            result["decision"] = "blocked"
    else:
        skip("preflight", "No original prompt provided.")
    stage("video_decode", lambda: visual_scan(paths["video"]))
    tracks = []
    for index, path in enumerate(track_paths):
        value = stage(f"imported_track_{index+1}", lambda path=path: _read_json(path))
        if value is not None:
            tracks.append(value)
    if "whisper_model" in paths:
        value = stage("whisper", lambda: asr_evidence(paths["audio"], paths["whisper_model"]))
        if value is not None:
            tracks.append(value)
    else:
        skip("whisper", "No local faster-whisper model requested.")
    if "ctc_model" in paths:
        value = stage("ctc", lambda: LocalGermanCTC(paths["ctc_model"]).transcribe(paths["audio"]))
        if value is not None:
            tracks.append(value)
    else:
        skip("ctc", "No local CTC model requested.")
    if drift_requested:
        if not tracks:
            skip("acoustic_drift", "No supplementary acoustic evidence available.", blocked=True)
        else:
            def audit_track(track):
                report = review_evidence(paths["audio"], paths["srt"], track, drift_tolerance)
                return {**report, "backend": track.get("backend"), "family": track.get("family"),
                        "model": track.get("model")}
            for index, track in enumerate(tracks, 1):
                reviewed = stage(f"acoustic_drift_{index}", lambda track=track: audit_track(track))
                if reviewed is None or reviewed["decision"] != "review_only":
                    result["decision"] = "blocked"
    else:
        skip("acoustic_drift", "Optional per-track caption drift diagnostic not requested.")
    if "phoneme_model" in paths and "phoneme_audio" in paths:
        phone = stage("phonemes", lambda: phoneme_evidence(paths["phoneme_audio"], paths["phoneme_model"]))
        if "phoneme_reference" in paths and phone is not None:
            reviewed = stage("pronunciation", lambda: pronunciation_review(
                _read_json(paths["phoneme_reference"]), phone))
            if reviewed is None or reviewed["decision"] != "phone_sequence_consistent":
                result["decision"] = "blocked"
        else:
            skip("pronunciation", "Teacher-approved phone reference is required for comparison.",
                 blocked=strict)
    elif "phoneme_model" in paths or "phoneme_audio" in paths:
        skip("phonemes", "Both a short segment and local phoneme model are required.", blocked=True)
    else:
        skip("phonemes", "No phoneme segment/model requested.")
    if "clip_model" in paths and "scene_manifest" in paths:
        semantic = stage("semantics", lambda: semantic_scan(paths["video"], paths["clip_model"],
                                                _read_json(paths["scene_manifest"]), spec.get("samples", 3)))
        if semantic is not None:
            samples = semantic.get("samples", [])
            groups = semantic.get("appearance_continuity", {}).get("groups", [])
            if (not samples or any(s.get("signal") != "supports_expected" for s in samples) or
                    any(g.get("status") != "sampled_description_consistent" for g in groups)):
                skip("semantic_gate", "Missing, ambiguous or conflicting sampled descriptions.", blocked=True)
            else:
                result["stages"]["semantic_gate"] = {"status": "completed", "evidence": "Sampled descriptions support expectations; manual review remains required."}
    else:
        skip("semantics", "Scene manifest and local CLIP model required.", blocked=True)
    if "song_spec" in paths:
        review = stage("education", lambda: education_review(_read_json(paths["song_spec"])))
        if review is not None and (review["decision"] == "blocked" or review.get("curriculum_issues")):
            result["decision"] = "blocked"
    else:
        skip("education", "No curriculum specification provided.")
    if "cost_spec" in paths:
        def budget():
            data = _read_json(paths["cost_spec"])
            return cost_plan(data["scenes"], data["budget_cents"])
        plan = stage("cost", budget)
        if plan is not None and plan["decision"] != "plan_only":
            result["decision"] = "blocked"
    else:
        skip("cost", "No user-supplied cost estimates provided.")
    if tracks:
        repair = stage("consensus_repair", lambda: guarded_repair(
            paths["audio"], paths["lyrics"], paths["srt"], paths["alignment_run"],
            tracks, destination / "caption-review", spec.get("tolerance_ms", 100)))
        if repair is None or repair["decision"] != "review":
            result["decision"] = "blocked"
    else:
        repair = None
        skip("consensus_repair", "No supplementary evidence track.", blocked=True)
    if repair is not None and repair["decision"] == "review" and "scene_manifest" in paths:
        def check_av():
            captions = parse_srt((destination / "caption-review" / "REVIEW_ONLY.srt").read_text(encoding="utf-8"))
            return audiovisual_review(captions, _read_json(paths["scene_manifest"]), repair["duration_seconds"])
        av = stage("audiovisual", check_av)
        if av is None or av["decision"] != "manifest_consistent":
            result["decision"] = "blocked"
    else:
        skip("audiovisual", "Verified draft captions and scene manifest required.", blocked=True)
    if "bilingual_reference" in paths:
        captions_path = paths["srt"]
        if repair is not None and repair["decision"] == "review":
            captions_path = destination / "caption-review" / "REVIEW_ONLY.srt"
        bilingual = stage("bilingual", lambda: bilingual_review(
            parse_srt(captions_path.read_text(encoding="utf-8-sig")),
            _read_json(paths["bilingual_reference"])))
        if bilingual is None or bilingual["decision"] != "reference_consistent":
            result["decision"] = "blocked"
    else:
        skip("bilingual", "No teacher-approved bilingual reference provided.")
    if spec.get("caption_image_qa") is True:
        clean = stage("clean_caption_ocr", lambda: scan_caption_images(
            paths["video"], mode="clean",
            panel=spec.get("caption_panel", (0., .70, 1., 1.)),
            inspection=spec.get("caption_inspection"), language=spec.get("caption_language", "deu+eng"),
            max_samples=spec.get("caption_max_samples", 180)))
        if clean is None or clean["decision"] != "sample_consistent":
            result["decision"] = "blocked"
    else:
        skip("clean_caption_ocr", "Optional sampled OCR not requested.")
    if spec.get("render") is True:
        if result["decision"] != "review" or repair is None or spec.get("clean_source") is not True:
            skip("render", "Required checks unresolved or clean-source confirmation missing.", blocked=True)
        else:
            stage("render", lambda: render_draft(
                paths["video"], paths["audio"], paths["lyrics"], paths["srt"], paths["alignment_run"],
                destination / "video-review", clean_source=True, burn=spec.get("burn") is True))
    else:
        skip("render", "Explicit render option not requested.")
    if (spec.get("caption_image_qa") is True and spec.get("burn") is True
            and result["stages"]["render"]["status"] == "completed"):
        checked = stage("rendered_caption_ocr", lambda: scan_caption_images(
            destination / "video-review" / "DRAFT_REQUIRES_HUMAN_REVIEW.mp4",
            destination / "video-review" / "repaired.srt",
            panel=spec.get("caption_panel", (0., .70, 1., 1.)),
            inspection=spec.get("caption_inspection"), language=spec.get("caption_language", "deu+eng"),
            max_samples=spec.get("caption_max_samples", 180)))
        if checked is None or checked["decision"] != "sample_consistent":
            result["decision"] = "blocked"
    (destination / "project-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2,
        allow_nan=False), encoding="utf-8")
    write_dashboard(result, destination / "dashboard.html")
    return result


def _command(args):
    result = run_project(args.manifest, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if result["decision"] == "blocked" else 3


def register(sub):
    parser = sub.add_parser("quality-run", help="Run explicitly configured local project QA stages")
    parser.add_argument("manifest")
    parser.add_argument("-o", "--output", required=True)
    parser.set_defaults(func=_command)
