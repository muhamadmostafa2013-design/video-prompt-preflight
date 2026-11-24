"""Conservative caption image audit and teacher-declared German phrase checks."""
from __future__ import annotations

import csv
import io
import json
import math
import subprocess
from collections import Counter
from pathlib import Path

from .song_alignment import _hash, _number, _tokens
from .subtitle_sync import parse_srt


def phrase_issues(text, targets):
    """Detect omissions inside declared phrases; never auto-insert a guessed noun."""
    if not isinstance(targets, list) or len(targets) > 100:
        raise ValueError("Provide at most 100 teacher-approved target phrases.")
    observed = _tokens(text)
    issues = []
    for target in targets:
        if not isinstance(target, str):
            raise TypeError("Target phrase must be text.")
        words = _tokens(target)
        if not 2 <= len(words) <= 12:
            raise ValueError("Target phrases need 2..12 tokens.")
        # Only diagnose a bounded deletion that keeps the initial/final anchor.
        for start in range(len(observed)):
            for width in range(2, len(words)):
                span = observed[start:start+width]
                if len(span) != width or span[0] != words[0] or span[-1] != words[-1]:
                    continue
                cursor = 0
                for word in span:
                    while cursor < len(words) and words[cursor] != word:
                        cursor += 1
                    if cursor == len(words):
                        break
                    cursor += 1
                else:
                    if observed[start:start+len(words)] != words:
                        issues.append({"code": "possible_incomplete_target_phrase",
                                       "expected": target, "observed": " ".join(span)})
    return issues


def caption_observation(expected, observed, outside=(), targets=None):
    """OCR evidence only. Both a missing expected token and extra text require review."""
    if not isinstance(expected, str) or not isinstance(observed, str):
        raise TypeError("Caption observations must be text.")
    want, got = _tokens(expected), _tokens(observed)
    missing = list((Counter(want)-Counter(got)).elements())
    extra = list((Counter(got)-Counter(want)).elements())
    issues = []
    if missing:
        issues.append({"code": "expected_caption_tokens_missing", "tokens": missing})
    if extra:
        issues.append({"code": "unexpected_caption_tokens", "tokens": extra})
    if want and got and not missing and not extra and want != got:
        issues.append({"code": "caption_token_order_differs"})
    if not want and got:
        issues.append({"code": "text_detected_in_clean_or_gap_region"})
    if any(_tokens(text) for text in outside):
        issues.append({"code": "possible_residual_text_outside_panel",
                       "observed": list(outside)})
    issues.extend(phrase_issues(observed, targets or []))
    return {"decision": "needs_review" if issues else "sample_consistent",
            "issues": issues, "publication_approved": False,
            "limitations": "OCR may miss stylized/low-confidence text; no absence, grammar, translation or publication certification."}


def _run(command, **kwargs):
    return subprocess.run(command, check=True, capture_output=True, timeout=45, **kwargs).stdout


def _ocr(image, language, min_confidence):
    data = _run(["tesseract", "stdin", "stdout", "-l", language, "--psm", "11", "tsv"],
                input=image)
    rows = csv.DictReader(io.StringIO(data.decode("utf-8", errors="replace")), delimiter="\t")
    accepted, rejected = [], 0
    for row in rows:
        token = row.get("text", "").strip()
        if not token:
            continue
        confidence = float(row["conf"])
        if confidence >= min_confidence:
            accepted.append(token)
        else:
            rejected += 1
    return " ".join(accepted), rejected


def scan_caption_images(video, srt=None, *, targets=None, mode="rendered",
                        panel=(0., .70, 1., 1.), language="deu+eng",
                        max_samples=180, min_confidence=40, samples_per_cue=3):
    """Inspect multiple points per caption and gap, and side strips of the declared panel."""
    if mode not in ("clean", "rendered"):
        raise ValueError("Mode must be clean or rendered.")
    if not isinstance(panel, (list, tuple)) or len(panel) != 4 or any(not _number(x) for x in panel):
        raise ValueError("Panel must have four finite normalized coordinates.")
    x0, y0, x1, y1 = panel
    if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
        raise ValueError("Invalid normalized caption panel.")
    if language not in ("deu+eng", "deu", "eng", "ara", "deu+eng+ara"):
        raise ValueError("Unsupported OCR language.")
    if type(max_samples) is not int or not 1 <= max_samples <= 600:
        raise ValueError("Sample limit must be 1..600.")
    if type(samples_per_cue) is not int or not 1 <= samples_per_cue <= 5:
        raise ValueError("Use 1..5 samples per cue.")
    if not _number(min_confidence) or not 0 <= min_confidence <= 100:
        raise ValueError("Invalid OCR confidence.")
    path = Path(video).resolve(strict=True)
    data = json.loads(_run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                            "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
                            "-of", "json", str(path)]))
    width, height = data["streams"][0]["width"], data["streams"][0]["height"]
    duration = float(data["format"]["duration"])
    if not math.isfinite(duration) or not 0 < duration <= 1800:
        raise ValueError("Unsupported duration.")
    if mode == "rendered" and srt is None:
        raise ValueError("Expected SRT required for rendered caption check.")
    captions = parse_srt(Path(srt).read_text(encoding="utf-8-sig")) if srt else []
    points = []
    cursor = 0.
    for cue in captions:
        start, end = cue["start_ms"]/1000, cue["end_ms"]/1000
        if start < cursor or end > duration+.001:
            raise ValueError("Caption overlaps or exceeds video duration.")
        if start-cursor > .15:
            points.append(((start+cursor)/2, ""))
        for i in range(samples_per_cue):
            at = start+(end-start)*(i+.5)/samples_per_cue
            expected = " ".join(cue["lines"]) if "ara" in language else cue["lines"][0]
            points.append((at, expected if mode == "rendered" else ""))
        cursor = end
    if duration-cursor > .15 and captions:
        points.append(((duration+cursor)/2, ""))
    if not captions:
        points = [(min(i+.5, duration/2 if duration < 1 else duration-.001), "")
                  for i in range(math.ceil(duration))]
    if not points or len(points) > max_samples:
        raise ValueError("Sample limit exceeded; split the review or increase explicit limit.")
    bounds = (round(x0*width), round(y0*height), round(x1*width), round(y1*height))
    left, top, right, bottom = bounds
    regions = [("panel", left, top, right-left, bottom-top)]
    if left >= 16:
        regions.append(("left_strip", 0, top, left, bottom-top))
    if width-right >= 16:
        regions.append(("right_strip", right, top, width-right, bottom-top))
    if height-bottom >= 16:
        regions.append(("bottom_strip", 0, bottom, width, height-bottom))
    if right-left < 16 or bottom-top < 16:
        raise ValueError("Caption panel is too small.")
    rows = []
    for seconds, expected in points:
        observed = {}
        uncertain = 0
        for name, x, y, w, h in regions:
            image = _run(["ffmpeg", "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
                          "-ss", f"{seconds:.6f}", "-i", str(path), "-frames:v", "1",
                          "-vf", f"crop={w}:{h}:{x}:{y}", "-f", "image2pipe", "-vcodec", "png", "-"])
            if not image:
                raise ValueError("No frame extracted.")
            text, rejected = _ocr(image, language, min_confidence)
            observed[name] = text
            uncertain += rejected
        row = caption_observation(expected, observed["panel"],
                                  [v for k, v in observed.items() if k != "panel"], targets)
        if uncertain:
            row["decision"] = "needs_review"
            row["issues"].append({"code": "low_confidence_ocr", "count": uncertain})
        rows.append({"seconds": round(seconds, 6), "expected": expected,
                     "observed_regions": observed, **row})
    return {"decision": "needs_review" if any(r["issues"] for r in rows) else "sample_consistent",
            "video_sha256": _hash(path), "mode": mode, "language": language,
            "samples": len(rows), "rows": rows, "publication_approved": False,
            "limitations": "Sampled OCR of declared lower panel and adjacent strips; not full-frame/all-frame text absence. Arabic not checked unless selected."}


def _command(args):
    targets = json.loads(Path(args.targets).read_text(encoding="utf-8")) if args.targets else []
    result = scan_caption_images(args.video, args.srt, mode=args.mode, targets=targets,
                                 panel=args.panel, language=args.language, max_samples=args.max_samples)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 2 if result["decision"] == "needs_review" else 3


def register(sub):
    parser = sub.add_parser("caption-image-qa", help="Review rendered or clean caption regions with local OCR")
    parser.add_argument("video")
    parser.add_argument("--srt")
    parser.add_argument("--targets")
    parser.add_argument("--mode", choices=["clean", "rendered"], default="rendered")
    parser.add_argument("--panel", type=float, nargs=4, default=(0., .70, 1., 1.))
    parser.add_argument("--language", default="deu+eng")
    parser.add_argument("--max-samples", type=int, default=180)
    parser.set_defaults(func=_command)
