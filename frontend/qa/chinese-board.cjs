/* Headless viewport + interaction QA for Exercise 13 Chinese Board.
 * Run: backend on :8000 (any fresh DB; /chinese-board/next generates),
 * `vite dev` on :5173, then `node qa/chinese-board.cjs`.
 * Measures real rendered geometry in system Chrome across the required
 * viewport matrix, both modes, plus memorize -> rebuild -> check passes. */
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

async function measure(page) {
  return page.evaluate(() => {
    const r = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const b = el.getBoundingClientRect();
      return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
    };
    const boardEl = document.querySelector('[data-testid="chessboard"]');
    const pieces = (sel) =>
      Array.from(document.querySelectorAll(`${sel} img`)).length;
    return {
      innerW: window.innerWidth,
      innerH: window.innerHeight,
      scrollH: document.documentElement.scrollHeight,
      scrollW: document.documentElement.scrollWidth,
      dir: document.dir,
      boardDir: boardEl ? boardEl.getAttribute("dir") : null,
      vazirmatn: document.fonts ? document.fonts.check("16px Vazirmatn", "تست") : "n/a",
      board: r('[data-testid="chessboard"]'),
      question: r('[data-testid="question"]'),
      progress: r('[data-testid="memorize-progress"]'),
      submit: r('[data-testid="submit-bar"]'),
      next: r('[data-testid="next-bar"]'),
      feedback: r('[data-testid="feedback"]'),
      timer: r('[data-testid="timer"]'),
      memorizePieces: pieces('[data-testid="chessboard"]'),
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
  await page.goto(`${APP}/exercises/chinese-board?mode=${mode}`, {
    waitUntil: "networkidle0",
    timeout: 60000,
  });
  await page.waitForSelector('[data-testid="chessboard"]', { timeout: 30000 });
  await page.waitForSelector('[data-testid="question"]', { timeout: 30000 });
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
        // Memorize phase: progress + full position visible.
        let m = await measure(page);
        check(`${tag} memorize-progress`, !!m.progress, JSON.stringify(m.progress));
        check(`${tag} memorize-shows-pieces`, m.memorizePieces >= 4, `${m.memorizePieces} imgs`);
        check(`${tag} no-page-scroll`, m.scrollH <= m.innerH + 1 && m.scrollW <= m.innerW + 1, `${m.scrollW}x${m.scrollH}/${m.innerW}x${m.innerH}`);
        check(`${tag} board-in-view`, inView(m, m.board), JSON.stringify(m.board));
        check(`${tag} board-square`, m.board && Math.abs(m.board.w - m.board.h) <= 1 && m.board.w >= 120, `${m.board && m.board.w}px`);
        check(`${tag} rtl-page-ltr-board`, m.dir === "rtl" && m.boardDir === "ltr", `${m.dir}/${m.boardDir}`);
        check(`${tag} vazirmatn-loaded`, m.vazirmatn === true, String(m.vazirmatn));
        // Wait out the study budget (max ~9.6s on real data) + fade.
        try {
          await page.waitForSelector('[data-testid="submit-bar"]', { timeout: 20000 });
        } catch (e) {
          check(`${tag} reaches-rebuild`, false, "submit-bar never appeared");
          await page.close();
          continue;
        }
        m = await measure(page);
        check(`${tag} board-cleared`, m.memorizePieces === 0, `${m.memorizePieces} imgs`);
        check(`${tag} board-still-in-view`, inView(m, m.board), JSON.stringify(m.board));
        check(`${tag} no-page-scroll-rebuild`, m.scrollH <= m.innerH + 1 && m.scrollW <= m.innerW + 1, `${m.scrollW}x${m.scrollH}/${m.innerW}x${m.innerH}`);
        check(`${tag} no-js-errors`, errors.length === 0, errors.join(" | ").slice(0, 200));
        await page.close();
      }
    }

    // Interaction pass: practice at 390x844 — place, replace, erase, check, next.
    {
      const tag = "interact practice 390x844";
      const { page } = await loadMode(browser, 390, 844, "practice");
      const posts = [];
      page.on("response", (r) => {
        if (r.url().includes("/attempts") && r.request().method() === "POST") posts.push(r.status());
      });
      await page.waitForSelector('[data-testid="submit-bar"]', { timeout: 20000 });
      // Place white queen on e4, replace with black knight, erase it.
      await page.click('[aria-label="سفید وزیر"]');
      await page.click('[aria-label="e4"]');
      let imgs = await page.$$eval('[aria-label="e4"] img', (els) => els.map((e) => e.src));
      check(`${tag} place`, imgs.length === 1 && imgs[0].includes("wQ"), JSON.stringify(imgs));
      await page.click('[aria-label="سیاه اسب"]');
      await page.click('[aria-label="e4"]');
      imgs = await page.$$eval('[aria-label="e4"] img', (els) => els.map((e) => e.src));
      check(`${tag} replace`, imgs.length === 1 && imgs[0].includes("bN"), JSON.stringify(imgs));
      await page.click('[aria-label="پاک‌کن"]');
      await page.click('[aria-label="e4"]');
      imgs = await page.$$eval('[aria-label="e4"] img', (els) => els.map((e) => e.src));
      check(`${tag} erase`, imgs.length === 0, JSON.stringify(imgs));
      // Place one piece and check: the payload must be pieces-only.
      let payload = null;
      await page.setRequestInterception(true);
      page.on("request", (req) => {
        if (req.url().includes("/attempts") && req.method() === "POST") {
          payload = req.postData();
        }
        req.continue();
      });
      await page.click('[aria-label="سفید وزیر"]');
      await page.click('[aria-label="d1"]');
      await page.click("button::-p-text(بررسی صفحه)");
      await page.waitForSelector('[data-testid="feedback"]', { timeout: 15000 });
      check(`${tag} feedback-shown`, posts.length === 1, JSON.stringify(posts));
      let parsed = null;
      try {
        parsed = JSON.parse(payload).answer;
      } catch (e) {
        parsed = null;
      }
      check(
        `${tag} pieces-only-payload`,
        !!parsed && Object.keys(parsed).join(",") === "pieces" && parsed.pieces.length === 1,
        String(payload).slice(0, 160),
      );
      // Manual next (no auto-advance in practice).
      await page.click("button::-p-text(صفحه بعدی)");
      await page.waitForSelector('[data-testid="memorize-progress"]', { timeout: 15000 });
      check(`${tag} next-puzzle`, true);
      await page.close();
    }

    // Interaction pass: speed at 390x844 — memorize, check, auto-advance.
    {
      const tag = "interact speed 390x844";
      const { page } = await loadMode(browser, 390, 844, "speed");
      const submits = [];
      page.on("response", (r) => {
        if (r.url().includes("/submit") && r.request().method() === "POST") submits.push(r.status());
      });
      await page.waitForSelector('[data-testid="timer"]', { timeout: 45000 });
      await page.waitForSelector('[data-testid="submit-bar"]', { timeout: 20000 });
      await page.click('[aria-label="سفید وزیر"]');
      await page.click('[aria-label="d1"]');
      await page.click("button::-p-text(بررسی صفحه)");
      await page.waitForSelector('[data-testid="feedback"]', { timeout: 15000 });
      check(`${tag} submit-sent`, submits.length === 1, JSON.stringify(submits));
      // Brief feedback then automatic transition (no manual button in speed).
      await page.waitForSelector('[data-testid="memorize-progress"]', { timeout: 15000 });
      check(`${tag} auto-advanced`, true);
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
