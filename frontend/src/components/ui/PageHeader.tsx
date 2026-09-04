import { t } from "../../i18n";
import type { FaKey } from "../../i18n/fa";

// Page header: title + optional subtitle. Presentational only.
export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="mb-4">
      <h1 className="text-2xl font-black text-stone-900">{title}</h1>
      {subtitle ? <p className="mt-1 text-sm text-stone-500">{subtitle}</p> : null}
    </header>
  );
}

// Feedback text by backend-provided key. Unknown keys fall back to generic error.
export function FeedbackText({ feedbackKey }: { feedbackKey: string }) {
  const known: FaKey[] = [
    "feedback.correct",
    "feedback.partial",
    "feedback.wrong",
    "feedback.timeout",
    "feedback.skipped",
    "feedback.abandoned",
  ];
  const text = known.includes(feedbackKey as FaKey)
    ? t(feedbackKey as FaKey)
    : t("common.error");
  return <p className="text-base font-bold text-stone-700">{text}</p>;
}
