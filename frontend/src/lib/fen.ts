// Display-only FEN parser (piece placement → square map).
// Used only to RENDER the board. Never for correctness decisions;
// the backend is authoritative for validation.
import type { BoardMap } from "../components/chess/ChessBoard";
import type { PieceSymbol } from "../components/chess/ChessPiece";

const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];
const SYMBOLS = new Set(["k", "q", "r", "b", "n", "p"]);

export function fenToPieces(fen: string | null): BoardMap {
  const map: BoardMap = {};
  if (!fen) return map;
  const rows = fen.split(" ")[0].split("/");
  if (rows.length !== 8) return map;
  for (let rowIndex = 0; rowIndex < 8; rowIndex++) {
    const rank = 8 - rowIndex;
    let file = 0;
    for (const ch of rows[rowIndex]) {
      if (file >= 8) break;
      if (ch >= "1" && ch <= "8") {
        file += parseInt(ch, 10);
      } else if (SYMBOLS.has(ch.toLowerCase())) {
        map[`${FILES[file]}${rank}`] = ch as PieceSymbol;
        file += 1;
      } else {
        break; // Invalid row: stop this rank, keep the rest.
      }
    }
  }
  return map;
}
