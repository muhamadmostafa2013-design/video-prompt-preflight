"""Public German singing smoke benchmark, independent published manual word onsets.

Downloads into runner temp only. Reports aggregate metrics, not lyrics or recordings.
"""
import csv
import json
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

from faster_whisper.utils import download_model

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


def main():
    root = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "vpp-singing"
    root.mkdir(exist_ok=True)
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
            # Evaluate the complete first 60 seconds for all three tracks. Use
            # a fixed cutoff chosen before inference, not a good-performing excerpt.
            reference = [{"word": word, "start": float(row["word_start"])}
                         for word, row in zip(lines, times)
                         if 0 <= float(row["word_start"]) < 60]
            # Normalize exactly one token per manual onset; no extrapolated ends.
            if any(len(_tokens(row["word"])) != 1 for row in reference):
                raise ValueError("Unexpected reference tokenization.")
            clip = root / f"{index}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-t", "60",
                            "-ac", "1", "-ar", "16000", str(clip)],
                           check=True, timeout=60)
            evidence = asr_evidence(clip, model)
            report = onset_benchmark(reference, evidence["words"], evidence["source_duration_seconds"])
            results.append({"track": track, "source_sha256": _hash(audio),
                            "clip_sha256": _hash(clip), "manual_onsets_sha256": _hash(labels),
                            "manual_words_sha256": _hash(words),
                            "model_timing_valid": evidence["timing_valid"], **report})
        except Exception as exc:  # noqa: BLE001 -- each benchmark case is recorded
            errors.append({"track": track, "error_type": type(exc).__name__, "message": str(exc)[:300]})
    total = sum(r["reference_words"] for r in results)
    result = {"dataset": "JamendoLyrics MultiLang, archived GitHub revision " + REV,
              "model": Path(model).name, "sample": "three preselected German songs, first 60s each",
              "rows": results, "errors": errors,
              "reference_words": total, "publication_approved": False}
    if total:
        result.update(wer=sum(r["word_errors"] for r in results)/total,
                      all_word_coverage_100ms=sum(r["within_100ms"] for r in results)/total,
                      all_word_coverage_200ms=sum(r["within_200ms"] for r in results)/total)
    Path("singing-benchmark-report.json").write_text(json.dumps(result, ensure_ascii=False,
        indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return bool(errors) or len(results) != len(TRACKS)


if __name__ == "__main__":
    raise SystemExit(main())
