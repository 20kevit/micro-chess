import { useSearchParams } from "react-router-dom";
import { CapturesPlay, type CaptureMode } from "../components/exercise/CapturesPlay";

// Captures gameplay page. The home card's Practice/Speed buttons link here
// with ?mode= and enter their loop directly (no intermediate screen);
// correctness, scoring, and the speed clock stay backend-authoritative.
// The hunter (white attacker) square comes from the puzzle's position_json
// (part of the task); capturable black-piece squares stay
// server-authoritative.
export function CapturesPage() {
  const [params] = useSearchParams();
  const mode: CaptureMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <CapturesPlay key={mode} mode={mode} />;
}
