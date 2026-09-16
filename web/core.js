window.VPP = window.VPP || {};
(() => {
  const A = window.VPP;
  A.hasArabic = t => /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]/u.test(t || "");
  A.wordCount = t => (t || "").trim().split(/\s+/u).filter(Boolean).length;
  const clean = x => x.trim().replace(/^(?:[-*•]\s+)/u, "").replace(/\s+/g, " ");
  const morphRe = /\b(?:transform|morph|animate)\b[^\n.;]{0,120}\b(?:into|to)\b/i;
  const stableTextRe = /\b(?:show|display|hold|static|keep|present|visible)\b/i;

  A.add = (a, rule_id, severity, message, recommendation, points, agent="Deterministic Verifier", sources=[]) =>
    a.push({rule_id,severity,message,recommendation,points,agent,sources});

  A.isTextMorphAction = action => morphRe.test(String(action || ""));

  A.safeTextAction = action => {
    const original = String(action || "").trim();
    const m = original.match(/\b(?:transform|morph|animate)\s+(.+?)\s+(?:into|to)\s+([^;]+)(.*)$/i);
    if (!m) return original;
    const before = m[1].trim();
    const after = m[2].trim();
    const tail = (m[3] || "").replace(/^;\s*/, "").trim();
    const safe = `show ${before} as static text, hold clearly, hard cut, then show ${after} as static text; do not morph, scramble, interpolate or animate letters`;
    return tail ? `${safe}; ${tail}` : safe;
  };

  A.parsePrompt = text => {
    const durations = [...text.matchAll(/(?<!\d)(\d+(?:\.\d+)?)\s*(?:[-–—]\s*)?(?:seconds?|secs?|sec|ثانية|ثواني)\b/giu)].map(m => Number(m[1]));
    const duration = durations[0] || 10;
    const aspect = (text.match(/\b(9\s*:\s*16|16\s*:\s*9|1\s*:\s*1|4\s*:\s*5)\b/i)?.[1] || "9:16").replace(/\s/g, "");
    const low = text.toLowerCase();
    const quoted = [...text.matchAll(/["“”](.*?)["“”]/gs)].map(m=>m[1]).filter(A.hasArabic);
    const arabic = quoted.sort((a,b)=>b.length-a.length)[0] || "";
    const lines = text.split(/\r?\n/), screen = []; let capture = false;

    for (const raw of lines) {
      const line = clean(raw);
      if (/^(on[- ]screen|screen text|on screen title|final screen)\s*:/i.test(line)) {
        capture = true;
        const inline=line.split(":").slice(1).join(":").trim();
        if(inline) screen.push(inline);
        continue;
      }
      if (capture && line.endsWith(":")) { capture=false; continue; }
      if (capture && line) {
        if (/^(show|display|transform|morph|animate|presenter|camera|visual|highlight|pause|no |do not|don't|never|only|then )/i.test(line)) {
          capture=false; continue;
        }
        if (line.length<=80 && line.split(/\s+/).length<=8 && (/[A-Za-zÄÖÜäöüß]/u.test(line)||A.hasArabic(line))) {
          screen.push(line.replace(/\.$/,""));
        }
      }
    }

    const timeline=[];
    for (const raw of lines) {
      const line=clean(raw),m=line.match(/(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*s\b/i);
      if(m){
        const start=Number(m[1]),end=Number(m[2]);
        if(end>start) timeline.push({
          seconds:end-start,
          action:line.slice((m.index||0)+m[0].length).replace(/^[:\s–—-]+/,"")||"unspecified action"
        });
      }
    }

    const style=[];
    ["premium educational short","dark modern studio","warm cinematic lighting","cinematic","modern educational","same Egyptian male presenter"]
      .forEach(p=>{if(low.includes(p.toLowerCase()))style.push(p)});

    const noArabic=/(?:no|do not|don't|without)\s+(?:any\s+)?arabic\s+(?:text|writing|subtitles?)/i.test(text);
    const noSubs=/(?:no|do not|don't|without)\s+(?:automatic\s+)?subtitles?/i.test(text);
    const noMusic=/(?:no|without|do not use|don't use)\s+(?:background\s+)?music/i.test(text);
    const presenterArabic=/presenter[^.\n]{0,100}(?:arabic only|speaks?[^.\n]{0,30}arabic)/i.test(text)
      ||/presenter[^.\n]{0,120}(?:must not|do not|don't)[^.\n]{0,50}pronounce[^.\n]{0,40}german/i.test(text);
    const textMorph = screen.length > 1 && timeline.some(e=>A.isTextMorphAction(e.action));

    return {
      name:"Imported free-form prompt",
      aspect_ratio:aspect,
      duration_seconds:duration,
      style,
      spoken:{arabic,german_by_presenter:[]},
      screen_text:[...new Set(screen)],
      text_whitelist:[...new Set(screen)],
      timeline,
      rules:{
        no_arabic_on_screen:noArabic,
        no_auto_subtitles:noSubs,
        no_background_music:noMusic,
        presenter_arabic_only:presenterArabic,
        same_presenter:/same(?:\s+\w+){0,2}\s+presenter/i.test(text),
        avoid_text_morph:textMorph,
        max_screen_text_items:6,
        max_events_per_10s:5,
        max_spoken_words_per_second:2.7
      },
      forbidden:[],
      parse_meta:{duration_mentions:durations,parser:"deterministic-web-v0.4"}
    };
  };

  A.simulate = scene => {
    const d=Number(scene.duration_seconds||10);
    const total=(scene.timeline||[]).reduce((s,e)=>s+Number(e.seconds||0),0);
    const words=A.wordCount(scene.spoken?.arabic||"");
    const speech=words/2.7, util=speech/d, rate=(scene.timeline||[]).length/d*10;
    let status="comfortable";
    if(total>d+.05||util>1)status="overflow";
    else if(util>.86||rate>6)status="tight";
    return {duration:d,total,words,speech,util,events:(scene.timeline||[]).length,text:(scene.screen_text||[]).length,status,rate};
  };

  A.analyze = (scene,text) => {
    const out=[], d=Number(scene.duration_seconds||0), rules=scene.rules||{}, screen=scene.screen_text||[], timeline=scene.timeline||[];

    if(d<=0) A.add(out,"duration.missing","error","A positive duration is required.","Set one exact scene duration.",30);

    if(rules.no_arabic_on_screen){
      const bad=screen.filter(A.hasArabic);
      if(bad.length) A.add(out,"screen_text.arabic","error",`Arabic screen text found: ${JSON.stringify(bad)}`,"Move Arabic text to post-production.",35);
    }

    if(screen.length>6) A.add(out,"screen_text.crowded","warning",`${screen.length} screen-text items requested.`,`Reduce text or split the scene.`,12);

    const total=timeline.reduce((s,e)=>s+Number(e.seconds||0),0);
    if(total>d+.05) A.add(out,"timeline.overflow","error",`Timeline totals ${total.toFixed(1)}s but scene is ${d}s.`,`Shorten events.`,35);

    const wc=A.wordCount(scene.spoken?.arabic||""),cap=d*2.7;
    if(wc>cap) A.add(out,"speech.too_dense","warning",`Arabic dialogue has ${wc} words; capacity is about ${Math.floor(cap)}.`,`Shorten dialogue.`,12);

    const durations=[...new Set(scene.parse_meta?.duration_mentions||[])];
    if(durations.length>1) A.add(out,"prompt.duration.conflict","error",`Conflicting durations: ${durations.join(", ")}s.`,`Use one exact duration.`,35);

    const low=text.toLowerCase();
    const noMusic=/(?:no|without|do not use|don't use)\s+(?:background\s+)?music/i.test(text);
    const yesMusic=/(?:add|use|with|include)\s+(?:soft\s+|subtle\s+)?(?:background\s+)?music/i.test(text);
    if(noMusic&&yesMusic) A.add(out,"prompt.music.conflict","error","Prompt both forbids and requests music.","Choose one audio policy.",30);

    const noSub=/(?:no|without|do not|don't)\s+(?:automatic\s+)?subtitles?/i.test(text);
    const yesSub=/(?:add|show|include|generate)\s+(?:automatic\s+)?subtitles?/i.test(text);
    if(noSub&&yesSub) A.add(out,"prompt.subtitle.conflict","error","Prompt both forbids and requests subtitles.","Keep subtitles in one stage only.",30);

    const noGerman=/presenter[^.\n]{0,120}(?:must not|do not|don't)[^.\n]{0,50}(?:pronounce|speak)[^.\n]{0,40}german/i.test(text);
    let yesGerman=false;
    for(const s of low.split(/[.\n]+/)){
      if(!s.includes("presenter"))continue;
      if(/(?:must not|do not|don't|never)[^;]{0,60}(?:pronounce|speak|say)/i.test(s))continue;
      if(/(?:say|says|pronounce|pronounces|speak|speaks)[^;]{0,60}(?:german|laufen|verfahren|verlaufen|hören|verschlafen)/i.test(s)){
        yesGerman=true;break;
      }
    }
    if(noGerman&&yesGerman) A.add(out,"prompt.audio.conflict","error","Presenter is both forbidden and asked to pronounce German.","Move German pronunciation to verified post audio.",40);

    const actions=(low.match(/\b(?:show|display|transform|morph|animate|cut|zoom|move|switch|split|highlight|pause|transition|appear|disappear)\b/g)||[]).length;
    const maxA=Math.max(5,Math.round(d/10*7));
    if(actions>maxA) A.add(out,"prompt.action_density","warning",`About ${actions} visual/action instructions for ${d}s.`,`Reduce actions or split the scene.`,15);

    const morphActions = timeline.filter(e=>A.isTextMorphAction(e.action));
    if(screen.length && morphActions.length){
      A.add(
        out,
        "screen_text.morph_risk",
        "warning",
        "Exact on-screen text is being morphed or animated between states. Generative video can corrupt letters during the transition.",
        "Use separate static text states with a clean hard cut, or add exact educational text in post-production.",
        22
      );
    }

    if(screen.length){
      const missingStable = screen.filter(item => {
        const needle=String(item).toLowerCase();
        return !timeline.some(e => {
          const action=String(e.action||"");
          return action.toLowerCase().includes(needle) && stableTextRe.test(action);
        });
      });
      if(missingStable.length){
        A.add(
          out,
          "screen_text.state_coverage",
          "warning",
          `Exact text states are not explicitly held as stable text: ${missingStable.join(" | ")}.`,
          "Give every required string an explicit show/hold/static state. Avoid relying on a morph transition to imply the source or target text.",
          18
        );
      }
    }

    if(!out.length) A.add(out,"preflight.clean","info","No deterministic preflight risks detected.","",0);
    return out;
  };

  A.compile = scene => {
    const r=scene.rules||{};
    const lines=[
      `SCENE: ${scene.name||"Scene"}`,
      `FORMAT: vertical ${scene.aspect_ratio||"9:16"}; exact duration ${scene.duration_seconds||10}s`
    ];
    if(scene.style?.length) lines.push(`STYLE: ${scene.style.join("; ")}`);
    if(scene.spoken?.arabic) lines.push(`ARABIC AUDIO ONLY: "${scene.spoken.arabic}"`);
    if(r.presenter_arabic_only) lines.push("PRESENTER AUDIO: Egyptian Arabic only; do not pronounce German.");
    if(scene.screen_text?.length) lines.push(`EXACT SCREEN TEXT ONLY: ${scene.screen_text.join(" | ")}`);
    if(scene.text_whitelist?.length) lines.push("TEXT WHITELIST IS STRICT; render no other words or subtitles.");
    if(scene.screen_text?.length){
      lines.push("TEXT SAFETY: each exact string is a separate static state; use clean cuts between states; never morph, interpolate, scramble or animate letters. If exact spelling cannot be rendered reliably, leave the text area blank for post-production overlay.");
    }
    if(scene.timeline?.length){
      let c=0;
      lines.push("TIMELINE: "+scene.timeline.map(e=>{
        const s=c;c+=Number(e.seconds||0);
        const action=scene.screen_text?.length?A.safeTextAction(e.action):e.action;
        return `${s}-${c}s ${action}`;
      }).join("; "));
    }
    const strict=[];
    if(r.no_arabic_on_screen) strict.push("no Arabic text on screen");
    if(r.no_auto_subtitles) strict.push("no automatic subtitles");
    if(r.no_background_music) strict.push("no background music");
    if(r.same_presenter) strict.push("same presenter identity, wardrobe, studio and lighting");
    if(strict.length) lines.push(`STRICT: ${strict.join("; ")}.`);
    return lines.join("\n");
  };
})();
