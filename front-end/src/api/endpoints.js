import { API_URL } from "./config";
import { removeToken } from "../lib/auth";

const URL_BASE = API_URL;

export const endpoints = {
    categories: `${URL_BASE}/categories`,
    transactions: `${URL_BASE}/transactions`,
    exports: `${URL_BASE}/exports`,
    imports: `${URL_BASE}/imports`,
    families: `${URL_BASE}/families`,
    budgets: `${URL_BASE}/budgets`,
    merchants: `${URL_BASE}/merchants`,
    user: `${URL_BASE}/user`,
    auth: `${URL_BASE}/auth`,
    oauth: `${URL_BASE}/oauth`,
    connections: `${URL_BASE}/connections`,
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

// ─── Imports (a spreadsheet of transactions, in steps) ────────────────────────

// Calls that can answer with the list of rows with something wrong. Resolves { ok: true, data: job } or
// { ok: false, status, detail, problems ([{ row, message }]), problemsTotal } and { ok: false } when it cannot be reached.
function importProblemsCall(url, options, what) {
    return fetch(url, options)
    .then(async res => {
        checkSession(res);
        const json = await res.json().catch(() => ({}));
        return res.ok
            ? { ok: true, data: json.data }
            : { ok: false, status: res.status, detail: json.detail, problems: json.problems ?? [], problemsTotal: json.problems_total ?? 0 };
    })
    .catch(error => {
        console.error(`Failed to ${what}`, error);
        return { ok: false };
    });
}

// Step 1: send the file. The server reads it and answers with its columns, a suggestion of which is which and a few rows.
export function uploadImport(file, token) {
    const body = new FormData();
    body.append("file", file);
    return importProblemsCall(
        endpoints.imports,
        {
            method: "POST",
            headers: { Authorization: `Bearer ${token}` }, // no Content-Type: the browser adds it, with the form boundary
            body,
        },
        "upload import",
    );
}

// Step 2: which column of the file holds each field ({ "Data": 0, "Valor": 3, "Tipo": null }) and how it is written:
// formats = { dateOrder: "auto" | "day_first" | "month_first", amountStyle: "auto" | "br" | "us",
// sign: "type_column" | "negative_debit" | "negative_credit" }. The server then checks every row the way the person said,
// and answers 422 with the problems if any is wrong.
export const matchImportColumns = (id, mapping, formats, token) =>
    importProblemsCall(
        endpoints.imports + `/${id}/columns`,
        {
            method: "PUT",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
            body: JSON.stringify({ mapping, date_order: formats.dateOrder, amount_style: formats.amountStyle, sign: formats.sign }),
        },
        "match import columns",
    );

export const getImport = (id, token) => jsonCall(endpoints.imports + `/${id}`, "get", token);
// Step 3: which category of the family each category name of the file stands for ({ "Pets": 12 }).
export const chooseImportCategories = (id, mapping, token) => jsonCall(endpoints.imports + `/${id}/categories`, "put", token, { mapping });
// Step 4: queue the import. It is saved in the background.
export const chooseImportPeople = (id, mapping, token) => jsonCall(endpoints.imports + `/${id}/people`, "put", token, { mapping });
export const startImport = (id, token) => jsonCall(endpoints.imports + `/${id}/start`, "post", token);
export const cancelImport = (id, token) => jsonCall(endpoints.imports + `/${id}`, "delete", token);

// ─── Families ─────────────────────────────────────────────────────────────────

// One call for the endpoints that answer with a message people can read. Resolves { ok: true, data } on success,
// { ok: false, status, detail } when the server answered with an error (detail is its message, to show the user),
// and { ok: false } when it cannot be reached.
function jsonCall(url, method, token, body) {
    return fetch(url, {
        // Upper case on purpose: a browser only fixes the case of GET, POST, PUT and DELETE. A lower case "patch" is sent
        // as it is and the server refuses it in the CORS check, so the call never reaches the API.
        method: method.toUpperCase(),
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: body === undefined ? undefined : JSON.stringify(body),
    })
    .then(async res => {
        checkSession(res);
        const json = await res.json().catch(() => ({}));
        return res.ok ? { ok: true, data: json.data } : { ok: false, status: res.status, detail: json.detail };
    })
    .catch(error => {
        console.error(`Failed to call ${method} ${url}`, error);
        return { ok: false };
    });
}

const familyCall = (path, method, token, body) => jsonCall(endpoints.families + path, method, token, body);

// ─── Managing categories ──────────────────────────────────────────────────────

export const getCategoryGroups = (token) => jsonCall(endpoints.categories + "/groups", "get", token);
export const createCategory = (payload, token) => jsonCall(endpoints.categories, "post", token, payload);
export const updateCategory = (id, payload, token) => jsonCall(endpoints.categories + `/${id}`, "patch", token, payload);
export const deleteCategory = (id, token) => jsonCall(endpoints.categories + `/${id}`, "delete", token);

// ─── Merchants (an optional setting of the family) ────────────────────────────

export const getMerchants = (token) => jsonCall(endpoints.merchants, "get", token);
export const renameMerchant = (id, name, token) => jsonCall(endpoints.merchants + `/${id}`, "patch", token, { name });
export const deleteMerchant = (id, token) => jsonCall(endpoints.merchants + `/${id}`, "delete", token);

// ─── AI apps (the Claude connector) ───────────────────────────────────────────

// The person's answer to an app that asks for access. Resolves with the address to send them to next.
export const decideConnection = (decision, token) => jsonCall(endpoints.oauth + "/authorize", "post", token, decision);
export const getConnections = (token) => jsonCall(endpoints.connections, "get", token);
export const disconnectApp = (id, token) => jsonCall(endpoints.connections + `/${id}`, "delete", token);

// ─── Budgets ──────────────────────────────────────────────────────────────────

export const getBudgets = (month, token) => jsonCall(endpoints.budgets + `?month=${encodeURIComponent(month)}`, "get", token);
export const setBudget = (categoryId, month, amount, token) =>
    jsonCall(endpoints.budgets, "put", token, { category_id: categoryId, month, amount });
export const getFamily = (token) => familyCall("/me", "get", token);
export const updateFamilySettings = (settings, token) => familyCall("/me/settings", "patch", token, settings);
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