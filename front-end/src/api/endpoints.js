
const URL_BASE = "http://127.0.0.1:8000";

export const endpoints ={
    categories: `${URL_BASE}/categories`,
    expenses: `${URL_BASE}/report-expense`
};

export function getAllCategories() {
    return fetch(endpoints.categories, {
            method: "get"
            })
            .then(Response => Response.json())

            .catch(error => console.error("Failed to get categories", error))
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

export function getAllTransactions() {
    return fetch(endpoints.expenses, {
        method: "get"
    })
    .then(Response => Response.json())

    .catch(error => console.error("Failed to get transactions", error))
}