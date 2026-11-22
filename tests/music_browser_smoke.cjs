/* Offline smoke test for German Educational Music QA browser controller. */
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function element() {
  return {
    value: "", checked: false, disabled: false, textContent: "", className: "",
    children: [], listeners: Object.create(null),
    addEventListener(name, cb) { this.listeners[name] = cb; },
    click() { if (this.listeners.click) return this.listeners.click(); },
    replaceChildren() { this.children = []; },
    appendChild(child) { this.children.push(child); }
  };
}
const elements = Object.create(null);
const document = {
  getElementById(id) { return elements[id] || (elements[id] = element()); },
  createElement() { return element(); }
};
const navigator = {clipboard: {async writeText(text) { assert.ok(text.length > 10); }}};
document.getElementById("musicQaPanel");
const script = fs.readFileSync(path.join(__dirname, "../web/music-qa.js"), "utf8");
vm.runInNewContext(script, {document, navigator, console, Set, RegExp}, {filename:"music-qa.js"});

const el = id => document.getElementById(id);
assert.match(el("musicQaStatus").textContent, /PREFLIGHT PASS/);
assert.match(el("musicQaPrompt").textContent, /EXACT LYRICS START/);

el("musicLyrics").value = "Wer ist das? Das ist die Hund!";
el("musicTargets").value = "der Hund";
el("musicCheck").click();
assert.match(el("musicQaStatus").textContent, /BLOCK/);
assert.equal(el("musicCopy").disabled, true);
assert.match(el("musicQaFindings").children.map(x=>x.textContent).join(" "), /article\.mismatch/);

el("musicExample").click();
el("musicLyrics").value += "\nأهلاً";
el("musicCheck").click();
assert.match(el("musicQaStatus").textContent, /BLOCK/);
el("musicBilingual").checked = true;
el("musicCheck").click();
assert.match(el("musicQaStatus").textContent, /PREFLIGHT PASS/);

el("musicInstrumental").checked = true;
el("musicCheck").click();
assert.match(el("musicQaStatus").textContent, /BLOCK/);

el("musicExample").click();
el("musicRepeats").value = "3";
el("musicCheck").click();
assert.match(el("musicQaStatus").textContent, /REVIEW/);
assert.equal(el("musicCopy").disabled, false);
console.log("German Educational Music QA browser smoke tests passed.");
