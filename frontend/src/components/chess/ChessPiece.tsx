// Simple inline SVG pieces. No Unicode symbols in UI.
import type { ReactElement } from "react";

export type PieceSymbol =
  | "K" | "Q" | "R" | "B" | "N" | "P"
  | "k" | "q" | "r" | "b" | "n" | "p";

// Minimal friendly glyphs drawn as text-free SVG paths/shapes.
// Real art can replace these paths later without changing call sites.
const PATHS: Record<string, ReactElement> = {
  p: <ellipse cx="12" cy="14" rx="6" ry="7" />,
  n: <path d="M6 20 L10 4 L14 10 L18 6 L16 20 Z" />,
  b: <path d="M12 3 L17 12 L12 21 L7 12 Z" />,
  r: <path d="M7 4 H17 V9 H15 V20 H9 V9 H7 Z" />,
  q: <circle cx="12" cy="12" r="8" />,
  k: <path d="M8 4 H16 V10 L20 14 L16 18 V21 H8 V18 L4 14 L8 10 Z" />,
};

export function ChessPiece({ symbol }: { symbol: PieceSymbol }) {
  const isWhite = symbol === symbol.toUpperCase();
  const key = symbol.toLowerCase();
  return (
    <svg viewBox="0 0 24 24" className="h-4/5 w-4/5" aria-hidden="true">
      <g
        fill={isWhite ? "#ffffff" : "#1f2430"}
        stroke={isWhite ? "#1f2430" : "#ffffff"}
        strokeWidth="1.4"
        strokeLinejoin="round"
      >
        {PATHS[key]}
      </g>
    </svg>
  );
}
