import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api/client";
import type { AdminOverview } from "../api/types";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

// Admin overview: read-only operational snapshot. Every number comes
// from the server; the response carries no secrets.
export function AdminDashboardPage() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFailed(false);
    adminApi
      .dashboard()
      .then((d) => {
        if (alive) {
          setData(d);
          setLoading(false);
        }
      })
      .catch(() => {
        if (alive) {
          setFailed(true);
          setLoading(false);
        }
      });
    return () => {
      alive = false;
    };
  }, [retryKey]);

  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (failed || !data)
    return (
      <div className="py-8 text-center">
        <p className="text-stone-500">{t("common.error")}</p>
        <div className="mx-auto mt-3 max-w-xs">
          <Button onClick={() => setRetryKey((k) => k + 1)} className="w-full">
            {t("common.retry")}
          </Button>
        </div>
      </div>
    );

  const stats: Array<[string, number]> = [
    [t("admin.usersTotal"), data.users_total],
    [t("admin.usersActive"), data.users_active],
    [t("admin.usersSuspended"), data.users_suspended],
    [t("admin.exercisesActive"), data.exercises_active],
    [t("admin.puzzlesPublished"), data.puzzles_published],
    [t("admin.attemptsTotal"), data.attempts_total],
    [t("admin.attempts24h"), data.attempts_last_24h],
  ];

  return (
    <div>
      <PageHeader title={t("admin.title")} subtitle={t("admin.subtitle")} />
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        {stats.map(([label, value]) => (
          <Card key={label} className="text-center">
            <p className="text-2xl font-black text-violet-700">{faNum(value)}</p>
            <p className="mt-1 text-xs text-stone-500">{label}</p>
          </Card>
        ))}
      </div>
      <div className="mt-3 flex flex-col gap-3">
        <Card>
          <h2 className="font-black">{t("admin.users")}</h2>
          <Link to="/admin/users" className="mt-2 block">
            <Button variant="secondary" className="w-full">
              {t("admin.details")}
            </Button>
          </Link>
          <h3 className="mt-3 text-sm font-bold text-stone-500">{t("admin.recentRegistrations")}</h3>
          {data.recent_registrations.length === 0 ? (
            <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {data.recent_registrations.map((u) => (
                <li
                  key={u.id}
                  className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
                >
                  <span className="font-bold" dir="ltr">
                    {u.username}
                  </span>
                  <span className="text-xs text-stone-500">{u.display_name}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <h2 className="font-black">{t("admin.audit")}</h2>
          {data.recent_audit.length === 0 ? (
            <p className="mt-1 text-sm text-stone-500">{t("admin.noAudit")}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {data.recent_audit.map((a) => (
                <li
                  key={a.id}
                  className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
                >
                  <span className="font-bold" dir="ltr">
                    {a.action}
                  </span>
                  <span className="text-xs text-stone-500" dir="ltr">
                    {a.target_type}:{a.target_id}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <div className="grid grid-cols-2 gap-2">
          <Link to="/admin/exercises" className="block">
            <Button variant="secondary" className="w-full">
              {t("admin.exercises")}
            </Button>
          </Link>
          <Link to="/admin/puzzles" className="block">
            <Button variant="secondary" className="w-full">
              {t("admin.puzzles")}
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
