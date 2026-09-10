import { ChessPiece, type PieceSymbol } from "../chess/ChessPiece";
import { faNum } from "./PieceGameLayout";

// Dedicated Balance Scale visual (Exercise 10, ترازو). No chessboard:
// a tilting beam with two hanging pans, each holding up to 10 pieces in
// a pyramid (1+2+3+4). Pure helpers are exported for tests; rendering
// only, the backend decides correctness, optimal counts, and scores.

// Display-only piece values (mirror the server; totals shown live while
// the child experiments, grading stays server-side).
export const PIECE_VALUES: Record<string, number> = { P: 1, N: 3, B: 3, R: 5, Q: 9 };
export const PIECE_ORDER = ["P", "N", "B", "R", "Q"];
export const MAX_PAN_PIECES = 10;
// Smooth bounded tilt: 25deg asymptote, ~half tilt at |diff| = 8.
export const MAX_ANGLE_DEG = 25;
export const ANGLE_SOFTNESS = 8;

export interface PanItem {
  uid: number;
  kind: string;
}

export function pieceValue(kind: string): number {
  return PIECE_VALUES[kind.toUpperCase()] ?? 0;
}

export function totalOf(kinds: string[]): number {
  return kinds.reduce((sum, kind) => sum + pieceValue(kind), 0);
}

/** Sort heaviest-first (stable for equal values) so heavy pieces sit lower. */
export function sortHeavyFirst<T extends { kind: string }>(items: T[]): T[] {
  return [...items]
    .map((item, index) => ({ item, index }))
    .sort(
      (a, b) => pieceValue(b.item.kind) - pieceValue(a.item.kind) || a.index - b.index,
    )
    .map((entry) => entry.item);
}

/** Arrange items into pyramid rows (top -> bottom), heaviest at the bottom.
 * The bottom row takes the heaviest items first: row sizes 1/2/3/4. */
export function layoutPyramid<T extends { kind: string }>(items: T[]): T[][] {
  const sorted = sortHeavyFirst(items);
  // Fill from the bottom row upward: 4 heaviest, then 3, 2, 1.
  const capacitiesBottomUp = [4, 3, 2, 1];
  const filledBottomUp: T[][] = [];
  let cursor = 0;
  for (const cap of capacitiesBottomUp) {
    filledBottomUp.push(sorted.slice(cursor, cursor + cap));
    cursor += cap;
  }
  return [filledBottomUp[3], filledBottomUp[2], filledBottomUp[1], filledBottomUp[0]];
}

/** Smooth bounded tilt angle for right-minus-left difference.
 * 0 when balanced; approaches ±MAX asymptotically, never jumps. */
export function scaleAngle(difference: number): number {
  if (!Number.isFinite(difference) || difference === 0) return 0;
  const magnitude = (MAX_ANGLE_DEG * Math.abs(difference)) / (Math.abs(difference) + ANGLE_SOFTNESS);
  return Math.sign(difference) * Math.min(MAX_ANGLE_DEG, magnitude);
}

export function asKindList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((entry): entry is string => typeof entry === "string")
    .map((entry) => entry.toUpperCase())
    .filter((entry) => entry in PIECE_VALUES);
}

function toSymbol(kind: string, black: boolean): PieceSymbol {
  const upper = kind.toUpperCase() as PieceSymbol;
  return (black ? upper.toLowerCase() : upper) as PieceSymbol;
}

export function PieceFigure({ kind, black }: { kind: string; black: boolean }) {
  return (
    <span className="relative block h-9 w-9 sm:h-11 sm:w-11" data-testid="piece-figure">
      <ChessPiece symbol={toSymbol(kind, black)} />
      <span className="absolute -bottom-1 -right-1 rounded-full bg-stone-800 px-1.5 text-[11px] font-black leading-4 text-white">
        {faNum(pieceValue(kind))}
      </span>
    </span>
  );
}

function PanPyramid({
  items,
  black,
  removable,
  disabled,
  onRemove,
  testId,
}: {
  items: PanItem[];
  black: boolean;
  removable: boolean;
  disabled: boolean;
  onRemove?: (uid: number) => void;
  testId: string;
}) {
  const rows = layoutPyramid(items);
  return (
    <div className="flex min-h-[190px] flex-col items-center justify-end gap-1" data-testid={testId}>
      {rows.map((row, r) => (
        <div key={r} className="flex min-h-[44px] items-end justify-center gap-1" data-testid={`${testId}-row-${r}`}>
          {row.map((item) =>
            removable ? (
              <button
                key={item.uid}
                type="button"
                data-testid="white-piece"
                aria-label={`${item.kind}`}
                disabled={disabled}
                onClick={() => onRemove?.(item.uid)}
                className="grid min-h-[44px] min-w-[44px] place-items-center rounded-xl transition motion-safe:duration-150 active:bg-white/60"
                style={{ touchAction: "manipulation" }}
              >
                <PieceFigure kind={item.kind} black={black} />
              </button>
            ) : (
              <span
                key={item.uid}
                data-testid="black-piece"
                className="grid min-h-[44px] min-w-[44px] place-items-center"
                aria-hidden="true"
              >
                <PieceFigure kind={item.kind} black={black} />
              </span>
            ),
          )}
        </div>
      ))}
    </div>
  );
}

export function BalanceScale({
  leftItems,
  rightItems,
  balanced,
  locked,
  onRemoveRight,
}: {
  leftItems: PanItem[];
  rightItems: PanItem[];
  balanced: boolean;
  locked: boolean;
  onRemoveRight: (uid: number) => void;
}) {
  const leftTotal = totalOf(leftItems.map((p) => p.kind));
  const rightTotal = totalOf(rightItems.map((p) => p.kind));
  const angle = scaleAngle(rightTotal - leftTotal);
  const panTone = balanced
    ? "border-green-500 bg-green-50"
    : "border-stone-300 bg-stone-100";
  return (
    <div data-testid="balance-scale" className="w-full overflow-hidden px-1">
      {/* Totals stay visible above the hero scale. */}
      <div className="mx-auto flex w-full max-w-md items-stretch justify-center gap-2 text-center">
        <div className="flex-1 rounded-2xl bg-stone-900 px-2 py-2 text-white">
          <p className="text-xs font-bold text-stone-300" data-testid="black-label">
            مهره‌های سیاه
          </p>
          <p className="text-2xl font-black" data-testid="black-total">
            {faNum(leftTotal)}
          </p>
        </div>
        <div
          className={`flex-1 rounded-2xl px-2 py-2 ${
            balanced ? "bg-green-600 text-white" : "bg-white text-stone-800 ring-2 ring-stone-200"
          }`}
        >
          <p className="text-xs font-bold opacity-80" data-testid="white-label">
            مهره‌های سفید
          </p>
          <p className="text-2xl font-black" data-testid="white-total">
            {faNum(rightTotal)}
          </p>
        </div>
      </div>

      {/* Scale: static stand + one rotating assembly (beam + both pans),
          so pieces stay visually attached to their pan while tilting.
          Headroom above the pivot absorbs the raised end at full tilt. */}
      <div dir="ltr" className="relative mx-auto mt-2 w-full max-w-md select-none">
        {/* Assembly height is dead space below the pans, not geometry: the
          stand stretches (bottom-0) and the beam/pans sit at fixed offsets,
          so this stays roomy on tall screens while fitting short ones. */}
        <div className="relative mx-auto w-full" style={{ minHeight: 350 }}>
          {/* Stand (never rotates). */}
          <div className="absolute bottom-0 left-1/2 top-28 w-3 -translate-x-1/2 rounded-full bg-amber-800" aria-hidden="true" />
          <div className="absolute bottom-0 left-1/2 h-4 w-24 -translate-x-1/2 rounded-t-2xl bg-amber-900" aria-hidden="true" />
          {/* Rotating assembly pivots at the beam center. */}
          <div
            className="absolute inset-x-2 top-24 transition-transform motion-safe:duration-500 motion-safe:ease-out"
            style={{ transform: `rotate(${angle}deg)`, transformOrigin: "50% 0%" }}
            data-testid="scale-beam"
            data-angle={angle.toFixed(2)}
          >
            {/* Beam */}
            <div className="relative mx-auto h-2.5 w-full rounded-full bg-amber-700" aria-hidden="true">
              <span className="absolute left-1/2 top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-amber-900 ring-4 ring-amber-200" />
            </div>
            {/* Hanging pans */}
            <div className="flex items-start justify-between gap-2 px-1">
              <div className="flex w-[46%] flex-col items-center">
                <div className="h-10 w-0.5 bg-stone-400" aria-hidden="true" />
                <div className={`w-full rounded-b-[2rem] rounded-t-lg border-2 px-1 pb-2 pt-1 ${panTone}`} data-testid="left-pan">
                  <PanPyramid items={leftItems} black removable={false} disabled testId="left-pyramid" />
                </div>
              </div>
              <div className="flex w-[46%] flex-col items-center">
                <div className="h-10 w-0.5 bg-stone-400" aria-hidden="true" />
                <div
                  className={`w-full rounded-b-[2rem] rounded-t-lg border-2 px-1 pb-2 pt-1 ${
                    balanced ? "border-green-500 bg-green-50" : "border-violet-400 bg-violet-50"
                  }`}
                  data-testid="right-pan"
                >
                  <PanPyramid
                    items={rightItems}
                    black={false}
                    removable
                    disabled={locked}
                    onRemove={onRemoveRight}
                    testId="right-pyramid"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function PieceInventory({
  onAdd,
  disabled,
  full,
}: {
  onAdd: (kind: string) => void;
  disabled: boolean;
  full: boolean;
}) {
  return (
    <div data-testid="inventory">
      <div className="flex flex-wrap items-stretch justify-center gap-2" dir="ltr">
        {PIECE_ORDER.map((kind) => (
          <button
            key={kind}
            type="button"
            data-testid={`inventory-${kind}`}
            aria-label={kind}
            disabled={disabled}
            onClick={() => onAdd(kind)}
            className={`flex min-h-[56px] min-w-[56px] flex-col items-center justify-center gap-0.5 rounded-2xl border-2 bg-white px-2 py-1 transition motion-safe:duration-150 active:scale-95 ${
              full ? "border-stone-200 opacity-70" : "border-violet-300 hover:border-violet-500"
            }`}
            style={{ touchAction: "manipulation" }}
          >
            <PieceFigure kind={kind} black={false} />
          </button>
        ))}
      </div>
    </div>
  );
}
