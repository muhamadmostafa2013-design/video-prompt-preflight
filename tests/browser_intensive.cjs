const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {test}=require('node:test');
const ctx={window:{},console};
for(const file of ['web/core.js','web/triple.js']){
  vm.runInNewContext(fs.readFileSync(file,'utf8'),ctx,{filename:file});
}
const A=ctx.window.VPP;

test('A/B/C candidates preserve absolute timing and gap intervals',()=>{
  const scene=A.parsePrompt('Create a 10 second 9:16 video.\nTIMELINE:\n3-5s show first\n7-9s show last');
  const candidates=A.candidates(scene,'veo');
  assert.equal(candidates.length,3);
  for(const candidate of candidates){
    assert.match(candidate.prompt,/3-5s/);
    assert.match(candidate.prompt,/7-9s/);
    assert.doesNotMatch(candidate.prompt,/0-2s/);
    assert.equal(candidate.coverage,100);
  }
});

test('camera instructions never become static screen text',()=>{
  const scene=A.parsePrompt('Create a 10 second 9:16 video.\nON SCREEN:\nlaufen\nTIMELINE:\n0-10s animate the camera to presenter');
  for(const candidate of A.candidates(scene,'veo')){
    assert.match(candidate.prompt,/animate the camera to presenter/);
    assert.doesNotMatch(candidate.prompt,/show the camera as static text/);
  }
});

test('exact word morph candidates include hard cuts',()=>{
  const scene=A.parsePrompt('Create a 10 second 9:16 video.\nON SCREEN:\nlaufen\nsich verlaufen\nTIMELINE:\n0-10s transform laufen into sich verlaufen');
  for(const candidate of A.candidates(scene,'veo')){
    assert.match(candidate.prompt,/hard cut/i);
  }
});

test('local gate blocks overlapping timeline instructions',()=>{
  const result=A.tripleReview('Create a 10 second 9:16 video.\nTIMELINE:\n0-6s first\n5-10s second','veo',[]);
  assert.equal(result.passed,false);
  assert.ok(result.findings.some(f=>f.rule_id==='timeline.overlap'));
});