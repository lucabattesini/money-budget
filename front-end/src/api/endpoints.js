import { API_URL } from "./config";

const URL_BASE = API_URL;

export const endpoints = {
    categories: `${URL_BASE}/categories`,
    transactions: `${URL_BASE}/transactions`,
    exports: `${URL_BASE}/exports`,
    user: `${URL_BASE}/user`,
    auth: `${URL_BASE}/auth`,
};

// ─── Auth ────────────────────────────────────────────────────────────────────

export function loginWithGoogle(idToken, phone) {
    return fetch(endpoints.auth + "/google", {
        method: "post",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: idToken, whatsapp_phone: phone }),
    })
    .then(res => {
        if (!res.ok) throw new Error("Google auth failed");
        return res.json();
    })
    .catch(error => console.error("Failed to login with Google", error));
}

// Deprecated email/password routes to prevent Vite from crashing
export function loginUser() { return Promise.resolve(); }
export function createUser() { return Promise.resolve(); }

export function getMe(token) {
    return fetch(endpoints.user + "/me", {
        method: "get",
        headers: { Authorization: `Bearer ${token}` },
    })
    .then(res => res.json())
    .catch(error => console.error("Failed to get current user", error));
}

export function updatePhone(phone, token) {
    return fetch(endpoints.user + "/me/phone", {
        method: "PATCH",
        headers: { 
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}` 
        },
        body: JSON.stringify({ whatsapp_phone: phone })
    })
    .then(res => {
        if (!res.ok) throw new Error("Failed to update phone");
        return res.json();
    })
    .catch(error => console.error("Failed to update phone", error));
}

// ─── Categories ───────────────────────────────────────────────────────────────

export function getAllCategories(token) {
    return fetch(endpoints.categories, {
        method: "get",
        headers: { Authorization: `Bearer ${token}` },
    })
    .then(res => res.json())
    .catch(error => console.error("Failed to get categories", error));
}

// ─── Transactions ─────────────────────────────────────────────────────────────

export function getSummedTransactionsByCategory(date, token) {
    return fetch(endpoints.transactions + "/summed-by-category", {
        method: "post",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(date),
    })
    .then(res => res.json())
    .catch(error => console.error("Failed to get transactions", error));
}

export function getTransactions(date, token) {
    return fetch(endpoints.transactions, {
        method: "post",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(date),
    })
    .then(res => res.json())
    .catch(error => console.error("Failed to get transactions", error));
}

export function insertNewTransaction(payload, token) {
    return fetch(endpoints.transactions + "/create", {
        method: "post",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
    })
    .then(res => {
        const body = res.json();
        return { status: res.status, body };
    })
    .catch(error => console.error("Failed to insert new transaction", error));
}

// ─── Exports (files built in the background) ──────────────────────────────────

// Queue an export. Resolves { ok: true, job } or { ok: false }.
export function createExport(format, token) {
    return fetch(endpoints.exports, {
        method: "post",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ format }),
    })
    .then(async res => (res.ok ? { ok: true, job: (await res.json()).data } : { ok: false }))
    .catch(error => {
        console.error("Failed to queue export", error);
        return { ok: false };
    });
}

// The state of a job. Resolves { ok, status (HTTP), job } and { ok: false } when the server cannot be reached.
export function getExport(id, token) {
    return fetch(endpoints.exports + `/${id}`, {
        method: "get",
        headers: { Authorization: `Bearer ${token}` },
    })
    .then(async res => (res.ok ? { ok: true, status: res.status, job: (await res.json()).data } : { ok: false, status: res.status }))
    .catch(error => {
        console.error("Failed to get export", error);
        return { ok: false };
    });
}

// The finished file. Resolves { ok: true, blob } or { ok: false }.
export function downloadExport(id, token) {
    return fetch(endpoints.exports + `/${id}/file`, {
        method: "get",
        headers: { Authorization: `Bearer ${token}` },
    })
    .then(async res => (res.ok ? { ok: true, blob: await res.blob() } : { ok: false }))
    .catch(error => {
        console.error("Failed to download export", error);
        return { ok: false };
    });
}

export function updateTransaction(id, payload, token) {
    return fetch(endpoints.transactions + `/${id}`, {
        method: "put",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
    })
    .then(res => ({ status: res.status }))
    .catch(error => console.error("Failed to update transaction", error));
}

export function deleteTransaction(id, token) {
    return fetch(endpoints.transactions + `/${id}`, {
        method: "delete",
        headers: { Authorization: `Bearer ${token}` },
    })
    .catch(error => console.error("Failed to delete transaction", error));
}