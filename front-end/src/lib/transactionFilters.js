import { digitsToCents } from "./money";

export const EMPTY_FILTERS = { search: "", category: "", type: "", from: "", to: "", min: "", max: "" };

export function countActiveFilters(filters) {
    return Object.values(filters).filter((value) => value !== "").length;
}

export function hasActiveFilters(filters) {
    return countActiveFilters(filters) > 0;
}

// "2026-03-15" -> local midnight of that day (new Date("2026-03-15") would be UTC)
function startOfDay(isoDate, addDays = 0) {
    const [year, month, day] = isoDate.split("-").map(Number);
    return new Date(year, month - 1, day + addDays);
}

/**
 * Keep the transactions that match every filter that was set.
 * from/to are whole days and both inclusive; min/max are masked amounts ("12,50").
 */
export function applyFilters(transactions, filters) {
    const search = filters.search.trim().toLowerCase();
    const from = filters.from ? startOfDay(filters.from) : null;
    const to = filters.to ? startOfDay(filters.to, 1) : null; // the whole last day is included
    const min = filters.min ? digitsToCents(filters.min) : null;
    const max = filters.max ? digitsToCents(filters.max) : null;

    return transactions.filter((transaction) => {
        const date = new Date(transaction.transactioned_at);
        if (search && !(transaction.label ?? "").toLowerCase().includes(search)) return false;
        if (filters.category && String(transaction.category_id) !== filters.category) return false;
        if (filters.type && (transaction.type ?? "debit") !== filters.type) return false;
        if (from && date < from) return false;
        if (to && date >= to) return false;
        if (min !== null && transaction.value < min) return false;
        if (max !== null && transaction.value > max) return false;
        return true;
    });
}
