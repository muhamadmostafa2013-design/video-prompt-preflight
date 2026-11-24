"""Local song post-production QA; machine alignment is never listening approval."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path


def _written_tokens(text):
    """Case-preserving normalized tokens for teacher-authored written text."""
    return re.findall(r"[^\W_]+(?:['’\-][^\W_]+)*", unicodedata.normalize("NFC", text))


def _tokens(text):
    # Speech recognition comparisons are intentionally case-insensitive.
    return _written_tokens(unicodedata.normalize("NFC", text).lower())


def _number(value):
    if type(value) not in (int, float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def audit_words(lines, words, duration, min_score=0.5):
    """Validate actual WhisperX word evidence, without interpolating missing times."""
    if not _number(duration) or duration <= 0:
        raise ValueError("Positive finite audio duration required.")
    if not _number(min_score) or not 0 <= min_score <= 1:
        raise ValueError("min_score must be in [0, 1].")
    if not isinstance(lines, (list, tuple)) or not lines or any(
            not isinstance(line, str) or not _tokens(line) for line in lines):
        raise ValueError("Reference needs nonempty lyric lines, including all repeats.")
    if not isinstance(words, list):
        raise TypeError("word_segments must be a list.")
    expected = [token for line in lines for token in _tokens(line)]
    observed = []
    issues = []
    previous_end = 0.0
    for i, word in enumerate(words):
        if not isinstance(word, dict) or not isinstance(word.get("word"), str):
            issues.append(f"word {i + 1}: malformed record")
            continue
        tokens = _tokens(word["word"])
        if len(tokens) != 1:
            issues.append(f"word {i + 1}: not exactly one lexical token")
        observed.extend(tokens)
        start, end, score = word.get("start"), word.get("end"), word.get("score")
        if not (_number(start) and _number(end) and 0 <= start < end <= duration):
            issues.append(f"word {i + 1}: missing or invalid acoustic timestamps")
        else:
            if start < previous_end:
                issues.append(f"word {i + 1}: overlaps or moves backwards")
            previous_end = max(previous_end, end)
        if not _number(score) or not min_score <= score <= 1:
            issues.append(f"word {i + 1}: missing or low alignment score")
    if not words:
        issues.append("No words recognized.")
    if expected != observed:
        issues.append("Reference and recognized words differ (including repetitions/order).")
    cues = []
    if not issues:
        offset = 0
        for line in lines:
            count = len(_tokens(line))
            span = words[offset:offset + count]
            cues.append({"start": span[0]["start"], "end": span[-1]["end"], "text": line})
            offset += count
    return {"decision": "blocked" if issues else "review",
            "human_listening_verified": False, "publication_approved": False,
            "expected_words": len(expected), "observed_words": len(observed),
            "issues": issues, "cues": cues,
            "limitations": "ASR and alignment scores are not proof of lyric accuracy or human listening. Singing and backing vocals need manual review."}


def _stamp(seconds):
    ms = round(seconds * 1000)
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def draft_srt(report, translations=None):
    if report["decision"] != "review" or not report["cues"]:
        raise ValueError("No subtitle draft: alignment evidence is blocked.")
    if translations is not None and (len(translations) != len(report["cues"]) or
            any(not isinstance(t, str) or not t.strip() or "\n" in t or "\r" in t for t in translations)):
        raise ValueError("Provide one nonempty translation per exact reference line.")
    rows = []
    for i, cue in enumerate(report["cues"]):
        if round(cue["start"] * 1000) >= round(cue["end"] * 1000):
            raise ValueError("Sub-millisecond cue cannot be represented in SRT.")
        text = cue["text"] + ("\n" + translations[i] if translations is not None else "")
        rows.append(f"{i+1}\n{_stamp(cue['start'])} --> {_stamp(cue['end'])}\n{text}")
    return "\n\n".join(rows) + "\n"


def _duration(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_entries", "format=duration",
                             "-of", "default=nw=1:nk=1", str(path)],
                            check=True, capture_output=True, text=True, timeout=60)
    value = float(result.stdout.strip())
    if not _number(value) or value <= 0:
        raise ValueError("Invalid media duration.")
    return value


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command, log, env):
    with log.open("w", encoding="utf-8") as handle:
        subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, check=True,
                       env=env, timeout=7200)


def run_alignment(args):
    audio = Path(args.audio).resolve(strict=True)
    lines = Path(args.lyrics).read_text(encoding="utf-8").splitlines()
    lines = [line.strip() for line in lines if line.strip()]
    translations = None
    if args.translations:
        translations = Path(args.translations).read_text(encoding="utf-8").splitlines()
        if len(translations) != len(lines) or any(not line.strip() for line in translations):
            raise ValueError("One translation per nonblank German line is required.")
    if not lines or any(not _tokens(line) for line in lines):
        raise ValueError("Reference must contain real lyric lines, not section labels.")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"decision": "blocked", "human_listening_verified": False,
              "publication_approved": False, "stage": "source",
              "audio_sha256": _hash(audio), "issues": []}
    env = os.environ.copy()
    if not args.allow_model_downloads:
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
    try:
        duration = _duration(audio)
        report["duration_seconds"] = duration
        report["stage"] = "demucs"
        # A local Demucs model repository avoids automatic weight downloads.
        if not args.demucs_repo and not args.allow_model_downloads:
            raise ValueError("Supply --demucs-repo with local weights or explicitly allow model downloads.")
        demucs = [args.demucs_python, "-m", "demucs", "-n", "htdemucs",
                  "--two-stems", "vocals", "-d", args.device, "-o", str(output / "stems")]
        if args.demucs_repo:
            demucs += ["--repo", str(Path(args.demucs_repo).resolve(strict=True))]
        _run(demucs + [str(audio)], output / "demucs.log", env)
        vocals = output / "stems" / "htdemucs" / audio.stem / "vocals.wav"
        if abs(_duration(vocals) - duration) > 0.15:
            raise ValueError("Vocal stem duration differs from original; cannot preserve timeline.")
        report["vocals_sha256"] = _hash(vocals)
        report["stage"] = "whisperx"
        asr_dir = output / "asr"
        asr_dir.mkdir()
        command = [args.whisperx_python, "-m", "whisperx", str(vocals),
                   "--language", "de", "--task", "transcribe", "--model", args.model,
                   "--device", args.device, "--compute_type", "int8" if args.device == "cpu" else "float16",
                   "--batch_size", "4", "--vad_method", "silero",
                   "--output_dir", str(asr_dir), "--output_format", "json",
                   "--interpolate_method", "ignore"]
        if not args.allow_model_downloads:
            command += ["--model_cache_only", "True"]
        _run(command, output / "whisperx.log", env)
        evidence_path = asr_dir / "vocals.json"
        raw = json.loads(evidence_path.read_text(encoding="utf-8"))
        report["evidence_schema"] = "vpp.whisperx.words.v1"
        report["word_evidence_sha256"] = _hash(evidence_path)
        report["reference_sha256"] = _hash(Path(args.lyrics))
        report["min_score"] = args.min_score
        report["model"] = args.model
        report["stage"] = "word_evidence"
        evidence = audit_words(lines, raw.get("word_segments", []), duration, args.min_score)
        report.update(evidence)
        if report["decision"] == "review":
            srt = draft_srt(report, translations)
            (output / "DRAFT_REQUIRES_LISTENING.srt").write_text(srt, encoding="utf-8")
    except (OSError, ValueError, TypeError, AttributeError, subprocess.SubprocessError) as exc:
        report["decision"] = "blocked"
        report["issues"].append(f"{report['stage']}: {exc}")
    (output / "alignment_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 3 if report["decision"] == "review" else 2


def register(sub):
    p = sub.add_parser("align-song", help="Local Demucs + WhisperX acoustic lyric evidence (review only)")
    p.add_argument("audio", help="Original song file")
    p.add_argument("--lyrics", required=True, help="Exact German lyrics, one sung line per line, repeats included")
    p.add_argument("--translations", help="Optional Arabic translations, one per German line")
    p.add_argument("-o", "--output", required=True, help="New output directory, must not exist")
    p.add_argument("--demucs-python", default=sys.executable)
    p.add_argument("--whisperx-python", default=sys.executable)
    p.add_argument("--demucs-repo", help="Local directory of Demucs weights")
    p.add_argument("--allow-model-downloads", action="store_true", help="Permit downloading model weights, never upload audio")
    p.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    p.add_argument("--model", default="large-v3", help="WhisperX ASR model or local model path")
    p.add_argument("--min-score", type=float, default=0.5, help="Heuristic acoustic alignment floor, not a probability")
    p.set_defaults(func=run_alignment)
