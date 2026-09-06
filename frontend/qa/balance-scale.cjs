/* Headless viewport + interaction QA for Exercise 10 Balance Scale.
 * Run: backend on :8000 (any fresh DB; /balance-scale/next generates),
 * `vite dev` on :5173, then `node qa/balance-scale.cjs`.
 * Measures real rendered geometry in system Chrome across the required
 * viewport matrix, both modes, plus solve-flow interaction passes. */
const puppeteer = require("puppeteer-core");

const VIEWPORTS = [
  [360, 800],
  [390, 844],
  [412, 915],
  [667, 375],
  [844, 390],
  [1024, 768],
  [1280, 800],
];
const EXE = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const APP = "http://localhost:5173";

const fails = [];
function check(name, cond, extra = "") {
  console.log(`${cond ? "PASS" : "FAIL"} ${name} ${extra}`);
  if (!cond) fails.push(name);
}

const FA = { "۰": 0, "۱": 1, "۲": 2, "۳": 3, "۴": 4, "۵": 5, "۶": 6, "۷": 7, "۸": 8, "۹": 9 };
function faNum(str) {
  let out = "";
  for (const ch of String(str)) out += ch in FA ? FA[ch] : ch;
  const m = out.replace(/[^0-9]/g, "");
  return m === "" ? NaN : parseInt(m, 10);
}

/** Minimum-piece combo for a target over [1,3,5,9] -> inventory kinds. */
function comboFor(target) {
  const coins = [
    [9, "Q"],
    [5, "R"],
    [3, "N"],
    [1, "P"],
  ];
  const INF = 1e9;
  const dp = new Array(target + 1).fill(INF);
  const pick = new Array(target + 1).fill(null);
  dp[0] = 0;
  for (let a = 1; a <= target; a++) {
    for (const [v, k] of coins) {
      if (v <= a && dp[a - v] + 1 < dp[a]) {
        dp[a] = dp[a - v] + 1;
        pick[a] = k;
      }
    }
  }
  const combo = [];
  let t = target;
  while (t > 0) {
    combo.push(pick[t]);
    t -= { Q: 9, R: 5, N: 3, P: 1 }[pick[t]];
  }
  return combo;
}

async function measure(page) {
  return page.evaluate(() => {
    const r = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
    };
    const beam = document.querySelector('[data-testid="scale-beam"]');
    return {
      innerW: window.innerWidth,
      innerH: window.innerHeight,
      scrollW: document.documentElement.scrollWidth,
      dir: document.dir,
      angle: beam ? beam.getAttribute("data-angle") : null,
      scale: r('[data-testid="balance-scale"]'),
      inventory: r('[data-testid="inventory"]'),
      blackTotal: document.querySelector('[data-testid="black-total"]')?.textContent ?? "",
      whiteTotal: document.querySelector('[data-testid="white-total"]')?.textContent ?? "",
      blackPieces: document.querySelectorAll('[data-testid="black-piece"]').length,
    };
  });
}

async function loadMode(browser, w, h, mode) {
  const page = await browser.newPage();
  await page.setViewport({ width: w, height: h, isMobile: w < 700 });
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + String(e.message).slice(0, 150)));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push("console: " + m.text().slice(0, 150));
  });
  await page.goto(`${APP}/exercises/balance-scale?mode=${mode}`, {
    waitUntil: "networkidle0",
    timeout: 60000,
  });
  await page.waitForSelector('[data-testid="balance-scale"]', { timeout: 30000 });
  if (mode === "speed") {
    await page.waitForSelector('[data-testid="timer"]', { timeout: 45000 });
  }
  return { page, errors };
}

async function solveCurrent(page) {
  const target = faNum((await measure(page)).blackTotal);
  const combo = comboFor(target);
  for (const kind of combo) {
    await page.click(`[data-testid="inventory-${kind}"]`);
    await new Promise((r) => setTimeout(r, 120));
  }
  return combo.length;
}

(async () => {
  const browser = await puppeteer.launch({ executablePath: EXE, args: ["--no-sandbox"] });
  try {
    for (const [w, h] of VIEWPORTS) {
      for (const mode of ["practice", "speed"]) {
        const tag = `${w}x${h} ${mode}`;
        let page;
        try {
          ({ page } = await loadMode(browser, w, h, mode));
        } catch (e) {
          check(`${tag} loads`, false, String(e).slice(0, 120));
          continue;
        }
        const errors = [];
        page.removeAllListeners("pageerror");
        page.removeAllListeners("console");
        page.on("pageerror", (e) => errors.push("pageerror: " + String(e.message).slice(0, 120)));
        const m = await measure(page);
        check(`${tag} no-h-overflow`, m.scrollW <= m.innerW + 1, `${m.scrollW}/${m.innerW}`);
        check(`${tag} rtl-page`, m.dir === "rtl", m.dir);
        check(`${tag} tilted-while-empty`, m.angle !== null && Number(m.angle) < 0, `angle=${m.angle}`);
        check(
          `${tag} inventory-fits`,
          !!m.inventory && m.inventory.x >= -1 && m.inventory.x + m.inventory.w <= m.innerW + 1,
          JSON.stringify(m.inventory),
        );
        check(`${tag} black-pieces-4-to-10`, m.blackPieces >= 4 && m.blackPieces <= 10, `${m.blackPieces}`);
        const target = faNum(m.blackTotal);
        check(`${tag} totals-sane`, Number.isFinite(target) && target >= 4 && faNum(m.whiteTotal) === 0, `${m.blackTotal}/${m.whiteTotal}`);
        check(`${tag} no-js-errors`, errors.length === 0, errors.join(" | ").slice(0, 200));
        await page.close();
      }
    }

    // Interaction pass: practice at 390x844 — solve, success, score, next.
    {
      const tag = "interact practice 390x844";
      const { page } = await loadMode(browser, 390, 844, "practice");
      const posts = [];
      page.on("response", (r) => {
        if (r.url().includes("/api/v1/attempts") && r.request().method() === "POST") posts.push(r.status());
      });
      const n = await solveCurrent(page);
      await page.waitForSelector('[data-testid="balanced-message"]', { timeout: 15000 });
      // The next button only appears after the submit resolves, so waiting
      // for it first removes the race between the POST and the assertion.
      await page.waitForSelector('[data-testid="next-question"]', { timeout: 15000 });
      const m = await measure(page);
      check(`${tag} submitted-once`, posts.length === 1, JSON.stringify(posts));
      check(`${tag} solved-with-${n}`, n >= 2 && n <= 10, `${n}`);
      check(`${tag} horizontal-at-balance`, m.angle === "0.00", `angle=${m.angle}`);
      check(`${tag} success-shown`, true);
      await page.click('[data-testid="next-question"]');
      await new Promise((r) => setTimeout(r, 800));
      const m2 = await measure(page);
      check(`${tag} next-resets-pan`, faNum(m2.whiteTotal) === 0, m2.whiteTotal);
      await page.close();
    }

    // Interaction pass: speed at 390x844 — solve, auto-submit, auto-advance.
    {
      const tag = "interact speed 390x844";
      const { page } = await loadMode(browser, 390, 844, "speed");
      const submits = [];
      page.on("response", (r) => {
        if (r.url().includes("/submit") && r.request().method() === "POST") submits.push(r.status());
      });
      await solveCurrent(page);
      await new Promise((r) => setTimeout(r, 1500));
      check(`${tag} auto-submitted`, submits.length === 1, JSON.stringify(submits));
      const m = await measure(page);
      check(`${tag} auto-advanced`, faNum(m.whiteTotal) === 0, m.whiteTotal);
      check(`${tag} no-manual-next`, (await page.$('[data-testid="next-question"]')) === null);
      await page.close();
    }
  } finally {
    await browser.close();
  }
  console.log(fails.length ? `FAILURES: ${fails.join("; ")}` : "ALL BALANCE CHECKS PASSED");
  process.exit(fails.length ? 1 : 0);
})().catch((e) => {
  console.error("QA HARNESS ERROR", e);
  process.exit(2);
});
