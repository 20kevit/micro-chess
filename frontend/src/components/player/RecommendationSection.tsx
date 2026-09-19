import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import type { Recommendation } from "../../api/types";
import { exerciseEntryTarget } from "../../exercises/catalog";
import { t } from "../../i18n";
import { exerciseTitle, recommendationReasonLabel } from "../../lib/playerDisplay";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

// Player-facing recommendation card (P8 integration). Display-only: the
// suggestion comes from GET /me/recommendations (read-only P7 engine);
// starting it links into the existing exercise attempt flow, so no
// duplicate state or new persistence is created here.
export function RecommendationSection() {
  const [item, setItem] = useState<Recommendation | null>(null);
  const [hasItem, setHasItem] = useState(false);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFailed(false);
    setItem(null);
    setHasItem(false);
    api
      .recommendation()
      .then((res) => {
        if (!alive) return;
        setItem(res);
        setHasItem(res !== null);
        setLoading(false);
      })
      .catch(() => {
        if (!alive) return;
        setFailed(true);
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [retryKey]);

  if (loading) {
    return (
      <Card>
        <h2 className="font-black">{t("recommendation.title")}</h2>
        <p className="mt-2 text-sm text-stone-500">{t("common.loading")}</p>
      </Card>
    );
  }
  if (failed) {
    return (
      <Card>
        <h2 className="font-black">{t("recommendation.title")}</h2>
        <p className="mt-2 text-sm text-stone-500">{t("common.error")}</p>
        <Button onClick={() => setRetryKey((k) => k + 1)}>{t("common.retry")}</Button>
      </Card>
    );
  }
  if (!hasItem || item === null) {
    return (
      <Card>
        <h2 className="font-black">{t("recommendation.title")}</h2>
        <p className="mt-1 text-xs text-stone-500">{t("recommendation.subtitle")}</p>
        <p className="mt-2 text-sm text-stone-500">{t("recommendation.empty")}</p>
      </Card>
    );
  }

  return (
    <Card>
      <h2 className="font-black">{t("recommendation.title")}</h2>
      <p className="mt-1 text-xs text-stone-500">{t("recommendation.subtitle")}</p>
      <div className="mt-3 rounded-xl bg-violet-50 px-3 py-2">
        <p className="mt-1 font-black text-violet-800">{exerciseTitle(item.exercise_slug)}</p>
        <p className="mt-1 text-sm">
          <Badge>{recommendationReasonLabel(item.reason)}</Badge>
        </p>
        <Link
          to={exerciseEntryTarget(item.exercise_slug)}
          aria-label={`${exerciseTitle(item.exercise_slug)} — ${t("recommendation.start")}`}
          className="mt-3 block"
        >
          <Button className="w-full">{t("recommendation.start")}</Button>
        </Link>
      </div>
    </Card>
  );
}
