const goodSample = `Create a 10-second vertical cinematic educational video. Vertical 9:16.
Same Egyptian male presenter in a dark modern studio with warm cinematic lighting.
Presenter speaks Egyptian Arabic only and must not pronounce German.
No Arabic text on screen. No automatic subtitles. No background music.

SPOKEN EGYPTIAN ARABIC:
"عايز تبدأ تفهم الألماني بدل ما تحفظه؟ ركّز في البادئة اللي قدامك… ساعات بتغيّر معنى الفعل بشكل كبير."

ON SCREEN:
ver-
laufen
sich verlaufen
hören
sich verhören

TIMELINE:
0-3s presenter delivers hook
3-5s show ver- large and clean
5-7s transform laufen into sich verlaufen
7-9s transform hören into sich verhören
9-10s hold ver- centered`;

const badSample = `Create a 10 second vertical video, but make the scene 12 seconds long.
No background music. Add subtle background music.
No automatic subtitles, but generate subtitles for every spoken sentence.
The presenter speaks Egyptian Arabic only and must not pronounce German.
The presenter should pronounce laufen and sich verlaufen clearly in German.
ON SCREEN:
ver-
يتوه وهو ماشي
laufen
sich verlaufen
Show, transform, animate, zoom, cut, switch, highlight, pause, transition and display every element quickly.`;

const $ = (id) => document.getElementById(id);
const input = $("promptInput");
const findingsEl = $("findings");
const compiledEl = $("compiledOutput");
const sceneEl = $("sceneOutput");
const statusEl = $("status");
const riskEl = $("risk");
const simulationEl = $("simulation");

function hasArabic(t){ return /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]/u.test(t || ""); }
function wordCount(t){ return (t || "").trim().split(/\s+/u).filter(Boolean).length; }
function add(a, rule_id, severity, message, suggestion, points){ a.push({rule_id,severity,message,suggestion,points}); }
function cleanLine(x){ return x.trim().replace(/^(?:[-*•]\s+)/u, "").replace(/\s+/g," "); }

function parsePrompt(text){
  const durationMatches = [...text.matchAll(/(?<!\d)(\d+(?:\.\d+)?)\s*(?:[-–—]\s*)?(?:seconds?|secs?|sec|ثانية|ثواني)\b/giu)].map(m=>Number(m[1]));
  const duration = durationMatches[0] || 10;
  const aspect = (text.match(/\b(9\s*:\s*16|16\s*:\s*9|1\s*:\s*1|4\s*:\s*5)\b/i)?.[1] || "9:16").replace(/\s/g,"");
  const low = text.toLowerCase();
  const quotedArabic = [...text.matchAll(/["“”](.*?)["“”]/gs)].map(m=>m[1]).filter(hasArabic);
  const arabic = quotedArabic.sort((a,b)=>b.length-a.length)[0] || "";

  const lines = text.split(/\r?\n/);
  const screen = [];
  let capture = false;
  for (const raw of lines){
    const line = cleanLine(raw); const l = line.toLowerCase();
    if (/^(on[- ]screen|screen text|on screen title|final screen)\s*:/i.test(line)){ capture=true; const inline=line.split(":").slice(1).join(":").trim(); if(inline) screen.push(inline); continue; }
    if (capture && line.endsWith(":")){ capture=false; continue; }
    if (capture){
      if (!line) continue;
      if (/^(show|display|transform|presenter|camera|visual|highlight|pause|no |do not|don't|never|only|then )/i.test(line)){ capture=false; continue; }
      if (line.length <= 80 && line.split(/\s+/).length <= 8 && (/[A-Za-zÄÖÜäöüß]/u.test(line) || hasArabic(line))) screen.push(line.replace(/\.$/,""));
    }
  }
  const timeline=[];
  for(const raw of lines){ const line=cleanLine(raw); const m=line.match(/(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*s\b/i); if(m){ const start=Number(m[1]), end=Number(m[2]); if(end>start) timeline.push({seconds:end-start, action:line.slice((m.index||0)+m[0].length).replace(/^[:\s–—-]+/,"")||"unspecified action"}); } }

  const style=[];
  ["premium educational short","dark modern studio","warm cinematic lighting","cinematic","modern educational","same Egyptian male presenter"].forEach(p=>{if(low.includes(p.toLowerCase())) style.push(p)});
  const noArabic=/(?:no|do not|don't|without)\s+(?:any\s+)?arabic\s+(?:text|writing|subtitles?)/i.test(text);
  const noSubs=/(?:no|do not|don't|without)\s+(?:automatic\s+)?subtitles?/i.test(text);
  const noMusic=/(?:no|without|do not use|don't use)\s+(?:background\s+)?music/i.test(text);
  const presenterArabic=/presenter[^.\n]{0,100}(?:arabic only|speaks?[^.\n]{0,30}arabic)/i.test(text) || /presenter[^.\n]{0,120}(?:must not|do not|don't)[^.\n]{0,50}pronounce[^.\n]{0,40}german/i.test(text);
  return {name:"Imported free-form prompt",aspect_ratio:aspect,duration_seconds:duration,style,spoken:{arabic,german_by_presenter:[]},screen_text:[...new Set(screen)],text_whitelist:[...new Set(screen)],timeline,rules:{no_arabic_on_screen:noArabic,no_auto_subtitles:noSubs,no_background_music:noMusic,presenter_arabic_only:presenterArabic,same_presenter:/same presenter|same male presenter/i.test(text),max_screen_text_items:6,max_events_per_10s:5,max_spoken_words_per_second:2.7},forbidden:[],parse_meta:{duration_mentions:durationMatches,parser:"deterministic-web-v0.2"}};
}

function analyze(scene,text){
  const out=[]; const duration=Number(scene.duration_seconds||0); const rules=scene.rules||{}; const screen=scene.screen_text||[];
  if(duration<=0) add(out,"duration.missing","error","A positive duration is required.","Set one exact scene duration.",30);
  if(rules.no_arabic_on_screen){const bad=screen.filter(x=>hasArabic(x)); if(bad.length)add(out,"screen_text.arabic","error",`Arabic screen text found: ${JSON.stringify(bad)}`,"Move Arabic text to post-production.",35)}
  if(screen.length>Number(rules.max_screen_text_items||6))add(out,"screen_text.crowded","warning",`${screen.length} screen-text items requested.`,`Reduce text or split the scene.`,12);
  const total=(scene.timeline||[]).reduce((s,e)=>s+Number(e.seconds||0),0); if(total>duration+.05)add(out,"timeline.overflow","error",`Timeline totals ${total.toFixed(1)}s but scene is ${duration}s.`,`Shorten events.`,35);
  const wc=wordCount(scene.spoken?.arabic||""); const cap=duration*Number(rules.max_spoken_words_per_second||2.7); if(wc>cap)add(out,"speech.too_dense","warning",`Arabic dialogue has ${wc} words; capacity is about ${Math.floor(cap)}.`,`Shorten dialogue.`,12);

  const durations=[...new Set(scene.parse_meta.duration_mentions||[])]; if(durations.length>1)add(out,"prompt.duration.conflict","error",`Conflicting durations: ${durations.join(", ")}s.`,`Use one exact duration.`,35);
  const low=text.toLowerCase();
  const noMusic=/(?:no|without|do not use|don't use)\s+(?:background\s+)?music/i.test(text); const yesMusic=/(?:add|use|with|include)\s+(?:soft\s+|subtle\s+)?(?:background\s+)?music/i.test(text); if(noMusic&&yesMusic)add(out,"prompt.music.conflict","error","Prompt both forbids and requests music.","Choose one audio policy.",30);
  const noSub=/(?:no|without|do not|don't)\s+(?:automatic\s+)?subtitles?/i.test(text); const yesSub=/(?:add|show|include|generate)\s+(?:automatic\s+)?subtitles?/i.test(text); if(noSub&&yesSub)add(out,"prompt.subtitle.conflict","error","Prompt both forbids and requests subtitles.","Keep subtitles in one stage only.",30);
  const noGerman=/presenter[^.\n]{0,120}(?:must not|do not|don't)[^.\n]{0,50}(?:pronounce|speak)[^.\n]{0,40}german/i.test(text); let yesGerman=false; for(const sentence of low.split(/[.\n]+/)){ if(!sentence.includes("presenter")) continue; if(/(?:must not|do not|don't|never)[^;]{0,60}(?:pronounce|speak|say)/i.test(sentence)) continue; if(/(?:should\s+|must\s+|will\s+|then\s+)?(?:say|says|pronounce|pronounces|speak|speaks)[^;]{0,60}(?:german|laufen|verfahren|verlaufen|hören|verschlafen)/i.test(sentence)){ yesGerman=true; break; } } if(noGerman&&yesGerman)add(out,"prompt.audio.conflict","error","Presenter is both forbidden and asked to pronounce German.","Move German pronunciation to verified post audio.",40);
  const actions=(low.match(/\b(?:show|display|transform|animate|cut|zoom|move|switch|split|highlight|pause|transition|appear|disappear)\b/g)||[]).length; const maxA=Math.max(5,Math.round(duration/10*7)); if(actions>maxA)add(out,"prompt.action_density","warning",`About ${actions} visual/action instructions for ${duration}s.`,`Reduce actions or split the scene.`,15);
  if(!out.length)add(out,"preflight.clean","info","No deterministic preflight risks detected.",null,0);
  return out;
}

function simulate(scene){ const d=Number(scene.duration_seconds||10), total=(scene.timeline||[]).reduce((s,e)=>s+Number(e.seconds||0),0), words=wordCount(scene.spoken?.arabic||""), speech=words/2.7, util=speech/d, rate=(scene.timeline||[]).length/d*10; let status="comfortable"; if(total>d+.05||util>1)status="overflow"; else if(util>.86||rate>6)status="tight"; return {duration:d,total,words,speech,util,events:(scene.timeline||[]).length,text:(scene.screen_text||[]).length,status}; }

function compile(scene){ const rules=scene.rules||{}, lines=[]; lines.push(`SCENE: ${scene.name||"Scene"}`); lines.push(`FORMAT: vertical ${scene.aspect_ratio||"9:16"}; exact duration ${scene.duration_seconds||10}s`); if(scene.style?.length)lines.push(`STYLE: ${scene.style.join("; ")}`); if(scene.spoken?.arabic)lines.push(`ARABIC AUDIO ONLY: "${scene.spoken.arabic}"`); if(rules.presenter_arabic_only)lines.push("PRESENTER AUDIO: Egyptian Arabic only; do not pronounce German."); if(scene.screen_text?.length)lines.push(`EXACT SCREEN TEXT ONLY: ${scene.screen_text.join(" | ")}`); if(scene.text_whitelist?.length)lines.push("TEXT WHITELIST IS STRICT; render no other words or subtitles."); if(scene.timeline?.length){let c=0;lines.push("TIMELINE: "+scene.timeline.map(e=>{const s=c;c+=Number(e.seconds||0);return `${s}-${c}s ${e.action}`}).join("; "));} const strict=[]; if(rules.no_arabic_on_screen)strict.push("no Arabic text on screen"); if(rules.no_auto_subtitles)strict.push("no automatic subtitles"); if(rules.no_background_music)strict.push("no background music"); if(rules.same_presenter)strict.push("same presenter identity, wardrobe, studio and lighting"); if(strict.length)lines.push(`STRICT: ${strict.join("; ")}.`); return lines.join("\n"); }

function render(optimize=false){ const text=input.value; const scene=parsePrompt(text); const fs=analyze(scene,text); const score=Math.min(100,fs.reduce((s,f)=>s+f.points,0)); const passed=!fs.some(f=>f.severity==="error"); const sim=simulate(scene); statusEl.textContent=passed?"PASS":"FAIL"; statusEl.className=passed?"pass":"fail"; riskEl.textContent=`Risk: ${score}/100`; simulationEl.textContent=`Simulation: ${sim.status}`; simulationEl.className=`pill ${sim.status==="comfortable"?"pass":sim.status==="tight"?"warn":"fail"}`; $("mDuration").textContent=`${sim.duration}s`; $("mSpeech").textContent=`${Math.round(sim.util*100)}%`; $("mEvents").textContent=String(sim.events); $("mText").textContent=String(sim.text); $("mTimeline").textContent=`${sim.total}/${sim.duration}s`; findingsEl.innerHTML=fs.map(f=>`<div class="finding ${f.severity==='error'?'fail':f.severity==='warning'?'warn':'pass'}"><strong>${f.severity.toUpperCase()} · ${f.rule_id}</strong><br>${f.message}${f.suggestion?`<br><small>→ ${f.suggestion}</small>`:''}</div>`).join(""); sceneEl.textContent=JSON.stringify(scene,null,2); compiledEl.textContent=optimize||passed?compile(scene):"Blocking errors found. Resolve them before generation, or press Optimize to inspect the constrained version."; }

$("analyzeBtn").addEventListener("click",()=>render(false));
$("optimizeBtn").addEventListener("click",()=>render(true));
$("sampleBtn").addEventListener("click",()=>{input.value=goodSample;render(false)});
$("badBtn").addEventListener("click",()=>{input.value=badSample;render(false)});
$("copyBtn").addEventListener("click",async()=>navigator.clipboard.writeText(compiledEl.textContent));
input.value=goodSample; render(false);
