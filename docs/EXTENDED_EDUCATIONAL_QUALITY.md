# Extended educational quality gates (experimental)

- Faster-whisper CPU inference: fixed decoding options (temperature 0, beam 5, no VAD), two CPU threads, one worker. Report model file SHA-256 and installed runtime package versions. This does not guarantee cross-machine determinism.
- Independent public singing workflow runs the same three preselected German tracks in first-minute and full-track scopes, twice per track. Full tracks over 300 seconds fail explicitly; no silent truncation. Exact word-evidence fingerprints flag nonrepeatability. These are public songs, not an educational-song benchmark.
- Consensus recognizes declared Whisper and Wav2Vec2 backend families; unknown labels cannot create independence. A declared family and file hash alone still do not authenticate evidence.
- Optional project manifest phoneme_reference points to local JSON with audio_sha256, annotation_source "teacher", accepted_phones (a list of accepted IPA token arrays). Mismatches flag suspected phones. It is not a calibrated pronunciation score.
- Optional bilingual_reference points to a JSON array of sequential {index, de, ar} teacher-approved captions. German case, Arabic letters/diacritics and punctuation are preserved (NFC and whitespace normalization only). A mismatch blocks project render. Translation meaning remains a teacher responsibility.
- Semantic scan requires a covered scene timeline and samples long scenes at intervals of at most five seconds, with a bounded 600-frame budget. CLIP similarity cannot prove scene content or all-frame continuity.

All stages remain review-only. No private media upload, paid APIs, publication approval or claim of independent human listening.

## Strict educational review profile
Set `strict_educational_qa: true` to require local semantic, curriculum, phoneme and bilingual references plus German/Arabic sampled OCR before rendering a review draft. Explicit phoneme references cannot be ignored when their model or audio is absent. Clean-source OCR samples the source timeline independently of old subtitle timing; rendered captions and gaps now receive bounded two-second sampling. Large sample jobs must be split or explicitly increase the cap. This profile still never approves publication or proves that the short phoneme clip represents every word in a song.

The public benchmark additionally runs a full_chunked scope: fixed 30-second core windows with five seconds of context, exact PCM slicing, source-time offsets, and single onset ownership. The same full-song reference is used only by the scorer. Unassignable timestamps are counted and prevent a successful experimental run. This is an experiment, not an adopted accuracy improvement; compare the full and chunked results and inspect timing faults before changing any production route.

## Independent real-media review
The fixed long-song experiment did not improve results: on 800 public reference words, whole-song WER was 38.0% versus 56.5% for overlapping chunks, onset coverage within 200 ms was 58.625% versus 58.125%. Keep chunking experimental; no default routing change. See run 45424931615. WhisperX 3.7.4 uses interpolation for sentence metadata; its word boundaries remain optional. Use supported nearest interpolation for this pinned version and preserve recognized text with null timestamps if alignment drops words. The separate local align-song path checks the version before running. Ruff runs in the ordinary test matrix.

Import the Windows acoustic evidence using `vpp acoustic-review --audio original_audio.m4a --srt reference_screen_timing.srt --evidence acoustic_evidence.json -o review`. The review binds the exact audio hash and reports only equal words shared by every optimal text-edit path. Repeated lyrics with ambiguous mappings, missing boundaries and unmatched observations remain unresolved; no subtitle repair is authorized. Screen timing is not used to select matches. Private media stays local.
