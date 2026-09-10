/* Headless viewport QA for shared-ExercisePlay screens (not part of the app bundle).
 * Run: backend on :8000 (pin + trapped-pieces + is-checkmate +
 * castling-rights seeded), `vite dev` on :5173, then `node qa/exercise-play.cjs`.
 * Measures real rendered geometry in system Chrome across the required
 * viewport matrix: no page scroll, board + prompt + controls + feedback
 * all inside the visible viewport, plus a full Pin answer cycle. */
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
// Split long runs: QA_ONLY="390x844,844x390" runs a subset;
// QA_INTERACT=0 skips the interaction passes.
const ONLY = process.env.QA_ONLY ? process.env.QA_ONLY.split(",") : null;
const SIZES = ONLY
  ? VIEWPORTS.filter(([w, h]) => ONLY.includes(`${w}x${h}`))
  : VIEWPORTS;
const WITH_INTERACT = process.env.QA_INTERACT !== "0";
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
    const btn = (text) => {
      const el = Array.from(document.querySelectorAll("button")).find((b) =>
        (b.textContent || "").includes(text),
      );
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
      board: r('[data-testid="chessboard"]'),
      question: r('[data-testid="question"]'),
      submit: r('[data-testid="submit-bar"]'),
      feedback: r('[data-testid="feedback"]'),
      submitBtn: btn("بررسی جواب"),
      nextBtn: btn("معمای بعدی"),
      startBtn: btn("شروع"),
    };
  });
}

function inView(m, b) {
  return !!b && b.x >= -1 && b.y >= -1 && b.x + b.w <= m.innerW + 1 && b.y + b.h <= m.innerH + 1;
}

async function openPage(browser, w, h, path) {
  const page = await browser.newPage();
  await page.setViewport({ width: w, height: h, isMobile: w < 700, hasTouch: w < 700 });
  const errors = [];
  page.on("pageerror", (e) => errors.push("pageerror: " + String(e && e.message).slice(0, 120)));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push("console: " + m.text().slice(0, 120));
  });
  await page.goto(`${APP}${path}`, { waitUntil: "networkidle0", timeout: 60000 });
  return { page, errors };
}

(async () => {
  const browser = await puppeteer.launch({ executablePath: EXE, args: ["--no-sandbox"] });
  try {
    // Pin play screen (direct play, no entry): answering layout.
    for (const [w, h] of SIZES) {
      const tag = `pin ${w}x${h} answering`;
      const { page, errors } = await openPage(browser, w, h, "/exercises/pin");
      try {
        await page.waitForSelector('[data-testid="chessboard"]', { timeout: 30000 });
        await page.waitForSelector('[data-testid="submit-bar"]', { timeout: 30000 });
        const m = await measure(page);
        check(`${tag} no-page-scroll`, m.scrollH <= m.innerH + 1 && m.scrollW <= m.innerW + 1, `${m.scrollW}x${m.scrollH}/${m.innerW}x${m.innerH}`);
        check(`${tag} board-in-view`, inView(m, m.board), JSON.stringify(m.board));
        check(`${tag} board-square`, m.board && Math.abs(m.board.w - m.board.h) <= 1 && m.board.w >= 100, `${m.board && m.board.w}px`);
        check(`${tag} question-in-view`, inView(m, m.question), JSON.stringify(m.question));
        check(`${tag} submit-in-view`, inView(m, m.submitBtn), JSON.stringify(m.submitBtn));
        check(`${tag} rtl-page-ltr-board`, m.dir === "rtl" && m.boardDir === "ltr", `${m.dir}/${m.boardDir}`);
        check(`${tag} no-js-errors`, errors.length === 0, errors.join(" | ").slice(0, 200));
      } finally {
        await page.close();
      }
    }

    // Sibling ExercisePlay screens: entry overlay fits (start button visible).
    for (const slug of ["trapped-pieces", "is-checkmate", "castling-rights"]) {
      for (const [w, h] of SIZES) {
        const tag = `${slug} ${w}x${h} entry`;
        const { page, errors } = await openPage(browser, w, h, `/exercises/${slug}`);
        try {
          await page.waitForFunction(
            () => Array.from(document.querySelectorAll("button")).some((b) => (b.textContent || "").includes("شروع")),
            { timeout: 30000 },
          );
          const m = await measure(page);
          check(`${tag} no-page-scroll`, m.scrollH <= m.innerH + 1 && m.scrollW <= m.innerW + 1, `${m.scrollW}x${m.scrollH}/${m.innerW}x${m.innerH}`);
          check(`${tag} start-in-view`, inView(m, m.startBtn), JSON.stringify(m.startBtn));
          check(`${tag} no-js-errors`, errors.length === 0, errors.join(" | ").slice(0, 200));
        } finally {
          await page.close();
        }
      }
    }

    // Sibling play screens (after entry): answering layout fits.
    for (const slug of ["trapped-pieces", "is-checkmate", "castling-rights"]) {
      for (const [w, h] of SIZES) {
        const tag = `${slug} ${w}x${h} answering`;
        const { page, errors } = await openPage(browser, w, h, `/exercises/${slug}`);
        try {
          await page.waitForFunction(
            () => Array.from(document.querySelectorAll("button")).some((b) => (b.textContent || "").includes("شروع")),
            { timeout: 30000 },
          );
          await page.evaluate(() => {
            const btn = Array.from(document.querySelectorAll("button")).find((b) =>
              (b.textContent || "").includes("شروع"),
            );
            if (btn) btn.click();
          });
          await page.waitForSelector('[data-testid="chessboard"]', { timeout: 30000 });
          const m = await measure(page);
          check(`${tag} no-page-scroll`, m.scrollH <= m.innerH + 1 && m.scrollW <= m.innerW + 1, `${m.scrollW}x${m.scrollH}/${m.innerW}x${m.innerH}`);
          check(`${tag} board-in-view`, inView(m, m.board), JSON.stringify(m.board));
          check(`${tag} question-in-view`, inView(m, m.question), JSON.stringify(m.question));
          check(`${tag} submit-in-view`, inView(m, m.submitBtn), JSON.stringify(m.submitBtn));
          check(`${tag} no-js-errors`, errors.length === 0, errors.join(" | ").slice(0, 200));
        } finally {
          await page.close();
        }
      }
    }

    // Balance Scale practice (generator-backed, no seed needed): whole
    // scale + inventory experience fits without page scrolling.
    for (const [w, h] of SIZES) {
      const tag = `balance-scale ${w}x${h} practice`;
      const { page, errors } = await openPage(browser, w, h, "/exercises/balance-scale?mode=practice");
      try {
        await page.waitForSelector('[data-testid="balance-scale"]', { timeout: 30000 });
        await page.waitForSelector('[data-testid="inventory"]', { timeout: 30000 });
        const m = await measure(page);
        const extra = await page.evaluate(() => {
          const r = (sel) => {
            const el = document.querySelector(sel);
            if (!el) return null;
            const b = el.getBoundingClientRect();
            return { x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.width), h: Math.round(b.height) };
          };
          return { scale: r('[data-testid="balance-scale"]'), inv: r('[data-testid="inventory"]') };
        });
        check(`${tag} no-page-scroll`, m.scrollH <= m.innerH + 1 && m.scrollW <= m.innerW + 1, `${m.scrollW}x${m.scrollH}/${m.innerW}x${m.innerH}`);
        check(`${tag} scale-in-view`, inView(m, extra.scale), JSON.stringify(extra.scale));
        check(`${tag} inventory-in-view`, inView(m, extra.inv), JSON.stringify(extra.inv));
        check(`${tag} no-js-errors`, errors.length === 0, errors.join(" | ").slice(0, 200));
      } finally {
        await page.close();
      }
    }

    if (WITH_INTERACT) {
      // Full Pin cycle (portrait + landscape): pick 3, submit, feedback + next visible.
      for (const [w, h] of SIZES.filter(([ww, hh]) => (ww === 390 && hh === 844) || (ww === 844 && hh === 390))) {
        const tag = `interact pin ${w}x${h}`;
        const { page } = await openPage(browser, w, h, "/exercises/pin");
        try {
          await page.waitForSelector('[data-testid="chessboard"]', { timeout: 30000 });
          const posts = [];
          page.on("response", (r) => {
            if (r.url().includes("/attempts") && r.request().method() === "POST") posts.push(r.status());
          });
          await page.click('[aria-label="e1"]');
          await page.click('[aria-label="e6"]');
          await page.click('[aria-label="e8"]');
          await page.click("button::-p-text(بررسی جواب)");
          await page.waitForSelector('[data-testid="feedback"]', { timeout: 15000 });
          const m = await measure(page);
          check(`${tag} attempt-graded`, posts.length === 1, JSON.stringify(posts));
          check(`${tag} feedback-in-view`, inView(m, m.feedback), JSON.stringify(m.feedback));
          check(`${tag} next-in-view`, inView(m, m.nextBtn), JSON.stringify(m.nextBtn));
          check(`${tag} no-page-scroll-after-feedback`, m.scrollH <= m.innerH + 1 && m.scrollW <= m.innerW + 1, `${m.scrollW}x${m.scrollH}/${m.innerW}x${m.innerH}`);
          await page.click("button::-p-text(معمای بعدی)");
          await page.waitForSelector('[data-testid="submit-bar"]', { timeout: 15000 });
          check(`${tag} next-puzzle`, true);
        } finally {
          await page.close();
        }
      }
    }
  } finally {
    await browser.close();
  }
  console.log(fails.length ? `FAILURES: ${fails.join("; ")}` : "ALL EXERCISE-PLAY CHECKS PASSED");
  process.exit(fails.length ? 1 : 0);
})().catch((e) => {
  console.error("QA HARNESS ERROR", e);
  process.exit(2);
});
