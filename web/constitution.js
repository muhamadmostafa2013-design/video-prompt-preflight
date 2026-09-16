window.VPP = window.VPP || {};
(() => {
  const A = window.VPP;

  A.evidenceLabels = {
    A: "Official",
    B: "Cross-platform / VPP regression",
    C: "Community empirical",
    D: "Hypothesis"
  };

  const sources = {
    veo: {name:"Google Cloud — Veo 3.1 prompting guide", url:"https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1"},
    flow: {name:"Google Flow Help — create videos and references", url:"https://support.google.com/flow/answer/16353334"},
    runway: {name:"Runway — Gen-4 Video Prompting Guide", url:"https://help.runwayml.com/hc/en-us/articles/39789879462419-Gen-4-Video-Prompting-Guide"},
    runwayI2V: {name:"Runway — Image to Video Prompting Guide", url:"https://help.runwayml.com/hc/en-us/articles/48324313115155-Image-to-Video-Prompting-Guide"},
    firefly: {name:"Adobe Firefly — effective video prompts", url:"https://helpx.adobe.com/firefly/web/work-with-audio-and-video/work-with-video/writing-effective-text-prompts-for-video-generation.html"},
    luma: {name:"Luma — Ray2 prompting guide", url:"https://lumalabs.ai/learning-hub/dream-machine-how-to-generate-with-ray2"},
    kling: {name:"Kling AI — Text-to-Video Prompt Guide", url:"https://kling.ai/quickstart/text-to-video-prompt-guide"},
    wan: {name:"Alibaba Cloud — Wan video prompt guide", url:"https://www.alibabacloud.com/help/en/model-studio/text-to-video-prompt"},
    pixverse: {name:"PixVerse V5.6 User Guide", url:"https://docs.pixverse.ai/PixVerse-V5-6-User-Guide-2fe3e99bf350806f86adc8a55de3c3a7"},
    minimax: {name:"MiniMax API — video generation", url:"https://platform.minimax.io/docs/api-reference/video-generation-t2v"},
    higgsfield: {name:"Higgsfield — Popcorn storyboard guide", url:"https://higgsfield.ai/creator-hub/help-center/ai-models/how-do-i-use-popcorn"},
    pika: {name:"Pika 2.5 Text-to-Video API", url:"https://mcp.pika.art/models/pika/pika-2.5/text-to-video"},
    seedance: {name:"ByteDance Seed — Seedance", url:"https://seed.bytedance.com/en/seedance"},
    midjourney: {name:"Midjourney — Video documentation", url:"https://docs.midjourney.com/hc/en-us/articles/37460773864589-Video"},
    veoDialogueCommunity: {name:"Reddit r/VEO3 — dialogue attribution report", url:"https://www.reddit.com/r/VEO3/comments/1mprm33/help_with_wrong_characterspeechdialogue/"},
    veoStaticCommunity: {name:"Reddit r/VEO3 — locked-camera drift report", url:"https://www.reddit.com/r/VEO3/comments/1mpksvy/video_keep_zooming_in_even_if_told_not_to/"},
    veoJsonCommunity: {name:"Reddit r/VEO3 — JSON comparison discussion", url:"https://www.reddit.com/r/VEO3/comments/1rah79n/does_veo_3_really_work_better_with_the_json_prompt/"},
    vppMorph: {name:"VPP regression — exact-text morph corruption", url:"https://github.com/muhamadmostafa2013-design/video-prompt-preflight/blob/main/failures/0003_exact_text_morph_corruption.json"}
  };

  const finding = (rule_id, severity, message, recommendation, points, sourceList, tier="A", scope="generic") => ({
    rule_id,
    agent:"Constitution Scout",
    severity,
    message,
    recommendation,
    points,
    sources:sourceList,
    evidence_tier:tier,
    provider_scope:scope
  });

  const features = (text, scene) => {
    const low = text.toLowerCase();
    const sim = A.simulate(scene);
    const cameraMoves = (text.match(/\b(?:pan(?:s|ning)?|tilt(?:s|ing)?|zoom(?:s|ing)?|tracking|dolly|crane|orbit|truck|push in|pull out|pedestal|handheld)\b/gi)||[]).length;
    const actions = (text.match(/\b(?:show|display|transform|morph|animate|cut|zoom|move|switch|split|highlight|transition|appear|disappear|walk|run|drive|turn|gesture)\w*\b/gi)||[]).length;
    const negatives = (text.match(/\b(?:no|not|never|without|avoid|don't|do not|must not)\b/gi)||[]).length;
    const dialogue = (text.match(/\b(?:says?|asks?|replies?|answers?|shouts?|whispers?)\b/gi)||[]).length;
    const subjectMatch = text.match(/\b(five|six|seven|eight|nine|ten|\d+)\s+(?:people|persons|characters|subjects|men|women|children|actors)\b/i);
    const numberWords={five:5,six:6,seven:7,eight:8,nine:9,ten:10};
    let subjectCount=0;
    if(subjectMatch){const raw=subjectMatch[1].toLowerCase();subjectCount=Number(raw)||numberWords[raw]||0;}
    return {
      sim,
      actions,
      negatives,
      cameraMoves,
      dialogue,
      subjectCount,
      exactText:(scene.screen_text||[]).length>0,
      multiShot:(scene.timeline||[]).length>=2||/\b(?:shot|scene)\s*#?\s*\d+\b/i.test(text),
      imageToVideo:/\b(?:image[- ]to[- ]video|input image|start(?:ing)? frame|first frame|reference image)\b/i.test(text),
      staticCamera:/\b(?:static shot|static camera|locked[- ]?off|locked camera|stationary camera|fixed camera|tripod)\b/i.test(text),
      jsonLike:text.trimStart().startsWith("{")||text.trimStart().startsWith("["),
      minimaxCommand:/\[(?:Truck|Pan|Push|Pull|Pedestal|Tilt|Zoom|Shake|Tracking shot|Static shot)/i.test(text),
      highMotion:/--motion\s+high\b/i.test(text)||/\bhigh motion\b/i.test(text),
      textMorph:(scene.timeline||[]).some(e=>A.isTextMorphAction?.(e.action))
    };
  };

  A.constitutionReview = (text, scene, provider="generic") => {
    const f=features(text,scene), out=[];

    if(f.exactText){
      out.push(finding(
        "constitution.exact_text_is_production_data","info",
        "Exact screen text is production data, not decoration.",
        "Keep spelling-critical text static and verify it after generation; post-production overlay is the safest fallback.",0,
        [sources.pika,sources.vppMorph],"B","cross-platform"
      ));
    }
    if(f.cameraMoves>=3){
      out.push(finding(
        "constitution.camera_motion_budget","warning",
        `${f.cameraMoves} camera-movement cues may compete inside one short shot.`,
        "Keep one motivated camera move when possible, or use an explicitly supported ordered camera sequence.",8,
        [sources.runway,sources.veo],"B","cross-platform"
      ));
    }
    if(f.actions>Math.max(5,Math.round(f.sim.duration/10*7))){
      out.push(finding(
        "constitution.action_budget","warning",
        "The action load is high for the requested duration.",
        "Reduce independent beats or use a provider that explicitly supports multi-shot/ordered sequences.",8,
        [sources.runway,sources.kling],"B","cross-platform"
      ));
    }
    if(f.imageToVideo){
      out.push(finding(
        "constitution.i2v_motion_focus","info",
        "Image-to-video already has a visual anchor.",
        "Spend most prompt budget on motion, camera, timing and intentional changes instead of re-describing the input image.",0,
        [sources.runwayI2V,sources.wan],"B","cross-platform"
      ));
    }

    if(provider==="veo"){
      if(f.dialogue>=2) out.push(finding("veo.multispeaker.community","warning","Multi-person dialogue has repeated community reports of speaker swaps or lip-sync drift.","For correctness-critical dialogue, prefer one active speaker per shot or split/stitch lines in editing.",6,[sources.veoDialogueCommunity],"C","veo"));
      if(f.staticCamera) out.push(finding("veo.static_camera.community","info","A locked/static-camera request is not guaranteed to remain perfectly still in every Veo generation.","Use clear locked/static framing, verify output, and use start/end frames when exact endpoints matter and Flow supports them.",0,[sources.veoStaticCommunity,sources.flow],"C","veo"));
      if(f.jsonLike) out.push(finding("veo.json.community","info","JSON can improve organization and reproducibility, but it is not a documented magic quality switch for Veo.","Keep JSON when it helps your pipeline; optimize the actual visual instructions rather than adding markup for its own sake.",0,[sources.veoJsonCommunity],"C","veo"));
      if(f.multiShot) out.push(finding("veo.references.official","info","Flow can use ingredients/references and start/end frames to improve continuity across clips.","Anchor recurring characters/objects with references instead of relying on repeated prose alone when the feature is available.",0,[sources.flow],"A","veo"));
    }

    if(provider==="runway"){
      if(f.negatives>=4) out.push(finding("runway.positive_phrasing","warning","Runway Gen-4 guidance says negative phrasing is not supported and can behave unpredictably.","Rewrite creative negatives as the desired visible state, e.g. 'locked camera' rather than 'no camera movement'.",12,[sources.runway],"A","runway"));
      if(f.imageToVideo) out.push(finding("runway.i2v.motion_focus","info","Runway image-to-video prompts should focus almost entirely on motion.","Describe subject action, environment motion, camera motion, timing, direction and speed.",0,[sources.runwayI2V],"A","runway"));
    }

    if(provider==="firefly"){
      if(f.subjectCount>4) out.push(finding("firefly.subject_count","warning",`The prompt explicitly asks for ${f.subjectCount} subjects; Adobe notes more than four can confuse Firefly.`,"Reduce primary subjects or split the shot.",12,[sources.firefly],"A","firefly"));
    }
    if(provider==="luma"&&f.cameraMoves>=3) out.push(finding("luma.camera_stack","warning","Luma prompts are easier to control with focused, visible camera direction.","Reduce camera moves and describe observable physical action rather than abstract emotion.",8,[sources.luma],"A","luma"));
    if(provider==="kling"&&f.sim.duration<=5&&f.actions>=4) out.push(finding("kling.short_motion_budget","warning","Kling recommends straightforward movement that fits the short clip duration.","Simplify movement and scene changes.",10,[sources.kling],"A","kling"));
    if(provider==="wan"){
      if(f.imageToVideo) out.push(finding("wan.i2v_formula","info","Wan's image-to-video formula emphasizes motion plus camera movement.","Let the image carry entity/scene/style unless you intentionally want to change them.",0,[sources.wan],"A","wan"));
      if(f.multiShot) out.push(finding("wan.multishot","info","Wan supports structured multi-shot prompting with shot order/timestamps.","Use explicit shot numbers/timestamps and keep each shot's content clear.",0,[sources.wan],"A","wan"));
    }
    if(provider==="pixverse"&&f.actions>5) out.push(finding("pixverse.direct_language","warning","PixVerse recommends clear, direct, concrete prompting rather than overloaded or poetic instructions.","Reduce competing actions and use Subject + Description + Motion + Environment + Sound + Camera.",8,[sources.pixverse],"A","pixverse"));
    if(provider==="minimax"){
      if(f.cameraMoves>0&&!f.minimaxCommand) out.push(finding("minimax.camera_commands","info","MiniMax Director/Hailuo models support explicit bracketed camera commands.","Consider supported commands such as [Static shot], [Push in], [Pan left] or [Tracking shot].",0,[sources.minimax],"A","minimax"));
      if(f.cameraMoves>=3) out.push(finding("minimax.camera_stack","warning","MiniMax recommends no more than three combined camera commands.","Reduce simultaneous moves or make them sequential.",8,[sources.minimax],"A","minimax"));
    }
    if(provider==="higgsfield"&&f.multiShot) out.push(finding("higgsfield.references","info","Higgsfield's storyboard workflow uses references to preserve continuity across frames/shots.","Anchor recurring subjects and locations with references and write each beat like a film cue.",0,[sources.higgsfield],"A","higgsfield"));
    if(provider==="pika"&&f.exactText) out.push(finding("pika.precise_text","warning","Pika 2.5 explicitly lists precise on-screen text as a poor fit.","Leave critical typography out of generation and add it deterministically in editing.",18,[sources.pika],"A","pika"));
    if(provider==="seedance"&&f.multiShot) out.push(finding("seedance.multishot","info","Seedance natively supports multi-shot storytelling and complex action sequences.","Keep shot transitions and identity/style anchors explicit; do not force a universal one-action rule here.",0,[sources.seedance],"A","seedance"));
    if(provider==="midjourney"&&f.highMotion) out.push(finding("midjourney.high_motion","warning","Midjourney documents that High Motion can create larger movement but may increase unrealistic or glitchy motion.","Use Low Motion for subtle/stable animation unless the shot needs stronger movement.",10,[sources.midjourney],"A","midjourney"));

    return out;
  };
})();
