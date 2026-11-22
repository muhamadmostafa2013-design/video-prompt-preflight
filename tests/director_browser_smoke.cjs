/* Browser smoke test for local AI Prompt Director (no browser/network needed). */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function element() {
  return {
    value: "", textContent: "", className: "", disabled: false,
    children: [], listeners: Object.create(null),
    addEventListener(name, callback) { this.listeners[name] = callback; },
    click() { return this.listeners.click && this.listeners.click(); },
    replaceChildren() { this.children = []; },
    appendChild(node) { this.children.push(node); }
  };
}
const controls = Object.create(null);
const document = {
  getElementById(id) { return controls[id] || (controls[id] = element()); },
  createElement() { return element(); }
};
const verdict = {passed: true, findings: []};
const window = {VPP: {tripleReview: () => verdict}};
const navigator = {clipboard: {async writeText(text) {
  assert.match(text, /EXACT GERMAN DIALOGUE/);
}}};
const source = fs.readFileSync(path.join(__dirname, "../web/director.js"), "utf8");
vm.runInNewContext(source, {document, window, navigator, Set}, {filename: "director.js"});
const get = id => document.getElementById(id);

assert.match(get("directorStatus").textContent, /READY FOR GENERATION/);
assert.equal(get("directorCopy").disabled, false);
assert.match(get("directorFinalPrompt").textContent, /Mensa/);

get("directorObjective").value = "";
get("directorCheck").click();
assert.match(get("directorStatus").textContent, /BLOCKED/);
assert.equal(get("directorCopy").disabled, true);

get("directorExample").click();
get("directorDialogue").value = "Das ist die Hund.";
get("directorTargets").value = "Das ist die Hund.";
get("directorScene").value = 'Student A says "Das ist die Hund."';
get("directorCheck").click();
assert.match(get("directorStatus").textContent, /BLOCKED/);
assert.match(get("directorFindings").children.map(x=>x.textContent).join(" "),
  /director.article.check/);

get("directorExample").click();
get("directorSpeaker").value = "Student C";
get("directorCheck").click();
assert.match(get("directorFindings").children.map(x=>x.textContent).join(" "),
  /director.speaker.not_in_cast/);

get("directorExample").click();
verdict.findings = [{severity:"warning",rule_id:"some.advisory"}];
get("directorCheck").click();
assert.match(get("directorStatus").textContent, /NEEDS REVISION/);
assert.equal(get("directorCopy").disabled, true);

verdict.findings = [];
verdict.passed = false;
get("directorCheck").click();
assert.match(get("directorStatus").textContent, /BLOCKED/);
assert.equal(get("directorCopy").disabled, true);

verdict.passed = true;
get("directorExample").click();
assert.match(get("directorStatus").textContent, /READY FOR GENERATION/);
console.log("AI Prompt Director browser smoke test passed.");
