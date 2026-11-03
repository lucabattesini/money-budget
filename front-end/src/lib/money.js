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
