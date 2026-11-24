# VPP v0.7 experimental intelligence workflow

All outputs remain review-only. No generation, upload or paid calls are performed by these commands.

- `consensus --audio source.mp3 --tracks first.json second.json`: source-bound word tracks with backend, family, model, audio_sha256 and words (word/start/end seconds). Requires at least two declared families, identical word order and bounded all-pair timing spread. WhisperX and faster-whisper are both Whisper family. Metadata cannot establish independent provenance. Agreement is never ground truth.
- `guarded-repair --audio source.mp3 --lyrics de.txt --srt old.srt --alignment-run align --tracks other.json --output review`: one bounded repair/recheck only if agreement and existing acoustic evidence agree. Writes review-only SRT, JSON and offline HTML. No automatic video publication.
- `phoneme-review file.json`: reference/observed explicit phone arrays; phone edit rate, not acoustic pronunciation inference.
- `av-review file.json`: srt local path, duration and scenes (id/start/end/required_phrases); lexical timing containment, not actual lip sync or identity.
- `education-qa file.json`: existing song spec plus curriculum.objective and approved_vocabulary; teacher-curated vocabulary review, not general CEFR certification.
- `cost-plan file.json`: budget_cents, scenes (id/status/regenerate_cents; statuses ok, subtitle_only, visual_failed, unknown). Estimates and selective repair planning only.
- `model-route file.json`: task, memory_mb, candidates (id/task/local/weights_verified/benchmark_comparable/required_memory_mb/benchmark_loss). Explicit metadata; no network or paid fallback.
- `risk-report file.json`: category and records (id/category/failed); min 30 observations, descriptive rate and Wilson interval, not a calibrated predictor.
- `prompt-mutate --seed 20261124 --trials 600`: reproducible supported-pattern mutation tests.
- `quality-dashboard report.json -o report.html`: offline escaped report viewer with no scripts or external resources. Does not overwrite files.

Full automatic phoneme recognition, lip-sync detection, character continuity, learned grammar/semantic assessment, calibrated prediction and UI integration with all model runners require independent datasets and validation. No real-song validation is implied by unit tests. Keep private recordings/reports local. Do not treat declared model family or hashes as proof of provenance.

## Optional independent acoustic models

`vpp ctc-evidence sample.mp3 --model-dir /local/german-ctc` uses a Wav2Vec2 CTC model (e.g. aware-ai/wav2vec2-base-german) with word timestamps and a 300-second bound. Explicit local safetensors, FFmpeg and Transformers/Torch required. The public model smoke also attempts this backend on the same three public FLEURS clips and compares the evidence to faster-whisper. Expect disagreements: a blocked consensus is useful evidence, not an integration failure.

`vpp phoneme-evidence short.wav --model-dir /local/phoneme-ctc` requires a trusted local Wav2Vec2 phoneme tokenizer configuration and safetensors weights, max 30 seconds. It returns CTC phone labels; no automatic IPA pronunciation correctness, accent grading or time-alignment approval. The public smoke does not download the larger phoneme model; actual inference on it remains unverified. The upstream phoneme model may require trusted offline conversion to safetensors. Do not load arbitrary pickle or remote model code.

## Appearance continuity and dashboard

Optional scene `appearance` object: group, expected, alternatives. Use explicit whole-frame costume, prop and art-style descriptions, not person identity or face matching. CLIP compares these labels independently per sampled frame and flags ambiguous or inconsistent groups. The result remains a review signal. The local report viewer provides summary metrics and expandable evidence without JavaScript or network connections. It is not a model execution web server.
