import { ExercisePlay } from "../components/exercise/ExercisePlay";

// Pin gameplay page. Drag-only move input: arrows stay off and the from/to
// rings plus the move status line carry the selection.
export function PinPage() {
  return (
    <ExercisePlay
      config={{
        slug: "pin",
        titleKey: "exercises.pin.title",
        introKey: "pin.intro",
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
