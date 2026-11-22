"""Opt-in Gemini Omni/Lyria production for VPP. Dry-run by default."""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from .german_music_qa import compile_song_prompt, review_song
from .triple_review import triple_review

VIDEO_MODEL = "gemini-omni-1.2-flash"
MUSIC_MODEL = "lyria-3.5"


class ProductionError(ValueError):
    """Input or production failed its safety gate."""


def _yaml(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > 128000:
        raise ProductionError("Missing production spec or file too large.")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProductionError("The production YAML must be a mapping.")
    return data


def _root_file(root: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not 1 <= len(relative) <= 180:
        raise ProductionError("Expected a relative file path.")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ProductionError("File reference must remain inside the repository.")
    return target


def validate_job(raw: dict[str, Any], root: Path) -> dict[str, Any]:
    kind = raw.get("type")
    if kind not in ("video", "song"):
        raise ProductionError("type must be video or song.")
    title = raw.get("title", "Deutsch lernen")
    if not isinstance(title, str) or not 1 <= len(title) <= 120:
        raise ProductionError("Invalid title.")
    aspect = raw.get("aspect_ratio", "9:16")
    if aspect not in ("9:16", "16:9"):
        raise ProductionError("Only 9:16 or 16:9 supported.")
    job: dict[str, Any] = {"type": kind, "title": title, "aspect_ratio": aspect}
    if kind == "song":
        job["song_spec"] = _yaml(_root_file(root, raw.get("song_spec")))
    else:
        scenes = raw.get("scenes")
        if not isinstance(scenes, list) or not 1 <= len(scenes) <= 6:
            raise ProductionError("A video needs 1–6 scenes.")
        job["scenes"] = []
        for index, scene in enumerate(scenes):
            if not isinstance(scene, dict):
                raise ProductionError("Each scene must be an object.")
            duration = scene.get("duration_seconds")
            prompt = scene.get("prompt")
            if type(duration) is not int or not 3 <= duration <= 15:
                raise ProductionError("Omni scene duration must be an integer 3..15 seconds.")
            if not isinstance(prompt, str) or not 20 <= len(prompt) <= 6500:
                raise ProductionError("Scene prompt must be 20..6500 characters.")
            job["scenes"].append({"id": index+1, "duration_seconds": duration, "prompt": prompt})
        if sum(x["duration_seconds"] for x in job["scenes"]) > 90:
            raise ProductionError("90 seconds per run maximum.")
    return job


def preflight(job: dict[str, Any]) -> dict[str, Any]:
    if job["type"] == "song":
        qa = review_song(job["song_spec"])
        if not qa["passed"]:
            raise ProductionError("German Educational Music QA blocked song: " +
                                  ", ".join(x["rule_id"] for x in qa["findings"]
                                            if x["severity"] == "error"))
        return {"qa": qa, "prompts": [compile_song_prompt(job["song_spec"])]}
    prompts = []
    reviews = []
    for scene in job["scenes"]:
        dur = scene["duration_seconds"]
        prompt = (
            f"Create exactly {dur}-second video. Format {job['aspect_ratio']}. "
            "One coherent German educational scene. Keep the German dialogue exactly "
            "as supplied, with natural Standard German pronunciation. No automatic "
            "subtitles or on-screen written text: captions are a postproduction task. "
            "No extra spoken words. Scene: " + scene["prompt"]
        )
        check = triple_review(prompt, provider="gemini_omni")
        if not check["passed"]:
            raise ProductionError(f"VPP Triple Verify blocked scene {scene['id']}.")
        # Never silently replace exact dialogue with a heuristic prompt candidate.
        prompts.append(prompt)
        reviews.append({"scene": scene["id"], "passed": True,
                        "confidence": check.get("confidence_band"),
                        "score": check.get("heuristic_score")})
    return {"qa": reviews, "prompts": prompts}


def estimated_usd(job: dict[str, Any]) -> float:
    return (0.10 if job["type"] == "song" else
            round(0.08 * sum(s["duration_seconds"] for s in job["scenes"]), 2))


def paid_gate(estimate: float, limit: float, env: dict[str, str]) -> None:
    # This is a conservative request estimate, not a guaranteed billing cap.
    if not math.isfinite(limit) or not 0 < limit <= 25 or estimate > limit:
        raise ProductionError("Estimated provider spend exceeds allowed limit.")
    if env.get("VPP_ALLOW_PAID_GENERATION") != "YES":
        raise ProductionError("Paid generation is locked. Explicit approval required.")
    if not env.get("GEMINI_API_KEY"):
        raise ProductionError("GEMINI_API_KEY GitHub secret is missing.")


def _decode(data: Any) -> bytes:
    if not isinstance(data, (str, bytes)) or len(data) > 400_000_000:
        raise ProductionError("No inline media or oversized response.")
    try:
        binary = base64.b64decode(data, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ProductionError("Invalid media encoding.") from exc
    if not 1 <= len(binary) <= 200_000_000:
        raise ProductionError("Invalid media size.")
    return binary


def generate_paid(job: dict[str, Any], prompts: list[str], out: Path, key: str) -> list[Path]:
    # The package is optional and is loaded only for paid generation.
    try:
        from google import genai
    except ImportError as exc:
        raise ProductionError("Install google-genai to use paid generation.") from exc
    client = genai.Client(api_key=key)
    paths = []
    for index, prompt in enumerate(prompts):
        if job["type"] == "video":
            try:
                response = client.interactions.create(
                    model=VIDEO_MODEL, input=prompt,
                    response_format={"type": "video",
                                     "duration": str(job["scenes"][index]["duration_seconds"]) + "s",
                                     "aspect_ratio": job["aspect_ratio"], "resolution": "720p"})
            except Exception:  # noqa: BLE001 -- sanitize unknown provider SDK failures
                raise ProductionError("Gemini video request failed. Check plan, model access and usage logs privately.") from None
            video = getattr(response, "output_video", None)
            blob = _decode(getattr(video, "data", None))
            path = out / f"clip_{index+1:02d}.mp4"
        else:
            try:
                response = client.interactions.create(model=MUSIC_MODEL, input=prompt)
            except Exception:  # noqa: BLE001 -- sanitize unknown provider SDK failures
                raise ProductionError("Gemini music request failed. Check plan, model access and usage logs privately.") from None
            audio = getattr(response, "output_audio", None)
            blob = _decode(getattr(audio, "data", None))
            path = out / "song.mp3"
            lyrics = getattr(response, "output_text", None)
            if lyrics:
                (out / "unverified_generated_lyrics.txt").write_text(
                    str(lyrics)[:20000], encoding="utf-8")
        path.write_bytes(blob)
        paths.append(path)
    return paths


def _command(args: list[str]) -> None:
    completed = subprocess.run(args, capture_output=True, text=True,
                               timeout=180, check=False)
    if completed.returncode:
        raise ProductionError("FFmpeg processing failed; inspect local generated files.")


def _probe(path: Path) -> dict[str, Any]:
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,width,height", "-of", "json",
                        str(path)], capture_output=True, text=True, timeout=30, check=False)
    if p.returncode:
        raise ProductionError("FFprobe could not read an output file.")
    return json.loads(p.stdout)


def render(job: dict[str, Any], assets: list[Path], out: Path) -> Path:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ProductionError("FFmpeg + FFprobe required.")
    width, height = (720, 1280) if job["aspect_ratio"] == "9:16" else (1280, 720)
    result = out / "final.mp4"
    if job["type"] == "song":
        _probe(assets[0])
        _command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                  "-f", "lavfi", "-i", f"color=c=0x172033:s={width}x{height}:r=30",
                  "-i", str(assets[0]), "-map", "0:v:0", "-map", "1:a:0",
                  "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                  "-c:a", "aac", "-b:a", "192k", "-shortest", str(result)])
    else:
        normalized = []
        for idx, asset in enumerate(assets):
            info = _probe(asset)
            streams = info.get("streams", [])
            if not any(s.get("codec_type") == "video" for s in streams):
                raise ProductionError("Clip missing video stream.")
            with_audio = any(s.get("codec_type") == "audio" for s in streams)
            normalized_path = out / f"norm_{idx:02d}.mp4"
            args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(asset)]
            if not with_audio:
                args += ["-f", "lavfi", "-i",
                         "anullsrc=channel_layout=stereo:sample_rate=48000"]
            args += ["-map", "0:v:0", "-map", "0:a:0" if with_audio else "1:a:0",
                     "-vf", (f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"),
                     "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                     "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
                     "-shortest", str(normalized_path)]
            _command(args)
            normalized.append(normalized_path)
        # Only internally generated filenames reach the concat list.
        playlist = out / "concat.txt"
        playlist.write_text("".join("file '" + p.as_posix() + "'\n" for p in normalized),
                            encoding="utf-8")
        _command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                  "-f", "concat", "-safe", "0", "-i", str(playlist),
                  "-c", "copy", "-movflags", "+faststart", str(result)])
    if not any(x.get("codec_type") == "video"
               for x in _probe(result).get("streams", [])):
        raise ProductionError("Final output lacks a video stream.")
    return result


def generate_demo(job: dict[str, Any], out: Path) -> list[Path]:
    """Offline, synthetic sound/video to test automation without Gemini charges."""
    if job["type"] == "song":
        path = out / "demo_sine.mp3"
        _command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                  "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
                  "-c:a", "libmp3lame", str(path)])
        return [path]
    assets = []
    for index, scene in enumerate(job["scenes"]):
        path = out / f"demo_clip_{index:02d}.mp4"
        dur = scene["duration_seconds"]
        _command(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                  "-f", "lavfi", "-i", f"testsrc2=size=360x640:rate=15:duration={dur}",
                  "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}",
                  "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                  "-c:a", "aac", "-shortest", str(path)])
        assets.append(path)
    return assets


def produce(
    spec: Path, root: Path, out: Path, mode: str = "dry-run",
    max_estimated_usd: float = 2.0, environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    if mode not in ("dry-run", "demo", "paid"):
        raise ProductionError("mode must be dry-run, demo or paid.")
    job = validate_job(_yaml(spec), root)
    checks = preflight(job)
    estimate = estimated_usd(job)
    env = os.environ if environ is None else environ
    if mode == "paid":
        paid_gate(estimate, max_estimated_usd, env)
    out.mkdir(parents=True, exist_ok=True)
    report = {
        "mode": mode, "type": job["type"], "model": VIDEO_MODEL if job["type"] == "video" else MUSIC_MODEL,
        "preflight": checks["qa"], "estimated_usd": estimate,
        "cost_note": "Estimate, NOT an actual API billing cap. External charges can differ.",
        "human_review_required": True,
    }
    (out / "preflight.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "prompts.txt").write_text(
        "\n\n--- NEXT SCENE ---\n\n".join(checks["prompts"]), encoding="utf-8")
    if mode == "dry-run":
        return report
    assets = (generate_demo(job, out) if mode == "demo" else
              generate_paid(job, checks["prompts"], out, env["GEMINI_API_KEY"]))
    rendered = render(job, assets, out)
    report["output"] = rendered.name
    report["technical_probe"] = _probe(rendered)
    report["quality_note"] = ("MP4 checked structurally; human listening, lip sync, "
                              "German language and exact script still require inspection.")
    (out / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    p = argparse.ArgumentParser(description="VPP Gemini production (safe dry-run default)")
    p.add_argument("--spec", type=Path, required=True)
    p.add_argument("--root", type=Path, default=Path.cwd())
    p.add_argument("--out", type=Path, default=Path("production_output"))
    p.add_argument("--mode", choices=("dry-run", "demo", "paid"), default="dry-run")
    p.add_argument("--max-estimated-usd", type=float, default=2.0)
    args = p.parse_args()
    try:
        report = produce(args.spec, args.root.resolve(), args.out.resolve(),
                         mode=args.mode, max_estimated_usd=args.max_estimated_usd)
        print(json.dumps({"mode": args.mode, "estimated_usd": report["estimated_usd"],
                          "output": report.get("output"), "human_review_required": True}))
    except (ProductionError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        # Avoid printing API exception details: some SDK errors include request text.
        print("Production stopped: " + str(exc), file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
