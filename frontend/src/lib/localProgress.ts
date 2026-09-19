// Local progress log for authenticated practice (client-side convenience).
// Guest practice is disabled product-wide: exercise routes require login
// and the server rejects guest/anonymous submits, so this log is only ever
// written after an authenticated attempt. Stored in browser now; the server
// remains the source of truth for accounts.
const KEY = "microchess.localProgress.v1";

export interface LocalProgress {
  attempts: Array<{ puzzleId: number; score: number; at: string }>;
}

export function loadLocalProgress(): LocalProgress {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { attempts: [] };
    return JSON.parse(raw) as LocalProgress;
  } catch {
    return { attempts: [] };
  }
}

export function savePracticeAttempt(puzzleId: number, score: number): void {
  const current = loadLocalProgress();
  current.attempts.push({ puzzleId, score, at: new Date().toISOString() });
  try {
    localStorage.setItem(KEY, JSON.stringify(current));
  } catch {
    // Storage full/blocked: ignore, server remains source of truth for accounts.
  }
}
