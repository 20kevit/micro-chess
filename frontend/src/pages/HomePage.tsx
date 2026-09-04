import { Link } from "react-router-dom";
import { t } from "../i18n";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { ChessBoard } from "../components/chess/ChessBoard";

// Landing page. Presentational only; exercise logic lives in backend.
export function HomePage() {
  return (
    <div>
      <PageHeader title={t("home.title")} subtitle={t("home.subtitle")} />
      <Card>
        <ChessBoard
          pieces={{ e2: "P", d1: "Q", e1: "K", e8: "k" }}
          onSquarePress={() => {}}
        />
        <Link to="/exercises" className="mt-4 block">
          <Button className="w-full">{t("home.cta")}</Button>
        </Link>
      </Card>
    </div>
  );
}
