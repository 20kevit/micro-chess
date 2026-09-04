import { ChessPiece, type PieceSymbol } from "./ChessPiece";

// Board is always LTR: a-file on the left in White orientation.
// Wrap usage in dir="ltr". Touch-friendly squares (pointer events, large targets).
export type BoardMap = Partial<Record<string, PieceSymbol>>;

const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];
const RANKS = [8, 7, 6, 5, 4, 3, 2, 1];

interface Props {
  pieces?: BoardMap;
  orientation?: "white" | "black";
  onSquarePress?: (square: string) => void;
  selected?: string | null;
  squareSize?: number;
}

export function ChessBoard({
  pieces = {},
  orientation = "white",
  onSquarePress,
  selected = null,
}: Props) {
  const files = orientation === "white" ? FILES : [...FILES].reverse();
  const ranks = orientation === "white" ? RANKS : [...RANKS].reverse();

  return (
    <div dir="ltr" className="w-full select-none" role="grid" aria-label="chessboard">
      <div className="grid aspect-square w-full grid-cols-8 overflow-hidden rounded-2xl shadow-md">
        {ranks.map((rank) =>
          files.map((file) => {
            const square = `${file}${rank}`;
            const isLight = (files.indexOf(file) + ranks.indexOf(rank)) % 2 === 1;
            const piece = pieces[square];
            const isSelected = selected === square;
            return (
              <button
                key={square}
                role="gridcell"
                aria-label={square}
                onPointerDown={() => onSquarePress?.(square)}
                className={`flex items-center justify-center text-lg ${
                  isLight ? "bg-amber-100" : "bg-emerald-600"
                } ${isSelected ? "outline-4 outline -outline-offset-4 outline-violet-500" : ""}`}
                style={{ touchAction: "manipulation" }}
              >
                {piece ? <ChessPiece symbol={piece} /> : null}
              </button>
            );
          }),
        )}
      </div>
    </div>
  );
}
