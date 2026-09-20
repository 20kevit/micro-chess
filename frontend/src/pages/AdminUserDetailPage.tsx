import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { adminApi } from "../api/client";
import type { AdminUserDetail } from "../api/types";
import { AdminLayout } from "../components/admin/AdminLayout";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faNum } from "../lib/playerDisplay";

export function AdminUserDetailPage() {
  const { id } = useParams();
  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!id) return;
    adminApi
      .user(Number(id))
      .then((u) => {
        setUser(u);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, [id]);

  return (
    <AdminLayout>
      <PageHeader title={t("admin.usersDetail")} subtitle={t("admin.subtitle")} />
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed || !user ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <Button onClick={() => window.location.reload()} className="mx-auto mt-3 max-w-xs">
            {t("common.retry")}
          </Button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          <Card>
            <p className="font-black" dir="ltr">{user.username}</p>
            <p className="text-sm text-stone-500">{user.display_name}</p>
            <p className="mt-1 text-xs text-stone-500" dir="ltr">
              roles: {user.roles.join(", ")} · attempts {faNum(user.attempts_count)}
            </p>
          </Card>
          <Card>
            <p className="text-sm text-stone-500">{user.profile.bio || "—"}</p>
          </Card>
        </div>
      )}
    </AdminLayout>
  );
}
