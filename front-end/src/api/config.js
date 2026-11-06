// The back-end address. Set VITE_API_URL in the root .env; without it the local dev address is used (see below).
// In the production build the web app is served by the API itself, so the address is the page's own: an empty prefix.
export const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? "" : "http://localhost:8000");
