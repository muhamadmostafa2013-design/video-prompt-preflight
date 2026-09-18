const goodSample=`Create a 10-second vertical cinematic educational video. Vertical 9:16.
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
5-7s show laufen as static text, hold clearly, hard cut, then show sich verlaufen as static text
7-9s show hören as static text, hold clearly, hard cut, then show sich verhören as static text
9-10s hold ver- centered`;

const badSample=`Create a 10 second vertical video, but make the scene 12 seconds long.
No background music. Add subtle background music.
No automatic subtitles, but generate subtitles for every spoken sentence.
The presenter speaks Egyptian Arabic only and must not pronounce German.
The presenter should pronounce laufen and sich verlaufen clearly in German.
ON SCREEN:
ver-
يتوه وهو ماشي
laufen
sich verlaufen
TIMELINE:
0-3s presenter hook
3-5s show ver-
5-8s transform laufen into sich verlaufen
8-10s animate and scramble the letters quickly.
Show, transform, animate, zoom, cut, switch, highlight, pause, transition and display every element quickly.`;

const $=id=>document.getElementById(id),
  A=window.VPP,
  input=$("promptInput"),
  findingsEl=$("findings"),
  compiledEl=$("compiledOutput"),
  sceneEl=$("sceneOutput"),
  roundsEl=$("rounds"),
  summaryEl=$("summaryLine");

const providerOptions=[
  ["generic","Generic / cross-platform"],
  ["gemini_omni","Gemini Apps · Omni"],
  ["veo","Google Veo 3.1 · Flow/API"],
  ["runway","Runway Gen-4.5"],
  ["firefly","Adobe Firefly Video"],
  ["luma","Luma Ray 3.2"],
  ["kling","Kling VIDEO 3.0"],
  ["wan","Alibaba Wan"],
  ["pixverse","PixVerse 5.6"],
  ["minimax","MiniMax / Hailuo"],
  ["higgsfield","Higgsfield"],
  ["pika","Pika 2.5"],
  ["seedance","ByteDance Seedance 2.5"],
  ["midjourney","Midjourney Video"],
  ["grok","Grok Imagine Video 1.5"],
  ["vidu","Vidu Q3"],
  ["dreamina","Dreamina / CapCut AI Video"],
  ["canva","Canva AI Video"],
  ["sora_legacy","Sora 2 API · legacy/sunset"]
];

function setupProviders(){
  const select=$("provider");
  select.innerHTML=providerOptions.map(([value,label])=>`<option value="${value}">${label}</option>`).join("");
  select.value="gemini_omni";
}

function loadScript(src){
  return new Promise(resolve=>{
    const existing=[...document.scripts].some(s=>s.src&&s.src.endsWith(src));
    if(existing){resolve();return;}
    const script=document.createElement("script");
    script.src=src;
    script.onload=resolve;
    script.onerror=()=>resolve();
    document.head.appendChild(script);
  });
}

const constitutionReady=(async()=>{
  if(!A.constitutionReview) await loadScript("constitution.js");
  await loadScript("constitution-extra.js");
})();

function failures(){
  try{return JSON.parse(localStorage.getItem("vpp_failures")||"[]")}
  catch{return[]}
}

function tierLabel(f){
  const tier=f.evidence_tier;
  if(!tier)return "";
  const labels={A:"Official",B:"Cross-platform / regression",C:"Community empirical",D:"Hypothesis"};
  return ` · ${labels[tier]||tier}`;
}

function drawFindings(fs){
  findingsEl.innerHTML=fs.map(f=>
    `<div class="finding ${f.severity==='error'?'fail':f.severity==='warning'?'warn':'info'}">
      <strong>${f.severity.toUpperCase()} · ${f.agent||'Verifier'} · ${f.rule_id}${tierLabel(f)}</strong><br>
      ${f.message}
      ${f.recommendation?`<br><small>Director note → ${f.recommendation}</small>`:''}
      ${(f.sources||[]).map(s=>`<div class="source">Evidence: <a href="${s.url}" target="_blank" rel="noreferrer">${s.name}</a></div>`).join("")}
    </div>`
  ).join("");
}

function metrics(sim){
  $("mDuration").textContent=`${sim.duration}s`;
  $("mSpeech").textContent=`${Math.round(sim.util*100)}%`;
  $("mEvents").textContent=sim.events;
  $("mText").textContent=sim.text;
  $("mTimeline").textContent=`${sim.total}/${sim.duration}s`;
  $("simulation").textContent=`Scene Pace: ${sim.status}`;
}

function verdictCopy(passed,fs,triple=false){
  const errors=fs.filter(f=>f.severity==='error').length;
  const warns=fs.filter(f=>f.severity==='warning').length;
  const morph=fs.some(f=>/morph|text_transition/.test(f.rule_id));
  if(morph)return "The spelling is fine on paper, but the text transition is asking for trouble. Use static states + hard cuts. 🔤✂️";
  if(passed&&triple&&warns===0)return "Three passes, no blocking issues. The crew can stop arguing now. 🎬";
  if(passed&&warns)return `Shootable, with ${warns} evidence-backed director note${warns>1?'s':''}. 🍿`;
  if(passed)return "Looks shoot-ready. No preventable prompt bloopers found. 🍿";
  return `${errors||fs.length} blocking issue${(errors||fs.length)!==1?'s':''} found. One more take before you spend a credit. ✋`;
}

function fast(opt=false){
  const text=input.value;
  const scene=A.parsePrompt(text);
  const fs=A.analyze(scene,text);
  const sim=A.simulate(scene);
  const passed=!fs.some(f=>f.severity==="error");
  const risk=Math.min(100,fs.reduce((s,f)=>s+(f.points||0),0));

  $("status").textContent=passed?"GREEN LIGHT 🎬":"CUT! FIX FIRST ✋";
  $("status").className=passed?"pass":"fail";
  $("risk").textContent=`Deterministic Risk: ${risk}/100`;
  $("confidence").textContent="Confidence: fast-mode";
  summaryEl.textContent=verdictCopy(passed,fs,false);
  metrics(sim);
  drawFindings(fs);
  sceneEl.textContent=JSON.stringify(scene,null,2);
  compiledEl.textContent=opt||passed?A.compile(scene):"Blocking errors found. Fix the take or run Director's Cut ×3.";
  roundsEl.innerHTML="<p>Quick Check finished. Press <strong>Director's Cut ×3</strong> for provider-specific, evidence-backed review.</p>";
}

function mergeConstitution(res,provider){
  if(typeof A.constitutionReview!=="function") return res;
  const extra=A.constitutionReview(input.value,res.scene,provider)||[];
  const existing=new Set((res.findings||[]).map(f=>`${f.rule_id}|${f.provider_scope||''}`));
  const added=extra.filter(f=>!existing.has(`${f.rule_id}|${f.provider_scope||''}`));
  if(!added.length)return res;

  res.findings=[...(res.findings||[]),...added];
  if(res.rounds?.[1]) res.rounds[1].findings=[...(res.rounds[1].findings||[]),...added];

  const penalty=added.reduce((sum,f)=>sum+Number(f.points||0),0);
  res.score=Math.max(0,Number(res.score||0)-penalty);
  if(added.some(f=>f.severity==="error")){
    res.passed=false;
    res.confidence="low";
    if(res.rounds?.[2]){res.rounds[2].passed=false;res.rounds[2].score=res.score;res.rounds[2].confidence="low";}
  }else if(added.some(f=>f.severity==="warning")&&res.confidence==="high"){
    res.confidence="medium";
    if(res.rounds?.[2]){res.rounds[2].score=res.score;res.rounds[2].confidence="medium";}
  }else if(res.rounds?.[2]) res.rounds[2].score=res.score;
  return res;
}

async function triple(){
  await constitutionReady;
  const provider=$("provider").value;
  let res=A.tripleReview(input.value,provider,failures());
  res=mergeConstitution(res,provider);

  $("status").textContent=res.passed?"GREEN LIGHT · 3× VERIFIED 🎬":"CUT! GATE BLOCKED ✋";
  $("status").className=res.passed?"pass":"fail";
  $("risk").textContent=`Review Score: ${res.score}/100`;
  $("confidence").textContent=`Confidence: ${res.confidence}`;
  summaryEl.textContent=verdictCopy(res.passed,res.findings,true);
  metrics(res.sim);
  drawFindings(res.findings);
  sceneEl.textContent=JSON.stringify(res.scene,null,2);
  compiledEl.textContent=res.finalPrompt;

  roundsEl.innerHTML=res.rounds.map(r=>
    `<div class="round">
      <h3>Round ${r.round} · ${r.name}</h3>
      ${r.winner?`<p class="pass">Director pick: <strong>${r.winner}</strong></p>`:""}
      ${(r.candidates||[]).map(c=>`<div class="candidate"><strong>${c.name}</strong> · score ${c.score} · ~${c.tok} tokens · constraints ${c.coverage}%</div>`).join("")}
      ${(r.findings||[]).map(f=>`<div class="finding ${f.severity==='error'?'fail':f.severity==='warning'?'warn':'info'}"><strong>${f.agent} · ${f.rule_id}${tierLabel(f)}</strong><br>${f.message}</div>`).join("")}
      ${r.passed!==undefined?`<p class="${r.passed?'pass':'fail'}"><strong>${r.passed?'GATE PASS · SHOOT IT':'GATE FAIL · ONE MORE TAKE'}</strong> · score ${r.score}/100 · confidence ${r.confidence}</p>`:""}
    </div>`
  ).join("");
}

function drawMemory(){
  const a=failures();
  $("failureList").innerHTML=a.length?a.map((x,i)=>
    `<div class="finding">
      <strong>💥 ${x.category}</strong><br>
      <small>Observed:</small> ${x.observed}<br>
      <small>Expected:</small> ${x.expected}
      <button class="secondary" onclick="deleteFailure(${i})">Delete</button>
    </div>`
  ).join(""):"<p>No bloopers saved yet. Your first bad take gets a starring role here. 🍿</p>";
}

window.deleteFailure=i=>{
  const a=failures();
  a.splice(i,1);
  localStorage.setItem("vpp_failures",JSON.stringify(a));
  drawMemory();
};

$("saveFailureBtn").onclick=()=>{
  const category=$("failureCategory").value.trim(),
    observed=$("failureObserved").value.trim(),
    expected=$("failureExpected").value.trim();
  if(!category||!observed||!expected)return;
  const a=failures();
  a.push({category,observed,expected,created_at:new Date().toISOString(),source:"manual"});
  localStorage.setItem("vpp_failures",JSON.stringify(a));
  $("failureCategory").value=$("failureObserved").value=$("failureExpected").value="";
  drawMemory();
};

setupProviders();
$("analyzeBtn").onclick=()=>fast(false);
$("optimizeBtn").onclick=()=>fast(true);
$("tripleBtn").onclick=triple;
$("sampleBtn").onclick=()=>{input.value=goodSample;fast(false)};
$("badBtn").onclick=()=>{input.value=badSample;fast(false)};

$("copyBtn").onclick=async()=>{
  await navigator.clipboard.writeText(compiledEl.textContent);
  const b=$("copyBtn"),old=b.textContent;
  b.textContent="Copied · action! 🎬";
  setTimeout(()=>b.textContent=old,1400);
};

input.value=goodSample;
fast(false);
drawMemory();

window.VPPOutputQA?.bind({
  getScene:()=>A.parsePrompt(input.value),
  onMemoryChanged:drawMemory
});
