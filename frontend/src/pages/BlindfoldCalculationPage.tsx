import { useSearchParams } from "react-router-dom";
import { BlindfoldCalculationPlay, type BlindfoldCalculationMode } from "../components/exercise/BlindfoldCalculationPlay";

// Blindfold Calculation gameplay page (محاسبه‌ی ذهنی). The home card's
// Practice/Speed buttons link here with ?mode= and enter their loop
// directly (no intermediate screen); the solution move, scoring, and
// the speed clock stay backend-authoritative. No board is shown at any
// point: the Persian position description plus a SAN input is the whole
// interface.
export function BlindfoldCalculationPage() {
  const [params] = useSearchParams();
  const mode: BlindfoldCalculationMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <BlindfoldCalculationPlay key={mode} mode={mode} />;
}
