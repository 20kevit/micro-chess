// FEN editing helpers for the admin Board Editor (client-side convenience).
// The server re-validates every saved position authoritatively;
// these helpers only keep the editor UI consistent.
import type { BoardMap } from "../components/chess/ChessBoard";
import type { PieceSymbol } from "../components/chess/ChessPiece";

export interface EditorPosition {
  pieces: BoardMap;
  turn: "w" | "b";
  castling: string;
  enPassant: string;
  halfmove: number;
  fullmove: number;
}

export const START_FEN =
  "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

export const EMPTY_FEN = "8/8/8/8/8/8/8/8 w - - 0 1";

const FILES = ["a", "b", "c", "d", "e", "f", "g", "h"];
const SYMBOLS = new Set(["k", "q", "r", "b", "n", "p"]);

export function isValidSquareName(square: string): boolean {
  if (typeof square !== "string" || square.length < 2 || square.length > 3) return false;
  const file = square[0].toLowerCase();
  const rank = Number(square.slice(1));
  return FILES.includes(file) && Number.isInteger(rank) && rank >= 1 && rank <= 8;
}

export function normalizeSquareName(square: string): string | null {
  const cleaned = square.trim().toLowerCase();
  return isValidSquareName(cleaned) ? cleaned : null;
}

export function parseFen(fen: string | null): EditorPosition | null {
  if (!fen || typeof fen !== "string") return null;
  const parts = fen.trim().split(/\s+/);
  if (parts.length < 2) return null;
  const rows = parts[0].split("/");
  if (rows.length !== 8) return null;
  const pieces: BoardMap = {};
  for (let rowIndex = 0; rowIndex < 8; rowIndex++) {
    const rank = 8 - rowIndex;
    let file = 0;
    for (const ch of rows[rowIndex]) {
      if (ch >= "1" && ch <= "8") {
        file += parseInt(ch, 10);
      } else if (SYMBOLS.has(ch.toLowerCase())) {
        if (file >= 8) return null;
        pieces[`${FILES[file]}${rank}`] = ch as PieceSymbol;
        file += 1;
      } else {
        return null;
      }
    }
    if (file !== 8) return null;
  }
  const turn = parts[1];
  if (turn !== "w" && turn !== "b") return null;
  const castling = parts[2] ?? "-";
  if (!/^(-|[KQkq]{1,4})$/.test(castling)) return null;
  const enPassant = parts[3] ?? "-";
  if (enPassant !== "-" && !isValidSquareName(enPassant)) return null;
  const halfmove = parts[4] !== undefined ? Number(parts[4]) : 0;
  const fullmove = parts[5] !== undefined ? Number(parts[5]) : 1;
  if (!Number.isInteger(halfmove) || halfmove < 0) return null;
  if (!Number.isInteger(fullmove) || fullmove < 1) return null;
  return { pieces, turn, castling, enPassant, halfmove, fullmove };
}

export function buildFen(position: EditorPosition): string {
  const rows: string[] = [];
  for (let rank = 8; rank >= 1; rank--) {
    let row = "";
    let empty = 0;
    for (const file of FILES) {
      const piece = position.pieces[`${file}${rank}`];
      if (!piece) {
        empty += 1;
      } else {
        if (empty > 0) {
          row += String(empty);
          empty = 0;
        }
        row += piece;
      }
    }
    if (empty > 0) row += String(empty);
    rows.push(row);
  }
  return `${rows.join("/")} ${position.turn} ${position.castling || "-"} ${
    position.enPassant || "-"
  } ${position.halfmove} ${position.fullmove}`;
}

export function pieceCount(position: EditorPosition): { white: number; black: number } {
  let white = 0;
  let black = 0;
  for (const symbol of Object.values(position.pieces)) {
    if (!symbol) continue;
    if (symbol === symbol.toUpperCase()) white += 1;
    else black += 1;
  }
  return { white, black };
}

const UCI_RE = /^[a-h][1-8][a-h][1-8][qrbn]?$/;

export function isValidUci(move: string): boolean {
  return typeof move === "string" && UCI_RE.test(move.trim().toLowerCase());
}

export function normalizeUci(move: string): string | null {
  const cleaned = move.trim().toLowerCase();
  return UCI_RE.test(cleaned) ? cleaned : null;
}

export function splitSquareList(raw: string): { valid: string[]; invalid: string[] } {
  const valid: string[] = [];
  const invalid: string[] = [];
  for (const part of raw.split(/[\s,;]+/)) {
    if (!part) continue;
    const square = normalizeSquareName(part);
    if (square) valid.push(square);
    else invalid.push(part);
  }
  return { valid, invalid };
}
