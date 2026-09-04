import { ExercisePlay } from "../components/exercise/ExercisePlay";
import { t } from "../i18n";

// Is it Checkmate gameplay page. Three fixed choices with Persian labels;
// the board only shows the position as context and stays read-only.
// The actual check state stays server-authoritative.
const OPTIONS = [
  { id: "checkmate", labelKey: "checkmate.checkmate", groupKey: "material.choose" },
  { id: "check", labelKey: "checkmate.check", groupKey: "material.choose" },
  { id: "not_check", labelKey: "checkmate.notCheck", groupKey: "material.choose" },
] as const;

function labelOf(id: string): string {
  const found = OPTIONS.find((item) => item.id === id);
  return found ? t(found.labelKey) : id;
}

export function CheckmatePage() {
  return (
    <ExercisePlay
      config={{
        slug: "is-checkmate",
        titleKey: "exercises.is-checkmate.title",
        introKey: "checkmate.intro",
        targetOf: () => null,
        answerOf: (selected) => ({ choice: selected[0] ?? "" }),
        options: [...OPTIONS],
        detailLabelOf: labelOf,
        requiredSelection: 1,
        singleChoice: true,
      }}
    />
  );
}
