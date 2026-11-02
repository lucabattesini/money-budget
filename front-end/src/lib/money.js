// Money helpers. The API stores amounts as integer cents; the UI shows reais as
// "R$ 1.234,50": always two digits after the comma, "." between thousands.

const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const plain = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

/** 2550 -> "R$ 25,50" */
export function formatCents(cents) {
  return brl.format((cents || 0) / 100).replace(/\s/g, ' ')
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
 * "2550" -> "25,50", "5" -> "0,05", "123456789" -> "1.234.567,89"
 */
export function maskAmount(text) {
  const typed = String(text ?? '')
  if (!/\d/.test(typed)) return ''
  let cents = digitsToCents(typed)
  while (cents > MAX_CENTS) cents = Math.floor(cents / 10) // drop the digit that went over the limit
  return plain.format(cents / 100)
}
