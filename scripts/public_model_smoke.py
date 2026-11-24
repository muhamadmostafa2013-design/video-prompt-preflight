"""Network opt-in experiment; only public dataset inputs, no user media."""
import json
import os
import urllib.request
from pathlib import Path

from huggingface_hub import snapshot_download
from PIL import Image

from vpp.model_evidence import LocalCLIP, asr_evidence, text_wer


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
        model = snapshot_download("Systran/faster-whisper-small", allow_patterns=[
            "config.json", "model.bin", "tokenizer.json", "vocabulary.json",
            "preprocessor_config.json"])
        url = ("https://datasets-server.huggingface.co/first-rows?"
               "dataset=google%2Ffleurs&config=de_de&split=test")
        with urllib.request.urlopen(url, timeout=90) as response:
            data = json.load(response)
        rows = []
        for i, item in enumerate(data["rows"][:3]):
            row = item["row"]
            audio = work / f"sample-{i}.wav"
            download(row["audio"][0]["src"], audio)
            evidence = asr_evidence(audio, model)
            prediction = " ".join(w["word"] for w in evidence["words"])
            rows.append({"row_idx": item["row_idx"], "reference": row["transcription"],
                         "prediction": prediction, **text_wer(row["transcription"], prediction),
                         "word_timestamps": evidence["words"]})
        report["audio"] = {"dataset": "google/fleurs de_de test", "rows": rows,
                           "wer": sum(r["word_errors"] for r in rows)/sum(r["reference_words"] for r in rows)}
    except Exception as exc:  # noqa: BLE001 -- report independent stage failures
        errors.append({"stage": "asr", "type": type(exc).__name__, "message": str(exc)[:600]})
    try:
        model = snapshot_download("openai/clip-vit-base-patch32", allow_patterns=[
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
