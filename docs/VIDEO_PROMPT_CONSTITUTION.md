# VPP Video Prompt Constitution v1.0

This document is the evidence hierarchy and operating doctrine for Video Prompt Preflight. It is deliberately provider-aware: a rule that is correct for Runway is not silently promoted into a universal rule for Veo, Kling, Wan, Luma, PixVerse, Pika, MiniMax/Hailuo, Seedance or Firefly.

## Evidence hierarchy

- **A — Official**: first-party model/platform documentation. Strongest source for provider-specific behavior.
- **B — Cross-platform / VPP regression**: a principle repeated across multiple first-party guides, or reproduced by a real VPP generation failure.
- **C — Community empirical**: repeated creator observations from Reddit/forums. Useful for risk prediction, never a hard rule without reproduction.
- **D — Hypothesis**: plausible but unverified. May be shown as an experiment suggestion only.

A lower-tier rule must never override a contradictory higher-tier provider instruction.

## Universal production doctrine

1. **Feasibility before beauty.** Fit the requested actions, text states, dialogue and camera changes into the clip duration before adding cinematic detail.
2. **Use a shot structure.** A robust default is: cinematography/shot + subject + visible action + context/scene + style/lighting; audio is a separate layer when supported.
3. **Describe observable behavior.** Prefer physical actions over abstract feelings: `hands shake and shoulders tense` is more controllable than `looks nervous`.
4. **One primary beat in short clips.** Short clips should normally have one focal action. Multi-shot or multi-beat prompting is reserved for models that explicitly support it and should use ordered beats/timestamps.
5. **Camera is a separate control surface.** State framing and one motivated camera move when it matters. Avoid stacking unrelated pan/zoom/dolly/orbit instructions unless the provider explicitly supports the combination.
6. **Image-to-video is different from text-to-video.** When the input image already fixes subject, composition, lighting and style, the prompt should primarily direct motion, camera and timing instead of re-describing the image.
7. **References beat re-description for identity.** Use character/style/start-frame references when supported. Repeating a canonical character description is a fallback, not a substitute for a reference system.
8. **Own the audio.** Assign dialogue to an explicit speaker and separate dialogue, SFX, ambience and music when the model supports native audio.
9. **Critical text is production data, not decoration.** If spelling must be exact, prefer a text image/reference or post-production overlay. Do not rely on generative letter morphing for educational terms, product names, legal text or numbers.
10. **Never morph exact educational text.** This is a VPP hard regression rule after a real Veo generation produced transient nonsense strings between correct German words. Use static states + hard cuts, or add text in post.
11. **Iterate scientifically.** Start with a minimal viable prompt and change one meaningful variable per iteration. Preserve the previous prompt/result so failures are attributable.
12. **No universal negative-prompt law.** Runway and Luma Modify recommend positive phrasing, while Google documents exclusions for Veo. Negative-prompt behavior is provider-specific.
13. **Prompt structure is not magic syntax.** JSON can improve organization and reproducibility, but VPP does not treat JSON itself as inherently superior unless the provider/API explicitly parses structured fields.
14. **Separate prompt QA from output QA.** A prompt can be internally perfect and the stochastic generator can still fail. Generated video must be checked for duration, aspect, identity, text, dialogue, motion and continuity.
15. **Every confirmed failure becomes a regression.** Reproduce, categorize, store expected vs observed behavior, add a detector where possible, then add a test.

## Provider profiles

### Google Veo / Gemini / Flow

Official Google guidance uses a five-part formula: **cinematography + subject + action + context + style/ambiance**. Veo supports explicit dialogue, SFX and ambience; Google documents quotation marks for exact dialogue. Veo 3.1 supports references/ingredients, first-and-last-frame transitions and timestamp prompting for multi-shot sequences. Complex fast action benefits from detailed play-by-play.

VPP empirical/community cautions: exact rendered text can misspell; multi-character dialogue can swap speakers/lip sync; static-camera requests may drift; character consistency improves more reliably with references/start frames than prose alone. These are risks, not guaranteed failures.

Sources:
- https://deepmind.google/models/veo/prompt-guide/
- https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1

### Runway Gen-4 / Gen-4.5

Runway recommends simple direct prompts, beginning with essential motion and adding one element at a time. For image-to-video, the image supplies appearance/composition/style and text should emphasize subject motion, camera motion and scene motion. Runway explicitly recommends **positive phrasing** and warns against over-complex short scenes.

Sources:
- https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide
- https://help.runwayml.com/hc/en-us/articles/42460036199443-Text-to-Video-Prompting-Guide

### Adobe Firefly Video

Adobe recommends **shot type + character + action + location + aesthetic**, clear camera direction, temporal/environment details and iterative prompting. Adobe notes that more than four subjects can confuse Firefly and recommends still frames/images to help continuity across generations.

Source:
- https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-video/writing-effective-text-prompts-for-video-generation.html

### Luma Dream Machine / Ray2

Luma recommends natural, specific language and iterative refinement. Ray2 documents an ordered structure: **main subject → action → subject details → scene → style → camera move → reinforcer** and recommends visible physical descriptions rather than vague emotion. Luma Modify recommends describing what you want rather than what to avoid.

Sources:
- https://lumalabs.ai/learning-hub/best-practices
- https://lumalabs.ai/learning-hub/dream-machine-how-to-generate-with-ray2
- https://lumalabs.ai/learning-hub/how-to-use-modify-video

### Kling AI

Kling's official formula is **subject (description) + subject movement + scene (description) + optional camera language + lighting + atmosphere**. The guide repeatedly stresses that motion/scene complexity should fit the short clip duration.

Source:
- https://kling.ai/quickstart/text-to-video-prompt-guide

### Alibaba Wan

Wan documents a basic formula **entity + scene + motion**, an advanced formula adding aesthetic control and stylization, and an image-to-video formula focusing on **motion + camera movement**. Wan also documents sound-layer formulas and timestamped multi-shot prompting.

Source:
- https://www.alibabacloud.com/help/en/model-studio/text-to-video-prompt

### PixVerse

PixVerse V5.6 recommends a structured format: **subject + subject description + motion + environment + sound + other controls such as camera**, with clear/direct/common language rather than poetic ambiguity.

Source:
- https://docs.pixverse.ai/

### MiniMax / Hailuo

MiniMax's official API documents explicit bracketed camera commands including `[Static shot]`, `[Push in]`, `[Pull out]`, pans, trucks, zooms, tilt, pedestal, tracking and shake. Provider adapters should compile camera direction into the provider's supported command vocabulary when using those models.

Source:
- https://platform.minimax.io/docs/api-reference/video-generation-t2v

### Higgsfield

Higgsfield recommends detailed layers for text-to-video, but for image animation it shifts to action, camera, timing and mood. It recommends reusable character references, positive descriptions, focused short-clip prompts, and changing one variable per iteration.

Source:
- https://higgsfield.ai/creator-hub/help-center/getting-started/how-do-i-write-a-good-prompt

### Pika

Pika's current API documentation explicitly lists precise on-screen text as a poor fit for Pika 2.5 text-to-video. This reinforces VPP's cross-provider rule that critical typography should be composed in a deterministic editing stage.

Source:
- https://mcp.pika.art/models/pika/pika-2.5/text-to-video

### Seedance

ByteDance documents native multi-shot storytelling, prompt following, complex motion and camera control. When used through third-party platforms, preserve the distinction between model-vendor documentation and platform workflow advice.

Sources:
- https://seed.bytedance.com/en/seedance
- https://seed.bytedance.com/en/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5

## Community findings for Veo — empirical, not law

Repeated creator reports suggest: keep a canonical character description unchanged across clips when no reference feature is available; prompt drift can cause identity/style drift; start/reference frames are often more reliable than pure text; exact on-screen text is a recurring failure point; multi-person dialogue is substantially less reliable than one-speaker shots; and static camera intent can still drift even when stated strongly. Some creators report JSON formatting helps them organize prompts, but there is no official evidence that JSON syntax itself is a magic quality switch.

Representative discussions:
- https://www.reddit.com/r/VEO3/comments/1p0slkg/
- https://www.reddit.com/r/VEO3/comments/1qooc3f/
- https://www.reddit.com/r/VEO3/comments/1tptw4v/
- https://www.reddit.com/r/VEO3/comments/1n9m9mn/
- https://www.reddit.com/r/PromptEngineering/comments/1ms5ri4/

## Conflict-resolution doctrine

When sources disagree, VPP uses this order:

1. Current official documentation for the selected model/version.
2. Reproduced VPP regression with a minimal test case.
3. Cross-provider official consensus.
4. Repeated community evidence from multiple independent users.
5. Single-user tips and unverified heuristics.

The UI must label evidence level and provider scope. It must never show `Risk 0` as a guarantee of generator success.
