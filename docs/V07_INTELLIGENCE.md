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

The encoded project pipeline regression exercises actual FFmpeg decode, repair, mux, stream preservation and dashboard creation with controlled synthetic model evidence (CLIP mocked). It also proves mismatched audio and inconsistent scene phrases prevent final rendering. The shared strict JSON reader also rejects overflowing exponent numbers and is applied to alignment evidence loading. This is not an end-to-end real singing accuracy test.


## Acoustic cue drift diagnostic (experimental)

`vpp acoustic-review --audio source.mp4 --srt old.srt --evidence track.json --tolerance-ms 150 -o acoustic-audit` now includes a per-cue `cue-drift.csv` and JSON summary. Positive errors mean the caption boundary is later than the acoustic candidate; negative errors mean earlier. MAE, nearest-rank p95 and maximum are computed only across measured boundaries. A cue receives no numerical estimate when any word is missing, ambiguous, invalid, noncontiguous, or its screen interval exceeds the declared evidence duration. Unmeasured cues are counted explicitly; zero measured cues yields null metrics, not zero error. Thresholds are engineering heuristics. The audio hash binds the supplied evidence to the source bytes, not the truth of its declared timing or model. These diagnostics are for listening review only; no SRT modifications, automatic repair, model accuracy or publication approval. The existing subtitle-sync/consensus gate remains the separate repair path.

### Unified project integration

Set `"acoustic_drift_review": true` in the project manifest to include a separate source-bound acoustic drift report per supplementary track in `project-report.json` and the offline dashboard. Optional `"acoustic_drift_tolerance_ms": 150` is an integer between 0 and 5000; it is separate from the consensus repair tolerance. An unavailable or malformed requested track blocks the requested workflow; a measured timing deviation is a diagnostic, not a repair approval or a substitute for the consensus gate. No new model execution or paid API is introduced by this option. Existing manifests are unchanged by default. Review the original captions, not the repaired captions, in these per-track diagnostics.

### Acoustic report readability and automation contract

The offline project dashboard now displays per-track caption drift tables, with signed millisecond errors and explicit missing measurements. Model labels and caption text are HTML-escaped. No scripts, external resources or automatic publication are enabled. The `consensus` command exits 2 for blocked evidence and 3 for review agreement; callers must still inspect the report and obtain human listening review.
