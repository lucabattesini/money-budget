// Keeps the app's own files so it opens quickly and the installed app starts even with a bad connection.
// Only files from this site are kept; the API (another address) and every non-GET request always go to the network.
const CACHE = "money-budget-v1";
const SHELL = ["/", "/manifest.json", "/icon-192.png", "/favicon.png", "/apple-touch-icon.png"];

self.addEventListener("install", (event) => {
    event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
            .then(() => self.clients.claim()),
    );
});

self.addEventListener("fetch", (event) => {
    const { request } = event;
    const url = new URL(request.url);
    if (request.method !== "GET" || url.origin !== self.location.origin) return;

    // The page itself: the network first (so a new version shows up), the kept copy when offline
    if (request.mode === "navigate") {
        event.respondWith(fetch(request).catch(() => caches.match("/")));
        return;
    }

    // Built files have a new name whenever they change, so a kept copy is always right
    event.respondWith(
        caches.match(request).then((kept) => kept || fetch(request).then((response) => {
            if (response.ok && url.pathname.startsWith("/assets/")) {
                const copy = response.clone();
                caches.open(CACHE).then((cache) => cache.put(request, copy));
            }
            return response;
        })),
    );
});
