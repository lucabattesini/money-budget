import { API_URL } from "./config";
import { removeToken } from "../lib/auth";

const URL_BASE = API_URL;

export const endpoints = {
    categories: `${URL_BASE}/categories`,
    transactions: `${URL_BASE}/transactions`,
    exports: `${URL_BASE}/exports`,
    families: `${URL_BASE}/families`,
    user: `${URL_BASE}/user`,
    auth: `${URL_BASE}/auth`,
};

// An answer of 401 means the login is no longer valid: forget it and go to the login page.
// (The router listens to the address, so changing it is enough.)
function checkSession(res) {
    if (res.status === 401) {
        removeToken();
        window.location.hash = "#/login-google";
    }
    return res;
}

// Read calls: the data on success. An error answer throws, and the call's own catch logs it and
// resolves undefined, so an error answer is never taken for data.
function readJson(res) {
    checkSession(res);
    if (!res.ok) throw new Error(`Request failed with status ${res.status}`);
    return res.json();
}

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
    .then(readJson)
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
        checkSession(res);
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
    .then(readJson)
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
    .then(readJson)
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
    .then(readJson)
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
    .then(async res => {
        checkSession(res);
        const body = await res.json().catch(() => null);
        return { status: res.status, body };
    })
    .catch(error => {
        console.error("Failed to insert new transaction", error);
        return { status: 0, body: null }; // 0: the server could not be reached
    });
}

// ─── Exports (files built in the background) ──────────────────────────────────

// Queue an export. Resolves { ok: true, job } or { ok: false, status (HTTP, when the server answered) }.
export function createExport(format, token) {
    return fetch(endpoints.exports, {
        method: "post",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ format }),
    })
    .then(async res => (checkSession(res).ok ? { ok: true, job: (await res.json()).data } : { ok: false, status: res.status }))
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
    .then(async res => (checkSession(res).ok ? { ok: true, status: res.status, job: (await res.json()).data } : { ok: false, status: res.status }))
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
    .then(async res => (checkSession(res).ok ? { ok: true, blob: await res.blob() } : { ok: false }))
    .catch(error => {
        console.error("Failed to download export", error);
        return { ok: false };
    });
}

// ─── Families ─────────────────────────────────────────────────────────────────

// One call for every family endpoint. Resolves { ok: true, data } on success, { ok: false, status, detail } when the
// server answered with an error (detail is its message, to show the user), and { ok: false } when it cannot be reached.
function familyCall(path, method, token, body) {
    return fetch(endpoints.families + path, {
        method,
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: body === undefined ? undefined : JSON.stringify(body),
    })
    .then(async res => {
        checkSession(res);
        const json = await res.json().catch(() => ({}));
        return res.ok ? { ok: true, data: json.data } : { ok: false, status: res.status, detail: json.detail };
    })
    .catch(error => {
        console.error("Failed to call the family API", error);
        return { ok: false };
    });
}

export const getFamily = (token) => familyCall("/me", "get", token);
export const getInvites = (token) => familyCall("/invites", "get", token);
export const createInvite = (token) => familyCall("/invites", "post", token);
export const cancelInvite = (id, token) => familyCall(`/invites/${id}`, "delete", token);
export const returnToPreviousFamily = (token) => familyCall("/rollback", "post", token);
export const joinFamily = (code, bringData, token) => familyCall("/join", "post", token, { code, bring_data: bringData });

export function updateTransaction(id, payload, token) {
    return fetch(endpoints.transactions + `/${id}`, {
        method: "put",
        headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
    })
    .then(res => ({ status: checkSession(res).status }))
    .catch(error => console.error("Failed to update transaction", error));
}

export function deleteTransaction(id, token) {
    return fetch(endpoints.transactions + `/${id}`, {
        method: "delete",
        headers: { Authorization: `Bearer ${token}` },
    })
    .then(checkSession)
    .catch(error => console.error("Failed to delete transaction", error));
}