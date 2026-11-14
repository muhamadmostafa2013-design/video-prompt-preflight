"""Local, opt-in media QA. No uploaded video, model download, or remote API calls.

Requires ffprobe for metadata; ffmpeg+pytesseract for sampled-frame OCR;
faster-whisper with a PRE-DOWNLOADED local model for transcript evidence.
OCR/ASR are advisory: automated evidence never certifies an exact video.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import unicodedata
from pathlib import Path


class MediaQAError(RuntimeError):
    """Missing dependency, invalid media or unavailable optional checker."""


def _command(args: list[str], *, timeout: int = 30) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaQAError(f"Could not execute {args[0]}: {exc}") from exc
    if result.returncode:
        raise MediaQAError(f"{args[0]} failed: {result.stderr.strip()[:450]}")
    return result.stdout


def _need(binary: str) -> None:
    if not shutil.which(binary):
        raise MediaQAError(f"{binary} is required but was not found on PATH.")


def _norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value)).casefold()
    return " ".join(re.findall(r"[\w]+", value, flags=re.UNICODE))


def probe_video(path: str | Path) -> dict:
    """Probe actual streams instead of trusting filename/extension."""
    video = Path(path)
    if not video.is_file():
        raise MediaQAError(f"Video file does not exist: {video}")
    _need("ffprobe")
    data = json.loads(_command([
        "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-show_streams", "-show_format",
        "-of", "json", "-i", str(video)
    ]))
    streams = data.get("streams", [])
    images = [s for s in streams if s.get("codec_type") == "video"]
    if not images:
        raise MediaQAError("No video stream found.")
    stream = images[0]
    try:
        duration = float(data.get("format", {}).get("duration") or stream.get("duration") or 0)
        width, height = int(stream["width"]), int(stream["height"])
    except (ValueError, TypeError, KeyError) as exc:
        raise MediaQAError("Missing video duration or dimensions.") from exc
    if not 0 < duration <= 86400 or width < 1 or height < 1:
        raise MediaQAError("Invalid video duration or dimensions.")
    # Display ratio accounts for non-square pixels and rotation metadata.
    sar = str(stream.get("sample_aspect_ratio") or "1:1")
    ratio = width / height
    try:
        num, den = (float(x) for x in sar.split(":"))
        if num > 0 and den > 0:
            ratio *= num / den
    except (ValueError, ZeroDivisionError):
        pass
    rotation = int(float((stream.get("tags") or {}).get("rotate") or 0))
    for item in stream.get("side_data_list", []) or []:
        if "rotation" in item:
            rotation = int(float(item["rotation"]))
    if abs(rotation) % 180 == 90:
        ratio = 1 / ratio
    return {
        "duration_seconds": round(duration, 3),
        "width": width,
        "height": height,
        "aspect_ratio": round(ratio, 5),
        "rotation_degrees": rotation,
        "sample_aspect_ratio": sar,
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
    }


def _aspect_ratio(value: str) -> float:
    try:
        a, b = (float(part.strip()) for part in value.split(":"))
        if a > 0 and b > 0:
            return a / b
    except (ValueError, AttributeError):
        pass
    raise MediaQAError(f"Invalid expected aspect ratio: {value!r}")


def sample_frames(path: str | Path, duration: float, count: int, directory: str | Path) -> list[dict]:
    if not 1 <= count <= 40:
        raise MediaQAError("Frame count must be between 1 and 40.")
    _need("ffmpeg")
    frames = []
    for i in range(count):
        fraction = .5 if count == 1 else .06 + i * (.88 / (count - 1))
        at = min(max(0, duration - .04), duration * fraction)
        out = Path(directory) / f"frame-{i + 1:02d}.png"
        _command([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{at:.3f}",
            "-protocol_whitelist", "file,pipe",
            "-i", str(path), "-frames:v", "1", "-vf", "scale=960:-2",
            "-y", str(out)
        ], timeout=40)
        if not out.is_file():
            raise MediaQAError(f"Frame could not be extracted at {at:.2f}s.")
        frames.append({"seconds": round(at, 2), "path": out})
    return frames


def ocr_frames(frames: list[dict], lang: str = "eng") -> list[dict]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise MediaQAError("OCR requires: pip install 'video-prompt-preflight[media-ocr]'") from exc
    output = []
    for frame in frames:
        try:
            with Image.open(frame["path"]) as image:
                text = pytesseract.image_to_string(image, lang=lang)
        except Exception as exc:
            raise MediaQAError(
                f"OCR failed; install Tesseract and the requested language pack ({lang}): {exc}"
            ) from exc
        output.append({"seconds": frame["seconds"], "text": text.strip()[:4000]})
    return output


def transcript_local(path: str | Path, model_path: str | Path) -> str:
    model_dir = Path(model_path)
    if not model_dir.is_dir():
        raise MediaQAError("ASR requires a pre-downloaded LOCAL model directory. Remote model names are refused.")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise MediaQAError("ASR requires: pip install 'video-prompt-preflight[media-asr]'") from exc
    # No download, no API request, no persistence of raw audio.
    model = WhisperModel(str(model_dir), device="cpu", compute_type="int8", local_files_only=True)
    segments, _ = model.transcribe(str(path), beam_size=1, vad_filter=True)
    return " ".join(segment.text.strip() for segment in segments).strip()


def detect_silent_audio(path: str | Path, max_seconds: float = 15.0) -> dict:
    """Measure sampled peak volume; not a substitute for validating speech content."""
    _need("ffmpeg")
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "info",
        "-protocol_whitelist", "file,pipe", "-i", str(path), "-t", str(max_seconds), "-vn",
        "-af", "volumedetect", "-f", "null", "-"
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=45, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaQAError(f"Cannot analyze audio level: {exc}") from exc
    if result.returncode:
        raise MediaQAError(f"Audio decoder failed: {result.stderr[-220:]}")
    match = re.search(r"max_volume:\s*(-?inf|-?\d+(?:\.\d+)?)\s*dB", result.stderr)
    if not match:
        raise MediaQAError("No peak-volume evidence available in this audio stream.")
    peak = float(match.group(1))
    return {"max_volume_db": peak if peak != float("-inf") else None,
            "sampled_seconds": max_seconds, "silent": peak == float("-inf") or peak < -50}


def inspect_video(
    path: str | Path,
    scene: dict | None = None,
    *,
    ocr: bool = False,
    ocr_lang: str = "eng",
    asr_model: str | Path | None = None,
    frames: int = 8,
    duration_tolerance: float = .35,
    aspect_tolerance: float = .07,
) -> dict:
    """Return reproducible evidence, with FAIL / REVIEW / PASS metadata gate.

    Any content requiring OCR/ASR remains REVIEW even when apparently detected:
    sampled frames/transcripts can miss brief errors, speech or subtitle states.
    """
    scene = scene or {}
    if not isinstance(scene, dict):
        raise MediaQAError('Scene Spec must be a YAML/JSON object.')
    metadata = probe_video(path)
    checks: list[dict] = []
    expected_duration = scene.get("duration_seconds")
    if expected_duration is not None:
        expected = float(expected_duration)
        ok = abs(metadata["duration_seconds"] - expected) <= duration_tolerance
        checks.append({"name": "duration", "status": "pass" if ok else "fail",
                       "expected": expected, "actual": metadata["duration_seconds"]})
    aspect = scene.get("aspect_ratio")
    if aspect:
        expected_ratio = _aspect_ratio(aspect)
        ok = abs(metadata["aspect_ratio"] - expected_ratio) / expected_ratio <= aspect_tolerance
        checks.append({"name": "aspect_ratio", "status": "pass" if ok else "fail",
                       "expected": aspect, "actual": metadata["aspect_ratio"]})

    words = [str(s) for s in (scene.get("screen_text") or []) if str(s).strip()]
    spoken = scene.get("spoken") or {}
    required_speech = " ".join(
        [spoken.get("arabic", "")] +
        [str(s) for s in (spoken.get("german_by_presenter") or [])]
    ).strip()

    frame_evidence: list[dict] = []
    transcript: str | None = None
    needs_visual_policy = bool((scene.get("rules") or {}).get("no_arabic_on_screen"))
    if ocr and (words or needs_visual_policy):
        with tempfile.TemporaryDirectory(prefix="vpp-qa-") as directory:
            frame_evidence = ocr_frames(
                sample_frames(path, metadata["duration_seconds"], frames, directory), ocr_lang
            )
        for word in words:
            matched = [f["seconds"] for f in frame_evidence
                       if _norm(word) and f" {_norm(word)} " in f" {_norm(f['text'])} "]
            checks.append({"name": "exact_screen_text", "expected": word,
                           "status": "observed" if matched else "review",
                           "sampled_at_seconds": matched})
        if needs_visual_policy:
            has_arabic = any(re.search(r"[\u0600-\u06ff]", frame["text"])
                             for frame in frame_evidence)
            checks.append({"name": "forbidden_arabic_visual", "status": "review",
                           "reason": "Arabic glyphs observed in OCR sample; confirm manually"
                           if has_arabic else "No Arabic observed in sampled OCR; still needs full-video review",
                           "sampled_arabic": has_arabic})
        whitelist = scene.get("text_whitelist") or []
        if whitelist:
            allowed_tokens = set(_norm(" ".join(map(str, whitelist))).split())
            observed_tokens = set(_norm(" ".join(f["text"] for f in frame_evidence)).split())
            unmatched = sorted(observed_tokens - allowed_tokens)[:40]
            checks.append({"name": "ocr_whitelist_review", "status": "review",
                           "unmatched_ocr_tokens": unmatched,
                           "reason": "OCR extras are only review signals, not certified violations"})
    elif words:
        checks.append({"name": "exact_screen_text", "status": "review",
                       "reason": "OCR not enabled; inspect all text states manually"})

    if required_speech and not metadata["has_audio"]:
        checks.append({"name": "expected_speech_audio", "status": "fail",
                       "reason": "Scene requires speech but no audio stream is present"})
    elif required_speech and metadata["has_audio"]:
        if shutil.which("ffmpeg") and Path(path).is_file():
            try:
                volume = detect_silent_audio(path, max_seconds=min(15.0, metadata["duration_seconds"]))
                if volume["silent"]:
                    full_sample = metadata["duration_seconds"] <= 15.0
                    checks.append({
                        "name": "audio_level", "status": "fail" if full_sample else "review",
                        "reason": "Silent/near-silent sampled audio; cannot confirm required speech",
                        "volume": volume,
                    })
            except MediaQAError:
                checks.append({"name": "audio_level", "status": "review",
                               "reason": "Audio level could not be measured reliably"})
        else:
            checks.append({"name": "audio_level", "status": "review",
                           "reason": "Audio level not checked (FFmpeg unavailable or media not mounted)"})

    if asr_model is not None:
        if not metadata["has_audio"]:
            checks.append({"name": "audio", "status": "fail",
                           "reason": "ASR requested but video has no audio stream"})
        else:
            transcript = transcript_local(path, asr_model)
            checks.append({"name": "speech_transcript", "status": "review",
                           "reason": "ASR evidence requires listening/linguistic validation",
                           "expected": required_speech or None})
    elif required_speech:
        checks.append({"name": "speech_transcript", "status": "review",
                       "reason": "ASR not enabled; speech has not been verified"})

    failure = any(check["status"] == "fail" for check in checks)
    review = any(check["status"] in {"review", "observed"} for check in checks)
    decision = "fail" if failure else "review" if review else "pass"
    return {
        "decision": decision,
        "video": str(path),
        "metadata": metadata,
        "checks": checks,
        "frame_evidence": frame_evidence,
        "transcript": transcript,
        "limitations": (
            "OCR is limited to sampled frames and can miss text or misread glyphs. "
            "ASR is probabilistic, not pronunciation verification. "
            "Content checks require human review before release."
        ),
    }
