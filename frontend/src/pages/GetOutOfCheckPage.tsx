import { useSearchParams } from "react-router-dom";
import { GetOutOfCheckPlay, type GetOutOfCheckMode } from "../components/exercise/GetOutOfCheckPlay";

// Get Out of Check gameplay page. The home card's Practice/Speed buttons link
// here with ?mode= and enter their loop directly (no intermediate screen);
// correctness, scoring, and the speed clock stay backend-authoritative.
// The user draws one arrow per escaping move (from->to); the complete set
// is submitted together and graded server-side.
export function GetOutOfCheckPage() {
  const [params] = useSearchParams();
  const mode: GetOutOfCheckMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <GetOutOfCheckPlay key={mode} mode={mode} />;
}
