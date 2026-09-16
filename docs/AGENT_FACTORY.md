# VPP Multi-Agent Triple Review

VPP v0.3 adds a local-first review factory without replacing the deterministic core.

## Roles

1. **Orchestrator** — selects provider profile and review path.
2. **Deterministic Verifier** — checks duration, timeline, speech, exact text and contradictions.
3. **Candidate Factory** — compiles three semantically conservative prompt candidates.
4. **Knowledge Scout** — matches provider guidance and research-backed failure categories.
5. **Adversarial Critic** — looks for timing margin and text-vs-motion competition.
6. **Failure Memory** — surfaces related prior real-world failures.
7. **Independent Gatekeeper** — blocks output on hard errors, overflow or candidate constraint loss.

## Three rounds

### Round 1 — correctness + comparison

- parse free-form prompt;
- run hard deterministic checks;
- compile A/B/C candidates;
- score candidate brevity, provider fit and hard-constraint coverage;
- select a winner.

### Round 2 — failure prediction

- apply Veo / Runway knowledge packs;
- apply VBench / T2V-CompBench / EvalCrafter-inspired risk categories;
- run adversarial checks;
- surface matching failure-memory entries.

### Round 3 — independent gate

The gate only consumes artifacts and scores. It does not trust the candidate generator's rationale.

A prompt is blocked when:

- deterministic errors remain;
- the timing simulator reports overflow;
- the selected candidate drops hard constraints.

## Hard vs soft constraints

Hard constraints stay deterministic whenever possible. Examples:

- exact screen-text whitelist;
- language ownership;
- subtitle policy;
- music policy;
- exact duration;
- timeline arithmetic;
- candidate constraint preservation.

Provider guidance and benchmark-derived patterns are advisory unless promoted to a hard regression rule by repeated evidence.

## Token economics

`Fast Analyze` and `Triple Verify` in v0.3 make zero API calls. Optional LLM agents can be added later behind adapters, but they are not required for the current pipeline.

## Safety against runaway loops

The current engine uses exactly three review rounds, three candidates and one gate. It has no autonomous unbounded retry loop.
