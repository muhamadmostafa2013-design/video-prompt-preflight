"""Optional local Wav2Vec2 word and phoneme inference (review evidence only)."""
from __future__ import annotations

import json
import subprocess
from itertools import groupby
from pathlib import Path

from .song_alignment import _hash, _number, _tokens


def _audio(path, seconds):
    import numpy as np

    # Decode bounded local media; no network protocols, no silent truncation.
    result = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-protocol_whitelist",
                             "file,pipe", "-i", str(path), "-map", "0:a:0",
                             "-t", str(seconds+1), "-ac", "1", "-ar", "16000",
                             "-f", "f32le", "-"], capture_output=True, check=True, timeout=90)
    data = np.frombuffer(result.stdout, dtype="<f4").copy()
    if not len(data) or len(data) > seconds*16000 or not np.isfinite(data).all():
        raise ValueError(f"Audio must be nonempty, finite and <= {seconds} seconds.")
    return data


def _local_model(model_dir):
    from transformers import AutoFeatureExtractor, AutoModelForCTC

    path = Path(model_dir).resolve(strict=True)
    if not path.is_dir() or not (path / "model.safetensors").is_file():
        raise ValueError("Provide a local model directory with safetensors weights.")
    config = json.loads((path / "config.json").read_text(encoding="utf-8"))
    if config.get("model_type") != "wav2vec2":
        raise ValueError("Expected Wav2Vec2 CTC model.")
    extractor = AutoFeatureExtractor.from_pretrained(str(path), local_files_only=True,
                                                       trust_remote_code=False)
    model = AutoModelForCTC.from_pretrained(str(path), local_files_only=True,
                                             use_safetensors=True, trust_remote_code=False).eval()
    return path, extractor, model


def ctc_timing_issues(words, duration):
    """Record model faults without shifting, rounding or dropping invalid words."""
    issues = []
    if not words:
        return [{"code": "empty_word_track"}]
    previous_end = 0.0
    for i, row in enumerate(words):
        start, end = row.get("start"), row.get("end")
        if not isinstance(row.get("word"), str) or len(_tokens(row["word"])) != 1:
            issues.append({"index": i+1, "code": "not_one_lexical_token"})
        if not (_number(start) and _number(end)):
            issues.append({"index": i+1, "code": "missing_or_nonfinite_boundary"})
        elif not 0 <= start < end <= duration:
            issues.append({"index": i+1, "code": "invalid_or_out_of_range_interval"})
        else:
            if start < previous_end:
                issues.append({"index": i+1, "code": "overlapping_boundary"})
            previous_end = max(previous_end, end)
    return issues


class LocalGermanCTC:
    def __init__(self, model_dir):
        from transformers import AutoTokenizer, pipeline

        self.path, extractor, model = _local_model(model_dir)
        tokenizer = AutoTokenizer.from_pretrained(str(self.path), local_files_only=True,
                                                    trust_remote_code=False)
        self.pipe = pipeline("automatic-speech-recognition", model=model, tokenizer=tokenizer,
                             feature_extractor=extractor, device=-1)

    def transcribe(self, audio):
        path = Path(audio).resolve(strict=True)
        samples = _audio(path, 300)
        result = self.pipe({"raw": samples, "sampling_rate": 16000},
                           chunk_length_s=15, stride_length_s=2, return_timestamps="word")
        words = []
        for item in result.get("chunks", []):
            start, end = item["timestamp"]
            words.append({"word": item["text"].strip(), "start": start, "end": end})
        duration = len(samples)/16000
        issues = ctc_timing_issues(words, duration)
        return {"backend": "wav2vec2-ctc", "family": "wav2vec2",
                "model": self.path.name, "audio_sha256": _hash(path),
                "text": result["text"], "words": words,
                "source_duration_seconds": duration, "timing_valid": not issues,
                "timing_issues": issues,
                "publication_approved": False,
                "limitations": "Independent CTC model estimates, not human timing. Word errors may differ from Whisper."}


def collapse_phones(ids, vocab, blank):
    """CTC collapse consecutive IDs, then drop blank; retain all other labels."""
    reverse = {int(index): token for token, index in vocab.items()}
    if len(reverse) != len(vocab) or blank not in reverse:
        raise ValueError("Invalid phoneme vocabulary or blank token.")
    phones = []
    for index, _ in groupby(ids):
        if index == blank:
            continue
        if index not in reverse:
            raise ValueError("Unknown phoneme ID.")
        token = reverse[index]
        if token.startswith("<") and token.endswith(">"):
            # Non-blank special tokens are uncertain, never silently erased.
            phones.append("[uncertain:" + token + "]")
        else:
            phones.append(token)
    return phones


def phoneme_evidence(audio, model_dir):
    """Local acoustic phone recognizer; short segment only, not grading."""
    import torch

    path = Path(audio).resolve(strict=True)
    model_path, extractor, model = _local_model(model_dir)
    tokenizer = json.loads((model_path / "tokenizer_config.json").read_text(encoding="utf-8"))
    if tokenizer.get("tokenizer_class") != "Wav2Vec2PhonemeCTCTokenizer":
        raise ValueError("Model is not explicitly configured for phoneme recognition.")
    vocab = json.loads((model_path / "vocab.json").read_text(encoding="utf-8"))
    samples = _audio(path, 30)
    inputs = extractor(samples, sampling_rate=16000, return_tensors="pt")
    with torch.inference_mode():
        ids = model(**inputs).logits.argmax(-1)[0].tolist()
    phones = collapse_phones(ids, vocab, model.config.pad_token_id)
    return {"backend": "wav2vec2-phoneme", "family": "wav2vec2",
            "model": model_path.name, "audio_sha256": _hash(path),
            "phones": phones, "publication_approved": False,
            "limitations": "Acoustic phone candidates only; no confidence calibration, pronunciation or accent verdict. Use independent phone annotations."}


def _ctc(args):
    result = LocalGermanCTC(args.model_dir).transcribe(args.audio)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 3


def _phones(args):
    result = phoneme_evidence(args.audio, args.model_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 3


def register(sub):
    for name, handler in (("ctc-evidence", _ctc), ("phoneme-evidence", _phones)):
        parser = sub.add_parser(name, help="Local model-backed evidence (review only)")
        parser.add_argument("audio")
        parser.add_argument("--model-dir", required=True)
        parser.set_defaults(func=handler)
