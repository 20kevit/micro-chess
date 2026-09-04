import { ExercisePlay } from "../components/exercise/ExercisePlay";

// Equal Attackers & Defenders gameplay page. There is no single hunter
// square: the whole board is the question, so nothing is highlighted up
// front and only the user's selections are shown. Correctness stays
// server-authoritative.
export function EqualAttackersDefendersPage() {
  return (
    <ExercisePlay
      config={{
        slug: "equal-attackers-defenders",
        titleKey: "exercises.equal-attackers-defenders.title",
        introKey: "equal.intro",
        targetOf: () => null,
      }}
    />
  );
}
