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

const ACHIEVEMENT_CODES = ["first_steps", "steady_10", "xp_100", "streak_3"] as const;

export type AchievementCode = (typeof ACHIEVEMENT_CODES)[number];

// Achievement display text. Unknown codes fall back to the raw code so a
// future server-side addition never breaks rendering.
export function achievementName(code: string): string {
  const key = `game.achievement.${code}.name` as FaKey;
  const text = t(key);
  return text === key ? code : text;
}

export function achievementDescription(code: string): string {
  const key = `game.achievement.${code}.desc` as FaKey;
  const text = t(key);
  return text === key ? "" : text;
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

export function faDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("fa-IR");
}

const ADMIN_STATUS_KEYS: Record<string, FaKey> = {
  draft: "admin.statusDraft",
  validated: "admin.statusValidated",
  reviewed: "admin.statusReviewed",
  approved: "admin.statusApproved",
  published: "admin.statusPublished",
  quarantined: "admin.status.quarantined",
  rejected: "admin.status.rejected",
  retired: "admin.status.retired",
  archived: "admin.status.retired",
  pending: "admin.status.pending",
  trialing: "admin.status.trialing",
  active: "admin.status.active",
  expired: "admin.status.expired",
  cancelled: "admin.status.cancelled",
  past_due: "admin.status.past_due",
  requires_action: "admin.status.requires_action",
  verified: "admin.status.verified",
  failed: "admin.status.failed",
  revoked: "admin.status.revoked",
  pass: "admin.status.verified",
  fail: "admin.status.failed",
  high: "admin.status.high",
  medium: "admin.status.medium",
  normal: "admin.status.normal",
  low: "admin.confidence.low",
  emerging: "admin.user.learning",
  developing: "admin.user.learning",
  struggling: "admin.user.learning",
  proficient: "admin.user.mastery",
  mastered: "admin.user.mastery",
  unseen: "admin.empty",
  direct: "admin.evidence.strong",
  strong: "admin.evidence.strong",
  weak: "admin.evidence.weak",
  positive: "admin.evidence.positive",
  negative: "admin.evidence.negative",
  neutral: "admin.evidence.neutral",
  open: "admin.support.new",
  answered: "admin.support.answered",
  closed: "admin.support.closed",
  applied: "admin.status.verified",
  shown: "admin.status.verified",
  accepted: "admin.status.verified",
  completed: "admin.status.verified",
  skipped: "feedback.skipped",
  abandoned: "feedback.abandoned",
};

export function adminStatusLabel(value: string | null | undefined): string {
  if (!value) return t("admin.notAvailable");
  return t(ADMIN_STATUS_KEYS[value] ?? "admin.unknown");
}

const ADMIN_SOURCE_KEYS: Record<string, FaKey> = {
  manual: "admin.sourceManual",
  generated: "admin.sourceGenerated",
  imported: "admin.sourceImported",
  free_beta: "admin.sourceFreeBeta",
  trial: "admin.sourceTrial",
  coupon: "admin.sourceCoupon",
  paid: "admin.sourcePaid",
  payment: "admin.sourcePaid",
  none: "admin.sourceNone",
};

export function adminSourceLabel(value: string | null | undefined): string {
  if (!value) return t("admin.notAvailable");
  return t(ADMIN_SOURCE_KEYS[value] ?? "admin.unknown");
}

const BILLING_INTERVAL_KEYS: Record<string, FaKey> = {
  none: "admin.plans.none",
  monthly: "admin.plans.monthly",
  yearly: "admin.plans.yearly",
  annual: "admin.plans.yearly",
  lifetime: "admin.plans.lifetime",
};

export function billingIntervalLabel(value: string): string {
  return t(BILLING_INTERVAL_KEYS[value] ?? "admin.unknown");
}

const COUPON_TYPE_KEYS: Record<string, FaKey> = {
  percent: "admin.coupon.percent",
  fixed: "admin.coupon.fixed",
  free_trial: "admin.coupon.freeTrial",
};

export function couponTypeLabel(value: string): string {
  return t(COUPON_TYPE_KEYS[value] ?? "admin.unknown");
}

export function verificationChannelLabel(value: string | null | undefined): string {
  if (value === "telegram") return t("verify.telegram");
  if (value === "bale") return t("verify.bale");
  return t("admin.notAvailable");
}

// Adaptive recommendation reason text. Unknown codes fall back to the
// raw code so a future server-side addition never breaks rendering.
export function adaptiveReasonLabel(reason: string): string {
  const key = `adaptive.reason.${reason}` as FaKey;
  const text = t(key);
  return text === key ? reason : text;
}

// P8 recommendation reason text (machine-readable codes from
// GET /me/recommendations). Unknown codes fall back to the raw code so
// a future server-side addition never breaks rendering.
export function recommendationReasonLabel(reason: string): string {
  const key = `recommendation.reason.${reason}` as FaKey;
  const text = t(key);
  return text === key ? reason : text;
}

// Observed-difficulty text. Derived-platform labels only, never answers.
export function observedDifficultyLabel(label: string): string {
  const key = `adaptive.observed.${label}` as FaKey;
  const text = t(key);
  return text === key ? label : text;
}
