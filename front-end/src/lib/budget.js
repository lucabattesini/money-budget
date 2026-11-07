// Helpers for the budget page. A month is written "2026-11" (the same way the API does).
import { formatDate } from './locale'

/** The month a date falls in: "2026-11". */
export const monthKey = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`

// The server offers the years 2000 to 2099
export const FIRST_MONTH = '2000-01'
export const LAST_MONTH = '2099-12'

/** A month from a link ("?month=2026-03"): that month, or `fallback` when it is missing or not one the server offers. */
export function monthFromLink(value, fallback) {
  return /^\d{4}-(0[1-9]|1[0-2])$/.test(value ?? '') && value >= FIRST_MONTH && value <= LAST_MONTH ? value : fallback
}

/** The first and last day of a month, as the date filters write them: "2026-02" -> { from: "2026-02-01", to: "2026-02-28" }. */
export function monthDays(key) {
  const [year, month] = key.split('-').map(Number)
  const last = new Date(year, month, 0).getDate()
  return { from: `${key}-01`, to: `${key}-${String(last).padStart(2, '0')}` }
}

/** The budgets page, opened on that month. */
export const budgetsLink = (key) => `/budgets?month=${key}`

/** The transactions page with the days of that month already filtered, and optionally only debits or credits. */
export function transactionsLink(key, type) {
  const { from, to } = monthDays(key)
  return `/transactions?from=${from}&to=${to}${type ? `&type=${type}` : ''}`
}

/** "2026-12" + 1 -> "2027-01"; -1 goes back. */
export function shiftMonth(key, delta) {
  const [year, month] = key.split('-').map(Number)
  return monthKey(new Date(year, month - 1 + delta, 1))
}

/** "2026-11" -> "novembro de 2026" (or "November 2026" in English), in the family's language. */
export function monthLabel(key) {
  const [year, month] = key.split('-').map(Number)
  return formatDate(new Date(year, month - 1, 1), { month: 'long', year: 'numeric' })
}

// Share of the plan from which the bar warns that the limit is near
export const WARNING_FROM = 0.8

/**
 * How a category is going. No plan (null) has no bar. With a plan, 0 included: "ok" until 80% of it is spent, "warn"
 * from 80% up to just under the plan, "limit" when exactly the plan was spent (still within it), "over" once more than
 * the plan was spent. `percent` is for the bar (never above 100).
 */
export function budgetStatus(spent, budgeted) {
  if (budgeted == null) return { state: 'none', percent: 0 }
  if (budgeted === 0) return spent > 0 ? { state: 'over', percent: 100 } : { state: 'limit', percent: 0 }
  const share = spent / budgeted
  const state = share > 1 ? 'over' : share === 1 ? 'limit' : share >= WARNING_FROM ? 'warn' : 'ok'
  return { state, percent: Math.min(100, Math.round(share * 100)) }
}

/** Whether any category of the month has a plan. 0 counts: it is a plan to spend nothing. */
export const hasPlan = (data) => data.groups.some((g) => g.categories.some((c) => c.budgeted != null))
