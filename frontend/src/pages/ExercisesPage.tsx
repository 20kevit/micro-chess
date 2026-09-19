import { Link } from "react-router-dom";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { EXERCISE_CATALOG, type ExerciseMeta } from "../exercises/catalog";
import { t } from "../i18n";
import { useAuth } from "../lib/auth-context";

// Exercise-selection menu. Serves both "/" (main menu) and "/exercises".
// Renders every exercise from the central registry.
// Availability is status-driven: active cards link to their route,
// coming-soon cards show a badge and no link. No per-slug conditionals.
export function ExercisesPage() {
  const { user, loading } = useAuth();
  return (
    <div>
      <PageHeader title={t("exercises.title")} subtitle={t("exercises.subtitle")} />
      {!loading && !user ? (
        <Card className="mb-3">
          <p className="text-sm text-stone-600">{t("exercises.loginHint")}</p>
          <Link to="/login" className="mt-2 block">
            <Button variant="secondary" className="w-full">
              {t("nav.login")}
            </Button>
          </Link>
        </Card>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        {EXERCISE_CATALOG.map((ex, index) => (
          <ExerciseCard key={ex.slug} meta={ex} number={index + 1} />
        ))}
      </div>
    </div>
  );
}

function ExerciseCard({ meta, number }: { meta: ExerciseMeta; number: number }) {
  const playable = meta.status === "active" && meta.route !== null;
  return (
    <Card className={playable ? "" : "opacity-70"}>
      <div className="flex items-start justify-between gap-2">
        <h2 className="text-lg font-black">
          <span className="me-2 inline-block rounded-full bg-violet-100 px-2 py-0.5 text-xs font-black text-violet-700">
            {number.toLocaleString("fa-IR")}
          </span>
          {t(meta.titleKey)}
        </h2>
        {playable ? null : <Badge>{t("exercise.comingSoon")}</Badge>}
      </div>
      <p className="mt-1 text-sm text-stone-500">{t(meta.descKey)}</p>
      {playable && meta.route ? (
        meta.modes ? (
          <div className="mt-3 grid grid-cols-2 gap-2">
            {meta.modes.map((entryMode, i) => (
              <Link
                key={entryMode.id}
                to={`${meta.route}${entryMode.params}`}
                className="block"
                aria-label={`${t(meta.titleKey)} — ${t(entryMode.labelKey)}`}
              >
                <Button variant={i === 0 ? "secondary" : "primary"} className="w-full">
                  {t(entryMode.labelKey)}
                </Button>
                <p className="mt-1 text-center text-xs text-stone-500">{t(entryMode.descKey)}</p>
              </Link>
            ))}
          </div>
        ) : (
          <Link to={meta.route} className="mt-3 block" aria-label={t(meta.titleKey)}>
            <Button className="w-full">{t("play.start")}</Button>
          </Link>
        )
      ) : null}
    </Card>
  );
}
