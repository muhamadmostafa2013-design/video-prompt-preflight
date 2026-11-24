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
