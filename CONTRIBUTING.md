# Contributing

Thanks for helping improve Video Prompt Preflight.

1. Open an issue describing the failure pattern or rule.
2. Add a minimal regression scene under `examples/` or `tests/fixtures/`.
3. Add a deterministic rule when possible; prefer rules over LLM calls.
4. Add or update tests.
5. Keep auto-fixes conservative: never invent semantic content.

## Design principles
- Deterministic first.
- Generator-agnostic.
- Token-conscious.
- Every real failure becomes a regression test.
- Never claim a generated video is guaranteed error-free.
