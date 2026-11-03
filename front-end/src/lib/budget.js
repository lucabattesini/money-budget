// Helpers for the budget page. A month is written "2026-11" (the same way the API does).
import { formatDate } from './locale'

/** The month a date falls in: "2026-11". */
export const monthKey = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`

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
 * How a category is going. Nothing planned has no bar. With a plan: "ok" until 80% of it is spent, "warn" from
 * 80% up to the plan itself, "over" once more than the plan was spent. `percent` is for the bar (never above 100).
 */
export function budgetStatus(spent, budgeted) {
  if (!budgeted) return { state: 'none', percent: 0 }
  const share = spent / budgeted
  const state = share > 1 ? 'over' : share >= WARNING_FROM ? 'warn' : 'ok'
  return { state, percent: Math.min(100, Math.round(share * 100)) }
}
