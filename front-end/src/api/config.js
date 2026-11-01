// The back-end address. Set VITE_API_URL in the root .env; without it the local dev address is used.
export const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
