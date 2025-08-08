
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

            .catch(error => console.error("Failed to search categories", error))
};