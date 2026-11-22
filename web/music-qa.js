/* German Educational Music QA: offline browser preflight; no audio verification. */
(function () {
  "use strict";
  const panel = document.getElementById("musicQaPanel");
  if (!panel) return;

  const $ = (id) => document.getElementById(id);
  const nouns = {
    hund:"der", katze:"die", pferd:"das", vogel:"der", fisch:"der",
    maus:"die", elefant:"der", hase:"der", löwe:"der", tiger:"der",
    kuh:"die", schaf:"das", kaninchen:"das", bär:"der", ente:"die",
    frosch:"der", apfel:"der", banane:"die", brot:"das", haus:"das",
    schule:"die", buch:"das", tisch:"der", stuhl:"der"
  };
  const validLevels = new Set(["pre-a1","a1","a2","b1","b2","c1","c2"]);
  let readyPrompt = "";

  function phraseCount(text, phrase) {
    const safe = phrase.trim().split(/\s+/).map(function (part) {
      return part.replace(/[.*+?^$()|[\]{}\\]/g, "\\$&");
    }).join("\\s+");
    if (!safe) return 0;
    const regex = new RegExp("(^|[^\\p{L}\\p{N}_])" + safe + "(?=$|[^\\p{L}\\p{N}_])", "gimu");
    return [...text.matchAll(regex)].length;
  }

  function gather() {
    return {
      lyrics: $("musicLyrics").value.trim(),
      target_vocabulary: $("musicTargets").value.split(/\n|,/).map(x => x.trim()).filter(Boolean),
      cefr: $("musicLevel").value,
      age_range: [6, 9],
      bpm: Number($("musicBpm").value),
      min_repetitions: Number($("musicRepeats").value),
      language: "de",
      allow_bilingual: $("musicBilingual").checked,
      instrumental_only: $("musicInstrumental").checked,
      vocal_direction: $("musicVoice").value.trim(),
      style: $("musicStyle").value.trim(),
      provider: "gemini-lyria"
    };
  }

  function review(spec) {
    const findings = [], counts = {};
    function add(rule, severity, message) {
      findings.push({rule_id:rule, severity:severity, message:message});
    }
    if (!spec.lyrics) add("music.lyrics.empty","error","Add the exact song lyrics.");
    if (spec.lyrics.length > 16000) add("music.lyrics.limit","error","Lyrics exceed the 16,000-character limit.");
    if (spec.target_vocabulary.length > 50) add("music.targets.limit","error","Use at most 50 teaching targets.");
    if (!spec.allow_bilingual && /[\u0600-\u06ff]/.test(spec.lyrics)) {
      add("music.lyrics.arabic","error","Arabic lyrics require the bilingual toggle.");
    }
    if (spec.instrumental_only && spec.lyrics) {
      add("music.vocals.conflict","error","Instrumental-only conflicts with sung lyrics.");
    }
    if (!validLevels.has(spec.cefr.toLowerCase())) {
      add("music.cefr.unknown","warning","Verify the learner's CEFR level.");
    }
    if (!Number.isInteger(spec.min_repetitions) || spec.min_repetitions < 1 || spec.min_repetitions > 20) {
      add("music.repetition.invalid","error","Repetitions must be a whole number from 1 to 20.");
    }
    if (!spec.bpm || !Number.isFinite(spec.bpm)) {
      add("music.bpm.missing","warning","Choose a BPM for predictable pacing.");
    } else if (spec.bpm < 45 || spec.bpm > 200) {
      add("music.bpm.extreme","warning","Verify unusually slow/fast tempo.");
    } else if (spec.bpm > 150) {
      add("music.tempo.children","warning","Fast tempo may obscure articles for young learners.");
    }
    if (!spec.target_vocabulary.length) add("music.targets.missing","warning","Add target phrases to verify learning objectives.");
    for (const target of spec.target_vocabulary) {
      const count = phraseCount(spec.lyrics, target);
      counts[target] = count;
      if (!count) add("music.target.missing","error","Missing vocabulary: " + target);
      else if (count < spec.min_repetitions) add("music.target.repetition","warning",
        target + ": " + count + " time(s), need " + spec.min_repetitions + ".");
    }
    const articleRegex = /(^|[^\p{L}\p{N}_])(der|die|das)\s+([\p{L}]+)/gimu;
    const seen = new Set();
    for (const match of spec.lyrics.matchAll(articleRegex)) {
      const article = match[2].toLocaleLowerCase("de");
      const noun = match[3].toLocaleLowerCase("de");
      const expected = nouns[noun];
      if (expected && article !== expected && !seen.has(article + "|" + noun)) {
        seen.add(article + "|" + noun);
        add("music.article.mismatch","error","Check " + match[2] + " " + match[3] +
          ": expected " + expected + " " + match[3] + ".");
      }
    }
    if (spec.lyrics.split("\n").some(line => line.trim().split(/\s+/).filter(Boolean).length > 12)) {
      add("music.line.dense","warning","A lyric line exceeds 12 words for young learners.");
    }
    if (!spec.vocal_direction) add("music.voice.unspecified","warning","Specify clear Standard German diction.");
    const blocked = findings.some(item => item.severity === "error");
    const warning = findings.some(item => item.severity === "warning");
    return {findings, counts, blocked, decision:blocked?"BLOCK":warning?"REVIEW":"PREFLIGHT PASS"};
  }

  function makePrompt(spec) {
    return [
      "TASK: Create an ORIGINAL German educational song for ages 6-9, CEFR " + spec.cefr + ".",
      "GENERATOR: " + spec.provider,
      "STYLE: " + (spec.style || "Cheerful, age-appropriate"),
      "TEMPO: " + spec.bpm + " BPM",
      "VOCALS: " + (spec.vocal_direction || "Clear Standard German diction"),
      "TEACHING TARGETS: " + (spec.target_vocabulary.join(", ") || "Teacher review required"),
      "Sing the EXACT lyrics below. Preserve all words and German articles.",
      "Do not add invented lyrics or narration.",
      "EXACT LYRICS START", spec.lyrics, "EXACT LYRICS END",
      "Mandatory AFTER generation: a German-speaking teacher must check pronunciation, lyric fidelity, intelligibility and rights."
    ].join("\n");
  }

  function run() {
    const spec = gather();
    const result = review(spec);
    const status = $("musicQaStatus");
    status.textContent = result.decision +
      " — text preflight only; the finished recording still requires listening QA.";
    status.className = result.blocked ? "fail" : result.decision === "REVIEW" ? "warn" : "pass";

    const findings = $("musicQaFindings");
    findings.replaceChildren();
    if (!result.findings.length) {
      const p = document.createElement("p");
      p.textContent = "No deterministic issues detected. This does not certify pronunciation or grammar.";
      findings.appendChild(p);
    }
    for (const finding of result.findings) {
      const p = document.createElement("p");
      p.className = finding.severity === "error" ? "fail" : "warn";
      p.textContent = finding.severity.toUpperCase() + " · " +
        finding.rule_id + ": " + finding.message;
      findings.appendChild(p);
    }

    readyPrompt = result.blocked ? "" : makePrompt(spec);
    $("musicQaPrompt").textContent = readyPrompt || "Blocking issues: fix the lyrics/spec and check again.";
    $("musicCopy").disabled = result.blocked;
  }

  $("musicCheck").addEventListener("click", run);
  $("musicExample").addEventListener("click", function () {
    $("musicLyrics").value = [
      "Wer ist das? Das ist der Hund!",
      "Wer ist das? Das ist die Katze!",
      "Wer ist das? Das ist das Pferd!",
      "Deutsch lernen macht uns Spaß!",
      "",
      "Wer ist das? Das ist der Hund!",
      "Wer ist das? Das ist die Katze!",
      "Wer ist das? Das ist das Pferd!",
      "Deutsch lernen macht uns Spaß!"
    ].join("\n");
    $("musicTargets").value = "der Hund\ndie Katze\ndas Pferd";
    $("musicBpm").value = "105";
    $("musicRepeats").value = "2";
    $("musicVoice").value = "Clear Standard German diction; emphasize der/die/das naturally.";
    $("musicStyle").value = "Cheerful original acoustic pop; ukulele and glockenspiel";
    $("musicBilingual").checked = false;
    $("musicInstrumental").checked = false;
    run();
  });
  $("musicCopy").addEventListener("click", async function () {
    if (!readyPrompt) return;
    try {
      await navigator.clipboard.writeText(readyPrompt);
      $("musicQaStatus").textContent = "Prompt copied. Audio verification is still required.";
    } catch {
      $("musicQaStatus").textContent = "Copy unavailable. Select the prompt text manually.";
    }
  });
  $("musicExample").click();
})();
