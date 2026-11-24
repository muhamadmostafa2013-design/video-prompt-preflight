"""Public German singing smoke benchmark, independent published manual word onsets.

Downloads into runner temp only. Reports aggregate metrics, not lyrics or recordings.
"""
import csv
import json
import os
import subprocess
import urllib.parse
import urllib.request
import wave
from pathlib import Path

from faster_whisper.utils import download_model

from vpp.acoustic_models import ctc_timing_issues
from vpp.extended_quality import chunk_schedule, own_chunk_words, word_fingerprint
from vpp.model_evidence import asr_evidence
from vpp.singing_benchmark import onset_benchmark
from vpp.song_alignment import _hash, _tokens

REV = "f093b7a74e034deac21eb5ea3fc40769b29c35b0"
BASE = "https://raw.githubusercontent.com/f90/jamendolyrics/" + REV + "/"
TRACKS = ["1_Freak_-_Automatisch_Gekommen", "Der_Baum_-_Dienstag_is_Damensauna_(2)",
          "Veränderung_-_doromusis"]


def download(relative, target):
    url = BASE + urllib.parse.quote(relative)
    with urllib.request.urlopen(url, timeout=90) as response:
        data = response.read(20_000_001)
    if not data or len(data) > 20_000_000:
        raise ValueError("Unexpected download length.")
    target.write_bytes(data)


def chunked_evidence(clip, model, root):
    """Experiment only: exact PCM slices, context overlap, onset-based ownership."""
    all_words, rejected = [], 0
    with wave.open(str(clip), "rb") as source:
        rate, count = source.getframerate(), source.getnframes()
        if rate != 16000 or source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError("Expected mono 16 kHz PCM16 benchmark input.")
        schedule = chunk_schedule(count, rate)
        provenance = None
        for i, chunk in enumerate(schedule):
            source.setpos(chunk["decode_start"])
            part = root / f"chunk-{i}.wav"
            with wave.open(str(part), "wb") as handle:
                handle.setparams(source.getparams())
                handle.writeframes(source.readframes(chunk["decode_end"]-chunk["decode_start"]))
            evidence = asr_evidence(part, model)
            if provenance is not None and provenance != evidence["provenance"]:
                raise ValueError("Chunk model provenance changed during inference.")
            provenance = evidence["provenance"]
            owned, invalid = own_chunk_words(evidence["words"], chunk, rate)
            all_words.extend(owned)
            rejected += invalid
    duration = count/rate
    issues = ctc_timing_issues(all_words, duration)
    return {"words": all_words, "source_duration_seconds": duration,
            "timing_valid": not issues and not rejected, "provenance": provenance,
            "chunk_count": len(schedule), "unassignable_words": rejected,
            "timing_issues": issues}


def main():
    root = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "vpp-singing"
    root.mkdir(exist_ok=True)
    scope = os.environ.get("VPP_BENCHMARK_SCOPE", "first_minute")
    if scope not in ("first_minute", "full", "full_chunked"):
        raise ValueError("Unknown benchmark scope.")
    model = download_model("small")
    results = []
    errors = []
    for index, track in enumerate(TRACKS):
        try:
            audio = root / f"{index}.mp3"
            labels = root / f"{index}.csv"
            words = root / f"{index}.txt"
            download(f"mp3/{track}.mp3", audio)
            download(f"annotations/words/{track}.csv", labels)
            download(f"lyrics/{track}.words.txt", words)
            lines = words.read_text(encoding="utf-8-sig").splitlines()
            lines = [line.strip() for line in lines if line.strip()]
            with labels.open(encoding="utf-8-sig") as handle:
                times = list(csv.DictReader(handle))
            if len(lines) != len(times):
                raise ValueError("Reference word/onset counts differ.")
            # Fixed scope selected before inference; no reference-informed cropping.
            reference = [{"word": word, "start": float(row["word_start"])}
                         for word, row in zip(lines, times)
                         if scope != "first_minute" or 0 <= float(row["word_start"]) < 60]
            # Normalize exactly one token per manual onset; no extrapolated ends.
            if any(len(_tokens(row["word"])) != 1 for row in reference):
                raise ValueError("Unexpected reference tokenization.")
            clip = root / f"{index}.wav"
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                    "-of", "default=nw=1:nk=1", str(audio)],
                                   capture_output=True, text=True, check=True, timeout=30)
            duration = float(probe.stdout)
            if scope != "first_minute" and not 0 < duration <= 300:
                raise ValueError("Full-track benchmark supports up to 300 seconds; no silent truncation.")
            cutoff = ["-t", "60"] if scope == "first_minute" else []
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(audio), *cutoff,
                            "-ac", "1", "-ar", "16000", str(clip)], check=True, timeout=90)
            if scope == "full_chunked":
                evidence = chunked_evidence(clip, model, root)
                repeated = chunked_evidence(clip, model, root)
            else:
                evidence = asr_evidence(clip, model)
                repeated = asr_evidence(clip, model)
            fingerprints = [word_fingerprint(x["words"]) for x in (evidence, repeated)]
            report = onset_benchmark(reference, evidence["words"], evidence["source_duration_seconds"])
            results.append({"track": track, "source_sha256": _hash(audio),
                            "clip_sha256": _hash(clip), "manual_onsets_sha256": _hash(labels),
                            "manual_words_sha256": _hash(words),
                            "model_timing_valid": evidence["timing_valid"],
                            "chunk_count": evidence.get("chunk_count", 1),
                            "unassignable_words": evidence.get("unassignable_words", 0),
                            "duration_seconds": evidence["source_duration_seconds"],
                            "provenance": evidence["provenance"], "repeat_fingerprints": fingerprints,
                            "repeat_stable": fingerprints[0] == fingerprints[1] and
                            evidence.get("unassignable_words", 0) == repeated.get("unassignable_words", 0),
                            **report})
        except Exception as exc:  # noqa: BLE001 -- each benchmark case is recorded
            errors.append({"track": track, "error_type": type(exc).__name__, "message": str(exc)[:300]})
    total = sum(r["reference_words"] for r in results)
    result = {"dataset": "JamendoLyrics MultiLang, archived GitHub revision " + REV,
              "model": Path(model).name, "sample": scope, "repeats_per_track": 2,
              "all_repeats_stable": len(results) == len(TRACKS) and all(r["repeat_stable"] for r in results),
              "rows": results, "errors": errors,
              "reference_words": total, "publication_approved": False}
    if total:
        result.update(wer=sum(r["word_errors"] for r in results)/total,
                      all_word_coverage_100ms=sum(r["within_100ms"] for r in results)/total,
                      all_word_coverage_200ms=sum(r["within_200ms"] for r in results)/total)
    Path("singing-benchmark-report.json").write_text(json.dumps(result, ensure_ascii=False,
        indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return (bool(errors) or not result["all_repeats_stable"] or
            any(r["unassignable_words"] for r in results))


if __name__ == "__main__":
    raise SystemExit(main())
