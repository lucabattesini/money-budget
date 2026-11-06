// Registers the service worker that lets the app be installed and open fast. Only in the built app:
// in development a service worker would keep serving old files.
export function registerServiceWorker() {
    if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return;
    window.addEventListener("load", () => {
        navigator.serviceWorker.register("/sw.js").catch((error) => console.error("Service worker failed", error));
    });
}
