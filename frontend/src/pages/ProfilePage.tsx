import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, apiStatus } from "../api/client";
import type { ChessIdentity, PlayerProfile } from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import type { FaKey } from "../i18n/fa";

const PROVIDERS = ["fide", "lichess", "chess_com"] as const;

function providerLabel(provider: string): string {
  const key = `profile.provider.${provider}` as FaKey;
  try {
    const label = t(key);
    return label === key ? provider : label;
  } catch {
    return provider;
  }
}

// Player profile: editable display name/bio plus self-reported external
// chess identities. Verification state is server-owned and only rendered.
export function ProfilePage() {
  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [identities, setIdentities] = useState<ChessIdentity[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [retryKey, setRetryKey] = useState(0);

  const [displayName, setDisplayName] = useState("");
  const [bio, setBio] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [formError, setFormError] = useState("");

  const [newProvider, setNewProvider] = useState<string>("lichess");
  const [newUsername, setNewUsername] = useState("");
  const [newRating, setNewRating] = useState("");
  const [newRatingType, setNewRatingType] = useState("");
  const [identityError, setIdentityError] = useState("");
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editUsername, setEditUsername] = useState("");
  const [editRating, setEditRating] = useState("");
  const [editRatingType, setEditRatingType] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFailed(false);
    Promise.all([api.getProfile(), api.listIdentities()])
      .then(([p, ids]) => {
        if (!alive) return;
        setProfile(p);
        setDisplayName(p.display_name);
        setBio(p.bio);
        setIdentities(ids);
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

  async function onSaveProfile(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaved(false);
    setFormError("");
    try {
      const updated = await api.updateProfile({ display_name: displayName, bio });
      setProfile(updated);
      setSaved(true);
    } catch {
      setFormError(t("common.error"));
    } finally {
      setSaving(false);
    }
  }

  function describeIdentityError(e: unknown): string {
    if (apiStatus(e) === 409) return t("profile.errorTaken");
    return t("profile.errorInvalid");
  }

  async function onAddIdentity(e: FormEvent) {
    e.preventDefault();
    setIdentityError("");
    const rating = newRating.trim() === "" ? null : Number(newRating);
    if (rating !== null && (!Number.isInteger(rating) || rating < 0)) {
      setIdentityError(t("profile.errorInvalid"));
      return;
    }
    try {
      const created = await api.addIdentity({
        provider: newProvider,
        username: newUsername,
        rating,
        rating_type: newRatingType.trim() === "" ? null : newRatingType.trim(),
      });
      setIdentities((prev) => [...prev, created]);
      setNewUsername("");
      setNewRating("");
      setNewRatingType("");
    } catch (err) {
      setIdentityError(describeIdentityError(err));
    }
  }

  async function onRemoveIdentity(id: number) {
    setIdentityError("");
    try {
      await api.deleteIdentity(id);
      setIdentities((prev) => prev.filter((row) => row.id !== id));
    } catch {
      setIdentityError(t("common.error"));
    }
  }

  function startEditing(identity: ChessIdentity) {
    setEditingId(identity.id);
    setEditUsername(identity.username);
    setEditRating(identity.rating === null ? "" : String(identity.rating));
    setEditRatingType(identity.rating_type ?? "");
    setIdentityError("");
  }

  async function onSaveIdentity(e: FormEvent) {
    e.preventDefault();
    if (editingId === null) return;
    setIdentityError("");
    const rating = editRating.trim() === "" ? null : Number(editRating);
    if (rating !== null && (!Number.isInteger(rating) || rating < 0)) {
      setIdentityError(t("profile.errorInvalid"));
      return;
    }
    try {
      const updated = await api.updateIdentity(editingId, {
        username: editUsername,
        rating,
        rating_type: editRatingType.trim() === "" ? null : editRatingType.trim(),
      });
      setIdentities((prev) => prev.map((row) => (row.id === updated.id ? updated : row)));
      setEditingId(null);
    } catch (err) {
      setIdentityError(describeIdentityError(err));
    }
  }

  if (loading) return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  if (failed || !profile)
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

  return (
    <div>
      <PageHeader title={t("profile.title")} subtitle={t("profile.subtitle")} />
      <div className="flex flex-col gap-3">
        <Card>
          <form onSubmit={(e) => void onSaveProfile(e)} className="flex flex-col gap-3">
            <label className="flex flex-col gap-1 text-sm font-bold">
              {t("profile.displayName")}
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                maxLength={100}
                className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 font-normal"
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-bold">
              {t("profile.bio")}
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                maxLength={500}
                rows={3}
                placeholder={t("profile.bioPlaceholder")}
                className="rounded-xl border border-stone-200 bg-white px-3 py-2 font-normal"
              />
            </label>
            {formError ? <p className="text-sm text-red-600">{formError}</p> : null}
            {saved ? <p className="text-sm text-emerald-700">{t("profile.saved")}</p> : null}
            <Button type="submit" disabled={saving} className="w-full">
              {t("profile.save")}
            </Button>
          </form>
        </Card>
        <Card>
          <h2 className="font-black">{t("profile.identities")}</h2>
          <p className="mt-1 text-sm text-stone-500">{t("profile.identitiesHint")}</p>
          {identities.length === 0 ? (
            <p className="mt-2 text-sm text-stone-500">{t("profile.noIdentities")}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {identities.map((identity) =>
                editingId === identity.id ? (
                  <li key={identity.id} className="rounded-xl bg-stone-50 px-3 py-2">
                    <form onSubmit={(e) => void onSaveIdentity(e)} className="flex flex-col gap-2">
                      <label className="flex flex-col gap-1 text-xs text-stone-500">
                        {t("profile.username")}
                        <input
                          value={editUsername}
                          onChange={(e) => setEditUsername(e.target.value)}
                          maxLength={100}
                          dir="ltr"
                          className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-bold text-stone-900"
                        />
                      </label>
                      <div className="grid grid-cols-2 gap-2">
                        <label className="flex flex-col gap-1 text-xs text-stone-500">
                          {t("profile.rating")}
                          <input
                            value={editRating}
                            onChange={(e) => setEditRating(e.target.value)}
                            inputMode="numeric"
                            dir="ltr"
                            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-bold text-stone-900"
                          />
                        </label>
                        <label className="flex flex-col gap-1 text-xs text-stone-500">
                          {t("profile.ratingType")}
                          <input
                            value={editRatingType}
                            onChange={(e) => setEditRatingType(e.target.value)}
                            maxLength={30}
                            dir="ltr"
                            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-bold text-stone-900"
                          />
                        </label>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <Button type="submit" className="w-full">
                          {t("profile.save")}
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={() => setEditingId(null)}
                          className="w-full"
                        >
                          {t("profile.cancel")}
                        </Button>
                      </div>
                    </form>
                  </li>
                ) : (
                  <li
                    key={identity.id}
                    className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
                  >
                    <span>
                      <span className="font-bold">{providerLabel(identity.provider)}</span>{" "}
                      <span dir="ltr" className="text-sm text-stone-600">
                        {identity.username}
                      </span>
                      {identity.rating !== null ? (
                        <span className="text-xs text-stone-500"> · {identity.rating}</span>
                      ) : null}{" "}
                      <Badge>{t("profile.unverified")}</Badge>
                    </span>
                    <span className="flex gap-1">
                      <button
                        type="button"
                        onClick={() => startEditing(identity)}
                        className="flex min-h-[44px] items-center rounded-xl px-3 text-sm font-bold text-violet-700"
                      >
                        {t("profile.edit")}
                      </button>
                      <button
                        type="button"
                        onClick={() => void onRemoveIdentity(identity.id)}
                        className="flex min-h-[44px] items-center rounded-xl px-3 text-sm font-bold text-red-600"
                      >
                        {t("profile.remove")}
                      </button>
                    </span>
                  </li>
                ),
              )}
            </ul>
          )}
          {identityError ? <p className="mt-2 text-sm text-red-600">{identityError}</p> : null}
          <form onSubmit={(e) => void onAddIdentity(e)} className="mt-3 flex flex-col gap-2">
            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1 text-xs text-stone-500">
                {t("profile.provider")}
                <select
                  value={newProvider}
                  onChange={(e) => setNewProvider(e.target.value)}
                  className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-2 text-sm font-bold text-stone-900"
                >
                  {PROVIDERS.map((provider) => (
                    <option key={provider} value={provider}>
                      {providerLabel(provider)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-stone-500">
                {t("profile.username")}
                <input
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  maxLength={100}
                  dir="ltr"
                  className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-bold text-stone-900"
                />
              </label>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <label className="flex flex-col gap-1 text-xs text-stone-500">
                {t("profile.rating")}
                <input
                  value={newRating}
                  onChange={(e) => setNewRating(e.target.value)}
                  inputMode="numeric"
                  dir="ltr"
                  className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-bold text-stone-900"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-stone-500">
                {t("profile.ratingType")}
                <input
                  value={newRatingType}
                  onChange={(e) => setNewRatingType(e.target.value)}
                  maxLength={30}
                  dir="ltr"
                  className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-bold text-stone-900"
                />
              </label>
            </div>
            <Button type="submit" variant="secondary" className="w-full">
              {t("profile.addIdentity")}
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
}
