import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi } from "../api/client";
import type { AdminOverview, DashboardExtended, ProductInsight } from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

// Admin overview: read-only operational snapshot. Every number comes
// from the server; the response carries no secrets.
export function AdminDashboardPage() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [extended, setExtended] = useState<DashboardExtended | null>(null);
  const [insights, setInsights] = useState<ProductInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFailed(false);
    Promise.all([
      adminApi.dashboard(),
      adminApi.dashboardExtended().catch(() => null),
      adminApi.insights().catch(() => []),
    ])
      .then(([d, e, i]) => {
        if (alive) {
          setData(d);
          setExtended(e);
          setInsights(i ?? []);
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

  if (loading)
    return (
      <AdminLayout>
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      </AdminLayout>
    );
  if (failed || !data)
    return (
      <AdminLayout>
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <div className="mx-auto mt-3 max-w-xs">
            <Button onClick={() => setRetryKey((k) => k + 1)} className="w-full">
              {t("common.retry")}
            </Button>
          </div>
        </div>
      </AdminLayout>
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
    <AdminLayout>
      <PageHeader title={t("admin.title")} subtitle={t("admin.subtitle")} />
      <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
        {stats.map(([label, value]) => (
          <Card key={label} className="text-center">
            <p className="text-2xl font-black text-violet-700">{faNum(value)}</p>
            <p className="mt-1 text-xs text-stone-500">{label}</p>
          </Card>
        ))}
      </div>
      {extended ? (
        <div className="mt-3 grid grid-cols-2 gap-2 md:grid-cols-4">
          <Card className="text-center">
            <p className="text-2xl font-black text-sky-700">{faNum(extended.registrations.today)}</p>
            <p className="mt-1 text-xs text-stone-500">
              {t("admin.newRegistrations")} امروز / هفته {faNum(extended.registrations.week)}
            </p>
          </Card>
          <Card className="text-center">
            <p className="text-2xl font-black text-sky-700">{faNum(extended.active.today)}</p>
            <p className="mt-1 text-xs text-stone-500">
              {t("admin.activeUsers")} امروز / هفته {faNum(extended.active.week)}
            </p>
          </Card>
          <Card className="text-center">
            <p className="text-2xl font-black text-sky-700">{faNum(extended.attempts.week)}</p>
            <p className="mt-1 text-xs text-stone-500">
              {t("admin.attemptsTotal")} هفته (قبلی {faNum(extended.attempts.prev_week)})
            </p>
          </Card>
          <Card className="text-center">
            <p className="text-2xl font-black text-emerald-700">{faNum(extended.sales.revenue_minor)}</p>
            <p className="mt-1 text-xs text-stone-500">{t("admin.revenue")}</p>
          </Card>
        </div>
      ) : null}
      {extended && extended.series.length > 0 ? (
        <Card>
          <h2 className="font-black">
            {t("admin.usageTrend")}
          </h2>
          <div className="mt-2 flex h-24 items-end gap-1" dir="ltr" aria-hidden>
            {extended.series.map((row) => {
              const max = Math.max(1, ...extended.series.map((r) => r.attempts));
              return (
                <div
                  key={row.day}
                  title={`${row.day}: ${row.registrations}/${row.attempts}`}
                  className="min-w-2 flex-1 rounded-t bg-violet-300"
                  style={{ height: `${Math.max(4, Math.round((row.attempts / max) * 96))}px` }}
                />
              );
            })}
          </div>
        </Card>
      ) : null}
      {extended && extended.series.some((row) => row.revenue_minor > 0) ? (
        <Card>
          <h2 className="font-black">{t("admin.revenueTrend")}</h2>
          <div className="mt-2 flex h-24 items-end gap-1" dir="ltr" aria-hidden>
            {extended.series.map((row) => {
              const max = Math.max(1, ...extended.series.map((r) => r.revenue_minor));
              return (
                <div
                  key={row.day}
                  title={`${row.day}: ${row.revenue_minor}`}
                  className="min-w-2 flex-1 rounded-t bg-emerald-300"
                  style={{ height: `${Math.max(4, Math.round((row.revenue_minor / max) * 96))}px` }}
                />
              );
            })}
          </div>
        </Card>
      ) : null}
      {extended && extended.attribution.length > 0 ? (
        <Card>
          <h2 className="font-black">{t("admin.attributionOverview")}</h2>
          <ul className="mt-2 flex flex-col gap-1">
            {extended.attribution.map((row) => (
              <li key={row.slug} className="rounded-xl bg-stone-50 px-3 py-2">
                <p className="font-bold" dir="ltr">{row.slug}</p>
                <p className="text-xs text-stone-500">
                  {t("admin.newRegistrations")}: {faNum(row.registrations)} · {t("admin.redemptions")}:{" "}
                  {faNum(row.redemptions)} · {t("admin.trials")}: {faNum(row.trials)} ·{" "}
                  {t("admin.paidUsers")}: {faNum(row.paid)}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
      {extended && extended.exercise_success.length > 0 ? (
        <Card>
          <h2 className="font-black">{t("admin.exerciseSuccess")}</h2>
          <ul className="mt-2 flex flex-col gap-1">
            {extended.exercise_success.map((row) => (
              <li key={row.exercise_slug} className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3">
                <span dir="ltr" className="font-bold">{row.exercise_slug}</span>
                <span className="text-sm text-stone-500" dir="ltr">
                  {faNum(row.attempts)} · {row.success_rate === null ? "—" : `${Math.round(row.success_rate * 100)}٪`}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
      {insights.length > 0 ? (
        <Card>
          <h2 className="font-black">
            {t("admin.insights")} ({faNum(insights.length)})
          </h2>
          <ul className="mt-2 flex flex-col gap-1">
            {insights.slice(0, 5).map((item) => (
              <li key={item.key} className="rounded-xl bg-amber-50 px-3 py-2 text-sm">
                <span className="font-bold">{item.title}</span>
              </li>
            ))}
          </ul>
          <Link to="/admin/insights" className="mt-2 block">
            <Button variant="secondary" className="w-full">
              {t("admin.details")}
            </Button>
          </Link>
        </Card>
      ) : null}
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
          <Link to="/admin/audit" className="mt-2 block">
            <Button variant="secondary" className="w-full">
              {t("admin.details")}
            </Button>
          </Link>
        </Card>
      </div>
    </AdminLayout>
  );
}
