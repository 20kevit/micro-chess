import { useSearchParams } from "react-router-dom";
import { PieceRecognitionPlay, type PieceMode } from "../components/exercise/PieceRecognitionPlay";

// Piece Recognition gameplay page. The home card's Practice/Speed buttons
// link here with ?mode= and enter their loop directly (no intermediate
// screen); correctness, scoring, and the speed clock stay
// backend-authoritative.
export function PieceRecognitionPage() {
  const [params] = useSearchParams();
  const mode: PieceMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <PieceRecognitionPlay key={mode} mode={mode} />;
}
