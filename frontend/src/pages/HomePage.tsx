import { Link } from "react-router-dom";
import { ChessBoard } from "../components/chess/ChessBoard";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

// Home: what MicroChess is + one clear action into the exercise catalog.
// Presentational only; exercise logic lives in backend.
export function HomePage() {
  return (
    <div>
      <PageHeader title={t("app.name")} subtitle={t("home.subtitle")} />
      <Card>
        <ChessBoard
          pieces={{
            e1: "K",
            d1: "Q",
            a1: "R",
            h1: "R",
            c1: "B",
            f1: "B",
            b1: "N",
            g1: "N",
            a2: "P",
            e2: "P",
            e8: "k",
          }}
          disabled
        />
        <p className="mt-3 text-center text-sm text-stone-500">{t("home.preview")}</p>
        <Link to="/exercises" className="mt-3 block">
          <Button className="w-full">{t("home.cta")}</Button>
        </Link>
      </Card>
    </div>
  );
}
