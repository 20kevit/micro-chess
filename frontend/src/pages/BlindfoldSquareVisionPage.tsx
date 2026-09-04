import { BlindfoldSquareVisionPlay } from "../components/exercise/BlindfoldSquareVisionPlay";

// Blindfold Square Vision gameplay page. Empty board with neutral markers;
// the answer is a number entered in a touch-friendly input.
export function BlindfoldSquareVisionPage() {
  return (
    <BlindfoldSquareVisionPlay
      slug="blindfold-square-vision"
      titleKey="exercises.blindfold-square-vision.title"
      introKey="blindfold.intro"
    />
  );
}
