import { ExercisePlay } from "../components/exercise/ExercisePlay";

// Give Check gameplay page. The user picks from→to on the board; both
// exercise modes currently accept any legal checking move, and the mode
// travels in the data model so future logic can diverge cleanly.
export function GiveCheckPage() {
  return (
    <ExercisePlay
      config={{
        slug: "give-check",
        titleKey: "exercises.give-check.title",
        introKey: "givecheck.intro",
        targetOf: () => null,
        moveInput: true,
        requiredSelection: 2,
        answerOf: (selected, extra) => ({
          from: selected[0] ?? "",
          to: selected[1] ?? "",
          promotion: extra?.promotion ?? "q",
        }),
        exerciseModes: [
          { id: "all-checks", labelKey: "givecheck.allChecks" },
          { id: "appropriate-checks", labelKey: "givecheck.appropriateChecks" },
        ],
        exerciseModeLabelKey: "givecheck.exerciseMode",
        modeOf: (puzzle) =>
          typeof puzzle.position_json.mode === "string" ? puzzle.position_json.mode : null,
      }}
    />
  );
}
