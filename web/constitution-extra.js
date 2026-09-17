window.VPP = window.VPP || {};
(() => {
  const A = window.VPP;
  const base = A.constitutionReview || (() => []);

  const S = {
    geminiHelp:{name:"Google Gemini Apps Help — Generate videos with Gemini Apps",url:"https://support.google.com/gemini/answer/16126339"},
    flow:{name:"Google Flow Help — models and supported features",url:"https://support.google.com/flow/answer/16352836"},
    geminiCommunity:{name:"Reddit r/GeminiAI — Gemini Omni trial-and-error structure",url:"https://www.reddit.com/r/GeminiAI/comments/1tzu0uo/after_a_lot_of_trial_and_error_with_gemini_omni/"},
    kling3:{name:"Kling AI — VIDEO 3.0 Model User Guide",url:"https://kling.ai/quickstart/klingai-video-3-model-user-guide"},
    klingOmni:{name:"Kling AI — VIDEO 3.0 Omni Model User Guide",url:"https://kling.ai/quickstart/klingai-video-3-omni-model-user-guide"},
    seedance25:{name:"ByteDance Seed — Seedance 2.5",url:"https://seed.bytedance.com/en/seedance2_5"},
    seedance25News:{name:"ByteDance Seed — Introducing Seedance 2.5",url:"https://seed.bytedance.com/en/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5"},
    luma:{name:"Luma — Official model information",url:"https://lumalabs.ai/llm-info"},
    lumaRefs:{name:"Luma — How To Use References Properly",url:"https://lumalabs.ai/learning-center/articles/how-to-use-references-properly"},
    lumaModel:{name:"Luma Agents — Ray 3.2 controls",url:"https://docs.agents.lumalabs.ai/guides/model"},
    grok:{name:"xAI — Create Short Videos From Prompts",url:"https://x.ai/grok/use-cases/video-generation"},
    grok15:{name:"xAI — Grok Imagine Video 1.5",url:"https://x.ai/news/grok-imagine-video-1-5"},
    vidu:{name:"Vidu Platform — Text to Video API",url:"https://platform.vidu.com/docs/text-to-video"},
    viduI2V:{name:"Vidu Platform — Image to Video API",url:"https://platform.vidu.com/docs/image-to-video"},
    dreamina:{name:"Dreamina — Text to Video Generator",url:"https://dreamina.capcut.com/tools/text-to-video-ai"},
    canva:{name:"Canva Help — AI prompting tips",url:"https://www.canva.com/help/ai-prompting-tips/"},
    sora:{name:"OpenAI — Sora 2",url:"https://openai.com/index/sora-2/"},
    soraApi:{name:"OpenAI API — Create a video",url:"https://developers.openai.com/api/reference/typescript/resources/videos/methods/create"}
  };

  const add=(out,id,severity,message,recommendation,points,sources,tier="A",scope="generic")=>out.push({
    rule_id:id,agent:"Constitution Scout",severity,message,recommendation,points,sources,evidence_tier:tier,provider_scope:scope
  });

  const feat=text=>{
    const actions=(text.match(/\b(?:show|display|transform|morph|animate|cut|zoom|move|switch|split|highlight|transition|appear|disappear|walk|run|drive|turn|gesture)\w*\b/gi)||[]).length;
    const dialogue=(text.match(/\b(?:says?|asks?|replies?|answers?|shouts?|whispers?)\b/gi)||[]).length;
    const imageToVideo=/\b(?:image[- ]to[- ]video|input image|starting frame|start frame|reference image|first frame|ingredient|reference video)\b/i.test(text);
    const multishot=/\b(?:multi[- ]?shot|shot\s*#?\s*\d+|scene\s*#?\s*\d+|storyboard)\b/i.test(text);
    return {actions,dialogue,imageToVideo,multishot};
  };

  A.constitutionReview=(text,scene,provider="generic")=>{
    let out=base(text,scene,provider) || [];
    const f=feat(text);

    if(provider==="gemini_omni"){
      add(out,"gemini_omni.current_product_model","info","Gemini Apps currently generate and edit video with Gemini Omni; this is a different product profile from Veo 3.1 in developer/Flow workflows.","Use the Gemini Omni profile for the Gemini app and the Veo profile when you are actually using Veo 3.1.",0,[S.geminiHelp],"A","gemini_omni");
      if(f.imageToVideo) add(out,"gemini_omni.references","info","Gemini Omni can combine text with image/video inputs and conversational edits.","Use references to anchor identity/composition and use follow-up edits for local changes instead of rewriting the entire prompt.",0,[S.geminiHelp],"A","gemini_omni");
      if(f.dialogue>=2) add(out,"gemini_omni.multispeaker.community","warning","Community testing still reports speaker swaps in complex multi-person dialogue.","For correctness-critical dialogue, prefer one active speaker per shot or split and stitch lines in editing.",6,[S.geminiCommunity],"C","gemini_omni");
      add(out,"gemini_omni.audio_layers.community","info","A recurring Gemini Omni community workflow separates Dialogue, SFX and Ambient instructions.","Treat this as an experiment: separate native-audio intent into Dialogue / SFX / Ambient layers and compare against a plain-language baseline.",0,[S.geminiCommunity],"C","gemini_omni");
    }

    if(provider==="kling"){
      out=out.filter(x=>!String(x.rule_id).startsWith("kling."));
      if(f.multishot) add(out,"kling3.multishot","info","Kling VIDEO 3.0 natively supports automatic and custom multi-shot generation.","Use explicit shot descriptions/durations when you need control; do not force a one-shot-only rule.",0,[S.kling3],"A","kling");
      if(f.imageToVideo) add(out,"kling3.references","info","Kling 3.0/Omni supports start/end frames and multi-image/video element references.","Anchor recurring characters, products or props with references when continuity matters.",0,[S.klingOmni],"A","kling");
      if(f.dialogue>=2) add(out,"kling3.dialogue_labels","info","Kling 3.0 improves multi-character coreference for native audio.","Pair every line with a clear character label and verify speaker assignment after generation.",0,[S.kling3],"A","kling");
    }

    if(provider==="seedance"){
      out=out.filter(x=>!String(x.rule_id).startsWith("seedance."));
      if(f.multishot) add(out,"seedance25.multishot","info","Seedance 2.5 is built for up-to-30-second multi-shot storytelling and extensions.","Keep narrative beats and continuity anchors explicit rather than reducing every sequence to one action.",0,[S.seedance25,S.seedance25News],"A","seedance");
      if(f.imageToVideo) add(out,"seedance25.references","info","Seedance 2.5 supports multimodal references and editing.","Use references for composition, identity, motion, camera language or audio when these need to persist.",0,[S.seedance25News],"A","seedance");
    }

    if(provider==="luma"){
      out=out.filter(x=>!String(x.rule_id).startsWith("luma."));
      add(out,"luma.current_model","info","Luma's current public video model is Ray 3.2; Ray2 and earlier Ray workflows are legacy.","Use Ray 3.2 controls and current reference/keyframe workflows for new projects.",0,[S.luma],"A","luma");
      if(f.imageToVideo) add(out,"luma.keyframes","info","Ray 3.2 supports start/end frames and multi-keyframe anchoring.","Use visual anchors when endpoints or identity matter instead of expanding prose indefinitely.",0,[S.lumaModel],"A","luma");
      if(f.multishot) add(out,"luma.references","info","Luma recommends establishing master references before iterative branching to reduce drift.","Define non-negotiable character/product/brand references before generating variants.",0,[S.lumaRefs],"A","luma");
    }

    if(provider==="grok"){
      add(out,"grok.core_brief","info","xAI's current video guidance centers the prompt on subject, action, camera movement and mood.","Write the shot as a compact creative brief and make camera/pacing explicit only where they matter.",0,[S.grok],"A","grok");
      if(f.dialogue>=2) add(out,"grok.native_audio","info","Grok Imagine Video 1.5 generates speech, ambience and SFX in the same pass.","Make speaker ownership and audio intent explicit, then verify lip-sync/output rather than assuming native audio is exact.",0,[S.grok15],"A","grok");
    }

    if(provider==="vidu"){
      add(out,"vidu.settings","info","Vidu Q3 exposes duration and seed as explicit generator controls.","Keep generator settings out of creative prose when the API already has a dedicated field.",0,[S.vidu],"A","vidu");
      if(f.imageToVideo) add(out,"vidu.i2v","info","Vidu image-to-video uses the uploaded image as the start frame.","Let the image anchor appearance and spend prompt budget on motion, camera and intended changes.",0,[S.viduI2V],"A","vidu");
    }

    if(provider==="dreamina"){
      add(out,"dreamina.brief","info","Dreamina recommends a compact brief: subject + action + setting + camera + style/mood.","Use the five essentials, then add sound/dialogue only when relevant.",0,[S.dreamina],"A","dreamina");
      if(f.actions>5) add(out,"dreamina.short_first","info","Dreamina recommends proving the idea in a short first draft and refining one dimension at a time.","Test subject, motion, framing and style separately before expanding the scene.",0,[S.dreamina],"A","dreamina");
    }

    if(provider==="canva"){
      add(out,"canva.front_load","info","Canva recommends putting the most important subject/action first and describing camera movement clearly when it matters.","Front-load the focal idea and keep secondary detail behind it.",0,[S.canva],"A","canva");
    }

    if(provider==="sora_legacy"){
      add(out,"sora.product_discontinued","warning","The Sora consumer product has been unavailable since April 26, 2026.","Do not build new consumer workflows around Sora.",0,[S.sora],"A","sora_legacy");
      add(out,"sora.api_sunset","warning","The Sora API is scheduled to permanently shut down on September 24, 2026.","Treat this as a migration-only legacy profile and choose another active provider for new work.",0,[S.soraApi],"A","sora_legacy");
    }

    return out;
  };
})();
