import { BalanceScalePlay } from "../components/exercise/BalanceScalePlay";

// Balance Scale gameplay page. No chessboard here: pieces are dragged
// between the bank and the left pan until both sides balance.
export function BalanceScalePage() {
  return (
    <BalanceScalePlay
      slug="balance-scale"
      titleKey="exercises.balance-scale.title"
      introKey="balance.intro"
    />
  );
}
