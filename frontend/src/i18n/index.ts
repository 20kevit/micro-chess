// Minimal i18n boundary. Persian default; English later.
// Components call t("key") only — never hardcode logic on locale.
import { fa, type FaKey } from "./fa";

// English comes later; keep shape loose so fa remains source of truth.
const en: Partial<Record<FaKey, string>> = {};

let locale: "fa" | "en" = "fa";

export function setLocale(next: "fa" | "en") {
  locale = next;
}

export function t(key: FaKey): string {
  if (locale === "en" && en[key]) return en[key] as string;
  return fa[key] ?? key;
}
