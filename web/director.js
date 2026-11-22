/* AI Prompt Director: local single-scene preview. Python CLI remains the full-job gate. */
(function () {
  "use strict";
  const panel = document.getElementById("directorPanel");
  if (!panel) return;
  const byId = id => document.getElementById(id);
  const articleLexicon = {
    hund:"der", katze:"die", pferd:"das", vogel:"der", fisch:"der",
    haus:"das", schule:"die", buch:"das", mensa:"die",
    universität:"die", bibliothek:"die", wohnheim:"das",
    bahnhof:"der", ticket:"das", student:"der", studentin:"die"
  };
  const levels = new Set(["pre-a1", "a1", "a2", "b1", "b2", "c1", "c2"]);
  let approvedPrompt = "";
  const normalize = value => String(value || "").normalize("NFC").trim().replace(/\s+/g, " ").toLocaleLowerCase("de");

  function collect() {
    return {
      objective:byId("directorObjective").value.trim(),
      level:byId("directorLevel").value,
      minAge:Number(byId("directorMinAge").value),
      maxAge:Number(byId("directorMaxAge").value),
      targets:byId("directorTargets").value.split("\n").map(v=>v.trim()).filter(Boolean),
      cast:byId("directorCast").value.split(",").map(v=>v.trim()).filter(Boolean),
      speaker:byId("directorSpeaker").value.trim(),
      dialogue:byId("directorDialogue").value.trim(),
      scene:byId("directorScene").value.trim(),
      seconds:Number(byId("directorDuration").value),
      anchor:byId("directorAnchor").value.trim()
    };
  }

  function check() {
    const spec = collect(), issues = [];
    function add(severity, rule, detail) {
      issues.push({severity, rule, detail});
    }
    if (!spec.objective || spec.objective.split(/\s+/).length < 4 || spec.objective.length > 280) {
      add("error", "director.objective.missing", "Add a specific learning objective (at least four words).");
    }
    if (!levels.has(normalize(spec.level))) {
      add("error", "director.cefr.missing", "Select a valid German CEFR level.");
    }
    if (!Number.isInteger(spec.minAge) || !Number.isInteger(spec.maxAge) ||
        spec.minAge < 3 || spec.maxAge > 100 || spec.minAge > spec.maxAge) {
      add("error", "director.age.missing", "Specify realistic learner age boundaries.");
    }
    if (!spec.targets.length || spec.targets.length > 20) {
      add("error", "director.targets.missing", "Set 1–20 exact German teaching phrases.");
    }
    if (!spec.speaker || !spec.dialogue) {
      add("error", "director.dialogue.unspecified", "Declare the speaker and exact line.");
    }
    if (spec.speaker && spec.cast.length && !spec.cast.some(x=>normalize(x)===normalize(spec.speaker))) {
      add("error", "director.speaker.not_in_cast", "Speaker must belong to the declared cast.");
    }
    if (!spec.scene || !normalize(spec.scene).includes(normalize(spec.dialogue))) {
      add("error", "director.dialogue.not_in_prompt", "Exact dialogue must appear in the scene prompt.");
    }
    for (const target of spec.targets) {
      if (!normalize(spec.dialogue).includes(normalize(target))) {
        add("error", "director.target.not_spoken", "Teaching phrase missing from approved dialogue: " + target);
      }
    }
    const articlePattern = /\b(der|die|das)\s+([a-zäöüß]+)\b/giu;
    for (const match of spec.dialogue.matchAll(articlePattern)) {
      const expected = articleLexicon[normalize(match[2])];
      if (expected && normalize(match[1]) !== expected) {
        add("error", "director.article.check", "Check " + match[1] + " " + match[2] + "; expected " + expected + ".");
      }
    }
    if (!Number.isInteger(spec.seconds) || spec.seconds < 3 || spec.seconds > 15) {
      add("error", "director.duration.invalid", "Gemini scene length must be 3–15 seconds.");
    }
    if (spec.dialogue.split(/\s+/).length > spec.seconds * 3.2) {
      add("error", "director.speech.overflow", "Too many German words for this duration.");
    } else if (spec.dialogue.split(/\s+/).length > spec.seconds * 2.4) {
      add("warning", "director.speech.tight", "Dialogue may be rushed for learners.");
    }
    if (/\b(?:add|show|generate|display|include)\s+(?:automatic\s+)?(?:subtitles?|captions?)\b/i.test(spec.scene)) {
      add("error", "director.captions.conflict", "Generated captions conflict with post-production subtitles.");
    }

    const prompt = [
      "Create exactly " + spec.seconds + "-second vertical 9:16 German educational video.",
      "LEARNING OBJECTIVE: " + spec.objective,
      "CEFR: " + spec.level + ", ages " + spec.minAge + "–" + spec.maxAge + ".",
      "CAST: " + (spec.cast.join(", ") || spec.speaker),
      "EXACT GERMAN DIALOGUE: " + spec.speaker + ': "' + spec.dialogue + '"',
      "No extra dialogue. No automatic subtitles; add captions in editing.",
      "SCENE: " + spec.scene
    ].concat(spec.anchor ? ["CONSISTENT VISUAL REFERENCE: " + spec.anchor] : []).join("\n");

    if (window.VPP && typeof window.VPP.tripleReview === "function" &&
        spec.seconds >= 3 && spec.seconds <= 15 && spec.scene) {
      try {
        const result = window.VPP.tripleReview(prompt, "gemini_omni", []);
        if (!result.passed) add("error", "director.vpp.blocked", "VPP 3-round scene preflight did not pass.");
        const warnings = Array.isArray(result.findings)
          ? result.findings.filter(f=>f.severity==="warning") : [];
        if (warnings.length) {
          add("warning", "director.vpp.advisory",
            String(warnings.length) + " advisory finding(s) remain in VPP's review.");
        }
      } catch {
        add("error", "director.vpp.unavailable", "VPP could not complete its local review.");
      }
    } else {
      add("error", "director.vpp.unavailable", "VPP scene review is required.");
    }
    const blocked = issues.some(x=>x.severity==="error");
    const needsRevision = issues.some(x=>x.severity==="warning");
    const verdict = blocked ? "BLOCKED" : needsRevision ? "NEEDS REVISION" : "READY FOR GENERATION";
    byId("directorStatus").textContent = verdict +
      " — only local text checks; verify source German and rendered media with a teacher.";
    byId("directorStatus").className = blocked ? "fail" : needsRevision ? "warn" : "pass";
    byId("directorFindings").replaceChildren();
    for (const issue of issues) {
      const line = document.createElement("p");
      line.className = issue.severity === "error" ? "fail" : "warn";
      line.textContent = issue.severity.toUpperCase() + " · " + issue.rule + ": " + issue.detail;
      byId("directorFindings").appendChild(line);
    }
    if (!issues.length) {
      const line = document.createElement("p");
      line.textContent = "Local checks passed. Audio/visual quality is not certified.";
      byId("directorFindings").appendChild(line);
    }
    approvedPrompt = blocked || needsRevision ? "" : prompt;
    byId("directorFinalPrompt").textContent = approvedPrompt ||
      "Resolve blocking/advisory findings first; no approved prompt is released.";
    byId("directorCopy").disabled = !approvedPrompt;
    return verdict;
  }

  byId("directorCheck").addEventListener("click", check);
  byId("directorExample").addEventListener("click", function () {
    byId("directorObjective").value = "Learners can ask for cafeteria directions politely in German.";
    byId("directorLevel").value = "A1";
    byId("directorMinAge").value = "17";
    byId("directorMaxAge").value = "25";
    byId("directorTargets").value = "Entschuldigung, wo ist die Mensa?";
    byId("directorCast").value = "Student A, Student B";
    byId("directorSpeaker").value = "Student A";
    byId("directorDialogue").value = "Entschuldigung, wo ist die Mensa?";
    byId("directorScene").value = 'On a German campus, Student A asks Student B: "Entschuldigung, wo ist die Mensa?" The camera stays stable, student B listens calmly.';
    byId("directorDuration").value = "8";
    byId("directorAnchor").value = "";
    check();
  });
  byId("directorCopy").addEventListener("click", async function () {
    if (!approvedPrompt) return;
    try {
      await navigator.clipboard.writeText(approvedPrompt);
      byId("directorStatus").textContent = "Reviewed draft copied. Listen to the final video before publishing.";
    } catch {
      byId("directorStatus").textContent = "Clipboard unavailable. Copy the prompt manually.";
    }
  });
  byId("directorExample").click();
})();