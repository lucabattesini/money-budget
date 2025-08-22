const URL_BASE = "http://127.0.0.1:8000";

export const endpoints ={
    categories: `${URL_BASE}/categories`,
    expenses: `${URL_BASE}/report-expense`,
    user: `${URL_BASE}/user`
};

export function getAllCategories() {
    return fetch(endpoints.categories, {
            method: "get"
            })
            .then(Response => Response.json())

            .catch(error => console.error("Failed to get categories", error))
};

export function getAddedTransactionsByCategory() {
    return fetch(endpoints.expenses + "/added-by-category", {
        method: "get"
    })
    .then(Response => Response.json())

    .catch(error => console.error("Failed to get added categories", error))
};

export function getAllTransactions() {
    return fetch(endpoints.expenses, {
        method: "get"
    })
    .then(Response => Response.json())

    .catch(error => console.error("Failed to get transactions", error))
};

export function insertNewTransaction(payload) {
    return fetch(endpoints.expenses, {
        method: "post",
        headers: {
                "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
    })
    .then(res => {
        if (!res.ok) throw new Error("Error to request");
        return res.json
    })

    .catch(error => console.error("Failed to insert new transaction", error))
};

export function createUser(userInfo) {
    return fetch(endpoints.user, {
        method: "post",
        headers: {
            "Content-type": "application/json"
        },
        body: JSON.stringify(userInfo)
    })
    .then(res => {
        if (!res.ok) throw new Error("Error to request");
        return res.json
    })
    .catch(error => console.error("Failed to create user", error))
};