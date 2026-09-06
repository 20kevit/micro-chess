import { useSearchParams } from "react-router-dom";
import { GivingCheckPlay, type GivingCheckMode } from "../components/exercise/GivingCheckPlay";

// Giving Check gameplay page. The home card's Practice/Speed buttons link
// here with ?mode= and enter their loop directly (no intermediate screen);
// correctness, scoring, and the speed clock stay backend-authoritative.
// The user draws one arrow per checking move (from->to); the complete set
// is submitted together and graded server-side.
export function GiveCheckPage() {
  const [params] = useSearchParams();
  const mode: GivingCheckMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <GivingCheckPlay key={mode} mode={mode} />;
}
