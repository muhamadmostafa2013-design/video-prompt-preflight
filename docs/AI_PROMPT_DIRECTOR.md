# AI Prompt Director — German Educational Preflight

**Purpose:** Review German-learning video and music prompts *before* Gemini production. This is local, deterministic QA, not a full German grammar corrector.

## Gates

1. Educational QA: learning objective, CEFR level, learner age and required phrases.
2. Language QA: exact dialogue speaker/text consistency with the scene prompt, limited known article/noun pairs and speaking-rate estimates.
3. Continuity: persistent cast and visual anchor across multiple scenes.
4. Gemini & VPP: existing duration/ratio bounds, triple-review and caption contradictions.
5. Final approval: any blocking error or unresolved warning means no generation.

### Job schema

See examples/production_university_video.yml and examples/production_animals_song.yml.

Required: learning_objective, cefr_level, learner_age ([min,max]), target_phrases.
For multi-scene videos: cast and continuity_anchor.
Each speaking scene needs expected_dialogue with speaker and exact German text.
A truly silent scene can instead set silent: true. In this version educational
target phrases must still appear in at least one declared speaking turn.

### Offline usage

    pip install -e '.[dev]'
    vpp director-review examples/production_university_video.yml
    vpp director-review examples/production_animals_song.yml --json
    vpp director-review examples/production_university_video.yml --json -o report.json --prompt-out final-prompt.txt

Exit status: 0 = ready_for_generation; 2 = blocked; 3 = needs_revision.
The CLI only creates a generator prompt when ready. No API requests are made.

Production dry-run:

    python -m vpp.production --spec examples/production_university_video.yml

The production engine enforces the Director gate before paid approval, secret
lookup or API calls. Its preflight report includes the Director findings.

### Browser

The Director's Room has a single-scene browser precheck. It cannot analyze
multi-scene YAML or song files; use the Python CLI for authoritative integration.

### Important limits

- Passing deterministic checks is NOT a certification of complete German
  grammar, pedagogy, pronunciation, video fidelity or intellectual-property rights.
- Article validation uses only a small curated noun list, not a grammar parser.
- The source script should be reviewed by a qualified German-speaking teacher
  and the rendered video or song listened to before publication.
- No Notion, tldraw, vidIQ, Gemini or other external services are called during
  local preflight. Paid generation remains strictly opt-in.
