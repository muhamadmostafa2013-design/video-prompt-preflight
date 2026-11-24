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

`vpp ctc-evidence sample.mp3 --model-dir /local/german-ctc` uses a Wav2Vec2 CTC model (e.g. aware-ai/wav2vec2-base-german) with word timestamps and a 300-second bound. Explicit local safetensors, FFmpeg and Transformers/Torch required. The public model smoke also attempts this backend on the same three public FLEURS clips and compares the evidence to faster-whisper. Expect disagreements: a blocked consensus is useful evidence, not an integration failure. Raw invalid CTC intervals are retained with timing_issues, and are blocked from repair; textual WER is reported separately.

`vpp phoneme-evidence short.wav --model-dir /local/phoneme-ctc` requires a trusted local Wav2Vec2 phoneme tokenizer configuration and safetensors weights, max 30 seconds. It returns CTC phone labels; no automatic IPA pronunciation correctness, accent grading or time-alignment approval. The public smoke attempts the upstream phoneme model's safetensors conversion (refs/pr/4, published weight SHA-256 verified). Successful execution is distinct from pronunciation accuracy; check CI results. Do not load arbitrary pickle or remote model code.

## Appearance continuity and dashboard

Optional scene `appearance` object: group, expected, alternatives. Use explicit whole-frame costume, prop and art-style descriptions, not person identity or face matching. CLIP compares these labels independently per sampled frame and flags ambiguous or inconsistent groups. The result remains a review signal. The local report viewer provides summary metrics and expandable evidence without JavaScript or network connections. It is not a model execution web server.

## One-command local project runner

Copy and adapt `examples/quality_project.json` inside your local project directory (all manifest input paths must resolve within that directory). First run align-song using the same exact audio/video; pre-download local models. Then run `vpp quality-run project.json -o review-run`. It records each requested stage separately, refuses missing semantic/consensus evidence, and writes JSON + dashboard. Set render and clean_source true only for a clean source with no baked-in subtitles; missing/failed stages block rendering. The runner never claims publication approval and doesn't invoke provider APIs. Optional preflight, song_spec, cost_spec, whisper_model, phoneme_model/phoneme_audio and independent_tracks inputs are documented by the manifest field names. Some stages can be computationally heavy; this is CLI integration, not a hosted model execution GUI.

The unified runner additionally blocks rendering when sampled scene or appearance descriptions disagree or are ambiguous, or when repaired caption intervals do not satisfy the declared scene manifest. This is a conservative review gate, not proof of semantic correctness or lip-sync.

The CTC adapter normalizes real numeric scalars to native Python floats without changing their numeric values. This prevents NumPy scalar types from being misclassified as missing timestamps. Actual interval/order/text failures still block repair. The public smoke compares two German CTC checkpoints on identical FLEURS clips; same-family checkpoints do not count as independent families. These three clips are insufficient for model selection in production.

## Cross-component audit

Run `vpp integration-simulate --seed 20261124 --trials 1200`. Twelve categories include clean controls, source mismatch, missing words, timing disagreement, duration overrun, shared family, invalid boundaries, scene mismatch, ambiguous visual score, insufficient budget, remote-only routing and inadequate risk sample. CI uses three seeds (3,600 new cases), in addition to the earlier 3,600 timing/prompt cases. Inputs are synthetic, not production accuracy. Whisper and CTC normalize model numeric scalars without guessing timestamps; source duration constrains guarded repair. JSON report inputs reject duplicate keys and non-finite constants; the unified runner blocks invalid stage results and non-boolean render options. Unknown-scene costs are not claimed as savings.
