// Shared player-platform display helpers (no business logic here).
import type { AttemptResult } from "../api/types";
import { getExerciseMeta } from "../exercises/catalog";
import { t } from "../i18n";
import type { FaKey } from "../i18n/fa";

const RESULT_KEYS: Record<AttemptResult, FaKey> = {
  correct: "report.correct",
  partial: "report.partial",
  wrong: "report.wrong",
  timeout: "feedback.timeout",
  skipped: "feedback.skipped",
  abandoned: "feedback.abandoned",
};

export function resultLabel(result: string): string {
  const key = (RESULT_KEYS as Record<string, FaKey>)[result];
  return key ? t(key) : result;
}

export function exerciseTitle(slug: string): string {
  const meta = getExerciseMeta(slug);
  return meta ? t(meta.titleKey) : slug;
}

export function modeLabel(mode: string): string {
  return mode === "rated" ? t("play.rated") : t("play.practice");
}

export function faNum(n: number): string {
  return n.toLocaleString("fa-IR");
}

export function faPercent(ratio: number): string {
  return `${Math.round(ratio * 100).toLocaleString("fa-IR")}٪`;
}

export function faDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("fa-IR");
}
