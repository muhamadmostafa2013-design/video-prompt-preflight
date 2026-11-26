"""Local post-production checks, reproducible fault injection, and safe media drafts."""
from __future__ import annotations

import importlib.util
import json
import random
import re
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from .song_alignment import _hash, _stamp, _tokens
from .subtitle_sync import audit_sync, load_evidence, parse_srt, repair_srt


def _run(args, *, cwd=None, timeout=120):
    try:
        return subprocess.run(args, cwd=cwd, check=True, capture_output=True,
                              timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"Local media command failed: {args[0]}") from exc


def _probe(path):
    return json.loads(_run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                            "-show_streams", "-show_format", "-of", "json", "-i", str(path)]))


def _one_stream(info, kind):
    streams = [s for s in info["streams"] if s.get("codec_type") == kind]
    if len(streams) != 1:
        raise ValueError(f"Exactly one {kind} stream is required.")
    return streams[0]


def _stream_hash(path, kind, *, decoded=False):
    args = ["ffmpeg", "-v", "error", "-protocol_whitelist", "file,pipe",
            "-i", str(path), "-map", f"0:{kind}:0"]
    if decoded:
        args += ["-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]
    else:
        args += ["-c", "copy"]
    return _run(args + ["-f", "streamhash", "-hash", "sha256", "-"]).decode().strip()


def _timeline(path, kind):
    data = json.loads(_run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                            "-select_streams", f"{kind}:0", "-show_packets",
                            "-show_entries", "packet=pts_time,dts_time,duration_time",
                            "-of", "json", "-i", str(path)]))
    return [[float(p[k]) if k in p and p[k] != "N/A" else None
             for k in ("pts_time", "dts_time", "duration_time")] for p in data["packets"]]


def _same_timeline(a, b, tolerance=.001):
    return len(a) == len(b) and all(
        all((x is None and y is None) or
            (x is not None and y is not None and abs(x-y) <= tolerance)
            for x, y in zip(p, q)) for p, q in zip(a, b))


def model_readiness():
    """Discover local dependencies, never assume downloaded weights or select paid APIs."""
    packages = {}
    for package in ("demucs", "whisperx", "faster_whisper", "torch"):
        try:
            packages[package] = importlib.util.find_spec(package) is not None
        except (ImportError, ValueError):
            packages[package] = False
    return {"binaries": {name: bool(shutil.which(name)) for name in ("ffmpeg", "ffprobe", "tesseract")},
            "packages_current_interpreter": packages, "model_weights_verified": False,
            "selected_route": "local_demucs_whisperx" if packages["demucs"] and packages["whisperx"]
            else "blocked_missing_local_dependencies",
            "remote_fallback": False, "notes": "Separate virtual environments may be used. Package presence does not prove model availability."}


def language_review(captions, glossary):
    """Restricted lexical and script checks, not grammar or translation certification."""
    if not isinstance(glossary, dict):
        raise TypeError("Glossary must map German phrases to Arabic phrase lists.")
    for phrase, alternatives in glossary.items():
        if not isinstance(phrase, str) or not _tokens(phrase):
            raise ValueError("Invalid glossary German phrase.")
        if not isinstance(alternatives, list) or not alternatives or any(
                not isinstance(a, str) or not _tokens(a) for a in alternatives):
            raise ValueError("Each glossary value needs Arabic phrase alternatives.")
    issues = []
    hits = dict.fromkeys(glossary, 0)
    for cue in captions:
        de = cue["lines"][0]
        ar = " ".join(cue["lines"][1:])
        if re.search(r"[\u0600-\u06ff]", de):
            issues.append({"code": "german_line_arabic", "cue": cue["index"]})
        if not re.search(r"[\u0621-\u064a]", ar):
            issues.append({"code": "arabic_translation_missing", "cue": cue["index"]})
        for phrase, alternatives in glossary.items():
            if " " + " ".join(_tokens(phrase)) + " " in " " + " ".join(_tokens(de)) + " ":
                hits[phrase] += 1
                if not any(" " + " ".join(_tokens(a)) + " " in " " + " ".join(_tokens(ar)) + " "
                           for a in alternatives):
                    issues.append({"code": "glossary_translation_review", "cue": cue["index"],
                                   "target": phrase})
    for phrase, count in hits.items():
        if not count:
            issues.append({"code": "target_not_found_in_single_cue", "target": phrase})
    return {"decision": "review", "issues": issues, "target_counts": hits,
            "limitations": "Curated glossary and script only; grammar, pronunciation and meaning require teacher review.",
            "publication_approved": False}


def visual_scan(video):
    """Decode whole video and inspect all one-second grayscale samples; no identity claims."""
    path = Path(video).resolve(strict=True)
    info = _probe(path)
    _one_stream(info, "video")
    duration = float(info["format"]["duration"])
    if not 0 < duration <= 1800:
        raise ValueError("Visual scan supports videos up to 30 minutes.")
    # Whole-video decoder catches corrupt frames; 1-Hz samples are a separate heuristic.
    _run(["ffmpeg", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
          "-i", str(path), "-map", "0:v:0", "-an", "-f", "null", "-"], timeout=600)
    raw = _run(["ffmpeg", "-v", "error", "-protocol_whitelist", "file,pipe",
                "-i", str(path), "-map", "0:v:0", "-vf", "fps=1,scale=32:32,format=gray",
                "-an", "-f", "rawvideo", "-"], timeout=600)
    size = 1024
    if not raw or len(raw) % size:
        raise ValueError("No valid visual samples.")
    frames = [raw[i:i+size] for i in range(0, len(raw), size)]
    alerts = []
    for i, frame in enumerate(frames):
        mean = sum(frame) / size
        if mean < 10:
            alerts.append({"sample": i, "code": "very_dark_frame"})
        if i:
            diff = sum(abs(x-y) for x, y in zip(frame, frames[i-1])) / size
            if diff > 60:
                alerts.append({"sample": i, "code": "large_visual_change", "mean_difference": round(diff, 2)})
            if diff < .2:
                alerts.append({"sample": i, "code": "near_identical_samples"})
    return {"decision": "review", "full_video_decode": "completed", "sample_rate_hz": 1,
            "samples": len(frames), "alerts": alerts, "publication_approved": False,
            "limitations": "Sampled luminance/change only. Intentional stills/cuts can trigger. No face identity, clothing, OCR, scene meaning or all-frame content certification."}


def render_draft(video, audio, lyrics, old_srt, alignment_run, output, *, clean_source, burn=False):
    """Recompute acoustic repair then create a new MP4, never overwrite input."""
    if clean_source is not True:
        raise ValueError("Confirm the video has no burned-in captions before repair.")
    video = Path(video).resolve(strict=True)
    audio = Path(audio).resolve(strict=True)
    info = _probe(video)
    v, a = _one_stream(info, "video"), _one_stream(info, "audio")
    if not 0 < float(info["format"]["duration"]) <= 1800:
        raise ValueError("Render supports videos up to 30 minutes.")
    for stream in (v, a):
        if abs(float(stream.get("start_time", 0))) > .001:
            raise ValueError("Nonzero stream start: normalize and align the exact clean source first.")
    if video != audio and _stream_hash(video, "a", decoded=True) != _stream_hash(audio, "a", decoded=True):
        raise ValueError("Video audio differs from aligned source; align the clean video itself.")
    words, duration, min_score = load_evidence(audio, lyrics, alignment_run)
    if abs(float(info["format"]["duration"]) - duration) > .15:
        raise ValueError("Video duration differs from alignment evidence.")
    if len(words) > 20000:
        raise ValueError("Oversized acoustic evidence.")
    captions = parse_srt(Path(old_srt).read_text(encoding="utf-8-sig"))
    lines = [s.strip() for s in Path(lyrics).read_text(encoding="utf-8-sig").splitlines() if s.strip()]
    report = audit_sync(captions, lines, words, duration, min_score=max(.5, min_score))
    repaired = repair_srt(captions, report)
    recheck = audit_sync(parse_srt(repaired), lines, words, duration, min_score=max(.5, min_score))
    if recheck["timing_status"] != "within_tolerance" or recheck["metrics"]["max_absolute_ms"]:
        raise ValueError("Repaired subtitle recheck failed.")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="vpp-render-") as temp:
        root = Path(temp)
        (root / "draft.srt").write_text(repaired, encoding="utf-8")
        target = root / "draft.mp4"
        command = ["ffmpeg", "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
                   "-i", str(video)]
        if burn:
            command += ["-map", "0:v:0", "-map", "0:a:0", "-vf",
                        "subtitles=draft.srt:force_style='FontName=DejaVu Sans,FontSize=20,Outline=2,Alignment=2'",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "copy"]
        else:
            command += ["-i", "draft.srt", "-map", "0:v:0", "-map", "0:a:0", "-map", "1:0",
                        "-c:v", "copy", "-c:a", "copy", "-c:s", "mov_text"]
        _run(command + ["-movflags", "+faststart", str(target)], cwd=root, timeout=900)
        out = _probe(target)
        ov, oa = _one_stream(out, "video"), _one_stream(out, "audio")
        if (ov["width"], ov["height"]) != (v["width"], v["height"]):
            raise ValueError("Rendered video dimensions changed.")
        if abs(float(out["format"]["duration"]) - float(info["format"]["duration"])) > .1:
            raise ValueError("Rendered video duration changed.")
        if _stream_hash(video, "a") != _stream_hash(target, "a") or not _same_timeline(
                _timeline(video, "a"), _timeline(target, "a")):
            raise ValueError("Audio packet content/timeline changed.")
        if abs(float(oa.get("start_time", 0))) > .001:
            raise ValueError("Output audio start shifted.")
        if not burn:
            if _stream_hash(video, "v") != _stream_hash(target, "v") or not _same_timeline(
                    _timeline(video, "v"), _timeline(target, "v")):
                raise ValueError("Video packet content/timeline changed.")
            decoded = _run(["ffmpeg", "-v", "error", "-i", str(target), "-map", "0:s:0",
                            "-f", "srt", "-"]).decode("utf-8")
            if parse_srt(decoded) != parse_srt(repaired):
                raise ValueError("Embedded subtitle roundtrip differs from repaired draft.")
        _run(["ffmpeg", "-v", "error", "-xerror", "-i", str(target), "-map", "0:a:0",
              "-vn", "-f", "null", "-"], timeout=600)
        visual = visual_scan(target)
        result_path = output / "DRAFT_REQUIRES_HUMAN_REVIEW.mp4"
        shutil.copyfile(target, result_path)
    (output / "repaired.srt").write_text(repaired, encoding="utf-8")
    result = {"decision": "review", "publication_approved": False, "human_listening_verified": False,
              "mode": "burned_draft" if burn else "selectable_subtitles",
              "source_sha256": _hash(video), "output_sha256": _hash(result_path),
              "audio_packets_and_timeline_preserved": True, "full_audio_decode": "completed",
              "packet_timestamp_tolerance_ms": 1,
              "video_packets_and_timeline_preserved": not burn,
              "embedded_subtitle_roundtrip_verified": not burn,
              "post_repair_metrics": recheck["metrics"], "visual": visual,
              "limitations": "Clean-source confirmation is user supplied. Burned text visibility, translation, scene continuity and listening still require manual QA."}
    (output / "render_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def simulate_faults(seed=20261124, trials=600):
    """Known-answer randomized fixtures, including timing and unsafe repair mutations."""
    if type(trials) is not int or not 1 <= trials <= 10000:
        raise ValueError("Trials must be 1..10000.")
    rng = random.Random(seed)
    counts = Counter()
    failures = []
    variants = ("drift", "missing_word", "low_score", "overlap", "wrong_caption", "repeat_missing")
    for i in range(trials):
        fault = variants[i % len(variants)]
        counts[fault] += 1
        lines = ["Ein Nomen", "ein Verb", "Ein Nomen", "ein Verb"]
        words = []
        cues = []
        for j, line in enumerate(lines):
            start = 3000 + j * 4000 + rng.randint(0, 500)
            for k, token in enumerate(line.split()):
                words.append({"word": token, "start": (start+k*300)/1000,
                              "end": (start+(k+1)*300)/1000, "score": .95})
            shift = rng.choice([-1, 1]) * rng.randint(200, 1400)
            cues.append(f"{j+1}\n{_stamp((start+shift)/1000)} --> "
                        f"{_stamp((start+shift+600)/1000)}\n{line}\nاسم وفعل")
        if fault == "missing_word":
            words.pop(rng.randrange(len(words)))
        elif fault == "low_score":
            words[rng.randrange(len(words))]["score"] = .1
        elif fault == "overlap":
            words[1]["start"] = words[0]["start"]
        elif fault == "wrong_caption":
            cues[0] = cues[0].replace("Nomen", "Haus")
        elif fault == "repeat_missing":
            cues = cues[:2]
        parsed = parse_srt("\n\n".join(cues))
        result = audit_sync(parsed, lines, words, 20)
        if fault == "drift":
            if result["decision"] != "review" or result["timing_status"] != "needs_repair":
                failures.append({"trial": i, "fault": fault, "reason": "drift not detected"})
                continue
            fixed = parse_srt(repair_srt(parsed, result))
            result = audit_sync(fixed, lines, words, 20)
            if (result["metrics"]["max_absolute_ms"] or
                    [c["lines"] for c in parsed] != [c["lines"] for c in fixed]):
                failures.append({"trial": i, "fault": fault, "reason": "repair differs from fixture"})
        elif result["decision"] != "blocked":
            failures.append({"trial": i, "fault": fault, "reason": "unsafe evidence accepted"})
        if result["publication_approved"]:
            failures.append({"trial": i, "fault": fault, "reason": "false publication approval"})
    return {"seed": seed, "trials": trials, "fault_counts": dict(counts),
            "failed_trials": len({f["trial"] for f in failures}), "failures": failures,
            "decision": "fail" if failures else "pass_simulation",
            "publication_approved": False, "basis": "synthetic known-answer fixtures, not real song accuracy"}


def _emit(result):
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


def _simulate(args):
    result = simulate_faults(args.seed, args.trials)
    _emit(result)
    return 2 if result["failures"] else 0


def _models(_args):
    _emit(model_readiness())
    return 3


def _visual(args):
    _emit(visual_scan(args.video))
    return 3


def _language(args):
    captions = parse_srt(Path(args.srt).read_text(encoding="utf-8-sig"))
    _emit(language_review(captions, json.loads(Path(args.glossary).read_text(encoding="utf-8"))))
    return 3


def _render(args):
    _emit(render_draft(args.video, args.audio, args.lyrics, args.srt,
                       args.alignment_run, args.output, clean_source=args.clean_source, burn=args.burn))
    return 3


def register(sub):
    sim = sub.add_parser("quality-simulate", help="Run seeded synthetic known-answer fault injection")
    sim.add_argument("--seed", type=int, default=20261124)
    sim.add_argument("--trials", type=int, default=600)
    sim.set_defaults(func=_simulate)
    model = sub.add_parser("model-readiness", help="Inspect free local dependencies; no paid fallback")
    model.set_defaults(func=_models)
    visual = sub.add_parser("visual-scan", help="Full decode plus one-second visual heuristics")
    visual.add_argument("video")
    visual.set_defaults(func=_visual)
    language = sub.add_parser("caption-language-qa", help="Check DE/AR script and curated glossary")
    language.add_argument("srt")
    language.add_argument("--glossary", required=True)
    language.set_defaults(func=_language)
    render = sub.add_parser("repair-video", help="Generate review-only MP4 from clean video and acoustic evidence")
    render.add_argument("video")
    render.add_argument("--audio", required=True)
    render.add_argument("--lyrics", required=True)
    render.add_argument("--srt", required=True)
    render.add_argument("--alignment-run", required=True)
    render.add_argument("-o", "--output", required=True)
    render.add_argument("--clean-source", action="store_true", help="Confirm no existing burned captions")
    render.add_argument("--burn", action="store_true", help="Burn a review draft using libass; requires visual inspection")
    render.set_defaults(func=_render)
