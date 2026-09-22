// Web Push subscription helper. Transport only: the backend owns
// subscriptions, preferences, and delivery decisions. Permission is
// never requested on first load; call sites ask after meaningful value.
import { notifyApi } from "../api/client";

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = window.atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) out[i] = raw.charCodeAt(i);
  return out;
}

export type PushState = "unsupported" | "denied" | "subscribed" | "unsubscribed" | "prompt";

export async function pushState(): Promise<PushState> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
    return "unsupported";
  }
  if (Notification.permission === "denied") return "denied";
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    if (sub) return "subscribed";
    return Notification.permission === "granted" ? "unsubscribed" : "prompt";
  } catch {
    return "unsupported";
  }
}

// Must be called from a user gesture with a prior explanation visible.
// Respects denied permissions (never re-prompts) and posts the
// subscription to the server (owner-scoped).
export async function subscribePush(vapidPublicKey: string): Promise<boolean> {
  if (!vapidPublicKey) return false;
  if (!("serviceWorker" in navigator) || !("PushManager" in window)) return false;
  try {
    const reg = await navigator.serviceWorker.ready;
    const existing = await reg.pushManager.getSubscription();
    const sub =
      existing ??
      (await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey) as unknown as ArrayBuffer,
      }));
    const keys = sub.toJSON().keys ?? {};
    await notifyApi.pushSubscribe({
      endpoint: sub.endpoint,
      p256dh: keys.p256dh ?? "",
      auth: keys.auth ?? "",
    });
    await notifyApi.track("notification_permission_granted").catch(() => {});
    return true;
  } catch {
    await notifyApi.track("notification_permission_denied").catch(() => {});
    return false;
  }
}
