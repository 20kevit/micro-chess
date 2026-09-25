// Professional board editor for admin content authoring.
// Client-side convenience only: the server re-validates every saved
// position authoritatively (preview-validate + lifecycle gates).
import { useEffect, useMemo, useState } from "react";
import { ChessBoard } from "../chess/ChessBoard";
import { ChessPiece, type PieceSymbol } from "../chess/ChessPiece";
import { t } from "../../i18n";
import {
  EMPTY_FEN,
  START_FEN,
  buildFen,
  parseFen,
  type EditorPosition,
} from "../../lib/fenEditor";

interface BoardEditorProps {
  fen: string | null;
  onChange: (fen: string) => void;
  disabled?: boolean;
}

type Palette = PieceSymbol | "eraser" | "mover";

const PALETTE_PIECES: PieceSymbol[] = ["K", "Q", "R", "B", "N", "P", "k", "q", "r", "b", "n", "p"];

const CASTLING_FLAGS = ["K", "Q", "k", "q"] as const;

function defaultPosition(): EditorPosition {
  return parseFen(START_FEN)!;
}

export function BoardEditor({ fen, onChange, disabled = false }: BoardEditorProps) {
  const [position, setPosition] = useState<EditorPosition>(() => parseFen(fen) ?? defaultPosition());
  const [orientation, setOrientation] = useState<"white" | "black">("white");
  const [palette, setPalette] = useState<Palette>("mover");
  const [pendingSquare, setPendingSquare] = useState<string | null>(null);
  const [fenText, setFenText] = useState(fen ?? START_FEN);
  const [fenError, setFenError] = useState("");

  // Keep the editor in sync when the parent loads a different puzzle.
  useEffect(() => {
    const parsed = parseFen(fen);
    if (parsed) {
      setPosition(parsed);
      setFenText(fen ?? "");
      setFenError("");
      setPendingSquare(null);
    }
  }, [fen]);

  function commit(next: EditorPosition) {
    setPosition(next);
    const built = buildFen(next);
    setFenText(built);
    setFenError("");
    onChange(built);
  }

  function onSquarePress(square: string) {
    if (disabled) return;
    if (palette === "mover") {
      const occupant = position.pieces[square];
      if (pendingSquare === null) {
        if (occupant) setPendingSquare(square);
        return;
      }
      if (pendingSquare === square) {
        setPendingSquare(null);
        return;
      }
      const moving = position.pieces[pendingSquare];
      if (!moving) {
        setPendingSquare(null);
        return;
      }
      const pieces = { ...position.pieces };
      delete pieces[pendingSquare];
      pieces[square] = moving;
      setPendingSquare(null);
      commit({ ...position, pieces });
      return;
    }
    setPendingSquare(null);
    const pieces = { ...position.pieces };
    if (palette === "eraser") {
      delete pieces[square];
    } else {
      pieces[square] = palette;
    }
    commit({ ...position, pieces });
  }

  function applyFenText() {
    const parsed = parseFen(fenText);
    if (!parsed) {
      setFenError(t("admin.boardInvalidFen"));
      return;
    }
    setFenError("");
    setPendingSquare(null);
    commit(parsed);
  }

  const counts = useMemo(() => {
    let white = 0;
    let black = 0;
    for (const symbol of Object.values(position.pieces)) {
      if (!symbol) continue;
      if (symbol === symbol.toUpperCase()) white += 1;
      else black += 1;
    }
    return { white, black, total: white + black };
  }, [position.pieces]);

  function toggleCastling(flag: string) {
    const current = position.castling === "-" ? "" : position.castling;
    const next = current.includes(flag)
      ? current.replace(flag, "") || "-"
      : `${current}${flag}`
          .split("")
          .sort((a, b) => "KQkq".indexOf(a) - "KQkq".indexOf(b))
          .join("");
    commit({ ...position, castling: next });
  }

  const inputClass =
    "min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm";

  return (
    <div className="flex flex-col gap-3 lg:flex-row">
      <div className="flex-1">
        <div dir="ltr">
          <ChessBoard
            pieces={position.pieces}
            orientation={orientation}
            onSquarePress={onSquarePress}
            selected={pendingSquare}
            disabled={disabled}
          />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-stone-500">
          <span>
            {t("admin.boardPieceCount")}: {counts.total} ({t("admin.boardWhite")}: {counts.white} ·{" "}
            {t("admin.boardBlack")}: {counts.black})
          </span>
          <button
            type="button"
            disabled={disabled}
            onClick={() => setOrientation((o) => (o === "white" ? "black" : "white"))}
            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 font-bold text-violet-700"
          >
            {t("admin.boardFlip")}
          </button>
        </div>
      </div>
      <div className="flex w-full flex-col gap-3 lg:max-w-xs">
        <div>
          <p className="text-sm font-bold">{t("admin.boardTool")}</p>
          <div className="mt-2 grid grid-cols-7 gap-1" dir="ltr">
            <button
              type="button"
              disabled={disabled}
              title={t("admin.boardMove")}
              onClick={() => {
                setPalette("mover");
                setPendingSquare(null);
              }}
              className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl border text-lg ${
                palette === "mover" ? "border-violet-700 bg-violet-100" : "border-stone-200 bg-white"
              }`}
            >
              ✥
            </button>
            <button
              type="button"
              disabled={disabled}
              title={t("admin.boardEraser")}
              onClick={() => {
                setPalette("eraser");
                setPendingSquare(null);
              }}
              className={`flex min-h-[44px] min-w-[44px] items-center justify-center rounded-xl border text-lg ${
                palette === "eraser" ? "border-violet-700 bg-violet-100" : "border-stone-200 bg-white"
              }`}
            >
              ⌫
            </button>
            {PALETTE_PIECES.map((symbol) => (
              <button
                key={symbol}
                type="button"
                disabled={disabled}
                onClick={() => {
                  setPalette(symbol);
                  setPendingSquare(null);
                }}
                className={`h-[44px] w-[44px] rounded-xl border p-1 ${
                  palette === symbol ? "border-violet-700 bg-violet-100" : "border-stone-200 bg-white"
                }`}
              >
                <ChessPiece symbol={symbol} />
              </button>
            ))}
          </div>
          <p className="mt-1 text-xs text-stone-500">
            {palette === "mover"
              ? t("admin.boardMoveHint")
              : palette === "eraser"
                ? t("admin.boardEraserHint")
                : t("admin.boardPlaceHint")}
          </p>
        </div>
        <div>
          <p className="text-sm font-bold">{t("admin.boardSideToMove")}</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {(["w", "b"] as const).map((side) => (
              <button
                key={side}
                type="button"
                disabled={disabled}
                onClick={() => commit({ ...position, turn: side })}
                className={`min-h-[44px] rounded-xl border px-3 text-sm font-bold ${
                  position.turn === side
                    ? "border-violet-700 bg-violet-700 text-white"
                    : "border-stone-200 bg-white text-stone-600"
                }`}
              >
                {side === "w" ? t("admin.boardWhite") : t("admin.boardBlack")}
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="text-sm font-bold">{t("admin.boardCastling")}</p>
          <div className="mt-2 flex gap-2" dir="ltr">
            {CASTLING_FLAGS.map((flag) => {
              const active = position.castling.includes(flag);
              return (
                <button
                  key={flag}
                  type="button"
                  disabled={disabled}
                  onClick={() => toggleCastling(flag)}
                  className={`min-h-[44px] min-w-[44px] rounded-xl border px-2 font-black ${
                    active ? "border-violet-700 bg-violet-700 text-white" : "border-stone-200 bg-white"
                  }`}
                >
                  {flag}
                </button>
              );
            })}
          </div>
        </div>
        <div>
          <label className="text-sm font-bold" htmlFor="board-ep">
            {t("admin.boardEnPassant")}
          </label>
          <input
            id="board-ep"
            dir="ltr"
            disabled={disabled}
            value={position.enPassant}
            onChange={(e) => commit({ ...position, enPassant: e.target.value.trim() || "-" })}
            placeholder="-"
            className={`${inputClass} mt-1 w-full`}
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            disabled={disabled}
            onClick={() => commit({ ...parseFen(EMPTY_FEN)!, turn: position.turn })}
            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-bold"
          >
            {t("admin.boardClear")}
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={() => commit(defaultPosition())}
            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-bold"
          >
            {t("admin.boardReset")}
          </button>
        </div>
        <div>
          <label className="text-sm font-bold" htmlFor="board-fen">
            FEN
          </label>
          <textarea
            id="board-fen"
            dir="ltr"
            disabled={disabled}
            value={fenText}
            onChange={(e) => setFenText(e.target.value)}
            rows={3}
            className={`${inputClass} mt-1 w-full py-2 font-mono text-xs`}
          />
          {fenError ? <p className="mt-1 text-xs font-bold text-red-600">{fenError}</p> : null}
          <button
            type="button"
            disabled={disabled}
            onClick={applyFenText}
            className="mt-2 min-h-[44px] w-full rounded-xl bg-violet-700 px-3 text-sm font-bold text-white"
          >
            {t("admin.boardApplyFen")}
          </button>
        </div>
      </div>
    </div>
  );
}
