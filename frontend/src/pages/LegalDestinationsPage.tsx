import { ExercisePlay } from "../components/exercise/ExercisePlay";

// Legal Destinations gameplay page. The target square comes from the puzzle's
// position_json (part of the task); destinations stay server-authoritative.
export function LegalDestinationsPage() {
  return (
    <ExercisePlay
      config={{
        slug: "legal-destinations",
        titleKey: "exercises.legal-destinations.title",
        introKey: "legal.intro",
        targetOf: (puzzle) =>
          typeof puzzle.position_json.from === "string" ? puzzle.position_json.from : null,
      }}
    />
  );
}
