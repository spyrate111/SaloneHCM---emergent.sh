/* SaloneHCM service worker — enterprise offline shell + queue with status tracking. */

// Cache version — bump when strategy changes; old caches get purged on activate.
const APP_SHELL_CACHE = "salonehcm-shell-v5";
const RUNTIME_CACHE = "salonehcm-runtime-v5";
const PAYSLIP_CACHE = "salonehcm-payslip-v5";
const ALL_CACHES = [APP_SHELL_CACHE, RUNTIME_CACHE, PAYSLIP_CACHE];
// Caches that must SURVIVE version bumps (user-saved offline payslip pack).
const PERSISTENT_PREFIX = "salonehcm-payslip-pack";

// Files we know exist up front — index.html gives us the SPA entry, favicon
// and the manifest let install progress. Everything else is populated on
// demand by the fetch handler.
const CORE_ASSETS = ["/", "/index.html", "/manifest.json", "/icon-192.png", "/icon-512.png"];

// JSON endpoints we cache for offline self-service.
const CACHEABLE_API_PATTERNS = [
  /\/api\/payroll\/my-payslip$/,
  /\/api\/payroll\/my-payslips$/,
  /\/api\/auth\/me$/,
  /\/api\/mobile\/summary$/,
  /\/api\/mobile\/punch\/today$/,
  /\/api\/leave$/,
];

// Endpoints whose POST bodies we queue when offline (network-first + fallback).
const QUEUEABLE_POST_PATTERNS = [
  /\/api\/attendance(\b|\/)/,
  /\/api\/mobile\/punch$/,
  /\/api\/leave$/,
];

// Max attempts before marking a queued item "failed" — user then has to
// manually retry from the Clock screen.
const MAX_ATTEMPTS = 5;

/* --------------------------------------------------------------------- */
/*  Lifecycle                                                             */
/* --------------------------------------------------------------------- */

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(APP_SHELL_CACHE)
      .then((c) => c.addAll(CORE_ASSETS))
      .catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    // Purge stale caches from prior versions
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => !ALL_CACHES.includes(k) && !k.startsWith(PERSISTENT_PREFIX)).map((k) => caches.delete(k)));
    await self.clients.claim();
  })());
});

/* --------------------------------------------------------------------- */
/*  IndexedDB queue with explicit status tracking                          */
/* --------------------------------------------------------------------- */

const DB_NAME = "salonehcm-queue";
const DB_VERSION = 2; // v2 adds status/attempts/last_error
const STORE = "pending";

function openQ() {
  return new Promise((res, rej) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
      }
      // v2 migration: add status field to any legacy rows (they'll be
      // treated as "queued" on first read, no need to touch here).
    };
    req.onsuccess = () => res(req.result);
    req.onerror = () => rej(req.error);
  });
}

async function queueRequest(record) {
  const db = await openQ();
  const row = {
    ...record,
    status: "queued",
    attempts: 0,
    last_error: null,
    queued_at: record.queued_at || new Date().toISOString(),
  };
  return new Promise((res, rej) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).add(row);
    tx.oncomplete = () => res(true);
    tx.onerror = () => rej(tx.error);
  });
}

async function readQueue() {
  const db = await openQ();
  return new Promise((res) => {
    const tx = db.transaction(STORE, "readonly");
    const req = tx.objectStore(STORE).getAll();
    req.onsuccess = () => res(req.result || []);
    req.onerror = () => res([]);
  });
}

async function updateItem(id, patch) {
  const db = await openQ();
  const tx = db.transaction(STORE, "readwrite");
  const store = tx.objectStore(STORE);
  const cur = await new Promise((r) => { const q = store.get(id); q.onsuccess = () => r(q.result); q.onerror = () => r(null); });
  if (!cur) return;
  Object.assign(cur, patch);
  store.put(cur);
}

async function deleteItem(id) {
  const db = await openQ();
  return new Promise((res) => {
    const tx = db.transaction(STORE, "readwrite");
    tx.objectStore(STORE).delete(id);
    tx.oncomplete = () => res(true);
    tx.onerror = () => res(false);
  });
}

/** Broadcast the current queue state to every open window client. */
async function broadcastQueue(extra) {
  const items = await readQueue();
  const summary = {
    queued: items.filter((i) => i.status === "queued").length,
    syncing: items.filter((i) => i.status === "syncing").length,
    failed: items.filter((i) => i.status === "failed").length,
    total: items.length,
  };
  const clients = await self.clients.matchAll({ type: "window" });
  clients.forEach((c) => c.postMessage({ kind: "queue-status", summary, items, ...extra }));
}

/** Mutex — reconnects fire online events + BackgroundSync + manual drains
 *  concurrently; without this, each pass replays the same queued items. */
let _drainInFlight = null;
function drainQueue() {
  if (_drainInFlight) return _drainInFlight;
  _drainInFlight = _drainQueue().finally(() => { _drainInFlight = null; });
  return _drainInFlight;
}

/** Try to POST every queued item. Returns the count synced this pass. */
async function _drainQueue() {
  const items = await readQueue();
  let synced = 0;
  let failedThisPass = 0;
  for (const it of items) {
    if (it.status === "failed") continue; // needs manual retry
    await updateItem(it.id, { status: "syncing" });
    await broadcastQueue({ event: "syncing", id: it.id });
    try {
      const r = await fetch(it.url, {
        method: it.method,
        headers: it.headers,
        body: it.body,
        credentials: "include", // ship the session cookie
      });
      if (r.ok || r.status === 202) {
        await deleteItem(it.id);
        synced += 1;
        await broadcastQueue({ event: "synced", id: it.id });
      } else {
        const attempts = (it.attempts || 0) + 1;
        const status = attempts >= MAX_ATTEMPTS ? "failed" : "queued";
        let errText = "";
        try { errText = (await r.text()).slice(0, 200); } catch (_) { /* ignore */ }
        await updateItem(it.id, {
          status, attempts, last_error: `HTTP ${r.status} ${errText}`,
        });
        if (status === "failed") failedThisPass += 1;
        await broadcastQueue({ event: status, id: it.id });
      }
    } catch (e) {
      // Network error — leave as queued so we retry on the next connectivity blip
      const attempts = (it.attempts || 0) + 1;
      await updateItem(it.id, {
        status: "queued", attempts,
        last_error: e && e.message ? e.message : "network unreachable",
      });
    }
  }
  if (synced > 0 || failedThisPass > 0) {
    if (synced > 0) await invalidateMobileApiCache().catch(() => {});
    // Legacy message shape kept for existing MobileClock listeners
    const clients = await self.clients.matchAll({ type: "window" });
    clients.forEach((c) => c.postMessage({ kind: "queue-drained", count: synced, failed: failedThisPass }));
  }
  await broadcastQueue({ event: "drain-complete", synced, failed: failedThisPass });
  return synced;
}

/** Drop cached /api/mobile/ GETs so post-sync refreshes fetch fresh data. */
async function invalidateMobileApiCache() {
  const cache = await caches.open(PAYSLIP_CACHE);
  const keys = await cache.keys();
  await Promise.all(
    keys.filter((r) => new URL(r.url).pathname.startsWith("/api/mobile/"))
        .map((r) => cache.delete(r))
  );
}

/** Reset a "failed" item back to "queued" so the next drain will retry it. */
async function retryFailed(id) {
  await updateItem(id, { status: "queued", attempts: 0, last_error: null });
  await broadcastQueue({ event: "retry-requested", id });
  return drainQueue();
}

async function purgeFailed() {
  const items = await readQueue();
  for (const it of items) {
    if (it.status === "failed") await deleteItem(it.id);
  }
  await broadcastQueue({ event: "purged" });
}

/* --------------------------------------------------------------------- */
/*  Sync events + message handlers                                        */
/* --------------------------------------------------------------------- */

self.addEventListener("sync", (event) => {
  if (event.tag === "salonehcm-clockin") {
    event.waitUntil(drainQueue());
  }
});

self.addEventListener("message", (event) => {
  const d = event.data || {};
  if (d.kind === "drain-queue") event.waitUntil(drainQueue());
  else if (d.kind === "queue-status") event.waitUntil(broadcastQueue({ event: "poll" }));
  else if (d.kind === "retry-failed" && d.id) event.waitUntil(retryFailed(d.id));
  else if (d.kind === "purge-failed") event.waitUntil(purgeFailed());
  else if (d.kind === "skip-waiting") self.skipWaiting();
});

/* --------------------------------------------------------------------- */
/*  Fetch strategies                                                      */
/* --------------------------------------------------------------------- */

self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // === queueable POSTs (attendance, punches, leave) ===
  if (request.method === "POST" &&
      QUEUEABLE_POST_PATTERNS.some((re) => re.test(url.pathname))) {
    event.respondWith((async () => {
      try {
        return await fetch(request.clone());
      } catch (e) {
        const headers = {};
        request.headers.forEach((v, k) => { headers[k] = v; });
        const body = await request.clone().text();
        await queueRequest({
          url: request.url, method: request.method, headers, body,
          endpoint: url.pathname,
        });
        // notify UI
        self.clients.matchAll({ type: "window" }).then((cs) => {
          cs.forEach((c) => c.postMessage({
            kind: "queue-added",
            url: url.pathname,
            queued_at: new Date().toISOString(),
          }));
        });
        broadcastQueue({ event: "queue-added" });
        try { await self.registration.sync?.register("salonehcm-clockin"); } catch (_) { /* noop */ }
        return new Response(JSON.stringify({ queued: true, offline: true }), {
          status: 202, headers: { "Content-Type": "application/json" },
        });
      }
    })());
    return;
  }

  // === cacheable API GETs (payslips, me, mobile summary, leave list) ===
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
        }).catch(() => cached || _offlineJson());
        return cached || network;
      })());
      return;
    }
    // All other API GETs — pass through, no caching (they need fresh data)
    return;
  }

  // === Navigation requests (SPA routes) — network-first, fallback to
  //     cached index.html so the app can bootstrap fully offline.
  if (request.mode === "navigate") {
    event.respondWith((async () => {
      try {
        const network = await fetch(request);
        // Cache a copy of successful navigates so /m, /dashboard, etc. reload
        // offline. Also refresh the /index.html copy since it's the SPA entry.
        if (network && network.status === 200) {
          const clone = network.clone();
          const cache = await caches.open(APP_SHELL_CACHE);
          cache.put(request, clone).catch(() => {});
          // Refresh /index.html so future navigate-fallbacks are current
          if (url.pathname !== "/index.html") {
            try {
              const idxRes = await fetch("/index.html");
              if (idxRes && idxRes.status === 200) cache.put("/index.html", idxRes.clone()).catch(() => {});
            } catch (_) { /* offline; fine */ }
          }
        }
        return network;
      } catch (e) {
        // Offline — reach into the shell cache. First try the exact URL, then
        // any known fallback that carries the SPA bundle entrypoints.
        const cache = await caches.open(APP_SHELL_CACHE);
        const hit = await cache.match(request)
          || await cache.match("/index.html")
          || await cache.match("/dashboard")
          || await cache.match("/");
        return hit || _offlineHtml();
      }
    })());
    return;
  }

  // === Static assets (JS, CSS, images, fonts) — cache-first with runtime
  //     population. This is what makes offline refresh actually work: the
  //     hashed CRA bundles referenced by index.html must be in cache.
  if (request.method === "GET") {
    event.respondWith((async () => {
      const cached = await caches.match(request);
      if (cached) {
        // Refresh in background (revalidate) but return the cache immediately
        fetch(request).then((res) => {
          if (res && res.status === 200) {
            caches.open(RUNTIME_CACHE).then((c) => c.put(request, res.clone())).catch(() => {});
          }
        }).catch(() => {});
        return cached;
      }
      try {
        const res = await fetch(request);
        if (res && res.status === 200 && (res.type === "basic" || res.type === "cors")) {
          const copy = res.clone();
          caches.open(RUNTIME_CACHE).then((c) => c.put(request, copy)).catch(() => {});
        }
        return res;
      } catch (e) {
        // Last-ditch offline fallback for images
        if (request.destination === "image") {
          return new Response("", { status: 504 });
        }
        return _offlineText();
      }
    })());
  }
});

/* Synthetic offline responses */
function _offlineHtml() {
  return new Response(`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SaloneHCM · Offline</title><style>body{font-family:system-ui,sans-serif;background:#F7F6F2;color:#1A1C1E;padding:2rem;text-align:center}h1{color:#0A4A1E}.pill{display:inline-block;padding:.4rem .8rem;background:#F6EDD8;color:#8B6A14;border-radius:99px;font-size:12px;margin-top:1rem}</style></head><body><h1>You appear to be offline</h1><p>SaloneHCM couldn't reach the network. Please connect and refresh.</p><p class="pill">Any punches or leave requests you made are safely queued and will sync automatically.</p></body></html>`,
    { status: 200, headers: { "Content-Type": "text/html; charset=utf-8" } });
}
function _offlineJson() {
  return new Response(JSON.stringify({ offline: true, error: "network unreachable" }),
    { status: 503, headers: { "Content-Type": "application/json" } });
}
function _offlineText() {
  return new Response("Offline", { status: 503 });
}

/* --------------------------------------------------------------------- */
/*  Push notifications (unchanged from v4)                                */
/* --------------------------------------------------------------------- */

self.addEventListener("push", (event) => {
  let data = { title: "SaloneHCM", body: "You have a new notification" };
  try { if (event.data) data = event.data.json(); } catch (e) { /* not json */ }
  const title = data.title || "SaloneHCM";
  const options = {
    body: data.body || "",
    icon: "/icon-192.png",
    badge: "/icon-192.png",
    data: {
      url: data.url || "/m",
      kind: data.kind || "info",
      employee_id: data.employee_id || null,
      employee_name: data.employee_name || null,
    },
    tag: data.tag || data.kind || "salonehcm",
    renotify: true,
  };
  // Out-of-zone alerts get an inline "Snooze" action for legitimate field work.
  if (data.kind === "ooz_alert" && data.employee_id) {
    options.actions = [{ action: "snooze", title: "Snooze alerts for this employee" }];
  }
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const d = event.notification.data || {};
  let url = d.url || "/m";
  if (event.action === "snooze" && d.employee_id) {
    url = `/m/clock?snooze=${encodeURIComponent(d.employee_id)}&name=${encodeURIComponent(d.employee_name || "")}`;
  }
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((all) => {
      for (const c of all) {
        if ("focus" in c) { c.navigate(url).catch(() => {}); return c.focus(); }
      }
      return self.clients.openWindow(url);
    })
  );
});
