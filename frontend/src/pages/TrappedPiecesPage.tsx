import { useSearchParams } from "react-router-dom";
import { TrappedPiecesPlay, type TrappedMode } from "../components/exercise/TrappedPiecesPlay";

// Trapped Pieces gameplay page. The home card's Practice/Speed buttons
// link here with ?mode= and enter their loop directly (no intermediate
// screen); correctness, scoring, and the speed clock stay
// backend-authoritative. The whole board is the question, so nothing is
// highlighted up front; trapped squares stay server-authoritative.
// Practice allows multi-select + confirm; Speed taps submit immediately
// (single-answer positions only).
export function TrappedPiecesPage() {
  const [params] = useSearchParams();
  const mode: TrappedMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <TrappedPiecesPlay key={mode} mode={mode} />;
}
