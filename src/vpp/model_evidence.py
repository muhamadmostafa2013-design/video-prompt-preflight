"""Local model-backed evidence. Scores are signals, never approval."""
from __future__ import annotations

import io
import json
import math
import subprocess
from pathlib import Path

from .song_alignment import _hash, _tokens


def asr_evidence(audio, model_dir):
    """Real faster-whisper inference using only a local model directory."""
    from faster_whisper import WhisperModel

    audio = Path(audio).resolve(strict=True)
    model_dir = Path(model_dir).resolve(strict=True)
    if not model_dir.is_dir():
        raise ValueError("A downloaded local model directory is required.")
    model = WhisperModel(str(model_dir), device="cpu", compute_type="int8", local_files_only=True)
    segments, info = model.transcribe(str(audio), language="de", word_timestamps=True,
                                      beam_size=5, condition_on_previous_text=False)
    words = []
    for segment in segments:
        for word in segment.words or []:
            words.append({"word": word.word.strip(), "start": word.start,
                          "end": word.end, "asr_probability": word.probability})
    return {"audio_sha256": _hash(audio), "words": words, "language": info.language,
            "model": model_dir.name, "backend": "faster-whisper", "family": "whisper",
            "publication_approved": False,
            "limitations": "ASR timestamps are not forced-alignment scores or human labels."}


def rank_scene(labels, scores, minimum_margin=.03):
    if len(labels) < 2 or len(labels) != len(scores) or len(set(labels)) != len(labels):
        raise ValueError("Supply distinct expected and alternative descriptions with corresponding scores.")
    if any(type(s) not in (int, float) or not math.isfinite(s) for s in scores):
        raise ValueError("Non-finite model score.")
    if not 0 < minimum_margin <= 1:
        raise ValueError("Invalid margin.")
    margin = scores[0] - max(scores[1:])
    return {"expected": labels[0], "ranking": sorted(
        [{"label": label, "cosine": round(score, 6)} for label, score in zip(labels, scores)],
        key=lambda row: -row["cosine"]), "margin": round(margin, 6),
        "signal": "supports_expected" if margin >= minimum_margin else
                  "alternative_ranked_higher" if margin <= -minimum_margin else "ambiguous",
        "publication_approved": False}


class LocalCLIP:
    def __init__(self, model_dir):
        import torch
        from transformers import CLIPModel, CLIPProcessor

        path = Path(model_dir).resolve(strict=True)
        if not path.is_dir():
            raise ValueError("A downloaded local CLIP directory is required.")
        self.torch = torch
        self.processor = CLIPProcessor.from_pretrained(str(path), local_files_only=True)
        self.model = CLIPModel.from_pretrained(str(path), local_files_only=True,
                                               use_safetensors=True).eval()
        self.model_name = path.name

    def compare(self, image, labels):
        if (not isinstance(labels, list) or not 2 <= len(labels) <= 12 or
                any(not isinstance(label, str) or not 1 <= len(label) <= 150 for label in labels)):
            raise ValueError("Use 2..12 short descriptions (expected first).")
        if len(set(labels)) != len(labels):
            raise ValueError("Descriptions must be distinct.")
        inputs = self.processor(text=labels, images=image.convert("RGB"), padding=True,
                                truncation=True, max_length=77, return_tensors="pt")
        with self.torch.inference_mode():
            output = self.model(**inputs)
            scores = (output.logits_per_image[0] / self.model.logit_scale.exp()).tolist()
        return rank_scene(labels, scores)


def semantic_scan(video, model_dir, scenes, samples=3):
    """Sample each scene and compare explicit descriptions; no identity inference."""
    from PIL import Image

    path = Path(video).resolve(strict=True)
    if type(samples) is not int or not 1 <= samples <= 10:
        raise ValueError("Samples per scene must be 1..10.")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 60:
        raise ValueError("Provide 1..60 scene definitions.")
    probe = subprocess.run(["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
                            "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                            str(path)], capture_output=True, check=True, timeout=30, text=True)
    duration = float(probe.stdout)
    if not math.isfinite(duration) or not 0 < duration <= 1800:
        raise ValueError("Video duration must be 0..1800 seconds.")
    previous = 0.0
    for scene in scenes:
        start, end = scene["start"], scene["end"]
        if not 0 <= start < end <= duration or start < previous:
            raise ValueError("Invalid or overlapping scene interval.")
        previous = end
        if not isinstance(scene["expected"], str) or not isinstance(scene["alternatives"], list):
            raise TypeError("Expected description and alternatives required.")
    model = LocalCLIP(model_dir)
    rows = []
    for scene in scenes:
        labels = [scene["expected"], *scene["alternatives"]]
        for i in range(samples):
            at = scene["start"] + (scene["end"] - scene["start"]) * (i+.5)/samples
            frame = subprocess.run(["ffmpeg", "-v", "error", "-protocol_whitelist", "file,pipe",
                                    "-ss", f"{at:.3f}", "-i", str(path), "-frames:v", "1",
                                    "-vf", "scale=512:-2", "-f", "image2pipe", "-vcodec", "png", "-"],
                                   capture_output=True, check=True, timeout=45).stdout
            with Image.open(io.BytesIO(frame)) as image:
                rows.append({"scene": scene["id"], "seconds": round(at, 3), **model.compare(image, labels)})
    return {"decision": "review", "model": model.model_name, "video_sha256": _hash(path),
            "samples": rows, "publication_approved": False,
            "limitations": "Relative CLIP similarity only; cannot prove scene meaning, absence, person identity, continuity or correctness between samples."}


def text_wer(reference, prediction):
    """Word error rate against an independently supplied transcript."""
    from .quality_evidence import _edit_distance

    ref, pred = _tokens(reference), _tokens(prediction)
    if not ref:
        raise ValueError("Reference transcript is empty.")
    return {"reference_words": len(ref), "predicted_words": len(pred),
            "word_errors": _edit_distance(ref, pred), "wer": _edit_distance(ref, pred)/len(ref)}


def _asr(args):
    report = asr_evidence(args.audio, args.model_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 3


def _visual(args):
    scenes = json.loads(Path(args.scenes).read_text(encoding="utf-8"))
    report = semantic_scan(args.video, args.model_dir, scenes, args.samples)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 3


def register(sub):
    audio = sub.add_parser("asr-evidence", help="Local faster-whisper transcription (review only)")
    audio.add_argument("audio")
    audio.add_argument("--model-dir", required=True)
    audio.set_defaults(func=_asr)
    visual = sub.add_parser("semantic-scan", help="Local CLIP scene comparison (review only)")
    visual.add_argument("video")
    visual.add_argument("--model-dir", required=True)
    visual.add_argument("--scenes", required=True)
    visual.add_argument("--samples", type=int, default=3)
    visual.set_defaults(func=_visual)
