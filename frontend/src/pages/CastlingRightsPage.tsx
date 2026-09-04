import { ExercisePlay } from "../components/exercise/ExercisePlay";
import { t } from "../i18n";

// Castling Rights gameplay page. The four options are fixed choices with
// Persian labels; the board only shows the position as context. Which
// options are legal stays server-authoritative.
const OPTIONS = [
  { id: "white_kingside", labelKey: "castling.white_kingside", groupKey: "castling.white" },
  { id: "white_queenside", labelKey: "castling.white_queenside", groupKey: "castling.white" },
  { id: "black_kingside", labelKey: "castling.black_kingside", groupKey: "castling.black" },
  { id: "black_queenside", labelKey: "castling.black_queenside", groupKey: "castling.black" },
] as const;

function labelOf(id: string): string {
  const found = OPTIONS.find((item) => item.id === id);
  return found ? t(found.labelKey) : id;
}

export function CastlingRightsPage() {
  return (
    <ExercisePlay
      config={{
        slug: "castling-rights",
        titleKey: "exercises.castling-rights.title",
        introKey: "castling.intro",
        targetOf: () => null,
        answerOf: (selected) => ({ options: selected }),
        options: [...OPTIONS],
        detailLabelOf: labelOf,
      }}
    />
  );
}
