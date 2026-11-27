"use strict";
const Studio = (() => {
  const MAX_TEXT = 4 * 1024 * 1024;
  const MAX_VIDEO = 256 * 1024 * 1024;
  function ms(stamp) {
    const m = /^(\d{2}):([0-5]\d):([0-5]\d),(\d{3})$/.exec(stamp);
    if (!m) throw Error("Invalid SRT timestamp.");
    return ((Number(m[1])*60+Number(m[2]))*60+Number(m[3]))*1000+Number(m[4]);
  }
  function stamp(n) {
    const p = (v,k=2) => String(v).padStart(k,"0");
    return p(Math.floor(n/3600000))+":"+p(Math.floor(n/60000)%60)+":"+p(Math.floor(n/1000)%60)+","+p(n%1000,3);
  }
  function validate(cues, duration=Infinity) {
    if (!Array.isArray(cues) || !cues.length || cues.length > 2000) throw Error("Expected 1–2000 captions.");
    let end=0;
    for (const c of cues) {
      if (!Number.isSafeInteger(c.start) || !Number.isSafeInteger(c.end) || c.start<end || c.end<=c.start || c.end>duration || c.end>=360000000)
        throw Error("Caption intervals must be ordered, non-overlapping and inside the video.");
      if (!Array.isArray(c.lines) || !c.lines.length || c.lines.some(l=>typeof l!=="string" || !l.trim() || /[<>\x00\r\n]/.test(l)))
        throw Error("Plain nonempty caption text required.");
      end=c.end;
    }
    return cues;
  }
  function parse(text) {
    if (typeof text!=="string" || text.length>MAX_TEXT) throw Error("SRT too large.");
    const clean=text.replace(/^\uFEFF/,"").replace(/\r\n?/g,"\n").trim();
    const cues=clean.split(/\n[ \t]*\n+/).map((block,i)=>{
      const [number,timing,...lines]=block.split("\n");
      const m=/^(\d{2}:[0-5]\d:[0-5]\d,\d{3}) --> (\d{2}:[0-5]\d:[0-5]\d,\d{3})$/.exec((timing||"").trim());
      if (number.trim()!==String(i+1) || !m) throw Error("Invalid SRT cue "+(i+1));
      return {index:i+1,start:ms(m[1]),end:ms(m[2]),lines};
    });
    // Original captions may overlap or exceed the media: open for manual review,
    // but validate the full edited draft before any export.
    if (cues.length>2000 || cues.some(c=>c.end<=c.start || !c.lines.length ||
        c.lines.some(l=>!l.trim() || /[<>\x00]/.test(l)))) throw Error("Invalid plain SRT captions.");
    return cues;
  }
  function serialize(cues,duration) {
    validate(cues,duration);
    return cues.map((c,i)=>[i+1,stamp(c.start)+" --> "+stamp(c.end),...c.lines].join("\n")).join("\n\n")+"\n";
  }
  function draftIssues(cues,duration) {
    const issues=new Map();
    const flag=(cue,reason)=>{if(!issues.has(cue))issues.set(cue,new Set());issues.get(cue).add(reason);};
    let furthest=null;
    for(const c of cues){
      if(!Number.isSafeInteger(c.start)||!Number.isSafeInteger(c.end)||c.start<0||c.end<=c.start)
        flag(c.index,"invalid interval");
      if(Number.isFinite(duration)&&c.end>duration)flag(c.index,"outside video");
      if(furthest&&c.start<furthest.end){flag(c.index,"overlap or out of order");flag(furthest.index,"overlap or out of order");}
      if(!furthest||c.end>furthest.end)furthest=c;
    }
    return issues;
  }
  function candidateDelta(cue,row,duration){
    if(!cue||!row||!["within_tolerance","drift_candidate"].includes(row.status))return null;
    const a=row.acoustic_start_ms,b=row.acoustic_end_ms;
    if(!Number.isSafeInteger(a)||!Number.isSafeInteger(b)||a<0||b<=a||
      !Number.isFinite(duration)||b>duration)return null;
    return {onset:cue.start-a,offset:cue.end-b};
  }
  function active(cues,time) { return cues.filter(c=>c.start<=time && time<c.end); }
  const plain = value => value!==null && typeof value==="object" && !Array.isArray(value);
  const scalar = value => typeof value==="string" || typeof value==="number";
  const statuses = new Set(["within_tolerance","drift_candidate","incomplete_acoustic_evidence",
    "noncontiguous_acoustic_evidence","screen_out_of_range"]);
  function validTrack(e) {
    if (!plain(e) || !Array.isArray(e.cue_drift) || e.cue_drift.length>2000 ||
        !Array.isArray(e.rows) || e.rows.length>2000) return false;
    const seen=new Set();
    for(const r of e.cue_drift){
      if(!plain(r)||!Number.isSafeInteger(r.cue)||r.cue<1||r.cue>2000||
         seen.has(r.cue)||!statuses.has(r.status))return false;
      seen.add(r.cue);
      if(r.acoustic_start_ms!=null&&(!Number.isSafeInteger(r.acoustic_start_ms)||r.acoustic_start_ms<0))return false;
      if(r.onset_error_ms!=null&&!Number.isSafeInteger(r.onset_error_ms))return false;
    }
    return e.rows.every(r=>plain(r)&&seen.has(r.cue)&&typeof r.expected==="string"&&
      (r.heard_candidate==null||typeof r.heard_candidate==="string")&&typeof r.status==="string"&&
      (r.start==null||Number.isFinite(r.start))&&(r.end==null||Number.isFinite(r.end)));
  }
  function tracks(report, videoHash, srtHash) {
    if (!videoHash || !srtHash || !plain(report)) return [];
    const candidates=Array.isArray(report.cue_drift)?[["acoustic-review",report]]:
      Object.entries(plain(report.stages)?report.stages:{}).filter(([k,v])=>k.startsWith("acoustic_drift_")&&v?.status==="completed").map(([k,v])=>[k,v.evidence]);
    return candidates.filter(([,e])=>e?.audio_sha256===videoHash&&e.reference_srt_sha256===srtHash&&validTrack(e))
      .map(([key,e])=>({key,e}));
  }
  function visual(report,videoHash) {
    if (!videoHash) return [];
    return Object.entries(report?.stages||{}).filter(([,v])=>v?.status==="completed"&&v.evidence?.video_sha256===videoHash)
      .map(([key,v])=>({key,evidence:v.evidence}));
  }
  function waveformEvidence(report,videoHash,durationMs) {
    const stage=report?.stages?.waveform;
    const e=stage?.evidence;
    if(stage?.status!=="completed"||!videoHash||e?.video_sha256!==videoHash||
       !Number.isFinite(durationMs)||!Number.isFinite(e.duration_seconds)||
       Math.abs(e.duration_seconds*1000-durationMs)>150||
       !Array.isArray(e.peaks)||e.peaks.length<1||e.peaks.length>2400||
       !e.peaks.every(p=>Number.isFinite(p)&&p>=0&&p<=1))return null;
    return e;
  }
  async function hash(file,limit) {
    if (file.size>limit) throw Error("File exceeds local hashing limit.");
    if (!globalThis.crypto?.subtle) throw Error("SHA-256 requires a secure localhost or HTTPS context.");
    const bytes=await globalThis.crypto.subtle.digest("SHA-256",await file.arrayBuffer());
    return Array.from(new Uint8Array(bytes),b=>b.toString(16).padStart(2,"0")).join("");
  }
  return {parse,serialize,validate,active,tracks,visual,hash,scalar,draftIssues,candidateDelta,waveformEvidence,MAX_TEXT,MAX_VIDEO};
})();
if (typeof module!=="undefined") module.exports=Studio;
if (typeof document!=="undefined") {
  const $=id=>document.getElementById(id);
  const video=$("video");
  let original=[],draft=[],report=null,videoHash=null,srtHash=null,objectUrl=null,selected=null,available=[],generation=0;
  let mediaLoaded=false, loadedVideo=null, loadedSrt=null;
  const notice=message=>{$("status").textContent=message;};
  const duration=()=>mediaLoaded&&Number.isFinite(video.duration)?Math.floor(video.duration*1000):null;
  function currentTrack(){return available.find(t=>t.key===$("track").value)?.e;}
  function rowFor(index){return currentTrack()?.cue_drift.find(r=>r?.cue===index);}
  function edited(c){const base=original.find(x=>x.index===c.index);return !!base&&(c.start!==base.start||c.end!==base.end);}
  function seek(ms){if (duration()!==null&&Number.isFinite(ms)&&ms>=0&&ms<=duration()) video.currentTime=ms/1000;}
  function refreshButtons(){
    const c=draft.find(x=>x.index===selected), r=rowFor(selected);
    $("saveTiming").disabled=!c||duration()===null;
    $("setStart").disabled=!c||duration()===null;
    $("setEnd").disabled=!c||duration()===null;
    $("timeline").disabled=duration()===null;
    $("timeline").max=duration()===null?1:duration();
    $("seekAudio").disabled=!r||!Number.isFinite(r.acoustic_start_ms)||duration()===null||r.acoustic_start_ms<0||r.acoustic_start_ms>duration();
    $("reset").disabled=!draft.length;
    let valid=false;
    try{if(duration()!==null){Studio.validate(draft,duration());valid=true;}}catch{}
    $("export").disabled=!valid||!$("ack").checked;
    const issues=Studio.draftIssues(draft,duration());
    $("draftSummary").textContent=draft.length+" cues · "+draft.filter(edited).length+" edited · "+issues.size+" invalid / conflicting. "+(valid?"Timing structurally valid (not acoustic approval).":"Export unavailable until intervals and video are valid.");
  }
  function drawWave(){
    const canvas=$("waveform"),ctx=canvas.getContext("2d");
    const e=Studio.waveformEvidence(report,videoHash,duration());
    const w=canvas.width,h=canvas.height;
    ctx.clearRect(0,0,w,h);
    if(!e){$("waveStatus").textContent="No source-bound decoded waveform.";return;}
    $("waveStatus").textContent="Actual mono audio peaks · click to seek · not phoneme evidence";
    ctx.fillStyle="#82afe7";
    for(let x=0;x<w;x++){
      const p=e.peaks[Math.floor(x*e.peaks.length/w)];
      ctx.fillRect(x,(h-h*p)/2,1,Math.max(1,h*p));
    }
    ctx.fillStyle="#ffcf87";
    ctx.fillRect(Math.min(w-2,Math.max(0,video.currentTime*1000/duration()*w)),0,2,h);
  }
  function drawActive(){
    drawWave();
    const now=Math.max(0,Math.round(video.currentTime*1000));
    $("timeline").value=String(now);
    $("playbackTime").textContent=now+" ms / "+(duration()===null?"—":duration()+" ms");
    const playing=Studio.active(draft,video.currentTime*1000);
    $("caption").textContent=playing.map(c=>c.lines.join("\n")).join("\n\n");
    for(const el of $("captionList").children) el.setAttribute("aria-current",String(playing.some(c=>String(c.index)===el.dataset.cue)));
  }
  function drawSelection(){
    const c=draft.find(x=>x.index===selected);
    $("selected").textContent=c?c.lines.join(" / "):"Select a cue to seek to its screen time.";
    $("start").value=c?c.start:"";$("end").value=c?c.end:"";
    const words=currentTrack()?.rows.filter(r=>r?.cue===selected)||[];
    $("words").textContent=words.length?words.map(r=>[r.expected,r.heard_candidate||"—",Number.isFinite(r.start)?r.start+"–"+r.end+" s":"no timing",r.status].join(" | ")).join("\n"):"No bound word evidence for this cue.";
    const delta=Studio.candidateDelta(c,rowFor(selected),duration());
    const sign=n=>(n>0?"+":"")+n+" ms";
    $("cueTiming").textContent=delta?"Current draft vs original acoustic candidate: onset "+sign(delta.onset)+" · end "+sign(delta.offset)+" (not revalidated).":"Current draft: no complete in-range acoustic candidate.";
    refreshButtons();
  }
  function drawList(){
    $("captionList").replaceChildren();
    const issues=Studio.draftIssues(draft,duration());
    for(const c of draft){
      const r=rowFor(c.index);
      if($("issuesOnly").checked&&r?.status==="within_tolerance"&&!edited(c)&&!issues.has(c.index))continue;
      const b=document.createElement("button");b.className="cue";b.dataset.cue=String(c.index);
      const signed=r&&Number.isFinite(r.onset_error_ms)?(r.onset_error_ms>0?"+":"")+r.onset_error_ms+" ms":"—";
      b.textContent=c.index+" · "+c.start+"–"+c.end+" ms · "+(edited(c)?"EDITED · ":"")+"Original evidence: "+(r?.status||"unmeasured")+" · "+signed+(issues.has(c.index)?" · INVALID: "+[...issues.get(c.index)].join(", "):"")+"\n"+c.lines.join("\n");
      b.addEventListener("click",()=>{selected=c.index;seek(c.start);drawSelection();});
      $("captionList").appendChild(b);
    }
    drawActive();drawSelection();
  }
  function bindReport(){
    available=Studio.tracks(report,videoHash,srtHash);
    $("track").replaceChildren();
    const none=document.createElement("option");none.value="";none.textContent="No track selected";$("track").appendChild(none);
    for(const t of available){const o=document.createElement("option");o.value=t.key;o.textContent=t.key+" · "+(Studio.scalar(t.e.model)?String(t.e.model):"model not declared");$("track").appendChild(o);}
    if(available.length)$("track").value=available[0].key;
    $("visual").replaceChildren();
    const evidence=Studio.visual(report,videoHash);
    for(const stage of evidence){
      const h=document.createElement("h3");h.textContent=stage.key;$("visual").appendChild(h);
      const pre=document.createElement("pre");pre.textContent=JSON.stringify(stage.evidence,null,2).slice(0,50000);$("visual").appendChild(pre);
      const rows=stage.evidence.rows||stage.evidence.samples;
      if(Array.isArray(rows))for(const r of rows.slice(0,600)){
        if(!Number.isFinite(r?.seconds)||r.seconds<0)continue;
        const b=document.createElement("button");b.textContent="Inspect "+r.seconds+" s";b.addEventListener("click",()=>seek(r.seconds*1000));$("visual").appendChild(b);
      }
    }
    if(!evidence.length)$("visual").textContent="No hash-bound visual evidence. Inspect the video manually.";
    notice(report?available.length+" source-bound acoustic track(s). Exact byte hashes do not establish model correctness. Reports for a different audio file are not linked.":"Local manual review; no report loaded.");
    drawList();
  }
  async function load(){
    const ticket=++generation;
    const vf=$("videoFile").files[0]||null, sf=$("srtFile").files[0]||null, rf=$("reportFile").files[0]||null;
    const sameSources=vf===loadedVideo&&sf===loadedSrt&&(!!objectUrl||original.length>0);
    $("ack").checked=false;
    report=null;videoHash=null;srtHash=null;
    if(!sameSources){
      mediaLoaded=false;video.pause();video.removeAttribute("src");video.load();
      if(objectUrl)URL.revokeObjectURL(objectUrl);objectUrl=null;
      original=[];draft=[];selected=null;loadedVideo=null;loadedSrt=null;
    }
    bindReport();notice("Opening local files…");
    try{
      if(sf&&sf.size>Studio.MAX_TEXT)throw Error("SRT file exceeds 4 MiB.");
      const captions=sameSources?original:(sf?Studio.parse(await sf.text()):[]);
      let data=null,vh=null,sh=null,warning="";
      if(rf){
        try{
          if(rf.size>Studio.MAX_TEXT)throw Error("JSON report exceeds 4 MiB.");
          data=JSON.parse(await rf.text());
          if(!data||typeof data!=="object"||Array.isArray(data))throw Error("Expected a JSON report object.");
          if(vf)vh=await Studio.hash(vf,Studio.MAX_VIDEO);
          if(sf)sh=await Studio.hash(sf,Studio.MAX_TEXT);
        }catch(err){data=null;vh=null;sh=null;warning=" Report ignored: "+err.message;}
      }
      if(ticket!==generation)return;
      if(!sameSources){
        original=captions;draft=captions.map(c=>({...c,lines:[...c.lines]}));
        if(vf){objectUrl=URL.createObjectURL(vf);video.src=objectUrl;}
        loadedVideo=vf;loadedSrt=sf;
      }
      report=data;videoHash=vh;srtHash=sh;bindReport();
      if(warning)notice($("status").textContent+warning);
    }catch(err){if(ticket===generation)notice("Cannot open files: "+err.message);}
  }
  for(const id of ["videoFile","srtFile","reportFile"])$(id).addEventListener("change",load);
  $("track").addEventListener("change",drawList);$("issuesOnly").addEventListener("change",drawList);
  video.addEventListener("loadedmetadata",()=>{mediaLoaded=!!objectUrl&&video.currentSrc===objectUrl;drawList();});
  video.addEventListener("error",()=>{mediaLoaded=false;refreshButtons();notice("Video cannot be played by this browser.");});
  video.addEventListener("timeupdate",drawActive);
  $("ack").addEventListener("change",refreshButtons);
  $("timeline").addEventListener("input",()=>seek($("timeline").valueAsNumber));
  $("waveform").addEventListener("click",event=>{
    if(!Studio.waveformEvidence(report,videoHash,duration()))return;
    const rect=$("waveform").getBoundingClientRect();
    seek(Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width))*duration());
  });
  $("setStart").addEventListener("click",()=>{$("start").value=String(Math.round(video.currentTime*1000));});
  $("setEnd").addEventListener("click",()=>{$("end").value=String(Math.round(video.currentTime*1000));});
  $("seekAudio").addEventListener("click",()=>seek(rowFor(selected)?.acoustic_start_ms));
  $("saveTiming").addEventListener("click",()=>{
    const c=draft.find(x=>x.index===selected),start=$("start").valueAsNumber,end=$("end").valueAsNumber;
    if(!c||duration()===null||!Number.isSafeInteger(start)||!Number.isSafeInteger(end)||start<0||start>=end||end>duration()){notice("Invalid manual interval.");return;}
    c.start=start;c.end=end;$("ack").checked=false;drawList();notice("Manual timing saved in memory. Resolve all overlaps before export; original evidence is unchanged.");
  });
  $("reset").addEventListener("click",()=>{draft=original.map(c=>({...c,lines:[...c.lines]}));$("ack").checked=false;drawList();notice("Original subtitle timing restored.");});
  $("export").addEventListener("click",()=>{
    try{if(!$("ack").checked||duration()===null)throw Error("Review acknowledgement and playable video required.");
      const srt=Studio.serialize(draft,duration());const url=URL.createObjectURL(new Blob([srt],{type:"text/plain;charset=utf-8"}));
      const a=document.createElement("a");a.href=url;a.download="REVIEW_ONLY.srt";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      notice("Review-only SRT draft exported; not publication approval.");
    }catch(err){notice(err.message);}
  });
  window.addEventListener("pagehide",event=>{if(!event.persisted&&objectUrl)URL.revokeObjectURL(objectUrl);});
  refreshButtons();
}
