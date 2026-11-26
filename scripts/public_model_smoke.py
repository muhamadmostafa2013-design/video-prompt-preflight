"""Network opt-in experiment; only public dataset inputs, no user media."""
import json
import os
import urllib.request
from pathlib import Path

from faster_whisper.utils import download_model
from huggingface_hub import hf_hub_download, snapshot_download
from PIL import Image
from pyarrow.parquet import ParquetFile

from vpp.acoustic_models import LocalGermanCTC, phoneme_evidence
from vpp.consensus import compare_tracks
from vpp.model_evidence import LocalCLIP, asr_evidence, text_wer
from vpp.song_alignment import _hash


def download(url, destination):
    with urllib.request.urlopen(url, timeout=90) as response:
        destination.write_bytes(response.read(20_000_000))


def main():
    work = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "vpp-model-smoke"
    work.mkdir(exist_ok=True)
    report = {"basis": "public human-read speech and public reference image; no user audio",
              "human_word_boundary_reference": False, "publication_approved": False}
    errors = []
    try:
        model = download_model("small")
        parquet = hf_hub_download("google/fleurs", "de_de/test-00000-of-00001.parquet",
                                  repo_type="dataset", revision="0b98f0538af50329c9b336824d7d697c594b9c26")
        table = next(ParquetFile(parquet).iter_batches(batch_size=3, columns=["audio", "transcription"]))
        rows = []
        for i, row in enumerate(table.to_pylist()):
            audio = work / f"sample-{i}.wav"
            audio.write_bytes(row["audio"]["bytes"])
            evidence = asr_evidence(audio, model)
            prediction = " ".join(w["word"] for w in evidence["words"])
            rows.append({"row_idx": i, "reference": row["transcription"],
                         "prediction": prediction, **text_wer(row["transcription"], prediction),
                         "word_timestamps": evidence["words"], "timing_valid": evidence["timing_valid"],
                         "timing_issues": evidence["timing_issues"],
                         "source_duration_seconds": evidence["source_duration_seconds"]})
        report["audio"] = {"dataset": "google/fleurs de_de test", "rows": rows,
                           "wer": sum(r["word_errors"] for r in rows)/sum(r["reference_words"] for r in rows)}
    except Exception as exc:  # noqa: BLE001 -- report independent stage failures
        errors.append({"stage": "asr", "type": type(exc).__name__, "message": str(exc)[:600]})
    for key, repo, revision in [
            ("ctc", "aware-ai/wav2vec2-base-german", "main"),
            ("ctc_large", "jonatasgrosman/wav2vec2-large-xlsr-53-german", "refs/pr/2")]:
        try:
            model = snapshot_download(repo, revision=revision, allow_patterns=[
                "config.json", "model.safetensors", "preprocessor_config.json",
                "tokenizer_config.json", "special_tokens_map.json", "added_tokens.json", "vocab.json"])
            ctc = LocalGermanCTC(model)
            results = []
            for row in report["audio"]["rows"]:
                audio = work / f"sample-{row['row_idx']}.wav"
                evidence = ctc.transcribe(audio)
                primary = {"backend": "faster-whisper", "family": "whisper", "model": "small",
                           "audio_sha256": _hash(audio), "words": row["word_timestamps"],
                           "timing_valid": row["timing_valid"],
                           "source_duration_seconds": row["source_duration_seconds"]}
                agreement = compare_tracks([primary, evidence], _hash(audio),
                                           duration=row["source_duration_seconds"])
                results.append({"row_idx": row["row_idx"], "prediction": evidence["text"],
                                **text_wer(row["reference"], evidence["text"]),
                                "agreement": agreement, "timing_valid": evidence["timing_valid"],
                                "timing_issues": evidence["timing_issues"], "word_timestamps": evidence["words"]})
            report[key] = {"model": repo, "rows": results,
                           "wer": sum(r["word_errors"] for r in results)/sum(r["reference_words"] for r in results)}
            del ctc
        except Exception as exc:  # noqa: BLE001 -- report independent stage failures
            errors.append({"stage": key, "type": type(exc).__name__, "message": str(exc)[:600]})
    try:
        model = snapshot_download("facebook/wav2vec2-lv-60-espeak-cv-ft", revision="refs/pr/4",
                                  allow_patterns=["config.json", "model.safetensors",
                                      "preprocessor_config.json", "tokenizer_config.json",
                                      "special_tokens_map.json", "vocab.json"])
        if _hash(Path(model) / "model.safetensors") != (
                "c934ee723992317fe6077d82359b74e1fbfa048a4269b0f83f006f9a0f65b528"):
            raise ValueError("Phoneme weight hash mismatch.")
        report["phonemes"] = phoneme_evidence(work / "sample-0.wav", model)
        if not report["phonemes"]["phones"]:
            raise ValueError("No phones recognized.")
    except Exception as exc:  # noqa: BLE001 -- report independent stage failures
        errors.append({"stage": "phonemes", "type": type(exc).__name__, "message": str(exc)[:600]})
    try:
        model = snapshot_download("openai/clip-vit-base-patch32",
                                  revision="bfc19449bc6f18c54292b85378cbccc3ad91a24e", allow_patterns=[
            "config.json", "model.safetensors", "preprocessor_config.json",
            "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "vocab.json", "merges.txt"])
        image = work / "parrots.png"
        download("https://huggingface.co/datasets/huggingface/documentation-images/resolve/main/hub/parrots.png", image)
        with Image.open(image) as im:
            report["visual"] = LocalCLIP(model).compare(im, ["a photograph of parrots",
                                                             "a photograph of a car",
                                                             "an empty office"])
    except Exception as exc:  # noqa: BLE001 -- report independent stage failures
        errors.append({"stage": "clip", "type": type(exc).__name__, "message": str(exc)[:600]})
    report["errors"] = errors
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    Path("model-smoke-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
