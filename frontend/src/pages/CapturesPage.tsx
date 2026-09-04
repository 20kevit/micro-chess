import { ExercisePlay } from "../components/exercise/ExercisePlay";

// Captures gameplay page. The hunter square comes from the puzzle's
// position_json (part of the task); capturable squares stay server-authoritative.
export function CapturesPage() {
  return (
    <ExercisePlay
      config={{
        slug: "captures",
        titleKey: "exercises.captures.title",
        introKey: "captures.intro",
        targetOf: (puzzle) =>
          typeof puzzle.position_json.from === "string" ? puzzle.position_json.from : null,
      }}
    />
  );
}
