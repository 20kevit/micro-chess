import { useSearchParams } from "react-router-dom";
import { LegalDestinationsPlay, type LegalMode } from "../components/exercise/LegalDestinationsPlay";

// Legal Destinations gameplay page. The home card's Practice/Speed buttons
// link here with ?mode= and enter their loop directly (no intermediate
// screen); correctness, scoring, and the speed clock stay
// backend-authoritative. The target square comes from the puzzle's
// position_json (part of the task); destinations stay server-authoritative.
export function LegalDestinationsPage() {
  const [params] = useSearchParams();
  const mode: LegalMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <LegalDestinationsPlay key={mode} mode={mode} />;
}
