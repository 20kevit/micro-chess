// Marketing attribution persistence (first-touch survives registration).
//
// The backend row is the source of truth after registration, but the
// touch itself must survive Landing -> Register -> verification/login in
// the browser first. React memory is not enough (reloads, navigation),
// so touches persist in localStorage. No personal data is stored here —
// only campaign/coupon codes from the URL. Backend validates everything.
const STORAGE_KEY = "microchess.attribution.v1";

export interface AttributionTouch {
  campaign_slug: string | null;
  coupon_code: string | null;
  landing_path: string | null;
}

export interface StoredAttribution {
  first: AttributionTouch & { touched_at: string };
  last: AttributionTouch & { touched_at: string };
}

function cleanSlug(value: string | null): string | null {
  const v = (value ?? "").trim().toLowerCase();
  return v ? v.slice(0, 100) : null;
}

function cleanCode(value: string | null): string | null {
  const v = (value ?? "").trim().toUpperCase();
  return v ? v.slice(0, 64) : null;
}

export function parseAttributionSearch(search: string): AttributionTouch | null {
  let params: URLSearchParams;
  try {
    params = new URLSearchParams(search.startsWith("?") ? search : `?${search}`);
  } catch {
    return null;
  }
  // Supported scheme: ?campaign= / ?ref= (campaign slug alias) and
  // ?coupon= (coupon code). Explicit ?coupon= wins over ?ref= for codes.
  const campaign = cleanSlug(params.get("campaign") ?? params.get("ref"));
  const coupon = cleanCode(params.get("coupon"));
  const refAsCode = coupon ? null : cleanCode(params.get("ref"));
  if (!campaign && !coupon && !refAsCode) return null;
  return {
    campaign_slug: campaign,
    coupon_code: coupon ?? refAsCode,
    landing_path: null,
  };
}

export function getStoredAttribution(): StoredAttribution | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredAttribution;
    if (!parsed || typeof parsed !== "object" || !parsed.first || !parsed.last) return null;
    return parsed;
  } catch {
    return null;
  }
}

function setStored(value: StoredAttribution): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Storage blocked: attribution simply won't survive reloads.
  }
}

// Merge a URL touch into storage. First-touch is write-once (never
// overwritten); last-touch always refreshes. Returns the stored value
// (or null when the URL carried nothing and nothing was stored).
export function captureAttribution(search: string, path: string): StoredAttribution | null {
  const touch = parseAttributionSearch(search);
  const now = new Date().toISOString();
  const landingPath = (path || "/").slice(0, 500);
  const stored = getStoredAttribution();
  if (!touch) return stored;
  const current: AttributionTouch = {
    campaign_slug: touch.campaign_slug,
    coupon_code: touch.coupon_code,
    landing_path: landingPath,
  };
  if (!stored) {
    const fresh: StoredAttribution = {
      first: { ...current, touched_at: now },
      last: { ...current, touched_at: now },
    };
    setStored(fresh);
    return fresh;
  }
  const merged: StoredAttribution = {
    first: stored.first,
    last: { ...current, touched_at: now },
  };
  setStored(merged);
  return merged;
}

// Extra fields for the register request. The server normalizes and
// validates; invalid coupons never break registration.
export function buildRegisterAttribution(): {
  coupon_code?: string;
  campaign_slug?: string;
  landing_path?: string;
} {
  const stored = getStoredAttribution();
  const last = stored?.last;
  const out: { coupon_code?: string; campaign_slug?: string; landing_path?: string } = {};
  if (last?.coupon_code) out.coupon_code = last.coupon_code;
  if (last?.campaign_slug) out.campaign_slug = last.campaign_slug;
  if (last?.landing_path) out.landing_path = last.landing_path;
  return out;
}
