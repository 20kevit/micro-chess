import { ExercisePlay } from "../components/exercise/ExercisePlay";

// Get Out of Check gameplay page. Drag-only move input: arrows stay off and
// the from/to rings plus the move status line carry the selection.
export function GetOutOfCheckPage() {
  return (
    <ExercisePlay
      config={{
        slug: "get-out-of-check",
        titleKey: "exercises.get-out-of-check.title",
        introKey: "getoutcheck.intro",
        targetOf: () => null,
        moveInput: true,
        arrowsEnabled: false,
        requiredSelection: 2,
        answerOf: (selected, extra) => ({
          from: selected[0] ?? "",
          to: selected[1] ?? "",
          promotion: extra?.promotion ?? "q",
        }),
      }}
    />
  );
}
