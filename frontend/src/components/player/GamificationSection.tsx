import { Badge } from "../ui/Badge";
import { Card } from "../ui/Card";
import type { AchievementItem, GamificationSummary, XpHistoryItem } from "../../api/types";
import { t } from "../../i18n";
import { achievementDescription, achievementName, faNum } from "../../lib/playerDisplay";

interface GamificationSectionProps {
  // null while loading; failed flags the error state with retry.
  summary: GamificationSummary | null;
  achievements: AchievementItem[] | null;
  recentXp: XpHistoryItem[] | null;
  failed: boolean;
  onRetry: () => void;
}

// Player-facing gamification. Display-only: every value comes from the
// server (/me/gamification, /me/gamification/xp, /me/achievements) and
// nothing here decides XP, level, streak, or achievement logic. The only
// client-side math is the presentational progress-bar width.
export function GamificationSection({
  summary,
  achievements,
  recentXp,
  failed,
  onRetry,
}: GamificationSectionProps) {
  if (summary === null && !failed) {
    return (
      <Card>
        <h2 className="font-black">{t("game.title")}</h2>
        <p className="mt-2 text-sm text-stone-500">{t("common.loading")}</p>
      </Card>
    );
  }
  if (failed || summary === null) {
    return (
      <Card>
        <h2 className="font-black">{t("game.title")}</h2>
        <p className="mt-2 text-sm text-stone-500">{t("common.error")}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 flex min-h-[44px] w-full items-center justify-center rounded-2xl bg-violet-600 px-3 text-sm font-bold text-white"
        >
          {t("common.retry")}
        </button>
      </Card>
    );
  }
  const progressPct =
    summary.xp.xp_for_next > 0
      ? Math.min(100, Math.max(0, (summary.xp.xp_in_level / summary.xp.xp_for_next) * 100))
      : 0;
  return (
    <Card>
      <h2 className="font-black">{t("game.title")}</h2>
      <p className="mt-1 text-xs text-stone-500">{t("game.subtitle")}</p>
      {summary.xp.total === 0 ? (
        <p className="mt-2 text-sm text-stone-500">{t("game.empty")}</p>
      ) : null}
      <div className="mt-2 grid grid-cols-3 gap-2">
        <div className="rounded-xl bg-stone-50 px-3 py-2 text-center">
          <p className="text-2xl font-black text-violet-700">{faNum(summary.xp.total)}</p>
          <p className="mt-1 text-xs text-stone-500">{t("game.xp")}</p>
        </div>
        <div className="rounded-xl bg-stone-50 px-3 py-2 text-center">
          <p className="text-2xl font-black text-emerald-700">{faNum(summary.xp.level)}</p>
          <p className="mt-1 text-xs text-stone-500">{t("game.level")}</p>
        </div>
        <div className="rounded-xl bg-stone-50 px-3 py-2 text-center">
          <p className="text-2xl font-black text-amber-600">{faNum(summary.streak.current)}</p>
          <p className="mt-1 text-xs text-stone-500">{t("game.streak")}</p>
        </div>
      </div>
      <div className="mt-2">
        <div
          className="h-2 overflow-hidden rounded-full bg-stone-100"
          role="progressbar"
          aria-valuenow={summary.xp.xp_in_level}
          aria-valuemin={0}
          aria-valuemax={summary.xp.xp_for_next}
        >
          <div className="h-full rounded-full bg-violet-600" style={{ width: `${progressPct}%` }} />
        </div>
        <p className="mt-1 text-xs text-stone-500">
          {`${faNum(summary.xp.xp_in_level)} / ${faNum(summary.xp.xp_for_next)} ${t("game.toNextLevel")}`}
          {` · ${t("game.longestStreak")}: ${faNum(summary.streak.longest)}`}
        </p>
      </div>
      <h3 className="mt-3 font-black">
        {t("game.achievements")} ({faNum(summary.achievements_unlocked)} /{" "}
        {faNum(summary.total_achievements)})
      </h3>
      {achievements === null || achievements.length === 0 ? (
        <p className="mt-2 text-sm text-stone-500">{t("common.loading")}</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-2">
          {achievements.map((item) => (
            <li
              key={item.code}
              className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
            >
              <span>
                <span className="font-bold">{achievementName(item.code)}</span>{" "}
                <span className="text-xs text-stone-500">{achievementDescription(item.code)}</span>
              </span>
              <Badge>{item.unlocked ? t("game.unlocked") : t("game.locked")}</Badge>
            </li>
          ))}
        </ul>
      )}
      <h3 className="mt-3 font-black">{t("game.recentXp")}</h3>
      {recentXp === null ? (
        <p className="mt-2 text-sm text-stone-500">{t("common.loading")}</p>
      ) : recentXp.length === 0 ? (
        <p className="mt-2 text-sm text-stone-500">{t("game.noRecentXp")}</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-2">
          {recentXp.map((entry) => (
            <li
              key={entry.attempt_id}
              className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
            >
              <span className="text-sm text-stone-500">#{faNum(entry.attempt_id)}</span>
              <span className="text-sm font-black text-violet-700">+{faNum(entry.amount)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
