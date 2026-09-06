import { useSearchParams } from "react-router-dom";
import { BalanceScalePlay, type BalanceScaleMode } from "../components/exercise/BalanceScalePlay";

// Balance Scale gameplay page (Exercise 10, ترازو). The home card's
// Practice/Speed buttons link here with ?mode= and enter their loop
// directly (no intermediate screen); totals, optimal counts, scoring,
// and the speed clock stay backend-authoritative. No chessboard: a
// dedicated tilting scale with black target pieces on one pan and the
// child's white pieces on the other; balance auto-submits server-side.
export function BalanceScalePage() {
  const [params] = useSearchParams();
  const mode: BalanceScaleMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <BalanceScalePlay key={mode} mode={mode} />;
}
