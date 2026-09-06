import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, apiDetail, apiStatus } from "../../api/client";
import type { AttemptResponse, Puzzle, SpeedReport, SpeedSummary } from "../../api/types";
import { t } from "../../i18n";
import { fenToPieces } from "../../lib/fen";
import { savePracticeAttempt } from "../../lib/localProgress";
import { playError, playSuccess } from "../../lib/sound";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import type { BoardMap } from "../chess/ChessBoard";
import { ChessBoard } from "../chess/ChessBoard";
import type { PieceSymbol } from "../chess/ChessPiece";
import { ChessPiece } from "../chess/ChessPiece";
import {
  GameShell,
  NextBar,
  PracticeFeedback,
  QuestionHeader,
  SpeedPill,
  TimerStrip,
  faNum,
  useGameFit,
  type DivRef,
} from "./PieceGameLayout";

export type ObstaclePathfindingMode = "practice" | "speed";

// Piece-movement animation: smooth glide from source to destination so
// every legal move feels like a chess move, never an instant jump.
// Speed mode animates faster than practice (spec requirement).
export const PRACTICE_ANIM_MS = 220;
export const SPEED_ANIM_MS = 110;
// How long the red illegal-destination highlight stays visible.
export const ILLEGAL_FLASH_MS = 700;
// How long speed success feedback shows before auto-advancing: very
// brief, then the next puzzle. No manual Next button in speed.
export const SPEED_FEEDBACK_MS = 400;

// Dedicated Practice + Speed loop for Pathfinding with Obstacles
// (Exercise 7). Renders and transports answers only; legality (movement,
// blocking, destination safety, capture rules), optimal counts, scoring,
// and the speed clock stay backend-authoritative. The ?mode= URL param
// picks the loop directly; there is no intermediate mode-selection screen.
//
// One white piece (knight/bishop/rook/queen) walks to the star while
// black enemies block rays, control destinations, and can be captured
// when undefended (captures change enemy control mid-puzzle). Primary
// input is drag-and-drop; click-select then click-destination works too.
// The piece STAYS selected after every move (legal or illegal), so
// destinations can be clicked repeatedly. Reaching the star auto-submits
// the full path as one attempt; the server recomputes the optimal
// distance and the score from scratch.
export function PathfindingObstaclesPlay({ mode }: { mode: ObstaclePathfindingMode }) {
  return mode === "practice" ? <PracticeLoop /> : <SpeedLoop />;
}

/** Public task data carried by a puzzle row (optimal counts never leave the server). */
export function obstaclePosOf(puzzle: Puzzle): {
  from: string;
  target: string;
  piece: string;
  enemies: { square: string; kind: string }[];
} {
  const pos = puzzle.position_json as Record<string, unknown>;
  const rawEnemies = Array.isArray(pos.enemies) ? pos.enemies : [];
  return {
    from: typeof pos.from === "string" ? pos.from : "",
    target: typeof pos.target === "string" ? pos.target : "",
    piece: typeof pos.piece === "string" ? pos.piece : "",
    enemies: rawEnemies
      .filter(
        (e): e is { square: string; kind: string } =>
          typeof e === "object" &&
          e !== null &&
          typeof (e as { square?: unknown }).square === "string" &&
          typeof (e as { kind?: unknown }).kind === "string",
      )
      .map((e) => ({ square: e.square, kind: e.kind })),
  };
}

/** Authoritative submission payload: the walked path + illegal-try count.
 * Never ships scores, optimal counts, or correctness flags. */
export function answerForPath(path: string[], illegalAttempts: number): {
  path: string[];
  illegal_attempts: number;
} {
  return { path, illegal_attempts: Math.max(0, illegalAttempts) };
}

/** Board-unit center of a square (white orientation, 0..8). Pure. */
export function squareCenter(square: string): { x: number; y: number } {
  const file = "abcdefgh".indexOf(square[0]);
  const rank = Number(square.slice(1));
  return { x: file + 0.5, y: 8 - rank + 0.5 };
}

interface Anim {
  from: string;
  to: string;
  symbol: PieceSymbol;
  key: number;
}

// Movement glide overlay: interpolates the piece from source to dest
// over animMs, then calls onDone exactly once. Timer-driven (no rAF),
// so it works identically on desktop/mobile and under fake timers.
function AnimOverlay({ anim, ms, onDone }: { anim: Anim; ms: number; onDone: () => void }) {
  const [pos, setPos] = useState(() => squareCenter(anim.from));
  const doneRef = useRef(onDone);
  doneRef.current = onDone;
  useEffect(() => {
    const start = Date.now();
    const id = window.setInterval(() => {
      const k = Math.min(1, (Date.now() - start) / Math.max(1, ms));
      const a = squareCenter(anim.from);
      const b = squareCenter(anim.to);
      setPos({ x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k });
      if (k >= 1) {
        window.clearInterval(id);
        doneRef.current();
      }
    }, 16);
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anim.key]);
  return (
    <span
      className="pointer-events-none absolute z-10 grid place-items-center"
      style={{
        left: `${(pos.x / 8) * 100}%`,
        top: `${(pos.y / 8) * 100}%`,
        width: "12.5%",
        aspectRatio: "1 / 1",
        transform: "translate(-50%, -50%)",
      }}
      aria-hidden="true"
      data-testid="move-anim"
    >
      <span className="block h-[92%] w-[92%]">
        <ChessPiece symbol={anim.symbol} />
      </span>
    </span>
  );
}

function PathBoard({
  areaRef,
  size,
  pieces,
  target,
  selectedAt,
  illegalFlash,
  anim,
  animMs,
  disabled,
  onMove,
  onPress,
  onAnimDone,
  overlay,
}: {
  areaRef: DivRef;
  size: number;
  pieces: BoardMap;
  target: string;
  selectedAt: string | null;
  illegalFlash: string | null;
  anim: Anim | null;
  animMs: number;
  disabled: boolean;
  onMove: (from: string, to: string) => void;
  onPress: (square: string) => void;
  onAnimDone: () => void;
  overlay?: ReactNode;
}) {
  const squareStates: Partial<
    Record<string, "selected" | "correct" | "missed" | "wrong" | "target">
  > = {};
  if (selectedAt) squareStates[selectedAt] = "selected";
  if (illegalFlash) squareStates[illegalFlash] = "wrong";
  // During the glide the piece is drawn by the overlay; hide the source
  // square copy so the piece never appears doubled.
  const shown: BoardMap = anim ? { ...pieces } : pieces;
  if (anim) delete shown[anim.from];
  return (
    <div ref={areaRef} className="relative min-h-0 min-w-0 flex-1" data-testid="board-zone">
      <div className="absolute inset-0 grid place-items-center">
        <div dir="ltr" data-testid="chessboard" style={{ width: size, height: size }}>
          <div className="relative h-full w-full">
            <ChessBoard
              pieces={shown}
              squareStates={squareStates}
              markers={target ? { [target]: "star" } : {}}
              disabled={disabled || anim !== null}
              draggablePieces
              draggableSquares={selectedAt ? [selectedAt] : []}
              arrowsEnabled={false}
              onMove={disabled ? undefined : onMove}
              onSquarePress={disabled ? undefined : onPress}
            />
            {anim ? <AnimOverlay anim={anim} ms={animMs} onDone={onAnimDone} /> : null}
          </div>
        </div>
      </div>
      {overlay}
    </div>
  );
}

function StatusLine({ moves, illegal }: { moves: number; illegal: number }) {
  return (
    <p className="shrink-0 px-3 text-center text-sm font-bold text-stone-600" data-testid="status-line">
      {t("pathfinding.moves")}: {faNum(moves)} · {t("pathfinding.illegal")}: {faNum(illegal)}
    </p>
  );
}

type PracticePhase = "loading" | "ready" | "submitting" | "feedback" | "error";

function PracticeLoop() {
  const [phase, setPhase] = useState<PracticePhase>("loading");
  const [current, setCurrent] = useState<Puzzle | null>(null);
  const [buffered, setBuffered] = useState<Puzzle | null>(null);
  const [fen, setFen] = useState<string | null>(null);
  const [selectedAt, setSelectedAt] = useState<string | null>(null);
  const [path, setPath] = useState<string[]>([]);
  const [illegal, setIllegal] = useState(0);
  const [illegalFlash, setIllegalFlash] = useState<string | null>(null);
  const [anim, setAnim] = useState<Anim | null>(null);
  const [stepBusy, setStepBusy] = useState(false);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>("");
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [solved, setSolved] = useState(0);
  const [scoreTotal, setScoreTotal] = useState(0);
  const genRef = useRef(0);
  const mountedRef = useRef(true);
  const currentIdRef = useRef<number | null>(null);
  const busyRef = useRef(false);
  const animKeyRef = useRef(0);
  const pendingRef = useRef<{ fen: string; selected_at: string; reached: boolean } | null>(null);
  const pathRef = useRef<string[]>([]);
  const illegalRef = useRef(0);
  const flashTimerRef = useRef<number | null>(null);
  const { rootRef, areaRef, orientation, size } = useGameFit();

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      genRef.current += 1;
      if (flashTimerRef.current !== null) window.clearTimeout(flashTimerRef.current);
    };
  }, []);

  function alive(gen: number) {
    return mountedRef.current && genRef.current === gen;
  }

  function resetFor(puzzle: Puzzle) {
    const pos = obstaclePosOf(puzzle);
    currentIdRef.current = puzzle.id;
    setCurrent(puzzle);
    setFen(puzzle.fen);
    setSelectedAt(pos.from);
    setPath(pos.from ? [pos.from] : []);
    pathRef.current = pos.from ? [pos.from] : [];
    setIllegal(0);
    illegalRef.current = 0;
    setIllegalFlash(null);
    setAnim(null);
    pendingRef.current = null;
    setStepBusy(false);
    setUsedHints([]);
    setResult(null);
    setError(null);
    setStartedAt(new Date().toISOString());
    setPhase("ready");
  }

  async function refill(exclude: number[]) {
    const gen = genRef.current;
    let next: Puzzle | null = null;
    try {
      next = await api.nextObstaclePracticePuzzle({ exclude_ids: exclude });
    } catch {
      return;
    }
    if (!alive(gen) || !next || next.id === currentIdRef.current) return;
    setBuffered(next);
  }

  async function loadInitial() {
    const gen = ++genRef.current;
    busyRef.current = false;
    setPhase("loading");
    setError(null);
    let first: Puzzle | null = null;
    try {
      first = await api.nextObstaclePracticePuzzle({ exclude_ids: [] });
    } catch {
      first = null;
    }
    if (!alive(gen)) return;
    if (!first) {
      setPhase("error");
      setError(t("common.error"));
      return;
    }
    resetFor(first);
    refill([first.id]);
  }

  useEffect(() => {
    loadInitial();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function advance() {
    if (busyRef.current) return;
    const gen = ++genRef.current;
    const next = buffered;
    if (next && (!current || next.id !== current.id)) {
      setBuffered(null);
      resetFor(next);
      refill([next.id]);
    } else {
      setBuffered(null);
      setPhase("loading");
      api
        .nextObstaclePracticePuzzle({ exclude_ids: current ? [current.id] : [] })
        .then((puzzle) => {
          if (!alive(gen)) return;
          resetFor(puzzle);
          refill([puzzle.id]);
        })
        .catch(() => {
          if (!alive(gen)) return;
          setPhase("error");
          setError(t("common.error"));
        });
    }
  }

  function retryCurrent() {
    if (!current || busyRef.current) return;
    resetFor(current);
  }

  function flagIllegal(dest: string) {
    playError();
    const next = illegalRef.current + 1;
    illegalRef.current = next;
    setIllegal(next);
    setIllegalFlash(dest);
    if (flashTimerRef.current !== null) window.clearTimeout(flashTimerRef.current);
    flashTimerRef.current = window.setTimeout(() => {
      flashTimerRef.current = null;
      setIllegalFlash(null);
    }, ILLEGAL_FLASH_MS);
  }

  async function submit(finalPath: string[], illegalCount: number) {
    if (!current || busyRef.current) return;
    busyRef.current = true;
    const gen = genRef.current;
    const puzzleId = current.id;
    const hints = usedHints;
    const started = startedAt;
    setPhase("submitting");
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzleId,
        answer: answerForPath(finalPath, illegalCount),
        mode: "practice",
        hints_used: hints,
        started_at: started,
      });
      if (!alive(gen)) return;
      playSuccess();
      setResult(res);
      setSolved((n) => n + 1);
      setScoreTotal((s) => s + res.score);
      savePracticeAttempt(puzzleId, res.score);
      setPhase("feedback");
    } catch {
      if (!alive(gen)) return;
      setError(t("common.error"));
      setPhase("ready");
    } finally {
      busyRef.current = false;
    }
  }

  function commitAnim() {
    const pending = pendingRef.current;
    pendingRef.current = null;
    setAnim(null);
    setStepBusy(false);
    if (!pending) return;
    const nextPath = [...pathRef.current, pending.selected_at];
    pathRef.current = nextPath;
    setPath(nextPath);
    setFen(pending.fen);
    setSelectedAt(pending.selected_at);
    setIllegalFlash(null);
    if (pending.reached) void submit(nextPath, illegalRef.current);
  }

  async function attemptMove(to: string) {
    const puzzle = current;
    if (phase !== "ready" || !puzzle || stepBusy || anim || result) return;
    const dest = to.toLowerCase();
    // Tapping the selected piece again: it simply stays selected.
    if (!selectedAt || dest === selectedAt) return;
    const origin = selectedAt;
    const currentFen = fen ?? puzzle.fen ?? "";
    const symbol = fenToPieces(currentFen)[origin];
    if (!symbol) return;
    setStepBusy(true);
    setError(null);
    try {
      const res = await api.validateObstacleStep({
        puzzle_id: puzzle.id,
        fen: currentFen,
        selected_at: origin,
        from: origin,
        to: dest,
      });
      if (!mountedRef.current) return;
      if (!res.ok) {
        // Illegal: buzz, red destination, piece stays, -3, still selected.
        setStepBusy(false);
        flagIllegal(dest);
        return;
      }
      pendingRef.current = { fen: res.fen, selected_at: res.selected_at, reached: res.reached };
      animKeyRef.current += 1;
      setAnim({ from: origin, to: res.selected_at, symbol, key: animKeyRef.current });
      // stepBusy stays true until the glide commits (no double-counting).
    } catch {
      if (!mountedRef.current) return;
      setStepBusy(false);
      setError(t("common.error"));
    }
  }

  const stat = `${faNum(solved)} · ${faNum(scoreTotal)}`;
  if ((phase === "loading" || phase === "error") && !current) {
    return (
      <GameShell title={t("exercises.pathfinding-obstacles.title")} modeKey="play.practice">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <Card>
            <p className="text-center">{phase === "error" ? (error ?? t("common.error")) : t("common.loading")}</p>
            {phase === "error" ? (
              <Button className="mt-3 w-full" onClick={loadInitial}>
                {t("common.retry")}
              </Button>
            ) : null}
          </Card>
        </div>
      </GameShell>
    );
  }
  const puzzle = current;
  if (!puzzle) {
    return (
      <GameShell title={t("exercises.pathfinding-obstacles.title")} modeKey="play.practice">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <p>{t("common.loading")}</p>
        </div>
      </GameShell>
    );
  }
  const pos = obstaclePosOf(puzzle);
  const pieces = fenToPieces(fen);
  const answering = phase === "ready" || phase === "submitting";
  const hints = puzzle.hint_json.hints ?? [];
  const busy = stepBusy || anim !== null || phase === "submitting";
  const board = (
    <PathBoard
      areaRef={areaRef}
      size={size}
      pieces={pieces}
      target={pos.target}
      selectedAt={selectedAt}
      illegalFlash={illegalFlash}
      anim={anim}
      animMs={PRACTICE_ANIM_MS}
      disabled={!answering || result !== null}
      onMove={(_, to) => void attemptMove(to)}
      onPress={(square) => void attemptMove(square)}
      onAnimDone={commitAnim}
    />
  );
  const status = <StatusLine moves={Math.max(0, path.length - 1)} illegal={illegal} />;
  const action =
    phase === "feedback" && result ? (
      <div className="shrink-0 px-3 pb-3 pt-1" data-testid="next-bar">
        <NextBar onNext={advance} onRetry={retryCurrent} />
      </div>
    ) : (
      <div className="shrink-0 px-3 pb-3 pt-1">
        <div className="flex gap-2">
          <Button variant="secondary" className="min-w-0 flex-1" onClick={retryCurrent} disabled={busy}>
            {t("play.retry")}
          </Button>
        </div>
        {error ? <p className="mt-2 text-center text-sm font-bold text-red-600">{error}</p> : null}
      </div>
    );
  const feedback =
    phase === "feedback" && result ? (
      <div className="shrink-0 px-3">
        <p className="mb-1 text-center text-sm font-black text-green-700" data-testid="arrived">
          {t("pathfinding.arrived")}
        </p>
        <PracticeFeedback puzzle={puzzle} result={result} />
      </div>
    ) : null;
  const question = (
    <QuestionHeader
      prompt={puzzle.prompt_fa}
      puzzleKey={puzzle.id}
      hints={hints}
      usedHints={usedHints}
      onUseHint={(id) => setUsedHints((p) => [...p, id])}
    />
  );

  return (
    <GameShell title={t("exercises.pathfinding-obstacles.title")} modeKey="play.practice" stat={stat}>
      <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {orientation === "landscape" ? (
          <div className="flex min-h-0 min-w-0 flex-1">
            {board}
            <aside className="flex w-60 shrink-0 flex-col gap-1 overflow-y-auto py-1">
              {question}
              {status}
              {feedback}
              {action}
            </aside>
          </div>
        ) : (
          <>
            {question}
            {board}
            {status}
            {feedback}
            {action}
          </>
        )}
      </div>
    </GameShell>
  );
}

type SpeedPhase = "preparing" | "active" | "report";

const MIN_BUFFER = 20;
const REFILL_AT = 12;
const REFILL_COUNT = 12;
const MAX_SKIPS = 3;

function SpeedLoop() {
  const [phase, setPhase] = useState<SpeedPhase>("preparing");
  const [session, setSession] = useState<SpeedSummary | null>(null);
  const [, setQueueTick] = useState(0);
  const [current, setCurrent] = useState<Puzzle | null>(null);
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [report, setReport] = useState<SpeedReport | null>(null);
  const [fen, setFen] = useState<string | null>(null);
  const [selectedAt, setSelectedAt] = useState<string | null>(null);
  const [path, setPath] = useState<string[]>([]);
  const [illegal, setIllegal] = useState(0);
  const [illegalFlash, setIllegalFlash] = useState<string | null>(null);
  const [anim, setAnim] = useState<Anim | null>(null);
  const [stepBusy, setStepBusy] = useState(false);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const deadlineRef = useRef(0);
  const finishingRef = useRef(false);
  const refillingRef = useRef(false);
  const busyRef = useRef(false);
  const transitionRef = useRef<number | null>(null);
  const consecutiveSkipRef = useRef(0);
  const sessionAliveRef = useRef(true);
  const genRef = useRef(0);
  const mountedRef = useRef(true);
  const sessionIdRef = useRef<string | null>(null);
  const queueRef = useRef<Puzzle[]>([]);
  const currentRef = useRef<Puzzle | null>(null);
  const animKeyRef = useRef(0);
  const pendingRef = useRef<{ fen: string; selected_at: string; reached: boolean } | null>(null);
  const pathRef = useRef<string[]>([]);
  const illegalRef = useRef(0);
  const flashTimerRef = useRef<number | null>(null);
  const { rootRef, areaRef, orientation, size } = useGameFit();

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      genRef.current += 1;
      if (transitionRef.current !== null) {
        clearTimeout(transitionRef.current);
        transitionRef.current = null;
      }
      if (flashTimerRef.current !== null) window.clearTimeout(flashTimerRef.current);
      const sid = sessionIdRef.current;
      if (sid && sessionAliveRef.current) api.finishObstacleSpeedSession(sid).catch(() => null);
    };
  }, []);

  function alive(gen: number) {
    return mountedRef.current && genRef.current === gen;
  }

  function cancelTransition() {
    if (transitionRef.current !== null) {
      clearTimeout(transitionRef.current);
      transitionRef.current = null;
    }
  }

  function anchorDeadline(remainingMs: number) {
    deadlineRef.current = Date.now() + Math.max(0, remainingMs);
    setNowMs(Date.now());
  }

  function isGone(e: unknown) {
    return apiStatus(e) === 410;
  }

  function isSessionLost(e: unknown) {
    return apiStatus(e) === 404 && (apiDetail(e) === "session_not_found" || apiDetail(e) === "session_expired");
  }

  function isUnknownPuzzle(e: unknown) {
    return (
      apiStatus(e) === 404 &&
      (apiDetail(e) === "puzzle_not_in_session" || apiDetail(e) === "puzzle_not_available")
    );
  }

  async function dieToReport(sessionId: string, gen: number) {
    sessionAliveRef.current = false;
    busyRef.current = false;
    if (alive(gen)) setBusy(false);
    try {
      const data = await api.getObstacleSpeedReport(sessionId);
      if (!alive(gen) || sessionIdRef.current !== sessionId) return;
      setReport(data);
      setSession(data.session);
      anchorDeadline(0);
      setError(null);
      setPhase("report");
    } catch {
      if (!alive(gen)) return;
      setReport(null);
      setSession(null);
      setError(t("speed.sessionLost"));
      setPhase("report");
    }
  }

  function resetFor(puzzle: Puzzle) {
    const pos = obstaclePosOf(puzzle);
    currentRef.current = puzzle;
    setCurrent(puzzle);
    setFen(puzzle.fen);
    setSelectedAt(pos.from);
    setPath(pos.from ? [pos.from] : []);
    pathRef.current = pos.from ? [pos.from] : [];
    setIllegal(0);
    illegalRef.current = 0;
    setIllegalFlash(null);
    setAnim(null);
    pendingRef.current = null;
    setStepBusy(false);
    setUsedHints([]);
    setResult(null);
    setError(null);
    setStartedAt(new Date().toISOString());
  }

  async function finishToReport(sessionId: string, gen: number) {
    if (finishingRef.current) return;
    finishingRef.current = true;
    cancelTransition();
    try {
      await api.finishObstacleSpeedSession(sessionId).catch(() => null);
      const data = await api.getObstacleSpeedReport(sessionId);
      if (!alive(gen) || sessionIdRef.current !== sessionId) return;
      setReport(data);
      setSession(data.session);
      anchorDeadline(0);
      setPhase("report");
    } catch {
      if (!alive(gen)) return;
      setError(t("common.error"));
    } finally {
      finishingRef.current = false;
    }
  }

  async function boot() {
    const gen = ++genRef.current;
    busyRef.current = false;
    refillingRef.current = false;
    finishingRef.current = false;
    consecutiveSkipRef.current = 0;
    sessionAliveRef.current = true;
    cancelTransition();
    const prev = sessionIdRef.current;
    sessionIdRef.current = null;
    queueRef.current = [];
    currentRef.current = null;
    setQueueTick((n) => n + 1);
    setCurrent(null);
    setResult(null);
    setReport(null);
    setError(null);
    setPhase("preparing");
    try {
      if (prev) await api.finishObstacleSpeedSession(prev).catch(() => null);
      const created = await api.startObstacleSpeedSession();
      if (!alive(gen)) return;
      sessionIdRef.current = created.session_id;
      setSession({ ...created, attempted: 0, correct: 0, partial: 0, wrong: 0, score: 0 });
      const acc: Puzzle[] = [];
      let guard = 0;
      while (acc.length < MIN_BUFFER && guard < 6) {
        guard += 1;
        const batch = await api.prepareObstacleSpeedPuzzles(created.session_id, { count: MIN_BUFFER });
        if (!alive(gen) || sessionIdRef.current !== created.session_id) return;
        for (const p of batch) {
          if (!acc.some((q) => q.id === p.id)) acc.push(p);
        }
      }
      if (acc.length < MIN_BUFFER) throw new Error("buffer_not_ready");
      const started = await api.startObstacleSpeedClock(created.session_id);
      if (!alive(gen) || sessionIdRef.current !== created.session_id) return;
      setSession({ ...started, attempted: 0, correct: 0, partial: 0, wrong: 0, score: 0 });
      anchorDeadline(started.remaining_ms);
      queueRef.current = acc.slice(1);
      setQueueTick((n) => n + 1);
      resetFor(acc[0]);
      setPhase("active");
    } catch {
      if (!alive(gen)) return;
      sessionIdRef.current = null;
      setError(t("common.error"));
    }
  }

  useEffect(() => {
    boot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refillIfNeeded() {
    const sid = sessionIdRef.current;
    const gen = genRef.current;
    if (!sid || refillingRef.current) return;
    if (queueRef.current.length >= REFILL_AT) return;
    refillingRef.current = true;
    try {
      const batch = await api.prepareObstacleSpeedPuzzles(sid, { count: REFILL_COUNT });
      if (!alive(gen) || sessionIdRef.current !== sid) return;
      const ids = new Set(queueRef.current.map((p) => p.id));
      if (currentRef.current) ids.add(currentRef.current.id);
      const fresh = batch.filter((p) => !ids.has(p.id));
      if (fresh.length > 0) {
        queueRef.current = [...queueRef.current, ...fresh];
        setQueueTick((n) => n + 1);
      }
    } catch (e) {
      if (isGone(e)) await finishToReport(sid, gen);
    } finally {
      refillingRef.current = false;
    }
  }

  useEffect(() => {
    if (phase !== "active" || !session || session.status !== "active") return;
    const sid = session.session_id;
    const gen = genRef.current;
    const timer = setInterval(() => {
      setNowMs(Date.now());
      if (Date.now() >= deadlineRef.current) {
        clearInterval(timer);
        finishToReport(sid, gen);
      }
    }, 250);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, session]);

  const remainingMs = Math.max(0, deadlineRef.current - nowMs);
  const remainingSec = Math.ceil(remainingMs / 1000);

  function flagIllegal(dest: string) {
    playError();
    const next = illegalRef.current + 1;
    illegalRef.current = next;
    setIllegal(next);
    setIllegalFlash(dest);
    if (flashTimerRef.current !== null) window.clearTimeout(flashTimerRef.current);
    flashTimerRef.current = window.setTimeout(() => {
      flashTimerRef.current = null;
      setIllegalFlash(null);
    }, ILLEGAL_FLASH_MS);
  }

  async function submitFinal(finalPath: string[], illegalCount: number) {
    const puzzle = currentRef.current;
    const sid = sessionIdRef.current;
    if (phase !== "active" || !puzzle || !sid || busyRef.current) return;
    busyRef.current = true;
    const gen = genRef.current;
    setBusy(true);
    setError(null);
    try {
      const res = await api.submitObstacleSpeedAnswer(sid, {
        puzzle_id: puzzle.id,
        answer: answerForPath(finalPath, illegalCount),
        hints_used: usedHints,
        started_at: startedAt,
      });
      if (!alive(gen) || sessionIdRef.current !== sid) {
        busyRef.current = false;
        return;
      }
      playSuccess();
      setResult(res.attempt);
      setSession(res.session);
      consecutiveSkipRef.current = 0;
      anchorDeadline(res.session.remaining_ms);
      // Very brief success feedback, then auto-advance with NO manual
      // button. The timer keeps running; expiry cancels this.
      transitionRef.current = window.setTimeout(() => {
        transitionRef.current = null;
        if (!alive(gen) || sessionIdRef.current !== sid) {
          busyRef.current = false;
          return;
        }
        advance();
      }, SPEED_FEEDBACK_MS);
    } catch (e) {
      if (!alive(gen)) {
        busyRef.current = false;
        return;
      }
      if (isGone(e)) {
        busyRef.current = false;
        if (alive(gen)) setBusy(false);
        await finishToReport(sid, gen);
        setError(t("speed.expired"));
      } else if (isSessionLost(e)) {
        await dieToReport(sid, gen);
      } else if (isUnknownPuzzle(e)) {
        consecutiveSkipRef.current += 1;
        if (consecutiveSkipRef.current >= MAX_SKIPS) {
          await dieToReport(sid, gen);
        } else {
          busyRef.current = false;
          if (alive(gen)) setBusy(false);
          advance();
        }
      } else {
        busyRef.current = false;
        setError(t("common.error"));
        if (alive(gen)) setBusy(false);
      }
    }
  }

  function commitAnim() {
    const pending = pendingRef.current;
    pendingRef.current = null;
    setAnim(null);
    setStepBusy(false);
    if (!pending) return;
    const nextPath = [...pathRef.current, pending.selected_at];
    pathRef.current = nextPath;
    setPath(nextPath);
    setFen(pending.fen);
    setSelectedAt(pending.selected_at);
    setIllegalFlash(null);
    if (pending.reached) void submitFinal(nextPath, illegalRef.current);
  }

  async function attemptMove(to: string) {
    const puzzle = currentRef.current;
    if (phase !== "active" || result || !puzzle || stepBusy || anim || busyRef.current) return;
    const dest = to.toLowerCase();
    if (!selectedAt || dest === selectedAt) return;
    const origin = selectedAt;
    const currentFen = fen ?? puzzle.fen ?? "";
    const symbol = fenToPieces(currentFen)[origin];
    if (!symbol) return;
    setStepBusy(true);
    setError(null);
    try {
      const res = await api.validateObstacleStep({
        puzzle_id: puzzle.id,
        fen: currentFen,
        selected_at: origin,
        from: origin,
        to: dest,
      });
      if (!mountedRef.current) return;
      if (!res.ok) {
        setStepBusy(false);
        flagIllegal(dest);
        return;
      }
      pendingRef.current = { fen: res.fen, selected_at: res.selected_at, reached: res.reached };
      animKeyRef.current += 1;
      setAnim({ from: origin, to: res.selected_at, symbol, key: animKeyRef.current });
    } catch {
      if (!mountedRef.current) return;
      setStepBusy(false);
      setError(t("common.error"));
    }
  }

  async function advance() {
    const sid = sessionIdRef.current;
    if (phase !== "active" || !sid) {
      busyRef.current = false;
      return;
    }
    if (Date.now() >= deadlineRef.current) {
      busyRef.current = false;
      if (alive(genRef.current)) setBusy(false);
      await finishToReport(sid, genRef.current);
      return;
    }
    const [next, ...rest] = queueRef.current;
    if (next) {
      queueRef.current = rest;
      setQueueTick((n) => n + 1);
      resetFor(next);
      busyRef.current = false;
      if (alive(genRef.current)) setBusy(false);
      refillIfNeeded();
      return;
    }
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      const puzzle = await api.nextObstacleSpeedPuzzle(sid);
      const gen = genRef.current;
      if (!alive(gen) || sessionIdRef.current !== sid) return;
      resetFor(puzzle);
      refillIfNeeded();
    } catch (e) {
      const gen = genRef.current;
      if (!alive(gen)) return;
      if (isGone(e)) await finishToReport(sid, gen);
      else if (isSessionLost(e)) await dieToReport(sid, gen);
      else if (isUnknownPuzzle(e)) {
        consecutiveSkipRef.current += 1;
        if (consecutiveSkipRef.current >= MAX_SKIPS) await dieToReport(sid, gen);
        else setError(t("common.error"));
      } else setError(t("common.error"));
    } finally {
      busyRef.current = false;
      if (alive(genRef.current)) setBusy(false);
    }
  }

  if (phase === "preparing") {
    return (
      <GameShell title={t("exercises.pathfinding-obstacles.title")} modeKey="play.speed">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <Card>
            <p className="text-center text-sm font-bold text-stone-600">{t("speed.preparing")}</p>
            {error ? (
              <div>
                <p className="mt-3 text-center text-sm font-bold text-red-600">{error}</p>
                <Button className="mt-3 w-full" onClick={boot}>
                  {t("common.retry")}
                </Button>
              </div>
            ) : null}
          </Card>
        </div>
      </GameShell>
    );
  }

  if (phase === "report") {
    return <SpeedReportView report={report} error={error} onRetry={boot} />;
  }

  const puzzle = current;
  if (!session || !puzzle) {
    return (
      <GameShell title={t("exercises.pathfinding-obstacles.title")} modeKey="play.speed">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <Card>
            <p className="text-center">{error ?? t("common.loading")}</p>
            {error ? (
              <Button className="mt-3 w-full" onClick={boot}>
                {t("common.retry")}
              </Button>
            ) : null}
          </Card>
        </div>
      </GameShell>
    );
  }

  const pos = obstaclePosOf(puzzle);
  const pieces = fenToPieces(fen);
  const totalMs = session.duration_s * 1000;
  const progress = Math.max(0, Math.min(1, remainingMs / totalMs));
  const hints = puzzle.hint_json.hints ?? [];
  const timer = <TimerStrip remainingSec={remainingSec} correct={session.correct} progress={progress} />;
  const question = (
    <QuestionHeader
      prompt={puzzle.prompt_fa}
      puzzleKey={puzzle.id}
      hints={hints}
      usedHints={usedHints}
      onUseHint={(id) => setUsedHints((p) => [...p, id])}
    />
  );
  const board = (
    <PathBoard
      areaRef={areaRef}
      size={size}
      pieces={pieces}
      target={pos.target}
      selectedAt={selectedAt}
      illegalFlash={illegalFlash}
      anim={anim}
      animMs={SPEED_ANIM_MS}
      disabled={result !== null || busy}
      onMove={(_, to) => void attemptMove(to)}
      onPress={(square) => void attemptMove(square)}
      onAnimDone={commitAnim}
      overlay={result ? <SpeedPill result={result} /> : null}
    />
  );
  const status = <StatusLine moves={Math.max(0, path.length - 1)} illegal={illegal} />;

  return (
    <GameShell title={t("exercises.pathfinding-obstacles.title")} modeKey="play.speed">
      <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {orientation === "landscape" ? (
          <div className="flex min-h-0 min-w-0 flex-1">
            {board}
            <aside className="flex w-60 shrink-0 flex-col gap-1 overflow-y-auto py-1">
              {question}
              {timer}
              {status}
              {error ? <p className="px-3 text-center text-xs font-bold text-red-600">{error}</p> : null}
            </aside>
          </div>
        ) : (
          <>
            {question}
            {timer}
            {board}
            {status}
            {error ? <p className="px-3 text-center text-xs font-bold text-red-600">{error}</p> : null}
          </>
        )}
      </div>
    </GameShell>
  );
}

function resultLabel(result: string) {
  if (result === "correct") return t("report.correct");
  if (result === "partial") return t("report.partial");
  return t("report.wrong");
}

function SpeedReportView({
  report,
  error,
  onRetry,
}: {
  report: SpeedReport | null;
  error: string | null;
  onRetry: () => void;
}) {
  if (!report) {
    return (
      <GameShell title={t("speed.result")} modeKey="play.speed">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <Card>
            <p className="text-center">{error ?? t("common.loading")}</p>
            {error ? (
              <Button className="mt-3 w-full" onClick={onRetry}>
                {t("common.retry")}
              </Button>
            ) : null}
          </Card>
        </div>
      </GameShell>
    );
  }
  const { session, entries } = report;
  const average = session.attempted > 0 ? session.score / session.attempted : null;
  const accuracy = session.attempted > 0 ? Math.round((session.correct / session.attempted) * 100) : null;
  return (
    <GameShell title={t("speed.result")} modeKey="play.speed" scroll>
      <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
        <p className="py-1 text-center text-sm font-bold text-stone-600">{t("speed.finished")}</p>
        <Card>
          {session.attempted === 0 ? (
            <p className="text-center text-sm font-bold text-stone-600">{t("report.empty")}</p>
          ) : (
            <div className="grid grid-cols-2 gap-2 text-center sm:grid-cols-3">
              <div className="rounded-2xl bg-violet-50 px-2 py-3">
                <p className="text-2xl font-black text-violet-700">{faNum(session.attempted)}</p>
                <p className="text-xs text-stone-500">{t("speed.attempted")}</p>
              </div>
              <div className="rounded-2xl bg-green-50 px-2 py-3">
                <p className="text-2xl font-black text-green-600">{faNum(session.correct)}</p>
                <p className="text-xs text-stone-500">{t("report.correct")}</p>
              </div>
              <div className="rounded-2xl bg-amber-50 px-2 py-3">
                <p className="text-2xl font-black text-amber-600">{faNum(session.partial)}</p>
                <p className="text-xs text-stone-500">{t("report.partial")}</p>
              </div>
              <div className="rounded-2xl bg-red-50 px-2 py-3">
                <p className="text-2xl font-black text-red-600">{faNum(session.wrong)}</p>
                <p className="text-xs text-stone-500">{t("report.wrong")}</p>
              </div>
              <div className="rounded-2xl bg-violet-50 px-2 py-3">
                <p className="text-2xl font-black text-violet-700">{faNum(session.score)}</p>
                <p className="text-xs text-stone-500">{t("speed.score")}</p>
              </div>
              <div className="rounded-2xl bg-stone-100 px-2 py-3">
                <p className="text-2xl font-black text-stone-700">
                  {average === null ? "—" : faNum(Math.round(average * 100) / 100)}
                </p>
                <p className="text-xs text-stone-500">{t("speed.average")}</p>
              </div>
            </div>
          )}
          {accuracy !== null ? (
            <p className="mt-3 text-center text-sm font-bold text-stone-600">
              {t("speed.accuracy")}: <span dir="ltr">{faNum(accuracy)}٪</span>
            </p>
          ) : null}
          {entries.length > 0 ? (
            <ul className="mt-4 grid gap-2">
              {entries.map((entry, index) => {
                const tone =
                  entry.result === "correct"
                    ? "border-green-500 bg-green-50"
                    : entry.result === "partial"
                      ? "border-amber-500 bg-amber-50"
                      : "border-red-400 bg-red-50";
                return (
                  <li key={entry.attempt_id} className={`rounded-2xl border-2 px-4 py-3 ${tone}`}>
                    <div className="flex min-w-0 items-center justify-between gap-2">
                      <p className="min-w-0 truncate text-sm font-black text-stone-800">
                        {t("report.puzzle")} {faNum(index + 1)} · {entry.prompt_fa}
                      </p>
                      <span className="shrink-0 text-sm font-black">{resultLabel(entry.result)}</span>
                    </div>
                    <p className="mt-1 text-sm font-bold text-stone-700">
                      {faNum(entry.score)} {t("speed.score")}
                    </p>
                  </li>
                );
              })}
            </ul>
          ) : null}
          <div className="mt-4 grid gap-2">
            <Button className="w-full" onClick={onRetry}>
              {t("speed.retry")}
            </Button>
          </div>
        </Card>
      </div>
    </GameShell>
  );
}
