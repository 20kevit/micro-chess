import { MemoryBoardPlay } from "../components/exercise/MemoryBoardPlay";

// Memory Board gameplay page. Two phases per puzzle: memorize the shown
// position against a countdown, then rebuild it piece by piece.
export function MemoryBoardPage() {
  return (
    <MemoryBoardPlay
      slug="memory-board"
      titleKey="exercises.memory-board.title"
      introKey="memory.intro"
    />
  );
}
