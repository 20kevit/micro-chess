import { useSearchParams } from "react-router-dom";
import { HeavierSidePlay, type HeavierSideMode } from "../components/exercise/HeavierSidePlay";

// Heavier Side gameplay page (کدام طرف سنگین‌تر؟). The home card's
// Practice/Speed buttons link here with ?mode= and enter their loop
// directly (no intermediate screen); the material verdict, scoring, and
// the speed clock stay backend-authoritative. A real board position is
// shown read-only with three large material choices (سفید/سیاه/مساوی);
// tapping a choice submits immediately with no material totals shown.
export function MaterialComparisonPage() {
  const [params] = useSearchParams();
  const mode: HeavierSideMode = params.get("mode") === "speed" ? "speed" : "practice";
  return <HeavierSidePlay key={mode} mode={mode} />;
}
