// Tiny reusable game sounds (WebAudio, no dependencies).
//
// The project has no established sound system (audio/ports.py is a TTS
// boundary only), so this is the smallest reusable solution: short
// synthesized blips played from user-gesture handlers. Never throws,
// never blocks gameplay, creates one shared AudioContext lazily, and
// respects autoplay policies by resuming inside the gesture when needed.

let ctx: AudioContext | null = null;

function context(): AudioContext | null {
  try {
    const AC =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AC) return null;
    ctx ??= new AC();
    if (ctx.state === "suspended") void ctx.resume().catch(() => null);
    return ctx;
  } catch {
    return null;
  }
}

function blip(frequency: number, durationMs: number, type: OscillatorType, gainValue: number): void {
  const ac = context();
  if (!ac) return;
  try {
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.type = type;
    osc.frequency.value = frequency;
    const now = ac.currentTime;
    gain.gain.setValueAtTime(gainValue, now);
    gain.gain.exponentialRampToValueAtTime(0.001, now + durationMs / 1000);
    osc.connect(gain);
    gain.connect(ac.destination);
    osc.start(now);
    osc.stop(now + durationMs / 1000);
  } catch {
    // Audio must never break gameplay.
  }
}

/** Short error buzz for illegal moves. Safe to call from any handler. */
export function playError(): void {
  blip(180, 140, "square", 0.06);
}

/** Brief success chime when the piece reaches the star. */
export function playSuccess(): void {
  blip(660, 110, "sine", 0.07);
}

/** Reset the shared context (tests only). */
export function __resetSoundForTests(): void {
  try {
    ctx?.close().catch(() => null);
  } catch {
    // ignore
  }
  ctx = null;
}
