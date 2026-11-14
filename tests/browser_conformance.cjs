// Same golden fixtures are executed against the actual browser JS analyzer.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const {test} = require("node:test");
const corpus = JSON.parse(fs.readFileSync("tests/conformance_cases.json", "utf8"));
const context = {window:{},console};
vm.runInNewContext(fs.readFileSync("web/core.js","utf8"),context,{filename:"web/core.js"});
for(const c of corpus){
  test("browser parity: "+c.name, ()=>{
    const scene=context.window.VPP.parsePrompt(c.prompt);
    const ids=new Set(context.window.VPP.analyze(scene,c.prompt).map(f=>f.rule_id));
    if("duration" in c) assert.equal(scene.duration_seconds,c.duration);
    if("screen" in c) assert.deepEqual([...scene.screen_text],c.screen);
    if("no_music" in c) assert.equal(scene.rules.no_background_music,c.no_music);
    if("no_subtitles" in c) assert.equal(scene.rules.no_auto_subtitles,c.no_subtitles);
    if("timeline_starts" in c){
      assert.deepEqual(scene.timeline.map(e=>e.start),c.timeline_starts);
      assert.deepEqual(scene.timeline.map(e=>e.end),c.timeline_ends);
    }
    for(const field of ["expect_finding","expect_finding_secondary"]){
      if(field in c)assert.ok(ids.has(c[field]),"Missing "+c[field]);
    }
    if(c.check_no_duration_conflict) assert.ok(!ids.has("prompt.duration.conflict"));
    if(c.check_no_music_conflict) assert.ok(!ids.has("prompt.music.conflict"));
    if(c.check_no_subtitle_conflict) assert.ok(!ids.has("prompt.subtitle.conflict"));
  });
}
