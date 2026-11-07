// Money helpers. The API stores amounts as integer cents; the UI shows them in the family's currency and language
// (see locale.js), always with two decimals: "R$ 1.234,50" in Portuguese, "R$1,234.50" in English.
import { formatMoney, languageTag } from './locale'

const plain = () => new Intl.NumberFormat(languageTag(), { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** 2550 -> "R$ 25,50" */
export function formatCents(cents) {
  return formatMoney((cents || 0) / 100)
}

/** Digits the user typed -> cents (typing "2", "5", "5", "0" gives 2550). */
export function digitsToCents(text) {
  const digits = String(text ?? '').replace(/\D/g, '')
  return digits === '' ? 0 : parseInt(digits, 10)
}

// The database column is a 32-bit integer
export const MAX_CENTS = 2147483647

/**
 * Input mask: whatever the user types, keep only the digits and show them as an
 * amount with two decimals. Nothing typed stays empty so the placeholder shows.
 * "2550" -> "25,50", "5" -> "0,05", "123456789" -> "1.234.567,89" (in English: "25.50", "1,234,567.89")
 */
export function maskAmount(text) {
  const typed = String(text ?? '')
  if (!/\d/.test(typed)) return ''
  let cents = digitsToCents(typed)
  while (cents > MAX_CENTS) cents = Math.floor(cents / 10) // drop the digit that went over the limit
  return plain().format(cents / 100)
}

// --- Budget amounts: whole units first, decimals only when the person wants them ---

/** 150000 -> "R$ 1.500" (whole amounts have no decimals), 150050 -> "R$ 1.500,50". */
export function formatBudgetCents(cents) {
  const value = (cents || 0) / 100
  return formatMoney(value, isWhole(cents) ? { minimumFractionDigits: 0, maximumFractionDigits: 0 } : {})
}

const isWhole = (cents) => (cents || 0) % 100 === 0

/** The decimal separator of the family's language: "," in Portuguese, "." in English. */
export const decimalSeparator = () => new Intl.NumberFormat(languageTag()).formatToParts(1.1).find((p) => p.type === 'decimal').value

/** A saved amount in the field when it is not being edited, without the symbol (it sits beside the field): 150000 -> "1.500", 150050 -> "1.500,50". */
export function budgetFieldText(cents) {
  if (cents == null) return '' // no plan: an empty field; 0 is a plan and shows as "0"
  return new Intl.NumberFormat(languageTag(), isWhole(cents) ? { maximumFractionDigits: 0 } : { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(cents / 100)
}

/** A saved amount to be edited, with no thousands separators: 150000 -> "1500", 150050 -> "1500,50". */
export function budgetEditText(cents) {
  if (cents == null) return ''
  const reais = Math.floor(cents / 100)
  const rest = cents % 100
  return rest === 0 ? String(reais) : `${reais}${decimalSeparator()}${String(rest).padStart(2, '0')}`
}

// The most whole units a budget can hold: 21.474.835 reais, so even with 99 cents it fits the 32-bit column
const MAX_REAIS = 21474835

/**
 * What the person types in a budget field: digits, and optionally a decimal separator ("," or ".") with up to two
 * digits after it. Anything else is dropped. The last separator is the decimal one, the ones before it are thousands
 * separators ("1.500,00" -> "1500,00"); a separator followed by exactly three digits is a thousands separator too when it comes after one to three
 * digits or after another separator ("1.500" -> "1500", "1,500" -> "1500"). "0,5" and ",5" are both fine as typed.
 */
export function sanitizeBudgetText(text) {
  const typed = String(text ?? '').replace(/[^\d.,]/g, '')
  const at = Math.max(typed.lastIndexOf('.'), typed.lastIndexOf(','))
  let whole = (at === -1 ? typed : typed.slice(0, at)).replace(/\D/g, '').replace(/^0+(?=\d)/, '')
  let decimals = at === -1 ? null : typed.slice(at + 1)
  if (decimals !== null && decimals.length === 3 && /^[1-9]\d*$/.test(whole) && (whole.length <= 3 || /[.,]/.test(typed.slice(0, at)))) {
    whole += decimals // "1.500": a thousands separator
    decimals = null
  }
  while (Number(whole) > MAX_REAIS) whole = whole.slice(0, -1)
  return decimals === null ? whole : `${whole}${decimalSeparator()}${decimals.slice(0, 2)}`
}

/** Typed budget text -> cents: "1500" -> 150000, "12,5" -> 1250, "0" -> 0 (a plan to spend nothing), "" -> null (no plan). Never above what the database holds. */
export function budgetTextToCents(text) {
  const clean = sanitizeBudgetText(text)
  if (!/\d/.test(clean)) return null // nothing, or only a separator: no plan
  const [reais = '', decimals = ''] = clean.split(decimalSeparator())
  const cents = (parseInt(reais || '0', 10) || 0) * 100 + parseInt(decimals.padEnd(2, '0') || '0', 10)
  return Math.min(cents, MAX_CENTS)
}
