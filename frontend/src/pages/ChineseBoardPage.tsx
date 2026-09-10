import { useSearchParams } from "react-router-dom";
import { ChineseBoardPlay, type ChineseBoardMode } from "../components/exercise/ChineseBoardPlay";

// Memorization Board gameplay page (صفحه‌ی حفظی). The home card's Practice/Speed
// buttons link here with ?mode= and enter their loop directly (no
// intermediate screen); the piece set, study budget, scoring, and the
// speed clock stay backend-authoritative. Each puzzle is shown read-only
// for piece_count * 400ms, then rebuilt from memory with a tap palette;
// the check button submits the full reconstruction for server grading.
export function ChineseBoardPage() {
  const [params] = useSearchParams();
  const mode: ChineseBoardMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <ChineseBoardPlay key={mode} mode={mode} />;
}
