"""Evidence-only quality gates for reproducibility, pronunciation and bilingual media."""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from difflib import SequenceMatcher
from importlib.metadata import version
from pathlib import Path

from .song_alignment import _hash, _number

ASR_SETTINGS = {"language": "de", "beam_size": 5, "temperature": 0.0,
                "condition_on_previous_text": False, "vad_filter": False,
                "word_timestamps": True}


def whisper_options():
    return dict(ASR_SETTINGS)


def model_provenance(directory):
    """Record model weights and inference runtime; never infer equivalence by name."""
    root = Path(directory)
    files = {}
    for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.json"):
        path = root / name
        if path.is_file():
            files[name] = _hash(path)
    if "model.bin" not in files or "config.json" not in files:
        raise ValueError("Missing required Whisper model weights or configuration.")
    return {"files_sha256": files, "settings": whisper_options(),
            "cpu_threads": 2, "num_workers": 1, "compute_type": "int8",
            "packages": {name: version(name) for name in ("faster-whisper", "ctranslate2")}}


def word_fingerprint(words):
    data = json.dumps(words, ensure_ascii=False, sort_keys=True, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def scene_schedule(scenes, duration, minimum=3, max_step=5.0):
    """Sample every declared interval with bounded spacing, including long scenes."""
    if not _number(duration) or not 0 < duration <= 1800:
        raise ValueError("Invalid duration.")
    if type(minimum) is not int or not 1 <= minimum <= 10:
        raise ValueError("Minimum samples must be 1..10.")
    if not _number(max_step) or not 1 <= max_step <= 10:
        raise ValueError("Maximum sample step must be 1..10 seconds.")
    if not isinstance(scenes, list) or not 1 <= len(scenes) <= 60:
        raise ValueError("Provide 1..60 scenes.")
    previous = 0.0
    ids = set()
    schedule = []
    for scene in scenes:
        sid, start, end = scene["id"], scene["start"], scene["end"]
        if not isinstance(sid, str) or not sid.strip() or sid in ids:
            raise ValueError("Invalid or repeated scene ID.")
        if not (_number(start) and _number(end) and previous <= start < end <= duration):
            raise ValueError("Invalid or overlapping scene interval.")
        if start - previous > .05:
            raise ValueError("Uncovered video interval in scene manifest.")
        ids.add(sid)
        previous = end
        count = max(minimum, math.ceil((end-start)/max_step))
        schedule.append([start+(end-start)*(i+.5)/count for i in range(count)])
    if duration - previous > .05:
        raise ValueError("Uncovered end of video.")
    if sum(map(len, schedule)) > 600:
        raise ValueError("Semantic sample budget exceeded; split the video for review.")
    return schedule


def _written(text):
    if not isinstance(text, str):
        raise TypeError("Expected text.")
    return " ".join(unicodedata.normalize("NFC", text).split())


def bilingual_review(captions, approved):
    """Compare each cue to teacher-supplied German and Arabic text, not a translation model."""
    if not isinstance(approved, list) or not approved or len(approved) > 2000:
        raise ValueError("Provide 1..2000 teacher-approved bilingual cue records.")
    for i, ref in enumerate(approved, 1):
        if (not isinstance(ref, dict) or ref.get("index") != i or
                not _written(ref.get("de", "")) or
                not re.search(r"[\u0621-\u064a]", _written(ref.get("ar", "")))):
            raise ValueError("Reference needs sequential indices, German and Arabic.")
    issues = []
    if len(captions) != len(approved):
        issues.append({"code": "bilingual_cue_count_differs"})
    for i, (cue, ref) in enumerate(zip(captions, approved), 1):
        if cue["index"] != i:
            issues.append({"cue": i, "code": "cue_index_differs"})
        if _written(cue["lines"][0]) != _written(ref["de"]):
            issues.append({"cue": i, "code": "german_written_text_differs"})
        actual_ar = _written(" ".join(cue["lines"][1:]))
        if not re.search(r"[\u0621-\u064a]", actual_ar):
            issues.append({"cue": i, "code": "arabic_missing"})
        elif actual_ar != _written(ref["ar"]):
            issues.append({"cue": i, "code": "arabic_reference_differs"})
    return {"decision": "blocked" if issues else "reference_consistent",
            "issues": issues, "publication_approved": False,
            "limitations": "Teacher-supplied text comparison; not automatic translation certification."}


def pronunciation_review(reference, evidence):
    """Review a source-bound short German word/phrase against approved phone variants."""
    from .consensus import phoneme_review

    if reference.get("audio_sha256") != evidence.get("audio_sha256") or not re.fullmatch(
            "[a-f0-9]{64}", str(reference.get("audio_sha256", ""))):
        raise ValueError("Pronunciation evidence must identify the same audio segment.")
    if reference.get("annotation_source") != "teacher":
        raise ValueError("Provide teacher-approved phone references.")
    variants = reference.get("accepted_phones")
    if not isinstance(variants, list) or not 1 <= len(variants) <= 10:
        raise ValueError("Provide 1..10 accepted phone variants.")
    observed = evidence["phones"]
    reports = [phoneme_review(variant, observed) for variant in variants]
    best = min(range(len(reports)), key=lambda i: (reports[i]["phone_error_rate"], i))
    wanted = variants[best]
    edits = [{"kind": tag, "reference": wanted[a:b], "observed": observed[c:d],
              "reference_index": a+1}
             for tag, a, b, c, d in SequenceMatcher(None, wanted, observed, autojunk=False).get_opcodes()
             if tag != "equal"]
    return {"decision": "needs_review" if edits else "phone_sequence_consistent",
            "closest_variant": best+1, "phone_error_rate": reports[best]["phone_error_rate"],
            "suspected_edits": edits, "publication_approved": False,
            "human_listening_verified": False,
            "limitations": "Model phone candidates, not certified pronunciation; teacher listening required."}
