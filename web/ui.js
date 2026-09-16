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
5-7s transform laufen into sich verlaufen
7-9s transform hören into sich verhören
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
Show, transform, animate, zoom, cut, switch, highlight, pause, transition and display every element quickly.`;
const $=id=>document.getElementById(id),A=window.VPP,input=$("promptInput"),findingsEl=$("findings"),compiledEl=$("compiledOutput"),sceneEl=$("sceneOutput"),roundsEl=$("rounds");
function failures(){try{return JSON.parse(localStorage.getItem("vpp_failures")||"[]")}catch{return[]}}
function drawFindings(fs){findingsEl.innerHTML=fs.map(f=>`<div class="finding ${f.severity==='error'?'fail':f.severity==='warning'?'warn':'info'}"><strong>${f.severity.toUpperCase()} · ${f.agent||'Verifier'} · ${f.rule_id}</strong><br>${f.message}${f.recommendation?`<br><small>Director note → ${f.recommendation}</small>`:''}${(f.sources||[]).map(s=>`<div class="source">Evidence: <a href="${s.url}" target="_blank" rel="noreferrer">${s.name}</a></div>`).join("")}</div>`).join("");}
function metrics(sim){$("mDuration").textContent=`${sim.duration}s`;$("mSpeech").textContent=`${Math.round(sim.util*100)}%`;$("mEvents").textContent=sim.events;$("mText").textContent=sim.text;$("mTimeline").textContent=`${sim.total}/${sim.duration}s`;$("simulation").textContent=`Scene Pace: ${sim.status}`;}
function fast(opt=false){const text=input.value,scene=A.parsePrompt(text),fs=A.analyze(scene,text),sim=A.simulate(scene),passed=!fs.some(f=>f.severity==="error"),risk=Math.min(100,fs.reduce((s,f)=>s+(f.points||0),0));$("status").textContent=passed?"GREEN LIGHT 🎬":"CUT! FIX FIRST ✋";$("status").className=passed?"pass":"fail";$("risk").textContent=`Deterministic Risk: ${risk}/100`;$("confidence").textContent="Confidence: fast-mode";metrics(sim);drawFindings(fs);sceneEl.textContent=JSON.stringify(scene,null,2);compiledEl.textContent=opt||passed?A.compile(scene):"Blocking errors found. Fix the take or run Director's Cut ×3.";roundsEl.innerHTML="<p>Quick Check finished. Press <strong>Director's Cut ×3</strong> for candidate comparison and evidence-backed review.</p>";}
function triple(){const res=A.tripleReview(input.value,$("provider").value,failures());$("status").textContent=res.passed?"GREEN LIGHT · 3× VERIFIED 🎬":"CUT! GATE BLOCKED ✋";$("status").className=res.passed?"pass":"fail";$("risk").textContent=`Review Score: ${res.score}/100`;$("confidence").textContent=`Confidence: ${res.confidence}`;metrics(res.sim);drawFindings(res.findings);sceneEl.textContent=JSON.stringify(res.scene,null,2);compiledEl.textContent=res.finalPrompt;roundsEl.innerHTML=res.rounds.map(r=>`<div class="round"><h3>Round ${r.round} · ${r.name}</h3>${r.winner?`<p class="pass">Director pick: <strong>${r.winner}</strong></p>`:""}${(r.candidates||[]).map(c=>`<div class="candidate"><strong>${c.name}</strong> · score ${c.score} · ~${c.tok} tokens · constraints ${c.coverage}%</div>`).join("")}${(r.findings||[]).map(f=>`<div class="finding ${f.severity==='error'?'fail':f.severity==='warning'?'warn':'info'}"><strong>${f.agent} · ${f.rule_id}</strong><br>${f.message}</div>`).join("")}${r.passed!==undefined?`<p class="${r.passed?'pass':'fail'}"><strong>${r.passed?'GATE PASS · SHOOT IT':'GATE FAIL · ONE MORE TAKE'}</strong> · score ${r.score}/100 · confidence ${r.confidence}</p>`:""}</div>`).join("");}
function drawMemory(){const a=failures();$("failureList").innerHTML=a.length?a.map((x,i)=>`<div class="finding"><strong>💥 ${x.category}</strong><br><small>Observed:</small> ${x.observed}<br><small>Expected:</small> ${x.expected} <button class="secondary" onclick="deleteFailure(${i})">Delete</button></div>`).join(""):"<p>No bloopers saved yet. Your first bad take gets a starring role here. 🍿</p>";}
window.deleteFailure=i=>{const a=failures();a.splice(i,1);localStorage.setItem("vpp_failures",JSON.stringify(a));drawMemory();};
$("saveFailureBtn").onclick=()=>{const category=$("failureCategory").value.trim(),observed=$("failureObserved").value.trim(),expected=$("failureExpected").value.trim();if(!category||!observed||!expected)return;const a=failures();a.push({category,observed,expected,created_at:new Date().toISOString()});localStorage.setItem("vpp_failures",JSON.stringify(a));$("failureCategory").value=$("failureObserved").value=$("failureExpected").value="";drawMemory();};
$("analyzeBtn").onclick=()=>fast(false);$("optimizeBtn").onclick=()=>fast(true);$("tripleBtn").onclick=triple;$("sampleBtn").onclick=()=>{input.value=goodSample;fast(false)};$("badBtn").onclick=()=>{input.value=badSample;fast(false)};
$("copyBtn").onclick=async()=>{await navigator.clipboard.writeText(compiledEl.textContent);const b=$("copyBtn"),old=b.textContent;b.textContent="Copied · action! 🎬";setTimeout(()=>b.textContent=old,1400);};
input.value=goodSample;fast(false);drawMemory();
