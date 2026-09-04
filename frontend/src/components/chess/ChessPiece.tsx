// SVG chess pieces served as static files (no runtime CDN dependency).
// Set: Cburnett pieces (as used by Lichess), originally by Colin M.L. Burnett,
// licensed GFDL/BSD. Files live in frontend/public/chess-pieces/.
// No Unicode chess glyphs anywhere in the UI.

export type PieceSymbol =
  | "K" | "Q" | "R" | "B" | "N" | "P"
  | "k" | "q" | "r" | "b" | "n" | "p";

export function pieceAsset(symbol: PieceSymbol): string {
  const color = symbol === symbol.toUpperCase() ? "w" : "b";
  return `/chess-pieces/${color}${symbol.toUpperCase()}.svg`;
}

export function ChessPiece({ symbol, className = "" }: { symbol: PieceSymbol; className?: string }) {
  // Fills a positioned wrapper provided by the parent square, so the image
  // can never influence the square's size.
  return (
    <img
      src={pieceAsset(symbol)}
      alt=""
      aria-hidden="true"
      draggable={false}
      className={`pointer-events-none block h-full w-full ${className}`}
    />
  );
}
