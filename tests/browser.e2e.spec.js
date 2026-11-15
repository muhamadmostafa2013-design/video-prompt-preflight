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


test.describe('deep QA: mobile, review and security',()=>{
  test.use({viewport:{width:390,height:844},isMobile:true,hasTouch:true});

  test('mobile layout does not horizontally overflow and controls stay visible',async({page})=>{
    const errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.goto('/');
    await expect(page.locator('#promptInput')).toBeVisible();
    await expect(page.locator('#videoInput')).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2)).toBe(false);
    expect(errors).toEqual([]);
  });

  test('all browser candidate prompts preserve original time gaps',async({page})=>{
    await page.goto('/');
    const result=await page.evaluate(()=>{
      const scene=window.VPP.parsePrompt('Create a 10 second 9:16 video.\nTIMELINE:\n3-5s show intro\n7-9s show ending');
      return window.VPP.candidates(scene,'veo');
    });
    expect(result).toHaveLength(3);
    for(const c of result){
      expect(c.prompt).toMatch(/3-5s/);
      expect(c.prompt).toMatch(/7-9s/);
      expect(c.coverage).toBe(100);
    }
  });

  test('invalid video file displays a clean error',async({page})=>{
    await page.goto('/');
    await page.locator('#videoInput').setInputFiles({
      name:'fake.mp4',mimeType:'video/mp4',buffer:Buffer.from('not a real video')
    });
    await expect(page.locator('#videoQaStatus')).toContainText("COULDN'T READ THIS TAKE",{timeout:20000});
    await expect(page.locator('#qaVideoPreview')).toBeHidden();
  });

  test('complete manual whitelist review and failed review produce distinct statuses',async({page})=>{
    await page.goto('/');
    await page.locator('#promptInput').fill('Create a 2 second 16:9 video.');
    await page.locator('#videoInput').setInputFiles(media);
    await expect(page.locator('#videoQaStatus')).toContainText('YOUR TURN',{timeout:20000});
    await page.locator('#textChecklist .qa-choice[data-result=pass]').last().click();
    await expect(page.locator('#videoQaStatus')).toContainText('VERIFY SOUND');
    await page.locator('#textChecklist .qa-choice[data-result=fail]').last().click();
    await expect(page.locator('#videoQaStatus')).toContainText('TEXT ISSUE');
  });

  test('CSP-compatible failure deletion and local storage persist correctly',async({page})=>{
    await page.goto('/');
    await page.locator('details.advanced > summary').click();
    await page.locator('#failureCategory').fill('timing');
    await page.locator('#failureObserved').fill('too short');
    await page.locator('#failureExpected').fill('exact length');
    await page.locator('#saveFailureBtn').click();
    await expect(page.locator('#failureList')).toContainText('too short');
    await page.locator('#failureList .memory-delete').click();
    await expect(page.locator('#failureList')).toContainText('No bloopers saved');
  });
});
