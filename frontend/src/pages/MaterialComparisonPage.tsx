import { ExercisePlay } from "../components/exercise/ExercisePlay";
import { ChessPiece } from "../components/chess/ChessPiece";
import { t } from "../i18n";
import type { Puzzle } from "../api/types";
import type { AttemptResponse } from "../api/types";

const faNum = (n: number) => n.toLocaleString("fa-IR");

const OPTIONS = [
  { id: "left", labelKey: "balance.leftSide", groupKey: "material.choose" },
  { id: "equal", labelKey: "material.equal", groupKey: "material.choose" },
  { id: "right", labelKey: "balance.rightSide", groupKey: "material.choose" },
] as const;

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === "string");
}

function labelOf(id: string): string {
  const found = OPTIONS.find((item) => item.id === id);
  return found ? t(found.labelKey) : id;
}

function SidePieces({ pieces }: { pieces: string[] }) {
  return (
    <div className="flex min-h-[76px] flex-wrap content-start items-start justify-center gap-1">
      {pieces.map((kind, i) => (
        <span key={`${kind}-${i}`} className="block h-12 w-12">
          <ChessPiece symbol={kind as "P"} />
        </span>
      ))}
    </div>
  );
}

function SidesDisplay({ puzzle }: { puzzle: Puzzle }) {
  const left = asStringList(puzzle.position_json.left);
  const right = asStringList(puzzle.position_json.right);
  return (
    <div dir="ltr" className="mt-3 grid grid-cols-2 gap-3">
      <div className="rounded-2xl border-2 border-stone-200 bg-white p-3">
        <p className="text-center text-sm font-black text-stone-700">{t("balance.leftSide")}</p>
        <SidePieces pieces={left} />
      </div>
      <div className="rounded-2xl border-2 border-stone-200 bg-white p-3">
        <p className="text-center text-sm font-black text-stone-700">{t("balance.rightSide")}</p>
        <SidePieces pieces={right} />
      </div>
    </div>
  );
}

function TotalsReveal({ result }: { result: AttemptResponse }) {
  const left = result.detail.left_value;
  const right = result.detail.right_value;
  if (left === undefined || right === undefined) return null;
  return (
    <p className="mt-3 text-sm font-bold">
      {t("balance.leftSide")}: {faNum(left)} / {t("balance.rightSide")}: {faNum(right)}
    </p>
  );
}

// Material Comparison gameplay page. Three fixed choices with Persian
// labels; both sides render as SVG pieces with no values shown. Which side
// is heavier stays server-authoritative.
export function MaterialComparisonPage() {
  return (
    <ExercisePlay
      config={{
        slug: "heavier-side",
        titleKey: "exercises.heavier-side.title",
        introKey: "material.intro",
        targetOf: () => null,
        answerOf: (selected) => ({ choice: selected[0] ?? "" }),
        options: [...OPTIONS],
        detailLabelOf: labelOf,
        requiredSelection: 1,
        singleChoice: true,
        hideBoard: true,
        renderPuzzleContent: (puzzle) => <SidesDisplay puzzle={puzzle} />,
        renderResultExtra: (result) => <TotalsReveal result={result} />,
      }}
    />
  );
}
