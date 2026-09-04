import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { Exercise } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

// Exercise list comes from backend catalog. Only routing links live here;
// no answer logic or correctness decisions.
const PLAYABLE: Record<string, string> = {
  "piece-recognition": "/exercises/piece-recognition",
};

// Exercise list comes from backend catalog. No hardcoded exercise logic here.
export function ExercisesPage() {
  const [items, setItems] = useState<Exercise[] | null>(null);
  const [error, setError] = useState(false);

  async function load() {
    setError(false);
    try {
      setItems(await api.listExercises());
    } catch {
      setError(true);
    }
  }

  useEffect(() => {
    load();
  }, []);

  if (error) {
    return (
      <div>
        <PageHeader title={t("exercises.title")} />
        <Card>
          <p>{t("common.error")}</p>
          <Button className="mt-3" onClick={load}>
            {t("common.retry")}
          </Button>
        </Card>
      </div>
    );
  }

  if (items === null) return <p>{t("common.loading")}</p>;
  if (items.length === 0) {
    return (
      <div>
        <PageHeader title={t("exercises.title")} />
        <Card>
          <Badge>{t("exercise.comingSoon")}</Badge>
          <p className="mt-2">{t("exercises.empty")}</p>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={t("exercises.title")} />
      <div className="grid gap-3">
        {items.map((ex) => (
          <Card key={ex.slug}>
            <h2 className="text-lg font-black">{ex.title_fa}</h2>
            {ex.description ? <p className="mt-1 text-sm text-stone-500">{ex.description}</p> : null}
            {PLAYABLE[ex.slug] ? (
              <Link to={PLAYABLE[ex.slug]} className="mt-3 block">
                <Button className="w-full">{t("piece.start")}</Button>
              </Link>
            ) : (
              <div className="mt-3">
                <Badge>{t("exercise.comingSoon")}</Badge>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  );
}
