/* Headless viewport QA for Exercise 18 trapped-pieces (not part of the app bundle).
 * Run: backend on :8000, `vite dev` on :5173, then `node qa/trapped-pieces.cjs`.
 * Measures real rendered geometry in system Chrome across the required
 * viewport matrix, both modes, plus interaction passes (practice
 * multi-select + confirm; speed tap-to-submit with no confirm button). */
const puppeteer = require("puppeteer-core");

const VIEWPORTS = [
  [1920, 1080],
  [1366, 768],
  [1024, 768],
  [768, 1024],
  [390, 844],
  [360, 800],
  [844, 390],
];
const EXE = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const APP = "http://localhost:5173";

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
      shell: r('[data-testid="game-shell"]'),
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
  await page.goto(`${APP}/exercises/trapped-pieces?mode=${mode}`, {
    waitUntil: "networkidle0",
    timeout: 60000,
  });
  await page.waitForSelector('[data-testid="chessboard"]', { timeout: 30000 });
  await page.waitForSelector('[data-testid="question"]', { timeout: 30000 });
  if (mode === "speed") {
    await page.waitForSelector('[data-testid="timer"]', { timeout: 90000 });
  } else {
    await page.waitForSelector('[data-testid="submit-bar"]', { timeout: 30000 });
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
        check(`${tag} no-js-errors`, errors.length === 0, errors.join(" | ").slice(0, 200));
        await page.close();
      }
    }

    // Interaction pass: practice at 390x844 — select two, confirm, feedback, next.
    {
      const tag = "interact practice 390x844";
      const { page } = await loadMode(browser, 390, 844, "practice");
      const posts = [];
      page.on("response", (r) => {
        if (r.url().includes("/attempts") && r.request().method() === "POST") posts.push(r.status());
      });
      const before = await page.$('[data-testid="feedback"]');
      check(`${tag} no-answer-before-submit`, before === null, "feedback hidden");
      await page.click('[aria-label="a1"]');
      await page.click('[aria-label="c8"]');
      const pressed = await page.evaluate(() =>
        document.querySelector('[aria-label="a1"]').getAttribute("aria-pressed"),
      );
      check(`${tag} multi-select-visible`, pressed === "true", String(pressed));
      await page.click("button::-p-text(بررسی جواب)");
      await page.waitForSelector('[data-testid="feedback"]', { timeout: 15000 });
      check(`${tag} feedback-shown`, posts.length === 1, JSON.stringify(posts));
      await page.click("button::-p-text(معمای بعدی)");
      await page.waitForSelector('[data-testid="submit-bar"]', { timeout: 15000 });
      check(`${tag} next-puzzle`, true);
      await page.close();
    }

    // Interaction pass: speed at 390x844 — one tap submits (no confirm
    // button exists), auto-advance, tap again.
    {
      const tag = "interact speed 390x844";
      const { page } = await loadMode(browser, 390, 844, "speed");
      const submits = [];
      page.on("response", (r) => {
        if (r.url().includes("/submit") && r.request().method() === "POST") submits.push(r.status());
      });
      const confirm = await page.$("button::-p-text(بررسی جواب)");
      check(`${tag} no-confirm-button`, confirm === null, "tap submits directly");
      await page.click('[aria-label="e2"]');
      await new Promise((r) => setTimeout(r, 1500));
      check(`${tag} tap-submitted`, submits.length === 1, JSON.stringify(submits));
      check(`${tag} auto-advanced`, !!(await page.$('[data-testid="submit-bar"]')), "answering again");
      await page.click('[aria-label="e4"]');
      await new Promise((r) => setTimeout(r, 1500));
      check(`${tag} second-tap-submitted`, submits.length === 2, JSON.stringify(submits));
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
