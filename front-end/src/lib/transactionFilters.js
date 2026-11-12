import { digitsToCents } from "./money";

// `counting`: "" every transaction, "left_out" only those left out of the totals, "counted" only the others
export const EMPTY_FILTERS = { search: "", category: "", type: "", person: "", merchant: "", counting: "", from: "", to: "", min: "", max: "" };

const isDay = (value) => /^\d{4}-\d{2}-\d{2}$/.test(value ?? "") && !Number.isNaN(new Date(`${value}T00:00:00`).getTime());

/** The filters a link asks for ("?from=2026-03-01&to=2026-03-31&type=debit"; every filter can be in the link); anything missing or invalid is left empty. */
export function filtersFromLink(search) {
    const params = new URLSearchParams(search);
    const day = (name) => (isDay(params.get(name)) ? params.get(name) : "");
    const type = params.get("type");
    const counting = params.get("counting");
    const amount = (name) => (/^[\d.,]{1,15}$/.test(params.get(name) ?? "") ? params.get(name) : "");
    const text = (name) => (params.get(name) ?? "").slice(0, 200);
    return {
        ...EMPTY_FILTERS,
        search: text("search"),
        category: /^\d{1,10}$/.test(params.get("category") ?? "") ? params.get("category") : "",
        person: /^\d{1,10}$/.test(params.get("person") ?? "") ? params.get("person") : "",
        merchant: /^\d{1,10}$/.test(params.get("merchant") ?? "") ? params.get("merchant") : "",
        counting: counting === "counted" || counting === "left_out" ? counting : "",
        from: day("from"),
        to: day("to"),
        min: amount("min"),
        max: amount("max"),
        type: type === "debit" || type === "credit" ? type : "",
    };
}

/** The other way round: the filters written into the address' parameters (empty ones are left out). */
export function writeFilters(params, filters) {
    const next = new URLSearchParams(params);
    Object.keys(EMPTY_FILTERS).forEach((name) => (filters[name] ? next.set(name, filters[name]) : next.delete(name)));
    return next;
}

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
        if (filters.merchant && String(transaction.merchant_id) !== filters.merchant) return false;
        if (filters.person && String(transaction.user_id) !== filters.person) return false;
        if (filters.type && (transaction.type ?? "debit") !== filters.type) return false;
        if (filters.counting === "left_out" && !transaction.excluded) return false;
        if (filters.counting === "counted" && transaction.excluded) return false;
        if (from && date < from) return false;
        if (to && date >= to) return false;
        if (min !== null && transaction.value < min) return false;
        if (max !== null && transaction.value > max) return false;
        return true;
    });
}
