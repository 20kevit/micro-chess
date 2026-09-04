import { useId, useRef, useState } from "react";
import { ChessPiece, type PieceSymbol } from "./ChessPiece";

// Board is always LTR: a-file on the left in White orientation.
// Strict 8x8 grid: the container keeps aspect-ratio 1/1 with 8 equal row and
// column tracks, so every square is exactly 1/8 x 1/8 of the board.
// Pieces are absolutely positioned inside their square and can NEVER affect
// square dimensions (no content-based sizing anywhere in the grid).
export type BoardMap = Partial<Record<string, PieceSymbol>>;

export interface BoardArrow {
  from: string;
  to: string;
}

const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];
const RANKS = [8, 7, 6, 5, 4, 3, 2, 1];

const LONG_PRESS_MS = 450;
const DRAG_THRESHOLD_PX = 10;

interface Props {
  pieces?: BoardMap;
  orientation?: "white" | "black";
  onSquarePress?: (square: string) => void;
  selected?: string | null;
  /** Multi-square selection (e.g. piece-recognition answers). */
  selectedSquares?: string[];
  /** Explicit per-square visual state; wins over selection props. */
  squareStates?: Partial<Record<string, "selected" | "correct" | "missed" | "wrong" | "target">>;
  /** Disable interaction (e.g. after submitting). */
  disabled?: boolean;
  squareSize?: number;
  /** Allow dragging a piece onto another square (pointer + touch). */
  draggablePieces?: boolean;
  /** restricts drag initiation to these squares when set (null = any piece). */
  draggableSquares?: string[] | null;
  /** Allow drawing a move arrow (right-drag on desktop, long-press-drag on touch). */
  arrowsEnabled?: boolean;
  /** Currently displayed arrow (controlled by the parent). */
  arrow?: BoardArrow | null;
  /** Fired after a successful piece drop (replaces any arrow). */
  onMove?: (from: string, to: string) => void;
  /** Fired after an arrow gesture completes (replaces any arrow). */
  onArrowDraw?: (from: string, to: string) => void;
  /** Decorative square markers (e.g. the pathfinding goal star).
   * Never derived from the answer; the parent decides what to mark. */
  markers?: Partial<Record<string, "star">>;
}

const STATE_RING: Record<string, string> = {
  selected: "outline-4 outline -outline-offset-4 outline-violet-500",
  correct: "outline-4 outline -outline-offset-4 outline-green-500",
  missed: "outline-4 outline-dashed -outline-offset-4 outline-amber-500",
  wrong: "outline-4 outline -outline-offset-4 outline-red-500",
  // Marks the task's target piece. Never implies a correct destination.
  target: "outline-4 outline -outline-offset-4 outline-sky-400",
};

type GestureMode = "idle" | "pending" | "arrow" | "drag" | "dead";

interface DragPreview {
  symbol: PieceSymbol;
  x: number;
  y: number;
}

export function ChessBoard({
  pieces = {},
  orientation = "white",
  onSquarePress,
  selected = null,
  selectedSquares = [],
  squareStates = {},
  disabled = false,
  draggablePieces = false,
  draggableSquares = null,
  arrowsEnabled = false,
  arrow = null,
  onMove,
  onArrowDraw,
  markers = {},
}: Props) {
  const files = orientation === "white" ? FILES : [...FILES].reverse();
  const ranks = orientation === "white" ? RANKS : [...RANKS].reverse();
  const gesturesOn = draggablePieces || arrowsEnabled;

  const gridRef = useRef<HTMLDivElement | null>(null);
  // useId() contains colons which break SVG url(#…) references; strip them.
  const markerId = `mc-arrow-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const gesture = useRef({
    mode: "idle" as GestureMode,
    pointerId: -1,
    button: 0,
    origin: "",
    startX: 0,
    startY: 0,
    hasPiece: false,
    canDrag: false,
    timer: 0 as number | ReturnType<typeof setTimeout> | null,
    previewTo: "",
  });
  const [arrowPreview, setArrowPreview] = useState<BoardArrow | null>(null);
  const [dragPreview, setDragPreview] = useState<DragPreview | null>(null);

  function squareAt(clientX: number, clientY: number): string | null {
    const el = gridRef.current;
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return null;
    const fx = (clientX - rect.left) / rect.width;
    const fy = (clientY - rect.top) / rect.height;
    if (fx < 0 || fx >= 1 || fy < 0 || fy >= 1) return null;
    const col = Math.min(7, Math.floor(fx * 8));
    const row = Math.min(7, Math.floor(fy * 8));
    return `${files[col]}${ranks[row]}`;
  }

  function centerOf(square: string): { x: number; y: number } {
    return { x: files.indexOf(square[0]) + 0.5, y: ranks.indexOf(Number(square.slice(1))) + 0.5 };
  }

  function fractionAt(clientX: number, clientY: number): { x: number; y: number } | null {
    const el = gridRef.current;
    if (!el) return null;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return null;
    const x = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    const y = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height));
    return { x: x * 8, y: y * 8 };
  }

  function clearTimer() {
    if (gesture.current.timer !== null) {
      clearTimeout(gesture.current.timer as ReturnType<typeof setTimeout>);
      gesture.current.timer = null;
    }
  }

  function resetGesture() {
    clearTimer();
    gesture.current.mode = "idle";
    gesture.current.pointerId = -1;
    setArrowPreview(null);
    setDragPreview(null);
  }

  function capture(e: React.PointerEvent) {
    try {
      e.currentTarget.setPointerCapture(e.pointerId);
    } catch {
      // Pointer capture is best-effort (e.g. right button quirks).
    }
  }

  function handlePointerDown(e: React.PointerEvent) {
    if (!gesturesOn || disabled) return;
    if (gesture.current.mode !== "idle") return; // one gesture at a time
    const square = squareAt(e.clientX, e.clientY);
    if (!square) return;
    const g = gesture.current;
    g.pointerId = e.pointerId;
    g.button = e.button;
    g.origin = square;
    g.startX = e.clientX;
    g.startY = e.clientY;
    g.previewTo = square;
    g.hasPiece = pieces[square] !== undefined;
    g.canDrag = g.hasPiece && (!draggableSquares || draggableSquares.includes(square));
    capture(e);

    if (e.pointerType === "mouse") {
      if (e.button === 2 && arrowsEnabled) {
        g.mode = "arrow";
        setArrowPreview({ from: square, to: square });
        e.preventDefault();
        return;
      }
      if (e.button !== 0) {
        g.mode = "idle";
        g.pointerId = -1;
        return;
      }
      g.mode = "pending";
    } else {
      // Touch/pen: wait to distinguish tap, piece drag and long-press arrow.
      g.mode = "pending";
      g.timer = setTimeout(() => {
        if (gesture.current.mode !== "pending" || !arrowsEnabled) return;
        gesture.current.mode = "arrow";
        setDragPreview(null);
        setArrowPreview({ from: gesture.current.origin, to: gesture.current.origin });
      }, LONG_PRESS_MS);
    }
  }

  function handlePointerMove(e: React.PointerEvent) {
    const g = gesture.current;
    if (g.mode === "idle" || e.pointerId !== g.pointerId) return;
    if (g.mode === "pending") {
      const moved = Math.hypot(e.clientX - g.startX, e.clientY - g.startY) > DRAG_THRESHOLD_PX;
      if (!moved) return;
      clearTimer();
      if (g.canDrag && draggablePieces) {
        g.mode = "drag";
        const pos = fractionAt(e.clientX, e.clientY);
        const symbol = pieces[g.origin];
        if (pos && symbol) setDragPreview({ symbol, x: pos.x, y: pos.y });
      } else {
        // Slid off without a draggable piece: cancel, select nothing.
        g.mode = "dead";
      }
      return;
    }
    if (g.mode === "drag") {
      const pos = fractionAt(e.clientX, e.clientY);
      const symbol = pieces[g.origin];
      if (pos && symbol) setDragPreview({ symbol, x: pos.x, y: pos.y });
      return;
    }
    if (g.mode === "arrow") {
      const square = squareAt(e.clientX, e.clientY);
      if (square && square !== g.previewTo) {
        g.previewTo = square;
        setArrowPreview({ from: g.origin, to: square });
      }
    }
  }

  function handlePointerUp(e: React.PointerEvent) {
    const g = gesture.current;
    if (g.mode === "idle" || e.pointerId !== g.pointerId) return;
    clearTimer();
    const origin = g.origin;
    const isRightButton = g.button === 2;

    if (g.mode === "arrow") {
      const target = squareAt(e.clientX, e.clientY) ?? g.previewTo;
      if (!isRightButton) {
        // Touch long-press released: a real arrow replaces, same square taps through.
        if (target && target !== origin) onArrowDraw?.(origin, target);
        else onSquarePress?.(origin);
      } else if (target && target !== origin) {
        onArrowDraw?.(origin, target);
      }
    } else if (g.mode === "drag") {
      const target = squareAt(e.clientX, e.clientY);
      if (target && target !== origin) onMove?.(origin, target);
      else onSquarePress?.(origin);
    } else if (g.mode === "pending") {
      // Press + release without movement: plain tap.
      onSquarePress?.(origin);
    }
    // "dead" mode: finger slid away, select nothing.
    resetGesture();
  }

  function renderArrow(a: BoardArrow, key: string, preview: boolean) {
    if (a.from === a.to) return null;
    const p1 = centerOf(a.from);
    const p2 = centerOf(a.to);
    if (p1.x < 0.5 || p2.x < 0.5 || p1.y < 0.5 || p2.y < 0.5) return null;
    return (
      <g key={key} opacity={preview ? 0.55 : 0.9}>
        <line
          x1={p1.x}
          y1={p1.y}
          x2={p2.x}
          y2={p2.y}
          stroke="#7c3aed"
          strokeWidth={0.3}
          strokeLinecap="round"
          markerEnd={`url(#${markerId})`}
        />
      </g>
    );
  }

  return (
    <div
      dir="ltr"
      className="w-full select-none"
      role="grid"
      aria-label="chessboard"
      style={{
        touchAction: gesturesOn ? "none" : undefined,
        WebkitTouchCallout: gesturesOn ? "none" : undefined,
      }}
    >
      <div className="relative">
        <div
          ref={gridRef}
          className="grid aspect-square w-full grid-cols-8 grid-rows-8 overflow-hidden rounded-2xl shadow-md"
          onPointerDown={gesturesOn ? handlePointerDown : undefined}
          onPointerMove={gesturesOn ? handlePointerMove : undefined}
          onPointerUp={gesturesOn ? handlePointerUp : undefined}
          onPointerCancel={gesturesOn ? resetGesture : undefined}
          onLostPointerCapture={gesturesOn ? resetGesture : undefined}
          onContextMenu={gesturesOn ? (e) => e.preventDefault() : undefined}
        >
          {ranks.map((rank) =>
            files.map((file) => {
              const square = `${file}${rank}`;
              const isLight = (files.indexOf(file) + ranks.indexOf(rank)) % 2 === 1;
              const piece = pieces[square];
              const explicit = squareStates[square];
              const isSelected =
                explicit === "selected" ||
                (!explicit && (selected === square || selectedSquares.includes(square)));
              const ring = explicit ? STATE_RING[explicit] : isSelected ? STATE_RING.selected : "";
              return (
                <button
                  key={square}
                  type="button"
                  role="gridcell"
                  aria-label={square}
                  aria-pressed={isSelected}
                  disabled={disabled}
                  onPointerDown={gesturesOn ? undefined : () => onSquarePress?.(square)}
                  className={`relative block min-h-0 min-w-0 overflow-hidden ${
                    isLight ? "bg-amber-100" : "bg-emerald-600"
                  } ${ring}`}
                  style={{ touchAction: "manipulation" }}
                >
                  {piece ? (
                    <span className="pointer-events-none absolute inset-0 grid place-items-center p-[4%]">
                      <ChessPiece symbol={piece} />
                    </span>
                  ) : null}
                  {markers[square] === "star" ? (
                    <span
                      className="pointer-events-none absolute inset-0 grid place-items-center"
                      aria-hidden="true"
                    >
                      <svg viewBox="0 0 24 24" className="block h-[55%] w-[55%]">
                        <path
                          d="M12 2.5l2.95 5.98 6.6.96-4.78 4.66 1.13 6.58L12 17.57l-5.9 3.1 1.13-6.57L2.45 9.44l6.6-.96L12 2.5z"
                          fill="#fbbf24"
                          stroke="#92400e"
                          strokeWidth="1.2"
                          strokeLinejoin="round"
                        />
                      </svg>
                    </span>
                  ) : null}
                </button>
              );
            }),
          )}
        </div>
        {(arrowPreview ?? arrow) ? (
          <svg
            className="pointer-events-none absolute inset-0 h-full w-full"
            viewBox="0 0 8 8"
            aria-hidden="true"
          >
            <defs>
              <marker
                id={markerId}
                markerWidth={1.6}
                markerHeight={1.6}
                refX={1.1}
                refY={0.8}
                orient="auto"
                markerUnits="strokeWidth"
              >
                <path d="M0,0 L1.6,0.8 L0,1.6 Z" fill="#7c3aed" />
              </marker>
            </defs>
            {arrowPreview
              ? renderArrow(arrowPreview, "arrow-preview", true)
              : arrow
                ? renderArrow(arrow, "arrow-final", false)
                : null}
          </svg>
        ) : null}
        {dragPreview ? (
          <span
            className="pointer-events-none absolute z-10 grid place-items-center"
            style={{
              left: `${(dragPreview.x / 8) * 100}%`,
              top: `${(dragPreview.y / 8) * 100}%`,
              width: "12.5%",
              aspectRatio: "1 / 1",
              transform: "translate(-50%, -50%) scale(1.15)",
              filter: "drop-shadow(0 4px 6px rgb(0 0 0 / 0.4))",
            }}
            aria-hidden="true"
          >
            <span className="block h-[92%] w-[92%]">
              <ChessPiece symbol={dragPreview.symbol} />
            </span>
          </span>
        ) : null}
      </div>
    </div>
  );
}
