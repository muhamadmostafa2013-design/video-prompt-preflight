const { test, expect } = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const {parse, serialize, tracks, active} = require("../web/quality-studio.js");
const videoPath=path.join(__dirname,"e2e.webm");
const srt="1\n00:00:00,100 --> 00:00:00,700\nEin Nomen\nاسم\n\n2\n00:00:00,800 --> 00:00:01,500\nein Verb\nفعل\n";
const sha=x=>crypto.createHash("sha256").update(x).digest("hex");
function report(videoHash,srtHash){
  return {stages:{acoustic_drift_1:{status:"completed",evidence:{
    audio_sha256:videoHash,reference_srt_sha256:srtHash,model:"Fixture only",
    cue_drift:[{cue:1,status:"drift_candidate",onset_error_ms:200,acoustic_start_ms:300},
      {cue:2,status:"within_tolerance",onset_error_ms:0}],
    rows:[{cue:1,expected:"Ein",heard_candidate:"ein",start:.3,end:.4,status:"candidate_match"}]
  }},rendered_caption_ocr:{status:"completed",evidence:{video_sha256:videoHash,
    rows:[{seconds:.4,expected:"Ein Nomen"}]}}}};
}
test("pure subtitle and evidence guards",()=>{
  const cues=parse(srt);
  expect(serialize(cues,2000)).toBe(srt);
  expect(active(cues,700)).toEqual([]);
  expect(()=>serialize([{...cues[0],end:900},cues[1]],2000)).toThrow();
  expect(()=>serialize(cues,1000)).toThrow();
  expect(()=>parse(srt.replace("Ein Nomen","<script>bad</script>"))).toThrow();
  expect(tracks(report("a","b"),"wrong","b")).toEqual([]);
  expect(tracks(report("a","b"),"a","wrong")).toEqual([]);
  expect(tracks(report("a","b"),"a","b")).toHaveLength(1);
  const invalid=report("a","b");
  invalid.stages.acoustic_drift_1.evidence.cue_drift.push({cue:1,status:"within_tolerance"});
  expect(tracks(invalid,"a","b")).toEqual([]);
  const malformed=report("a","b");
  malformed.stages.acoustic_drift_1.evidence.rows[0].expected={toString: null};
  expect(tracks(malformed,"a","b")).toEqual([]);
});
test("local playback, bound evidence, manual draft and invalid edit",async({page})=>{
  const errors=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto("/quality-studio.html");
  await page.locator("#videoFile").setInputFiles(videoPath);
  await page.locator("#srtFile").setInputFiles({name:"source.srt",mimeType:"text/plain",buffer:Buffer.from(srt)});
  await page.locator("#reportFile").setInputFiles({name:"report.json",mimeType:"application/json",
    buffer:Buffer.from(JSON.stringify(report(sha(fs.readFileSync(videoPath)),sha(srt))))});
  await expect(page.locator("#status")).toContainText("1 source-bound");
  await expect(page.locator("#captionList button")).toHaveCount(2);
  await expect(page.locator("#visual")).toContainText("rendered_caption_ocr");
  await page.locator("#captionList button").first().click();
  await expect(page.locator("#words")).toContainText("candidate_match");
  await expect(page.locator("#saveTiming")).toBeEnabled();
  await page.locator("#seekAudio").click();
  await expect.poll(()=>page.locator("#video").evaluate(v=>v.currentTime)).toBeCloseTo(.3,1);
  await page.locator("#issuesOnly").check();
  await expect(page.locator("#captionList button")).toHaveCount(1);
  await page.locator("#start").fill("200");
  await page.locator("#end").fill("950");
  await page.locator("#saveTiming").click();
  await page.locator("#ack").check();
  await expect(page.locator("#export")).toBeDisabled();
  await page.locator("#end").fill("700");
  await page.locator("#saveTiming").click();
  await expect(page.locator("#ack")).not.toBeChecked();
  await page.locator("#ack").check();
  const downloaded=page.waitForEvent("download");
  await page.locator("#export").click();
  const d=await downloaded;
  expect(d.suggestedFilename()).toBe("REVIEW_ONLY.srt");
  const result=fs.readFileSync(await d.path(),"utf8");
  expect(result).toBe(srt.replace("00:00:00,100","00:00:00,200"));
  await page.locator("#reset").click();
  await expect(page.locator("#export")).toBeDisabled();
  expect(errors).toEqual([]);
});
test("mismatched evidence is not linked; narrow viewport remains usable",async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto("/quality-studio.html");
  await page.locator("#videoFile").setInputFiles(videoPath);
  await page.locator("#srtFile").setInputFiles({name:"source.srt",mimeType:"text/plain",buffer:Buffer.from(srt)});
  await page.locator("#reportFile").setInputFiles({name:"wrong.json",mimeType:"application/json",
    buffer:Buffer.from(JSON.stringify(report("wrong",sha(srt))))});
  await expect(page.locator("#status")).toContainText("0 source-bound");
  await expect(page.locator("#track option")).toHaveCount(1);
  await expect(page.locator("#visual")).toContainText("No hash-bound");
  await page.locator("#captionList button").first().click();
  await expect(page.locator("#seekAudio")).toBeDisabled();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
});


test("invalid optional report preserves manual draft and playable video",async({page})=>{
  const errors=[];page.on("pageerror",e=>errors.push(e.message));
  await page.goto("/quality-studio.html");
  await page.locator("#videoFile").setInputFiles(videoPath);
  await page.locator("#srtFile").setInputFiles({name:"source.srt",mimeType:"text/plain",buffer:Buffer.from(srt)});
  await expect(page.locator("#captionList button")).toHaveCount(2);
  await page.locator("#captionList button").first().click();
  await expect(page.locator("#saveTiming")).toBeEnabled();
  await page.locator("#start").fill("250");
  await page.locator("#saveTiming").click();
  await expect(page.locator("#captionList button").first()).toContainText("EDITED");
  await page.locator("#reportFile").setInputFiles({name:"broken.json",mimeType:"application/json",buffer:Buffer.from("{")});
  await expect(page.locator("#status")).toContainText("Report ignored");
  await expect(page.locator("#captionList button").first()).toContainText("250–700");
  await expect(page.locator("#saveTiming")).toBeEnabled();
  await page.locator("#ack").check();
  await expect(page.locator("#export")).toBeEnabled();
  expect(errors).toEqual([]);
});

test("edited originally matching cues stay visible in flagged filter",async({page})=>{
  await page.goto("/quality-studio.html");
  await page.locator("#videoFile").setInputFiles(videoPath);
  await page.locator("#srtFile").setInputFiles({name:"source.srt",mimeType:"text/plain",buffer:Buffer.from(srt)});
  await page.locator("#reportFile").setInputFiles({name:"report.json",mimeType:"application/json",
    buffer:Buffer.from(JSON.stringify(report(sha(fs.readFileSync(videoPath)),sha(srt))))});
  await expect(page.locator("#status")).toContainText("1 source-bound");
  await page.locator("#captionList button").nth(1).click();
  await expect(page.locator("#saveTiming")).toBeEnabled();
  await page.locator("#start").fill("900");
  await page.locator("#saveTiming").click();
  await page.locator("#issuesOnly").check();
  await expect(page.locator("#captionList button")).toHaveCount(2);
  await expect(page.locator("#captionList button").nth(1)).toContainText("EDITED");
  await expect(page.locator("#captionList button").nth(1)).toContainText("Original evidence");
});

test("320px to desktop width without horizontal overflow",async({page})=>{
  await page.goto("/quality-studio.html");
  for(const width of [320,390,768,1280]){
    await page.setViewportSize({width,height:844});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  }
});
