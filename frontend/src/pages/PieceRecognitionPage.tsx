import { ExercisePlay } from "../components/exercise/ExercisePlay";

// Piece Recognition gameplay page. Thin config over the shared play loop;
// correctness, scoring, and rating stay backend-authoritative.
export function PieceRecognitionPage() {
  return (
    <ExercisePlay
      config={{
        slug: "piece-recognition",
        titleKey: "piece.title",
        introKey: "piece.intro",
        targetOf: () => null,
      }}
    />
  );
}
