"""Desktop acoustic pipeline: explicit local models, no publication authorization."""
from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

from .acoustic_models import LocalGermanCTC
from .acoustic_review import review_evidence
from .intelligence_workflow import guarded_repair
from .quality_engine import visual_scan
from .song_alignment import _hash, run_alignment
from .subtitle_sync import parse_srt
from .waveform import waveform


def run_desktop_review(video, lyrics, srt, demucs_repo, whisper_model, ctc_model, output,
                       *, demucs_python=sys.executable, whisperx_python=sys.executable):
    """Run two model families and the existing conservative repair gate in a new directory."""
    video, lyrics, srt = (Path(p).resolve(strict=True) for p in (video, lyrics, srt))
    demucs_repo, whisper_model, ctc_model = (Path(p).resolve(strict=True)
                                            for p in (demucs_repo, whisper_model, ctc_model))
    if not all(p.is_file() for p in (video, lyrics, srt)):
        raise ValueError("Select local video, lyrics and subtitles.")
    if not all(p.is_dir() for p in (demucs_repo, whisper_model, ctc_model)):
        raise ValueError("Select existing local model directories.")
    if srt.stat().st_size > 4*1024*1024 or lyrics.stat().st_size > 4*1024*1024:
        raise ValueError("Text inputs exceed local review limit.")
    parse_srt(srt.read_text(encoding="utf-8-sig"))
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    source_hashes = [_hash(p) for p in (video, lyrics, srt)]
    result = {"decision": "blocked", "publication_approved": False,
              "human_listening_verified": False, "stages": {}}

    def stage(name, fn):
        try:
            data = fn()
            json.dumps(data, allow_nan=False)
            result["stages"][name] = {"status": "completed", "evidence": data}
            return data
        except Exception as exc:  # noqa: BLE001 -- report every failed local stage
            result["stages"][name] = {"status": "failed", "error": str(exc), "error_type": type(exc).__name__}
            return None

    wave = stage("waveform", lambda: waveform(video))
    visual = stage("video_decode", lambda: visual_scan(video))
    aligned = None
    track = None
    if wave is not None and visual is not None:
        def align():
            args = Namespace(audio=str(video), lyrics=str(lyrics), translations=None,
                             output=str(root / "alignment"), demucs_python=demucs_python,
                             whisperx_python=whisperx_python, demucs_repo=str(demucs_repo),
                             allow_model_downloads=False, device="cpu", model=str(whisper_model),
                             min_score=.5)
            code = run_alignment(args)
            if code != 3:
                raise ValueError("WhisperX alignment blocked; inspect alignment report and local logs.")
            return {"decision": "review", "publication_approved": False}
        aligned = stage("whisperx", align)
        track = stage("ctc", lambda: LocalGermanCTC(ctc_model).transcribe(video))
    if track is not None:
        stage("acoustic_drift_1", lambda: {**review_evidence(video, srt, track),
                                           "model": track.get("model"), "backend": track.get("backend")})
    if (aligned is not None and track is not None and
            [_hash(p) for p in (video, lyrics, srt)] == source_hashes):
        repair = stage("consensus_repair", lambda: guarded_repair(
            video, lyrics, srt, root / "alignment", [track], root / "caption-review"))
        if repair is not None and repair.get("decision") == "review":
            result["decision"] = "review"
    else:
        result["stages"]["consensus_repair"] = {"status": "blocked", "reason": "Missing or changed evidence."}
    (root / "project-report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2,
        allow_nan=False), encoding="utf-8")
    return result


def _command(args):
    report = run_desktop_review(args.video, args.lyrics, args.srt, args.demucs_repo,
                                args.whisper_model, args.ctc_model, args.output,
                                demucs_python=args.demucs_python, whisperx_python=args.whisperx_python)
    return 3 if report["decision"] == "review" else 2


def register(sub):
    parser = sub.add_parser("studio-review", help="Local WhisperX + CTC, waveform and guarded SRT review")
    for name in ("video", "lyrics", "srt", "demucs-repo", "whisper-model", "ctc-model", "output"):
        parser.add_argument("--"+name, required=True)
    parser.add_argument("--demucs-python", default=sys.executable)
    parser.add_argument("--whisperx-python", default=sys.executable)
    parser.set_defaults(func=_command)
