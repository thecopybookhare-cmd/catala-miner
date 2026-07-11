// Service worker de CatalàMiner. Convierte la web en PWA instalable y da un
// arranque offline del "shell". Nunca cachea /api/ ni /media/ (dinámicos y
// pesados). Sube CACHE al publicar para invalidar el shell viejo.
const CACHE = "catalaminer-0.9.12";
const SHELL = [
  "/",
  "/index.html",
  "/app.js",
  "/i18n.js",
  "/style.css",
  "/favicon.png",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;          // solo mismo origen
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/media/")) return;

  // Navegaciones: red primero, index.html cacheado como fallback offline.
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req)
        .then((res) => {
          caches.open(CACHE).then((c) => c.put("/index.html", res.clone()));
          return res;
        })
        .catch(() => caches.match("/index.html").then((r) => r || caches.match("/")))
    );
    return;
  }

  // Recursos estáticos: stale-while-revalidate (rápido y se actualiza solo).
  // ignoreSearch: el shell se precachea SIN query pero la página pide
  // /app.js?v=x.y.z — sin esto, el arranque offline moría tras actualizar.
  e.respondWith(
    caches.match(req, { ignoreSearch: true }).then((cached) => {
      const net = fetch(req)
        .then((res) => {
          if (res && res.ok) {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(url.pathname, copy));
          }
          return res;
        })
        .catch(() => cached || Response.error());
      return cached || net;
    })
  );
});
