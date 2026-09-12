import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { apiCode, apiRoles } from "../api/client";
import { t } from "../i18n";
import type { FaKey } from "../i18n/fa";
import { useAuth } from "../lib/auth-context";
import { authErrorKey } from "../lib/auth-errors";

// Login screen. Persian RTL; username/password inputs stay LTR. When the
// account holds several roles, the server answers 409 with the assigned
// set and this page shows a role-selection step (server list only; the
// client never invents roles).
export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const next = (location.state as { next?: string } | null)?.next ?? "/account";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorKey, setErrorKey] = useState<FaKey | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [choiceRoles, setChoiceRoles] = useState<string[] | null>(null);

  useEffect(() => {
    if (user) navigate(next, { replace: true });
  }, [user, next, navigate]);

  async function attempt(role?: string) {
    setSubmitting(true);
    setErrorKey(null);
    try {
      if (role === undefined) await login(username.trim(), password);
      else await login(username.trim(), password, role);
    } catch (err) {
      // Multi-role account: move to the selection step instead of an error.
      if (!role && apiCode(err) === "ROLE_SELECTION_REQUIRED") {
        const roles = apiRoles(err);
        if (roles.length > 0) {
          setChoiceRoles(roles);
          return;
        }
      }
      setErrorKey(authErrorKey(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    await attempt();
  }

  // Role-selection step: only roles the server just reported are shown.
  if (choiceRoles) {
    return (
      <div>
        <PageHeader title={t("auth.selectRoleTitle")} subtitle={t("auth.selectRoleSubtitle")} />
        <Card>
          <div className="flex flex-col gap-2">
            {choiceRoles.map((role) => (
              <Button
                key={role}
                variant="secondary"
                disabled={submitting}
                onClick={() => void attempt(role)}
              >
                {t(`auth.role.${role}` as FaKey)}
              </Button>
            ))}
            {errorKey ? (
              <p role="alert" className="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
                {t(errorKey)}
              </p>
            ) : null}
            <Button
              variant="ghost"
              disabled={submitting}
              onClick={() => {
                setChoiceRoles(null);
                setErrorKey(null);
              }}
            >
              {t("common.back")}
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={t("auth.loginTitle")} />
      <Card>
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm font-bold text-stone-700">
            {t("auth.username")}
            <input
              dir="ltr"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="min-h-[44px] rounded-2xl border border-stone-200 px-4 py-3 text-left text-base font-normal"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-bold text-stone-700">
            {t("auth.password")}
            <input
              dir="ltr"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="min-h-[44px] rounded-2xl border border-stone-200 px-4 py-3 text-left text-base font-normal"
            />
          </label>
          {errorKey ? (
            <p role="alert" className="rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
              {t(errorKey)}
            </p>
          ) : null}
          <Button type="submit" disabled={submitting}>
            {submitting ? t("common.loading") : t("auth.loginSubmit")}
          </Button>
        </form>
        <Link
          to="/register"
          state={{ next }}
          className="mt-3 flex min-h-[44px] items-center justify-center font-bold text-violet-700"
        >
          {t("auth.toRegister")}
        </Link>
      </Card>
    </div>
  );
}
