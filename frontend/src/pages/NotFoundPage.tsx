import { Link } from "react-router-dom";
import { t } from "../i18n";
import { Button } from "../components/ui/Button";

export function NotFoundPage() {
  return (
    <div className="text-center">
      <h1 className="text-2xl font-black">{t("notFound.title")}</h1>
      <Link to="/" className="mt-4 inline-block">
        <Button>{t("notFound.cta")}</Button>
      </Link>
    </div>
  );
}
