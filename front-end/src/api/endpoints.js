const URL_BASE = `${import.meta.env.VITE_API_URL}`

export const endpoints = {
    categories: `${URL_BASE}/categories`,
    transactions: `${URL_BASE}/transactions`,
    user: `${URL_BASE}/user`,
    auth: `${URL_BASE}/auth`,
};

// ─── Auth ────────────────────────────────────────────────────────────────────

export function loginWithGoogle(idToken) {
    return fetch(endpoints.auth + "/google", {
        method: "post",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id_token: idToken }),
    })
    .then(res => {
        if (!res.ok) throw new Error("Google auth failed");
        return res.json();
    })
    .catch(error => console.error("Failed to login with Google", error));
}

export function getMe(token) {
    return fetch(endpoints.user + "/me", {
        method: "get",
        headers: { Authorization: `Bearer ${token}` },
    })
    .then(res => res.json())
    .catch(error => console.error("Failed to get current user", error));
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

export function deleteTransaction(id, token) {
    return fetch(endpoints.transactions + `/${id}`, {
        method: "delete",
        headers: { Authorization: `Bearer ${token}` },
    })
    .catch(error => console.error("Failed to delete transaction", error));
}