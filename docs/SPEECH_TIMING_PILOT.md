# Local speech-timing pilot

This benchmark measures the onset and offset of German speech words against independent annotations. It does not estimate pronunciation quality, transfer audio, certify release readiness, or judge subtitle timing from subtitle screen cues. Use an owned or rights-cleared short solo recording and keep the clip, reference and ASR JSON local. No model download is initiated by the benchmark.

1. Choose one exact audio file (the same bytes and time origin for both sides). Record the SHA-256 with `Get-FileHash -Algorithm SHA256 <path>` or `sha256sum <path>` and use lowercase hex in both inputs.
2. Have a reviewer mark start/end in seconds from the recording, using the waveform and listening, before exposing them to the model output. Record genuinely spoken words in order. Keep only one word per row; overlapping speakers require a different benchmark. Save this independent JSON locally:

```json
{"schema":"vpp-human-word-boundaries-1","audio_sha256":"replace-with-lowercase-sha256","words":[{"word":"Hallo","start":0.21,"end":0.51}]}
```

3. Run local ASR separately on the exact same file. Use the existing local `asr-evidence` workflow, or a local evidence JSON containing `audio_sha256`, `source_duration_seconds` and `words` rows with `word`, `start` and `end` in the same units. Do not feed manual timestamps to the model.
4. Run `vpp speech-timing-benchmark --audio clip.wav --reference human.json --evidence asr.json`. It emits aggregate JSON, with no paths, words or source hash in successful output. Exit 3 means review-only and exit 2 means invalid input. Store the model version, recording license and reviewer notes separately from the aggregate.

Report coverage across **all** reference words within 100 and 200 ms for **both** boundaries. A repeated word whose text match is ambiguous, a missing word or a bad observation interval never contributes to the numerator. Onset and offset MAE/p95 are computed only on uniquely matched words with valid intervals and may hide missing coverage, so report both metrics together. Do not compare methods on different clips or references. Keep separate speech and singing results.
