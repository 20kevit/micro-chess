import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { adminApi, apiCode } from "../api/client";
import type { AdminUser, AdminUserDetail } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

const MANAGEABLE_ROLES = ["COACH", "PARENT", "ADMIN"] as const;

// User management: search, inspect, suspend/reactivate, role assign/revoke.
// Destructive actions ask for confirmation; authorization stays server-side.
export function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [selected, setSelected] = useState<AdminUserDetail | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    adminApi
      .users({
        search: search || undefined,
        role: role || undefined,
        status: status || undefined,
        page_size: 50,
      })
      .then((rows) => {
        setUsers(rows);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, [search, role, status]);

  useEffect(() => {
    load();
  }, [load]);

  async function openDetail(id: number) {
    setBusy(true);
    setNotice("");
    try {
      setSelected(await adminApi.user(id));
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function refreshSelected(id: number) {
    try {
      setSelected(await adminApi.user(id));
    } catch {
      setNotice(t("common.error"));
    }
    load();
  }

  async function onSuspend(id: number) {
    if (!window.confirm(t("admin.suspendConfirm"))) return;
    setBusy(true);
    try {
      await adminApi.suspendUser(id);
      await refreshSelected(id);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function onReactivate(id: number) {
    if (!window.confirm(t("admin.reactivateConfirm"))) return;
    setBusy(true);
    try {
      await adminApi.reactivateUser(id);
      await refreshSelected(id);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function onAssign(id: number, next: string) {
    setBusy(true);
    setNotice("");
    try {
      await adminApi.assignRole(id, next);
      await refreshSelected(id);
    } catch (e) {
      setNotice(apiCode(e) === "LAST_ADMIN" ? t("admin.lastAdminBlocked") : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function onRevoke(id: number, next: string) {
    setBusy(true);
    setNotice("");
    try {
      await adminApi.revokeRole(id, next);
      await refreshSelected(id);
    } catch (e) {
      setNotice(apiCode(e) === "LAST_ADMIN" ? t("admin.lastAdminBlocked") : t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <PageHeader title={t("admin.users")} subtitle={t("admin.subtitle")} />
      <Card>
        <div className="flex flex-col gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("admin.searchUsers")}
            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
          />
          <div className="grid grid-cols-2 gap-2">
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
            >
              <option value="">{t("admin.allRoles")}</option>
              {["PLAYER", ...MANAGEABLE_ROLES].map((r) => (
                <option key={r} value={r}>
                  {t(`auth.role.${r}` as "auth.role.PLAYER")}
                </option>
              ))}
            </select>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm"
            >
              <option value="">{t("admin.allStatuses")}</option>
              <option value="active">{t("admin.statusActive")}</option>
              <option value="suspended">{t("admin.statusSuspended")}</option>
            </select>
          </div>
        </div>
      </Card>
      {notice ? (
        <p className="mt-2 text-center text-sm font-bold text-red-600">{notice}</p>
      ) : null}
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <div className="mx-auto mt-3 max-w-xs">
            <Button onClick={load} className="w-full">
              {t("common.retry")}
            </Button>
          </div>
        </div>
      ) : users.length === 0 ? (
        <Card>
          <p className="text-center text-stone-500">{t("admin.noUsers")}</p>
        </Card>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {users.map((u) => (
            <li key={u.id}>
              <Card>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void openDetail(u.id)}
                  className="flex min-h-[44px] w-full items-center justify-between gap-2 text-right"
                >
                  <span className="font-bold" dir="ltr">
                    {u.username}
                  </span>
                  <Badge>{u.is_active ? t("admin.statusActive") : t("admin.statusSuspended")}</Badge>
                </button>
                <Link to={`/admin/users/${u.id}`} className="mt-1 inline-block text-sm font-bold text-violet-700">
                  {t("admin.details")}
                </Link>
              </Card>
            </li>
          ))}
        </ul>
      )}
      {selected ? (
        <Card className="mt-3">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-black" dir="ltr">
              {selected.username}
            </h2>
            <span className="text-xs text-stone-500">
              {t("admin.attempts")}: {faNum(selected.attempts_count)}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-2">
            {selected.roles.map((r) => (
              <Badge key={r}>{t(`auth.role.${r}` as "auth.role.PLAYER")}</Badge>
            ))}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            {selected.is_active ? (
              <Button variant="secondary" disabled={busy} onClick={() => void onSuspend(selected.id)}>
                {t("admin.suspend")}
              </Button>
            ) : (
              <Button disabled={busy} onClick={() => void onReactivate(selected.id)}>
                {t("admin.reactivate")}
              </Button>
            )}
            <Button variant="secondary" disabled={busy} onClick={() => setSelected(null)}>
              {t("profile.cancel")}
            </Button>
          </div>
          <h3 className="mt-3 text-sm font-bold">{t("admin.assignRole")}</h3>
          <div className="mt-2 flex flex-wrap gap-2">
            {MANAGEABLE_ROLES.map((r) =>
              selected.roles.includes(r) ? (
                <Button
                  key={r}
                  variant="secondary"
                  disabled={busy}
                  onClick={() => void onRevoke(selected.id, r)}
                >
                  {t("admin.revokeRole")}: {t(`auth.role.${r}` as "auth.role.PLAYER")}
                </Button>
              ) : (
                <Button key={r} variant="secondary" disabled={busy} onClick={() => void onAssign(selected.id, r)}>
                  {t("admin.assignRole")}: {t(`auth.role.${r}` as "auth.role.PLAYER")}
                </Button>
              ),
            )}
          </div>
        </Card>
      ) : null}
    </div>
  );
}
