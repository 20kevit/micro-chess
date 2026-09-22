/* MicroChess service worker: Web Push handling only (no caching yet).
 *
 * - push: shows the notification (server sends title/body).
 * - notificationclick: focuses/opens the app at the target URL.
 * Install prompt timing is left to the browser; the app never prompts
 * for notification permission on first load (see lib/push.ts).
 */
self.addEventListener("push", (event) => {
  let title = "میکروچس";
  let body = "";
  let url = "/journey";
  try {
    const data = event.data ? event.data.json() : {};
    if (typeof data.title === "string" && data.title) title = data.title;
    if (typeof data.body === "string") body = data.body;
    if (typeof data.url === "string" && data.url.startsWith("/")) url = data.url;
  } catch {
    try {
      body = event.data ? event.data.text() : "";
    } catch {
      body = "";
    }
  }
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      data: { url },
      dir: "rtl",
      lang: "fa",
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/journey";
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const win of windows) {
        if ("focus" in win) {
          try {
            await win.focus();
          } catch {
            /* ignore */
          }
          try {
            await win.navigate(url);
          } catch {
            /* ignore */
          }
          return;
        }
      }
      await self.clients.openWindow(url);
    })(),
  );
});
