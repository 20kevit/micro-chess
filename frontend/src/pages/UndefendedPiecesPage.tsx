import { useSearchParams } from "react-router-dom";
import { UndefendedPiecesPlay, type UndefendedMode } from "../components/exercise/UndefendedPiecesPlay";

// Undefended Pieces gameplay page. The home card's Practice/Speed buttons
// link here with ?mode= and enter their loop directly (no intermediate
// screen); correctness, scoring, and the speed clock stay
// backend-authoritative. The whole board is the question, so nothing is
// highlighted up front; undefended squares stay server-authoritative.
export function UndefendedPiecesPage() {
  const [params] = useSearchParams();
  const mode: UndefendedMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <UndefendedPiecesPlay key={mode} mode={mode} />;
}
