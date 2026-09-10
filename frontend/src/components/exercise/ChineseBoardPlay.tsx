import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { api, apiDetail, apiStatus } from "../../api/client";
import type { AttemptResponse, Puzzle, SpeedReport, SpeedSummary } from "../../api/types";
import { t } from "../../i18n";
import { fenToPieces } from "../../lib/fen";
import { savePracticeAttempt } from "../../lib/localProgress";
import { playError, playSuccess } from "../../lib/sound";
import { ChessBoard, type BoardMap } from "../chess/ChessBoard";
import { ChessPiece, type PieceSymbol } from "../chess/ChessPiece";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { FeedbackText } from "../ui/PageHeader";
import {
  GameShell,
  QuestionHeader,
  TimerStrip,
  faNum,
  useGameFit,
  type DivRef,
} from "./PieceGameLayout";

export type ChineseBoardMode = "practice" | "speed";

type Tool = PieceSymbol | "eraser";

const PALETTE: PieceSymbol[] = ["K", "Q", "R", "B", "N", "P", "k", "q", "r", "b", "n", "p"];

const FALLBACK_BUDGET_MS = 3000;

// Dedicated Practice + Speed loop for the Memorization Board (صفحه‌ی حفظی).
// Each puzzle is first shown read-only for a server-authoritative study
// budget (piece_count * 400ms in position_json.memorization_ms), then the
// board fades to empty and the child rebuilds the whole position with a
// tap palette (select piece, tap square, replace freely, eraser removes).
// Renders and transports answers only; the piece set, the study budget,
// scoring, and the speed clock stay backend-authoritative. Every
// submission is graded server-side from the stored FEN. The ?mode= URL
// param (set by the home card's Practice/Speed buttons) picks the loop
// directly; there is no intermediate mode-selection screen.
//
// Layout: full-viewport game shell (no page scroll). Portrait stacks
// question -> board -> palette -> check; landscape puts the board beside
// a control column. The board is exactly fitted to its area via
// ResizeObserver. Orientation is always White, identical in both phases.
export function ChineseBoardPlay({ mode }: { mode: ChineseBoardMode }) {
  return mode === "practice" ? <PracticeLoop /> : <SpeedLoop />;
}

function pieceName(symbol: PieceSymbol): string {
  switch (symbol.toUpperCase()) {
    case "K":
      return t("pieces.king");
    case "Q":
      return t("pieces.queen");
    case "R":
      return t("pieces.rook");
    case "B":
      return t("pieces.bishop");
    case "N":
      return t("pieces.knight");
    default:
      return t("pieces.pawn");
  }
}

function toolLabel(tool: Tool): string {
  if (tool === "eraser") return t("memory.eraser");
  const color = tool === tool.toUpperCase() ? t("heavierSide.white") : t("heavierSide.black");
  return `${color} ${pieceName(tool)}`;
}

/** Server-authoritative study budget (ms) for a puzzle.
 *
 * Single source of truth is the backend (`MEMORIZE_MS_PER_PIECE` in
 * `chinese_board/pieces.py`), delivered per puzzle as
 * `position_json.memorization_ms`. The multipliers below only cover
 * malformed payloads and must match the backend constant — never invent
 * a separate frontend timing. */
export function memorizeMsOf(puzzle: Puzzle): number {
  const raw = puzzle.position_json.memorization_ms;
  if (typeof raw === "number" && Number.isFinite(raw) && raw > 0) return Math.round(raw);
  const count = puzzle.position_json.piece_count;
  if (typeof count === "number" && Number.isFinite(count) && count > 0)
    return Math.round(count) * 1000;
  return Math.max(1, Object.keys(fenToPieces(puzzle.fen)).length) * 1000 || FALLBACK_BUDGET_MS;
}

function piecesToAnswer(placed: BoardMap): Array<{ square: string; piece: string; color: string }> {
  return Object.entries(placed)
    .filter((entry): entry is [string, PieceSymbol] => entry[1] !== undefined)
    .map(([square, symbol]) => ({
      square,
      piece: symbol.toUpperCase(),
      color: symbol === symbol.toUpperCase() ? "white" : "black",
    }));
}

function missingOf(result: AttemptResponse): string[] {
  return result.detail.missing ?? result.detail.missed ?? [];
}

function extraOf(result: AttemptResponse): string[] {
  return result.detail.extra ?? [];
}

function correctCountOf(result: AttemptResponse): number {
  return result.detail.correct.length;
}

// Thin memorize progress bar (subtle, above the board). The text ticks in
// whole seconds; the bar itself is smooth. Not a live region: announcing
// every tick would drown out the board for screen readers.
function MemorizeProgress({ remainingMs, totalMs }: { remainingMs: number; totalMs: number }) {
  const progress = totalMs > 0 ? Math.max(0, Math.min(1, remainingMs / totalMs)) : 0;
  return (
    <div
      className="mx-3 mt-1 shrink-0 rounded-2xl border-2 border-violet-200 bg-white px-3 py-1"
      role="timer"
      aria-label={t("chineseBoard.study")}
      data-testid="memorize-progress"
    >
      <div className="flex min-w-0 items-center justify-between gap-2">
        <span className="text-xs font-bold text-stone-600">{t("chineseBoard.study")}</span>
        <span className="text-lg font-black text-violet-700" dir="ltr">
          {faNum(Math.ceil(Math.max(0, remainingMs) / 1000))}{" "}
          <span className="text-xs font-bold">{t("common.seconds")}</span>
        </span>
      </div>
      <div className="mt-1 h-1.5 min-w-0 overflow-hidden rounded-full bg-violet-100" aria-hidden="true">
        <div
          className="h-full rounded-full bg-violet-600 transition-[width] duration-100"
          style={{ width: `${Math.round(progress * 100)}%` }}
        />
      </div>
    </div>
  );
}

function FittedBoard({
  areaRef,
  size,
  pieces,
  squareStates,
  onSquarePress,
  disabled,
  fading,
  overlay,
}: {
  areaRef: DivRef;
  size: number;
  pieces: BoardMap;
  squareStates?: Partial<Record<string, "selected" | "correct" | "missed" | "wrong" | "target">>;
  onSquarePress?: (square: string) => void;
  disabled?: boolean;
  fading?: boolean;
  overlay?: ReactNode;
}) {
  return (
    <div ref={areaRef} className="relative min-h-0 min-w-0 flex-1" data-testid="board-zone">
      <div className="absolute inset-0 grid place-items-center">
        <div
          dir="ltr"
          data-testid="chessboard"
          style={{ width: size, height: size }}
          className={fading ? "motion-safe:opacity-0 motion-safe:transition-opacity motion-safe:duration-300" : undefined}
        >
          <ChessBoard
            pieces={fading ? {} : pieces}
            onSquarePress={fading ? undefined : onSquarePress}
            squareStates={squareStates}
            disabled={disabled}
          />
        </div>
      </div>
      {overlay}
    </div>
  );
}

function Palette({ active, onPick }: { active: Tool | null; onPick: (tool: Tool | null) => void }) {
  // Fixed 44px tools in a wrapping centered row: the palette never
  // stretches (which would distort the SVG pieces in narrow sidebars),
  // never balloons (which would steal board space on tablets), and wraps
  // to more rows on very narrow screens instead of overflowing.
  const toolClass = (isActive: boolean) =>
    `h-11 w-11 min-h-[44px] min-w-[44px] shrink-0 rounded-xl border-2 p-1 transition ${
      isActive ? "border-violet-600 bg-violet-50" : "border-stone-200 bg-white"
    }`;
  return (
    <div className="shrink-0 px-3 pt-1" role="group" aria-label={t("chineseBoard.palette")}>
      <div className="flex flex-wrap justify-center gap-1">
        {PALETTE.map((symbol) => {
          const isActive = active === symbol;
          return (
            <button
              key={symbol}
              type="button"
              aria-pressed={isActive}
              aria-label={toolLabel(symbol)}
              title={toolLabel(symbol)}
              onClick={() => onPick(isActive ? null : symbol)}
              className={toolClass(isActive)}
              style={{ touchAction: "manipulation" }}
            >
              <ChessPiece symbol={symbol} />
            </button>
          );
        })}
        <button
          type="button"
          aria-pressed={active === "eraser"}
          aria-label={t("memory.eraser")}
          title={t("memory.eraser")}
          onClick={() => onPick(active === "eraser" ? null : "eraser")}
          className={`h-11 w-11 min-h-[44px] min-w-[44px] shrink-0 rounded-xl border-2 text-lg font-black transition ${
            active === "eraser"
              ? "border-violet-600 bg-violet-50 text-violet-800"
              : "border-stone-200 bg-white text-stone-500"
          }`}
          style={{ touchAction: "manipulation" }}
        >
          <span aria-hidden="true">⌫</span>
        </button>
      </div>
    </div>
  );
}

function CheckBar({
  placedCount,
  submitting,
  canCheck,
  onCheck,
  onClear,
}: {
  placedCount: number;
  submitting: boolean;
  canCheck: boolean;
  onCheck: () => void;
  onClear: () => void;
}) {
  return (
    <div className="shrink-0 px-3 pb-3 pt-1" data-testid="submit-bar">
      <p className="mb-1 truncate text-center text-xs font-bold text-stone-600">
        {t("chineseBoard.placed")}: {faNum(placedCount)}
      </p>
      <div className="flex gap-2">
        <Button className="min-w-0 flex-1" onClick={onCheck} disabled={submitting || !canCheck}>
          {t("chineseBoard.check")}
        </Button>
        <Button variant="secondary" onClick={onClear} disabled={submitting}>
          {t("play.clear")}
        </Button>
      </div>
    </div>
  );
}

// Post-submit result: per-piece counts + score + a toggle between the
// child's reconstruction and the correct board. The correct board renders
// from the puzzle FEN already held in memory from the memorize phase —
// no answer is fetched after the board disappears.
function ResultPanel({
  puzzle,
  placed,
  result,
  compact,
}: {
  puzzle: Puzzle;
  placed: BoardMap;
  result: AttemptResponse;
  compact?: boolean;
}) {
  const [view, setView] = useState<"yours" | "correct">("yours");
  const missing = missingOf(result);
  const extra = extraOf(result);
  const counts = (
    <div
      className={`shrink-0 rounded-2xl border-2 px-3 py-2 ${
        result.result === "correct" ? "border-green-500 bg-green-50" : "border-red-400 bg-red-50"
      }`}
    >
      <FeedbackText feedbackKey={result.feedback_key} />
      <div className="mt-1 grid grid-cols-4 gap-1 text-center">
        <div>
          <p className="text-xl font-black text-green-600">{faNum(correctCountOf(result))}</p>
          <p className="text-[11px] text-stone-500">{t("chineseBoard.correct")}</p>
        </div>
        <div>
          <p className="text-xl font-black text-red-600">
            {faNum(result.detail.wrong.length - extra.length)}
          </p>
          <p className="text-[11px] text-stone-500">{t("chineseBoard.wrong")}</p>
        </div>
        <div>
          <p className="text-xl font-black text-amber-600">{faNum(missing.length)}</p>
          <p className="text-[11px] text-stone-500">{t("chineseBoard.missing")}</p>
        </div>
        <div>
          <p className="text-xl font-black text-red-600">{faNum(extra.length)}</p>
          <p className="text-[11px] text-stone-500">{t("chineseBoard.extra")}</p>
        </div>
      </div>
      <p className="mt-1 text-center text-base font-black text-stone-800">
        {faNum(result.score)} {t("speed.score")}
      </p>
    </div>
  );
  // Speed (compact) feedback shows counts + score only: the 600ms glance
  // must always fit without scrolling, so no board is rendered there.
  if (compact) {
    return (
      <div className="shrink-0 px-3 pb-3" data-testid="feedback">
        {counts}
      </div>
    );
  }
  const userStates: Partial<Record<string, "selected" | "correct" | "missed" | "wrong" | "target">> =
    {};
  for (const s of result.detail.correct_squares ?? []) userStates[s] = "correct";
  for (const s of result.detail.wrong_squares ?? []) userStates[s] = "wrong";
  const answerStates: Partial<
    Record<string, "selected" | "correct" | "missed" | "wrong" | "target">
  > = {};
  for (const s of result.detail.correct_squares ?? []) answerStates[s] = "correct";
  for (const s of result.detail.missed_squares ?? []) answerStates[s] = "missed";
  const shown = view === "yours" ? placed : fenToPieces(puzzle.fen);
  const states = view === "yours" ? userStates : answerStates;
  return (
    <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-1 overflow-y-auto px-3 pb-3" data-testid="feedback">
      {counts}
      <div className="grid shrink-0 grid-cols-2 gap-1" role="group" aria-label={t("play.correctAnswer")}>
        <button
          type="button"
          aria-pressed={view === "yours"}
          onClick={() => setView("yours")}
          className={`min-h-[44px] rounded-xl border-2 text-sm font-black transition ${
            view === "yours"
              ? "border-violet-600 bg-violet-50 text-violet-800"
              : "border-stone-200 bg-white text-stone-600"
          }`}
          style={{ touchAction: "manipulation" }}
        >
          {t("chineseBoard.yourAnswer")}
        </button>
        <button
          type="button"
          aria-pressed={view === "correct"}
          onClick={() => setView("correct")}
          className={`min-h-[44px] rounded-xl border-2 text-sm font-black transition ${
            view === "correct"
              ? "border-violet-600 bg-violet-50 text-violet-800"
              : "border-stone-200 bg-white text-stone-600"
          }`}
          style={{ touchAction: "manipulation" }}
        >
          {t("chineseBoard.correctBoard")}
        </button>
      </div>
      {/* Capped like the main board (same GAME_BOARD_MAX philosophy) and
          centered, so review boards never blow out narrow viewports. */}
      <div dir="ltr" data-testid={view === "yours" ? "yours-board" : "answer-board"} className="mx-auto w-full max-w-[520px]">
        <ChessBoard pieces={shown} squareStates={states} disabled />
      </div>
    </div>
  );
}

type PuzzlePhase = "loading" | "memorizing" | "reconstructing" | "submitting" | "feedback" | "error";

function PracticeLoop() {
  const [phase, setPhase] = useState<PuzzlePhase>("loading");
  const [current, setCurrent] = useState<Puzzle | null>(null);
  const [buffered, setBuffered] = useState<Puzzle | null>(null);
  const [placed, setPlaced] = useState<BoardMap>({});
  const [tool, setTool] = useState<Tool | null>(null);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>("");
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [remainingMs, setRemainingMs] = useState(0);
  const [fading, setFading] = useState(false);
  const [solved, setSolved] = useState(0);
  const [correctTotal, setCorrectTotal] = useState(0);
  const [scoreTotal, setScoreTotal] = useState(0);
  const genRef = useRef(0);
  const mountedRef = useRef(true);
  const currentIdRef = useRef<number | null>(null);
  const busyRef = useRef(false);
  const { rootRef, areaRef, orientation, size } = useGameFit();

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      genRef.current += 1;
    };
  }, []);

  function alive(gen: number) {
    return mountedRef.current && genRef.current === gen;
  }

  function beginMemorize(puzzle: Puzzle) {
    currentIdRef.current = puzzle.id;
    setCurrent(puzzle);
    setPlaced({});
    setTool(null);
    setUsedHints([]);
    setResult(null);
    setError(null);
    setFading(false);
    setStartedAt(new Date().toISOString());
    setRemainingMs(memorizeMsOf(puzzle));
    setPhase("memorizing");
  }

  async function refill(exclude: number[]) {
    const gen = genRef.current;
    let next: Puzzle | null = null;
    try {
      next = await api.nextChinesePracticePuzzle({ exclude_ids: exclude });
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
      first = await api.nextChinesePracticePuzzle({ exclude_ids: [] });
    } catch {
      first = null;
    }
    if (!alive(gen)) return;
    if (!first) {
      setPhase("error");
      setError(t("common.error"));
      return;
    }
    beginMemorize(first);
    refill([first.id]);
  }

  useEffect(() => {
    loadInitial();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Memorize countdown: when the server-authoritative budget elapses, fade
  // the board (skipped under prefers-reduced-motion) and reconstruct.
  useEffect(() => {
    if (phase !== "memorizing" || !current) return;
    const deadline = Date.now() + remainingMs;
    const timer = setInterval(() => {
      const left = deadline - Date.now();
      if (left <= 0) {
        clearInterval(timer);
        setRemainingMs(0);
        const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
        if (reduce) {
          setPhase("reconstructing");
        } else {
          setFading(true);
          window.setTimeout(() => {
            setFading(false);
            setPhase("reconstructing");
          }, 320);
        }
      } else {
        setRemainingMs(left);
      }
    }, 100);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, current]);

  function advance() {
    if (busyRef.current) return;
    const gen = ++genRef.current;
    const next = buffered;
    if (next && (!current || next.id !== current.id)) {
      setBuffered(null);
      beginMemorize(next);
      refill([next.id]);
    } else {
      setBuffered(null);
      setPhase("loading");
      api
        .nextChinesePracticePuzzle({ exclude_ids: current ? [current.id] : [] })
        .then((puzzle) => {
          if (!alive(gen)) return;
          beginMemorize(puzzle);
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
    beginMemorize(current);
  }

  function tapSquare(square: string) {
    if (phase !== "reconstructing" || tool === null) return;
    setPlaced((prev) => {
      const next: BoardMap = { ...prev };
      if (tool === "eraser") {
        delete next[square];
      } else {
        next[square] = tool;
      }
      return next;
    });
  }

  async function check() {
    if (phase !== "reconstructing" || !current || busyRef.current) return;
    busyRef.current = true;
    const gen = genRef.current;
    const puzzleId = current.id;
    setPhase("submitting");
    setError(null);
    try {
      const res = await api.submitAttempt({
        puzzle_id: puzzleId,
        answer: { pieces: piecesToAnswer(placed) },
        mode: "practice",
        hints_used: usedHints,
        started_at: startedAt,
      });
      if (!alive(gen)) return;
      setResult(res);
      setSolved((n) => n + 1);
      if (res.result === "correct") {
        setCorrectTotal((n) => n + 1);
        playSuccess();
      } else {
        playError();
      }
      setScoreTotal((s) => s + res.score);
      savePracticeAttempt(puzzleId, res.score);
      setPhase("feedback");
    } catch {
      if (!alive(gen)) return;
      setError(t("common.error"));
      setPhase("reconstructing");
    } finally {
      busyRef.current = false;
    }
  }

  const stat = `${faNum(solved)} · ${faNum(correctTotal)} · ${faNum(scoreTotal)}`;
  if ((phase === "loading" || phase === "error") && !current) {
    return (
      <GameShell title={t("exercises.chinese-board.title")} modeKey="play.practice">
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
      <GameShell title={t("exercises.chinese-board.title")} modeKey="play.practice">
        <div className="grid min-h-0 flex-1 place-items-center px-4">
          <p>{t("common.loading")}</p>
        </div>
      </GameShell>
    );
  }

  const hints = puzzle.hint_json.hints ?? [];
  const total = memorizeMsOf(puzzle);
  const question = (
    <QuestionHeader
      prompt={
        phase === "memorizing"
          ? t("chineseBoard.study")
          : phase === "feedback"
            ? t("chineseBoard.score")
            : t("chineseBoard.reconstruct")
      }
      puzzleKey={puzzle.id}
      hints={hints}
      usedHints={usedHints}
      onUseHint={(id) => setUsedHints((p) => [...p, id])}
    />
  );

  if (phase === "memorizing") {
    const board = (
      <FittedBoard
        areaRef={areaRef}
        size={size}
        pieces={fenToPieces(puzzle.fen)}
        disabled
        fading={fading}
      />
    );
    return (
      <GameShell title={t("exercises.chinese-board.title")} modeKey="play.practice" stat={stat}>
        <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          {question}
          <MemorizeProgress remainingMs={remainingMs} totalMs={total} />
          {board}
        </div>
      </GameShell>
    );
  }

  if (phase === "feedback" && result) {
    return (
      <GameShell title={t("exercises.chinese-board.title")} modeKey="play.practice" stat={stat} scroll>
        <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          {question}
          <ResultPanel puzzle={puzzle} placed={placed} result={result} />
          <div className="shrink-0 px-3 pb-3 pt-1" data-testid="next-bar">
            <div className="flex gap-2">
              <Button className="min-w-0 flex-1" onClick={advance}>
                {t("chineseBoard.next")}
              </Button>
              <Button variant="secondary" onClick={retryCurrent}>
                {t("play.retry")}
              </Button>
            </div>
          </div>
        </div>
      </GameShell>
    );
  }

  const answering = phase === "reconstructing";
  const board = (
    <FittedBoard
      areaRef={areaRef}
      size={size}
      pieces={placed}
      squareStates={undefined}
      onSquarePress={tapSquare}
      disabled={!answering}
    />
  );
  const controls = (
    <>
      <Palette active={tool} onPick={setTool} />
      <CheckBar
        placedCount={Object.keys(placed).length}
        submitting={!answering}
        canCheck
        onCheck={check}
        onClear={() => setPlaced({})}
      />
      {error ? <p className="px-3 text-center text-xs font-bold text-red-600">{error}</p> : null}
    </>
  );

  return (
    <GameShell title={t("exercises.chinese-board.title")} modeKey="play.practice" stat={stat}>
      <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {orientation === "landscape" ? (
          <div className="flex min-h-0 min-w-0 flex-1">
            {board}
            {/* Wide control column (w-92 = 368px): fits all 13 palette
                tools in 2 rows (7×44px + gaps = 332px ≤ 344px usable) and
                keeps the question on one line, so palette + بررسی stay
                visible without scrolling down to ~330px heights. The
                board is height-capped here, so it loses nothing. */}
            <aside className="flex w-92 shrink-0 flex-col gap-1 overflow-y-auto py-1">
              {question}
              {controls}
            </aside>
          </div>
        ) : (
          <>
            {question}
            {board}
            {controls}
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
// Speed feedback window: long enough to read the four counts + score,
// short enough to keep the 60s pace. The session timer keeps running.
const FEEDBACK_MS = 600;

function SpeedLoop() {
  const [phase, setPhase] = useState<SpeedPhase>("preparing");
  const [session, setSession] = useState<SpeedSummary | null>(null);
  const [, setQueueTick] = useState(0);
  const [current, setCurrent] = useState<Puzzle | null>(null);
  const [puzzlePhase, setPuzzlePhase] = useState<"memorizing" | "reconstructing" | "feedback">(
    "memorizing",
  );
  const [placed, setPlaced] = useState<BoardMap>({});
  const [tool, setTool] = useState<Tool | null>(null);
  const [usedHints, setUsedHints] = useState<string[]>([]);
  const [startedAt, setStartedAt] = useState<string>("");
  const [result, setResult] = useState<AttemptResponse | null>(null);
  const [report, setReport] = useState<SpeedReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());
  const [remainingMemMs, setRemainingMemMs] = useState(0);
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
      const sid = sessionIdRef.current;
      if (sid && sessionAliveRef.current) api.finishChineseSpeedSession(sid).catch(() => null);
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
      const data = await api.getChineseSpeedReport(sessionId);
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
    currentRef.current = puzzle;
    setCurrent(puzzle);
    setPlaced({});
    setTool(null);
    setUsedHints([]);
    setResult(null);
    setError(null);
    setStartedAt(new Date().toISOString());
    setRemainingMemMs(memorizeMsOf(puzzle));
    setPuzzlePhase("memorizing");
  }

  async function finishToReport(sessionId: string, gen: number) {
    if (finishingRef.current) return;
    finishingRef.current = true;
    cancelTransition();
    try {
      await api.finishChineseSpeedSession(sessionId).catch(() => null);
      const data = await api.getChineseSpeedReport(sessionId);
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
      if (prev) await api.finishChineseSpeedSession(prev).catch(() => null);
      const created = await api.startChineseSpeedSession();
      if (!alive(gen)) return;
      sessionIdRef.current = created.session_id;
      setSession({ ...created, attempted: 0, correct: 0, partial: 0, wrong: 0, score: 0 });
      const acc: Puzzle[] = [];
      let guard = 0;
      while (acc.length < MIN_BUFFER && guard < 6) {
        guard += 1;
        const batch = await api.prepareChineseSpeedPuzzles(created.session_id, { count: MIN_BUFFER });
        if (!alive(gen) || sessionIdRef.current !== created.session_id) return;
        for (const p of batch) {
          if (!acc.some((q) => q.id === p.id)) acc.push(p);
        }
      }
      if (acc.length < MIN_BUFFER) throw new Error("buffer_not_ready");
      const started = await api.startChineseSpeedClock(created.session_id);
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
      const batch = await api.prepareChineseSpeedPuzzles(sid, { count: REFILL_COUNT });
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

  // Visible countdown; the server still rejects late submits (410).
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

  // Per-puzzle memorize countdown (display budget only; the 60s clock above
  // keeps running throughout).
  useEffect(() => {
    if (phase !== "active" || puzzlePhase !== "memorizing" || !current) return;
    const deadline = Date.now() + remainingMemMs;
    const timer = setInterval(() => {
      const left = deadline - Date.now();
      if (left <= 0) {
        clearInterval(timer);
        setRemainingMemMs(0);
        setPuzzlePhase("reconstructing");
      } else {
        setRemainingMemMs(left);
      }
    }, 100);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, puzzlePhase, current]);

  const remainingMs = Math.max(0, deadlineRef.current - nowMs);
  const remainingSec = Math.ceil(remainingMs / 1000);

  function tapSquare(square: string) {
    if (phase !== "active" || puzzlePhase !== "reconstructing" || tool === null) return;
    setPlaced((prev) => {
      const next: BoardMap = { ...prev };
      if (tool === "eraser") {
        delete next[square];
      } else {
        next[square] = tool;
      }
      return next;
    });
  }

  async function check() {
    const puzzle = currentRef.current;
    const sid = sessionIdRef.current;
    if (phase !== "active" || puzzlePhase !== "reconstructing" || !puzzle || !sid || busyRef.current)
      return;
    busyRef.current = true;
    const gen = genRef.current;
    setBusy(true);
    setError(null);
    try {
      const res = await api.submitChineseSpeedAnswer(sid, {
        puzzle_id: puzzle.id,
        answer: { pieces: piecesToAnswer(placed) },
        hints_used: usedHints,
        started_at: startedAt,
      });
      if (!alive(gen) || sessionIdRef.current !== sid) {
        busyRef.current = false;
        return;
      }
      setResult(res.attempt);
      if (res.attempt.result === "correct") playSuccess();
      else playError();
      setSession(res.session);
      consecutiveSkipRef.current = 0;
      anchorDeadline(res.session.remaining_ms);
      setPuzzlePhase("feedback");
      transitionRef.current = window.setTimeout(() => {
        transitionRef.current = null;
        if (!alive(gen) || sessionIdRef.current !== sid) {
          busyRef.current = false;
          return;
        }
        advance();
      }, FEEDBACK_MS);
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
      const puzzle = await api.nextChineseSpeedPuzzle(sid);
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
      <GameShell title={t("exercises.chinese-board.title")} modeKey="play.speed">
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
      <GameShell title={t("exercises.chinese-board.title")} modeKey="play.speed">
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

  const totalMs = session.duration_s * 1000;
  const progress = Math.max(0, Math.min(1, remainingMs / totalMs));
  const hints = puzzle.hint_json.hints ?? [];
  const timer = (
    <TimerStrip remainingSec={remainingSec} correct={session.correct} progress={progress} />
  );
  const question = (
    <QuestionHeader
      prompt={
        puzzlePhase === "memorizing"
          ? t("chineseBoard.study")
          : puzzlePhase === "feedback"
            ? t("chineseBoard.score")
            : t("chineseBoard.reconstruct")
      }
      puzzleKey={puzzle.id}
      hints={hints}
      usedHints={usedHints}
      onUseHint={(id) => setUsedHints((p) => [...p, id])}
    />
  );

  if (puzzlePhase === "memorizing") {
    const board = (
      <FittedBoard areaRef={areaRef} size={size} pieces={fenToPieces(puzzle.fen)} disabled />
    );
    return (
      <GameShell title={t("exercises.chinese-board.title")} modeKey="play.speed">
        <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          {question}
          {timer}
          <MemorizeProgress remainingMs={remainingMemMs} totalMs={memorizeMsOf(puzzle)} />
          {board}
        </div>
      </GameShell>
    );
  }

  if (puzzlePhase === "feedback" && result) {
    return (
      <GameShell title={t("exercises.chinese-board.title")} modeKey="play.speed">
        <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
          {question}
          {timer}
          <ResultPanel puzzle={puzzle} placed={placed} result={result} compact />
        </div>
      </GameShell>
    );
  }

  const board = (
    <FittedBoard
      areaRef={areaRef}
      size={size}
      pieces={placed}
      onSquarePress={tapSquare}
      disabled={busy}
    />
  );
  const controls = (
    <>
      <Palette active={tool} onPick={setTool} />
      <CheckBar
        placedCount={Object.keys(placed).length}
        submitting={busy}
        canCheck
        onCheck={check}
        onClear={() => setPlaced({})}
      />
      {error ? <p className="px-3 text-center text-xs font-bold text-red-600">{error}</p> : null}
    </>
  );

  return (
    <GameShell title={t("exercises.chinese-board.title")} modeKey="play.speed">
      <div ref={rootRef} className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {orientation === "landscape" ? (
          <div className="flex min-h-0 min-w-0 flex-1">
            {board}
            {/* Same wide control column as practice (see above): with the
                extra timer strip, this is what keeps بررسی visible
                without scrolling at short landscape heights. */}
            <aside className="flex w-92 shrink-0 flex-col gap-1 overflow-y-auto py-1">
              {question}
              {timer}
              {controls}
            </aside>
          </div>
        ) : (
          <>
            {question}
            {timer}
            {board}
            {controls}
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
