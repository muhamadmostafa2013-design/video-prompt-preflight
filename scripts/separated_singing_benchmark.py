"""Public paired comparison: vocal separation and acoustic word alignment."""
import json
import os
import subprocess
import sys
from pathlib import Path

import whisperx
from faster_whisper import WhisperModel
from faster_whisper.utils import download_model
from public_singing_benchmark import TRACKS, download

from vpp.acoustic_models import native_boundary
from vpp.model_evidence import asr_evidence
from vpp.singing_benchmark import onset_benchmark


def main():
    import csv

    root = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "vpp-separated"
    root.mkdir(exist_ok=True)
    model_dir = download_model("small")
    asr = WhisperModel(model_dir, device="cpu", compute_type="int8", local_files_only=True)
    align_model, metadata = whisperx.load_align_model(language_code="de", device="cpu")
    rows, errors = [], []
    for index, track in enumerate(TRACKS):
        try:
            mp3, labels, words = [root / f"{index}.{ext}" for ext in ("mp3", "csv", "txt")]
            download(f"mp3/{track}.mp3", mp3)
            download(f"annotations/words/{track}.csv", labels)
            download(f"lyrics/{track}.words.txt", words)
            lines = [s.strip() for s in words.read_text(encoding="utf-8-sig").splitlines() if s.strip()]
            with labels.open(encoding="utf-8-sig") as handle:
                times = list(csv.DictReader(handle))
            if len(lines) != len(times):
                raise ValueError("Manual reference count mismatch.")
            ref = [{"word": word, "start": float(row["word_start"])}
                   for word, row in zip(lines, times) if 0 <= float(row["word_start"]) < 60]
            mix = root / f"mix-{index}.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-i", str(mp3), "-t", "60",
                            "-ac", "2", "-ar", "44100", str(mix)], check=True, timeout=60)
            baseline = asr_evidence(mix, model_dir)
            row = {"track": track, "raw_whisper": onset_benchmark(ref, baseline["words"], 60)}
            rows.append(row)
            subprocess.run([sys.executable, "-m", "demucs", "-n", "htdemucs", "--two-stems",
                            "vocals", "-d", "cpu", "--shifts", "0", "-o", str(root / "stems"), str(mix)],
                           check=True, timeout=420)
            vocal = root / "stems" / "htdemucs" / mix.stem / "vocals.wav"
            separated = asr_evidence(vocal, model_dir)
            if abs(separated["source_duration_seconds"]-baseline["source_duration_seconds"]) > .05:
                raise ValueError("Vocal stem timeline differs.")
            row["demucs_whisper"] = onset_benchmark(ref, separated["words"], 60)
            # Alignment uses only recognized segment text and bounds, never manual onsets.
            audio = whisperx.load_audio(str(vocal))
            segments, _ = asr.transcribe(audio, language="de", beam_size=5,
                                         condition_on_previous_text=False)
            segments = [{"start": float(s.start), "end": float(s.end), "text": s.text}
                        for s in segments]
            aligned = whisperx.align(segments, align_model, metadata, audio, "cpu",
                                     interpolate_method="ignore", return_char_alignments=False)
            predicted = [{"word": w["word"], "start": native_boundary(w.get("start"))}
                         for w in aligned.get("word_segments", [])]
            row["demucs_whisperx"] = onset_benchmark(ref, predicted, 60)
        except Exception as exc:  # noqa: BLE001 -- benchmark records partial results
            errors.append({"track": track, "error_type": type(exc).__name__, "message": str(exc)[:400]})
    report = {"dataset": "JamendoLyrics, same three fixed first-minute excerpts", "rows": rows,
              "errors": errors, "publication_approved": False}
    for name in ("raw_whisper", "demucs_whisper", "demucs_whisperx"):
        items = [r[name] for r in rows if name in r]
        n = sum(r["reference_words"] for r in items)
        if n:
            report[name] = {"tracks": len(items), "reference_words": n,
                            "wer": sum(r["word_errors"] for r in items)/n,
                            "coverage_100ms": sum(r["within_100ms"] for r in items)/n,
                            "coverage_200ms": sum(r["within_200ms"] for r in items)/n}
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    Path("separated-singing-report.json").write_text(json.dumps(report, ensure_ascii=False,
        indent=2, allow_nan=False), encoding="utf-8")
    return bool(errors) or len(rows) != len(TRACKS)


if __name__ == "__main__":
    raise SystemExit(main())
