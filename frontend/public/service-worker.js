const CACHE_NAME = "salonehcm-app-shell-v1";
const SHELL_PATHS = ["/", "/index.html", "/manifest.json", "/icon-192.png", "/icon-512.png"];

function isApiPath(pathname) {
  return pathname === "/api" || pathname.startsWith("/api/");
}

function isStaticAsset(pathname) {
  return pathname.startsWith("/static/")
    || /\.(?:js|css|png|svg|ico|woff2?)$/i.test(pathname);
}

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    let shellResponse;
    try {
      shellResponse = await fetch("/", { cache: "reload" });
    } catch {
      shellResponse = await fetch("/index.html", { cache: "reload" });
    }
    if (shellResponse.ok) {
      const shellCopy = shellResponse.clone();
      await cache.put("/", shellCopy.clone());
      await cache.put("/index.html", shellCopy);
      const html = await shellResponse.text();
      const references = [...html.matchAll(/(?:src|href)=["']([^"']+\.(?:js|css))[^"']*["']/gi)];
      const assets = references.map((match) => new URL(match[1], self.location.origin))
        .filter((url) => url.origin === self.location.origin && !isApiPath(url.pathname));
      await Promise.all(assets.map(async (url) => {
        try {
          const response = await fetch(url.href, { cache: "reload" });
          if (response.ok && response.type === "basic") {
            await cache.put(url.href, response);
          }
        } catch {
          // One missing optional asset should not prevent the app shell from installing.
        }
      }));
    }
    await Promise.all(SHELL_PATHS.slice(2).map(async (path) => {
      try {
        const response = await fetch(path, { cache: "reload" });
        if (response.ok) await cache.put(path, response);
      } catch {
        // Keep installation available if an optional icon or manifest is missing.
      }
    }));
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames
      .filter((name) => name.startsWith("salonehcm-app-shell-") && name !== CACHE_NAME)
      .map((name) => caches.delete(name)));
  })());
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || isApiPath(url.pathname)) return;

  if (request.mode === "navigate") {
    event.respondWith((async () => {
      try {
        const response = await fetch(request);
        if (response.ok && response.headers.get("content-type")?.includes("text/html")) {
          const cache = await caches.open(CACHE_NAME);
          await cache.put("/index.html", response.clone());
        }
        return response;
      } catch {
        return (await caches.match("/index.html"))
          || (await caches.match("/"))
          || new Response("SaloneHCM is offline. Reconnect and try again.", {
            status: 503,
            headers: { "Content-Type": "text/plain; charset=utf-8" },
          });
      }
    })());
    return;
  }

  if (!isStaticAsset(url.pathname)) return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(request);
    if (cached) return cached;
    const response = await fetch(request);
    if (response.ok && response.type === "basic") {
      await cache.put(request, response.clone());
    }
    return response;
  })());
});
