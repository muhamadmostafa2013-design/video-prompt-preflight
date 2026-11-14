// Browser boot and media-verdict smoke test using Node's built-in VM.
// Not a substitute for a real browser/device test, but it executes actual UI scripts.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const { test } = require("node:test");

const UI = fs.readFileSync("web/ui.js", "utf8");
const QA = fs.readFileSync("web/output-qa.js", "utf8");

function makeUIContext(rawMemory, storageThrows = false) {
  const elements = new Map();
  const el = id => {
    if (!elements.has(id)) {
      elements.set(id, {
        innerHTML:"", textContent:"", value:"", hidden:false, className:"",
        dataset:{}, onclick:null, style:{}, addEventListener(){},
        querySelectorAll(){return[];}, querySelector(){return {classList:{toggle(){}}};}
      });
    }
    return elements.get(id);
  };
  const document = {
    getElementById: el,
    scripts:[],
    head:{appendChild(){}},
    createElement(){return {src:"", onload:null, onerror:null};},
  };
  const storage = {
    getItem(){if(storageThrows) throw new Error("blocked"); return rawMemory;},
    setItem(){if(storageThrows) throw new Error("blocked");},
  };
  const A = {
    parsePrompt:()=>({duration_seconds:10,screen_text:[],timeline:[],rules:{}}),
    analyze:()=>[],
    simulate:()=>({duration:10,util:0,events:0,text:0,total:0,status:"comfortable"}),
    compile:()=>("safe compiled prompt"),
  };
  let bound = false;
  const context = {
    document, localStorage:storage, console, URL,
    navigator:{clipboard:{writeText:async()=>{}}},
    window:{VPP:A,VPPOutputQA:{bind(){bound=true}}},
    setTimeout, clearTimeout,
  };
  vm.runInNewContext(UI,context,{filename:"web/ui.js",timeout:1500});
  return {el,context,isBound:()=>bound};
}

test("null-valued failure memory does not prevent initialization",()=>{
  const page=makeUIContext("[null]");
  assert.equal(page.isBound(),true);
  assert.equal(typeof page.el("analyzeBtn").onclick,"function");
});

test("stored injection is HTML escaped on UI initialization",()=>{
  const attack=JSON.stringify([{category:'<img src=x onerror=alert(1)>',
    observed:'<svg onload=alert(2)>',expected:"secure",source:"manual"}]);
  const page=makeUIContext(attack);
  const html=page.el("failureList").innerHTML;
  assert.equal(html.includes("<img"),false);
  assert.equal(html.includes("<svg"),false);
  assert.equal(html.includes("&lt;img"),true);
});

test("disabled localStorage does not prevent app boot or recording a failure",()=>{
  const page=makeUIContext("[]",true);
  page.el("failureCategory").value="audio";
  page.el("failureObserved").value="missing";
  page.el("failureExpected").value="present";
  page.el("saveFailureBtn").onclick();
  assert.equal(page.isBound(),true);
  assert.match(page.el("summaryLine").textContent,/storage/i);
});

function makeQAContext(){
  const elements=new Map();
  const el=id=>{
    if(!elements.has(id)) elements.set(id,{
      id, hidden:false, innerHTML:"", textContent:"",className:"",
      files:[],dataset:{},addEventListener(){},querySelectorAll(){return[];},
      querySelector(){return {classList:{toggle(){}}};}
    });
    return elements.get(id);
  };
  class FakeVideo {
    constructor(){
      this.duration=4;this.videoWidth=640;this.videoHeight=360;
      this.readyState=2;this._listeners=new Map();this._time=0;
    }
    addEventListener(ev,fn){this._listeners.set(ev,fn);}
    removeEventListener(ev){this._listeners.delete(ev);}
    set src(v){this._src=v;setImmediate(()=>this._listeners.get("loadedmetadata")?.());}
    get src(){return this._src;}
    set currentTime(x){this._time=x;setImmediate(()=>this._listeners.get("seeked")?.());}
    get currentTime(){return this._time;}
  }
  const document={
    getElementById:el,
    createElement(type){
      if(type==="video")return new FakeVideo();
      if(type==="canvas")return{
        width:0,height:0,
        getContext(){return{drawImage(){}};},
        toDataURL(){return "data:image/jpeg;base64,AAA";},
      };
      throw new Error("unexpected "+type);
    },
  };
  const context={
    document, localStorage:{getItem(){return"[null]";},setItem(){throw Error("blocked");}},
    window:{}, URL:{createObjectURL(){return"blob:test";},revokeObjectURL(){}},
    setTimeout,clearTimeout,
  };
  vm.runInNewContext(QA,context,{filename:"web/output-qa.js",timeout:1500});
  return {el,context};
}
test("no screen text still fails wrong metadata and handles blocked storage",async()=>{
  const {el,context}=makeQAContext();
  context.window.VPPOutputQA.bind({
    getScene:()=>({duration_seconds:10,aspect_ratio:"9:16",screen_text:[]}),
    onMemoryChanged:()=>{},
  });
  await context.window.VPPOutputQA.analyzeFile({name:"bad.mp4",size:1024});
  assert.match(el("videoQaStatus").textContent,/METADATA ISSUE/);
  assert.match(el("videoQaSummary").innerHTML,/4\.00s vs 10s/);
  assert.match(el("textChecklist").innerHTML,/whitelist check/);
});
