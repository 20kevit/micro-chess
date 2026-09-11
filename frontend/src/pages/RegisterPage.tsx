import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import type { FaKey } from "../i18n/fa";
import { useAuth } from "../lib/auth-context";
import { authErrorKey } from "../lib/auth-errors";

// Registration screen: username + password only. Persian RTL.
export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const next = (location.state as { next?: string } | null)?.next ?? "/account";
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errorKey, setErrorKey] = useState<FaKey | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (user) navigate(next, { replace: true });
  }, [user, next, navigate]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setErrorKey(null);
    try {
      await register(username.trim(), password);
    } catch (err) {
      setErrorKey(authErrorKey(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <PageHeader title={t("auth.registerTitle")} />
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
            <span className="text-xs font-normal text-stone-500">{t("auth.usernameHint")}</span>
          </label>
          <label className="flex flex-col gap-1 text-sm font-bold text-stone-700">
            {t("auth.password")}
            <input
              dir="ltr"
              type="password"
              autoComplete="new-password"
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
            {submitting ? t("common.loading") : t("auth.registerSubmit")}
          </Button>
        </form>
        <Link
          to="/login"
          state={{ next }}
          className="mt-3 flex min-h-[44px] items-center justify-center font-bold text-violet-700"
        >
          {t("auth.toLogin")}
        </Link>
      </Card>
    </div>
  );
}
