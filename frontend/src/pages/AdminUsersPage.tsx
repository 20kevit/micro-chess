import { useCallback, useEffect, useState } from "react";
import type { KeyboardEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { adminApi } from "../api/client";
import type { PageResult } from "../api/client";
import type { AdminUser } from "../api/types";
import type { FaKey } from "../i18n/fa";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { adminStatusLabel, faDate, faDateTime, faNum, verificationChannelLabel } from "../lib/playerDisplay";

const PAGE_SIZE = 20;
const ROLES = ["PLAYER", "COACH", "PARENT", "ADMIN"] as const;
const ROLE_KEYS: Record<string, FaKey> = {
  PLAYER: "auth.role.PLAYER",
  COACH: "auth.role.COACH",
  PARENT: "auth.role.PARENT",
  ADMIN: "auth.role.ADMIN",
};

type UserPage = PageResult<AdminUser> | AdminUser[];

function unpack(value: UserPage): { items: AdminUser[]; total: number } {
  if (Array.isArray(value)) return { items: value, total: value.length };
  return value;
}

function roleLabel(role: string): string {
  const key = ROLE_KEYS[role];
  return t(key ?? "admin.unknown");
}

function accountStatus(active: boolean): string {
  return active ? t("admin.statusActive") : t("admin.statusSuspended");
}

function subscriptionStatusLabel(status: string | null): string {
  if (status === "suspended") return t("admin.statusSuspended");
  return adminStatusLabel(status);
}

function planLabel(plan: string | null): string {
  if (!plan) return t("admin.notAvailable");
  if (plan === "free") return t("account.plan.free");
  if (plan === "premium") return t("account.plan.premium");
  return t("admin.unknown");
}

function pageSummary(page: number, total: number): string {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  return t("admin.pagination.summary")
    .replace("{page}", faNum(page))
    .replace("{pages}", faNum(pages))
    .replace("{total}", faNum(total));
}

export function AdminUsersPage() {
  const navigate = useNavigate();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState("created_at");
  const [order, setOrder] = useState("desc");
  const [page, setPage] = useState(1);

  const load = useCallback(async () => {
    setLoading(true);
    setFailed(false);
    const params = {
      search: search || undefined,
      role: role || undefined,
      status: status || undefined,
      sort,
      order,
      page,
      page_size: PAGE_SIZE,
    };
    try {
      const response = typeof adminApi.usersPage === "function"
        ? await adminApi.usersPage(params)
        : await adminApi.users(params);
      const result = unpack(response as UserPage);
      setUsers(result.items);
      setTotal(result.total);
    } catch {
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [order, page, role, search, sort, status]);

  useEffect(() => {
    void load();
  }, [load]);

  function resetPage() {
    setPage(1);
  }

  function openUser(userId: number) {
    navigate(`/admin/users/${userId}`);
  }

  function onRowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, userId: number) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openUser(userId);
    }
  }

  return (
    <div>
      <PageHeader title={t("admin.users")} subtitle={t("admin.users.summary")} />
      <Card>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-6">
          <label className="md:col-span-2 xl:col-span-2" htmlFor="admin-users-search">
            <span className="sr-only">{t("admin.searchUsers")}</span>
            <input
              id="admin-users-search"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                resetPage();
              }}
              placeholder={t("admin.searchUsers")}
              className="min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
            />
          </label>
          <label htmlFor="admin-users-role">
            <span className="sr-only">{t("admin.allRoles")}</span>
            <select
              id="admin-users-role"
              value={role}
              onChange={(event) => {
                setRole(event.target.value);
                resetPage();
              }}
              className="min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
            >
              <option value="">{t("admin.allRoles")}</option>
              {ROLES.map((value) => <option key={value} value={value}>{roleLabel(value)}</option>)}
            </select>
          </label>
          <label htmlFor="admin-users-status">
            <span className="sr-only">{t("admin.allStatuses")}</span>
            <select
              id="admin-users-status"
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                resetPage();
              }}
              className="min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
            >
              <option value="">{t("admin.allStatuses")}</option>
              <option value="active">{t("admin.statusActive")}</option>
              <option value="suspended">{t("admin.statusSuspended")}</option>
            </select>
          </label>
          <label htmlFor="admin-users-sort">
            <span className="sr-only">{t("admin.sortBy")}</span>
            <select
              id="admin-users-sort"
              value={sort}
              onChange={(event) => {
                setSort(event.target.value);
                resetPage();
              }}
              className="min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
            >
              <option value="created_at">{t("admin.sortCreated")}</option>
              <option value="username">{t("auth.username")}</option>
              <option value="id">{t("admin.sortId")}</option>
            </select>
          </label>
          <label htmlFor="admin-users-order">
            <span className="sr-only">{t("admin.orderDesc")}</span>
            <select
              id="admin-users-order"
              value={order}
              onChange={(event) => {
                setOrder(event.target.value);
                resetPage();
              }}
              className="min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
            >
              <option value="desc">{t("admin.orderDesc")}</option>
              <option value="asc">{t("admin.orderAsc")}</option>
            </select>
          </label>
        </div>
      </Card>
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <div className="mx-auto mt-3 max-w-xs">
            <Button onClick={() => void load()} className="w-full">{t("common.retry")}</Button>
          </div>
        </div>
      ) : users.length === 0 ? (
        <Card><p className="text-center text-stone-500">{t("admin.noUsers")}</p></Card>
      ) : (
        <Card className="mt-3 overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="min-w-[1180px] w-full text-right text-sm">
              <thead className="bg-stone-50 text-xs text-stone-500">
                <tr>
                  <th className="px-3 py-3 font-black">{t("auth.username")}</th>
                  <th className="px-3 py-3 font-black">{t("admin.registered")}</th>
                  <th className="px-3 py-3 font-black">{t("admin.label.plan")}</th>
                  <th className="px-3 py-3 font-black">{t("admin.sales.freeUsers")} / {t("admin.sales.premiumUsers")}</th>
                  <th className="px-3 py-3 font-black">{t("admin.subscriptions")}</th>
                  <th className="px-3 py-3 font-black">{t("admin.users.verification")}</th>
                  <th className="px-3 py-3 font-black">{t("admin.users.activity")}</th>
                  <th className="px-3 py-3 font-black">{t("admin.lastActive")}</th>
                  <th className="px-3 py-3 font-black">{t("admin.attempts")}</th>
                  <th className="px-3 py-3 font-black">{t("admin.users.couponUsage")}</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr
                    key={user.id}
                    tabIndex={0}
                    onClick={() => openUser(user.id)}
                    onKeyDown={(event) => onRowKeyDown(event, user.id)}
                    className="cursor-pointer border-t border-stone-100 transition hover:bg-violet-50 focus:bg-violet-50 focus:outline-none"
                  >
                    <td className="px-3 py-3">
                      <Link
                        to={`/admin/users/${user.id}`}
                        onClick={(event) => event.stopPropagation()}
                        className="inline-flex min-h-[44px] items-center font-black text-violet-700"
                        dir="ltr"
                      >
                        {user.username}
                      </Link>
                      <p className="mt-1 text-xs text-stone-500">{user.display_name}</p>
                    </td>
                    <td className="px-3 py-3"><span dir="ltr">{faDate(user.created_at)}</span></td>
                    <td className="px-3 py-3"><span dir="ltr">{planLabel(user.current_plan_code)}</span></td>
                    <td className="px-3 py-3"><span dir="ltr">{user.current_plan_code === "premium" ? t("account.plan.premium") : user.current_plan_code === "free" ? t("account.plan.free") : t("admin.notAvailable")}</span></td>
                    <td className="px-3 py-3"><Badge>{subscriptionStatusLabel(user.current_plan_status)}</Badge></td>
                    <td className="px-3 py-3">
                       {user.phone_verified
                         ? `${t("account.verified")} · ${verificationChannelLabel(user.verification_channel)}`
                         : t("account.unverified")}
                    </td>
                    <td className="px-3 py-3">
                      <span className="font-bold">{accountStatus(user.is_active)}</span>
                    </td>
                    <td className="px-3 py-3"><span dir="ltr">{faDateTime(user.last_active_at)}</span></td>
                    <td className="px-3 py-3">{faNum(user.attempts_count ?? 0)}</td>
                    <td className="px-3 py-3">{faNum(user.coupon_redemption_count ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      <div className="mt-3 flex items-center justify-between gap-2">
        <Button
          variant="secondary"
          disabled={loading || page <= 1}
          onClick={() => setPage((value) => Math.max(1, value - 1))}
        >
          {t("admin.pagination.previous")}
        </Button>
        <span className="text-center text-xs font-bold text-stone-500">{pageSummary(page, total)}</span>
        <Button
          variant="secondary"
          disabled={loading || page >= Math.max(1, Math.ceil(total / PAGE_SIZE))}
          onClick={() => setPage((value) => value + 1)}
        >
          {t("admin.pagination.next")}
        </Button>
      </div>
    </div>
  );
}
