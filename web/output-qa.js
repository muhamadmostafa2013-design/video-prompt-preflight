window.VPPOutputQA = (() => {
  const $ = id => document.getElementById(id);
  let options = {};
  let current = null;

  const readFailures = () => {
    try { return JSON.parse(localStorage.getItem("vpp_failures") || "[]"); }
    catch { return []; }
  };

  const writeFailures = items => {
    localStorage.setItem("vpp_failures", JSON.stringify(items));
    if (typeof options.onMemoryChanged === "function") options.onMemoryChanged();
  };

  const saveFailure = (category, observed, expected) => {
    const items = readFailures();
    const duplicate = items.some(x => x.category === category && x.observed === observed);
    if (!duplicate) {
      items.push({category, observed, expected, created_at:new Date().toISOString(), source:"output_qa"});
      writeFailures(items);
    }
  };

  const parseAspect = value => {
    const m = String(value || "9:16").match(/(\d+(?:\.\d+)?)\s*:\s*(\d+(?:\.\d+)?)/);
    return m ? Number(m[1]) / Number(m[2]) : 9/16;
  };

  const once = (target, event) => new Promise((resolve, reject) => {
    const ok = () => { cleanup(); resolve(); };
    const bad = () => { cleanup(); reject(new Error(`Video ${event} failed`)); };
    const cleanup = () => {
      target.removeEventListener(event, ok);
      target.removeEventListener("error", bad);
    };
    target.addEventListener(event, ok, {once:true});
    target.addEventListener("error", bad, {once:true});
  });

  const seek = async (video, time) => {
    if (Math.abs(video.currentTime - time) < 0.03) return;
    const done = once(video, "seeked");
    video.currentTime = Math.max(0, Math.min(time, Math.max(0, video.duration - 0.03)));
    await done;
  };

  const sampleFrames = async (video, count=8) => {
    const frames = [];
    const canvas = document.createElement("canvas");
    const targetW = 150;
    const ratio = video.videoHeight / Math.max(1, video.videoWidth);
    canvas.width = targetW;
    canvas.height = Math.max(90, Math.round(targetW * ratio));
    const ctx = canvas.getContext("2d", {willReadFrequently:false});

    for (let i=0;i<count;i++) {
      const frac = count === 1 ? .5 : (.06 + i * (.88/(count-1)));
      const t = Math.max(0, Math.min(video.duration - .04, video.duration * frac));
      await seek(video, t);
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      frames.push({time:t, url:canvas.toDataURL("image/jpeg", .72)});
    }
    return frames;
  };

  const badge = (ok, yes, no) => `<span class="qa-badge ${ok ? "qa-ok" : "qa-bad"}">${ok ? "✓" : "!"} ${ok ? yes : no}</span>`;

  const renderFrames = frames => {
    const el = $("frameStrip");
    el.innerHTML = frames.map(f =>
      `<figure><img src="${f.url}" alt="Sample frame at ${f.time.toFixed(1)} seconds"><figcaption>${f.time.toFixed(1)}s</figcaption></figure>`
    ).join("");
  };

  const updateManualSummary = () => {
    if (!current) return;
    const states = current.scene.screen_text || [];
    const reviewed = Object.keys(current.textReview).length;
    const failed = Object.values(current.textReview).filter(v => v === "fail").length;
    const passed = Object.values(current.textReview).filter(v => v === "pass").length;

    if (!states.length) {
      $("textQaSummary").textContent = "No exact screen-text states were requested in this prompt.";
      return;
    }

    if (reviewed < states.length) {
      $("textQaSummary").textContent = `Exact-text review: ${reviewed}/${states.length} checked. Tap ✓ when spelling is exact, × when it is wrong or missing.`;
      $("videoQaStatus").textContent = current.autoPass ? "AUTO CHECK DONE · YOUR TURN 👀" : "CUT! METADATA ISSUE ✋";
      $("videoQaStatus").className = current.autoPass ? "warn" : "fail";
      return;
    }

    if (failed) {
      $("textQaSummary").textContent = `Text QA failed: ${failed} of ${states.length} required states were wrong or missing. Saved to Bloopers Memory.`;
      $("videoQaStatus").textContent = "CUT! TEXT ISSUE ✋";
      $("videoQaStatus").className = "fail";
    } else {
      $("textQaSummary").textContent = `Exact-text review passed: ${passed}/${states.length} states confirmed.`;
      $("videoQaStatus").textContent = current.autoPass ? "OUTPUT GREEN LIGHT 🎬" : "TEXT PASS · METADATA NEEDS FIX";
      $("videoQaStatus").className = current.autoPass ? "pass" : "warn";
    }
  };

  const escapeHtml = value => String(value ?? "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");

  const renderChecklist = scene => {
    const states = scene.screen_text || [];
    const el = $("textChecklist");
    if (!states.length) {
      el.innerHTML = `<p class="micro">No exact text states to review for this scene.</p>`;
      updateManualSummary();
      return;
    }

    el.innerHTML = states.map((text, i) => `
      <div class="text-check-row" data-index="${i}">
        <div><small>Expected text state</small><strong>${escapeHtml(text)}</strong></div>
        <div class="text-check-actions">
          <button type="button" class="qa-choice" data-result="pass" data-index="${i}" aria-label="Mark ${escapeHtml(text)} correct">✓</button>
          <button type="button" class="qa-choice" data-result="fail" data-index="${i}" aria-label="Mark ${escapeHtml(text)} wrong or missing">×</button>
        </div>
      </div>
    `).join("");

    el.querySelectorAll(".qa-choice").forEach(btn => {
      btn.addEventListener("click", () => {
        const i = Number(btn.dataset.index);
        const result = btn.dataset.result;
        const word = states[i];
        current.textReview[i] = result;

        const row = el.querySelector(`.text-check-row[data-index="${i}"]`);
        row.classList.toggle("row-pass", result === "pass");
        row.classList.toggle("row-fail", result === "fail");
        row.querySelectorAll(".qa-choice").forEach(x => x.classList.toggle("selected", x === btn));

        if (result === "fail") {
          saveFailure(
            "exact_text",
            `Generated video showed "${word}" incorrectly or did not hold it as a clean stable state.`,
            `Render "${word}" exactly as a separate static state with a clean cut; for critical spelling, prefer a post-production overlay.`
          );
        }
        updateManualSummary();
      });
    });

    updateManualSummary();
  };

  const analyzeFile = async file => {
    const scene = typeof options.getScene === "function" ? options.getScene() : {};
    const panel = $("videoQaPanel");
    panel.hidden = false;
    $("videoQaStatus").textContent = "ROLLING QA… 🎥";
    $("videoQaStatus").className = "warn";
    $("videoQaSummary").textContent = "Reading video metadata and sampling frames locally…";
    $("frameStrip").innerHTML = "";
    $("textChecklist").innerHTML = "";
    $("textQaSummary").textContent = "";

    const url = URL.createObjectURL(file);
    const video = document.createElement("video");
    video.preload = "auto";
    video.muted = true;
    video.playsInline = true;
    video.src = url;

    try {
      await once(video, "loadedmetadata");
      if (video.readyState < 2) await once(video, "loadeddata");

      const expectedDuration = Number(scene.duration_seconds || 10);
      const actualDuration = Number(video.duration || 0);
      const durationOk = Math.abs(actualDuration - expectedDuration) <= 0.35;

      const expectedAspect = parseAspect(scene.aspect_ratio || "9:16");
      const actualAspect = video.videoWidth / Math.max(1, video.videoHeight);
      const aspectError = Math.abs(actualAspect - expectedAspect) / expectedAspect;
      const aspectOk = aspectError <= 0.07;

      const frames = await sampleFrames(video, 8);
      current = {
        fileName:file.name,
        scene,
        actualDuration,
        expectedDuration,
        width:video.videoWidth,
        height:video.videoHeight,
        durationOk,
        aspectOk,
        autoPass:durationOk && aspectOk,
        textReview:{}
      };

      const autoBits = [
        badge(durationOk, `${actualDuration.toFixed(2)}s duration`, `${actualDuration.toFixed(2)}s vs ${expectedDuration}s`),
        badge(aspectOk, `${video.videoWidth}×${video.videoHeight}`, `${video.videoWidth}×${video.videoHeight} ratio`)
      ];

      $("videoQaSummary").innerHTML =
        `${autoBits.join(" ")} <span class="qa-note">File stays in this browser. No upload, no API call.</span>`;

      renderFrames(frames);
      renderChecklist(scene);

      if (!durationOk) {
        saveFailure(
          "timing",
          `Generated video duration was ${actualDuration.toFixed(2)}s instead of ${expectedDuration}s.`,
          `Keep generated duration within ±0.35s of ${expectedDuration}s.`
        );
      }
      if (!aspectOk) {
        saveFailure(
          "aspect_ratio",
          `Generated video resolution ${video.videoWidth}×${video.videoHeight} did not match ${scene.aspect_ratio || "9:16"} closely.`,
          `Generate the requested ${scene.aspect_ratio || "9:16"} aspect ratio.`
        );
      }
    } catch (err) {
      $("videoQaStatus").textContent = "COULDN'T READ THIS TAKE";
      $("videoQaStatus").className = "fail";
      $("videoQaSummary").textContent = err?.message || "The browser could not inspect this video.";
    } finally {
      URL.revokeObjectURL(url);
    }
  };

  const bind = opts => {
    options = opts || {};
    const input = $("videoInput");
    if (!input || input.dataset.bound === "1") return;
    input.dataset.bound = "1";
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (file) analyzeFile(file);
    });
  };

  return {bind, analyzeFile};
})();
