import { useSearchParams } from "react-router-dom";
import {
  PathfindingObstaclesPlay,
  type ObstaclePathfindingMode,
} from "../components/exercise/PathfindingObstaclesPlay";

// Pathfinding-with-obstacles gameplay page. The home card's
// Practice/Speed buttons link here with ?mode= and enter their loop
// directly (no intermediate screen); legality (movement, blocking,
// destination safety, capture rules), optimal counts, scoring, and the
// speed clock stay backend-authoritative. The user walks one white piece
// to the star around/through black enemies with drag or repeated clicks;
// arrival auto-submits the path server-side.
export function PathfindingObstaclesPage() {
  const [params] = useSearchParams();
  const mode: ObstaclePathfindingMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <PathfindingObstaclesPlay key={mode} mode={mode} />;
}
