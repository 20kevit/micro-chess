import { useSearchParams } from "react-router-dom";
import { PathfindingPlay, type PathfindingMode } from "../components/exercise/PathfindingPlay";

// Pathfinding gameplay page. The home card's Practice/Speed buttons link
// here with ?mode= and enter their loop directly (no intermediate screen);
// legality, optimal counts, scoring, and the speed clock stay
// backend-authoritative. The user walks one white piece to the star with
// drag or repeated clicks; arrival auto-submits the path server-side.
export function PathfindingPage() {
  const [params] = useSearchParams();
  const mode: PathfindingMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <PathfindingPlay key={mode} mode={mode} />;
}
