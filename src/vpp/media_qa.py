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
        "ffprobe", "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(video)
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
    return {
        "duration_seconds": round(duration, 3),
        "width": width,
        "height": height,
        "aspect_ratio": round(width / height, 5),
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
    if ocr and words:
        with tempfile.TemporaryDirectory(prefix="vpp-qa-") as directory:
            frame_evidence = ocr_frames(
                sample_frames(path, metadata["duration_seconds"], frames, directory), ocr_lang
            )
        for word in words:
            matched = [f["seconds"] for f in frame_evidence
                       if _norm(word) and _norm(word) in _norm(f["text"])]
            checks.append({"name": "exact_screen_text", "expected": word,
                           "status": "observed" if matched else "review",
                           "sampled_at_seconds": matched})
    elif words:
        checks.append({"name": "exact_screen_text", "status": "review",
                       "reason": "OCR not enabled; inspect all text states manually"})

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
