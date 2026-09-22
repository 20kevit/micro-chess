import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiDetail, journeyApi, notifyApi, onboardingApi } from "../api/client";
import { exerciseEntryTarget } from "../exercises/catalog";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";

// Short conversational onboarding: 4 steps, optional signals skippable.
// Collects only what materially improves initial recommendations.
const EXPERIENCES = ["new", "beginner", "club", "advanced"] as const;
const FREQUENCIES = ["never", "sometimes", "weekly", "daily"] as const;
const GOALS = ["fun", "improve", "compete", "coach"] as const;

export function OnboardingPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [experience, setExperience] = useState("");
  const [frequency, setFrequency] = useState("");
  const [fide, setFide] = useState("");
  const [lichess, setLichess] = useState("");
  const [chesscom, setChesscom] = useState("");
  const [goal, setGoal] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<{ headline: string; summary: string; goal_text: string } | null>(
    null,
  );

  useEffect(() => {
    onboardingApi
      .get()
      .then((o) => {
        if (o.onboarding_completed) {
          onboardingApi.plan().then(setPlan).catch(() => {});
          setStep(4);
        }
      })
      .catch(() => {});
  }, []);

  function Choice({
    label,
    selected,
    onPick,
  }: {
    label: string;
    selected: boolean;
    onPick: () => void;
  }) {
    return (
      <button
        type="button"
        aria-pressed={selected}
        onClick={onPick}
        className={`flex min-h-[52px] items-center justify-between rounded-2xl border px-4 py-3 text-base font-bold active:bg-violet-50 ${
          selected ? "border-violet-600 bg-violet-50 text-violet-800" : "border-stone-200"
        }`}
      >
        {label}
        <span aria-hidden>{selected ? "●" : "○"}</span>
      </button>
    );
  }

  async function finish() {
    setBusy(true);
    setError("");
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "Asia/Tehran";
      const saved = await onboardingApi.save({
        experience,
        play_frequency: frequency,
        fide_rating: fide.trim() ? Number(fide.trim()) : null,
        lichess_username: lichess.trim(),
        chesscom_username: chesscom.trim(),
        goal,
        intensity: "standard",
        timezone: tz,
      });
      void saved;
      const p = await onboardingApi.plan();
      setPlan(p);
      setStep(4);
      notifyApi.track("onboarding_completed").catch(() => {});
      // Kick off placement content load in the background (no blocking).
      onboardingApi.placement().catch(() => {});
    } catch (e) {
      setError(apiDetail(e) || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  if (step === 4 && plan) {
    return (
      <div>
        <PageHeader title={plan.headline} subtitle={plan.summary} />
        <Card>
          <p className="text-sm text-stone-500">{plan.goal_text}</p>
          <div className="mt-3 flex flex-col gap-2">
            <Button
              onClick={() => {
                onboardingApi.completePlacement().catch(() => {});
                notifyApi.track("placement_completed").catch(() => {});
                journeyApi.today().catch(() => {});
                navigate("/", { replace: true });
              }}
            >
              {t("plan.cta")}
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  const titles = [
    t("onboarding.step1Title"),
    t("onboarding.step2Title"),
    t("onboarding.step3Title"),
    t("onboarding.step4Title"),
  ];

  const canNext =
    (step === 0 && experience !== "") ||
    (step === 1 && frequency !== "") ||
    step === 2 ||
    (step === 3 && goal !== "");

  return (
    <div>
      <PageHeader title={titles[step]} />
      <Card>
        <div className="flex flex-col gap-2" role="group" aria-label={titles[step]}>
          {step === 0 &&
            EXPERIENCES.map((v) => (
              <Choice
                key={v}
                label={t(`onboarding.experience.${v}` as "onboarding.experience.new")}
                selected={experience === v}
                onPick={() => setExperience(v)}
              />
            ))}
          {step === 1 &&
            FREQUENCIES.map((v) => (
              <Choice
                key={v}
                label={t(`onboarding.frequency.${v}` as "onboarding.frequency.never")}
                selected={frequency === v}
                onPick={() => setFrequency(v)}
              />
            ))}
          {step === 2 && (
            <>
              <label className="flex flex-col gap-1 text-sm font-bold text-stone-700">
                {t("onboarding.fide")}
                <input
                  dir="ltr"
                  inputMode="numeric"
                  value={fide}
                  onChange={(e) => setFide(e.target.value.replace(/[^0-9]/g, "").slice(0, 4))}
                  className="min-h-[44px] rounded-2xl border border-stone-200 px-4 py-3 text-left text-base font-normal"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm font-bold text-stone-700">
                {t("onboarding.lichess")}
                <input
                  dir="ltr"
                  value={lichess}
                  onChange={(e) => setLichess(e.target.value)}
                  className="min-h-[44px] rounded-2xl border border-stone-200 px-4 py-3 text-left text-base font-normal"
                />
              </label>
              <label className="flex flex-col gap-1 text-sm font-bold text-stone-700">
                {t("onboarding.chesscom")}
                <input
                  dir="ltr"
                  value={chesscom}
                  onChange={(e) => setChesscom(e.target.value)}
                  className="min-h-[44px] rounded-2xl border border-stone-200 px-4 py-3 text-left text-base font-normal"
                />
              </label>
            </>
          )}
          {step === 3 &&
            GOALS.map((v) => (
              <Choice
                key={v}
                label={t(`onboarding.goal.${v}` as "onboarding.goal.fun")}
                selected={goal === v}
                onPick={() => setGoal(v)}
              />
            ))}
        </div>
        {error ? (
          <p role="alert" className="mt-2 rounded-2xl bg-red-50 px-4 py-3 text-sm font-bold text-red-600">
            {error}
          </p>
        ) : null}
        <div className="mt-3 flex gap-2">
          {step > 0 ? (
            <Button variant="secondary" onClick={() => setStep(step - 1)} className="flex-1">
              {t("onboarding.back")}
            </Button>
          ) : null}
          {step < 3 ? (
            <Button onClick={() => setStep(step + 1)} disabled={!canNext} className="flex-1">
              {step === 2 ? t("onboarding.skipOptional") : t("onboarding.next")}
            </Button>
          ) : (
            <Button onClick={finish} disabled={!canNext || busy} className="flex-1">
              {busy ? t("common.loading") : t("onboarding.finish")}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}

export function questStartTarget(exerciseSlug: string): string {
  return exerciseEntryTarget(exerciseSlug);
}
