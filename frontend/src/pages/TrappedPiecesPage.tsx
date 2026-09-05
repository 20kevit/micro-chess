import { ExercisePlay } from "../components/exercise/ExercisePlay";

// Trapped Pieces gameplay page. There is no single hunter square: the whole
// board is the question, so nothing is highlighted up front and only the
// user's selections are shown. Correctness stays server-authoritative.
export function TrappedPiecesPage() {
  return (
    <ExercisePlay
      config={{
        slug: "trapped-pieces",
        titleKey: "exercises.trapped-pieces.title",
        introKey: "trapped.intro",
        targetOf: () => null,
      }}
    />
  );
}
