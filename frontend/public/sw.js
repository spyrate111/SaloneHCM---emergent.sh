/* SaloneHCM service worker — offline shell, payslip cache, push notifications, clock-in sync. */
const STATIC_CACHE = "salonehcm-static-v3";
const RUNTIME_CACHE = "salonehcm-runtime-v3";
const PAYSLIP_CACHE = "salonehcm-payslip-v3";
const STATIC_ASSETS = ["/", "/dashboard", "/self-service", "/manifest.json"];
// Endpoints whose JSON responses we cache for offline ESS
const CACHEABLE_API_PATTERNS = [
  /\/api\/payroll\/my-payslip$/,
  /\/api\/payroll\/my-payslips$/,
  /\/api\/auth\/me$/,
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(STATIC_CACHE).then((c) => c.addAll(STATIC_ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => ![STATIC_CACHE, RUNTIME_CACHE, PAYSLIP_CACHE].includes(k))
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

/* ---------- IndexedDB queue for offline clock-ins ---------- */
function openQ() {
  return new Promise((res, rej) => {
    const req = indexedDB.open("salonehcm-queue", 1);
    req.onupgradeneeded = () => req.result.createObjectStore("pending", { keyPath: "id", autoIncrement: true });
    req.onsuccess = () => res(req.result);
    req.onerror = () => rej(req.error);
  });
}
async function queueRequest(record) {
  const db = await openQ();
  return new Promise((res, rej) => {
    const tx = db.transaction("pending", "readwrite");
    tx.objectStore("pending").add(record);
    tx.oncomplete = () => res(true);
    tx.onerror = () => rej(tx.error);
  });
}
async function drainQueue() {
  const db = await openQ();
  const tx = db.transaction("pending", "readwrite");
  const store = tx.objectStore("pending");
  return new Promise((res) => {
    const req = store.getAll();
    req.onsuccess = async () => {
      const items = req.result || [];
      let drained = 0;
      for (const it of items) {
        try {
          const r = await fetch(it.url, {
            method: it.method,
            headers: it.headers,
            body: it.body,
            credentials: "omit",
          });
          if (r.ok) {
            store.delete(it.id);
            drained += 1;
          }
        } catch (e) { /* still offline */ }
      }
      if (drained > 0) {
        self.clients.matchAll({ type: "window" }).then((cs) => {
          cs.forEach((c) => c.postMessage({ kind: "queue-drained", count: drained }));
        });
      }
      res(drained);
    };
  });
}

self.addEventListener("sync", (event) => {
  if (event.tag === "salonehcm-clockin") {
    event.waitUntil(drainQueue());
  }
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.kind === "drain-queue") {
    event.waitUntil(drainQueue());
  }
});

/* ---------- Fetch strategy ---------- */
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method === "POST" && /\/api\/attendance(\b|\/)/.test(url.pathname)) {
    // Network-first; if offline, queue + return synthetic 202
    event.respondWith((async () => {
      try {
        return await fetch(request.clone());
      } catch (e) {
        const headers = {};
        request.headers.forEach((v, k) => { headers[k] = v; });
        const body = await request.clone().text();
        await queueRequest({
          url: request.url, method: request.method, headers, body,
          queued_at: new Date().toISOString(),
        });
        return new Response(JSON.stringify({ queued: true, offline: true }), {
          status: 202, headers: { "Content-Type": "application/json" },
        });
      }
    })());
    return;
  }

  if (request.method === "GET" && url.pathname.startsWith("/api/")) {
    const cacheable = CACHEABLE_API_PATTERNS.some((re) => re.test(url.pathname));
    if (cacheable) {
      // Stale-while-revalidate
      event.respondWith((async () => {
        const cache = await caches.open(PAYSLIP_CACHE);
        const cached = await cache.match(request);
        const network = fetch(request).then((res) => {
          if (res && res.status === 200) cache.put(request, res.clone()).catch(() => {});
          return res;
        }).catch(() => cached);
        return cached || network;
      })());
      return;
    }
    return; // other API calls: pass-through (no caching)
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() => caches.match("/dashboard").then((m) => m || caches.match("/")))
    );
    return;
  }

  if (request.method === "GET") {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((res) => {
        if (res && res.status === 200) {
          const copy = res.clone();
          caches.open(RUNTIME_CACHE).then((c) => c.put(request, copy)).catch(() => {});
        }
        return res;
      }).catch(() => cached))
    );
  }
});

/* ---------- Push notifications ---------- */
self.addEventListener("push", (event) => {
  let data = { title: "SaloneHCM", body: "You have a new notification" };
  try { if (event.data) data = event.data.json(); } catch (e) { /* not json */ }
  const title = data.title || "SaloneHCM";
  const options = {
    body: data.body || "",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    data: { url: data.url || "/dashboard", kind: data.kind || "info" },
    tag: data.tag || data.kind || "salonehcm",
    renotify: true,
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/dashboard";
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((all) => {
      for (const c of all) {
        if ("focus" in c) { c.navigate(url).catch(() => {}); return c.focus(); }
      }
      return self.clients.openWindow(url);
    })
  );
});
