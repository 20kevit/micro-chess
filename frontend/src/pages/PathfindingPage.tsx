import { PathfindingPlay } from "../components/exercise/PathfindingPlay";

// Pathfinding gameplay page. Multi-step play reusing the shared board,
// attempt, timing, hint and feedback primitives.
export function PathfindingPage() {
  return (
    <PathfindingPlay
      slug="pathfinding"
      titleKey="exercises.pathfinding.title"
      introKey="pathfinding.intro"
    />
  );
}
