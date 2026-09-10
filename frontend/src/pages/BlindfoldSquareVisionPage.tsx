import { useSearchParams } from "react-router-dom";
import { BlindfoldSquareVisionPlay, type SquareVisionMode } from "../components/exercise/BlindfoldSquareVisionPlay";

// Blindfold Square Vision gameplay page (خانه‌یابی ذهنی). The home card's
// Practice/Speed buttons link here with ?mode= and enter their loop
// directly (no intermediate screen); the color verdict, scoring (+5/−3),
// and the speed clock stay backend-authoritative. Practice shows an empty
// tappable board; Speed shows no board, only سفید/سیاه choices.
export function BlindfoldSquareVisionPage() {
  const [params] = useSearchParams();
  const mode: SquareVisionMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <BlindfoldSquareVisionPlay key={mode} mode={mode} />;
}
