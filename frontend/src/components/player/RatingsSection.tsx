import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import type { PlayerRating } from "../../api/types";
import { t } from "../../i18n";
import { exerciseTitle, faNum } from "../../lib/playerDisplay";

interface RatingsSectionProps {
  // null while loading; failed flags the error state with retry.
  ratings: PlayerRating[] | null;
  failed: boolean;
  onRetry: () => void;
}

// Player-facing rated-play activity per exercise. Display-only: every
// value comes from the server (/me/ratings) and nothing here decides
// rating logic. Internal rating numbers are deliberately never shown:
// the section reports rated-game activity (counts + provisional state)
// while accuracy and progress live in the sibling sections.
export function RatingsSection({ ratings, failed, onRetry }: RatingsSectionProps) {
  if (ratings === null && !failed) {
    return (
      <Card>
        <h2 className="font-black">{t("rating.title")}</h2>
        <p className="mt-2 text-sm text-stone-500">{t("common.loading")}</p>
      </Card>
    );
  }
  if (failed || ratings === null) {
    return (
      <Card>
        <h2 className="font-black">{t("rating.title")}</h2>
        <p className="mt-2 text-sm text-stone-500">{t("common.error")}</p>
        <div className="mt-3">
          <Button onClick={onRetry} className="w-full">
            {t("common.retry")}
          </Button>
        </div>
      </Card>
    );
  }
  return (
    <Card>
      <h2 className="font-black">{t("rating.title")}</h2>
      <p className="mt-1 text-xs text-stone-500">{t("rating.subtitle")}</p>
      {ratings.length === 0 ? (
        <p className="mt-2 text-sm text-stone-500">{t("rating.empty")}</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-2">
          {ratings.map((row) => (
            <li
              key={row.exercise}
              className="flex min-h-[44px] items-center justify-between gap-2 rounded-xl bg-stone-50 px-3 py-2"
            >
              <span className="font-bold">{exerciseTitle(row.exercise)}</span>
              <span className="flex items-center gap-2">
                {row.provisional ? <Badge>{t("rating.provisional")}</Badge> : null}
                <span className="text-xs text-stone-500">
                  {`${faNum(row.attempts_count)} ${t("rating.ratedGames")}`}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
