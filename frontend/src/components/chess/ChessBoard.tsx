import { ChessPiece, type PieceSymbol } from "./ChessPiece";

// Board is always LTR: a-file on the left in White orientation.
// Strict 8x8 grid: the container keeps aspect-ratio 1/1 with 8 equal row and
// column tracks, so every square is exactly 1/8 x 1/8 of the board.
// Pieces are absolutely positioned inside their square and can NEVER affect
// square dimensions (no content-based sizing anywhere in the grid).
export type BoardMap = Partial<Record<string, PieceSymbol>>;

const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];
const RANKS = [8, 7, 6, 5, 4, 3, 2, 1];

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
}

const STATE_RING: Record<string, string> = {
  selected: "outline-4 outline -outline-offset-4 outline-violet-500",
  correct: "outline-4 outline -outline-offset-4 outline-green-500",
  missed: "outline-4 outline-dashed -outline-offset-4 outline-amber-500",
  wrong: "outline-4 outline -outline-offset-4 outline-red-500",
  // Marks the task's target piece. Never implies a correct destination.
  target: "outline-4 outline -outline-offset-4 outline-sky-400",
};

export function ChessBoard({
  pieces = {},
  orientation = "white",
  onSquarePress,
  selected = null,
  selectedSquares = [],
  squareStates = {},
  disabled = false,
}: Props) {
  const files = orientation === "white" ? FILES : [...FILES].reverse();
  const ranks = orientation === "white" ? RANKS : [...RANKS].reverse();

  return (
    <div dir="ltr" className="w-full select-none" role="grid" aria-label="chessboard">
      <div className="grid aspect-square w-full grid-cols-8 grid-rows-8 overflow-hidden rounded-2xl shadow-md">
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
                onPointerDown={() => onSquarePress?.(square)}
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
              </button>
            );
          }),
        )}
      </div>
    </div>
  );
}
