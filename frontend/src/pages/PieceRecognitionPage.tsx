import { useSearchParams } from "react-router-dom";
import { PieceRecognitionPlay, type PieceMode } from "../components/exercise/PieceRecognitionPlay";

// Piece Recognition gameplay page. Practice (untimed) and Speed (60s) modes
// enter via ?mode= from the exercise card; correctness, scoring, and the
// speed clock stay backend-authoritative.
export function PieceRecognitionPage() {
  const [params] = useSearchParams();
  const initial: PieceMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <PieceRecognitionPlay key={initial} initialMode={initial} />;
}
