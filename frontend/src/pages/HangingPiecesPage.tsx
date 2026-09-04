import { ExercisePlay } from "../components/exercise/ExercisePlay";

// Hanging Pieces gameplay page. There is no single hunter square: the whole
// board is the question, so nothing is highlighted up front and only the
// user's selections are shown. Correctness stays server-authoritative.
export function HangingPiecesPage() {
  return (
    <ExercisePlay
      config={{
        slug: "hanging-pieces",
        titleKey: "exercises.hanging-pieces.title",
        introKey: "hanging.intro",
        targetOf: () => null,
      }}
    />
  );
}
