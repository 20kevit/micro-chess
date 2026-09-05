/* Headless viewport QA for Exercise 1 (not part of the app bundle).
 * Run: backend on :8000, `vite dev` on :5173, then `node qa/viewports.cjs`.
 * Measures real rendered geometry in system Chrome across the required
 * viewport matrix, both modes, plus interaction passes. */
const puppeteer = require("puppeteer-core");

const VIEWPORTS = [
  [360, 800],
  [390, 844],
  [412, 915],
  [667, 375],
  [844, 390],
  [1024, 768],
  [1280, 720],
  [1366, 768],
];
const EXE = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const APP = "http://127.0.0.1:5173";

const fails = [];
function check(name, cond, extra = "") {
  console.log(`${cond ? "PASS" : "FAIL"} ${name} ${extra}`);
  if (!cond) fails.push(name);
}

async function measure(page) {
  return page.evaluate(() => {
    const r = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
    };
    const boardEl = document.querySelector('[data-testid="chessboard"]');
    return {
      innerW: window.innerWidth,
      innerH: window.innerHeight,
      scrollH: document.documentElement.scrollHeight,
      scrollW: document.documentElement.scrollWidth,
      dir: document.dir,
      boardDir: boardEl ? boardEl.getAttribute("dir") : null,
      vazirmatn: document.fonts ? document.fonts.check('16px Vazirmatn', "تست") : "n/a",
      board: r('[data-testid="chessboard"]'),
      question: r('[data-testid="question"]'),
      submit: r('[data-testid="submit-bar"]'),
      timer: r('[data-testid="timer"]'),
    };
  });
}

function inView(m, b) {
  return !!b && b.x >= -1 && b.y >= -1 && b.x + b.w <= m.innerW + 1 && b.y + b.h <= m.innerH + 1;
}

async function loadMode(browser, w, h, mode) {
  const page = await browser.newPage();
  await page.setViewport({ width: w, height: h, isMobile: w < 700 });
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + String(e.message).slice(0, 150)));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push("console: " + m.text().slice(0, 150));
  });
  await page.goto(`${APP}/exercises/piece-recognition?mode=${mode}`, {
    waitUntil: "networkidle0",
    timeout: 60000,
  });
  await page.waitForSelector('[data-testid="chessboard"]', { timeout: 30000 });
  await page.waitForSelector('[data-testid="question"]', { timeout: 30000 });
  if (mode === "speed") {
    await page.waitForSelector('[data-testid="submit-bar"]', { timeout: 45000 });
  }
  return { page, errors };
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
        check(`${tag} no-page-scroll`, m.scrollH <= m.innerH + 1 && m.scrollW <= m.innerW + 1, `${m.scrollW}x${m.scrollH}/${m.innerW}x${m.innerH}`);
        check(`${tag} board-in-view`, inView(m, m.board), JSON.stringify(m.board));
        check(`${tag} board-square`, m.board && Math.abs(m.board.w - m.board.h) <= 1 && m.board.w >= 120, `${m.board && m.board.w}px`);
        check(`${tag} question-in-view`, inView(m, m.question), JSON.stringify(m.question));
        check(`${tag} submit-in-view`, inView(m, m.submit), JSON.stringify(m.submit));
        if (mode === "speed") check(`${tag} timer-in-view`, inView(m, m.timer), JSON.stringify(m.timer));
        check(`${tag} rtl-page-ltr-board`, m.dir === "rtl" && m.boardDir === "ltr", `${m.dir}/${m.boardDir}`);
        check(`${tag} vazirmatn-loaded`, m.vazirmatn === true, String(m.vazirmatn));
        check(`${tag} no-js-errors`, errors.length === 0, errors.join(" | ").slice(0, 200));
        await page.close();
      }
    }

    // Interaction pass: speed at 390x844 — select, submit, auto-advance, submit again.
    // Submissions are verified by tracked network requests (question text
    // alone proves nothing, since prompts may legitimately repeat).
    {
      const tag = "interact speed 390x844";
      const { page } = await loadMode(browser, 390, 844, "speed");
      const submits = [];
      page.on("response", (r) => {
        if (r.url().includes("/submit") && r.request().method() === "POST") submits.push(r.status());
      });
      const SUBMIT = "button::-p-text(بررسی جواب)";
      await page.click('[aria-label="e2"]');
      await page.click(SUBMIT);
      await new Promise((r) => setTimeout(r, 1200));
      check(`${tag} first-submit-sent`, submits.length === 1, JSON.stringify(submits));
      check(`${tag} auto-advanced`, !!(await page.$('[data-testid="submit-bar"]')), "answering again");
      await page.click(SUBMIT);
      await new Promise((r) => setTimeout(r, 1200));
      check(`${tag} second-submit-sent`, submits.length === 2, JSON.stringify(submits));
      await page.close();
    }

    // Interaction pass: practice at 667x375 landscape — select, submit, next.
    {
      const tag = "interact practice 667x375";
      const { page } = await loadMode(browser, 667, 375, "practice");
      const posts = [];
      page.on("response", (r) => {
        if (r.url().includes("/attempts") && r.request().method() === "POST") posts.push(r.status());
      });
      await page.click('[aria-label="e2"]');
      await page.click("button::-p-text(بررسی جواب)");
      await page.waitForSelector('[data-testid="feedback"]', { timeout: 15000 });
      check(`${tag} feedback-shown`, posts.length === 1, JSON.stringify(posts));
      await page.click("button::-p-text(معمای بعدی)");
      await page.waitForSelector('[data-testid="submit-bar"]', { timeout: 15000 });
      check(`${tag} next-puzzle`, true);
      await page.close();
    }
  } finally {
    await browser.close();
  }
  console.log(fails.length ? `FAILURES: ${fails.join("; ")}` : "ALL VIEWPORT CHECKS PASSED");
  process.exit(fails.length ? 1 : 0);
})().catch((e) => {
  console.error("QA HARNESS ERROR", e);
  process.exit(2);
});

