const {test,expect} = require("@playwright/test");
const path=require("node:path");
const media=path.resolve(__dirname,"e2e.webm");

test("real Chromium boot, keyboard-accessible prompt and native video selection",async({page})=>{
  const errors=[];
  page.on("pageerror",e=>errors.push(e.message));
  await page.goto("/");
  await expect(page.locator("#promptInput")).toBeVisible();
  await expect(page.locator("#promptInput")).toHaveAttribute("dir","auto");
  await expect(page.locator("#videoInput")).toBeVisible();
  await expect(page.locator("label[for=promptInput]")).toBeVisible();
  await expect(page.locator("#status")).toContainText("LOCAL CHECK PASSED");
  expect(errors).toEqual([]);
});

test("negative music instructions are not mislabeled as positive",async({page})=>{
  await page.goto("/");
  await page.locator("#promptInput").fill("Create a 10 second 16:9 video. Do not use background music.");
  await page.locator("#analyzeBtn").click();
  await expect(page.locator("#findings")).not.toContainText("prompt.music.conflict");
  await expect(page.locator("#status")).toContainText("LOCAL CHECK PASSED");
});

test("real conflicting music blocks generation",async({page})=>{
  await page.goto("/");
  await page.locator("#promptInput").fill("Create a 10 second 16:9 video. No background music. Add subtle background music.");
  await page.locator("#analyzeBtn").click();
  await expect(page.locator("#findings")).toContainText("prompt.music.conflict");
  await expect(page.locator("#status")).toContainText("REVIEW / FIX REQUIRED");
});

test("actual WebM review shows complete playable video and metadata verdict",async({page})=>{
  await page.goto("/");
  await page.locator("#promptInput").fill("Create a 2 second 16:9 video with a sunset.");
  await page.locator("#videoInput").setInputFiles(media);
  await expect(page.locator("#qaVideoPreview")).toBeVisible({timeout:20000});
  await expect(page.locator("#videoQaSummary")).toContainText("2.00s duration");
  await expect(page.locator("#textChecklist")).toContainText("Manual whole-video whitelist check");
  await expect(page.locator("#videoQaStatus")).toContainText("YOUR TURN");
  await expect(page.locator("#qaVideoPreview")).toHaveJSProperty("paused",true);
});

test("inferred duration and aspect never create false saved failures",async({page})=>{
  await page.goto("/");
  await page.locator("#promptInput").fill("Show a sunset with no titles.");
  await page.locator("#videoInput").setInputFiles(media);
  await expect(page.locator("#videoQaSummary")).toContainText("Duration not specified");
  await expect(page.locator("#videoQaSummary")).toContainText("Aspect not specified");
  const failures=await page.evaluate(()=>JSON.parse(localStorage.getItem("vpp_failures")||"[]"));
  expect(failures.filter(f=>["timing","aspect_ratio"].includes(f.category))).toHaveLength(0);
  await expect(page.locator("#qaVideoPreview")).toBeVisible();
});

test("stored HTML fails to execute even after reload",async({page})=>{
  await page.goto("/");
  await page.evaluate(()=>{
    localStorage.setItem("vpp_failures",JSON.stringify([{
      category:"<img src=x onerror=window.__injected=1>",
      observed:"<svg onload=window.__injected=1>",
      expected:"safe"
    }]));
  });
  await page.reload();
  await expect(page.locator("#failureList")).toContainText("<img");
  expect(await page.evaluate(()=>window.__injected)).toBeUndefined();
  expect(await page.locator("#failureList img").count()).toBe(0);
});

test("CSP rejects scripts injected as inline elements",async({page})=>{
  await page.goto("/");
  await page.evaluate(()=>{
    const script=document.createElement("script");
    script.textContent="window.__csp_bypassed = true";
    document.head.appendChild(script);
  });
  expect(await page.evaluate(()=>window.__csp_bypassed)).toBeUndefined();
});
