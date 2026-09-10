import { ExercisePlay } from "../components/exercise/ExercisePlay";

// Pin gameplay page. Opens the ordered-triplet board directly (no entry
// screen, no mode selector): the user taps the three pieces forming the
// pin in order — pinner, pinned piece, piece behind — and the backend
// decides whether the ordered triplet is correct.
export function PinPage() {
  return (
    <ExercisePlay
      config={{
        slug: "pin",
        titleKey: "exercises.pin.title",
        introKey: "pin.intro",
        targetOf: () => null,
        requiredSelection: 3,
        orderedSelection: true,
        directPlay: true,
        answerOf: (selected) => ({ squares: selected.slice(0, 3) }),
      }}
    />
  );
}
